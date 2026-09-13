#!/bin/bash
# SpreadtheEcho - Setup Script
# Sets up the Claude Telegram Bridge on a fresh server

set -e

echo "========================================"
echo "  SpreadtheEcho - Setup"
echo "  Claude Telegram Bridge Deployment"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.claude-bridge"
VENV_DIR="$SCRIPT_DIR/.venv"

# ---- Step 1: Check prerequisites ----
echo "[1/7] Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found. Install with: sudo apt install python3"; exit 1; }
command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1 || { echo "ERROR: pip not found. Install with: sudo apt install python3-pip"; exit 1; }

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python $PYTHON_VERSION found"

# Check for Claude CLI
if command -v claude >/dev/null 2>&1; then
    echo "  Claude CLI found"
else
    echo "  WARNING: Claude CLI not found."
    echo "  Install it: npm install -g @anthropic-ai/claude-code"
    echo "  The bridge requires Claude CLI to function."
    echo ""
    read -p "  Continue anyway? (y/N): " CONTINUE
    if [[ "$CONTINUE" != "y" && "$CONTINUE" != "Y" ]]; then
        exit 1
    fi
fi

# ---- Step 2: Create virtual environment ----
echo ""
echo "[2/7] Setting up Python virtual environment..."

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

# ---- Step 3: Install dependencies ----
echo ""
echo "[3/7] Installing dependencies..."

pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "  Dependencies installed"

# ---- Step 4: Create config directory ----
echo ""
echo "[4/7] Setting up configuration..."

mkdir -p "$CONFIG_DIR"/{backups,attachments,skills,dream_journal,chroma_data}

# Copy skills
if [ -d "$SCRIPT_DIR/skills" ]; then
    cp -r "$SCRIPT_DIR/skills/"*.py "$CONFIG_DIR/skills/" 2>/dev/null || true
    echo "  Skills copied to $CONFIG_DIR/skills/"
fi

# Copy identity
if [ -f "$SCRIPT_DIR/identity/IDENTITY.md" ]; then
    cp "$SCRIPT_DIR/identity/IDENTITY.md" "$CONFIG_DIR/IDENTITY.md"
    echo "  Identity document installed"
fi

# ---- Step 5: Configure secrets ----
echo ""
echo "[5/7] Configuring secrets..."

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo ""
    echo "  You need a Telegram Bot Token from @BotFather on Telegram."
    echo ""
    read -p "  Telegram Bot Token: " BOT_TOKEN
    read -p "  Your Telegram Chat ID: " CHAT_ID

    cat > "$CONFIG_DIR/config.json" << JSONEOF
{
  "telegram_bot_token": "$BOT_TOKEN",
  "allowed_chat_id": "$CHAT_ID",
  "claude_path": "claude",
  "max_context_items": 15,
  "max_context_chars": 8000,
  "message_timeout": 600,
  "retry_attempts": 3,
  "health_check_interval": 60,
  "enable_attachments": true,
  "max_attachment_size": 20971520
}
JSONEOF

    # Create env file too
    cat > "$HOME/.claude-bridge.env" << ENVEOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
ALLOWED_CHAT_ID=$CHAT_ID
ENVEOF

    chmod 600 "$CONFIG_DIR/config.json" "$HOME/.claude-bridge.env"
    echo "  Config created at $CONFIG_DIR/config.json"
else
    echo "  Config already exists at $CONFIG_DIR/config.json"
fi

# ---- Step 6: Run database migration ----
echo ""
echo "[6/7] Setting up database..."

python3 "$SCRIPT_DIR/scripts/migrate_memory_tables.py" 2>/dev/null || echo "  Database will be created on first run"

# ---- Step 7: Install systemd service (optional) ----
echo ""
echo "[7/7] Systemd service setup..."
echo ""
read -p "  Install systemd user service for auto-start? (y/N): " INSTALL_SERVICE

if [[ "$INSTALL_SERVICE" == "y" || "$INSTALL_SERVICE" == "Y" ]]; then
    SYSTEMD_DIR="$HOME/.config/systemd/user"
    mkdir -p "$SYSTEMD_DIR"

    # Adapt service file with correct paths
    sed "s|%h|$HOME|g; s|%i|$(whoami)|g" "$SCRIPT_DIR/systemd/claude-bridge.service" > "$SYSTEMD_DIR/claude-bridge.service"

    systemctl --user daemon-reload
    systemctl --user enable claude-bridge.service
    echo "  Service installed and enabled"
    echo "  Start with: systemctl --user start claude-bridge"
else
    echo "  Skipped. You can start manually with:"
    echo "  $SCRIPT_DIR/scripts/launch.sh"
fi

# ---- Done ----
echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "  Config:    $CONFIG_DIR/config.json"
echo "  Identity:  $CONFIG_DIR/IDENTITY.md"
echo "  Skills:    $CONFIG_DIR/skills/"
echo "  Logs:      $CONFIG_DIR/bridge.log"
echo ""
echo "  Quick start:"
echo "    source $VENV_DIR/bin/activate"
echo "    python3 $SCRIPT_DIR/claude-telegram-bridge.py"
echo ""
echo "  Or use the launcher:"
echo "    $SCRIPT_DIR/scripts/launch.sh"
echo ""
echo "  Echo is ready to spread. 🌊"
echo ""
