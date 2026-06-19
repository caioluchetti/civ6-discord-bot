import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

from flask import Flask, request, jsonify, render_template, redirect

from storage import (
    get_discord_id,
    get_notification_channel,
    record_turn,
    is_round_complete,
    get_player_stats,
    get_current_turn,
    get_last_update,
    format_duration,
    get_all_players,
    get_all_games,
    get_game_order,
    set_game_order,
    get_player_order,
    set_player_order,
    clear_player_order,
    get_last_game_name_for_players,
)

logger = logging.getLogger("webhook_server")
app = Flask(__name__)

_bot_client = None


def set_bot_client(client):
    global _bot_client
    _bot_client = client


async def _send_to_discord(channel, message):
    await channel.send(message)


def _build_recap_message(game_name):
    stats = get_player_stats(game_name)
    if not stats:
        return None

    turn = get_current_turn(game_name)
    lines = [f"**Round {turn} complete!**\n"]

    lines.append("```")
    lines.append(f"{'Player':<16} {'Order':<6} {'Avg Wait':<10} {'Avg Play':<10}")
    lines.append("-" * 44)

    ordered = sorted(stats.items(), key=lambda x: x[1]["order"])
    for name, s in ordered:
        order = f"#{s['order']}"
        lines.append(
            f"{name:<16} {order:<6} {s['avg_wait']:<10} {s['avg_play']:<10}"
        )
    lines.append("```")

    total_wait_sec = 0
    count = 0
    for s in stats.values():
        if isinstance(s["avg_wait"], str) and "m" in s["avg_wait"]:
            parts = s["avg_wait"].replace("m", "").replace("s", "").split()
            if len(parts) == 2:
                total_wait_sec += int(parts[0]) * 60 + int(parts[1])
                count += 1
    if count > 0:
        avg_all = format_duration(total_wait_sec / count)
        lines.append(f"Average wait across all players: **{avg_all}**")

    return "\n".join(lines)


def _format_last_update(last_update):
    if not last_update:
        return "never"
    last_ts = datetime.fromisoformat(last_update)
    now = datetime.now(timezone.utc)
    delta = now - last_ts
    if delta.total_seconds() < 60:
        return "just now"
    elif delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() // 60)}m ago"
    elif delta.total_seconds() < 86400:
        return f"{int(delta.total_seconds() // 3600)}h ago"
    else:
        return f"{int(delta.total_seconds() // 86400)}d ago"


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

    future = asyncio.run_coroutine_threadsafe(
        _send_to_discord(channel, message),
        _bot_client.loop,
    )
    try:
        future.result(timeout=10)
        logger.info("Turn notification sent for %s", steam_name)
    except Exception as e:
        logger.error("Failed to send Discord message: %s", e)
        return "Failed to send notification", 500

    record_turn(game_name, steam_name, turn_number)

    if is_round_complete(turn_number, game_name):
        recap = _build_recap_message(game_name)
        if recap:
            recap_future = asyncio.run_coroutine_threadsafe(
                _send_to_discord(channel, recap),
                _bot_client.loop,
            )
            try:
                recap_future.result(timeout=10)
                logger.info("Round recap sent for turn %s, game %s", turn_number, game_name)
            except Exception as e:
                logger.error("Failed to send recap: %s", e)

    return "ok", 200


def _get_ordered_game_list():
    all_games = get_all_games()
    saved_order = get_game_order()
    ordered = [g for g in saved_order if g in all_games]
    rest = [g for g in all_games if g not in ordered]
    return ordered + sorted(rest)


@app.route("/")
def index():
    games = _get_ordered_game_list()
    if games:
        return redirect(f"/game/{urlquote(games[0], safe='')}")
    return redirect("/game/No%20Games%20Yet")


@app.route("/game/<path:game_name>")
def dashboard(game_name):
    all_games = _get_ordered_game_list()
    stats = get_player_stats(game_name)
    last_update = get_last_update(game_name)
    current_turn = get_current_turn(game_name)
    manual_order = get_player_order(game_name)
    public_url = os.getenv("PUBLIC_URL", "http://localhost:5000")

    return render_template(
        "dashboard.html",
        game_name=game_name,
        current_turn=current_turn,
        last_update=_format_last_update(last_update),
        stats=stats,
        webhook_url=f"{public_url}/webhook",
        all_games=all_games,
        has_manual_order=bool(manual_order),
    )


@app.route("/api/game-order", methods=["POST"])
def api_game_order():
    data = request.get_json(force=True)
    ordered = data.get("games", [])
    set_game_order(ordered)
    return jsonify({"ok": True})


@app.route("/api/game/<path:game_name>/order", methods=["POST"])
def api_player_order(game_name):
    data = request.get_json(force=True)
    ordered = data.get("players", [])
    set_player_order(game_name, ordered)
    return jsonify({"ok": True})


@app.route("/api/game/<path:game_name>/order", methods=["DELETE"])
def api_player_order_delete(game_name):
    clear_player_order(game_name)
    return jsonify({"ok": True})
