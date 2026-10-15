"""Diagnóstico Concurrente de Permisos, Latencia LPU y Cuotas HTTP en Groq Cloud.
Evalúa en paralelo (< 5 segundos) los 4 modelos configurados en GROQ_MODEL_POOL:
1. openai/gpt-oss-20b
2. openai/gpt-oss-120b
3. allam-2-7b
4. qwen/qwen3.8-27b

Soporta resolución híbrida sync/async de `raw_resp.parse()` en todas las versiones
del SDK `groq` (Python 3.12 Windows y Python 3.14 Linux).
"""
import asyncio
import importlib
import inspect
import json
import sys
import time
from typing import Any, Dict, List

from groq import AsyncGroq
import config_parametros as cfg

_escudo = importlib.import_module("2_escudo_semantico")
_extraer_json_robusto = _escudo._extraer_json_robusto

PROMPT_SISTEMA_TEST = (
    "Eres un Gestor de Riesgo Cuantitativo HFT en Bybit. "
    "Recibirás un JSON con métricas en tiempo real (z, ofi, ret) de perpetuos cripto. "
    "Identifica únicamente activos que sufran colapso estructural sin absorción "
    "(ret <= -0.06 y ofi <= -0.75 simultáneamente). "
    'Responde ÚNICAMENTE con un objeto JSON válido con la clave "vetados". '
    'Ejemplo exacto: {"vetados": []}'
)

PAYLOAD_PRUEBA = json.dumps(
    {
        "ZEREBRO/USDT:USDT": {"z": -2.45, "ofi": 0.31, "ret": -0.008},
        "STRK/USDT:USDT": {"z": -1.80, "ofi": 0.19, "ret": -0.004},
        "NEAR/USDT:USDT": {"z": -6.90, "ofi": -0.88, "ret": -0.082},
    },
    separators=(",", ":"),
)


def _extraer_codigo_error(exc: Exception) -> Dict[str, str]:
    """Clasifica con precisión la excepción devuelta por el SDK de Groq."""
    texto = str(exc)
    texto_low = texto.lower()
    status_code = getattr(exc, "status_code", None)

    if status_code == 403 or "403" in texto_low or "permission" in texto_low or "blocked" in texto_low:
        if "model_permission_blocked_org" in texto_low:
            return {
                "estado": "403 BLOCKED (ORG)",
                "accion": "Habilitar en https://console.groq.com/settings/limits (Nivel Organización)",
            }
        return {
            "estado": "403 BLOCKED (PROJECT)",
            "accion": "Habilitar en https://console.groq.com/settings/project/limits (Nivel Proyecto)",
        }

    if status_code == 429 or "429" in texto_low or "rate_limit" in texto_low:
        if "tokens per day" in texto_low or "tpd" in texto_low:
            return {
                "estado": "429 QUOTA TPD AGOTADA",
                "accion": "Cuota diaria (TPD) agotada; reinicia a las 00:00 UTC",
            }
        if "requests per day" in texto_low or "rpd" in texto_low:
            return {
                "estado": "429 QUOTA RPD AGOTADA",
                "accion": "Peticiones diarias (RPD) agotadas; reinicia a las 00:00 UTC",
            }
        return {
            "estado": "429 RATE LIMIT (TPM/RPM)",
            "accion": "Ventana de 60s saturada; operativo tras enfriamiento de 1 min",
        }

    if status_code == 404 or "404" in texto_low or "model_not_found" in texto_low:
        return {
            "estado": "404 NOT FOUND",
            "accion": "Modelo retirado o inexistente en el catálogo actual",
        }

    return {
        "estado": f"ERR ({type(exc).__name__})",
        "accion": texto[:90],
    }


async def _parsear_respuesta_raw(raw_resp: Any) -> Any:
    """Resuelve `raw_resp.parse()` tanto si es corrutina (AsyncAPIResponse) como si es método síncrono."""
    resultado_parse = raw_resp.parse()
    if inspect.isawaitable(resultado_parse):
        return await resultado_parse
    return resultado_parse


async def _diagnosticar_modelo_individual(
    cliente: AsyncGroq, modelo: str
) -> Dict[str, Any]:
    """Ejecuta una sonda real contra un modelo específico midiendo RTT, cabeceras y JSON."""
    mensajes = [
        {"role": "system", "content": PROMPT_SISTEMA_TEST},
        {"role": "user", "content": f"Telemetría actual: {PAYLOAD_PRUEBA}"},
    ]
    t0 = time.perf_counter()
    modo_json = "JSON_OBJECT"

    try:
        try:
            raw_resp = await asyncio.wait_for(
                cliente.chat.completions.with_raw_response.create(
                    messages=mensajes,
                    model=modelo,
                    temperature=0.0,
                    max_tokens=160,
                    response_format={"type": "json_object"},
                ),
                timeout=6.0,
            )
        except Exception as e_first:
            err_s = str(e_first).lower()
            if (
                "response_format" in err_s
                or "json_validate_failed" in err_s
                or ("400" in err_s and "permission" not in err_s and "blocked" not in err_s)
            ):
                modo_json = "RAW_TEXT_FALLBACK"
                raw_resp = await asyncio.wait_for(
                    cliente.chat.completions.with_raw_response.create(
                        messages=mensajes,
                        model=modelo,
                        temperature=0.0,
                        max_tokens=160,
                    ),
                    timeout=6.0,
                )
            else:
                raise

        latencia_ms = (time.perf_counter() - t0) * 1000.0
        headers = raw_resp.headers
        completion = await _parsear_respuesta_raw(raw_resp)
        contenido = completion.choices[0].message.content or "{}"
        parsed = _extraer_json_robusto(contenido)
        vetados = parsed.get("vetados", None)
        json_ok = isinstance(vetados, list)

        rpd_rem = headers.get("x-ratelimit-remaining-requests", "N/A")
        rpd_lim = headers.get("x-ratelimit-limit-requests", "N/A")
        tpm_rem = headers.get("x-ratelimit-remaining-tokens", "N/A")
        tpm_lim = headers.get("x-ratelimit-limit-tokens", "N/A")

        return {
            "modelo": modelo,
            "operativo": True,
            "estado": "200 OK",
            "latencia_ms": round(latencia_ms, 1),
            "modo": modo_json,
            "json_valido": json_ok,
            "vetados_detectados": vetados if json_ok else [],
            "rpd_info": f"{rpd_rem}/{rpd_lim}",
            "tpm_info": f"{tpm_rem}/{tpm_lim}",
            "accion": "Listo para producción en Sniper-Tokio",
        }
    except Exception as exc:
        latencia_ms = (time.perf_counter() - t0) * 1000.0
        info_err = _extraer_codigo_error(exc)
        return {
            "modelo": modelo,
            "operativo": False,
            "estado": info_err["estado"],
            "latencia_ms": round(latencia_ms, 1),
            "modo": "-",
            "json_valido": False,
            "vetados_detectados": [],
            "rpd_info": "-",
            "tpm_info": "-",
            "accion": info_err["accion"],
        }


async def ejecutar_diagnostico_concurrente() -> int:
    """Lanza la auditoría paralela de los 4 modelos y genera el reporte ejecutivo."""
    print("=" * 108)
    print("🔬 DIAGNÓSTICO DE PERMISOS, LATENCIA Y CUOTAS GROQ LPU — SPLITBRAIN V6.4.0")
    print("=" * 108)

    if not cfg.GROQ_API_KEY:
        print("❌ ERROR: GROQ_API_KEY vacía en el entorno (.env). Configúrala antes de ejecutar.")
        return 1

    modelos: List[str] = list(cfg.GROQ_MODEL_POOL)
    cliente = AsyncGroq(api_key=cfg.GROQ_API_KEY)

    t_global = time.perf_counter()
    resultados = await asyncio.gather(
        *(_diagnosticar_modelo_individual(cliente, m) for m in modelos)
    )
    duracion_total = (time.perf_counter() - t_global) * 1000.0
    await cliente.close()

    cabecera = (
        f"{'MODELO':<24} | {'ESTADO HTTP':<23} | {'RTT (ms)':<9} | "
        f"{'MODO JSON':<17} | {'RPD (Rest/Tot)':<14} | {'TPM (Rest/Tot)':<14}"
    )
    print(cabecera)
    print("-" * 108)

    operativos: List[Dict[str, Any]] = []
    bloqueados: List[Dict[str, Any]] = []

    for r in resultados:
        icono = "✅" if r["operativo"] else ("🚫" if "403" in r["estado"] else "⚠️")
        print(
            f"{icono} {r['modelo']:<21} | {r['estado']:<23} | {r['latencia_ms']:>7.1f}ms | "
            f"{r['modo']:<17} | {r['rpd_info']:<14} | {r['tpm_info']:<14}"
        )
        if r["operativo"]:
            operativos.append(r)
        else:
            bloqueados.append(r)

    print("=" * 108)
    print(f"⏱️  Tiempo total de barrido paralelo: {duracion_total:.0f} ms | Modelos 200 OK: {len(operativos)}/{len(modelos)}")

    if operativos:
        ordenados = sorted(operativos, key=lambda x: x["latencia_ms"])
        recomendados = [x["modelo"] for x in ordenados] + [x["modelo"] for x in bloqueados]
        print("\n🏆 ORDEN ÓPTIMO POR LATENCIA DESDE ESTE NODO:")
        print(f"   GROQ_MODEL = \"{ordenados[0]['modelo']}\"")
        print(f"   GROQ_MODEL_POOL = {tuple(recomendados)}")

    if bloqueados:
        print("\n🔧 ACCIONES REQUERIDAS EN CONSOLA GROQ O CUOTAS:")
        for b in bloqueados:
            print(f"   • {b['modelo']}: {b['estado']} -> {b['accion']}")

    print("=" * 108)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(ejecutar_diagnostico_concurrente()))