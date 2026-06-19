# ⚔️ BeikaoBot — Civilization VI Discord Turn Tracker

A Discord bot with a web dashboard that notifies Civilization VI players when it's their turn to play, featuring wait time stats, average play time, and turn order. Perfect for asynchronous multiplayer matches (play-by-cloud or hotseat with a bot).

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/discord.py-2.3+-5865F2.svg" alt="discord.py">
  <img src="https://img.shields.io/badge/flask-3.0+-000000.svg" alt="Flask">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg" alt="Docker">
</p>

---

## Features

- **Webhook Notifications**: Receives POST from Civ 6 and pings the next player on Discord with `@mention`
- **Multi-Game**: Supports multiple simultaneous matches, each with its own dashboard
- **Themed Web Dashboard**: Civilization VI-inspired interface showing live stats
- **Player Stats**: Average wait time, average play time, last turn
- **Round Recap**: When all players finish their turn, the bot sends a full summary
- **Drag-and-Drop**: Reorder games in the sidebar and set manual player turn order
- **Dockerized**: Deploy with a single command via Docker Compose

---

## How It Works

```
┌──────────────┐     POST /webhook      ┌──────────────┐     @mention       ┌──────────┐
│   Civ 6      │ ──────────────────────→ │  BeikaoBot   │ ─────────────────→ │ Discord  │
│  (webhook)   │   {game, player, turn}  │  Flask+Bot   │   "Your turn!"     │ Channel  │
└──────────────┘                         └──────┬───────┘                   └──────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  Dashboard   │
                                         │  Stats       │
                                         │  Drag&Drop   │
                                         └──────────────┘
```

1. Players register on Discord with `/register <username>`
2. Configure the Civ 6 webhook (via mod or script) to point to `https://your-bot.com/webhook`
3. When a player finishes their turn, Civ 6 sends a POST and the bot notifies the next player
4. Access the dashboard at `https://your-bot.com` to see live stats

---

## Prerequisites

- **Python 3.12+** (or Docker)
- A **Discord Bot Token** ([Discord Developer Portal](https://discord.com/developers/applications))
- A **server with port 5000 publicly exposed** (to receive webhooks from Civ 6)

---

## Quick Start

### With Docker (Recommended)

```bash
git clone https://github.com/caioluchetti/civ6-discord-bot.git
cd civ6-discord-bot
cp .env.example .env
# Edit .env with your token and guild ID
nano .env
docker compose up -d
```

The dashboard will be available at `http://your-ip:5000`.

### Without Docker

```bash
git clone https://github.com/caioluchetti/civ6-discord-bot.git
cd civ6-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your token and guild ID
python bot.py
```

---

## Configuration

Create a `.env` file at the project root:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here
PORT=5000
PUBLIC_URL=https://civ6.your-domain.com
```

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | — | Discord bot token |
| `DISCORD_GUILD_ID` | Yes | — | Discord server ID |
| `PORT` | No | `5000` | Web server port |
| `PUBLIC_URL` | No | `http://localhost:5000` | Public URL (used for webhook and dashboard) |

---

## Discord Commands

| Command | Description |
|---------|-------------|
| `/register <username>` | Links your game username to your Discord |
| `/unregister <username>` | Removes a registered game username |
| `/players` | Lists all registered players |
| `/webhook` | Shows the webhook URL to configure in Civ 6 |
| `/channel` | Sets the current channel as the notification channel |
| `/status` | Shows bot configuration status |

---

## Setting Up the Civ 6 Webhook

Civ 6 has no native webhook support. You'll need:

- **Mod**: A mod that detects turn completion and sends an HTTP POST
- **External script**: A script that reads game logs and POSTs when it detects a turn change

The endpoint expects JSON in this format:

```json
{
  "value1": "Game Name",
  "value2": "player_game_username",
  "value3": "42"
}
```

| Field | Description |
|-------|-------------|
| `value1` | Game name (unique identifier, e.g. "Brazil vs World") |
| `value2` | Game username of the player who just finished their turn (case-insensitive) |
| `value3` | Current turn number |

---

## Web Dashboard

Visit `https://your-bot.com` to see:

- **Sidebar**: List of all games with drag-and-drop to reorder
- **Stats Table**: Per player — order, average wait time, average play time, last turn
- **Order Editing**: "Edit Turn Order" button for manual ordering (drag-and-drop), with "Reset Order" to revert to automatic
- **Auto-refresh**: Page refreshes every 30 seconds

The visual theme is inspired by Civilization VI (gold colors, Cinzel font, dark background with hexagonal pattern).

---

## Project Structure

```
civ6-discord-bot/
├── bot.py                  # Entry point: Discord bot + Flask thread
├── webhook_server.py       # Flask: webhook, dashboard, APIs
├── storage.py              # JSON persistence (no database)
├── cogs/
│   └── setup.py            # Discord slash commands
├── templates/
│   └── dashboard.html      # Web dashboard template
├── Dockerfile              # Docker image build
├── docker-compose.yml      # Docker orchestration
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
└── .gitignore
```

---

## Deploy

The project is designed for Docker deployment on any VPS. It is recommended to use a reverse proxy (Nginx, Caddy) with HTTPS in front:

```nginx
# Example Nginx
server {
    server_name civ6.your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Contributing

Contributions are welcome! Open an issue or PR on GitHub.

---

## License

MIT
