"""
video_builder.py
Ensambla el video final 9:16 listo para TikTok a partir de:
  - una o varias imágenes del producto (con efecto Ken Burns / zoom lento)
  - el audio de voz generado por tts_voice.py
  - subtítulos quemados (generados desde el mismo guion, sincronía simple)
  - música de fondo opcional a bajo volumen

Requiere ffmpeg instalado (ya viene en la mayoría de distros Linux;
en Windows: https://ffmpeg.org/download.html y agregarlo al PATH).
"""

import os
import subprocess
import textwrap
from config import VIDEO_WIDTH, VIDEO_HEIGHT, BACKGROUND_MUSIC_PATH


def _duracion_audio(ruta_audio: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", ruta_audio,
    ]
    out = subprocess.check_output(cmd).decode().strip()
    return float(out)


def _generar_srt(guion_texto: str, duracion: float, ruta_srt: str):
    """Genera subtítulos repartiendo el texto en bloques de tiempo iguales.
    Es una sincronía aproximada pero efectiva; si querés sincronía exacta
    palabra por palabra, se puede integrar whisper-timestamped más adelante."""
    palabras = guion_texto.split()
    bloques = textwrap.wrap(guion_texto, width=40)
    if not bloques:
        bloques = [guion_texto]
    tiempo_por_bloque = duracion / len(bloques)

    def fmt(t):
        h, m = int(t // 3600), int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    with open(ruta_srt, "w", encoding="utf-8") as f:
        for i, bloque in enumerate(bloques):
            inicio = i * tiempo_por_bloque
            fin = inicio + tiempo_por_bloque
            f.write(f"{i+1}\n{fmt(inicio)} --> {fmt(fin)}\n{bloque}\n\n")


def construir_video(imagenes: list, ruta_audio: str, guion_texto: str,
                     ruta_salida: str = "output/video_final.mp4"):
    duracion = _duracion_audio(ruta_audio)
    n_img = len(imagenes)
    dur_por_imagen = duracion / n_img

    ruta_srt = ruta_salida.replace(".mp4", ".srt")
    _generar_srt(guion_texto, duracion, ruta_srt)

    # 1) clip con zoom lento (Ken Burns) por cada imagen
    clips_tmp = []
    for idx, img in enumerate(imagenes):
        clip_tmp = f"output/_clip_{idx}.mp4"
        zoom_filter = (
            f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
            f"zoompan=z='min(zoom+0.0015,1.2)':d={int(dur_por_imagen*25)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_WIDTH}x{VIDEO_HEIGHT}"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img,
            "-vf", zoom_filter, "-t", str(dur_por_imagen),
            "-r", "25", "-pix_fmt", "yuv420p", clip_tmp,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        clips_tmp.append(clip_tmp)

    # 2) concatenar todos los clips de imagen
    lista_path = "output/_lista.txt"
    with open(lista_path, "w") as f:
        for c in clips_tmp:
            f.write(f"file '{os.path.abspath(c)}'\n")
    video_mudo = "output/_video_mudo.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_path,
         "-c", "copy", video_mudo],
        check=True, capture_output=True,
    )

    # 3) audio final: voz + (música de fondo opcional a bajo volumen)
    audio_final = ruta_audio
    if os.path.exists(BACKGROUND_MUSIC_PATH):
        audio_final = "output/_audio_mix.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", ruta_audio, "-i", BACKGROUND_MUSIC_PATH,
            "-filter_complex",
            "[1:a]volume=0.12,aloop=loop=-1:size=2e9[bg];"
            "[0:a][bg]amix=inputs=2:duration=first[aout]",
            "-map", "[aout]", audio_final,
        ], check=True, capture_output=True)

    # 4) video + audio + subtítulos quemados, todo junto
    subtitle_filter = f"subtitles={ruta_srt}:force_style='FontSize=14,FontName=DejaVu Sans Bold,Outline=2,BorderStyle=1'"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_mudo, "-i", audio_final,
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-c:a", "aac", "-shortest", ruta_salida,
    ], check=True, capture_output=True)

    # limpieza de temporales
    for c in clips_tmp:
        os.remove(c)
    os.remove(video_mudo)
    os.remove(lista_path)

    return ruta_salida


if __name__ == "__main__":
    # Prueba con una imagen sintética (reemplazar por fotos reales del producto)
    pass
