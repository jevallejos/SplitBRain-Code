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
# 2. CONFIGURACIÓN BASE DE MERCADO Y RADAR DE MICROESTRUCTURA (V6.3.0)
# ==============================================================================
MODO_PAPER = False          # Modo Producción Real en Bybit UTA (asia-northeast1)
TOP_N = 15
UMBRAL_PANICO = -2.6
UMBRAL_OFI_TOXICO = -0.35   # V6.2.4+: Filtra libros con > 2.08x presión vendedora
CAIDA_MIN_PCT = -0.0045     # V6.3.0: Exige caída >= 0.45% desde el máximo de 60s
STD_MIN = 1e-8
STD_REL_FLOOR = 0.0005      # Piso de volatilidad relativa (0.05% del precio)
Z_MAX_ABS = 50.0

# ==============================================================================
# 3. GESTIÓN DE CAPITAL, TAMAÑO DE ORDEN Y VIABILIDAD DE LOTE (V6.3.0)
# ==============================================================================
KELLY_MAX_PCT = 0.35
APALANCAMIENTO = 3
CAPITAL_BASE_USDT = 11.2365       # Sincronizado con certificación real Bybit UTA
MIN_INVERSION_USDT = 2.0          # Margen mínimo por disparo
MAX_MIN_QTY_KELLY_RATIO = 0.60    # V6.3.0: Excluye pares cuyo min_qty*price > 60% del nocional Kelly (BTW, ZEC)
PENNY_JUMP_OFI_MIN = 0.25         # V6.3.0: Adelanta best_bid + 1 tick si spread >= 2 ticks y OFI >= +0.25
ESPERA_LLENADO_SEG = 10           # V6.3.0: Cancela compras no llenadas en 10s para liberar margen rápido
KEEPALIVE_SOCKET_SEG = 45.0       # V6.3.0: Mantiene caliente el socket TLS privado hacia Bybit

# ==============================================================================
# 4. GESTIÓN DINÁMICA DE SALIDAS Y FIN DEL "VALLE DE LA MUERTE" (V6.3.0)
# ==============================================================================
MOTOR_SALIDA = "TRAILING"   # "TRAILING" (PositionManager) | "AS" (Avellaneda-Stoikov HJB)

# Horquilla temporal máxima y cuarentena post-cierre Anti-Knife-Catching
TIEMPO_MAX_HOLD_SEG = 300         # 5 minutos máximos de retención (Anti-Zombie)
COOLDOWN_POST_CIERRE_SEG = 300    # V6.3.0: 300s de bloqueo por símbolo medidos desde el CIERRE

# Parámetros de Triple Barrera Recalibrados (Micro-Break-Even y Trailing Ágil)
TP_PCT = 0.05                     # Referencia de Take-Profit (+5.0%)
SL_PCT = 0.03                     # SL de catástrofe adjunto en Bybit (-3.0%)
SL_INICIAL_PCT = 0.025            # SL interno inicial (-2.5%)
BE_ACTIVACION_PCT = 0.0048        # V6.3.0: PnL >= +0.48% -> Arma Micro-Break-Even
BE_OFFSET_PCT = 0.0012            # V6.3.0: Asegura entrada + 0.12% (cubre fees y deja utilidad neta)
TRAIL_ACTIVACION_PCT = 0.0080     # V6.3.0: PnL >= +0.80% -> Activa Trailing Stop
TRAIL_DISTANCIA_PCT = 0.0035      # V6.3.0: Distancia de trailing ajustada a 0.35% desde el máximo
OFI_SALIDA_EMERGENCIA = -0.80     # Salida a mercado si el flujo es tóxico en pérdidas
OFI_SALIDA_VENTANA_SEG = 10       # Ventana de media móvil OFI para salida de emergencia
SYNC_SL_EXCHANGE_SEG = 5          # Sincronización de SL dinámico hacia Bybit (segundos)

# Parámetros Avellaneda-Stoikov HJB Real (AS)
GAMMA_AS = 0.05
KAPPA_AS = 1.5                    # Densidad estructural del libro de órdenes k

# ==============================================================================
# 5. CIRCUIT BREAKER GLOBAL (BTC + CONTAGIO CROSS-ASSET V6.3.0)
# ==============================================================================
BLOQUEO_BTC_SEG = 300
CONTAGIO_MIN_PARES = 3            # V6.3.0: >= 3 altcoins en pánico activan bloqueo global y evacuación
CONTAGIO_VENTANA_SEG = 10.0       # V6.3.0: Ventana móvil de 10s para detección de contagio simultáneo
OFI_REANUDACION_BTC = 0.30
OFI_REANUDACION_VENTANA_SEG = 30
RECUPERACION_MIN_PCT = 0.50

# ==============================================================================
# 6. CENTINELA LPU GROQ (MEMORIA RAM LOCK-FREE + ROTACIÓN MULTI-MODELO V6.3.0)
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