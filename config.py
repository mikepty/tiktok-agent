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
