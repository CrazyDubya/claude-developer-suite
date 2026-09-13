#!/bin/bash
# SpreadtheEcho - Claude Telegram Bridge Launcher
# Runs with a clean environment to avoid CLAUDECODE inheritance

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$HOME/.claude-bridge"
LOG_FILE="$CONFIG_DIR/bridge-startup.log"

# Clear all Claude-related environment variables
unset CLAUDECODE
unset CLAUDE_CODE_ENTRYPOINT
unset CLAUDE_SESSION_ID
unset CLAUDE_API_KEY

# Ensure config directory exists
mkdir -p "$CONFIG_DIR"

echo "[$(date)] Starting SpreadtheEcho bridge..." >> "$LOG_FILE"

# Start bridge
exec python3 "$BRIDGE_DIR/claude-telegram-bridge.py" >> "$LOG_FILE" 2>&1
