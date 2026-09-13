# Publication Pipelines

This directory contains configurations and guides for publishing your Claude-powered applications.

## Supported Targets

| Target | Description | Best For |
|--------|-------------|----------|
| [npm](targets/npm.md) | Node.js package registry | JS/TS libraries and tools |
| [PyPI](targets/pypi.md) | Python Package Index | Python libraries and tools |
| [Docker](targets/docker.md) | Container registry | Deployable services |
| [GitHub](targets/github.md) | GitHub releases | Open source projects |

## Publication Workflow

```
1. Complete Development
        │
        ▼
2. Run Pre-Publication Checklist
   └── Security review
   └── Documentation check
   └── License verification
   └── Test coverage
        │
        ▼
3. Prepare Release
   └── Version bump
   └── Changelog update
   └── Build artifacts
        │
        ▼
4. Publish
   └── Target-specific steps
   └── Announcements
        │
        ▼
5. Post-Publication
   └── Monitor for issues
   └── Update documentation
```

## Quick Start

1. Review the appropriate checklist in `checklists/`
2. Use templates in `templates/` for standard files
3. Follow target-specific guide in `targets/`
4. Ask Claude Code: "Help me publish to [target]"
