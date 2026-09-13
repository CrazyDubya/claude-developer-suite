"""
Core primitives for the Agent Abstraction Layer.

These are the fundamental building blocks for working with AI agents
as first-class entities distinct from deterministic code.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import hashlib
import json


class MemoryStrategy(Enum):
    """How to manage conversation/context memory."""
    FULL = "full"  # Keep everything (may hit token limits)
    SLIDING_WINDOW = "sliding_window"  # Keep last N messages
    SUMMARIZED = "summarized"  # Compress old messages


class PermissionLevel(Enum):
    """Tool/action permission levels."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class BehavioralFingerprint:
    """
    A fingerprint of expected agent behavior for drift detection.

    Unlike code which has a hash of its source, agents have behavioral
    fingerprints that describe their expected statistical properties.
    """
    expected_latency_p50_ms: float
    expected_latency_p95_ms: float
    expected_token_ratio: float  # output_tokens / input_tokens
    typical_tool_usage: Dict[str, float]  # tool_name -> frequency
    response_length_distribution: Dict[str, float]  # bucket -> frequency
    behavioral_hash: str  # Hash of the fingerprint itself

    @classmethod
    def create(
        cls,
        latency_p50: float,
        latency_p95: float,
        token_ratio: float,
        tool_usage: Dict[str, float],
        response_lengths: Dict[str, float],
    ) -> "BehavioralFingerprint":
        """Create a fingerprint and compute its hash."""
        data = {
            "latency_p50": latency_p50,
            "latency_p95": latency_p95,
            "token_ratio": token_ratio,
            "tool_usage": tool_usage,
            "response_lengths": response_lengths,
        }
        hash_value = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

        return cls(
            expected_latency_p50_ms=latency_p50,
            expected_latency_p95_ms=latency_p95,
            expected_token_ratio=token_ratio,
            typical_tool_usage=tool_usage,
            response_length_distribution=response_lengths,
            behavioral_hash=f"sha256:{hash_value[:16]}",
        )


@dataclass
class AgentEntity:
    """
    The fundamental unit of the AAL.

    An AgentEntity is not a function or a class—it's an entity with:
    - Identity (id, version)
    - Behavioral expectations (fingerprint)
    - Uncertainty bounds
    - Lifecycle management
    """
    id: str
    version: str
    model: str
    fingerprint: Optional[BehavioralFingerprint] = None

    # Uncertainty configuration
    confidence_threshold: float = 0.7
    max_retries_on_low_confidence: int = 3
    fallback_agent_id: Optional[str] = None

    # Lifecycle
    cold_start_warmup: bool = True
    max_concurrent_instances: int = 5
    graceful_shutdown_timeout_ms: int = 5000

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_invoked_at: Optional[datetime] = None
    invocation_count: int = 0

    def get_qualified_id(self) -> str:
        """Return fully qualified agent identifier."""
        return f"{self.id}@{self.version}"

    def is_fallback_available(self) -> bool:
        """Check if a fallback agent is configured."""
        return self.fallback_agent_id is not None

    def record_invocation(self) -> None:
        """Record that this agent was invoked."""
        self.last_invoked_at = datetime.utcnow()
        self.invocation_count += 1


@dataclass
class ContextInjection:
    """A piece of context to inject into the agent."""
    type: str  # "system_prompt" | "few_shot" | "dynamic"
    source: str  # File path or hook name
    content: Optional[str] = None  # Resolved content


@dataclass
class AgentContext:
    """
    The execution environment for an agent.

    Manages what the agent knows and operates within, including:
    - Conversation history
    - Working memory (ephemeral)
    - Long-term memory (persisted)
    - Injected context
    """
    # Conversation management
    history_strategy: MemoryStrategy = MemoryStrategy.SLIDING_WINDOW
    max_messages: int = 50
    summary_trigger_at: int = 40
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # Working memory (session-scoped)
    working_memory: Dict[str, Any] = field(default_factory=dict)
    working_memory_max_items: int = 20
    working_memory_ttl_seconds: int = 3600

    # Context injections
    injections: List[ContextInjection] = field(default_factory=list)

    # Resolved system prompt
    system_prompt: str = ""

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._apply_strategy()

    def _apply_strategy(self) -> None:
        """Apply the configured memory strategy."""
        if self.history_strategy == MemoryStrategy.SLIDING_WINDOW:
            if len(self.messages) > self.max_messages:
                self.messages = self.messages[-self.max_messages:]
        elif self.history_strategy == MemoryStrategy.SUMMARIZED:
            if len(self.messages) >= self.summary_trigger_at:
                # Placeholder: actual summarization would use the model
                pass

    def get_messages_for_api(self) -> List[Dict[str, str]]:
        """Get messages in API-ready format."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
        ]

    def set_working_memory(self, key: str, value: Any) -> None:
        """Store something in working memory."""
        if len(self.working_memory) >= self.working_memory_max_items:
            # Remove oldest item (simple LRU)
            oldest_key = next(iter(self.working_memory))
            del self.working_memory[oldest_key]
        self.working_memory[key] = {
            "value": value,
            "stored_at": datetime.utcnow().isoformat(),
        }

    def get_working_memory(self, key: str) -> Optional[Any]:
        """Retrieve from working memory."""
        item = self.working_memory.get(key)
        if item:
            return item["value"]
        return None


@dataclass
class ResourceLimits:
    """Resource limits for agent execution."""
    max_tokens_per_turn: int = 8192
    max_tool_calls_per_turn: int = 10
    max_cost_per_session_usd: float = 1.0
    current_session_cost_usd: float = 0.0


@dataclass
class ScopeRestrictions:
    """Scope restrictions for agent operations."""
    allowed_directories: List[str] = field(default_factory=lambda: ["/workspace"])
    allowed_domains: List[str] = field(default_factory=list)
    denied_patterns: List[str] = field(default_factory=lambda: ["*.env", "credentials.*"])


@dataclass
class AgentPermissions:
    """
    What the agent can and cannot do.

    This is the security boundary for agent operations.
    """
    # Tool permissions
    allowed_tools: Set[str] = field(default_factory=set)
    denied_tools: Set[str] = field(default_factory=set)
    approval_required_tools: Set[str] = field(default_factory=set)

    # Resource limits
    resources: ResourceLimits = field(default_factory=ResourceLimits)

    # Scope
    scope: ScopeRestrictions = field(default_factory=ScopeRestrictions)

    # Escalation behavior
    on_permission_denied: str = "ask_human"  # "ask_human" | "fail" | "log_and_continue"
    on_uncertainty_high: str = "pause_and_confirm"

    def check_tool_permission(self, tool_name: str) -> PermissionLevel:
        """Check what permission level a tool has."""
        if tool_name in self.denied_tools:
            return PermissionLevel.DENIED
        if tool_name in self.approval_required_tools:
            return PermissionLevel.REQUIRE_APPROVAL
        if tool_name in self.allowed_tools:
            return PermissionLevel.ALLOWED
        # Default: deny unlisted tools
        return PermissionLevel.DENIED

    def check_path_allowed(self, path: str) -> bool:
        """Check if a file path is allowed."""
        path_obj = Path(path)

        # Check against denied patterns
        for pattern in self.scope.denied_patterns:
            if path_obj.match(pattern):
                return False

        # Check against allowed directories
        for allowed_dir in self.scope.allowed_directories:
            try:
                path_obj.relative_to(allowed_dir)
                return True
            except ValueError:
                continue

        return False

    def record_cost(self, cost_usd: float) -> bool:
        """Record cost and return whether we're still under budget."""
        self.resources.current_session_cost_usd += cost_usd
        return self.resources.current_session_cost_usd <= self.resources.max_cost_per_session_usd


@dataclass
class MemoryItem:
    """An item in long-term memory."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMemory:
    """
    The persistence layer for agent state.

    Manages what survives across sessions:
    - Episodic memory (what happened)
    - Semantic memory (what things mean)
    - Procedural memory (how to do things)
    """
    # Episodic memory
    episodic_enabled: bool = True
    episodic_storage_path: Optional[str] = None
    episodic_retention_days: int = 30
    episodes: List[Dict[str, Any]] = field(default_factory=list)

    # Semantic memory
    semantic_enabled: bool = True
    semantic_items: List[MemoryItem] = field(default_factory=list)

    # Procedural memory (learned skills/patterns)
    procedural_enabled: bool = True
    learned_skills: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Working to long-term consolidation
    consolidation_strategy: str = "importance_weighted"

    def record_episode(
        self,
        event_type: str,
        data: Dict[str, Any],
        importance: float = 0.5,
    ) -> None:
        """Record an episodic memory."""
        if not self.episodic_enabled:
            return

        self.episodes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data,
            "importance": importance,
        })

    def add_semantic_item(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryItem:
        """Add an item to semantic memory."""
        item = MemoryItem(
            id=hashlib.sha256(content.encode()).hexdigest()[:16],
            content=content,
            importance=importance,
            metadata=metadata or {},
        )
        self.semantic_items.append(item)
        return item

    def register_skill(
        self,
        skill_id: str,
        description: str,
        confidence: float = 0.5,
    ) -> None:
        """Register a learned skill in procedural memory."""
        self.learned_skills[skill_id] = {
            "description": description,
            "confidence": confidence,
            "learned_at": datetime.utcnow().isoformat(),
            "use_count": 0,
        }

    def update_skill_confidence(self, skill_id: str, success: bool) -> None:
        """Update skill confidence based on usage outcome."""
        if skill_id in self.learned_skills:
            skill = self.learned_skills[skill_id]
            skill["use_count"] += 1
            # Simple confidence update
            delta = 0.05 if success else -0.1
            skill["confidence"] = max(0.0, min(1.0, skill["confidence"] + delta))


@dataclass
class AgentOutput:
    """
    The output of an agent invocation.

    Unlike a function return value, this carries uncertainty metadata
    and alternative outputs that were considered.
    """
    content: str
    confidence: float  # 0.0 - 1.0

    # Uncertainty classification
    uncertainty_type: str = "epistemic"  # "epistemic" | "aleatoric"

    # Alternative outputs considered
    alternatives: List[str] = field(default_factory=list)

    # Reasoning trace (if available)
    reasoning_trace: Optional[str] = None

    # Tool usage in this output
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    model: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Timestamp
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """Check if the output meets a confidence threshold."""
        return self.confidence >= threshold

    def needs_human_review(self, threshold: float = 0.5) -> bool:
        """Check if this output should be reviewed by a human."""
        return self.confidence < threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "content": self.content,
            "confidence": self.confidence,
            "uncertainty_type": self.uncertainty_type,
            "alternatives": self.alternatives,
            "reasoning_trace": self.reasoning_trace,
            "tool_calls": self.tool_calls,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "created_at": self.created_at.isoformat(),
        }
