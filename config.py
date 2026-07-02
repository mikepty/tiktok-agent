"""
config.py — Configuración central del agente
Copia y renombra a config_local.py para tus claves reales.
NUNCA subas tus claves a GitHub. Usá GitHub Secrets (ver README).
"""
import os

# ── Motor de IA para guiones ────────────────────────────────────────────────
LLM_PROVIDER   = "gemini"              # "gemini" (gratis) o "claude" (pago)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "PON_TU_KEY_AQUI")
GEMINI_MODEL   = "gemini-2.5-flash"   # modelo gratuito recomendado

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-6"

# ── Canal de aprobación ─────────────────────────────────────────────────────
APPROVAL_CHANNEL     = "telegram"      # "telegram" (gratis) o "whatsapp"

TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_TOKEN           = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_TO_NUMBER       = os.getenv("WHATSAPP_TO_NUMBER", "")

# ── Voz IA (edge-tts, gratis) ───────────────────────────────────────────────
TTS_ENGINE = "edge-tts"
TTS_VOICE  = "es-MX-DaliaNeural"   # alternativas: es-US-PalomaNeural, es-CO-SalomeNeural

# ── Video ────────────────────────────────────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920   # 9:16 vertical, obligatorio para TikTok
SUBTITLE_FONT = "DejaVu-Sans-Bold"
BACKGROUND_MUSIC_PATH = "music/background.mp3"  # opcional, mp3 libre de derechos

# ── Rutas ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
ASSETS_DIR = "assets"
STATE_DIR  = "state"
MEMORY_DB  = os.path.join(STATE_DIR, "memory.sqlite")

# ── Memory Agent ─────────────────────────────────────────────────────────────
# Cuántos días recordar un producto/ASIN como "ya publicado" antes de
# permitir que vuelva a elegirse (evita contenido repetido).
MEMORIA_DIAS_COOLDOWN = 60

# ── Media Agent (B-roll real, gratis) ───────────────────────────────────────
# Claves gratuitas: pexels.com/api (instantáneo) y pixabay.com/api/docs
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
# Mínimo de clips reales que debe conseguir el Media Agent antes de
# recurrir al Imagegen Agent (tarjetas generadas) como relleno.
MIN_CLIPS_REALES = 3
CLIP_DURACION_MAX = 6  # segundos que se recortan de cada clip descargado

# ── Amazon Agent (scraping real con Playwright) ─────────────────────────────
AMAZON_DOMINIO = os.getenv("AMAZON_DOMINIO", "amazon.com")
AMAZON_CACHE_HORAS = 24        # no repetir la misma búsqueda en <24h
AMAZON_RATING_MINIMO = 4.0
AMAZON_RESENAS_MINIMO = 50
AMAZON_TIMEOUT_MS = 20000
# Si el scraping falla (bloqueo, captcha, timeout) el orquestador cae
# automáticamente al Research Agent basado en Gemini (product_researcher.py)

# ── Subtitle Agent ───────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")  # tiny/small/base
SUBTITULOS_PALABRA_POR_PALABRA = True

# ── Tipos de video que rota el Trend/SEO Agent ──────────────────────────────
TIPOS_DE_VIDEO = [
    "review", "top5", "comparativa", "tutorial", "como_funciona",
    "errores_comunes", "vale_la_pena", "antes_y_despues",
    "configuracion", "hack_smart_home", "lo_compraria_o_no",
]
