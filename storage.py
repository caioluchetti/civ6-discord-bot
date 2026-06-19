import json
import logging
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger("storage")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "players.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "turn_history.json")

_lock = threading.RLock()


def _load_json(path, default):
    with _lock:
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Corrupt JSON file: %s — using default", path)
            return default


def _save_json(path, data):
    with _lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def load_players():
    return _load_json(DATA_FILE, {"players": {}}).get("players", {})


def save_players(players):
    _save_json(DATA_FILE, {"players": players})


def register_player(username, discord_id):
    with _lock:
        players = load_players()
        players[username.lower()] = discord_id
        save_players(players)


def unregister_player(username):
    with _lock:
        players = load_players()
        removed = players.pop(username.lower(), None)
        save_players(players)
        return removed is not None


def get_discord_id(username):
    players = load_players()
    return players.get(username.lower())


def get_all_players():
    return load_players()


def get_notification_channel():
    config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
    return config.get("notification_channel_id")


def set_notification_channel(channel_id):
    with _lock:
        config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
        config["notification_channel_id"] = channel_id
        _save_json(CONFIG_FILE, config)


def record_turn(game, username, turn):
    with _lock:
        history = _load_json(HISTORY_FILE, {"history": []})
        history["history"].append({
            "game": game,
            "username": username.lower(),
            "turn": str(turn),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _save_json(HISTORY_FILE, history)


def get_turn_history(game_name=None):
    data = _load_json(HISTORY_FILE, {"history": []})
    if game_name:
        return [e for e in data["history"] if e["game"] == game_name]
    return data["history"]


def _get_game_player_set(game_name):
    history = get_turn_history(game_name)
    players = set()
    for entry in history:
        players.add(entry["username"])
    return players


def get_all_games():
    history = get_turn_history()
    games = {}
    for e in history:
        g = e["game"]
        if g not in games:
            games[g] = e["timestamp"]
        else:
            games[g] = max(games[g], e["timestamp"])
    return sorted(games.keys())


def get_game_order():
    config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
    return config.get("game_order", [])


def set_game_order(ordered_games):
    with _lock:
        config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
        config["game_order"] = ordered_games
        _save_json(CONFIG_FILE, config)


def get_player_order(game_name):
    config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
    orders = config.get("player_orders", {})
    return orders.get(game_name)


def set_player_order(game_name, ordered_players):
    with _lock:
        config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
        if "player_orders" not in config:
            config["player_orders"] = {}
        config["player_orders"][game_name] = ordered_players
        _save_json(CONFIG_FILE, config)


def clear_player_order(game_name):
    with _lock:
        config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
        if "player_orders" in config and game_name in config["player_orders"]:
            del config["player_orders"][game_name]
        _save_json(CONFIG_FILE, config)


def get_current_turn(game_name=None):
    history = get_turn_history(game_name)
    if not history:
        return "?"
    return history[-1]["turn"]


def get_last_update(game_name=None):
    history = get_turn_history(game_name)
    if not history:
        return None
    return history[-1]["timestamp"]


def is_round_complete(turn_number, game_name=None):
    players = get_all_players() if game_name is None else _get_game_player_set(game_name)
    if not players:
        return False
    history = get_turn_history(game_name)
    finished = set()
    for entry in reversed(history):
        if entry["turn"] == str(turn_number):
            finished.add(entry["username"])
        elif int(entry["turn"]) < int(turn_number):
            break
    return players.issubset(finished)


def get_player_stats(game_name=None):
    history = get_turn_history(game_name)
    if not history:
        return {}

    game_players = _get_game_player_set(game_name) if game_name else set(get_all_players().keys())
    if not game_players:
        return {}

    global_players = get_all_players()

    player_turns = {name: [] for name in game_players}
    for entry in history:
        name = entry["username"]
        if name in player_turns:
            player_turns[name].append({
                "turn": int(entry["turn"]),
                "ts": datetime.fromisoformat(entry["timestamp"]),
            })

    last_turn = {}
    last_timestamp = {}
    for entry in history:
        name = entry["username"]
        if name in game_players:
            last_turn[name] = int(entry["turn"])
            last_timestamp[name] = datetime.fromisoformat(entry["timestamp"])

    manual_order = get_player_order(game_name) if game_name else None
    if manual_order:
        order_map = {name.lower(): idx + 1 for idx, name in enumerate(manual_order)}
    else:
        player_order = sorted(
            last_timestamp.items(),
            key=lambda x: x[1],
        )
        order_map = {name: idx + 1 for idx, (name, _) in enumerate(player_order)}

    stats = {}
    for name in game_players:
        turns = player_turns.get(name, [])
        avg_wait = "—"
        if len(turns) >= 2:
            wait_seconds = []
            for i in range(1, len(turns)):
                delta = (turns[i]["ts"] - turns[i - 1]["ts"]).total_seconds()
                wait_seconds.append(delta)
            avg_wait = format_duration(sum(wait_seconds) / len(wait_seconds))

        avg_play = "—"
        if len(turns) >= 1:
            gaps = []
            for i, t in enumerate(turns):
                current_turn = t["turn"]
                later_same_turn = None
                for h in history:
                    h_name = h["username"]
                    h_turn = int(h["turn"])
                    if h_name != name and h_turn == current_turn:
                        h_ts = datetime.fromisoformat(h["timestamp"])
                        if h_ts > t["ts"]:
                            if later_same_turn is None or h_ts < later_same_turn:
                                later_same_turn = h_ts
                if later_same_turn:
                    gaps.append((later_same_turn - t["ts"]).total_seconds())
            if gaps:
                avg_play = format_duration(sum(gaps) / len(gaps))

        stats[name] = {
            "discord_id": global_players.get(name, ""),
            "order": order_map.get(name, len(game_players) + 1),
            "avg_wait": avg_wait,
            "avg_play": avg_play,
            "last_turn": last_turn.get(name, "—"),
            "last_timestamp": last_timestamp.get(name, ""),
        }

    return stats


def get_next_player(game_name=None):
    players = _get_game_player_set(game_name) if game_name else set(get_all_players().keys())
    if not players:
        return None

    current_turn = get_current_turn(game_name)
    if current_turn == "?":
        manual_order = get_player_order(game_name)
        if manual_order:
            return manual_order[0]
        return next(iter(players)) if players else None

    current_turn_int = int(current_turn)
    history = get_turn_history(game_name)

    played = set()
    for entry in reversed(history):
        if int(entry["turn"]) == current_turn_int:
            played.add(entry["username"])
        elif int(entry["turn"]) < current_turn_int:
            break

    manual_order = get_player_order(game_name)
    if manual_order:
        ordered = [p.lower() for p in manual_order]
    else:
        ordered = list(players)

    for name in ordered:
        if name not in played:
            return name

    return ordered[0] if ordered else None


def _parse_duration(value):
    import re
    if not isinstance(value, str) or value == "—":
        return 0
    match = re.fullmatch(r"(?:(\d+)h ?)?(?:(\d+)m ?)?(?:(\d+)s)?", value)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
