# ⚔️ BeikaoBot — Civilization VI Discord Turn Tracker

Um bot de Discord com dashboard web que notifica jogadores de Civilization VI quando é a vez deles jogarem, com estatísticas de tempo de espera, tempo médio de jogo e ordem de turno. Perfeito para partidas multiplayer assíncronas (play-by-cloud ou hotseat com bot).

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/discord.py-2.3+-5865F2.svg" alt="discord.py">
  <img src="https://img.shields.io/badge/flask-3.0+-000000.svg" alt="Flask">
  <img src="https://img.shields.io/badge/docker-ready-2496ED.svg" alt="Docker">
</p>

---

## Funcionalidades

- **Notificações por Webhook**: Recebe POST do jogo Civ 6 e notifica o jogador da vez no Discord com `@mention`
- **Multi-Jogo**: Suporta múltiplas partidas simultâneas, cada uma com seu próprio dashboard
- **Dashboard Web Temático**: Interface com visual Civilization VI mostrando estatísticas ao vivo
- **Estatísticas por Jogador**: Tempo médio de espera, tempo médio de jogo, último turno
- **Recap de Rodada**: Quando todos os jogadores terminam o turno, o bot envia um resumo completo
- **Drag-and-Drop**: Reordene jogos na sidebar e defina ordem manual de turno dos jogadores
- **Dockerizado**: Deploy com um comando via Docker Compose

---

## Como Funciona

```
┌──────────────┐     POST /webhook      ┌──────────────┐     @mention       ┌──────────┐
│   Civ 6      │ ──────────────────────→ │  BeikaoBot   │ ─────────────────→ │ Discord  │
│  (webhook)   │   {game, player, turn}  │  Flask+Bot   │   "Sua vez!"      │ Channel  │
└──────────────┘                         └──────┬───────┘                   └──────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  Dashboard   │
                                         │  Estatísticas│
                                         │  Drag&Drop   │
                                         └──────────────┘
```

1. Jogadores se registram no Discord com `/register <steam_name>`
2. Configure o webhook no Civ 6 (via mod ou script) para apontar para `https://seu-bot.com/webhook`
3. Quando um jogador termina seu turno, o Civ 6 envia um POST e o bot notifica o próximo
4. Acesse o dashboard em `https://seu-bot.com` para ver estatísticas em tempo real

---

## Pré-requisitos

- **Python 3.12+** (ou Docker)
- Um **Discord Bot Token** ([Discord Developer Portal](https://discord.com/developers/applications))
- Um **servidor com porta 5000 exposta** publicamente (para receber webhooks do Civ 6)

---

## Instalação Rápida

### Com Docker (Recomendado)

```bash
git clone https://github.com/caioluchetti/civ6-discord-bot.git
cd civ6-discord-bot
cp .env.example .env
# Edite .env com seu token e guild ID
nano .env
docker compose up -d
```

O dashboard estará em `http://seu-ip:5000`.

### Sem Docker

```bash
git clone https://github.com/caioluchetti/civ6-discord-bot.git
cd civ6-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env com seu token e guild ID
python bot.py
```

---

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
DISCORD_BOT_TOKEN=seu_token_aqui
DISCORD_GUILD_ID=id_do_seu_servidor_discord
PORT=5000
PUBLIC_URL=https://civ6.seu-dominio.com
```

| Variável | Obrigatória | Padrão | Descrição |
|----------|:-----------:|--------|-----------|
| `DISCORD_BOT_TOKEN` | Sim | — | Token do bot do Discord |
| `DISCORD_GUILD_ID` | Sim | — | ID do servidor Discord |
| `PORT` | Não | `5000` | Porta do servidor web |
| `PUBLIC_URL` | Não | `http://localhost:5000` | URL pública (usada no webhook e dashboard) |

---

## Comandos do Discord

| Comando | Descrição |
|---------|-----------|
| `/register <steam_name>` | Vincula seu nome Steam ao seu Discord |
| `/unregister <steam_name>` | Remove um nome Steam registrado |
| `/players` | Lista todos os jogadores registrados |
| `/webhook` | Mostra a URL do webhook para configurar no Civ 6 |
| `/channel` | Define o canal atual como canal de notificações |
| `/status` | Mostra status da configuração do bot |

---

## Configurando o Webhook no Civ 6

O Civ 6 não tem suporte nativo a webhooks. Você precisará de:

- **Mod**: Um mod que detecte fim de turno e envie um HTTP POST
- **Script externo**: Um script que leia logs do jogo e faça POST quando detectar troca de turno

O endpoint espera um JSON no formato:

```json
{
  "value1": "Nome do Jogo",
  "value2": "nome_steam_do_jogador",
  "value3": "42"
}
```

| Campo | Descrição |
|-------|-----------|
| `value1` | Nome do jogo (identificador único, ex: "Brasil vs Mundo") |
| `value2` | Steam name do jogador que acabou de jogar (case-insensitive) |
| `value3` | Número do turno atual |

---

## Dashboard Web

Acesse `https://seu-bot.com` para ver:

- **Sidebar**: Lista de todos os jogos com drag-and-drop para reordenar
- **Tabela de Estatísticas**: Por jogador — ordem, tempo médio de espera, tempo médio de jogo, último turno
- **Edição de Ordem**: Botão "Edit Turn Order" para definir ordem manual (drag-and-drop), com "Reset Order" para voltar ao automático
- **Auto-refresh**: A página atualiza a cada 30 segundos

O tema visual é inspirado em Civilization VI (cores douradas, fonte Cinzel, background escuro com padrão hexagonal).

---

## Estrutura do Projeto

```
civ6-discord-bot/
├── bot.py                  # Entry point: Discord bot + Flask thread
├── webhook_server.py       # Flask: webhook, dashboard, APIs
├── storage.py              # Persistência em JSON (sem banco de dados)
├── cogs/
│   └── setup.py            # Slash commands do Discord
├── templates/
│   └── dashboard.html      # Template do dashboard web
├── Dockerfile              # Build da imagem Docker
├── docker-compose.yml      # Orquestração Docker
├── requirements.txt        # Dependências Python
├── .env.example            # Template de variáveis de ambiente
└── .gitignore
```

---

## Deploy

O projeto é feito para deploy com Docker em qualquer VPS. Recomenda-se usar um proxy reverso (Nginx, Caddy) com HTTPS na frente:

```nginx
# Exemplo Nginx
server {
    server_name civ6.seu-dominio.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Contribuindo

Contribuições são bem-vindas! Abra uma issue ou PR no GitHub.

---

## Licença

MIT
