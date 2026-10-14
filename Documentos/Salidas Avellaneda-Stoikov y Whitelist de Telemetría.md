# Salidas Avellaneda-Stoikov y Whitelist de Telemetría

**Proyecto:** SPLITBRAIN V6.0 (bot de trading cuantitativo, asíncrono) — "Innovación 2"
**Fase:** salidas dinámicas tipo Avellaneda-Stoikov (AS) persiguiendo el precio, lista blanca en Telegram y lista negra ampliada
**Estado:** ✅ 4 archivos editados y aprobados uno a uno · ✅ Motor AS validado con exchange y reloj simulados (8/8) · ✅ Telemetría 10/10 · ✅ Prueba en `MODO_PAPER=True` estable (2º intento) · ⚠️ **Hallazgos abiertos en la sección 8**
**Fecha:** 2026-10-13
**Ruta del proyecto:** `d:\dev\SplitBRain-Code` (Windows, PowerShell, Python 3.12.10, ccxt 4.5.87)
**Documentos previos:** `Parámetros Base y Telemetría Silenciada.md`, `Escudo Semántico LPU (Groq).md`, `Ejecutor Sniper (Bybit PostOnly).md`, `Radar OFI, Circuit Breaker y Bucle Central.md`

---

## 1. Objetivo

1. Dejar de delegar el take-profit estático a Bybit: tras la compra, un motor en segundo plano coloca una venta Limit PostOnly al TP máximo (+5 %) y **baja el precio exigido con el tiempo** hasta liquidar a mercado a los 120 s ("anti-zombie").
2. Telegram solo debe recibir mensajes de éxito: **lista blanca** por el emoji 🟩.
3. Ampliar la lista negra (ETFs, sintéticos, tokens con fallos de precisión).
4. Banner V6.0.

Restricciones del usuario: código asíncrono puro, el bot nunca debe caerse, no eliminar código funcional (OFI, etc.), aprobación por archivo.

```
radar (1_) ─► escudo Groq (2_) ─► sniper (3_): compra Limit PostOnly + SL de emergencia
                                     └─► create_task(motor AS)            ← NUEVO
                                            Fase 0: esperar llenado (≤ 30 s)
                                            Venta Limit PostOnly reduceOnly a entry·(1+TP)
                                            cada 2 s: estado → éxito / SL / reajuste a la baja
                                            t ≥ 120 s: cancelar + venta a mercado reduceOnly
telemetría (4_): solo pasa 🟩 (y además la lista negra previa)
```

---

## 2. Investigación previa (solo lectura, sin órdenes)

| Comprobación | Resultado |
|---|---|
| Tipo de cuenta Bybit | **UTA** (Unified Trading Account) |
| `fetch_order(id, symbol)` en UTA | ❌ lanza `ArgumentsRequired` salvo `params={'acknowledged': True}` (solo últimas 500 órdenes) |
| Respuesta de `create_order` | Solo `orderId` → ccxt devuelve `price=None`, `amount=None`, `status=None` |
| `reduceOnly` en ccxt bybit | ✅ soportado; aparece en el request firmado |
| `LUNA/USDT:USDT` | **No existe** en Bybit (el LUNA real es `LUNA2/USDT:USDT`) |

---

## 3. Fallos del código AS de la spec (detectados antes de implementar)

| # | Fallo | Consecuencia |
|---|---|---|
| 1 | `fetch_order` sin `acknowledged` como primera línea del `try`, con `except: pass` | En UTA lanza siempre → bucle infinito cada 2 s; **el anti-zombie (situado después) nunca se evalúa**. La posición solo saldría por el SL. |
| 2 | `float(orden_venta['price'])` | `float(None)` → `TypeError` silenciado → **el reajuste nunca ocurre**. |
| 3 | Ventas sin `reduceOnly` y sin esperar al llenado de la compra PostOnly | Si la compra no se llenó, o el SL ya cerró la posición, la venta límite o la de mercado **abren un CORTO** (perpetuos en modo one-way). |
| 4 | Alerta `🟩 [ESCAPE ANTI-ZOMBIE]` | Contiene `ZOMBIE`, que está en la lista negra conservada → **silenciada**. |
| 5 | `asyncio.create_task(...)` sin guardar la referencia | asyncio guarda referencias débiles: el GC puede destruir el motor con una posición abierta. |
| 6 | Nombre "Avellaneda-Stoikov" | La fórmula es un **descuento lineal en el tiempo**, no el modelo AS (ver 8.1). Se implementó tal cual por ser decisión de diseño. |

---

## 4. Decisiones del usuario

| Decisión | Elegido |
|---|---|
| Lista negra | Lista exacta de la spec **+** `LUNA2` y sintéticos detectados (XAG, SKHYNIX, SNDK, KORU, AAPL, TSLA, AMZN, GOOGL, META, MSTR, COIN, HOOD) |
| Alerta anti-zombie | Renombrada a `🟩 [ESCAPE TEMPORAL]` |
| Alerta de arranque | `🟩 Motor SPLITBRAIN V6.0 Inicializado.` |
| Reajuste | cancel + create (como la spec), no `edit_order` |
| Correcciones 1–5 | Aprobadas |

---

## 5. Código final

### 5.1 `config_parametros.py` (cambios)

```python
# Lista Negra Institucional (Filtro de Compliance y Sintéticos)
PROHIBIDAS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'USDC/USDT:USDT', 'USDE/USDT:USDT', 'SOXL/USDT:USDT', 'SOXS/USDT:USDT', 'TQQQ/USDT:USDT', 'SQQQ/USDT:USDT', 'SUI/USDT:USDT', 'SPY/USDT:USDT', 'LUNA/USDT:USDT', 'XAU/USDT:USDT', 'NVDA/USDT:USDT']
# Extensión V6.0: LUNA real en Bybit (LUNA2) y sintéticos (acciones/materias primas) detectados en el exchange
PROHIBIDAS += ['LUNA2/USDT:USDT', 'XAG/USDT:USDT', 'SKHYNIX/USDT:USDT', 'SNDK/USDT:USDT', 'KORU/USDT:USDT',
               'AAPL/USDT:USDT', 'TSLA/USDT:USDT', 'AMZN/USDT:USDT', 'GOOGL/USDT:USDT', 'META/USDT:USDT',
               'MSTR/USDT:USDT', 'COIN/USDT:USDT', 'HOOD/USDT:USDT']

# Parámetros Avellaneda-Stoikov (AS) Salidas Dinámicas
GAMMA_AS = 0.05  # Aversión al riesgo de inventario (Velocidad de decaimiento del precio)
TIEMPO_MAX_HOLD_SEG = 120  # Segundos máximos antes de liquidar a mercado (Operación Zombie)
```
26 símbolos, sin duplicados. Resto de parámetros sin cambios (`MODO_PAPER=True`, `TOP_N=15`, `UMBRAL_PANICO=-2.6`, `KELLY_MAX_PCT=0.35`, `SL_PCT=0.03`, `TP_PCT=0.05`, `UMBRAL_OFI_TOXICO=-0.5`).

### 5.2 `4_telemetria_telegram.py` (cambio)

```python
async def enviar_alerta(mensaje: str):
    # Lista blanca V6.0: solo los mensajes verdes llegan al operador.
    if "🟩" not in str(mensaje):
        return

    if any(p in str(mensaje) for p in PALABRAS_SILENCIADAS):   # lista negra previa, conservada
        return
    ...  # POST aiohttp a sendMessage, timeout 5 s, try/except: pass (sin cambios)
```

### 5.3 `3_ejecutor_sniper.py` (completo)

```python
import asyncio
import importlib
import time
import config_parametros as cfg

# El nombre del módulo empieza por dígito: no admite `from 4_... import`.
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta

MIN_INVERSION_USDT = 2.0

# Motor de salidas Avellaneda-Stoikov (V6.0)
ESPERA_LLENADO_SEG = 30   # máx. espera a que la compra maker se llene
INTERVALO_AS_SEG = 2      # evaluar la física del mercado cada 2 segundos
_tareas_as = set()        # referencias fuertes: asyncio solo guarda referencias débiles a las tareas


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

        # 4-5. Limit Maker estricto con SL de emergencia adjunto.
        # V6.0: el take-profit ya no se delega al exchange (precio_tp queda solo como referencia);
        # la salida la gestiona motor_salida_avellaneda_stoikov.
        params = {"timeInForce": "PostOnly", "stopLoss": str(precio_sl)}
        orden = await exchange.create_order(symbol, "limit", "buy", amount, price, params)
    except Exception as e:
        # Sin emojis en consola: en Windows (cp1252) provocan UnicodeEncodeError dentro del except.
        print(f"[SNIPER] ERROR ejecutando {symbol}: {type(e).__name__}: {e}")
        await enviar_alerta(f"🔴 ERROR Sniper {symbol}: {e}")  # silenciado por el filtro
        return

    await enviar_alerta(
        f"🟩 ALERTA VERDE (PROD):\nOrden Limit PostOnly en {symbol}\nPrecio: {price}\nID: {orden['id']}"
    )

    # Motor AS en segundo plano: no bloquea al Sniper.
    tarea = asyncio.create_task(motor_salida_avellaneda_stoikov(exchange, symbol, amount, price, orden["id"]))
    _tareas_as.add(tarea)
    tarea.add_done_callback(_tareas_as.discard)


async def _estado_orden(exchange, order_id, symbol):
    # En cuentas UTA, fetch_order exige 'acknowledged' (accede a las últimas 500 órdenes).
    return await exchange.fetch_order(order_id, symbol, {"acknowledged": True})


async def _posicion_larga(exchange, symbol):
    """Tamaño de la posición larga abierta (0 si no hay). None si la API falla."""
    try:
        posiciones = await exchange.fetch_positions([symbol])
    except Exception as e:
        print(f"[{symbol}] AS: no se pudo leer la posición: {type(e).__name__}: {e}")
        return None
    total = 0.0
    for p in posiciones or []:
        if p.get("symbol") == symbol and p.get("side") == "long":
            total += float(p.get("contracts") or 0)
    return total


async def _esperar_llenado_compra(exchange, symbol, id_compra):
    """Devuelve la cantidad realmente comprada (0 si no se llenó). Cancela el resto al expirar."""
    limite = time.time() + ESPERA_LLENADO_SEG
    while time.time() < limite:
        await asyncio.sleep(1)
        try:
            o = await _estado_orden(exchange, id_compra, symbol)
        except Exception:
            continue
        if o.get("status") in ("closed", "canceled", "rejected", "expired"):  # p. ej. PostOnly rechazado
            return float(o.get("filled") or 0)
    try:
        await exchange.cancel_order(id_compra, symbol)
    except Exception:
        pass  # ya llenada o cancelada
    try:
        return float((await _estado_orden(exchange, id_compra, symbol)).get("filled") or 0)
    except Exception as e:
        print(f"[{symbol}] AS: no se pudo confirmar el llenado de la compra: {type(e).__name__}: {e}")
        return 0.0


async def motor_salida_avellaneda_stoikov(exchange, symbol, amount, entry_price, id_compra=None):
    try:
        # Fase 0: no gestionar salida hasta tener posición real (evita abrir cortos).
        if id_compra is not None:
            amount = await _esperar_llenado_compra(exchange, symbol, id_compra)
            if amount <= 0:
                print(f"[{symbol}] AS: compra no llenada; no hay posición que gestionar.")
                return

        entry = float(entry_price)
        tiempo_inicio = time.time()
        precio_objetivo_max = entry * (1 + cfg.TP_PCT)
        p_minimo_rentable = entry * 1.002  # Spread mínimo para asegurar rentabilidad neta (0.2%)
        salida = {"timeInForce": "PostOnly", "reduceOnly": True}  # reduceOnly: jamás abre un corto

        # Orden Limit (Ask) inicial con el TP máximo exigido
        try:
            p_exit_format = exchange.price_to_precision(symbol, precio_objetivo_max)
            orden_venta = await exchange.create_order(symbol, "limit", "sell", amount, float(p_exit_format), salida)
            precio_orden_actual = float(p_exit_format)  # Bybit no devuelve el precio al crear
        except Exception as e:
            print(f"[{symbol}] Error AS inicial: {type(e).__name__}: {e}")
            return

        restante = float(amount)
        while True:
            await asyncio.sleep(INTERVALO_AS_SEG)
            tiempo_hold = time.time() - tiempo_inicio

            # 1. Liquidación forzada (anti-zombie): se evalúa PRIMERO y por tiempo, aunque la API falle.
            if tiempo_hold >= cfg.TIEMPO_MAX_HOLD_SEG:
                try:
                    await exchange.cancel_order(orden_venta["id"], symbol)
                except Exception:
                    pass  # ya llenada/cancelada
                posicion = await _posicion_larga(exchange, symbol)
                if posicion is not None:
                    restante = posicion
                try:
                    if restante > 0:
                        cantidad = exchange.amount_to_precision(symbol, restante)
                        await exchange.create_order(symbol, "market", "sell", cantidad, None, {"reduceOnly": True})
                        await enviar_alerta(f"🟩 [ESCAPE TEMPORAL] {symbol} liquidado a mercado tras "
                                            f"{int(tiempo_hold)}s para liberar liquidez.")
                except Exception as e:
                    print(f"[{symbol}] AS: fallo en la liquidación a mercado: {type(e).__name__}: {e}")
                break  # siempre sale: reduceOnly + SL de emergencia cubren el resto

            try:
                check_order = await _estado_orden(exchange, orden_venta["id"], symbol)
                estado = check_order.get("status")

                if estado == "closed":
                    precio_final = check_order.get("average") or check_order.get("price")
                    await enviar_alerta(f"🟩 [EXITO AS] {symbol} liquidado pasivamente a {precio_final}. Ganancia Asegurada.")
                    break

                ticker = await exchange.fetch_ticker(symbol)
                p_mid = float(ticker["last"])

                # Ecuación AS: Descuento dinámico del precio exigido por riesgo temporal (inventario radiactivo)
                decaimiento = cfg.GAMMA_AS * (tiempo_hold / cfg.TIEMPO_MAX_HOLD_SEG) * entry
                p_exit_dinamico = precio_objetivo_max - decaimiento

                if estado in ("canceled", "rejected", "expired"):
                    # ¿La cerró el SL (fin) o se cayó la venta (PostOnly rechazado / reajuste a medias)?
                    posicion = await _posicion_larga(exchange, symbol)
                    if posicion is None:
                        continue  # API caída: el anti-zombie actuará por tiempo
                    if posicion <= 0:
                        print(f"[{symbol}] AS: posición cerrada externamente (SL); fin del motor.")
                        break
                    restante = posicion
                    p_reponer = max(p_exit_dinamico, p_minimo_rentable)
                    p_exit_format = exchange.price_to_precision(symbol, p_reponer)
                    orden_venta = await exchange.create_order(symbol, "limit", "sell", restante, float(p_exit_format), salida)
                    precio_orden_actual = float(p_exit_format)
                    continue

                restante = float(check_order.get("remaining") or restante)

                # 2. Reajuste de Limit Order (Persiguiendo el precio)
                p_exit_format = exchange.price_to_precision(symbol, p_exit_dinamico)
                if precio_orden_actual > float(p_exit_format) and p_exit_dinamico > p_mid and p_exit_dinamico > p_minimo_rentable:
                    await exchange.cancel_order(orden_venta["id"], symbol)
                    orden_venta = await exchange.create_order(symbol, "limit", "sell", restante, float(p_exit_format), salida)
                    precio_orden_actual = float(p_exit_format)
            except Exception as e:
                # Error transitorio de la API: el bucle sigue y el anti-zombie va por tiempo.
                print(f"[{symbol}] AS transitorio: {type(e).__name__}: {e}")
    except Exception as e:
        # Última red: el motor jamás tumba el bot (el SL de emergencia sigue en Bybit).
        print(f"[{symbol}] AS abortado: {type(e).__name__}: {e}")
```

### 5.4 `main.py` (cambio)

```diff
-    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V5.0 - ARQUITECTURA CUÁNTICA OFI)")
+    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V6.0 - ARQUITECTURA AVELLANEDA-STOIKOV)")
-    await enviar_alerta("🟩 Motor SPLITBRAIN V5.0 Inicializado.")
+    await enviar_alerta("🟩 Motor SPLITBRAIN V6.0 Inicializado.")
```

`1_radar_volatilidad.py` (OFI, circuit breaker) y `2_escudo_semantico.py`: **sin cambios**.

---

## 6. Desviaciones respecto a la spec

| Spec | Implementación | Motivo |
|---|---|---|
| La salida arranca inmediatamente | **Fase 0**: espera ≤ 30 s a que la compra se llene; si no, la cancela y usa la cantidad realmente llenada | Fallo 3. Resuelve también la "orden colgada" del informe del sniper. |
| Ventas sin `reduceOnly` | `reduceOnly: True` en la limit inicial, en los reajustes, en las reposiciones y en la de mercado | Fallo 3: Bybit nunca permitirá que una venta abra posición. |
| `fetch_order(id, symbol)` | `fetch_order(..., {"acknowledged": True})` | Fallo 1 (UTA). |
| `float(orden_venta['price'])` | Variable local `precio_orden_actual` | Fallo 2. |
| Anti-zombie después de `fetch_order` | Anti-zombie **primero**, por reloj, con errores de API aislados; **siempre** sale del bucle | Garantiza la salida a los 120 s aunque la API falle; evita reintentar una venta a mercado cada 2 s. |
| `canceled`/`rejected` → `break` | Consulta `fetch_positions`: sin posición → fin (lo cerró el SL); con posición → **repone** la venta | Un PostOnly rechazado o un reajuste a medias (cancel OK, create falla) dejaban la posición sin salida gestionada. *Añadido durante la implementación.* |
| Market sell con `amount` | Market sell con el **tamaño real de la posición** (`fetch_positions`), con `amount_to_precision` | Llenados parciales y reposiciones. |
| Reajustes con `amount` | `restante` (`remaining` del exchange) | Llenados parciales de la venta. |
| Reajuste si `p_exit_dinamico < precio_actual` | Compara el precio **ya redondeado al tick** | Evita cancel/replace sin cambio de precio. |
| `[ESCAPE ANTI-ZOMBIE]` | `[ESCAPE TEMPORAL]` | Fallo 4. |
| `create_task` suelto | Conjunto `_tareas_as` + `add_done_callback(discard)` | Fallo 5. |
| `except: pass` | `print` del error | Diagnóstico. |
| `'expired'` no contemplado | Incluido | Estado posible en ccxt. |
| Imports dentro de la función | A nivel de módulo | Equivalente, sin repetir trabajo. |
| TP estático eliminado | Eliminado del request; `precio_tp` se sigue calculando (no se borra código) | Spec. |

---

## 7. Verificación

### 7.1 Telemetría (aiohttp interceptado, sin envíos reales)

| Mensaje | Resultado |
|---|---|
| `🟩 ALERTA VERDE`, `🟩 Motor V6.0`, `🟩 [EXITO AS]`, `🟩 [ESCAPE TEMPORAL]` | Enviado ✅ |
| `🟩 [ESCAPE ANTI-ZOMBIE]` | Silenciado ✅ (confirma el fallo 4) |
| `🟩 ERROR ...` | Silenciado ✅ (la lista negra sigue activa) |
| `🔴 ...`, `⚠️ ...`, texto sin emoji, `None` | Silenciado ✅ |

**10/10.**

### 7.2 Motor AS (exchange y reloj simulados)

Montaje: mercados **reales** de Bybit (API pública) para precisión y para construir cada request con `create_order_request`; órdenes, posición, ticker y reloj simulados; Telegram interceptado. Símbolo SOL (tick 0,01; lote 0,1), entrada 100.

| Escenario | Resultado |
|---|---|
| A. El precio sube 0,05/s | 27 limits de 105,00 → 102,83; **`[EXITO AS]` a 102,83** a los 57 s; sin market ✅ |
| B. Precio plano | 58 limits de 105,00 → **100,25** (respeta el suelo de +0,2 %); **market reduceOnly** a 123 s; `[ESCAPE TEMPORAL]` ✅ |
| C. La compra nunca se llena | Compra cancelada a 30 s; **0 ventas** ✅ |
| D. El SL cierra la posición a 40 s | Detecta la venta cancelada y la posición 0; termina **sin market** ✅ |
| E. `fetch_order` de la venta falla siempre | Errores registrados cada 2 s; **market reduceOnly a 120 s igualmente** ✅ |
| F. Un reajuste rechazado por PostOnly | Detecta `rejected` + posición abierta → repone → termina ✅ |
| G. Compra llenada al 50 % | Todas las ventas de 0,5 ✅ |
| H. Integración desde `ejecutar_orden_sniper` | Compra `{'timeInForce':'PostOnly','stopLoss':'96.99'}` **sin `takeProfit`**; 1 tarea en `_tareas_as`, liberada al terminar; `[EXITO AS]` ✅ |

**8/8.** En todos los escenarios, **todas** las ventas llevaron `reduceOnly: True` tanto en los argumentos como en el request firmado por ccxt. (El primer intento dio 7/8 por un bug del simulador en el llenado parcial, no del motor.)

### 7.3 Prueba real en `MODO_PAPER=True` (`python -u main.py`, salida redirigida)

Conexión real a Bybit (websockets públicos y endpoints privados), Groq y Telegram reales. **Sin órdenes reales:** en modo paper el sniper sale antes y el motor AS no se ejecuta.

**Intento 1 — 23:13:45 (UTC−3) — ❌ caída en el arranque**

```
load_markets → fetch_currencies → privateGetV5AssetCoinQueryInfo
ccxt.base.errors.InvalidNonce: bybit {"retCode":10002,"retMsg":"invalid request, please check your server
timestamp or recv_window param: req_timestamp[1791944083628],server_timestamp[1791944089588],recv_window[5000]"}
```

- La petición llegó **5,96 s** después de firmada; `recv_window` = 5 s.
- Medición posterior del reloj: servidor − local = **+305 a +448 ms** (RTT 450–784 ms). El desfase del reloj **no** explica 6 s: fue **latencia de conexión o DNS en frío**, el mismo patrón que tumbó el intento 1 de la V5.0.
- El servicio de hora de Windows (`w32time`) **no está iniciado**: no hay sincronización NTP activa.
- La alerta de arranque se envió antes de la caída (hallazgo ya conocido de V5.0).

**Intento 2 — 23:16:37 (UTC−3) — ✅ vivo a los 90 s, stderr vacío**

```
==================================================
INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V6.0 - ARQUITECTURA AVELLANEDA-STOIKOV)
==================================================
[MAIN] Radar fijado en 15 pares.
[MAIN] Presas: SOL/USDT:USDT, ZEC/USDT:USDT, NEAR/USDT:USDT, XRP/USDT:USDT, HYPE/USDT:USDT, STRK/USDT:USDT, ENA/USDT:USDT, CL/USDT:USDT, WLD/USDT:USDT, MU/USDT:USDT, ADA/USDT:USDT, S/USDT:USDT, QNT/USDT:USDT, DOGE/USDT:USDT, 1000PEPE/USDT:USDT
```

- La nueva lista negra retiró XAU, NVDA, SKHYNIX, SNDK y KORU (presentes en la prueba V5.0).
- **Entraron otros dos sintéticos: `CL` (petróleo crudo, `commodity`) y `MU` (Micron, `stock`).** Ver 8.2.
- Sin anomalías en esos 90 s (incluye 60 s de calentamiento de la ventana Z).

---

## 8. 🚨 Hallazgos y riesgos

### 8.1 La fórmula no es Avellaneda-Stoikov

AS (2008) define un precio de reserva `r = s − q·γ·σ²·(T−t)` y un spread óptimo `δ = γσ²(T−t) + (2/γ)·ln(1 + γ/k)`. Ambos dependen de la volatilidad σ, del inventario q y de la intensidad de llegada de órdenes k. La spec usa:

```
p_exit(t) = entry·(1 + TP) − γ·(t/T)·entry      con γ = 0,05, TP = 5 %, T = 120 s
```

Es un descuento **lineal en el tiempo**, independiente de la volatilidad, del libro y del tamaño de la posición: de +5 % a +0 % en 120 s (−0,0417 %/s). El suelo de +0,2 % se alcanza a los ~115 s.

| t (s) | Precio exigido |
|---|---|
| 0 | entry × 1,050 |
| 30 | entry × 1,0375 |
| 60 | entry × 1,025 |
| 90 | entry × 1,0125 |
| ~115 | entry × 1,002 (suelo) |
| 120 | venta a mercado |

Con la volatilidad de 1 minuto observada en V5.0 (rangos del 0,03–0,18 %), **un +5 % en 120 s es improbable**: en la práctica, la mayoría de las operaciones acabarán en el suelo o en la venta a mercado.

### 8.2 La lista negra estática es insostenible → filtro dinámico disponible

Bybit expone `market['info']['symbolType']` en cada perpetuo lineal USDT:

| `symbolType` | Nº de mercados | Ejemplos |
|---|---|---|
| `''` (cripto) | 394 | SOL, ADA, 1000PEPE, S, QNT |
| `innovation` (cripto, zona de innovación) | 128 | listados nuevos o de alto riesgo |
| `stock` | **218** | AAPL, NVDA, MU, ARM, BABA… |
| `ETF` | **57** | SPY, QQQ, SOXL, KORU, IBIT… |
| `commodity` | **4** | XAU, XAG, CL, BZ |
| `forex` | **3** | EURUSD, GBPUSD, USDJPY |

**282 sintéticos** frente a 13 añadidos a mano. Propuesta: en `main.py`, filtrar por `symbolType in ('',)` (o `('', 'innovation')`) además de `PROHIBIDAS`. **No implementado:** requiere aprobación.

### 8.3 Concurrencia sobre el mismo símbolo

El cooldown del radar es de 60 s, pero el ciclo AS dura hasta ~150 s (30 s de espera + 120 s). Un segundo disparo sobre el mismo símbolo abriría otra compra mientras el primer motor sigue vivo:

- `_posicion_larga` lee la posición **agregada**, así que el anti-zombie del motor 1 vendería también la parte del motor 2.
- Los dos motores competirían con ventas reduceOnly sobre la misma posición.
- El SL de Bybit adjunto a la orden es de posición; su interacción con dos entradas no está verificada.

Sugerencia: lock o registro por símbolo (no disparar si hay un motor AS activo en ese símbolo), o elevar el cooldown por encima de `ESPERA_LLENADO_SEG + TIEMPO_MAX_HOLD_SEG`.

### 8.4 La liquidación a mercado ignora el PnL

A los 120 s vende a mercado sea cual sea el precio, potencialmente con pérdida hasta el SL (−3 %). A eso se suman las comisiones: entrada maker ~0,02 % y salida taker ~0,055 % (valores habituales de Bybit, por confirmar para la cuenta). El nombre "Ganancia Asegurada" de `[EXITO AS]` es correcto (venta ≥ +0,2 %), pero `[ESCAPE TEMPORAL]` puede ser una pérdida y llega en verde.

### 8.5 La whitelist deja al operador ciego ante fallos críticos

Por diseño, Telegram ya no recibe:
- fallos de la liquidación a mercado;
- posición sin salida gestionada;
- caídas del arranque;
- circuit breaker.

Todo queda solo en consola. Además, la alerta de arranque se envía **antes** de `load_markets`: en el intento 1 llegó "🟩 Motor V6.0 Inicializado" y el bot murió segundos después.

### 8.6 Otros

1. **Rotación de órdenes:** con precio plano, ~58 cancel/replace por operación. Cada uno pierde la prioridad en la cola; hay riesgo de rate limit si hay muchas posiciones simultáneas. `edit_order` (amend) lo evitaría.
2. **Apagado (Ctrl+C):** `main.py` cancela las tareas del radar y `asyncio.run` cancela los motores AS. Quedan en Bybit la venta reduceOnly en reposo y el SL, sin liquidación ni limpieza.
3. **Ruido en logs:** con la API caída, 1 línea cada 2 s por posición (60 líneas en E).
4. **PostOnly en el reajuste:** la condición usa `last`; una venta PostOnly se rechaza si su precio ≤ best bid. Está cubierto por la reposición (escenario F), pero el filtro ideal sería contra `bid`.
5. **Arranque frágil** (heredado, mejora G de V5.0): `InvalidNonce` o DNS en frío matan el bot. Mitigación: `recvWindow` mayor (p. ej. 10–20 s), reintentos con backoff en `load_markets`/`fetch_tickers`, `w32time` activo.
6. **Mejoras A–I del informe V5.0** (falsos positivos del Z, carrera breaker↔sniper, etc.): **siguen sin implementar**. El motor AS no corrige la calidad de las entradas.

---

## 9. Preguntas abiertas para revisión (Deep Think)

1. **¿AS real o descuento temporal?** ¿Merece la pena implementar el precio de reserva y el spread de Avellaneda-Stoikov (σ estimada en línea, k calibrada desde el libro o los trades, q = tamaño de la posición), o el descuento lineal es suficiente para una salida de una sola posición larga? ¿Qué forma de decaimiento (lineal, exponencial, dependiente de σ) maximiza la esperanza neta de comisiones?
2. **Calibración de TP_PCT, GAMMA_AS y T:** con la volatilidad real de 1–2 min de los TOP_N, ¿qué probabilidad tiene cada nivel de precio de ejecutarse en una ventana de 120 s? ¿Es coherente un TP inicial de +5 %?
3. **Anti-zombie:** ¿liquidar siempre a mercado a los 120 s, o condicionar al PnL o la volatilidad (p. ej. extender el hold si el precio está por encima de la entrada y el flujo es favorable)?
4. **Interacción con el SL de Bybit:** ¿el `stopLoss` adjunto a una compra PostOnly parcialmente llenada y después cancelada protege la parte llenada? ¿Y con dos entradas en el mismo símbolo (`tpslMode` Full vs Partial)?
5. **Universo:** ¿filtrar por `symbolType == ''` solamente, o incluir `innovation`? ¿Mantener `PROHIBIDAS` solo para criptos concretas (stablecoins, BTC/ETH)?
6. **Telemetría:** ¿un segundo canal (u otro chat) para alertas críticas no verdes, sin romper la regla de "solo victorias" del canal principal?
7. **Riesgo agregado:** con `KELLY_MAX_PCT = 0,35` por disparo y varios motores AS simultáneos, ¿qué límite de exposición total y de posiciones concurrentes aplicar?

---

## 10. Pendiente

- [ ] Revisión Deep Think de este documento.
- [ ] Decidir: filtro dinámico por `symbolType` (8.2), lock por símbolo (8.3), robustez del arranque (8.6.5), canal de alertas críticas (8.5).
- [ ] Decidir mejoras A–I del informe V5.0 antes de cualquier ejecución prolongada en paper.
- [ ] Prueba del motor AS en **Bybit testnet** antes de `MODO_PAPER=False` (el motor AS solo se ha validado con un exchange simulado).
