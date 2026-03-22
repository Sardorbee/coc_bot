"""
bot.py — Asosiy kirish nuqtasi
Render deployment uchun moslashtirilgan.

Ishga tushirish:
    pip install -r requirements.txt
    python bot.py
"""

import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import config  # noqa: F401  — triggers logging setup & env validation
from callbacks import button_callback
from handlers import (
    cmd_help,
    cmd_members,
    cmd_player,
    cmd_start,
    cmd_war,
    cmd_warlog,
    cmd_qurol,
    cmd_yutuq,
    cmd_builder,
    cmd_solishtir,
)
from monitor import keep_alive, war_monitor

log = logging.getLogger(__name__)


# ── Health server (Render requires an open port) ──────────────────────────────

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        import urllib.request
        try:
            ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode()
        except Exception:
            ip = "unavailable"
        body = f"CoC Bot ishlayapti | Chiqish IP: {ip}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass  # silence HTTP access logs


def _start_health_server():
    server = HTTPServer(("0.0.0.0", config.PORT), _HealthHandler)
    log.info("Health server port %d da ishlamoqda.", config.PORT)
    server.serve_forever()


# ── Bot setup ─────────────────────────────────────────────────────────────────

def _build_app() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("urush",     cmd_war))
    app.add_handler(CommandHandler("urushlog",  cmd_warlog))
    app.add_handler(CommandHandler("oyinchi",   cmd_player))
    app.add_handler(CommandHandler("azolar",    cmd_members))
    app.add_handler(CommandHandler("qurol",     cmd_qurol))
    app.add_handler(CommandHandler("yutuq",     cmd_yutuq))
    app.add_handler(CommandHandler("builder",   cmd_builder))
    app.add_handler(CommandHandler("solishtir", cmd_solishtir))
    app.add_handler(CallbackQueryHandler(button_callback))

    return app


# ── Main async entry point ────────────────────────────────────────────────────

async def run():
    app = _build_app()

    async with app:
        await app.initialize()
        await app.start()

        monitor_task   = asyncio.create_task(war_monitor(app.bot))
        keepalive_task = asyncio.create_task(keep_alive())
        log.info("Bot, urush monitoru va keep-alive ishlamoqda...")

        await app.updater.start_polling(drop_pending_updates=True)

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            log.info("To'xtatilmoqda...")
        finally:
            monitor_task.cancel()
            keepalive_task.cancel()
            await app.updater.stop()
            await app.stop()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Start HTTP health server in background thread
    threading.Thread(target=_start_health_server, daemon=True).start()
    # Run async bot
    asyncio.run(run())