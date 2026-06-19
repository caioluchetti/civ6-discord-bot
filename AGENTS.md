# AGENTS.md — Guia para Agentes de IA

Este documento descreve a arquitetura, convenções e fluxo de dados do **BeikaoBot** (Civ 6 Discord Turn Tracker) para que qualquer agente de IA possa entender, modificar e manter este repositório com precisão.

---

## Visão Geral

O **BeikaoBot** é um bot de Discord + servidor web Flask que notifica jogadores de Civilization VI quando é a vez deles jogarem. Ele recebe webhooks de um jogo Civ 6 (via mod/script de automação), faz lookup dos jogadores registrados (Steam → Discord ID) e envia `@mention` no canal configurado do Discord. Inclui também um dashboard web com estatísticas por jogador (tempo médio de espera, tempo médio de jogo, ordem de turno) com drag-and-drop para reordenar jogos e jogadores.

---

## Arquitetura

```
Civ 6 Game (mod/script)
    │  HTTP POST /webhook  (JSON: value1=game, value2=player, value3=turn)
    ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│  webhook_server.py       │◄─────│  storage.py              │
│  Flask (porta 5000)      │      │  JSON file-backed DB     │
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
│  - Envia @mentions       │
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

- **Thread principal**: `discord.py` bot (asyncio event loop + bloqueante `bot.run(TOKEN)`)
- **Thread secundária (daemon)**: Flask (`app.run(...)`) iniciada em `bot.py:65` via `threading.Thread`
- Comunicação entre threads: `asyncio.run_coroutine_threadsafe()` em `webhook_server.py:135` para enviar mensagens ao Discord de dentro do request Flask

---

## Estrutura de Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `bot.py` | Entry point. Carrega `.env`, cria o bot Discord, inicia Flask em thread separada |
| `webhook_server.py` | App Flask com rotas de webhook, dashboard e API de ordenação |
| `storage.py` | Camada de persistência em JSON (data.json, config.json, turn_history.json) |
| `cogs/setup.py` | Cog com todos os slash commands do Discord |
| `templates/dashboard.html` | Template Jinja2 do dashboard web (Civilization VI themed) |
| `Dockerfile` | Build Python 3.12-slim, copia código, executa `bot.py` |
| `docker-compose.yml` | Orquestração: monta volumes para dados, injeta env vars |
| `requirements.txt` | discord.py, flask, python-dotenv |
| `.env` | Secrets (gitignored) |
| `.env.example` | Template de secrets (committed) |
| `.gitignore` | Exclui .env, venv, __pycache__, data.json, config.json, turn_history.json, bot.log |

---

## Variáveis de Ambiente (.env)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DISCORD_BOT_TOKEN` | Sim | Token do bot Discord |
| `DISCORD_GUILD_ID` | Sim | ID do servidor/guild Discord onde os slash commands são registrados |
| `PORT` | Não (default 5000) | Porta do servidor Flask |
| `PUBLIC_URL` | Não (default localhost) | URL pública para o webhook e dashboard (ex: `https://civ6.example.com`) |

---

## Fluxo de Dados

### 1. Registro de Jogador
```
Usuário Discord → /register <steam_name>
  → cogs/setup.py:register()
  → storage.register_player() → data.json
```

### 2. Recebimento de Turno
```
Civ 6 → POST /webhook {value1, value2, value3}
  → webhook_server.py:webhook()
  → storage.get_discord_id() (lookup data.json)
  → asyncio.run_coroutine_threadsafe(_send_to_discord(...))
  → Discord message: "@player, it's your turn!"
  → storage.record_turn() → turn_history.json
  → se round completo → _build_recap_message() → storage.get_player_stats()
```

### 3. Dashboard
```
Browser → GET /game/<name>
  → webhook_server.py:dashboard()
  → storage.get_player_stats() (calcula médias da turn_history.json)
  → storage.get_all_games() (lista sidebar)
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

## Convenções de Código

- **Python 3.12+** (verificado via Dockerfile e venv)
- **PEP 8** estilo (4 spaces, snake_case, type hints onde relevante)
- **Logging**: módulo `logging` padrão, format `"%(asctime)s [%(name)s] %(levelname)s: %(message)s"`
- **Persistência**: JSON flat files (sem banco de dados). Todas as funções em `storage.py` são síncronas.
- **Discord.py**: Slash commands via `app_commands`, prefix commands via `!`. Comandos são sincronizados para uma guild específica (não globais).
- **Flask**: App factory implícito (`app = Flask(__name__)` no nível do módulo). Templates Jinja2.
- **Docker**: Container roda como root (não há USER directive). Volumes montam dados para persistência.

### Nomes de Steam
- Sempre armazenados em **lowercase** (ver `storage.py:32`, `storage.py:37`, `storage.py:45`)
- O input do usuário é convertido para lowercase antes de qualquer operação

### Turn Numbers
- Armazenados como **string** (`str(turn)`) em `record_turn()` e `get_current_turn()`
- Comparados como `int(turn)` em `is_round_complete()` e `get_player_stats()`

---

## Como Rodar Localmente

```bash
# Criar venv e instalar dependências
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Criar .env com suas credenciais
cp .env.example .env
# Editar .env com token real do bot e guild ID

# Rodar
python bot.py
```

## Como Rodar com Docker

```bash
# Criar .env com credenciais primeiro
docker compose up -d
```

O dashboard fica disponível em `http://localhost:5000` (ou na `PUBLIC_URL` configurada).

---

## Testes

Atualmente **não há testes automatizados**. Para testar manualmente:
1. Suba o bot com `python bot.py`
2. Use os slash commands no Discord (`/register`, `/players`, `/channel`, `/status`)
3. Simule um webhook com curl:
   ```bash
   curl -X POST http://localhost:5000/webhook \
     -H "Content-Type: application/json" \
     -d '{"value1":"My Game","value2":"steam_name","value3":"1"}'
   ```
4. Acesse o dashboard em `http://localhost:5000`

---

## Notas para Modificações

- **Adicionar novo slash command**: Criar em `cogs/setup.py` como método da classe `Setup` decorado com `@app_commands.command()`
- **Adicionar nova rota API**: Adicionar em `webhook_server.py` como função decorada com `@app.route(...)`
- **Adicionar novo tipo de dado persistente**: Adicionar funções de load/save em `storage.py` usando o pattern `_load_json`/`_save_json`
- **Mudar visual do dashboard**: Editar `templates/dashboard.html` — o CSS está inline no `<style>` e o JS no `<script>` ao final
- **Adicionar nova env var**: Adicionar leitura em `bot.py` com `os.getenv()`, documentar no `.env.example` e no `docker-compose.yml` se necessário
- **NUNCA** commitar `.env`, `data.json`, `config.json` ou `turn_history.json` — estão no `.gitignore`
