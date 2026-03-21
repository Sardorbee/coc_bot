"""
╔══════════════════════════════════════════════════════════════╗
║        Clash of Clans — Telegram Bot  (Render Edition)       ║
║──────────────────────────────────────────────────────────────║
║  Render requires:                                            ║
║   • A real HTTP server (Flask) so the service stays alive    ║
║   • Webhook mode instead of polling                          ║
║   • PORT env var respected (Render sets this automatically)  ║
║──────────────────────────────────────────────────────────────║
║  Features:                                                   ║
║   ⏰  War end reminder  (2 hr + 30 min warnings)             ║
║   🏁  Auto-post war results when war ends                    ║
║   🌟  Real-time 3-star alert with full description           ║
║   👤  /player #TAG  — detailed player card                   ║
║   ⚔️   /war          — live war snapshot                     ║
║   📋  /warlog       — last 5 war results                     ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

import aiohttp
from flask import Flask, Response
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── CONFIG ────────────────────────────────────────────────────────────────────
COC_API_KEY   = os.environ["COC_API_KEY"]           # raise if missing
BOT_TOKEN     = os.environ["TELEGRAM_BOT_TOKEN"]
CLAN_TAG      = os.environ["CLAN_TAG"]
TELEGRAM_CHAT = os.environ["TELEGRAM_CHAT_ID"]
WEBHOOK_URL   = os.environ["WEBHOOK_URL"]           # e.g. https://your-app.onrender.com

PORT          = int(os.getenv("PORT", "10000"))     # Render injects PORT
POLL_INTERVAL = 60                                  # war monitor cadence (seconds)

COC_BASE = "https://api.clashofclans.com/v1"
HEADERS  = {"Authorization": f"Bearer {COC_API_KEY}", "Accept": "application/json"}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── WAR STATE ─────────────────────────────────────────────────────────────────
_state = {
    "war_end_time":    None,
    "reminded_2h":     False,
    "reminded_30m":    False,
    "posted_result":   False,
    "three_star_seen": set(),
}

def _reset_war_state(end_time: str):
    _state.update({
        "war_end_time":    end_time,
        "reminded_2h":     False,
        "reminded_30m":    False,
        "posted_result":   False,
        "three_star_seen": set(),
    })
    log.info("War state reset (endTime=%s)", end_time)

# ── COC API ───────────────────────────────────────────────────────────────────

def encode_tag(tag: str) -> str:
    return tag.strip().upper().replace("#", "%23")


async def coc_get(session: aiohttp.ClientSession, path: str):
    try:
        async with session.get(
            f"{COC_BASE}{path}", headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            if r.status == 200:
                return await r.json()
            log.warning("CoC API %s → HTTP %s", path, r.status)
    except Exception as exc:
        log.error("CoC request failed %s: %s", path, exc)
    return None


async def get_current_war(s): return await coc_get(s, f"/clans/{encode_tag(CLAN_TAG)}/currentwar")
async def get_war_log(s):
    d = await coc_get(s, f"/clans/{encode_tag(CLAN_TAG)}/warlog?limit=5")
    return (d or {}).get("items", [])
async def get_player(s, tag): return await coc_get(s, f"/players/{encode_tag(tag)}")

# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_coc_time(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)

def time_left_str(sec: float) -> str:
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    return f"{h}h {m}m" if h else f"{m}m"

def stars_bar(n: int) -> str:
    return "⭐" * n + "☆" * (3 - n)

def result_emoji(r: str) -> str:
    return {"WIN": "🏆", "LOSE": "💀", "TIE": "🤝"}.get((r or "").upper(), "🏁")

def find_defender_name(war: dict, tag: str) -> str:
    for m in war.get("opponent", {}).get("members", []):
        if m["tag"] == tag:
            return m["name"]
    return "Unknown"

def find_new_3stars(war: dict) -> list:
    hits = []
    for m in war.get("clan", {}).get("members", []):
        for atk in m.get("attacks", []):
            if atk["stars"] == 3:
                key = f"{atk['attackerTag']}-{atk['defenderTag']}"
                if key not in _state["three_star_seen"]:
                    hits.append({
                        "key":           key,
                        "attacker_name": m["name"],
                        "defender_tag":  atk["defenderTag"],
                        "destruction":   atk["destructionPercentage"],
                        "duration":      atk.get("duration", 0),
                    })
    return hits

# ── MESSAGE TEMPLATES ─────────────────────────────────────────────────────────

def msg_three_star(attacker, defender, destruction, duration, war_type="Clan War") -> str:
    mins, secs = divmod(duration, 60)
    dur = f"{mins}m {secs}s" if mins else f"{secs}s"
    hype = (
        "💯 Perfect destruction — flawless victory!" if destruction == 100 else
        "🔥 Near-perfect raid — incredible attack!"   if destruction >= 95  else
        "👏 Outstanding attack! The clan is proud!"
    )
    return (
        f"╔══════════════════════╗\n"
        f"🌟 *TRIPLE STAR!* 🌟\n"
        f"╚══════════════════════╝\n\n"
        f"⚔️  *War Type:* {war_type}\n\n"
        f"🗡  *Attacker:* {attacker}\n"
        f"🏰  *Defender:* {defender}\n\n"
        f"⭐⭐⭐  `{destruction:.0f}%` destruction\n"
        f"⏱  *Duration:* {dur}\n\n"
        f"{hype}"
    )

def msg_war_status(war: dict) -> str:
    state = war.get("state", "unknown")
    clan, opp = war["clan"], war["opponent"]
    used  = clan.get("attacks", 0)
    total = war["teamSize"] * war.get("attacksPerMember", 2)
    emoji = {"preparation": "📋", "inWar": "⚔️", "warEnded": "🏁"}.get(state, "❓")
    lines = [
        f"{emoji} *War Status: {state.upper()}*", "",
        f"🔵 *{clan['name']}*  vs  🔴 *{opp['name']}*",
        f"👥 {war['teamSize']}v{war['teamSize']}", "",
        f"⭐ Stars:       `{clan['stars']}` — `{opp['stars']}`",
        f"💥 Destruction: `{clan.get('destructionPercentage',0):.1f}%` — `{opp.get('destructionPercentage',0):.1f}%`",
        f"⚔️  Attacks:    `{used}/{total}` ({total-used} left)",
    ]
    if state == "inWar":
        rem = (parse_coc_time(war["endTime"]) - datetime.now(timezone.utc)).total_seconds()
        if rem > 0:
            lines.append(f"⏳ Time left: *{time_left_str(rem)}*")
    return "\n".join(lines)

def msg_war_result(war: dict) -> str:
    clan, opp = war["clan"], war["opponent"]
    result    = war.get("result", "unknown")
    attacks   = sorted(
        [(m["name"], a["stars"], a["destructionPercentage"])
         for m in clan.get("members", []) for a in m.get("attacks", [])],
        key=lambda x: (x[1], x[2]), reverse=True
    )
    missed = [m["name"] for m in clan.get("members", []) if not m.get("attacks")]
    lines = [
        f"{result_emoji(result)} *WAR ENDED — {result.upper()}*", "",
        f"🔵 *{clan['name']}*",
        f"   ⭐`{clan['stars']}`  💥`{clan.get('destructionPercentage',0):.1f}%`  ⚔️`{clan['attacks']}` attacks", "",
        f"🔴 *{opp['name']}*",
        f"   ⭐`{opp['stars']}`  💥`{opp.get('destructionPercentage',0):.1f}%`  ⚔️`{opp['attacks']}` attacks", "",
    ]
    if attacks:
        lines.append("🏅 *Top 5 Attacks:*")
        for name, stars, dest in attacks[:5]:
            lines.append(f"   {stars_bar(stars)} `{dest:.0f}%` — {name}")
        lines.append("")
    if missed:
        lines.append(f"😴 *Missed attacks ({len(missed)}):* " + ", ".join(missed))
    return "\n".join(lines)

def msg_warlog(entries: list) -> str:
    if not entries:
        return "📭 War log is empty or set to private in clan settings."
    lines = ["📜 *Last 5 Wars:*", ""]
    for i, w in enumerate(entries[:5], 1):
        c, o = w.get("clan", {}), w.get("opponent", {})
        lines.append(
            f"{i}. {result_emoji(w.get('result','?'))} vs *{o.get('name','?')}*  "
            f"⭐`{c.get('stars','?')}:{o.get('stars','?')}`  "
            f"💥`{c.get('destructionPercentage',0):.0f}%`"
        )
    return "\n".join(lines)

def msg_player(p: dict) -> str:
    hv = {h["name"]: h["level"] for h in p.get("heroes", []) if h.get("village") == "HOME_VILLAGE"}
    war_pref = "✅ In" if p.get("warPreference") == "IN" else "❌ Out"
    return "\n".join([
        f"👤 *{p['name']}* (`{p['tag']}`)",
        f"🏠 Town Hall *{p['townHallLevel']}*  |  🎖 XP {p['expLevel']}",
        f"🏆 Trophies: `{p['trophies']}`  (Best: `{p['bestTrophies']}`)",
        f"🛡 Clan: *{p.get('clan',{}).get('name','No Clan')}*  [{p.get('role','').replace('_',' ').title()}]",
        f"🥇 League: {p.get('league',{}).get('name','Unranked')}",
        "",
        "👑 *Heroes:*",
        f"   Barbarian King: `{hv.get('Barbarian King', 0)}`",
        f"   Archer Queen:   `{hv.get('Archer Queen', 0)}`",
        f"   Grand Warden:   `{hv.get('Grand Warden', 0)}`",
        f"   Royal Champion: `{hv.get('Royal Champion', 0)}`",
        "",
        f"⭐ War Stars: `{p.get('warStars', 0)}`  |  War: {war_pref}",
        f"🤝 Donations: `{p['donations']}` sent / `{p['donationsReceived']}` received",
        f"🏰 Attack Wins: `{p.get('attackWins',0)}`  |  Defense Wins: `{p.get('defenseWins',0)}`",
    ])

# ── TELEGRAM COMMANDS ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *CoC Clan Bot is Online!*\n\n"
        "*Commands:*\n"
        "• /war — live war status\n"
        "• /warlog — last 5 war results\n"
        "• /player #TAG — full player profile\n\n"
        "*Auto-Alerts:*\n"
        "• ⏰ 2hr & 30min war end warnings\n"
        "• 🌟 Real-time 3-star notifications\n"
        "• 🏁 Full war result when war ends",
        parse_mode="Markdown",
    )

async def cmd_war(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        war = await get_current_war(s)
    if not war or war.get("state") == "notInWar":
        await update.message.reply_text("😴 Clan is not currently in a war.")
        return
    await update.message.reply_text(msg_war_status(war), parse_mode="Markdown")

async def cmd_warlog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        entries = await get_war_log(s)
    await update.message.reply_text(msg_warlog(entries), parse_mode="Markdown")

async def cmd_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /player #PLAYERTAG\nExample: /player #2ABC123")
        return
    async with aiohttp.ClientSession() as s:
        p = await get_player(s, ctx.args[0])
    if not p:
        await update.message.reply_text("❌ Player not found — double-check the tag.")
        return
    await update.message.reply_text(msg_player(p), parse_mode="Markdown")

# ── WAR MONITOR LOOP ──────────────────────────────────────────────────────────

async def war_monitor(bot: Bot):
    log.info("War monitor started (every %ds).", POLL_INTERVAL)
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                war = await get_current_war(s)

            if war:
                state = war.get("state")

                if state == "inWar":
                    end_time = war["endTime"]
                    if _state["war_end_time"] != end_time:
                        _reset_war_state(end_time)

                    remaining = (parse_coc_time(end_time) - datetime.now(timezone.utc)).total_seconds()
                    clan, opp = war["clan"], war["opponent"]
                    attacks_left = war["teamSize"] * war.get("attacksPerMember", 2) - clan.get("attacks", 0)

                    # 3-star alerts
                    for hit in find_new_3stars(war):
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            msg_three_star(
                                hit["attacker_name"],
                                find_defender_name(war, hit["defender_tag"]),
                                hit["destruction"], hit["duration"],
                            ),
                            parse_mode="Markdown",
                        )
                        _state["three_star_seen"].add(hit["key"])
                        log.info("3⭐ sent: %s", hit["attacker_name"])

                    # 2h reminder
                    if 0 < remaining <= 7200 and not _state["reminded_2h"]:
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"⏰ *War ends in ~2 hours!*\n\n"
                            f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage',0):.1f}%`\n"
                            f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage',0):.1f}%`\n\n"
                            f"⚔️ Attacks remaining: *{attacks_left}*\n📣 Don't forget to attack!",
                            parse_mode="Markdown",
                        )
                        _state["reminded_2h"] = True

                    # 30m reminder
                    if 0 < remaining <= 1800 and not _state["reminded_30m"]:
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"🚨 *FINAL WARNING — War ends in 30 minutes!*\n\n"
                            f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage',0):.1f}%`\n"
                            f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage',0):.1f}%`\n\n"
                            f"⚔️ Attacks remaining: *{attacks_left}*\n⚠️ Last chance — attack *NOW*!",
                            parse_mode="Markdown",
                        )
                        _state["reminded_30m"] = True

                elif state == "warEnded":
                    end_time = war.get("endTime", "")
                    if _state["war_end_time"] != end_time:
                        _reset_war_state(end_time)
                    if not _state["posted_result"]:
                        await bot.send_message(TELEGRAM_CHAT, msg_war_result(war), parse_mode="Markdown")
                        _state["posted_result"] = True
                        log.info("War result posted.")

        except Exception as exc:
            log.error("Monitor error: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)

# ── FLASK HEALTH SERVER ───────────────────────────────────────────────────────
# Render requires a web server to keep the service alive.
# This tiny Flask app answers health checks on the PORT Render provides.

flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return Response("⚔️ CoC Bot is running!", status=200, mimetype="text/plain")

@flask_app.route("/webhook", methods=["POST"])
def webhook_stub():
    # Placeholder — actual webhook handling is done by python-telegram-bot below
    return Response("ok", status=200)

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False)

# ── MAIN ──────────────────────────────────────────────────────────────────────

async def post_init(app: Application):
    # Register webhook with Telegram
    webhook_endpoint = f"{WEBHOOK_URL}/tg_webhook"
    await app.bot.set_webhook(url=webhook_endpoint)
    log.info("Webhook set → %s", webhook_endpoint)
    # Launch war monitor as background task
    asyncio.create_task(war_monitor(app.bot))


async def post_shutdown(app: Application):
    await app.bot.delete_webhook()
    log.info("Webhook deleted.")


def main():
    # Start Flask in a background thread (keeps Render happy)
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    log.info("Flask health server started on port %d.", PORT)

    # Build Telegram app in webhook mode
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("war",    cmd_war))
    app.add_handler(CommandHandler("warlog", cmd_warlog))
    app.add_handler(CommandHandler("player", cmd_player))

    log.info("Bot starting in webhook mode…")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT + 1,          # PTB webhook on a different port from Flask
        webhook_url=f"{WEBHOOK_URL}/tg_webhook",
        url_path="/tg_webhook",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
