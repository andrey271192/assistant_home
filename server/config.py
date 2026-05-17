"""Configuration for Assistant Home."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"

load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR.parent / ".env", override=False)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8010"))
ENV = (os.getenv("ENV", "development") or "development").strip().lower()
PRODUCTION = ENV in ("production", "prod")
DISABLE_OPENAPI = PRODUCTION

PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8010") or "").rstrip("/")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN", "") or "").strip()
# Mini App: Telegram *user* id (в личке часто совпадает с chat_id). TELEGRAM_CHAT_ID — синоним.
_allowed_raw = (os.getenv("TELEGRAM_ALLOWED_IDS", "") or "").strip()
_chat_id = (os.getenv("TELEGRAM_CHAT_ID", "") or "").strip().strip('"').strip("'")
TELEGRAM_ALLOWED_IDS = [
    x.strip().strip('"').strip("'")
    for x in _allowed_raw.split(",")
    if x.strip()
]
if _chat_id and _chat_id not in TELEGRAM_ALLOWED_IDS:
    TELEGRAM_ALLOWED_IDS.append(_chat_id)
TELEGRAM_PIN = (os.getenv("TELEGRAM_PIN", "") or "").strip()
TELEGRAM_PIN_SESSION_HOURS = float(os.getenv("TELEGRAM_PIN_SESSION_HOURS", "12") or "12")

HA_URL = (os.getenv("HA_URL", "") or "").rstrip("/")
HA_TOKEN = (os.getenv("HA_TOKEN", "") or "").strip()

ROOMS_FILE = DATA_DIR / "rooms.json"
ACCESS_FILE = DATA_DIR / "access.json"
SESSIONS_FILE = DATA_DIR / "tg_sessions.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
