"""
agents/amazon_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Investiga productos REALES en Amazon con Playwright (no le pide a un
LLM que "adivine" ASINs — que era lo que hacía product_researcher.py).

Qué hace:
  1. Busca la query en Amazon (dominio configurable).
  2. Extrae de los resultados: nombre, precio, rating, cantidad de
     reseñas, ASIN, URL y URL de imagen.
  3. Filtra por rating/reseñas mínimas (config.AMAZON_RATING_MINIMO,
     AMAZON_RESENAS_MINIMO).
  4. Elige el de MEJOR relación calidad/precio con un score simple:
         score = rating * log10(reseñas + 1) / precio
     (no el más caro, no el más barato: castiga precio, premia
     confianza social real).
  5. Cachea resultados por 24h en la misma DB de memory_agent para no
     golpear Amazon en cada corrida del workflow ni arriesgarse a
     bloqueos por exceso de requests.

IMPORTANTE — riesgo operativo:
  Amazon activamente bloquea scraping (captchas, IP bans, cambios de
  HTML frecuentes). Este agente está pensado para ser el "camino feliz"
  y SIEMPRE debe tener un fallback: si Playwright falla o Amazon
  devuelve un captcha, el orquestador debe caer automáticamente a
  product_researcher.py (Gemini + Google Search grounding), que es más
  lento pero no depende de la estructura HTML de Amazon ni corre riesgo
  de bloqueo de IP. Ver core/orchestrator.py.

Requiere: pip install playwright && playwright install chromium
(en CI: agregar el step de instalación de browsers al workflow).
"""

import re
import json
import math
import sqlite3
import datetime
import os

from config import (
    AMAZON_DOMINIO, AMAZON_CACHE_HORAS, AMAZON_RATING_MINIMO,
    AMAZON_RESENAS_MINIMO, AMAZON_TIMEOUT_MS, STATE_DIR, MEMORY_DB,
)

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS amazon_cache (
    query TEXT PRIMARY KEY,
    resultado_json TEXT NOT NULL,
    fecha TEXT NOT NULL
);
"""


def _init_cache():
    os.makedirs(STATE_DIR, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    conn.executescript(CACHE_SCHEMA)
    conn.commit()
    conn.close()


def _cache_get(query: str):
    _init_cache()
    conn = sqlite3.connect(MEMORY_DB)
    row = conn.execute(
        "SELECT resultado_json, fecha FROM amazon_cache WHERE query = ?", (query,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    resultado_json, fecha = row
    edad = datetime.datetime.now() - datetime.datetime.fromisoformat(fecha)
    if edad.total_seconds() > AMAZON_CACHE_HORAS * 3600:
        return None
    return json.loads(resultado_json)


def _cache_set(query: str, resultado: list):
    _init_cache()
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        "INSERT INTO amazon_cache (query, resultado_json, fecha) VALUES (?, ?, ?) "
        "ON CONFLICT(query) DO UPDATE SET resultado_json = excluded.resultado_json, "
        "fecha = excluded.fecha",
        (query, json.dumps(resultado, ensure_ascii=False), datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def _parsear_precio(texto: str):
    if not texto:
        return None
    m = re.search(r"[\d.,]+", texto.replace(",", ""))
    return float(m.group()) if m else None


def _parsear_rating(texto: str):
    if not texto:
        return None
    m = re.search(r"([\d.]+)", texto)
    return float(m.group(1)) if m else None


def _parsear_resenas(texto: str):
    if not texto:
        return 0
    texto = texto.replace(",", "").replace(".", "")
    m = re.search(r"(\d+)", texto)
    return int(m.group(1)) if m else 0


def _scrapear_amazon(query: str, max_resultados: int = 8) -> list:
    """Scraping real con Playwright. Lanza excepción si algo falla
    (bloqueo, timeout, cambio de estructura) — el llamador debe
    capturarla y caer al Research Agent basado en Gemini."""
    from playwright.sync_api import sync_playwright

    resultados = []
    url = f"https://www.{AMAZON_DOMINIO}/s?k={query.replace(' ', '+')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pagina = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1800},
        )
        pagina.goto(url, timeout=AMAZON_TIMEOUT_MS)
        pagina.wait_for_selector('div[data-component-type="s-search-result"]',
                                  timeout=AMAZON_TIMEOUT_MS)

        tarjetas = pagina.query_selector_all('div[data-component-type="s-search-result"]')
        for tarjeta in tarjetas[:max_resultados]:
            try:
                asin = tarjeta.get_attribute("data-asin") or ""
                nombre_el = tarjeta.query_selector("h2 span")
                nombre = nombre_el.inner_text().strip() if nombre_el else ""

                enlace_el = tarjeta.query_selector("h2 a")
                href = enlace_el.get_attribute("href") if enlace_el else ""
                url_producto = f"https://www.{AMAZON_DOMINIO}{href}" if href else ""

                precio_el = tarjeta.query_selector("span.a-price > span.a-offscreen")
                precio = _parsear_precio(precio_el.inner_text() if precio_el else "")

                rating_el = tarjeta.query_selector("span.a-icon-alt")
                rating = _parsear_rating(rating_el.inner_text() if rating_el else "")

                resenas_el = tarjeta.query_selector(
                    'span[aria-label][class*="a-size-base"]'
                )
                resenas = _parsear_resenas(resenas_el.inner_text() if resenas_el else "")

                img_el = tarjeta.query_selector("img.s-image")
                url_imagen = img_el.get_attribute("src") if img_el else ""

                if not (nombre and asin and precio):
                    continue

                resultados.append({
                    "nombre": nombre,
                    "asin": asin,
                    "precio_usd": precio,
                    "rating": rating or 0,
                    "num_resenas": resenas,
                    "url_amazon": url_producto,
                    "url_imagen": url_imagen,
                })
            except Exception:
                continue

        browser.close()

    return resultados


def _mejor_relacion_calidad_precio(candidatos: list) -> list:
    """
    Filtra por mínimos de calidad y ordena por score de valor real
    (no el más caro, no el más barato):
        score = rating * log10(reseñas + 1) / precio
    """
    filtrados = [
        c for c in candidatos
        if c.get("rating", 0) >= AMAZON_RATING_MINIMO
        and c.get("num_resenas", 0) >= AMAZON_RESENAS_MINIMO
        and c.get("precio_usd")
    ]
    if not filtrados:
        # si el filtro estricto deja la lista vacía, relajamos reseñas
        # mínimas antes de rendirnos (mejor un producto ok que ninguno)
        filtrados = [c for c in candidatos if c.get("rating", 0) >= AMAZON_RATING_MINIMO
                     and c.get("precio_usd")]

    for c in filtrados:
        c["score_valor"] = (
            c["rating"] * math.log10(c["num_resenas"] + 1) / max(c["precio_usd"], 1)
        )

    return sorted(filtrados, key=lambda c: c["score_valor"], reverse=True)


def investigar_categoria_amazon(query_en_ingles: str, categoria: str,
                                 productos_deseados: int = 2) -> list:
    """
    Punto de entrada principal. Busca en Amazon, filtra y elige los
    productos con mejor relación calidad/precio para la categoría dada.
    Usa caché de 24h para no golpear Amazon en cada corrida.

    query_en_ingles: término de búsqueda (Amazon.com funciona mejor
                      en inglés aunque el guion final sea en español).
    Devuelve lista de dicts en el MISMO formato que product_researcher.py
    espera (nombre, categoria, precio_usd, asin, url_amazon, url_imagen)
    para que el resto del pipeline (script_generator, etc.) no necesite
    cambios.
    """
    cacheado = _cache_get(query_en_ingles)
    if cacheado is not None:
        print(f"    [Amazon Agent] Cache hit para '{query_en_ingles}'")
        candidatos = cacheado
    else:
        candidatos = _scrapear_amazon(query_en_ingles)
        _cache_set(query_en_ingles, candidatos)

    mejores = _mejor_relacion_calidad_precio(candidatos)[:productos_deseados]

    productos = []
    for m in mejores:
        productos.append({
            "nombre": m["nombre"],
            "categoria": categoria,
            "precio_usd": str(m["precio_usd"]),
            "asin": m["asin"],
            "url_amazon": m["url_amazon"],
            "url_imagen": m["url_imagen"],
            "rating": m.get("rating"),
            "num_resenas": m.get("num_resenas"),
            # Estos tres campos NO los tiene Amazon directamente; el
            # Script Agent los completa con el LLM a partir del nombre
            # y categoría reales ya verificados (evita inventar ASINs,
            # solo se "inventa" copy narrativo, que es su trabajo).
            "beneficio_clave": "",
            "problema_que_resuelve": "",
            "por_que_es_buena_compra": (
                f"{m.get('rating', '')}★ con {m.get('num_resenas', 0)} reseñas reales en Amazon"
            ),
            "caracteristicas": [],
        })
    return productos


if __name__ == "__main__":
    try:
        productos = investigar_categoria_amazon("smart plug wifi", "enchufes inteligentes")
        print(json.dumps(productos, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Amazon Agent falló (esperable sin Playwright instalado): {e}")
