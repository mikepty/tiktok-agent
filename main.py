"""
main.py — Orquestador autónomo del agente de contenido TikTok
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline completo sin intervención manual:

  1. Gemini investiga en Google qué productos de tecnología están
     ganando tracción en Amazon HOY (rota categorías diariamente)
  2. Por cada producto: genera guion viral + voz IA + video editado
  3. Te lo manda por Telegram para aprobar
  4. Vos subís con un tap a TikTok

Uso:
  python3 main.py                 → produce todos los videos del día
  python3 main.py --limite 1      → solo 1 (para probar)
  python3 main.py --categorias 3  → investiga 3 categorías (más volumen)

Corre solo en GitHub Actions todos los días sin que toques nada.
"""

import argparse
import os

from product_researcher import investigar_productos
from script_generator import generar_guion
from tts_voice import generar_audio
from video_builder import construir_video
from image_fetcher import obtener_imagen_producto
from config import OUTPUT_DIR, APPROVAL_CHANNEL

if APPROVAL_CHANNEL == "telegram":
    from telegram_approval import enviar_para_aprobacion
else:
    from whatsapp_approval import enviar_para_aprobacion


def procesar_producto(producto: dict, indice: int):
    nombre = producto.get("nombre", f"Producto #{indice}")
    precio = str(producto.get("precio_usd", ""))
    categoria = producto.get("categoria", "tecnologia")
    url_imagen = producto.get("url_imagen", "")

    print(f"\n[{indice}] {nombre}")

    # 1. Imagen del producto
    print("  → Imagen...")
    ruta_imagen = obtener_imagen_producto(url_imagen, nombre, precio, categoria, indice)

    # 2. Guion viral
    print("  → Guion viral con IA...")
    guion = generar_guion(producto)

    # 3. Voz
    print("  → Voz IA...")
    ruta_audio = f"{OUTPUT_DIR}/voz_{indice}.mp3"
    generar_audio(guion["guion_completo"], ruta_audio)

    # 4. Video
    print("  → Armando video...")
    ruta_video = f"{OUTPUT_DIR}/video_{indice}.mp4"
    construir_video([ruta_imagen], ruta_audio, guion["guion_completo"], ruta_video)

    # 5. Caption final = caption + hashtags + link
    url_amazon = producto.get("url_amazon", "")
    caption = (
        f"{guion['caption']}\n\n"
        f"{' '.join(guion['hashtags'])}\n"
        + (f"\n🔗 {url_amazon}" if url_amazon else "")
    )

    # 6. Enviar para aprobación
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

    # ── FASE 1: Investigación autónoma ──────────────────────────────────────
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

    # ── FASE 2: Producción de videos ────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"FASE 2: Produciendo {len(productos)} video(s)...")
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
