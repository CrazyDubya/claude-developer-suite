#!/usr/bin/env python3
"""
Echo Plugin System
Extends the Telegram Bridge with memory-aware commands and auto-learning
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from memory_interface import EchoMemory


@dataclass
class PluginCommand:
    """Plugin command definition"""
    name: str
    description: str
    handler: Callable
    requires_args: bool = False
    hidden: bool = False


class EchoPluginManager:
    """Manages Echo's memory-aware plugins"""

    def __init__(self):
        self.memory = EchoMemory()
        self.commands: Dict[str, PluginCommand] = {}
        self._register_default_commands()

    def register_command(self, name: str, description: str, handler: Callable,
                        requires_args: bool = False, hidden: bool = False):
        """Register a new command"""
        self.commands[name] = PluginCommand(
            name=name,
            description=description,
            handler=handler,
            requires_args=requires_args,
            hidden=hidden
        )

    def execute_command(self, command: str, args: List[str], chat_id: str) -> str:
        """Execute a plugin command"""
        if command not in self.commands:
            return f"❓ Unknown command: {command}"

        cmd = self.commands[command]

        if cmd.requires_args and not args:
            return f"⚠️ {command} requires arguments"

        try:
            return cmd.handler(args, chat_id)
        except Exception as e:
            return f"❌ Error executing {command}: {e}"

    def get_help_text(self) -> str:
        """Generate help text for all commands"""
        help_lines = ["🧠 **Echo Memory Commands:**\n"]

        for name, cmd in sorted(self.commands.items()):
            if not cmd.hidden:
                args_text = " <args>" if cmd.requires_args else ""
                help_lines.append(f"/{name}{args_text} - {cmd.description}")

        return "\n".join(help_lines)

    # ============================================================
    # DEFAULT COMMAND HANDLERS
    # ============================================================

    def _register_default_commands(self):
        """Register all default memory commands"""

        # Memory stats
        self.register_command(
            "memory-stats",
            "Show memory system statistics",
            self._cmd_memory_stats
        )

        # Remember knowledge
        self.register_command(
            "remember",
            "Store knowledge (usage: /remember <category> <text>)",
            self._cmd_remember,
            requires_args=True
        )

        # Recall knowledge
        self.register_command(
            "recall",
            "Search memory (usage: /recall <query>)",
            self._cmd_recall,
            requires_args=True
        )

        # Insights
        self.register_command(
            "insights",
            "Show recent insights",
            self._cmd_insights
        )

        # Add insight
        self.register_command(
            "note-insight",
            "Record an insight (usage: /note-insight <type> <title> | <description>)",
            self._cmd_note_insight,
            requires_args=True
        )

        # Pending actions
        self.register_command(
            "actions",
            "Show pending actions",
            self._cmd_actions
        )

        # Add action
        self.register_command(
            "todo",
            "Add pending action (usage: /todo <priority> <text>)",
            self._cmd_todo,
            requires_args=True
        )

        # Project memory
        self.register_command(
            "projects",
            "List known projects",
            self._cmd_projects
        )

        # Project details
        self.register_command(
            "project",
            "Show project details (usage: /project <name>)",
            self._cmd_project,
            requires_args=True
        )

        # System knowledge
        self.register_command(
            "system-info",
            "Search system knowledge (usage: /system-info <component>)",
            self._cmd_system_info
        )

        # Session summaries
        self.register_command(
            "session-history",
            "Show session summary history",
            self._cmd_session_history
        )

        # Cleanup
        self.register_command(
            "memory-cleanup",
            "Clean up expired memory entries",
            self._cmd_memory_cleanup
        )

        # Full memory search
        self.register_command(
            "search-all",
            "Search across all memory types (usage: /search-all <query>)",
            self._cmd_search_all,
            requires_args=True
        )

    # ============================================================
    # COMMAND IMPLEMENTATIONS
    # ============================================================

    def _cmd_memory_stats(self, args: List[str], chat_id: str) -> str:
        """Show memory statistics"""
        stats = self.memory.get_memory_stats()

        output = ["📊 **Echo Memory Statistics**\n"]
        output.append("**Short-term memory:**")
        output.append(f"  • Recent insights: {stats.get('recent_insights', 0)}")
        output.append(f"  • Active contexts: {stats.get('active_contexts', 0)}")
        output.append(f"  • Pending actions: {stats.get('pending_actions', 0)}")

        output.append("\n**Long-term memory:**")
        output.append(f"  • Knowledge base: {stats.get('knowledge_base', 0)}")
        output.append(f"  • Projects tracked: {stats.get('project_memory', 0)}")
        output.append(f"  • System knowledge: {stats.get('system_knowledge', 0)}")

        output.append("\n**Conversation history:**")
        output.append(f"  • Summaries: {stats.get('conversation_summaries', 0)}")

        output.append(f"\n💾 Database size: {stats.get('db_size_kb', 0):.1f} KB")

        return "\n".join(output)

    def _cmd_remember(self, args: List[str], chat_id: str) -> str:
        """Store knowledge"""
        if len(args) < 2:
            return "⚠️ Usage: /remember <category> <text>"

        category = args[0]
        text = " ".join(args[1:])

        # Try to extract a subject from the text (first sentence or first 50 chars)
        subject = text.split('.')[0][:50]

        id = self.memory.store_knowledge(category, subject, text)
        return f"✅ Stored as knowledge #{id} in category '{category}'"

    def _cmd_recall(self, args: List[str], chat_id: str) -> str:
        """Search memory"""
        query = " ".join(args)
        results = self.memory.search_knowledge(query, limit=5)

        if not results:
            return f"🔍 No results found for '{query}'"

        output = [f"🔍 **Found {len(results)} results for '{query}':**\n"]
        for i, r in enumerate(results, 1):
            output.append(f"**{i}. [{r['category']}] {r['subject']}**")
            output.append(f"   {r['knowledge'][:150]}...")
            output.append(f"   _Confidence: {r['confidence']:.1f}, Accessed: {r['access_count']} times_\n")

        return "\n".join(output)

    def _cmd_insights(self, args: List[str], chat_id: str) -> str:
        """Show recent insights"""
        insights = self.memory.get_recent_insights(limit=10)

        if not insights:
            return "💡 No recent insights"

        output = ["💡 **Recent Insights:**\n"]
        for ins in insights:
            age = self._human_time_ago(ins['created_at'])
            output.append(f"**[{ins['insight_type']}] {ins['title']}**")
            output.append(f"   {ins['description'][:200]}")
            output.append(f"   _{age}_\n")

        return "\n".join(output)

    def _cmd_note_insight(self, args: List[str], chat_id: str) -> str:
        """Record an insight"""
        # Format: /note-insight <type> <title> | <description>
        text = " ".join(args)
        if '|' not in text:
            return "⚠️ Usage: /note-insight <type> <title> | <description>"

        parts = text.split('|', 1)
        header = parts[0].strip().split(None, 1)

        if len(header) < 2:
            return "⚠️ Usage: /note-insight <type> <title> | <description>"

        insight_type = header[0]
        title = header[1]
        description = parts[1].strip()

        id = self.memory.remember_insight(insight_type, title, description, ttl_hours=72)
        return f"✅ Insight #{id} recorded (expires in 72 hours)"

    def _cmd_actions(self, args: List[str], chat_id: str) -> str:
        """Show pending actions"""
        actions = self.memory.get_pending_actions()

        if not actions:
            return "✅ No pending actions"

        output = ["📋 **Pending Actions:**\n"]
        for act in actions:
            priority_icon = "🔴" if act['priority'] <= 3 else "🟡" if act['priority'] <= 5 else "🟢"
            due_text = f" (due: {act['due_date'][:10]})" if act['due_date'] else ""
            output.append(f"{priority_icon} **P{act['priority']}** {act['action_text']}{due_text}")

        return "\n".join(output)

    def _cmd_todo(self, args: List[str], chat_id: str) -> str:
        """Add a pending action"""
        if len(args) < 2:
            return "⚠️ Usage: /todo <priority 1-10> <text>"

        try:
            priority = int(args[0])
            text = " ".join(args[1:])
        except ValueError:
            return "⚠️ Priority must be a number (1-10)"

        id = self.memory.add_pending_action("manual", text, priority=priority)
        return f"✅ Action #{id} added with priority {priority}"

    def _cmd_projects(self, args: List[str], chat_id: str) -> str:
        """List all projects"""
        # This requires a custom query since we want all projects
        with self.memory.get_connection() as conn:
            rows = conn.execute('''
                SELECT project_name, project_type, activity_count, updated_at
                FROM project_memory
                ORDER BY updated_at DESC
            ''').fetchall()

        if not rows:
            return "📦 No projects tracked yet"

        output = ["📦 **Tracked Projects:**\n"]
        for row in rows:
            age = self._human_time_ago(row['updated_at'])
            output.append(f"**{row['project_name']}** ({row['project_type']})")
            output.append(f"   {row['activity_count']} activities, updated {age}\n")

        return "\n".join(output)

    def _cmd_project(self, args: List[str], chat_id: str) -> str:
        """Show project details"""
        project_name = " ".join(args)
        project = self.memory.get_project_memory(project_name)

        if not project:
            return f"❓ Project '{project_name}' not found"

        output = [f"📦 **Project: {project['project_name']}**\n"]
        output.append(f"**Type:** {project['project_type']}")
        output.append(f"**Description:** {project['description']}")

        if project.get('key_files'):
            output.append(f"\n**Key files:**")
            for file in project['key_files'][:10]:
                output.append(f"  • {file}")

        output.append(f"\n**Last activity:** {project['last_activity']}")
        output.append(f"**Activity count:** {project['activity_count']}")
        output.append(f"**Created:** {project['created_at'][:10]}")

        return "\n".join(output)

    def _cmd_system_info(self, args: List[str], chat_id: str) -> str:
        """Search system knowledge"""
        component = args[0] if args else None
        results = self.memory.search_system_knowledge(component=component)

        if not results:
            query = f" for '{component}'" if component else ""
            return f"🔍 No system knowledge found{query}"

        output = [f"🖥️ **System Knowledge:**\n"]
        for r in results:
            output.append(f"**[{r['system_component']}] {r['knowledge_type']}**")
            output.append(f"   {r['content'][:200]}...")
            if r.get('file_paths'):
                output.append(f"   Files: {', '.join(r['file_paths'][:3])}")
            output.append("")

        return "\n".join(output)

    def _cmd_session_history(self, args: List[str], chat_id: str) -> str:
        """Show session summary history"""
        # Get current session ID from chat
        # This would need to be passed in or looked up from the main bridge
        # For now, show all recent summaries
        with self.memory.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM conversation_summaries
                ORDER BY summary_date DESC
                LIMIT 7
            ''').fetchall()

        if not rows:
            return "📅 No conversation summaries yet"

        output = ["📅 **Recent Session Summaries:**\n"]
        for row in rows:
            topics = json.loads(row['key_topics']) if row['key_topics'] else []
            output.append(f"**{row['summary_date']}** ({row['message_count']} messages)")
            output.append(f"   Topics: {', '.join(topics)}")
            output.append(f"   {row['summary_text'][:150]}...\n")

        return "\n".join(output)

    def _cmd_memory_cleanup(self, args: List[str], chat_id: str) -> str:
        """Clean up expired memory"""
        count = self.memory.cleanup_expired_insights()
        self.memory.vacuum_database()
        return f"🧹 Cleaned up {count} expired insights and optimized database"

    def _cmd_search_all(self, args: List[str], chat_id: str) -> str:
        """Search across all memory types"""
        query = " ".join(args)

        output = [f"🔍 **Global search for '{query}':**\n"]

        # Search knowledge base
        knowledge = self.memory.search_knowledge(query, limit=3)
        if knowledge:
            output.append("**Knowledge base:**")
            for k in knowledge:
                output.append(f"  • [{k['category']}] {k['subject']}")

        # Search insights
        with self.memory.get_connection() as conn:
            insights = conn.execute('''
                SELECT * FROM recent_insights
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY created_at DESC LIMIT 3
            ''', (f'%{query}%', f'%{query}%')).fetchall()

        if insights:
            output.append("\n**Recent insights:**")
            for ins in insights:
                output.append(f"  • [{ins['insight_type']}] {ins['title']}")

        # Search system knowledge
        with self.memory.get_connection() as conn:
            system = conn.execute('''
                SELECT * FROM system_knowledge
                WHERE content LIKE ?
                LIMIT 3
            ''', (f'%{query}%',)).fetchall()

        if system:
            output.append("\n**System knowledge:**")
            for s in system:
                output.append(f"  • [{s['system_component']}] {s['knowledge_type']}")

        if len(output) == 1:
            return f"🔍 No results found for '{query}'"

        return "\n".join(output)

    # ============================================================
    # AUTO-LEARNING HOOKS
    # ============================================================

    def on_message_processed(self, user_text: str, assistant_text: str,
                            chat_id: str, session_id: str):
        """
        Called after each message is processed
        Use this to automatically extract and store insights
        """
        # Extract patterns
        self._extract_command_patterns(user_text)
        self._extract_system_mentions(user_text, assistant_text)
        self._extract_project_references(user_text, assistant_text)

    def _extract_command_patterns(self, user_text: str):
        """Learn from user commands"""
        # Look for bash commands, file paths, etc.
        # This is a simple example - can be much more sophisticated
        pass

    def _extract_system_mentions(self, user_text: str, assistant_text: str):
        """Extract system component mentions"""
        # Look for mentions of system components
        components = ['nginx', 'exim4', 'systemd', 'docker', 'postgres', 'sqlite']

        for component in components:
            if component.lower() in user_text.lower() or component.lower() in assistant_text.lower():
                # Could auto-update system knowledge here
                pass

    def _extract_project_references(self, user_text: str, assistant_text: str):
        """Extract project references"""
        # Look for project names, file paths, etc.
        # Could auto-update project memory
        pass

    # ============================================================
    # UTILITIES
    # ============================================================

    def _human_time_ago(self, timestamp: str) -> str:
        """Convert timestamp to human-readable relative time"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now()
            if dt.tzinfo:
                import pytz
                now = datetime.now(pytz.UTC)

            delta = now - dt

            if delta.days > 7:
                return f"{delta.days // 7} weeks ago"
            elif delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return "just now"
        except:
            return timestamp[:10]


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_plugin_manager = None


def get_plugin_manager() -> EchoPluginManager:
    """Get or create the global plugin manager"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = EchoPluginManager()
    return _plugin_manager


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    import sys

    manager = get_plugin_manager()

    if len(sys.argv) < 2:
        print(manager.get_help_text())
        sys.exit(0)

    command = sys.argv[1].lstrip('/')
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    result = manager.execute_command(command, args, "test")
    print(result)
