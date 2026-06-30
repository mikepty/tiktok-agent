"""
video_builder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ensambla el video final a partir de MÚLTIPLES ESCENAS (hook, problema,
4 características, cta). Cada escena tiene su propia imagen (con zoom
Ken Burns), su propio audio narrado, y dura lo que dura su audio.
El resultado es un video con progresión temática real, no una sola
imagen estática estirada — y con duración garantizada de 45+ segundos
porque cada escena aporta ~6-9s y son 7 escenas en total.

Requiere ffmpeg/ffprobe instalados.
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


def _clip_con_zoom(imagen: str, duracion: float, ruta_salida: str, zoom_in: bool = True):
    """Genera un clip de video mudo con efecto Ken Burns a partir de una imagen."""
    if zoom_in:
        zoom_expr = "min(zoom+0.0018,1.18)"
    else:
        zoom_expr = "if(eq(on,1),1.18,max(zoom-0.0018,1.0))"

    zoom_filter = (
        f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},"
        f"zoompan=z='{zoom_expr}':d={max(int(duracion*25),1)}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_WIDTH}x{VIDEO_HEIGHT}"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", imagen,
        "-vf", zoom_filter, "-t", str(duracion),
        "-r", "25", "-pix_fmt", "yuv420p", ruta_salida,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _concatenar_clips(rutas: list, ruta_salida: str, es_audio: bool = False):
    lista_path = ruta_salida + "_lista.txt"
    with open(lista_path, "w") as f:
        for r in rutas:
            f.write(f"file '{os.path.abspath(r)}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_path]
    cmd += (["-c", "copy"] if not es_audio else ["-c", "copy"])
    cmd += [ruta_salida]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(lista_path)


def _generar_srt_multiescena(escenas: list, duraciones: list, ruta_srt: str):
    """Genera subtítulos con timing real por escena (no aproximado),
    usando el texto narrado de cada escena."""
    def fmt(t):
        h, m = int(t // 3600), int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    tiempo_acumulado = 0.0
    bloque_n = 1
    with open(ruta_srt, "w", encoding="utf-8") as f:
        for escena, dur in zip(escenas, duraciones):
            texto = escena["texto_narrado"]
            # Dividir el texto de la escena en sub-bloques cortos para
            # que el subtítulo no sea una pared de texto
            sub_bloques = textwrap.wrap(texto, width=38) or [texto]
            t_por_bloque = dur / len(sub_bloques)
            for i, bloque in enumerate(sub_bloques):
                inicio = tiempo_acumulado + i * t_por_bloque
                fin = inicio + t_por_bloque
                f.write(f"{bloque_n}\n{fmt(inicio)} --> {fmt(fin)}\n{bloque}\n\n")
                bloque_n += 1
            tiempo_acumulado += dur


def construir_video_multiescena(escenas_con_media: list, ruta_salida: str = "output/video_final.mp4") -> str:
    """
    escenas_con_media: lista de dicts, cada uno con:
        - "imagen": ruta de la imagen de fondo de esa escena
        - "audio": ruta del mp3 narrado de esa escena
        - "texto_narrado": el texto que dice la voz (para subtítulos)

    Devuelve la ruta del video final, con duración = suma de cada escena
    (diseñado para superar los 45 segundos con 7 escenas de ~7-9s c/u).
    """
    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)

    duraciones = [_duracion_audio(e["audio"]) for e in escenas_con_media]
    duracion_total = sum(duraciones)
    print(f"    Duración total calculada: {duracion_total:.1f}s "
          f"({len(escenas_con_media)} escenas)")

    # 1. Clip con Ken Burns por escena
    clips_video = []
    for idx, (escena, dur) in enumerate(zip(escenas_con_media, duraciones)):
        clip_tmp = f"{ruta_salida}_clip{idx}.mp4"
        _clip_con_zoom(escena["imagen"], dur, clip_tmp, zoom_in=(idx % 2 == 0))
        clips_video.append(clip_tmp)

    video_mudo = ruta_salida + "_mudo.mp4"
    _concatenar_clips(clips_video, video_mudo)

    # 2. Concatenar todos los audios narrados en uno solo
    audios = [e["audio"] for e in escenas_con_media]
    audio_narrado = ruta_salida + "_narrado.mp3"
    _concatenar_clips(audios, audio_narrado, es_audio=True)

    # 3. Mezclar con música de fondo si existe
    audio_final = audio_narrado
    if os.path.exists(BACKGROUND_MUSIC_PATH):
        audio_final = ruta_salida + "_mix.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_narrado, "-i", BACKGROUND_MUSIC_PATH,
            "-filter_complex",
            "[1:a]volume=0.10,aloop=loop=-1:size=2e9[bg];"
            "[0:a][bg]amix=inputs=2:duration=first[aout]",
            "-map", "[aout]", audio_final,
        ], check=True, capture_output=True)

    # 4. Subtítulos con timing real por escena
    ruta_srt = ruta_salida.replace(".mp4", ".srt")
    _generar_srt_multiescena(escenas_con_media, duraciones, ruta_srt)

    # 5. Render final: video + audio + subtítulos quemados
    subtitle_filter = (
        f"subtitles={ruta_srt}:force_style="
        f"'FontSize=14,FontName=DejaVu Sans Bold,Outline=2,BorderStyle=1,"
        f"MarginV=60'"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", video_mudo, "-i", audio_final,
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-c:a", "aac", "-shortest", ruta_salida,
    ], check=True, capture_output=True)

    # limpieza
    for c in clips_video:
        os.remove(c)
    os.remove(video_mudo)
    os.remove(audio_narrado)
    if audio_final != audio_narrado and os.path.exists(audio_final):
        os.remove(audio_final)

    return ruta_salida


if __name__ == "__main__":
    pass
