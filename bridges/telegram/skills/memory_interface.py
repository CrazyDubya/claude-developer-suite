#!/usr/bin/env python3
"""
Echo Memory Interface Skills
Provides high-level memory operations for the Claude Telegram Bridge
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

DB_FILE = Path.home() / ".claude-bridge" / "bridge.db"


@dataclass
class MemorySearchResult:
    """Result from memory search"""
    source: str
    title: str
    content: str
    relevance: float
    created_at: datetime
    metadata: Dict


class EchoMemory:
    """High-level memory interface for Echo"""

    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ============================================================
    # SHORT-TERM MEMORY - Active Working Context
    # ============================================================

    def remember_insight(self, insight_type: str, title: str, description: str,
                        session_id: Optional[str] = None, ttl_hours: int = 24) -> int:
        """
        Store a temporary insight that should be readily available

        Args:
            insight_type: Type of insight (pattern, observation, issue, solution)
            title: Brief title
            description: Full description
            session_id: Optional session ID reference
            ttl_hours: How long to keep this insight (default 24 hours)

        Returns:
            Insight ID
        """
        expires_at = datetime.now() + timedelta(hours=ttl_hours)

        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO recent_insights
                (insight_type, title, description, related_session_id, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (insight_type, title, description, session_id, expires_at.isoformat()))
            return cursor.lastrowid

    def get_recent_insights(self, limit: int = 10, insight_type: Optional[str] = None) -> List[Dict]:
        """Get recent valid insights"""
        with self.get_connection() as conn:
            query = '''
                SELECT * FROM recent_insights
                WHERE expires_at > ?
            '''
            params = [datetime.now().isoformat()]

            if insight_type:
                query += ' AND insight_type = ?'
                params.append(insight_type)

            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def update_active_context(self, context_key: str, context_data: Dict):
        """Update or create an active context entry"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO active_contexts
                (context_key, context_type, context_data, last_accessed)
                VALUES (?, ?, ?, ?)
            ''', (
                context_key,
                context_data.get('type', 'general'),
                json.dumps(context_data),
                datetime.now().isoformat()
            ))

    def get_active_context(self, context_key: str) -> Optional[Dict]:
        """Retrieve active context data"""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT context_data FROM active_contexts WHERE context_key = ?',
                (context_key,)
            ).fetchone()

            if row:
                return json.loads(row['context_data'])
            return None

    def add_pending_action(self, action_type: str, action_text: str,
                          priority: int = 5, due_date: Optional[datetime] = None) -> int:
        """Add a pending action to track"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO pending_actions
                (action_type, action_text, priority, due_date)
                VALUES (?, ?, ?, ?)
            ''', (
                action_type,
                action_text,
                priority,
                due_date.isoformat() if due_date else None
            ))
            return cursor.lastrowid

    def get_pending_actions(self, status: str = 'pending') -> List[Dict]:
        """Get pending actions"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM pending_actions
                WHERE status = ?
                ORDER BY priority ASC, due_date ASC
            ''', (status,)).fetchall()
            return [dict(row) for row in rows]

    # ============================================================
    # LONG-TERM MEMORY - Persistent Knowledge
    # ============================================================

    def store_knowledge(self, category: str, subject: str, knowledge: str,
                       session_id: Optional[str] = None, confidence: float = 1.0) -> int:
        """
        Store long-term knowledge

        Args:
            category: Knowledge category (system, code, config, procedure)
            subject: Subject/topic
            knowledge: The actual knowledge content
            session_id: Source session
            confidence: How confident we are (0.0-1.0)

        Returns:
            Knowledge ID
        """
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO knowledge_base
                (category, subject, knowledge, source_session_id, confidence)
                VALUES (?, ?, ?, ?, ?)
            ''', (category, subject, knowledge, session_id, confidence))
            return cursor.lastrowid

    def search_knowledge(self, query: str, category: Optional[str] = None,
                        limit: int = 10) -> List[Dict]:
        """
        Search knowledge base with simple text matching

        Args:
            query: Search query
            category: Optional category filter
            limit: Max results

        Returns:
            List of matching knowledge entries
        """
        with self.get_connection() as conn:
            # Simple LIKE search (can be enhanced with FTS later)
            sql = '''
                SELECT * FROM knowledge_base
                WHERE (subject LIKE ? OR knowledge LIKE ?)
            '''
            params = [f'%{query}%', f'%{query}%']

            if category:
                sql += ' AND category = ?'
                params.append(category)

            sql += ' ORDER BY confidence DESC, access_count DESC LIMIT ?'
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            # Update access count for returned results
            for row in rows:
                conn.execute('''
                    UPDATE knowledge_base
                    SET access_count = access_count + 1,
                        last_accessed = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), row['id']))

            return [dict(row) for row in rows]

    def update_project_memory(self, project_name: str, **kwargs):
        """
        Update or create project memory

        Kwargs can include:
            - project_type: Type of project
            - description: Project description
            - key_files: JSON list of important files
            - last_activity: Recent activity summary
            - metadata: Additional metadata dict
        """
        with self.get_connection() as conn:
            # Check if project exists
            existing = conn.execute(
                'SELECT id FROM project_memory WHERE project_name = ?',
                (project_name,)
            ).fetchone()

            if existing:
                # Update
                updates = []
                params = []

                for key, value in kwargs.items():
                    if key in ['project_type', 'description', 'last_activity']:
                        updates.append(f"{key} = ?")
                        params.append(value)
                    elif key == 'key_files':
                        updates.append("key_files = ?")
                        params.append(json.dumps(value) if isinstance(value, list) else value)
                    elif key == 'metadata':
                        updates.append("metadata = ?")
                        params.append(json.dumps(value))

                if updates:
                    updates.append("updated_at = ?")
                    params.append(datetime.now().isoformat())
                    updates.append("activity_count = activity_count + 1")
                    params.append(project_name)

                    sql = f"UPDATE project_memory SET {', '.join(updates)} WHERE project_name = ?"
                    conn.execute(sql, params)
            else:
                # Insert new
                conn.execute('''
                    INSERT INTO project_memory
                    (project_name, project_type, description, key_files, last_activity, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    project_name,
                    kwargs.get('project_type', 'unknown'),
                    kwargs.get('description', ''),
                    json.dumps(kwargs.get('key_files', [])),
                    kwargs.get('last_activity', ''),
                    json.dumps(kwargs.get('metadata', {}))
                ))

    def get_project_memory(self, project_name: str) -> Optional[Dict]:
        """Get project memory by name"""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM project_memory WHERE project_name = ?',
                (project_name,)
            ).fetchone()

            if row:
                data = dict(row)
                # Parse JSON fields
                if data.get('key_files'):
                    data['key_files'] = json.loads(data['key_files'])
                if data.get('metadata'):
                    data['metadata'] = json.loads(data['metadata'])
                return data
            return None

    def store_system_knowledge(self, component: str, knowledge_type: str, content: str,
                              file_paths: Optional[List[str]] = None,
                              related_services: Optional[List[str]] = None):
        """
        Store system-specific knowledge

        Args:
            component: System component (nginx, telegram-bridge, exim4, etc)
            knowledge_type: Type (config, procedure, troubleshooting, architecture)
            content: The actual knowledge
            file_paths: Related file paths
            related_services: Related systemd services or processes
        """
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO system_knowledge
                (system_component, knowledge_type, content, file_paths, related_services, last_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                component,
                knowledge_type,
                content,
                json.dumps(file_paths or []),
                json.dumps(related_services or []),
                datetime.now().isoformat()
            ))

    def search_system_knowledge(self, component: Optional[str] = None,
                               knowledge_type: Optional[str] = None) -> List[Dict]:
        """Search system knowledge"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM system_knowledge WHERE 1=1'
            params = []

            if component:
                query += ' AND system_component = ?'
                params.append(component)
            if knowledge_type:
                query += ' AND knowledge_type = ?'
                params.append(knowledge_type)

            query += ' ORDER BY last_verified DESC'

            rows = conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                data = dict(row)
                if data.get('file_paths'):
                    data['file_paths'] = json.loads(data['file_paths'])
                if data.get('related_services'):
                    data['related_services'] = json.loads(data['related_services'])
                results.append(data)
            return results

    # ============================================================
    # CONVERSATION SUMMARIES - Compressed Session History
    # ============================================================

    def create_daily_summary(self, session_id: str, summary_text: str,
                           key_topics: List[str], message_count: int,
                           importance: float = 0.5):
        """Create a daily conversation summary"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO conversation_summaries
                (session_id, summary_date, message_count, key_topics, summary_text, importance_score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                datetime.now().date().isoformat(),
                message_count,
                json.dumps(key_topics),
                summary_text,
                importance
            ))

    def get_session_history(self, session_id: str, days: int = 7) -> List[Dict]:
        """Get summarized session history"""
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM conversation_summaries
                WHERE session_id = ? AND summary_date >= ?
                ORDER BY summary_date DESC
            ''', (session_id, cutoff)).fetchall()

            results = []
            for row in rows:
                data = dict(row)
                if data.get('key_topics'):
                    data['key_topics'] = json.loads(data['key_topics'])
                results.append(data)
            return results

    # ============================================================
    # MEMORY STATS & MAINTENANCE
    # ============================================================

    def get_memory_stats(self) -> Dict:
        """Get comprehensive memory statistics"""
        with self.get_connection() as conn:
            stats = {}

            # Count all memory tables
            tables = [
                'recent_insights', 'active_contexts', 'pending_actions',
                'knowledge_base', 'project_memory', 'system_knowledge',
                'conversation_summaries'
            ]

            for table in tables:
                try:
                    count = conn.execute(f'SELECT COUNT(*) as cnt FROM {table}').fetchone()
                    stats[table] = count['cnt'] if count else 0
                except:
                    stats[table] = 0

            # Database size
            import os
            stats['db_size_kb'] = os.path.getsize(self.db_path) / 1024 if self.db_path.exists() else 0

            return stats

    def cleanup_expired_insights(self) -> int:
        """Remove expired insights, return count removed"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                DELETE FROM recent_insights
                WHERE expires_at <= ?
            ''', (datetime.now().isoformat(),))
            return cursor.rowcount

    def vacuum_database(self):
        """Optimize database"""
        with self.get_connection() as conn:
            conn.execute('VACUUM')


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def quick_remember(text: str, category: str = "general") -> int:
    """Quick function to remember something"""
    memory = EchoMemory()
    return memory.store_knowledge(category, "Quick Note", text)


def quick_recall(query: str, limit: int = 5) -> List[Dict]:
    """Quick function to recall knowledge"""
    memory = EchoMemory()
    return memory.search_knowledge(query, limit=limit)


def remember_project(name: str, description: str, files: List[str]):
    """Quick function to remember project details"""
    memory = EchoMemory()
    memory.update_project_memory(
        name,
        description=description,
        key_files=files,
        last_activity=f"Registered on {datetime.now().strftime('%Y-%m-%d')}"
    )


def get_stats() -> Dict:
    """Quick stats"""
    memory = EchoMemory()
    return memory.get_memory_stats()


# ============================================================
# CLI INTERFACE (for testing)
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python memory_interface.py stats")
        print("  python memory_interface.py remember <text>")
        print("  python memory_interface.py recall <query>")
        print("  python memory_interface.py cleanup")
        sys.exit(1)

    cmd = sys.argv[1]
    memory = EchoMemory()

    if cmd == "stats":
        stats = memory.get_memory_stats()
        print("📊 Memory Statistics:")
        for key, value in stats.items():
            print(f"  {key:30s}: {value}")

    elif cmd == "remember" and len(sys.argv) >= 3:
        text = " ".join(sys.argv[2:])
        id = memory.store_knowledge("manual", "CLI Note", text)
        print(f"✅ Stored as knowledge #{id}")

    elif cmd == "recall" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        results = memory.search_knowledge(query, limit=5)
        print(f"🔍 Found {len(results)} results:")
        for r in results:
            print(f"\n  [{r['category']}] {r['subject']}")
            print(f"  {r['knowledge'][:100]}...")

    elif cmd == "cleanup":
        count = memory.cleanup_expired_insights()
        print(f"🧹 Cleaned up {count} expired insights")
        memory.vacuum_database()
        print("✅ Database vacuumed")

    else:
        print(f"Unknown command: {cmd}")
