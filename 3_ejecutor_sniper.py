import asyncio
import importlib
import re
import time
from decimal import ROUND_FLOOR, Decimal
from typing import Optional

import config_parametros as cfg

# El nombre del módulo empieza por dígito: no admite `from 4_... import`.
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta
_gestor_mod = importlib.import_module("5_gestor_posiciones")

MIN_INVERSION_USDT = 2.0  # margen mínimo por disparo

# Motor de salidas Avellaneda-Stoikov (V6.0)
ESPERA_LLENADO_SEG = 30   # máx. espera a que la compra maker se llene
INTERVALO_AS_SEG = 2      # evaluar la física del mercado cada 2 segundos
_tareas_as = set()        # referencias fuertes: asyncio solo guarda referencias débiles a las tareas

# V6.1
_en_vuelo: set[str] = set()              # pares con compra enviada y salida aún no entregada al gestor / AS
_apalancamiento_ok: set[str] = set()     # pares con set_leverage ya aplicado
_RE_BLACKLIST = re.compile(r"(?<!\d)(" + "|".join(cfg.CODIGOS_BLACKLIST) + r")(?!\d)")


def posicion_activa(symbol: str) -> bool:
    """True si el par tiene una compra en curso o una posición gestionada (trailing o AS)."""
    return symbol in _en_vuelo or _gestor_mod.gestor.tiene(symbol)


def _d(x) -> Decimal:
    return Decimal(str(x))


def cuantizar_orden(exchange, symbol: str, nocional: float, precio: float) -> Optional[tuple[str, str]]:
    """Smart quantization: cantidad = floor(nocional / precio) al step_size; precio con floor al tick_size.
    Devuelve (amount, price) formateados, o None si no alcanza min_qty / min_notional (sin llamar a la API)."""
    m = exchange.market(symbol)
    step = _d(m["precision"]["amount"])
    tick = _d(m["precision"]["price"])
    min_qty = _d(m["limits"]["amount"]["min"] or 0)
    min_notional = _d(m["limits"]["cost"]["min"] or 0)

    precio_q = (_d(precio) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    if precio_q <= 0:
        print(f"[FRANCOTIRADOR] Precio inválido en {symbol}: {precio}")
        return None
    cantidad = (_d(nocional) / precio_q / step).to_integral_value(rounding=ROUND_FLOOR) * step
    valor = cantidad * precio_q
    if cantidad <= 0 or cantidad < min_qty or valor < min_notional:
        print(f"[FRANCOTIRADOR] Munición insuficiente en {symbol}: {cantidad.normalize():f} x {precio_q.normalize():f} "
              f"= {valor:.4f} USDT (mín. {min_notional.normalize():f} USDT, mín. qty {min_qty.normalize():f}). Disparo abortado.")
        return None
    return exchange.amount_to_precision(symbol, float(cantidad)), exchange.price_to_precision(symbol, float(precio_q))


def _es_error_blacklist(e: Exception) -> bool:
    """Errores de permiso por símbolo (acuerdo sin firmar, compliance, whitelist). 10005 es de la API key: no cuenta."""
    texto = str(e)
    return bool(_RE_BLACKLIST.search(texto)) or "agreement" in texto.lower()


async def _fijar_apalancamiento(exchange, symbol: str) -> None:
    if symbol in _apalancamiento_ok:
        return
    try:
        await exchange.set_leverage(cfg.APALANCAMIENTO, symbol)
    except Exception as e:
        if "110043" not in str(e):  # 110043 = "leverage not modified": ya estaba fijado
            raise
    _apalancamiento_ok.add(symbol)


async def ejecutar_orden_sniper(exchange, symbol, z_score, ofi=None):
    if cfg.MODO_PAPER:
        print("[PAPER TRADING] Ejecución simulada")
        return
    if symbol in cfg.BLACKLIST_PAIRS or posicion_activa(symbol):
        print(f"[FRANCOTIRADOR] {symbol} no disparable (lista negra o posición activa).")
        return

    try:
        await exchange.load_markets()  # cacheado tras la 1ª llamada; necesario para *_to_precision

        # 1. Saldo libre y tamaño Kelly: margen = libre × Kelly; nocional = margen × apalancamiento
        balance = await exchange.fetch_balance()
        libre = float(balance.get("USDT", {}).get("free") or 0)
        inversion = libre * cfg.KELLY_MAX_PCT
        if inversion < MIN_INVERSION_USDT:
            print(f"[FRANCOTIRADOR] Munición insuficiente: margen {inversion:.2f} USDT < {MIN_INVERSION_USDT} USDT. Disparo abortado.")
            return
        nocional = inversion * cfg.APALANCAMIENTO

        # 2. Precio de disparo, siempre en lado maker (nunca cruzar el spread)
        ticker = await exchange.fetch_ticker(symbol)
        last, bid = ticker["last"], ticker["bid"]
        precio_ref = min(last, bid) if bid else last

        # 3. Smart quantization (step/tick/min_notional). Si no alcanza, aborta sin tocar la API de órdenes.
        cuantizado = cuantizar_orden(exchange, symbol, nocional, precio_ref)
        if cuantizado is None:
            return
        amount, price = cuantizado
        precio_tp = exchange.price_to_precision(symbol, float(price) * (1 + cfg.TP_PCT))
        precio_sl = exchange.price_to_precision(symbol, float(price) * (1 - cfg.SL_PCT))  # SL de catástrofe (-3 %)

        # 4-5. Limit Maker estricto con SL de emergencia adjunto.
        # V6.0: el take-profit ya no se delega al exchange (precio_tp queda solo como referencia);
        # la salida la gestiona el PositionManager (V6.1) o motor_salida_avellaneda_stoikov (V6.0).
        await _fijar_apalancamiento(exchange, symbol)
        params = {"timeInForce": "PostOnly", "stopLoss": str(precio_sl)}
        orden = await exchange.create_order(symbol, "limit", "buy", amount, price, params)
    except Exception as e:
        # Sin emojis en consola: en Windows (cp1252) provocan UnicodeEncodeError dentro del except.
        print(f"[FRANCOTIRADOR] ERROR ejecutando {symbol}: {type(e).__name__}: {e}")
        if _es_error_blacklist(e):
            cfg.BLACKLIST_PAIRS.add(symbol)
            print(f"[FRANCOTIRADOR] {symbol} a la lista negra dinámica (permiso/contrato). WebSocket liberado.")
        await enviar_alerta(f"🔴 ERROR Sniper {symbol}: {e}")  # silenciado por el filtro
        return

    await enviar_alerta(
        f"🟩 ALERTA VERDE (PROD):\nOrden Limit PostOnly en {symbol}\nPrecio: {price}\nID: {orden['id']}"
    )
    print(f"[FRANCOTIRADOR] Orden {orden['id']} en {symbol}: {amount} @ {price} (nocional ~{float(amount) * float(price):.2f} USDT, "
          f"{cfg.APALANCAMIENTO}x, Z={z_score:.2f}, OFI={ofi if ofi is None else round(ofi, 2)})")

    # Salida en segundo plano: no bloquea al Sniper.
    _en_vuelo.add(symbol)
    if cfg.MOTOR_SALIDA == "AS":
        tarea = asyncio.create_task(motor_salida_avellaneda_stoikov(exchange, symbol, amount, price, orden["id"]))
    else:
        tarea = asyncio.create_task(_entregar_al_gestor(exchange, symbol, orden["id"], price, z_score, ofi))
    _tareas_as.add(tarea)
    tarea.add_done_callback(_tareas_as.discard)
    tarea.add_done_callback(lambda _t: _en_vuelo.discard(symbol))


async def _entregar_al_gestor(exchange, symbol, id_compra, price, z_score, ofi):
    """Espera el llenado real de la compra y entrega la posición al PositionManager (V6.1)."""
    try:
        llenado, medio = await _esperar_llenado_detalle(exchange, symbol, id_compra)
        if llenado <= 0:
            print(f"[FRANCOTIRADOR] Compra en {symbol} no llenada: sin posición que gestionar.")
            return
        _gestor_mod.gestor.abrir(exchange, symbol, llenado, medio or float(price), z_score, ofi)
    except Exception as e:
        print(f"[FRANCOTIRADOR] ERROR entregando {symbol} al gestor: {type(e).__name__}: {e} "
              f"(la posición conserva el SL de Bybit)")


async def _estado_orden(exchange, order_id, symbol):
    # En cuentas UTA, fetch_order exige 'acknowledged' (accede a las últimas 500 órdenes).
    return await exchange.fetch_order(order_id, symbol, {"acknowledged": True})


async def _posicion_larga(exchange, symbol):
    """Tamaño de la posición larga abierta (0 si no hay). None si la API falla."""
    try:
        posiciones = await exchange.fetch_positions([symbol])
    except Exception as e:
        print(f"[{symbol}] AS: no se pudo leer la posición: {type(e).__name__}: {e}")
        return None
    total = 0.0
    for p in posiciones or []:
        if p.get("symbol") == symbol and p.get("side") == "long":
            total += float(p.get("contracts") or 0)
    return total


async def _esperar_llenado_detalle(exchange, symbol, id_compra) -> tuple[float, Optional[float]]:
    """(cantidad realmente comprada, precio medio). (0, None) si no se llenó. Cancela el resto al expirar."""
    def _resultado(o):
        medio = o.get("average") or o.get("price")
        return float(o.get("filled") or 0), (float(medio) if medio else None)

    limite = time.time() + ESPERA_LLENADO_SEG
    while time.time() < limite:
        await asyncio.sleep(1)
        try:
            o = await _estado_orden(exchange, id_compra, symbol)
        except Exception:
            continue
        if o.get("status") in ("closed", "canceled", "rejected", "expired"):  # p. ej. PostOnly rechazado
            return _resultado(o)
    try:
        await exchange.cancel_order(id_compra, symbol)
    except Exception:
        pass  # ya llenada o cancelada
    try:
        return _resultado(await _estado_orden(exchange, id_compra, symbol))
    except Exception as e:
        print(f"[{symbol}] AS: no se pudo confirmar el llenado de la compra: {type(e).__name__}: {e}")
        return 0.0, None


async def _esperar_llenado_compra(exchange, symbol, id_compra):
    """Devuelve la cantidad realmente comprada (0 si no se llenó). Cancela el resto al expirar."""
    return (await _esperar_llenado_detalle(exchange, symbol, id_compra))[0]


async def motor_salida_avellaneda_stoikov(exchange, symbol, amount, entry_price, id_compra=None):
    try:
        # Fase 0: no gestionar salida hasta tener posición real (evita abrir cortos).
        if id_compra is not None:
            amount = await _esperar_llenado_compra(exchange, symbol, id_compra)
            if amount <= 0:
                print(f"[{symbol}] AS: compra no llenada; no hay posición que gestionar.")
                return

        entry = float(entry_price)
        tiempo_inicio = time.time()
        precio_objetivo_max = entry * (1 + cfg.TP_PCT)
        p_minimo_rentable = entry * 1.002  # Spread mínimo para asegurar rentabilidad neta (0.2%)
        salida = {"timeInForce": "PostOnly", "reduceOnly": True}  # reduceOnly: jamás abre un corto

        # Orden Limit (Ask) inicial con el TP máximo exigido
        try:
            p_exit_format = exchange.price_to_precision(symbol, precio_objetivo_max)
            orden_venta = await exchange.create_order(symbol, "limit", "sell", amount, float(p_exit_format), salida)
            precio_orden_actual = float(p_exit_format)  # Bybit no devuelve el precio al crear
        except Exception as e:
            print(f"[{symbol}] Error AS inicial: {type(e).__name__}: {e}")
            return

        restante = float(amount)
        while True:
            await asyncio.sleep(INTERVALO_AS_SEG)
            tiempo_hold = time.time() - tiempo_inicio

            # 1. Liquidación forzada (anti-zombie): se evalúa PRIMERO y por tiempo, aunque la API falle.
            if tiempo_hold >= cfg.TIEMPO_MAX_HOLD_SEG:
                try:
                    await exchange.cancel_order(orden_venta["id"], symbol)
                except Exception:
                    pass  # ya llenada/cancelada
                posicion = await _posicion_larga(exchange, symbol)
                if posicion is not None:
                    restante = posicion
                try:
                    if restante > 0:
                        cantidad = exchange.amount_to_precision(symbol, restante)
                        await exchange.create_order(symbol, "market", "sell", cantidad, None, {"reduceOnly": True})
                        await enviar_alerta(f"🟩 [ESCAPE TEMPORAL] {symbol} liquidado a mercado tras "
                                            f"{int(tiempo_hold)}s para liberar liquidez.")
                except Exception as e:
                    print(f"[{symbol}] AS: fallo en la liquidación a mercado: {type(e).__name__}: {e}")
                break  # siempre sale: reduceOnly + SL de emergencia cubren el resto

            try:
                check_order = await _estado_orden(exchange, orden_venta["id"], symbol)
                estado = check_order.get("status")

                if estado == "closed":
                    precio_final = check_order.get("average") or check_order.get("price")
                    await enviar_alerta(f"🟩 [EXITO AS] {symbol} liquidado pasivamente a {precio_final}. Ganancia Asegurada.")
                    break

                ticker = await exchange.fetch_ticker(symbol)
                p_mid = float(ticker["last"])

                # Ecuación AS: Descuento dinámico del precio exigido por riesgo temporal (inventario radiactivo)
                decaimiento = cfg.GAMMA_AS * (tiempo_hold / cfg.TIEMPO_MAX_HOLD_SEG) * entry
                p_exit_dinamico = precio_objetivo_max - decaimiento

                if estado in ("canceled", "rejected", "expired"):
                    # ¿La cerró el SL (fin) o se cayó la venta (PostOnly rechazado / reajuste a medias)?
                    posicion = await _posicion_larga(exchange, symbol)
                    if posicion is None:
                        continue  # API caída: el anti-zombie actuará por tiempo
                    if posicion <= 0:
                        print(f"[{symbol}] AS: posición cerrada externamente (SL); fin del motor.")
                        break
                    restante = posicion
                    p_reponer = max(p_exit_dinamico, p_minimo_rentable)
                    p_exit_format = exchange.price_to_precision(symbol, p_reponer)
                    orden_venta = await exchange.create_order(symbol, "limit", "sell", restante, float(p_exit_format), salida)
                    precio_orden_actual = float(p_exit_format)
                    continue

                restante = float(check_order.get("remaining") or restante)

                # 2. Reajuste de Limit Order (Persiguiendo el precio)
                p_exit_format = exchange.price_to_precision(symbol, p_exit_dinamico)
                if precio_orden_actual > float(p_exit_format) and p_exit_dinamico > p_mid and p_exit_dinamico > p_minimo_rentable:
                    await exchange.cancel_order(orden_venta["id"], symbol)
                    orden_venta = await exchange.create_order(symbol, "limit", "sell", restante, float(p_exit_format), salida)
                    precio_orden_actual = float(p_exit_format)
            except Exception as e:
                # Error transitorio de la API: el bucle sigue y el anti-zombie va por tiempo.
                print(f"[{symbol}] AS transitorio: {type(e).__name__}: {e}")
    except Exception as e:
        # Última red: el motor jamás tumba el bot (el SL de emergencia sigue en Bybit).
        print(f"[{symbol}] AS abortado: {type(e).__name__}: {e}")
