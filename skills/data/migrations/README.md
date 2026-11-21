# Skills error-report view upgrade

Fresh installations use the corrected `skill_errors` view in `data/schema.sql`.
Existing databases keep the old persisted view even when schema.sql changes.
Do not delete the database or rerun the broad skill registry initializer to fix
this report.

An explicit, optional one-view upgrade is available after reviewing the change
and backing up the database with your usual process:

```sh
python3 ~/.claude/skills/scripts/upgrade_error_view.py --db ~/.claude/skills/data/skills_metadata.db
```

Run this only for the existing skills database you intend to upgrade. The path
is required and a missing database is refused. Nothing runs automatically during
normal reads, logging or initialization. This command replaces only the derived
`skill_errors` view in a transaction and prepares the new view before committing.
It does not delete, repopulate or rewrite stored history, feedback, registry
metadata or other views/tables. Repeating it is safe for the same view definition.
An error rolls back the view replacement. It requires normal SQLite write access
and can wait for or fail on another writer's lock; no force-unlock is attempted.

The report still counts every failed execution, ignores successful executions,
deduplicates message text and joins distinct non-NULL messages with ` | `. NULL
messages still count as failed executions. No stable message ordering is promised.

This is migration tooling to review for adoption, not approval to run it on an
existing user's database. No operational migration is performed by installing
or reviewing these files.
