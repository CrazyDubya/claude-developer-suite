# Claude Developer Suite

One monorepo for Claude/Claude-Code tooling — skills, agent management, a desktop MCP launcher, a local Artifact renderer, a Telegram bridge, and an app-building forge. Each component installs and runs independently; see `docs/ARCHITECTURE.md` for how they compose.

## Layout

| Path | What | Source |
|---|---|---|
| `skills/` | 12 Claude Code skills + SQLite tracking layer | claude-skills |
| `agents/` | Claude Agent Manager (shadow-directory agent registry) | Claude-dynamic-agents |
| `apps/launcher/` | macOS app to manage/launch Claude Desktop w/ MCP configs | claude-mcp-launcher |
| `apps/artifacts/` | Local Artifact renderer w/ security validation (`npm install` first) | Claude-Artifacts |
| `bridges/telegram/` | Telegram bridge to a Claude Code instance | SpreadtheEcho |
| `forge/` | Version-controlled app-building apprenticeship system | ClaudeApp |
| `docs/` | Provenance table + architecture notes | — |

## Install

Per-component — there is no single root requirements file by design:

```bash
pip install -r requirements/skills.txt      # light
pip install -r requirements/agents.txt
pip install -r requirements/launcher.txt    # macOS only
pip install -r requirements/telegram.txt    # heavy: chromadb, sentence-transformers
pip install -r requirements/forge.txt
cd apps/artifacts/app-analyzer && npm install
```

## Provenance

Clean-copy consolidation from six repos (histories 1–10 commits; subtree added nothing). Full source→destination mapping in `docs/PROVENANCE.md`. Source repos were archived, never deleted.
