# SPLIT-BRAIN HFT — Adaptive Quantum Predator (V6.2.4 Base Estable)

Motor de arbitraje cuantitativo y reversión a la media de alta frecuencia (HFT) diseñado para operar perpetuos lineales USDT en **Bybit UTA**, fundamentado en microestructura de libro de órdenes (Order Flow Imbalance), gestión dinámica de inventario e inferencia semántica/cuantitativa desacoplada en memoria RAM sobre unidades de procesamiento de lenguaje (**Groq LPU**).

---

## 1. Arquitectura de Cerebro Dividido (Principio de Segmentación TRIZ)

El sistema resuelve la contradicción física entre la latencia de inferencia de modelos de lenguaje ($\sim 800\text{–}1,500\text{ ms}$) y la velocidad de ejecución microestructural ($\sim 30\text{–}60\ \mu\text{s}$ en CPU) dividiendo el procesamiento en tres motores independientes:

1. **Módulo Cuantitativo — Motor A (`1_radar_volatilidad.py`):**
   - Escanea en tiempo real los 15 perpetuos cripto-nativos con mayor volumen vía WebSockets (`ccxt.pro`).
   - Calcula el $Z$-Score rodante en $O(1)$ (`VentanaZ`) con piso de volatilidad relativa (`STD_REL_FLOOR = 0.0005`) y filtro anti-glitch (`Z_MAX_ABS = 50.0`).
   - Evalúa la tensión de liquidez en el Nivel 1 mediante **Order Flow Imbalance ($\text{OFI}$)** y bloquea disparos cuando la presión de venta supera $2.08\times$ la de compra (`UMBRAL_OFI_TOXICO = -0.35`).
   - Incluye un **Circuit Breaker Global sobre BTC** con regla de excepción cuántica por recuperación en $V$ ($\text{OFI}_{\text{BTC}} > 0.30$ y recuperación $\ge 50\%$).

2. **Módulo Cualitativo / Cuantitativo LPU — Motor B (`2_escudo_semantico.py`):**
   - Demonio asíncrono (`CentinelaGroqRAM`) que audita en segundo plano el universo de activos cada $180\text{ s}$ empleando `openai/gpt-oss-20b` en Groq LPU.
   - Actualiza mediante intercambio atómico de punteros un `frozenset` en memoria RAM (`_whitelist_ram`), permitiendo que la ruta crítica verifique la aprobación del activo en **$\sim 0.65\ \mu\text{s}$ ($O(1)$ Lock-Free)**.
   - Incorpora un filtro heurístico cuantitativo de respaldo (*Anti-LUNA*) ante caídas estructurales ($> 6\%$ en $60\text{ s}$ con $\text{OFI} \le -0.85$).

3. **Módulo Determinista de Ejecución y Gestión — Motor C (`3_ejecutor_sniper.py` y `5_gestor_posiciones.py`):**
   - **Disparo Zero-REST:** Lee el saldo libre desde caché atómico en RAM (`_saldo_libre_ram`), extrae el precio *Maker* directamente del frame WebSocket y pre-calienta el apalancamiento ($3\times$) en el arranque, ejecutando únicamente `create_order` con `timeInForce="PostOnly"`.
   - **Auto-Reconciliador de Arranque:** Al iniciar `main.py`, audita Bybit para adoptar posiciones vivas heredadas o liquidar inmediatamente posiciones zombies que hayan excedido `TIEMPO_MAX_HOLD_SEG = 300` segundos.
   - **PositionManager Dinámico:** Gestiona *Stop-Loss* inicial ($-2.5\%$ interno / $-3.0\%$ en Bybit), *Break-Even* ($+1.0\%$ $\to$ $+0.15\%$), *Trailing Stop* ($+1.5\%$ con distancia de $0.8\%$), *OFI Exit* de emergencia ($\text{OFI}_{10\text{s}} < -0.80$) y *Escape Temporal Anti-Zombie* ($300\text{ s}$).

4. **Caja Negra y Observabilidad (`6_stats_tracker.py`, `4_telemetria_telegram.py`, `main.py`):**
   - Registro inmutable en disco (`splitbrain_stats_v6.jsonl`) mediante hilos asíncronos (`asyncio.to_thread`).
   - Log operativo `bot_hft.log` con sellado de tiempo dual al milisegundo (`[YYYY-MM-DD HH:MM:SS.mmm CL | HH:MM:SS UTC]`).
   - Alertas a Telegram despachadas en modo *Fire-and-Forget* (`enviar_alerta_bg`) con filtro de lista blanca.
   - Cerrojo físico de proceso único a nivel de kernel (`.splitbrain.lock` vía `fcntl`/`msvcrt`).

---

## 2. Estructura del Repositorio

```text
SplitBRain-Code/
├── config_parametros.py          # Parámetros de riesgo, microestructura, Kelly y listas negras
├── main.py                       # Orquestador central, PID Lock, _TeeLogger con hora y arranque
├── 1_radar_volatilidad.py        # VentanaZ O(1), cálculo OFI y Circuit Breaker de BTC
├── 2_escudo_semantico.py         # Centinela Groq LPU en background y Whitelist Lock-Free en RAM
├── 3_ejecutor_sniper.py          # Ejecutor PostOnly Zero-REST, Smart Quantization y motor AS
├── 4_telemetria_telegram.py      # Emisor asíncrono de alertas con lista blanca institucional
├── 5_gestor_posiciones.py        # PositionManager, Trailing, OFI Exit, Escape 300s y Reconciliador
├── 6_stats_tracker.py            # Caja Negra JSONL y Dashboard de rendimiento en consola
├── test_v6_2_suite.py            # Suite de verificación integrada (8/8 pruebas con auditoría AST)
├── requirements.txt              # Dependencias limpias: ccxt, groq, aiohttp, python-dotenv
└── Documentos/                   # Especificaciones técnicas y bitácora de evolución V1.0 a V6.2.4