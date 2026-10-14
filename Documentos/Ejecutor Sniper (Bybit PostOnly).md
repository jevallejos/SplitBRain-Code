# Ejecutor Sniper (Bybit · Limit PostOnly)

**Proyecto:** SPLITBRAIN V5.0 (bot de trading cuantitativo, asíncrono)
**Fase:** Ejecución — compra Limit *maker-only* con TP/SL adjuntos en perpetuos lineales de Bybit (ccxt)
**Estado:** ✅ Implementado y verificado con exchange simulado sobre mercados reales · ⛔ Nunca se ha enviado una orden real
**Fecha:** 2026-10-13
**Ruta del proyecto:** `d:\dev\SplitBRain-Code` (Windows, PowerShell)
**Documentos previos:** `Parámetros Base y Telemetría Silenciada.md`, `Escudo Semántico LPU (Groq).md`

---

## 1. Objetivo

Ejecutar la entrada en fuego real **eliminando el slippage**: solo órdenes Limit con `PostOnly`, que se añaden al libro como maker o se cancelan, nunca toman liquidez. TP y SL van adjuntos a la orden de entrada. Con `MODO_PAPER=True` no se toca el exchange.

---

## 2. Estado del proyecto

```
SplitBRain-Code/
├── .env                          (5 credenciales)
├── requirements.txt              (ccxt 4.5.87, groq 1.7.0, aiohttp, python-dotenv)
├── venv/                         (Python 3.12.10)
├── config_parametros.py          (MODO_PAPER=True, KELLY_MAX_PCT=0.35, SL_PCT=0.03, TP_PCT=0.05)
├── 2_escudo_semantico.py         (filtro LLM Groq)
├── 3_ejecutor_sniper.py          ← NUEVO (esta fase)
└── 4_telemetria_telegram.py      (alertas, solo victorias)
```

---

## 3. Investigación previa (solo datos públicos, sin órdenes)

### 3.1 Mapeo de parámetros en ccxt 4.5.87 (`bybit.create_order_request`)
- `params['takeProfit']` / `params['stopLoss']` → TP/SL **adjuntos** a la orden ("solo efectivos al abrir posición"). Distintos de `takeProfitPrice`/`stopLossPrice`, que crean órdenes condicionales independientes.
- `params['timeInForce'] = 'PostOnly'` → `timeInForce: 'PostOnly'` nativo de Bybit.
- Admite TP/SL como número o `str`. Se usa `str(...)` según la spec.

### 3.2 Petición construida en vivo (sin enviar) para `SOL/USDT:USDT`
```
{'symbol': 'SOLUSDT', 'side': 'Buy', 'orderType': 'Limit', 'timeInForce': 'PostOnly',
 'price': '106.88', 'category': 'linear', 'qty': '0.1',
 'stopLoss': '103.67', 'takeProfit': '112.22'}
```

### 3.3 Reglas reales del mercado `SOL/USDT:USDT`
| Regla | Valor |
|---|---|
| Cantidad mínima | 0,1 SOL (≈ 10,7 USDT a 107) |
| Nocional mínimo | **5 USDT** |
| Paso de cantidad | 0,1 |
| Paso de precio | 0,01 |

### 3.4 Muestras de ticker observadas
| Muestra | last | bid | ask | Observación |
|---|---|---|---|---|
| 1 | 106.95 | 106.94 | 106.95 | **`last == ask`** → un PostOnly a `last` cruzaría el spread |
| 2 | 106.88 | 106.88 | 106.89 | `last == bid` → seguro |

---

## 4. Desviaciones de la spec original (aprobadas por el usuario)

| # | Spec original | Implementación | Motivo |
|---|---|---|---|
| 1 | `from 4_telemetria_telegram import enviar_alerta` | `importlib.import_module("4_telemetria_telegram").enviar_alerta` | Un nombre de módulo que empieza por dígito es **SyntaxError**. El archivo no habría compilado. |
| 2 | Precio = `ticker['last']` | Precio = `min(last, bid)` | Si `last == ask`, una compra PostOnly tomaría liquidez y Bybit la cancela al instante, pero `create_order` **devuelve un `id` igualmente**. Resultado: alerta verde falsa de una orden inexistente. |
| 3 | Mínimo 2 USDT | Mínimo = `max(2, limits.cost.min del mercado)` | Bybit exige ≥ 5 USDT de nocional. Entre 2 y 5 USDT la orden falla siempre. |
| 4 | Solo `enviar_alerta` en errores | `print` local + `enviar_alerta` | El filtro de telemetría silencia el error. Sin `print`, un fallo con dinero real sería invisible. |
| 5 | — | `await exchange.load_markets()` al inicio del `try` | `amount_to_precision`, `price_to_precision` y `market()` requieren mercados cargados. ccxt los cachea. |
| 6 | — | TP/SL también pasan por `price_to_precision` | Bybit rechaza precios fuera del paso de precio. |
| 7 | (emoji 🔴 en el `print` de error) | `print` sin emojis | **Bug descubierto en las pruebas** (ver 6.3). |

---

## 5. Código final — `3_ejecutor_sniper.py`

```python
import asyncio
import importlib
import config_parametros as cfg

# El nombre del módulo empieza por dígito: no admite `from 4_... import`.
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta

MIN_INVERSION_USDT = 2.0


async def ejecutar_orden_sniper(exchange, symbol, z_score):
    if cfg.MODO_PAPER:
        print("[PAPER TRADING] Ejecución simulada")
        return

    try:
        await exchange.load_markets()  # cacheado tras la 1ª llamada; necesario para *_to_precision

        # 1. Saldo libre y tamaño Kelly
        balance = await exchange.fetch_balance()
        libre = float(balance.get("USDT", {}).get("free") or 0)
        inversion = libre * cfg.KELLY_MAX_PCT
        minimo_mercado = exchange.market(symbol)["limits"]["cost"]["min"] or 0
        if inversion < max(MIN_INVERSION_USDT, minimo_mercado):
            raise ValueError(f"Inversión {inversion:.2f} USDT bajo el mínimo operable")

        # 2. Precio de disparo, siempre en lado maker (nunca cruzar el spread)
        ticker = await exchange.fetch_ticker(symbol)
        last, bid = ticker["last"], ticker["bid"]
        precio_ref = min(last, bid) if bid else last

        # 3. Precisión según las reglas del exchange
        price = exchange.price_to_precision(symbol, precio_ref)
        amount = exchange.amount_to_precision(symbol, inversion / float(price))
        precio_tp = exchange.price_to_precision(symbol, float(price) * (1 + cfg.TP_PCT))
        precio_sl = exchange.price_to_precision(symbol, float(price) * (1 - cfg.SL_PCT))

        # 4-5. Limit Maker estricto con TP/SL adjuntos
        params = {"timeInForce": "PostOnly", "takeProfit": str(precio_tp), "stopLoss": str(precio_sl)}
        orden = await exchange.create_order(symbol, "limit", "buy", amount, price, params)
    except Exception as e:
        # Sin emojis en consola: en Windows (cp1252) provocan UnicodeEncodeError dentro del except.
        print(f"[SNIPER] ERROR ejecutando {symbol}: {type(e).__name__}: {e}")
        await enviar_alerta(f"🔴 ERROR Sniper {symbol}: {e}")  # silenciado por el filtro
        return

    await enviar_alerta(
        f"🟩 ALERTA VERDE (PROD):\nOrden Limit PostOnly en {symbol}\nPrecio: {price}\nID: {orden['id']}"
    )
```

**Interfaz:** `async def ejecutar_orden_sniper(exchange, symbol, z_score) -> None`

**Requisitos del objeto `exchange`** (responsabilidad de quien llama):
```python
import ccxt.async_support as ccxt
exchange = ccxt.bybit({
    "apiKey": cfg.BYBIT_API_KEY,
    "secret": cfg.BYBIT_API_SECRET,
    "options": {"defaultType": "swap"},
})
# ... y al apagar: await exchange.close()
```

**Uso:**
```python
sniper = importlib.import_module("3_ejecutor_sniper")
await sniper.ejecutar_orden_sniper(exchange, "XYZ/USDT:USDT", z_score)
```

---

## 6. Verificación

### 6.1 Método
- `py_compile` del módulo → **OK**.
- Arnés de pruebas con **mercados reales de Bybit** (cargados vía API pública) y `fetch_balance`, `fetch_ticker` y `create_order` **simulados**. El `create_order` simulado reconstruye la petición real con `exchange.create_order_request(...)` para validar lo que llegaría a Bybit. `enviar_alerta` interceptada: nada se envió a Telegram.

### 6.2 Resultados

| Caso | Entrada | Resultado |
|---|---|---|
| A. Paper | `MODO_PAPER=True` | `[PAPER TRADING] Ejecución simulada`, sin tocar el exchange ✅ |
| B. Éxito, `last == ask` | saldo 100 USDT; last 100.05 / bid 100.00 / ask 100.05 | Precio **100** (bid, lado maker) · qty **0.3** · TP **105** · SL **97** · alerta 🟩 con `ID: MOCK-123` ✅ |
| C. Saldo insuficiente | saldo 10 USDT → inversión 3,5 < 5 | `ValueError` → `print` + alerta 🔴 (silenciada) + `return` ✅ |
| D. Fallo del exchange | `create_order` lanza `InvalidOrder(EC_PostOnlyWillTakeLiquidity)` | Capturado → `print` + alerta 🔴 (silenciada) + `return` ✅ |
| E. Filtro real de telemetría | `"🔴 ERROR Sniper ..."` / `"🟩 ALERTA VERDE (PROD): ..."` | Error silenciado ✅ / verde pasa ✅ |

Petición final del caso B (lo que recibiría Bybit):
```
{'symbol': 'SOLUSDT', 'side': 'Buy', 'orderType': 'Limit', 'timeInForce': 'PostOnly',
 'price': '100', 'category': 'linear', 'qty': '0.3', 'stopLoss': '97', 'takeProfit': '105'}
```
Tamaño: 100 × 0,35 = 35 USDT → 0,35 SOL → **truncado a 0,3** (30 USDT efectivos).

### 6.3 Bug crítico descubierto y corregido

En la primera ejecución, el `print` del arnés con el emoji 🟩 lanzó:
```
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f7e9'
```
Con la salida redirigida (pipe, archivo de log, servicio), la consola de Windows usa **cp1252**, que no tiene emojis. El `print(f"[SNIPER] 🔴 ERROR ...")` original estaba **dentro del `except`**: habría lanzado una nueva excepción, que **escaparía de la función** y podría tumbar el event loop justo cuando falla una orden real.

**Corrección:** `print` sin emojis. Los emojis siguen en los mensajes de Telegram, que no pasan por la consola.
**Recomendación global:** arrancar el bot con `$env:PYTHONUTF8 = "1"` (o `python -X utf8`).

---

## 7. Riesgos conocidos (no resueltos en esta fase)

### Microestructura
1. **"Colocada" ≠ "abierta" ≠ "llenada".** La alerta verde solo confirma que `create_order` devolvió un `id`. Bybit puede cancelar un PostOnly **después** de aceptarlo si el bid se movió en esos milisegundos (`min(last, bid)` lo mitiga, no lo elimina). Falta confirmar el estado con `fetch_order` o el websocket de órdenes.
2. **Orden colgada:** si el precio rebota antes de llenarse, la orden maker queda abierta indefinidamente y bloquea margen. Falta cancelar por timeout (p. ej., `asyncio.sleep(N)` → `cancel_order` si no está llenada).
3. **Selección adversa del maker:** en un colapso, una orden de compra pasiva en el bid se llena precisamente cuando el precio sigue cayendo (atraviesa el bid) y no se llena cuando rebota. El PostOnly elimina slippage, pero introduce **riesgo de no ejecución sesgado**: las ejecuciones que sí ocurren tienden a ser las peores.
4. **Ticker vs libro:** `fetch_ticker` es una foto REST con latencia (cientos de ms). En HFT real se usaría el libro L1 por websocket (`watch_order_book` / `watch_ticker` de ccxt pro).
5. **Ejecuciones parciales:** TP/SL adjuntos en modo `Full` (por defecto) se aplican a la posición. Con ejecución parcial, la posición abierta es menor que la prevista.

### Riesgo y cuenta
6. **Apalancamiento no gestionado:** se usa el configurado en Bybit para cada símbolo. El nocional es el 35 % del saldo libre; el margen consumido = nocional / apalancamiento. Con apalancamiento alto, el SL del 3 % puede quedar cerca del precio de liquidación.
7. **Hedge mode:** si la cuenta está en modo cobertura, Bybit exige `positionIdx=1` para largos. El código asume one-way mode.
8. **Concurrencia:** si se disparan varios sniper en paralelo (hasta `TOP_N=15`), cada uno lee el mismo saldo libre y aplica el 35 %, así que la exposición total puede superar el saldo. Hace falta un lock o un gestor de capital central.
9. **Sin control de posición existente:** no se comprueba si ya hay posición u órdenes abiertas en el símbolo (riesgo de duplicar la entrada).
10. **Truncado de cantidad:** el tamaño real puede ser bastante menor que el objetivo Kelly (30 vs 35 USDT en la prueba; en activos de precio alto, la diferencia relativa es mayor).

### Operativos
11. **`z_score` no se usa** (la spec no lo emplea).
12. **`asyncio` importado pero sin uso** (lo exige la spec; útil para el timeout del punto 2).
13. **Nunca probado contra Bybit real ni testnet.** Bybit tiene testnet (`exchange.set_sandbox_mode(True)`) con claves separadas.
14. **Rate limits:** `enableRateLimit` está activo por defecto en ccxt, pero ráfagas multi-símbolo pueden provocar 10006 / 429 en Bybit.

---

## 8. Preguntas abiertas para revisión (Deep Think)

1. **Maker vs taker en colapsos:** dado el sesgo de selección adversa del punto 7.3, ¿compensa el ahorro de slippage y fees de un PostOnly el coste de oportunidad de no llenarse en los rebotes en V más rápidos (justo los más rentables para la estrategia de reversión a la media)? ¿Conviene un esquema híbrido, por ejemplo PostOnly con timeout y luego IOC limitado a X bps?
2. **Precio de la orden:** ¿`min(last, bid)`, el bid exacto, o `bid − k·tick` para mejorar la entrada a cambio de menos probabilidad de ejecución? ¿Cómo calibrar `k` según la volatilidad y el `z_score`?
3. **Kelly al 35 % del saldo libre por operación:** con SL 3 % y apalancamiento L, la pérdida por operación es ≈ 0,35 × 0,03 × L del saldo. ¿Cuál es el L máximo coherente? ¿Debería el tamaño escalar con el `z_score` o con la confianza del escudo semántico?
4. **TP/SL fijos (5 % / 3 %)** frente a dinámicos basados en ATR o volatilidad realizada del colapso: ¿cuál conviene para activos con perfiles de volatilidad muy distintos?
5. **Gestión de capital concurrente:** ¿qué arquitectura (semáforo, presupuesto de riesgo global, cola de órdenes) evita sobreexposición cuando varios activos colapsan a la vez (eventos correlacionados de mercado)?
6. **Confirmación de estado:** ¿REST `fetch_order` tras N ms, o suscripción websocket a órdenes y ejecuciones? Impacto en latencia y complejidad.

---

## 9. Pendiente

- [ ] Revisión Deep Think de este documento.
- [ ] Decidir: confirmación de estado de la orden, cancelación por timeout, apalancamiento y hedge mode, gestor de capital concurrente.
- [ ] Prueba en **Bybit testnet** antes de cualquier `MODO_PAPER=False` en real.
- [ ] Módulo `1_` (escáner de mercado / detector de pánico) y orquestador principal que encadene escáner → escudo → sniper → telemetría.
