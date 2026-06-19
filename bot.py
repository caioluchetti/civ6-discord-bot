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
GUILD_ID_RAW = os.getenv("DISCORD_GUILD_ID")
PORT = int(os.getenv("PORT", "5000"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5000")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bot")

try:
    GUILD_ID = int(GUILD_ID_RAW) if GUILD_ID_RAW else None
except (ValueError, TypeError):
    logger.fatal("DISCORD_GUILD_ID must be a numeric ID, got: %s", GUILD_ID_RAW)
    sys.exit(1)


class Civ6Bot(commands.Bot):
    def __init__(self, public_url: str, guild_id: int):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.public_url = public_url
        self.guild_id = guild_id

    async def setup_hook(self):
        await self.load_extension("cogs.setup")
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info("Slash commands synced to guild %s", self.guild_id)

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

    if not GUILD_ID:
        logger.fatal("DISCORD_GUILD_ID not set in .env")
        sys.exit(1)

    bot = Civ6Bot(public_url=PUBLIC_URL, guild_id=GUILD_ID)
    set_bot_client(bot)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    bot.run(TOKEN)
