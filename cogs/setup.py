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

    @app_commands.command(name="register", description="Link your game username to your Discord account")
    @app_commands.describe(username="Your game username (case-insensitive)")
    async def register(self, interaction: discord.Interaction, username: str):
        safe = discord.utils.escape_markdown(username)
        register_player(username, str(interaction.user.id))
        await interaction.response.send_message(
            f"Registered **{safe}** as <@{interaction.user.id}>.",
            ephemeral=True,
        )

    @app_commands.command(name="unregister", description="Remove a registered game username")
    @app_commands.describe(username="The game username to remove")
    async def unregister(self, interaction: discord.Interaction, username: str):
        safe = discord.utils.escape_markdown(username)
        if unregister_player(username):
            await interaction.response.send_message(
                f"Removed **{safe}** from the registry.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"**{safe}** was not registered.",
                ephemeral=True,
            )

    @app_commands.command(name="players", description="List all registered players")
    async def players(self, interaction: discord.Interaction):
        all_players = get_all_players()
        if not all_players:
            await interaction.response.send_message("No players registered yet.")
            return

        lines = []
        for username, discord_id in sorted(all_players.items()):
            safe = discord.utils.escape_markdown(username)
            lines.append(f"- **{safe}** → <@{discord_id}>")

        await interaction.response.send_message(
            "**Registered Players:**\n" + "\n".join(lines),
        )

    @app_commands.command(name="webhook", description="Get the webhook URL to paste into Civ 6")
    async def webhook(self, interaction: discord.Interaction):
        url = f"{self.public_url}/webhook"
        dash = f"{self.public_url}/"
        await interaction.response.send_message(
            f"**Webhook URL** (paste into Civ 6):\n`{url}`\n\n"
            f"**Dashboard:** {dash}",
            ephemeral=True,
        )

    @app_commands.command(
        name="channel",
        description="Set the channel where turn notifications are posted",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def channel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        set_notification_channel(str(interaction.channel_id))
        await interaction.followup.send(
            f"Turn notifications will now be posted in {interaction.channel.mention}.",
        )

    @app_commands.command(name="status", description="Show bot configuration status")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channel_id = get_notification_channel()
        player_count = len(get_all_players())

        lines = [
            f"**Webhook URL:** `{self.public_url}/webhook`",
            f"**Dashboard:** {self.public_url}/",
            f"**Notification channel:** {f'<#{channel_id}>' if channel_id else '*Not set*'}",
            f"**Registered players:** {player_count}",
        ]
        await interaction.followup.send("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
