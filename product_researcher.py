"""
product_researcher.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Motor de investigación 100% autónoma de productos.
No requiere CSV manual. No requiere API de Amazon.
Costo: $0 (usa el mismo Gemini gratuito del script_generator).

Qué hace:
  1. Rota entre categorías de tecnología/gadgets todos los días
  2. Usa Gemini con Google Search grounding para buscar los productos
     NUEVOS más interesantes que existen en Amazon hoy
  3. Por cada categoría del día, encuentra el modelo con MEJOR
     relación precio/rendimiento (no el más caro ni el más barato)
  4. Devuelve hasta N productos listos para hacer video, con:
     - Nombre, precio, ASIN, categoría
     - Beneficio clave y problema que resuelve
     - URL de imagen del producto para descargar
"""

import json
import re
import datetime
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

# ── Categorías de nichos que rota el agente ─────────────────────────────────
# El índice del día del año módulo len(CATEGORIAS) decide qué categorías
# se investigan hoy. Cada 3-4 semanas vuelve a repetir el ciclo pero
# con búsquedas distintas (distinta fecha = distintos resultados).
CATEGORIAS = [
    # Hogar inteligente
    "enchufes y regletas inteligentes para el hogar",
    "cámaras de seguridad wifi para casa",
    "cerraduras inteligentes para puertas",
    "bombillas y tiras LED inteligentes RGB",
    "termostatos y climatización inteligente",
    "sensores de movimiento y alarmas wifi",
    "robots aspiradores y limpiadores",
    "hubs y bridges para smart home Matter",
    # Gadgets de productividad
    "gadgets para home office y trabajo en casa",
    "monitores portátiles y pantallas extra USB-C",
    "teclados y ratones ergonómicos inalámbricos",
    "webcams y micrófonos para videoconferencias",
    "cargadores rápidos y baterías portátiles",
    "organizadores de cables y adaptadores USB",
    # Salud y bienestar tech
    "pulseras y relojes inteligentes de salud",
    "básculas inteligentes con análisis corporal",
    "purificadores de aire con medidor de calidad",
    "humidificadores y difusores inteligentes",
    # Entretenimiento y estudio
    "proyectores portátiles para el hogar",
    "altavoces inteligentes y barras de sonido",
    "tabletas gráficas para dibujar y diseñar",
    "lámparas de luz para videollamadas y streaming",
    "gadgets retro gaming y emulación portátil",
    # Cocina y electrodomésticos inteligentes
    "freidoras de aire inteligentes con app",
    "básculas y accesorios de cocina conectados",
    "termos y cafeteras inteligentes",
    # Herramientas y exterior
    "destornilladores eléctricos y herramientas compactas",
    "impresoras 3D de escritorio para principiantes",
    "drones y cámaras aéreas portátiles",
    "linternas y gadgets de supervivencia",
    # Mascotas y niños tech
    "gadgets tecnológicos para mascotas",
    "juguetes educativos de robótica para niños",
]

PROMPT_INVESTIGACION = """
Fecha de hoy: {fecha}
Categoría a investigar: {categoria}

Actúa como un experto investigador de productos tecnológicos para un canal
de TikTok sobre gadgets y domótica en español latinoamericano. Tu misión
es encontrar los mejores productos NUEVOS o que están ganando popularidad
AHORA en Amazon para la categoría dada.

Busca en Google productos en la categoría "{categoria}" disponibles en
Amazon. Encuentra {cantidad} productos con la MEJOR relación
precio/rendimiento (no el más caro, no el más barato, el más conveniente
para alguien que quiere empezar o mejorar su hogar/trabajo).

Para cada producto devuelve información REAL y VERIFICADA buscando en
Amazon.com o Amazon.com.mx:
- El nombre exacto del producto como aparece en Amazon
- El precio aproximado en USD (modelo económico y de buen rendimiento)
- El número ASIN de Amazon (ejemplo: B0XXXXXXXXX)
- La URL directa del producto en amazon.com
- Una URL de imagen del producto (la imagen principal de Amazon)
- Categoría específica
- El beneficio clave más atractivo para el usuario promedio
- El problema cotidiano que resuelve (algo con lo que el usuario se
  identifique, no tecnicismos)
- Por qué es el mejor valor del mercado ahora mismo

IMPORTANTE: Elige productos que:
1. Existan REALMENTE en Amazon (no inventes ASINs)
2. Tengan buenas reseñas (mínimo 4.0 estrellas)
3. Sean de marcas conocidas o con muchas reseñas
4. Estén disponibles para compra (no "sold out")
5. Sean novedosos o estén ganando tracción en 2025-2026

Responde SOLO con un array JSON válido, sin texto adicional:
[
  {{
    "nombre": "nombre exacto del producto en Amazon",
    "categoria": "categoría específica",
    "precio_usd": "XX.XX",
    "asin": "B0XXXXXXXXX",
    "url_amazon": "https://www.amazon.com/dp/B0XXXXXXXXX",
    "url_imagen": "URL directa de la imagen del producto",
    "beneficio_clave": "en una frase corta y atractiva",
    "problema_que_resuelve": "problema cotidiano que soluciona",
    "por_que_es_buena_compra": "razón breve de por qué es el mejor valor ahora"
  }}
]
"""


def _categoria_del_dia(cantidad: int = 2) -> list:
    """Selecciona las categorías a investigar hoy según el día del año."""
    dia = datetime.datetime.now().timetuple().tm_yday
    total = len(CATEGORIAS)
    indices = [(dia * cantidad + i) % total for i in range(cantidad)]
    return [CATEGORIAS[i] for i in indices]


def _buscar_productos_categoria(categoria: str, cantidad: int = 2) -> list:
    """
    Usa Gemini con Google Search grounding para investigar productos reales
    en Amazon para la categoría dada.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = PROMPT_INVESTIGACION.format(
        fecha=datetime.datetime.now().strftime("%d de %B de %Y"),
        categoria=categoria,
        cantidad=cantidad,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )

    texto = response.text.strip()

    # Extraer el JSON del texto (Gemini a veces agrega texto alrededor)
    json_match = re.search(r'\[[\s\S]*\]', texto)
    if not json_match:
        raise RuntimeError(f"Gemini no devolvió JSON de array:\n{texto[:500]}")

    productos = json.loads(json_match.group())
    # Inyectar la categoría por si Gemini la omitió
    for p in productos:
        p.setdefault("categoria", categoria)
    return productos


def investigar_productos(categorias_por_dia: int = 2,
                          productos_por_categoria: int = 2) -> list:
    """
    Punto de entrada principal. Investiga productos del día sin necesidad
    de ningún CSV manual.

    categorias_por_dia: cuántas categorías diferentes rotar hoy
    productos_por_categoria: cuántos productos buscar por categoría
    """
    categorias = _categoria_del_dia(categorias_por_dia)
    print(f"[Investigación] Categorías de hoy: {categorias}")

    todos = []
    for cat in categorias:
        print(f"  -> Buscando en: {cat} ...")
        try:
            productos = _buscar_productos_categoria(cat, productos_por_categoria)
            print(f"     Encontrados: {len(productos)} productos")
            todos.extend(productos)
        except Exception as e:
            print(f"  ⚠️  Error en '{cat}': {e}")

    print(f"[Investigación] Total de productos a procesar hoy: {len(todos)}")
    return todos


if __name__ == "__main__":
    # Prueba: investigar sin necesitar API key real (mostrará error esperado)
    import os
    if not os.getenv("GEMINI_API_KEY") and GEMINI_API_KEY.startswith("PON"):
        print("Configura GEMINI_API_KEY en config.py para probar.")
    else:
        productos = investigar_productos()
        print(json.dumps(productos, indent=2, ensure_ascii=False))
