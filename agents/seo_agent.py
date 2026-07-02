"""
agents/seo_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Combina dos responsabilidades del prompt original (Trend Agent + SEO
Agent) porque comparten la misma fuente de verdad: la memoria de qué
ya se hizo. Sin acceso a la API de Analytics de TikTok (de pago), la
señal de "qué funciona" que SÍ podemos tener gratis es:
  1. Qué hashtags se repiten más en nuestras propias publicaciones
     pasadas → agents/memory_agent.hashtags_top()
  2. Qué tipo de video (review/top5/tutorial...) NO se usó recientemente
     → evita monotonía, cumple el requisito de "alternar formatos"

Responsabilidades:
  - elegir_tipo_video(): rota el formato del video evitando repetir
    los últimos usados.
  - completar_datos_producto(): cuando el producto viene del Amazon
    Agent (que solo tiene datos objetivos: nombre/precio/rating), usa
    el LLM para redactar beneficio_clave / problema_que_resuelve /
    características, ANCLADO a datos reales (nombre, rating, precio)
    para minimizar alucinación.
  - optimizar_hashtags(): mezcla los hashtags que generó el Script
    Agent con los históricamente más usados de nuestra cuenta.
"""

import random
from agents import memory_agent
from core.llm_router import generar_json
from config import TIPOS_DE_VIDEO

HASHTAGS_NICHO_FIJOS = ["#domotica", "#smarthome", "#gadgets", "#tecnologia"]
HASHTAGS_ALCANCE_FIJOS = ["#parati", "#viral", "#tiktokme"]

PROMPT_COMPLETAR = """Eres un copywriter de e-commerce para TikTok en español
latino, especializado en domótica y gadgets para el hogar.

Con estos datos REALES y VERIFICADOS de Amazon (no los inventes ni los
cambies, son objetivos):
- Nombre: {nombre}
- Categoría: {categoria}
- Precio: ${precio_usd}
- Rating: {rating} estrellas ({num_resenas} reseñas)

Escribe copy de marketing para este producto. Responde SOLO JSON:
{{
  "beneficio_clave": "una frase corta y atractiva del beneficio principal",
  "problema_que_resuelve": "problema cotidiano concreto que soluciona",
  "por_que_es_buena_compra": "razón breve, mencionando el rating/reseñas reales",
  "caracteristicas": [
    "característica plausible 1 (basada en el tipo de producto)",
    "característica plausible 2",
    "característica plausible 3",
    "característica plausible 4"
  ]
}}
IMPORTANTE: las características deben ser típicas y razonables para ESE
tipo de producto, sin inventar números de certificaciones o specs que no
puedas saber con certeza (evita cifras hiper-específicas no verificables,
preferí beneficios funcionales: "controlá desde el celular", "compatible
con Alexa y Google Home", etc.)"""


def elegir_tipo_video() -> str:
    """Elige un tipo de video evitando repetir los últimos usados."""
    recientes = set(memory_agent.ultimos_tipos_video(n=4))
    candidatos = [t for t in TIPOS_DE_VIDEO if t not in recientes]
    if not candidatos:
        candidatos = TIPOS_DE_VIDEO
    return random.choice(candidatos)


def completar_datos_producto(producto: dict) -> dict:
    """
    Si el producto viene del Amazon Agent y le faltan campos narrativos
    (porque Amazon no te da "beneficio_clave" en el HTML), los completa
    con el LLM anclado a los datos objetivos ya verificados.
    Si el producto ya viene completo (ej: del Research Agent con
    Gemini), no hace nada.
    """
    if producto.get("beneficio_clave") and producto.get("caracteristicas"):
        return producto

    user_msg = PROMPT_COMPLETAR.format(
        nombre=producto.get("nombre", ""),
        categoria=producto.get("categoria", ""),
        precio_usd=producto.get("precio_usd", ""),
        rating=producto.get("rating", "N/D"),
        num_resenas=producto.get("num_resenas", "N/D"),
    )
    datos = generar_json("Eres un copywriter experto.", user_msg, temperature=0.6)
    producto.update({k: v for k, v in datos.items() if not producto.get(k)})
    return producto


def optimizar_hashtags(hashtags_del_guion: list, cantidad_final: int = 7) -> list:
    """
    Mezcla los hashtags que sugirió el Script Agent con los que
    históricamente más se repitieron en nuestras publicaciones (nuestra
    única señal gratuita de "qué funciona" sin Analytics de TikTok),
    más un piso fijo de nicho/alcance para no depender 100% del LLM.
    """
    historicos = memory_agent.hashtags_top(n=6)
    pool = list(dict.fromkeys(
        HASHTAGS_NICHO_FIJOS + historicos + hashtags_del_guion + HASHTAGS_ALCANCE_FIJOS
    ))
    return pool[:cantidad_final]


def generar_descripcion_final(producto: dict, guion: dict, tipo_video: str) -> dict:
    """
    Ensambla el paquete SEO final: caption, hashtags optimizados y CTA,
    listo para el Publishing Agent (telegram_approval.py hoy;
    publishing API de TikTok más adelante).
    """
    hashtags = optimizar_hashtags(guion.get("hashtags", []))
    url_amazon = producto.get("url_amazon", "")
    descripcion = (
        f"{guion.get('caption', '')}\n\n"
        f"{' '.join(hashtags)}"
        + (f"\n\n🔗 {url_amazon}" if url_amazon else "")
    )
    return {
        "tipo_video": tipo_video,
        "caption": guion.get("caption", ""),
        "hashtags": hashtags,
        "descripcion_final": descripcion,
    }


if __name__ == "__main__":
    memory_agent.init_db()
    print("Tipo de video sugerido hoy:", elegir_tipo_video())
    print("Hashtags históricos top:", memory_agent.hashtags_top())
