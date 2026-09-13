#!/usr/bin/env python3
"""
Bridge Integration Module
Connects Echo's memory skills to the Telegram Bridge
"""

import sys
from pathlib import Path

# Add skills directory to path
SKILLS_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILLS_DIR))

from echo_plugins import get_plugin_manager
from memory_interface import EchoMemory


class MemoryEnabledBridge:
    """
    Mixin class to add memory capabilities to TelegramBridge

    Usage:
    Instead of modifying claude-telegram-bridge-v6.py directly,
    this provides extension points that can be imported and used
    """

    def __init__(self):
        self.plugin_manager = get_plugin_manager()
        self.echo_memory = EchoMemory()

    def handle_memory_command(self, chat_id: str, command: str, args: list) -> tuple[bool, str]:
        """
        Handle memory-related commands

        Returns:
            (handled: bool, response: str)
            - handled: True if this was a memory command
            - response: The response text to send
        """
        # Check if this is a registered plugin command
        cmd_name = command.lstrip('/')

        if cmd_name in self.plugin_manager.commands:
            response = self.plugin_manager.execute_command(cmd_name, args, chat_id)
            return (True, response)

        return (False, "")

    def on_message_complete(self, user_text: str, assistant_text: str,
                           chat_id: str, session_id: str):
        """
        Hook called after message processing
        Use for auto-learning and memory updates
        """
        # Let plugins learn from this interaction
        self.plugin_manager.on_message_processed(
            user_text, assistant_text, chat_id, session_id
        )

        # Auto-extract insights if assistant mentions something important
        self._auto_extract_insights(user_text, assistant_text, session_id)

    def _auto_extract_insights(self, user_text: str, assistant_text: str, session_id: str):
        """Automatically extract insights from conversation"""
        # Look for error patterns
        if "error" in assistant_text.lower() or "failed" in assistant_text.lower():
            # Could auto-record this as an insight
            pass

        # Look for solutions
        if "✅" in assistant_text and ("fixed" in assistant_text.lower() or "solved" in assistant_text.lower()):
            # Could auto-record successful solutions
            pass

        # Look for system discoveries
        if "discovered" in assistant_text.lower() or "found" in assistant_text.lower():
            # Could auto-update system knowledge
            pass

    def enhance_system_prompt(self, base_prompt: str, session_id: str) -> str:
        """
        Enhance system prompt with relevant memory context

        This adds relevant knowledge, insights, and project context
        to the system prompt automatically
        """
        enhancements = []

        # Add recent insights
        insights = self.echo_memory.get_recent_insights(limit=3)
        if insights:
            enhancements.append("\n=== RECENT INSIGHTS ===")
            for ins in insights:
                enhancements.append(f"• [{ins['insight_type']}] {ins['title']}: {ins['description'][:100]}")

        # Add pending actions
        actions = self.echo_memory.get_pending_actions()
        if actions:
            enhancements.append("\n=== PENDING ACTIONS ===")
            for act in actions[:5]:
                priority_label = "HIGH" if act['priority'] <= 3 else "NORMAL"
                enhancements.append(f"• [{priority_label}] {act['action_text']}")

        # Add active context (if any)
        context = self.echo_memory.get_active_context("current_task")
        if context:
            enhancements.append("\n=== ACTIVE TASK CONTEXT ===")
            enhancements.append(f"Task: {context.get('description', 'Unknown')}")

        if enhancements:
            return base_prompt + "\n" + "\n".join(enhancements) + "\n"
        else:
            return base_prompt

    def get_memory_help_text(self) -> str:
        """Get help text for memory commands"""
        return self.plugin_manager.get_help_text()


def integrate_memory_to_bridge(bridge_instance):
    """
    Monkey-patch an existing TelegramBridge instance with memory capabilities

    Usage in claude-telegram-bridge-v6.py:
        from skills.bridge_integration import integrate_memory_to_bridge
        bridge = TelegramBridge(config)
        integrate_memory_to_bridge(bridge)
    """
    # Add memory components
    bridge_instance._memory_bridge = MemoryEnabledBridge()

    # Wrap the handle_command method
    original_handle_command = bridge_instance.handle_command

    def enhanced_handle_command(chat_id: str, command: str):
        """Enhanced command handler with memory support"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Try memory commands first
        handled, response = bridge_instance._memory_bridge.handle_memory_command(chat_id, cmd, args)
        if handled:
            bridge_instance.telegram.send_message(chat_id, response)
            return

        # Fall back to original handler
        original_handle_command(chat_id, command)

    bridge_instance.handle_command = enhanced_handle_command

    # Wrap the build_system_prompt method
    original_build_system_prompt = bridge_instance.build_system_prompt

    def enhanced_build_system_prompt(chat_id: str, include_context: bool = True) -> str:
        """Enhanced system prompt with memory context"""
        base_prompt = original_build_system_prompt(chat_id, include_context)
        session = bridge_instance.get_or_create_session(chat_id)
        return bridge_instance._memory_bridge.enhance_system_prompt(base_prompt, session.session_id)

    bridge_instance.build_system_prompt = enhanced_build_system_prompt

    # Wrap message handling for auto-learning
    original_handle_message = bridge_instance.handle_message

    def enhanced_handle_message(update: dict):
        """Enhanced message handler with memory learning"""
        # Call original handler
        original_handle_message(update)

        # Extract message data for learning
        message = update.get('message', {})
        text = message.get('text', '') or message.get('caption', '')
        chat_id = str(message.get('chat', {}).get('id', ''))

        if text and chat_id == bridge_instance.config.allowed_chat_id:
            session = bridge_instance.get_or_create_session(chat_id)

            # Get the last assistant response from context
            if session.context:
                last_exchange = session.context[-1]
                bridge_instance._memory_bridge.on_message_complete(
                    text,
                    last_exchange.get('assistant', ''),
                    chat_id,
                    session.session_id
                )

    bridge_instance.handle_message = enhanced_handle_message

    print("✅ Memory system integrated into bridge")


# ============================================================
# HELPER FUNCTION FOR QUICK INTEGRATION
# ============================================================

def create_memory_commands_list() -> str:
    """
    Generate a list of memory commands to add to /help
    """
    manager = get_plugin_manager()
    return manager.get_help_text()


if __name__ == "__main__":
    print("🧠 Bridge Integration Module")
    print("\nTo integrate memory into the bridge:")
    print("\n1. Import in claude-telegram-bridge-v6.py:")
    print("   from skills.bridge_integration import integrate_memory_to_bridge")
    print("\n2. After creating bridge instance:")
    print("   bridge = TelegramBridge(config)")
    print("   integrate_memory_to_bridge(bridge)")
    print("\n3. Update /help command to include:")
    print("   from skills.bridge_integration import create_memory_commands_list")
    print("   help_text += create_memory_commands_list()")
    print("\n" + "="*60)
    print("\nAvailable memory commands:")
    print(create_memory_commands_list())
