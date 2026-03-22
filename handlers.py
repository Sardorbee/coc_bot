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
        "*Buyruqlar:*\n\n"
        "*🏰 Klan:*\n"
        "• /urush — joriy urush holati\n"
        "• /urushlog — oxirgi 5 ta urush\n"
        "• /azolar — barcha a'zolar (TH bo'yicha)\n"
        "• /azolar 14 — faqat TH14 a'zolari\n\n"
        "*👤 O'yinchi:*\n"
        "• /oyinchi #TAG — to'liq o'yinchi profili\n"
        "• /qurol #TAG — yangilanish kuzatuvchi (max %)\n"
        "• /yutuq #TAG — yutuqlar va bajarilish %\n"
        "• /builder #TAG — Builder Base statistikasi\n"
        "• /solishtir #TAG1 #TAG2 — ikki o'yinchini solishtir\n\n"
        "*Avtomatik xabarlar:*\n"
        "• ✅ A'zo qo'shilganda / 👋 Chiqqanda\n"
        "• 📋 Tayyorgarlik boshlanganda\n"
        "• ⚔️ Urush boshlanganida\n"
        "• ⏰ 2 soat va 30 daqiqalik ogohlantirishlar\n"
        "• 🌟 3 yulduzli hujum bildirishnomasi\n"
        "• 🏁 Urush tugaganda natija",
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


async def cmd_qurol(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yangilanish kuzatuvchi — /qurol #TAG"""
    if not ctx.args:
        await update.message.reply_text("Ishlatish: /qurol #TAG\nMisol: /qurol #2ABC123")
        return
    await update.message.reply_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        player = await fetch_player(s, ctx.args[0])
    if not player:
        await update.message.reply_text("❌ O'yinchi topilmadi — tegni tekshiring.")
        return
    text = msg.upgrade_tracker(player)
    # Can be long — send in chunks if needed
    if len(text) > 4000:
        mid = text[:4000].rfind("\n")
        await update.message.reply_text(text[:mid], parse_mode="Markdown")
        await update.message.reply_text(text[mid:], parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_yutuq(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Yutuqlar — /yutuq #TAG"""
    if not ctx.args:
        await update.message.reply_text("Ishlatish: /yutuq #TAG\nMisol: /yutuq #2ABC123")
        return
    await update.message.reply_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        player = await fetch_player(s, ctx.args[0])
    if not player:
        await update.message.reply_text("❌ O'yinchi topilmadi — tegni tekshiring.")
        return
    text = msg.achievements(player)
    if len(text) > 4000:
        mid = text[:4000].rfind("\n")
        await update.message.reply_text(text[:mid], parse_mode="Markdown")
        await update.message.reply_text(text[mid:], parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_builder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Builder Base — /builder #TAG"""
    if not ctx.args:
        await update.message.reply_text("Ishlatish: /builder #TAG\nMisol: /builder #2ABC123")
        return
    await update.message.reply_text("⏳ Yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        player = await fetch_player(s, ctx.args[0])
    if not player:
        await update.message.reply_text("❌ O'yinchi topilmadi — tegni tekshiring.")
        return
    await update.message.reply_text(msg.builder_base(player), parse_mode="Markdown")


async def cmd_solishtir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """O'yinchi solishtirish — /solishtir #TAG1 #TAG2"""
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Ishlatish: /solishtir #TAG1 #TAG2\n"
            "Misol: /solishtir #2ABC123 #9XYZ456"
        )
        return
    await update.message.reply_text("⏳ Ikkala o'yinchi yuklanmoqda...")
    async with aiohttp.ClientSession() as s:
        p1 = await fetch_player(s, ctx.args[0])
        p2 = await fetch_player(s, ctx.args[1])
    if not p1:
        await update.message.reply_text(f"❌ Birinchi o'yinchi topilmadi: {ctx.args[0]}")
        return
    if not p2:
        await update.message.reply_text(f"❌ Ikkinchi o'yinchi topilmadi: {ctx.args[1]}")
        return
    await update.message.reply_text(msg.compare_players(p1, p2), parse_mode="Markdown")