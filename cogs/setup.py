import discord
from discord import app_commands
from discord.ext import commands

from storage import (
    register_player,
    unregister_player,
    get_all_players,
    set_notification_channel,
    get_notification_channel,
)


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.public_url = bot.public_url.rstrip("/")

    @app_commands.command(name="register", description="Link your Steam name to your Discord account")
    @app_commands.describe(steam_name="Your Steam/Civ 6 player name (case-insensitive)")
    async def register(self, interaction: discord.Interaction, steam_name: str):
        register_player(steam_name, str(interaction.user.id))
        await interaction.response.send_message(
            f"Registered **{steam_name}** as <@{interaction.user.id}>.",
            ephemeral=True,
        )

    @app_commands.command(name="unregister", description="Remove a registered Steam name")
    @app_commands.describe(steam_name="The Steam name to remove")
    async def unregister(self, interaction: discord.Interaction, steam_name: str):
        if unregister_player(steam_name):
            await interaction.response.send_message(
                f"Removed **{steam_name}** from the registry.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"**{steam_name}** was not registered.",
                ephemeral=True,
            )

    @app_commands.command(name="players", description="List all registered players")
    async def players(self, interaction: discord.Interaction):
        all_players = get_all_players()
        if not all_players:
            await interaction.response.send_message("No players registered yet.")
            return

        lines = []
        for steam_name, discord_id in sorted(all_players.items()):
            lines.append(f"- **{steam_name}** → <@{discord_id}>")

        await interaction.response.send_message(
            "**Registered Players:**\n" + "\n".join(lines),
        )

    @app_commands.command(name="webhook", description="Get the webhook URL to paste into Civ 6")
    async def webhook(self, interaction: discord.Interaction):
        url = f"{self.public_url}/webhook"
        await interaction.response.send_message(
            f"Paste this URL into Civ 6's Play By Cloud webhook settings:\n\n`{url}`",
            ephemeral=True,
        )

    @app_commands.command(name="channel", description="Set the channel where turn notifications are posted")
    async def channel(self, interaction: discord.Interaction):
        set_notification_channel(str(interaction.channel_id))
        await interaction.response.send_message(
            f"Turn notifications will now be posted in {interaction.channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="status", description="Show bot configuration status")
    async def status(self, interaction: discord.Interaction):
        channel_id = get_notification_channel()
        player_count = len(get_all_players())

        lines = [
            f"**Webhook URL:** `{self.public_url}/webhook`",
            f"**Notification channel:** {f'<#{channel_id}>' if channel_id else '*Not set*'}",
            f"**Registered players:** {player_count}",
        ]
        await interaction.response.send_message("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
