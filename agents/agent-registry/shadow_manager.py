#!/usr/bin/env python3
"""
Shadow Manager - Physical Agent File Management System

This module provides complete control over which agents Claude Code sees by 
physically moving files between archive and active directories. It ensures
Claude Code's context window is never overwhelmed while maintaining access
to unlimited agent libraries through intelligent file management.

Architecture:
- Archive: ~/.claude-agent-manager/archive/ (ALL agents stored here)
- Active: ~/.claude/agents/ and .claude/agents/ (what Claude Code sees)
- State: Tracks which agents are currently active
- Safety: Multiple backups and atomic operations
"""

import os
import shutil
import json
import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import logging

class ShadowManager:
    """Manages the shadow directory system for agent files"""
    
    def __init__(self):
        self.manager_dir = Path.home() / ".claude-agent-manager"
        self.archive_dir = self.manager_dir / "archive"
        self.state_file = self.manager_dir / "state.yml"
        self.backup_dir = self.manager_dir / "backups"
        
        # Standard Claude Code directories
        self.global_agents = Path.home() / ".claude" / "agents"
        self.project_agents = Path.cwd() / ".claude" / "agents"
        
        # Ensure all directories exist
        self._ensure_directories()
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _ensure_directories(self):
        """Create all necessary directories"""
        directories = [
            self.manager_dir,
            self.archive_dir / "global",
            self.archive_dir / "project", 
            self.backup_dir,
            self.global_agents,
            self.project_agents
        ]
        for dir_path in directories:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _load_state(self) -> Dict:
        """Load current state from state.yml"""
        if not self.state_file.exists():
            return {
                "active_agents": {"global": [], "project": []},
                "last_profile": None,
                "last_update": None,
                "checksums": {}
            }
        
        with open(self.state_file, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def _save_state(self, state: Dict):
        """Save state to state.yml with timestamp"""
        state["last_update"] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    
    def _create_backup(self, operation: str) -> str:
        """Create timestamped backup before operations"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{operation}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)
        
        # Backup current active agents
        if self.global_agents.exists():
            shutil.copytree(self.global_agents, backup_path / "global_agents", dirs_exist_ok=True)
        
        if self.project_agents.exists():
            shutil.copytree(self.project_agents, backup_path / "project_agents", dirs_exist_ok=True)
            
        # Backup state
        if self.state_file.exists():
            shutil.copy2(self.state_file, backup_path / "state.yml")
        
        self.logger.info(f"Backup created: {backup_name}")
        return backup_name
    
    def initialize_shadow_system(self, force: bool = False) -> Dict:
        """
        Initialize shadow system by archiving all existing agents
        
        Args:
            force: If True, re-initialize even if already initialized
            
        Returns:
            Dict with operation results
        """
        state = self._load_state()
        
        # Check if already initialized
        if state.get("initialized") and not force:
            return {
                "success": False,
                "message": "Shadow system already initialized. Use --force to re-initialize.",
                "archived_agents": 0
            }
        
        # Create backup before major operation
        backup_name = self._create_backup("initialize")
        
        archived_count = 0
        results = {"global": [], "project": []}
        
        try:
            # Archive global agents
            if self.global_agents.exists():
                for agent_file in self.global_agents.glob("*.md"):
                    archive_path = self.archive_dir / "global" / agent_file.name
                    if not archive_path.exists() or force:
                        shutil.move(str(agent_file), str(archive_path))
                        archived_count += 1
                        results["global"].append(agent_file.name)
                        self.logger.info(f"Archived global: {agent_file.name}")
            
            # Archive project agents
            if self.project_agents.exists():
                for agent_file in self.project_agents.glob("*.md"):
                    archive_path = self.archive_dir / "project" / agent_file.name
                    if not archive_path.exists() or force:
                        shutil.move(str(agent_file), str(archive_path))
                        archived_count += 1
                        results["project"].append(agent_file.name)
                        self.logger.info(f"Archived project: {agent_file.name}")
            
            # Update state
            state = {
                "initialized": True,
                "active_agents": {"global": [], "project": []},
                "archived_agents": {
                    "global": results["global"],
                    "project": results["project"]
                },
                "last_profile": None,
                "initialization_backup": backup_name
            }
            
            self._save_state(state)
            
            return {
                "success": True,
                "message": f"Shadow system initialized. Archived {archived_count} agents.",
                "archived_agents": archived_count,
                "backup": backup_name,
                "details": results
            }
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return {
                "success": False,
                "message": f"Initialization failed: {e}",
                "backup": backup_name
            }
    
    def activate_agents(self, agent_names: List[str], source: str = "global") -> Dict:
        """
        Activate specific agents by moving them from archive to active directory
        
        Args:
            agent_names: List of agent names to activate
            source: "global" or "project" 
        """
        if source not in ["global", "project"]:
            return {"success": False, "message": "Source must be 'global' or 'project'"}
        
        backup_name = self._create_backup("activate")
        state = self._load_state()
        
        activated = []
        failed = []
        active_dir = self.global_agents if source == "global" else self.project_agents
        archive_source = self.archive_dir / source
        
        try:
            for agent_name in agent_names:
                if not agent_name.endswith('.md'):
                    agent_name += '.md'
                
                archive_path = archive_source / agent_name
                active_path = active_dir / agent_name
                
                if not archive_path.exists():
                    failed.append(f"{agent_name} - not found in archive")
                    continue
                
                if active_path.exists():
                    failed.append(f"{agent_name} - already active")
                    continue
                
                # Move from archive to active
                shutil.copy2(archive_path, active_path)
                activated.append(agent_name)
                
                # Update state
                if agent_name not in state["active_agents"][source]:
                    state["active_agents"][source].append(agent_name)
                
                self.logger.info(f"Activated {source}: {agent_name}")
            
            self._save_state(state)
            
            return {
                "success": len(activated) > 0,
                "message": f"Activated {len(activated)} agents, {len(failed)} failed",
                "activated": activated,
                "failed": failed,
                "backup": backup_name
            }
            
        except Exception as e:
            self.logger.error(f"Activation failed: {e}")
            return {
                "success": False,
                "message": f"Activation failed: {e}",
                "backup": backup_name
            }
    
    def deactivate_agents(self, agent_names: List[str], source: str = "global") -> Dict:
        """
        Deactivate specific agents by moving them from active to archive
        
        Args:
            agent_names: List of agent names to deactivate
            source: "global" or "project"
        """
        if source not in ["global", "project"]:
            return {"success": False, "message": "Source must be 'global' or 'project'"}
        
        backup_name = self._create_backup("deactivate")
        state = self._load_state()
        
        deactivated = []
        failed = []
        active_dir = self.global_agents if source == "global" else self.project_agents
        archive_dest = self.archive_dir / source
        
        try:
            for agent_name in agent_names:
                if not agent_name.endswith('.md'):
                    agent_name += '.md'
                
                active_path = active_dir / agent_name
                archive_path = archive_dest / agent_name
                
                if not active_path.exists():
                    failed.append(f"{agent_name} - not currently active")
                    continue
                
                # Move from active to archive (replace if exists)
                if archive_path.exists():
                    archive_path.unlink()  # Remove old version
                
                shutil.move(str(active_path), str(archive_path))
                deactivated.append(agent_name)
                
                # Update state
                if agent_name in state["active_agents"][source]:
                    state["active_agents"][source].remove(agent_name)
                
                self.logger.info(f"Deactivated {source}: {agent_name}")
            
            self._save_state(state)
            
            return {
                "success": len(deactivated) > 0,
                "message": f"Deactivated {len(deactivated)} agents, {len(failed)} failed",
                "deactivated": deactivated,
                "failed": failed,
                "backup": backup_name
            }
            
        except Exception as e:
            self.logger.error(f"Deactivation failed: {e}")
            return {
                "success": False,
                "message": f"Deactivation failed: {e}",
                "backup": backup_name
            }
    
    def switch_profile(self, profile_agents: Dict[str, List[str]]) -> Dict:
        """
        Switch to a complete new profile by replacing all active agents
        
        Args:
            profile_agents: {"global": [...], "project": [...]}
        """
        backup_name = self._create_backup("switch_profile")
        
        try:
            # First deactivate all current agents
            state = self._load_state()
            current_global = state.get("active_agents", {}).get("global", [])
            current_project = state.get("active_agents", {}).get("project", [])
            
            results = {"deactivated": {}, "activated": {}}
            
            # Deactivate current global agents
            if current_global:
                result = self.deactivate_agents(current_global, "global")
                results["deactivated"]["global"] = result
            
            # Deactivate current project agents  
            if current_project:
                result = self.deactivate_agents(current_project, "project")
                results["deactivated"]["project"] = result
            
            # Activate new global agents
            if profile_agents.get("global"):
                result = self.activate_agents(profile_agents["global"], "global")
                results["activated"]["global"] = result
            
            # Activate new project agents
            if profile_agents.get("project"):
                result = self.activate_agents(profile_agents["project"], "project")
                results["activated"]["project"] = result
            
            return {
                "success": True,
                "message": "Profile switch completed",
                "backup": backup_name,
                "details": results
            }
            
        except Exception as e:
            self.logger.error(f"Profile switch failed: {e}")
            return {
                "success": False,
                "message": f"Profile switch failed: {e}",
                "backup": backup_name
            }
    
    def get_status(self) -> Dict:
        """Get current status of shadow system"""
        state = self._load_state()
        
        # Count archived agents
        archived_counts = {
            "global": len(list((self.archive_dir / "global").glob("*.md"))),
            "project": len(list((self.archive_dir / "project").glob("*.md")))
        }
        
        # Count active agents
        active_counts = {
            "global": len(list(self.global_agents.glob("*.md"))),
            "project": len(list(self.project_agents.glob("*.md")))
        }
        
        return {
            "initialized": state.get("initialized", False),
            "active_agents": state.get("active_agents", {"global": [], "project": []}),
            "active_counts": active_counts,
            "archived_counts": archived_counts,
            "last_profile": state.get("last_profile"),
            "last_update": state.get("last_update"),
            "total_agents": sum(archived_counts.values()) + sum(active_counts.values())
        }
    
    def list_archived_agents(self, source: Optional[str] = None) -> Dict:
        """List all agents in the archive"""
        if source and source not in ["global", "project"]:
            return {"success": False, "message": "Source must be 'global' or 'project'"}
        
        archived = {}
        
        sources = [source] if source else ["global", "project"]
        
        for src in sources:
            archive_path = self.archive_dir / src
            if archive_path.exists():
                archived[src] = [f.stem for f in archive_path.glob("*.md")]
            else:
                archived[src] = []
        
        return {
            "success": True,
            "archived": archived,
            "total": sum(len(agents) for agents in archived.values())
        }
    
    def emergency_restore(self, backup_name: str) -> Dict:
        """Emergency restore from backup"""
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            return {
                "success": False,
                "message": f"Backup {backup_name} not found"
            }
        
        try:
            # Clear current active directories
            if self.global_agents.exists():
                shutil.rmtree(self.global_agents)
            if self.project_agents.exists():
                shutil.rmtree(self.project_agents)
            
            self.global_agents.mkdir(parents=True, exist_ok=True)
            self.project_agents.mkdir(parents=True, exist_ok=True)
            
            # Restore from backup
            global_backup = backup_path / "global_agents"
            if global_backup.exists():
                shutil.copytree(global_backup, self.global_agents, dirs_exist_ok=True)
            
            project_backup = backup_path / "project_agents"
            if project_backup.exists():
                shutil.copytree(project_backup, self.project_agents, dirs_exist_ok=True)
            
            # Restore state
            state_backup = backup_path / "state.yml"
            if state_backup.exists():
                shutil.copy2(state_backup, self.state_file)
            
            return {
                "success": True,
                "message": f"Emergency restore completed from {backup_name}",
                "restored_backup": backup_name
            }
            
        except Exception as e:
            self.logger.error(f"Emergency restore failed: {e}")
            return {
                "success": False,
                "message": f"Emergency restore failed: {e}"
            }

def main():
    """Command line interface for testing"""
    import sys
    
    manager = ShadowManager()
    
    if len(sys.argv) < 2:
        print("Usage: python shadow_manager.py <command>")
        print("Commands: init, status, activate, deactivate, list")
        return
    
    command = sys.argv[1]
    
    if command == "init":
        result = manager.initialize_shadow_system()
        print(json.dumps(result, indent=2))
    
    elif command == "status":
        result = manager.get_status()
        print(json.dumps(result, indent=2))
    
    elif command == "list":
        result = manager.list_archived_agents()
        print(json.dumps(result, indent=2))
    
    elif command == "activate" and len(sys.argv) >= 3:
        agents = sys.argv[2].split(",")
        source = sys.argv[3] if len(sys.argv) > 3 else "global"
        result = manager.activate_agents(agents, source)
        print(json.dumps(result, indent=2))
    
    elif command == "deactivate" and len(sys.argv) >= 3:
        agents = sys.argv[2].split(",")
        source = sys.argv[3] if len(sys.argv) > 3 else "global"
        result = manager.deactivate_agents(agents, source)
        print(json.dumps(result, indent=2))
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()