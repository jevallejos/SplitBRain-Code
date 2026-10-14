import asyncio
import importlib
import math
import time
from collections import deque

import ccxt.pro as ccxt  # noqa: F401  (el exchange se inyecta desde main)
import config_parametros as cfg

# Los módulos empiezan por dígito: no admiten `import` normal.
_escudo = importlib.import_module("2_escudo_semantico")
evaluar_anomalia_groq = _escudo.evaluar_anomalia_groq
_sniper = importlib.import_module("3_ejecutor_sniper")
ejecutar_orden_sniper = _sniper.ejecutar_orden_sniper

VENTANA = 60          # muestras (1/s → 60 s)
COOLDOWN_S = 60
Z_CISNE_NEGRO = -4.0
BLOQUEO_S = cfg.BLOQUEO_BTC_SEG   # V6.1: 5 min (antes 1800 s fijos)
BTC = "BTC/USDT:USDT"

bloqueo_btc_hasta = 0


class VentanaZ:
    """Z-Score rodante O(1): sumas acumuladas con piso relativo anti-ruido en mercados planos."""
    __slots__ = ("buf", "n", "s", "s2", "cnt")

    def __init__(self, n=VENTANA):
        self.buf = deque(maxlen=n)
        self.n, self.s, self.s2, self.cnt = n, 0.0, 0.0, 0

    def reset(self):
        self.buf.clear()
        self.s = self.s2 = 0.0

    def cambio_relativo(self) -> float:
        """Retorno relativo entre el inicio y el final de la ventana de 60 s."""
        if len(self.buf) < 2 or self.buf[0] <= 0:
            return 0.0
        return (self.buf[-1] - self.buf[0]) / self.buf[0]

    def push(self, x):
        # Validar ANTES de mutar: un None/NaN dentro del deque envenenaría la ventana para siempre.
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
        if self.cnt % 10_000 == 0:  # re-sincroniza contra deriva de coma flotante (O(1) amortizado)
            self.s = sum(self.buf)
            self.s2 = sum(v * v for v in self.buf)
        if len(self.buf) < self.n:
            return None  # calentando
        media = self.s / self.n
        std = max(self.s2 / self.n - media * media, 0.0) ** 0.5
        if std <= abs(media) * 1e-9:  # precio plano: evita Z gigantes por ruido numérico
            return 0.0
        # V6.2: piso de volatilidad relativa (STD_REL_FLOOR) + piso absoluto (STD_MIN)
        piso_rel = abs(media) * getattr(cfg, "STD_REL_FLOOR", 0.0)
        std = max(std, piso_rel, cfg.STD_MIN)
        return (x - media) / std


def es_glitch(z):
    """V6.1: Z no finito o |Z| > Z_MAX_ABS → ruido de datos (vacíos del orderbook)."""
    return z is not None and (not math.isfinite(z) or abs(z) > cfg.Z_MAX_ABS)


class MediaMovilTemporal:
    """Media de los valores de los últimos `ventana_seg` segundos. O(1) amortizado."""
    __slots__ = ("ventana", "buf", "suma")

    def __init__(self, ventana_seg):
        self.ventana = ventana_seg
        self.buf = deque()  # (t, valor)
        self.suma = 0.0

    def push(self, t, x):
        if x is None or not math.isfinite(x):
            return self.media()
        self.buf.append((t, x))
        self.suma += x
        while self.buf and self.buf[0][0] < t - self.ventana:
            self.suma -= self.buf.popleft()[1]
        return self.media()

    def media(self):
        return self.suma / len(self.buf) if len(self.buf) else None

    def cobertura(self):
        """Segundos cubiertos por los datos de la ventana."""
        return self.buf[-1][0] - self.buf[0][0] if len(self.buf) > 1 else 0.0


def calcular_ofi(ticker):
    # Física de fluidos: desequilibrio del libro L1
    vol_bid = ticker.get("bidVolume") or 0
    vol_ask = ticker.get("askVolume") or 0
    return (vol_bid - vol_ask) / (vol_bid + vol_ask) if (vol_bid + vol_ask) > 0 else 0


def bloqueo_activo():
    return time.time() < bloqueo_btc_hasta


async def cazar_cisne_negro(exchange):
    global bloqueo_btc_hasta
    ventana, ultimo_seg = VentanaZ(), 0
    ofi_btc = MediaMovilTemporal(cfg.OFI_REANUDACION_VENTANA_SEG)
    precio_pre, precio_min = None, None   # máximo previo al colapso y mínimo durante el bloqueo
    while True:
        try:
            ticker = await exchange.watch_ticker(BTC)
            ahora = time.time()
            last = ticker.get("last")
            media_ofi = ofi_btc.push(ahora, calcular_ofi(ticker))  # cada tick, no solo 1/s

            # V6.1 Regla de excepción cuántica (V-shape): absorción institucional + recuperación de precio
            if ahora < bloqueo_btc_hasta and last and precio_pre and precio_min:
                precio_min = min(precio_min, last)
                caida = precio_pre - precio_min
                recuperado = (last - precio_min) / caida if caida > 0 else 1.0
                if (media_ofi is not None and media_ofi > cfg.OFI_REANUDACION_BTC
                        and ofi_btc.cobertura() >= cfg.OFI_REANUDACION_VENTANA_SEG * 0.8
                        and recuperado >= cfg.RECUPERACION_MIN_PCT):
                    bloqueo_btc_hasta = 0
                    ventana.reset()  # exige 60 s frescos: sin re-armado inmediato con los precios del colapso
                    print(f"🟢 [MICROESTRUCTURA] Modo Caza Restaurado: OFI BTC {media_ofi:+.2f} "
                          f"({cfg.OFI_REANUDACION_VENTANA_SEG}s), recuperación {recuperado:.0%}")

            seg = int(ahora)
            if seg == ultimo_seg:
                continue
            ultimo_seg = seg
            z = ventana.push(last)
            if es_glitch(z):
                print(f"[MICROESTRUCTURA] Glitch de datos ignorado en BTC (Z={z})")
                continue
            if z is not None and z <= Z_CISNE_NEGRO:
                if ahora >= bloqueo_btc_hasta:  # nuevo colapso (no renovación)
                    precio_pre, precio_min = max(ventana.buf), last
                    print("🔴 [CIRCUIT BREAKER GLOBAL] ¡BTC COLAPSÓ!")
                bloqueo_btc_hasta = ahora + BLOQUEO_S
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(1)


async def cazar_anomalia_ws(exchange, symbol):
    ventana, ultimo_seg = VentanaZ(), 0
    while True:
        try:
            ticker = await exchange.watch_ticker(symbol)

            # V6.1 Auto-blacklist: el francotirador marcó el par (p. ej. Bybit 110126) → soltar el stream
            if symbol in cfg.BLACKLIST_PAIRS:
                try:
                    await exchange.un_watch_tickers([symbol])
                except Exception:
                    pass
                print(f"[MICROESTRUCTURA] {symbol} en lista negra dinámica: radar desconectado.")
                return

            seg = int(time.time())
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

            # V6.2: Alimentar telemetría en RAM para que el Centinela Groq la audite en background
            _escudo.centinela.actualizar_telemetria(
                symbol, z_actual, ofi, precio_actual, ventana.cambio_relativo()
            )

            if z_actual > cfg.UMBRAL_PANICO:
                continue

            # Árbol de decisión del gatillo en sub-milisegundos
            if bloqueo_activo():
                print(f"[BLOQUEO] Anomalía ignorada ({symbol})")
                continue
            if ofi < cfg.UMBRAL_OFI_TOXICO:
                print(f"⚠️ [MICROESTRUCTURA] Flujo TÓXICO. Abortando. ({symbol} OFI={ofi:.2f})")
                continue
            if _sniper.posicion_activa(symbol):
                continue  # ya hay una posición gestionándose en este par

            # V6.2: Verificación Lock-Free O(1) en memoria RAM (sin latencia HTTP de Groq en la ruta crítica)
            aprobado_ram = await evaluar_anomalia_groq(symbol)
            lat_us = (time.perf_counter_ns() - t_inicio_ns) / 1000.0
            print(f"[RADAR] {symbol} Z={z_actual:.2f} OFI={ofi:.2f} -> ESCUDO RAM O(1): "
                  f"{'APROBADO' if aprobado_ram else 'VETADO'} ({lat_us:.1f} µs)")

            if aprobado_ram:
                if bloqueo_activo():
                    print(f"[BLOQUEO] Circuit breaker activado: disparo abortado ({symbol})")
                elif _sniper.posicion_activa(symbol) or symbol in cfg.BLACKLIST_PAIRS:
                    print(f"[RADAR] {symbol} ya no es disparable: abortado.")
                else:
                    await ejecutar_orden_sniper(exchange, symbol, z_actual, ofi)

            await asyncio.sleep(COOLDOWN_S)  # anti multi-disparo (también tras rechazo)
            ventana.reset()                   # exige 60 s de datos frescos
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[RADAR] Error en {symbol}: {type(e).__name__}: {e}")
            await asyncio.sleep(1)
