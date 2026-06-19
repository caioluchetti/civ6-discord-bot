import json
import os
from datetime import datetime, timezone

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "turn_history.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_players():
    return _load_json(DATA_FILE, {"players": {}}).get("players", {})


def save_players(players):
    _save_json(DATA_FILE, {"players": players})


def register_player(steam_name, discord_id):
    players = load_players()
    players[steam_name.lower()] = discord_id
    save_players(players)


def unregister_player(steam_name):
    players = load_players()
    removed = players.pop(steam_name.lower(), None)
    save_players(players)
    return removed is not None


def get_discord_id(steam_name):
    players = load_players()
    return players.get(steam_name.lower())


def get_all_players():
    return load_players()


def get_notification_channel():
    config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
    return config.get("notification_channel_id")


def set_notification_channel(channel_id):
    config = _load_json(CONFIG_FILE, {"notification_channel_id": None})
    config["notification_channel_id"] = channel_id
    _save_json(CONFIG_FILE, config)


def record_turn(game, steam_name, turn):
    history = _load_json(HISTORY_FILE, {"history": []})
    history["history"].append({
        "game": game,
        "steam_name": steam_name.lower(),
        "turn": str(turn),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save_json(HISTORY_FILE, history)


def get_turn_history():
    data = _load_json(HISTORY_FILE, {"history": []})
    return data["history"]


def get_current_turn():
    history = get_turn_history()
    if not history:
        return "?"
    return history[-1]["turn"]


def get_last_update():
    history = get_turn_history()
    if not history:
        return None
    return history[-1]["timestamp"]


def is_round_complete(turn_number):
    players = get_all_players()
    if not players:
        return False
    history = get_turn_history()
    finished = set()
    for entry in reversed(history):
        if entry["turn"] == str(turn_number):
            finished.add(entry["steam_name"])
        elif int(entry["turn"]) < int(turn_number):
            break
    return set(players.keys()).issubset(finished)


def get_player_stats():
    history = get_turn_history()
    players = get_all_players()
    if not history or not players:
        return {}

    player_turns = {name: [] for name in players}
    for entry in history:
        name = entry["steam_name"]
        if name in player_turns:
            player_turns[name].append({
                "turn": int(entry["turn"]),
                "ts": datetime.fromisoformat(entry["timestamp"]),
            })

    last_turn = {}
    last_timestamp = {}
    for entry in history:
        name = entry["steam_name"]
        if name in players:
            last_turn[name] = int(entry["turn"])
            last_timestamp[name] = datetime.fromisoformat(entry["timestamp"])

    player_order = sorted(
        last_timestamp.items(),
        key=lambda x: x[1],
    )
    order_map = {name: idx + 1 for idx, (name, _) in enumerate(player_order)}

    stats = {}
    for name in players:
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
                current_player = name
                later_same_turn = None
                for h in history:
                    h_name = h["steam_name"]
                    h_turn = int(h["turn"])
                    if h_name != current_player and h_turn == current_turn:
                        h_ts = datetime.fromisoformat(h["timestamp"])
                        if h_ts > t["ts"]:
                            if later_same_turn is None or h_ts < later_same_turn:
                                later_same_turn = h_ts
                if later_same_turn:
                    gaps.append((later_same_turn - t["ts"]).total_seconds())
            if gaps:
                avg_play = format_duration(sum(gaps) / len(gaps))

        stats[name] = {
            "discord_id": players.get(name, ""),
            "order": order_map.get(name, len(players) + 1),
            "avg_wait": avg_wait,
            "avg_play": avg_play,
            "last_turn": last_turn.get(name, "—"),
            "last_timestamp": last_timestamp.get(name, ""),
        }

    return stats


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
