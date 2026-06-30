"""
script_generator.py
Genera el guion viral de TikTok para cada producto.
Usa el nuevo SDK google-genai (mismo que product_researcher.py).
Motor de IA: Gemini Flash (gratis) o Claude (de pago) — ver config.LLM_PROVIDER
"""

import json
import re
from config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEM_PROMPT = """Eres un guionista experto en contenido viral de TikTok para
una tienda propia de productos de domótica, gadgets y tecnología para el hogar
en español latinoamericano.

Reglas de viralidad que SIEMPRE aplicas:
- Hook de los primeros 1-2 segundos: pregunta intrigante, dato sorprendente,
  o "pattern interrupt". NUNCA empieces con el nombre del producto.
- Estructura: Hook → Problema que el espectador siente → Producto como solución
  → Beneficio concreto → CTA claro.
- Frases cortas, ritmo rápido, lenguaje hablado natural (no de vendedor).
- El guion debe poder narrarse en 20-35 segundos.
- Caption: gancho diferente al hook, cierra invitando a comentar o al link en bio.
- 5-8 hashtags: mezcla de nicho + alcance (#domotica #casainteligente #parati).

Responde SOLO con JSON, sin texto adicional ni backticks:
{
  "hook": "...",
  "guion_completo": "...",
  "cta": "...",
  "caption": "...",
  "hashtags": ["#...", "#..."]
}
"""

USER_TEMPLATE = """Producto: {nombre}
Categoria: {categoria}
Precio: ${precio_usd}
Beneficio clave: {beneficio_clave}
Problema que resuelve: {problema_que_resuelve}
Por qué es buena compra ahora: {por_que_es_buena_compra}

Genera el guion viral."""


def _limpiar_json(texto: str) -> dict:
    texto = re.sub(r'```json|```', '', texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # Intentar extraer el objeto JSON del texto
        match = re.search(r'\{[\s\S]*\}', texto)
        if match:
            return json.loads(match.group())
        raise RuntimeError(f"Respuesta no es JSON válido:\n{texto[:500]}")


def _con_gemini(user_msg: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
        ),
    )
    return _limpiar_json(response.text)


def _con_claude(user_msg: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _limpiar_json(response.content[0].text)


def generar_guion(producto: dict) -> dict:
    user_msg = USER_TEMPLATE.format(
        nombre=producto.get("nombre", ""),
        categoria=producto.get("categoria", ""),
        precio_usd=producto.get("precio_usd", ""),
        beneficio_clave=producto.get("beneficio_clave", "a definir"),
        problema_que_resuelve=producto.get("problema_que_resuelve", "a definir"),
        por_que_es_buena_compra=producto.get("por_que_es_buena_compra", ""),
    )
    if LLM_PROVIDER == "gemini":
        return _con_gemini(user_msg)
    elif LLM_PROVIDER == "claude":
        return _con_claude(user_msg)
    else:
        raise ValueError(f"LLM_PROVIDER desconocido: {LLM_PROVIDER}")
