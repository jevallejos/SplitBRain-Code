"""PositionManager SPLITBRAIN V6.1: SL dinámico, break-even, trailing y salida de emergencia por OFI.

Cada posición tiene su propia tarea con su propio `watch_ticker` (el radar duerme 60 s tras cada
disparo y no puede alimentar al gestor). El SL de catástrofe vive en Bybit (adjunto a la compra)
y se sube vía `trading-stop` cuando el break-even o el trailing lo superan, para que la posición
quede protegida aunque el bot muera.
"""
import asyncio
import importlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import config_parametros as cfg

enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta
_stats = importlib.import_module("6_stats_tracker")

CHECK_POSICION_SEG = 10        # verificación periódica de que la posición sigue viva en Bybit
REINTENTO_CIERRE_SEG = 2       # backoff si la venta a mercado falla
MARGEN_SL_EXCHANGE = 0.002     # el SL de Bybit queda 0.2 % por debajo del SL interno (respaldo, no competidor)


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
    extra: dict = field(default_factory=dict)


class PositionManager:
    def __init__(self) -> None:
        self.posiciones: dict[str, Posicion] = {}
        self._tareas: set[asyncio.Task] = set()

    def tiene(self, symbol: str) -> bool:
        return symbol in self.posiciones

    def abrir(self, exchange, symbol: str, cantidad: float, entrada: float,
              z_entrada: Optional[float] = None, ofi_entrada: Optional[float] = None) -> Posicion:
        media_movil = importlib.import_module("1_radar_volatilidad").MediaMovilTemporal
        entrada = float(entrada)
        pos = Posicion(
            symbol=symbol, cantidad=float(cantidad), entrada=entrada,
            z_entrada=z_entrada, ofi_entrada=ofi_entrada,
            sl=entrada * (1 - cfg.SL_INICIAL_PCT),
            sl_exchange=entrada * (1 - cfg.SL_PCT),
            max_precio=entrada, t_apertura=time.time(),
            ofi_media=media_movil(cfg.OFI_SALIDA_VENTANA_SEG),
        )
        pos.t_ult_check = pos.t_apertura
        self.posiciones[symbol] = pos
        tarea = asyncio.create_task(self._vigilar(exchange, pos))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)
        print(f"[FRANCOTIRADOR] 🎯 Posición en {symbol}: {pos.cantidad} @ {entrada} | "
              f"SL interno {pos.sl:.6g} | SL Bybit {pos.sl_exchange:.6g}")
        return pos

    # ------------------------------------------------------------------ vigilancia
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
            print(f"[MAIN] Gestor de {pos.symbol} detenido: la posición queda protegida solo por el SL de Bybit.")
            raise
        finally:
            self.posiciones.pop(pos.symbol, None)

    async def _evaluar(self, exchange, pos: Posicion, ticker: dict) -> bool:
        """Procesa un tick. Devuelve True si la posición quedó cerrada."""
        ahora = time.time()
        bid = ticker.get("bid") or ticker.get("last")
        if not bid or bid <= 0:
            return False
        bid = float(bid)
        media_ofi = pos.ofi_media.push(ahora, calcular_ofi(ticker))
        pnl = bid / pos.entrada - 1
        pos.max_precio = max(pos.max_precio, bid)

        # 1. Break-even: +1.0 % → SL a entrada + 0.15 %
        if not pos.be_activo and pnl >= cfg.BE_ACTIVACION_PCT:
            pos.be_activo = True
            pos.sl = max(pos.sl, pos.entrada * (1 + cfg.BE_OFFSET_PCT))
            print(f"[FRANCOTIRADOR] 🛡️ {pos.symbol} break-even armado: SL {pos.sl:.6g} (PnL {pnl:+.2%})")
        # 2. Trailing: +1.5 % → SL a 0.8 % del máximo
        if not pos.trailing_activo and pnl >= cfg.TRAIL_ACTIVACION_PCT:
            pos.trailing_activo = True
            print(f"[FRANCOTIRADOR] 🧲 {pos.symbol} trailing activo (PnL {pnl:+.2%})")
        if pos.trailing_activo:
            pos.sl = max(pos.sl, pos.max_precio * (1 - cfg.TRAIL_DISTANCIA_PCT))

        # 3. Disparadores de salida
        motivo = None
        if (media_ofi is not None and pnl < 0 and media_ofi < cfg.OFI_SALIDA_EMERGENCIA
                and pos.ofi_media.cobertura() >= cfg.OFI_SALIDA_VENTANA_SEG * 0.8):
            motivo = "OFI_EXIT"
            print(f"⚠️ [MICROESTRUCTURA] {pos.symbol} flujo TÓXICO masivo (OFI {cfg.OFI_SALIDA_VENTANA_SEG}s "
                  f"{media_ofi:+.2f}): salida de emergencia")
        elif bid <= pos.sl:
            motivo = "TRAILING" if pos.trailing_activo else "BREAK_EVEN" if pos.be_activo else "SL"

        if motivo and ahora >= pos.t_reintento:
            return await self.cerrar(exchange, pos, motivo, bid)

        # 4. Sincronizar el SL de Bybit (solo hacia arriba, con throttle)
        objetivo = pos.sl * (1 - MARGEN_SL_EXCHANGE)
        if (pos.be_activo or pos.trailing_activo) and objetivo > pos.sl_exchange \
                and ahora - pos.t_ult_sync >= cfg.SYNC_SL_EXCHANGE_SEG:
            await self._sync_sl_exchange(exchange, pos, objetivo)

        # 5. Verificación periódica (¿la cerró el SL de Bybit o una intervención manual?)
        if ahora - pos.t_ult_check >= CHECK_POSICION_SEG:
            return await self._verificar_externo(exchange, pos)
        return False

    # ------------------------------------------------------------------ exchange
    async def _sync_sl_exchange(self, exchange, pos: Posicion, objetivo: float) -> None:
        try:
            precio = exchange.price_to_precision(pos.symbol, objetivo)
            if float(precio) <= pos.sl_exchange:
                return  # redondeado al tick no sube: no gastar una llamada
            pos.t_ult_sync = time.time()
            await exchange.privatePostV5PositionTradingStop({
                "category": "linear",
                "symbol": exchange.market_id(pos.symbol),
                "stopLoss": str(precio),
                "tpslMode": "Full",
                "positionIdx": 0,
            })
            pos.sl_exchange = float(precio)
            print(f"[FRANCOTIRADOR] SL de Bybit en {pos.symbol} subido a {precio}")
        except Exception as e:
            if "34040" in str(e):  # "not modified"
                pos.sl_exchange = objetivo
                return
            print(f"[FRANCOTIRADOR] No se pudo subir el SL de Bybit en {pos.symbol}: {type(e).__name__}: {e}")

    async def _posicion_larga(self, exchange, symbol: str) -> Optional[float]:
        try:
            posiciones = await exchange.fetch_positions([symbol])
        except Exception as e:
            print(f"[MICROESTRUCTURA] No se pudo leer la posición de {symbol}: {type(e).__name__}: {e}")
            return None
        return sum(float(p.get("contracts") or 0) for p in posiciones or []
                   if p.get("symbol") == symbol and p.get("side") == "long")

    async def _precio_salida_externo(self, exchange, pos: Posicion) -> Optional[float]:
        """Precio medio de las ventas ejecutadas desde la apertura (p. ej. el SL de Bybit)."""
        try:
            trades = await exchange.fetch_my_trades(pos.symbol, int(pos.t_apertura * 1000))
            ventas = [t for t in trades or [] if t.get("side") == "sell" and t.get("amount")]
            qty = sum(float(t["amount"]) for t in ventas)
            if qty > 0:
                return sum(float(t["price"]) * float(t["amount"]) for t in ventas) / qty
        except Exception as e:
            print(f"[MICROESTRUCTURA] Sin trades de salida de {pos.symbol}: {type(e).__name__}: {e}")
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
        """Market Sell reduce-only del tamaño real. Devuelve True si la posición quedó cerrada."""
        if pos.cerrando:
            return False
        pos.cerrando = True
        try:
            real = await self._posicion_larga(exchange, pos.symbol)
            if real is not None and real <= 0:  # se adelantó el SL de Bybit
                salida = await self._precio_salida_externo(exchange, pos) or pos.sl_exchange
                await self._registrar_cierre(exchange, pos, "SL_EXCHANGE", salida, pos.cantidad)
                return True
            cantidad = real if real else pos.cantidad
            orden = await exchange.create_order(pos.symbol, "market", "sell",
                                                exchange.amount_to_precision(pos.symbol, cantidad),
                                                None, {"reduceOnly": True})
            salida = precio_ref
            try:
                o = await exchange.fetch_order(orden["id"], pos.symbol, {"acknowledged": True})
                salida = float(o.get("average") or o.get("price") or precio_ref)
            except Exception:
                pass  # el precio de referencia (bid) sirve como estimación
            await self._registrar_cierre(exchange, pos, motivo, salida, cantidad)
            return True
        except Exception as e:
            print(f"[FRANCOTIRADOR] ERROR cerrando {pos.symbol} ({motivo}): {type(e).__name__}: {e}. Reintento.")
            pos.t_reintento = time.time() + REINTENTO_CIERRE_SEG
            return False
        finally:
            pos.cerrando = False

    async def _registrar_cierre(self, exchange, pos: Posicion, motivo: str, salida: float, cantidad: float) -> None:
        try:
            pnl_pct, pnl_usdt, fees = _stats.calcular_pnl(pos.entrada, float(salida), float(cantidad))
            hold = time.time() - pos.t_apertura
            await _stats.tracker.registrar({
                "symbol": pos.symbol, "side": "long",
                "z_score_entry": pos.z_entrada, "ofi_entry": pos.ofi_entrada,
                "pnl_percentage": pnl_pct, "pnl_usdt": pnl_usdt,
                "entry_price": pos.entrada, "exit_price": float(salida), "qty": float(cantidad),
                "motivo": motivo, "hold_seg": round(hold, 1), "fees_usdt": fees,
            })
            icono = "🟩" if pnl_usdt > 0 else "🔴"  # las pérdidas quedan silenciadas por la lista blanca
            print(f"[FRANCOTIRADOR] {icono} CIERRE {pos.symbol} [{motivo}] {pos.entrada} → {salida} | "
                  f"{pnl_pct:+.2f} % ({pnl_usdt:+.4f} USDT) en {hold:.0f}s")
            await enviar_alerta(f"{icono} [CIERRE {motivo}] {pos.symbol}\n{pnl_pct:+.2f} % ({pnl_usdt:+.4f} USDT) en {hold:.0f}s")
            _stats.tracker.imprimir_dashboard(await _stats.leer_balance_real(exchange))
        except Exception as e:
            print(f"[FRANCOTIRADOR] ERROR registrando cierre de {pos.symbol}: {type(e).__name__}: {e}")


gestor = PositionManager()
