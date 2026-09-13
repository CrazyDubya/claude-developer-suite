"""
MainWindow - The main UI for the Claude MCP Launcher
"""

import os
import sys
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel,
    QMessageBox, QInputDialog, QDialog, QCheckBox,
    QGroupBox, QFrame, QSplitter, QApplication
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFont

from launch_manager import LaunchManager
from github_manager import GitHubManager
from ui.server_list_widget import ServerListWidget
from ui.config_editor import ConfigEditorDialog
from ui.mcp_setup_guide import show_mcp_setup_guide
from ui.mcp_tester import test_mcp_configuration
from config_manager import ConfigManager
from ui.github_settings import GitHubSettingsDialog
from ui.cloudflare_settings import CloudflareSettingsDialog
from ui.directory_wizard import DirectoryWizardDialog
from ui.directory_manager import DirectoryManagerDialog

# Initialize configuration paths
def get_config_paths():
    """Get the configuration paths for Claude and the launcher"""
    home = os.path.expanduser("~")
    
    # Claude's config directory
    claude_config = os.path.join(home, "Library", "Application Support", "Claude")
    
    # Launcher's config directory
    launcher_config = os.path.join(home, "Library", "Application Support", "Claude MCP Launcher")
    
    # Create directories if they don't exist
    for path in [claude_config, launcher_config]:
        if not os.path.exists(path):
            os.makedirs(path)
            
    return claude_config, launcher_config

# Global config manager instance
CLAUDE_CONFIG_PATH, LAUNCHER_CONFIG_PATH = get_config_paths()
config_manager = ConfigManager(CLAUDE_CONFIG_PATH, LAUNCHER_CONFIG_PATH)

class MainWindow(QMainWindow):
    """Main window for the Claude MCP Launcher"""

    def __init__(self, config_manager):
        super().__init__()

        self.config_manager = config_manager
        self.launch_manager = LaunchManager(config_manager)
        self.github_manager = GitHubManager(config_manager)

        self.current_config_path = None
        self.current_config_data = None

        self.init_ui()
        self.load_configs()

    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Config list
        config_group = QGroupBox("Configurations")
        config_layout = QVBoxLayout()
        
        self.config_list = QListWidget()
        self.config_list.setSelectionMode(QListWidget.SingleSelection)
        self.config_list.currentItemChanged.connect(self.on_config_selected)
        config_layout.addWidget(self.config_list)
        
        # Config buttons
        config_buttons_layout = QHBoxLayout()
        
        self.new_config_btn = QPushButton("New Config")
        self.new_config_btn.clicked.connect(self.on_new_config)
        config_buttons_layout.addWidget(self.new_config_btn)
        
        self.edit_config_btn = QPushButton("Edit Config")
        self.edit_config_btn.clicked.connect(self.on_edit_config)
        config_buttons_layout.addWidget(self.edit_config_btn)
        
        self.delete_config_btn = QPushButton("Delete Config")
        self.delete_config_btn.clicked.connect(self.on_delete_config)
        config_buttons_layout.addWidget(self.delete_config_btn)
        
        self.manage_dirs_btn = QPushButton("Manage Directories")
        self.manage_dirs_btn.clicked.connect(self.on_manage_directories)
        self.manage_dirs_btn.setVisible(False)  # Initially hidden
        config_buttons_layout.addWidget(self.manage_dirs_btn)
        
        # Add a second row of buttons
        config_buttons_layout2 = QHBoxLayout()
        
        self.restore_original_btn = QPushButton("Restore Original Config")
        self.restore_original_btn.clicked.connect(self.on_restore_original)
        self.restore_original_btn.setToolTip("Restore the original Claude configuration")
        config_buttons_layout2.addWidget(self.restore_original_btn)
        
        config_layout.addLayout(config_buttons_layout)
        config_layout.addLayout(config_buttons_layout2)
        
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        # GitHub integration
        github_group = QGroupBox("GitHub Integration")
        github_layout = QVBoxLayout()
        
        self.github_settings_btn = QPushButton("GitHub Settings")
        self.github_settings_btn.clicked.connect(self.on_github_settings)
        github_layout.addWidget(self.github_settings_btn)
        
        self.cloudflare_settings_btn = QPushButton("Cloudflare Settings")
        self.cloudflare_settings_btn.clicked.connect(self.on_cloudflare_settings)
        github_layout.addWidget(self.cloudflare_settings_btn)
        
        github_group.setLayout(github_layout)
        left_layout.addWidget(github_group)
        
        # Add left panel to main layout
        main_layout.addWidget(left_panel)
        
        # Create right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Server list
        self.server_list = ServerListWidget()
        right_layout.addWidget(self.server_list)
        
        # Safe mode checkbox
        self.safe_mode_cb = QCheckBox("Safe Mode (Only allow filesystem access)")
        self.safe_mode_cb.setToolTip("When enabled, only filesystem access will be allowed, all other MCP servers will be disabled")
        right_layout.addWidget(self.safe_mode_cb)
        
        # Launch button
        self.launch_btn = QPushButton("Launch Claude")
        self.launch_btn.clicked.connect(self.on_launch)
        right_layout.addWidget(self.launch_btn)
        
        # Status label
        self.status_label = QLabel("Select a configuration to launch Claude")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)
        
        # Add right panel to main layout
        main_layout.addWidget(right_panel)
        
        # Set window properties
        self.setWindowTitle("Claude MCP Launcher")
        self.setMinimumSize(800, 600)
        
        # Load configurations
        self.load_configs()

    def center_on_screen(self):
        """Center the window on the screen"""
        screen_geometry = QApplication.desktop().availableGeometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen_geometry.center())
        self.move(window_geometry.topLeft())

    def load_configs(self):
        """Load available configurations"""
        self.config_list.clear()

        configs = self.config_manager.get_available_configs()
        for config in configs:
            item = QListWidgetItem(config["name"])
            item.setData(Qt.UserRole, config)
            self.config_list.addItem(item)

    def on_config_selected(self, current, previous):
        """Handle configuration selection"""
        if not current:
            self.current_config_path = None
            self.current_config_data = None
            self.server_list.clear()
            self.edit_config_btn.setEnabled(False)
            self.delete_config_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            return

        config = current.data(Qt.UserRole)
        self.current_config_path = config["path"]

        # Load the configuration data
        self.current_config_data = self.config_manager.get_config_content(self.current_config_path)

        # Update the server list
        servers = self.config_manager.get_server_info(self.current_config_data)
        self.server_list.set_servers(servers)

        # Update button states
        self.edit_config_btn.setEnabled(not config.get("builtin", False))
        self.delete_config_btn.setEnabled(True)
        self.launch_btn.setEnabled(True)
        
        # Show manage directories button only if this is a filesystem configuration
        has_filesystem = False
        if "mcpServers" in self.current_config_data and "filesystem" in self.current_config_data["mcpServers"]:
            has_filesystem = True
        self.manage_dirs_btn.setVisible(has_filesystem)

        # Get capabilities
        capabilities = self.config_manager.get_config_status(self.current_config_data)
        
        # Update status
        self.status_label.setText(f"Ready to launch with {config['name']} - {capabilities}")

    def on_new_config(self):
        """Create a new configuration"""
        name, ok = QInputDialog.getText(
            self, "New Configuration", "Enter a name for the new configuration:"
        )

        if ok and name:
            empty_config = {"mcpServers": {}}
            path = self.config_manager.save_config(name, empty_config)

            if path:
                self.load_configs()

                # Select the new config
                for i in range(self.config_list.count()):
                    item = self.config_list.item(i)
                    if item.data(Qt.UserRole)["path"] == path:
                        self.config_list.setCurrentItem(item)
                        break

                # Open the editor
                self.on_edit_config()
            else:
                QMessageBox.warning(
                    self, "Error", "Failed to create new configuration"
                )

    def on_edit_config(self):
        """Edit the selected configuration"""
        if not self.current_config_path or not self.current_config_data:
            return

        editor = ConfigEditorDialog(
            self, self.current_config_data, self.config_list.currentItem().text()
        )

        if editor.exec_() == QDialog.Accepted:
            # Save the edited configuration
            name = self.config_list.currentItem().text()
            path = self.config_manager.save_config(name, editor.get_config_data())

            if path:
                # Reload the configuration
                self.current_config_data = self.config_manager.get_config_content(path)

                # Update the server list
                servers = self.config_manager.get_server_info(self.current_config_data)
                self.server_list.set_servers(servers)

                # Update status
                self.status_label.setText(f"Configuration '{name}' updated")
            else:
                QMessageBox.warning(
                    self, "Error", "Failed to save configuration changes"
                )

    def on_delete_config(self):
        """Delete the selected configuration"""
        if not self.current_config_path or not self.current_config_data:
            return

        # Show a confirmation dialog
        result = QMessageBox.question(
            self, "Delete Configuration",
            f"Are you sure you want to delete the configuration '{self.config_list.currentItem().text()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if result == QMessageBox.Yes:
            # Delete the configuration
            self.config_manager.delete_config(self.current_config_path)
            self.load_configs()

    def on_launch(self):
        """Launch Claude with the selected configuration"""
        if not self.current_config_path:
            return

        # Check if Claude is running first
        if not self.check_claude_running():
            return

        safe_mode = self.safe_mode_cb.isChecked()
        self.status_label.setText("Launching Claude...")
        QApplication.processEvents()

        success, message = self.launch_manager.launch_claude(
            self.current_config_path, safe_mode
        )

        if success:
            self.status_label.setText("Claude launched successfully")
            # Close this app after a short delay
            QApplication.processEvents()
            self.close()
        else:
            QMessageBox.warning(self, "Launch Error", message)
            self.status_label.setText("Launch failed")

    def on_github_settings(self):
        """Open GitHub settings dialog"""
        dialog = GitHubSettingsDialog(self)
        tokens = self.github_manager.get_tokens()
        dialog.set_launcher_token(tokens['launcher'])
        dialog.set_mcp_token(tokens['mcp'])
            
        if dialog.exec_() == GitHubSettingsDialog.Accepted:
            launcher_token = dialog.get_launcher_token()
            mcp_token = dialog.get_mcp_token()
            if launcher_token or mcp_token:
                if self.github_manager.save_tokens(launcher_token, mcp_token):
                    QMessageBox.information(self, "Success", "GitHub settings saved")
                else:
                    QMessageBox.warning(self, "Error", "Failed to save GitHub settings")

    def on_cloudflare_settings(self):
        """Open Cloudflare settings dialog"""
        dialog = CloudflareSettingsDialog(self)
        token = self.config_manager.get_cloudflare_token()
        if token:
            dialog.set_token(token)
            
        if dialog.exec_() == CloudflareSettingsDialog.Accepted:
            token = dialog.get_token()
            if token:
                if self.config_manager.save_cloudflare_token(token):
                    QMessageBox.information(self, "Success", "Cloudflare settings saved")
                else:
                    QMessageBox.warning(self, "Error", "Failed to save Cloudflare settings")

    def create_filesystem_config(self, paths):
        """Create a new filesystem configuration with specified paths"""
        name = "Filesystem Access"
        config_data = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem"
                    ] + paths
                }
            },
            "version": "1.0"
        }
        
        path = self.config_manager.save_config(name, config_data)
        if path:
            self.load_configs()
            # Select the new config
            for i in range(self.config_list.count()):
                item = self.config_list.item(i)
                if item.data(Qt.UserRole)["path"] == path:
                    self.config_list.setCurrentItem(item)
                    break
            return True
        return False

    def create_smithery_config(self):
        """Create a new Smithery configuration"""
        name = "Smithery CLI"
        config_data = {
            "mcpServers": {
                "smithery": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@smithery/cli@latest",
                        "run",
                        "@smithery-ai/github",
                        "--config",
                        "{\"githubPersonalAccessToken\":\"\"}"  # Empty token by default
                    ]
                }
            },
            "version": "1.0"
        }
        
        path = self.config_manager.save_config(name, config_data)
        if path:
            self.load_configs()
            # Select the new config
            for i in range(self.config_list.count()):
                item = self.config_list.item(i)
                if item.data(Qt.UserRole)["path"] == path:
                    self.config_list.setCurrentItem(item)
                    break
            return True
        return False

    def on_manage_directories(self):
        """Open directory manager dialog"""
        current_item = self.config_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a configuration first")
            return
            
        # Get the config path from the item data
        config_path = current_item.data(Qt.UserRole)["path"]
        
        # Load the actual config content
        config_data = self.config_manager.get_config_content(config_path)
        if not config_data:
            QMessageBox.warning(self, "Warning", "Failed to load configuration data")
            return
        
        # Check if this is a filesystem configuration
        if "mcpServers" not in config_data or "filesystem" not in config_data["mcpServers"]:
            QMessageBox.warning(self, "Warning", "This configuration does not have filesystem access")
            return
            
        dialog = DirectoryManagerDialog(config_data, self)
        if dialog.exec_() == QDialog.Accepted:
            updated_config = dialog.get_updated_config()
            
            # Save the updated config
            self.config_manager.save_config(
                current_item.data(Qt.UserRole)["name"],
                updated_config
            )
            self.load_configs()

    def on_restore_original(self):
        """Restore the original Claude configuration"""
        # Check if the original config exists
        original_path = os.path.join(self.config_manager.launcher_config_path, "original_config.json")
        if not os.path.exists(original_path):
            QMessageBox.warning(
                self, 
                "Error", 
                "Original configuration backup not found. Cannot restore."
            )
            return
            
        # Confirm with the user
        result = QMessageBox.question(
            self, 
            "Restore Original Configuration",
            "Are you sure you want to restore the original Claude configuration?\n\n"
            "This will replace the current Claude configuration with the original one.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # Check if Claude is running
        if not self.check_claude_running():
            return
            
        # Copy the original config to the Claude config path
        try:
            claude_config_file = os.path.join(self.config_manager.claude_config_path, "claude_desktop_config.json")
            with open(original_path, 'r') as f:
                original_config = json.load(f)
                
            with open(claude_config_file, 'w') as f:
                json.dump(original_config, f, indent=2)
                
            QMessageBox.information(
                self,
                "Success",
                "Original configuration has been restored. Claude will use this configuration the next time it starts."
            )
            
            # Update status
            self.status_label.setText("Original configuration restored")
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to restore original configuration: {str(e)}"
            )

    def check_claude_running(self):
        """Check if Claude is running and handle it appropriately"""
        if not self.launch_manager.is_claude_running():
            return True
            
        # Show a dialog with options
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Claude is Running")
        msg.setText("Claude is currently running.")
        msg.setInformativeText(
            "What would you like to do?\n\n"
            "• Close Claude and continue\n"
            "• Force close if normal close fails\n"
            "• Launch another instance anyway\n"
            "• Cancel"
        )
        
        # Add custom buttons
        close_btn = msg.addButton("Close Claude", QMessageBox.ActionRole)
        force_btn = msg.addButton("Force Close", QMessageBox.ActionRole)
        continue_btn = msg.addButton("Launch Anyway", QMessageBox.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.Cancel)
        
        msg.exec_()
        clicked = msg.clickedButton()
        
        if clicked == cancel_btn:
            self.status_label.setText("Launch cancelled")
            return False
            
        elif clicked == continue_btn:
            return True
            
        elif clicked in (close_btn, force_btn):
            force = (clicked == force_btn)
            self.status_label.setText("Closing Claude...")
            QApplication.processEvents()
            
            success, message = self.launch_manager.terminate_claude()
            if success:
                self.status_label.setText("Claude closed successfully")
                return True
            else:
                QMessageBox.warning(self, "Error", f"Failed to close Claude: {message}")
                return False
                
        return False

def main():
    try:
        print("Starting Claude MCP Launcher...")
        app = QApplication(sys.argv)
        
        # Initialize config paths
        print("Initializing config paths...")
        home = os.path.expanduser("~")
        claude_config = os.path.join(home, "Library", "Application Support", "Claude")
        launcher_config = os.path.join(home, "Library", "Application Support", "Claude MCP Launcher")
        
        print(f"Claude config path: {claude_config}")
        print(f"Launcher config path: {launcher_config}")
        
        # Create config manager
        print("Creating config manager...")
        config_manager = ConfigManager(claude_config, launcher_config)
        
        # Create main window
        print("Creating main window...")
        window = MainWindow(config_manager)
        
        # Create default configurations
        window.create_smithery_config()
        
        # Create a default ClaudeCLutter configuration if it doesn't exist
        clutter_dir = os.path.join(os.path.expanduser("~/Desktop"), "ClaudeCLutter")
        if not os.path.exists(clutter_dir):
            try:
                os.makedirs(clutter_dir)
            except Exception as e:
                print(f"Error creating ClaudeCLutter directory: {e}")
        
        # Check if we already have a filesystem config
        has_filesystem_config = False
        for i in range(window.config_list.count()):
            item = window.config_list.item(i)
            config = item.data(Qt.UserRole)
            config_data = config_manager.get_config_content(config["path"])
            if "mcpServers" in config_data and "filesystem" in config_data["mcpServers"]:
                has_filesystem_config = True
                break
        
        # Show directory wizard if needed
        if not has_filesystem_config:
            wizard = DirectoryWizardDialog(window)
            if wizard.exec_() == QDialog.Accepted:
                paths = wizard.get_selected_paths()
                if paths:
                    window.create_filesystem_config(paths)
        
        window.show()
        
        print("Starting application event loop...")
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"ERROR: Application crashed: {str(e)}")
        input("Press Enter to exit...")  # Keep terminal window open
        sys.exit(1)

if __name__ == "__main__":
    main()
