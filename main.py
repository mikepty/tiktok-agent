"""
main.py — Orquestador autónomo del agente de contenido TikTok
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline completo, sin intervención manual, con videos de 45+ segundos
estructurados en escenas con sentido temático (hook → problema →
4 características reales del producto → cta):

  1. Gemini investiga en Google qué productos de tecnología están
     ganando tracción en Amazon HOY, con sus características técnicas
     reales (rota categorías diariamente)
  2. Por cada producto: genera guion de 7 escenas + voz por escena +
     imagen por escena + video final ensamblado
  3. Te lo manda por Telegram para aprobar
  4. Vos subís con un tap a TikTok

Uso:
  python3 main.py                 → produce todos los videos del día
  python3 main.py --limite 1      → solo 1 (para probar)
  python3 main.py --categorias 3  → investiga 3 categorías (más volumen)
"""

import argparse
import os

from product_researcher import investigar_productos
from script_generator import generar_guion
from tts_voice import generar_audio
from video_builder import construir_video_multiescena
from image_fetcher import obtener_imagen_producto, generar_tarjeta_escena
from config import OUTPUT_DIR, APPROVAL_CHANNEL

if APPROVAL_CHANNEL == "telegram":
    from telegram_approval import enviar_para_aprobacion
else:
    from whatsapp_approval import enviar_para_aprobacion


def _preparar_escenas(producto: dict, guion: dict, indice_producto: int) -> list:
    """
    Por cada una de las 7 escenas del guion, genera su imagen y su
    audio narrado. La escena 0 (hook) intenta usar la foto real del
    producto; el resto usa tarjetas de característica generadas con
    el texto específico de esa escena.
    """
    nombre = producto.get("nombre", "")
    precio = str(producto.get("precio_usd", ""))
    categoria = producto.get("categoria", "tecnologia")
    url_imagen = producto.get("url_imagen", "")

    escenas_con_media = []
    for i, escena in enumerate(guion["escenas"]):
        sufijo = f"{indice_producto}_{i}"

        # Imagen: la primera escena intenta foto real; el resto, tarjeta
        # temática con el texto_pantalla de esa escena específica.
        if i == 0:
            ruta_img = obtener_imagen_producto(
                url_imagen, nombre, precio, categoria, f"{sufijo}_hero"
            )
        else:
            ruta_img = f"{OUTPUT_DIR}/img_{sufijo}.jpg"
            generar_tarjeta_escena(
                texto_pantalla=escena["texto_pantalla"],
                tipo_escena=escena["tipo"],
                nombre_producto=nombre,
                categoria=categoria,
                precio=precio,
                indice_escena=i,
                ruta_destino=ruta_img,
            )

        # Audio narrado de esa escena
        ruta_audio = f"{OUTPUT_DIR}/voz_{sufijo}.mp3"
        generar_audio(escena["texto_narrado"], ruta_audio)

        escenas_con_media.append({
            "imagen": ruta_img,
            "audio": ruta_audio,
            "texto_narrado": escena["texto_narrado"],
        })

    return escenas_con_media


def procesar_producto(producto: dict, indice: int):
    nombre = producto.get("nombre", f"Producto #{indice}")
    print(f"\n[{indice}] {nombre}")

    print("  → Generando guion de 7 escenas con IA...")
    guion = generar_guion(producto)

    print("  → Generando imagen y voz de cada escena...")
    escenas_con_media = _preparar_escenas(producto, guion, indice)

    print("  → Ensamblando video final...")
    ruta_video = f"{OUTPUT_DIR}/video_{indice}.mp4"
    construir_video_multiescena(escenas_con_media, ruta_video)

    url_amazon = producto.get("url_amazon", "")
    caption = (
        f"{guion['caption']}\n\n"
        f"{' '.join(guion['hashtags'])}\n"
        + (f"\n🔗 {url_amazon}" if url_amazon else "")
    )

    print(f"  → Enviando por {APPROVAL_CHANNEL}...")
    try:
        enviar_para_aprobacion(ruta_video, caption, nombre)
        print("  ✅ Enviado. Revisa tu teléfono.")
    except Exception as e:
        print(f"  ⚠️  Envío fallido ({e})")
        print(f"     Video guardado en: {ruta_video}")
        print(f"     Caption sugerido:\n{caption}")

    return ruta_video


def main():
    parser = argparse.ArgumentParser(description="Agente de contenido TikTok")
    parser.add_argument("--limite", type=int, default=None,
                        help="Procesar solo N productos (para probar)")
    parser.add_argument("--categorias", type=int, default=2,
                        help="Cuántas categorías investigar hoy (default: 2)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("FASE 1: Investigando productos del día en Amazon...")
    print("=" * 60)
    productos = investigar_productos(
        categorias_por_dia=args.categorias,
        productos_por_categoria=2,
    )

    if not productos:
        print("❌ No se encontraron productos hoy. Intenta de nuevo.")
        return

    if args.limite:
        productos = productos[:args.limite]

    print(f"\n{'=' * 60}")
    print(f"FASE 2: Produciendo {len(productos)} video(s) de 45+ segundos...")
    print("=" * 60)

    exitosos = 0
    for i, producto in enumerate(productos, start=1):
        try:
            procesar_producto(producto, i)
            exitosos += 1
        except Exception as e:
            print(f"  ❌ Error en '{producto.get('nombre', '')}': {e}")

    print(f"\n{'=' * 60}")
    print(f"Listo. {exitosos}/{len(productos)} videos enviados a tu {APPROVAL_CHANNEL}.")
    print("Aprobá desde el teléfono y subí a TikTok con un tap.")
    print("=" * 60)


if __name__ == "__main__":
    main()
