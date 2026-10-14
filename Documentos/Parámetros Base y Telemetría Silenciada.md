# Parámetros Base y Telemetría Silenciada

**Proyecto:** SPLITBRAIN V5.0 (bot de trading cuantitativo, asíncrono)
**Fase:** Config global + telemetría táctica filtrada (Pasos 1 y 2)
**Estado:** ✅ Completado y verificado
**Fecha:** 2026-10-13
**Ruta del proyecto:** `d:\dev\SplitBRain-Code` (Windows, PowerShell)

---

## 1. Objetivo de la fase

1. Centralizar credenciales y parámetros de riesgo/mercado en un único módulo de configuración.
2. Tener un canal de alertas a Telegram que:
   - sea **100 % asíncrono** y nunca bloquee el event loop,
   - **solo transmita victorias**, descartando en silencio todo mensaje con ruido rojo (errores, bloqueos, señales tóxicas, etc.).

Restricciones del usuario: código asíncrono puro, usar la carpeta actual, aprobación explícita por cada archivo creado.

---

## 2. Estado del entorno

| Elemento | Estado |
|---|---|
| Python | 3.12.10 (`C:\Users\fergu\AppData\Local\Programs\Python\Python312`) |
| `venv/` | Funcional. Importa `aiohttp`, `dotenv`, `ccxt`, `groq` sin errores |
| `requirements.txt` | `ccxt`, `groq`, `aiohttp`, `python-dotenv` (no hizo falta añadir nada) |
| `.gitignore` | Incluye `.env`, `venv/`, `__pycache__/`, `*.log`, `*.db`, etc. → credenciales protegidas |
| `.env` | Existe; contiene las credenciales (no se leyó ni se expuso su contenido) |

Estructura actual:

```
SplitBRain-Code/
├── .env
├── .gitignore
├── requirements.txt
├── venv/
├── config_parametros.py          ← NUEVO (Paso 1)
└── 4_telemetria_telegram.py      ← NUEVO (Paso 2)
```

---

## 3. Paso 1 — `config_parametros.py`

Se escribió **literalmente** según la especificación, sin añadidos.

```python
import os
from dotenv import load_dotenv
load_dotenv()

# Credenciales
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Configuración de Riesgo y Mercado
MODO_PAPER = True  # Comenzamos en simulación
TOP_N = 15
UMBRAL_PANICO = -2.6
KELLY_MAX_PCT = 0.35
SL_PCT = 0.03
TP_PCT = 0.05
UMBRAL_OFI_TOXICO = -0.5

# Lista Negra Institucional (Filtro de Compliance y Sintéticos)
PROHIBIDAS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'USDC/USDT:USDT', 'USDE/USDT:USDT', 'SOXL/USDT:USDT', 'SOXS/USDT:USDT', 'TQQQ/USDT:USDT', 'SQQQ/USDT:USDT', 'SUI/USDT:USDT', 'SPY/USDT:USDT']
```

### Semántica de los parámetros

| Parámetro | Valor | Significado |
|---|---|---|
| `MODO_PAPER` | `True` | Simulación; no se envían órdenes reales |
| `TOP_N` | `15` | Tamaño del universo de símbolos a escanear |
| `UMBRAL_PANICO` | `-2.6` | Umbral de pánico de mercado (umbral de señal; la métrica concreta, p. ej. z-score, la define el módulo que lo use) |
| `KELLY_MAX_PCT` | `0.35` | Tope de la fracción de Kelly para dimensionar posiciones (35 %) |
| `SL_PCT` | `0.03` | Stop-loss al 3 % |
| `TP_PCT` | `0.05` | Take-profit al 5 % → ratio R:R ≈ 1 : 1,67 |
| `UMBRAL_OFI_TOXICO` | `-0.5` | Order Flow Imbalance por debajo de este valor = flujo tóxico |
| `PROHIBIDAS` | 10 símbolos | Blacklist en formato de símbolo perpetuo de **ccxt** (`BASE/QUOTE:SETTLE`): majors, stablecoins, ETFs apalancados sintéticos y otros excluidos |

---

## 4. Paso 2 — `4_telemetria_telegram.py`

```python
import aiohttp
import config_parametros as cfg

# Filtro institucional: solo se transmiten victorias, nunca ruido rojo.
PALABRAS_SILENCIADAS = ['🔴', 'ERROR', 'denegada', 'abortó', 'BLOQUEO', 'COLAPSÓ',
                        'encasquillada', 'ignorada', 'TÓXICO', '⚠️', 'ZOMBIE']


async def enviar_alerta(mensaje: str):
    if any(p in str(mensaje) for p in PALABRAS_SILENCIADAS):
        return

    url = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": cfg.TELEGRAM_CHAT_ID, "text": str(mensaje)}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                await resp.read()
    except Exception:
        # Telegram caído o lento: jamás bloquear el event loop.
        pass
```

### Decisiones de diseño

1. **Filtro primero:** la comprobación de palabras silenciadas va antes de cualquier I/O. Los mensajes descartados cuestan microsegundos y no abren conexiones.
2. **Lista a nivel de módulo:** `PALABRAS_SILENCIADAS` se define una sola vez como constante (no se recrea en cada llamada). La lógica es la misma que la especificada: `any(p in str(mensaje) for p in ...)`.
3. **`timeout=5`** se implementa como `aiohttp.ClientTimeout(total=5)`, que es la forma correcta en aiohttp ≥ 3. Limita el tiempo total de la petición (conexión + respuesta).
4. **`try/except Exception: pass`** envuelve la creación de la sesión y el POST. Si Telegram cae, hay timeout, falla el DNS o falta una credencial, la función retorna en silencio y el bot sigue operando.
5. **`await resp.read()`** consume la respuesta para liberar bien la conexión.
6. **Endpoint:** `POST https://api.telegram.org/bot<TOKEN>/sendMessage` con JSON `{chat_id, text}`. Sin `parse_mode`, para que caracteres Markdown/HTML del mensaje no provoquen un HTTP 400.

### Características del filtro (importante para quien lo use)

- **Distingue mayúsculas:** `'ERROR'` bloquea, `'error'` o `'Error'` **no**. Lo mismo con `'BLOQUEO'`, `'TÓXICO'`, `'ZOMBIE'`, `'COLAPSÓ'`.
- **Sensible a tildes:** `'TÓXICO'` bloquea, `'TOXICO'` no; `'abortó'` bloquea, `'aborto'` no.
- **Coincidencia por subcadena:** `'ignorada'` también bloquea `'ignoradas'`; `'denegada'` bloquea `'denegadas'`, pero **no** `'denegado'`.
- **Emoji `⚠️`:** es `U+26A0` + selector de variación `U+FE0F`. Un `⚠` sin el selector **no** se bloquea.
- Los módulos que emitan alertas de error deben usar exactamente estas palabras (o el emoji 🔴) para que se silencien.

---

## 5. Verificación realizada

| Prueba | Comando / método | Resultado |
|---|---|---|
| Import de config + dependencias | `venv\Scripts\python.exe -c "import aiohttp, dotenv, ccxt, groq; import config_parametros as c; print('OK', c.MODO_PAPER, len(c.PROHIBIDAS))"` | `OK True 10` ✅ |
| Filtro de silenciado | `enviar_alerta()` con `'🔴 ERROR orden'`, `'Señal TÓXICO'` y `'⚠️ ZOMBIE'` | Los 3 descartados, sin red, **3,82 ms** en total ✅ |
| Envío real a Telegram | Alerta de arranque de `main.py` ("🟩 Motor SPLITBRAIN V5.0 Inicializado.") durante la prueba en paper | ✅ **Entregada** (confirmado por el usuario, 2026-10-13) |

Para probar el envío real:

```powershell
.\venv\Scripts\python.exe -c "import asyncio, importlib; asyncio.run(importlib.import_module('4_telemetria_telegram').enviar_alerta('✅ Test SPLITBRAIN'))"
```

### Incidencia resuelta: falso diagnóstico de `venv` roto

La primera verificación dio `No Python at 'C:\Users\fergu\AppData\Local\Programs\Python\Python312\python.exe'`. La causa era que el sandbox del agente no veía rutas fuera del workspace, no un `venv` roto. Ejecutado fuera del sandbox, el intérprete base existe y el `venv` funciona. **No se recreó**: hubiera reinstalado exactamente lo mismo.

---

## 6. Advertencias y riesgos conocidos

> [!WARNING]
> **El nombre `4_telemetria_telegram.py` no se puede importar con `import` normal.**
> Un identificador Python no puede empezar por un dígito, así que `import 4_telemetria_telegram` da *SyntaxError*. Hay que usar:
> ```python
> import importlib
> telemetria = importlib.import_module("4_telemetria_telegram")
> await telemetria.enviar_alerta("✅ ...")
> ```
> Se mantuvo el nombre por decisión del usuario (probablemente para numerar los módulos del pipeline).

1. **Una `ClientSession` por alerta.** Es simple y robusto, pero cada llamada paga un handshake TCP+TLS (~100–300 ms). Con muchas alertas conviene una sesión compartida a nivel de módulo, con cierre ordenado al apagar.
2. **Latencia en la ruta crítica.** Si el motor hace `await enviar_alerta(...)` directamente, puede esperar hasta 5 s si Telegram va lento. Para HFT se recomienda dispararla en segundo plano: `asyncio.create_task(telemetria.enviar_alerta(msg))`, guardando una referencia a la tarea para que no la recolecte el GC.
3. **Fallos totalmente silenciosos.** El `except: pass` también oculta errores de configuración (token inválido, `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` en `None`, HTTP 401/400). La función no comprueba `resp.status`. Conviene validar las credenciales al arrancar el bot.
4. **Rate limit de Telegram:** ~1 msg/s por chat y ~30 msg/s globales. No hay throttling ni cola; si se supera, Telegram devuelve 429 y el mensaje se pierde sin aviso.
5. **Límite de 4096 caracteres** por mensaje en Telegram. No hay truncado; un mensaje más largo se pierde sin aviso.
6. **Config sin validación de tipos.** Las credenciales pueden ser `None` si faltan en `.env`; no hay fail-fast al importar.
7. **Filtro sensible a mayúsculas y tildes** (ver sección 4): una alerta de error mal escrita (`"Error"`, `"TOXICO"`) **sí** llegará a Telegram.

---

## 7. Siguientes pasos sugeridos (no implementados)

- Validar al arrancar que existen las credenciales críticas según `MODO_PAPER`.
- Decidir si se pasa a una sesión `aiohttp` compartida y a disparo con `create_task`.
- Hacer una prueba real de envío a Telegram.
- Definir los módulos `1_`, `2_`, `3_` del pipeline (escáner de mercado, señal/IA con Groq, ejecución con ccxt/Bybit) que consumirán `config_parametros` y `enviar_alerta`.

---

## 8. Preguntas abiertas para revisión (Deep Think)

1. ¿`KELLY_MAX_PCT = 0.35` es demasiado agresivo combinado con `SL_PCT = 0.03` en perpetuos con apalancamiento? (Riesgo por trade ≈ 0,35 × 0,03 × apalancamiento.)
2. ¿Un ratio R:R de 1 : 1,67 (SL 3 % / TP 5 %) es coherente con la tasa de acierto esperada? Punto de equilibrio ≈ 37,5 % de aciertos sin comisiones.
3. ¿El filtro de "solo victorias" crea un punto ciego operativo? Fallos críticos (exchange caído, posición zombie, colapso de conexión) no llegarán al operador. ¿Haría falta un segundo canal privado de errores o un log local?
4. ¿Debe la blacklist `PROHIBIDAS` ser un `set` o `frozenset` para búsquedas O(1) y para que no se pueda modificar en tiempo de ejecución?
