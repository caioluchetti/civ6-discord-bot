import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

from flask import Flask, request, jsonify, render_template, redirect

from storage import (
    get_discord_id,
    get_next_player,
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
    _parse_duration,
)

logger = logging.getLogger("webhook_server")
app = Flask(__name__)

PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5000")
API_SECRET = os.getenv("API_SECRET", "")

_bot_client = None


def set_bot_client(client):
    global _bot_client
    _bot_client = client


async def _send_to_discord(channel, message):
    await channel.send(message)


def _notify_discord(channel, message):
    if _bot_client is None:
        logger.error("Bot client not set — cannot send to Discord")
        return False, "Bot not ready"
    future = asyncio.run_coroutine_threadsafe(
        _send_to_discord(channel, message),
        _bot_client.loop,
    )
    try:
        future.result(timeout=10)
        return True, None
    except Exception as e:
        logger.error("Failed to send Discord message: %s", e)
        return False, str(e)


def _resolve_channel():
    channel_id = get_notification_channel()
    if not channel_id:
        return None, "No channel configured"
    channel = _bot_client.get_channel(int(channel_id))
    if channel is None:
        return None, "Channel not found"
    return channel, None


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
        sec = _parse_duration(s["avg_wait"])
        if sec > 0:
            total_wait_sec += sec
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


def _require_secret():
    if not API_SECRET:
        return None
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_SECRET}":
        return jsonify({"error": "Unauthorized"}), 401
    return None


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Invalid JSON received: %s", e)
        return "Invalid JSON", 400

    game_name = data.get("value1", "Unknown Game")
    username = data.get("value2", "Unknown Player")
    turn_number = data.get("value3", "?")

    logger.info(
        "Webhook received: game=%s, player=%s, turn=%s",
        game_name, username, turn_number,
    )

    channel, err = _resolve_channel()
    if err:
        logger.error(err)
        return err, 500

    discord_id = get_discord_id(username)
    mention = f"<@{discord_id}>" if discord_id else f"**{username}** (not registered)"

    message = (
        f"{mention}, it's your turn!\n"
        f"Turn: **{turn_number}**\n"
        f"Game: **{game_name}**"
    )

    _notify_discord(channel, message)
    record_turn(game_name, username, turn_number)

    if is_round_complete(turn_number, game_name):
        recap = _build_recap_message(game_name)
        if recap:
            _notify_discord(channel, recap)

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

    return render_template(
        "dashboard.html",
        game_name=game_name,
        current_turn=current_turn,
        last_update=_format_last_update(last_update),
        stats=stats,
        webhook_url=f"{PUBLIC_URL}/webhook",
        all_games=all_games,
        has_manual_order=bool(manual_order),
    )


@app.route("/api/game-order", methods=["POST"])
def api_game_order():
    auth_err = _require_secret()
    if auth_err:
        return auth_err
    data = request.get_json(force=True)
    ordered = data.get("games", [])
    set_game_order(ordered)
    return jsonify({"ok": True})


@app.route("/api/game/<path:game_name>/order", methods=["POST"])
def api_player_order(game_name):
    auth_err = _require_secret()
    if auth_err:
        return auth_err
    data = request.get_json(force=True)
    ordered = data.get("players", [])
    set_player_order(game_name, ordered)
    return jsonify({"ok": True})


@app.route("/api/game/<path:game_name>/order", methods=["DELETE"])
def api_player_order_delete(game_name):
    auth_err = _require_secret()
    if auth_err:
        return auth_err
    clear_player_order(game_name)
    return jsonify({"ok": True})


@app.route("/api/game/<path:game_name>/ping", methods=["POST"])
def api_ping_player(game_name):
    auth_err = _require_secret()
    if auth_err:
        return auth_err

    channel, err = _resolve_channel()
    if err:
        return jsonify({"error": err}), 400

    next_player = get_next_player(game_name)
    if not next_player:
        return jsonify({"error": "No players registered"}), 400

    discord_id = get_discord_id(next_player)
    mention = f"<@{discord_id}>" if discord_id else f"**{next_player}**"

    message = (
        f"\U0001f514 {mention}, it's your turn!\n"
        f"Game: **{game_name}**"
    )

    ok, err = _notify_discord(channel, message)
    if not ok:
        return jsonify({"error": err}), 500

    logger.info("Ping sent for %s in game %s", next_player, game_name)
    return jsonify({"ok": True, "player": next_player})
