"""
Claude Skills Database Connector

Provides a Python API for interacting with the skills metadata database.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

class SkillDB:
    """Database connector for Claude Skills metadata."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connector.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.claude/skills/data/skills_metadata.db
        """
        if db_path is None:
            db_path = Path.home() / '.claude' / 'skills' / 'data' / 'skills_metadata.db'
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Run 'python3 ~/.claude/skills/scripts/init_db.py' to create it."
            )

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
        finally:
            conn.close()

    # === Skill Management ===

    def get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get skill metadata by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skills_registry WHERE name = ?',
                (skill_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all skills, optionally filtered by category.

        Args:
            category: Filter by category (e.g., 'database', 'testing')
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if category:
                cursor.execute(
                    'SELECT * FROM skills_registry WHERE category = ? ORDER BY name',
                    (category,)
                )
            else:
                cursor.execute('SELECT * FROM skills_registry ORDER BY name')

            return [dict(row) for row in cursor.fetchall()]

    def get_skill_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with skill counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category, COUNT(*) as skill_count
                FROM skills_registry
                GROUP BY category
                ORDER BY skill_count DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # === Execution Logging ===

    def log_execution(
        self,
        skill_name: str,
        duration_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        trigger_keywords: Optional[str] = None
    ) -> int:
        """
        Log a skill execution.

        Args:
            skill_name: Name of the skill
            duration_ms: Execution duration in milliseconds
            success: Whether execution was successful
            error_message: Error message if execution failed
            trigger_keywords: Keywords that triggered the skill

        Returns:
            Execution ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO skill_executions
                (skill_name, duration_ms, success, error_message, trigger_keywords)
                VALUES (?, ?, ?, ?, ?)
            ''', (skill_name, duration_ms, success, error_message, trigger_keywords))
            conn.commit()
            return cursor.lastrowid

    def get_execution_history(
        self,
        skill_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get execution history.

        Args:
            skill_name: Filter by skill name
            limit: Maximum number of records to return
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if skill_name:
                cursor.execute('''
                    SELECT * FROM skill_executions
                    WHERE skill_name = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                ''', (skill_name, limit))
            else:
                cursor.execute('''
                    SELECT * FROM skill_executions
                    ORDER BY executed_at DESC
                    LIMIT ?
                ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    # === Analytics ===

    def get_skill_stats(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for a skill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skill_usage_stats WHERE skill_name = ?',
                (skill_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_skill_popularity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most popular skills by usage count.

        Args:
            limit: Number of skills to return
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skill_popularity LIMIT ?',
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_skill_errors(self) -> List[Dict[str, Any]]:
        """Get skills with errors."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM skill_errors')
            return [dict(row) for row in cursor.fetchall()]

    # === Feedback ===

    def add_feedback(
        self,
        skill_name: str,
        rating: int,
        helpful: bool,
        comments: Optional[str] = None
    ) -> int:
        """
        Add user feedback for a skill.

        Args:
            skill_name: Name of the skill
            rating: Rating from 1-5
            helpful: Whether the skill was helpful
            comments: Optional comments

        Returns:
            Feedback ID
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO skill_feedback
                (skill_name, rating, helpful, comments)
                VALUES (?, ?, ?, ?)
            ''', (skill_name, rating, helpful, comments))
            conn.commit()
            return cursor.lastrowid

    def get_skill_feedback(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get all feedback for a skill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM skill_feedback
                WHERE skill_name = ?
                ORDER BY submitted_at DESC
            ''', (skill_name,))
            return [dict(row) for row in cursor.fetchall()]

    # === Resources ===

    def get_skill_templates(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get all templates for a skill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skill_templates WHERE skill_name = ?',
                (skill_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_skill_scripts(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get all scripts for a skill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skill_scripts WHERE skill_name = ?',
                (skill_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_skill_references(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get all reference docs for a skill."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM skill_references WHERE skill_name = ?',
                (skill_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_skill_resources(self, skill_name: str) -> Dict[str, Any]:
        """Get all resources (templates, scripts, references) for a skill."""
        return {
            'templates': self.get_skill_templates(skill_name),
            'scripts': self.get_skill_scripts(skill_name),
            'references': self.get_skill_references(skill_name)
        }

    # === Search ===

    def search_skills(self, query: str) -> List[Dict[str, Any]]:
        """
        Search skills by name or description.

        Args:
            query: Search query
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f'%{query}%'
            cursor.execute('''
                SELECT * FROM skills_registry
                WHERE name LIKE ? OR description LIKE ?
                ORDER BY name
            ''', (search_pattern, search_pattern))
            return [dict(row) for row in cursor.fetchall()]

    # === Summary Reports ===

    def get_summary(self) -> Dict[str, Any]:
        """Get overall database summary."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Count totals
            cursor.execute('SELECT COUNT(*) FROM skills_registry')
            total_skills = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM skill_executions')
            total_executions = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM skill_templates')
            total_templates = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM skill_scripts')
            total_scripts = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM skill_feedback')
            total_feedback = cursor.fetchone()[0]

            # Most used skill
            cursor.execute('''
                SELECT skill_name, total_executions
                FROM skill_usage_stats
                ORDER BY total_executions DESC
                LIMIT 1
            ''')
            most_used = cursor.fetchone()

            # Highest rated skill
            cursor.execute('''
                SELECT name, avg_rating
                FROM skill_popularity
                WHERE feedback_count > 0
                ORDER BY avg_rating DESC
                LIMIT 1
            ''')
            highest_rated = cursor.fetchone()

            return {
                'total_skills': total_skills,
                'total_executions': total_executions,
                'total_templates': total_templates,
                'total_scripts': total_scripts,
                'total_feedback': total_feedback,
                'most_used_skill': dict(most_used) if most_used else None,
                'highest_rated_skill': dict(highest_rated) if highest_rated else None
            }


# Convenience function for quick access
def get_db() -> SkillDB:
    """Get a SkillDB instance."""
    return SkillDB()
