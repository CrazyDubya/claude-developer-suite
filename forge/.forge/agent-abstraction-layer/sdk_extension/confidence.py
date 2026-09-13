"""
Confidence Estimation for AAL.

Since AI agents are stochastic, every output should carry confidence metadata.
This module provides heuristics for estimating output confidence.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class ConfidenceScore:
    """
    A structured confidence score with interpretable components.

    Confidence isn't a single number - it's composed of multiple factors.
    """
    overall: float  # 0.0 - 1.0

    # Component scores
    linguistic_certainty: float = 0.0  # Based on language patterns
    grounding_score: float = 0.0  # How well grounded in context
    consistency_score: float = 0.0  # Consistency with prior responses
    tool_reliability: float = 0.0  # Reliability of tools used

    # Metadata
    reasoning: str = ""
    uncertainty_sources: List[str] = field(default_factory=list)

    def is_actionable(self, threshold: float = 0.7) -> bool:
        """Is confidence high enough to act without confirmation?"""
        return self.overall >= threshold

    def needs_review(self, threshold: float = 0.5) -> bool:
        """Does this need human review?"""
        return self.overall < threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "components": {
                "linguistic_certainty": self.linguistic_certainty,
                "grounding_score": self.grounding_score,
                "consistency_score": self.consistency_score,
                "tool_reliability": self.tool_reliability,
            },
            "reasoning": self.reasoning,
            "uncertainty_sources": self.uncertainty_sources,
        }


class ConfidenceEstimator:
    """
    Estimates confidence in agent outputs.

    Uses multiple heuristics since we can't directly access model uncertainty:
    - Linguistic markers (hedging language, certainty indicators)
    - Context grounding (references to provided context)
    - Tool usage patterns (reliable tools vs. web search)
    - Response consistency (if exploring multiple paths)
    """

    # Hedging phrases indicate lower confidence
    HEDGING_PATTERNS = [
        r"\bmight\b",
        r"\bperhaps\b",
        r"\bpossibly\b",
        r"\bcould be\b",
        r"\bI think\b",
        r"\bI believe\b",
        r"\bnot sure\b",
        r"\buncertain\b",
        r"\bmaybe\b",
        r"\bprobably\b",
        r"\bit seems\b",
        r"\bappears to\b",
    ]

    # Certainty phrases indicate higher confidence
    CERTAINTY_PATTERNS = [
        r"\bdefinitely\b",
        r"\bcertainly\b",
        r"\bclearly\b",
        r"\bobviously\b",
        r"\bwithout doubt\b",
        r"\bI am confident\b",
        r"\bthis is\b",
        r"\bthe answer is\b",
    ]

    # Tool reliability scores
    TOOL_RELIABILITY = {
        "Read": 0.95,  # Reading files is reliable
        "Glob": 0.95,
        "Grep": 0.90,
        "Edit": 0.85,  # Edits can fail
        "Write": 0.85,
        "Bash": 0.75,  # Commands can fail
        "WebSearch": 0.60,  # Web results are uncertain
        "WebFetch": 0.65,
        "Task": 0.70,  # Subagent results vary
    }

    def __init__(self):
        self.response_history: List[str] = []
        self.confidence_history: List[float] = []
        self._compile_patterns()

    def _compile_patterns(self):
        self.hedging_re = [re.compile(p, re.IGNORECASE) for p in self.HEDGING_PATTERNS]
        self.certainty_re = [re.compile(p, re.IGNORECASE) for p in self.CERTAINTY_PATTERNS]

    def estimate(
        self,
        prompt: str,
        response: str,
        tool_calls: List[Dict[str, Any]],
        context: Optional[str] = None,
        degraded: bool = False,
    ) -> ConfidenceScore:
        """
        Estimate confidence in a response.

        Args:
            prompt: The original user prompt
            response: The agent's response
            tool_calls: Tools used in generating the response
            context: Optional context that was provided
            degraded: Whether this was a degraded response

        Returns:
            ConfidenceScore with overall and component scores
        """
        uncertainty_sources = []

        # 1. Linguistic certainty analysis
        linguistic = self._analyze_linguistic_certainty(response)
        if linguistic < 0.5:
            uncertainty_sources.append("hedging_language")

        # 2. Context grounding
        grounding = self._analyze_grounding(response, context) if context else 0.7
        if grounding < 0.5:
            uncertainty_sources.append("weak_grounding")

        # 3. Tool reliability
        tool_reliability = self._analyze_tool_reliability(tool_calls)
        if tool_reliability < 0.7:
            uncertainty_sources.append("unreliable_tools")

        # 4. Consistency with history
        consistency = self._analyze_consistency(response)
        if consistency < 0.6:
            uncertainty_sources.append("inconsistent_with_history")

        # Calculate overall score (weighted average)
        weights = {
            "linguistic": 0.25,
            "grounding": 0.30,
            "tool": 0.25,
            "consistency": 0.20,
        }

        overall = (
            linguistic * weights["linguistic"]
            + grounding * weights["grounding"]
            + tool_reliability * weights["tool"]
            + consistency * weights["consistency"]
        )

        # Penalty for degraded mode
        if degraded:
            overall *= 0.8
            uncertainty_sources.append("degraded_mode")

        # Update history
        self.response_history.append(response[:500])
        self.confidence_history.append(overall)

        # Keep history bounded
        if len(self.response_history) > 20:
            self.response_history = self.response_history[-20:]
            self.confidence_history = self.confidence_history[-20:]

        return ConfidenceScore(
            overall=overall,
            linguistic_certainty=linguistic,
            grounding_score=grounding,
            consistency_score=consistency,
            tool_reliability=tool_reliability,
            uncertainty_sources=uncertainty_sources,
            reasoning=self._generate_reasoning(overall, uncertainty_sources),
        )

    def estimate_partial(
        self,
        prompt: str,
        partial_response: str,
        completion_ratio: float,
    ) -> ConfidenceScore:
        """Estimate confidence for a partial (streaming) response."""
        # For partial responses, we can only use linguistic analysis
        linguistic = self._analyze_linguistic_certainty(partial_response)

        # Confidence increases as response completes (more context)
        overall = linguistic * (0.5 + 0.5 * completion_ratio)

        return ConfidenceScore(
            overall=overall,
            linguistic_certainty=linguistic,
            reasoning=f"Partial response ({completion_ratio:.0%} complete)",
        )

    def _analyze_linguistic_certainty(self, text: str) -> float:
        """Analyze hedging vs certainty language."""
        if not text:
            return 0.5

        hedging_count = sum(
            len(pattern.findall(text)) for pattern in self.hedging_re
        )
        certainty_count = sum(
            len(pattern.findall(text)) for pattern in self.certainty_re
        )

        # Normalize by text length (per 100 words)
        word_count = len(text.split())
        if word_count == 0:
            return 0.5

        hedging_rate = hedging_count / (word_count / 100)
        certainty_rate = certainty_count / (word_count / 100)

        # Convert to confidence score
        # More hedging = lower confidence, more certainty = higher confidence
        base = 0.7
        adjustment = (certainty_rate - hedging_rate) * 0.1
        score = max(0.1, min(0.95, base + adjustment))

        return score

    def _analyze_grounding(self, response: str, context: str) -> float:
        """Analyze how well response is grounded in context."""
        if not context:
            return 0.7

        # Extract key terms from context
        context_words = set(
            word.lower() for word in re.findall(r'\b\w{4,}\b', context)
        )
        response_words = set(
            word.lower() for word in re.findall(r'\b\w{4,}\b', response)
        )

        if not context_words:
            return 0.7

        # Calculate overlap
        overlap = len(context_words & response_words)
        grounding_ratio = overlap / len(context_words)

        # Map to confidence (0.5-0.95 range)
        return 0.5 + grounding_ratio * 0.45

    def _analyze_tool_reliability(self, tool_calls: List[Dict[str, Any]]) -> float:
        """Analyze reliability of tools used."""
        if not tool_calls:
            return 0.8  # No tools = moderate confidence

        reliabilities = []
        for call in tool_calls:
            tool_name = call.get("name", "")
            reliability = self.TOOL_RELIABILITY.get(tool_name, 0.7)
            reliabilities.append(reliability)

        # Overall is the minimum (weakest link)
        return min(reliabilities) if reliabilities else 0.7

    def _analyze_consistency(self, response: str) -> float:
        """Analyze consistency with previous responses."""
        if len(self.response_history) < 2:
            return 0.8  # Not enough history

        # Simple consistency: are we contradicting ourselves?
        # This is a simplified heuristic
        recent = self.response_history[-5:]

        # Check for contradiction patterns
        contradictions = 0
        for prev in recent:
            if self._seems_contradictory(prev, response):
                contradictions += 1

        # More contradictions = lower consistency
        if contradictions == 0:
            return 0.9
        elif contradictions == 1:
            return 0.7
        else:
            return 0.5

    def _seems_contradictory(self, text1: str, text2: str) -> bool:
        """Simple heuristic for detecting contradictions."""
        # Look for negation patterns
        negation_pairs = [
            ("is not", "is"),
            ("cannot", "can"),
            ("won't", "will"),
            ("doesn't", "does"),
            ("incorrect", "correct"),
            ("wrong", "right"),
        ]

        text1_lower = text1.lower()
        text2_lower = text2.lower()

        for neg, pos in negation_pairs:
            if neg in text1_lower and pos in text2_lower:
                return True
            if pos in text1_lower and neg in text2_lower:
                return True

        return False

    def _generate_reasoning(
        self,
        overall: float,
        uncertainty_sources: List[str],
    ) -> str:
        """Generate human-readable reasoning for the confidence score."""
        if overall >= 0.8:
            level = "high"
        elif overall >= 0.5:
            level = "moderate"
        else:
            level = "low"

        reasoning = f"Confidence is {level} ({overall:.2f})."

        if uncertainty_sources:
            reasons = ", ".join(s.replace("_", " ") for s in uncertainty_sources)
            reasoning += f" Uncertainty from: {reasons}."

        return reasoning

    @property
    def running_average(self) -> float:
        """Get running average confidence."""
        if not self.confidence_history:
            return 0.0
        return sum(self.confidence_history) / len(self.confidence_history)
