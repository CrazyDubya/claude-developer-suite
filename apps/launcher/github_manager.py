"""
GitHubManager - Handles downloading configurations from GitHub
"""

import os
import json
import requests
from urllib.parse import urlparse
from PyQt5.QtWidgets import QMessageBox
from ui.github_settings import GitHubSettingsDialog


class GitHubManager:
    """Manages GitHub-related operations"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.tokens_file = os.path.join(config_manager.launcher_config_path, "github_tokens.json")

    def get_tokens(self):
        """Get the stored GitHub tokens"""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    return {
                        'launcher': data.get('launcher_token'),
                        'mcp': data.get('mcp_token')
                    }
        except Exception:
            pass
        return {'launcher': None, 'mcp': None}

    def save_tokens(self, launcher_token, mcp_token):
        """Save the GitHub tokens"""
        try:
            with open(self.tokens_file, 'w') as f:
                json.dump({
                    'launcher_token': launcher_token,
                    'mcp_token': mcp_token
                }, f)
            return True
        except Exception:
            return False

    def is_valid_github_url(self, url):
        """Check if a URL is a valid GitHub raw content URL"""
        parsed = urlparse(url)
        return (parsed.netloc == "raw.githubusercontent.com" or
                parsed.netloc == "github.com" or
                parsed.netloc == "api.github.com")

    def convert_to_raw_url(self, url):
        """Convert a GitHub URL to a raw content URL if needed"""
        if "raw.githubusercontent.com" in url:
            return url

        # Convert github.com/user/repo/blob/path to raw URL
        if "github.com" in url and "/blob/" in url:
            return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

        return url

    def download_config(self, url):
        """Download a configuration from GitHub"""
        tokens = self.get_tokens()
        launcher_token = tokens['launcher']
        
        # If no launcher token, show settings dialog
        if not launcher_token:
            dialog = GitHubSettingsDialog()
            if dialog.exec_() == GitHubSettingsDialog.Accepted:
                launcher_token = dialog.get_launcher_token()
                mcp_token = dialog.get_mcp_token()
                if launcher_token or mcp_token:
                    self.save_tokens(launcher_token, mcp_token)
                else:
                    return False, "GitHub token is required"
            else:
                return False, "Operation cancelled"

        try:
            headers = {'Authorization': f'token {launcher_token}'} if launcher_token else {}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            config_data = response.json()
            
            # Save the configuration
            filename = os.path.basename(url)
            if not filename.endswith('.json'):
                filename += '.json'
                
            path = os.path.join(self.config_manager.user_configs_path, filename)
            with open(path, 'w') as f:
                json.dump(config_data, f, indent=2)
                
            return True, path
            
        except requests.exceptions.RequestException as e:
            return False, f"Failed to download: {str(e)}"
        except json.JSONDecodeError:
            return False, "Invalid JSON in configuration"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_repo_configs(self, repo_url):
        """List MCP configurations from a GitHub repository"""
        # This would need to use the GitHub API to list files in a repo
        # For now, we'll just return a placeholder message
        return False, "Repository scanning is not implemented yet"