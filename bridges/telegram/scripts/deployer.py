#!/usr/bin/env python3
"""
Claude Bridge Blue-Green Deployment System
==========================================

Manages deployment of even (blue) and odd (green) versions with:
- Automatic health checks
- Rollback on failure
- Version management
- Zero-downtime deployment
- Self-healing capabilities

Version Scheme:
- Even builds (2, 4, 6, ...) = BLUE
- Odd builds (3, 5, 7, ...) = GREEN
"""

import os
import sys
import json
import time
import signal
import sqlite3
import logging
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict

# ============ CONFIGURATION ============

BRIDGE_DIR = Path.home() / "claude-bridge"
VERSIONS_DIR = BRIDGE_DIR / "versions"
CONFIG_DIR = Path.home() / ".claude-bridge"
DB_FILE = CONFIG_DIR / "bridge.db"
DEPLOY_LOG = BRIDGE_DIR / "deployment.log"
STATE_FILE = BRIDGE_DIR / "deployment-state.json"
PID_FILE = CONFIG_DIR / "bridge.pid"

# Create directories
BRIDGE_DIR.mkdir(exist_ok=True)
VERSIONS_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)

# ============ LOGGING ============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(DEPLOY_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ DATA MODELS ============

@dataclass
class DeploymentState:
    """Current deployment state"""
    active_version: int
    standby_version: Optional[int]
    last_deployment: str
    rollback_count: int = 0
    deployment_history: list = None

    def __post_init__(self):
        if self.deployment_history is None:
            self.deployment_history = []

@dataclass
class HealthStatus:
    """Health check result"""
    healthy: bool
    checks: Dict[str, Tuple[bool, str]]
    timestamp: str

# ============ DEPLOYMENT MANAGER ============

class BridgeDeployer:
    """Manages blue-green deployment of Claude Bridge"""

    def __init__(self):
        self.state = self.load_state()

    def load_state(self) -> DeploymentState:
        """Load deployment state"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                return DeploymentState(**data)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

        # Default state (v2 is currently running)
        return DeploymentState(
            active_version=2,
            standby_version=None,
            last_deployment=datetime.now().isoformat()
        )

    def save_state(self):
        """Save deployment state"""
        with open(STATE_FILE, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def get_version_color(self, version: int) -> str:
        """Get color for version (even=blue, odd=green)"""
        return "BLUE" if version % 2 == 0 else "GREEN"

    def get_version_path(self, version: int) -> Path:
        """Get path to version file"""
        return Path.home() / f"claude-telegram-bridge-v{version}.py"

    def version_exists(self, version: int) -> bool:
        """Check if version file exists"""
        return self.get_version_path(version).exists()

    def get_current_pid(self) -> Optional[int]:
        """Get PID of currently running bridge"""
        if not PID_FILE.exists():
            return None

        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, OSError):
            return None

    def stop_bridge(self) -> bool:
        """Stop currently running bridge"""
        pid = self.get_current_pid()

        if not pid:
            logger.info("No bridge process running")
            return True

        logger.info(f"Stopping bridge (PID: {pid})")

        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)

            # Wait up to 10 seconds
            for i in range(10):
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    logger.info("Bridge stopped gracefully")
                    return True

            # Force kill if still running
            logger.warning("Forcing bridge shutdown")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"Failed to stop bridge: {e}")
            return False

    def start_bridge(self, version: int) -> bool:
        """Start bridge with specified version using systemd-run to break process tree"""
        version_file = self.get_version_path(version)

        if not version_file.exists():
            logger.error(f"Version file not found: {version_file}")
            return False

        # Clean up stale PID file
        if PID_FILE.exists():
            logger.info("Removing stale PID file")
            PID_FILE.unlink()

        logger.info(f"Starting bridge v{version} ({self.get_version_color(version)})")

        try:
            # Create a launcher script that breaks the process tree
            launcher_script = CONFIG_DIR / f"launch-v{version}.sh"
            log_file = CONFIG_DIR / f"v{version}-startup.log"

            # Write launcher script with clean environment
            launcher_content = f"""#!/bin/bash
# Launcher for Claude Bridge v{version}
# This script runs with a clean environment to avoid CLAUDECODE inheritance

# Clear all Claude-related environment variables
unset CLAUDECODE
unset CLAUDE_CODE_ENTRYPOINT
unset CLAUDE_SESSION_ID
unset CLAUDE_API_KEY

# Start bridge
cd {Path.home()}
exec {sys.executable} {version_file} >> {log_file} 2>&1
"""
            launcher_script.write_text(launcher_content)
            launcher_script.chmod(0o755)

            logger.info(f"Created launcher script: {launcher_script}")

            # Start launcher in background with nohup (breaks process tree)
            subprocess.Popen(
                ['nohup', 'bash', str(launcher_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            logger.info(f"Bridge v{version} launcher started")

            # Wait for startup (increased for v9's heavy initialization: ChromaDB, sentence-transformers)
            time.sleep(30)

            # Check if it's running by looking for PID file
            pid = self.get_current_pid()
            if pid:
                # Verify no CLAUDECODE in environment
                try:
                    with open(f'/proc/{pid}/environ', 'rb') as f:
                        environ_data = f.read().decode('utf-8', errors='ignore')
                        if 'CLAUDECODE' in environ_data:
                            logger.warning(f"⚠️ Bridge PID {pid} still has CLAUDECODE in environment!")
                        else:
                            logger.info(f"✓ Bridge PID {pid} has clean environment (no CLAUDECODE)")
                except:
                    pass

                logger.info(f"Bridge v{version} started (PID: {pid})")
                return True
            else:
                logger.error(f"Bridge v{version} failed to start")
                # Show startup errors
                if log_file.exists():
                    errors = log_file.read_text()[-1000:]  # Last 1000 chars
                    logger.error(f"Startup errors: {errors}")
                return False

        except Exception as e:
            logger.error(f"Failed to start bridge v{version}: {e}")
            return False

    def check_health(self, timeout: int = 30) -> HealthStatus:
        """Perform health checks on running bridge"""
        logger.info("Running health checks...")

        checks = {}

        # Check 1: Process running
        pid = self.get_current_pid()
        checks['process'] = (pid is not None, f"PID: {pid}" if pid else "Not running")

        # Check 2: Database accessible
        try:
            if DB_FILE.exists():
                conn = sqlite3.connect(str(DB_FILE))
                conn.execute("SELECT 1 FROM sessions LIMIT 1")
                conn.close()
                checks['database'] = (True, "OK")
            else:
                checks['database'] = (False, "Database not found")
        except Exception as e:
            checks['database'] = (False, str(e))

        # Check 3: Log file recent activity
        try:
            log_file = CONFIG_DIR / "bridge.log"
            if log_file.exists():
                mtime = log_file.stat().st_mtime
                age = time.time() - mtime
                if age < 300:  # Active within 5 minutes (increased for stream-json)
                    checks['activity'] = (True, f"Active {int(age)}s ago")
                else:
                    checks['activity'] = (False, f"Inactive for {int(age)}s")
            else:
                checks['activity'] = (False, "No log file")
        except Exception as e:
            checks['activity'] = (False, str(e))

        # Check 4: Config exists
        config_file = CONFIG_DIR / "config.json"
        checks['config'] = (config_file.exists(), "OK" if config_file.exists() else "Missing")

        # Overall health
        healthy = all(check[0] for check in checks.values())

        return HealthStatus(
            healthy=healthy,
            checks=checks,
            timestamp=datetime.now().isoformat()
        )

    def run_migration(self, target_version: int) -> bool:
        """Run database migration if needed"""
        # Check if migration script exists
        migration_script = Path.home() / "migrate-bridge-db.py"

        if not migration_script.exists():
            logger.info("No migration script found, skipping")
            return True

        # Only run migration for v3+
        if target_version < 3:
            return True

        logger.info(f"Running database migration for v{target_version}...")

        try:
            result = subprocess.run(
                [sys.executable, str(migration_script)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("✓ Migration successful")
                return True
            else:
                logger.error(f"Migration failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Migration error: {e}")
            return False

    def deploy(self, target_version: int, force: bool = False) -> bool:
        """
        Deploy a new version with health checks and rollback

        Args:
            target_version: Version number to deploy
            force: Skip health checks and deploy anyway

        Returns:
            True if deployment successful, False otherwise
        """
        logger.info("="*60)
        logger.info(f"DEPLOYMENT: v{self.state.active_version} → v{target_version}")
        logger.info(f"COLOR: {self.get_version_color(self.state.active_version)} → {self.get_version_color(target_version)}")
        logger.info("="*60)

        # Validate target version exists
        if not self.version_exists(target_version):
            logger.error(f"Version {target_version} not found")
            return False

        # Run migration if needed
        if not self.run_migration(target_version):
            logger.error("Database migration failed")
            if not force:
                return False

        # Backup current version
        backup_version = self.state.active_version

        # Stop current bridge
        if not self.stop_bridge():
            logger.error("Failed to stop current bridge")
            if not force:
                return False

        # Start new version
        if not self.start_bridge(target_version):
            logger.error(f"Failed to start v{target_version}")
            logger.info("Rolling back...")
            self.start_bridge(backup_version)
            self.state.rollback_count += 1
            self.save_state()
            return False

        # Health check
        if not force:
            logger.info("Waiting for health check...")
            time.sleep(5)  # Give it time to initialize

            health = self.check_health()

            if not health.healthy:
                logger.error("Health check failed!")
                for check_name, (ok, msg) in health.checks.items():
                    status = "✓" if ok else "✗"
                    logger.error(f"  {status} {check_name}: {msg}")

                logger.info("Rolling back...")
                self.stop_bridge()
                self.start_bridge(backup_version)
                self.state.rollback_count += 1
                self.save_state()
                return False

        # Success!
        logger.info("✓ Deployment successful!")

        # Update state
        self.state.standby_version = self.state.active_version
        self.state.active_version = target_version
        self.state.last_deployment = datetime.now().isoformat()
        self.state.deployment_history.append({
            'version': target_version,
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        })
        self.save_state()

        # Final health check
        health = self.check_health()
        logger.info("\nFinal Health Status:")
        for check_name, (ok, msg) in health.checks.items():
            status = "✓" if ok else "✗"
            logger.info(f"  {status} {check_name}: {msg}")

        return True

    def rollback(self) -> bool:
        """Rollback to standby version"""
        if not self.state.standby_version:
            logger.error("No standby version available")
            return False

        logger.info(f"Rolling back to v{self.state.standby_version}")
        return self.deploy(self.state.standby_version, force=False)

    def status(self):
        """Show current deployment status"""
        print("\n" + "="*60)
        print("CLAUDE BRIDGE DEPLOYMENT STATUS")
        print("="*60)

        print(f"\nActive Version:  v{self.state.active_version} ({self.get_version_color(self.state.active_version)})")

        if self.state.standby_version:
            print(f"Standby Version: v{self.state.standby_version} ({self.get_version_color(self.state.standby_version)})")

        print(f"Last Deployment: {self.state.last_deployment}")
        print(f"Rollback Count:  {self.state.rollback_count}")

        # Current health
        health = self.check_health()
        print(f"\nHealth Status: {'✓ HEALTHY' if health.healthy else '✗ UNHEALTHY'}")
        for check_name, (ok, msg) in health.checks.items():
            status = "✓" if ok else "✗"
            print(f"  {status} {check_name}: {msg}")

        # Available versions
        print("\nAvailable Versions:")
        for v in range(2, 20):  # Check up to v19
            if self.version_exists(v):
                color = self.get_version_color(v)
                current = " (ACTIVE)" if v == self.state.active_version else ""
                standby = " (STANDBY)" if v == self.state.standby_version else ""
                print(f"  v{v} - {color}{current}{standby}")

        # Recent deployments
        if self.state.deployment_history:
            print("\nRecent Deployments:")
            for deploy in self.state.deployment_history[-5:]:
                print(f"  v{deploy['version']} - {deploy['timestamp']} - {deploy['status']}")

        print("\n" + "="*60 + "\n")

# ============ CLI ============

def main():
    """Main CLI entry point"""
    deployer = BridgeDeployer()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  claude-bridge-deployer.py status              - Show status")
        print("  claude-bridge-deployer.py deploy <version>    - Deploy version")
        print("  claude-bridge-deployer.py rollback            - Rollback to previous")
        print("  claude-bridge-deployer.py health              - Run health check")
        print("  claude-bridge-deployer.py stop                - Stop bridge")
        print("  claude-bridge-deployer.py start <version>     - Start specific version")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'status':
        deployer.status()

    elif command == 'deploy':
        if len(sys.argv) < 3:
            print("Error: Specify version to deploy")
            sys.exit(1)

        version = int(sys.argv[2])
        force = '--force' in sys.argv

        if deployer.deploy(version, force=force):
            print(f"\n✓ Successfully deployed v{version}")
            deployer.status()
        else:
            print(f"\n✗ Deployment failed")
            sys.exit(1)

    elif command == 'rollback':
        if deployer.rollback():
            print("\n✓ Rollback successful")
            deployer.status()
        else:
            print("\n✗ Rollback failed")
            sys.exit(1)

    elif command == 'health':
        health = deployer.check_health()
        print(f"\nHealth: {'✓ HEALTHY' if health.healthy else '✗ UNHEALTHY'}")
        for check_name, (ok, msg) in health.checks.items():
            status = "✓" if ok else "✗"
            print(f"  {status} {check_name}: {msg}")
        sys.exit(0 if health.healthy else 1)

    elif command == 'stop':
        if deployer.stop_bridge():
            print("✓ Bridge stopped")
        else:
            print("✗ Failed to stop bridge")
            sys.exit(1)

    elif command == 'start':
        if len(sys.argv) < 3:
            print("Error: Specify version to start")
            sys.exit(1)

        version = int(sys.argv[2])
        if deployer.start_bridge(version):
            print(f"✓ Bridge v{version} started")
            time.sleep(3)
            deployer.check_health()
        else:
            print(f"✗ Failed to start v{version}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
