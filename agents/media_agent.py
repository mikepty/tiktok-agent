"""
agents/media_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Busca y descarga VIDEO REAL (B-roll) libre de derechos para usar en
las escenas, en vez de depender solo de imágenes estáticas con Ken
Burns. Este es el agente que convierte el video de "slideshow narrado"
a "cinematográfico".

Fuentes gratuitas (con API key gratis, sin tarjeta de crédito):
  - Pexels   → https://www.pexels.com/api/          (PEXELS_API_KEY)
  - Pixabay  → https://pixabay.com/api/docs/         (PIXABAY_API_KEY)

Estrategia por escena:
  1. Buscar clips reales con keywords relevantes a la escena/categoría.
  2. Preferir clips orientación vertical o que se puedan recortar a 9:16.
  3. Descargar el de mejor resolución disponible dentro de un límite
     razonable de tamaño.
  4. Si no hay AL MENOS `MIN_CLIPS_REALES` clips utilizables para todo
     el video, el orquestador debe rellenar el resto con el Imagegen
     Agent (image_fetcher.py) — nunca se decide eso acá, este agente
     solo devuelve lo que consiguió (puede ser lista vacía).

No usa researchers de LLM: es HTTP puro + requests, sin dependencias
pesadas. Requiere: pip install requests
"""

import os
import requests
from config import (
    OUTPUT_DIR, PEXELS_API_KEY, PIXABAY_API_KEY,
    VIDEO_WIDTH, VIDEO_HEIGHT, CLIP_DURACION_MAX,
)

TIMEOUT = 15


def _buscar_pexels(query: str, cantidad: int) -> list:
    """Devuelve lista de URLs de video candidatas desde Pexels."""
    if not PEXELS_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={
                "query": query, "per_page": cantidad,
                "orientation": "portrait", "size": "medium",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        candidatos = []
        for video in resp.json().get("videos", []):
            archivos = video.get("video_files", [])
            # preferimos el archivo vertical de menor tamaño razonable
            archivos_ok = [
                f for f in archivos
                if f.get("width") and f.get("height")
                and f["height"] >= f["width"]  # vertical u orientación 9:16
            ] or archivos
            if not archivos_ok:
                continue
            mejor = sorted(archivos_ok, key=lambda f: f.get("width", 0))[0]
            candidatos.append(mejor["link"])
        return candidatos
    except Exception:
        return []


def _buscar_pixabay(query: str, cantidad: int) -> list:
    """Devuelve lista de URLs de video candidatas desde Pixabay."""
    if not PIXABAY_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": PIXABAY_API_KEY, "q": query,
                "per_page": max(cantidad, 3),
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        candidatos = []
        for hit in resp.json().get("hits", []):
            videos = hit.get("videos", {})
            # "small" suele ser suficiente para recorte vertical y pesa poco
            variante = videos.get("small") or videos.get("medium") or videos.get("tiny")
            if variante and variante.get("url"):
                candidatos.append(variante["url"])
        return candidatos
    except Exception:
        return []


def _descargar(url: str, ruta_destino: str) -> bool:
    try:
        resp = requests.get(url, timeout=30, stream=True)
        if resp.status_code != 200:
            return False
        with open(ruta_destino, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        return os.path.getsize(ruta_destino) > 10_000  # descarta archivos vacíos/rotos
    except Exception:
        return False


def _recortar_vertical(ruta_video: str, duracion_max: float = CLIP_DURACION_MAX) -> bool:
    """
    Recorta el clip a `duracion_max` segundos y lo fuerza a 1080x1920
    (crop-and-scale) para que encaje en el timeline de TikTok sin
    deformarse. Sobrescribe el archivo original.
    """
    import subprocess
    tmp = ruta_video + ".tmp.mp4"
    filtro = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
    )
    cmd = [
        "ffmpeg", "-y", "-i", ruta_video, "-t", str(duracion_max),
        "-vf", filtro, "-an", "-r", "25", "-pix_fmt", "yuv420p", tmp,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        os.replace(tmp, ruta_video)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def buscar_clips_para_escena(keywords: str, indice_unico: str, cantidad: int = 2) -> list:
    """
    Punto de entrada principal. Busca y descarga clips reales de B-roll
    para una escena, ya recortados a formato vertical TikTok.

    keywords: términos de búsqueda en INGLÉS (Pexels/Pixabay indexan
              mejor en inglés; traducir categorías smart-home antes
              de llamar, ej: "smart plug home" en vez de "enchufe
              inteligente hogar").
    indice_unico: sufijo para nombrar los archivos sin colisionar
                  (ej: "3_2" = producto 3, escena 2).

    Devuelve lista de rutas locales .mp4 listas para usar en el
    Video Agent. Lista vacía si no encontró nada (el llamador debe
    tener un fallback a imagegen).
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    candidatos = _buscar_pexels(keywords, cantidad)
    candidatos += _buscar_pixabay(keywords, cantidad)

    rutas_ok = []
    for i, url in enumerate(candidatos):
        if len(rutas_ok) >= cantidad:
            break
        ruta = f"{OUTPUT_DIR}/broll_{indice_unico}_{i}.mp4"
        if _descargar(url, ruta) and _recortar_vertical(ruta):
            rutas_ok.append(ruta)
        elif os.path.exists(ruta):
            os.remove(ruta)  # descarga corrupta, no la dejamos huérfana

    return rutas_ok


# Diccionario de traducción rápida categoría→keywords en inglés, para no
# depender de un LLM solo para esto (barato y determinístico).
TRADUCCION_KEYWORDS = {
    "enchufe": "smart plug home automation",
    "camara": "home security camera",
    "cerradura": "smart door lock",
    "bombilla": "smart led bulb home",
    "termostato": "smart thermostat wall",
    "sensor": "motion sensor smart home",
    "aspiradora": "robot vacuum cleaner home",
    "hub": "smart home hub device",
    "webcam": "webcam video call desk",
    "teclado": "wireless keyboard desk setup",
    "cargador": "phone charger cable desk",
    "reloj": "smartwatch wearable hand",
    "bascula": "smart scale bathroom",
    "purificador": "air purifier living room",
    "proyector": "portable projector living room",
    "altavoz": "smart speaker home",
    "freidora": "air fryer kitchen",
    "impresora": "3d printer desk",
    "dron": "drone flying camera",
    "default": "smart home technology gadget",
}


def keywords_desde_categoria(categoria: str) -> str:
    """Convierte una categoría en español a keywords de búsqueda en inglés."""
    cat = (categoria or "").lower()
    for clave, valor in TRADUCCION_KEYWORDS.items():
        if clave in cat:
            return valor
    return TRADUCCION_KEYWORDS["default"]


if __name__ == "__main__":
    if not PEXELS_API_KEY and not PIXABAY_API_KEY:
        print("Configura PEXELS_API_KEY y/o PIXABAY_API_KEY en tu .env para probar.")
    else:
        clips = buscar_clips_para_escena("smart home automation", "test_0", cantidad=2)
        print(f"Clips descargados: {clips}")
