#!/usr/bin/env python3
"""
Agent Registry Database Setup and Management
Scalable system for organizing billions of agents with project-specific loading

Version 2.0: Shadow Directory System
- Physical control over which agents Claude Code sees
- Archive system for unlimited agent storage
- State management for active/inactive agents
"""

import sqlite3
import os
import sys
import yaml
import json
import hashlib
import shutil
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re

# Import shadow manager
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
from shadow_manager import ShadowManager

class AgentRegistry:
    def __init__(self, registry_path: str = None, enable_shadow_system: bool = False):
        if registry_path is None:
            registry_path = os.path.expanduser("~/.claude/agent-registry")
        
        self.registry_path = Path(registry_path)
        self.db_path = self.registry_path / "index.db"
        self.enable_shadow_system = enable_shadow_system
        
        # Initialize shadow manager if enabled
        self.shadow_manager = None
        if enable_shadow_system:
            self.shadow_manager = ShadowManager()
        
        # Define multiple agent source paths
        # In shadow mode, we scan from archive instead of active directories
        if enable_shadow_system and self.shadow_manager:
            self.agent_sources = {
                'global': self.shadow_manager.archive_dir / "global",
                'project': self.shadow_manager.archive_dir / "project"
            }
        else:
            self.agent_sources = {
                'global': Path(os.path.expanduser("~/.claude/agents")),
                'project': Path.cwd() / ".claude" / "agents"
            }
        
        # Ensure directories exist
        self.registry_path.mkdir(parents=True, exist_ok=True)
        (self.registry_path / "domains").mkdir(exist_ok=True)
        (self.registry_path / "capabilities").mkdir(exist_ok=True)
        (self.registry_path / "projects" / "templates").mkdir(parents=True, exist_ok=True)
        (self.registry_path / "projects" / "profiles").mkdir(parents=True, exist_ok=True)
        (self.registry_path / "backups").mkdir(parents=True, exist_ok=True)
        
        self.init_database()
    
    def init_database(self):
        """Initialize the agent registry database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            description TEXT,
            tools TEXT,
            domains TEXT,
            capabilities TEXT,
            tags TEXT,
            file_hash TEXT,
            source TEXT DEFAULT 'global',
            is_custom BOOLEAN DEFAULT FALSE,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS agent_domains (
            agent_id INTEGER,
            domain TEXT,
            FOREIGN KEY(agent_id) REFERENCES agents(id)
        );
        
        CREATE TABLE IF NOT EXISTS agent_capabilities (
            agent_id INTEGER,
            capability TEXT,
            FOREIGN KEY(agent_id) REFERENCES agents(id)
        );
        
        CREATE TABLE IF NOT EXISTS agent_tags (
            agent_id INTEGER,
            tag TEXT,
            FOREIGN KEY(agent_id) REFERENCES agents(id)
        );
        
        CREATE TABLE IF NOT EXISTS project_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            agent_list TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_agent_name ON agents(name);
        CREATE INDEX IF NOT EXISTS idx_agent_source ON agents(source);
        CREATE INDEX IF NOT EXISTS idx_domains ON agent_domains(domain);
        CREATE INDEX IF NOT EXISTS idx_capabilities ON agent_capabilities(capability);
        CREATE INDEX IF NOT EXISTS idx_tags ON agent_tags(tag);
        """)

        # Check if we need to migrate existing schema
        cursor.execute("PRAGMA table_info(agents)")
        columns = [col[1] for col in cursor.fetchall()]

        # Add missing columns for v1.1.0+ compatibility
        if 'source' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN source TEXT DEFAULT 'global'")
            print("✅ Added 'source' column to agents table")

        if 'is_custom' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN is_custom BOOLEAN DEFAULT FALSE")
            print("✅ Added 'is_custom' column to agents table")
        
        conn.commit()
        conn.close()
    
    def scan_and_index_agents(self):
        """Scan agents from multiple sources and add them to the registry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        total_indexed = 0
        total_updated = 0
        
        # Scan each agent source
        for source_name, source_path in self.agent_sources.items():
            if not source_path.exists():
                print(f"Agent source '{source_name}' not found: {source_path}")
                continue
                
            print(f"Scanning {source_name} agents: {source_path}")
            indexed_count = 0
            updated_count = 0
            
            for agent_file in source_path.glob("*.md"):
                try:
                    # Calculate file hash to detect changes
                    with open(agent_file, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Check if agent already exists (by file path)
                    cursor.execute("SELECT id, file_hash FROM agents WHERE file_path = ?", (str(agent_file),))
                    existing = cursor.fetchone()
                    
                    if existing and existing[1] == file_hash:
                        continue  # No changes, skip
                    
                    # Parse agent file
                    agent_data = self.parse_agent_file(agent_file)
                    if not agent_data:
                        continue
                    
                    # Add source information
                    agent_data['source'] = source_name
                    agent_data['is_custom'] = source_name != 'global'
                    
                    if existing:
                        # Update existing agent
                        self.update_agent(cursor, existing[0], agent_data, file_hash)
                        updated_count += 1
                    else:
                        # Check for naming conflicts (same name, different path)
                        cursor.execute("SELECT id, file_path, source FROM agents WHERE name = ?", (agent_data['name'],))
                        conflict = cursor.fetchone()
                        
                        if conflict:
                            print(f"⚠️  Name conflict: '{agent_data['name']}' exists in {conflict[2]} source")
                            print(f"   Existing: {conflict[1]}")
                            print(f"   New: {agent_file}")
                            if source_name == 'project':
                                print(f"   → Using project version (takes precedence)")
                                # Remove the global version
                                cursor.execute("DELETE FROM agents WHERE id = ?", (conflict[0],))
                            else:
                                print(f"   → Keeping existing version")
                                continue
                        
                        # Insert new agent
                        self.insert_agent(cursor, agent_file, agent_data, file_hash)
                        indexed_count += 1
                        
                except Exception as e:
                    print(f"Error processing {agent_file}: {e}")
            
            print(f"  → {source_name}: {indexed_count} new, {updated_count} updated")
            total_indexed += indexed_count
            total_updated += updated_count
        
        conn.commit()
        conn.close()
        
        print(f"Agent indexing complete: {total_indexed} new, {total_updated} updated")
    
    def parse_agent_file(self, file_path: Path) -> Optional[Dict]:
        """Parse agent markdown file and extract metadata"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract YAML frontmatter
            yaml_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
            if not yaml_match:
                return None
            
            frontmatter = yaml.safe_load(yaml_match.group(1))
            
            # Extract description from content
            description = content[yaml_match.end():].strip()
            # Get first paragraph as description
            desc_lines = description.split('\n\n')[0].replace('\n', ' ').strip()
            
            return {
                'name': frontmatter.get('name', file_path.stem),
                'description': frontmatter.get('description', desc_lines),
                'tools': frontmatter.get('tools', []),
                'domains': self.extract_domains(frontmatter, description),
                'capabilities': self.extract_capabilities(frontmatter, description),
                'tags': self.extract_tags(frontmatter, description)
            }
            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
    
    def extract_domains(self, frontmatter: Dict, content: str) -> List[str]:
        """Extract domain classifications from agent"""
        domains = []
        
        # Domain keywords mapping
        domain_map = {
            'web': ['html', 'css', 'javascript', 'react', 'vue', 'angular', 'frontend', 'web'],
            'backend': ['api', 'server', 'fastapi', 'django', 'flask', 'backend', 'express'],
            'data-science': ['pandas', 'numpy', 'scikit', 'tensorflow', 'pytorch', 'data', 'ml'],
            'infrastructure': ['docker', 'kubernetes', 'aws', 'terraform', 'devops', 'deployment'],
            'graphics': ['threejs', 'opengl', 'shader', 'webgl', 'graphics', 'visualization'],
            'database': ['sql', 'postgres', 'mysql', 'mongodb', 'database', 'query'],
            'testing': ['pytest', 'jest', 'test', 'unittest', 'testing', 'qa'],
            'security': ['security', 'auth', 'encryption', 'vulnerability', 'audit'],
            'mobile': ['ios', 'android', 'mobile', 'swift', 'kotlin', 'flutter'],
            'desktop': ['electron', 'tauri', 'qt', 'gui', 'desktop']
        }
        
        name = frontmatter.get('name', '').lower()
        description = frontmatter.get('description', '').lower()
        full_content = (name + ' ' + description + ' ' + content.lower())
        
        for domain, keywords in domain_map.items():
            if any(keyword in full_content for keyword in keywords):
                domains.append(domain)
        
        return domains
    
    def extract_capabilities(self, frontmatter: Dict, content: str) -> List[str]:
        """Extract capability classifications from agent"""
        capabilities = []
        
        capability_map = {
            'optimization': ['optim', 'performance', 'speed', 'efficiency'],
            'debugging': ['debug', 'error', 'troubleshoot', 'fix'],
            'refactoring': ['refactor', 'clean', 'restructure', 'improve'],
            'documentation': ['doc', 'readme', 'comment', 'explain'],
            'testing': ['test', 'unit', 'integration', 'coverage'],
            'analysis': ['analy', 'review', 'audit', 'examine'],
            'generation': ['generat', 'create', 'build', 'scaffold'],
            'migration': ['migrat', 'upgrade', 'convert', 'port'],
            'monitoring': ['monitor', 'observ', 'log', 'metric'],
            'automation': ['automat', 'script', 'workflow', 'pipeline']
        }
        
        full_content = (frontmatter.get('name', '') + ' ' + 
                       frontmatter.get('description', '') + ' ' + content).lower()
        
        for capability, keywords in capability_map.items():
            if any(keyword in full_content for keyword in keywords):
                capabilities.append(capability)
        
        return capabilities
    
    def extract_tags(self, frontmatter: Dict, content: str) -> List[str]:
        """Extract tags from agent content"""
        tags = []
        
        # Extract programming languages
        languages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'rust', 'go', 
                    'php', 'ruby', 'swift', 'kotlin', 'scala', 'r', 'julia']
        
        full_content = (frontmatter.get('name', '') + ' ' + 
                       frontmatter.get('description', '') + ' ' + content).lower()
        
        for lang in languages:
            if lang in full_content:
                tags.append(f"lang:{lang}")
        
        # Extract frameworks
        frameworks = ['react', 'vue', 'angular', 'django', 'flask', 'fastapi', 
                     'express', 'spring', 'rails', 'laravel']
        
        for framework in frameworks:
            if framework in full_content:
                tags.append(f"framework:{framework}")
        
        return tags
    
    def insert_agent(self, cursor, file_path: Path, agent_data: Dict, file_hash: str):
        """Insert new agent into database"""
        cursor.execute("""
        INSERT INTO agents (name, file_path, description, tools, domains, 
                           capabilities, tags, file_hash, source, is_custom)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_data['name'],
            str(file_path),
            agent_data['description'],
            json.dumps(agent_data['tools']),
            json.dumps(agent_data['domains']),
            json.dumps(agent_data['capabilities']),
            json.dumps(agent_data['tags']),
            file_hash,
            agent_data.get('source', 'global'),
            agent_data.get('is_custom', False)
        ))
        
        agent_id = cursor.lastrowid
        
        # Insert domain relationships
        for domain in agent_data['domains']:
            cursor.execute("INSERT INTO agent_domains (agent_id, domain) VALUES (?, ?)",
                          (agent_id, domain))
        
        # Insert capability relationships
        for capability in agent_data['capabilities']:
            cursor.execute("INSERT INTO agent_capabilities (agent_id, capability) VALUES (?, ?)",
                          (agent_id, capability))
        
        # Insert tag relationships
        for tag in agent_data['tags']:
            cursor.execute("INSERT INTO agent_tags (agent_id, tag) VALUES (?, ?)",
                          (agent_id, tag))
    
    def update_agent(self, cursor, agent_id: int, agent_data: Dict, file_hash: str):
        """Update existing agent in database"""
        cursor.execute("""
        UPDATE agents SET description = ?, tools = ?, domains = ?, 
               capabilities = ?, tags = ?, file_hash = ?, source = ?, 
               is_custom = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            agent_data['description'],
            json.dumps(agent_data['tools']),
            json.dumps(agent_data['domains']),
            json.dumps(agent_data['capabilities']),
            json.dumps(agent_data['tags']),
            file_hash,
            agent_data.get('source', 'global'),
            agent_data.get('is_custom', False),
            agent_id
        ))
        
        # Clear existing relationships
        cursor.execute("DELETE FROM agent_domains WHERE agent_id = ?", (agent_id,))
        cursor.execute("DELETE FROM agent_capabilities WHERE agent_id = ?", (agent_id,))
        cursor.execute("DELETE FROM agent_tags WHERE agent_id = ?", (agent_id,))
        
        # Insert updated relationships
        for domain in agent_data['domains']:
            cursor.execute("INSERT INTO agent_domains (agent_id, domain) VALUES (?, ?)",
                          (agent_id, domain))
        
        for capability in agent_data['capabilities']:
            cursor.execute("INSERT INTO agent_capabilities (agent_id, capability) VALUES (?, ?)",
                          (agent_id, capability))
        
        for tag in agent_data['tags']:
            cursor.execute("INSERT INTO agent_tags (agent_id, tag) VALUES (?, ?)",
                          (agent_id, tag))
    
    def search_agents(self, query: str = None, domains: List[str] = None, 
                     capabilities: List[str] = None, tags: List[str] = None,
                     source: str = None, limit: int = 50) -> List[Dict]:
        """Search agents based on criteria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql_parts = ["SELECT DISTINCT a.name, a.description, a.domains, a.capabilities, a.source FROM agents a"]
        conditions = []
        params = []
        
        if domains:
            sql_parts.append("JOIN agent_domains ad ON a.id = ad.agent_id")
            conditions.append(f"ad.domain IN ({','.join(['?' for _ in domains])})")
            params.extend(domains)
        
        if capabilities:
            sql_parts.append("JOIN agent_capabilities ac ON a.id = ac.agent_id")
            conditions.append(f"ac.capability IN ({','.join(['?' for _ in capabilities])})")
            params.extend(capabilities)
        
        if tags:
            sql_parts.append("JOIN agent_tags at ON a.id = at.agent_id")
            conditions.append(f"at.tag IN ({','.join(['?' for _ in tags])})")
            params.extend(tags)
        
        if query:
            conditions.append("(a.name LIKE ? OR a.description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        
        if source:
            conditions.append("a.source = ?")
            params.append(source)
        
        if conditions:
            sql_parts.append("WHERE " + " AND ".join(conditions))
        
        sql_parts.append(f"LIMIT {limit}")
        
        sql = " ".join(sql_parts)
        cursor.execute(sql, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'name': row[0],
                'description': row[1],
                'domains': json.loads(row[2]),
                'capabilities': json.loads(row[3]),
                'source': row[4]
            })
        
        conn.close()
        return results
    
    def save_project_profile(self, name: str, description: str, agents: List[str]):
        """Save a project agent profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT OR REPLACE INTO project_profiles (name, description, agent_list)
        VALUES (?, ?, ?)
        """, (name, description, json.dumps(agents)))
        
        conn.commit()
        conn.close()
    
    def load_project_profile(self, name: str) -> Optional[Dict]:
        """Load a project agent profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT description, agent_list FROM project_profiles WHERE name = ?", (name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'name': name,
                'description': result[0],
                'agents': json.loads(result[1])
            }
        return None
    
    def backup_agents(self, backup_name: str = None) -> str:
        """Create a timestamped backup of all agent configurations"""
        if backup_name is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"agents_backup_{timestamp}"
        
        backup_dir = self.registry_path / "backups" / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup database
        backup_db_path = backup_dir / "index.db"
        shutil.copy2(self.db_path, backup_db_path)
        
        # Backup agent files from all sources
        for source_name, source_path in self.agent_sources.items():
            if source_path.exists():
                source_backup_dir = backup_dir / source_name
                source_backup_dir.mkdir(exist_ok=True)
                
                for agent_file in source_path.glob("*.md"):
                    shutil.copy2(agent_file, source_backup_dir / agent_file.name)
        
        # Create backup manifest
        manifest = {
            'timestamp': datetime.datetime.now().isoformat(),
            'sources': {name: str(path) for name, path in self.agent_sources.items()},
            'agent_count': self.get_agent_count(),
            'backup_name': backup_name
        }
        
        with open(backup_dir / "backup_manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"✅ Backup created: {backup_name}")
        print(f"   Location: {backup_dir}")
        print(f"   Agents backed up: {manifest['agent_count']}")
        
        return backup_name
    
    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        backups_dir = self.registry_path / "backups"
        
        if not backups_dir.exists():
            return backups
        
        for backup_dir in backups_dir.iterdir():
            if backup_dir.is_dir():
                manifest_file = backup_dir / "backup_manifest.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r') as f:
                        manifest = json.load(f)
                    backups.append({
                        'name': manifest['backup_name'],
                        'timestamp': manifest['timestamp'],
                        'agent_count': manifest['agent_count'],
                        'path': str(backup_dir)
                    })
        
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def restore_backup(self, backup_name: str, confirm: bool = False) -> bool:
        """Restore agents from backup"""
        backup_dir = self.registry_path / "backups" / backup_name
        
        if not backup_dir.exists():
            print(f"❌ Backup not found: {backup_name}")
            return False
        
        manifest_file = backup_dir / "backup_manifest.json"
        if not manifest_file.exists():
            print(f"❌ Backup manifest not found: {backup_name}")
            return False
        
        if not confirm:
            print(f"⚠️  This will restore agents from backup: {backup_name}")
            print("   Current agents will be replaced with backup versions.")
            print("   Run with confirm=True to proceed.")
            return False
        
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
        
        # Restore database
        backup_db_path = backup_dir / "index.db"
        if backup_db_path.exists():
            shutil.copy2(backup_db_path, self.db_path)
        
        print(f"✅ Backup restored: {backup_name}")
        print(f"   Timestamp: {manifest['timestamp']}")
        print(f"   Agent count: {manifest['agent_count']}")
        
        return True
    
    def verify_agents(self) -> Dict[str, List[str]]:
        """Verify agent file integrity against database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, file_path, file_hash FROM agents")
        agents_in_db = cursor.fetchall()
        conn.close()
        
        results = {
            'valid': [],
            'missing_files': [],
            'hash_mismatches': [],
            'orphaned_files': []
        }
        
        # Check agents in database
        for name, file_path, stored_hash in agents_in_db:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                results['missing_files'].append(f"{name} ({file_path})")
                continue
            
            # Check file hash
            with open(file_path_obj, 'rb') as f:
                current_hash = hashlib.md5(f.read()).hexdigest()
            
            if current_hash != stored_hash:
                results['hash_mismatches'].append(f"{name} ({file_path})")
            else:
                results['valid'].append(name)
        
        # Check for orphaned files
        for source_name, source_path in self.agent_sources.items():
            if source_path.exists():
                for agent_file in source_path.glob("*.md"):
                    # Check if this file is in the database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM agents WHERE file_path = ?", (str(agent_file),))
                    if not cursor.fetchone():
                        results['orphaned_files'].append(str(agent_file))
                    conn.close()
        
        return results
    
    def get_agent_count(self) -> int:
        """Get total number of indexed agents"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM agents")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_sources(self) -> List[Dict]:
        """Get information about all agent sources"""
        sources = []
        for name, path in self.agent_sources.items():
            agent_count = 0
            if path.exists():
                agent_count = len(list(path.glob("*.md")))
            
            sources.append({
                'name': name,
                'path': str(path),
                'exists': path.exists(),
                'agent_count': agent_count
            })
        
        return sources
    
    def import_agents(self, import_path: str) -> int:
        """Import agents from a directory"""
        import_path_obj = Path(import_path)
        
        if not import_path_obj.exists():
            print(f"❌ Import path not found: {import_path}")
            return 0
        
        imported_count = 0
        
        # Temporarily add import path as a source
        original_sources = self.agent_sources.copy()
        self.agent_sources['import'] = import_path_obj
        
        try:
            # Run indexing on just the import source
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for agent_file in import_path_obj.glob("*.md"):
                try:
                    # Calculate file hash
                    with open(agent_file, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Parse agent file
                    agent_data = self.parse_agent_file(agent_file)
                    if not agent_data:
                        continue
                    
                    # Mark as custom import
                    agent_data['source'] = 'import'
                    agent_data['is_custom'] = True
                    
                    # Check if agent already exists
                    cursor.execute("SELECT id FROM agents WHERE name = ?", (agent_data['name'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        print(f"⚠️  Agent '{agent_data['name']}' already exists, skipping")
                        continue
                    
                    # Insert new agent
                    self.insert_agent(cursor, agent_file, agent_data, file_hash)
                    imported_count += 1
                    print(f"✅ Imported: {agent_data['name']}")
                    
                except Exception as e:
                    print(f"Error importing {agent_file}: {e}")
            
            conn.commit()
            conn.close()
            
        finally:
            # Restore original sources
            self.agent_sources = original_sources
        
        print(f"Import complete: {imported_count} agents imported")
        return imported_count
    
    # Shadow System Integration Methods
    
    def initialize_shadow_system(self, force: bool = False) -> Dict:
        """Initialize shadow directory system"""
        if not self.shadow_manager:
            return {
                "success": False,
                "message": "Shadow system not enabled. Create registry with enable_shadow_system=True"
            }
        
        result = self.shadow_manager.initialize_shadow_system(force=force)
        
        # After initialization, re-scan the archive for indexing
        if result.get("success"):
            print("Re-indexing agents from archive...")
            self.agent_sources = {
                'global': self.shadow_manager.archive_dir / "global",
                'project': self.shadow_manager.archive_dir / "project"
            }
            self.scan_and_index_agents()
        
        return result
    
    def get_shadow_status(self) -> Dict:
        """Get shadow system status"""
        if not self.shadow_manager:
            return {"shadow_enabled": False}
        
        status = self.shadow_manager.get_status()
        status["shadow_enabled"] = True
        return status
    
    def activate_agents_shadow(self, agent_names: List[str], source: str = "global") -> Dict:
        """Activate agents in shadow system"""
        if not self.shadow_manager:
            return {"success": False, "message": "Shadow system not enabled"}
        
        return self.shadow_manager.activate_agents(agent_names, source)
    
    def deactivate_agents_shadow(self, agent_names: List[str], source: str = "global") -> Dict:
        """Deactivate agents in shadow system"""
        if not self.shadow_manager:
            return {"success": False, "message": "Shadow system not enabled"}
        
        return self.shadow_manager.deactivate_agents(agent_names, source)
    
    def switch_profile_shadow(self, profile_name: str) -> Dict:
        """Switch to a complete agent profile in shadow system"""
        if not self.shadow_manager:
            return {"success": False, "message": "Shadow system not enabled"}
        
        # Load profile from database
        profile_data = self.load_project_profile(profile_name)
        if not profile_data:
            return {"success": False, "message": f"Profile '{profile_name}' not found"}
        
        # Convert agent list to shadow system format
        profile_agents = {
            "global": profile_data["agents"],
            "project": []  # Profiles typically use global agents
        }
        
        result = self.shadow_manager.switch_profile(profile_agents)
        
        # Update shadow system state with profile name
        if result.get("success"):
            state = self.shadow_manager._load_state()
            state["last_profile"] = profile_name
            self.shadow_manager._save_state(state)
        
        return result
    
    def list_archived_agents_shadow(self, source: Optional[str] = None) -> Dict:
        """List archived agents in shadow system"""
        if not self.shadow_manager:
            return {"success": False, "message": "Shadow system not enabled"}
        
        return self.shadow_manager.list_archived_agents(source)
    
    def emergency_restore_shadow(self, backup_name: str) -> Dict:
        """Emergency restore from shadow system backup"""
        if not self.shadow_manager:
            return {"success": False, "message": "Shadow system not enabled"}
        
        return self.shadow_manager.emergency_restore(backup_name)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Registry Setup")
    parser.add_argument("--shadow", action="store_true", help="Enable shadow system")
    parser.add_argument("--init-shadow", action="store_true", help="Initialize shadow system")
    parser.add_argument("--force", action="store_true", help="Force re-initialization")
    args = parser.parse_args()
    
    # Create registry with shadow system if requested
    registry = AgentRegistry(enable_shadow_system=args.shadow)
    
    if args.init_shadow:
        if not args.shadow:
            print("❌ --shadow flag required to initialize shadow system")
            sys.exit(1)
        
        print("🔄 Initializing shadow directory system...")
        result = registry.initialize_shadow_system(force=args.force)
        print(json.dumps(result, indent=2))
        
        if result.get("success"):
            print("\n✅ Shadow system initialization complete!")
            print("   All existing agents have been archived.")
            print("   Use /agent-manager activate to make agents available to Claude Code.")
        else:
            print(f"\n❌ Shadow system initialization failed: {result.get('message')}")
            sys.exit(1)
    else:
        print("Initializing agent registry...")
        registry.scan_and_index_agents()
        print("Agent registry setup complete!")
        
        if args.shadow:
            print("\n🔍 Shadow system status:")
            status = registry.get_shadow_status()
            print(json.dumps(status, indent=2))