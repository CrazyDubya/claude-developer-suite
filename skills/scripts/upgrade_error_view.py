#!/usr/bin/env python3
"""Explicitly upgrade only skill_errors in an existing skills database."""

import argparse
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path,
                        help='Existing skills database to upgrade; no database is created')
    args = parser.parse_args()
    database = args.db.expanduser().resolve()
    migration = Path(__file__).resolve().parents[1] / 'data/migrations/001_skill_errors.sql'
    try:
        # Read/write mode refuses a missing database instead of creating one.
        connection = sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)
        try:
            connection.executescript(migration.read_text(encoding='utf-8'))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as error:
        parser.exit(1, f'Error-report view upgrade failed: {error}\n')
    print(f'Updated skill_errors view in {database}; stored rows unchanged.')


if __name__ == '__main__':
    main()
