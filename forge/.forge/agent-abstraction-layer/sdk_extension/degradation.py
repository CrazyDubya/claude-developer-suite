"""
Graceful Degradation for AAL.

When things go wrong, don't fail completely - degrade gracefully
through levels of reduced capability.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DegradationLevel(Enum):
    """Levels of capability degradation."""
    FULL = "full"  # All capabilities available
    REDUCED_TOOLS = "reduced_tools"  # Limited tool access
    CONVERSATION_ONLY = "conversation_only"  # No tools
    CACHED = "cached"  # Pre-computed responses only
    HUMAN_HANDOFF = "human_handoff"  # Escalate to human


@dataclass
class LevelConfig:
    """Configuration for a degradation level."""
    level: DegradationLevel
    description: str
    tools_enabled: bool = True
    allowed_tools: List[str] = field(default_factory=list)
    disabled_tools: List[str] = field(default_factory=list)
    use_cache: bool = False
    escalate: bool = False


class DegradationManager:
    """
    Manages graceful degradation when errors occur.

    Rather than failing completely, we descend through levels
    of reduced capability until something works.
    """

    def __init__(self):
        self.levels = self._default_levels()
        self.current_index = 0
        self.descent_history: List[Dict[str, Any]] = []

    def _default_levels(self) -> List[LevelConfig]:
        """Default degradation ladder."""
        return [
            LevelConfig(
                level=DegradationLevel.FULL,
                description="All tools and capabilities available",
                tools_enabled=True,
            ),
            LevelConfig(
                level=DegradationLevel.REDUCED_TOOLS,
                description="Safe tools only, no Bash or external calls",
                tools_enabled=True,
                allowed_tools=["Read", "Grep", "Glob", "Edit", "Write"],
                disabled_tools=["Bash", "WebSearch", "WebFetch", "Task"],
            ),
            LevelConfig(
                level=DegradationLevel.CONVERSATION_ONLY,
                description="No tool use, conversation only",
                tools_enabled=False,
            ),
            LevelConfig(
                level=DegradationLevel.CACHED,
                description="Return cached or pre-computed responses",
                tools_enabled=False,
                use_cache=True,
            ),
            LevelConfig(
                level=DegradationLevel.HUMAN_HANDOFF,
                description="Escalate to human operator",
                tools_enabled=False,
                escalate=True,
            ),
        ]

    @property
    def current_level(self) -> DegradationLevel:
        """Get current degradation level."""
        return self.levels[self.current_index].level

    @property
    def current_config(self) -> LevelConfig:
        """Get current level configuration."""
        return self.levels[self.current_index]

    def descend(self, reason: str = "") -> DegradationLevel:
        """
        Descend to the next degradation level.

        Returns the new level.
        """
        if self.current_index < len(self.levels) - 1:
            self.descent_history.append({
                "from": self.current_level.value,
                "reason": reason,
            })
            self.current_index += 1

        return self.current_level

    def reset(self) -> DegradationLevel:
        """Reset to full capability."""
        self.current_index = 0
        return self.current_level

    def get_restrictions(self) -> Dict[str, Any]:
        """Get current restrictions for SDK configuration."""
        config = self.current_config

        return {
            "tools_enabled": config.tools_enabled,
            "allowed_tools": config.allowed_tools if config.allowed_tools else None,
            "disabled_tools": config.disabled_tools,
            "use_cache": config.use_cache,
            "needs_human": config.escalate,
        }

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed at current level."""
        config = self.current_config

        if not config.tools_enabled:
            return False

        if config.allowed_tools and tool_name not in config.allowed_tools:
            return False

        if tool_name in config.disabled_tools:
            return False

        return True

    def at_bottom(self) -> bool:
        """Are we at the bottom of the ladder?"""
        return self.current_index >= len(self.levels) - 1

    def needs_human(self) -> bool:
        """Do we need human intervention?"""
        return self.current_config.escalate

    def get_status(self) -> Dict[str, Any]:
        """Get current degradation status."""
        return {
            "current_level": self.current_level.value,
            "level_index": self.current_index,
            "total_levels": len(self.levels),
            "description": self.current_config.description,
            "descent_count": len(self.descent_history),
            "at_bottom": self.at_bottom(),
            "needs_human": self.needs_human(),
        }


class ErrorClassifier:
    """
    Classifies errors to determine degradation strategy.
    """

    # Errors that should trigger degradation
    DEGRADABLE_ERRORS = {
        "rate_limit": DegradationLevel.REDUCED_TOOLS,
        "timeout": DegradationLevel.REDUCED_TOOLS,
        "tool_failure": DegradationLevel.REDUCED_TOOLS,
        "context_overflow": DegradationLevel.CONVERSATION_ONLY,
        "network_error": DegradationLevel.CACHED,
    }

    # Errors that should NOT degrade (just retry or fail)
    NON_DEGRADABLE = [
        "auth_failure",
        "invalid_request",
        "safety_violation",
    ]

    @classmethod
    def classify(cls, error: Exception) -> Optional[DegradationLevel]:
        """
        Classify an error and suggest degradation level.

        Returns None if error should not trigger degradation.
        """
        error_str = str(error).lower()

        # Check non-degradable first
        for pattern in cls.NON_DEGRADABLE:
            if pattern in error_str:
                return None

        # Check degradable patterns
        for pattern, level in cls.DEGRADABLE_ERRORS.items():
            if pattern.replace("_", " ") in error_str:
                return level

        # Default: try reducing tools
        return DegradationLevel.REDUCED_TOOLS

    @classmethod
    def should_retry(cls, error: Exception) -> bool:
        """Should we retry this error?"""
        error_str = str(error).lower()

        retryable = ["rate_limit", "timeout", "temporary", "retry"]
        return any(r in error_str for r in retryable)
