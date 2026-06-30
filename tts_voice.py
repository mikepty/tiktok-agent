"""
tts_voice.py
Convierte el guion en audio de voz natural en español, gratis,
usando edge-tts (motor de voces neuronales de Microsoft Edge).

Instalar: pip install edge-tts --break-system-packages
"""

import asyncio
import edge_tts
from config import TTS_VOICE


async def _generar_audio_async(texto: str, ruta_salida: str):
    communicate = edge_tts.Communicate(texto, TTS_VOICE)
    await communicate.save(ruta_salida)


def generar_audio(texto: str, ruta_salida: str = "output/voz.mp3"):
    """Genera un archivo mp3 con la voz narrando `texto`."""
    asyncio.run(_generar_audio_async(texto, ruta_salida))
    return ruta_salida


if __name__ == "__main__":
    texto_prueba = (
        "Esto que tenes enchufado ahora mismo te esta subiendo la factura "
        "de luz y ni te das cuenta."
    )
    salida = generar_audio(texto_prueba, "output/voz_prueba.mp3")
    print(f"Audio generado en: {salida}")
