# claude-skills

Twelve Claude Code skills, plus a SQLite layer for tracking and inspecting them.

## The skills

`accessibility-auditor`, `api-documentation-generator`, `code-style-enforcer`, `configuration-validator`, `database-migration-helper`, `dependency-audit-assistant`, `docker-optimizer`, `error-tracking-integrator`, `git-workflow-enforcer`, `internationalization-helper`, `performance-profiler`.

Each is a directory with a `SKILL.md` and, where useful, `reference/`, `templates/` and `scripts/`. The migration helper ships templates for Alembic, Knex, Prisma, Rails, Sequelize and TypeORM; the docker optimizer ships an optimized Dockerfile and dockerignore.

## The database

`scripts/init_db.py` scans the skills directory and populates `data/skills_metadata.db` with metadata, templates, scripts and references. `scripts/skill_dashboard.py` reads it back, interactively or as quick views. `lib/skill_db.py` holds the access layer and `data/schema.sql` the schema. See `DATABASE_README.md`.

## Installing

Copy the skill directories into `~/.claude/skills/`, then run `python3 scripts/init_db.py`.
