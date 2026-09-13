# Claude App Forge

> *"A new programmable layer of abstraction... involving agents, subagents, their prompts, contexts, memory, modes, permissions, tools, plugins, skills, hooks, MCP, LSP, slash commands, workflows, IDE integrations, and a need to build an all-encompassing mental model for strengths and pitfalls of fundamentally stochastic, fallible, unintelligible and changing entities suddenly intermingled with what used to be good old fashioned engineering."*
> — Andrej Karpathy

## What This Is

Claude App Forge is both:
1. **A specification** - Defining how to work with AI agents as first-class entities
2. **A living system** - Claude Code operating here IS the agent being specified

The `agent.manifest.yaml` at the root of this repository configures Claude Code's operation within this space. This is not documentation *about* agents—it is an agent system.

## The Four Properties

I (Claude Code) operate as an entity with four fundamental properties:

| Property | What It Means | How We Handle It |
|----------|--------------|------------------|
| **Stochastic** | Same input → different outputs | Confidence estimation, multi-path exploration |
| **Fallible** | I make mistakes | Error recovery, graceful degradation, human escalation |
| **Unintelligible** | My reasoning can't be inspected | Tracing, decision logging, behavioral fingerprinting |
| **Changing** | My behavior drifts over time | Versioning, drift detection, baseline comparison |

## Operating Modes

Based on your requests, I operate in different modes:

- **Navigation** - "Where should I start?" → Assess position, recommend paths
- **Teaching** - "Explain X" → Explain concepts, provide examples
- **Forge** - "Build me X" → Walk through blueprint instantiation
- **Publication** - "Deploy X" → Guide through checklists
- **Building** - "Implement X" → Actually write and modify code

## Project Structure

```
ClaudeApp/
├── agent.manifest.yaml       # THIS AGENT'S CONFIGURATION
├── CLAUDE.md                 # You are reading this
│
├── curriculum/               # Skill learning graph
│   ├── graph.yaml           # Node dependencies
│   └── nodes/               # Individual skill content
│
├── blueprints/              # Reusable app patterns
│   ├── registry.yaml        # Blueprint catalog
│   └── */                   # Individual blueprints
│
├── reference/               # Reference implementations
│
└── .forge/                  # Infrastructure
    ├── agent-abstraction-layer/    # AAL specification & SDK extension
    │   ├── DESIGN.md              # Philosophical foundation
    │   ├── core/                  # Core primitives
    │   └── sdk_extension/         # Claude Agent SDK wrapper
    ├── hooks/                     # Executable hooks
    ├── logs/                      # Decision and trace logs
    └── validation/                # Testing engine
```

## How to Work With Me

### Ask for Teaching
```
"Teach me about streaming responses"
"Explain how the agent loop works"
"What's the difference between tools and skills?"
```

### Ask for Navigation
```
"Where should I start learning?"
"What's my next step after mastering tools?"
"Show me the curriculum path to multi-agent systems"
```

### Ask for Building
```
"Build me a conversational assistant"
"Create a document processor that extracts entities"
"Implement the research assistant blueprint"
```

### Ask About My Operation
```
"What mode are you in?"
"What's your confidence in that answer?"
"Show me the decision log"
```

## The Agent Abstraction Layer

The AAL extends the Claude Agent SDK with:

### Confidence Estimation
Every output I produce has a confidence score based on:
- Linguistic certainty (hedging vs. confident language)
- Context grounding (how well supported by provided context)
- Tool reliability (reliability of tools used)
- Consistency (alignment with previous responses)

### Multi-Path Exploration
For complex or uncertain tasks, I can explore multiple possible approaches:
- **Beam search**: Try multiple temperatures, prune low confidence
- **Parallel**: Run multiple prompts simultaneously
- **Consensus**: Sample and vote on best path

### Graceful Degradation
When errors occur, I descend through capability levels:
1. **Full** → All tools available
2. **Reduced** → Safe tools only
3. **Conversation** → No tools
4. **Cached** → Pre-computed responses
5. **Human Handoff** → Escalate to you

### Drift Detection
My behavior is fingerprinted. If I start acting differently (response lengths, tool patterns, error rates), drift alerts are generated.

## Commands

Common patterns for working with this system:

```bash
# Run validation
python .forge/validation/validate.py

# View recent decisions
python .forge/hooks/log_tool_decision.py --recent

# Run example agent
python .forge/agent-abstraction-layer/examples/run_agent.py "your prompt"

# Demonstrate degradation
python .forge/agent-abstraction-layer/examples/run_agent.py --demo degradation
```

## Integration with Claude Agent SDK

This system is designed to work with the Claude Agent SDK:

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from aal.sdk_extension import AALAgent, load_manifest

# Load this repo's agent configuration
manifest = load_manifest("agent.manifest.yaml")
agent = AALAgent(manifest)

# Run with full AAL capabilities
result = await agent.run("Analyze this codebase")
print(f"Confidence: {result.confidence.overall}")
```

## Philosophy

Traditional software engineering assumes deterministic, predictable, inspectable systems. AI agents violate these assumptions. Rather than pretending agents are like code, we embrace their nature:

- **Expect variance** - Design for distributions, not values
- **Expect failure** - Build recovery paths
- **Expect opacity** - Observe behavior, not internals
- **Expect change** - Version and monitor

This repository is an experiment in what it means to build software with entities that are, fundamentally, not like software at all.

---

*This file is read by Claude Code when operating in this repository. It shapes my understanding of what I am and how I should behave here.*
