# Claude App Forge

A version-controlled apprenticeship system where Claude Code serves as your forge-master, guiding you through creating apps using blueprint patterns continuously validated against the live Claude SDK.

## Philosophy

The name "Forge" is intentional: forging implies iterative refinement, heat and reshaping, producing something durable. It's a place where master and apprentice work together.

## Quick Start

```bash
# Clone the forge
git clone https://github.com/your-org/claude-app-forge
cd claude-app-forge

# Initialize your journal
cp -r journals/.template journals/my-journal

# Start with Claude Code
claude

# Ask Claude Code to guide you
> "I want to build an app that [describe your goal]"
```

## Architecture

### The Five Pillars

1. **Curriculum Graph** - Non-linear skill paths tailored to your goals
2. **Blueprint Patterns** - Abstract app patterns you instantiate with Claude Code
3. **Validation Engine** - Continuous testing against SDK versions
4. **Forge Journal** - Your personal learning and project record
5. **Publication Pipelines** - End-to-end paths from code to published artifact

## Directory Structure

```
claude-app-forge/
├── .forge/                      # Forge infrastructure
│   ├── validation/              # CI and validation tooling
│   ├── sdk-manifests/           # SDK version compatibility data
│   └── claude-code-context/     # Instructions for Claude Code
│
├── curriculum/                  # The skill graph
│   ├── graph.yaml               # Node and edge definitions
│   ├── nodes/                   # Individual skill nodes
│   └── challenges/              # Challenge project specifications
│
├── blueprints/                  # App pattern blueprints
│   ├── registry.yaml            # Blueprint index
│   └── [blueprint-name]/        # Individual blueprints
│
├── reference/                   # Canonical implementations
│   ├── by-blueprint/            # Examples organized by blueprint
│   └── by-technique/            # Examples organized by technique
│
├── publication/                 # Publication pipeline configs
│   ├── targets/                 # Deployment target configs
│   ├── checklists/              # Pre-publication requirements
│   └── templates/               # Scaffolding templates
│
└── journals/                    # Developer journals
    └── .template/               # Journal template
```

## Working with Claude Code

The forge is designed to be navigated and operated *with* Claude Code:

### Navigation Mode
Ask Claude Code to assess your position, recommend skill paths, and find relevant content.

### Teaching Mode
At any skill node, Claude Code explains concepts, runs validations, and provides feedback.

### Forge Mode
When instantiating blueprints, Claude Code walks through decisions and generates code.

### Publication Mode
Claude Code guides you through checklists, documentation, and deployment.

## Blueprints

| Blueprint | Description | Skill Level |
|-----------|-------------|-------------|
| [Conversational Assistant](blueprints/conversational-assistant/) | Multi-turn dialogue with context management | Beginner |
| [Document Processor](blueprints/document-processor/) | Analyze and transform documents | Intermediate |
| *More coming...* | | |

## Validation Status

Content is continuously validated against the Claude SDK:

- 🟢 Validated against current SDK within 7 days
- 🟡 Validated against previous SDK version
- 🔴 Validation failing or stale

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Adding curriculum nodes
- Creating new blueprints
- Improving validation coverage

## Roadmap

See [ROADMAP.md](ROADMAP.md) for version planning from v0.1 through v10.5.7.

## License

MIT License - See [LICENSE](LICENSE)
