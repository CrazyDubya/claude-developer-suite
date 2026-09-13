"""
Multi-Path Exploration for AAL.

When confidence is low or the task is complex, explore multiple
possible outputs and select based on consensus/confidence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio
import hashlib

from .confidence import ConfidenceScore


class ExplorationStrategy(Enum):
    """Strategies for exploring multiple paths."""
    SINGLE = "single"  # No exploration
    BEAM_SEARCH = "beam_search"  # Multiple temps, prune low confidence
    MONTE_CARLO = "monte_carlo"  # Random sampling
    PARALLEL = "parallel"  # Run multiple prompts in parallel


@dataclass
class ExplorationConfig:
    """Configuration for path exploration."""
    strategy: str = "beam_search"
    beam_width: int = 3
    prune_threshold: float = 0.3
    temperature_range: Tuple[float, float] = (0.3, 1.0)
    max_parallel: int = 3
    timeout_seconds: float = 30.0


@dataclass
class ExploredPath:
    """A single explored path."""
    id: str
    content: str
    confidence: ConfidenceScore
    temperature: float
    duration_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content: str,
        confidence: ConfidenceScore,
        temperature: float,
        duration_ms: float,
    ) -> "ExploredPath":
        path_id = hashlib.sha256(
            f"{content[:100]}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]
        return cls(
            id=path_id,
            content=content,
            confidence=confidence,
            temperature=temperature,
            duration_ms=duration_ms,
        )


@dataclass
class ExplorationResult:
    """Result of multi-path exploration."""
    paths: List[ExploredPath]
    selected_path: ExploredPath
    consensus_confidence: ConfidenceScore
    strategy_used: str
    total_duration_ms: float

    @property
    def selected_content(self) -> str:
        return self.selected_path.content

    @property
    def alternatives(self) -> List[str]:
        return [
            p.content for p in self.paths
            if p.id != self.selected_path.id
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paths_explored": len(self.paths),
            "selected_id": self.selected_path.id,
            "consensus_confidence": self.consensus_confidence.overall,
            "strategy": self.strategy_used,
            "duration_ms": self.total_duration_ms,
            "alternatives_count": len(self.alternatives),
        }


class PathExplorer:
    """
    Explores multiple output paths for uncertain situations.

    Rather than taking a single sample, this explores the output
    distribution and selects based on confidence/consensus.
    """

    def __init__(self, config: ExplorationConfig):
        self.config = config

    async def explore(
        self,
        generator: Callable[[float], tuple],
    ) -> ExplorationResult:
        """
        Explore multiple paths.

        Args:
            generator: Async function that takes temperature and returns
                      (content, confidence) tuple

        Returns:
            ExplorationResult with all paths and selected best
        """
        start_time = datetime.utcnow()

        if self.config.strategy == "single":
            paths = await self._single(generator)
        elif self.config.strategy == "beam_search":
            paths = await self._beam_search(generator)
        elif self.config.strategy == "monte_carlo":
            paths = await self._monte_carlo(generator)
        elif self.config.strategy == "parallel":
            paths = await self._parallel(generator)
        else:
            paths = await self._single(generator)

        # Select best path
        selected = self._select_best(paths)

        # Calculate consensus confidence
        consensus = self._calculate_consensus(paths, selected)

        duration = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ExplorationResult(
            paths=paths,
            selected_path=selected,
            consensus_confidence=consensus,
            strategy_used=self.config.strategy,
            total_duration_ms=duration,
        )

    async def _single(
        self,
        generator: Callable,
    ) -> List[ExploredPath]:
        """Single path - no exploration."""
        start = datetime.utcnow()
        content, confidence = await generator(1.0)
        duration = (datetime.utcnow() - start).total_seconds() * 1000

        return [ExploredPath.create(content, confidence, 1.0, duration)]

    async def _beam_search(
        self,
        generator: Callable,
    ) -> List[ExploredPath]:
        """Beam search with temperature variation."""
        paths = []
        temp_min, temp_max = self.config.temperature_range
        temp_step = (temp_max - temp_min) / (self.config.beam_width - 1)

        for i in range(self.config.beam_width):
            temp = temp_min + i * temp_step
            start = datetime.utcnow()

            try:
                content, confidence = await asyncio.wait_for(
                    generator(temp),
                    timeout=self.config.timeout_seconds,
                )
                duration = (datetime.utcnow() - start).total_seconds() * 1000

                # Prune low confidence
                if confidence.overall >= self.config.prune_threshold:
                    paths.append(ExploredPath.create(
                        content, confidence, temp, duration
                    ))
            except asyncio.TimeoutError:
                continue

        # Ensure at least one path
        if not paths:
            start = datetime.utcnow()
            content, confidence = await generator(1.0)
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            paths.append(ExploredPath.create(content, confidence, 1.0, duration))

        return paths

    async def _monte_carlo(
        self,
        generator: Callable,
    ) -> List[ExploredPath]:
        """Random temperature sampling."""
        import random
        paths = []
        temp_min, temp_max = self.config.temperature_range

        for _ in range(self.config.beam_width):
            temp = random.uniform(temp_min, temp_max)
            start = datetime.utcnow()

            try:
                content, confidence = await asyncio.wait_for(
                    generator(temp),
                    timeout=self.config.timeout_seconds,
                )
                duration = (datetime.utcnow() - start).total_seconds() * 1000
                paths.append(ExploredPath.create(
                    content, confidence, temp, duration
                ))
            except asyncio.TimeoutError:
                continue

        return paths if paths else await self._single(generator)

    async def _parallel(
        self,
        generator: Callable,
    ) -> List[ExploredPath]:
        """Run multiple generations in parallel."""
        temp_min, temp_max = self.config.temperature_range
        temps = [
            temp_min + i * (temp_max - temp_min) / (self.config.max_parallel - 1)
            for i in range(self.config.max_parallel)
        ]

        async def run_one(temp: float) -> Optional[ExploredPath]:
            start = datetime.utcnow()
            try:
                content, confidence = await asyncio.wait_for(
                    generator(temp),
                    timeout=self.config.timeout_seconds,
                )
                duration = (datetime.utcnow() - start).total_seconds() * 1000
                return ExploredPath.create(content, confidence, temp, duration)
            except asyncio.TimeoutError:
                return None

        results = await asyncio.gather(*[run_one(t) for t in temps])
        paths = [r for r in results if r is not None]

        return paths if paths else await self._single(generator)

    def _select_best(self, paths: List[ExploredPath]) -> ExploredPath:
        """Select the best path based on confidence."""
        if not paths:
            raise ValueError("No paths to select from")
        return max(paths, key=lambda p: p.confidence.overall)

    def _calculate_consensus(
        self,
        paths: List[ExploredPath],
        selected: ExploredPath,
    ) -> ConfidenceScore:
        """Calculate consensus confidence across all paths."""
        if len(paths) == 1:
            return selected.confidence

        # Calculate variance in confidences
        confidences = [p.confidence.overall for p in paths]
        mean = sum(confidences) / len(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)

        # Lower variance = higher consensus = confidence boost
        consensus_factor = 1.0 - min(variance * 2, 0.3)

        return ConfidenceScore(
            overall=selected.confidence.overall * consensus_factor,
            reasoning=f"Consensus from {len(paths)} paths (variance: {variance:.3f})",
        )
