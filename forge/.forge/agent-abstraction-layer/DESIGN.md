# Agent Abstraction Layer (AAL) Design

## Philosophical Foundation

*"A new programmable layer of abstraction... involving agents, subagents, their prompts, contexts, memory, modes, permissions, tools, plugins, skills, hooks, MCP, LSP, slash commands, workflows, IDE integrations, and a need to build an all-encompassing mental model for strengths and pitfalls of fundamentally stochastic, fallible, unintelligible and changing entities suddenly intermingled with what used to be good old fashioned engineering."* — Andrej Karpathy

This document defines the Agent Abstraction Layer (AAL): a principled framework for working with AI agents that acknowledges their fundamentally different nature from deterministic code.

---

## The Four Properties of AI Entities

Traditional software has predictable properties: given input X, produce output Y, always. AI agents violate this. They exhibit four properties that demand new abstractions:

### 1. STOCHASTIC
Same input → different outputs. Temperature, sampling, and model internals create variance.

**Implications:**
- Cannot rely on exact output matching
- Must design for output distributions, not values
- Need confidence/uncertainty quantification
- Require multiple-path exploration

### 2. FALLIBLE
AI agents make mistakes. They hallucinate, misunderstand, and produce incorrect outputs.

**Implications:**
- Cannot trust outputs without verification
- Must design recovery paths
- Need human escalation mechanisms
- Require graceful degradation

### 3. UNINTELLIGIBLE
We cannot fully inspect the "reasoning" process. Transformers are not interpretable.

**Implications:**
- Cannot debug via traditional inspection
- Must observe behavior patterns, not internals
- Need extensive tracing and logging
- Require behavioral fingerprinting

### 4. CHANGING
Models update, prompts drift, behavior shifts over time.

**Implications:**
- Cannot assume stable behavior
- Must version everything
- Need drift detection
- Require regression testing

---

## Core Abstractions

### 1. AgentEntity

The fundamental unit. Not code, not a function—an entity with identity.

```yaml
agent:
  id: "researcher-v2"
  version: "2.4.1"
  model: "claude-opus-4-5-20251101"

  # Behavioral fingerprint for drift detection
  fingerprint:
    expected_latency_p50_ms: 1200
    expected_token_ratio: 2.3
    behavioral_hash: "sha256:a1b2c3..."

  # Uncertainty bounds
  uncertainty:
    confidence_threshold: 0.7
    max_retries_on_low_confidence: 3
    fallback_agent: "researcher-v1"

  # Lifecycle
  lifecycle:
    cold_start_warmup: true
    max_concurrent_instances: 5
    graceful_shutdown_timeout_ms: 5000
```

### 2. AgentContext

The execution environment—what the agent knows and operates within.

```yaml
context:
  # Conversation state
  conversation:
    history_strategy: "sliding_window"  # full | sliding_window | summarized
    max_messages: 50
    summary_trigger_at: 40

  # Working memory (ephemeral within session)
  working_memory:
    max_items: 20
    ttl_seconds: 3600

  # Long-term memory (persisted)
  persistent_memory:
    storage: "vector_db"
    retrieval_strategy: "semantic_top_k"
    k: 10
    decay_factor: 0.95

  # Injected context
  injections:
    - type: "system_prompt"
      source: "prompts/researcher.md"
    - type: "few_shot_examples"
      source: "examples/research_patterns.yaml"
    - type: "dynamic"
      hook: "inject_current_date"
```

### 3. AgentPermissions

What the agent can and cannot do. Security boundary.

```yaml
permissions:
  # Tool access
  tools:
    allowed:
      - "web_search"
      - "read_file"
      - "write_file"
    denied:
      - "execute_code"  # Explicit deny
    require_approval:
      - "delete_file"
      - "send_email"

  # Resource limits
  resources:
    max_tokens_per_turn: 8192
    max_tool_calls_per_turn: 10
    max_cost_per_session_usd: 1.00

  # Scope restrictions
  scope:
    allowed_directories: ["/workspace", "/tmp"]
    allowed_domains: ["*.anthropic.com", "github.com"]
    denied_patterns: ["*.env", "credentials.*"]

  # Escalation
  escalation:
    on_permission_denied: "ask_human"
    on_uncertainty_high: "pause_and_confirm"
```

### 4. AgentMemory

The persistence layer—what survives across sessions.

```yaml
memory:
  # Episodic memory (what happened)
  episodic:
    enabled: true
    storage: "sessions/{session_id}/episodes.jsonl"
    retention_days: 30

  # Semantic memory (what things mean)
  semantic:
    enabled: true
    storage: "vector"
    embedding_model: "text-embedding-3-small"

  # Procedural memory (how to do things)
  procedural:
    enabled: true
    storage: "skills/"
    learned_skills:
      - id: "parse_error_logs"
        confidence: 0.92
        last_used: "2025-01-15"

  # Working memory bridge
  working_to_long_term:
    strategy: "importance_weighted"
    consolidation_trigger: "session_end"
```

### 5. AgentHooks

Lifecycle events that allow intervention.

```yaml
hooks:
  # Before agent receives input
  pre_input:
    - name: "sanitize_input"
      handler: "hooks/sanitize.py:sanitize"
    - name: "inject_context"
      handler: "hooks/context.py:inject_user_prefs"

  # Before agent produces output
  pre_output:
    - name: "validate_safety"
      handler: "hooks/safety.py:check_output"
      on_fail: "block_and_log"

  # After each tool call
  post_tool:
    - name: "audit_tool_use"
      handler: "hooks/audit.py:log_tool"

  # On error
  on_error:
    - name: "error_recovery"
      handler: "hooks/recovery.py:attempt_recovery"
      max_attempts: 3

  # On low confidence
  on_low_confidence:
    - name: "escalate_to_human"
      threshold: 0.5
      handler: "hooks/escalation.py:ask_human"
```

### 6. AgentTools

Tool definitions with uncertainty handling.

```yaml
tools:
  - name: "web_search"
    description: "Search the web for information"
    input_schema:
      type: object
      properties:
        query:
          type: string
          description: "Search query"
      required: ["query"]

    # Execution configuration
    execution:
      timeout_ms: 10000
      retries: 2

    # Result uncertainty
    uncertainty:
      # How reliable are results from this tool?
      reliability_score: 0.85
      # Should agent verify results?
      verification_required: false

    # Cost tracking
    cost:
      per_call_usd: 0.01
      rate_limit: "10/minute"
```

### 7. AgentSkills

Reusable capabilities that can be composed.

```yaml
skills:
  - id: "code_review"
    name: "Code Review"
    description: "Review code for bugs, style, and improvements"

    # Required tools
    requires_tools:
      - "read_file"
      - "grep"

    # Prompt template
    prompt_template: "skills/code_review.md"

    # Invocation
    invocation:
      slash_command: "/review"
      mcp_endpoint: "skills/code_review"

    # Quality metrics
    quality:
      success_rate: 0.94
      avg_latency_ms: 3500
      user_satisfaction: 4.2
```

### 8. AgentModes

Behavioral configurations for different contexts.

```yaml
modes:
  default:
    temperature: 1.0
    max_tokens: 4096
    tools_enabled: true
    streaming: true

  careful:
    temperature: 0.3
    max_tokens: 2048
    tools_enabled: true
    require_confirmation: true

  creative:
    temperature: 1.0
    max_tokens: 8192
    tools_enabled: false
    streaming: true

  # Mode can be set by
  mode_selection:
    default: "default"
    triggers:
      - pattern: "be careful|double check"
        mode: "careful"
      - pattern: "brainstorm|creative|imagine"
        mode: "creative"
```

---

## Uncertainty Management System

### Confidence Quantification

Every agent output should carry confidence metadata:

```python
@dataclass
class AgentOutput:
    content: str
    confidence: float  # 0.0 - 1.0
    uncertainty_type: str  # "epistemic" | "aleatoric"
    alternatives: List[str]  # Other possible outputs considered
    reasoning_trace: Optional[str]  # If available
```

### Multi-Path Exploration

When confidence is low, explore multiple paths:

```yaml
exploration:
  strategy: "beam_search"  # single | beam_search | monte_carlo

  beam_search:
    width: 3
    depth: 5
    prune_threshold: 0.3

  monte_carlo:
    samples: 10
    temperature_range: [0.5, 1.2]

  consensus:
    strategy: "majority_vote"  # majority_vote | weighted_average | human_select
    min_agreement: 0.6
```

### Rollback and Checkpoints

Enable reverting when things go wrong:

```yaml
checkpoints:
  enabled: true
  strategy: "on_tool_call"  # on_tool_call | periodic | manual

  storage:
    type: "local"
    path: "checkpoints/{session_id}/"

  retention:
    max_checkpoints: 20
    max_age_hours: 24

  rollback:
    triggers:
      - "user_command"
      - "error_threshold_exceeded"
      - "confidence_below_threshold"
```

---

## Fallibility Handling

### Error Classification

```yaml
error_taxonomy:
  recoverable:
    - rate_limit:
        action: "exponential_backoff"
        max_wait_ms: 60000
    - timeout:
        action: "retry"
        max_attempts: 3
    - context_overflow:
        action: "summarize_and_retry"

  degradable:
    - tool_failure:
        action: "proceed_without_tool"
        notify_user: true
    - low_confidence:
        action: "provide_alternatives"

  fatal:
    - auth_failure:
        action: "halt_and_notify"
    - safety_violation:
        action: "halt_and_log"
```

### Graceful Degradation Ladder

```yaml
degradation_ladder:
  # Try these in order when primary path fails
  levels:
    - name: "full_capability"
      description: "All tools and features available"

    - name: "reduced_tools"
      description: "Proceed with subset of tools"
      disabled_tools: ["web_search", "code_execute"]

    - name: "conversation_only"
      description: "No tool use, conversation only"
      tools_enabled: false

    - name: "cached_responses"
      description: "Return cached/pre-computed responses"
      use_cache: true

    - name: "human_handoff"
      description: "Escalate to human operator"
      action: "escalate"
```

### Human-in-the-Loop Integration

```yaml
human_loop:
  escalation_triggers:
    - confidence_below: 0.4
    - cost_exceeds_usd: 0.50
    - sensitive_action: true
    - explicit_request: true

  interface:
    type: "async_approval"  # sync_block | async_approval | log_only
    timeout_seconds: 300
    default_on_timeout: "deny"

  channels:
    - type: "cli_prompt"
      enabled: true
    - type: "slack"
      webhook: "${SLACK_WEBHOOK}"
    - type: "email"
      address: "${ALERT_EMAIL}"
```

---

## Observability Layer

### Trace Everything

```yaml
tracing:
  enabled: true

  spans:
    - name: "agent_turn"
      attributes:
        - input_tokens
        - output_tokens
        - latency_ms
        - model_version
        - confidence

    - name: "tool_call"
      attributes:
        - tool_name
        - input_hash
        - output_hash
        - duration_ms
        - success

  exporters:
    - type: "otlp"
      endpoint: "http://jaeger:4317"
    - type: "file"
      path: "traces/{date}.jsonl"
```

### Decision Logging

Every decision the agent makes should be logged:

```yaml
decision_log:
  enabled: true

  capture:
    - type: "tool_selection"
      fields: [tool_name, reason, alternatives_considered]

    - type: "response_formulation"
      fields: [approach, confidence, key_points]

    - type: "error_handling"
      fields: [error_type, recovery_action, success]

  storage:
    type: "structured"
    format: "jsonl"
    path: "decisions/{session_id}.jsonl"
```

### Behavioral Fingerprinting

Detect when agent behavior drifts:

```yaml
fingerprinting:
  enabled: true

  metrics:
    - name: "response_length_distribution"
      type: "histogram"
      buckets: [100, 500, 1000, 2000, 4000]

    - name: "tool_usage_frequency"
      type: "counter_vector"
      labels: ["tool_name"]

    - name: "sentiment_distribution"
      type: "histogram"
      buckets: [-1.0, -0.5, 0.0, 0.5, 1.0]

    - name: "error_rate"
      type: "gauge"

  drift_detection:
    method: "kolmogorov_smirnov"
    threshold: 0.1
    window_size: 100
    alert_on_drift: true
```

---

## Unified Agent Manifest

The complete specification for an agent:

```yaml
# agent.manifest.yaml
apiVersion: aal/v1
kind: AgentManifest

metadata:
  id: "research-assistant"
  version: "1.2.0"
  name: "Research Assistant"
  description: "An agent that helps with research tasks"

spec:
  # Core entity definition
  entity:
    model: "claude-opus-4-5-20251101"
    fingerprint:
      behavioral_hash: "sha256:..."

  # Context configuration
  context:
    system_prompt: "prompts/research.md"
    memory:
      episodic: true
      semantic: true

  # Permissions
  permissions:
    tools:
      allowed: ["web_search", "read_file", "write_file"]
      require_approval: ["delete_file"]
    resources:
      max_cost_per_session_usd: 1.00

  # Tools
  tools:
    - $ref: "tools/web_search.yaml"
    - $ref: "tools/file_operations.yaml"

  # Skills
  skills:
    - $ref: "skills/summarize.yaml"
    - $ref: "skills/analyze.yaml"

  # Hooks
  hooks:
    pre_input:
      - handler: "hooks/sanitize.py"
    on_error:
      - handler: "hooks/recovery.py"

  # Modes
  modes:
    default:
      temperature: 1.0
    careful:
      temperature: 0.3
      require_confirmation: true

  # Uncertainty handling
  uncertainty:
    confidence_threshold: 0.7
    exploration_strategy: "beam_search"
    fallback_agent: "research-assistant-v1"

  # Observability
  observability:
    tracing: true
    decision_logging: true
    fingerprinting: true

  # Integration points
  integrations:
    mcp:
      enabled: true
      servers:
        - "filesystem"
        - "web"
    lsp:
      enabled: false
    ide:
      vscode_extension: "research-assistant"
```

---

## Implementation Priorities

### Phase 1: Core Primitives
1. AgentEntity with versioning and fingerprinting
2. AgentContext with memory strategies
3. AgentPermissions with security boundaries

### Phase 2: Uncertainty & Fallibility
4. Confidence quantification system
5. Multi-path exploration
6. Error classification and recovery

### Phase 3: Observability
7. Tracing infrastructure
8. Decision logging
9. Drift detection

### Phase 4: Integration
10. MCP integration
11. Hook system
12. Unified manifest parser

---

## The Mental Model

When working with AI agents, shift from:

| Traditional Code | Agent Abstraction Layer |
|-----------------|------------------------|
| Functions return values | Agents produce distributions |
| Errors are exceptions | Errors are expected paths |
| Debug with breakpoints | Observe with traces |
| Test with assertions | Test with behavioral bounds |
| Version with git | Version behavior + model + prompt |
| Security via access control | Security via permissions + verification |
| Deploy and forget | Monitor for drift |

The AAL is not about making agents behave like code. It's about creating the right abstractions for what agents actually are: **stochastic, fallible, unintelligible, and changing entities** that we must nevertheless build reliable systems with.

---

*This design is living documentation. It evolves as we learn more about working with these new entities.*
