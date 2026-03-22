"""
callbacks.py — Inline tugma callback handlerlari
"""

import logging

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import messages as msg
from api import fetch_clan_members, fetch_current_war, fetch_war_log
from handlers import main_menu_keyboard

log = logging.getLogger(__name__)

BACK_BTN  = InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_start")
BACK_ROW  = [[BACK_BTN]]


async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "war":
        await _show_war(query)

    elif data == "warlog":
        await _show_warlog(query)

    elif data == "azolar":
        await _show_th_picker(query)

    elif data == "azolar_all":
        await _show_all_members(query)

    elif data.startswith("th_"):
        th = int(data.split("_")[1])
        await _show_members_by_th(query, th)

    elif data == "help":
        await _show_help(query)

    elif data == "back_start":
        await query.edit_message_text(
            "⚔️ *CoC Klan Boti faol!*\n\n"
            "Quyidagi tugmalardan foydalaning yoki buyruq yozing:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


# ── Private helpers ───────────────────────────────────────────────────────────

async def _show_war(query):
    async with aiohttp.ClientSession() as s:
        war = await fetch_current_war(s)
    if not war or war.get("state") in ("notInWar", None):
        await query.edit_message_text(
            "😴 Klan hozir urushda emas.",
            reply_markup=InlineKeyboardMarkup(BACK_ROW),
        )
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Yangilash", callback_data="war")],
        BACK_ROW[0],
    ])
    await query.edit_message_text(
        msg.war_status(war),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def _show_warlog(query):
    async with aiohttp.ClientSession() as s:
        entries = await fetch_war_log(s)
    await query.edit_message_text(
        msg.war_log(entries),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(BACK_ROW),
    )


async def _show_th_picker(query):
    await query.edit_message_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        members = await fetch_clan_members(s)
    if not members:
        await query.edit_message_text(
            "❌ A'zolar ma'lumotini olishda xatolik.",
            reply_markup=InlineKeyboardMarkup(BACK_ROW),
        )
        return
    ths = sorted({m.get("townHallLevel", 0) for m in members}, reverse=True)
    th_btns = [InlineKeyboardButton(f"TH{th}", callback_data=f"th_{th}") for th in ths]
    rows = [th_btns[i:i + 4] for i in range(0, len(th_btns), 4)]
    rows.append([InlineKeyboardButton("👥 Barchasi", callback_data="azolar_all")])
    rows.append(BACK_ROW[0])
    await query.edit_message_text(
        f"🏠 *Qaysi TH ko'rishni xohlaysiz?*\nJami: {len(members)} ta a'zo",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def _show_all_members(query):
    await query.edit_message_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        members = await fetch_clan_members(s)
    text = msg.members_list(members)
    keyboard = InlineKeyboardMarkup(BACK_ROW)
    if len(text) > 4000:
        await query.edit_message_text(
            "📋 Ro'yxat juda uzun. Iltimos /azolar buyrug'ini ishlating.",
            reply_markup=keyboard,
        )
    else:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def _show_members_by_th(query, th: int):
    await query.edit_message_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        members = await fetch_clan_members(s)
    filtered = [m for m in members if m.get("townHallLevel") == th]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 TH tanlash", callback_data="azolar")]])
    if not filtered:
        await query.edit_message_text(f"❌ TH{th} darajali a'zolar topilmadi.", reply_markup=keyboard)
        return
    await query.edit_message_text(
        msg.members_list(filtered, title=f"🏠 *TH{th} A'zolari — {len(filtered)} ta*"),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def _show_help(query):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Urush", callback_data="war"),
            InlineKeyboardButton("📜 Tarix", callback_data="warlog"),
            InlineKeyboardButton("👥 A'zolar", callback_data="azolar"),
        ],
        BACK_ROW[0],
    ])
    await query.edit_message_text(
        "*Buyruqlar:*\n"
        "• /urush — joriy urush holati\n"
        "• /urushlog — oxirgi 5 ta urush\n"
        "• /oyinchi #TAG — o'yinchi ma'lumotlari\n"
        "• /azolar — barcha a'zolar\n"
        "• /azolar 14 — TH14 a'zolari\n\n"
        "*Avtomatik:*\n"
        "• ✅ Klanga qo'shilish / 👋 Chiqish\n"
        "• ⏰ Urush ogohlantirishlari\n"
        "• 🌟 3 yulduz bildirishnomasi\n"
        "• 🏁 Urush natijasi",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )