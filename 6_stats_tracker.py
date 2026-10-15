"""Caja Negra SPLITBRAIN V6.3.0:
Registro JSONL asíncrono, métricas institucionales MAP (Mean Absolute Position),
ratio PnL-to-MAP y estimación de LVR (Loss-Versus-Rebalancing).
"""
import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import config_parametros as cfg

_RAIZ = Path(__file__).resolve().parent


def calcular_pnl(
    entrada: float,
    salida: float,
    cantidad: float,
    fee_entrada: float = cfg.FEE_MAKER,
    fee_salida: float = cfg.FEE_TAKER,
) -> tuple[float, float, float]:
    """PnL neto de un largo: (pnl_percentage sobre el nocional de entrada, pnl_usdt, fees_usdt)."""
    nocional_in = entrada * cantidad
    nocional_out = salida * cantidad
    fees = nocional_in * fee_entrada + nocional_out * fee_salida
    pnl_usdt = nocional_out - nocional_in - fees
    pnl_pct = (pnl_usdt / nocional_in * 100.0) if nocional_in > 0 else 0.0
    return round(pnl_pct, 4), round(pnl_usdt, 6), round(fees, 6)


def estimar_lvr_operacion(nocional_usdt: float, hold_seg: float, sigma_seg: Optional[float] = None) -> float:
    """Milionis et al. (2022) Loss-Versus-Rebalancing instantáneo integrado:
        LVR = (sigma^2 / 8) * V(P) * dt
    """
    sigma = float(sigma_seg if sigma_seg is not None else getattr(cfg, "STD_REL_FLOOR", 0.0005))
    return round((sigma ** 2) / 8.0 * max(0.0, float(nocional_usdt)) * max(0.0, float(hold_seg)), 6)


class StatsTracker:
    def __init__(self, ruta: Optional[Path] = None, capital_base: float = cfg.CAPITAL_BASE_USDT):
        self.ruta = Path(ruta) if ruta else _RAIZ / cfg.STATS_FILE
        self.capital_base = float(capital_base)
        self._trades: Optional[list[dict[str, Any]]] = None
        self._lock = asyncio.Lock()

    # ---------- persistencia ----------
    def cargar(self) -> list[dict[str, Any]]:
        """Lee el histórico (tolerante a líneas corruptas). Se cachea en memoria."""
        if self._trades is None:
            trades = []
            try:
                with self.ruta.open("r", encoding="utf-8") as f:
                    for linea in f:
                        linea = linea.strip()
                        if not linea:
                            continue
                        try:
                            trades.append(json.loads(linea))
                        except json.JSONDecodeError:
                            print(f"[CAJA NEGRA] Línea corrupta ignorada en {self.ruta.name}")
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"[CAJA NEGRA] No se pudo leer {self.ruta.name}: {type(e).__name__}: {e}")
            self._trades = trades
        return self._trades

    def _append(self, linea: str) -> None:
        with self.ruta.open("a", encoding="utf-8") as f:
            f.write(linea + "\n")

    async def registrar(self, trade: dict[str, Any]) -> None:
        """Añade un trade cerrado. La E/S de disco va a un hilo: nunca bloquea el event loop."""
        nocional = float(trade.get("entry_price") or 0.0) * float(trade.get("qty") or 0.0)
        hold_s = float(trade.get("hold_seg") or 0.0)
        lvr_est = estimar_lvr_operacion(nocional, hold_s)
        registro = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **trade,
            "lvr_usdt": trade.get("lvr_usdt", lvr_est),
        }
        try:
            linea = json.dumps(registro, ensure_ascii=False)
            async with self._lock:
                self.cargar()
                await asyncio.to_thread(self._append, linea)
                self._trades.append(registro)
        except Exception as e:
            print(f"[CAJA NEGRA] ERROR registrando trade: {type(e).__name__}: {e}")

    # ---------- analítica ----------
    def resumen(self) -> dict[str, Any]:
        trades = self.cargar()
        pnls = [
            float(t.get("pnl_usdt") or 0.0)
            for t in trades
            if isinstance(t.get("pnl_usdt"), (int, float)) and math.isfinite(t["pnl_usdt"])
        ]
        nocionales = [
            float(t.get("map_usdt") or (float(t.get("entry_price") or 0.0) * float(t.get("qty") or 0.0)))
            for t in trades
        ]
        nocionales_validos = [n for n in nocionales if n > 0 and math.isfinite(n)]
        lvrs = [
            float(t.get("lvr_usdt") or 0.0)
            for t in trades
            if isinstance(t.get("lvr_usdt"), (int, float)) and math.isfinite(t["lvr_usdt"])
        ]

        total = len(pnls)
        ganadores = sum(1 for p in pnls if p > 0)
        pnl_total = sum(pnls)
        map_medio = (sum(nocionales_validos) / len(nocionales_validos)) if nocionales_validos else 0.0
        pnl_to_map = (pnl_total / map_medio) if map_medio > 0 else 0.0

        return {
            "total_trades": total,
            "ganadores": ganadores,
            "perdedores": total - ganadores,
            "win_rate": (ganadores / total * 100.0) if total else 0.0,
            "pnl_total_usdt": pnl_total,
            "balance_teorico": self.capital_base + pnl_total,
            "mejor_usdt": max(pnls) if pnls else 0.0,
            "peor_usdt": min(pnls) if pnls else 0.0,
            "map_usdt": map_medio,
            "pnl_to_map": pnl_to_map,
            "lvr_total_usdt": sum(lvrs),
        }

    def dashboard(self, balance_real: Optional[float] = None) -> str:
        r = self.resumen()
        real = f"{balance_real:.4f} USDT" if balance_real is not None else "n/d"
        ancho = 64
        lineas = [
            f" Trades: {r['total_trades']}  (W {r['ganadores']} / L {r['perdedores']}) | Win Rate: {r['win_rate']:.1f} %",
            f" PnL total: {r['pnl_total_usdt']:+.4f} USDT   mejor {r['mejor_usdt']:+.4f} / peor {r['peor_usdt']:+.4f}",
            f" MAP: {r['map_usdt']:.2f} USDT | PnL/MAP: {r['pnl_to_map']:+.4f} | LVR: {r['lvr_total_usdt']:.4f}",
            f" Balance: {r['balance_teorico']:.4f} USDT (base {self.capital_base:.2f})   real: {real}",
        ]
        cab = " [CAJA NEGRA] SPLITBRAIN V6.3.0 APEX PREDATOR "
        out = ["╔" + cab.center(ancho, "═") + "╗"]
        out += ["║" + l.ljust(ancho)[:ancho] + "║" for l in lineas]
        out.append("╚" + "═" * ancho + "╝")
        return "\n".join(out)

    def imprimir_dashboard(self, balance_real: Optional[float] = None) -> None:
        try:
            print(self.dashboard(balance_real))
        except Exception as e:
            print(f"[CAJA NEGRA] ERROR en dashboard: {type(e).__name__}: {e}")


tracker = StatsTracker()


async def leer_balance_real(exchange) -> Optional[float]:
    """Equity USDT real (solo fuera de MODO_PAPER). None si no aplica o falla."""
    if cfg.MODO_PAPER or exchange is None:
        return None
    try:
        balance = await exchange.fetch_balance()
        total = balance.get("USDT", {}).get("total")
        return float(total) if total is not None else None
    except Exception as e:
        print(f"[CAJA NEGRA] Balance real no disponible: {type(e).__name__}: {e}")
        return None


async def bucle_dashboard(exchange=None, intervalo: float = cfg.DASHBOARD_INTERVALO_SEG) -> None:
    """Imprime el dashboard periódicamente. Nunca termina por errores."""
    while True:
        await asyncio.sleep(intervalo)
        try:
            tracker.imprimir_dashboard(await leer_balance_real(exchange))
        except Exception as e:
            print(f"[CAJA NEGRA] ERROR en bucle de dashboard: {type(e).__name__}: {e}")