"""
Agent Runtime for the Agent Abstraction Layer.

The runtime is where all the abstractions come together to
actually execute an agent. It orchestrates:
- Entity lifecycle
- Context management
- Permission enforcement
- Uncertainty handling
- Error recovery
- Observability

This is the main entry point for running agents with AAL.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from .primitives import (
    AgentEntity,
    AgentContext,
    AgentPermissions,
    AgentMemory,
    AgentOutput,
    PermissionLevel,
)
from .uncertainty import (
    ConfidenceScore,
    UncertaintyType,
    ExplorationConfig,
    ExplorationStrategy,
    MultiPathExplorer,
    CheckpointManager,
)
from .fallibility import (
    ErrorClassification,
    ErrorSeverity,
    RecoveryAction,
    DegradationLadder,
    HumanLoop,
    HumanLoopConfig,
    RetryPolicy,
)
from .observability import (
    SpanKind,
    DecisionType,
    Tracer,
)
from .manifest import AgentManifest


@dataclass
class InvocationRequest:
    """A request to invoke an agent."""
    input: str
    session_id: str
    mode: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvocationResult:
    """The result of an agent invocation."""
    output: AgentOutput
    trace_id: str
    session_id: str
    duration_ms: float
    degradation_level: str
    checkpoints_created: int
    human_escalations: int
    errors_recovered: int


class AgentRuntime:
    """
    The main runtime for executing agents.

    This orchestrates all the AAL abstractions to provide
    a coherent execution environment for AI agents.
    """

    def __init__(
        self,
        manifest: AgentManifest,
        model_executor: Callable[[str, List[Dict[str, str]], float], Tuple[str, float]],
    ):
        """
        Initialize the runtime.

        Args:
            manifest: The agent manifest
            model_executor: Function that actually calls the model.
                           Takes (system_prompt, messages, temperature)
                           Returns (response, confidence)
        """
        self.manifest = manifest
        self.model_executor = model_executor

        # Initialize core components from manifest
        self._init_entity()
        self._init_permissions()
        self._init_memory()

        # Initialize runtime components
        self.degradation_ladder = DegradationLadder()
        self.checkpoint_manager = CheckpointManager()
        self.human_loop = HumanLoop(HumanLoopConfig(
            confidence_threshold=manifest.uncertainty.confidence_threshold if manifest.uncertainty else 0.4,
        ))
        self.retry_policy = RetryPolicy()

        # Session management
        self.sessions: Dict[str, AgentContext] = {}
        self.tracers: Dict[str, Tracer] = {}

        # Statistics
        self.total_invocations = 0
        self.total_errors = 0
        self.total_escalations = 0

    def _init_entity(self) -> None:
        """Initialize the agent entity from manifest."""
        entity_spec = self.manifest.entity
        self.entity = AgentEntity(
            id=self.manifest.metadata.id,
            version=self.manifest.metadata.version,
            model=entity_spec.model if entity_spec else "claude-sonnet-4-20250514",
            confidence_threshold=entity_spec.confidence_threshold if entity_spec else 0.7,
            fallback_agent_id=entity_spec.fallback_agent_id if entity_spec else None,
        )

    def _init_permissions(self) -> None:
        """Initialize permissions from manifest."""
        perm_spec = self.manifest.permissions
        self.permissions = AgentPermissions()

        if perm_spec:
            self.permissions.allowed_tools = set(perm_spec.allowed_tools)
            self.permissions.denied_tools = set(perm_spec.denied_tools)
            self.permissions.approval_required_tools = set(perm_spec.approval_required_tools)
            self.permissions.resources.max_tokens_per_turn = perm_spec.max_tokens_per_turn
            self.permissions.resources.max_cost_per_session_usd = perm_spec.max_cost_per_session_usd

    def _init_memory(self) -> None:
        """Initialize memory system from manifest."""
        ctx_spec = self.manifest.context
        self.memory = AgentMemory(
            episodic_enabled=ctx_spec.episodic_memory if ctx_spec else True,
            semantic_enabled=ctx_spec.semantic_memory if ctx_spec else True,
            episodic_retention_days=ctx_spec.memory_retention_days if ctx_spec else 30,
        )

    def get_or_create_session(self, session_id: str) -> AgentContext:
        """Get or create a session context."""
        if session_id not in self.sessions:
            ctx_spec = self.manifest.context
            self.sessions[session_id] = AgentContext(
                max_messages=ctx_spec.max_messages if ctx_spec else 50,
                system_prompt=ctx_spec.system_prompt or "",
            )
        return self.sessions[session_id]

    def get_or_create_tracer(self, session_id: str) -> Tracer:
        """Get or create a tracer for a session."""
        if session_id not in self.tracers:
            self.tracers[session_id] = Tracer(
                agent_id=self.entity.id,
                session_id=session_id,
            )
        return self.tracers[session_id]

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        """
        Invoke the agent.

        This is the main entry point that orchestrates all the
        AAL components to process a request.
        """
        start_time = datetime.utcnow()
        self.total_invocations += 1
        self.entity.record_invocation()

        # Get session and tracer
        context = self.get_or_create_session(request.session_id)
        tracer = self.get_or_create_tracer(request.session_id)

        # Start trace
        main_span = tracer.start_span("agent_invocation", SpanKind.AGENT_TURN)
        main_span.set_attribute("input_length", len(request.input))
        main_span.set_attribute("mode", request.mode)

        # Track metrics for result
        checkpoints_created = 0
        human_escalations = 0
        errors_recovered = 0

        try:
            # Add user message to context
            context.add_message("user", request.input)

            # Create checkpoint before processing
            self.checkpoint_manager.create_checkpoint(
                context, self.memory, "pre_invocation"
            )
            checkpoints_created += 1

            # Get mode configuration
            mode = self._get_mode(request.mode)

            # Execute with uncertainty handling
            output = self._execute_with_uncertainty(
                context=context,
                tracer=tracer,
                temperature=mode.get("temperature", 1.0),
            )

            # Check if we need human escalation
            if output.needs_human_review(self.entity.confidence_threshold):
                tracer.log_decision(
                    decision_type=DecisionType.ESCALATION,
                    context=f"Low confidence output: {output.confidence:.2f}",
                    choice="escalate_to_human",
                    alternatives=["proceed_anyway", "retry"],
                    confidence=output.confidence,
                )

                if self.human_loop.should_escalate(
                    confidence=output.confidence,
                    cost_usd=output.cost_usd,
                    action="respond",
                ):
                    human_escalations += 1
                    self.total_escalations += 1
                    # In a real implementation, this would block for human input
                    # For now, we proceed with the low confidence output

            # Add assistant message to context
            context.add_message("assistant", output.content)

            # Record to memory
            self.memory.record_episode(
                event_type="invocation",
                data={
                    "input": request.input[:500],
                    "output": output.content[:500],
                    "confidence": output.confidence,
                },
                importance=output.confidence,
            )

            # Record completion for drift detection
            tracer.record_completion(
                response_length=len(output.content),
                latency_ms=output.latency_ms,
                tools_used=[tc.get("name", "") for tc in output.tool_calls],
                input_tokens=output.input_tokens,
                output_tokens=output.output_tokens,
                confidence=output.confidence,
            )

            # End span successfully
            main_span.set_attribute("output_length", len(output.content))
            main_span.set_attribute("confidence", output.confidence)
            tracer.end_span("ok")

        except Exception as e:
            self.total_errors += 1

            # Classify and attempt recovery
            error = self._classify_error(e)
            errors_recovered += self._attempt_recovery(error, context, tracer)

            # End span with error
            tracer.end_span("error", str(e))

            # Create error output
            output = AgentOutput(
                content=f"Error: {str(e)}",
                confidence=0.0,
                uncertainty_type="epistemic",
            )

        # Calculate duration
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        # End trace
        trace = tracer.end_trace()

        return InvocationResult(
            output=output,
            trace_id=trace.id,
            session_id=request.session_id,
            duration_ms=duration_ms,
            degradation_level=self.degradation_ladder.get_current_level().name,
            checkpoints_created=checkpoints_created,
            human_escalations=human_escalations,
            errors_recovered=errors_recovered,
        )

    def _get_mode(self, mode_name: str) -> Dict[str, Any]:
        """Get mode configuration."""
        if mode_name in self.manifest.modes:
            mode = self.manifest.modes[mode_name]
            return {
                "temperature": mode.temperature,
                "max_tokens": mode.max_tokens,
                "tools_enabled": mode.tools_enabled,
                "require_confirmation": mode.require_confirmation,
            }
        return {"temperature": 1.0, "max_tokens": 4096, "tools_enabled": True}

    def _execute_with_uncertainty(
        self,
        context: AgentContext,
        tracer: Tracer,
        temperature: float,
    ) -> AgentOutput:
        """Execute with uncertainty handling."""
        uncertainty_spec = self.manifest.uncertainty

        # Determine exploration strategy
        if uncertainty_spec and uncertainty_spec.exploration_strategy != "single":
            return self._execute_with_exploration(context, tracer, uncertainty_spec)
        else:
            return self._execute_single(context, tracer, temperature)

    def _execute_single(
        self,
        context: AgentContext,
        tracer: Tracer,
        temperature: float,
    ) -> AgentOutput:
        """Execute a single model call."""
        span = tracer.start_span("model_call", SpanKind.AGENT_TURN)

        try:
            start_time = datetime.utcnow()

            # Call the model
            response, confidence = self.model_executor(
                context.system_prompt,
                context.get_messages_for_api(),
                temperature,
            )

            end_time = datetime.utcnow()
            latency_ms = (end_time - start_time).total_seconds() * 1000

            # Create output
            output = AgentOutput(
                content=response,
                confidence=confidence,
                model=self.entity.model,
                latency_ms=latency_ms,
            )

            # Log the decision
            tracer.log_decision(
                decision_type=DecisionType.RESPONSE_FORMULATION,
                context="Single execution",
                choice=response[:100] + "...",
                alternatives=[],
                confidence=confidence,
            )

            span.set_attribute("confidence", confidence)
            span.set_attribute("latency_ms", latency_ms)
            tracer.end_span("ok")

            return output

        except Exception as e:
            tracer.end_span("error", str(e))
            raise

    def _execute_with_exploration(
        self,
        context: AgentContext,
        tracer: Tracer,
        uncertainty_spec: Any,
    ) -> AgentOutput:
        """Execute with multi-path exploration."""
        span = tracer.start_span("exploration", SpanKind.AGENT_TURN)

        strategy = ExplorationStrategy.BEAM_SEARCH
        if uncertainty_spec.exploration_strategy == "monte_carlo":
            strategy = ExplorationStrategy.MONTE_CARLO

        config = ExplorationConfig(
            strategy=strategy,
            beam_width=uncertainty_spec.beam_width,
            mc_samples=uncertainty_spec.mc_samples,
        )

        explorer = MultiPathExplorer(config)

        def generator(temp: float) -> Tuple[str, ConfidenceScore]:
            response, confidence = self.model_executor(
                context.system_prompt,
                context.get_messages_for_api(),
                temp,
            )
            score = ConfidenceScore(overall=confidence)
            return response, score

        result = explorer.explore(generator)

        # Log the exploration
        tracer.log_decision(
            decision_type=DecisionType.PATH_SELECTION,
            context=f"Explored {len(result.paths)} paths",
            choice=result.selected_path.content[:100] + "...",
            alternatives=[p.content[:50] + "..." for p in result.paths if p.id != result.selected_path.id],
            confidence=result.consensus_confidence,
        )

        span.set_attribute("paths_explored", len(result.paths))
        span.set_attribute("consensus_confidence", result.consensus_confidence)
        tracer.end_span("ok")

        return AgentOutput(
            content=result.selected_path.content,
            confidence=result.consensus_confidence,
            alternatives=[p.content for p in result.paths if p.id != result.selected_path.id],
            model=self.entity.model,
        )

    def _classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error for appropriate handling."""
        error_str = str(error).lower()

        if "rate limit" in error_str:
            return ErrorClassification.rate_limit()
        elif "timeout" in error_str:
            return ErrorClassification.timeout()
        elif "context" in error_str and ("overflow" in error_str or "length" in error_str):
            return ErrorClassification.context_overflow()
        elif "auth" in error_str:
            return ErrorClassification.auth_failure()
        else:
            return ErrorClassification(
                error_type="unknown",
                severity=ErrorSeverity.RECOVERABLE,
                recovery_action=RecoveryAction.RETRY,
                message=str(error),
            )

    def _attempt_recovery(
        self,
        error: ErrorClassification,
        context: AgentContext,
        tracer: Tracer,
    ) -> int:
        """Attempt to recover from an error. Returns count of successful recoveries."""
        tracer.log_decision(
            decision_type=DecisionType.ERROR_HANDLING,
            context=f"Error: {error.message}",
            choice=error.recovery_action.value,
            alternatives=["halt", "degrade", "escalate"],
            confidence=0.5,
        )

        if error.severity == ErrorSeverity.FATAL:
            return 0

        # Try degradation
        if error.severity == ErrorSeverity.DEGRADABLE:
            new_level = self.degradation_ladder.descend()
            if new_level:
                return 1

        # Rollback if possible
        checkpoint = self.checkpoint_manager.get_latest()
        if checkpoint:
            return 1

        return 0

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session."""
        if session_id not in self.sessions:
            return {}

        context = self.sessions[session_id]
        tracer = self.tracers.get(session_id)

        return {
            "message_count": len(context.messages),
            "working_memory_items": len(context.working_memory),
            "trace_spans": len(tracer.current_trace.spans) if tracer else 0,
            "decisions_logged": len(tracer.decision_log.entries) if tracer else 0,
        }

    def get_runtime_stats(self) -> Dict[str, Any]:
        """Get overall runtime statistics."""
        return {
            "agent_id": self.entity.get_qualified_id(),
            "total_invocations": self.total_invocations,
            "total_errors": self.total_errors,
            "total_escalations": self.total_escalations,
            "error_rate": self.total_errors / max(1, self.total_invocations),
            "escalation_rate": self.total_escalations / max(1, self.total_invocations),
            "active_sessions": len(self.sessions),
            "current_degradation_level": self.degradation_ladder.get_current_level().name,
        }


def create_runtime_from_manifest(
    manifest_path: str,
    model_executor: Callable[[str, List[Dict[str, str]], float], Tuple[str, float]],
) -> AgentRuntime:
    """
    Create an agent runtime from a manifest file.

    Args:
        manifest_path: Path to the manifest file
        model_executor: Function to execute model calls

    Returns:
        Configured AgentRuntime
    """
    manifest = AgentManifest.from_file(manifest_path)

    # Validate manifest
    errors = manifest.validate()
    if errors:
        raise ValueError(f"Invalid manifest: {errors}")

    return AgentRuntime(manifest, model_executor)
