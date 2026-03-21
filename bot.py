"""
╔══════════════════════════════════════════════════════════════╗
║     Clash of Clans — Telegram Bot  (O'zbek tilida)          ║
║──────────────────────────────────────────────────────────────║
║  Buyruqlar:                                                  ║
║   /urush      — joriy urush holati                           ║
║   /urushlog   — oxirgi 5 ta urush natijasi                   ║
║   /oyinchi    — o'yinchi ma'lumotlari                        ║
║   /azolar     — klan a'zolari ro'yxati                       ║
║  Avtomatik xabarlar:                                         ║
║   ⏰  Urush tugashiga 2 soat qolganda ogohlantirish          ║
║   🚨  Urush tugashiga 30 daqiqa qolganda ogohlantirish       ║
║   🌟  3 yulduzli hujum bildirishnomasi                       ║
║   🏁  Urush natijasi avtomatik e'lon                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── CONFIG ────────────────────────────────────────────────────────────────────
COC_API_KEY   = os.environ["COC_API_KEY"]
BOT_TOKEN     = os.environ["TELEGRAM_BOT_TOKEN"]
CLAN_TAG      = os.environ["CLAN_TAG"]
TELEGRAM_CHAT = os.environ["TELEGRAM_CHAT_ID"]
PORT          = int(os.getenv("PORT", "10000"))
POLL_INTERVAL = 60

# ── HEALTH SERVER ─────────────────────────────────────────────────────────────
class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        import urllib.request
        try:
            ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
        except Exception:
            ip = "unavailable"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"CoC Bot ishlayapti | Chiqish IP: {ip}".encode())
    def log_message(self, *_):
        pass

def _start_health_server():
    HTTPServer(("0.0.0.0", PORT), _Health).serve_forever()

threading.Thread(target=_start_health_server, daemon=True).start()

COC_BASE = "https://api.clashofclans.com/v1"
HEADERS  = {"Authorization": f"Bearer {COC_API_KEY}", "Accept": "application/json"}

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
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
    log.info("Urush holati yangilandi (endTime=%s)", end_time)

# ── MEMBER TRACKING STATE ─────────────────────────────────────────────────────
_known_members: dict[str, str] = {}   # tag → name
_members_initialized: bool = False

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
        log.error("CoC so'rov xatosi %s: %s", path, exc)
    return None

async def get_current_war(s):
    return await coc_get(s, f"/clans/{encode_tag(CLAN_TAG)}/currentwar")

async def get_war_log(s):
    d = await coc_get(s, f"/clans/{encode_tag(CLAN_TAG)}/warlog?limit=5")
    return (d or {}).get("items", [])

async def get_player(s, tag):
    return await coc_get(s, f"/players/{encode_tag(tag)}")

async def get_clan_members(s):
    d = await coc_get(s, f"/clans/{encode_tag(CLAN_TAG)}/members?limit=50")
    return (d or {}).get("items", [])

# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_coc_time(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)

def time_left_str(sec: float) -> str:
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    return f"{h}s {m}d" if h else f"{m}d"

def stars_bar(n: int) -> str:
    return "⭐" * n + "☆" * (3 - n)

def result_emoji(r: str) -> str:
    return {"WIN": "🏆", "LOSE": "💀", "TIE": "🤝"}.get((r or "").upper(), "🏁")

def result_uz(r: str) -> str:
    return {"WIN": "G'ALABA", "LOSE": "MAG'LUBIYAT", "TIE": "DURRANG"}.get((r or "").upper(), "NOMA'LUM")

def role_uz(role: str) -> str:
    return {
        "LEADER":    "Rahbar",
        "COLEADER":  "Yordamchi rahbar",
        "ELDER":     "Katta a'zo",
        "MEMBER":    "A'zo",
        "NOT_MEMBER": "A'zo emas",
    }.get(role.upper(), role)

def find_defender_name(war: dict, tag: str) -> str:
    for m in war.get("opponent", {}).get("members", []):
        if m["tag"] == tag:
            return m["name"]
    return "Noma'lum"

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

def msg_three_star(attacker, defender, destruction, duration, war_type="Klan Urushi") -> str:
    mins, secs = divmod(duration, 60)
    dur = f"{mins}d {secs}s" if mins else f"{secs}s"
    hype = (
        "💯 Mukammal vayronagarchilik — beqiyos g'alaba!" if destruction == 100 else
        "🔥 Deyarli mukammal hujum — ajoyib!"              if destruction >= 95  else
        "👏 Zo'r hujum! Klan faxrlanadi!"
    )
    return (
        f"╔══════════════════════╗\n"
        f"🌟 *3 YULDUZ!* 🌟\n"
        f"╚══════════════════════╝\n\n"
        f"⚔️  *Urush turi:* {war_type}\n\n"
        f"🗡  *Hujumchi:* {attacker}\n"
        f"🏰  *Himoyachi:* {defender}\n\n"
        f"⭐⭐⭐  `{destruction:.0f}%` vayronagarchilik\n"
        f"⏱  *Vaqt:* {dur}\n\n"
        f"{hype}"
    )

def msg_war_status(war: dict) -> str:
    state = war.get("state", "unknown")
    clan, opp = war["clan"], war["opponent"]
    used  = clan.get("attacks", 0)
    total = war["teamSize"] * war.get("attacksPerMember", 2)
    emoji = {"preparation": "📋", "inWar": "⚔️", "warEnded": "🏁"}.get(state, "❓")
    state_uz = {"preparation": "TAYYORGARLIK", "inWar": "URUSH DAVOM ETMOQDA", "warEnded": "URUSH TUGADI"}.get(state, state.upper())

    lines = [
        f"{emoji} *Urush holati: {state_uz}*", "",
        f"🔵 *{clan['name']}*  vs  🔴 *{opp['name']}*",
        f"👥 {war['teamSize']}v{war['teamSize']}", "",
    ]

    if state == "preparation":
        start_time = parse_coc_time(war["startTime"])
        prep_left  = (start_time - datetime.now(timezone.utc)).total_seconds()
        lines.append(f"⏳ Urush boshlanishiga: *{time_left_str(prep_left)}*")
        lines.append(f"📣 Qo'shinlarni tayyorlang!")

    elif state == "inWar":
        rem = (parse_coc_time(war["endTime"]) - datetime.now(timezone.utc)).total_seconds()
        lines += [
            f"⭐ Yulduzlar:      `{clan['stars']}` — `{opp['stars']}`",
            f"💥 Vayronagarchilik: `{clan.get('destructionPercentage',0):.1f}%` — `{opp.get('destructionPercentage',0):.1f}%`",
            f"⚔️  Hujumlar:     `{used}/{total}` ({total-used} ta qoldi)",
        ]
        if rem > 0:
            lines.append(f"⏳ Qolgan vaqt: *{time_left_str(rem)}*")

    elif state == "warEnded":
        lines += [
            f"⭐ Yulduzlar:        `{clan['stars']}` — `{opp['stars']}`",
            f"💥 Vayronagarchilik: `{clan.get('destructionPercentage',0):.1f}%` — `{opp.get('destructionPercentage',0):.1f}%`",
            f"⚔️  Hujumlar:       `{used}/{total}`",
        ]

    return "\n".join(lines)

def msg_war_result(war: dict) -> str:
    clan, opp = war["clan"], war["opponent"]
    result = war.get("result", "unknown")
    attacks = sorted(
        [(m["name"], a["stars"], a["destructionPercentage"])
         for m in clan.get("members", []) for a in m.get("attacks", [])],
        key=lambda x: (x[1], x[2]), reverse=True
    )
    missed = [m["name"] for m in clan.get("members", []) if not m.get("attacks")]
    lines = [
        f"{result_emoji(result)} *URUSH TUGADI — {result_uz(result)}*", "",
        f"🔵 *{clan['name']}*",
        f"   ⭐`{clan['stars']}`  💥`{clan.get('destructionPercentage',0):.1f}%`  ⚔️`{clan['attacks']}` hujum", "",
        f"🔴 *{opp['name']}*",
        f"   ⭐`{opp['stars']}`  💥`{opp.get('destructionPercentage',0):.1f}%`  ⚔️`{opp['attacks']}` hujum", "",
    ]
    if attacks:
        lines.append("🏅 *Top 5 Hujum:*")
        for name, stars, dest in attacks[:5]:
            lines.append(f"   {stars_bar(stars)} `{dest:.0f}%` — {name}")
        lines.append("")
    if missed:
        lines.append(f"😴 *Hujum qilmaganlar ({len(missed)}):* " + ", ".join(missed))
    return "\n".join(lines)

def msg_warlog(entries: list) -> str:
    if not entries:
        return "📭 Urush tarixi bo'sh yoki yopiq."
    lines = ["📜 *Oxirgi 5 ta urush:*", ""]
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
    war_pref = "✅ Ishtirok etadi" if p.get("warPreference") == "IN" else "❌ Ishtirok etmaydi"
    role = role_uz(p.get("role", ""))
    clan_name = p.get("clan", {}).get("name", "Klan yo'q")
    league = p.get("league", {}).get("name", "Ligasiz")
    return "\n".join([
        f"👤 *{p['name']}* (`{p['tag']}`)",
        f"🏠 Qishloq Darvozasi *{p['townHallLevel']}*  |  🎖 Daraja {p['expLevel']}",
        f"🏆 Kuboklar: `{p['trophies']}`  (Eng ko'p: `{p['bestTrophies']}`)",
        f"🛡 Klan: *{clan_name}*  [{role}]",
        f"🥇 Liga: {league}",
        "",
        "👑 *Qahramonlar:*",
        f"   Barbar Qirol:    `{hv.get('Barbarian King', 0)}`",
        f"   Kamonchi Malika: `{hv.get('Archer Queen', 0)}`",
        f"   Buyuk Qorovul:   `{hv.get('Grand Warden', 0)}`",
        f"   Qirollik Chempion: `{hv.get('Royal Champion', 0)}`",
        "",
        f"⭐ Urush yulduzlari: `{p.get('warStars', 0)}`  |  Urush: {war_pref}",
        f"🤝 Hadya: `{p['donations']}` berildi / `{p['donationsReceived']}` olindi",
        f"🏰 Hujum g'alabalari: `{p.get('attackWins',0)}`  |  Mudofaa g'alabalari: `{p.get('defenseWins',0)}`",
    ])

def msg_members(members: list, title: str = None) -> str:
    if not members:
        return "📭 A'zolar topilmadi."

    role_icons = {
        "LEADER":   "👑",
        "COLEADER": "⚜️",
        "ELDER":    "🔰",
        "MEMBER":   "👤",
    }
    role_labels = {
        "LEADER":   "Leader",
        "COLEADER": "Co-Leader",
        "ELDER":    "Elder",
        "MEMBER":   "Member",
    }

    # Group by TH level descending
    from collections import defaultdict
    by_th = defaultdict(list)
    for m in members:
        by_th[m.get("townHallLevel", 0)].append(m)

    header = title or f"👥 *Klan A'zolari — {len(members)} ta*"
    lines  = [header, ""]

    for th in sorted(by_th.keys(), reverse=True):
        group = sorted(by_th[th], key=lambda m: m.get("trophies", 0), reverse=True)
        lines.append(f"🏠 *Town Hall {th}* ({len(group)} ta)")
        lines.append("─" * 24)
        for m in group:
            role  = m.get("role", "MEMBER").upper()
            icon  = role_icons.get(role, "👤")
            label = role_labels.get(role, role.title())
            troph = m.get("trophies", 0)
            don   = m.get("donations", 0)
            lines.append(
                f"{icon} *{m['name']}*  —  {label}\n"
                f"    🏆 {troph} kubok  |  🤝 {don} hadya"
            )
        lines.append("")

    return "\n".join(lines)

# ── TELEGRAM COMMANDS ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *CoC Klan Boti faol!*\n\n"
        "*Buyruqlar:*\n"
        "• /urush — joriy urush holati\n"
        "• /urushlog — oxirgi 5 ta urush\n"
        "• /oyinchi #TAG — o'yinchi ma'lumotlari\n"
        "• /azolar — barcha a'zolar (TH bo'yicha)\n"
        "• /azolar 14 — faqat TH14 a'zolari\n\n"
        "*Avtomatik xabarlar:*\n"
        "• ✅ A'zo klanga qo'shilganda\n"
        "• 👋 A'zo klandan chiqqanda\n"
        "• ⏰ 2 soat va 30 daqiqalik ogohlantirishlar\n"
        "• 🌟 3 yulduzli hujum bildirishnomasi\n"
        "• 🏁 Urush tugaganda natija e'lon qilinadi",
        parse_mode="Markdown",
    )

async def cmd_war(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        war = await get_current_war(s)
    if not war or war.get("state") in ("notInWar", None):
        await update.message.reply_text("😴 Klan hozir urushda emas.")
        return
    await update.message.reply_text(msg_war_status(war), parse_mode="Markdown")

async def cmd_warlog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        entries = await get_war_log(s)
    await update.message.reply_text(msg_warlog(entries), parse_mode="Markdown")

async def cmd_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Ishlatish: /oyinchi #TAG\nMisol: /oyinchi #2ABC123")
        return
    async with aiohttp.ClientSession() as s:
        p = await get_player(s, ctx.args[0])
    if not p:
        await update.message.reply_text("❌ O'yinchi topilmadi — tegni tekshiring.")
        return
    await update.message.reply_text(msg_player(p), parse_mode="Markdown")

async def cmd_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Optional TH filter: /azolar th14  or  /azolar 14
    th_filter = None
    if ctx.args:
        arg = ctx.args[0].lower().replace("th", "").strip()
        if arg.isdigit():
            th_filter = int(arg)

    await update.message.reply_text("⏳ A'zolar yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        members = await get_clan_members(s)
    if not members:
        await update.message.reply_text("❌ A'zolar ma'lumotini olishda xatolik.")
        return

    if th_filter:
        filtered = [m for m in members if m.get("townHallLevel") == th_filter]
        if not filtered:
            await update.message.reply_text(f"❌ TH{th_filter} darajali a'zolar topilmadi.")
            return
        title = f"🏠 *TH{th_filter} A'zolari — {len(filtered)} ta*"
        chunks = [filtered]
    else:
        title = None
        # Split into groups of 15 to avoid message too long
        chunks = [members[i:i+15] for i in range(0, len(members), 15)]

    first = True
    for chunk in chunks:
        t = msg_members(chunk, title if first else "")
        await update.message.reply_text(t, parse_mode="Markdown")
        first = False

# ── WAR MONITOR LOOP ──────────────────────────────────────────────────────────

async def war_monitor(bot: Bot):
    global _known_members, _members_initialized
    log.info("Urush monitoru boshlandi (har %ds).", POLL_INTERVAL)
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                war     = await get_current_war(s)
                members = await get_clan_members(s)

            # ── Join / Leave tracking ─────────────────────────────────────
            if members:
                current = {m["tag"]: m["name"] for m in members}

                if not _members_initialized:
                    _known_members       = current
                    _members_initialized = True
                    log.info("A'zolar boshlang'ich holati saqlandi (%d ta).", len(_known_members))
                else:
                    joined_tags = current.keys()  - _known_members.keys()
                    left_tags   = _known_members.keys() - current.keys()

                    for tag in joined_tags:
                        name = current[tag]
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"✅ *{name}* klanga qo'shildi!\n🏠 Xush kelibsiz!",
                            parse_mode="Markdown",
                        )
                        log.info("Qo'shildi: %s", name)

                    for tag in left_tags:
                        name = _known_members[tag]
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"👋 *{name}* klandan chiqib ketdi.",
                            parse_mode="Markdown",
                        )
                        log.info("Chiqdi: %s", name)

                    _known_members = current

            if war:
                state = war.get("state")

                if state == "inWar":
                    end_time = war["endTime"]
                    if _state["war_end_time"] != end_time:
                        _reset_war_state(end_time)

                    remaining    = (parse_coc_time(end_time) - datetime.now(timezone.utc)).total_seconds()
                    clan, opp    = war["clan"], war["opponent"]
                    attacks_left = war["teamSize"] * war.get("attacksPerMember", 2) - clan.get("attacks", 0)

                    # 3-yulduz bildirishnomasi
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
                        log.info("3⭐ yuborildi: %s", hit["attacker_name"])

                    # 2 soatlik ogohlantirish
                    if 0 < remaining <= 7200 and not _state["reminded_2h"]:
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"⏰ *Urush tugashiga ~2 soat qoldi!*\n\n"
                            f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage',0):.1f}%`\n"
                            f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage',0):.1f}%`\n\n"
                            f"⚔️ Qolgan hujumlar: *{attacks_left}*\n"
                            f"📣 Hujum qilishni unutmang!",
                            parse_mode="Markdown",
                        )
                        _state["reminded_2h"] = True
                        log.info("2 soatlik ogohlantirish yuborildi.")

                    # 30 daqiqalik ogohlantirish
                    if 0 < remaining <= 1800 and not _state["reminded_30m"]:
                        await bot.send_message(
                            TELEGRAM_CHAT,
                            f"🚨 *OXIRGI OGOHLANTIRISH — Urush tugashiga 30 daqiqa qoldi!*\n\n"
                            f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage',0):.1f}%`\n"
                            f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage',0):.1f}%`\n\n"
                            f"⚔️ Qolgan hujumlar: *{attacks_left}*\n"
                            f"⚠️ Oxirgi imkoniyat — *HOZIROQ* hujum qiling!",
                            parse_mode="Markdown",
                        )
                        _state["reminded_30m"] = True
                        log.info("30 daqiqalik ogohlantirish yuborildi.")

                elif state == "warEnded":
                    end_time = war.get("endTime", "")
                    if _state["war_end_time"] != end_time:
                        _reset_war_state(end_time)
                    if not _state["posted_result"]:
                        await bot.send_message(TELEGRAM_CHAT, msg_war_result(war), parse_mode="Markdown")
                        _state["posted_result"] = True
                        log.info("Urush natijasi e'lon qilindi.")

        except Exception as exc:
            log.error("Monitor xatosi: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)

# ── MAIN ──────────────────────────────────────────────────────────────────────

async def run():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("urush",    cmd_war))
    app.add_handler(CommandHandler("urushlog", cmd_warlog))
    app.add_handler(CommandHandler("oyinchi",  cmd_player))
    app.add_handler(CommandHandler("azolar",   cmd_members))

    async with app:
        await app.initialize()
        await app.start()
        monitor_task = asyncio.create_task(war_monitor(app.bot))
        log.info("Bot va urush monitoru ishlamoqda...")
        await app.updater.start_polling(drop_pending_updates=True)
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            monitor_task.cancel()
            await app.updater.stop()
            await app.stop()


if __name__ == "__main__":
    asyncio.run(run())