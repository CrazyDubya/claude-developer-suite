#!/bin/bash
# Enhanced installation script for Claude MCP Launcher

# Get the directory this script is in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create log directory
LOG_DIR="$DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/install_$(date +%Y%m%d_%H%M%S).log"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Change to that directory
cd "$DIR"

log "Starting installation of Claude MCP Launcher"
log "Installation directory: $DIR"

echo "======================================="
echo "Claude MCP Launcher Installation"
echo "======================================="
echo ""

# Check for Python
log "Checking for Python 3"
if ! command -v python3 &> /dev/null; then
    log "ERROR: Python 3 not found"
    echo "Python 3 is required but not found."
    echo "Would you like to install Python 3 using Homebrew? (y/n)"
    read -p "> " INSTALL_PYTHON
    
    if [[ $INSTALL_PYTHON =~ ^[Yy]$ ]]; then
        log "Installing Python via Homebrew"
        if ! command -v brew &> /dev/null; then
            log "Homebrew not found, installing"
            echo "Homebrew not found. Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
                log "ERROR: Failed to install Homebrew"
                echo "Failed to install Homebrew. Please install Python 3 manually and try again."
                exit 1
            }
        fi
        
        echo "Installing Python 3 via Homebrew..."
        brew install python || {
            log "ERROR: Failed to install Python via Homebrew"
            echo "Failed to install Python 3. Please install Python 3 manually and try again."
            exit 1
        }
    else
        log "User declined to install Python"
        echo "Please install Python 3 manually and run this script again."
        exit 1
    fi
fi

PYTHON_VERSION=$(python3 --version)
log "Using $PYTHON_VERSION"
echo "Using $PYTHON_VERSION"

# Set up virtual environment
log "Setting up virtual environment"
echo "Setting up Python virtual environment..."

if [ -d ".venv" ]; then
    log "Removing existing virtual environment"
    echo "Removing existing virtual environment..."
    rm -rf .venv
fi

log "Creating new virtual environment"
echo "Creating new virtual environment..."
python3 -m venv .venv || {
    log "WARNING: Failed to create virtual environment, continuing with system Python"
    echo "WARNING: Failed to create virtual environment. Continuing with system Python."
    USE_VENV=false
}

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    log "Activating virtual environment"
    echo "Activating virtual environment..."
    source .venv/bin/activate || {
        log "WARNING: Failed to activate virtual environment, continuing with system Python"
        echo "WARNING: Failed to activate virtual environment. Continuing with system Python."
        USE_VENV=false
    }
    USE_VENV=true
else
    USE_VENV=false
fi

# Install required packages
log "Installing required Python packages"
echo "Installing required Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt || {
    log "ERROR: Failed to install required packages"
    echo "Failed to install required packages. Check your internet connection and try again."
    exit 1
}

# Create directories
log "Creating application directories"
echo "Creating application directories..."

CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
CLAUDE_MCP_DIR="$CLAUDE_CONFIG_DIR/MCP Launcher"
CLAUDE_USER_CONFIGS="$CLAUDE_MCP_DIR/user_configs"

for DIR in "$CLAUDE_CONFIG_DIR" "$CLAUDE_MCP_DIR" "$CLAUDE_USER_CONFIGS"; do
    if [ ! -d "$DIR" ]; then
        log "Creating directory: $DIR"
        mkdir -p "$DIR" || {
            log "ERROR: Failed to create directory: $DIR"
            echo "Failed to create directory: $DIR"
            echo "Check permissions and try again."
            exit 1
        }
    fi
done

# Make scripts executable
log "Making scripts executable"
echo "Making scripts executable..."
chmod +x run.sh

# Create desktop shortcut
log "Creating desktop shortcut"
echo ""
echo "Would you like to create a desktop shortcut? (y/n)"
read -p "> " CREATE_SHORTCUT

if [[ $CREATE_SHORTCUT =~ ^[Yy]$ ]]; then
    SCRIPT_PATH="$HOME/Desktop/Claude MCP Launcher.app"
    
    log "Creating desktop shortcut at: $SCRIPT_PATH"
    echo "Creating desktop shortcut..."
    
    # Remove existing app if it exists
    if [ -d "$SCRIPT_PATH" ]; then
        log "Removing existing shortcut"
        rm -rf "$SCRIPT_PATH"
    fi
    
    # Create the app directory structure
    mkdir -p "$SCRIPT_PATH/Contents/MacOS"
    mkdir -p "$SCRIPT_PATH/Contents/Resources"
    
    # Create the Info.plist file
    cat > "$SCRIPT_PATH/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>launcher</string>
	<key>CFBundleIconFile</key>
	<string>AppIcon</string>
	<key>CFBundleIdentifier</key>
	<string>com.claudemcplauncher</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>Claude MCP Launcher</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.0</string>
	<key>NSHighResolutionCapable</key>
	<true/>
</dict>
</plist>
EOF
    
    # Create the launcher script
    cat > "$SCRIPT_PATH/Contents/MacOS/launcher" << EOF
#!/bin/bash
cd "$DIR"
"$DIR/run.sh"
EOF
    
    # Make the launcher script executable
    chmod +x "$SCRIPT_PATH/Contents/MacOS/launcher"
    
    # Use a default icon or copy one if available
    if [ -f "$DIR/icons/claude_launcher.icns" ]; then
        cp "$DIR/icons/claude_launcher.icns" "$SCRIPT_PATH/Contents/Resources/AppIcon.icns"
    else
        log "No icon found, using default"
        # Create a default icon using system icons
        SYSTEM_ICON="/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ApplicationIcon.icns"
        if [ -f "$SYSTEM_ICON" ]; then
            cp "$SYSTEM_ICON" "$SCRIPT_PATH/Contents/Resources/AppIcon.icns"
        fi
    fi
    
    log "Desktop shortcut created successfully"
    echo "Desktop shortcut created successfully!"
fi

# Final instructions
log "Installation completed successfully"
echo ""
echo "======================================="
echo "Installation completed successfully!"
echo "======================================="
echo ""
echo "You can now run the launcher with: $DIR/run.sh"
echo "Or use the desktop shortcut if you created one."
echo ""
echo "Thank you for installing Claude MCP Launcher!"

exit 0