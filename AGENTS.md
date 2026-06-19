# AGENTS.md — AI Agent Guide

This document describes the architecture, conventions, and data flow of **BeikaoBot** (Civ 6 Discord Turn Tracker) so any AI agent can understand, modify, and maintain this repository with precision.

---

## Overview

**BeikaoBot** is a Discord bot + Flask web server that notifies Civilization VI players when it's their turn to play. It receives webhooks from a Civ 6 game (via a mod/automation script), looks up registered players (game username → Discord ID), and sends `@mention` messages in the configured Discord channel. It also includes a web dashboard with per-player stats (average wait time, average play time, turn order) with drag-and-drop for reordering games and players.

---

## Architecture

```
Civ 6 Game (mod/script)
    │  HTTP POST /webhook  (JSON: value1=game, value2=player, value3=turn)
    ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│  webhook_server.py       │◄─────│  storage.py              │
│  Flask (port 5000)       │      │  JSON file-backed DB     │
│  - /webhook (POST)       │      │  - data.json (players)   │
│  - /game/<name> (GET)    │      │  - config.json (configs) │
│  - /api/* (POST/DELETE)  │      │  - turn_history.json     │
└──────────┬───────────────┘      └──────────────────────────┘
           │  set_bot_client()
           ▼
┌──────────────────────────┐
│  bot.py                  │
│  discord.py (asyncio)    │
│  - Gateway client        │
│  - Slash commands        │
│  - Sends @mentions       │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  cogs/setup.py           │
│  Slash commands cog:     │
│  /register, /unregister, │
│  /players, /webhook,     │
│  /channel, /status       │
└──────────────────────────┘
```

### Threading Model

- **Main thread**: `discord.py` bot (asyncio event loop + blocking `bot.run(TOKEN)`)
- **Secondary thread (daemon)**: Flask (`app.run(...)`) started in `bot.py:65` via `threading.Thread`
- Cross-thread communication: `asyncio.run_coroutine_threadsafe()` in `webhook_server.py:135` to send Discord messages from within a Flask request

---

## File Structure

| File | Purpose |
|------|---------|
| `bot.py` | Entry point. Loads `.env`, creates Discord bot, starts Flask in a separate thread |
| `webhook_server.py` | Flask app with webhook, dashboard, and ordering API routes |
| `storage.py` | JSON persistence layer (data.json, config.json, turn_history.json) |
| `cogs/setup.py` | Cog with all Discord slash commands |
| `templates/dashboard.html` | Jinja2 template for the web dashboard (Civilization VI themed) |
| `Dockerfile` | Python 3.12-slim build, copies code, runs `bot.py` |
| `docker-compose.yml` | Orchestration: mounts volumes for data, injects env vars |
| `requirements.txt` | discord.py, flask, python-dotenv |
| `.env` | Secrets (gitignored) |
| `.env.example` | Secrets template (committed) |
| `.gitignore` | Excludes .env, venv, __pycache__, data.json, config.json, turn_history.json, bot.log |

---

## Environment Variables (.env)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord bot token |
| `DISCORD_GUILD_ID` | Yes | Discord server/guild ID where slash commands are registered |
| `PORT` | No (default 5000) | Flask server port |
| `PUBLIC_URL` | No (default localhost) | Public URL for webhook and dashboard (e.g. `https://civ6.example.com`) |

---

## Data Flow

### 1. Player Registration
```
Discord User → /register <username>
  → cogs/setup.py:register()
  → storage.register_player() → data.json
```

### 2. Turn Notification
```
Civ 6 → POST /webhook {value1, value2, value3}
  → webhook_server.py:webhook()
  → storage.get_discord_id() (lookup data.json)
  → asyncio.run_coroutine_threadsafe(_send_to_discord(...))
  → Discord message: "@player, it's your turn!"
  → storage.record_turn() → turn_history.json
  → if round complete → _build_recap_message() → storage.get_player_stats()
```

### 3. Dashboard
```
Browser → GET /game/<name>
  → webhook_server.py:dashboard()
  → storage.get_player_stats() (calculates averages from turn_history.json)
  → storage.get_all_games() (sidebar list)
  → render_template("dashboard.html")
```

### 4. Drag-and-Drop Ordering
```
Browser → POST /api/game-order {games: [...]}
  → storage.set_game_order() → config.json

Browser → POST /api/game/<name>/order {players: [...]}
  → storage.set_player_order() → config.json

Browser → DELETE /api/game/<name>/order
  → storage.clear_player_order() → config.json
```

---

## Code Conventions

- **Python 3.12+** (verified via Dockerfile and venv)
- **PEP 8** style (4 spaces, snake_case, type hints where relevant)
- **Logging**: standard `logging` module, format `"%(asctime)s [%(name)s] %(levelname)s: %(message)s"`
- **Persistence**: JSON flat files (no database). All functions in `storage.py` are synchronous.
- **Discord.py**: Slash commands via `app_commands`, prefix commands via `!`. Commands are synced to a specific guild (not global).
- **Flask**: Implicit app factory (`app = Flask(__name__)` at module level). Jinja2 templates.
- **Docker**: Container runs as root (no USER directive). Volumes mount data for persistence.

### Usernames
- Always stored in **lowercase** (see `storage.py:32`, `storage.py:37`, `storage.py:45`)
- User input is converted to lowercase before any operation

### Turn Numbers
- Stored as **string** (`str(turn)`) in `record_turn()` and `get_current_turn()`
- Compared as `int(turn)` in `is_round_complete()` and `get_player_stats()`

---

## How to Run Locally

```bash
# Create venv and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with your credentials
cp .env.example .env
# Edit .env with real bot token and guild ID

# Run
python bot.py
```

## How to Run with Docker

```bash
# Create .env with credentials first
docker compose up -d
```

The dashboard is available at `http://localhost:5000` (or the configured `PUBLIC_URL`).

---

## Testing

There are currently **no automated tests**. To test manually:
1. Start the bot with `python bot.py`
2. Use slash commands on Discord (`/register`, `/players`, `/channel`, `/status`)
3. Simulate a webhook with curl:
   ```bash
   curl -X POST http://localhost:5000/webhook \
     -H "Content-Type: application/json" \
     -d '{"value1":"My Game","value2":"username","value3":"1"}'
   ```
4. Access the dashboard at `http://localhost:5000`

---

## Notes for Modifications

- **Add a new slash command**: Create it in `cogs/setup.py` as a method of the `Setup` class decorated with `@app_commands.command()`
- **Add a new API route**: Add it in `webhook_server.py` as a function decorated with `@app.route(...)`
- **Add a new persistent data type**: Add load/save functions in `storage.py` using the `_load_json`/`_save_json` pattern
- **Change dashboard visuals**: Edit `templates/dashboard.html` — CSS is inline in `<style>` and JS is at the end in `<script>`
- **Add a new env var**: Read it in `bot.py` with `os.getenv()`, document in `.env.example` and `docker-compose.yml` if needed
- **NEVER** commit `.env`, `data.json`, `config.json`, or `turn_history.json` — they are in `.gitignore`
