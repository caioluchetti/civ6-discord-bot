import asyncio
import logging
import os
import sys
import threading

import discord
from discord.ext import commands
from dotenv import load_dotenv

from webhook_server import app, set_bot_client

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PORT = int(os.getenv("PORT", "5000"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5000")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bot")


class Civ6Bot(commands.Bot):
    def __init__(self, public_url: str):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.public_url = public_url

    async def setup_hook(self):
        await self.load_extension("cogs.setup")
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Webhook URL: {PUBLIC_URL}/webhook")


def run_flask():
    logger.info("Starting Flask webhook server on port %d", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    if not TOKEN:
        logger.fatal("DISCORD_BOT_TOKEN not set in .env")
        sys.exit(1)

    bot = Civ6Bot(public_url=PUBLIC_URL)
    set_bot_client(bot)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    bot.run(TOKEN)
