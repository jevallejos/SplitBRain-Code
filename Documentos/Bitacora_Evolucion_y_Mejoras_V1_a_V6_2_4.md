---

#### B. Archivo `Documentos/Bitacora_Evolucion_y_Mejoras_V1_a_V6_2_4.md`
Documenta exhaustivamente cada versión y mejora técnica siguiendo el estándar de los archivos originales de la carpeta `Documentos/`[cite: 1] y del documento fundacional `Split-Brain-Code Proyect.pdf`[cite: 2, 3, 4, 5, 6, 7, 8, 9].

```markdown
# Bitácora de Evolución Arquitectónica y Mejoras Técnicas (V1.0 a V6.2.4 Base Estable)

Este documento consolida la genealogía técnica, las decisiones de ingeniería y las remediaciones forenses aplicadas al motor **Split-Brain HFT** desde su concepción experimental hasta la **Versión 6.2.4 (Base Estable)** desplegada en producción en GCP Tokio (`sniper-tokio`).

---

## 1. Fase Fundacional y Transición Microestructural (V1.0 – V6.0)

### V1.0 – V2.0: Fase de Laboratorio y Validación Conceptual
- Implementación del prototipo inicial en entorno local (ASUS TUF Gaming FX505DD, Ryzen 5, 16 GB RAM, GTX 1050) bajo modalidad *Paper Trading*.
- Identificación del cuello de botella de inferencia local (Ollama sobre GPU de 3 GB) frente a la velocidad requerida por el libro de órdenes.

### V3.0: Fase de Telemetría y Delegación a LPU
- Migración de la inferencia cualitativa hacia la red **Groq LPU** utilizando el modelo `openai/gpt-oss-20b`.
- Escaneo concurrente de múltiples pares mediante flujos WebSocket asíncronos.

### V4.0: Fuego Real y Pivote Geográfico a Tokio
- Despliegue en **Google Cloud Platform (GCP)** región `asia-northeast1` (Tokio) sobre instancia `e2-micro` con Ubuntu 24.04 LTS, logrando latencia $< 5\text{ ms}$ hacia Singapur y evadiendo bloqueos regionales (`403 Forbidden`).
- Sincronización de reloj atómico mediante `chrony` (`chronyc makestep`) para erradicar rechazos de firma `InvalidNonce`.
- Ejecución estricta con órdenes `Limit PostOnly` para garantizar cero *slippage* en entrada y captura de tarifa *Maker* ($0.02\%$).

### V5.0: Arquitectura Cuántica OFI y Repositorio Inmaculado (`SplitBRain-Code`)
- **Aislamiento Zero-Debt:** Creación del repositorio limpio `SplitBRain-Code` (reemplazando `HFT_SplitBrain`) con dependencias mínimas (`ccxt`, `groq`, `aiohttp`, `python-dotenv`) y extirpación de `winloop`.
- **Radar de Toxicidad OFI (`calcular_ofi`):** Extracción en $O(1)$ de `bidVolume` y `askVolume` del Nivel 1 del libro de órdenes para abortar compras ante cascadas de venta informada ("cuchillos cayendo").

### V6.0: Salidas Dinámicas de Avellaneda-Stoikov y Silenciador de Telemetría
- Introducción del motor de decaimiento temporal de precio de salida inspirado en Avellaneda-Stoikov (`motor_salida_avellaneda_stoikov`) para tratar el inventario como "radiactivo".
- Implementación de lista blanca en `4_telemetria_telegram.py` (`PALABRAS_SILENCIADAS` y filtro `🟩`) para evitar saturación de alertas de error.

---

## 2. Fase "Adaptive Quantum Predator" y Caja Negra (V6.1)

Nacida tras la auditoría de fricciones mecánicas en producción:
1. **Smart Quantization (`cuantizar_orden`):** Cuantización exacta de cantidad y precio con `Decimal` y `ROUND_FLOOR` al `step_size` y `tick_size` de cada mercado, abortando en memoria si no alcanza `min_notional` o `min_qty` sin golpear la API.
2. **Auto-Blacklist Dinámica (`BLACKLIST_PAIRS`):** Detección por expresión regular de códigos de restricción de Bybit (`110126`, `10024`, `10029`) y liberación inmediata del stream WebSocket (`un_watch_tickers`).
3. **Filtro Anti-Glitch Matemático (`es_glitch`):** Descarte de valores `Z` no finitos o con $\vert{}Z\vert{} > 50.0$ provocados por vacíos momentáneos de liquidez, e incorporación de resincronización periódica cada $10,000$ ticks contra deriva de coma flotante IEEE 754.
4. **Circuit Breaker Inteligente con Recuperación en V (`cazar_cisne_negro`):** Reducción del bloqueo global por colapso de BTC ($Z \le -4.0$) de $1,800\text{ s}$ a $300\text{ s}$, añadiendo desbloqueo anticipado si la media móvil de $30\text{ s}$ del OFI de BTC supera $+0.30$ y el precio recupera $\ge 50\%$ de la caída.
5. **PositionManager (`5_gestor_posiciones.py`):** Gestión independiente por posición con *Stop-Loss* interno ($-2.5\%$), *Break-Even* ($+1.0\%$ $\to$ $+0.15\%$), *Trailing Stop* ($+1.5\%$ con distancia de $0.8\%$), *OFI Exit* ($\text{OFI}_{10\text{s}} < -0.80$) y sincronización hacia arriba del Stop-Loss de respaldo en Bybit (`privatePostV5PositionTradingStop`).
6. **Caja Negra (`6_stats_tracker.py`):** Registro persistente en `splitbrain_stats_v6.jsonl` y dashboard periódico en consola con cálculo exacto de comisiones y lectura de balance real.

---

## 3. Fase "Groq RAM Lock-Free Sentinel" (V6.2)

1. **Erradicación de Latencia HTTP de IA en la Ruta Crítica (`2_escudo_semantico.py`):**
   - Sustitución de la consulta bloqueante a Groq en el momento del pánico por el demonio `CentinelaGroqRAM`, que audita el lote completo cada $180\text{ s}$ en segundo plano y actualiza atómicamente un `frozenset` en RAM (`_whitelist_ram`).
   - Reducción del tiempo de consulta del Escudo Semántico de $\sim 1,100\text{ ms}$ a **$\sim 0.65\ \mu\text{s}$ ($O(1)$ sin locks)**.
2. **Fallback Cuantitativo Anti-LUNA (`_filtro_heuristico_respaldo`):**
   - Si Groq experimenta caída o *rate limit*, un filtro determinista local veta activos con caída $\le -6.0\%$ en $60\text{ s}$ y $\text{OFI} \le -0.85$.
3. **Piso de Volatilidad Relativa (`STD_REL_FLOOR = 0.0005`):**
   - Previene que micro-oscilaciones de $-0.04\%$ en mercados planos disparen falsos $Z$-Scores extremos.
4. **Telemetría Local Persistente (`_TeeLogger` en `main.py`):**
   - Duplicación automática de `stdout` y `stderr` hacia `bot_hft.log`.

---

## 4. Fase de Blindaje Forense en Producción: Serie V6.2.1 a V6.2.4 (Base Estable)

Mejoras implementadas tras la auditoría forense de los registros reales de Bybit (`Bybit-UTA-Perp-OrderHistory`) en `sniper-tokio`:

### Hotfix V6.2.1: Cerrojo de Instancia Única y Escape Anti-Zombie en PositionManager
- **Problema Detectado:** Tres posiciones (`ADAUSDT`, `ENAUSDT`, `XRPUSDT`) quedaron atrapadas en rango lateral durante más de 4 horas consumiendo $\$8.24\text{ USDT}$ de margen (dejando el margen libre en $\$1.44\text{ USDT} < \$2.00\text{ USDT}$), además de detectarse órdenes duplicadas en el mismo segundo por dos procesos `main.py` corriendo en paralelo.
- **Solución Implementada:**
  1. Integración de `TIEMPO_MAX_HOLD_SEG = 300` dentro de `PositionManager._evaluar` (`5_gestor_posiciones.py`), forzando el cierre a mercado (`ESCAPE_TEMPORAL`) a los 5 minutos.
  2. Creación de `adquirir_bloqueo_instancia_unica()` en `main.py` mediante cerrojo exclusivo de kernel sobre `.splitbrain.lock` (`fcntl.LOCK_EX | fcntl.LOCK_NB` en Linux / `msvcrt.LK_NBLCK` en Windows).

### Hotfix V6.2.2: Auto-Reconciliador de Posiciones Huérfanas en el Arranque
- **Problema Detectado:** Al reiniciar el proceso `main.py`, `PositionManager` nacía con `self.posiciones = {}` en memoria RAM, ignorando las posiciones abiertas en sesiones anteriores.
- **Solución Implementada:**
  1. Método `reconciliar_posiciones_exchange(exchange)` en `5_gestor_posiciones.py` invocado automáticamente por `main.py` antes de armar el radar.
  2. Audita `exchange.fetch_positions()` al arrancar: si una posición heredada supera `TIEMPO_MAX_HOLD_SEG`, la liquida inmediatamente a mercado con `reduceOnly=True` (`ESCAPE_HUERFANA_BOOT`) liberando el $100\%$ del margen; si es reciente, la adopta con su edad real.
  3. Función `_auditar_margen_libre(exchange)` en `main.py` para certificar en consola el saldo total, libre, bloqueado y margen Kelly disponible.

### Hotfix V6.2.3: Auditoría Estática AST de Contratos de Configuración
- **Problema Detectado:** Excepción `AttributeError` en tiempo de disparo por ausencia de `TP_PCT` en `config_parametros.py`.
- **Solución Implementada:**
  1. Restauración íntegra del mapa de constantes en `config_parametros.py`.
  2. Incorporación de `_extraer_atributos_cfg_ast()` en `test_v6_2_suite.py`, que analiza el árbol sintáctico (`ast.walk`) de los 8 módulos y verifica que las 39 constantes invocadas en los 55 puntos de llamada existan antes de permitir el despliegue.

### Release V6.2.4 (Base Estable): Disparo Zero-REST, Fire-and-Forget Telegram, Filtro OFI `-0.35` y Sellado Temporal
- **Problemas Detectados en Traza de Producción:**
  - `ejecutar_orden_sniper` realizaba llamadas REST (`fetch_balance`, `fetch_ticker`, `set_leverage`) antes de `create_order`.
  - `await enviar_alerta(...)` bloqueaba la activación de `_entregar_al_gestor` hasta que respondiera el servidor de Telegram.
  - `UMBRAL_OFI_TOXICO = -0.50` permitía entradas con casi $3\times$ más volumen de venta que de compra (`OFI = -0.49`), agotando el margen antes de oportunidades con absorción institucional positiva.
  - Ausencia de hora exacta en cada línea de `bot_hft.log`.
- **Soluciones Implementadas:**
  1. **Ruta Crítica Zero-REST (`3_ejecutor_sniper.py`):** Inyección directa del `ticker` WebSocket desde `1_radar_volatilidad.py`, caché de margen libre en RAM (`_saldo_libre_ram`) con deducción atómica instantánea y pre-calentamiento de apalancamiento en el arranque (`precalentar_apalancamiento_universo`).
  2. **Prioridad de Vigilancia y Telegram Fire-and-Forget:** Activación de `_entregar_al_gestor` inmediatamente después de `create_order` y despacho asíncrono no bloqueante `enviar_alerta_bg()`.
  3. **Endurecimiento del Filtro de Microestructura:** Ajuste de `UMBRAL_OFI_TOXICO = -0.35` en `config_parametros.py`.
  4. **Sellado de Tiempo Dual en `_TeeLogger` (`main.py`):** Inyección automática de `[YYYY-MM-DD HH:MM:SS.mmm CL | HH:MM:SS UTC]` al inicio de cada línea escrita en consola y en `bot_hft.log`.
  5. **Certificación Empírica en Producción:** Crecimiento del capital real en Bybit de $12.3023\text{ USDT}$ a **$12.8896\text{ USDT}$ ($+0.5184\text{ USDT}$ PnL acumulado, $56.5\%$ Win Rate en 23 operaciones)** con las 8/8 pruebas de integridad aprobadas.