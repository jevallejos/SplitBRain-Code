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
# 2. CONFIGURACIÓN BASE DE MERCADO Y RADAR DE MICROESTRUCTURA
# ==============================================================================
MODO_PAPER = False  # Modo Real UTA Perpetuos
TOP_N = 15
UMBRAL_PANICO = -2.6
UMBRAL_OFI_TOXICO = -0.5
STD_MIN = 1e-8
STD_REL_FLOOR = 0.0005  # Piso de volatilidad relativa (0.05% del precio)
Z_MAX_ABS = 50.0

# ==============================================================================
# 3. GESTIÓN DE CAPITAL, TAMAÑO DE ORDEN Y APALANCAMIENTO
# ==============================================================================
KELLY_MAX_PCT = 0.35
APALANCAMIENTO = 3
CAPITAL_BASE_USDT = 13.18
MIN_INVERSION_USDT = 2.0  # Margen mínimo para disparar

# ==============================================================================
# 4. GESTIÓN DINÁMICA DE SALIDAS (HOTFIX V6.2.1 ANTI-ZOMBIE ESCAPE)
# ==============================================================================
MOTOR_SALIDA = "TRAILING"  # "TRAILING" (PositionManager V6.2.1) | "AS" (Avellaneda-Stoikov)

# Horquilla temporal máxima para liberar margen forzosamente ante mercados planos
TIEMPO_MAX_HOLD_SEG = 300  # 5 minutos máximos de retención (Erradicación de Posiciones Zombie)

# Parámetros del PositionManager
SL_PCT = 0.03                 # SL de emergencia en Bybit (-3.0%)
SL_INICIAL_PCT = 0.025        # SL interno (-2.5%)
BE_ACTIVACION_PCT = 0.010     # PnL ≥ +1.0% → SL a break-even
BE_OFFSET_PCT = 0.0015        # SL break-even = entrada + 0.15% (cubre fees)
TRAIL_ACTIVACION_PCT = 0.015  # PnL ≥ +1.5% → Trailing activo
TRAIL_DISTANCIA_PCT = 0.008   # Distancia de trailing: 0.8% desde el pico máximo
OFI_SALIDA_EMERGENCIA = -0.80 # Salida inmediata a mercado si el flujo es tóxico en pérdidas
OFI_SALIDA_VENTANA_SEG = 10   # Ventana de media móvil OFI
SYNC_SL_EXCHANGE_SEG = 5      # Sincronización de SL dinámico hacia Bybit (segundos)

# Parámetros heredados de Avellaneda-Stoikov (AS)
GAMMA_AS = 0.05

# ==============================================================================
# 5. CIRCUIT BREAKER GLOBAL (BTC V-SHAPE RECOVERY)
# ==============================================================================
BLOQUEO_BTC_SEG = 300
OFI_REANUDACION_BTC = 0.30
OFI_REANUDACION_VENTANA_SEG = 30
RECUPERACION_MIN_PCT = 0.50

# ==============================================================================
# 6. CENTINELA LPU GROQ (MEMORIA RAM LOCK-FREE)
# ==============================================================================
GROQ_CICLO_SEG = 180
GROQ_TIMEOUT_SEG = 6.0

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