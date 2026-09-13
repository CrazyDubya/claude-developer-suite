"""
Observability layer for the Agent Abstraction Layer.

AI agents are unintelligible - we cannot inspect their reasoning.
This module provides tools for observing behavior patterns,
tracing decisions, and detecting drift.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import defaultdict
import hashlib
import json
import math
import statistics


class SpanKind(Enum):
    """Types of trace spans."""
    AGENT_TURN = "agent_turn"
    TOOL_CALL = "tool_call"
    MEMORY_ACCESS = "memory_access"
    DECISION = "decision"
    ERROR = "error"
    HUMAN_ESCALATION = "human_escalation"


class DecisionType(Enum):
    """Types of decisions agents make."""
    TOOL_SELECTION = "tool_selection"
    RESPONSE_FORMULATION = "response_formulation"
    ERROR_HANDLING = "error_handling"
    ESCALATION = "escalation"
    PATH_SELECTION = "path_selection"


@dataclass
class SpanAttribute:
    """An attribute on a trace span."""
    name: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TraceSpan:
    """
    A span in a trace.

    Represents a single operation in the agent's execution,
    with timing, attributes, and parent/child relationships.
    """
    id: str
    name: str
    kind: SpanKind
    start_time: datetime
    end_time: Optional[datetime] = None
    parent_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # "ok" | "error"
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        name: str,
        kind: SpanKind,
        parent_id: Optional[str] = None,
    ) -> "TraceSpan":
        """Create a new span."""
        span_id = hashlib.sha256(
            f"{name}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        return cls(
            id=span_id,
            name=name,
            kind=kind,
            start_time=datetime.utcnow(),
            parent_id=parent_id,
        )

    def end(self, status: str = "ok", error_message: Optional[str] = None) -> None:
        """End the span."""
        self.end_time = datetime.utcnow()
        self.status = status
        self.error_message = error_message

    def set_attribute(self, name: str, value: Any) -> None:
        """Set an attribute on the span."""
        self.attributes[name] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })

    def duration_ms(self) -> Optional[float]:
        """Get the duration of the span in milliseconds."""
        if self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() * 1000
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "parent_id": self.parent_id,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms(),
        }


@dataclass
class AgentTrace:
    """
    A complete trace of agent execution.

    Contains all spans from a single agent invocation,
    organized hierarchically.
    """
    id: str
    agent_id: str
    session_id: str
    spans: List[TraceSpan] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Aggregated metrics
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    tool_calls_count: int = 0
    errors_count: int = 0

    @classmethod
    def create(cls, agent_id: str, session_id: str) -> "AgentTrace":
        """Create a new trace."""
        trace_id = hashlib.sha256(
            f"{agent_id}{session_id}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:24]

        return cls(
            id=trace_id,
            agent_id=agent_id,
            session_id=session_id,
        )

    def start_span(
        self,
        name: str,
        kind: SpanKind,
        parent_id: Optional[str] = None,
    ) -> TraceSpan:
        """Start a new span in this trace."""
        span = TraceSpan.create(name, kind, parent_id)
        self.spans.append(span)
        return span

    def end_trace(self) -> None:
        """End the trace and calculate aggregates."""
        self.end_time = datetime.utcnow()

        # Aggregate metrics
        for span in self.spans:
            if span.kind == SpanKind.TOOL_CALL:
                self.tool_calls_count += 1
            if span.status == "error":
                self.errors_count += 1

            tokens_in = span.attributes.get("input_tokens", 0)
            tokens_out = span.attributes.get("output_tokens", 0)
            cost = span.attributes.get("cost_usd", 0.0)

            self.total_input_tokens += tokens_in
            self.total_output_tokens += tokens_out
            self.total_cost_usd += cost

    def get_span_tree(self) -> Dict[str, Any]:
        """Get spans organized as a tree structure."""
        # Build parent -> children mapping
        children: Dict[str, List[TraceSpan]] = defaultdict(list)
        roots: List[TraceSpan] = []

        for span in self.spans:
            if span.parent_id:
                children[span.parent_id].append(span)
            else:
                roots.append(span)

        def build_tree(span: TraceSpan) -> Dict[str, Any]:
            node = span.to_dict()
            node["children"] = [
                build_tree(child) for child in children.get(span.id, [])
            ]
            return node

        return {
            "trace_id": self.id,
            "roots": [build_tree(root) for root in roots],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
            "metrics": {
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cost_usd": self.total_cost_usd,
                "tool_calls_count": self.tool_calls_count,
                "errors_count": self.errors_count,
            },
        }


@dataclass
class DecisionLogEntry:
    """
    A logged decision made by the agent.

    Since we can't inspect agent reasoning, we log
    decisions with their context and outcomes.
    """
    id: str
    decision_type: DecisionType
    timestamp: datetime
    context: str  # What situation led to this decision
    choice: str  # What was chosen
    alternatives_considered: List[str]
    confidence: float
    outcome: Optional[str] = None  # Was it successful?
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        decision_type: DecisionType,
        context: str,
        choice: str,
        alternatives: List[str],
        confidence: float,
    ) -> "DecisionLogEntry":
        """Create a new decision log entry."""
        entry_id = hashlib.sha256(
            f"{decision_type.value}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        return cls(
            id=entry_id,
            decision_type=decision_type,
            timestamp=datetime.utcnow(),
            context=context,
            choice=choice,
            alternatives_considered=alternatives,
            confidence=confidence,
        )

    def record_outcome(self, outcome: str) -> None:
        """Record the outcome of this decision."""
        self.outcome = outcome

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "decision_type": self.decision_type.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "choice": self.choice,
            "alternatives_considered": self.alternatives_considered,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }


class DecisionLog:
    """
    Maintains a log of all agent decisions.

    This is the primary debugging tool for agent behavior -
    since we can't step through reasoning, we analyze decisions.
    """

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.entries: List[DecisionLogEntry] = []

    def log(
        self,
        decision_type: DecisionType,
        context: str,
        choice: str,
        alternatives: List[str],
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionLogEntry:
        """Log a decision."""
        entry = DecisionLogEntry.create(
            decision_type=decision_type,
            context=context,
            choice=choice,
            alternatives=alternatives,
            confidence=confidence,
        )
        if metadata:
            entry.metadata = metadata

        self.entries.append(entry)

        # Enforce max entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        return entry

    def get_by_type(self, decision_type: DecisionType) -> List[DecisionLogEntry]:
        """Get all decisions of a specific type."""
        return [e for e in self.entries if e.decision_type == decision_type]

    def get_low_confidence(self, threshold: float = 0.5) -> List[DecisionLogEntry]:
        """Get decisions below a confidence threshold."""
        return [e for e in self.entries if e.confidence < threshold]

    def get_failed(self) -> List[DecisionLogEntry]:
        """Get decisions that had negative outcomes."""
        return [
            e for e in self.entries
            if e.outcome and "fail" in e.outcome.lower()
        ]

    def analyze_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in decision-making."""
        if not self.entries:
            return {}

        # Decision type distribution
        type_counts: Dict[str, int] = defaultdict(int)
        for entry in self.entries:
            type_counts[entry.decision_type.value] += 1

        # Confidence distribution
        confidences = [e.confidence for e in self.entries]

        # Success rate by type
        type_outcomes: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0, "unknown": 0}
        )
        for entry in self.entries:
            outcome_key = "unknown"
            if entry.outcome:
                outcome_key = "success" if "success" in entry.outcome.lower() else "failure"
            type_outcomes[entry.decision_type.value][outcome_key] += 1

        return {
            "total_decisions": len(self.entries),
            "type_distribution": dict(type_counts),
            "confidence_stats": {
                "mean": statistics.mean(confidences),
                "median": statistics.median(confidences),
                "stdev": statistics.stdev(confidences) if len(confidences) > 1 else 0,
            },
            "outcomes_by_type": dict(type_outcomes),
        }

    def to_jsonl(self) -> str:
        """Export to JSON Lines format."""
        return "\n".join(
            json.dumps(e.to_dict()) for e in self.entries
        )


@dataclass
class MetricBucket:
    """A histogram bucket for metrics."""
    upper_bound: float
    count: int = 0


@dataclass
class MetricValue:
    """A metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


class BehavioralFingerprint:
    """
    A fingerprint of agent behavior for drift detection.

    Rather than comparing code, we compare behavioral
    distributions to detect when an agent changes.
    """

    def __init__(self):
        # Response length distribution
        self.response_lengths: List[int] = []

        # Latency distribution
        self.latencies_ms: List[float] = []

        # Tool usage frequency
        self.tool_usage: Dict[str, int] = defaultdict(int)

        # Token ratios (output/input)
        self.token_ratios: List[float] = []

        # Error rate
        self.total_invocations: int = 0
        self.error_count: int = 0

        # Confidence distribution
        self.confidences: List[float] = []

    def record_invocation(
        self,
        response_length: int,
        latency_ms: float,
        tools_used: List[str],
        input_tokens: int,
        output_tokens: int,
        confidence: float,
        error: bool = False,
    ) -> None:
        """Record metrics from an invocation."""
        self.response_lengths.append(response_length)
        self.latencies_ms.append(latency_ms)
        self.confidences.append(confidence)

        for tool in tools_used:
            self.tool_usage[tool] += 1

        if input_tokens > 0:
            self.token_ratios.append(output_tokens / input_tokens)

        self.total_invocations += 1
        if error:
            self.error_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the behavioral fingerprint."""
        def safe_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0, "median": 0, "p95": 0}
            sorted_vals = sorted(values)
            p95_idx = int(len(sorted_vals) * 0.95)
            return {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "p95": sorted_vals[min(p95_idx, len(sorted_vals) - 1)],
            }

        return {
            "invocations": self.total_invocations,
            "error_rate": self.error_count / max(1, self.total_invocations),
            "response_length": safe_stats([float(x) for x in self.response_lengths]),
            "latency_ms": safe_stats(self.latencies_ms),
            "token_ratio": safe_stats(self.token_ratios),
            "confidence": safe_stats(self.confidences),
            "tool_usage": dict(self.tool_usage),
        }

    def compute_hash(self) -> str:
        """Compute a hash of the behavioral fingerprint."""
        summary = self.get_summary()
        return hashlib.sha256(
            json.dumps(summary, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]


class DriftDetector:
    """
    Detects when agent behavior drifts from baseline.

    Uses statistical tests to determine if current behavior
    differs significantly from historical patterns.
    """

    def __init__(
        self,
        baseline: Optional[BehavioralFingerprint] = None,
        threshold: float = 0.1,
        window_size: int = 100,
    ):
        self.baseline = baseline or BehavioralFingerprint()
        self.current = BehavioralFingerprint()
        self.threshold = threshold
        self.window_size = window_size
        self.drift_alerts: List[Dict[str, Any]] = []

    def record(
        self,
        response_length: int,
        latency_ms: float,
        tools_used: List[str],
        input_tokens: int,
        output_tokens: int,
        confidence: float,
        error: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Record an invocation and check for drift.

        Returns a drift alert if significant drift detected.
        """
        self.current.record_invocation(
            response_length=response_length,
            latency_ms=latency_ms,
            tools_used=tools_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            confidence=confidence,
            error=error,
        )

        # Check for drift after we have enough samples
        if self.current.total_invocations >= self.window_size:
            alert = self._check_drift()
            if alert:
                self.drift_alerts.append(alert)
                return alert

        return None

    def _check_drift(self) -> Optional[Dict[str, Any]]:
        """Check if current behavior has drifted from baseline."""
        if not self.baseline.total_invocations:
            return None

        baseline_summary = self.baseline.get_summary()
        current_summary = self.current.get_summary()

        drifted_metrics = []

        # Compare latency
        if self._ks_test(
            self.baseline.latencies_ms,
            self.current.latencies_ms,
        ) > self.threshold:
            drifted_metrics.append("latency")

        # Compare response length
        if self._ks_test(
            [float(x) for x in self.baseline.response_lengths],
            [float(x) for x in self.current.response_lengths],
        ) > self.threshold:
            drifted_metrics.append("response_length")

        # Compare confidence
        if self._ks_test(
            self.baseline.confidences,
            self.current.confidences,
        ) > self.threshold:
            drifted_metrics.append("confidence")

        # Compare error rate
        baseline_error_rate = baseline_summary.get("error_rate", 0)
        current_error_rate = current_summary.get("error_rate", 0)
        if abs(current_error_rate - baseline_error_rate) > self.threshold:
            drifted_metrics.append("error_rate")

        if drifted_metrics:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "drifted_metrics": drifted_metrics,
                "baseline_hash": self.baseline.compute_hash(),
                "current_hash": self.current.compute_hash(),
                "baseline_summary": baseline_summary,
                "current_summary": current_summary,
            }

        return None

    def _ks_test(
        self,
        baseline: List[float],
        current: List[float],
    ) -> float:
        """
        Simplified Kolmogorov-Smirnov test statistic.

        Returns a value between 0 and 1, where higher values
        indicate more divergence between distributions.
        """
        if not baseline or not current:
            return 0.0

        # Sort both samples
        baseline_sorted = sorted(baseline)
        current_sorted = sorted(current)

        # Compute empirical CDFs and find max difference
        n1 = len(baseline_sorted)
        n2 = len(current_sorted)

        # Merge and compare CDFs at each point
        all_values = sorted(set(baseline_sorted + current_sorted))

        max_diff = 0.0
        for val in all_values:
            # CDF of baseline at this point
            cdf1 = sum(1 for x in baseline_sorted if x <= val) / n1
            # CDF of current at this point
            cdf2 = sum(1 for x in current_sorted if x <= val) / n2

            diff = abs(cdf1 - cdf2)
            max_diff = max(max_diff, diff)

        return max_diff

    def save_baseline(self) -> None:
        """Save current as the new baseline."""
        self.baseline = self.current
        self.current = BehavioralFingerprint()

    def get_drift_alerts(self) -> List[Dict[str, Any]]:
        """Get all drift alerts."""
        return self.drift_alerts


class Tracer:
    """
    Main tracing interface for agent observability.

    Provides a simple API for instrumenting agent code.
    """

    def __init__(self, agent_id: str, session_id: str):
        self.current_trace = AgentTrace.create(agent_id, session_id)
        self.span_stack: List[TraceSpan] = []
        self.decision_log = DecisionLog()
        self.fingerprint = BehavioralFingerprint()
        self.drift_detector = DriftDetector()

    def start_span(self, name: str, kind: SpanKind) -> TraceSpan:
        """Start a new span."""
        parent_id = self.span_stack[-1].id if self.span_stack else None
        span = self.current_trace.start_span(name, kind, parent_id)
        self.span_stack.append(span)
        return span

    def end_span(
        self,
        status: str = "ok",
        error_message: Optional[str] = None,
    ) -> Optional[TraceSpan]:
        """End the current span."""
        if self.span_stack:
            span = self.span_stack.pop()
            span.end(status, error_message)
            return span
        return None

    def log_decision(
        self,
        decision_type: DecisionType,
        context: str,
        choice: str,
        alternatives: List[str],
        confidence: float,
    ) -> DecisionLogEntry:
        """Log a decision."""
        return self.decision_log.log(
            decision_type=decision_type,
            context=context,
            choice=choice,
            alternatives=alternatives,
            confidence=confidence,
        )

    def record_completion(
        self,
        response_length: int,
        latency_ms: float,
        tools_used: List[str],
        input_tokens: int,
        output_tokens: int,
        confidence: float,
        error: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Record a completion and check for drift."""
        self.fingerprint.record_invocation(
            response_length=response_length,
            latency_ms=latency_ms,
            tools_used=tools_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            confidence=confidence,
            error=error,
        )

        return self.drift_detector.record(
            response_length=response_length,
            latency_ms=latency_ms,
            tools_used=tools_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            confidence=confidence,
            error=error,
        )

    def end_trace(self) -> AgentTrace:
        """End the current trace."""
        # End any open spans
        while self.span_stack:
            self.end_span()

        self.current_trace.end_trace()
        return self.current_trace

    def get_trace(self) -> AgentTrace:
        """Get the current trace."""
        return self.current_trace
