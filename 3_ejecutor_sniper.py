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
