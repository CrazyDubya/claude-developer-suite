"""Prevent new duplicate physical resource rows during full public initialization."""
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SUITE_SOURCE', Path(__file__).resolve().parents[1]))
TABLES = [('skill_templates', 'template', 'templates', 'fixture.txt'),
          ('skill_scripts', 'script', 'scripts', 'fixture.py'),
          ('skill_references', 'reference', 'reference', 'fixture.md')]


class RepeatResourceInitialization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-reinit-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.target = self.home / '.claude/skills'
        self.target.mkdir(parents=True)
        for name in ['scripts', 'lib', 'data']:
            shutil.copytree(ROOT / 'skills' / name, self.target / name)
        self.dbpath = self.target / 'data/skills_metadata.db'
        self.dbpath.unlink(missing_ok=True)
        self.skill('synthetic-local')
        guard = self.home / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text('import socket,pathlib,os\ndef blocked(*a,**k):\n pathlib.Path(os.environ["GUARD_ATTEMPTS"]).write_text("attempted")\n raise AssertionError("Network prohibited")\nsocket.socket.connect=blocked\nsocket.create_connection=blocked\n')
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(guard),
                        GUARD_ATTEMPTS=str(self.home / 'network-attempts'), PYTHONDONTWRITEBYTECODE='1')

    def skill(self, name):
        skill = self.target / name
        skill.mkdir()
        (skill / 'SKILL.md').write_text('---\nname: ' + name + '\ndescription: Synthetic fixture\nallowed-tools: Read\n---\nSynthetic.\n')
        for _, _, folder, filename in TABLES:
            directory = skill / folder
            directory.mkdir()
            (directory / filename).write_text('Synthetic resource.\n')

    def execute(self, args):
        result = subprocess.run([sys.executable, *map(str, args)], env=self.env, cwd=self.home,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.home / 'network-attempts').exists())
        return result.stdout

    def initialize(self):
        return self.execute([self.target / 'scripts/init_db.py'])

    def rows(self, table, skill='synthetic-local'):
        with sqlite3.connect(self.dbpath) as db:
            return db.execute('SELECT * FROM ' + table + ' WHERE skill_name=? ORDER BY id', (skill,)).fetchall()

    def history(self):
        code = "import sys;from pathlib import Path;sys.path.insert(0,str(Path.home()/'.claude/skills/lib'));from skill_db import SkillDB;d=SkillDB();d.log_execution('synthetic-local',duration_ms=12);d.add_feedback('synthetic-local',4,True,'Synthetic feedback')"
        self.execute(['-c', code])
        return {table: self.rows(table) for table in ['skill_executions', 'skill_feedback']}

    def test_unchanged_full_initialization_is_resource_stable_and_keeps_history(self):
        self.initialize()
        history = self.history()
        before = {table: self.rows(table) for table, *_ in TABLES}
        for _ in range(2):
            output = self.initialize()
            for table, prefix, *_ in TABLES:
                self.assertEqual(self.rows(table), before[table])
                label = 'References' if prefix == 'reference' else prefix.title() + 's'
                self.assertIn(label + ': 0', output)
        for table, rows in history.items():
            self.assertEqual(self.rows(table), rows)
        detail = self.execute([self.target / 'scripts/skill_dashboard.py', 'detail', 'synthetic-local'])
        for _, _, _, filename in TABLES:
            self.assertEqual(detail.count(filename), 1)
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute("SELECT template_count,script_count,reference_count FROM skill_resources WHERE name='synthetic-local'").fetchone(), (1, 1, 1))

    def test_historical_duplicate_rows_and_metadata_are_not_deleted_or_rewritten(self):
        self.initialize()
        with sqlite3.connect(self.dbpath) as db:
            for table, prefix, *_ in TABLES:
                db.execute('UPDATE ' + table + ' SET description=?', ('Preserve existing annotation',))
                columns = [row[1] for row in db.execute('PRAGMA table_info(' + table + ')') if row[1] != 'id']
                joined = ','.join(columns)
                db.execute('INSERT INTO ' + table + ' (' + joined + ') SELECT ' + joined + ' FROM ' + table)
        before = {table: self.rows(table) for table, *_ in TABLES}
        self.initialize()
        for table, *_ in TABLES:
            self.assertEqual(len(before[table]), 2)
            self.assertEqual(self.rows(table), before[table])

    def test_distinct_paths_and_skills_are_still_inserted_once(self):
        self.initialize()
        self.skill('synthetic-other')
        for _, _, folder, filename in TABLES:
            nested = self.target / 'synthetic-local' / folder / 'nested'
            nested.mkdir()
            (nested / filename).write_text('Different physical path, same basename.\n')
        self.initialize()
        self.initialize()
        for table, *_ in TABLES:
            self.assertEqual(len(self.rows(table)), 2)
            self.assertEqual(len(self.rows(table, 'synthetic-other')), 1)

    def test_shipped_database_copy_supports_same_prevention_without_migration(self):
        shutil.copy2(ROOT / 'skills/data/skills_metadata.db', self.dbpath)
        self.initialize()
        before = {table: self.rows(table) for table, *_ in TABLES}
        self.initialize()
        for table, *_ in TABLES:
            self.assertEqual(len(before[table]), 1)
            self.assertEqual(self.rows(table), before[table])
