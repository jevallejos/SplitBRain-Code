"""Cerebro Central SPLIT-BRAIN HFT (V6.2.2 - Boot-Time Orphan Reconciliation & PID Lock)."""
import asyncio
import importlib
import os
import sys
from pathlib import Path

import ccxt.pro as ccxt
import config_parametros as cfg

_RAIZ = Path(__file__).resolve().parent
LOG_FILE = _RAIZ / "bot_hft.log"
LOCK_FILE = _RAIZ / ".splitbrain.lock"
_lock_file_handle = None


def adquirir_bloqueo_instancia_unica() -> None:
    """Garantiza la ejecución de exactamente una instancia física de Split-Brain (Cross-Platform)."""
    global _lock_file_handle
    try:
        _lock_file_handle = LOCK_FILE.open("a+", encoding="utf-8")
        if sys.platform != "win32":
            import fcntl
            fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            _lock_file_handle.seek(0)
            msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)

        _lock_file_handle.seek(0)
        _lock_file_handle.truncate()
        _lock_file_handle.write(f"{os.getpid()}\n")
        _lock_file_handle.flush()
    except (BlockingIOError, PermissionError, OSError):
        print(f"❌ [CRÍTICO] Ya existe una instancia activa de SPLITBRAIN ejecutándose (PID Lock en {LOCK_FILE.name}).")
        print("❌ [CRÍTICO] Abortando este proceso inmediatamente para evitar dobles disparos y colapso de margen.")
        sys.exit(1)


def liberar_bloqueo_instancia_unica() -> None:
    """Libera el cerrojo y elimina el archivo de bloqueo al apagar el bot limpiamente."""
    global _lock_file_handle
    if _lock_file_handle:
        try:
            if sys.platform != "win32":
                import fcntl
                fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_UN)
            else:
                import msvcrt
                _lock_file_handle.seek(0)
                msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            _lock_file_handle.close()
        except Exception:
            pass
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


class _TeeLogger:
    """Duplica la salida estándar hacia bot_hft.log en UTF-8 con vaciado continuo."""
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


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_log_handle = LOG_FILE.open("a", encoding="utf-8", buffering=1, errors="replace")
sys.stdout = _TeeLogger(sys.stdout, _log_handle)
sys.stderr = _TeeLogger(sys.stderr, _log_handle)

radar = importlib.import_module("1_radar_volatilidad")
vigilar_mercado = radar.cazar_anomalia_ws
escudo = importlib.import_module("2_escudo_semantico")
sniper = importlib.import_module("3_ejecutor_sniper")
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta
gestor_mod = importlib.import_module("5_gestor_posiciones")
stats = importlib.import_module("6_stats_tracker")

REINTENTOS_ARRANQUE = 4
TIMEOUT_EXCHANGE_MS = 20000
RECV_WINDOW_MS = 15000


def _es_perpetuo_cripto_puro(exchange, symbol: str) -> bool:
    """Filtra perpetuos lineales USDT activos, excluyendo listas negras y sintéticos."""
    if not symbol.endswith("USDT:USDT"):
        return False
    if symbol in cfg.PROHIBIDAS or symbol in cfg.BLACKLIST_PAIRS:
        return False
    m = exchange.markets.get(symbol)
    if not m or not m.get("active", True):
        return False
    info = m.get("info") or {}
    symbol_type = str(info.get("symbolType") or "").strip().lower()
    if symbol_type and symbol_type not in ("", "innovation"):
        return False
    return True


async def _inicializar_mercados_con_backoff(exchange) -> dict:
    ultimo_error = None
    for intento in range(1, REINTENTOS_ARRANQUE + 1):
        try:
            await exchange.load_markets()
            tickers = await exchange.fetch_tickers()
            return tickers
        except Exception as e:
            ultimo_error = e
            espera = min(2 ** intento, 10)
            print(
                f"[MAIN] Aviso de red en arranque (intento {intento}/{REINTENTOS_ARRANQUE}): "
                f"{type(e).__name__}: {e}. Reintentando en {espera}s..."
            )
            await asyncio.sleep(espera)
    raise RuntimeError(f"Fallo crítico inicializando mercados tras {REINTENTOS_ARRANQUE} intentos: {ultimo_error}")


async def _auditar_margen_libre(exchange) -> None:
    """Inspecciona el balance USDT libre vs bloqueado después de reconciliar posiciones."""
    if cfg.MODO_PAPER:
        return
    try:
        bal = await exchange.fetch_balance()
        usdt = bal.get("USDT") or {}
        total = float(usdt.get("total") or 0.0)
        libre = float(usdt.get("free") or 0.0)
        usado = max(0.0, total - libre)
        margen_disparo = libre * cfg.KELLY_MAX_PCT
        estado = "LISTO PARA DISPARAR" if margen_disparo >= 2.0 else "MUNICIÓN BAJA (< 2.0 USDT)"
        print(
            f"[MAIN] Auditoría UTA USDT -> Total: {total:.4f} | Libre: {libre:.4f} | "
            f"Bloqueado: {usado:.4f} | Margen Kelly (35%): {margen_disparo:.2f} USDT [{estado}]"
        )
    except Exception as e:
        print(f"[MAIN] Aviso leyendo margen libre: {type(e).__name__}: {e}")


async def main():
    adquirir_bloqueo_instancia_unica()
    print("==================================================================")
    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V6.2.2 - ORPHAN RECONCILIATION)")
    print("==================================================================")
    print(f"[MAIN] Bloqueo de instancia física adquirido exitosamente (PID {os.getpid()}).")
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

    tareas: list[asyncio.Task] = []
    try:
        tickers = await _inicializar_mercados_con_backoff(exchange)
        candidatos = [
            t for sym, t in tickers.items()
            if _es_perpetuo_cripto_puro(exchange, sym)
        ]
        candidatos.sort(key=lambda t: float(t.get("quoteVolume") or 0.0), reverse=True)
        presas = [t["symbol"] for t in candidatos[:cfg.TOP_N]]

        print(
            f"[MAIN] Modo Paper: {cfg.MODO_PAPER} | Motor Salida: {cfg.MOTOR_SALIDA} | "
            f"Máx Hold: {cfg.TIEMPO_MAX_HOLD_SEG}s | Apalancamiento: {cfg.APALANCAMIENTO}x"
        )
        print(f"[MAIN] Radar fijado en {len(presas)} pares cripto-nativos.")
        print(f"[MAIN] Presas activas: {', '.join(presas)}")

        # 0. Reconciliar y liquidar posiciones huérfanas de sesiones previas ANTES de armar el Sniper
        await gestor_mod.gestor.reconciliar_posiciones_exchange(exchange)
        await _auditar_margen_libre(exchange)

        escudo.centinela.inicializar_universo(presas)
        stats.tracker.imprimir_dashboard(await stats.leer_balance_real(exchange))
        await enviar_alerta("🟩 Motor SPLITBRAIN V6.2.2 (Auto-Reconciliación + Anti-Zombie) Inicializado.")

        # 1. Tarea de Circuit Breaker Global BTC
        tareas.append(asyncio.create_task(radar.cazar_cisne_negro(exchange)))

        # 2. Tarea Demonio Centinela Groq RAM en Background
        tareas.append(asyncio.create_task(escudo.centinela.bucle_centinela_background(cfg.GROQ_CICLO_SEG)))

        # 3. Tareas del Radar para cada par seleccionado
        for symbol in presas:
            tareas.append(asyncio.create_task(vigilar_mercado(exchange, symbol)))

        # 4. Tarea Periódica del Dashboard de la Caja Negra
        tareas.append(asyncio.create_task(stats.bucle_dashboard(exchange, cfg.DASHBOARD_INTERVALO_SEG)))

        while True:
            await asyncio.sleep(1)
    finally:
        todas_las_tareas = list(tareas) + list(gestor_mod.gestor._tareas) + list(sniper._tareas_as)
        for t in todas_las_tareas:
            if not t.done():
                t.cancel()
        if todas_las_tareas:
            await asyncio.gather(*todas_las_tareas, return_exceptions=True)
        await exchange.close()
        liberar_bloqueo_instancia_unica()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN] Apagado manual completado de forma segura.")
    finally:
        liberar_bloqueo_instancia_unica()
        try:
            _log_handle.flush()
            _log_handle.close()
        except Exception:
            pass