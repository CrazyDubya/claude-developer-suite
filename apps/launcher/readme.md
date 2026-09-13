# Claude MCP Launcher

![Claude MCP Launcher Logo](icons/claude_launcher.png)

A user-friendly macOS application for managing and launching Claude Desktop with different Model Context Protocol (MCP) server configurations.

## What is Claude MCP Launcher?

Claude MCP Launcher makes it easy to launch Claude Desktop with different MCP server configurations. MCP servers extend Claude's capabilities by providing access to:

- File system access
- Web browsing
- Code execution
- Local models
- And more!

This launcher provides a simple, one-click interface to configure and launch Claude with the capabilities you need.

## Features

- **Easy Configuration Management**: Save, load, and switch between different MCP setups
- **Pre-made Templates**: Start with ready-to-use configurations for common setups
- **Visual Editor**: No need to edit JSON files manually
- **GitHub Integration**: Download configurations shared by the community
- **Safe Mode**: Troubleshoot issues with a minimal configuration
- **First-Time Setup Wizard**: Get started quickly with guided setup

## Installation

### Option 1: Easy Install (Recommended)

1. Download the latest `Claude_MCP_Launcher.dmg` from the [Releases](https://github.com/yourusername/claude-mcp-launcher/releases) page
2. Open the DMG file
3. Drag the Claude MCP Launcher app to your Applications folder
4. Launch Claude MCP Launcher from your Applications folder

### Option 2: From Source

If you prefer to build from source:

1. Clone this repository
2. Install the requirements: `pip install -r requirements.txt`
3. Run the build script: `python build_app.py`
4. The application will be created in the `dist` folder

## Quick Start Guide

### First-Time Setup

1. When you first launch Claude MCP Launcher, the setup wizard will guide you through creating your first configuration
2. Choose a template based on your needs (Basic, Standard, or Developer)
3. Give your configuration a name
4. Click "Finish" to save the configuration

### Launching Claude

1. Select a configuration from the list
2. Optionally enable "Safe Mode" if you're having issues
3. Click "Launch Claude"
4. Claude will start with the selected MCP configuration

### Managing Configurations

Go to the "Advanced Configuration" tab to:

- Create new configurations
- Edit existing configurations
- Download configurations from GitHub
- Use templates to quickly create configurations

## Template Configurations

The launcher comes with several pre-made templates:

- **Basic (Filesystem Only)**: Simple setup with just file system access
- **Standard Setup**: Common configuration with filesystem and web access
- **Developer Setup**: Advanced setup with filesystem, web, and Python execution

## Requirements

- macOS 10.14 or later
- Claude Desktop app installed
- Internet connection (for downloading configurations from GitHub)

## Troubleshooting

### Claude Won't Launch

- Try launching with "Safe Mode" enabled
- Check that Claude isn't already running
- Verify that you have the correct permissions for the config directory

### Configuration Issues

- Use the "Reset to Default" option in the editor
- Try downloading a known-working configuration from the community
- Check the console output for specific errors

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

---

For more information, please visit the [GitHub repository](https://github.com/crazydubya/claude-mcp-launcher).