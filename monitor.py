"""
monitor.py — Urush monitoru va keep-alive loop
"""

import asyncio
import logging

import aiohttp
from telegram import Bot

import messages as msg
import state
from api import fetch_clan_members, fetch_current_war
from config import POLL_INTERVAL, RENDER_URL, TELEGRAM_CHAT

log = logging.getLogger(__name__)


# ── Member join/leave tracker ─────────────────────────────────────────────────

async def _check_members(bot: Bot, session: aiohttp.ClientSession):
    members = await fetch_clan_members(session)
    if not members:
        return

    current      = {m["tag"]: m["name"] for m in members}
    member_count = len(current)

    if not state.members_initialized:
        state.init_members(current)
        return

    joined, left = state.diff_members(current)

    for tag in joined:
        name = current[tag]

        # Fetch full player profile for the new member
        from api import fetch_player
        player = await fetch_player(session, tag)
        profile_text = msg.player_card(player) if player else ""

        join_text = (
            f"✅ *{name}* klanga qo'shildi!\n"
            f"🏠 Xush kelibsiz!\n\n"
            f"👥 Klan a'zolari endi *{member_count}* ta bo'ldi!"
        )
        await bot.send_message(TELEGRAM_CHAT, join_text, parse_mode="Markdown")

        if profile_text:
            await bot.send_message(
                TELEGRAM_CHAT,
                f"👤 *Yangi a'zo haqida:*\n\n{profile_text}",
                parse_mode="Markdown",
            )

        log.info("Qo'shildi: %s (%s), jami: %d", name, tag, member_count)

    for tag in left:
        name         = state.members[tag]
        member_count_after = member_count  # already updated after leave
        await bot.send_message(
            TELEGRAM_CHAT,
            f"👋 *{name}* klandan chiqib ketdi.\n\n"
            f"👥 Klan a'zolari endi *{member_count_after}* ta bo'ldi.",
            parse_mode="Markdown",
        )
        log.info("Chiqdi: %s (%s), jami: %d", name, tag, member_count_after)

    state.update_members(current)


# ── War event tracker ─────────────────────────────────────────────────────────

def _find_new_3stars(war: dict) -> list:
    hits = []
    for m in war.get("clan", {}).get("members", []):
        for atk in m.get("attacks", []):
            if atk["stars"] == 3:
                key = f"{atk['attackerTag']}-{atk['defenderTag']}"
                if key not in state.war["three_star_seen"]:
                    hits.append({
                        "key":           key,
                        "attacker_name": m["name"],
                        "defender_tag":  atk["defenderTag"],
                        "destruction":   atk["destructionPercentage"],
                        "duration":      atk.get("duration", 0),
                    })
    return hits


def _find_defender_name(war: dict, tag: str) -> str:
    for m in war.get("opponent", {}).get("members", []):
        if m["tag"] == tag:
            return m["name"]
    return "Noma'lum"


async def _check_war(bot: Bot, session: aiohttp.ClientSession):
    war = await fetch_current_war(session)
    if not war:
        return

    war_state = war.get("state")
    war_id    = war.get("preparationStartTime", war.get("endTime", ""))

    # ── Preparation ───────────────────────────────────────────────────────────
    if war_state == "preparation":
        if state.is_new_war(war_id):
            state.reset_war(war_id)
        if not state.war["preparation_announced"]:
            await bot.send_message(TELEGRAM_CHAT, msg.war_preparation(war), parse_mode="Markdown")
            state.war["preparation_announced"] = True
            log.info("Tayyorgarlik e'lon qilindi.")

    # ── In War ────────────────────────────────────────────────────────────────
    elif war_state == "inWar":
        if state.is_new_war(war_id):
            state.reset_war(war_id)
            state.war["preparation_announced"] = True   # skip re-announcing prep

        clan          = war["clan"]
        opp           = war["opponent"]
        end_time      = war["endTime"]
        from messages import parse_coc_time
        from datetime import datetime, timezone
        remaining     = (parse_coc_time(end_time) - datetime.now(timezone.utc)).total_seconds()
        attacks_left  = war["teamSize"] * war.get("attacksPerMember", 2) - clan.get("attacks", 0)

        # War started announcement
        if not state.war["war_started_announced"]:
            await bot.send_message(TELEGRAM_CHAT, msg.war_started(war), parse_mode="Markdown")
            state.war["war_started_announced"] = True
            log.info("Urush boshlanishi e'lon qilindi.")

        # 3-star alerts
        for hit in _find_new_3stars(war):
            defender = _find_defender_name(war, hit["defender_tag"])
            await bot.send_message(
                TELEGRAM_CHAT,
                msg.three_star(hit["attacker_name"], defender, hit["destruction"], hit["duration"]),
                parse_mode="Markdown",
            )
            state.war["three_star_seen"].add(hit["key"])
            log.info("3 yulduz: %s -> %s", hit["attacker_name"], defender)

        # 2-hour reminder
        if 0 < remaining <= 7200 and not state.war["reminded_2h"]:
            await bot.send_message(TELEGRAM_CHAT, msg.war_reminder_2h(war, attacks_left), parse_mode="Markdown")
            state.war["reminded_2h"] = True
            log.info("2 soatlik ogohlantirish yuborildi.")

        # 30-minute reminder
        if 0 < remaining <= 1800 and not state.war["reminded_30m"]:
            await bot.send_message(TELEGRAM_CHAT, msg.war_reminder_30m(war, attacks_left), parse_mode="Markdown")
            state.war["reminded_30m"] = True
            log.info("30 daqiqalik ogohlantirish yuborildi.")

    # ── War Ended ─────────────────────────────────────────────────────────────
    elif war_state == "warEnded":
        if state.is_new_war(war_id):
            state.reset_war(war_id)
            state.war["preparation_announced"] = True
            state.war["war_started_announced"] = True
        if not state.war["posted_result"]:
            await bot.send_message(TELEGRAM_CHAT, msg.war_result(war), parse_mode="Markdown")
            state.war["posted_result"] = True
            log.info("Urush natijasi e'lon qilindi.")


# ── Main monitor loop ─────────────────────────────────────────────────────────

async def war_monitor(bot: Bot):
    log.info("Urush monitoru boshlandi (har %ds).", POLL_INTERVAL)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await _check_members(bot, session)
                await _check_war(bot, session)
        except Exception as exc:
            log.error("Monitor xatosi: %s", exc)
        await asyncio.sleep(POLL_INTERVAL)


# ── Keep-alive ────────────────────────────────────────────────────────────────

async def keep_alive():
    """Render free tier'ni uyquga ketmaslik uchun har 10 daqiqada o'zini ping qiladi."""
    if not RENDER_URL:
        log.info("RENDER_URL yo'q — keep-alive o'chirildi.")
        return
    await asyncio.sleep(30)  # server to'liq ishga tushishini kutish
    log.info("Keep-alive boshlandi → %s", RENDER_URL)
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(RENDER_URL, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    log.info("Keep-alive ping → HTTP %s", r.status)
        except Exception as exc:
            log.warning("Keep-alive xatosi: %s", exc)
        await asyncio.sleep(600)  # 10 daqiqa