"""
telegram_approval.py
Canal de aprobación 100% GRATIS — sin verificación de negocio, sin costo
por mensaje, nunca. Listo en 5 minutos:

  1. En Telegram, buscá @BotFather y mandale /newbot
  2. Te da un token (algo como 123456:ABC-DEF...) -> eso va en
     config.TELEGRAM_BOT_TOKEN
  3. Buscá tu bot por su nombre y mandale cualquier mensaje (ej: "hola")
  4. Abrí en el navegador:
     https://api.telegram.org/bot<TU_TOKEN>/getUpdates
     y copiá el número "id" que aparece dentro de "chat" -> eso va en
     config.TELEGRAM_CHAT_ID

Listo, ya podés recibir videos para aprobar gratis para siempre.
"""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def enviar_para_aprobacion(ruta_video: str, caption: str, nombre_producto: str):
    texto = (
        f"🎬 Nuevo video listo: {nombre_producto}\n\n"
        f"{caption}\n\n"
        f"Si te gusta, descargalo y subilo a TikTok. "
        f"Si no, avisame qué cambiar."
    )
    url = f"{API_BASE}/sendVideo"
    with open(ruta_video, "rb") as f:
        files = {"video": f}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": texto[:1024]}
        resp = requests.post(url, files=files, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    print("Configurá TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en config.py antes de probar.")
