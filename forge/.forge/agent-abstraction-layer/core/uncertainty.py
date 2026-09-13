"""
Uncertainty management for the Agent Abstraction Layer.

AI agents are fundamentally stochastic. This module provides tools
for quantifying, exploring, and managing uncertainty.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import hashlib
import json
import random


class UncertaintyType(Enum):
    """
    Classification of uncertainty sources.

    EPISTEMIC: Uncertainty from lack of knowledge (reducible)
        - Could be reduced with more data/context
        - Examples: unclear requirements, missing information

    ALEATORIC: Inherent randomness (irreducible)
        - Fundamental to the system
        - Examples: model sampling, ambiguous inputs
    """
    EPISTEMIC = "epistemic"
    ALEATORIC = "aleatoric"


class ExplorationStrategy(Enum):
    """Strategies for exploring multiple possible outputs."""
    SINGLE = "single"  # Just take one sample
    BEAM_SEARCH = "beam_search"  # Explore multiple paths, prune low confidence
    MONTE_CARLO = "monte_carlo"  # Random sampling with temperature variation
    CONSENSUS = "consensus"  # Multiple samples, vote on best


class ConsensusStrategy(Enum):
    """How to combine multiple outputs into a consensus."""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_AVERAGE = "weighted_average"
    HUMAN_SELECT = "human_select"
    HIGHEST_CONFIDENCE = "highest_confidence"


@dataclass
class ConfidenceScore:
    """
    A structured confidence score with components.

    Rather than a single number, this breaks down confidence
    into interpretable components.
    """
    overall: float  # 0.0 - 1.0

    # Component scores
    model_confidence: float = 0.0  # From model's own uncertainty estimates
    consistency_score: float = 0.0  # How consistent across multiple samples
    grounding_score: float = 0.0  # How well grounded in provided context
    tool_reliability: float = 0.0  # Reliability of tools used

    # Metadata
    uncertainty_type: UncertaintyType = UncertaintyType.EPISTEMIC
    reasoning: str = ""

    @classmethod
    def from_components(
        cls,
        model_confidence: float,
        consistency_score: float,
        grounding_score: float,
        tool_reliability: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> "ConfidenceScore":
        """Calculate overall confidence from components."""
        if weights is None:
            weights = {
                "model": 0.3,
                "consistency": 0.3,
                "grounding": 0.25,
                "tool": 0.15,
            }

        overall = (
            model_confidence * weights["model"]
            + consistency_score * weights["consistency"]
            + grounding_score * weights["grounding"]
            + tool_reliability * weights["tool"]
        )

        return cls(
            overall=overall,
            model_confidence=model_confidence,
            consistency_score=consistency_score,
            grounding_score=grounding_score,
            tool_reliability=tool_reliability,
        )

    def is_actionable(self, threshold: float = 0.7) -> bool:
        """Check if confidence is high enough to act on."""
        return self.overall >= threshold

    def needs_exploration(self, threshold: float = 0.5) -> bool:
        """Check if we should explore alternative paths."""
        return self.overall < threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "overall": self.overall,
            "components": {
                "model_confidence": self.model_confidence,
                "consistency_score": self.consistency_score,
                "grounding_score": self.grounding_score,
                "tool_reliability": self.tool_reliability,
            },
            "uncertainty_type": self.uncertainty_type.value,
            "reasoning": self.reasoning,
        }


@dataclass
class ExplorationPath:
    """A single path in multi-path exploration."""
    id: str
    content: str
    confidence: ConfidenceScore
    temperature_used: float
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        content: str,
        confidence: ConfidenceScore,
        temperature: float,
    ) -> "ExplorationPath":
        """Create a new exploration path."""
        path_id = hashlib.sha256(
            f"{content}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        return cls(
            id=path_id,
            content=content,
            confidence=confidence,
            temperature_used=temperature,
        )


@dataclass
class ExplorationConfig:
    """Configuration for multi-path exploration."""
    strategy: ExplorationStrategy = ExplorationStrategy.SINGLE

    # Beam search config
    beam_width: int = 3
    beam_depth: int = 5
    prune_threshold: float = 0.3

    # Monte Carlo config
    mc_samples: int = 10
    temperature_range: Tuple[float, float] = (0.5, 1.2)

    # Consensus config
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.HIGHEST_CONFIDENCE
    min_agreement: float = 0.6


@dataclass
class ExplorationResult:
    """Result of multi-path exploration."""
    paths: List[ExplorationPath]
    selected_path: ExplorationPath
    consensus_confidence: float
    exploration_config: ExplorationConfig
    duration_ms: float = 0.0

    def get_alternative_summaries(self) -> List[str]:
        """Get summaries of alternative paths not selected."""
        return [
            f"[{p.confidence.overall:.2f}] {p.content[:100]}..."
            for p in self.paths
            if p.id != self.selected_path.id
        ]


class MultiPathExplorer:
    """
    Explores multiple possible outputs when confidence is low.

    This is the key abstraction for handling stochasticity:
    rather than taking a single sample, we explore the output
    distribution and select based on confidence/consensus.
    """

    def __init__(self, config: ExplorationConfig):
        self.config = config

    def explore(
        self,
        generator: Callable[[float], Tuple[str, ConfidenceScore]],
    ) -> ExplorationResult:
        """
        Explore multiple paths using the configured strategy.

        Args:
            generator: A function that takes a temperature and returns
                      (content, confidence) tuple.

        Returns:
            ExplorationResult with all paths and selected best path.
        """
        start_time = datetime.utcnow()

        if self.config.strategy == ExplorationStrategy.SINGLE:
            paths = self._single_sample(generator)
        elif self.config.strategy == ExplorationStrategy.BEAM_SEARCH:
            paths = self._beam_search(generator)
        elif self.config.strategy == ExplorationStrategy.MONTE_CARLO:
            paths = self._monte_carlo(generator)
        elif self.config.strategy == ExplorationStrategy.CONSENSUS:
            paths = self._consensus_sampling(generator)
        else:
            paths = self._single_sample(generator)

        # Select best path based on consensus strategy
        selected = self._select_best(paths)

        # Calculate consensus confidence
        consensus_confidence = self._calculate_consensus_confidence(paths)

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ExplorationResult(
            paths=paths,
            selected_path=selected,
            consensus_confidence=consensus_confidence,
            exploration_config=self.config,
            duration_ms=duration,
        )

    def _single_sample(
        self,
        generator: Callable[[float], Tuple[str, ConfidenceScore]],
    ) -> List[ExplorationPath]:
        """Take a single sample at default temperature."""
        content, confidence = generator(1.0)
        path = ExplorationPath.create(content, confidence, 1.0)
        return [path]

    def _beam_search(
        self,
        generator: Callable[[float], Tuple[str, ConfidenceScore]],
    ) -> List[ExplorationPath]:
        """Beam search: explore multiple paths, prune low confidence."""
        paths = []

        for i in range(self.config.beam_width):
            # Vary temperature slightly for diversity
            temp = 0.8 + (i * 0.2)
            content, confidence = generator(temp)
            path = ExplorationPath.create(content, confidence, temp)

            # Prune if below threshold
            if confidence.overall >= self.config.prune_threshold:
                paths.append(path)

        # Ensure we have at least one path
        if not paths:
            content, confidence = generator(1.0)
            paths.append(ExplorationPath.create(content, confidence, 1.0))

        return paths

    def _monte_carlo(
        self,
        generator: Callable[[float], Tuple[str, ConfidenceScore]],
    ) -> List[ExplorationPath]:
        """Monte Carlo: random sampling with temperature variation."""
        paths = []
        temp_min, temp_max = self.config.temperature_range

        for _ in range(self.config.mc_samples):
            temp = random.uniform(temp_min, temp_max)
            content, confidence = generator(temp)
            path = ExplorationPath.create(content, confidence, temp)
            paths.append(path)

        return paths

    def _consensus_sampling(
        self,
        generator: Callable[[float], Tuple[str, ConfidenceScore]],
    ) -> List[ExplorationPath]:
        """Sample multiple times and look for consensus."""
        # Use Monte Carlo sampling as base
        return self._monte_carlo(generator)

    def _select_best(self, paths: List[ExplorationPath]) -> ExplorationPath:
        """Select the best path based on consensus strategy."""
        if not paths:
            raise ValueError("No paths to select from")

        if len(paths) == 1:
            return paths[0]

        strategy = self.config.consensus_strategy

        if strategy == ConsensusStrategy.HIGHEST_CONFIDENCE:
            return max(paths, key=lambda p: p.confidence.overall)

        elif strategy == ConsensusStrategy.MAJORITY_VOTE:
            # Group similar responses and pick most common
            # Simplified: just use highest confidence
            return max(paths, key=lambda p: p.confidence.overall)

        elif strategy == ConsensusStrategy.WEIGHTED_AVERAGE:
            # For now, just use highest confidence
            # True weighted average would need semantic similarity
            return max(paths, key=lambda p: p.confidence.overall)

        else:
            return paths[0]

    def _calculate_consensus_confidence(
        self,
        paths: List[ExplorationPath],
    ) -> float:
        """Calculate how confident we are in the consensus."""
        if not paths:
            return 0.0

        if len(paths) == 1:
            return paths[0].confidence.overall

        # Calculate variance in confidence scores
        confidences = [p.confidence.overall for p in paths]
        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)

        # Lower variance = higher consensus confidence
        # Map variance [0, 0.25] to confidence boost [1.0, 0.5]
        variance_penalty = min(variance * 2, 0.5)
        consensus_boost = 1.0 - variance_penalty

        return mean_conf * consensus_boost


@dataclass
class Checkpoint:
    """A checkpoint of agent state for rollback."""
    id: str
    timestamp: datetime
    context_snapshot: Dict[str, Any]
    memory_snapshot: Dict[str, Any]
    trigger: str  # What caused this checkpoint

    @classmethod
    def create(
        cls,
        context: Any,
        memory: Any,
        trigger: str,
    ) -> "Checkpoint":
        """Create a checkpoint from current state."""
        checkpoint_id = hashlib.sha256(
            f"{datetime.utcnow().isoformat()}{trigger}".encode()
        ).hexdigest()[:16]

        return cls(
            id=checkpoint_id,
            timestamp=datetime.utcnow(),
            context_snapshot=context.to_dict() if hasattr(context, 'to_dict') else {},
            memory_snapshot=memory.to_dict() if hasattr(memory, 'to_dict') else {},
            trigger=trigger,
        )


class CheckpointManager:
    """
    Manages checkpoints for rollback capability.

    Since agents are fallible, we need the ability to
    revert to known-good states.
    """

    def __init__(
        self,
        max_checkpoints: int = 20,
        max_age_hours: int = 24,
    ):
        self.max_checkpoints = max_checkpoints
        self.max_age_hours = max_age_hours
        self.checkpoints: List[Checkpoint] = []

    def create_checkpoint(
        self,
        context: Any,
        memory: Any,
        trigger: str,
    ) -> Checkpoint:
        """Create and store a new checkpoint."""
        checkpoint = Checkpoint.create(context, memory, trigger)
        self.checkpoints.append(checkpoint)

        # Enforce max checkpoints
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints = self.checkpoints[-self.max_checkpoints:]

        return checkpoint

    def get_latest(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint."""
        if self.checkpoints:
            return self.checkpoints[-1]
        return None

    def get_by_id(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a specific checkpoint by ID."""
        for cp in self.checkpoints:
            if cp.id == checkpoint_id:
                return cp
        return None

    def rollback_to(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Rollback to a specific checkpoint.

        Returns the checkpoint if found, removes all later checkpoints.
        """
        for i, cp in enumerate(self.checkpoints):
            if cp.id == checkpoint_id:
                # Remove all checkpoints after this one
                self.checkpoints = self.checkpoints[: i + 1]
                return cp
        return None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints with metadata."""
        return [
            {
                "id": cp.id,
                "timestamp": cp.timestamp.isoformat(),
                "trigger": cp.trigger,
            }
            for cp in self.checkpoints
        ]
