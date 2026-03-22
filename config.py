"""
config.py — Barcha sozlamalar va muhit o'zgaruvchilari
"""

import logging
import os

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT = os.environ["TELEGRAM_CHAT_ID"]

# ── Clash of Clans ────────────────────────────────────────────────────────────
COC_API_KEY = os.environ["COC_API_KEY"]
CLAN_TAG    = os.environ["CLAN_TAG"]
COC_BASE    = "https://api.clashofclans.com/v1"
COC_HEADERS = {"Authorization": f"Bearer {COC_API_KEY}", "Accept": "application/json"}

# ── Server ────────────────────────────────────────────────────────────────────
PORT          = int(os.getenv("PORT", "10000"))
RENDER_URL    = os.getenv("RENDER_URL", "")   # e.g. https://coc-clan-bot.onrender.com
POLL_INTERVAL = 60                            # war monitor poll cadence (seconds)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
