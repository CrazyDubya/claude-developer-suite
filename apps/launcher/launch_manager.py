"""
LaunchManager - Handles launching Claude Desktop with the configured MCP servers
"""

import os
import sys
import json
import subprocess
import time
from typing import List, Dict, Tuple

class LaunchManager:
    """Manages launching Claude Desktop with configurations"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

        # Paths to potential Claude app locations
        self.claude_app_paths = [
            "/Applications/Claude.app",
            os.path.expanduser("~/Applications/Claude.app")
        ]

    def find_claude_app(self):
        """Find the Claude app on the system"""
        for path in self.claude_app_paths:
            if os.path.exists(path):
                return path
        return None

    def get_claude_processes(self) -> List[Dict[str, str]]:
        """Get all running Claude processes with detailed information"""
        try:
            # Use ps to get all processes containing 'Claude'
            cmd = ["ps", "-ax", "-o", "pid,ppid,command"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
                
            processes = []
            for line in result.stdout.splitlines()[1:]:  # Skip header
                if '/Claude.app/' in line:
                    parts = line.strip().split(None, 2)
                    if len(parts) >= 3:
                        pid, ppid, cmd = parts
                        processes.append({
                            'pid': pid,
                            'ppid': ppid,
                            'command': cmd,
                            'type': self._get_process_type(cmd)
                        })
            
            return processes
        except Exception as e:
            print(f"Error getting Claude processes: {e}")
            return []
    
    def _get_process_type(self, cmd: str) -> str:
        """Determine the type of Claude process from its command"""
        if 'Claude.app/Contents/MacOS/Claude' in cmd:
            return 'main'
        elif 'Helper (Renderer)' in cmd:
            return 'renderer'
        elif 'Helper (GPU)' in cmd:
            return 'gpu'
        elif 'chrome_crashpad_handler' in cmd:
            return 'crashpad'
        elif 'Helper.app' in cmd and 'utility' in cmd:
            return 'utility'
        return 'unknown'
    
    def is_claude_running(self) -> bool:
        """Check if Claude is running by looking for the main process"""
        processes = self.get_claude_processes()
        return any(p['type'] == 'main' for p in processes)
    
    def terminate_claude(self) -> Tuple[bool, str]:
        """Attempt to gracefully terminate Claude processes"""
        try:
            processes = self.get_claude_processes()
            
            if not processes:
                return True, "Claude is not running"
            
            # First try to terminate the main process
            main_process = next((p for p in processes if p['type'] == 'main'), None)
            if main_process:
                subprocess.run(['kill', main_process['pid']])
                
                # Wait up to 5 seconds for processes to terminate
                for _ in range(10):
                    time.sleep(0.5)
                    if not self.is_claude_running():
                        return True, "Claude terminated successfully"
                        
            # If still running, force kill all Claude processes
            for process in self.get_claude_processes():
                try:
                    subprocess.run(['kill', '-9', process['pid']])
                except:
                    pass
                    
            return True, "Claude forcefully terminated"
            
        except Exception as e:
            return False, f"Failed to terminate Claude: {str(e)}"
    
    def launch_claude(self, config_path: str, safe_mode: bool = False) -> Tuple[bool, str]:
        """Launch Claude with the specified configuration"""
        try:
            # Ensure Claude isn't running
            if self.is_claude_running():
                success, message = self.terminate_claude()
                if not success:
                    return False, message
            
            # Get the Claude app path
            claude_path = "/Applications/Claude.app"
            if not os.path.exists(claude_path):
                return False, "Claude.app not found in Applications folder"
            
            # Launch Claude
            cmd = ["open", claude_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, f"Failed to launch Claude: {result.stderr}"
            
            # Wait for Claude to start (up to 10 seconds)
            for _ in range(20):
                time.sleep(0.5)
                if self.is_claude_running():
                    return True, "Claude launched successfully"
            
            return False, "Claude failed to start within timeout period"
            
        except Exception as e:
            return False, f"Error launching Claude: {str(e)}"
