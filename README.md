# claude-skills

Twelve Claude Code skills, plus a SQLite layer for tracking them.

## The skills

Each is a directory containing a `SKILL.md`, and where useful `reference/`, `templates/` and `scripts/`. Twelve `SKILL.md` files are present. Among them: `accessibility-auditor`, `api-documentation-generator`, `code-style-enforcer`, `configuration-validator`, `database-migration-helper`, `dependency-audit-assistant`, `docker-optimizer`, `error-tracking-integrator`, `git-workflow-enforcer`, `internationalization-helper`, `performance-profiler`.

`database-migration-helper` ships templates for Alembic, Knex, Prisma, Rails, Sequelize and TypeORM. `docker-optimizer` ships an optimized Dockerfile and a `.dockerignore`. `dependency-audit-assistant` includes a license-checking script and vulnerability and license references.

## The database

Per `DATABASE_README.md`:

- `scripts/init_db.py` scans `~/.claude/skills/` and populates `data/skills_metadata.db` with metadata, templates, scripts and references.
- `scripts/skill_dashboard.py` reads it back, interactively or as quick views.
- `lib/skill_db.py` is the access layer; `data/schema.sql` the schema.

## Installing

Copy the skill directories into `~/.claude/skills/`, then run `python3 scripts/init_db.py`.
