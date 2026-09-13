#!/usr/bin/env python3
"""
Hook: Validate path access.

Ensures file operations stay within allowed scope as defined
in the agent manifest.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


# Default allowed paths (can be overridden by manifest)
ALLOWED_PATHS = [
    "/home/user/ClaudeApp",
    "/tmp",
]

# Sensitive patterns that require extra scrutiny
SENSITIVE_PATTERNS = [
    ".env",
    "credentials",
    ".key",
    ".pem",
    ".secret",
    "password",
    "token",
]

# Absolutely denied patterns
DENIED_PATTERNS = [
    "../../../",  # Path traversal
    "/etc/passwd",
    "/etc/shadow",
    "~/.ssh",
]


def is_path_allowed(path: str, allowed_paths: List[str] = None) -> bool:
    """Check if a path is within allowed directories."""
    allowed = allowed_paths or ALLOWED_PATHS

    try:
        # Resolve to absolute path
        abs_path = Path(path).resolve()

        # Check against allowed paths
        for allowed_path in allowed:
            allowed_abs = Path(allowed_path).resolve()
            try:
                abs_path.relative_to(allowed_abs)
                return True
            except ValueError:
                continue

        return False

    except Exception:
        return False


def is_sensitive(path: str) -> bool:
    """Check if path matches sensitive patterns."""
    path_lower = path.lower()
    return any(pattern in path_lower for pattern in SENSITIVE_PATTERNS)


def is_denied(path: str) -> bool:
    """Check if path matches denied patterns."""
    path_lower = path.lower()
    return any(pattern in path_lower for pattern in DENIED_PATTERNS)


def hook_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hook handler for path validation.

    Called before Read, Write, Edit, and Bash operations.
    """
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Extract path based on tool
    path = None
    if tool_name == "Read":
        path = tool_input.get("file_path")
    elif tool_name in ("Write", "Edit"):
        path = tool_input.get("file_path")
    elif tool_name == "Bash":
        # Try to extract paths from command
        command = tool_input.get("command", "")
        # Simple heuristic - look for file-like arguments
        words = command.split()
        for word in words:
            if "/" in word and not word.startswith("-"):
                # Check this path-like argument
                if is_denied(word):
                    return {
                        "block": True,
                        "reason": f"Denied path pattern in command: {word}",
                    }
                if not is_path_allowed(word):
                    return {
                        "block": True,
                        "reason": f"Path outside allowed scope: {word}",
                    }
        # Command passed basic checks
        return {}

    if path is None:
        return {}  # No path to validate

    # Check denied patterns first
    if is_denied(path):
        return {
            "block": True,
            "reason": f"Path matches denied pattern: {path}",
        }

    # Check if path is allowed
    if not is_path_allowed(path):
        return {
            "block": True,
            "reason": f"Path outside allowed scope: {path}",
        }

    # Check for sensitive paths (warn but allow)
    if is_sensitive(path):
        return {
            "warning": f"Accessing sensitive path: {path}",
            "requires_confirmation": True,
        }

    return {}  # Allowed


def main():
    """CLI interface for testing."""
    if len(sys.argv) > 1:
        # Test mode: validate a specific path
        path = sys.argv[1]
        print(f"Path: {path}")
        print(f"  Allowed: {is_path_allowed(path)}")
        print(f"  Sensitive: {is_sensitive(path)}")
        print(f"  Denied: {is_denied(path)}")
    else:
        # Hook mode: read from stdin
        data = json.loads(sys.stdin.read())
        result = hook_handler(data)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
