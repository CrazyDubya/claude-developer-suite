# Claude Agent Manager

**Scalable agent organization system for Claude Code that prevents context window overflow while enabling intelligent agent discovery and management.**

## 🎯 Overview

The Claude Agent Manager v2.0 provides **complete physical control** over which agents Claude Code sees, solving the fundamental challenge of context window overflow. Through an innovative shadow directory system, you can manage unlimited agents while Claude Code only sees the specific ones you choose.

**v2.0 Shadow System Features:**
- **Physical Agent Control**: Move agents between archive ↔ active directories
- **Zero Context Overflow**: Claude Code only sees agents you explicitly activate
- **Unlimited Storage**: Archive holds thousands of agents without affecting performance
- **Intelligent Discovery**: Fast search across all archived agents
- **Profile Switching**: Instantly switch between complete agent configurations
- **Safe Operations**: Multiple backups and atomic operations prevent data loss

## 🛡️ Safety First

**Your existing agents are designed to remain safe.** The Agent Manager follows a non-destructive approach:

✅ **Read-Only Operations**: Original agent files are only read for indexing, never modified  
✅ **Database Indexing**: Creates searchable indexes without touching source files  
✅ **Backup System**: Provides backup functionality for peace of mind  
✅ **Multi-Source Support**: Works with global (`~/.claude/agents/`) and project (`.claude/agents/`) agents  
✅ **Custom Agent Integration**: Designed to work with your existing custom agents  
✅ **Rollback Options**: Includes backup/restore functionality  

**Approach**: The system is designed to be non-destructive, but as with any software, we recommend backing up important files before installation.

## 🏗️ Architecture

```
claude-agent-manager/
├── agents/                          # Sample agent definitions
│   ├── react-specialist.md
│   ├── python-specialist.md
│   ├── api-specialist.md
│   ├── database-specialist.md
│   └── testing-specialist.md
├── commands/
│   └── agent-manager.sh            # Main CLI interface
├── agent-registry/
│   ├── setup.py                   # Database & indexing system
│   ├── domains/                   # Domain-based organization
│   ├── capabilities/              # Capability-based grouping
│   └── projects/
│       ├── templates/             # Project templates
│       └── profiles/              # Pre-configured agent sets
├── docs/                          # Additional documentation
└── examples/                      # Usage examples
```

## 🔄 Shadow System (v2.0) - Complete Control

The shadow directory system gives you **physical control** over what Claude Code sees by managing which agent files are present in the active directories.

### How It Works

```
Claude Code sees:          Shadow System manages:
~/.claude/agents/           ~/.claude-agent-manager/archive/
├── react-specialist.md     ├── global/
└── nodejs-specialist.md    │   ├── react-specialist.md
    (Only 2 agents)        │   ├── python-specialist.md  
                            │   ├── ... (115+ more agents)
                            └── project/
                                └── ... (project agents)
```

### Shadow System Commands

```bash
# Initialize shadow system (archive all existing agents)
/agent-manager shadow-init

# Activate specific agents (Claude Code can see them)
/agent-manager activate react-specialist nodejs-specialist testing-specialist

# Deactivate agents (hide from Claude Code)
/agent-manager deactivate pandas-specialist

# Switch to complete profile (replace all active agents)
/agent-manager switch web-fullstack

# Check what Claude Code currently sees
/agent-manager status
/agent-manager active

# Browse available archived agents
/agent-manager archived
/agent-manager archived --source global
```

### Workflow Example

```bash
# Start fresh - Claude Code sees 0 agents
/agent-manager shadow-init
# → Archives 100+ agents, leaves directories empty

# Work on React project - activate only what you need
/agent-manager activate react-specialist nodejs-specialist css-specialist
# → Claude Code now sees exactly 3 agents

# Switch to data science project
/agent-manager switch data-science
# → Deactivates web agents, activates pandas, numpy, etc.

# Add specific agent temporarily
/agent-manager activate testing-specialist
# → Now includes testing agent with data science stack

# Check what's currently active
/agent-manager active
# → Shows exactly which agents Claude Code can see
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/CrazyDubya/Claude-dynamic-agents.git
cd Claude-dynamic-agents

# Make scripts executable
chmod +x commands/agent-manager.sh
chmod +x agent-registry/setup.py

# Install Python dependencies
pip install sqlite3 pyyaml

# Initialize the agent database
python agent-registry/setup.py
```

### 2. Shadow System Setup (Recommended)

```bash
# Initialize shadow system (archives all existing agents)
./commands/agent-manager.sh shadow-init

# Activate agents for your current project
./commands/agent-manager.sh activate react-specialist nodejs-specialist css-specialist

# Check what Claude Code currently sees
./commands/agent-manager.sh status
```

### 3. Traditional Usage (Without Shadow System)

```bash
# Initialize a project with web development agents
./commands/agent-manager.sh setup web

# Search for agents without loading them
./commands/agent-manager.sh search "testing python" --limit 5

# View project manifest
./commands/agent-manager.sh manifest show

# Save current configuration as a reusable profile
./commands/agent-manager.sh profile save my-web-stack
```

### 3. Integration with Claude Code

Copy the agent manager to your Claude Code commands directory:

```bash
cp commands/agent-manager.sh ~/.claude/commands/
cp -r agent-registry ~/.claude/
```

Then use in Claude Code with slash commands:

```bash
/agent-manager setup data-science
/agent-manager search --domain backend --capability optimization
/agent-manager profile load my-saved-configuration
```

## 📚 Core Concepts

### Project Manifests

Each project contains a `.claude-agents` manifest file that controls which agents are loaded:

```yaml
# .claude-agents
agents:
  - name: react-specialist
    description: Expert in React framework and modern patterns
  - name: testing-specialist
    description: Comprehensive testing strategies and quality assurance
  
config:
  max_agents: 15
  respect_priority: true
```

### Agent Registry

Agents are indexed in a SQLite database by:
- **Domains**: web, backend, data-science, infrastructure, graphics, mobile, desktop
- **Capabilities**: testing, optimization, debugging, generation, analysis
- **Tags**: programming languages, frameworks, specific technologies

### Intelligent Search

Fast agent discovery using multiple criteria:

```bash
# Search by domain
/agent-manager search --domain web --limit 10

# Search by capability
/agent-manager search --capability testing

# Combined search with keywords
/agent-manager search "api python" --domain backend
```

## 🎨 Agent Profiles

Pre-configured agent sets for common project types:

### Web Full-Stack
- **Agents**: react-specialist, nodejs-specialist, database-optimizer, testing-specialist
- **Use Case**: Complete web application development
- **Load**: `/agent-manager profile load web-fullstack`

### Data Science
- **Agents**: pandas-specialist, scikit-learn-specialist, plotly-specialist, jupyter-specialist
- **Use Case**: Data analysis and machine learning projects
- **Load**: `/agent-manager profile load data-science`

### AI Infrastructure
- **Agents**: fastapi-specialist, pytorch-specialist, docker-specialist, monitoring-specialist
- **Use Case**: ML/AI service development and deployment
- **Load**: `/agent-manager profile load ai-infrastructure`

## 🔧 Command Reference

### Shadow System Commands (v2.0)
```bash
/agent-manager shadow-init              # Initialize shadow system (archive all agents)
/agent-manager activate <agents>        # Move agents from archive → active (Claude Code sees them)
  --source <global|project>             # Specify source (default: global)
/agent-manager deactivate <agents>      # Move agents from active → archive (hide from Claude Code)
  --source <global|project>             # Specify source (default: global)
/agent-manager switch <profile>         # Replace all active agents with profile agents
/agent-manager status                   # Show shadow system status and active agents
/agent-manager active                   # List currently active agents (what Claude Code sees)
/agent-manager archived                 # List archived agents (available for activation)
  --source <global|project>             # Filter by source
/agent-manager emergency-restore <name> # Restore from shadow system backup
```

### Setup Commands
```bash
/agent-manager setup [project-type]    # Initialize project with relevant agents
/agent-manager index                    # Re-index all agents in registry
```

### Search Commands
```bash
/agent-manager search <query>           # Search agents by keywords
  --domain <domain>                     # Filter by domain
  --capability <capability>             # Filter by capability  
  --source <global|project>             # Filter by source location
  --limit <number>                      # Limit results (default: 20)
```

### Profile Management
```bash
/agent-manager profile save <name>      # Save current manifest as profile
/agent-manager profile load <name>      # Load saved profile
/agent-manager profile list             # List all saved profiles
/agent-manager profile merge <name>     # Merge profile with current setup
```

### Manifest Management
```bash
/agent-manager manifest show            # Display current project manifest
/agent-manager manifest validate        # Check manifest for errors
/agent-manager manifest create <type>   # Create new manifest
/agent-manager manifest backup          # Backup current manifest
```

### Safety & Backup Commands
```bash
/agent-manager backup                   # Create timestamped backup of all agents
/agent-manager restore <timestamp>      # Restore agents from backup
/agent-manager verify                   # Verify agent file integrity
/agent-manager sources                  # List all agent source locations
```

### Import/Export
```bash
/agent-manager import <path>            # Import custom agents from directory
/agent-manager export --format <type>   # Export agent configurations (json/yaml)
```

### Statistics & Information
```bash
/agent-manager stats                    # Show registry statistics
/agent-manager domains                  # List available domains
/agent-manager capabilities             # List available capabilities
```

## 📊 Scalability Features

### Billions of Agents Support

The system is designed to scale efficiently:

- **SQLite Database**: Fast queries on millions of agent records
- **Indexed Search**: Domain, capability, and full-text indexes
- **Lazy Loading**: Agent details loaded only when needed
- **Hierarchical Organization**: Domain/capability-based agent grouping

### Context Window Management

Prevents context overflow through:

- **Project Manifests**: Only listed agents are loaded (typically 10-15)
- **Intelligent Selection**: Automatic agent recommendation based on project type
- **Dynamic Loading**: Add/remove agents during development as needed
- **Profile System**: Reusable configurations for common scenarios

## 🛠️ Development

### Adding New Agents

1. Create agent definition file in `agents/` directory
2. Include proper YAML frontmatter with name, description, and tools
3. Re-index the database: `python agent-registry/setup.py`

Example agent structure:

```markdown
---
name: my-specialist
description: Expert in specific technology or domain
tools: Read, Write, Edit, MultiEdit, Grep, Glob, Bash
---

# My Specialist

## Overview
Detailed description of the agent's capabilities...

## Core Expertise
- Skill 1
- Skill 2
- Skill 3

## Implementation Examples
Code examples and technical details...
```

### Creating Custom Profiles

```bash
# Create agents for your specific use case
/agent-manager search "your requirements" --domain relevant-domain

# Modify .claude-agents manifest as needed
# Save as reusable profile
/agent-manager profile save custom-stack-name
```

### Extending the System

The agent manager is modular and extensible:

- **Database Schema**: Add new agent metadata fields
- **Search Algorithms**: Enhance agent matching logic  
- **CLI Commands**: Add new subcommands for specific workflows
- **Integration Points**: Connect with CI/CD, IDEs, or other tools

## 📈 Benefits

### For Individual Developers
- ✅ Never overwhelmed by too many agents
- ✅ Quick discovery of relevant specialists
- ✅ Consistent setups across projects
- ✅ Focus on coding, not agent management

### For Teams
- ✅ Share proven agent configurations
- ✅ Standardize development toolchains
- ✅ Onboard new developers quickly
- ✅ Scale expertise across the organization

### For Organizations
- ✅ Manage thousands of custom agents
- ✅ Enforce standards and best practices
- ✅ Track agent usage and effectiveness
- ✅ Build institutional knowledge

## 🔮 Future Roadmap

- **Dependency Resolution**: Auto-include supporting agents
- **Learning System**: Recommend agents based on success patterns
- **Version Management**: Handle agent updates and compatibility
- **Cloud Sync**: Share profiles across devices and teams
- **Analytics**: Track agent effectiveness and usage patterns
- **Integration APIs**: Connect with external development tools

## 📄 License

This project is available under a **Revenue-Restricted MIT License**:

- ✅ **Free for personal use, education, and small businesses** (<$1M revenue)
- ✅ **Open source contributions welcome from anyone**  
- ✅ **Large companies can use internally but need permission to commercialize**
- ⚠️ **Commercial licensing available for large enterprises**

See [LICENSE](LICENSE) file for complete terms.

## 🤝 Contributing

We welcome contributions! Please see CONTRIBUTING.md for guidelines.

## 📞 Support

- **Issues**: Report bugs and request features on GitHub Issues
- **Documentation**: Additional docs in the `/docs` directory
- **Examples**: See `/examples` for common usage patterns

---

**Transform your Claude Code experience from overwhelming to intelligently curated.**