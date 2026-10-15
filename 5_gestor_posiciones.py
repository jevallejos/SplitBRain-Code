"""PositionManager SPLITBRAIN V6.3.0:
Auto-Reconciliación de Huérfanas, Evacuación Macro Instantánea (BTC Crash / Contagio Cross-Asset),
Cuarentena Post-Cierre Anti-Knife-Catching (300s), Micro-Break-Even (+0.48%) y Sync Zero-REST.
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
MARGEN_SL_EXCHANGE = 0.002     # SL de Bybit 0.2% por debajo del SL interno


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
    t_ult_sync: float = 0.0
    t_ult_check: float = 0.0
    t_reintento: float = 0.0
    ultimo_bid: float = 0.0
    muestras_q: int = 0
    suma_nocional_abs: float = 0.0
    extra: dict = field(default_factory=dict)


class PositionManager:
    def __init__(self) -> None:
        self.posiciones: dict[str, Posicion] = {}
        self.cooldown_hasta: dict[str, float] = {}
        self._tareas: set[asyncio.Task] = set()

    def tiene(self, symbol: str) -> bool:
        return symbol in self.posiciones

    def registrar_cooldown_post_cierre(self, symbol: str, duracion_seg: Optional[float] = None) -> None:
        """V6.3.0 Grim Trigger Cooldown:
        Bloquea nuevas entradas en `symbol` durante COOLDOWN_POST_CIERRE_SEG (300s)
        contados estrictamente desde el instante en que se cierra la posición.
        """
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
        """V6.3.0 Neutralización Instantánea de Beta en Crash Macro / Contagio:
        Recorre todas las posiciones abiertas en el milisegundo en que colapsa BTC o salta el
        Breadth Contagion Breaker:
        - Si la posición está en pérdida o aún no aseguró ganancia neta, la cierra a mercado de inmediato.
        - Si la posición está en ganancia holgada (> BE_OFFSET_PCT), ciñe su SL interno al bid actual
          o la liquida para impedir que el contagio borre el beneficio.
        """
        activas = list(self.posiciones.values())
        if not activas:
            return 0
        evacuadas = 0
        print(
            f"🚨 [EVACUACIÓN MACRO] Ejecutando protocolo `{motivo_macro}` sobre "
            f"{len(activas)} posición(es) abierta(s)..."
        )
        for pos in activas:
            if pos.cerrando:
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
            while True:
                try:
                    ticker = await exchange.watch_ticker(pos.symbol)
                    if await self._evaluar(exchange, pos, ticker):
                        return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[MICROESTRUCTURA] Gestor {pos.symbol}: {type(e).__name__}: {e}")
                    await asyncio.sleep(1)
                    if await self._verificar_externo(exchange, pos):
                        return
        except asyncio.CancelledError:
            print(f"[MAIN] Gestor de {pos.symbol} cancelado: protegido por SL en exchange.")
            raise
        finally:
            self.posiciones.pop(pos.symbol, None)

    async def _evaluar(self, exchange, pos: Posicion, ticker: dict) -> bool:
        """Evalúa las condiciones de salida de Triple Barrera en sub-milisegundos."""
        ahora = time.time()
        bid = ticker.get("bid") or ticker.get("last")
        if not bid or bid <= 0:
            return False
        bid = float(bid)
        pos.ultimo_bid = bid
        pos.muestras_q += 1
        pos.suma_nocional_abs += pos.cantidad * bid

        media_ofi = pos.ofi_media.push(ahora, calcular_ofi(ticker))
        pnl = bid / pos.entrada - 1.0
        pos.max_precio = max(pos.max_precio, bid)
        tiempo_hold = ahora - pos.t_apertura

        # 1. Micro-Break-Even V6.3.0: +0.48% -> Asegura entrada + 0.12% (elimina el Valle de la Muerte)
        if not pos.be_activo and pnl >= cfg.BE_ACTIVACION_PCT:
            pos.be_activo = True
            pos.sl = max(pos.sl, pos.entrada * (1.0 + cfg.BE_OFFSET_PCT))
            print(f"[FRANCOTIRADOR] 🛡️ {pos.symbol} Micro-Break-Even armado: SL {pos.sl:.6g} (PnL {pnl:+.2%})")

        # 2. Trailing Stop Ágil V6.3.0: +0.80% -> Rastrear el máximo a distancia de 0.35%
        if not pos.trailing_activo and pnl >= cfg.TRAIL_ACTIVACION_PCT:
            pos.trailing_activo = True
            print(f"[FRANCOTIRADOR] 🧲 {pos.symbol} Trailing Stop activado (PnL {pnl:+.2%})")
        if pos.trailing_activo:
            pos.sl = max(pos.sl, pos.max_precio * (1.0 - cfg.TRAIL_DISTANCIA_PCT))

        # 3. Disparadores deterministas de salida
        motivo = None

        # A) Liquidación forzada anti-zombie por expiración de tiempo (300s)
        if tiempo_hold >= cfg.TIEMPO_MAX_HOLD_SEG:
            motivo = "ESCAPE_TEMPORAL"
            print(
                f"⌛ [FRANCOTIRADOR] {pos.symbol} alcanzó tiempo límite ({int(tiempo_hold)}s >= {cfg.TIEMPO_MAX_HOLD_SEG}s). "
                f"Liquidando posición zombie para liberar margen."
            )
        # B) Escape por flujo tóxico institucional persistente en terreno negativo
        elif (
            media_ofi is not None
            and pnl < 0
            and media_ofi < cfg.OFI_SALIDA_EMERGENCIA
            and pos.ofi_media.cobertura() >= cfg.OFI_SALIDA_VENTANA_SEG * 0.8
        ):
            motivo = "OFI_EXIT"
            print(
                f"⚠️ [MICROESTRUCTURA] {pos.symbol} flujo TÓXICO masivo (OFI {cfg.OFI_SALIDA_VENTANA_SEG}s "
                f"{media_ofi:+.2f}): salida de emergencia"
            )
        # C) Ejecución por Stop-Loss interno, Micro-Break-Even o Trailing
        elif bid <= pos.sl:
            motivo = "TRAILING" if pos.trailing_activo else "BREAK_EVEN" if pos.be_activo else "SL"

        if motivo and ahora >= pos.t_reintento:
            return await self.cerrar(exchange, pos, motivo, bid)

        # 4. Sincronizar SL en Bybit de forma asíncrona hacia arriba
        objetivo = pos.sl * (1.0 - MARGEN_SL_EXCHANGE)
        if (
            (pos.be_activo or pos.trailing_activo)
            and objetivo > pos.sl_exchange
            and ahora - pos.t_ult_sync >= cfg.SYNC_SL_EXCHANGE_SEG
        ):
            await self._sync_sl_exchange(exchange, pos, objetivo)

        # 5. Verificación periódica contra liquidaciones externas de Bybit
        if ahora - pos.t_ult_check >= CHECK_POSICION_SEG:
            return await self._verificar_externo(exchange, pos)
        return False

    # ------------------------------------------------------------------ Exchange
    async def _sync_sl_exchange(self, exchange, pos: Posicion, objetivo: float) -> None:
        try:
            precio = exchange.price_to_precision(pos.symbol, objetivo)
            if float(precio) <= pos.sl_exchange:
                return
            pos.t_ult_sync = time.time()
            await exchange.privatePostV5PositionTradingStop({
                "category": "linear",
                "symbol": exchange.market_id(pos.symbol),
                "stopLoss": str(precio),
                "tpslMode": "Full",
                "positionIdx": 0,
            })
            pos.sl_exchange = float(precio)
            print(f"[FRANCOTIRADOR] SL de Bybit en {pos.symbol} ajustado a {precio}")
        except Exception as e:
            if "34040" in str(e):
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
        pos.t_ult_check = time.time()
        real = await self._posicion_larga(exchange, pos.symbol)
        if real is not None and real <= 0:
            salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange
            await self._registrar_cierre(exchange, pos, "SL_EXCHANGE", salida, pos.cantidad)
            return True
        return False

    async def cerrar(self, exchange, pos: Posicion, motivo: str, precio_ref: float) -> bool:
        """Market Sell reduce-only de la posición. Devuelve True si se liquidó exitosamente."""
        if pos.cerrando:
            return False
        pos.cerrando = True
        try:
            real = await self._posicion_larga(exchange, pos.symbol)
            if real is not None and real <= 0:
                salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange
                await self._registrar_cierre(exchange, pos, "SL_EXCHANGE", salida, pos.cantidad)
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
            await self._registrar_cierre(exchange, pos, motivo, salida, cantidad)
            return True
        except Exception as e:
            print(f"[FRANCOTIRADOR] ERROR cerrando {pos.symbol} ({motivo}): {type(e).__name__}: {e}. Reintentando.")
            pos.t_reintento = time.time() + REINTENTO_CIERRE_SEG
            return False
        finally:
            pos.cerrando = False

    async def _registrar_cierre(
        self, exchange, pos: Posicion, motivo: str, salida: float, cantidad: float
    ) -> None:
        try:
            # 1. Activar cuarentena post-cierre de 300s (salvo en limpieza de boot heredado)
            if motivo != "ESCAPE_HUERFANA_BOOT":
                self.registrar_cooldown_post_cierre(pos.symbol)

            pnl_pct, pnl_usdt, fees = _stats.calcular_pnl(pos.entrada, float(salida), float(cantidad))
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

            # 2. Sincronizar saldo libre en RAM inmediatamente y despachar alerta sin bloquear
            sniper_mod = importlib.import_module("3_ejecutor_sniper")
            sniper_mod.disparar_sincronizacion_saldo_bg(exchange)
            await enviar_alerta(
                f"{icono} [CIERRE {motivo}] {pos.symbol}\n{pnl_pct:+.2f} % ({pnl_usdt:+.4f} USDT) en {hold:.0f}s"
            )
            _stats.tracker.imprimir_dashboard(await _stats.leer_balance_real(exchange))
        except Exception as e:
            print(f"[FRANCOTIRADOR] ERROR registrando cierre de {pos.symbol}: {type(e).__name__}: {e}")


gestor = PositionManager()