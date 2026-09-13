#!/usr/bin/env python3
"""
Claude Bridge Self-Healing Watchdog
====================================

Monitors the Claude Bridge and automatically:
- Restarts if crashed
- Upgrades to new versions when available
- Rolls back on upgrade failure
- Maintains uptime and reliability

Run as: python3 claude-bridge-watchdog.py [--upgrade-to <version>]
"""

import os
import sys
import time
import signal
import logging
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

# ============ CONFIGURATION ============

BRIDGE_DIR = Path.home() / "claude-bridge"
CONFIG_DIR = Path.home() / ".claude-bridge"
WATCHDOG_LOG = BRIDGE_DIR / "watchdog.log"
PID_FILE = CONFIG_DIR / "bridge.pid"
DEPLOYER_SCRIPT = Path.home() / "claude-bridge-deployer.py"

BRIDGE_DIR.mkdir(exist_ok=True)

# ============ LOGGING ============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(WATCHDOG_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ WATCHDOG ============

class BridgeWatchdog:
    """Self-healing watchdog for Claude Bridge"""

    def __init__(self, upgrade_to: int = None):
        self.running = True
        self.upgrade_to = upgrade_to
        self.restart_count = 0
        self.last_health_check = None

        # Handle signals
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run_deployer_command(self, command: list) -> tuple[bool, str]:
        """Run deployer command and return result"""
        try:
            result = subprocess.run(
                [sys.executable, str(DEPLOYER_SCRIPT)] + command,
                capture_output=True,
                text=True,
                timeout=60
            )

            return result.returncode == 0, result.stdout + result.stderr

        except Exception as e:
            logger.error(f"Deployer command failed: {e}")
            return False, str(e)

    def check_bridge_health(self) -> bool:
        """Check if bridge is healthy"""
        success, output = self.run_deployer_command(['health'])
        self.last_health_check = datetime.now()
        return success

    def restart_bridge(self, version: int = None):
        """Restart bridge (optionally with specific version)"""
        logger.info(f"Restarting bridge{f' with v{version}' if version else ''}...")

        # Stop current
        self.run_deployer_command(['stop'])
        time.sleep(2)

        if version:
            # Start specific version
            success, output = self.run_deployer_command(['start', str(version)])
        else:
            # Start current version from state
            success, output = self.run_deployer_command(['start', '2'])  # Fallback to v2

        if success:
            logger.info("Bridge restarted successfully")
            self.restart_count += 1
        else:
            logger.error(f"Failed to restart bridge: {output}")

        return success

    def upgrade_bridge(self, target_version: int) -> bool:
        """Upgrade bridge to target version"""
        logger.info(f"Upgrading to v{target_version}...")

        success, output = self.run_deployer_command(['deploy', str(target_version)])

        if success:
            logger.info(f"✓ Upgraded to v{target_version}")
            return True
        else:
            logger.error(f"✗ Upgrade to v{target_version} failed")
            logger.error(output)
            return False

    def run(self):
        """Main watchdog loop"""
        logger.info("="*60)
        logger.info("Claude Bridge Watchdog Started")
        logger.info("="*60)

        # Perform upgrade if requested
        if self.upgrade_to:
            logger.info(f"Upgrade requested to v{self.upgrade_to}")

            if self.upgrade_bridge(self.upgrade_to):
                logger.info("Upgrade successful, continuing monitoring...")
            else:
                logger.error("Upgrade failed, monitoring current version...")

        check_interval = 30  # Check every 30 seconds
        consecutive_failures = 0
        max_consecutive_failures = 3

        while self.running:
            try:
                # Health check
                healthy = self.check_bridge_health()

                if healthy:
                    consecutive_failures = 0
                    logger.debug("Health check passed")
                else:
                    consecutive_failures += 1
                    logger.warning(f"Health check failed ({consecutive_failures}/{max_consecutive_failures})")

                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Multiple health check failures, restarting bridge...")
                        self.restart_bridge()
                        consecutive_failures = 0
                        time.sleep(10)  # Extra wait after restart

                # Sleep
                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}", exc_info=True)
                time.sleep(check_interval)

        logger.info("Watchdog stopped")
        logger.info(f"Total restarts performed: {self.restart_count}")

# ============ CLI ============

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Claude Bridge Watchdog')
    parser.add_argument(
        '--upgrade-to',
        type=int,
        help='Upgrade to specified version on startup'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run upgrade once and exit (no monitoring)'
    )

    args = parser.parse_args()

    watchdog = BridgeWatchdog(upgrade_to=args.upgrade_to)

    if args.once and args.upgrade_to:
        # Just do the upgrade and exit
        success = watchdog.upgrade_bridge(args.upgrade_to)
        sys.exit(0 if success else 1)
    else:
        # Run continuous monitoring
        watchdog.run()

if __name__ == "__main__":
    main()
