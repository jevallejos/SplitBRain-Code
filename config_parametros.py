import os
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# 1. CREDENCIALES DE INFRAESTRUCTURA Y CONECTIVIDAD
# ==============================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# ==============================================================================
# 2. CONFIGURACIÓN BASE DE MERCADO Y RADAR DE MICROESTRUCTURA (V6.4.0)
# ==============================================================================
MODO_PAPER = False                 # Modo Producción Real en Bybit UTA (asia-northeast1)
TOP_N = 15
UMBRAL_PANICO = -2.6
UMBRAL_OFI_TOXICO = 0.08           # V6.4.0: Exige absorción compradora sólida en L1 (OFI >= +0.08)
CAIDA_MIN_PCT = -0.0045            # Exige caída >= 0.45% desde el máximo rodante de 60s
EMA_MACRO_VENTANA_SEG = 900        # Horizonte de 15 min (900s) para ancla macro O(1)
TECHO_MACRO_EMA_PCT = 0.0080       # Veta compras si el precio está > +0.80% sobre EMA900 (Anti-Pump-Top)
LYAPUNOV_ACCEL_MIN = -0.00025      # V6.4.0: Freno de Atractor de Lyapunov (veta cuchillos acelerando < -0.025%/s^2)
VPIN_MAX_TOXICO = 0.72             # V6.4.0: Veta entradas con probabilidad de flujo tóxico VPIN > 0.72
VOL_MAX_P99_REL = 0.0065           # V6.4.0: Techo de volatilidad GJR-EWMA P99 (evita explosión cuadrática LVR)
MAX_SPREAD_REL_ENTRADA = 0.0012    # V6.4.0: Compuerta de fricción de Macrì (spread máximo tolerable 12 bps)
PERMITIR_ZONA_INNOVATION = False   # Excluye tokens catalogados en zona 'innovation'
STD_MIN = 1e-8
STD_REL_FLOOR = 0.0005             # Piso de volatilidad relativa (0.05% del precio)
Z_MAX_ABS = 50.0

# ==============================================================================
# 3. GESTIÓN DE CAPITAL, TAMAÑO DE ORDEN Y VIABILIDAD DE LOTE (V6.4.0)
# ==============================================================================
KELLY_MAX_PCT = 0.35
APALANCAMIENTO = 3
CAPITAL_BASE_USDT = 11.9117        # Auto-conciliado en arranque con el saldo real de Bybit UTA
MIN_INVERSION_USDT = 2.0           # Margen mínimo por disparo
MAX_MIN_QTY_KELLY_RATIO = 0.60     # Excluye pares cuyo min_qty*price > 60% del nocional Kelly (SOL, ZEC, BTW)
PENNY_JUMP_OFI_MIN = 0.25          # Adelanta best_bid + 1 tick si spread >= 2 ticks y OFI >= +0.25
ESPERA_LLENADO_SEG = 10            # Cancela compras no llenadas en 10s para liberar margen rápido
KEEPALIVE_SOCKET_SEG = 45.0        # Mantiene caliente el socket TLS privado hacia Bybit
WS_KEEPALIVE_MS = 10000            # V6.4.0: Ping-pong streaming ccxt.pro cada 10s (cero RequestTimeout)
WS_MAX_PING_MISSES = 5.0           # V6.4.0: Tolerancia de 5 latidos antes de reciclar el WebSocket

# ==============================================================================
# 4. SALIDAS MAKER-FIRST (0.02%) Y ANIQUILACIÓN DE ZOMBIES (V6.4.0)
# ==============================================================================
MOTOR_SALIDA = "TRAILING"          # "TRAILING" (PositionManager Híbrido Maker-First) | "AS"

# Reducción del horizonte anti-zombie y cortes tempranos de sangrado LVR
TIEMPO_MAX_HOLD_SEG = 180          # V6.4.0: Reducido de 300s a 180s (erradica zombies de 5 minutos)
COOLDOWN_POST_CIERRE_SEG = 300     # 300s de bloqueo por símbolo medidos estrictamente desde el CIERRE
EARLY_TOXIC_HOLD_SEG = 45          # V6.4.0: Evaluar corte temprano de cuchillo lento a partir de los 45s
EARLY_TOXIC_LOSS_PCT = -0.0080     # V6.4.0: Corta en -0.80% si a los 45s no armó BE y el flujo es negativo
EARLY_TOXIC_OFI_MAX = -0.15        # V6.4.0: Umbral OFI 10s para activar EARLY_TOXIC_SL
STAGNATION_HOLD_SEG = 105          # V6.4.0: Evaluar corte por estancamiento Markoviano a los 105s
STAGNATION_LOSS_PCT = -0.0022      # V6.4.0: Corta en -0.22% si a los 105s sigue sin BE y sin flujo comprador
STAGNATION_OFI_MAX = 0.05          # V6.4.0: Umbral OFI 10s para activar STAGNATION_EXIT

# Motor Híbrido Maker-First Unwind (PFQI Persistencia k = 12s -> Tarifa 0.020% en vez de 0.055%)
MAKER_UNWIND_ACTIVACION_PCT = 0.0052  # V6.4.0: PnL >= +0.52% con desaceleración coloca Limit Sell PostOnly
MAKER_UNWIND_STALL_SEG = 65           # V6.4.0: Si t >= 65s y PnL >= +0.12%, coloca Limit Sell PostOnly
MAKER_UNWIND_MIN_PNL_PCT = 0.0012     # V6.4.0: Ganancia mínima (+0.12%) para desarme pasivo pre-estancamiento
MAKER_UNWIND_OFI_TECHO = 0.18         # V6.4.0: Solo coloca orden pasiva si el impulso comprador cede (OFI < +0.18)
MAKER_PERSISTENCIA_SEG = 12.0         # V6.4.0: Persistencia PFQI de 12s en el libro para conservar cola FIFO

# Parámetros de Triple Barrera Recalibrados y Cota Inferior de SL en Exchange
TP_PCT = 0.05                      # Referencia de Take-Profit (+5.0%)
SL_PCT = 0.03                      # SL de catástrofe adjunto en Bybit (-3.0%)
SL_INICIAL_PCT = 0.025             # SL interno inicial (-2.5%)
BE_ACTIVACION_PCT = 0.0045         # V6.4.0: PnL >= +0.45% -> Arma Micro-Break-Even
BE_OFFSET_PCT = 0.0016             # Asegura entrada + 0.16% interno (cubre fees Taker y slippage)
BE_PISO_EXCHANGE_PCT = 0.0010      # El SL sincronizado en Bybit jamás baja de entrada + 0.10%
TRAIL_ACTIVACION_PCT = 0.0075      # V6.4.0: PnL >= +0.75% -> Activa Trailing Stop
TRAIL_DISTANCIA_PCT = 0.0032       # V6.4.0: Distancia de trailing ceñida a 0.32% desde el máximo
OFI_SALIDA_EMERGENCIA = -0.42      # V6.4.0: Sensibilizado de -0.80 a -0.42 para abortar desplomes rápido
OFI_SALIDA_MIN_LOSS_PCT = -0.0025  # V6.4.0: Pérdida mínima (-0.25%) para disparar OFI_EXIT
OFI_SALIDA_VENTANA_SEG = 10        # Ventana de media móvil OFI para salida de emergencia
SYNC_SL_EXCHANGE_SEG = 5           # Sincronización de SL dinámico hacia Bybit (segundos)

# Parámetros Avellaneda-Stoikov HJB Real (AS)
GAMMA_AS = 0.05
KAPPA_AS = 1.5

# ==============================================================================
# 5. CIRCUIT BREAKER GLOBAL (BTC + CONTAGIO CROSS-ASSET)
# ==============================================================================
BLOQUEO_BTC_SEG = 300
CONTAGIO_MIN_PARES = 3             # >= 3 altcoins en pánico activan bloqueo global y evacuación
CONTAGIO_VENTANA_SEG = 10.0        # Ventana móvil de 10s para detección de contagio simultáneo
OFI_REANUDACION_BTC = 0.30
OFI_REANUDACION_VENTANA_SEG = 30
RECUPERACION_MIN_PCT = 0.50

# ==============================================================================
# 6. CENTINELA LPU GROQ (MEMORIA RAM LOCK-FREE + ROTACIÓN MULTI-MODELO)
# ==============================================================================
GROQ_CICLO_SEG = 180
GROQ_TIMEOUT_SEG = 6.0
GROQ_MODELOS = (
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
)

# ==============================================================================
# 7. TELEMETRÍA, COMISIONES Y PERSISTENCIA (CAJA NEGRA)
# ==============================================================================
FEE_MAKER = 0.0002
FEE_TAKER = 0.00055
STATS_FILE = "splitbrain_stats_v6.jsonl"
DASHBOARD_INTERVALO_SEG = 300

# ==============================================================================
# 8. FILTROS INSTITUCIONALES Y LISTAS NEGRAS DINÁMICAS
# ==============================================================================
PROHIBIDAS = [
    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'USDC/USDT:USDT', 'USDE/USDT:USDT',
    'SOXL/USDT:USDT', 'SOXS/USDT:USDT', 'TQQQ/USDT:USDT', 'SQQQ/USDT:USDT',
    'SUI/USDT:USDT', 'SPY/USDT:USDT', 'LUNA/USDT:USDT', 'LUNA2/USDT:USDT',
    'XAU/USDT:USDT', 'XAG/USDT:USDT', 'NVDA/USDT:USDT', 'SKHYNIX/USDT:USDT',
    'SNDK/USDT:USDT', 'KORU/USDT:USDT', 'AAPL/USDT:USDT', 'TSLA/USDT:USDT',
    'AMZN/USDT:USDT', 'GOOGL/USDT:USDT', 'META/USDT:USDT', 'MSTR/USDT:USDT',
    'COIN/USDT:USDT', 'HOOD/USDT:USDT'
]

BLACKLIST_PAIRS: set[str] = set()
CODIGOS_BLACKLIST = ("110126", "10024", "10029")