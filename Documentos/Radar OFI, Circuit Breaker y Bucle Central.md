# Radar OFI, Circuit Breaker y Bucle Central

**Proyecto:** SPLITBRAIN V5.0 (bot de trading cuantitativo, asíncrono)
**Fase:** Detección (radar Z-Score + OFI), circuit breaker global por BTC y orquestador principal
**Estado:** ✅ Pipeline completo ensamblado · ✅ Tests offline superados · ✅ Prueba real en `MODO_PAPER=True` · ⚠️ **La prueba en paper confirma falsos positivos sistemáticos (sección 8)**
**Fecha:** 2026-10-13
**Ruta del proyecto:** `d:\dev\SplitBRain-Code` (Windows, PowerShell)
**Documentos previos:** `Parámetros Base y Telemetría Silenciada.md`, `Escudo Semántico LPU (Groq).md`, `Ejecutor Sniper (Bybit PostOnly).md`

---

## 1. Objetivo

Cerrar el pipeline:

```
main.py ──► fetch_tickers → TOP_N (excluye PROHIBIDAS)
   ├─► cazar_cisne_negro(BTC)          → bloqueo global 30 min si Z_BTC ≤ −4
   └─► cazar_anomalia_ws(símbolo) ×15
          Z ≤ UMBRAL_PANICO (−2,6)?
            ├─ bloqueo BTC activo?      → [BLOQUEO] ignorar
            ├─ OFI < UMBRAL_OFI_TOXICO? → ⚠️ TÓXICO, abortar
            └─ escudo Groq (2_) ─True─► sniper (3_) → telemetría (4_)
                 └─ cooldown 60 s + reset de ventana
```

Restricción del usuario: código asíncrono O(1).

---

## 2. Estado del proyecto

```
SplitBRain-Code/
├── .env                          (5 credenciales; claves de Bybit válidas: fetch_balance retCode 0)
├── requirements.txt              (ccxt 4.5.87 con ccxt.pro, groq 1.7.0, aiohttp, python-dotenv)
├── config_parametros.py          (MODO_PAPER=True, TOP_N=15, UMBRAL_PANICO=-2.6, UMBRAL_OFI_TOXICO=-0.5)
├── 1_radar_volatilidad.py        ← NUEVO
├── 2_escudo_semantico.py
├── 3_ejecutor_sniper.py
├── 4_telemetria_telegram.py
└── main.py                       ← NUEVO (punto de entrada: python main.py)
```

---

## 3. Investigación previa en vivo (datos públicos de Bybit)

| Prueba | Resultado |
|---|---|
| `ccxt.pro` disponible en ccxt 4.5.87 | ✅ |
| `fetch_tickers()` sin parámetros | 912 tickers; **804 terminan en `USDT:USDT`** → no hace falta `defaultType` |
| `watch_ticker` trae `bidVolume`/`askVolume` | ✅ (p. ej. SOL `bidVol=189.3`, `askVol=838.2`) |
| **Frecuencia de `watch_ticker`** | SOL **4,0 updates/s con solo 2 precios distintos en 5 s**; BTC 3,2/s con 5 precios distintos |

Conclusión clave: una ventana de 60 *ticks* (spec original) ≈ 15 s de precio casi constante → la desviación estándar es diminuta y un solo tick produce Z extremos.

---

## 4. Desviaciones de la spec (aprobadas por el usuario)

| # | Spec original | Implementación | Motivo |
|---|---|---|---|
| 1 | `deque(maxlen=60)` con cada tick | **1 muestra por segundo** (primer tick de cada segundo) → ventana de 60 s reales | Con ticks crudos el Z mide ruido de cotización (ver sección 3). |
| 2 | Media/std recalculadas sobre el deque | Clase `VentanaZ` con **sumas acumuladas** (Σx, Σx²) → **O(1)** por tick | Cumplir la restricción O(1). Re-sincronización cada 10 000 muestras contra la deriva de coma flotante (O(1) amortizado). |
| 3 | Cooldown 60 s solo si Groq aprueba | Cooldown **tras cualquier evaluación de Groq** | Evitar una llamada a Groq por segundo mientras el Z siga bajo y Groq rechace. |
| 4 | — | **`ventana.reset()` tras el cooldown** | Sin reset, el deque conserva los precios previos al colapso → re-disparo inmediato → entrada duplicada. |
| 5 | `print` con 🔴/⚠️ | Textos exactos de la spec + `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` en `main.py` | En Windows, con la salida redirigida (cp1252), los emojis lanzan `UnicodeEncodeError` (bug ya visto en el sniper). |
| 6 | `from 2_... import` / módulos 2, 3, 4 | `importlib.import_module(...)` | Un nombre de módulo que empieza por dígito es SyntaxError. |
| 7 | — | Lista `tareas` + `try/finally: exchange.close()` + `except KeyboardInterrupt` | Referencias fuertes a las tareas (el GC de asyncio), cierre limpio de websockets y apagado sin traceback. |
| 8 | — | `print` adicional con la lista de presas | Diagnóstico. |

---

## 5. Código final

### 5.1 `1_radar_volatilidad.py`

```python
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
```

### 5.2 `main.py`

```python
import asyncio
import importlib
import sys

import ccxt.pro as ccxt
import config_parametros as cfg

radar = importlib.import_module("1_radar_volatilidad")
vigilar_mercado = radar.cazar_anomalia_ws
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta

# Consola a prueba de emojis (Windows usa cp1252 al redirigir la salida a log/pipe)
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")


async def main():
    print("==================================================")
    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V5.0 - ARQUITECTURA CUÁNTICA OFI)")
    print("==================================================")
    await enviar_alerta("🟩 Motor SPLITBRAIN V5.0 Inicializado.")

    exchange = ccxt.bybit({"apiKey": cfg.BYBIT_API_KEY, "secret": cfg.BYBIT_API_SECRET})
    tareas = []  # referencias fuertes: evita que el GC destruya tareas en curso
    try:
        await exchange.load_markets()
        tickers = await exchange.fetch_tickers()
        candidatos = [t for sym, t in tickers.items()
                      if sym.endswith("USDT:USDT") and sym not in cfg.PROHIBIDAS]
        candidatos.sort(key=lambda t: t.get("quoteVolume") or 0, reverse=True)
        presas = [t["symbol"] for t in candidatos[:cfg.TOP_N]]
        print(f"[MAIN] Radar fijado en {len(presas)} pares.")
        print(f"[MAIN] Presas: {', '.join(presas)}")

        tareas.append(asyncio.create_task(radar.cazar_cisne_negro(exchange)))
        for symbol in presas:
            tareas.append(asyncio.create_task(vigilar_mercado(exchange, symbol)))

        while True:
            await asyncio.sleep(1)
    finally:
        for t in tareas:
            t.cancel()
        await exchange.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN] Apagado manual.")
```

---

## 6. Verificación offline (sin red, sin Groq, sin Telegram)

### 6.1 Precisión de `VentanaZ` frente a `statistics.pstdev` (200 000 muestras con deriva)

| Escala de precio | Error máx. del Z |
|---|---|
| BTC (~83 000) | 2,9e-07 |
| SOL (~107) | 2,9e-08 |
| Memecoin (~0,0001) | 2,1e-09 |

Calentamiento → `None` ✅ · Precio plano → `0.0` ✅

### 6.2 Árbol de decisión (exchange y reloj simulados, 4 ticks/s; Groq y sniper sustituidos por stubs)

| Caso | Resultado |
|---|---|
| Pánico limpio + Groq aprueba | 1 Groq, 1 sniper (`Z=-7.67`), **sin re-disparo** tras el reset ✅ |
| OFI tóxico (−0,80) | Aviso ⚠️, 0 Groq ✅ |
| Circuit breaker BTC activo | `[BLOQUEO]`, 0 Groq ✅ |
| Groq rechaza | 1 sola llamada, sin bucle ✅ |
| Ticker `last=None` / `NaN` y luego pánico | Se ignoran sin dañar la ventana; el pánico posterior se detecta ✅ |
| Colapso de BTC | 🔴 CIRCUIT BREAKER, bloqueo 1800 s ✅ |

### 6.3 Bug encontrado y corregido durante los tests
Un `last=None` se añadía al deque **antes** de que `self.s += x` lanzara `TypeError`. Al llegar ese `None` al frente de la ventana, cada `push` posterior fallaba en `self.s -= viejo`: **el símbolo quedaba inutilizado para siempre** (un error por segundo). Lo mismo pasaría con `NaN` (envenena las sumas). **Corrección:** validar `x` antes de mutar el estado.

### 6.4 Propiedad matemática relevante
Con N = 60 y el punto actual incluido en la ventana, |Z| ≤ √(N−1) ≈ **7,68**. El Z mínimo alcanzable es −7,68: los umbrales −2,6 y −4,0 son alcanzables, pero cualquier umbral por debajo de −7,68 nunca dispararía.

---

## 7. Prueba real en `MODO_PAPER=True`

Ejecución: `python -u main.py` con stdout/stderr redirigidos a fichero (eso prueba también el blindaje de emojis), con conexión real a Bybit (websockets públicos + endpoints privados con las claves del `.env`), Groq real y Telegram real. **Sin órdenes reales** (el sniper sale en el bloque paper).

### 7.1 Intento 1 — 19:51:00 (UTC−3) — ❌ caída en el arranque

Salida: solo el banner. El proceso **murió antes de 120 s** con:

```
main.py, line 26: await exchange.load_markets()
  → bybit.fetch_currencies() → privateGetV5AssetCoinQueryInfo
  → aiohttp _resolve_host → CancelledError → TimeoutError
ccxt.base.errors.RequestTimeout: bybit GET https://api.bybit.com/v5/asset/coin/query-info?
```

**Diagnóstico posterior** (mismo equipo, minutos después, solo lectura):

| Llamada | Ronda 1 | Ronda 2 |
|---|---|---|
| `fetch_time` (público) | **6 377 ms** (DNS en frío) | 937 ms |
| `fetch_currencies` (privado) | 2 052 ms | 2 079 ms |
| `load_markets` (con claves) | 5 346 ms | — |
| `fetch_balance` (privado) | 1 098 ms, `retCode 0` ✅ | — |

**Causa:** resolución DNS lenta y transitoria que superó el timeout por defecto de ccxt (10 s). Las claves son válidas. Hallazgos:
- **Con claves, `load_markets` llama a un endpoint privado** (`/v5/asset/coin/query-info`) que añade ~2 s al arranque y un punto de fallo extra. Sin claves (sondas previas) no se llama.
- **`main.py` no tiene reintentos en el arranque:** un único fallo transitorio de red mata el bot.
- **La alerta "🟩 Motor SPLITBRAIN V5.0 Inicializado." se envía antes de `load_markets`:** si el arranque falla, Telegram anuncia que el motor está vivo cuando ya ha muerto (y el error queda silenciado por el filtro).

### 7.2 Intento 2 — 19:55:35 → 19:58:05 (UTC−3) — ✅ 150 s estable

Proceso **vivo a los 150 s**, **stderr vacío**, emojis escritos correctamente en el log redirigido. Salida completa:

```
==================================================
INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V5.0 - ARQUITECTURA CUÁNTICA OFI)
==================================================
[MAIN] Radar fijado en 15 pares.
[MAIN] Presas: SOL/USDT:USDT, ZEC/USDT:USDT, NEAR/USDT:USDT, XRP/USDT:USDT, XAU/USDT:USDT, HYPE/USDT:USDT, ENA/USDT:USDT, STRK/USDT:USDT, WLD/USDT:USDT, KORU/USDT:USDT, NVDA/USDT:USDT, SKHYNIX/USDT:USDT, SNDK/USDT:USDT, DOGE/USDT:USDT, ADA/USDT:USDT
[RADAR] NEAR/USDT:USDT Z=-3.19 OFI=-0.46 -> escudo LPU
🔴 [CIRCUIT BREAKER GLOBAL] ¡BTC COLAPSÓ!
[BLOQUEO] Anomalía ignorada (XRP/USDT:USDT)
[PAPER TRADING] Ejecución simulada
```

### 7.3 Contraste con el mercado real (velas de 1 m de Bybit, UTC)

**BTC/USDT:USDT** — el "colapso" que activó el circuit breaker:

| Minuto | O | H | L | C | Rango | Retorno |
|---|---|---|---|---|---|---|
| 22:55 | 83491.2 | 83493.5 | 83491.2 | 83493.5 | 0,003 % | +0,003 % |
| 22:56 | 83493.5 | 83493.5 | 83493.4 | 83493.5 | **0,000 %** | +0,000 % |
| 22:57 | 83493.5 | 83493.5 | 83485.4 | 83485.5 | 0,010 % | −0,010 % |
| 22:58 | 83485.5 | 83485.5 | **83459.2** | 83478.3 | 0,032 % | −0,009 % |

→ El circuit breaker saltó por una bajada de **≈ −0,04 %** (≈ 34 USD) tras un minuto completamente plano.

**NEAR/USDT:USDT** — el pánico que el escudo aprobó:

| Minuto | O | H | L | C | Rango | Retorno |
|---|---|---|---|---|---|---|
| 22:56 | 5.073 | 5.074 | 5.069 | 5.070 | 0,099 % | −0,059 % |
| 22:57 | 5.070 | 5.071 | **5.062** | 5.062 | 0,178 % | **−0,158 %** |
| 22:58 | 5.062 | 5.066 | 5.059 | 5.064 | 0,138 % | +0,040 % |

→ "Pánico" con Z = −3,19 por una caída de **≈ −0,16 %**. El escudo Groq lo **aprobó** y el sniper habría comprado en real.

**XRP/USDT:USDT** — rango máximo del 0,051 % en esos minutos: también un movimiento trivial, bloqueado solo por el falso circuit breaker.

---

## 8. 🚨 Hallazgos críticos de la prueba en paper

> [!CAUTION]
> **1. El Z-Score sobre 60 s de precio confunde micro-ruido con colapsos.** En ~90 s de radar activo (tras 60 s de calentamiento) hubo **1 entrada aprobada** (NEAR, −0,16 %) y **1 circuit breaker global** (BTC, −0,04 %). El Z normaliza por la volatilidad del último minuto: en mercado tranquilo la std es casi cero y cualquier tick da Z extremos. Es exactamente el riesgo anticipado en el plan, ahora confirmado con datos reales.

> [!CAUTION]
> **2. Carrera entre el circuit breaker y la ejecución.** Secuencia real: NEAR dispara → se llama a Groq → **mientras Groq responde salta el breaker de BTC** → Groq aprueba → **el sniper ejecuta igualmente** (`[PAPER TRADING]` aparece después del 🔴). El bloqueo solo se comprueba antes de Groq, no justo antes de disparar. En real, se habría abierto una posición con el circuit breaker global activo.

> [!WARNING]
> **3. La lista negra no cubre los sintéticos actuales.** El TOP_N incluyó **XAU** (oro), **NVDA**, **SKHYNIX**, **SNDK** (acciones tokenizadas) y **KORU** (ETF apalancado tokenizado). `PROHIBIDAS` es una lista estática de 10 símbolos y no refleja el objetivo declarado ("Filtro de Compliance y Sintéticos"). Su microestructura (horario de mercado subyacente, gaps, oráculos) es distinta a la de las criptos.

> [!WARNING]
> **4. Arranque frágil.** Sin reintentos en `load_markets`/`fetch_tickers`, un fallo DNS transitorio tumbó el bot (intento 1). Además, la alerta de arranque se envía antes de confirmar la conexión.

5. **El circuit breaker se auto-prolonga:** cada segundo con Z_BTC ≤ −4 renueva los 30 min. Con el ruido observado, en mercado plano podría mantener el sistema bloqueado de forma casi permanente.
6. **"OFI" = queue imbalance L1 instantáneo**, no el OFI de Cont et al. (que usa variaciones del libro entre eventos). El caso NEAR (OFI −0,46, a 0,04 del umbral tóxico) muestra lo cerca que queda de filtrar o no por pura fluctuación del tamaño del mejor nivel. Es manipulable con spoofing.
7. **Presas fijas:** el TOP_N se calcula una sola vez al arrancar.
8. **Concurrencia de capital** (heredado del sniper): varios disparos simultáneos leen el mismo saldo.

---

## 9. Mejoras propuestas (no implementadas; pendientes de decisión)

| # | Mejora | Ataca |
|---|---|---|
| A | **Filtro de magnitud mínima:** exigir además una caída absoluta (p. ej. ≥ 1,5–3 % en la ventana) o un retorno por debajo de k·ATR de horizonte mayor | Hallazgo 1 |
| B | **Suelo de volatilidad en el Z:** `std_efectiva = max(std, σ_min)` con σ_min derivado de volatilidad diaria/horaria o de N ticks | Hallazgos 1 y 5 |
| C | **Ventanas más largas o multi-escala:** Z de retornos en 5–15 min, o confirmación cruzada 1 m + 5 m | Hallazgo 1 |
| D | **Re-comprobar `bloqueo_btc_hasta` justo antes de `ejecutar_orden_sniper`** (y opcionalmente dentro del sniper) | Hallazgo 2 |
| E | **Circuit breaker BTC con umbral de magnitud** (p. ej. caída ≥ 2 % en 5 min) y sin auto-renovación por ruido | Hallazgos 1 y 5 |
| F | **Filtro de sintéticos dinámico:** usar los metadatos de mercado de ccxt/Bybit (tipo de subyacente) o una lista blanca de criptos | Hallazgo 3 |
| G | **Reintentos con backoff en el arranque** (`load_markets`, `fetch_tickers`), mayor `timeout` y alerta de arranque *después* de fijar el radar | Hallazgo 4 |
| H | **OFI real (Cont et al.)** acumulado sobre la ventana, en lugar de la foto L1 | Hallazgo 6 |
| I | Refresco periódico del TOP_N (p. ej. cada hora) | Hallazgo 7 |

---

## 10. Preguntas abiertas para revisión (Deep Think)

1. **Definición operativa de "pánico":** ¿qué combinación de magnitud absoluta, velocidad, volumen relativo y Z (¿de precio o de retornos? ¿en qué horizontes?) separa un colapso explotable del micro-ruido observado (−0,16 % aprobado como pánico)?
2. **Calibración estadística:** con los precios muestreados a 1 s, ¿qué frecuencia de disparo se espera con UMBRAL_PANICO = −2,6? Los retornos tienen colas gruesas y autocorrelación, y el Z está acotado en ±7,68. ¿Debería calibrarse el umbral por percentiles empíricos (backtest) en vez de asumir normalidad?
3. **Circuit breaker BTC:** ¿Z ≤ −4 sobre 60 s es una métrica válida para "colapso sistémico"? ¿Mejor una caída porcentual en 5–15 min, la correlación cruzada entre activos o el funding/OI agregado?
4. **OFI:** ¿merece la pena pasar del queue imbalance L1 al OFI multi-nivel acumulado (Cont, Kukanov & Stoikov, 2014), dado que ccxt.pro ofrece `watch_order_book`? ¿Qué coste de latencia y CPU tiene con 15 símbolos?
5. **Universo:** ¿excluir todos los sintéticos (acciones, materias primas, ETFs tokenizados) o tratarlos con parámetros propios? ¿Lista blanca frente a lista negra?
6. **Orden de los filtros:** ¿debería el escudo Groq (lento: 0,4–1 s) ir al final, solo tras filtros deterministas estrictos de magnitud? ¿Cuál es el coste de latencia frente al beneficio?
7. **Atomicidad de la decisión:** ¿cómo garantizar que el estado global (bloqueo BTC, capital disponible, posiciones abiertas) se valida en el instante del disparo y no solo al detectar la anomalía?

---

## 11. Pendiente

- [x] ~~Confirmar que llegó a Telegram el mensaje "🟩 Motor SPLITBRAIN V5.0 Inicializado."~~ **Confirmado por el usuario:** la telemetría funciona de punta a punta en producción (alerta verde entregada). Recordatorio: en el intento 1 también se envió aunque el bot murió después (hallazgo 4).
- [ ] Revisión Deep Think de este documento y de los tres anteriores.
- [ ] Decidir mejoras A–I antes de cualquier ejecución prolongada en paper y, por supuesto, antes de `MODO_PAPER=False`.
- [ ] Prueba en Bybit testnet antes de fuego real.
