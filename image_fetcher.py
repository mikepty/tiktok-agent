"""
image_fetcher.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Obtiene la imagen del producto para usarla en el video.
Estrategia con 2 intentos antes de generar una imagen propia:

  1. Descargar la URL de imagen que devolvió Gemini (rápido y gratis)
  2. Si falla: generar una tarjeta de producto profesional con Pillow
     (gradiente + nombre del producto + precio) — siempre funciona,
     sin depender de ninguna URL externa.

Requiere: pip install pillow requests
"""

import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT

# Paletas de color por categoría (para que las tarjetas varíen visualmente)
PALETAS = {
    "seguridad": [(15, 52, 96), (21, 101, 192)],
    "iluminacion": [(40, 0, 80), (103, 58, 183)],
    "energia": [(0, 60, 30), (56, 142, 60)],
    "productividad": [(10, 20, 60), (25, 118, 210)],
    "salud": [(60, 0, 40), (194, 24, 91)],
    "cocina": [(50, 20, 0), (230, 81, 0)],
    "entretenimiento": [(30, 0, 50), (123, 31, 162)],
    "herramientas": [(30, 30, 30), (97, 97, 97)],
    "mascotas": [(0, 50, 30), (67, 160, 71)],
    "default": [(10, 15, 40), (21, 67, 155)],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}


def _paleta_para_categoria(categoria: str) -> list:
    cat = categoria.lower()
    for clave, colores in PALETAS.items():
        if clave in cat:
            return colores
    return PALETAS["default"]


def _descargar_imagen(url: str, ruta_destino: str) -> bool:
    """Intenta descargar una imagen de cualquier URL. Retorna True si OK."""
    if not url:
        return False
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", ""):
            with open(ruta_destino, "wb") as f:
                f.write(resp.content)
            # Verificar que Pillow puede abrirla (no es HTML de error)
            img = Image.open(ruta_destino)
            img.verify()
            return True
    except Exception:
        pass
    return False


def _generar_tarjeta(nombre: str, precio: str, categoria: str,
                      ruta_destino: str) -> str:
    """
    Genera una imagen de producto estilo 'product card' con gradiente,
    texto del producto y precio. Se usa cuando no hay imagen disponible.
    Siempre funciona. Calidad visual decente para TikTok.
    """
    W, H = VIDEO_WIDTH, VIDEO_HEIGHT
    colores = _paleta_para_categoria(categoria)
    color_inicio = colores[0]
    color_fin = colores[1]

    # Gradiente diagonal
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        ratio = y / H
        r = int(color_inicio[0] + (color_fin[0] - color_inicio[0]) * ratio)
        g = int(color_inicio[1] + (color_fin[1] - color_inicio[1]) * ratio)
        b = int(color_inicio[2] + (color_fin[2] - color_inicio[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Overlay de formas geométricas decorativas
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([W // 2, -100, W + 300, 600], fill=(*color_fin, 30))
    od.ellipse([-200, H - 400, 500, H + 200], fill=(*color_inicio, 20))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Intentar cargar fuentes del sistema; fallback a la default de Pillow
    def load_font(size):
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_cat = load_font(36)
    font_nombre = load_font(58)
    font_precio = load_font(72)
    font_etiq = load_font(32)

    # Línea decorativa
    draw.rectangle([80, H // 3 - 10, 160, H // 3 + 4], fill=(255, 255, 255, 200))

    # Etiqueta de categoría (pequeña, arriba del nombre)
    cat_upper = categoria.upper()[:30]
    draw.text((80, H // 3 + 30), cat_upper, font=font_cat,
              fill=(200, 220, 255), stroke_width=0)

    # Nombre del producto (con salto de línea automático)
    palabras = nombre.split()
    lineas = []
    linea_actual = ""
    for palabra in palabras:
        prueba = (linea_actual + " " + palabra).strip()
        if len(prueba) <= 28:
            linea_actual = prueba
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)

    y_nombre = H // 3 + 100
    for linea in lineas[:4]:  # máximo 4 líneas
        draw.text((80, y_nombre), linea, font=font_nombre, fill="white",
                  stroke_width=2, stroke_fill=(0, 0, 0, 120))
        y_nombre += 75

    # Badge de precio
    precio_texto = f"${precio}" if not str(precio).startswith("$") else precio
    badge_y = y_nombre + 40
    badge_w, badge_h = 300, 90
    badge_x = 80
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=20, fill=(255, 255, 255, 240)
    )
    draw.text((badge_x + 20, badge_y + 15), precio_texto,
              font=font_precio, fill=(*color_inicio,))

    # Footer
    footer_y = H - 120
    draw.rectangle([0, footer_y, W, H], fill=(*color_inicio, 200))
    draw.text((80, footer_y + 30), "Disponible en Amazon",
              font=font_etiq, fill=(180, 200, 255))

    # Guardar
    img.save(ruta_destino, "JPEG", quality=90)
    return ruta_destino


def generar_tarjeta_escena(texto_pantalla: str, tipo_escena: str, nombre_producto: str,
                            categoria: str, precio: str, indice_escena: int,
                            ruta_destino: str) -> str:
    """
    Genera la imagen de fondo para UNA escena del video, mostrando el
    texto destacado de esa escena (texto_pantalla) en grande, con un
    diseño que varía levemente según el tipo de escena (hook/problema/
    caracteristica/cta) para dar variedad visual entre escenas.
    """
    W, H = VIDEO_WIDTH, VIDEO_HEIGHT
    colores = _paleta_para_categoria(categoria)
    color_inicio, color_fin = colores

    # Variar la dirección del gradiente y el acento según el índice de
    # escena, para que consecutivas no se vean idénticas.
    invertir = indice_escena % 2 == 1
    c1, c2 = (color_fin, color_inicio) if invertir else (color_inicio, color_fin)

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        ratio = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if indice_escena % 3 == 0:
        od.ellipse([W // 2, -150, W + 400, 500], fill=(*c2, 35))
    elif indice_escena % 3 == 1:
        od.ellipse([-250, H - 500, 450, H + 250], fill=(*c1, 30))
    else:
        od.ellipse([-150, -150, 450, 450], fill=(*c2, 25))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    def load_font(size, bold=True):
        candidatos = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        for path in candidatos:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    # Etiqueta pequeña según tipo de escena (da contexto narrativo)
    ETIQUETAS = {
        "hook": "👀 ATENCIÓN",
        "problema": "¿TE PASA ESTO?",
        "caracteristica": nombre_producto.upper()[:34],
        "cta": "NO TE LO PIERDAS",
    }
    etiqueta = ETIQUETAS.get(tipo_escena, categoria.upper()[:30])

    font_etiq = load_font(34)
    font_titular = load_font(80)

    draw.rectangle([80, H // 2 - 220, 160, H // 2 - 206], fill=(255, 255, 255))
    draw.text((80, H // 2 - 170), etiqueta, font=font_etiq, fill=(210, 225, 255))

    # Texto principal de la escena (texto_pantalla), centrado vertical,
    # ajustado a varias líneas si hace falta
    palabras = texto_pantalla.upper().split()
    lineas, linea_actual = [], ""
    for palabra in palabras:
        prueba = (linea_actual + " " + palabra).strip()
        if len(prueba) <= 16:
            linea_actual = prueba
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)

    y_texto = H // 2 - 90
    for linea in lineas[:3]:
        draw.text((80, y_texto), linea, font=font_titular, fill="white",
                  stroke_width=4, stroke_fill=(0, 0, 0, 160))
        y_texto += 95

    # Badge de precio solo en escenas de característica (refuerza recall)
    if tipo_escena in ("caracteristica", "cta") and precio:
        precio_texto = f"${precio}" if not str(precio).startswith("$") else precio
        font_precio = load_font(44)
        bw, bh = 220, 70
        bx, by = W - bw - 60, H - bh - 220
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=18,
                                fill=(255, 255, 255, 235))
        draw.text((bx + 25, by + 12), precio_texto, font=font_precio, fill=(*c1,))

    img.save(ruta_destino, "JPEG", quality=90)
    return ruta_destino


def obtener_imagen_producto(url_imagen: str, nombre: str, precio: str,
                             categoria: str, indice: int) -> str:
    """
    Obtiene la imagen del producto para el video.
    Retorna la ruta del archivo local listo para usar.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ruta = f"{OUTPUT_DIR}/img_{indice}.jpg"

    print(f"    -> Intentando descargar imagen del producto...")
    if _descargar_imagen(url_imagen, ruta):
        print(f"    ✅ Imagen descargada.")
        # Redimensionar a formato vertical si es necesario
        try:
            img = Image.open(ruta).convert("RGB")
            # Si es imagen cuadrada o horizontal (de Amazon), enmarcarla en fondo
            iw, ih = img.size
            if ih < iw * 1.2:  # no es ya vertical
                fondo = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT),
                                   (10, 15, 40))
                img.thumbnail((VIDEO_WIDTH, VIDEO_HEIGHT // 2))
                x = (VIDEO_WIDTH - img.width) // 2
                y = (VIDEO_HEIGHT - img.height) // 2
                fondo.paste(img, (x, y))
                img = fondo
            else:
                img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
            img.save(ruta, "JPEG", quality=90)
        except Exception:
            pass  # si falla el resize, usamos la imagen tal cual
        return ruta

    print(f"    ⚠️  No se pudo descargar. Generando tarjeta de producto...")
    _generar_tarjeta(nombre, precio, categoria, ruta)
    print(f"    ✅ Tarjeta generada.")
    return ruta


if __name__ == "__main__":
    # Prueba: genera una tarjeta sin necesitar internet
    ruta = _generar_tarjeta(
        nombre="Enchufe Inteligente TP-Link Tapo P115",
        precio="14.99",
        categoria="enchufes inteligentes",
        ruta_destino="output/tarjeta_prueba.jpg",
    )
    print(f"Tarjeta generada en: {ruta}")
