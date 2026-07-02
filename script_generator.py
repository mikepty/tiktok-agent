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
from core.llm_router import generar_json

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


# Instrucciones cortas por tipo de video (el SEO/Trend Agent rota entre
# estos formatos para no repetir siempre "review genérico").
INSTRUCCION_POR_TIPO = {
    "review": "Formato: reseña directa del producto.",
    "top5": "Formato: enmarca el producto como parte de un 'ranking' aunque "
            "solo desarrolles este, ej. 'de los 5 gadgets que probé, este ganó'.",
    "comparativa": "Formato: compara implícitamente contra la forma 'tradicional' "
                   "de resolver el problema, sin nombrar marcas de la competencia.",
    "tutorial": "Formato: tono instructivo, 'así lo configuras/usas paso a paso'.",
    "como_funciona": "Formato: explica el mecanismo/tecnología detrás del producto "
                     "de forma simple y curiosa.",
    "errores_comunes": "Formato: 'el error que cometías antes de tener esto'.",
    "vale_la_pena": "Formato: honesto, tipo '¿vale la pena o es hype?', con veredicto.",
    "antes_y_despues": "Formato: contraste explícito de la vida sin vs. con el producto.",
    "configuracion": "Formato: enfocado en lo fácil/rápido que es de instalar/configurar.",
    "hack_smart_home": "Formato: 'smart home hack' — un truco de automatización del hogar "
                       "que este producto habilita.",
    "lo_compraria_o_no": "Formato: veredicto de compra en primera persona, con pros y contras.",
}


def generar_guion(producto: dict, tipo_video: str = "review") -> dict:
    caracteristicas = producto.get("caracteristicas", []) or []
    # Aseguramos 4 características aunque vengan menos del researcher
    while len(caracteristicas) < 4:
        caracteristicas.append(producto.get("beneficio_clave", "Excelente relación calidad-precio"))

    instruccion_formato = INSTRUCCION_POR_TIPO.get(tipo_video, INSTRUCCION_POR_TIPO["review"])

    user_msg = USER_TEMPLATE.format(
        nombre=producto.get("nombre", ""),
        categoria=producto.get("categoria", ""),
        precio_usd=producto.get("precio_usd", ""),
        beneficio_clave=producto.get("beneficio_clave", "a definir"),
        problema_que_resuelve=producto.get("problema_que_resuelve", "a definir"),
        por_que_es_buena_compra=producto.get("por_que_es_buena_compra", ""),
        c1=caracteristicas[0], c2=caracteristicas[1],
        c3=caracteristicas[2], c4=caracteristicas[3],
    ) + f"\n\n{instruccion_formato}"

    guion = generar_json(SYSTEM_PROMPT, user_msg, temperature=0.8)
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
