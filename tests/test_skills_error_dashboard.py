"""Full installed-layout initializer/logging/dashboard and opt-in upgrade tests."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SUITE_SOURCE', Path(__file__).resolve().parents[1]))
LEGACY_VIEW = """CREATE VIEW skill_errors AS
SELECT skill_name, COUNT(*) as error_count, MAX(executed_at) as last_error,
GROUP_CONCAT(DISTINCT error_message, ' | ') as error_messages
FROM skill_executions WHERE success = 0
GROUP BY skill_name ORDER BY error_count DESC;"""


class ErrorDashboardConsumer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-error-view-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.target = self.home / '.claude/skills'
        self.target.mkdir(parents=True)
        for part in ['scripts', 'lib', 'data']:
            shutil.copytree(ROOT / 'skills' / part, self.target / part)
        fixture = self.target / 'synthetic-local'
        fixture.mkdir()
        (fixture / 'SKILL.md').write_text('---\nname: synthetic-local\ndescription: Synthetic reporting fixture\nallowed-tools: Read\n---\nFixture.\n')
        guard = self.home / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(
            'import socket, pathlib, os\n'
            'def blocked(*args, **kwargs):\n'
            '    pathlib.Path(os.environ["GUARD_ATTEMPTS"]).write_text("attempted")\n'
            '    raise AssertionError("Network prohibited")\n'
            'socket.socket.connect = blocked\n'
            'socket.create_connection = blocked\n')
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(guard),
                        GUARD_ATTEMPTS=str(self.home / 'network-attempts'),
                        PYTHONDONTWRITEBYTECODE='1')
        self.db = self.target / 'data/skills_metadata.db'
        # Fresh-schema tests start without the repository's shipped initialized DB.
        if self.db.exists():
            self.db.unlink()  # Temporary copied fixture only, never a user database.
        self.run_script('init_db.py')

    def execute(self, args, stdin=None, expect=0):
        result = subprocess.run([sys.executable, *map(str, args)], cwd=self.home,
                                env=self.env, input=stdin, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        self.assertFalse((self.home / 'network-attempts').exists())
        return result

    def run_script(self, name, *args, stdin=None, expect=0):
        return self.execute([self.target / 'scripts' / name, *args], stdin, expect)

    def log_fixture(self):
        code = '''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.home()/'.claude/skills/lib'))
from skill_db import SkillDB
d=SkillDB()
for message in ['Synthetic, transport unavailable','Synthetic, transport unavailable','Synthetic | second message',None]:
 d.log_execution('synthetic-local',duration_ms=12,success=False,error_message=message)
d.log_execution('synthetic-local',duration_ms=14,success=True,error_message='Successful note must be excluded')
d.add_feedback('synthetic-local',rating=4,helpful=True,comments='Synthetic feedback to preserve')
'''
        self.execute(['-c', code])

    def errors(self):
        result = self.execute(['-c', '''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.home()/'.claude/skills/lib'))
from skill_db import SkillDB
print(json.dumps(SkillDB().get_skill_errors()))
'''])
        return json.loads(result.stdout)

    def snapshot(self):
        with sqlite3.connect(self.db) as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            rows = {name: connection.execute('SELECT * FROM "' + name.replace('"','""') + '" ORDER BY rowid').fetchall() for name in tables}
            schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name != 'skill_errors' ORDER BY type,name").fetchall()
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            return rows, schema, version

    def install_legacy_view(self):
        with sqlite3.connect(self.db) as connection:
            connection.execute('DROP VIEW skill_errors')
            connection.execute(LEGACY_VIEW)
            connection.execute("UPDATE skills_registry SET version='synthetic-custom-version', description='Preserve custom metadata'")
            connection.execute('PRAGMA user_version=7')
        with sqlite3.connect(self.db) as connection:
            with self.assertRaisesRegex(sqlite3.OperationalError, 'DISTINCT aggregates'):
                connection.execute('SELECT * FROM skill_errors').fetchall()

    def test_fresh_empty_error_dashboard_and_interactive_menu(self):
        result = self.run_script('skill_dashboard.py', 'errors')
        self.assertIn('No errors recorded', result.stdout)
        result = self.run_script('skill_dashboard.py', stdin='7\n8\n')
        self.assertIn('No errors recorded', result.stdout)
        self.assertGreaterEqual(result.stdout.count('Claude Skills Dashboard - Menu'), 2)

    def test_fresh_public_logging_deduplicates_messages_but_counts_every_failure(self):
        self.log_fixture()
        self.run_script('skill_dashboard.py', 'activity')
        self.run_script('skill_dashboard.py', 'errors')
        rows = self.errors()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['error_count'], 4)
        self.assertEqual(rows[0]['skill_name'], 'synthetic-local')
        messages = rows[0]['error_messages']
        self.assertEqual(messages.count('Synthetic, transport unavailable'), 1)
        self.assertEqual(messages.count('Synthetic | second message'), 1)
        self.assertNotIn('Successful note', messages)
        self.assertIn(' | ', messages)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM skill_executions').fetchone()[0], 5)

    def test_explicit_legacy_upgrade_preserves_all_rows_metadata_and_is_idempotent(self):
        self.log_fixture()
        self.install_legacy_view()
        before = self.snapshot()
        self.run_script('upgrade_error_view.py', '--db', self.db)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.errors()[0]['error_count'], 4)
        first = self.errors()
        self.run_script('upgrade_error_view.py', '--db', self.db)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.errors(), first)
        result = self.run_script('skill_dashboard.py', stdin='7\n8\n')
        self.assertIn('synthetic-local', result.stdout)

    def test_failed_upgrade_rolls_back_and_missing_path_never_creates_database(self):
        self.log_fixture()
        self.install_legacy_view()
        before = self.snapshot()
        with sqlite3.connect(self.db) as connection:
            original_view = connection.execute("SELECT sql FROM sqlite_master WHERE name='skill_errors'").fetchone()[0]
        migration = self.target / 'data/migrations/001_skill_errors.sql'
        # Deliberate local fault after DROP tests the explicit tool's rollback path.
        migration.parent.mkdir(exist_ok=True)
        migration.write_text('BEGIN IMMEDIATE; DROP VIEW skill_errors; SELECT * FROM synthetic_missing_table;')
        self.run_script('upgrade_error_view.py', '--db', self.db, expect=1)
        self.assertEqual(self.snapshot(), before)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT sql FROM sqlite_master WHERE name='skill_errors'").fetchone()[0], original_view)
        absent = self.home / 'missing.db'
        self.run_script('upgrade_error_view.py', '--db', absent, expect=1)
        self.assertFalse(absent.exists())

    def test_shipped_initialized_database_requires_explicit_upgrade_and_keeps_rows(self):
        shutil.copy2(ROOT / 'skills/data/skills_metadata.db', self.db)
        self.log_fixture()
        before = self.snapshot()
        self.run_script('upgrade_error_view.py', '--db', self.db)
        self.assertEqual(self.snapshot(), before)
        rows = self.errors()
        fixture = [row for row in rows if row['skill_name'] == 'synthetic-local']
        self.assertEqual(fixture[0]['error_count'], 4)
        self.run_script('skill_dashboard.py', 'errors')
