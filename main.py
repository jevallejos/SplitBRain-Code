import asyncio
import importlib
import sys

import ccxt.pro as ccxt
import config_parametros as cfg

radar = importlib.import_module("1_radar_volatilidad")
vigilar_mercado = radar.cazar_anomalia_ws
enviar_alerta = importlib.import_module("4_telemetria_telegram").enviar_alerta

# Consola a prueba de emojis (Windows usa cp1252 al redirigir la salida a log/pipe)
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")


async def main():
    print("==================================================")
    print("INICIANDO CEREBRO CENTRAL SPLIT-BRAIN HFT (V5.0 - ARQUITECTURA CUÁNTICA OFI)")
    print("==================================================")
    await enviar_alerta("🟩 Motor SPLITBRAIN V5.0 Inicializado.")

    exchange = ccxt.bybit({"apiKey": cfg.BYBIT_API_KEY, "secret": cfg.BYBIT_API_SECRET})
    tareas = []  # referencias fuertes: evita que el GC destruya tareas en curso
    try:
        await exchange.load_markets()
        tickers = await exchange.fetch_tickers()
        candidatos = [t for sym, t in tickers.items()
                      if sym.endswith("USDT:USDT") and sym not in cfg.PROHIBIDAS]
        candidatos.sort(key=lambda t: t.get("quoteVolume") or 0, reverse=True)
        presas = [t["symbol"] for t in candidatos[:cfg.TOP_N]]
        print(f"[MAIN] Radar fijado en {len(presas)} pares.")
        print(f"[MAIN] Presas: {', '.join(presas)}")

        tareas.append(asyncio.create_task(radar.cazar_cisne_negro(exchange)))
        for symbol in presas:
            tareas.append(asyncio.create_task(vigilar_mercado(exchange, symbol)))

        while True:
            await asyncio.sleep(1)
    finally:
        for t in tareas:
            t.cancel()
        await exchange.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN] Apagado manual.")
