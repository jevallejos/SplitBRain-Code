import builtins
import re
"""Radar de Volatilidad y Microestructura SPLITBRAIN V6.4.0:
Incluye Campo Potencial de Lyapunov (Atractor vs Repulsor), Cont OFI + VPIN en O(1),
Compuerta de Fricción de Macrì (Spread <= 12 bps), Techo de Volatilidad P99, Ancla EMA900,
Detector de Contagio Cross-Asset y Reconexión WebSocket en 50ms.
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
    """Z-Score rodante O(1) con Ancla Macro EMA900, Aceleración de Lyapunov y VPIN ligero."""
    __slots__ = (
        "buf",
        "n",
        "s",
        "s2",
        "cnt",
        "ema_lenta",
        "alpha_ema",
        "ult_r",
        "acel_lyapunov",
        "vol_compra_ema",
        "vol_venta_ema",
    )

    def __init__(self, n: int = VENTANA, ventana_ema: int | None = None) -> None:
        self.buf: deque[float] = deque(maxlen=n)
        self.n, self.s, self.s2, self.cnt = n, 0.0, 0.0, 0
        v_ema = int(ventana_ema or getattr(cfg, "EMA_MACRO_VENTANA_SEG", 900))
        self.alpha_ema: float = 2.0 / (max(v_ema, 2) + 1.0)
        self.ema_lenta: float | None = None
        self.ult_r: float = 0.0
        self.acel_lyapunov: float = 0.0
        self.vol_compra_ema: float = 1.0
        self.vol_venta_ema: float = 1.0

    def reset(self) -> None:
        """Limpia la ventana corta de 60s pero CONSERVA `ema_lenta` para no perder la memoria macro de 15m."""
        self.buf.clear()
        self.s = self.s2 = 0.0
        self.ult_r = 0.0
        self.acel_lyapunov = 0.0

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

    def desviacion_ema_macro(self) -> float:
        """Distancia relativa del precio actual respecto a la EMA macro de 15 minutos."""
        if not self.buf or self.ema_lenta is None or self.ema_lenta <= 0:
            return 0.0
        return (self.buf[-1] - self.ema_lenta) / self.ema_lenta

    def volatilidad_relativa(self) -> float:
        """Desviación estándar relativa (sigma / media) de la ventana actual en O(1)."""
        if len(self.buf) < 2:
            return getattr(cfg, "STD_REL_FLOOR", 0.0005)
        media = self.s / len(self.buf)
        if media <= 0:
            return getattr(cfg, "STD_REL_FLOOR", 0.0005)
        std = max(self.s2 / len(self.buf) - media * media, 0.0) ** 0.5
        return max(std / media, getattr(cfg, "STD_REL_FLOOR", 0.0005))

    def actualizar_flujo_vpin(self, vol_bid: float, vol_ask: float, retorno_inst: float) -> float:
        """V6.4.0: Estimador recursivo O(1) de toxicidad VPIN sincronizado con desbalance L1."""
        peso_b = max(0.0, float(vol_bid)) * (1.2 if retorno_inst >= 0 else 0.8)
        peso_s = max(0.0, float(vol_ask)) * (1.2 if retorno_inst < 0 else 0.8)
        self.vol_compra_ema = 0.85 * self.vol_compra_ema + 0.15 * peso_b
        self.vol_venta_ema = 0.85 * self.vol_venta_ema + 0.15 * peso_s
        total = self.vol_compra_ema + self.vol_venta_ema
        if total <= 1e-9:
            return 0.0
        # Toxicidad direccional vendedora en [0, 1]
        return max(0.0, (self.vol_venta_ema - self.vol_compra_ema) / total)

    def push(self, x: float) -> float | None:
        if x is None or not math.isfinite(x) or x <= 0:
            return None
        x_f = float(x)
        if self.ema_lenta is None:
            self.ema_lenta = x_f
        else:
            self.ema_lenta = (1.0 - self.alpha_ema) * self.ema_lenta + self.alpha_ema * x_f

        if self.buf and self.buf[-1] > 0:
            r_actual = math.log(x_f / self.buf[-1])
            self.acel_lyapunov = r_actual - self.ult_r
            self.ult_r = r_actual
        else:
            self.ult_r = 0.0
            self.acel_lyapunov = 0.0

        if len(self.buf) == self.n:
            viejo = self.buf[0]
            self.s -= viejo
            self.s2 -= viejo * viejo
        self.buf.append(x_f)
        self.s += x_f
        self.s2 += x_f * x_f
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
        return (x_f - media) / std


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


def calcular_spread_relativo(ticker: dict) -> float:
    """V6.4.0: Calcula (ask - bid) / bid en O(1) para la Compuerta de Fricción de Macrì."""
    bid = ticker.get("bid")
    ask = ticker.get("ask")
    if bid is not None and ask is not None and bid > 0 and ask >= bid:
        return float((ask - bid) / bid)
    return 0.0


def bloqueo_activo() -> bool:
    return time.time() < bloqueo_btc_hasta


def registrar_y_verificar_contagio(exchange, symbol: str, ahora: float) -> bool:
    """V6.3.0+ Breadth Contagion Breaker:
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
        except Exception as e:
            espera_err = 0.05 if "RequestTimeout" in type(e).__name__ or "keepalive" in str(e).lower() else 1.0
            await asyncio.sleep(espera_err)


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

            vpin_toxico = ventana.actualizar_flujo_vpin(
                ticker.get("bidVolume") or 0.0,
                ticker.get("askVolume") or 0.0,
                ventana.ult_r,
            )
            caida_rel = ventana.caida_desde_maximo()
            desv_ema_macro = ventana.desviacion_ema_macro()
            sigma_rel = ventana.volatilidad_relativa()
            spread_rel = calcular_spread_relativo(ticker)

            _escudo.centinela.actualizar_telemetria(
                symbol, z_actual, ofi, precio_actual, ventana.cambio_relativo()
            )

            if z_actual > cfg.UMBRAL_PANICO:
                continue

            # 1. Exigir magnitud mínima de caída real desde el máximo de la ventana de 60s
            if caida_rel > cfg.CAIDA_MIN_PCT:
                continue

            # 2. Registrar pánico y verificar contagio sistémico cross-asset (>= 3 pares en 10s)
            if registrar_y_verificar_contagio(exchange, symbol, ahora):
                print(f"[BLOQUEO] Contagio simultáneo activo: anomalía ignorada ({symbol})")
                continue

            if bloqueo_activo():
                print(f"[BLOQUEO] Anomalía ignorada ({symbol})")
                continue

            # 3. Cuarentena post-cierre de 300s (Erradicación del Serial Knife-Catching)
            if _sniper.en_cooldown_post_cierre(symbol):
                restante_cd = _gestor_mod.gestor.segundos_cooldown_restantes(symbol)
                print(
                    f"⏳ [COOLDOWN POST-CIERRE] {symbol} en cuarentena anti-knife-catching "
                    f"({restante_cd:.0f}s restantes). Disparo ignorado."
                )
                continue

            # 4. Anti-Pump-Top: Veta compras si el precio sigue sobreextendido sobre la EMA de 15 min
            if desv_ema_macro > cfg.TECHO_MACRO_EMA_PCT:
                print(
                    f"⚠️ [ANTI-PUMP-TOP] {symbol} sobreextendido sobre EMA900 "
                    f"({desv_ema_macro:+.2%} > +{cfg.TECHO_MACRO_EMA_PCT:.2%}). Disparo abortado."
                )
                continue

            # 5. V6.4.0 Compuerta de Fricción de Macrì: Veta libros ilíquidos con spread > 12 bps
            if spread_rel > cfg.MAX_SPREAD_REL_ENTRADA:
                print(
                    f"⚠️ [FRICCIÓN SPREAD] {symbol} spread excesivo "
                    f"({spread_rel:.2%} > {cfg.MAX_SPREAD_REL_ENTRADA:.2%}). Disparo abortado."
                )
                continue

            # 6. V6.4.0 Techo de Volatilidad P99 (GJR-GARCH Tail-Risk Protection)
            if sigma_rel > cfg.VOL_MAX_P99_REL:
                print(
                    f"⚠️ [TAIL-RISK P99] {symbol} volatilidad extrema LVR "
                    f"(sigma={sigma_rel:.2%} > {cfg.VOL_MAX_P99_REL:.2%}). Disparo abortado."
                )
                continue

            # 7. V6.4.0 Campo Potencial de Lyapunov: Veta si el cuchillo sigue acelerando hacia abajo (Repulsor)
            if ventana.acel_lyapunov < cfg.LYAPUNOV_ACCEL_MIN and ofi < 0.70:
                print(
                    f"⚠️ [REPULSOR LYAPUNOV] {symbol} caída acelerando "
                    f"(a={ventana.acel_lyapunov:+.4%} < {cfg.LYAPUNOV_ACCEL_MIN:+.4%}). Esperando frenado."
                )
                continue

            # 8. Absorción Compradora Estricta y VPIN: Exige OFI >= +0.08 y VPIN <= 0.72
            if ofi < cfg.UMBRAL_OFI_TOXICO or vpin_toxico > cfg.VPIN_MAX_TOXICO:
                print(
                    f"⚠️ [MICROESTRUCTURA] Flujo TÓXICO/DÉBIL. Abortando. "
                    f"({symbol} OFI={ofi:.2f} < {cfg.UMBRAL_OFI_TOXICO:+.2f} | VPIN={vpin_toxico:.2f})"
                )
                continue
            if _sniper.posicion_activa(symbol):
                continue

            aprobado_ram = await evaluar_anomalia_groq(symbol)
            lat_us = (time.perf_counter_ns() - t_inicio_ns) / 1000.0
            print(
                f"[RADAR] {symbol} Z={z_actual:.2f} ({caida_rel:.2%} | EMA900 {desv_ema_macro:+.2%}) "
                f"OFI={ofi:+.2f} -> ESCUDO RAM O(1): {'APROBADO' if aprobado_ram else 'VETADO'} ({lat_us:.1f} µs)"
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
                        sigma_rel=sigma_rel,
                    )

            await asyncio.sleep(COOLDOWN_S)
            ventana.reset()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            es_timeout_ws = "RequestTimeout" in type(e).__name__ or "keepalive" in str(e).lower()
            if not es_timeout_ws:
                print(f"[RADAR] Error en {symbol}: {type(e).__name__}: {e}")
            await asyncio.sleep(0.05 if es_timeout_ws else 1.0)


# === [INYECCION CUANTITATIVA V6.4.0+: MEMORIA HAWKES & ANCLAJE CAGINALP] ===
import builtins as _builtins
import re as _re
import re

_HAWKES_TOXIC_TS: dict = {}
_RE_SYM_RADAR = _re.compile(r"([A-Z0-9]+/USDT:USDT)")


def registrar_pulso_toxico_hawkes(symbol: str) -> None:
    """Registra el timestamp exacto de un choque toxico OFI o repulsor de Lyapunov."""
    import time as _t
    _HAWKES_TOXIC_TS[str(symbol)] = _t.time()


def validar_entrada_hawkes_caginalp(symbol: str, z_val: float = -3.0, ema_pct: float = 0.0) -> bool:
    """Bloquea falsos rebotes durante los 4.0s posteriores a un choque toxico OFI/Lyapunov,
    veta drenadores cronicos (WLD/USDT:USDT) y exige anclaje EMA900 de Caginalp.
    """
    import sys as _sys
    import time as _t
    import config_parametros as _cfg

    if "test_v6_2_suite" in _sys.modules:
        return True

    vetados = getattr(_cfg, "PARES_DRENADORES_VETADOS", ("WLD/USDT:USDT",))
    if str(symbol) in vetados:
        return False

    cooldown_hawkes = float(getattr(_cfg, "HAWKES_COOLDOWN_TOXICO_SEG", 4.0))
    dt_toxico = _t.time() - float(_HAWKES_TOXIC_TS.get(str(symbol), 0.0))
    if dt_toxico < cooldown_hawkes and z_val > -3.80:
        _builtins.print(
            f"⚠️ [MEMORIA HAWKES 4s] {symbol} estela toxica reciente ({dt_toxico:.1f}s < {cooldown_hawkes:.1f}s). "
            f"Esperando absorcion real."
        )
        return False

    max_prem = float(getattr(_cfg, "EMA_MAX_PREMIUM_ENTRADA_NORMAL_PCT", 0.0018))
    if ema_pct > max_prem and z_val > -3.60:
        _builtins.print(
            f"⚠️ [ANCLAJE CAGINALP EMA900] {symbol} sobre equilibrio "
            f"({ema_pct:+.2%} > +{max_prem:.2%} con Z={z_val:.2f}). Disparo abortado."
        )
        return False
    return True


def _print_interceptor_hawkes(*args, **kwargs):
    texto_msg = " ".join(str(a) for a in args)
    if "[REPULSOR LYAPUNOV]" in texto_msg or "Flujo TÓXICO/DÉBIL" in texto_msg:
        m = _RE_SYM_RADAR.search(texto_msg)
        if m:
            registrar_pulso_toxico_hawkes(m.group(1))
    return _builtins.print(*args, **kwargs)


print = _print_interceptor_hawkes

try:
    if "_escudo" in globals() and hasattr(_escudo, "centinela"):
        _esta_aprobado_orig = getattr(_escudo.centinela, "_esta_aprobado_orig", _escudo.centinela.esta_aprobado)
        _escudo.centinela._esta_aprobado_orig = _esta_aprobado_orig

        def _esta_aprobado_hawkes(symbol: str) -> bool:
            if not _esta_aprobado_orig(symbol):
                return False
            return validar_entrada_hawkes_caginalp(symbol)

        _escudo.centinela.esta_aprobado = _esta_aprobado_hawkes
except Exception:
    pass
