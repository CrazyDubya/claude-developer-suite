"""Complete shell search input transport, real registry queries, temp fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SUITE_SOURCE', Path(__file__).resolve().parents[1]))


class ShellSearchTransport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-search-data-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.home, self.project = root / 'home', root / 'project'
        self.home.mkdir()
        self.project.mkdir()
        install = self.home / '.claude'
        install.mkdir()
        for name in ['agent-registry', 'commands']:
            shutil.copytree(ROOT / 'agents' / name, install / name)
        active = install / 'agents'
        active.mkdir()
        for name in ['synthetic-reference-a', 'synthetic-reference-b']:
            (active / (name + '.md')).write_text(
                "---\nname: " + name + "\ndescription: O'Reilly reference librarian C:\\Shelf\n"
                "tools: []\n---\nPython backend API testing pytest fixture.\n")
        self.cli = install / 'commands/agent-manager.sh'
        guard = root / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(
            'import socket, pathlib, os\n'
            'def blocked(*args, **kwargs):\n'
            '    pathlib.Path(os.environ["GUARD_ATTEMPTS"]).write_text("attempted")\n'
            '    raise AssertionError("Network prohibited")\n'
            'socket.socket.connect = blocked\n'
            'socket.create_connection = blocked\n')
        self.attempts = root / 'network-attempts'
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(guard),
                        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                        GUARD_ATTEMPTS=str(self.attempts), PYTHONDONTWRITEBYTECODE='1')
        self.run_shell('index')

    def run_shell(self, *args, expect=0):
        result = subprocess.run(['bash', str(self.cli), *args], cwd=self.project,
                                env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        self.assertFalse(self.attempts.exists())
        return result

    def test_apostrophe_and_backslash_queries_reach_actual_parameterized_search(self):
        for text in ["O'Reilly", r'C:\Shelf']:
            result = self.run_shell('search', text)
            self.assertIn('Found 2 agents', result.stdout)
            self.assertNotIn('SyntaxError', result.stderr)

    def test_ordinary_multiword_missing_and_existing_like_wildcards_unchanged(self):
        for args in [('reference',), ('reference', 'librarian'), ('%',), ('_',)]:
            result = self.run_shell('search', *args)
            self.assertIn('Found 2 agents', result.stdout)
        self.assertIn('No agents found', self.run_shell('search', 'synthetic-no-match').stdout)

    def test_existing_domain_capability_and_limit_flags_keep_query_semantics(self):
        for args in [('reference', '--domain', 'backend', '--capability', 'testing', '--limit', '1'),
                     ('reference', '-d', 'backend', '-c', 'testing', '-l', '1')]:
            result = self.run_shell('search', *args)
            self.assertIn('Found 1 agents', result.stdout)
        # Benign punctuation in filters is data, not generated Python syntax.
        self.assertIn('No agents found', self.run_shell('search', '--domain', "O'Reilly").stdout)
        self.assertIn('No agents found', self.run_shell('search', '--capability', "O'Reilly").stdout)

    def test_empty_request_keeps_existing_usage_error(self):
        result = self.run_shell('search', expect=1)
        self.assertIn('Please provide a search query', result.stdout)
