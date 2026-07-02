"""
core/orchestrator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline modular: cada fase es un agente independiente. Si un agente
"premium" (más real pero más frágil) falla, el orquestador cae al
agente de respaldo más simple, y SIEMPRE registra el error en la
memoria para diagnóstico — nunca tumba todo el run por un producto.

  Amazon Agent (scraping real)  ──falla──▶  Research Agent (Gemini)
  Media Agent (B-roll real)     ──falla──▶  Imagegen Agent (tarjetas Pillow)
  Subtitle Agent (whisper)      ──falla──▶  SRT aproximado (ya integrado
                                              dentro de video_builder.py)

Uso:
  python3 -m core.orchestrator                  → todos los productos del día
  python3 -m core.orchestrator --limite 1        → solo 1 (para probar)
  python3 -m core.orchestrator --categorias 3    → más volumen
  python3 -m core.orchestrator --sin-amazon      → forzar Research Agent
"""

import argparse
import os

from config import OUTPUT_DIR, APPROVAL_CHANNEL, MIN_CLIPS_REALES

from agents import memory_agent, seo_agent, media_agent
from product_researcher import investigar_productos as investigar_con_gemini
from script_generator import generar_guion
from tts_voice import generar_audio
from video_builder import construir_video_multiescena
from image_fetcher import obtener_imagen_producto, generar_tarjeta_escena

if APPROVAL_CHANNEL == "telegram":
    from telegram_approval import enviar_para_aprobacion
else:
    from whatsapp_approval import enviar_para_aprobacion

# Categorías reales (en inglés, para Amazon + Pexels/Pixabay) espejadas
# de product_researcher.CATEGORIAS (en español, para el prompt de Gemini).
CATEGORIAS_EN = [
    "smart plug wifi", "wifi security camera", "smart door lock",
    "smart led bulb", "smart thermostat", "wifi motion sensor",
    "robot vacuum", "matter smart home hub",
]


# ────────────────────────────────────────────────────────────────────────
# FASE 1: Research (Amazon Agent con fallback a Research Agent Gemini)
# ────────────────────────────────────────────────────────────────────────
def fase_investigacion(categorias_por_dia: int, productos_por_categoria: int,
                        forzar_gemini: bool = False) -> list:
    if forzar_gemini:
        return investigar_con_gemini(categorias_por_dia, productos_por_categoria)

    try:
        from agents.amazon_agent import investigar_categoria_amazon
        import datetime
        dia = datetime.datetime.now().timetuple().tm_yday
        idx = [(dia * categorias_por_dia + i) % len(CATEGORIAS_EN)
               for i in range(categorias_por_dia)]

        productos = []
        for i in idx:
            query = CATEGORIAS_EN[i]
            resultado = investigar_categoria_amazon(query, query, productos_por_categoria)
            productos.extend(resultado)

        if not productos:
            raise RuntimeError("Amazon Agent no devolvió productos")
        print(f"[Research] Amazon Agent OK: {len(productos)} productos reales")
        return productos

    except Exception as e:
        print(f"[Research] ⚠️  Amazon Agent falló ({e}); cayendo a Research Agent (Gemini)")
        memory_agent.registrar_error("amazon_agent", e)
        return investigar_con_gemini(categorias_por_dia, productos_por_categoria)


# ────────────────────────────────────────────────────────────────────────
# FASE 2: Media por escena (Media Agent con fallback a Imagegen Agent)
# ────────────────────────────────────────────────────────────────────────
def _media_para_escena(producto: dict, escena: dict, indice_escena: int,
                        sufijo: str) -> dict:
    nombre = producto.get("nombre", "")
    precio = str(producto.get("precio_usd", ""))
    categoria = producto.get("categoria", "tecnologia")

    ruta_img = f"{OUTPUT_DIR}/img_{sufijo}.jpg"
    if indice_escena == 0:
        obtener_imagen_producto(producto.get("url_imagen", ""), nombre, precio,
                                 categoria, f"{sufijo}_hero")
        ruta_img = f"{OUTPUT_DIR}/img_{sufijo}_hero.jpg"
    else:
        generar_tarjeta_escena(
            texto_pantalla=escena["texto_pantalla"], tipo_escena=escena["tipo"],
            nombre_producto=nombre, categoria=categoria, precio=precio,
            indice_escena=indice_escena, ruta_destino=ruta_img,
        )

    broll = None
    try:
        keywords = media_agent.keywords_desde_categoria(categoria)
        clips = media_agent.buscar_clips_para_escena(keywords, sufijo, cantidad=1)
        if clips:
            broll = clips[0]
    except Exception as e:
        memory_agent.registrar_error("media_agent", e)

    ruta_audio = f"{OUTPUT_DIR}/voz_{sufijo}.mp3"
    generar_audio(escena["texto_narrado"], ruta_audio)

    return {"imagen": ruta_img, "broll": broll, "audio": ruta_audio,
            "texto_narrado": escena["texto_narrado"]}


def _preparar_escenas(producto: dict, guion: dict, indice_producto: int) -> list:
    escenas_con_media = []
    for i, escena in enumerate(guion["escenas"]):
        sufijo = f"{indice_producto}_{i}"
        escenas_con_media.append(_media_para_escena(producto, escena, i, sufijo))

    clips_reales = sum(1 for e in escenas_con_media if e.get("broll"))
    if clips_reales < MIN_CLIPS_REALES:
        print(f"    ℹ️  Solo {clips_reales} clips reales de B-roll; "
              f"el resto usa tarjetas generadas (esperado sin PEXELS/PIXABAY_API_KEY)")

    return escenas_con_media


# ────────────────────────────────────────────────────────────────────────
# Pipeline por producto
# ────────────────────────────────────────────────────────────────────────
def procesar_producto(producto: dict, indice: int) -> str:
    nombre = producto.get("nombre", f"Producto #{indice}")
    print(f"\n[{indice}] {nombre}")

    if memory_agent.ya_publicado(producto.get("asin", ""), nombre):
        print("  ⏭️  Ya publicado recientemente (Memory Agent). Saltando.")
        return ""

    print("  → SEO/Trend Agent: eligiendo formato y completando datos...")
    tipo_video = seo_agent.elegir_tipo_video()
    producto = seo_agent.completar_datos_producto(producto)
    print(f"    Formato elegido: {tipo_video}")

    print("  → Script Agent: generando guion de 7 escenas...")
    guion = generar_guion(producto, tipo_video=tipo_video)

    print("  → Media + Voice Agent: clips reales / tarjetas + narración por escena...")
    escenas_con_media = _preparar_escenas(producto, guion, indice)

    print("  → Video Agent: ensamblando (B-roll real + Ken Burns + subtítulos)...")
    ruta_video = f"{OUTPUT_DIR}/video_{indice}.mp4"
    construir_video_multiescena(escenas_con_media, ruta_video)

    print("  → SEO Agent: armando descripción y hashtags finales...")
    seo_final = seo_agent.generar_descripcion_final(producto, guion, tipo_video)

    print(f"  → Publishing Agent: enviando por {APPROVAL_CHANNEL} para aprobación manual...")
    try:
        enviar_para_aprobacion(ruta_video, seo_final["descripcion_final"], nombre)
        print("  ✅ Enviado. Revisa tu teléfono para subirlo a TikTok.")
    except Exception as e:
        print(f"  ⚠️  Envío fallido ({e}). Video guardado en: {ruta_video}")
        memory_agent.registrar_error("publishing_agent", e)

    memory_agent.registrar_publicacion(producto, tipo_video, ruta_video)
    memory_agent.registrar_hashtags(seo_final["hashtags"])

    return ruta_video


def guardar_productos_json(productos: list, ruta: str):
    """Serializa los productos investigados a JSON, para pasarlos entre
    jobs de GitHub Actions vía upload-artifact/download-artifact."""
    import json
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)


def cargar_productos_json(ruta: str) -> list:
    import json
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Orquestador del agente de contenido TikTok")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--categorias", type=int, default=2)
    parser.add_argument("--sin-amazon", action="store_true",
                        help="Forzar Research Agent (Gemini) en vez de Amazon Agent")
    parser.add_argument("--modo", choices=["full", "investigar", "producir"], default="full",
                        help=(
                            "full: investiga y produce en la misma corrida (default, uso local). "
                            "investigar: solo Fase 1 (Amazon/Gemini), guarda "
                            "--productos-json y termina — pensado para un job de "
                            "Actions corto y aislado, ya que Playwright/Amazon "
                            "pueden colgarse o tardar. "
                            "producir: solo Fase 2, lee productos de "
                            "--productos-json en vez de investigar — pensado para "
                            "el job de Actions que depende del anterior."
                        ))
    parser.add_argument("--productos-json", default=f"{OUTPUT_DIR}/productos_del_dia.json",
                        help="Ruta del JSON intermedio usado por --modo investigar/producir")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    memory_agent.init_db()

    # ── Fase 1: investigación ────────────────────────────────────────
    if args.modo in ("full", "investigar"):
        print("=" * 60)
        print("FASE 1: Research Agent (Amazon real → fallback Gemini)")
        print("=" * 60)
        productos = fase_investigacion(args.categorias, 2, forzar_gemini=args.sin_amazon)

        if not productos:
            print("❌ No se encontraron productos hoy.")
            if args.modo == "investigar":
                # Igual escribimos un JSON vacío: el job de producción lo
                # detecta y termina limpio en vez de fallar por archivo
                # inexistente.
                guardar_productos_json([], args.productos_json)
            return

        if args.modo == "investigar":
            guardar_productos_json(productos, args.productos_json)
            print(f"✅ {len(productos)} producto(s) guardados en {args.productos_json}")
            return
    else:  # modo == "producir"
        print("=" * 60)
        print(f"Cargando productos investigados de {args.productos_json}")
        print("=" * 60)
        try:
            productos = cargar_productos_json(args.productos_json)
        except FileNotFoundError:
            print(f"❌ No existe {args.productos_json}. ¿Corrió el job de investigación?")
            return
        if not productos:
            print("ℹ️  El job de investigación no encontró productos hoy. Nada que producir.")
            return

    if args.limite:
        productos = productos[:args.limite]

    print(f"\n{'=' * 60}")
    print(f"FASE 2: Produciendo {len(productos)} video(s)")
    print("=" * 60)

    exitosos = 0
    for i, producto in enumerate(productos, start=1):
        try:
            if procesar_producto(producto, i):
                exitosos += 1
        except Exception as e:
            print(f"  ❌ Error en '{producto.get('nombre', '')}': {e}")
            memory_agent.registrar_error(f"producto_{i}", e)

    print(f"\n{'=' * 60}")
    print(f"Listo. {exitosos}/{len(productos)} videos enviados a tu {APPROVAL_CHANNEL}.")
    print("Memoria:", memory_agent.resumen())
    print("=" * 60)


if __name__ == "__main__":
    main()
