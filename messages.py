"""
messages.py — Barcha Telegram xabar shablonlari (o'zbek tilida)
"""

from collections import defaultdict
from datetime import datetime, timezone


# ── Util ──────────────────────────────────────────────────────────────────────

def parse_coc_time(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)


def time_left(sec: float) -> str:
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    return f"{h}soat {m} daqiqa" if h else f"{m} daqiqa"


def stars_bar(n: int) -> str:
    return "⭐" * n + "☆" * (3 - n)


def result_emoji(r: str) -> str:
    return {"WIN": "🏆", "LOSE": "💀", "TIE": "🤝"}.get((r or "").upper(), "🏁")


def result_uz(r: str) -> str:
    return {
        "WIN":  "G'ALABA",
        "LOSE": "MAG'LUBIYAT",
        "TIE":  "DURRANG",
    }.get((r or "").upper(), "NOMA'LUM")


ROLE_ICONS = {
    "LEADER":   "👑",
    "COLEADER": "⚜️",
    "ELDER":    "🔰",
    "MEMBER":   "👤",
}

ROLE_LABELS = {
    "LEADER":   "Leader",
    "COLEADER": "Co-Leader",
    "ELDER":    "Elder",
    "MEMBER":   "Member",
}

STATE_LABELS = {
    "preparation": "TAYYORGARLIK",
    "inWar":       "URUSH DAVOM ETMOQDA",
    "warEnded":    "URUSH TUGADI",
}

STATE_EMOJI = {
    "preparation": "📋",
    "inWar":       "⚔️",
    "warEnded":    "🏁",
}


# ── War messages ──────────────────────────────────────────────────────────────

def war_preparation(war: dict) -> str:
    clan, opp  = war["clan"], war["opponent"]
    start_time = parse_coc_time(war["startTime"])
    prep_left  = (start_time - datetime.now(timezone.utc)).total_seconds()
    return (
        f"📋 *URUSH TOPILDI — TAYYORGARLIK BOSHLANDI!*\n\n"
        f"🔵 *{clan['name']}*  vs  🔴 *{opp['name']}*\n"
        f"👥 {war['teamSize']}v{war['teamSize']}\n\n"
        f"⏳ Urush boshlanishiga: *{time_left(prep_left)}*\n\n"
        f"🏹 Hujum strategiyangizni tayyorlang!"
    )


def war_started(war: dict) -> str:
    clan, opp = war["clan"], war["opponent"]
    remaining = (parse_coc_time(war["endTime"]) - datetime.now(timezone.utc)).total_seconds()
    return (
        f"⚔️ *URUSH BOSHLANDI!*\n\n"
        f"🔵 *{clan['name']}*  vs  🔴 *{opp['name']}*\n"
        f"👥 {war['teamSize']}v{war['teamSize']}\n\n"
        f"⏳ Urush davomiyligi: *{time_left(remaining)}*\n\n"
        f"🏹 Hujum qilish vaqti keldi — omad!"
    )


def war_reminder_2h(war: dict, attacks_left: int) -> str:
    clan, opp = war["clan"], war["opponent"]
    return (
        f"⏰ *Urush tugashiga ~2 soat qoldi!*\n\n"
        f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage', 0):.1f}%`\n"
        f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage', 0):.1f}%`\n\n"
        f"⚔️ Qolgan hujumlar: *{attacks_left}*\n"
        f"📣 Hujum qilishni unutmang!"
    )


def war_reminder_30m(war: dict, attacks_left: int) -> str:
    clan, opp = war["clan"], war["opponent"]
    return (
        f"🚨 *OXIRGI OGOHLANTIRISH — Urush tugashiga 30 daqiqa qoldi!*\n\n"
        f"🔵 {clan['name']}: ⭐`{clan['stars']}` 💥`{clan.get('destructionPercentage', 0):.1f}%`\n"
        f"🔴 {opp['name']}: ⭐`{opp['stars']}` 💥`{opp.get('destructionPercentage', 0):.1f}%`\n\n"
        f"⚔️ Qolgan hujumlar: *{attacks_left}*\n"
        f"⚠️ Oxirgi imkoniyat — *HOZIROQ* hujum qiling!"
    )


def war_result(war: dict) -> str:
    clan, opp = war["clan"], war["opponent"]
    result    = war.get("result", "unknown")

    attacks = sorted(
        [
            (m["name"], a["stars"], a["destructionPercentage"])
            for m in clan.get("members", [])
            for a in m.get("attacks", [])
        ],
        key=lambda x: (x[1], x[2]),
        reverse=True,
    )
    missed = [m["name"] for m in clan.get("members", []) if not m.get("attacks")]

    lines = [
        f"{result_emoji(result)} *URUSH TUGADI — {result_uz(result)}*", "",
        f"🔵 *{clan['name']}*",
        f"   ⭐`{clan['stars']}`  💥`{clan.get('destructionPercentage', 0):.1f}%`  ⚔️`{clan['attacks']}` hujum",
        "",
        f"🔴 *{opp['name']}*",
        f"   ⭐`{opp['stars']}`  💥`{opp.get('destructionPercentage', 0):.1f}%`  ⚔️`{opp['attacks']}` hujum",
        "",
    ]
    if attacks:
        lines.append("🏅 *Top 5 Hujum:*")
        for name, s, dest in attacks[:5]:
            lines.append(f"   {stars_bar(s)} `{dest:.0f}%` — {name}")
        lines.append("")
    if missed:
        lines.append(f"😴 *Hujum qilmaganlar ({len(missed)}):* " + ", ".join(missed))

    return "\n".join(lines)


def war_status(war: dict) -> str:
    state = war.get("state", "unknown")
    clan, opp = war["clan"], war["opponent"]
    used  = clan.get("attacks", 0)
    total = war["teamSize"] * war.get("attacksPerMember", 2)
    emoji = STATE_EMOJI.get(state, "❓")
    label = STATE_LABELS.get(state, state.upper())

    lines = [
        f"{emoji} *Urush holati: {label}*", "",
        f"🔵 *{clan['name']}*  vs  🔴 *{opp['name']}*",
        f"👥 {war['teamSize']}v{war['teamSize']}", "",
    ]

    if state == "preparation":
        prep_left = (parse_coc_time(war["startTime"]) - datetime.now(timezone.utc)).total_seconds()
        if prep_left > 0:
            lines.append(f"⏳ Urush boshlanishiga: *{time_left(prep_left)}*")
            lines.append("🏹 Hujum strategiyangizni tayyorlang!")
        else:
            lines.append("⚔️ Urush boshlanishi kutilmoqda...")
            lines.append("🔄 Bir oz kutib /urush ni qayta yuboring")

    elif state == "inWar":
        rem = (parse_coc_time(war["endTime"]) - datetime.now(timezone.utc)).total_seconds()
        lines += [
            f"⭐ Yulduzlar:        `{clan['stars']}` — `{opp['stars']}`",
            f"💥 Vayronagarchilik: `{clan.get('destructionPercentage', 0):.1f}%` — `{opp.get('destructionPercentage', 0):.1f}%`",
            f"⚔️  Hujumlar:       `{used}/{total}` ({total - used} ta qoldi)",
        ]
        if rem > 0:
            lines.append(f"⏳ Qolgan vaqt: *{time_left(rem)}*")

    elif state == "warEnded":
        lines += [
            f"⭐ Yulduzlar:        `{clan['stars']}` — `{opp['stars']}`",
            f"💥 Vayronagarchilik: `{clan.get('destructionPercentage', 0):.1f}%` — `{opp.get('destructionPercentage', 0):.1f}%`",
            f"⚔️  Hujumlar:       `{used}/{total}`",
        ]

    return "\n".join(lines)


def three_star(attacker: str, defender: str, destruction: float,
               duration: int, war_type: str = "Klan Urushi") -> str:
    mins, secs = divmod(duration, 60)
    dur  = f"{mins}d {secs}s" if mins else f"{secs}s"
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


def war_log(entries: list) -> str:
    if not entries:
        return "📭 Urush tarixi bo'sh yoki yopiq."
    lines = ["📜 *Oxirgi 5 ta urush:*", ""]
    for i, w in enumerate(entries[:5], 1):
        c, o = w.get("clan", {}), w.get("opponent", {})
        lines.append(
            f"{i}. {result_emoji(w.get('result', '?'))} vs *{o.get('name', '?')}*  "
            f"⭐`{c.get('stars', '?')}:{o.get('stars', '?')}`  "
            f"💥`{c.get('destructionPercentage', 0):.0f}%`"
        )
    return "\n".join(lines)


# ── Player message ────────────────────────────────────────────────────────────

def player_card(p: dict) -> str:
    hv       = {h["name"]: h["level"] for h in p.get("heroes", []) if h.get("village") == "HOME_VILLAGE"}
    war_pref = "✅ Ishtirok etadi" if p.get("warPreference") == "IN" else "❌ Ishtirok etmaydi"
    role     = ROLE_LABELS.get(p.get("role", "").upper(), p.get("role", ""))

    return "\n".join([
        f"👤 *{p['name']}* (`{p['tag']}`)",
        f"🏠 Town Hall *{p['townHallLevel']}*  |  🎖 Daraja {p['expLevel']}",
        f"🏆 Kuboklar: `{p['trophies']}`  (Eng ko'p: `{p['bestTrophies']}`)",
        f"🛡 Klan: *{p.get('clan', {}).get('name', 'Klan yoq')}*  [{role}]",
        f"🥇 Liga: {p.get('league', {}).get('name', 'Ligasiz')}",
        "",
        "👑 *Qahramonlar:*",
        f"   Barbar Qirol:      `{hv.get('Barbarian King', 0)}`",
        f"   Kamonchi Malika:   `{hv.get('Archer Queen', 0)}`",
        f"   Buyuk Qorovul:     `{hv.get('Grand Warden', 0)}`",
        f"   Qirollik Chempion: `{hv.get('Royal Champion', 0)}`",
        "",
        f"⭐ Urush yulduzlari: `{p.get('warStars', 0)}`  |  Urush: {war_pref}",
        f"🤝 Hadya: `{p['donations']}` berildi / `{p['donationsReceived']}` olindi",
        f"🏰 Hujum: `{p.get('attackWins', 0)}`  |  Mudofaa: `{p.get('defenseWins', 0)}`",
    ])


# ── Members list ──────────────────────────────────────────────────────────────

def members_list(members: list, title: str | None = None) -> str:
    if not members:
        return "📭 A'zolar topilmadi."

    by_th: dict[int, list] = defaultdict(list)
    for m in members:
        by_th[m.get("townHallLevel", 0)].append(m)

    lines = [title or f"👥 *Klan A'zolari — {len(members)} ta*", ""]

    for th in sorted(by_th.keys(), reverse=True):
        group = sorted(by_th[th], key=lambda m: m.get("trophies", 0), reverse=True)
        lines.append(f"🏠 *Town Hall {th}* ({len(group)} ta)")
        lines.append("─" * 24)
        for m in group:
            role  = m.get("role", "MEMBER").upper()
            icon  = ROLE_ICONS.get(role, "👤")
            label = ROLE_LABELS.get(role, role.title())
            lines.append(
                f"{icon} *{m['name']}*  —  {label}\n"
                f"    🏆 {m.get('trophies', 0)} kubok  |  🤝 {m.get('donations', 0)} hadya"
            )
        lines.append("")

    return "\n".join(lines)
