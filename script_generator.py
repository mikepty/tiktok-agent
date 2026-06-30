"""
script_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Genera el guion del video DIVIDIDO EN ESCENAS, cada una atada a un
detalle real del producto (no un párrafo plano). Esto le da al video:

  - Sentido temático: cada escena muestra una característica concreta
  - Duración garantizada de 45+ segundos (7 escenas de ~8s narradas)
  - Texto en pantalla específico por escena, distinto del audio,
    para reforzar visualmente lo que se está diciendo

Estructura de escenas:
  1. hook        → pattern interrupt, agarra la atención
  2. problema     → el dolor cotidiano que el espectador reconoce
  3-6. caracteristica × 4 → una por cada característica real del producto
  7. cta          → cierre con llamado a la acción

Motor: Gemini (gratis) o Claude (si LLM_PROVIDER="claude" y hay presupuesto)
"""

import json
import re
from config import LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEM_PROMPT = """Eres un guionista experto en contenido viral de TikTok para
una tienda propia de productos de domótica, gadgets y tecnología para el hogar,
en español latinoamericano.

Tu tarea es escribir un guion DIVIDIDO EN ESCENAS para un video de 45-60
segundos. Cada escena tiene un texto narrado (lo que dice la voz en off) y un
texto en pantalla (corto, tipo titular, que refuerza visualmente esa escena;
NO debe ser idéntico al texto narrado).

ESTRUCTURA OBLIGATORIA (7 escenas exactas, en este orden):
1. "hook" — Pattern interrupt de 1-2 frases. Pregunta intrigante o dato
   sorprendente. NUNCA menciones el nombre del producto todavía.
2. "problema" — Agita un dolor cotidiano real con el que el espectador se
   identifica al instante (sin el producto aún).
3. "caracteristica" — Presenta el producto y narra la PRIMERA característica
   real que te paso, explicada como beneficio concreto para el usuario
   (no como ficha técnica fría).
4. "caracteristica" — Segunda característica real, mismo estilo.
5. "caracteristica" — Tercera característica real, mismo estilo.
6. "caracteristica" — Cuarta característica real, mismo estilo.
7. "cta" — Cierre con urgencia/curiosidad y llamado a la acción claro
   (ej: "link en la descripción", "te dejo el link", "corre por el tuyo").

REGLAS DE CADA texto_narrado:
- Entre 18 y 26 palabras por escena (ritmo natural hablado, ni telegráfico
  ni inflado). Frases cortas, lenguaje hablado de TikTok, cero tecnicismos
  innecesarios.
- Las escenas de "caracteristica" deben sonar a beneficio real para una
  persona común, traduciendo el dato técnico a "por qué te importa".

REGLAS DE CADA texto_pantalla:
- Máximo 6 palabras, tipo titular/bullet, todo en mayúsculas o con
  formato llamativo. Refuerza visualmente la escena sin repetir el audio
  literal.

Además genera:
- "caption": gancho de TikTok (distinto al hook), cierra invitando a
  comentar o ver el link en bio. Máximo 2 líneas.
- "hashtags": 5 a 8 hashtags, mezcla de nicho (#domotica #gadgets
  #casainteligente) y de alcance (#parati #viral #tiktokme).

Responde SOLO con JSON válido, sin texto adicional ni backticks:
{
  "escenas": [
    {"tipo": "hook", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "problema", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "caracteristica", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "caracteristica", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "caracteristica", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "caracteristica", "texto_narrado": "...", "texto_pantalla": "..."},
    {"tipo": "cta", "texto_narrado": "...", "texto_pantalla": "..."}
  ],
  "caption": "...",
  "hashtags": ["#...", "#..."]
}
"""

USER_TEMPLATE = """Producto: {nombre}
Categoría: {categoria}
Precio: ${precio_usd}
Beneficio clave: {beneficio_clave}
Problema que resuelve: {problema_que_resuelve}
Por qué es buena compra ahora: {por_que_es_buena_compra}

Características reales para usar UNA POR ESCENA (en este orden):
1. {c1}
2. {c2}
3. {c3}
4. {c4}

Genera el guion por escenas."""


def _limpiar_json(texto: str) -> dict:
    texto = re.sub(r'```json|```', '', texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
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
            temperature=0.8,
        ),
    )
    return _limpiar_json(response.text)


def _con_claude(user_msg: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _limpiar_json(response.content[0].text)


def _validar_y_completar(guion: dict) -> dict:
    """Garantiza que haya al menos 7 escenas; si Gemini devolvió menos,
    repite la última característica para no quedar corto de duración."""
    escenas = guion.get("escenas", [])
    while len(escenas) < 7:
        relleno = escenas[-1].copy() if escenas else {
            "tipo": "caracteristica",
            "texto_narrado": "Y eso no es todo lo que tiene para ofrecerte.",
            "texto_pantalla": "MÁS VENTAJAS",
        }
        escenas.append(relleno)
    guion["escenas"] = escenas
    guion.setdefault("caption", "Esto te va a cambiar el día a día 👀")
    guion.setdefault("hashtags", ["#domotica", "#gadgets", "#parati", "#tecnologia"])
    return guion


def generar_guion(producto: dict) -> dict:
    caracteristicas = producto.get("caracteristicas", []) or []
    # Aseguramos 4 características aunque vengan menos del researcher
    while len(caracteristicas) < 4:
        caracteristicas.append(producto.get("beneficio_clave", "Excelente relación calidad-precio"))

    user_msg = USER_TEMPLATE.format(
        nombre=producto.get("nombre", ""),
        categoria=producto.get("categoria", ""),
        precio_usd=producto.get("precio_usd", ""),
        beneficio_clave=producto.get("beneficio_clave", "a definir"),
        problema_que_resuelve=producto.get("problema_que_resuelve", "a definir"),
        por_que_es_buena_compra=producto.get("por_que_es_buena_compra", ""),
        c1=caracteristicas[0], c2=caracteristicas[1],
        c3=caracteristicas[2], c4=caracteristicas[3],
    )

    if LLM_PROVIDER == "gemini":
        guion = _con_gemini(user_msg)
    elif LLM_PROVIDER == "claude":
        guion = _con_claude(user_msg)
    else:
        raise ValueError(f"LLM_PROVIDER desconocido: {LLM_PROVIDER}")

    return _validar_y_completar(guion)


if __name__ == "__main__":
    producto_prueba = {
        "nombre": "TP-Link Tapo P115 Mini Enchufe Inteligente",
        "categoria": "enchufes inteligentes",
        "precio_usd": "13.99",
        "beneficio_clave": "Controla y mide el consumo eléctrico desde el celular",
        "problema_que_resuelve": "Factura de luz cara sin saber qué aparato gasta más",
        "por_que_es_buena_compra": "Mejor vendido con 4.7 estrellas, compatible con Alexa",
        "caracteristicas": [
            "Mide el consumo en tiempo real con precisión de 0.1 kWh",
            "Tamaño mini que no tapa el otro enchufe de la regleta",
            "Compatible con Alexa, Google Home y la app Tapo",
            "Programa horarios automáticos de encendido y apagado",
        ],
    }
    print(json.dumps(generar_guion(producto_prueba), indent=2, ensure_ascii=False))
