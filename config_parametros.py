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
PROHIBIDAS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'USDC/USDT:USDT', 'USDE/USDT:USDT', 'SOXL/USDT:USDT', 'SOXS/USDT:USDT', 'TQQQ/USDT:USDT', 'SQQQ/USDT:USDT', 'SUI/USDT:USDT', 'SPY/USDT:USDT']
