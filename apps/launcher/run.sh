#!/bin/bash
# Enhanced launcher script for Claude MCP Launcher

# Get the directory this script is in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to that directory
cd "$DIR"

# Create log directory if it doesn't exist
LOG_DIR="$DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting Claude MCP Launcher"

# Check for Python
if ! command -v python3 &> /dev/null; then
    log "ERROR: Python 3 not found"
    osascript -e 'display dialog "Python 3 is required but not found. Please install Python 3 and try again." buttons {"OK"} default button "OK" with icon stop with title "Error"'
    exit 1
fi

# Check for virtual environment
if [ -d ".venv" ]; then
    log "Using virtual environment"
    source .venv/bin/activate || {
        log "WARNING: Failed to activate virtual environment, using system Python"
    }
fi

# Check for required packages
if ! python3 -c "import PyQt5" &> /dev/null; then
    log "Installing required packages"
    echo "Installing required packages..."
    python3 -m pip install -r requirements.txt || {
        log "ERROR: Failed to install packages"
        osascript -e 'display dialog "Failed to install required packages. Check your internet connection and try again." buttons {"OK"} default button "OK" with icon stop with title "Error"'
        exit 1
    }
fi

# Log Python and package versions
log "Python version: $(python3 --version)"
log "PyQt5 version: $(python3 -c "import PyQt5; print(PyQt5.__version__)" 2>/dev/null || echo 'unknown')"

# Run the launcher
log "Launching application"
echo "Starting Claude MCP Launcher..."
python3 main.py

# Record exit code
EXIT_CODE=$?
log "Application exited with code $EXIT_CODE"

exit $EXIT_CODE
