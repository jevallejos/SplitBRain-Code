import asyncio
import importlib
import math
import time
from collections import deque

import ccxt.pro as ccxt  # noqa: F401  (el exchange se inyecta desde main)
import config_parametros as cfg

# Los módulos empiezan por dígito: no admiten `import` normal.
evaluar_anomalia_groq = importlib.import_module("2_escudo_semantico").evaluar_anomalia_groq
ejecutar_orden_sniper = importlib.import_module("3_ejecutor_sniper").ejecutar_orden_sniper

VENTANA = 60          # muestras (1/s → 60 s)
COOLDOWN_S = 60
Z_CISNE_NEGRO = -4.0
BLOQUEO_S = 1800      # 30 min

bloqueo_btc_hasta = 0


class VentanaZ:
    """Z-Score rodante O(1): sumas acumuladas en vez de recorrer el deque."""
    __slots__ = ("buf", "n", "s", "s2", "cnt")

    def __init__(self, n=VENTANA):
        self.buf = deque(maxlen=n)
        self.n, self.s, self.s2, self.cnt = n, 0.0, 0.0, 0

    def reset(self):
        self.buf.clear()
        self.s = self.s2 = 0.0

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
        return (x - media) / std


async def cazar_cisne_negro(exchange):
    global bloqueo_btc_hasta
    ventana, ultimo_seg = VentanaZ(), 0
    while True:
        try:
            ticker = await exchange.watch_ticker("BTC/USDT:USDT")
            seg = int(time.time())
            if seg == ultimo_seg:
                continue
            ultimo_seg = seg
            z = ventana.push(ticker["last"])
            if z is not None and z <= Z_CISNE_NEGRO:
                bloqueo_btc_hasta = time.time() + BLOQUEO_S
                print("🔴 [CIRCUIT BREAKER GLOBAL] ¡BTC COLAPSÓ!")
        except Exception:
            pass
            await asyncio.sleep(1)


async def cazar_anomalia_ws(exchange, symbol):
    ventana, ultimo_seg = VentanaZ(), 0
    while True:
        try:
            ticker = await exchange.watch_ticker(symbol)
            seg = int(time.time())
            if seg == ultimo_seg:
                continue
            ultimo_seg = seg

            # Física de fluidos: desequilibrio del libro L1
            vol_bid = ticker.get("bidVolume") or 0
            vol_ask = ticker.get("askVolume") or 0
            ofi = (vol_bid - vol_ask) / (vol_bid + vol_ask) if (vol_bid + vol_ask) > 0 else 0

            z_actual = ventana.push(ticker["last"])
            if z_actual is None or z_actual > cfg.UMBRAL_PANICO:
                continue

            # Árbol de decisión del gatillo
            if time.time() < bloqueo_btc_hasta:
                print(f"[BLOQUEO] Anomalía ignorada ({symbol})")
                continue
            if ofi < cfg.UMBRAL_OFI_TOXICO:
                print(f"⚠️ [MICROESTRUCTURA] Flujo TÓXICO. Abortando. ({symbol} OFI={ofi:.2f})")
                continue

            print(f"[RADAR] {symbol} Z={z_actual:.2f} OFI={ofi:.2f} -> escudo LPU")
            if await evaluar_anomalia_groq(symbol):
                await ejecutar_orden_sniper(exchange, symbol, z_actual)
            await asyncio.sleep(COOLDOWN_S)  # anti multi-disparo (también tras rechazo)
            ventana.reset()                   # exige 60 s de datos frescos
        except Exception as e:
            print(f"[RADAR] Error en {symbol}: {type(e).__name__}: {e}")
            await asyncio.sleep(1)
