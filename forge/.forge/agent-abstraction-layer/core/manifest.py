"""
Unified Agent Manifest for the Agent Abstraction Layer.

The manifest is the single source of truth for an agent's:
- Identity and versioning
- Context and memory configuration
- Permissions and security boundaries
- Tools and skills
- Hooks and integrations
- Uncertainty handling
- Observability settings
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import yaml
import json


class ManifestVersion(Enum):
    """Supported manifest API versions."""
    V1 = "aal/v1"


@dataclass
class ManifestMetadata:
    """Metadata about the agent."""
    id: str
    version: str
    name: str
    description: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class EntitySpec:
    """Specification for the agent entity."""
    model: str
    behavioral_hash: Optional[str] = None
    confidence_threshold: float = 0.7
    fallback_agent_id: Optional[str] = None
    max_concurrent: int = 5


@dataclass
class ContextSpec:
    """Specification for agent context."""
    system_prompt_path: Optional[str] = None
    system_prompt: Optional[str] = None
    history_strategy: str = "sliding_window"
    max_messages: int = 50

    # Memory settings
    episodic_memory: bool = True
    semantic_memory: bool = True
    memory_retention_days: int = 30


@dataclass
class ToolSpec:
    """Specification for a tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    timeout_ms: int = 10000
    retries: int = 2
    reliability_score: float = 0.9
    require_approval: bool = False


@dataclass
class SkillSpec:
    """Specification for a skill."""
    id: str
    name: str
    description: str
    prompt_template_path: str
    required_tools: List[str] = field(default_factory=list)
    slash_command: Optional[str] = None
    mcp_endpoint: Optional[str] = None


@dataclass
class HookSpec:
    """Specification for a hook."""
    name: str
    handler: str  # module:function format
    on_fail: str = "log"  # "log" | "block" | "retry"
    timeout_ms: int = 5000


@dataclass
class HooksSpec:
    """Collection of hooks for different lifecycle points."""
    pre_input: List[HookSpec] = field(default_factory=list)
    pre_output: List[HookSpec] = field(default_factory=list)
    post_tool: List[HookSpec] = field(default_factory=list)
    on_error: List[HookSpec] = field(default_factory=list)
    on_low_confidence: List[HookSpec] = field(default_factory=list)


@dataclass
class PermissionsSpec:
    """Specification for agent permissions."""
    # Tool permissions
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    approval_required_tools: List[str] = field(default_factory=list)

    # Resource limits
    max_tokens_per_turn: int = 8192
    max_tool_calls_per_turn: int = 10
    max_cost_per_session_usd: float = 1.0

    # Scope restrictions
    allowed_directories: List[str] = field(default_factory=lambda: ["/workspace"])
    allowed_domains: List[str] = field(default_factory=list)
    denied_patterns: List[str] = field(default_factory=lambda: ["*.env"])


@dataclass
class ModeSpec:
    """Specification for a behavioral mode."""
    temperature: float = 1.0
    max_tokens: int = 4096
    tools_enabled: bool = True
    require_confirmation: bool = False
    streaming: bool = True


@dataclass
class UncertaintySpec:
    """Specification for uncertainty handling."""
    confidence_threshold: float = 0.7
    exploration_strategy: str = "single"  # "single" | "beam_search" | "monte_carlo"
    beam_width: int = 3
    mc_samples: int = 10
    fallback_agent: Optional[str] = None


@dataclass
class ObservabilitySpec:
    """Specification for observability settings."""
    tracing_enabled: bool = True
    decision_logging_enabled: bool = True
    fingerprinting_enabled: bool = True
    drift_threshold: float = 0.1
    export_format: str = "jsonl"  # "jsonl" | "otlp"
    export_path: Optional[str] = None


@dataclass
class MCPIntegration:
    """MCP integration settings."""
    enabled: bool = True
    servers: List[str] = field(default_factory=list)


@dataclass
class LSPIntegration:
    """LSP integration settings."""
    enabled: bool = False
    languages: List[str] = field(default_factory=list)


@dataclass
class IDEIntegration:
    """IDE integration settings."""
    vscode_extension: Optional[str] = None
    jetbrains_plugin: Optional[str] = None


@dataclass
class IntegrationsSpec:
    """External integration specifications."""
    mcp: MCPIntegration = field(default_factory=MCPIntegration)
    lsp: LSPIntegration = field(default_factory=LSPIntegration)
    ide: IDEIntegration = field(default_factory=IDEIntegration)


@dataclass
class AgentManifest:
    """
    The complete specification for an agent.

    This is the unified configuration that brings together
    all aspects of agent behavior, from identity to observability.
    """
    api_version: str
    kind: str
    metadata: ManifestMetadata
    spec: Dict[str, Any]

    # Parsed specifications
    entity: Optional[EntitySpec] = None
    context: Optional[ContextSpec] = None
    permissions: Optional[PermissionsSpec] = None
    tools: List[ToolSpec] = field(default_factory=list)
    skills: List[SkillSpec] = field(default_factory=list)
    hooks: Optional[HooksSpec] = None
    modes: Dict[str, ModeSpec] = field(default_factory=dict)
    uncertainty: Optional[UncertaintySpec] = None
    observability: Optional[ObservabilitySpec] = None
    integrations: Optional[IntegrationsSpec] = None

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "AgentManifest":
        """Parse a manifest from YAML content."""
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "AgentManifest":
        """Load a manifest from a file."""
        path = Path(path)
        content = path.read_text()

        if path.suffix in [".yaml", ".yml"]:
            return cls.from_yaml(content)
        elif path.suffix == ".json":
            data = json.loads(content)
            return cls.from_dict(data)
        else:
            raise ValueError(f"Unsupported manifest format: {path.suffix}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentManifest":
        """Parse a manifest from a dictionary."""
        # Validate API version
        api_version = data.get("apiVersion", "aal/v1")
        if api_version not in [v.value for v in ManifestVersion]:
            raise ValueError(f"Unsupported API version: {api_version}")

        # Parse metadata
        meta_data = data.get("metadata", {})
        metadata = ManifestMetadata(
            id=meta_data.get("id", "unknown"),
            version=meta_data.get("version", "0.0.0"),
            name=meta_data.get("name", "Unknown Agent"),
            description=meta_data.get("description", ""),
            labels=meta_data.get("labels", {}),
            annotations=meta_data.get("annotations", {}),
        )

        spec = data.get("spec", {})

        # Create manifest
        manifest = cls(
            api_version=api_version,
            kind=data.get("kind", "AgentManifest"),
            metadata=metadata,
            spec=spec,
        )

        # Parse spec sections
        manifest._parse_entity(spec.get("entity", {}))
        manifest._parse_context(spec.get("context", {}))
        manifest._parse_permissions(spec.get("permissions", {}))
        manifest._parse_tools(spec.get("tools", []))
        manifest._parse_skills(spec.get("skills", []))
        manifest._parse_hooks(spec.get("hooks", {}))
        manifest._parse_modes(spec.get("modes", {}))
        manifest._parse_uncertainty(spec.get("uncertainty", {}))
        manifest._parse_observability(spec.get("observability", {}))
        manifest._parse_integrations(spec.get("integrations", {}))

        return manifest

    def _parse_entity(self, data: Dict[str, Any]) -> None:
        """Parse entity specification."""
        if not data:
            self.entity = EntitySpec(model="claude-sonnet-4-20250514")
            return

        self.entity = EntitySpec(
            model=data.get("model", "claude-sonnet-4-20250514"),
            behavioral_hash=data.get("fingerprint", {}).get("behavioral_hash"),
            confidence_threshold=data.get("confidence_threshold", 0.7),
            fallback_agent_id=data.get("fallback_agent"),
            max_concurrent=data.get("max_concurrent", 5),
        )

    def _parse_context(self, data: Dict[str, Any]) -> None:
        """Parse context specification."""
        memory = data.get("memory", {})

        self.context = ContextSpec(
            system_prompt_path=data.get("system_prompt"),
            history_strategy=data.get("history_strategy", "sliding_window"),
            max_messages=data.get("max_messages", 50),
            episodic_memory=memory.get("episodic", True),
            semantic_memory=memory.get("semantic", True),
            memory_retention_days=memory.get("retention_days", 30),
        )

    def _parse_permissions(self, data: Dict[str, Any]) -> None:
        """Parse permissions specification."""
        tools = data.get("tools", {})
        resources = data.get("resources", {})
        scope = data.get("scope", {})

        self.permissions = PermissionsSpec(
            allowed_tools=tools.get("allowed", []),
            denied_tools=tools.get("denied", []),
            approval_required_tools=tools.get("require_approval", []),
            max_tokens_per_turn=resources.get("max_tokens_per_turn", 8192),
            max_tool_calls_per_turn=resources.get("max_tool_calls_per_turn", 10),
            max_cost_per_session_usd=resources.get("max_cost_per_session_usd", 1.0),
            allowed_directories=scope.get("allowed_directories", ["/workspace"]),
            allowed_domains=scope.get("allowed_domains", []),
            denied_patterns=scope.get("denied_patterns", ["*.env"]),
        )

    def _parse_tools(self, data: List[Dict[str, Any]]) -> None:
        """Parse tools specification."""
        self.tools = []
        for tool_data in data:
            # Handle $ref for external tool definitions
            if "$ref" in tool_data:
                # Would load from external file in full implementation
                continue

            execution = tool_data.get("execution", {})
            uncertainty = tool_data.get("uncertainty", {})

            self.tools.append(ToolSpec(
                name=tool_data.get("name", "unknown"),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("input_schema", {}),
                timeout_ms=execution.get("timeout_ms", 10000),
                retries=execution.get("retries", 2),
                reliability_score=uncertainty.get("reliability_score", 0.9),
                require_approval=tool_data.get("require_approval", False),
            ))

    def _parse_skills(self, data: List[Dict[str, Any]]) -> None:
        """Parse skills specification."""
        self.skills = []
        for skill_data in data:
            if "$ref" in skill_data:
                continue

            invocation = skill_data.get("invocation", {})

            self.skills.append(SkillSpec(
                id=skill_data.get("id", "unknown"),
                name=skill_data.get("name", ""),
                description=skill_data.get("description", ""),
                prompt_template_path=skill_data.get("prompt_template", ""),
                required_tools=skill_data.get("requires_tools", []),
                slash_command=invocation.get("slash_command"),
                mcp_endpoint=invocation.get("mcp_endpoint"),
            ))

    def _parse_hooks(self, data: Dict[str, Any]) -> None:
        """Parse hooks specification."""
        def parse_hook_list(hook_list: List[Dict[str, Any]]) -> List[HookSpec]:
            hooks = []
            for hook_data in hook_list:
                hooks.append(HookSpec(
                    name=hook_data.get("name", ""),
                    handler=hook_data.get("handler", ""),
                    on_fail=hook_data.get("on_fail", "log"),
                    timeout_ms=hook_data.get("timeout_ms", 5000),
                ))
            return hooks

        self.hooks = HooksSpec(
            pre_input=parse_hook_list(data.get("pre_input", [])),
            pre_output=parse_hook_list(data.get("pre_output", [])),
            post_tool=parse_hook_list(data.get("post_tool", [])),
            on_error=parse_hook_list(data.get("on_error", [])),
            on_low_confidence=parse_hook_list(data.get("on_low_confidence", [])),
        )

    def _parse_modes(self, data: Dict[str, Any]) -> None:
        """Parse modes specification."""
        self.modes = {}
        for mode_name, mode_data in data.items():
            if mode_name == "mode_selection":
                continue  # Skip mode selection config

            self.modes[mode_name] = ModeSpec(
                temperature=mode_data.get("temperature", 1.0),
                max_tokens=mode_data.get("max_tokens", 4096),
                tools_enabled=mode_data.get("tools_enabled", True),
                require_confirmation=mode_data.get("require_confirmation", False),
                streaming=mode_data.get("streaming", True),
            )

    def _parse_uncertainty(self, data: Dict[str, Any]) -> None:
        """Parse uncertainty specification."""
        self.uncertainty = UncertaintySpec(
            confidence_threshold=data.get("confidence_threshold", 0.7),
            exploration_strategy=data.get("exploration_strategy", "single"),
            beam_width=data.get("beam_width", 3),
            mc_samples=data.get("mc_samples", 10),
            fallback_agent=data.get("fallback_agent"),
        )

    def _parse_observability(self, data: Dict[str, Any]) -> None:
        """Parse observability specification."""
        self.observability = ObservabilitySpec(
            tracing_enabled=data.get("tracing", True),
            decision_logging_enabled=data.get("decision_logging", True),
            fingerprinting_enabled=data.get("fingerprinting", True),
            drift_threshold=data.get("drift_threshold", 0.1),
            export_format=data.get("export_format", "jsonl"),
            export_path=data.get("export_path"),
        )

    def _parse_integrations(self, data: Dict[str, Any]) -> None:
        """Parse integrations specification."""
        mcp_data = data.get("mcp", {})
        lsp_data = data.get("lsp", {})
        ide_data = data.get("ide", {})

        self.integrations = IntegrationsSpec(
            mcp=MCPIntegration(
                enabled=mcp_data.get("enabled", True),
                servers=mcp_data.get("servers", []),
            ),
            lsp=LSPIntegration(
                enabled=lsp_data.get("enabled", False),
                languages=lsp_data.get("languages", []),
            ),
            ide=IDEIntegration(
                vscode_extension=ide_data.get("vscode_extension"),
                jetbrains_plugin=ide_data.get("jetbrains_plugin"),
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manifest to dictionary."""
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "id": self.metadata.id,
                "version": self.metadata.version,
                "name": self.metadata.name,
                "description": self.metadata.description,
                "labels": self.metadata.labels,
                "annotations": self.metadata.annotations,
            },
            "spec": self.spec,
        }

    def to_yaml(self) -> str:
        """Serialize manifest to YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def validate(self) -> List[str]:
        """
        Validate the manifest for consistency.

        Returns a list of validation errors.
        """
        errors = []

        # Validate metadata
        if not self.metadata.id:
            errors.append("metadata.id is required")
        if not self.metadata.version:
            errors.append("metadata.version is required")

        # Validate entity
        if self.entity and not self.entity.model:
            errors.append("spec.entity.model is required")

        # Validate permissions consistency
        if self.permissions:
            # Check for tools in both allowed and denied
            overlap = set(self.permissions.allowed_tools) & set(self.permissions.denied_tools)
            if overlap:
                errors.append(f"Tools in both allowed and denied: {overlap}")

        # Validate tools have required fields
        for tool in self.tools:
            if not tool.name:
                errors.append("All tools must have a name")
            if not tool.input_schema:
                errors.append(f"Tool '{tool.name}' must have input_schema")

        # Validate skills reference existing tools
        if self.permissions:
            available_tools = set(self.permissions.allowed_tools)
            for skill in self.skills:
                missing = set(skill.required_tools) - available_tools
                if missing:
                    errors.append(
                        f"Skill '{skill.id}' requires unavailable tools: {missing}"
                    )

        return errors

    def get_agent_id(self) -> str:
        """Get the fully qualified agent ID."""
        return f"{self.metadata.id}@{self.metadata.version}"


# Example manifest template
EXAMPLE_MANIFEST = """
apiVersion: aal/v1
kind: AgentManifest

metadata:
  id: research-assistant
  version: 1.0.0
  name: Research Assistant
  description: An agent that helps with research tasks

spec:
  entity:
    model: claude-opus-4-5-20251101
    confidence_threshold: 0.7
    max_concurrent: 5

  context:
    system_prompt: prompts/research.md
    history_strategy: sliding_window
    max_messages: 50
    memory:
      episodic: true
      semantic: true
      retention_days: 30

  permissions:
    tools:
      allowed:
        - web_search
        - read_file
        - write_file
      require_approval:
        - delete_file
    resources:
      max_cost_per_session_usd: 1.00

  tools:
    - name: web_search
      description: Search the web
      input_schema:
        type: object
        properties:
          query:
            type: string
        required:
          - query
      execution:
        timeout_ms: 10000

  skills:
    - id: summarize
      name: Summarize
      description: Summarize documents
      prompt_template: skills/summarize.md
      requires_tools:
        - read_file
      invocation:
        slash_command: /summarize

  hooks:
    pre_input:
      - name: sanitize
        handler: hooks/sanitize.py:sanitize
    on_error:
      - name: recovery
        handler: hooks/recovery.py:attempt_recovery

  modes:
    default:
      temperature: 1.0
      tools_enabled: true
    careful:
      temperature: 0.3
      require_confirmation: true

  uncertainty:
    confidence_threshold: 0.7
    exploration_strategy: beam_search
    beam_width: 3

  observability:
    tracing: true
    decision_logging: true
    fingerprinting: true

  integrations:
    mcp:
      enabled: true
      servers:
        - filesystem
        - web
"""
