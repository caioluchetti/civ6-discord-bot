import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


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
