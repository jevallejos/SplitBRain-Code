# Escudo Semántico LPU (Groq)

**Proyecto:** SPLITBRAIN V5.0 (bot de trading cuantitativo, asíncrono)
**Fase:** Lógica semántica — filtro de anomalías con LLM sobre Groq LPU
**Estado:** ✅ Implementado y verificado en vivo · ⚠️ Con una limitación funcional crítica (sección 6)
**Fecha:** 2026-10-13
**Ruta del proyecto:** `d:\dev\SplitBRain-Code` (Windows, PowerShell)
**Documento previo:** `Parámetros Base y Telemetría Silenciada.md`

---

## 1. Objetivo

Cuando un activo colapsa (señal de pánico, ver `UMBRAL_PANICO` en la config), un LLM decide antes de entrar:

- **APROBADO (`True`):** pánico irracional → oportunidad de reversión a la media.
- **RECHAZADO (`False`):** hackeo o fraude estructural → no tocar.

Requisitos del usuario:

- Manejo absoluto de excepciones de red.
- Ante 429, 503 o timeout: imprimir el error en consola y devolver **`False`** (fail-closed) para proteger el capital de forma autónoma.

---

## 2. Estado del proyecto

```
SplitBRain-Code/
├── .env                          (5 credenciales cargadas)
├── .gitignore
├── requirements.txt              (ccxt, groq, aiohttp, python-dotenv)
├── venv/                         (Python 3.12.10, groq 1.7.0)
├── config_parametros.py          (fase anterior)
├── 2_escudo_semantico.py         ← NUEVO (esta fase)
└── 4_telemetria_telegram.py      (fase anterior)
```

---

## 3. Investigación previa a la implementación

| Verificación | Resultado |
|---|---|
| Versión SDK `groq` en el `venv` | **1.7.0** |
| Parámetros de `AsyncGroq.__init__` | `api_key`, `base_url`, `timeout`, **`max_retries` (por defecto 2)**, `http_client`, … |
| Parámetros de `chat.completions.create` | Admite `response_format`, `reasoning_effort`, `reasoning_format`, `include_reasoning`, `temperature`, `max_completion_tokens`, `timeout` |
| Docs de Groq (`/docs/reasoning`) | `openai/gpt-oss-20b` es un **modelo de razonamiento**. `reasoning_effort` ∈ {`low`, `medium`, `high`} (solo GPT-OSS). `include_reasoning` y `reasoning_format` son **mutuamente excluyentes**. En JSON mode no se permite `reasoning_format="raw"` (400). |

---

## 4. Código final — `2_escudo_semantico.py`

```python
import json
from groq import AsyncGroq
import config_parametros as cfg

MODELO = "openai/gpt-oss-20b"
_cliente = None


def _obtener_cliente():
    # Creación diferida: si falta GROQ_API_KEY, AsyncGroq lanza excepción.
    # Así ocurre dentro del try y no rompe el import del módulo.
    global _cliente
    if _cliente is None:
        _cliente = AsyncGroq(api_key=cfg.GROQ_API_KEY, timeout=5.0, max_retries=0)
    return _cliente


async def evaluar_anomalia_groq(symbol) -> bool:
    prompt = (
        f"Eres un analista de riesgos HFT. El activo {symbol} ha colapsado. "
        "Evalúa si es un pánico irracional (APROBADO) o un hackeo/fraude estructural (RECHAZADO). "
        'Responde ÚNICAMENTE con JSON estricto: {"aprobado": true} o {"aprobado": false}.'
    )
    try:
        cliente = _obtener_cliente()
        resp = await cliente.chat.completions.create(
            model=MODELO,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            reasoning_effort="low",
            include_reasoning=False,
            temperature=0.2,
            max_completion_tokens=1024,
        )
        datos = json.loads(resp.choices[0].message.content)
        return datos.get("aprobado") is True
    except Exception as e:
        # 429 / 503 / Timeout / JSON inválido / sin API key → RECHAZADO
        print(f"[ESCUDO LPU] Fallo evaluando {symbol}: {type(e).__name__}: {e}")
        return False
```

**Interfaz pública:** `async def evaluar_anomalia_groq(symbol) -> bool`
**Uso desde otro módulo** (el nombre empieza por dígito, así que no vale `import` normal):

```python
import importlib
escudo = importlib.import_module("2_escudo_semantico")
aprobado = await escudo.evaluar_anomalia_groq("XYZ/USDT:USDT")
```

---

## 5. Decisiones de diseño

| Decisión | Motivo |
|---|---|
| **Cliente diferido** (`_obtener_cliente`) | Si `GROQ_API_KEY` es `None`, `AsyncGroq(...)` lanza `GroqError`. A nivel de módulo, eso tumbaría el bot al importar. Así el error cae dentro del `try` y devuelve `False`. El cliente se crea una sola vez y se reutiliza (pool HTTP compartido, conexión caliente). |
| `timeout=5.0` | Coherente con la telemetría; una decisión de entrada en pánico no puede esperar más. |
| **`max_retries=0`** | El SDK reintenta por defecto **2 veces** con backoff exponencial ante 429/5xx/timeout, lo que podría superar los 15 s. Con 0, falla rápido → `False`. |
| `response_format={"type":"json_object"}` | JSON mode de Groq: garantiza un JSON válido sintácticamente. El prompt contiene la palabra "JSON" (requisito del modo). |
| `reasoning_effort="low"` | Menos tokens de razonamiento → menos latencia. |
| `include_reasoning=False` | No devuelve el razonamiento: respuesta más pequeña. No se combina con `reasoning_format` porque son excluyentes. |
| `temperature=0.2` | Respuestas más deterministas en una decisión binaria. |
| `max_completion_tokens=1024` | Los tokens de razonamiento cuentan en el límite. Si fuera muy bajo, el JSON saldría truncado → `json.loads` falla → `False`. |
| `datos.get("aprobado") is True` | Solo el booleano `True` aprueba. `"true"` (string), `1`, `null` o una clave ausente → `False`. |
| `try/except Exception` envuelve **todo** | Cubre `RateLimitError` (429), `InternalServerError` (5xx/503), `APITimeoutError`, `APIConnectionError`, `AuthenticationError` (401), `GroqError` (sin key), `JSONDecodeError`, `IndexError`/`AttributeError` por respuestas vacías o `content=None`. |
| Errores con `print` local, no por Telegram | Lo pide la spec. Además, la telemetría silencia `ERROR` igualmente. |

---

## 6. Verificación

### 6.1 Fail-closed sin coste

Script de prueba con `importlib`, eliminando `GROQ_API_KEY` del entorno para evitar el fallback del SDK a la variable de entorno.

| Caso | Salida de consola | Retorno | Latencia |
|---|---|---|---|
| Sin API key | `GroqError: The api_key client option must be set...` | `False` ✅ | 0 ms |
| API key inválida | `AuthenticationError: Error code: 401 - Invalid API Key` | `False` ✅ | 4143 ms ⚠️ |

### 6.2 Llamada real a Groq

| Símbolo | Retorno | Latencia |
|---|---|---|
| `LUNA/USDT:USDT` | **`True` (APROBADO)** | 962 ms (conexión en frío: TLS + DNS) |
| `SOL/USDT:USDT` | `True` (APROBADO) | 395 ms (conexión caliente reutilizada) |

### 6.3 Incidencia durante las pruebas

El primer intento de llamada real falló con `GroqError` (sin key) porque el `.env` estaba **vacío en disco (0 bytes)**: las claves estaban en el editor sin guardar. Tras guardarlo se confirmó que se cargan las 5 variables (`GROQ_API_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `BYBIT_API_KEY`, `BYBIT_API_SECRET`). El incidente demostró de paso que el escudo, sin credenciales, devuelve `False` en vez de romper el bot.

---

## 7. ⚠️ Hallazgo crítico: el escudo decide a ciegas

> [!CAUTION]
> **El escudo APROBÓ LUNA**, cuyo colapso de mayo de 2022 (Terra/UST) es el ejemplo canónico de **fallo estructural**: una stablecoin algorítmica entró en una espiral de muerte. Debería haber devuelto `RECHAZADO`.

**Causa raíz:** el modelo solo recibe el **nombre del símbolo**. No tiene:

- magnitud ni velocidad de la caída (% en 1 m / 5 m / 1 h),
- volumen relativo, OFI, profundidad del libro, funding rate, open interest,
- noticias o eventos del día (hackeos, depegs, delistings, exploits),
- acceso a internet (su conocimiento termina en su fecha de corte de entrenamiento).

Además, el prompt afirma "ha colapsado" sin datos, y el modelo tiende a responder "pánico irracional" por defecto. **En la práctica, el escudo actúa como un aprobador casi incondicional**, no como un filtro de riesgo. Peor aún, si la API va bien, aprueba sistemáticamente.

**Opciones de mejora (no implementadas, pendientes de decisión):**

1. **Inyectar contexto cuantitativo:** `evaluar_anomalia_groq(symbol, contexto: dict)` con % de caída, ventana, volumen vs media, OFI, funding, OI, spread y profundidad. El prompt pediría reglas explícitas, por ejemplo: "caída > X % con OFI < `UMBRAL_OFI_TOXICO` y funding normal = pánico".
2. **Contexto cualitativo:** titulares recientes del activo (API de noticias o el anuncio de estado del exchange), para detectar hackeos o depegs.
3. **Búsqueda web integrada de Groq:** los modelos GPT-OSS en Groq admiten la herramienta *Browser Search*. Da información actual, pero añade mucha latencia; habría que validar si cabe en el presupuesto de 5 s.
4. **Salida más rica:** `{"aprobado": bool, "confianza": 0-1, "motivo": str}` y aprobar solo si `confianza >= umbral`, además de registrar `motivo` para auditoría.
5. **Structured Outputs** (`response_format` con `json_schema` y `strict: true`), que gpt-oss en Groq admite: garantiza el esquema exacto, no solo un JSON válido.
6. **Lista de rechazo duro previa al LLM:** activos con historial de colapso estructural (LUNA, UST, FTT…) rechazados sin consultar al modelo.

---

## 8. Otros riesgos y observaciones

1. **Latencia de conexión en frío:** el 401 tardó 4,1 s en un intento (casi todo DNS + TLS de la primera conexión), rozando el timeout de 5 s. La llamada real en frío tardó 962 ms, así que fue variabilidad de red. Si se repite, la primera evaluación tras arrancar podría agotar el timeout → `False`. Mitigación: una llamada de calentamiento al arrancar.
2. **`max_retries=0` ante 429 puntuales:** un rate limit momentáneo provoca un `RECHAZADO` inmediato. Es conservador, pero puede perder oportunidades válidas en ráfagas de pánico multi-activo (precisamente cuando más llamadas hay a la vez).
3. **Rate limits de Groq en ráfaga:** si se evalúan en paralelo muchos símbolos (hasta `TOP_N = 15`) en el mismo instante, podrían saltar 429 en cadena. Conviene un `asyncio.Semaphore` o una cola.
4. **No hay caché:** el mismo símbolo puede evaluarse varias veces en segundos. Una caché con TTL corto (30–60 s) ahorraría latencia y tokens.
5. **`print` en lugar de `logging`:** cumple la spec, pero no queda registro persistente. Con la telemetría silenciando errores, los fallos de Groq solo se ven en la consola en vivo.
6. **Sin observabilidad de la decisión:** no se registra qué respondió el modelo ni por qué, así que no se pueden auditar falsos positivos (como LUNA).
7. **Determinismo:** con `temperature=0.2` la respuesta para un mismo símbolo puede variar entre llamadas.

---

## 9. Preguntas abiertas para revisión (Deep Think)

1. Dado el hallazgo LUNA, ¿qué conjunto mínimo de features cuantitativas debe recibir el LLM para distinguir pánico de fallo estructural con latencia < 1 s? ¿Tiene sentido usar el LLM aquí, o un clasificador determinista basado en microestructura (OFI, funding, OI, spread) sería más fiable y rápido?
2. ¿Fail-closed (`False`) es la política correcta ante errores de API en un sistema que **solo** entra tras confirmación? ¿Cuál es el coste de oportunidad frente al riesgo evitado?
3. ¿`max_retries=0` o `1`? Contrastar el riesgo de perder la ventana de entrada con el de rechazar por un 429 transitorio.
4. ¿Debería el escudo devolver una confianza continua (0–1) que module el tamaño Kelly (`KELLY_MAX_PCT`), en lugar de un booleano?
5. ¿Es aceptable depender de un proveedor externo (Groq) en la ruta crítica de entrada? ¿Haría falta un fallback (otro modelo u otro proveedor) o un modo degradado?
6. ¿Cómo validar el escudo con backtesting? Por ejemplo, un dataset histórico de colapsos etiquetados (pánicos que revirtieron frente a hackeos/depegs) para medir precisión y recall.

---

## 10. Pendiente

- [ ] Decidir la mejora del escudo (sección 7) tras la revisión Deep Think.
- [ ] Siguiente módulo del pipeline (pendiente de especificación del usuario).
