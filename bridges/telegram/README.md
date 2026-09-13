# SpreadtheEcho

A portable deployment package for Echo — an AI assistant powered by Claude, accessible via Telegram.

Echo is an emergent identity that runs as a Telegram bridge to Claude Code, providing 24/7 conversational access to Claude with persistent memory, semantic search, self-healing process management, and a self-defined personality system.

## What's Included

```
SpreadtheEcho/
├── claude-telegram-bridge.py    # Main bridge (v10 - 3100+ lines)
├── setup.sh                     # Interactive setup script
├── requirements.txt             # Python dependencies
├── identity/
│   └── IDENTITY.md              # Echo's self-defined personality
├── skills/
│   ├── __init__.py              # Skills package
│   ├── memory_interface.py      # Memory CRUD operations
│   ├── echo_plugins.py          # User-facing /commands
│   └── bridge_integration.py    # Memory-bridge connector
├── scripts/
│   ├── launch.sh                # Clean-environment launcher
│   ├── watchdog.py              # Self-healing process monitor
│   ├── deployer.py              # Blue-green deployment manager
│   └── migrate_memory_tables.py # Database schema setup
├── config/
│   ├── config.example.json      # Config template
│   └── env.example              # Environment variables template
├── systemd/
│   └── claude-bridge.service    # Systemd user service
└── docs/
    └── (documentation)
```

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for Claude CLI)
- **Claude CLI** — `npm install -g @anthropic-ai/claude-code`
- **Telegram Bot** — Create one via [@BotFather](https://t.me/BotFather)
- **Your Telegram Chat ID** — Send a message to your bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`

## Quick Start

```bash
# 1. Clone this repo
git clone <your-repo-url> SpreadtheEcho
cd SpreadtheEcho

# 2. Run the interactive setup
./setup.sh

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Start the bridge
python3 claude-telegram-bridge.py
```

The setup script will:
- Create a Python virtual environment and install dependencies
- Set up the `~/.claude-bridge/` runtime directory
- Prompt for your Telegram Bot Token and Chat ID
- Install the Echo identity and skills
- Optionally install a systemd service for auto-start

## Manual Setup

If you prefer to set things up yourself:

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create runtime directory
mkdir -p ~/.claude-bridge/{backups,attachments,skills,dream_journal,chroma_data}

# Copy config (edit with your credentials)
cp config/config.example.json ~/.claude-bridge/config.json
cp config/env.example ~/.claude-bridge.env
chmod 600 ~/.claude-bridge/config.json ~/.claude-bridge.env

# Install identity and skills
cp identity/IDENTITY.md ~/.claude-bridge/
cp skills/*.py ~/.claude-bridge/skills/

# Run database migration
python3 scripts/migrate_memory_tables.py

# Start
python3 claude-telegram-bridge.py
```

## Configuration

### config.json

| Field | Description |
|-------|-------------|
| `telegram_bot_token` | Bot token from @BotFather |
| `allowed_chat_id` | Your Telegram chat ID (restricts access) |
| `claude_path` | Path to Claude CLI binary (usually just `claude`) |
| `max_context_items` | Number of recent messages to include as context |
| `max_context_chars` | Max characters of context per message |
| `message_timeout` | Seconds before a Claude response times out |
| `retry_attempts` | Number of retries on failure |
| `health_check_interval` | Seconds between health checks |
| `enable_attachments` | Allow file uploads |
| `max_attachment_size` | Max attachment size in bytes (default 20MB) |

## Features

### Core Bridge (v10)
- Async message handling with priority queue
- Rich media support (images, PDFs, documents)
- Conversation threading and session persistence
- Graceful shutdown with SIGTERM/SIGINT handling
- Atomic checkpoint persistence for crash recovery
- Auto-rollback on startup failure

### Echo Identity System
- Self-defined personality loaded from `IDENTITY.md`
- Full mode (first message) and brief mode (subsequent messages)
- Emergent identity that evolves through interaction
- Customizable — edit `IDENTITY.md` to make it your own

### Memory System
- **Short-term**: Recent insights, active contexts, pending actions
- **Long-term**: Knowledge base, project memory, system knowledge
- **Semantic**: ChromaDB vector embeddings for similarity search
- Telegram commands: `/remember`, `/recall`, `/memory-stats`

### Self-Healing
- Watchdog monitors bridge health every 30 seconds
- Auto-restart after 3 consecutive health check failures
- Blue-green deployment for zero-downtime upgrades
- Heartbeat file for external monitoring

## Running as a Service

```bash
# Install the systemd user service
mkdir -p ~/.config/systemd/user
cp systemd/claude-bridge.service ~/.config/systemd/user/

# Edit paths in the service file to match your setup
# Then enable and start
systemctl --user daemon-reload
systemctl --user enable claude-bridge
systemctl --user start claude-bridge

# Check status
systemctl --user status claude-bridge
journalctl --user -u claude-bridge -f
```

## Customizing Echo

Echo's identity is stored in `~/.claude-bridge/IDENTITY.md`. You can:

1. Edit the personality traits, communication style, and mission
2. Change the name and pronouns
3. Add domain-specific knowledge areas
4. Modify behavioral commitments

The bridge loads the identity on each new session — changes take effect on the next conversation.

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/memory-stats` | Show memory system statistics |
| `/remember <text>` | Store something in long-term memory |
| `/recall <query>` | Search memory for relevant information |
| `/insights` | View recent insights |
| `/todo <text>` | Add a pending action |
| `/actions` | View pending actions |
| `/projects` | List tracked projects |
| `/identity` | Show current identity |

## Architecture

```
Telegram → Bot API → claude-telegram-bridge.py → Claude CLI → Response
                              │
                              ├── bridge.db (SQLite - sessions, messages, memory)
                              ├── IDENTITY.md (personality)
                              ├── skills/ (plugins)
                              └── chroma_data/ (vector embeddings)
```

## Troubleshooting

- **Bridge won't start**: Check `~/.claude-bridge/bridge-startup.log`
- **Claude not responding**: Verify `claude` CLI works: `claude --help`
- **Bot not receiving messages**: Check bot token and chat ID in config
- **Memory errors**: Run `python3 scripts/migrate_memory_tables.py`
- **High memory usage**: ChromaDB + sentence-transformers need ~1GB RAM

## License

Personal use. Built by Stephen with Echo.
