"""
ConfigManager - Handles saving, loading, and modifying Claude MCP configurations
Enhanced version with template support and more robust error handling
"""

import os
import json
import shutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class ConfigError(Exception):
    """Custom exception for configuration errors"""
    pass

class ConfigManager:
    """Manages Claude Desktop MCP configurations"""

    # Configuration schema for validation
    CONFIG_SCHEMA = {
        "required": ["servers", "version"],
        "properties": {
            "servers": {"type": "array"},
            "version": {"type": "string"}
        }
    }

    def __init__(self, claude_config_path: str, launcher_config_path: str):
        """Initialize the config manager with proper path validation"""
        if not claude_config_path or not launcher_config_path:
            raise ConfigError("Configuration paths cannot be empty")

        self.claude_config_path = os.path.expanduser(claude_config_path)
        self.launcher_config_path = os.path.expanduser(launcher_config_path)
        self.user_configs_path = os.path.join(self.launcher_config_path, "user_configs")
        self.templates_path = os.path.join(self.launcher_config_path, "templates")
        self.claude_config_file = os.path.join(self.claude_config_path, "claude_desktop_config.json")
        self.tokens_file = os.path.join(self.launcher_config_path, "tokens.json")

        try:
            # Create directories if they don't exist
            for path in [self.user_configs_path, self.templates_path]:
                if not os.path.exists(path):
                    os.makedirs(path)

            # Load or create initial configs
            self._initialize_configs()
        except OSError as e:
            raise ConfigError(f"Failed to initialize configuration directories: {e}")

    def _validate_config(self, config_data: Dict) -> bool:
        """Validate configuration data against schema"""
        try:
            # Check required fields
            for field in self.CONFIG_SCHEMA["required"]:
                if field not in config_data:
                    raise ConfigError(f"Missing required field: {field}")

            # Validate types
            if not isinstance(config_data.get("servers"), list):
                raise ConfigError("'servers' must be an array")
            if not isinstance(config_data.get("version"), str):
                raise ConfigError("'version' must be a string")

            return True
        except Exception as e:
            raise ConfigError(f"Configuration validation failed: {e}")

    def _safe_read_json(self, file_path: str) -> Dict:
        """Safely read and parse JSON file"""
        try:
            if not os.path.exists(file_path):
                raise ConfigError(f"File not found: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in {file_path}: {e}")
        except OSError as e:
            raise ConfigError(f"Failed to read {file_path}: {e}")

    def _safe_write_json(self, file_path: str, data: Dict) -> None:
        """Safely write JSON file with backup"""
        if os.path.exists(file_path):
            # Create backup
            backup_path = f"{file_path}.bak"
            try:
                shutil.copy2(file_path, backup_path)
            except OSError as e:
                raise ConfigError(f"Failed to create backup of {file_path}: {e}")

        try:
            # Write new file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            # Restore from backup if write fails
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
            raise ConfigError(f"Failed to write {file_path}: {e}")

    def _initialize_configs(self) -> None:
        """Initialize configuration storage with error handling"""
        try:
            # If Claude has a config, back it up if we haven't already
            if os.path.exists(self.claude_config_file):
                backup_path = os.path.join(self.launcher_config_path, "original_config.json")
                if not os.path.exists(backup_path):
                    shutil.copy2(self.claude_config_file, backup_path)
        except OSError as e:
            raise ConfigError(f"Failed to backup original configuration: {e}")

    def get_available_configs(self):
        """Get list of available configurations"""
        configs = []

        # Check for original Claude config
        original_path = os.path.join(self.launcher_config_path, "original_config.json")
        if os.path.exists(original_path):
            configs.append({"name": "Original Claude Config", "path": original_path, "builtin": True})

        # Get user configs
        for filename in sorted(os.listdir(self.user_configs_path)):
            if filename.endswith(".json"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.user_configs_path, filename)
                configs.append({"name": name, "path": path, "builtin": False})

        return configs

    def get_available_templates(self):
        """Get list of available templates"""
        templates = []

        for filename in sorted(os.listdir(self.templates_path)):
            if filename.endswith(".json"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.templates_path, filename)

                # Try to load the template to get its description
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)

                    description = data.get("description", "No description available")
                except:
                    description = "Invalid template"

                templates.append({
                    "name": name,
                    "path": path,
                    "description": description
                })

        return templates

    def save_template(self, name, template_data):
        """Save a template to the templates directory"""
        # Sanitize the filename
        safe_name = "".join(c for c in name if c.isalnum() or c in " ._-").strip()
        if not safe_name:
            safe_name = "template"

        file_path = os.path.join(self.templates_path, f"{safe_name}.json")

        try:
            with open(file_path, 'w') as f:
                json.dump(template_data, f, indent=2)
            return file_path
        except Exception as e:
            print(f"Error saving template: {e}")
            return None

    def get_config_content(self, config_path):
        """Get the content of a configuration file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config {config_path}: {e}")
            return None

    def save_config(self, name, config_data):
        """Save a configuration to the user configs directory"""
        # Sanitize the filename
        safe_name = "".join(c for c in name if c.isalnum() or c in " ._-").strip()
        if not safe_name:
            safe_name = "config"

        file_path = os.path.join(self.user_configs_path, f"{safe_name}.json")

        try:
            with open(file_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            return file_path
        except Exception as e:
            print(f"Error saving config: {e}")
            return None

    def apply_config(self, config_path, safe_mode=False):
        """Apply a configuration as the active Claude config"""
        try:
            # Read the source config
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # If safe mode, keep only filesystem server
            if safe_mode and "mcpServers" in config_data:
                filesystem_only = {}
                if "filesystem" in config_data["mcpServers"]:
                    filesystem_only["filesystem"] = config_data["mcpServers"]["filesystem"]
                config_data["mcpServers"] = filesystem_only

            # Make sure target directory exists
            os.makedirs(os.path.dirname(self.claude_config_file), exist_ok=True)

            # Write the config
            with open(self.claude_config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

            return True
        except Exception as e:
            print(f"Error applying config: {e}")
            return False

    def process_template_variables(self, config_data):
        """Process template variables in the config data"""
        # Convert to string to do replacements
        config_str = json.dumps(config_data)

        # Replace variables
        replacements = {
            "${HOME}": os.path.expanduser("~"),
            "${DESKTOP}": os.path.expanduser("~/Desktop"),
            "${DOCUMENTS}": os.path.expanduser("~/Documents"),
            "${DOWNLOADS}": os.path.expanduser("~/Downloads"),
            "${PICTURES}": os.path.expanduser("~/Pictures"),
            "${MOVIES}": os.path.expanduser("~/Movies"),
            "${MUSIC}": os.path.expanduser("~/Music"),
            "${TIMESTAMP}": datetime.now().strftime("%Y%m%d_%H%M%S")
        }

        for var, value in replacements.items():
            config_str = config_str.replace(var, value)

        # Convert back to object
        try:
            return json.loads(config_str)
        except:
            # If there's an error, return the original
            return config_data

    def get_server_info(self, config_data):
        """Extract server information from a config for display"""
        servers = []

        if not config_data or "mcpServers" not in config_data:
            return servers

        for name, server in config_data["mcpServers"].items():
            servers.append({
                "name": name,
                "command": server.get("command", ""),
                "args": server.get("args", [])
            })

        return servers

    def create_config_from_servers(self, selected_servers, source_config):
        """Create a new config using only selected servers from a source config"""
        if not source_config or "mcpServers" not in source_config:
            return {"mcpServers": {}}

        new_config = {"mcpServers": {}}

        for name in selected_servers:
            if name in source_config["mcpServers"]:
                new_config["mcpServers"][name] = source_config["mcpServers"][name]

        return new_config

    def get_config_status(self, config_data):
        """Get a human-readable status of what the configuration provides"""
        if not config_data or "mcpServers" not in config_data:
            return "Empty configuration"

        servers = config_data.get("mcpServers", {})

        capabilities = []

        if "filesystem" in servers:
            capabilities.append("File Access")

        if "fetch" in servers or "webresearch" in servers:
            capabilities.append("Web Access")

        if "python_executor" in servers:
            capabilities.append("Python Execution")

        if "ollama" in servers:
            capabilities.append("Local Models (Ollama)")

        if not capabilities:
            return "No capabilities"

        return ", ".join(capabilities)

    def delete_config(self, config_path):
        """Delete a configuration file"""
        try:
            if os.path.exists(config_path) and os.path.isfile(config_path):
                os.remove(config_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting config: {e}")
            return False

    def get_tokens(self):
        """Get all stored tokens"""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            'github': {'launcher': None, 'mcp': None},
            'cloudflare': None
        }

    def save_tokens(self, tokens):
        """Save all tokens"""
        try:
            with open(self.tokens_file, 'w') as f:
                json.dump(tokens, f)
            return True
        except Exception:
            return False

    def get_cloudflare_token(self):
        """Get the Cloudflare token"""
        tokens = self.get_tokens()
        return tokens.get('cloudflare')

    def save_cloudflare_token(self, token):
        """Save the Cloudflare token"""
        tokens = self.get_tokens()
        tokens['cloudflare'] = token
        return self.save_tokens(tokens)