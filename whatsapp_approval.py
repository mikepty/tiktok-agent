"""
whatsapp_approval.py
Envía el video generado a tu WhatsApp para aprobación antes de publicar.

Usa la misma lógica que ya estás construyendo para RemateHoy
(WhatsApp Cloud API de Meta). Si ya tenés esa integración funcionando
en ese proyecto, podés copiar/pegar tus credenciales y la función
de envío de mensajes prácticamente tal cual.

Requiere:
  - Una app de Meta for Developers con producto WhatsApp Business
  - WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, WHATSAPP_TO_NUMBER en config.py
  - El video subido a algún lugar con URL pública temporal para poder
    enviarlo (Meta exige una URL, no acepta archivo local directo salvo
    que lo subas primero a su endpoint de media). Aquí se sube como
    "media" directamente, que es el camino mas simple.
"""

import requests
from config import WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, WHATSAPP_TO_NUMBER

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _subir_media(ruta_video: str) -> str:
    url = f"{GRAPH_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    with open(ruta_video, "rb") as f:
        files = {"file": (ruta_video, f, "video/mp4")}
        data = {"messaging_product": "whatsapp"}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]


def enviar_para_aprobacion(ruta_video: str, caption: str, nombre_producto: str):
    media_id = _subir_media(ruta_video)

    url = f"{GRAPH_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    texto_mensaje = (
        f"🎬 *Nuevo video listo: {nombre_producto}*\n\n"
        f"{caption}\n\n"
        f"Responde:\n✅ para aprobar y publicar\n❌ para descartar\n"
        f"✏️ \"editar: ...\" para pedir cambios"
    )

    payload_video = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_TO_NUMBER,
        "type": "video",
        "video": {"id": media_id, "caption": texto_mensaje},
    }
    resp = requests.post(url, headers=headers, json=payload_video, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Nota sobre cómo recibir la respuesta (✅ / ❌) ───────────────────────────
# Para que el agente "escuche" tu respuesta y dispare la publicación,
# necesitás un webhook de WhatsApp (un endpoint que Meta llama cuando
# respondés). Si ya tenés ese webhook corriendo para RemateHoy, es la
# MISMA pieza de infraestructura: solo agregás una rama de lógica que
# identifique "este mensaje es sobre un video de TikTok pendiente" y
# actúe en consecuencia (mover el archivo a la carpeta de publicar,
# o llamar a la API de publicación si ya tenés AUTO_PUBLISH=True).

if __name__ == "__main__":
    print("Módulo de prueba: configurá tus credenciales en config.py antes de correr esto.")
