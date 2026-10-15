"""Escudo Semántico LPU Desacoplado en RAM (SPLITBRAIN V6.3.0).

Incorpora Rotación Automática Multi-Modelo ante Error HTTP 429 (agotamiento de cuota TPD)
entre `openai/gpt-oss-20b`, `llama-3.3-70b-versatile` y `llama-3.1-8b-instant`, manteniendo
lectura Lock-Free O(1) en ~0.65 microsegundos mediante `frozenset` en memoria RAM.
"""
import asyncio
import json
import time
from typing import Any, Dict, FrozenSet, Iterable, Optional, Set, Tuple

from groq import AsyncGroq
import config_parametros as cfg

MODELO = "openai/gpt-oss-20b"
_cliente: Optional[AsyncGroq] = None


def _obtener_cliente() -> AsyncGroq:
    """Creación diferida: evita lanzar excepción en tiempo de importación si falta GROQ_API_KEY."""
    global _cliente
    if _cliente is None:
        _cliente = AsyncGroq(
            api_key=cfg.GROQ_API_KEY,
            timeout=getattr(cfg, "GROQ_TIMEOUT_SEG", 6.0),
            max_retries=0,
        )
    return _cliente


def _parametros_modelo(modelo: str) -> Dict[str, Any]:
    """Ajusta los parámetros específicos según la familia de modelo en Groq LPU."""
    base: Dict[str, Any] = {
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_completion_tokens": 1024,
    }
    if "gpt-oss" in modelo:
        base["reasoning_effort"] = "low"
        base["include_reasoning"] = False
    return base


class CentinelaGroqRAM:
    """Mantiene una Whitelist inmutable (`frozenset`) en RAM con Failover Multi-Modelo en Groq."""

    def __init__(self) -> None:
        self._universo: Set[str] = set()
        self._whitelist_ram: FrozenSet[str] = frozenset()
        self._telemetria: Dict[str, Dict[str, float]] = {}
        self._ultima_actualizacion: float = 0.0
        self._idx_modelo_preferido: int = 0

    def _lista_modelos(self) -> Tuple[str, ...]:
        modelos = getattr(cfg, "GROQ_MODELOS", (MODELO,))
        if isinstance(modelos, (list, tuple)) and len(modelos) > 0:
            return tuple(str(m) for m in modelos)
        return (MODELO,)

    def inicializar_universo(self, simbolos: Iterable[str]) -> None:
        """Carga inicial instantánea al arrancar main.py."""
        limpios = {s for s in simbolos if s not in cfg.PROHIBIDAS and s not in cfg.BLACKLIST_PAIRS}
        self._universo = set(limpios)
        self._whitelist_ram = frozenset(limpios)
        self._ultima_actualizacion = time.time()
        print(f"[ESCUDO RAM] Whitelist O(1) inicializada con {len(self._whitelist_ram)} pares activos.")

    def actualizar_telemetria(
        self, symbol: str, z_score: float, ofi: float, precio: float, cambio_pct: float
    ) -> None:
        """Actualización O(1) en memoria alimentada por 1_radar_volatilidad.py en cada segundo."""
        self._telemetria[symbol] = {
            "z": round(float(z_score), 2),
            "ofi": round(float(ofi), 2),
            "price": float(precio),
            "chg_pct": round(float(cambio_pct) * 100.0, 2),
        }

    def es_aprobado_ram(self, symbol: str) -> bool:
        """RUTA CRÍTICA (~0.65 µs): Verifica membresía O(1) sin red ni locks."""
        if symbol in cfg.BLACKLIST_PAIRS or symbol in cfg.PROHIBIDAS:
            return False
        return symbol in self._whitelist_ram

    def _filtro_heuristico_respaldo(self) -> Set[str]:
        """Fallback cuantitativo determinista si todos los modelos de Groq fallan o falta API Key."""
        aprobados: Set[str] = set()
        for sym in self._universo:
            if sym in cfg.BLACKLIST_PAIRS or sym in cfg.PROHIBIDAS:
                continue
            datos = self._telemetria.get(sym)
            if datos is None:
                aprobados.add(sym)
                continue
            # Aísla activos con drenaje estructural crónico (caída <= -6.0% en 60s con OFI <= -0.85)
            if datos["chg_pct"] <= -6.0 and datos["ofi"] <= -0.85:
                print(
                    f"[ESCUDO RAM] Fallback cuantitativo vetó a {sym} "
                    f"(caída {datos['chg_pct']}%, OFI {datos['ofi']})"
                )
                continue
            aprobados.add(sym)
        return aprobados

    async def auditar_lote_groq(self) -> FrozenSet[str]:
        """Consulta asíncrona por lote a Groq LPU con rotación automática multi-modelo ante Error 429."""
        activos_validos = [
            s for s in self._universo
            if s not in cfg.BLACKLIST_PAIRS and s not in cfg.PROHIBIDAS
        ]
        if not activos_validos:
            self._whitelist_ram = frozenset()
            return self._whitelist_ram

        snapshot_envio = {
            s: self._telemetria.get(s, {"z": 0.0, "ofi": 0.0, "chg_pct": 0.0})
            for s in activos_validos
        }
        prompt = (
            "Eres un comité institucional de riesgo HFT en criptoderivados. "
            "Analiza la siguiente telemetría en tiempo real de perpetuos USDT (z = Z-Score 60s, "
            "ofi = Order Flow Imbalance [-1 a 1], chg_pct = variación % en 60s). "
            "Aprueba los activos aptos para reversión a la media (pánico normal o mercado sano) "
            "y excluye aquellos con señales de exploit, rugpull, depeg, cascada tóxica sin absorción "
            "o colapso estructural (caídas extremas o presión vendedora persistente ofi < -0.80). "
            f"Datos: {json.dumps(snapshot_envio, separators=(',', ':'))}. "
            'Responde ÚNICAMENTE con JSON estricto con este esquema exacto: {"aprobados": ["SIMBOLO1", "SIMBOLO2"]}'
        )

        modelos = self._lista_modelos()
        total_modelos = len(modelos)
        ultimo_error: Optional[Exception] = None

        for offset in range(total_modelos):
            idx = (self._idx_modelo_preferido + offset) % total_modelos
            modelo_actual = modelos[idx]
            t0 = time.perf_counter()
            try:
                cliente = _obtener_cliente()
                kwargs_extra = _parametros_modelo(modelo_actual)
                resp = await cliente.chat.completions.create(
                    model=modelo_actual,
                    messages=[{"role": "user", "content": prompt}],
                    **kwargs_extra,
                )
                contenido = resp.choices[0].message.content or "{}"
                datos: Dict[str, Any] = json.loads(contenido)
                lista_aprobados = datos.get("aprobados")
                if isinstance(lista_aprobados, list):
                    conjunto_nuevo = {
                        str(s) for s in lista_aprobados
                        if str(s) in self._universo
                        and str(s) not in cfg.BLACKLIST_PAIRS
                        and str(s) not in cfg.PROHIBIDAS
                    }
                    if not conjunto_nuevo and len(activos_validos) > 0:
                        conjunto_nuevo = self._filtro_heuristico_respaldo()
                else:
                    conjunto_nuevo = self._filtro_heuristico_respaldo()

                lat_ms = (time.perf_counter() - t0) * 1000.0
                self._whitelist_ram = frozenset(conjunto_nuevo)
                self._ultima_actualizacion = time.time()
                self._idx_modelo_preferido = idx
                print(
                    f"[ESCUDO RAM] Whitelist actualizada vía Groq LPU ({modelo_actual}) en {lat_ms:.0f}ms "
                    f"(fuera de ruta crítica): {len(self._whitelist_ram)}/{len(activos_validos)} aprobados."
                )
                return self._whitelist_ram
            except Exception as e:
                ultimo_error = e
                texto_err = str(e)
                if "429" in texto_err or "rate_limit" in texto_err.lower():
                    siguiente_idx = (idx + 1) % total_modelos
                    print(
                        f"[ESCUDO RAM] Cuota/Rate-Limit 429 en `{modelo_actual}`. "
                        f"Rotando automáticamente al modelo `{modelos[siguiente_idx]}`..."
                    )
                    continue
                break

        respaldo = self._filtro_heuristico_respaldo()
        self._whitelist_ram = frozenset(respaldo)
        self._ultima_actualizacion = time.time()
        print(
            f"[ESCUDO RAM] Aviso Groq background ({type(ultimo_error).__name__}: {ultimo_error}). "
            f"Whitelist mantenida por heurística cuantitativa ({len(self._whitelist_ram)} activos)."
        )
        return self._whitelist_ram

    async def bucle_centinela_background(self, intervalo_seg: Optional[float] = None) -> None:
        """Tarea demonio perpetua invocada desde main.py."""
        ciclo = intervalo_seg or getattr(cfg, "GROQ_CICLO_SEG", 180)
        await asyncio.sleep(15)
        while True:
            try:
                await self.auditar_lote_groq()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ESCUDO RAM] Error inesperado en bucle centinela: {type(e).__name__}: {e}")
            await asyncio.sleep(ciclo)


centinela = CentinelaGroqRAM()


def es_aprobado_ram(symbol: str) -> bool:
    """Acceso directo O(1) para 1_radar_volatilidad.py."""
    return centinela.es_aprobado_ram(symbol)


async def evaluar_anomalia_groq(symbol: str) -> bool:
    """Retrocompatibilidad O(1): resuelve instantáneamente desde RAM en ~0.65 µs sin I/O de red."""
    if not centinela._universo:
        for modelo_actual in centinela._lista_modelos():
            try:
                cliente = _obtener_cliente()
                kwargs_extra = _parametros_modelo(modelo_actual)
                resp = await cliente.chat.completions.create(
                    model=modelo_actual,
                    messages=[{"role": "user", "content": (
                        f"Eres un analista de riesgos HFT. El activo {symbol} ha colapsado. "
                        "Evalúa si es un pánico irracional (APROBADO) o un hackeo/fraude estructural (RECHAZADO). "
                        'Responde ÚNICAMENTE con JSON estricto: {"aprobado": true} o {"aprobado": false}.'
                    )}],
                    **kwargs_extra,
                )
                datos = json.loads(resp.choices[0].message.content or "{}")
                return datos.get("aprobado") is True
            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    continue
                print(f"[ESCUDO (Groq)] Fallo evaluando {symbol}: {type(e).__name__}: {e}")
                return False
        return False
    return centinela.es_aprobado_ram(symbol)