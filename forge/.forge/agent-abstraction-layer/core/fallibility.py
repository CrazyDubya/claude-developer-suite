"""
Fallibility handling for the Agent Abstraction Layer.

AI agents make mistakes. This module provides patterns for
error classification, recovery, graceful degradation, and
human-in-the-loop integration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import time


class ErrorSeverity(Enum):
    """How severe is the error?"""
    RECOVERABLE = "recoverable"  # Can retry or work around
    DEGRADABLE = "degradable"  # Can continue with reduced capability
    FATAL = "fatal"  # Must stop


class RecoveryAction(Enum):
    """What to do when an error occurs."""
    RETRY = "retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    SUMMARIZE_AND_RETRY = "summarize_and_retry"
    PROCEED_WITHOUT = "proceed_without"
    PROVIDE_ALTERNATIVES = "provide_alternatives"
    HALT_AND_NOTIFY = "halt_and_notify"
    HALT_AND_LOG = "halt_and_log"
    ASK_HUMAN = "ask_human"


@dataclass
class ErrorClassification:
    """
    Classification of an error for appropriate handling.

    Unlike traditional exceptions, agent errors need richer
    classification because recovery strategies vary widely.
    """
    error_type: str
    severity: ErrorSeverity
    recovery_action: RecoveryAction
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # For retry logic
    max_retries: int = 3
    current_retry: int = 0
    retry_delay_ms: int = 1000

    # For degradation
    can_proceed_without: bool = False
    fallback_behavior: Optional[str] = None

    @classmethod
    def rate_limit(cls, retry_after_ms: int = 1000) -> "ErrorClassification":
        """Create a rate limit error classification."""
        return cls(
            error_type="rate_limit",
            severity=ErrorSeverity.RECOVERABLE,
            recovery_action=RecoveryAction.EXPONENTIAL_BACKOFF,
            message="Rate limit exceeded",
            retry_delay_ms=retry_after_ms,
            max_retries=5,
        )

    @classmethod
    def timeout(cls) -> "ErrorClassification":
        """Create a timeout error classification."""
        return cls(
            error_type="timeout",
            severity=ErrorSeverity.RECOVERABLE,
            recovery_action=RecoveryAction.RETRY,
            message="Request timed out",
            max_retries=3,
        )

    @classmethod
    def context_overflow(cls) -> "ErrorClassification":
        """Create a context overflow error classification."""
        return cls(
            error_type="context_overflow",
            severity=ErrorSeverity.RECOVERABLE,
            recovery_action=RecoveryAction.SUMMARIZE_AND_RETRY,
            message="Context window exceeded",
            max_retries=2,
        )

    @classmethod
    def tool_failure(cls, tool_name: str) -> "ErrorClassification":
        """Create a tool failure error classification."""
        return cls(
            error_type="tool_failure",
            severity=ErrorSeverity.DEGRADABLE,
            recovery_action=RecoveryAction.PROCEED_WITHOUT,
            message=f"Tool '{tool_name}' failed",
            can_proceed_without=True,
            details={"tool_name": tool_name},
        )

    @classmethod
    def low_confidence(cls, confidence: float) -> "ErrorClassification":
        """Create a low confidence error classification."""
        return cls(
            error_type="low_confidence",
            severity=ErrorSeverity.DEGRADABLE,
            recovery_action=RecoveryAction.PROVIDE_ALTERNATIVES,
            message=f"Low confidence output ({confidence:.2f})",
            details={"confidence": confidence},
        )

    @classmethod
    def auth_failure(cls) -> "ErrorClassification":
        """Create an authentication failure classification."""
        return cls(
            error_type="auth_failure",
            severity=ErrorSeverity.FATAL,
            recovery_action=RecoveryAction.HALT_AND_NOTIFY,
            message="Authentication failed",
        )

    @classmethod
    def safety_violation(cls, reason: str) -> "ErrorClassification":
        """Create a safety violation classification."""
        return cls(
            error_type="safety_violation",
            severity=ErrorSeverity.FATAL,
            recovery_action=RecoveryAction.HALT_AND_LOG,
            message=f"Safety violation: {reason}",
            details={"reason": reason},
        )

    def should_retry(self) -> bool:
        """Check if we should attempt a retry."""
        if self.severity == ErrorSeverity.FATAL:
            return False
        return self.current_retry < self.max_retries

    def get_retry_delay_ms(self) -> int:
        """Get the delay before next retry (with exponential backoff)."""
        if self.recovery_action == RecoveryAction.EXPONENTIAL_BACKOFF:
            return self.retry_delay_ms * (2 ** self.current_retry)
        return self.retry_delay_ms


@dataclass
class RecoveryStrategy:
    """
    A strategy for recovering from errors.

    Encapsulates the logic for handling specific error types.
    """
    error_type: str
    handler: Callable[["ErrorClassification", Any], Any]
    max_attempts: int = 3
    timeout_ms: int = 30000

    def execute(
        self,
        error: ErrorClassification,
        context: Any,
    ) -> Any:
        """Execute the recovery strategy."""
        return self.handler(error, context)


class RecoveryExecutor:
    """
    Executes recovery strategies for errors.

    Handles the retry logic, backoff, and strategy selection.
    """

    def __init__(self):
        self.strategies: Dict[str, RecoveryStrategy] = {}

    def register_strategy(self, strategy: RecoveryStrategy) -> None:
        """Register a recovery strategy for an error type."""
        self.strategies[strategy.error_type] = strategy

    def attempt_recovery(
        self,
        error: ErrorClassification,
        context: Any,
        on_retry: Optional[Callable[[], Any]] = None,
    ) -> Optional[Any]:
        """
        Attempt to recover from an error.

        Args:
            error: The classified error
            context: Current execution context
            on_retry: Function to call for retry attempts

        Returns:
            Recovery result or None if recovery failed
        """
        # Check if we have a strategy
        strategy = self.strategies.get(error.error_type)

        while error.should_retry():
            error.current_retry += 1

            # Apply delay
            delay_ms = error.get_retry_delay_ms()
            time.sleep(delay_ms / 1000.0)

            try:
                if strategy:
                    return strategy.execute(error, context)
                elif on_retry:
                    return on_retry()
            except Exception:
                continue

        return None


@dataclass
class DegradationLevel:
    """A level in the degradation ladder."""
    name: str
    description: str
    capabilities_available: List[str]
    capabilities_disabled: List[str] = field(default_factory=list)
    tools_enabled: bool = True
    use_cache: bool = False
    escalate_to_human: bool = False


class DegradationLadder:
    """
    Manages graceful degradation when things go wrong.

    Rather than failing completely, we descend through levels
    of reduced capability until we find something that works.
    """

    def __init__(self):
        self.levels: List[DegradationLevel] = []
        self.current_level_index: int = 0
        self._setup_default_levels()

    def _setup_default_levels(self) -> None:
        """Setup the default degradation ladder."""
        self.levels = [
            DegradationLevel(
                name="full_capability",
                description="All tools and features available",
                capabilities_available=["tools", "memory", "search", "code_execute"],
            ),
            DegradationLevel(
                name="reduced_tools",
                description="Proceed with subset of tools",
                capabilities_available=["tools", "memory"],
                capabilities_disabled=["search", "code_execute"],
            ),
            DegradationLevel(
                name="conversation_only",
                description="No tool use, conversation only",
                capabilities_available=["memory"],
                capabilities_disabled=["tools", "search", "code_execute"],
                tools_enabled=False,
            ),
            DegradationLevel(
                name="cached_responses",
                description="Return cached/pre-computed responses",
                capabilities_available=[],
                capabilities_disabled=["tools", "memory", "search", "code_execute"],
                tools_enabled=False,
                use_cache=True,
            ),
            DegradationLevel(
                name="human_handoff",
                description="Escalate to human operator",
                capabilities_available=[],
                capabilities_disabled=["tools", "memory", "search", "code_execute"],
                tools_enabled=False,
                escalate_to_human=True,
            ),
        ]

    def get_current_level(self) -> DegradationLevel:
        """Get the current degradation level."""
        return self.levels[self.current_level_index]

    def descend(self) -> Optional[DegradationLevel]:
        """
        Descend to the next degradation level.

        Returns the new level, or None if at bottom.
        """
        if self.current_level_index < len(self.levels) - 1:
            self.current_level_index += 1
            return self.levels[self.current_level_index]
        return None

    def reset(self) -> DegradationLevel:
        """Reset to full capability level."""
        self.current_level_index = 0
        return self.levels[0]

    def is_at_human_handoff(self) -> bool:
        """Check if we've descended to human handoff."""
        return self.get_current_level().escalate_to_human

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if a tool can be used at current degradation level."""
        level = self.get_current_level()
        if not level.tools_enabled:
            return False
        if tool_name in level.capabilities_disabled:
            return False
        return True


class EscalationChannel(Enum):
    """Channels for human escalation."""
    CLI_PROMPT = "cli_prompt"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class EscalationRequest:
    """A request for human intervention."""
    id: str
    reason: str
    context: str
    options: List[str]
    timeout_seconds: int
    default_on_timeout: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass
class HumanLoopConfig:
    """Configuration for human-in-the-loop integration."""
    # When to escalate
    confidence_threshold: float = 0.4
    cost_threshold_usd: float = 0.50
    sensitive_actions: List[str] = field(default_factory=list)

    # How to escalate
    interface_type: str = "async_approval"  # "sync_block" | "async_approval" | "log_only"
    timeout_seconds: int = 300
    default_on_timeout: str = "deny"

    # Channels
    channels: List[EscalationChannel] = field(
        default_factory=lambda: [EscalationChannel.CLI_PROMPT]
    )


class HumanLoop:
    """
    Manages human-in-the-loop escalation.

    When agents encounter situations beyond their confidence
    or permission, they escalate to humans.
    """

    def __init__(self, config: HumanLoopConfig):
        self.config = config
        self.pending_requests: Dict[str, EscalationRequest] = {}
        self.request_handlers: Dict[EscalationChannel, Callable] = {}

    def register_handler(
        self,
        channel: EscalationChannel,
        handler: Callable[[EscalationRequest], Optional[str]],
    ) -> None:
        """Register a handler for an escalation channel."""
        self.request_handlers[channel] = handler

    def should_escalate(
        self,
        confidence: float,
        cost_usd: float,
        action: str,
    ) -> bool:
        """Check if the current situation requires human escalation."""
        if confidence < self.config.confidence_threshold:
            return True
        if cost_usd > self.config.cost_threshold_usd:
            return True
        if action in self.config.sensitive_actions:
            return True
        return False

    def escalate(
        self,
        reason: str,
        context: str,
        options: List[str],
    ) -> EscalationRequest:
        """
        Create an escalation request.

        Args:
            reason: Why we're escalating
            context: Current situation description
            options: Possible choices for the human

        Returns:
            The escalation request
        """
        import hashlib

        request_id = hashlib.sha256(
            f"{reason}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        request = EscalationRequest(
            id=request_id,
            reason=reason,
            context=context,
            options=options,
            timeout_seconds=self.config.timeout_seconds,
            default_on_timeout=self.config.default_on_timeout,
        )

        self.pending_requests[request_id] = request
        return request

    def wait_for_resolution(
        self,
        request: EscalationRequest,
    ) -> str:
        """
        Wait for human resolution of an escalation.

        Returns the chosen option or default on timeout.
        """
        if self.config.interface_type == "log_only":
            # Just log and proceed with default
            return self.config.default_on_timeout

        # Try each configured channel
        for channel in self.config.channels:
            handler = self.request_handlers.get(channel)
            if handler:
                try:
                    resolution = handler(request)
                    if resolution:
                        request.resolved = True
                        request.resolution = resolution
                        request.resolved_at = datetime.utcnow()
                        return resolution
                except Exception:
                    continue

        # Timeout or no handler succeeded
        return self.config.default_on_timeout

    def resolve(
        self,
        request_id: str,
        resolution: str,
        resolved_by: str = "human",
    ) -> bool:
        """Manually resolve an escalation request."""
        request = self.pending_requests.get(request_id)
        if request and not request.resolved:
            request.resolved = True
            request.resolution = resolution
            request.resolved_by = resolved_by
            request.resolved_at = datetime.utcnow()
            return True
        return False


@dataclass
class RetryContext:
    """Context for a retry attempt."""
    attempt: int
    max_attempts: int
    error: ErrorClassification
    delay_ms: int
    cumulative_delay_ms: int = 0


class RetryPolicy:
    """
    Configurable retry policy with various strategies.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_ms: int = 1000,
        max_delay_ms: int = 60000,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> int:
        """Calculate delay for a given attempt."""
        import random

        delay = self.base_delay_ms * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay_ms)

        if self.jitter:
            # Add up to 25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return int(delay)

    def should_retry(self, attempt: int, error: ErrorClassification) -> bool:
        """Check if we should retry given current state."""
        if error.severity == ErrorSeverity.FATAL:
            return False
        return attempt < self.max_attempts

    def execute_with_retry(
        self,
        operation: Callable[[], Any],
        classify_error: Callable[[Exception], ErrorClassification],
    ) -> Any:
        """
        Execute an operation with retry logic.

        Args:
            operation: The operation to execute
            classify_error: Function to classify exceptions

        Returns:
            The operation result

        Raises:
            The last exception if all retries exhausted
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
            except Exception as e:
                last_error = e
                classification = classify_error(e)

                if not self.should_retry(attempt, classification):
                    raise

                delay = self.get_delay(attempt)
                time.sleep(delay / 1000.0)

        if last_error:
            raise last_error
