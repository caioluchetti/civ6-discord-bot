import json
import logging

from flask import Flask, request, jsonify

from storage import get_discord_id, get_notification_channel

logger = logging.getLogger("webhook_server")
app = Flask(__name__)

_bot_client = None


def set_bot_client(client):
    global _bot_client
    _bot_client = client


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
    except Exception:
        logger.warning("Invalid JSON received")
        return "Invalid JSON", 400

    game_name = data.get("value1", "Unknown Game")
    steam_name = data.get("value2", "Unknown Player")
    turn_number = data.get("value3", "?")

    logger.info(
        "Webhook received: game=%s, player=%s, turn=%s",
        game_name, steam_name, turn_number,
    )

    if _bot_client is None:
        logger.error("Bot client not set — cannot send notification")
        return "Bot not ready", 503

    channel_id = get_notification_channel()
    if not channel_id:
        logger.error("No notification channel configured")
        return "No channel configured", 500

    channel = _bot_client.get_channel(int(channel_id))
    if channel is None:
        logger.error("Channel not found: %s", channel_id)
        return "Channel not found", 500

    discord_id = get_discord_id(steam_name)
    mention = f"<@{discord_id}>" if discord_id else f"**{steam_name}** (not registered)"

    message = (
        f"{mention}, it's your turn!\n"
        f"Turn: **{turn_number}**\n"
        f"Game: **{game_name}**"
    )

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(channel.send(message))
        else:
            loop.run_until_complete(channel.send(message))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(channel.send(message))

    logger.info("Turn notification sent for %s", steam_name)
    return "ok", 200
