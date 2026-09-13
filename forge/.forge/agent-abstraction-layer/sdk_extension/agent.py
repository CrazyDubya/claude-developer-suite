"""
AALAgent - The Claude Agent SDK wrapper with AAL capabilities.

This is the main entry point for running agents with uncertainty handling,
fallibility recovery, and observability built in.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
import asyncio
import json

# These would be actual imports from claude-agent-sdk
# from claude_agent_sdk import query, ClaudeAgentOptions
# For now, we define the interface

from ..core.manifest import AgentManifest
from .confidence import ConfidenceEstimator, ConfidenceScore
from .explorer import PathExplorer, ExplorationConfig, ExplorationResult
from .degradation import DegradationManager, DegradationLevel
from .drift import DriftDetector
from .hooks import AALHookManager


@dataclass
class AALAgentOptions:
    """Extended options for AAL-wrapped agents."""
    # Standard SDK options
    permission_mode: str = "strict"
    allowed_tools: List[str] = field(default_factory=list)
    disallowed_tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    max_tokens: int = 8192

    # AAL extensions
    confidence_threshold: float = 0.7
    enable_exploration: bool = True
    exploration_config: Optional[ExplorationConfig] = None
    enable_drift_detection: bool = True
    enable_degradation: bool = True


@dataclass
class AALResponse:
    """Response from an AAL-wrapped agent invocation."""
    content: str
    confidence: ConfidenceScore
    exploration_result: Optional[ExplorationResult] = None
    degradation_level: DegradationLevel = DegradationLevel.FULL
    drift_detected: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AALAgent:
    """
    An agent wrapped with AAL capabilities.

    Extends the Claude Agent SDK with:
    - Confidence estimation on outputs
    - Multi-path exploration for uncertain situations
    - Graceful degradation when things fail
    - Behavioral drift detection
    - Enhanced observability

    Example:
        manifest = load_manifest("agent.manifest.yaml")
        agent = AALAgent(manifest)

        async for response in agent.stream("Analyze this code"):
            print(response.content)
            if response.confidence.overall < 0.5:
                print("Low confidence - consider reviewing")
    """

    def __init__(
        self,
        manifest: AgentManifest,
        options: Optional[AALAgentOptions] = None,
    ):
        self.manifest = manifest
        self.options = options or self._options_from_manifest(manifest)

        # Initialize AAL components
        self.confidence_estimator = ConfidenceEstimator()
        self.path_explorer = PathExplorer(
            self.options.exploration_config or ExplorationConfig()
        )
        self.degradation_manager = DegradationManager()
        self.drift_detector = DriftDetector(
            threshold=manifest.observability.drift_threshold
            if manifest.observability else 0.15
        )
        self.hook_manager = AALHookManager(manifest.hooks if manifest.hooks else None)

        # Session state
        self.session_id: Optional[str] = None
        self.invocation_count = 0
        self.total_tokens = 0

    def _options_from_manifest(self, manifest: AgentManifest) -> AALAgentOptions:
        """Create options from manifest specification."""
        options = AALAgentOptions()

        if manifest.permissions:
            options.allowed_tools = list(manifest.permissions.allowed_tools)
            options.disallowed_tools = list(manifest.permissions.denied_tools)

        if manifest.uncertainty:
            options.confidence_threshold = manifest.uncertainty.confidence_threshold
            options.enable_exploration = manifest.uncertainty.exploration_strategy != "single"
            options.exploration_config = ExplorationConfig(
                strategy=manifest.uncertainty.exploration_strategy,
                beam_width=manifest.uncertainty.beam_width,
            )

        if manifest.observability:
            options.enable_drift_detection = manifest.observability.fingerprinting_enabled

        return options

    async def run(self, prompt: str, **kwargs) -> AALResponse:
        """
        Run the agent on a prompt, returning a single response.

        This is the main entry point for single-shot execution.
        Uses exploration if confidence is uncertain.
        """
        start_time = datetime.utcnow()
        self.invocation_count += 1

        # Pre-input hooks
        processed_prompt = await self.hook_manager.run_pre_input(prompt)

        # Determine if we should explore multiple paths
        should_explore = (
            self.options.enable_exploration
            and self._is_complex_request(processed_prompt)
        )

        if should_explore:
            result = await self._run_with_exploration(processed_prompt)
        else:
            result = await self._run_single(processed_prompt)

        # Check for drift
        if self.options.enable_drift_detection:
            result.drift_detected = self.drift_detector.check(result)

        # Calculate duration
        end_time = datetime.utcnow()
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        # Post-output hooks
        await self.hook_manager.run_post_output(result)

        return result

    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[AALResponse]:
        """
        Stream responses from the agent.

        Yields partial responses as they're generated.
        Confidence is estimated incrementally.
        """
        start_time = datetime.utcnow()
        self.invocation_count += 1

        # Pre-input hooks
        processed_prompt = await self.hook_manager.run_pre_input(prompt)

        # For streaming, we use single path (exploration doesn't stream well)
        async for chunk in self._stream_single(processed_prompt):
            chunk.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            yield chunk

    async def _run_single(self, prompt: str) -> AALResponse:
        """Run a single path through the agent."""
        try:
            # This is where we'd call the actual SDK
            # response = await query(prompt, options=self._sdk_options())

            # Simulated for now - in real implementation, this calls SDK
            content = await self._call_sdk(prompt)

            # Estimate confidence
            confidence = self.confidence_estimator.estimate(
                prompt=prompt,
                response=content,
                tool_calls=[],
            )

            return AALResponse(
                content=content,
                confidence=confidence,
                degradation_level=self.degradation_manager.current_level,
            )

        except Exception as e:
            # Attempt degradation
            if self.options.enable_degradation:
                return await self._run_degraded(prompt, e)
            raise

    async def _run_with_exploration(self, prompt: str) -> AALResponse:
        """Run with multi-path exploration."""

        async def generate_path(temperature: float) -> tuple:
            """Generate one exploration path."""
            content = await self._call_sdk(prompt, temperature=temperature)
            confidence = self.confidence_estimator.estimate(
                prompt=prompt,
                response=content,
                tool_calls=[],
            )
            return content, confidence

        # Explore multiple paths
        exploration_result = await self.path_explorer.explore(generate_path)

        return AALResponse(
            content=exploration_result.selected_content,
            confidence=exploration_result.consensus_confidence,
            exploration_result=exploration_result,
            degradation_level=self.degradation_manager.current_level,
        )

    async def _run_degraded(self, prompt: str, error: Exception) -> AALResponse:
        """Run with degraded capabilities after an error."""
        # Descend the degradation ladder
        new_level = self.degradation_manager.descend()

        if new_level == DegradationLevel.HUMAN_HANDOFF:
            # We've hit bottom - need human intervention
            return AALResponse(
                content=f"I need human assistance. Error: {error}",
                confidence=ConfidenceScore(overall=0.0),
                degradation_level=new_level,
                metadata={"error": str(error), "needs_human": True},
            )

        # Retry with reduced capabilities
        try:
            content = await self._call_sdk(
                prompt,
                reduced_capabilities=self.degradation_manager.get_restrictions(),
            )

            confidence = self.confidence_estimator.estimate(
                prompt=prompt,
                response=content,
                tool_calls=[],
                degraded=True,
            )

            return AALResponse(
                content=content,
                confidence=confidence,
                degradation_level=new_level,
            )

        except Exception as e2:
            # Recursive degradation
            return await self._run_degraded(prompt, e2)

    async def _stream_single(self, prompt: str) -> AsyncIterator[AALResponse]:
        """Stream a single path."""
        accumulated_content = ""

        # In real implementation, this would stream from SDK
        # async for chunk in query_stream(prompt, options=self._sdk_options()):
        #     accumulated_content += chunk.content
        #     yield AALResponse(...)

        # Simulated streaming
        content = await self._call_sdk(prompt)
        words = content.split()

        for i, word in enumerate(words):
            accumulated_content += word + " "

            # Estimate running confidence
            confidence = self.confidence_estimator.estimate_partial(
                prompt=prompt,
                partial_response=accumulated_content,
                completion_ratio=i / len(words),
            )

            yield AALResponse(
                content=accumulated_content.strip(),
                confidence=confidence,
                degradation_level=self.degradation_manager.current_level,
                metadata={"streaming": True, "complete": i == len(words) - 1},
            )

            await asyncio.sleep(0.01)  # Simulate streaming delay

    async def _call_sdk(
        self,
        prompt: str,
        temperature: float = 1.0,
        reduced_capabilities: Optional[Dict] = None,
    ) -> str:
        """
        Call the actual Claude Agent SDK.

        In real implementation, this would be:
            async for msg in query(prompt, options=self._sdk_options()):
                ...

        For now, we simulate the interface.
        """
        # TODO: Replace with actual SDK call
        # from claude_agent_sdk import query
        #
        # options = ClaudeAgentOptions(
        #     permission_mode=self.options.permission_mode,
        #     allowed_tools=self.options.allowed_tools,
        #     disallowed_tools=self.options.disallowed_tools,
        #     system_prompt=self._get_system_prompt(),
        # )
        #
        # result = []
        # async for message in query(prompt, options=options):
        #     result.append(message.content)
        # return "".join(result)

        # Placeholder - would be replaced with SDK
        return f"[SDK Response to: {prompt[:50]}...]"

    def _is_complex_request(self, prompt: str) -> bool:
        """Heuristic: is this request complex enough to warrant exploration?"""
        complexity_indicators = [
            "architecture",
            "design",
            "implement",
            "refactor",
            "multiple",
            "several",
            "complex",
            "tradeoff",
            "decision",
        ]
        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in complexity_indicators)

    def _get_system_prompt(self) -> str:
        """Build the system prompt from manifest context."""
        parts = []

        if self.manifest.context and self.manifest.context.system_prompt:
            parts.append(self.manifest.context.system_prompt)

        # Add AAL behavioral instructions
        parts.append("""
When responding, internally assess your confidence:
- High confidence (>0.8): Proceed directly
- Medium confidence (0.5-0.8): Note uncertainties
- Low confidence (<0.5): Ask clarifying questions

If you encounter errors, describe what you attempted and suggest alternatives.
""")

        return "\n\n".join(parts)

    def reset_degradation(self) -> None:
        """Reset degradation level to full capability."""
        self.degradation_manager.reset()

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_id": self.manifest.metadata.id,
            "version": self.manifest.metadata.version,
            "invocation_count": self.invocation_count,
            "current_degradation": self.degradation_manager.current_level.value,
            "drift_alerts": len(self.drift_detector.alerts),
            "confidence_avg": self.confidence_estimator.running_average,
        }


async def create_agent(
    manifest_path: str,
    options: Optional[AALAgentOptions] = None,
) -> AALAgent:
    """
    Factory function to create an AAL agent from a manifest file.

    Example:
        agent = await create_agent("agent.manifest.yaml")
        result = await agent.run("Analyze this codebase")
    """
    from .manifest_loader import load_manifest
    manifest = load_manifest(manifest_path)
    return AALAgent(manifest, options)
