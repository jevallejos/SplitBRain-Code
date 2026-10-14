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
