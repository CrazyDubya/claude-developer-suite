"""
Echo Skills Package
Provides memory and learning capabilities for the Telegram Bridge
"""

__version__ = "1.0.0"
__all__ = ["EchoMemory", "get_plugin_manager", "integrate_memory_to_bridge"]

from .memory_interface import EchoMemory
from .echo_plugins import get_plugin_manager
from .bridge_integration import integrate_memory_to_bridge
