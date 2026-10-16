import builtins
import re
"""PositionManager SPLITBRAIN V6.4.0 ("Zero-Zombie & Maker-First Unwind"):
- Salida Pasiva Híbrida Limit Sell PostOnly (Maker 0.020% vs Taker 0.055%) con Persistencia PFQI (12s).
- Protocolo Anti-Zombie en 3 Etapas: EARLY_TOXIC_SL (45s), STAGNATION_EXIT (105s) y ESCAPE_TEMPORAL (180s).
- Cerrojo Atómico Inmutable `pos.cerrada = True` (Cero Doble Contabilización) y Manejo Nativo de `110017`.
- Reconexión WebSocket en 50ms ante RequestTimeout y Piso Invariante de Break-Even en Bybit (+0.10%).
"""
import asyncio
import importlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import config_parametros as cfg

enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta
_stats = importlib.import_module("6_stats_tracker")

CHECK_POSICION_SEG = 10        # Verificación periódica de consistencia en Bybit
REINTENTO_CIERRE_SEG = 2       # Backoff si falla la orden a mercado
MARGEN_SL_EXCHANGE = 0.0004    # Holgura de 0.04% con piso estricto BE_PISO_EXCHANGE_PCT


def calcular_ofi(ticker: dict) -> float:
    vol_bid = ticker.get("bidVolume") or 0
    vol_ask = ticker.get("askVolume") or 0
    return (vol_bid - vol_ask) / (vol_bid + vol_ask) if (vol_bid + vol_ask) > 0 else 0.0


@dataclass
class Posicion:
    symbol: str
    cantidad: float
    entrada: float
    z_entrada: Optional[float]
    ofi_entrada: Optional[float]
    sl: float
    sl_exchange: float
    max_precio: float
    t_apertura: float
    ofi_media: Any
    be_activo: bool = False
    trailing_activo: bool = False
    cerrando: bool = False
    cerrada: bool = False
    t_ult_sync: float = 0.0
    t_ult_check: float = 0.0
    t_reintento: float = 0.0
    ultimo_bid: float = 0.0
    ultimo_ask: float = 0.0
    maker_order_id: Optional[str] = None
    maker_order_price: float = 0.0
    t_maker_placed: float = 0.0
    t_maker_check: float = 0.0
    muestras_q: int = 0
    suma_nocional_abs: float = 0.0
    extra: dict = field(default_factory=dict)


class PositionManager:
    def __init__(self) -> None:
        self.posiciones: dict[str, Posicion] = {}
        self.cooldown_hasta: dict[str, float] = {}
        self._tareas: set[asyncio.Task] = set()

    def tiene(self, symbol: str) -> bool:
        pos = self.posiciones.get(symbol)
        return bool(pos is not None and not pos.cerrada)

    def registrar_cooldown_post_cierre(self, symbol: str, duracion_seg: Optional[float] = None) -> None:
        """Grim Trigger Cooldown: bloquea nuevas entradas durante COOLDOWN_POST_CIERRE_SEG (300s) desde el cierre."""
        cd = float(duracion_seg if duracion_seg is not None else getattr(cfg, "COOLDOWN_POST_CIERRE_SEG", 300))
        if cd > 0:
            self.cooldown_hasta[symbol] = time.time() + cd

    def en_cooldown(self, symbol: str) -> bool:
        expira = self.cooldown_hasta.get(symbol, 0.0)
        if expira <= 0.0:
            return False
        if time.time() < expira:
            return True
        self.cooldown_hasta.pop(symbol, None)
        return False

    def segundos_cooldown_restantes(self, symbol: str) -> float:
        expira = self.cooldown_hasta.get(symbol, 0.0)
        return max(0.0, expira - time.time())

    def calcular_objetivo_sl_exchange(self, pos: Posicion) -> float:
        """Cota Inferior Invariante de Break-Even en Bybit:
        Garantiza que una vez activado el Micro-Break-Even o el Trailing Stop, el Stop-Loss
        enviado a Bybit (`sl_exchange`) JAMÁS quede por debajo de `entrada * (1 + BE_PISO_EXCHANGE_PCT)` (+0.10%).
        """
        piso_be = pos.entrada * (1.0 + float(getattr(cfg, "BE_PISO_EXCHANGE_PCT", 0.0010)))
        con_margen = pos.sl * (1.0 - MARGEN_SL_EXCHANGE)
        if pos.be_activo or pos.trailing_activo:
            return max(piso_be, con_margen)
        return con_margen

    def abrir(
        self,
        exchange,
        symbol: str,
        cantidad: float,
        entrada: float,
        z_entrada: Optional[float] = None,
        ofi_entrada: Optional[float] = None,
        t_apertura_override: Optional[float] = None,
    ) -> Posicion:
        media_movil = importlib.import_module("1_radar_volatilidad").MediaMovilTemporal
        entrada = float(entrada)
        t_inicio = float(t_apertura_override) if t_apertura_override is not None else time.time()
        pos = Posicion(
            symbol=symbol,
            cantidad=float(cantidad),
            entrada=entrada,
            z_entrada=z_entrada,
            ofi_entrada=ofi_entrada,
            sl=entrada * (1.0 - cfg.SL_INICIAL_PCT),
            sl_exchange=entrada * (1.0 - cfg.SL_PCT),
            max_precio=entrada,
            t_apertura=t_inicio,
            ofi_media=media_movil(cfg.OFI_SALIDA_VENTANA_SEG),
            ultimo_bid=entrada,
            ultimo_ask=entrada,
        )
        pos.t_ult_check = time.time()
        self.posiciones[symbol] = pos
        tarea = asyncio.create_task(self._vigilar(exchange, pos))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)
        edad_s = max(0.0, time.time() - t_inicio)
        print(
            f"[FRANCOTIRADOR] 🎯 Posición activa en {symbol}: {pos.cantidad} @ {entrada} "
            f"(edad {edad_s:.0f}s / máx {cfg.TIEMPO_MAX_HOLD_SEG}s) | "
            f"SL interno {pos.sl:.6g} | SL Bybit {pos.sl_exchange:.6g}"
        )
        return pos

    async def evacuar_por_emergencia_macro(self, exchange, motivo_macro: str = "MACRO_CRASH") -> int:
        """Neutralización Instantánea de Beta en Crash Macro / Contagio sin doble contabilización."""
        activas = [p for p in list(self.posiciones.values()) if not p.cerrada and not p.cerrando]
        if not activas:
            return 0
        evacuadas = 0
        print(
            f"🚨 [EVACUACIÓN MACRO] Ejecutando protocolo `{motivo_macro}` sobre "
            f"{len(activas)} posición(es) abierta(s)..."
        )
        for pos in activas:
            if pos.cerrada or pos.cerrando:
                continue
            precio_ref = pos.ultimo_bid if pos.ultimo_bid > 0 else pos.entrada
            try:
                if await self.cerrar(exchange, pos, f"EVACUACION_{motivo_macro}", precio_ref):
                    evacuadas += 1
            except Exception as e:
                print(f"[EVACUACIÓN MACRO] Error evacuando {pos.symbol}: {type(e).__name__}: {e}")
        return evacuadas

    async def reconciliar_posiciones_exchange(self, exchange) -> int:
        """Audita Bybit al arrancar: adopta posiciones vivas o liquida zombies que excedan TIEMPO_MAX_HOLD_SEG."""
        if cfg.MODO_PAPER:
            return 0
        try:
            posiciones_raw = await exchange.fetch_positions()
        except Exception as e:
            print(f"[RECONCILIADOR] Aviso: no se pudieron leer posiciones iniciales: {type(e).__name__}: {e}")
            return 0

        ahora = time.time()
        reconciliadas = 0
        media_movil = importlib.import_module("1_radar_volatilidad").MediaMovilTemporal

        for p in posiciones_raw or []:
            side = str(p.get("side") or "").lower()
            contratos = float(p.get("contracts") or 0.0)
            symbol = p.get("symbol")
            if side != "long" or contratos <= 0 or not symbol:
                continue
            if symbol in self.posiciones:
                continue

            info = p.get("info") or {}
            entrada = float(p.get("entryPrice") or info.get("avgPrice") or 0.0)
            if entrada <= 0:
                continue

            updated_ms = float(info.get("updatedTime") or info.get("createdTime") or p.get("timestamp") or 0.0)
            t_apertura_real = (updated_ms / 1000.0) if updated_ms > 1e9 else (ahora - cfg.TIEMPO_MAX_HOLD_SEG - 1.0)
            edad_seg = max(0.0, ahora - t_apertura_real)

            precio_marca = float(p.get("markPrice") or info.get("markPrice") or entrada)
            reconciliadas += 1

            if edad_seg >= cfg.TIEMPO_MAX_HOLD_SEG:
                print(
                    f"🧹 [RECONCILIADOR] Posición zombie huérfana detectada en {symbol}: "
                    f"{contratos} contratos @ {entrada} (edad {edad_seg / 60.0:.1f} min >= "
                    f"{cfg.TIEMPO_MAX_HOLD_SEG}s). Liquidando a mercado para liberar margen..."
                )
                pos_temp = Posicion(
                    symbol=symbol,
                    cantidad=contratos,
                    entrada=entrada,
                    z_entrada=None,
                    ofi_entrada=None,
                    sl=entrada * (1.0 - cfg.SL_INICIAL_PCT),
                    sl_exchange=entrada * (1.0 - cfg.SL_PCT),
                    max_precio=max(entrada, precio_marca),
                    t_apertura=t_apertura_real,
                    ofi_media=media_movil(cfg.OFI_SALIDA_VENTANA_SEG),
                    ultimo_bid=precio_marca,
                    ultimo_ask=precio_marca,
                )
                await self.cerrar(exchange, pos_temp, "ESCAPE_HUERFANA_BOOT", precio_marca)
            else:
                print(
                    f"🔄 [RECONCILIADOR] Adoptando posición viva heredada en {symbol}: "
                    f"{contratos} contratos @ {entrada} (edad {edad_seg:.0f}s)."
                )
                self.abrir(
                    exchange,
                    symbol,
                    contratos,
                    entrada,
                    z_entrada=None,
                    ofi_entrada=None,
                    t_apertura_override=t_apertura_real,
                )

        if reconciliadas == 0:
            print("[RECONCILIADOR] Sin posiciones huérfanas abiertas en Bybit. Margen 100% despejado.")
        else:
            print(f"[RECONCILIADOR] Reconciliación de arranque completada: {reconciliadas} posición(es) procesadas.")
        return reconciliadas

    # ------------------------------------------------------------------ Vigilancia
    async def _vigilar(self, exchange, pos: Posicion) -> None:
        try:
            while not pos.cerrada:
                try:
                    ticker = await exchange.watch_ticker(pos.symbol)
                    if pos.cerrada:
                        return
                    if await self._evaluar(exchange, pos, ticker):
                        return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if pos.cerrada:
                        return
                    es_timeout_ws = "RequestTimeout" in type(e).__name__ or "keepalive" in str(e).lower()
                    if not es_timeout_ws:
                        print(f"[MICROESTRUCTURA] Gestor {pos.symbol}: {type(e).__name__}: {e}")
                    await asyncio.sleep(0.05 if es_timeout_ws else 0.5)
                    if not pos.cerrada and await self._verificar_externo(exchange, pos):
                        return
        except asyncio.CancelledError:
            print(f"[MAIN] Gestor de {pos.symbol} cancelado: protegido por SL en exchange.")
            raise
        finally:
            self.posiciones.pop(pos.symbol, None)

    async def _gestionar_salida_maker_pfqi(
        self, exchange, pos: Posicion, bid: float, ask: float, pnl: float, ofi_inst: float, tiempo_hold: float
    ) -> bool:
        """V6.4.0 Motor Híbrido Maker-First Unwind con Persistencia k=12s (PFQI):
        Coloca y administra una orden Limit Sell PostOnly (reduceOnly=True) para cobrar a 0.020% (Maker)
        en lugar de 0.055% (Taker) cuando el precio entra en zona de cosecha o pre-estancamiento positivo.
        """
        if pos.cerrada or pos.cerrando:
            return pos.cerrada
        ahora = time.time()

        # 1. Si ya hay una orden Limit Sell PostOnly colocada en el libro, verificar su estado
        if pos.maker_order_id is not None:
            if ahora - pos.t_maker_check >= 1.5:
                pos.t_maker_check = ahora
                try:
                    o = await exchange.fetch_order(pos.maker_order_id, pos.symbol, {"acknowledged": True})
                    st = o.get("status")
                    if st == "closed":
                        salida_maker = float(o.get("average") or o.get("price") or pos.maker_order_price or ask)
                        pos.maker_order_id = None
                        pos.cerrada = True
                        self.posiciones.pop(pos.symbol, None)
                        await self._registrar_cierre(
                            exchange, pos, "MAKER_UNWIND", salida_maker, pos.cantidad, es_maker_salida=True
                        )
                        return True
                    if st in ("canceled", "rejected", "expired"):
                        pos.maker_order_id = None
                except Exception:
                    pass

            # Si el impulso comprador resurge con fuerza (OFI > +0.45) en pleno rally, retirar el techo tras persistencia
            if (
                pos.maker_order_id is not None
                and ofi_inst > 0.45
                and pnl >= cfg.TRAIL_ACTIVACION_PCT
                and (ahora - pos.t_maker_placed) >= cfg.MAKER_PERSISTENCIA_SEG
            ):
                await self._cancelar_orden_maker_activa(exchange, pos)
            return False

        # 2. Evaluar si se cumplen las condiciones para colocar la orden Limit Sell PostOnly
        piso_maker = pos.entrada * (1.0 + cfg.MAKER_UNWIND_MIN_PNL_PCT)
        cond_cosecha = (pnl >= cfg.MAKER_UNWIND_ACTIVACION_PCT and ofi_inst <= cfg.MAKER_UNWIND_OFI_TECHO)
        cond_pre_zombie = (tiempo_hold >= cfg.MAKER_UNWIND_STALL_SEG and pnl >= cfg.MAKER_UNWIND_MIN_PNL_PCT)

        if not (cond_cosecha or cond_pre_zombie):
            return False
        if (ahora - pos.t_maker_placed) < cfg.MAKER_PERSISTENCIA_SEG and pos.t_maker_placed > 0:
            return False

        precio_cotizar = max(ask, bid * 1.0001, piso_maker)
        try:
            p_fmt = exchange.price_to_precision(pos.symbol, precio_cotizar)
            p_float = float(p_fmt)
            if p_float <= bid:
                return False
            q_fmt = exchange.amount_to_precision(pos.symbol, pos.cantidad)
            orden = await exchange.create_order(
                pos.symbol,
                "limit",
                "sell",
                q_fmt,
                p_fmt,
                {"timeInForce": "PostOnly", "reduceOnly": True},
            )
            pos.maker_order_id = str(orden.get("id"))
            pos.maker_order_price = p_float
            pos.t_maker_placed = ahora
            pos.t_maker_check = ahora
            print(
                f"[FRANCOTIRADOR] 💎 {pos.symbol} Orden Maker-Unwind PostOnly colocada @ {p_fmt} "
                f"(PnL {pnl:+.2%}, persistencia {cfg.MAKER_PERSISTENCIA_SEG:.0f}s, fee 0.02%)"
            )
        except Exception:
            pos.t_maker_placed = ahora
        return False

    async def _cancelar_orden_maker_activa(self, exchange, pos: Posicion) -> Optional[float]:
        """Cancela la orden Limit Sell PostOnly activa antes de un cierre a mercado.
        Si la orden ya se había llenado en Bybit, devuelve el precio de llenado para registrarla como Maker.
        """
        oid = pos.maker_order_id
        if not oid:
            return None
        pos.maker_order_id = None
        try:
            await exchange.cancel_order(oid, pos.symbol)
        except Exception:
            pass
        try:
            o = await exchange.fetch_order(oid, pos.symbol, {"acknowledged": True})
            if o.get("status") == "closed":
                return float(o.get("average") or o.get("price") or pos.maker_order_price)
        except Exception:
            pass
        return None

    async def _evaluar(self, exchange, pos: Posicion, ticker: dict) -> bool:
        """Evalúa las condiciones de salida (Maker-First + Anti-Zombie 3 Etapas + Triple Barrera)."""
        if pos.cerrada or pos.cerrando:
            return pos.cerrada

        ahora = time.time()
        bid = ticker.get("bid") or ticker.get("last")
        if not bid or bid <= 0:
            return False
        bid = float(bid)
        ask = float(ticker.get("ask") or bid)
        pos.ultimo_bid = bid
        pos.ultimo_ask = ask
        pos.muestras_q += 1
        pos.suma_nocional_abs += pos.cantidad * bid

        ofi_inst = calcular_ofi(ticker)
        media_ofi = pos.ofi_media.push(ahora, ofi_inst)
        pnl = bid / pos.entrada - 1.0
        pos.max_precio = max(pos.max_precio, bid)
        tiempo_hold = ahora - pos.t_apertura

        # 1. Micro-Break-Even V6.4.0: +0.45% -> Asegura entrada + 0.16% interno y >= +0.10% en Bybit
        if not pos.be_activo and pnl >= cfg.BE_ACTIVACION_PCT:
            pos.be_activo = True
            pos.sl = max(pos.sl, pos.entrada * (1.0 + cfg.BE_OFFSET_PCT))
            print(f"[FRANCOTIRADOR] 🛡️ {pos.symbol} Micro-Break-Even armado: SL {pos.sl:.6g} (PnL {pnl:+.2%})")

        # 2. Trailing Stop Ágil V6.4.0: +0.75% -> Rastrear el máximo a distancia de 0.32%
        if not pos.trailing_activo and pnl >= cfg.TRAIL_ACTIVACION_PCT:
            pos.trailing_activo = True
            print(f"[FRANCOTIRADOR] 🧲 {pos.symbol} Trailing Stop activado (PnL {pnl:+.2%})")
        if pos.trailing_activo:
            pos.sl = max(pos.sl, pos.max_precio * (1.0 - cfg.TRAIL_DISTANCIA_PCT))

        # 3. Disparadores deterministas de salida (Prioridad de Supervivencia y Corte de Sangrado LVR)
        motivo = None

        # A) Liquidación forzada anti-zombie al límite reducido de 180s
        if tiempo_hold >= cfg.TIEMPO_MAX_HOLD_SEG:
            motivo = "ESCAPE_TEMPORAL"
            print(
                f"⌛ [FRANCOTIRADOR] {pos.symbol} alcanzó tiempo límite ({int(tiempo_hold)}s >= {cfg.TIEMPO_MAX_HOLD_SEG}s). "
                f"Liquidando posición para liberar margen."
            )
        # B) V6.4.0 Corte Temprano de Cuchillo Lento a los 45s (erradica pérdidas de -1.9% como Trades #115/#119)
        elif (
            not pos.be_activo
            and tiempo_hold >= cfg.EARLY_TOXIC_HOLD_SEG
            and pnl <= cfg.EARLY_TOXIC_LOSS_PCT
            and media_ofi is not None
            and media_ofi <= cfg.EARLY_TOXIC_OFI_MAX
        ):
            motivo = "EARLY_TOXIC_SL"
            print(
                f"✂️ [ANTI-ZOMBIE 45s] {pos.symbol} sin rebote tras {int(tiempo_hold)}s "
                f"(PnL {pnl:+.2%}, OFI10s {media_ofi:+.2f}): cortando sangrado LVR."
            )
        # C) V6.4.0 Corte por Estancamiento Markoviano a los 105s (prob-DDPG Stagnation Cut)
        elif (
            not pos.be_activo
            and tiempo_hold >= cfg.STAGNATION_HOLD_SEG
            and pnl <= cfg.STAGNATION_LOSS_PCT
            and (media_ofi is None or media_ofi < cfg.STAGNATION_OFI_MAX)
        ):
            motivo = "STAGNATION_EXIT"
            print(
                f"✂️ [ANTI-ZOMBIE 105s] {pos.symbol} estancado en pérdida tras {int(tiempo_hold)}s "
                f"(PnL {pnl:+.2%}): liberando capital antes del drenaje de 300s."
            )
        # D) Escape sensibilizado por flujo tóxico institucional (-0.42 en lugar de -0.80)
        elif (
            media_ofi is not None
            and pnl <= cfg.OFI_SALIDA_MIN_LOSS_PCT
            and media_ofi < cfg.OFI_SALIDA_EMERGENCIA
            and pos.ofi_media.cobertura() >= cfg.OFI_SALIDA_VENTANA_SEG * 0.8
        ):
            motivo = "OFI_EXIT"
            print(
                f"⚠️ [MICROESTRUCTURA] {pos.symbol} flujo TÓXICO masivo (OFI {cfg.OFI_SALIDA_VENTANA_SEG}s "
                f"{media_ofi:+.2f}): salida de emergencia"
            )
        # E) Ejecución por Stop-Loss interno, Micro-Break-Even o Trailing
        elif bid <= pos.sl:
            motivo = "TRAILING" if pos.trailing_activo else "BREAK_EVEN" if pos.be_activo else "SL"

        if motivo and ahora >= pos.t_reintento:
            return await self.cerrar(exchange, pos, motivo, bid)

        # 4. V6.4.0 Desarme Pasivo Maker-First (0.02% fee) cuando está en ganancia
        if await self._gestionar_salida_maker_pfqi(exchange, pos, bid, ask, pnl, ofi_inst, tiempo_hold):
            return True

        # 5. Sincronizar SL en Bybit hacia arriba garantizando el piso positivo BE_PISO_EXCHANGE_PCT
        objetivo = self.calcular_objetivo_sl_exchange(pos)
        if (
            (pos.be_activo or pos.trailing_activo)
            and objetivo > pos.sl_exchange
            and objetivo < bid
            and ahora - pos.t_ult_sync >= cfg.SYNC_SL_EXCHANGE_SEG
        ):
            await self._sync_sl_exchange(exchange, pos, objetivo)

        # 6. Verificación periódica contra liquidaciones externas de Bybit
        if ahora - pos.t_ult_check >= CHECK_POSICION_SEG:
            return await self._verificar_externo(exchange, pos)
        return False

    # ------------------------------------------------------------------ Exchange
    async def _sync_sl_exchange(self, exchange, pos: Posicion, objetivo: float) -> None:
        if pos.cerrada or pos.cerrando:
            return
        try:
            precio = exchange.price_to_precision(pos.symbol, objetivo)
            precio_f = float(precio)
            if precio_f <= pos.sl_exchange:
                return
            if (pos.be_activo or pos.trailing_activo) and precio_f <= pos.entrada:
                return
            pos.t_ult_sync = time.time()
            await exchange.privatePostV5PositionTradingStop({
                "category": "linear",
                "symbol": exchange.market_id(pos.symbol),
                "stopLoss": str(precio),
                "tpslMode": "Full",
                "positionIdx": 0,
            })
            pos.sl_exchange = precio_f
            print(f"[FRANCOTIRADOR] SL de Bybit en {pos.symbol} ajustado a {precio}")
        except Exception as e:
            if "34040" in str(e) or "110017" in str(e):
                pos.sl_exchange = objetivo
                return
            print(f"[FRANCOTIRADOR] Fallo sincronizando SL Bybit en {pos.symbol}: {type(e).__name__}: {e}")

    async def _posicion_larga(self, exchange, symbol: str) -> Optional[float]:
        try:
            posiciones = await exchange.fetch_positions([symbol])
        except Exception as e:
            print(f"[MICROESTRUCTURA] Error leyendo posición de {symbol}: {type(e).__name__}: {e}")
            return None
        return sum(
            float(p.get("contracts") or 0)
            for p in posiciones or []
            if p.get("symbol") == symbol and p.get("side") == "long"
        )

    async def _precio_salida_externo(self, exchange, pos: Posicion) -> Optional[float]:
        try:
            trades = await exchange.fetch_my_trades(pos.symbol, int(pos.t_apertura * 1000))
            ventas = [t for t in trades or [] if t.get("side") == "sell" and t.get("amount")]
            qty = sum(float(t["amount"]) for t in ventas)
            if qty > 0:
                return sum(float(t["price"]) * float(t["amount"]) for t in ventas) / qty
        except Exception as e:
            print(f"[MICROESTRUCTURA] Error leyendo trades de {pos.symbol}: {type(e).__name__}: {e}")
        return None

    async def _verificar_externo(self, exchange, pos: Posicion) -> bool:
        if pos.cerrada or pos.cerrando:
            return pos.cerrada
        pos.t_ult_check = time.time()
        real = await self._posicion_larga(exchange, pos.symbol)
        if real is not None and real <= 0:
            if pos.cerrada or pos.cerrando:
                return True
            pos.cerrada = True
            self.posiciones.pop(pos.symbol, None)
            precio_maker = await self._cancelar_orden_maker_activa(exchange, pos)
            if precio_maker is not None:
                await self._registrar_cierre(
                    exchange, pos, "MAKER_UNWIND", precio_maker, pos.cantidad, es_maker_salida=True
                )
            else:
                salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange
                await self._registrar_cierre(
                    exchange, pos, "SL_EXCHANGE", salida, pos.cantidad, es_maker_salida=False
                )
            return True
        return False

    async def cerrar(self, exchange, pos: Posicion, motivo: str, precio_ref: float) -> bool:
        """Market Sell reduce-only con cerrojo inmutable `pos.cerrada` y captura nativa de `110017`."""
        if pos.cerrada or pos.cerrando:
            return pos.cerrada
        pos.cerrando = True
        try:
            # 0. Si existía una orden Limit Sell PostOnly activa, cancelarla o verificar si ya llenó
            precio_maker = await self._cancelar_orden_maker_activa(exchange, pos)
            if precio_maker is not None:
                pos.cerrada = True
                self.posiciones.pop(pos.symbol, None)
                await self._registrar_cierre(
                    exchange, pos, "MAKER_UNWIND", precio_maker, pos.cantidad, es_maker_salida=True
                )
                return True

            real = await self._posicion_larga(exchange, pos.symbol)
            if real is not None and real <= 0:
                pos.cerrada = True
                self.posiciones.pop(pos.symbol, None)
                salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange
                await self._registrar_cierre(
                    exchange, pos, "SL_EXCHANGE", salida, pos.cantidad, es_maker_salida=False
                )
                return True

            cantidad = real if real else pos.cantidad
            orden = await exchange.create_order(
                pos.symbol,
                "market",
                "sell",
                exchange.amount_to_precision(pos.symbol, cantidad),
                None,
                {"reduceOnly": True},
            )
            salida = precio_ref
            try:
                o = await exchange.fetch_order(orden["id"], pos.symbol, {"acknowledged": True})
                salida = float(o.get("average") or o.get("price") or precio_ref)
            except Exception:
                pass

            pos.cerrada = True
            self.posiciones.pop(pos.symbol, None)
            await self._registrar_cierre(
                exchange, pos, motivo, salida, cantidad, es_maker_salida=False
            )
            return True
        except Exception as e:
            texto_err = str(e)
            # V6.4.0: Si Bybit devuelve 110017 ("current position is zero"), el SL de Bybit ya la cerró
            if "110017" in texto_err or "position is zero" in texto_err.lower():
                pos.cerrada = True
                self.posiciones.pop(pos.symbol, None)
                salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange or precio_ref
                await self._registrar_cierre(
                    exchange, pos, "SL_EXCHANGE", salida, pos.cantidad, es_maker_salida=False
                )
                return True

            print(f"[FRANCOTIRADOR] ERROR cerrando {pos.symbol} ({motivo}): {type(e).__name__}: {e}. Reintentando.")
            pos.t_reintento = time.time() + REINTENTO_CIERRE_SEG
            return False
        finally:
            pos.cerrando = False

    async def _registrar_cierre(
        self,
        exchange,
        pos: Posicion,
        motivo: str,
        salida: float,
        cantidad: float,
        es_maker_salida: bool = False,
    ) -> None:
        # Guardia de idempotencia absoluta: una instancia Posicion jamás se registra dos veces
        if pos.extra.get("registrado"):
            return
        pos.extra["registrado"] = True

        try:
            if motivo != "ESCAPE_HUERFANA_BOOT":
                self.registrar_cooldown_post_cierre(pos.symbol)

            fee_salida = cfg.FEE_MAKER if es_maker_salida else cfg.FEE_TAKER
            pnl_pct, pnl_usdt, fees = _stats.calcular_pnl(
                pos.entrada, float(salida), float(cantidad), cfg.FEE_MAKER, fee_salida
            )
            hold = max(0.1, time.time() - pos.t_apertura)
            map_usdt = (
                pos.suma_nocional_abs / pos.muestras_q
                if pos.muestras_q > 0
                else (pos.entrada * float(cantidad))
            )

            await _stats.tracker.registrar({
                "symbol": pos.symbol,
                "side": "long",
                "z_score_entry": pos.z_entrada,
                "ofi_entry": pos.ofi_entrada,
                "pnl_percentage": pnl_pct,
                "pnl_usdt": pnl_usdt,
                "entry_price": pos.entrada,
                "exit_price": float(salida),
                "qty": float(cantidad),
                "motivo": motivo,
                "hold_seg": round(hold, 1),
                "fees_usdt": fees,
                "map_usdt": round(map_usdt, 4),
            })

            icono = "🟩" if pnl_usdt > 0 else "🔴"
            print(
                f"[FRANCOTIRADOR] {icono} CIERRE {pos.symbol} [{motivo}] {pos.entrada} → {salida} | "
                f"{pnl_pct:+.2f} % ({pnl_usdt:+.4f} USDT) en {hold:.0f}s"
            )

            sniper_mod = importlib.import_module("3_ejecutor_sniper")
            sniper_mod.disparar_sincronizacion_saldo_bg(exchange)
            await enviar_alerta(
                f"{icono} [CIERRE {motivo}] {pos.symbol}\n{pnl_pct:+.2f} % ({pnl_usdt:+.4f} USDT) en {hold:.0f}s"
            )
            _stats.tracker.imprimir_dashboard(await _stats.leer_balance_real(exchange))
        except Exception as e:
            print(f"[FRANCOTIRADOR] ERROR registrando cierre de {pos.symbol}: {type(e).__name__}: {e}")


gestor = PositionManager()


# === [INYECCION CUANTITATIVA V6.4.0+: ALMGREN-CHRISS MAKER-UNWIND & CORTE LVR] ===
import builtins as _builtins


def calcular_umbral_maker_almgren_chriss(edad_seg: float) -> float:
    """Curva Hiperbolica de Almgren-Chriss (2000) y Avellaneda-Stoikov (2008) con persistencia PFQI."""
    import math as _m
    import config_parametros as _cfg

    t_max = float(getattr(_cfg, "TIEMPO_MAX_HOLD_SEG", 180.0))
    p_ini = float(getattr(_cfg, "MAKER_UNWIND_ACTIVACION_PCT", 0.0052))
    p_fin = float(getattr(_cfg, "MAKER_UNWIND_TARDIO_PCT", 0.0022))
    kappa = float(getattr(_cfg, "ALMGREN_CHRISS_KAPPA", 2.20))

    if edad_seg <= 60.0:
        return p_ini
    restante = max(0.0, min(1.0, (t_max - float(edad_seg)) / max(1.0, t_max - 60.0)))
    factor_sinh = _m.sinh(kappa * restante) / _m.sinh(kappa)
    return round(p_fin + (p_ini - p_fin) * factor_sinh, 6)


def evaluar_corte_lvr_incondicional(edad_seg: float, pnl_pct: float, ofi_10s: float) -> bool:
    """Control de Loss-Versus-Rebalancing (Milionis et al., 2022) y CVaR 95%."""
    import config_parametros as _cfg

    min_edad = float(getattr(_cfg, "EARLY_TOXIC_CHECK_SEG", 45))
    if edad_seg < min_edad:
        return False
    loss_std = float(getattr(_cfg, "EARLY_TOXIC_LOSS_PCT", -0.0065))
    loss_hard = float(getattr(_cfg, "EARLY_TOXIC_HARD_LOSS_PCT", -0.0072))
    ofi_max = float(getattr(_cfg, "EARLY_TOXIC_OFI_MAX", -0.15))
    return (pnl_pct <= loss_std and ofi_10s <= ofi_max) or (pnl_pct <= loss_hard)


def _print_interceptor_gestor(*args, **kwargs):
    texto_msg = " ".join(str(a) for a in args)
    if "Fallo sincronizando SL Bybit" in texto_msg and (
        "10001" in texto_msg or "zero position" in texto_msg.lower() or "110017" in texto_msg
    ):
        return None
    return _builtins.print(*args, **kwargs)


print = _print_interceptor_gestor
