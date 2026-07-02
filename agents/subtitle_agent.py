"""
agents/subtitle_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Genera subtítulos PALABRA POR PALABRA con resaltado (estilo TikTok
"karaoke"), usando faster-whisper para obtener el timing REAL de cada
palabra a partir del audio narrado — en vez del reparto aproximado por
longitud de texto que usa video_builder._generar_srt_multiescena.

faster-whisper corre bien en CPU (el runner de GitHub Actions no tiene
GPU) para audios cortos de 45-90s con el modelo "small"; tarda unos
10-20s por video, aceptable dentro del timeout del workflow.

Requiere: pip install faster-whisper
"""

import os
import subprocess
from config import WHISPER_MODEL_SIZE, VIDEO_WIDTH

_modelo = None  # cache: cargar el modelo Whisper una sola vez por proceso


def _cargar_modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        _modelo = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _modelo


def _fmt_ass_time(segundos: float) -> str:
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans Bold,72,&H00FFFFFF,&H0000D7FF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,2,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _construir_ass(palabras: list, ruta_ass: str):
    """
    palabras: lista de dicts {"texto": str, "inicio": float, "fin": float}
    Genera un .ass donde cada palabra aparece resaltada (color de acento)
    mientras se pronuncia, y el resto de la línea en blanco — efecto
    karaoke típico de subtítulos de TikTok/CapCut.
    """
    # Agrupamos palabras en líneas cortas (máx 4 palabras) para que el
    # bloque de texto no ocupe toda la pantalla.
    lineas = []
    actual = []
    for p in palabras:
        actual.append(p)
        if len(actual) >= 4:
            lineas.append(actual)
            actual = []
    if actual:
        lineas.append(actual)

    with open(ruta_ass, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER.format(ancho=VIDEO_WIDTH, alto=int(VIDEO_WIDTH * 16 / 9)))
        for linea in lineas:
            inicio_linea = linea[0]["inicio"]
            fin_linea = linea[-1]["fin"]
            for i, palabra in enumerate(linea):
                # Durante el intervalo de ESTA palabra, se resalta ella;
                # las demás de la línea van en blanco normal.
                partes = []
                for j, p in enumerate(linea):
                    txt = p["texto"].upper()
                    if j == i:
                        partes.append(r"{\c&H0AD7FF&}" + txt + r"{\c&HFFFFFF&}")
                    else:
                        partes.append(txt)
                texto_linea = " ".join(partes)
                f.write(
                    f"Dialogue: 0,{_fmt_ass_time(palabra['inicio'])},"
                    f"{_fmt_ass_time(palabra['fin'])},Default,,0,0,0,,{texto_linea}\n"
                )


def transcribir_palabras(ruta_audio: str) -> list:
    """
    Transcribe el audio narrado y devuelve timestamps por palabra.
    Como ya sabemos el texto exacto (viene del guion), esto se usa
    solo para obtener el TIMING real de cada palabra, no el contenido.
    """
    modelo = _cargar_modelo()
    segmentos, _info = modelo.transcribe(
        ruta_audio, word_timestamps=True, language="es", vad_filter=True,
    )
    palabras = []
    for seg in segmentos:
        for w in (seg.words or []):
            palabras.append({
                "texto": w.word.strip(),
                "inicio": w.start,
                "fin": w.end,
            })
    return palabras


def generar_subtitulos_animados(ruta_audio_final: str, ruta_ass_salida: str) -> str:
    """
    Punto de entrada del Subtitle Agent. Transcribe el audio final ya
    concatenado (narración + música) y genera un .ass con resaltado
    palabra por palabra listo para quemar con ffmpeg.

    Si faster-whisper falla por cualquier motivo (modelo no disponible,
    audio corrupto, etc.) devuelve None: el Video Agent debe entonces
    caer al .srt aproximado que ya genera video_builder.py.
    """
    try:
        palabras = transcribir_palabras(ruta_audio_final)
        if not palabras:
            return None
        _construir_ass(palabras, ruta_ass_salida)
        return ruta_ass_salida
    except Exception as e:
        print(f"    ⚠️  Subtitle Agent falló, se usará el .srt aproximado: {e}")
        return None


def quemar_subtitulos(ruta_video_sin_subs: str, ruta_ass: str, ruta_salida: str):
    """Quema el .ass sobre el video mudo+audio ya mezclado."""
    subprocess.run([
        "ffmpeg", "-y", "-i", ruta_video_sin_subs,
        "-vf", f"ass={ruta_ass}",
        "-c:v", "libx264", "-c:a", "copy", ruta_salida,
    ], check=True, capture_output=True)
    return ruta_salida


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 agents/subtitle_agent.py output/algun_audio.mp3")
    else:
        palabras = transcribir_palabras(sys.argv[1])
        for p in palabras[:20]:
            print(f"{p['inicio']:.2f}-{p['fin']:.2f}  {p['texto']}")
