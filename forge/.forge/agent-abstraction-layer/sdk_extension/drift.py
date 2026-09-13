"""
Behavioral Drift Detection for AAL.

AI agents change over time - models update, prompts evolve, behavior shifts.
This module detects when current behavior diverges from baseline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import statistics
from pathlib import Path


@dataclass
class BehavioralMetrics:
    """Metrics captured for behavioral analysis."""
    response_length: int
    latency_ms: float
    tool_count: int
    tools_used: List[str]
    confidence: float
    error_occurred: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_length": self.response_length,
            "latency_ms": self.latency_ms,
            "tool_count": self.tool_count,
            "tools_used": self.tools_used,
            "confidence": self.confidence,
            "error_occurred": self.error_occurred,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BehavioralBaseline:
    """Baseline behavioral fingerprint for drift detection."""
    # Response length statistics
    response_length_mean: float
    response_length_std: float

    # Latency statistics
    latency_mean_ms: float
    latency_std_ms: float

    # Tool usage patterns
    avg_tool_count: float
    tool_frequency: Dict[str, float]  # tool -> usage frequency

    # Confidence statistics
    confidence_mean: float
    confidence_std: float

    # Error rate
    error_rate: float

    # Metadata
    sample_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_length": {
                "mean": self.response_length_mean,
                "std": self.response_length_std,
            },
            "latency_ms": {
                "mean": self.latency_mean_ms,
                "std": self.latency_std_ms,
            },
            "tool_usage": {
                "avg_count": self.avg_tool_count,
                "frequency": self.tool_frequency,
            },
            "confidence": {
                "mean": self.confidence_mean,
                "std": self.confidence_std,
            },
            "error_rate": self.error_rate,
            "sample_count": self.sample_count,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }

    def save(self, path: str) -> None:
        """Save baseline to file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str) -> "BehavioralBaseline":
        """Load baseline from file."""
        data = json.loads(Path(path).read_text())
        return cls(
            response_length_mean=data["response_length"]["mean"],
            response_length_std=data["response_length"]["std"],
            latency_mean_ms=data["latency_ms"]["mean"],
            latency_std_ms=data["latency_ms"]["std"],
            avg_tool_count=data["tool_usage"]["avg_count"],
            tool_frequency=data["tool_usage"]["frequency"],
            confidence_mean=data["confidence"]["mean"],
            confidence_std=data["confidence"]["std"],
            error_rate=data["error_rate"],
            sample_count=data["sample_count"],
            created_at=datetime.fromisoformat(data["created_at"]),
            version=data.get("version", "1.0"),
        )


@dataclass
class DriftAlert:
    """Alert when drift is detected."""
    timestamp: datetime
    metric: str
    baseline_value: float
    current_value: float
    deviation: float  # Standard deviations from baseline
    threshold: float
    severity: str  # "warning" | "critical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric": self.metric,
            "baseline": self.baseline_value,
            "current": self.current_value,
            "deviation_std": self.deviation,
            "threshold": self.threshold,
            "severity": self.severity,
        }


class DriftDetector:
    """
    Detects behavioral drift from baseline.

    Monitors:
    - Response length distribution
    - Latency patterns
    - Tool usage frequency
    - Confidence levels
    - Error rates
    """

    def __init__(
        self,
        baseline: Optional[BehavioralBaseline] = None,
        threshold: float = 0.15,
        window_size: int = 50,
    ):
        self.baseline = baseline
        self.threshold = threshold
        self.window_size = window_size

        # Current window of observations
        self.observations: List[BehavioralMetrics] = []
        self.alerts: List[DriftAlert] = []

    def record(self, metrics: BehavioralMetrics) -> None:
        """Record an observation."""
        self.observations.append(metrics)

        # Keep window bounded
        if len(self.observations) > self.window_size * 2:
            self.observations = self.observations[-self.window_size:]

    def check(self, response: Any) -> bool:
        """
        Check for drift against baseline.

        Returns True if drift is detected.
        """
        if not self.baseline:
            return False

        if len(self.observations) < 10:
            return False  # Not enough data

        # Extract metrics from response
        metrics = self._extract_metrics(response)
        self.record(metrics)

        # Check each metric dimension
        drift_detected = False

        # Response length
        if self._check_metric_drift(
            "response_length",
            [o.response_length for o in self.observations[-self.window_size:]],
            self.baseline.response_length_mean,
            self.baseline.response_length_std,
        ):
            drift_detected = True

        # Latency
        if self._check_metric_drift(
            "latency_ms",
            [o.latency_ms for o in self.observations[-self.window_size:]],
            self.baseline.latency_mean_ms,
            self.baseline.latency_std_ms,
        ):
            drift_detected = True

        # Confidence
        if self._check_metric_drift(
            "confidence",
            [o.confidence for o in self.observations[-self.window_size:]],
            self.baseline.confidence_mean,
            self.baseline.confidence_std,
        ):
            drift_detected = True

        # Error rate
        current_error_rate = sum(
            1 for o in self.observations[-self.window_size:]
            if o.error_occurred
        ) / min(len(self.observations), self.window_size)

        if abs(current_error_rate - self.baseline.error_rate) > self.threshold:
            self._add_alert(
                "error_rate",
                self.baseline.error_rate,
                current_error_rate,
                abs(current_error_rate - self.baseline.error_rate) / max(0.01, self.baseline.error_rate),
            )
            drift_detected = True

        return drift_detected

    def _extract_metrics(self, response: Any) -> BehavioralMetrics:
        """Extract metrics from a response object."""
        # Handle different response types
        if hasattr(response, 'content'):
            length = len(response.content)
        elif isinstance(response, str):
            length = len(response)
        else:
            length = len(str(response))

        return BehavioralMetrics(
            response_length=length,
            latency_ms=getattr(response, 'duration_ms', 0),
            tool_count=len(getattr(response, 'tool_calls', [])),
            tools_used=[t.get('name', '') for t in getattr(response, 'tool_calls', [])],
            confidence=getattr(response, 'confidence', type('', (), {'overall': 0.7})).overall,
            error_occurred=getattr(response, 'degradation_level', None) is not None,
        )

    def _check_metric_drift(
        self,
        metric_name: str,
        current_values: List[float],
        baseline_mean: float,
        baseline_std: float,
    ) -> bool:
        """Check if a metric has drifted from baseline."""
        if not current_values:
            return False

        current_mean = statistics.mean(current_values)

        # How many standard deviations from baseline?
        if baseline_std > 0:
            deviation = abs(current_mean - baseline_mean) / baseline_std
        else:
            deviation = abs(current_mean - baseline_mean) / max(0.01, baseline_mean)

        # Threshold in standard deviations (e.g., 2 std = significant)
        std_threshold = 2.0

        if deviation > std_threshold:
            self._add_alert(metric_name, baseline_mean, current_mean, deviation)
            return True

        return False

    def _add_alert(
        self,
        metric: str,
        baseline_value: float,
        current_value: float,
        deviation: float,
    ) -> None:
        """Add a drift alert."""
        severity = "critical" if deviation > 3.0 else "warning"

        alert = DriftAlert(
            timestamp=datetime.utcnow(),
            metric=metric,
            baseline_value=baseline_value,
            current_value=current_value,
            deviation=deviation,
            threshold=self.threshold,
            severity=severity,
        )
        self.alerts.append(alert)

    def create_baseline(self) -> BehavioralBaseline:
        """Create a baseline from current observations."""
        if len(self.observations) < 10:
            raise ValueError("Need at least 10 observations to create baseline")

        obs = self.observations

        lengths = [o.response_length for o in obs]
        latencies = [o.latency_ms for o in obs]
        confidences = [o.confidence for o in obs]
        tool_counts = [o.tool_count for o in obs]

        # Calculate tool frequency
        tool_freq: Dict[str, int] = {}
        for o in obs:
            for tool in o.tools_used:
                tool_freq[tool] = tool_freq.get(tool, 0) + 1

        total_tools = sum(tool_freq.values())
        if total_tools > 0:
            tool_frequency = {k: v / total_tools for k, v in tool_freq.items()}
        else:
            tool_frequency = {}

        error_count = sum(1 for o in obs if o.error_occurred)

        return BehavioralBaseline(
            response_length_mean=statistics.mean(lengths),
            response_length_std=statistics.stdev(lengths) if len(lengths) > 1 else 0,
            latency_mean_ms=statistics.mean(latencies),
            latency_std_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            avg_tool_count=statistics.mean(tool_counts),
            tool_frequency=tool_frequency,
            confidence_mean=statistics.mean(confidences),
            confidence_std=statistics.stdev(confidences) if len(confidences) > 1 else 0,
            error_rate=error_count / len(obs),
            sample_count=len(obs),
        )

    def set_baseline(self, baseline: BehavioralBaseline) -> None:
        """Set the baseline for drift detection."""
        self.baseline = baseline

    def get_recent_alerts(self, limit: int = 10) -> List[DriftAlert]:
        """Get recent drift alerts."""
        return self.alerts[-limit:]

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self.alerts = []

    def get_status(self) -> Dict[str, Any]:
        """Get detector status."""
        return {
            "has_baseline": self.baseline is not None,
            "observation_count": len(self.observations),
            "alert_count": len(self.alerts),
            "recent_alerts": [a.to_dict() for a in self.alerts[-5:]],
        }
