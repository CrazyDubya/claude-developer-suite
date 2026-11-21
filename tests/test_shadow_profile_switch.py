"""Complete installed agent-manager shell consumer, temporary HOME/project only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('SUITE_SOURCE', Path(__file__).resolve().parents[1]))


class ShadowProfileSwitch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='suite-shadow-switch-test-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.home, self.project = root / 'home', root / 'project'
        self.home.mkdir()
        self.project.mkdir()
        install = self.home / '.claude'
        install.mkdir()
        for name in ['agent-registry', 'commands']:
            shutil.copytree(ROOT / 'agents' / name, install / name)
        self.active = install / 'agents'
        self.active.mkdir()
        for name in ['synthetic-old', 'synthetic-new']:
            (self.active / (name + '.md')).write_text(
                '---\nname: ' + name + '\ndescription: Synthetic fixture\n---\nLocal fixture.\n')
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
        self.env = dict(os.environ, HOME=str(self.home), PYTHONPATH=str(guard),
                        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                        GUARD_ATTEMPTS=str(root / 'network-attempts'), PYTHONDONTWRITEBYTECODE='1')
        self.guard_attempts = root / 'network-attempts'
        self.shell('shadow-init')
        self.shell('activate', 'synthetic-old')
        self.save_profile('synthetic-old-profile', ['synthetic-old'])
        self.shell('switch', 'synthetic-old-profile')

    def execute(self, args, expect=0):
        result = subprocess.run(list(map(str, args)), cwd=self.project, env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        self.assertFalse(self.guard_attempts.exists())
        return result

    def shell(self, *args, expect=0):
        return self.execute(['bash', self.cli, *args], expect)

    def python(self, code, expect=0):
        bootstrap = "import sys;from pathlib import Path;sys.path.insert(0,str(Path.home()/'.claude/agent-registry'));"
        return self.execute([sys.executable, '-c', bootstrap + code], expect)

    def save_profile(self, name, agents):
        self.python("from setup import AgentRegistry;r=AgentRegistry(enable_shadow_system=True);r.save_project_profile(" + repr(name) + ",'Synthetic switching fixture'," + repr(agents) + ")")

    def state(self):
        result = self.python("import json;from setup import AgentRegistry;r=AgentRegistry(enable_shadow_system=True);print('FIXTURE_STATE='+json.dumps(r.shadow_manager._load_state()))")
        return json.loads(result.stdout.split('FIXTURE_STATE=')[1].splitlines()[0])

    def active_names(self):
        return sorted(path.name for path in self.active.glob('*.md'))

    def test_valid_full_shell_switch_and_status_keep_success(self):
        self.save_profile('synthetic-target', ['synthetic-new'])
        result = self.shell('switch', 'synthetic-target')
        self.assertIn('Successfully switched', result.stdout)
        self.assertEqual(self.active_names(), ['synthetic-new.md'])
        self.assertEqual(self.state()['last_profile'], 'synthetic-target')
        self.assertIn('Last Successful Profile: synthetic-target', self.shell('status').stdout)

    def test_missing_target_agent_reports_failure_without_false_profile_assignment(self):
        self.save_profile('synthetic-target', ['synthetic-absent'])
        result = self.shell('switch', 'synthetic-target', expect=1)
        self.assertNotIn('Successfully switched', result.stdout)
        self.assertIn('synthetic-absent.md - not found in archive', result.stdout)
        self.assertIn('incomplete', result.stdout)
        self.assertEqual(self.active_names(), [])  # Existing non-atomic behavior, not rollback.
        self.assertEqual(self.state()['last_profile'], 'synthetic-old-profile')
        status = self.shell('status').stdout
        self.assertNotIn('synthetic-target', status)
        self.assertIn('Last Successful Profile: synthetic-old-profile', status)
        self.assertNotIn('Current Profile:', status)

    def test_partial_activation_is_not_overall_success(self):
        self.save_profile('synthetic-partial', ['synthetic-new', 'synthetic-absent'])
        result = self.shell('switch', 'synthetic-partial', expect=1)
        self.assertIn('synthetic-new.md', result.stdout)
        self.assertIn('synthetic-absent.md - not found in archive', result.stdout)
        self.assertNotIn('Successfully switched', result.stdout)
        self.assertEqual(self.active_names(), ['synthetic-new.md'])
        self.assertEqual(self.state()['last_profile'], 'synthetic-old-profile')
        status = self.shell('status').stdout
        self.assertNotIn('synthetic-partial', status)
        self.assertIn('Last Successful Profile: synthetic-old-profile', status)

    def test_empty_saved_profile_retains_existing_successful_deactivation_behavior(self):
        self.save_profile('synthetic-empty', [])
        self.shell('switch', 'synthetic-empty')
        self.assertEqual(self.active_names(), [])
        self.assertEqual(self.state()['last_profile'], 'synthetic-empty')

    def test_deactivation_failure_is_not_hidden_by_successful_activation(self):
        self.save_profile('synthetic-target', ['synthetic-new'])
        # External local fixture change produces a real stale-file failure; no method mocks.
        (self.active / 'synthetic-old.md').unlink()
        result = self.shell('switch', 'synthetic-target', expect=1)
        self.assertIn('synthetic-old.md - not currently active', result.stdout)
        self.assertNotIn('Successfully switched', result.stdout)
        self.assertEqual(self.active_names(), ['synthetic-new.md'])
        self.assertEqual(self.state()['last_profile'], 'synthetic-old-profile')
