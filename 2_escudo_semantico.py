import json
from groq import AsyncGroq
import config_parametros as cfg

MODELO = "openai/gpt-oss-20b"
_cliente = None


def _obtener_cliente():
    # Creación diferida: si falta GROQ_API_KEY, AsyncGroq lanza excepción.
    # Así ocurre dentro del try y no rompe el import del módulo.
    global _cliente
    if _cliente is None:
        _cliente = AsyncGroq(api_key=cfg.GROQ_API_KEY, timeout=5.0, max_retries=0)
    return _cliente


async def evaluar_anomalia_groq(symbol) -> bool:
    prompt = (
        f"Eres un analista de riesgos HFT. El activo {symbol} ha colapsado. "
        "Evalúa si es un pánico irracional (APROBADO) o un hackeo/fraude estructural (RECHAZADO). "
        'Responde ÚNICAMENTE con JSON estricto: {"aprobado": true} o {"aprobado": false}.'
    )
    try:
        cliente = _obtener_cliente()
        resp = await cliente.chat.completions.create(
            model=MODELO,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            reasoning_effort="low",
            include_reasoning=False,
            temperature=0.2,
            max_completion_tokens=1024,
        )
        datos = json.loads(resp.choices[0].message.content)
        return datos.get("aprobado") is True
    except Exception as e:
        # 429 / 503 / Timeout / JSON inválido / sin API key → RECHAZADO
        print(f"[ESCUDO LPU] Fallo evaluando {symbol}: {type(e).__name__}: {e}")
        return False
