"""Full installed init/public logging/detail/interactive consumer regressions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SUITE_SOURCE', Path(__file__).resolve().parents[1]))


class OptionalExecutionDuration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-duration-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.target = self.home / '.claude/skills'
        self.target.mkdir(parents=True)
        for name in ['scripts', 'lib', 'data']:
            shutil.copytree(ROOT / 'skills' / name, self.target / name)
        fixture = self.target / 'synthetic-local'
        fixture.mkdir()
        (fixture / 'SKILL.md').write_text('---\nname: synthetic-local\ndescription: Synthetic timing fixture\nallowed-tools: Read\n---\nSynthetic.\n')
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
                        GUARD_ATTEMPTS=str(self.home / 'network-attempts'), PYTHONDONTWRITEBYTECODE='1')
        self.run_script('init_db.py')

    def execute(self, args, stdin=None):
        result = subprocess.run([sys.executable, *map(str, args)], cwd=self.home, env=self.env,
                                input=stdin, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.home / 'network-attempts').exists())
        return result

    def run_script(self, name, *args, stdin=None):
        return self.execute([self.target / 'scripts' / name, *args], stdin)

    def exercise(self, durations, expected):
        code = "import sys,json;from pathlib import Path;sys.path.insert(0,str(Path.home()/'.claude/skills/lib'));from skill_db import SkillDB;d=SkillDB();"
        for duration in durations:
            code += "d.log_execution('synthetic-local'" + ('' if duration is None else ',duration_ms=' + repr(duration)) + ');'
        code += "print(json.dumps(d.get_skill_stats('synthetic-local')))"
        stats = json.loads(self.execute(['-c', code]).stdout)
        self.assertEqual(stats['total_executions'], len(durations))
        self.assertEqual(stats['success_rate_percent'], 100)
        timed = [duration for duration in durations if duration is not None]
        self.assertEqual(stats['avg_duration_ms'], sum(timed) / len(timed) if timed else None)
        activity = self.run_script('skill_dashboard.py', 'activity')
        if None in durations:
            self.assertIn('N/A', activity.stdout)
        detail = self.run_script('skill_dashboard.py', 'detail', 'synthetic-local')
        self.assertIn('Avg Duration: ' + expected, detail.stdout)
        interactive = self.run_script('skill_dashboard.py', stdin='4\nsynthetic-local\n8\n')
        self.assertIn('Avg Duration: ' + expected, interactive.stdout)
        self.assertGreaterEqual(interactive.stdout.count('Claude Skills Dashboard - Menu'), 2)

    def test_omitted_public_duration_is_unavailable_not_zero(self):
        self.exercise([None], 'N/A')

    def test_timed_public_duration_keeps_existing_format(self):
        self.exercise([12], '12ms')

    def test_zero_measured_duration_is_zero_not_unavailable(self):
        self.exercise([0], '0ms')

    def test_mixed_untimed_and_timed_keeps_sql_avg_semantics(self):
        self.exercise([None, 12, 24], '18ms')
