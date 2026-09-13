#!/usr/bin/env python3
"""
Hook: Log tool decisions for observability.

Every tool use is logged for debugging and behavioral analysis.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


# Log directory
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "tool_decisions.jsonl"


def ensure_log_dir():
    """Ensure log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_decision(entry: Dict[str, Any]) -> None:
    """Append a decision to the log file."""
    ensure_log_dir()

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def hook_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hook handler for logging tool decisions.

    Called before and after every tool use.
    """
    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})

    # Create log entry
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "tool": tool_name,
        "input_summary": _summarize_input(tool_input),
        "session_id": os.environ.get("SESSION_ID", "unknown"),
    }

    # Add tool-specific details
    if tool_name == "Read":
        entry["file"] = tool_input.get("file_path", "")
    elif tool_name in ("Write", "Edit"):
        entry["file"] = tool_input.get("file_path", "")
        entry["content_length"] = len(str(tool_input.get("content", "")))
    elif tool_name == "Bash":
        entry["command"] = tool_input.get("command", "")[:100]
    elif tool_name == "Task":
        entry["subagent"] = tool_input.get("subagent_type", "")
        entry["description"] = tool_input.get("description", "")

    log_decision(entry)

    # Return empty - we're just logging, not modifying
    return {}


def _summarize_input(tool_input: Dict[str, Any], max_length: int = 200) -> str:
    """Create a brief summary of tool input."""
    # Convert to string and truncate
    summary = json.dumps(tool_input)
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."
    return summary


def get_recent_logs(limit: int = 50) -> list:
    """Read recent log entries."""
    if not LOG_FILE.exists():
        return []

    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    return entries[-limit:]


def main():
    """CLI interface."""
    if len(sys.argv) > 1 and sys.argv[1] == "--recent":
        # Show recent logs
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        for entry in get_recent_logs(limit):
            print(json.dumps(entry))
    else:
        # Hook mode
        data = json.loads(sys.stdin.read())
        result = hook_handler(data)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
