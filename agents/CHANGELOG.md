# Changelog

All notable changes to the Claude Agent Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-09-08

### 🛡️ Added - Safety & Multi-Source Features

- **Multi-Source Agent Support**: Automatically scans both global (`~/.claude/agents/`) and project (`.claude/agents/`) agent directories
- **Backup System**: Provides backup and restore functionality for agent configurations
- **Agent Source Tracking**: Database tracks whether agents come from global or project sources
- **Custom Agent Integration**: Designed to work with user's existing custom agents
- **Non-Destructive Design**: Read-only operations on original agent files

### 🔧 Added - New Commands

**Safety & Backup:**
- `/agent-manager backup` - Create timestamped backup of agent configurations
- `/agent-manager restore <timestamp>` - Restore from specific backup
- `/agent-manager verify` - Verify agent file integrity
- `/agent-manager sources` - List all detected agent source locations

**Import/Export:**
- `/agent-manager import <path>` - Import custom agents from directory
- `/agent-manager export --format <json|yaml>` - Export agent configurations

**Enhanced Search:**
- `--source <global|project>` option to filter agents by source location

**Profile Management:**
- `/agent-manager profile merge <name>` - Merge profile with current setup
- `/agent-manager manifest backup` - Backup current project manifest

### 🔄 Changed

- **Database Schema**: Added `source` and `is_custom` columns to agents table
- **Agent Scanning**: Now scans multiple directories automatically
- **Conflict Resolution**: Project-level agents take precedence over global agents with same name
- **Search Results**: Display agent source (global/project) in search results

### 📚 Documentation

- Added **Safety First** section explaining non-destructive approach
- Updated command reference with all new safety and import/export features
- Created **Revenue-Restricted MIT License** for fair use
- Added migration guidance for existing users

### ⚠️ Breaking Changes

**None.** This release maintains full backward compatibility.

---

## [1.0.0] - 2024-09-08

### 🎉 Initial Release

**Core Features:**
- SQLite-based agent registry with intelligent indexing
- Project-specific agent manifests to prevent context window overflow
- Slash command interface (`/agent-manager`) for Claude Code integration
- Pre-configured profiles for common project types

**Sample Agents:**
- `react-specialist` - Modern React development
- `python-specialist` - Full-stack Python development
- `api-specialist` - API design and integration
- `database-specialist` - Database optimization
- `testing-specialist` - Testing strategies

**Agent Profiles:**
- Web Full-Stack: React, Node.js, testing, deployment
- Data Science: Python ML/data analysis toolkit
- AI Infrastructure: MLOps and AI service deployment

---

## [2.0.0] - 2024-09-08

### 🎯 MAJOR RELEASE - Shadow Directory System

**Revolutionary feature: Complete physical control over which agents Claude Code sees!**

### 🏗️ Added - Shadow Directory Architecture

- **Physical Agent Control**: Move agents between archive ↔ active directories
- **Shadow Manager**: Core file operations and state management system  
- **Complete CLI Integration**: 8 new shadow management commands
- **Zero Context Overflow**: Claude Code only sees agents you explicitly activate
- **Unlimited Agent Storage**: Archive system handles thousands of agents without performance impact

### 🔧 Added - New Shadow Commands

**Core Shadow Operations:**
- `/agent-manager shadow-init` - Initialize shadow system (archive all existing agents)
- `/agent-manager activate <agents>` - Move agents from archive → active (Claude Code sees them)
- `/agent-manager deactivate <agents>` - Move agents from active → archive (hide from Claude Code)
- `/agent-manager switch <profile>` - Replace all active agents with profile agents
- `/agent-manager status` - Show shadow system status and active agents
- `/agent-manager active` - List currently active agents (what Claude Code sees)
- `/agent-manager archived` - List archived agents (available for activation)
- `/agent-manager emergency-restore <name>` - Restore from shadow system backup

**Enhanced Safety:**
- **Atomic Operations**: All-or-nothing file moves with comprehensive backups
- **State Tracking**: YAML-based state management with timestamps
- **Automatic Backups**: Every operation creates timestamped backup
- **Emergency Recovery**: Full restore capabilities from any backup point

### 🔄 Changed - System Architecture

- **Database Schema**: Compatible migration system for existing v1.1.0 installations
- **Dual Mode Operation**: Shadow system optional - existing functionality unchanged
- **Archive Directory**: `~/.claude-agent-manager/archive/` for unlimited agent storage
- **State Management**: `~/.claude-agent-manager/state.yml` tracks active/archived agents

### 💡 How Shadow System Works

```
Before Shadow System:
~/.claude/agents/
├── agent1.md
├── agent2.md
├── ... (100+ agents)  ← Claude Code sees ALL agents

After Shadow System:
~/.claude/agents/           ~/.claude-agent-manager/archive/
├── react-specialist.md     ├── global/
└── nodejs-specialist.md    │   ├── pandas-specialist.md
   (Only 2 agents)         │   ├── python-specialist.md
                            │   └── ... (100+ archived)
                            └── project/
```

### 🎨 User Experience Improvements

- **Instant Context Control**: Activate exactly the agents you need for each project
- **Profile Switching**: Switch between complete agent configurations instantly
- **Real-time Status**: Always know exactly what Claude Code can see
- **Safe Experimentation**: Try different agent combinations without risk
- **Scalable Growth**: Add unlimited agents without affecting Claude Code performance

### 📚 Documentation Updates

- **Complete README Rewrite**: Shadow system workflow and examples
- **Command Reference**: All 8 new shadow commands documented
- **Migration Guide**: Seamless upgrade path from v1.1.0
- **Architecture Diagrams**: Visual explanation of shadow system operation

### ⚠️ Breaking Changes

**None.** This release maintains full backward compatibility with v1.1.0. Shadow system is opt-in via `/agent-manager shadow-init`.

### 🚀 Performance Impact

- **Zero Performance Degradation**: Only active agents loaded by Claude Code
- **Unlimited Scale**: Archive thousands of agents with no context window impact
- **Instant Operations**: Agent activation/deactivation in milliseconds
- **Memory Efficient**: State tracking uses minimal system resources

---

## [Unreleased]

### 🔮 Planned Features

- **Profile Learning**: AI-powered agent recommendations based on usage patterns
- **Dependency Resolution**: Auto-include supporting agents for complex workflows
- **Cloud Sync**: Share profiles and configurations across devices
- **Analytics Dashboard**: Usage tracking and effectiveness metrics
- **Integration APIs**: Connect with CI/CD pipelines and development tools
- **Agent Auto-Discovery**: Automatic detection and indexing of community agents

### 📄 License

Revenue-Restricted MIT License:
- Free for personal use and businesses <$1M revenue
- Commercial licensing available for large enterprises
- Open source contributions welcome