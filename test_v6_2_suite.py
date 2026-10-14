"""Suite de Verificación Integrada para SplitBRain-Code V6.2."""
import asyncio
import importlib
import py_compile
import time
from pathlib import Path

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


async def ejecutar_auditoria_v6_2() -> None:
    print("==================================================================")
    print("🧪 INICIANDO SUITE DE PRUEBAS INTEGRADA: SPLITBRAIN-CODE V6.2")
    print("==================================================================")

    # 1. Verificación de compilación sintáctica de todos los módulos del repositorio
    raiz = Path(__file__).resolve().parent
    for archivo in ARCHIVOS_PROYECTO:
        ruta = raiz / archivo
        assert ruta.exists(), f"Falta el archivo obligatorio: {archivo}"
        py_compile.compile(str(ruta), doraise=True)
    print(f"✅ [1/4] Compilación exitosa de los {len(ARCHIVOS_PROYECTO)} módulos del repositorio.")

    cfg = importlib.import_module("config_parametros")
    radar = importlib.import_module("1_radar_volatilidad")
    escudo = importlib.import_module("2_escudo_semantico")

    # 2. Prueba de Latencia Lock-Free O(1) en RAM del Centinela Groq
    presas_mock = ["SOL/USDT:USDT", "NEAR/USDT:USDT", "ADA/USDT:USDT", "ZEC/USDT:USDT"]
    escudo.centinela.inicializar_universo(presas_mock)

    iteraciones = 10_000
    t0 = time.perf_counter_ns()
    for _ in range(iteraciones):
        aprobado = await escudo.evaluar_anomalia_groq("SOL/USDT:USDT")
    latencia_media_us = ((time.perf_counter_ns() - t0) / iteraciones) / 1000.0
    assert aprobado is True, "SOL/USDT:USDT debía estar aprobado en RAM"
    assert latencia_media_us < 50.0, f"Latencia excesiva: {latencia_media_us:.2f} µs"
    print(f"✅ [2/4] Lookup O(1) en Whitelist RAM validado: {latencia_media_us:.3f} µs por consulta.")

    # 3. Prueba de Fallback Cuantitativo ante Drenaje Estructural (Anti-LUNA)
    escudo.centinela.actualizar_telemetria(
        "NEAR/USDT:USDT", z_score=-5.4, ofi=-0.92, precio=4.50, cambio_pct=-0.085
    )
    aprobados_fallback = escudo.centinela._filtro_heuristico_respaldo()
    assert "NEAR/USDT:USDT" not in aprobados_fallback, "El fallback debió vetar el drenaje estructural de NEAR"
    assert "SOL/USDT:USDT" in aprobados_fallback, "SOL debía permanecer aprobado"
    print("✅ [3/4] Filtro anti-colapso estructural (Anti-LUNA) validado correctamente.")

    # 4. Prueba de Inmunidad contra Micro-Ruido en Mercado Plano (Bug BTC -0.04% / NEAR -0.16%)
    vz = radar.VentanaZ(n=60)
    for _ in range(59):
        vz.push(83493.5)
    # Caída minúscula de -0.04% (83493.5 -> 83459.2) que antes disparaba falsamente el Circuit Breaker
    z_micro_ruido = vz.push(83459.2)
    assert z_micro_ruido is not None and z_micro_ruido > -2.0, (
        f"Un micro-ruido de -0.04% no debe disparar pánico (Z obtenido: {z_micro_ruido:.2f})"
    )

    # Caída genuina de pánico (-2.2% a 81650.0) sí debe superar el umbral
    vz_panico = radar.VentanaZ(n=60)
    for _ in range(59):
        vz_panico.push(83493.5)
    z_panico_real = vz_panico.push(81650.0)
    assert z_panico_real is not None and z_panico_real <= cfg.UMBRAL_PANICO, (
        f"Un colapso real de -2.2% debe activar el gatillo (Z obtenido: {z_panico_real:.2f})"
    )
    print(f"✅ [4/4] Calibración VentanaZ verificada: Micro-ruido (-0.04%) -> Z={z_micro_ruido:.2f} (Ignorado) | "
          f"Colapso Real (-2.2%) -> Z={z_panico_real:.2f} (Disparo).")
    print("==================================================================")
    print("🏆 TODAS LAS PRUEBAS DE INTEGRIDAD V6.2 SUPERADAS SIN ERRORES")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(ejecutar_auditoria_v6_2())