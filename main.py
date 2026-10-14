import asyncio
import importlib
import sys
from pathlib import Path

import ccxt.pro as ccxt
import config_parametros as cfg

_RAIZ = Path(__file__).resolve().parent
LOG_FILE = _RAIZ / "bot_hft.log"


class _TeeLogger:
    """Duplica toda salida de consola (stdout/stderr) hacia bot_hft.log en UTF-8 con flush inmediato."""
    __slots__ = ("_stream", "_archivo")

    def __init__(self, stream, archivo):
        self._stream = stream
        self._archivo = archivo

    def write(self, data: str) -> int:
        if not data:
            return 0
        try:
            self._stream.write(data)
            self._stream.flush()
        except Exception:
            pass
        try:
            self._archivo.write(data)
            self._archivo.flush()
        except Exception:
            pass
        return len(data)

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass
        try:
            self._archivo.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        return getattr(self._stream, "isatty", lambda: False)()

    def __getattr__(self, name):
        return getattr(self._stream, name)


# Consola a prueba de emojis (Windows usa cp1252 al redirigir la salida a log/pipe)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Apertura persistente de bot_hft.log en modo append ('a') con vaciado por línea
_log_handle = LOG_FILE.open("a", encoding="utf-8", buffering=1, errors="replace")
sys.stdout = _TeeLogger(sys.stdout, _log_handle)
sys.stderr = _TeeLogger(sys.stderr, _log_handle)

radar = importlib.import_module("1_radar_volatilidad")
vigilar_mercado = radar.cazar_anomalia_ws
sniper = importlib.import_module("3_ejecutor_sniper")
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta
gestor_mod = importlib.import_module("5_gestor_posiciones")
stats = importlib.import_module("6_stats_tracker")

REINTENTOS_ARRANQUE = 4
TIMEOUT_EXCHANGE_MS = 20000
RECV_WINDOW_MS = 15000


def _es_perpetuo_cripto_puro(exchange, symbol: str) -> bool:
    """Filtra perpetuos lineales USDT activos, excluyendo listas negras y sintéticos (stock/ETF/commodity/forex)."""
    if not symbol.endswith("USDT:USDT"):
        return False
    if symbol in cfg.PROHIBIDAS or symbol in cfg.BLACKLIST_PAIRS:
        return False
    m = exchange.markets.get(symbol)
    if not m or not m.get("active", True):
        return False
    info = m.get("info") or {}
    symbol_type = str(info.get("symbolType") or "").strip().lower()
    # En Bybit v5, '' o 'innovation' son criptoactivos; 'stock', 'etf', 'commodity', 'forex' son sintéticos.
    if symbol_type and symbol_type not in ("", "innovation"):
        return False
    return True


async def _inicializar_mercados_con_backoff(exchange) -> dict:
    """Carga mercados y tickers con reintentos exponenciales contra DNS frío o InvalidNonce."""
    ultimo_error = None
    for intento in range(1, REINTENTOS_ARRANQUE + 1):
        try:
            await exchange.load_markets()
            tickers = await exchange.fetch_tickers()
            return tickers
        except Exception as e:
            ultimo_error = e
            espera = min(2 ** intento, 10)
            print(f"[MAIN] Aviso de red en arranque (intento {intento}/{REINTENTOS_ARRANQUE}): "
                  f"{type(e).__name__}: {e}. Reintentando en {espera}s...")
            await asyncio.sleep(espera)
    raise RuntimeError(f"Fallo crítico inicializando mercados tras {REINTENTOS_ARRANQUE} intentos: {ultimo_error}")


async def main():
    print("==================================================")
    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V6.1 - ADAPTIVE QUANTUM PREDATOR)")
    print("==================================================")
    print(f"[MAIN] Telemetría local persistente activa en: {LOG_FILE.name}")

    exchange = ccxt.bybit({
        "apiKey": cfg.BYBIT_API_KEY,
        "secret": cfg.BYBIT_API_SECRET,
        "timeout": TIMEOUT_EXCHANGE_MS,
        "enableRateLimit": True,
        "options": {
            "defaultType": "swap",
            "recvWindow": RECV_WINDOW_MS,
            "adjustForTimeDifference": True,
        },
    })

    tareas: list[asyncio.Task] = []  # referencias fuertes: evita que el GC destruya tareas en curso
    try:
        tickers = await _inicializar_mercados_con_backoff(exchange)
        candidatos = [
            t for sym, t in tickers.items()
            if _es_perpetuo_cripto_puro(exchange, sym)
        ]
        candidatos.sort(key=lambda t: float(t.get("quoteVolume") or 0.0), reverse=True)
        presas = [t["symbol"] for t in candidatos[:cfg.TOP_N]]

        print(f"[MAIN] Modo Paper: {cfg.MODO_PAPER} | Motor Salida: {cfg.MOTOR_SALIDA} | Apalancamiento: {cfg.APALANCAMIENTO}x")
        print(f"[MAIN] Radar fijado en {len(presas)} pares cripto-nativos.")
        print(f"[MAIN] Presas: {', '.join(presas)}")

        # Mostrar estado inicial de la Caja Negra (histórico JSONL + balance en vivo)
        stats.tracker.imprimir_dashboard(await stats.leer_balance_real(exchange))

        # Notificar a Telegram SOLO después de que el exchange respondió y el radar está armado
        await enviar_alerta("🟩 Motor SPLITBRAIN V6.1 Apex Predator Inicializado.")

        # 1. Tarea de Circuit Breaker Global (BTC con recuperación en V)
        tareas.append(asyncio.create_task(radar.cazar_cisne_negro(exchange)))

        # 2. Tareas del Radar de Volatilidad y Microestructura OFI por cada presa
        for symbol in presas:
            tareas.append(asyncio.create_task(vigilar_mercado(exchange, symbol)))

        # 3. Tarea periódica del Dashboard de Caja Negra (V6.1)
        tareas.append(asyncio.create_task(stats.bucle_dashboard(exchange, cfg.DASHBOARD_INTERVALO_SEG)))

        while True:
            await asyncio.sleep(1)
    finally:
        # Cancelación limpia de radares, gestores de posición y motores de salida
        todas_las_tareas = list(tareas) + list(gestor_mod.gestor._tareas) + list(sniper._tareas_as)
        for t in todas_las_tareas:
            if not t.done():
                t.cancel()
        if todas_las_tareas:
            await asyncio.gather(*todas_las_tareas, return_exceptions=True)
        await exchange.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN] Apagado manual completado de forma segura.")
    finally:
        try:
            _log_handle.flush()
            _log_handle.close()
        except Exception:
            pass