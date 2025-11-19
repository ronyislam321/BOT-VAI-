import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
FISH_AUDIO_API_KEY = os.getenv("VOICE_API_KEY", "")
FISH_AUDIO_BASE_URL = os.getenv("FISH_AUDIO_BASE_URL", "https://api.fish.audio")
FISH_AUDIO_BACKEND = os.getenv("FISH_AUDIO_BACKEND", "s1")
FISH_AUDIO_MP3_BITRATE = int(os.getenv("FISH_AUDIO_MP3_BITRATE", "128"))

ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "t.me/sellmodel")
WEBSITE_URL   = os.getenv("WEBSITE_URL", "modelboxbd.com")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

DB_PATH = os.getenv("DB_PATH", "file.db")
VOICES_DIR = os.getenv("VOICES_DIR", "voices")

COST_PER_VOICE = 1

# When True, users must have active validity to generate voices.
# When False, credits alone are sufficient for generation.
REQUIRE_VALIDITY_FOR_TTS = False
MAX_TTS_CHARS = int(os.getenv("MAX_TTS_CHARS", "200"))

DEFAULT_MODELS = [
    {"id": "494877879d2b42958012daee17db9009", "name": "Ava"},
    {"id": "de41bdcdf09045e5945bf01adc92c287", "name": "Emily"},
    {"id": "9f20d4638c2846968e51c794faaf26a5", "name": "Sara"},
    {"id": "e88ebb71665b4e85a704060e302b3dcf", "name": "Sofiya"},
    {"id": "d75c78da679a4d8480e4bcfb6c60bdc6", "name": "Nora"},
]

# When True, users will only see and use models defined above.
USE_CONFIG_MODELS_ONLY = True

PLANS = [
    {"name": "Starter", "credits": 50, "price": "$5", "validity_days": 30},
    {"name": "Pro", "credits": 200, "price": "$15", "validity_days": 30},
    {"name": "Unlimited-Day", "credits": 400, "price": "$30", "validity_days": 30},
]

# Webhook / Railway deployment configuration
# When running on Railway, set USE_WEBHOOK=true and WEBHOOK_BASE_URL to your service URL (e.g., https://your-app.up.railway.app)
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")
# Railway provides PORT via env; default to 8000 for local runs
PORT = int(os.getenv("PORT", "8000"))
