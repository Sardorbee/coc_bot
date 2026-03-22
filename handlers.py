"""
handlers.py — Telegram buyruq handlerlari (/urush, /oyinchi, ...)
"""

import logging

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import messages as msg
from api import fetch_clan_members, fetch_current_war, fetch_player, fetch_war_log

log = logging.getLogger(__name__)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Urush holati", callback_data="war"),
            InlineKeyboardButton("📜 Urush tarixi",  callback_data="warlog"),
        ],
        [
            InlineKeyboardButton("👥 A'zolar",  callback_data="azolar"),
            InlineKeyboardButton("📖 Yordam",   callback_data="help"),
        ],
    ])


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *CoC Klan Boti faol!*\n\n"
        "Quyidagi tugmalardan foydalaning yoki buyruq yozing:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Buyruqlar:*\n"
        "• /urush — joriy urush holati\n"
        "• /urushlog — oxirgi 5 ta urush\n"
        "• /oyinchi #TAG — o'yinchi ma'lumotlari\n"
        "• /azolar — barcha a'zolar (TH boyicha)\n"
        "• /azolar 14 — faqat TH14 a'zolari\n\n"
        "*Avtomatik xabarlar:*\n"
        "• A'zo qo'shilganda / Chiqqanda\n"
        "• Tayyorgarlik boshlanganda\n"
        "• Urush boshlanganida\n"
        "• 2 soat va 30 daqiqalik ogohlantirishlar\n"
        "• 3 yulduzli hujum bildirishnomasi\n"
        "• Urush tugaganda natija",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_war(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        war = await fetch_current_war(s)
    if not war or war.get("state") in ("notInWar", None):
        await update.message.reply_text("Klan hozir urushda emas.")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yangilash", callback_data="war")],
        [InlineKeyboardButton("Asosiy menyu", callback_data="back_start")],
    ])
    await update.message.reply_text(
        msg.war_status(war),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cmd_warlog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as s:
        entries = await fetch_war_log(s)
    await update.message.reply_text(msg.war_log(entries), parse_mode="Markdown")


async def cmd_player(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Ishlatish: /oyinchi #TAG\nMisol: /oyinchi #2ABC123")
        return
    async with aiohttp.ClientSession() as s:
        player = await fetch_player(s, ctx.args[0])
    if not player:
        await update.message.reply_text("O'yinchi topilmadi -- tegni tekshiring.")
        return
    await update.message.reply_text(msg.player_card(player), parse_mode="Markdown")


async def cmd_members(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    th_filter = None
    if ctx.args:
        arg = ctx.args[0].lower().replace("th", "").strip()
        if arg.isdigit():
            th_filter = int(arg)

    await update.message.reply_text("A'zolar yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        all_members = await fetch_clan_members(s)
    if not all_members:
        await update.message.reply_text("A'zolar ma'lumotini olishda xatolik.")
        return

    if th_filter:
        filtered = [m for m in all_members if m.get("townHallLevel") == th_filter]
        if not filtered:
            await update.message.reply_text(f"TH{th_filter} darajali a'zolar topilmadi.")
            return
        await update.message.reply_text(
            msg.members_list(filtered, title=f"TH{th_filter} A'zolari -- {len(filtered)} ta"),
            parse_mode="Markdown",
        )
    else:
        chunks = [all_members[i:i + 15] for i in range(0, len(all_members), 15)]
        for i, chunk in enumerate(chunks):
            title = f"Klan A'zolari -- {len(all_members)} ta" if i == 0 else None
            await update.message.reply_text(
                msg.members_list(chunk, title=title),
                parse_mode="Markdown",
            )
