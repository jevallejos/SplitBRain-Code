import asyncio
import importlib
import time
import config_parametros as cfg

# El nombre del módulo empieza por dígito: no admite `from 4_... import`.
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta

MIN_INVERSION_USDT = 2.0

# Motor de salidas Avellaneda-Stoikov (V6.0)
ESPERA_LLENADO_SEG = 30   # máx. espera a que la compra maker se llene
INTERVALO_AS_SEG = 2      # evaluar la física del mercado cada 2 segundos
_tareas_as = set()        # referencias fuertes: asyncio solo guarda referencias débiles a las tareas


async def ejecutar_orden_sniper(exchange, symbol, z_score):
    if cfg.MODO_PAPER:
        print("[PAPER TRADING] Ejecución simulada")
        return

    try:
        await exchange.load_markets()  # cacheado tras la 1ª llamada; necesario para *_to_precision

        # 1. Saldo libre y tamaño Kelly
        balance = await exchange.fetch_balance()
        libre = float(balance.get("USDT", {}).get("free") or 0)
        inversion = libre * cfg.KELLY_MAX_PCT
        minimo_mercado = exchange.market(symbol)["limits"]["cost"]["min"] or 0
        if inversion < max(MIN_INVERSION_USDT, minimo_mercado):
            raise ValueError(f"Inversión {inversion:.2f} USDT bajo el mínimo operable")

        # 2. Precio de disparo, siempre en lado maker (nunca cruzar el spread)
        ticker = await exchange.fetch_ticker(symbol)
        last, bid = ticker["last"], ticker["bid"]
        precio_ref = min(last, bid) if bid else last

        # 3. Precisión según las reglas del exchange
        price = exchange.price_to_precision(symbol, precio_ref)
        amount = exchange.amount_to_precision(symbol, inversion / float(price))
        precio_tp = exchange.price_to_precision(symbol, float(price) * (1 + cfg.TP_PCT))
        precio_sl = exchange.price_to_precision(symbol, float(price) * (1 - cfg.SL_PCT))

        # 4-5. Limit Maker estricto con SL de emergencia adjunto.
        # V6.0: el take-profit ya no se delega al exchange (precio_tp queda solo como referencia);
        # la salida la gestiona motor_salida_avellaneda_stoikov.
        params = {"timeInForce": "PostOnly", "stopLoss": str(precio_sl)}
        orden = await exchange.create_order(symbol, "limit", "buy", amount, price, params)
    except Exception as e:
        # Sin emojis en consola: en Windows (cp1252) provocan UnicodeEncodeError dentro del except.
        print(f"[SNIPER] ERROR ejecutando {symbol}: {type(e).__name__}: {e}")
        await enviar_alerta(f"🔴 ERROR Sniper {symbol}: {e}")  # silenciado por el filtro
        return

    await enviar_alerta(
        f"🟩 ALERTA VERDE (PROD):\nOrden Limit PostOnly en {symbol}\nPrecio: {price}\nID: {orden['id']}"
    )

    # Motor AS en segundo plano: no bloquea al Sniper.
    tarea = asyncio.create_task(motor_salida_avellaneda_stoikov(exchange, symbol, amount, price, orden["id"]))
    _tareas_as.add(tarea)
    tarea.add_done_callback(_tareas_as.discard)


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


async def _esperar_llenado_compra(exchange, symbol, id_compra):
    """Devuelve la cantidad realmente comprada (0 si no se llenó). Cancela el resto al expirar."""
    limite = time.time() + ESPERA_LLENADO_SEG
    while time.time() < limite:
        await asyncio.sleep(1)
        try:
            o = await _estado_orden(exchange, id_compra, symbol)
        except Exception:
            continue
        if o.get("status") in ("closed", "canceled", "rejected", "expired"):  # p. ej. PostOnly rechazado
            return float(o.get("filled") or 0)
    try:
        await exchange.cancel_order(id_compra, symbol)
    except Exception:
        pass  # ya llenada o cancelada
    try:
        return float((await _estado_orden(exchange, id_compra, symbol)).get("filled") or 0)
    except Exception as e:
        print(f"[{symbol}] AS: no se pudo confirmar el llenado de la compra: {type(e).__name__}: {e}")
        return 0.0


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
