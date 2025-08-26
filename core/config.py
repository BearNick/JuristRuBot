import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# --- Payments ---
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
PRICE_RUB_SUBUNITS = int(os.getenv("PRICE_RUB_SUBUNITS", "50000"))  # 500 руб
POSTPAY_MODE = os.getenv("POSTPAY_MODE", "true").lower() in ("1", "true", "yes", "on")

# --- Flags ---
STRICT_VALIDATION = os.getenv("STRICT_VALIDATION", "false").lower() in ("1", "true", "yes", "on")
REQUIRE_SOURCES_TO_ANSWER = os.getenv("REQUIRE_SOURCES_TO_ANSWER", "false").lower() in ("1", "true", "yes", "on")

# --- Search ---
SOURCE_SITES = [
    s.strip() for s in os.getenv(
        "SOURCE_SITES",
        "pravo.gov.ru,consultant.ru,base.garant.ru,sudact.ru,publication.pravo.gov.ru"
    ).split(",") if s.strip()
]
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "8"))

# Google CSE (fallback)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

# SearXNG (self-hosted)
SEARXNG_URL = os.getenv("SEARXNG_URL", "")
SEARXNG_ENABLED = os.getenv("SEARXNG_ENABLED", "false").lower() in ("1", "true", "yes", "on")

# Startpage fallback
STARTPAGE_ENABLED = os.getenv("STARTPAGE_ENABLED", "true").lower() in ("1", "true", "yes", "on")

# --- Voice (опционально) ---
USE_VOSK = os.getenv("USE_VOSK", "false").lower() in ("1", "true", "yes", "on")
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "")
MAX_USER_CHARS = int(os.getenv("MAX_USER_CHARS", "500"))

# --- Disclaimer ---
USER_DISCLAIMER = (
    "⚠️ Я не являюсь вашим адвокатом. Ответ носит справочный характер и не заменяет юридическую помощь."
)