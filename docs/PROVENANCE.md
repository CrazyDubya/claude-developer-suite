# Provenance — Claude Developer Suite

Clean-copy consolidation, 2026-09-13. Source repos archived (not deleted) after verification.

| Destination | Source repo | Source HEAD | HEAD date | Notes |
|---|---|---|---|---|
| `skills/` | [claude-developer-suite](https://github.com/CrazyDubya/claude-developer-suite) | `0310e75b9c08` | 2026-08-31 | skills/ = 12 skill dirs + lib/ + data/ + scripts/ |
| `agents/` | [Claude-dynamic-agents](https://github.com/CrazyDubya/Claude-dynamic-agents) | `f8333513ca83` | 2025-11-14 | full copy: agent-registry/, agents/, commands/, examples/ |
| `apps/launcher/` | [claude-mcp-launcher](https://github.com/CrazyDubya/claude-mcp-launcher) | `665dc21b6892` | 2025-05-22 | full copy: main.py, config_manager.py, launch_manager.py, build_app.py |
| `apps/artifacts/` | [Claude-Artifacts](https://github.com/CrazyDubya/Claude-Artifacts) | `c49303068b97` | 2025-11-15 | full copy EXCEPT app-analyzer/node_modules/ (~900 vendored files dropped; reinstall via npm install) |
| `bridges/telegram/` | [SpreadtheEcho](https://github.com/CrazyDubya/SpreadtheEcho) | `70fefa920ed7` | 2026-02-21 | full copy: claude-telegram-bridge.py, scripts/watchdog.py, identity/, config/ |
| `forge/` | [ClaudeApp](https://github.com/CrazyDubya/ClaudeApp) | `5e9733309fdb` | 2025-12-30 | full copy: .forge/agent-abstraction-layer/, blueprints/, curriculum/, agent.manifest.yaml |

Also folded into private `claude-daemon` (kept standalone, not part of this suite): `recursion` docs (7 files, HEAD `8144a41e42ae`, 2026-01-23) → `claude-daemon/docs/recursion/`.

Excluded: `claude-daemon` (private journal, standalone), `claude-code-config` (private ~/.claude backup), `claude-play` (Gemma client, off-theme).
