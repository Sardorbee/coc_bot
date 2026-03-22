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
    return f"{h}s {m}d" if h else f"{m}d"


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


# ── Progress bar ──────────────────────────────────────────────────────────────

def progress_bar(current: int, total: int, length: int = 12) -> str:
    """Visual progress bar:  ████████░░░░  75%"""
    if total == 0:
        return "░" * length + "  0%"
    pct   = current / total
    filled = round(pct * length)
    bar   = "█" * filled + "░" * (length - filled)
    return f"{bar}  {pct*100:.0f}%"


# ── Upgrade tracker /qurol ────────────────────────────────────────────────────

def upgrade_tracker(p: dict) -> str:
    """
    Shows troops/spells/heroes with current vs max level.
    Groups into: maxed ✅ and not maxed 🔧.
    Overall % of base finished.
    """
    th = p["townHallLevel"]

    categories = [
        ("🗡 Qo'shinlar",  [i for i in p.get("troops", [])  if i.get("village") == "HOME_VILLAGE"]),
        ("✨ Sehrlar",     [i for i in p.get("spells", [])  if i.get("village") == "HOME_VILLAGE"]),
        ("👑 Qahramonlar", [i for i in p.get("heroes", [])  if i.get("village") == "HOME_VILLAGE"]),
    ]

    total_levels  = 0
    max_levels    = 0
    total_items   = 0
    maxed_items   = 0
    section_lines = []

    for label, items in categories:
        if not items:
            continue
        not_maxed = []
        cat_total = 0
        cat_max   = 0

        for item in items:
            lvl  = item.get("level", 0)
            mxl  = item.get("maxLevel", 1)
            cat_total    += lvl
            cat_max      += mxl
            total_levels += lvl
            max_levels   += mxl
            total_items  += 1
            if lvl >= mxl:
                maxed_items += 1
            else:
                not_maxed.append(
                    f"  🔧 {item['name']}: `{lvl}/{mxl}`  {progress_bar(lvl, mxl, 8)}"
                )

        cat_pct = (cat_total / cat_max * 100) if cat_max else 0
        section_lines.append(f"\n{label} — `{cat_pct:.0f}%` to'liq")
        section_lines.append("─" * 22)
        if not_maxed:
            section_lines.extend(not_maxed)
        else:
            section_lines.append("  ✅ Barchasi maksimal!")

    overall_pct = (total_levels / max_levels * 100) if max_levels else 0
    bar         = progress_bar(total_levels, max_levels, 14)

    header = [
        f"🔨 *Yangilanish Kuzatuvchi*",
        f"👤 *{p['name']}*  —  TH{th}",
        "",
        f"📊 *Umumiy holat:*",
        f"`{bar}`",
        f"✅ Maksimal: `{maxed_items}/{total_items}` ta",
        f"🔧 Qolgan:   `{total_items - maxed_items}` ta",
    ]

    return "\n".join(header + section_lines)


# ── Achievements /yutuq ───────────────────────────────────────────────────────

def achievements(p: dict) -> str:
    """Shows player achievements with star count and completion %."""
    achs = [a for a in p.get("achievements", []) if a.get("village") == "HOME_VILLAGE"]
    if not achs:
        return "❌ Yutuqlar topilmadi."

    completed   = [a for a in achs if a.get("stars", 0) >= 3]
    in_progress = [a for a in achs if a.get("stars", 0) < 3]

    lines = [
        f"🏅 *Yutuqlar — {p['name']}*  (TH{p['townHallLevel']})",
        f"✅ Tugallangan: `{len(completed)}/{len(achs)}`  "
        f"{progress_bar(len(completed), len(achs), 10)}",
        "",
    ]

    if in_progress:
        lines.append("⏳ *Davom etayotganlar:*")
        lines.append("─" * 22)
        for a in sorted(in_progress, key=lambda x: x.get("stars", 0), reverse=True):
            stars = "⭐" * a.get("stars", 0) + "☆" * (3 - a.get("stars", 0))
            val   = a.get("value", 0)
            tgt   = a.get("target", 1)
            pct   = min(val / tgt * 100, 100) if tgt else 0
            lines.append(
                f"{stars} *{a['name']}*\n"
                f"   `{val:,}/{tgt:,}`  {progress_bar(val, tgt, 8)}"
            )

    return "\n".join(lines)


# ── Builder Base /builder ─────────────────────────────────────────────────────

def builder_base(p: dict) -> str:
    """Builder Base stats: BH level, BB trophies, league, hero, troops."""
    bh_lvl   = p.get("builderHallLevel", "?")
    bb_troph = p.get("builderBaseTrophies", 0)
    best_bb  = p.get("bestBuilderBaseTrophies", 0)
    bb_league = p.get("builderBaseLeague", {}).get("name", "Ligasiz")

    bb_heroes = {
        h["name"]: h
        for h in p.get("heroes", [])
        if h.get("village") == "BUILDER_BASE"
    }
    bb_troops = [
        t for t in p.get("troops", [])
        if t.get("village") == "BUILDER_BASE"
    ]

    bm = bb_heroes.get("Battle Machine", {})
    bc = bb_heroes.get("Battle Copter", {})

    not_maxed = [
        f"  🔧 {t['name']}: `{t['level']}/{t['maxLevel']}`  {progress_bar(t['level'], t['maxLevel'], 8)}"
        for t in bb_troops if t.get("level", 0) < t.get("maxLevel", 1)
    ]

    total  = sum(t.get("maxLevel", 1) for t in bb_troops)
    current = sum(t.get("level", 0) for t in bb_troops)

    lines = [
        f"🏗 *Builder Base — {p['name']}*",
        f"🏠 Builder Hall: *{bh_lvl}*",
        f"🏆 Kuboklar: `{bb_troph}`  (Eng ko'p: `{best_bb}`)",
        f"🥇 Liga: {bb_league}",
        "",
        f"🤖 Battle Machine: `{bm.get('level', 0)}/{bm.get('maxLevel', '?')}`",
        f"🚁 Battle Copter:  `{bc.get('level', 0)}/{bc.get('maxLevel', '?')}`",
        "",
        f"📊 *Qo'shinlar:* {progress_bar(current, total, 12)}",
    ]

    if not_maxed:
        lines.append("─" * 22)
        lines.extend(not_maxed[:10])
        if len(not_maxed) > 10:
            lines.append(f"  ... va yana {len(not_maxed) - 10} ta")

    return "\n".join(lines)


# ── Player comparison /solishtir ──────────────────────────────────────────────

def compare_players(p1: dict, p2: dict) -> str:
    """Side-by-side comparison of two players."""

    def hv(p: dict, name: str) -> int:
        for h in p.get("heroes", []):
            if h["name"] == name and h.get("village") == "HOME_VILLAGE":
                return h.get("level", 0)
        return 0

    def max_pct(p: dict) -> float:
        items  = (
            [i for i in p.get("troops", [])  if i.get("village") == "HOME_VILLAGE"] +
            [i for i in p.get("spells", [])  if i.get("village") == "HOME_VILLAGE"] +
            [i for i in p.get("heroes", [])  if i.get("village") == "HOME_VILLAGE"]
        )
        total   = sum(i.get("maxLevel", 1) for i in items)
        current = sum(i.get("level", 0)    for i in items)
        return (current / total * 100) if total else 0

    def win(a, b, higher=True) -> tuple[str, str]:
        """Returns (marker_for_a, marker_for_b). Winner gets 🟢, loser 🔴."""
        if a == b:
            return "🟡", "🟡"
        if (a > b) == higher:
            return "🟢", "🔴"
        return "🔴", "🟢"

    th1, th2 = p1["townHallLevel"], p2["townHallLevel"]
    tr1, tr2 = p1["trophies"],      p2["trophies"]
    ws1, ws2 = p1.get("warStars", 0), p2.get("warStars", 0)
    dn1, dn2 = p1.get("donations", 0), p2.get("donations", 0)
    aw1, aw2 = p1.get("attackWins", 0), p2.get("attackWins", 0)
    bk1, bk2 = hv(p1, "Barbarian King"),  hv(p2, "Barbarian King")
    aq1, aq2 = hv(p1, "Archer Queen"),    hv(p2, "Archer Queen")
    gw1, gw2 = hv(p1, "Grand Warden"),    hv(p2, "Grand Warden")
    rc1, rc2 = hv(p1, "Royal Champion"),  hv(p2, "Royal Champion")
    mx1, mx2 = max_pct(p1), max_pct(p2)

    def row(label, a, b, higher=True, fmt=lambda x: x) -> str:
        ma, mb = win(a, b, higher)
        return f"{ma} `{fmt(a):<10}` *{label}* `{fmt(b):>10}` {mb}"

    lines = [
        f"⚔️ *O'yinchi Solishtirish*",
        f"",
        f"🔵 *{p1['name']}*  vs  🔴 *{p2['name']}*",
        f"",
        f"{'─'*30}",
        row("TH",            th1,  th2,  fmt=lambda x: f"TH{x}"),
        row("Kuboklar",      tr1,  tr2,  fmt=lambda x: f"{x:,}"),
        row("Urush yulduz",  ws1,  ws2,  fmt=lambda x: f"{x:,}"),
        row("Hadya",         dn1,  dn2,  fmt=lambda x: f"{x:,}"),
        row("Hujum g'alaba", aw1,  aw2,  fmt=lambda x: f"{x:,}"),
        f"{'─'*30}",
        f"👑 *Qahramonlar:*",
        row("Barbar Qirol",  bk1,  bk2,  fmt=lambda x: f"Lv{x}"),
        row("Kamonchi M.",   aq1,  aq2,  fmt=lambda x: f"Lv{x}"),
        row("B. Qorovul",    gw1,  gw2,  fmt=lambda x: f"Lv{x}"),
        row("Q. Chempion",   rc1,  rc2,  fmt=lambda x: f"Lv{x}"),
        f"{'─'*30}",
        row("Max %",         mx1,  mx2,  fmt=lambda x: f"{x:.1f}%"),
        f"",
        f"🟢 Yaxshiroq  🟡 Teng  🔴 Kamroq",
    ]
    return "\n".join(lines)