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
PROHIBIDAS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'USDC/USDT:USDT', 'USDE/USDT:USDT', 'SOXL/USDT:USDT', 'SOXS/USDT:USDT', 'TQQQ/USDT:USDT', 'SQQQ/USDT:USDT', 'SUI/USDT:USDT', 'SPY/USDT:USDT', 'LUNA/USDT:USDT', 'XAU/USDT:USDT', 'NVDA/USDT:USDT']
# Extensión V6.0: LUNA real en Bybit (LUNA2) y sintéticos (acciones/materias primas) detectados en el exchange
PROHIBIDAS += ['LUNA2/USDT:USDT', 'XAG/USDT:USDT', 'SKHYNIX/USDT:USDT', 'SNDK/USDT:USDT', 'KORU/USDT:USDT',
               'AAPL/USDT:USDT', 'TSLA/USDT:USDT', 'AMZN/USDT:USDT', 'GOOGL/USDT:USDT', 'META/USDT:USDT',
               'MSTR/USDT:USDT', 'COIN/USDT:USDT', 'HOOD/USDT:USDT']

# Parámetros Avellaneda-Stoikov (AS) Salidas Dinámicas
GAMMA_AS = 0.05  # Aversión al riesgo de inventario (Velocidad de decaimiento del precio)
TIEMPO_MAX_HOLD_SEG = 120  # Segundos máximos antes de liquidar a mercado (Operación Zombie)

# ===================== V6.1 APEX PREDATOR =====================
# Motor de salida: "TRAILING" (PositionManager V6.1) | "AS" (Avellaneda-Stoikov V6.0)
MOTOR_SALIDA = "TRAILING"

# Tamaño: nocional = saldo libre × KELLY_MAX_PCT × APALANCAMIENTO (margen usado = saldo × Kelly)
APALANCAMIENTO = 3

# Gestión dinámica de riesgo (PositionManager). SL_PCT (3 %) queda como SL de catástrofe en Bybit.
SL_INICIAL_PCT = 0.025        # SL interno inicial (-2.5 %)
BE_ACTIVACION_PCT = 0.010     # PnL ≥ +1.0 % → SL a break-even
BE_OFFSET_PCT = 0.0015        # break-even = entrada + 0.15 % (cubre fees)
TRAIL_ACTIVACION_PCT = 0.015  # PnL ≥ +1.5 % → trailing activo
TRAIL_DISTANCIA_PCT = 0.008   # trailing a 0.8 % del máximo
OFI_SALIDA_EMERGENCIA = -0.80
OFI_SALIDA_VENTANA_SEG = 10   # media móvil del OFI para la salida de emergencia (solo con PnL < 0)
SYNC_SL_EXCHANGE_SEG = 5      # máx. 1 actualización del SL en Bybit cada N s

# Circuit breaker en V
BLOQUEO_BTC_SEG = 300               # 5 min
OFI_REANUDACION_BTC = 0.30
OFI_REANUDACION_VENTANA_SEG = 30    # media móvil del OFI de BTC
RECUPERACION_MIN_PCT = 0.50         # BTC debe recuperar ≥ 50 % de la caída

# Filtro anti-glitch del Z-Score
STD_MIN = 1e-8
Z_MAX_ABS = 50.0

# Caja negra (Stats Tracker)
CAPITAL_BASE_USDT = 13.18
STATS_FILE = "splitbrain_stats_v6.jsonl"
FEE_MAKER = 0.0002    # estimación para el PnL neto
FEE_TAKER = 0.00055
DASHBOARD_INTERVALO_SEG = 300

# Auto-blacklist dinámica (se rellena en tiempo de ejecución)
BLACKLIST_PAIRS: set[str] = set()
CODIGOS_BLACKLIST = ("110126", "10024", "10029")  # acuerdo sin firmar / compliance / símbolo no permitido
