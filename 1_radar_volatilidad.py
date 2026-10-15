"""Radar de Volatilidad y Microestructura SPLITBRAIN V6.3.0:
Incluye Detector de Contagio Cross-Asset (>= 3 pares en 10s), Evacuación Activa Macro,
Filtro de Magnitud Mínima de Caída y Verificación de Cuarentena Post-Cierre.
"""
import asyncio
import importlib
import math
import time
from collections import deque

import ccxt.pro as ccxt  # noqa: F401
import config_parametros as cfg

_escudo = importlib.import_module("2_escudo_semantico")
evaluar_anomalia_groq = _escudo.evaluar_anomalia_groq
_sniper = importlib.import_module("3_ejecutor_sniper")
ejecutar_orden_sniper = _sniper.ejecutar_orden_sniper
_gestor_mod = importlib.import_module("5_gestor_posiciones")

VENTANA = 60          # muestras (1/s -> 60 s)
COOLDOWN_S = 60
Z_CISNE_NEGRO = -4.0
BLOQUEO_S = cfg.BLOQUEO_BTC_SEG
BTC = "BTC/USDT:USDT"

bloqueo_btc_hasta: float = 0.0
_timestamps_panico: dict[str, float] = {}


class VentanaZ:
    """Z-Score rodante O(1): sumas acumuladas con piso relativo anti-ruido en mercados planos."""
    __slots__ = ("buf", "n", "s", "s2", "cnt")

    def __init__(self, n: int = VENTANA) -> None:
        self.buf: deque[float] = deque(maxlen=n)
        self.n, self.s, self.s2, self.cnt = n, 0.0, 0.0, 0

    def reset(self) -> None:
        self.buf.clear()
        self.s = self.s2 = 0.0

    def cambio_relativo(self) -> float:
        """Retorno relativo entre el inicio y el final de la ventana de 60 s."""
        if len(self.buf) < 2 or self.buf[0] <= 0:
            return 0.0
        return (self.buf[-1] - self.buf[0]) / self.buf[0]

    def caida_desde_maximo(self) -> float:
        """Retorno relativo desde el máximo rodante de los últimos 60 s hasta el precio actual."""
        if len(self.buf) < 2:
            return 0.0
        max_p = max(self.buf)
        return (self.buf[-1] - max_p) / max_p if max_p > 0 else 0.0

    def volatilidad_relativa(self) -> float:
        """Desviación estándar relativa (sigma / media) de la ventana actual en O(1)."""
        if len(self.buf) < 2:
            return getattr(cfg, "STD_REL_FLOOR", 0.0005)
        media = self.s / len(self.buf)
        if media <= 0:
            return getattr(cfg, "STD_REL_FLOOR", 0.0005)
        std = max(self.s2 / len(self.buf) - media * media, 0.0) ** 0.5
        return max(std / media, getattr(cfg, "STD_REL_FLOOR", 0.0005))

    def push(self, x: float) -> float | None:
        if x is None or not math.isfinite(x) or x <= 0:
            return None
        if len(self.buf) == self.n:
            viejo = self.buf[0]
            self.s -= viejo
            self.s2 -= viejo * viejo
        self.buf.append(x)
        self.s += x
        self.s2 += x * x
        self.cnt += 1
        if self.cnt % 10_000 == 0:
            self.s = sum(self.buf)
            self.s2 = sum(v * v for v in self.buf)
        if len(self.buf) < self.n:
            return None
        media = self.s / self.n
        std = max(self.s2 / self.n - media * media, 0.0) ** 0.5
        if std <= abs(media) * 1e-9:
            return 0.0
        piso_rel = abs(media) * getattr(cfg, "STD_REL_FLOOR", 0.0)
        std = max(std, piso_rel, cfg.STD_MIN)
        return (x - media) / std


def es_glitch(z: float | None) -> bool:
    """V6.1+: Z no finito o |Z| > Z_MAX_ABS -> ruido de datos."""
    return z is not None and (not math.isfinite(z) or abs(z) > cfg.Z_MAX_ABS)


class MediaMovilTemporal:
    """Media de los valores de los últimos `ventana_seg` segundos. O(1) amortizado."""
    __slots__ = ("ventana", "buf", "suma")

    def __init__(self, ventana_seg: float) -> None:
        self.ventana = ventana_seg
        self.buf: deque[tuple[float, float]] = deque()
        self.suma = 0.0

    def push(self, t: float, x: float | None) -> float | None:
        if x is None or not math.isfinite(x):
            return self.media()
        self.buf.append((t, x))
        self.suma += x
        while self.buf and self.buf[0][0] < t - self.ventana:
            self.suma -= self.buf.popleft()[1]
        return self.media()

    def media(self) -> float | None:
        return self.suma / len(self.buf) if len(self.buf) else None

    def cobertura(self) -> float:
        """Segundos cubiertos por los datos de la ventana."""
        return self.buf[-1][0] - self.buf[0][0] if len(self.buf) > 1 else 0.0


def calcular_ofi(ticker: dict) -> float:
    vol_bid = ticker.get("bidVolume") or 0
    vol_ask = ticker.get("askVolume") or 0
    return (vol_bid - vol_ask) / (vol_bid + vol_ask) if (vol_bid + vol_ask) > 0 else 0.0


def bloqueo_activo() -> bool:
    return time.time() < bloqueo_btc_hasta


def registrar_y_verificar_contagio(exchange, symbol: str, ahora: float) -> bool:
    """V6.3.0 Breadth Contagion Breaker:
    Registra el timestamp de pánico del símbolo y purga eventos antiguos (> CONTAGIO_VENTANA_SEG).
    Si >= CONTAGIO_MIN_PARES entran en pánico dentro de la ventana móvil, activa el bloqueo global
    y ordena la evacuación inmediata de las posiciones abiertas en PositionManager.
    """
    global bloqueo_btc_hasta
    ventana_contagio = getattr(cfg, "CONTAGIO_VENTANA_SEG", 10.0)
    min_pares = getattr(cfg, "CONTAGIO_MIN_PARES", 3)

    expirados = [s for s, ts in _timestamps_panico.items() if ahora - ts > ventana_contagio]
    for s in expirados:
        _timestamps_panico.pop(s, None)

    _timestamps_panico[symbol] = ahora
    if len(_timestamps_panico) >= min_pares:
        estaba_bloqueado = ahora < bloqueo_btc_hasta
        bloqueo_btc_hasta = max(bloqueo_btc_hasta, ahora + cfg.BLOQUEO_BTC_SEG)
        if not estaba_bloqueado:
            pares_str = ", ".join(sorted(_timestamps_panico.keys()))
            print(
                f"🔴 [CIRCUIT BREAKER CONTAGIO] ¡{len(_timestamps_panico)} pares colapsando simultáneamente "
                f"en <={ventana_contagio:.0f}s ({pares_str})! Activando escudo macro y evacuando posiciones..."
            )
            _sniper._lanzar_bg(
                _gestor_mod.gestor.evacuar_por_emergencia_macro(exchange, "CONTAGIO_CROSS_ASSET")
            )
        return True
    return False


async def cazar_cisne_negro(exchange) -> None:
    global bloqueo_btc_hasta
    ventana, ultimo_seg = VentanaZ(), 0
    ofi_btc = MediaMovilTemporal(cfg.OFI_REANUDACION_VENTANA_SEG)
    precio_pre, precio_min = None, None
    while True:
        try:
            ticker = await exchange.watch_ticker(BTC)
            ahora = time.time()
            last = ticker.get("last")
            media_ofi = ofi_btc.push(ahora, calcular_ofi(ticker))

            if ahora < bloqueo_btc_hasta and last and precio_pre and precio_min:
                precio_min = min(precio_min, last)
                caida = precio_pre - precio_min
                recuperado = (last - precio_min) / caida if caida > 0 else 1.0
                if (
                    media_ofi is not None
                    and media_ofi > cfg.OFI_REANUDACION_BTC
                    and ofi_btc.cobertura() >= cfg.OFI_REANUDACION_VENTANA_SEG * 0.8
                    and recuperado >= cfg.RECUPERACION_MIN_PCT
                ):
                    bloqueo_btc_hasta = 0.0
                    _timestamps_panico.clear()
                    ventana.reset()
                    print(
                        f"🟢 [MICROESTRUCTURA] Modo Caza Restaurado: OFI BTC {media_ofi:+.2f} "
                        f"({cfg.OFI_REANUDACION_VENTANA_SEG}s), recuperación {recuperado:.0%}"
                    )

            seg = int(ahora)
            if seg == ultimo_seg:
                continue
            ultimo_seg = seg
            z = ventana.push(last)
            if es_glitch(z):
                print(f"[MICROESTRUCTURA] Glitch de datos ignorado en BTC (Z={z})")
                continue
            if z is not None and z <= Z_CISNE_NEGRO:
                if ahora >= bloqueo_btc_hasta:
                    precio_pre, precio_min = max(ventana.buf), last
                    print("🔴 [CIRCUIT BREAKER GLOBAL] ¡BTC COLAPSÓ! Evacuando posiciones abiertas...")
                    _sniper._lanzar_bg(
                        _gestor_mod.gestor.evacuar_por_emergencia_macro(exchange, "BTC_CRASH")
                    )
                bloqueo_btc_hasta = ahora + cfg.BLOQUEO_BTC_SEG
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(1)


async def cazar_anomalia_ws(exchange, symbol: str) -> None:
    ventana, ultimo_seg = VentanaZ(), 0
    while True:
        try:
            ticker = await exchange.watch_ticker(symbol)

            if symbol in cfg.BLACKLIST_PAIRS:
                try:
                    await exchange.un_watch_tickers([symbol])
                except Exception:
                    pass
                print(f"[MICROESTRUCTURA] {symbol} en lista negra dinámica: radar desconectado.")
                return

            ahora = time.time()
            seg = int(ahora)
            if seg == ultimo_seg:
                continue
            ultimo_seg = seg

            t_inicio_ns = time.perf_counter_ns()
            ofi = calcular_ofi(ticker)
            precio_actual = ticker.get("last")
            z_actual = ventana.push(precio_actual)

            if es_glitch(z_actual):
                print(f"[MICROESTRUCTURA] Glitch de datos ignorado en {symbol} (Z={z_actual})")
                continue
            if z_actual is None:
                continue

            caida_rel = ventana.caida_desde_maximo()
            _escudo.centinela.actualizar_telemetria(
                symbol, z_actual, ofi, precio_actual, ventana.cambio_relativo()
            )

            if z_actual > cfg.UMBRAL_PANICO:
                continue

            # V6.3.0: Exigir magnitud mínima de caída real desde el máximo de la ventana de 60s
            if caida_rel > cfg.CAIDA_MIN_PCT:
                continue

            # V6.3.0: Registrar pánico y verificar contagio sistémico cross-asset (>= 3 pares en 10s)
            if registrar_y_verificar_contagio(exchange, symbol, ahora):
                print(f"[BLOQUEO] Contagio simultáneo activo: anomalía ignorada ({symbol})")
                continue

            if bloqueo_activo():
                print(f"[BLOQUEO] Anomalía ignorada ({symbol})")
                continue

            # V6.3.0: Cuarentena post-cierre de 300s (Erradicación del Serial Knife-Catching)
            if _sniper.en_cooldown_post_cierre(symbol):
                restante_cd = _gestor_mod.gestor.segundos_cooldown_restantes(symbol)
                print(
                    f"⏳ [COOLDOWN POST-CIERRE] {symbol} en cuarentena anti-knife-catching "
                    f"({restante_cd:.0f}s restantes). Disparo ignorado."
                )
                continue

            if ofi < cfg.UMBRAL_OFI_TOXICO:
                print(f"⚠️ [MICROESTRUCTURA] Flujo TÓXICO. Abortando. ({symbol} OFI={ofi:.2f})")
                continue
            if _sniper.posicion_activa(symbol):
                continue

            aprobado_ram = await evaluar_anomalia_groq(symbol)
            lat_us = (time.perf_counter_ns() - t_inicio_ns) / 1000.0
            print(
                f"[RADAR] {symbol} Z={z_actual:.2f} ({caida_rel:.2%}) OFI={ofi:.2f} -> ESCUDO RAM O(1): "
                f"{'APROBADO' if aprobado_ram else 'VETADO'} ({lat_us:.1f} µs)"
            )

            if aprobado_ram:
                if bloqueo_activo():
                    print(f"[BLOQUEO] Circuit breaker activado: disparo abortado ({symbol})")
                elif (
                    _sniper.posicion_activa(symbol)
                    or _sniper.en_cooldown_post_cierre(symbol)
                    or symbol in cfg.BLACKLIST_PAIRS
                ):
                    print(f"[RADAR] {symbol} ya no es disparable: abortado.")
                else:
                    await ejecutar_orden_sniper(
                        exchange,
                        symbol,
                        z_actual,
                        ofi,
                        ticker=ticker,
                        sigma_rel=ventana.volatilidad_relativa(),
                    )

            await asyncio.sleep(COOLDOWN_S)
            ventana.reset()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[RADAR] Error en {symbol}: {type(e).__name__}: {e}")
            await asyncio.sleep(1)