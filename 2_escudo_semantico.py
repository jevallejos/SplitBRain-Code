"""Escudo Semántico y Cuantitativo en Background (O(1) RAM Lookup + Rotación Multi-Modelo Groq).
Optimizado para el catálogo real de Groq del usuario:
1. openai/gpt-oss-20b  (8K TPM / 200K TPD / 1K RPD)
2. qwen/qwen3.8-27b    (8K TPM / 200K TPD / 1K RPD)
3. openai/gpt-oss-120b (8K TPM / 200K TPD / 1K RPD)
4. allam-2-7b          (6K TPM / 500K TPD / 7K RPD)
"""
import asyncio
import json
import re
import time
from typing import Dict, List, Set

from groq import AsyncGroq
import config_parametros as cfg

cliente_groq = AsyncGroq(api_key=cfg.GROQ_API_KEY) if cfg.GROQ_API_KEY else None

_RE_THINK = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


def _extraer_json_robusto(contenido: str) -> dict:
    """Extrae el diccionario JSON incluso si el modelo (ej. qwen/qwen3.8-27b o allam-2-7b)
    incluye etiquetas de razonamiento <think>...</think> o bloques Markdown ```json ... ```.
    """
    if not contenido:
        return {}
    limpio = _RE_THINK.sub("", contenido).strip()
    try:
        return json.loads(limpio)
    except Exception:
        pass
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        try:
            return json.loads(limpio[inicio : fin + 1])
        except Exception:
            return {}
    return {}


class CentinelaSemanticoRAM:
    """Mantiene en memoria RAM la Whitelist de activos operables.
    - La ruta crítica de trading consulta `esta_aprobado(symbol)` en O(1) (< 0.001 ms, CERO red).
    - Un demonio asíncrono audita la telemetría cada GROQ_CICLO_SEG (180s) fuera de la ruta crítica
      y rota automáticamente entre los 4 modelos generativos habilitados en la cuenta Groq.
    """

    def __init__(self) -> None:
        self.whitelist_activa: Set[str] = set()
        self.telemetria_pares: Dict[str, Dict[str, float]] = {}
        self.ultimo_update_ts: float = 0.0
        self.universo_base: List[str] = []
        self._modelo_idx: int = 0

    def inicializar_universo(self, presas: List[str]) -> None:
        """Habilita inicialmente las presas seleccionadas para no bloquear el arranque en frío."""
        self.universo_base = list(presas)
        self.whitelist_activa = set(presas)
        ahora = time.time()
        for sym in presas:
            self.telemetria_pares.setdefault(
                sym,
                {"z_score": 0.0, "ofi": 0.0, "precio": 0.0, "cambio_pct": 0.0, "ts": ahora},
            )
        self.ultimo_update_ts = ahora
        print(f"[ESCUDO RAM] Whitelist O(1) inicializada con {len(self.whitelist_activa)} pares activos.")

    def actualizar_telemetria(
        self, symbol: str, z_score: float, ofi: float, precio: float, cambio_pct: float = 0.0
    ) -> None:
        """Actualiza en RAM (< 1 microsegundo) el estado microestructural del par observado por el Radar."""
        self.telemetria_pares[symbol] = {
            "z_score": round(float(z_score), 3),
            "ofi": round(float(ofi), 3),
            "precio": float(precio),
            "cambio_pct": round(float(cambio_pct), 4),
            "ts": time.time(),
        }

    def esta_aprobado(self, symbol: str) -> bool:
        """Lookup O(1) en memoria RAM para la ruta crítica de disparo (0.000 ms de latencia de red)."""
        if symbol in cfg.PROHIBIDAS or symbol in cfg.BLACKLIST_PAIRS:
            return False
        if not self.whitelist_activa:
            return True
        return symbol in self.whitelist_activa

    def _filtro_heuristico_respaldo(self) -> Set[str]:
        """Filtro cuantitativo determinista si Groq no está configurado o agota cuota en los 4 modelos:
        veta activos con drenaje continuo sin absorción (caída >= 6% en ventana y OFI <= -0.75).
        """
        aprobados: Set[str] = set()
        for sym in self.universo_base:
            if sym in cfg.PROHIBIDAS or sym in cfg.BLACKLIST_PAIRS:
                continue
            datos = self.telemetria_pares.get(sym) or {}
            cambio = float(datos.get("cambio_pct") or 0.0)
            ofi = float(datos.get("ofi") or 0.0)
            if cambio <= -0.06 and ofi <= -0.75:
                print(
                    f"[ESCUDO RAM] Fallback cuantitativo vetó a {sym} "
                    f"(caída {cambio:.1%}, OFI {ofi:+.2f})"
                )
                continue
            aprobados.add(sym)
        return aprobados if aprobados else set(self.universo_base)

    def _lista_modelos(self) -> List[str]:
        pool = list(cfg.GROQ_MODEL_POOL)
        if cfg.GROQ_MODEL and cfg.GROQ_MODEL not in pool:
            pool.insert(0, cfg.GROQ_MODEL)
        return pool

    async def _llamar_modelo_groq(self, modelo: str, prompt_sistema: str, resumen_json: str) -> str:
        """Invoca a Groq intentando primero JSON mode nativo; si el modelo (ej. allam-2-7b o qwen3.8-27b)
        no soporta `response_format`, reintenta en el acto en modo texto puro.
        """
        mensajes = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Telemetría actual: {resumen_json}"},
        ]
        try:
            respuesta = await asyncio.wait_for(
                cliente_groq.chat.completions.create(
                    messages=mensajes,
                    model=modelo,
                    temperature=0.0,
                    max_tokens=320,
                    response_format={"type": "json_object"},
                ),
                timeout=cfg.GROQ_TIMEOUT_SEG,
            )
            return respuesta.choices[0].message.content or "{}"
        except Exception as e_json:
            err_str = str(e_json).lower()
            if "response_format" in err_str or "json_validate_failed" in err_str or "400" in err_str:
                respuesta = await asyncio.wait_for(
                    cliente_groq.chat.completions.create(
                        messages=mensajes,
                        model=modelo,
                        temperature=0.0,
                        max_tokens=320,
                    ),
                    timeout=cfg.GROQ_TIMEOUT_SEG,
                )
                return respuesta.choices[0].message.content or "{}"
            raise

    async def auditar_universo_una_vez(self) -> Set[str]:
        """Ejecuta una auditoría de lotes en background rotando modelos ante 429/404/503."""
        if not self.universo_base:
            return self.whitelist_activa

        if cliente_groq is None:
            self.whitelist_activa = self._filtro_heuristico_respaldo()
            self.ultimo_update_ts = time.time()
            return self.whitelist_activa

        resumen_lote = {
            sym: {
                "z": self.telemetria_pares.get(sym, {}).get("z_score", 0.0),
                "ofi": self.telemetria_pares.get(sym, {}).get("ofi", 0.0),
                "ret": self.telemetria_pares.get(sym, {}).get("cambio_pct", 0.0),
            }
            for sym in self.universo_base
        }

        prompt_sistema = (
            "Eres un Gestor de Riesgo Cuantitativo HFT en Bybit. "
            "Recibirás un JSON con métricas en tiempo real (z: Z-score, ofi: Order Flow Imbalance, ret: retorno reciente) "
            "de perpetuos cripto. Identifica únicamente activos que sufran colapso estructural sin absorción "
            "(ret <= -0.06 y ofi <= -0.75 simultáneamente). "
            'Responde ÚNICAMENTE con un objeto JSON válido con la clave "vetados" (lista de símbolos a bloquear). '
            'Ejemplo exacto: {"vetados": []}'
        )
        resumen_str = json.dumps(resumen_lote, separators=(",", ":"))

        modelos = self._lista_modelos()
        total_modelos = len(modelos)

        for intento in range(total_modelos):
            idx = (self._modelo_idx + intento) % total_modelos
            modelo_actual = modelos[idx]
            try:
                t0 = time.perf_counter()
                contenido = await self._llamar_modelo_groq(modelo_actual, prompt_sistema, resumen_str)
                latencia_ms = (time.perf_counter() - t0) * 1000.0
                datos = _extraer_json_robusto(contenido)
                vetados_raw = datos.get("vetados") or []
                vetados = {str(s) for s in vetados_raw if isinstance(s, str)}

                nuevos_aprobados = {
                    sym for sym in self.universo_base
                    if sym not in vetados and sym not in cfg.PROHIBIDAS and sym not in cfg.BLACKLIST_PAIRS
                }
                self.whitelist_activa = nuevos_aprobados if nuevos_aprobados else self._filtro_heuristico_respaldo()
                self.ultimo_update_ts = time.time()
                self._modelo_idx = idx
                print(
                    f"[ESCUDO RAM] Whitelist actualizada vía Groq LPU ({modelo_actual}) en {latencia_ms:.0f}ms "
                    f"(fuera de ruta crítica): {len(self.whitelist_activa)}/{len(self.universo_base)} aprobados."
                )
                return self.whitelist_activa
            except Exception as e:
                texto_err = str(e)
                texto_low = texto_err.lower()
                if any(k in texto_low for k in ("429", "rate_limit", "404", "not_found", "decommissioned", "503")):
                    sig_idx = (idx + 1) % total_modelos
                    print(
                        f"[ESCUDO RAM] Cuota/No-Disponible en `{modelo_actual}`. "
                        f"Rotando automáticamente al modelo `{modelos[sig_idx]}`..."
                    )
                    continue
                print(
                    f"[ESCUDO RAM] Aviso Groq background ({type(e).__name__}: {e}). "
                    f"Whitelist mantenida por heurística cuantitativa ({len(self.whitelist_activa)} activos)."
                )
                break

        self.whitelist_activa = self._filtro_heuristico_respaldo()
        self.ultimo_update_ts = time.time()
        return self.whitelist_activa

    async def bucle_centinela_background(self, intervalo_seg: float = cfg.GROQ_CICLO_SEG) -> None:
        """Demonio infinito en segundo plano. Jamás interrumpe al motor de ejecución."""
        await asyncio.sleep(15.0)
        while True:
            try:
                await self.auditar_universo_una_vez()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ESCUDO RAM] Error inesperado en bucle centinela: {type(e).__name__}: {e}")
            await asyncio.sleep(intervalo_seg)


centinela = CentinelaSemanticoRAM()


async def evaluar_anomalia_groq(symbol: str, contexto_mercado: str = "") -> bool:
    """Interfaz O(1) en RAM (< 0.001 ms).
    Elimina por completo el bloqueo HTTP de 510-792ms de la ruta crítica de disparo.
    """
    return centinela.esta_aprobado(symbol)