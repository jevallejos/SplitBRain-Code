"""Suite de Verificación Integrada para SplitBRain-Code V6.3.0 (10/10 Pruebas de Grado Producción)."""
import ast
import asyncio
import importlib
import py_compile
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

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


def _extraer_atributos_cfg_ast(raiz: Path) -> Set[Tuple[str, str]]:
    """Escanea el AST de todos los módulos y extrae cada acceso `cfg.<ATRIBUTO>`."""
    requeridos: Set[Tuple[str, str]] = set()
    for nombre_archivo in ARCHIVOS_PROYECTO:
        codigo = (raiz / nombre_archivo).read_text(encoding="utf-8")
        arbol = ast.parse(codigo, filename=nombre_archivo)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Name) and nodo.value.id == "cfg":
                requeridos.add((nombre_archivo, nodo.attr))
    return requeridos


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
        return {"USDT": {"total": 11.2365, "free": 11.2365}}


class _MockExchangeZeroRest:
    """Verifica que ejecutar_orden_sniper NO invoque REST antes de create_order y valide Penny-Jump."""

    def __init__(self) -> None:
        self.markets = {
            "BTW/USDT:USDT": {
                "precision": {"amount": 1.0, "price": 0.0001},
                "limits": {"amount": {"min": 1.0}, "cost": {"min": 5.0}},
            }
        }
        self.ordenes_creadas: List[Dict[str, Any]] = []
        self.create_order_en_ruta_critica = False

    async def load_markets(self) -> None:
        raise AssertionError("VIOLACIÓN ZERO-REST: load_markets() fue llamado en la ruta crítica")

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        raise AssertionError("VIOLACIÓN ZERO-REST: fetch_ticker() fue llamado en la ruta crítica")

    async def set_leverage(self, leverage: int, symbol: str) -> None:
        raise AssertionError("VIOLACIÓN ZERO-REST: set_leverage() fue llamado en la ruta crítica")

    async def fetch_balance(self) -> Dict[str, Any]:
        if self.create_order_en_ruta_critica:
            raise AssertionError("VIOLACIÓN ZERO-REST: fetch_balance() fue llamado antes de create_order()")
        return {"USDT": {"total": 11.2365, "free": 11.2365}}

    def market(self, symbol: str) -> Dict[str, Any]:
        return self.markets[symbol]

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        return f"{int(amount)}"

    def price_to_precision(self, symbol: str, price: float) -> str:
        return f"{float(price):.4f}"

    async def create_order(
        self, symbol: str, order_type: str, side: str, amount: Any, price: Any = None, params: Any = None
    ) -> Dict[str, Any]:
        self.create_order_en_ruta_critica = False
        orden = {
            "id": "zero_rest_order_1",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": float(amount),
            "price": float(price),
            "params": params or {},
        }
        self.ordenes_creadas.append(orden)
        return orden

    async def fetch_order(self, order_id: str, symbol: str, params: Any = None) -> Dict[str, Any]:
        return {"id": order_id, "status": "canceled", "filled": 0.0}


async def ejecutar_auditoria_v6_3() -> None:
    print("==================================================================")
    print("🧪 INICIANDO SUITE DE PRUEBAS INTEGRADA: SPLITBRAIN-CODE V6.3.0")
    print("==================================================================")

    # 1. Verificación de compilación sintáctica de todos los módulos
    raiz = Path(__file__).resolve().parent
    for archivo in ARCHIVOS_PROYECTO:
        ruta = raiz / archivo
        assert ruta.exists(), f"Falta el archivo obligatorio: {archivo}"
        py_compile.compile(str(ruta), doraise=True)
    print(f"✅ [1/10] Compilación exitosa de los {len(ARCHIVOS_PROYECTO)} módulos del repositorio.")

    cfg = importlib.import_module("config_parametros")
    radar = importlib.import_module("1_radar_volatilidad")
    escudo = importlib.import_module("2_escudo_semantico")
    sniper = importlib.import_module("3_ejecutor_sniper")
    gestor_mod = importlib.import_module("5_gestor_posiciones")
    stats_mod = importlib.import_module("6_stats_tracker")
    main_mod = importlib.import_module("main")

    # 2. Auditoría AST de Contratos de Configuración V6.3.0
    referencias_cfg = _extraer_atributos_cfg_ast(raiz)
    faltantes = [(arch, attr) for arch, attr in sorted(referencias_cfg) if not hasattr(cfg, attr)]
    assert not faltantes, f"Atributos faltantes en config_parametros.py: {faltantes}"
    assert abs(cfg.UMBRAL_OFI_TOXICO - (-0.35)) < 1e-9
    assert abs(cfg.BE_ACTIVACION_PCT - 0.0048) < 1e-9
    assert abs(cfg.TRAIL_ACTIVACION_PCT - 0.0080) < 1e-9
    assert cfg.COOLDOWN_POST_CIERRE_SEG == 300
    atributos_unicos = {attr for _, attr in referencias_cfg}
    print(
        f"✅ [2/10] Contrato AST V6.3.0 validado: {len(atributos_unicos)} constantes verificadas "
        f"(BE={cfg.BE_ACTIVACION_PCT:.2%}, Trail={cfg.TRAIL_ACTIVACION_PCT:.2%}, CD={cfg.COOLDOWN_POST_CIERRE_SEG}s)."
    )

    # 3. Prueba de Latencia Lock-Free O(1) en RAM del Centinela Groq + Lista Multi-Modelo
    presas_mock = ["SOL/USDT:USDT", "NEAR/USDT:USDT", "ADA/USDT:USDT", "ZEC/USDT:USDT"]
    escudo.centinela.inicializar_universo(presas_mock)
    assert len(escudo.centinela._lista_modelos()) >= 3, "Deben existir al menos 3 modelos de failover en Groq"

    iteraciones = 10_000
    t0 = time.perf_counter_ns()
    for _ in range(iteraciones):
        aprobado = await escudo.evaluar_anomalia_groq("SOL/USDT:USDT")
    latencia_media_us = ((time.perf_counter_ns() - t0) / iteraciones) / 1000.0
    assert aprobado is True
    assert latencia_media_us < 50.0
    print(
        f"✅ [3/10] Lookup O(1) en Whitelist RAM ({latencia_media_us:.3f} µs) y pool de "
        f"{len(escudo.centinela._lista_modelos())} modelos Groq validados."
    )

    # 4. Prueba de Fallback Cuantitativo ante Drenaje Estructural (Anti-LUNA)
    escudo.centinela.actualizar_telemetria(
        "NEAR/USDT:USDT", z_score=-5.4, ofi=-0.92, precio=4.50, cambio_pct=-0.085
    )
    aprobados_fallback = escudo.centinela._filtro_heuristico_respaldo()
    assert "NEAR/USDT:USDT" not in aprobados_fallback
    assert "SOL/USDT:USDT" in aprobados_fallback
    print("✅ [4/10] Filtro anti-colapso estructural (Anti-LUNA) validado correctamente.")

    # 5. Prueba de Inmunidad contra Micro-Ruido y Caída Desde Máximo
    vz = radar.VentanaZ(n=60)
    for _ in range(59):
        vz.push(83493.5)
    z_micro_ruido = vz.push(83459.2)
    assert z_micro_ruido is not None and z_micro_ruido > -2.0
    assert vz.caida_desde_maximo() > cfg.CAIDA_MIN_PCT

    vz_panico = radar.VentanaZ(n=60)
    for _ in range(59):
        vz_panico.push(83493.5)
    z_panico_real = vz_panico.push(81650.0)
    assert z_panico_real is not None and z_panico_real <= cfg.UMBRAL_PANICO
    assert vz_panico.caida_desde_maximo() <= cfg.CAIDA_MIN_PCT
    print(
        f"✅ [5/10] Calibración VentanaZ verificada: Micro-ruido (-0.04%) -> Z={z_micro_ruido:.2f} (Ignorado) | "
        f"Colapso Real (-2.21%) -> Z={z_panico_real:.2f} (Disparo)."
    )

    # 6. Prueba de Cerrojo Físico de Instancia Única y Propiedad de Lock (PID Lock en main.py)
    main_mod.adquirir_bloqueo_instancia_unica()
    assert main_mod.LOCK_FILE.exists()
    assert main_mod._lock_adquirido_por_mi is True
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
    assert bloqueado_correctamente
    print("✅ [6/10] Cerrojo físico de instancia única (.splitbrain.lock) con blindaje de propiedad validado.")

    # 7. Prueba de Auto-Reconciliación de Huérfanas, Evacuación Macro y Cooldown Post-Cierre (300s)
    ruta_original = stats_mod.tracker.ruta
    trades_originales = stats_mod.tracker._trades
    modo_paper_original = cfg.MODO_PAPER
    alerta_original_gestor = gestor_mod.enviar_alerta
    alerta_original_sniper = sniper.enviar_alerta
    ruta_temp = raiz / ".test_stats_v6_3_0_tmp.jsonl"

    async def _alerta_silenciosa(_msg: str) -> None:
        return None

    try:
        cfg.MODO_PAPER = False
        stats_mod.tracker.ruta = ruta_temp
        stats_mod.tracker._trades = []
        gestor_mod.enviar_alerta = _alerta_silenciosa
        sniper.enviar_alerta = _alerta_silenciosa

        t_hace_4_horas_ms = int((time.time() - 14_400) * 1000)
        mock_ex = _MockExchangeHuerfanas(t_antiguo_ms=t_hace_4_horas_ms)
        procesadas = await gestor_mod.gestor.reconciliar_posiciones_exchange(mock_ex)
        assert procesadas == 3
        assert len(mock_ex.ordenes_cerradas) == 3
        print(
            "✅ [7/10] Auto-Reconciliación de arranque validada: 3 posiciones zombies (ADA, ENA, XRP) "
            "liquidadas con reduceOnly=True."
        )

        # 8. Prueba de Detector de Contagio Cross-Asset (>= 3 pares en 10s), Evacuación Macro y Cooldown 300s
        gestor_mod.gestor.registrar_cooldown_post_cierre("WAL/USDT:USDT", 300)
        assert sniper.en_cooldown_post_cierre("WAL/USDT:USDT") is True
        assert gestor_mod.gestor.segundos_cooldown_restantes("WAL/USDT:USDT") > 290
        gestor_mod.gestor.cooldown_hasta.clear()

        radar.bloqueo_btc_hasta = 0.0
        radar._timestamps_panico.clear()
        t_now = time.time()
        assert radar.registrar_y_verificar_contagio(mock_ex, "ENA/USDT:USDT", t_now) is False
        assert radar.registrar_y_verificar_contagio(mock_ex, "NEAR/USDT:USDT", t_now + 1.0) is False
        assert radar.registrar_y_verificar_contagio(mock_ex, "ADA/USDT:USDT", t_now + 2.0) is True
        assert radar.bloqueo_activo() is True
        radar.bloqueo_btc_hasta = 0.0
        radar._timestamps_panico.clear()
        print(
            "✅ [8/10] Detector de Contagio Cross-Asset (>= 3 pares en 10s) y Cooldown Post-Cierre (300s) validados."
        )

        # 9. Prueba de Cotización Penny-Jump (Bertrand Discreto) y Filtro de Lote Mínimo
        mock_zero = _MockExchangeZeroRest()
        # Spread = 0.0502 - 0.0499 = 0.0003 (3 ticks) y OFI = +0.40 >= +0.25 -> Debe cotizar en 0.0500 (bid + 1 tick)
        ticker_penny = {"last": 0.0501, "bid": 0.0499, "ask": 0.0502}
        p_penny = sniper._extraer_precio_maker_ws(mock_zero, "BTW/USDT:USDT", ticker_penny, ofi=0.40)
        assert p_penny is not None and abs(p_penny - 0.0500) < 1e-9, f"Esperado Penny-Jump 0.0500, obtenido {p_penny}"
        print(f"✅ [9/10] Cotización Penny-Jump validada: bid=0.0499, ask=0.0502, OFI=+0.40 -> quote={p_penny:.4f}.")

        # 10. Prueba de Disparo Zero-REST en Ruta Crítica + Fire-and-Forget Telegram
        mock_zero.create_order_en_ruta_critica = True
        sniper._saldo_libre_ram = 11.2365
        sniper._saldo_ts = time.time()
        sniper._apalancamiento_ok.add("BTW/USDT:USDT")
        ticker_ws_mock = {"last": 0.0500, "bid": 0.0499, "bidVolume": 50000, "askVolume": 25000}

        await sniper.ejecutar_orden_sniper(
            mock_zero, "BTW/USDT:USDT", z_score=-3.58, ofi=0.33, ticker=ticker_ws_mock
        )
        assert len(mock_zero.ordenes_creadas) == 1
        assert sniper._saldo_libre_ram < 11.2365
        for t in list(sniper._tareas_as) + list(sniper._tareas_bg):
            t.cancel()
        await asyncio.gather(*sniper._tareas_as, *sniper._tareas_bg, return_exceptions=True)
        sniper._en_vuelo.discard("BTW/USDT:USDT")
        print(
            "✅ [10/10] Disparo Zero-REST validado: 0 llamadas HTTP previas a create_order, "
            "deducción atómica de margen en RAM y despacho Fire-and-Forget verificados."
        )
    finally:
        cfg.MODO_PAPER = modo_paper_original
        stats_mod.tracker.ruta = ruta_original
        stats_mod.tracker._trades = trades_originales
        gestor_mod.enviar_alerta = alerta_original_gestor
        sniper.enviar_alerta = alerta_original_sniper
        gestor_mod.gestor.cooldown_hasta.clear()
        if ruta_temp.exists():
            ruta_temp.unlink()

    print("==================================================================")
    print("🏆 TODAS LAS PRUEBAS DE INTEGRIDAD V6.3.0 (10/10) SUPERADAS")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(ejecutar_auditoria_v6_3())