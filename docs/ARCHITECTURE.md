# Architecture — Claude Developer Suite

A monorepo of complementary Claude/Claude-Code tooling. Components are independently installable; there is no shared Python environment.

## Components

- **skills/** — 12 Claude Code skills (SKILL.md + reference/templates/scripts each), plus a SQLite tracking layer (`lib/skill_db.py`, `data/skills_metadata.db`, `scripts/init_db.py`, `scripts/skill_dashboard.py`). Pure Markdown + stdlib Python.
- **agents/** — Claude Agent Manager: a scalable agent-organization system built around a shadow directory system (`agent-registry/shadow_manager.py`) so Claude Code only sees a subset of agents, preventing context-window overflow. Agents ≠ skills: skills are capabilities, agents are personas/profiles.
- **apps/launcher/** — macOS desktop app (tkinter; `build_app.py` → .app bundle) for managing and launching Claude Desktop with different MCP server configurations. macOS-only.
- **apps/artifacts/** — Local Claude Artifact renderer: drop a Claude-generated React component into a sub-dir and it renders, with security validation (XSS/injection checks, dependency analysis in `app-analyzer/`). Run `npm install` in `app-analyzer/` first — `node_modules/` was deliberately not committed.
- **bridges/telegram/** — "Echo": a Telegram bridge to a Claude Code instance (`claude-telegram-bridge.py` v10) with persistent memory, semantic search (chromadb), self-healing process management (`scripts/watchdog.py`), and an identity system (`identity/IDENTITY.md`). Heavy optional deps: see `requirements/telegram.txt`.
- **forge/** — "Claude App Forge": a version-controlled apprenticeship system where Claude Code acts as forge-master guiding app creation. Core primitives in `.forge/agent-abstraction-layer/` (Python: core, runtime, observability, uncertainty), `blueprints/`, `curriculum/`, `agent.manifest.yaml`.

## How they compose

skills + agents extend Claude Code itself (capabilities + agent registry). launcher configures Claude Desktop's MCP servers. artifacts renders Claude's React output locally. telegram bridges Claude Code to a phone. forge is a meta-system for building apps *with* Claude Code. They share no code — they share an audience.

## Tech debt

- No CI anywhere; add a minimal workflow that at least parses each component's entry points.
- No real test suites (only `apps/artifacts/test_suite.py`); contributions welcome.
