"""
Hook System for AAL.

Extends Claude Agent SDK hooks with AAL-specific lifecycle points:
- on_low_confidence: When output confidence is below threshold
- on_drift_detected: When behavioral drift is detected
- on_degradation: When capabilities are reduced
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import asyncio
import importlib.util
import sys
from pathlib import Path


class HookPoint(Enum):
    """Points in the lifecycle where hooks can be attached."""
    # Standard SDK hooks
    PRE_INPUT = "pre_input"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    POST_OUTPUT = "post_output"

    # AAL-specific hooks
    ON_LOW_CONFIDENCE = "on_low_confidence"
    ON_DRIFT_DETECTED = "on_drift_detected"
    ON_DEGRADATION = "on_degradation"
    ON_EXPLORATION = "on_exploration"
    ON_HUMAN_ESCALATION = "on_human_escalation"


@dataclass
class HookResult:
    """Result from executing a hook."""
    success: bool
    modified_data: Optional[Any] = None
    should_block: bool = False
    message: str = ""
    duration_ms: float = 0.0


@dataclass
class HookConfig:
    """Configuration for a hook."""
    name: str
    point: HookPoint
    handler: str  # "module.path:function" or callable
    matcher: Optional[str] = None  # For tool hooks, which tool to match
    timeout_seconds: float = 5.0
    on_fail: str = "log"  # "log" | "block" | "ignore"
    threshold: Optional[float] = None  # For confidence hooks
    enabled: bool = True


class AALHookManager:
    """
    Manages lifecycle hooks for AAL agents.

    Extends SDK hook patterns with AAL-specific points.
    """

    def __init__(self, hooks_spec: Optional[Any] = None):
        self.hooks: Dict[HookPoint, List[HookConfig]] = {
            point: [] for point in HookPoint
        }
        self.execution_log: List[Dict[str, Any]] = []

        if hooks_spec:
            self._load_from_spec(hooks_spec)

    def _load_from_spec(self, hooks_spec: Any) -> None:
        """Load hooks from manifest specification."""
        # Map manifest hook names to HookPoints
        mapping = {
            "pre_input": HookPoint.PRE_INPUT,
            "pre_tool_use": HookPoint.PRE_TOOL_USE,
            "post_tool_use": HookPoint.POST_TOOL_USE,
            "on_error": HookPoint.ON_DEGRADATION,
            "on_low_confidence": HookPoint.ON_LOW_CONFIDENCE,
        }

        for attr_name, hook_point in mapping.items():
            hook_list = getattr(hooks_spec, attr_name, [])
            for hook_data in hook_list:
                config = HookConfig(
                    name=hook_data.name,
                    point=hook_point,
                    handler=hook_data.handler,
                    matcher=getattr(hook_data, 'matcher', None),
                    timeout_seconds=getattr(hook_data, 'timeout_ms', 5000) / 1000,
                    on_fail=getattr(hook_data, 'on_fail', 'log'),
                    threshold=getattr(hook_data, 'threshold', None),
                )
                self.register(config)

    def register(self, config: HookConfig) -> None:
        """Register a hook."""
        self.hooks[config.point].append(config)

    def register_function(
        self,
        point: HookPoint,
        name: str,
        handler: Callable,
        **kwargs,
    ) -> None:
        """Register a hook with a function directly."""
        config = HookConfig(
            name=name,
            point=point,
            handler=handler,  # type: ignore
            **kwargs,
        )
        self.hooks[point].append(config)

    async def run_pre_input(self, prompt: str) -> str:
        """Run pre-input hooks, potentially modifying the prompt."""
        result = prompt

        for hook in self.hooks[HookPoint.PRE_INPUT]:
            if not hook.enabled:
                continue

            hook_result = await self._execute_hook(hook, {"prompt": result})

            if hook_result.should_block:
                raise HookBlockedError(f"Hook {hook.name} blocked input")

            if hook_result.modified_data:
                result = hook_result.modified_data.get("prompt", result)

        return result

    async def run_pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> tuple:
        """
        Run pre-tool-use hooks.

        Returns (should_proceed, modified_input)
        """
        for hook in self.hooks[HookPoint.PRE_TOOL_USE]:
            if not hook.enabled:
                continue

            # Check matcher
            if hook.matcher and hook.matcher != "*":
                if isinstance(hook.matcher, list):
                    if tool_name not in hook.matcher:
                        continue
                elif tool_name != hook.matcher:
                    continue

            hook_result = await self._execute_hook(
                hook,
                {"tool_name": tool_name, "tool_input": tool_input}
            )

            if hook_result.should_block:
                return False, tool_input

            if hook_result.modified_data:
                tool_input = hook_result.modified_data.get("tool_input", tool_input)

        return True, tool_input

    async def run_post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> Any:
        """Run post-tool-use hooks."""
        result = tool_output

        for hook in self.hooks[HookPoint.POST_TOOL_USE]:
            if not hook.enabled:
                continue

            if hook.matcher and hook.matcher != "*":
                if isinstance(hook.matcher, list):
                    if tool_name not in hook.matcher:
                        continue
                elif tool_name != hook.matcher:
                    continue

            hook_result = await self._execute_hook(
                hook,
                {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_output": result,
                }
            )

            if hook_result.modified_data:
                result = hook_result.modified_data.get("tool_output", result)

        return result

    async def run_post_output(self, response: Any) -> None:
        """Run post-output hooks."""
        for hook in self.hooks[HookPoint.POST_OUTPUT]:
            if not hook.enabled:
                continue

            await self._execute_hook(hook, {"response": response})

    async def run_on_low_confidence(
        self,
        confidence: float,
        response: Any,
    ) -> Optional[str]:
        """
        Run low-confidence hooks.

        Returns optional action to take.
        """
        for hook in self.hooks[HookPoint.ON_LOW_CONFIDENCE]:
            if not hook.enabled:
                continue

            # Check threshold
            if hook.threshold and confidence >= hook.threshold:
                continue

            hook_result = await self._execute_hook(
                hook,
                {"confidence": confidence, "response": response}
            )

            if hook_result.modified_data:
                action = hook_result.modified_data.get("action")
                if action:
                    return action

        return None

    async def run_on_drift(self, drift_data: Dict[str, Any]) -> None:
        """Run drift detection hooks."""
        for hook in self.hooks[HookPoint.ON_DRIFT_DETECTED]:
            if not hook.enabled:
                continue

            await self._execute_hook(hook, drift_data)

    async def run_on_degradation(
        self,
        from_level: str,
        to_level: str,
        reason: str,
    ) -> None:
        """Run degradation hooks."""
        for hook in self.hooks[HookPoint.ON_DEGRADATION]:
            if not hook.enabled:
                continue

            await self._execute_hook(
                hook,
                {"from_level": from_level, "to_level": to_level, "reason": reason}
            )

    async def _execute_hook(
        self,
        config: HookConfig,
        data: Dict[str, Any],
    ) -> HookResult:
        """Execute a single hook."""
        start = datetime.utcnow()

        try:
            # Get handler function
            handler = self._resolve_handler(config.handler)

            # Execute with timeout
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(data),
                    timeout=config.timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(handler, data),
                    timeout=config.timeout_seconds,
                )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            # Parse result
            if result is None:
                hook_result = HookResult(success=True, duration_ms=duration)
            elif isinstance(result, dict):
                hook_result = HookResult(
                    success=True,
                    modified_data=result,
                    should_block=result.get("block", False),
                    message=result.get("message", ""),
                    duration_ms=duration,
                )
            else:
                hook_result = HookResult(
                    success=True,
                    modified_data={"result": result},
                    duration_ms=duration,
                )

            self._log_execution(config, hook_result)
            return hook_result

        except asyncio.TimeoutError:
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            hook_result = HookResult(
                success=False,
                message=f"Hook {config.name} timed out",
                duration_ms=duration,
            )
            self._log_execution(config, hook_result)
            return self._handle_failure(config, hook_result)

        except Exception as e:
            duration = (datetime.utcnow() - start).total_seconds() * 1000
            hook_result = HookResult(
                success=False,
                message=f"Hook {config.name} failed: {e}",
                duration_ms=duration,
            )
            self._log_execution(config, hook_result)
            return self._handle_failure(config, hook_result)

    def _resolve_handler(self, handler: Union[str, Callable]) -> Callable:
        """Resolve handler string to callable."""
        if callable(handler):
            return handler

        # Parse "module.path:function" format
        if ":" in handler:
            module_path, func_name = handler.rsplit(":", 1)
        else:
            raise ValueError(f"Invalid handler format: {handler}")

        # Handle file path
        if "/" in module_path or module_path.endswith(".py"):
            # It's a file path
            path = Path(module_path)
            if not path.is_absolute():
                path = Path.cwd() / path

            if not path.exists():
                raise FileNotFoundError(f"Hook file not found: {path}")

            spec = importlib.util.spec_from_file_location("hook_module", path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load hook from: {path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules["hook_module"] = module
            spec.loader.exec_module(module)

            return getattr(module, func_name)
        else:
            # It's a module path
            module = importlib.import_module(module_path)
            return getattr(module, func_name)

    def _handle_failure(
        self,
        config: HookConfig,
        result: HookResult,
    ) -> HookResult:
        """Handle hook failure based on on_fail policy."""
        if config.on_fail == "block":
            result.should_block = True
        elif config.on_fail == "ignore":
            result.success = True  # Pretend it succeeded
        # "log" is the default - just log and continue

        return result

    def _log_execution(self, config: HookConfig, result: HookResult) -> None:
        """Log hook execution."""
        self.execution_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "hook": config.name,
            "point": config.point.value,
            "success": result.success,
            "blocked": result.should_block,
            "duration_ms": result.duration_ms,
            "message": result.message,
        })

        # Keep log bounded
        if len(self.execution_log) > 1000:
            self.execution_log = self.execution_log[-500:]

    def get_execution_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent hook executions."""
        return self.execution_log[-limit:]


class HookBlockedError(Exception):
    """Raised when a hook blocks execution."""
    pass


def hook(point: HookPoint, name: Optional[str] = None, **kwargs):
    """
    Decorator to register a function as a hook.

    Usage:
        @hook(HookPoint.PRE_INPUT, name="sanitize")
        async def sanitize_input(data):
            data["prompt"] = data["prompt"].strip()
            return data
    """
    def decorator(func: Callable) -> Callable:
        func._aal_hook = {
            "point": point,
            "name": name or func.__name__,
            **kwargs,
        }
        return func
    return decorator
