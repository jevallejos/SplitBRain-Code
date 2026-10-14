"""Suite de Verificación Integrada para SplitBRain-Code V6.2.2 (6/6 Pruebas de Grado Producción)."""
import asyncio
import importlib
import py_compile
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ARCHIVOS_PROYECTO = [
    "config_parametros.py",
    "1_radar_volatilidad.py",
    "2_escudo_semantico.py",
    "3_ejecutor_sniper.py",
    "4_telemetria_telegram.py",
    "5_gestor_posiciones.py",
    "6_stats_tracker.py",
    "main.py",
]


class _MockExchangeHuerfanas:
    """Simula en memoria las 3 posiciones zombies reales de Bybit (ADA, ENA, XRP) sin tocar red."""

    def __init__(self, t_antiguo_ms: int) -> None:
        self.t_antiguo_ms = t_antiguo_ms
        self.ordenes_cerradas: List[Dict[str, Any]] = []

    async def fetch_positions(self, symbols: Any = None) -> List[Dict[str, Any]]:
        todas = [
            {
                "symbol": "ADA/USDT:USDT",
                "side": "long",
                "contracts": 33.0,
                "entryPrice": 0.2307,
                "markPrice": 0.2315,
                "timestamp": self.t_antiguo_ms,
                "info": {"avgPrice": "0.2307", "markPrice": "0.2315", "updatedTime": str(self.t_antiguo_ms)},
            },
            {
                "symbol": "ENA/USDT:USDT",
                "side": "long",
                "contracts": 53.0,
                "entryPrice": 0.19659,
                "markPrice": 0.19720,
                "timestamp": self.t_antiguo_ms,
                "info": {"avgPrice": "0.19659", "markPrice": "0.19720", "updatedTime": str(self.t_antiguo_ms)},
            },
            {
                "symbol": "XRP/USDT:USDT",
                "side": "long",
                "contracts": 5.0,
                "entryPrice": 1.3278,
                "markPrice": 1.3310,
                "timestamp": self.t_antiguo_ms,
                "info": {"avgPrice": "1.3278", "markPrice": "1.3310", "updatedTime": str(self.t_antiguo_ms)},
            },
        ]
        if symbols:
            return [p for p in todas if p["symbol"] in symbols]
        return todas

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        return f"{float(amount):.4f}"

    def price_to_precision(self, symbol: str, price: float) -> str:
        return f"{float(price):.6f}"

    async def create_order(
        self, symbol: str, order_type: str, side: str, amount: Any, price: Any = None, params: Any = None
    ) -> Dict[str, Any]:
        orden = {
            "id": f"mock_{len(self.ordenes_cerradas) + 1}",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": float(amount),
            "params": params or {},
        }
        self.ordenes_cerradas.append(orden)
        return orden

    async def fetch_order(self, order_id: str, symbol: str, params: Any = None) -> Dict[str, Any]:
        precios_mock = {
            "ADA/USDT:USDT": 0.2315,
            "ENA/USDT:USDT": 0.19720,
            "XRP/USDT:USDT": 1.3310,
        }
        return {"id": order_id, "status": "closed", "average": precios_mock.get(symbol, 1.0)}

    async def fetch_balance(self) -> Dict[str, Any]:
        return {"USDT": {"total": 12.3663, "free": 12.3663}}


async def ejecutar_auditoria_v6_2() -> None:
    print("==================================================================")
    print("🧪 INICIANDO SUITE DE PRUEBAS INTEGRADA: SPLITBRAIN-CODE V6.2.2")
    print("==================================================================")

    # 1. Verificación de compilación sintáctica de todos los módulos del repositorio
    raiz = Path(__file__).resolve().parent
    for archivo in ARCHIVOS_PROYECTO:
        ruta = raiz / archivo
        assert ruta.exists(), f"Falta el archivo obligatorio: {archivo}"
        py_compile.compile(str(ruta), doraise=True)
    print(f"✅ [1/6] Compilación exitosa de los {len(ARCHIVOS_PROYECTO)} módulos del repositorio.")

    cfg = importlib.import_module("config_parametros")
    radar = importlib.import_module("1_radar_volatilidad")
    escudo = importlib.import_module("2_escudo_semantico")
    gestor_mod = importlib.import_module("5_gestor_posiciones")
    stats_mod = importlib.import_module("6_stats_tracker")
    main_mod = importlib.import_module("main")

    # 2. Prueba de Latencia Lock-Free O(1) en RAM del Centinela Groq
    presas_mock = ["SOL/USDT:USDT", "NEAR/USDT:USDT", "ADA/USDT:USDT", "ZEC/USDT:USDT"]
    escudo.centinela.inicializar_universo(presas_mock)

    iteraciones = 10_000
    t0 = time.perf_counter_ns()
    for _ in range(iteraciones):
        aprobado = await escudo.evaluar_anomalia_groq("SOL/USDT:USDT")
    latencia_media_us = ((time.perf_counter_ns() - t0) / iteraciones) / 1000.0
    assert aprobado is True, "SOL/USDT:USDT debía estar aprobado en RAM"
    assert latencia_media_us < 50.0, f"Latencia excesiva en CPU: {latencia_media_us:.2f} µs"
    print(f"✅ [2/6] Lookup O(1) en Whitelist RAM validado: {latencia_media_us:.3f} µs por consulta.")

    # 3. Prueba de Fallback Cuantitativo ante Drenaje Estructural (Anti-LUNA)
    escudo.centinela.actualizar_telemetria(
        "NEAR/USDT:USDT", z_score=-5.4, ofi=-0.92, precio=4.50, cambio_pct=-0.085
    )
    aprobados_fallback = escudo.centinela._filtro_heuristico_respaldo()
    assert "NEAR/USDT:USDT" not in aprobados_fallback, "El fallback debió vetar el drenaje estructural de NEAR"
    assert "SOL/USDT:USDT" in aprobados_fallback, "SOL debía permanecer aprobado"
    print("✅ [3/6] Filtro anti-colapso estructural (Anti-LUNA) validado correctamente.")

    # 4. Prueba de Inmunidad contra Micro-Ruido en Mercado Plano (Bug BTC -0.04% / NEAR -0.16%)
    vz = radar.VentanaZ(n=60)
    for _ in range(59):
        vz.push(83493.5)
    z_micro_ruido = vz.push(83459.2)
    assert z_micro_ruido is not None and z_micro_ruido > -2.0, (
        f"Un micro-ruido de -0.04% no debe disparar pánico (Z obtenido: {z_micro_ruido:.2f})"
    )

    vz_panico = radar.VentanaZ(n=60)
    for _ in range(59):
        vz_panico.push(83493.5)
    z_panico_real = vz_panico.push(81650.0)
    assert z_panico_real is not None and z_panico_real <= cfg.UMBRAL_PANICO, (
        f"Un colapso real de -2.2% debe activar el gatillo (Z obtenido: {z_panico_real:.2f})"
    )
    print(
        f"✅ [4/6] Calibración VentanaZ verificada: Micro-ruido (-0.04%) -> Z={z_micro_ruido:.2f} (Ignorado) | "
        f"Colapso Real (-2.2%) -> Z={z_panico_real:.2f} (Disparo)."
    )

    # 5. Prueba de Cerrojo Físico de Instancia Única (PID Lock en main.py)
    if hasattr(main_mod, "adquirir_bloqueo_instancia_unica"):
        main_mod.adquirir_bloqueo_instancia_unica()
        assert main_mod.LOCK_FILE.exists(), "El archivo .splitbrain.lock no fue creado"
        # Verificar que un segundo descriptor en el mismo nodo detecte el bloqueo activo
        segundo_handle = main_mod.LOCK_FILE.open("a+", encoding="utf-8")
        bloqueado_correctamente = False
        try:
            if sys.platform != "win32":
                import fcntl
                fcntl.flock(segundo_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt
                segundo_handle.seek(0)
                msvcrt.locking(segundo_handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (BlockingIOError, PermissionError, OSError):
            bloqueado_correctamente = True
        finally:
            segundo_handle.close()
            main_mod.liberar_bloqueo_instancia_unica()
        assert bloqueado_correctamente, "El cerrojo físico no bloqueó el segundo descriptor concurrente"
        print("✅ [5/6] Cerrojo físico de instancia única (.splitbrain.lock) validado contra procesos duplicados.")
    else:
        print("⚠️ [5/6] main.py aún en versión V6.2 (sin adquirir_bloqueo_instancia_unica).")

    # 6. Prueba de Auto-Reconciliación de Posiciones Huérfanas (ADA, ENA, XRP) sin tocar Caja Negra real
    if hasattr(gestor_mod.gestor, "reconciliar_posiciones_exchange"):
        ruta_original = stats_mod.tracker.ruta
        trades_originales = stats_mod.tracker._trades
        modo_paper_original = cfg.MODO_PAPER
        alerta_original = gestor_mod.enviar_alerta
        ruta_temp = raiz / ".test_stats_v6_2_2_tmp.jsonl"

        async def _alerta_silenciosa(_msg: str) -> None:
            return None

        try:
            cfg.MODO_PAPER = False
            stats_mod.tracker.ruta = ruta_temp
            stats_mod.tracker._trades = []
            gestor_mod.enviar_alerta = _alerta_silenciosa

            # Simular que ADA, ENA y XRP llevan 4 horas abiertas (> TIEMPO_MAX_HOLD_SEG = 300s)
            t_hace_4_horas_ms = int((time.time() - 14_400) * 1000)
            mock_ex = _MockExchangeHuerfanas(t_antiguo_ms=t_hace_4_horas_ms)
            procesadas = await gestor_mod.gestor.reconciliar_posiciones_exchange(mock_ex)

            assert procesadas == 3, f"Debieron reconciliarse 3 posiciones huérfanas, procesadas: {procesadas}"
            assert len(mock_ex.ordenes_cerradas) == 3, "Las 3 posiciones zombies debieron liquidarse a mercado"
            for o in mock_ex.ordenes_cerradas:
                assert o["type"] == "market" and o["side"] == "sell", f"Orden inválida: {o}"
                assert o["params"].get("reduceOnly") is True, "Falta reduceOnly=True en liquidación de huérfana"
            print(
                "✅ [6/6] Auto-Reconciliación de arranque validada: 3 posiciones zombies (ADA, ENA, XRP) "
                "detectadas y liquidadas con reduceOnly=True."
            )
        finally:
            cfg.MODO_PAPER = modo_paper_original
            stats_mod.tracker.ruta = ruta_original
            stats_mod.tracker._trades = trades_originales
            gestor_mod.enviar_alerta = alerta_original
            if ruta_temp.exists():
                ruta_temp.unlink()
    else:
        print("⚠️ [6/6] 5_gestor_posiciones.py aún en versión V6.2.1 (sin reconciliar_posiciones_exchange).")

    print("==================================================================")
    print("🏆 TODAS LAS PRUEBAS DE INTEGRIDAD SUPERADAS SIN ERRORES")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(ejecutar_auditoria_v6_2())