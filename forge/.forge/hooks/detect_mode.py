#!/usr/bin/env python3
"""
Hook: Detect operating mode from user input.

Analyzes the user's prompt to determine which mode Claude Code
should operate in: navigation, teaching, forge, publication, or building.
"""

import json
import re
import sys
from typing import Dict, Any, Optional


# Mode detection patterns
MODE_PATTERNS = {
    "navigation": [
        r"where (should|do) I start",
        r"what('s| is) next",
        r"my progress",
        r"what can I (do|learn)",
        r"show me the (curriculum|path|graph)",
        r"recommend",
    ],
    "teaching": [
        r"teach me",
        r"explain",
        r"how (does|do)",
        r"what (is|are)",
        r"why (does|do|is)",
        r"help me understand",
        r"tutorial",
        r"example of",
    ],
    "forge": [
        r"create (a|an|the)",
        r"build (a|an|the|me)",
        r"forge",
        r"scaffold",
        r"generate",
        r"instantiate",
        r"new (project|app|blueprint)",
    ],
    "publication": [
        r"publish",
        r"deploy",
        r"release",
        r"checklist",
        r"ready for production",
        r"ship",
    ],
    "building": [
        r"implement",
        r"fix (the|this|a)",
        r"add (a|the|this)",
        r"refactor",
        r"modify",
        r"change",
        r"update (the|this)",
        r"write (the|a|some)",
        r"code",
    ],
}


def detect_mode(prompt: str) -> Optional[str]:
    """Detect mode from prompt text."""
    prompt_lower = prompt.lower()

    # Score each mode
    scores: Dict[str, int] = {mode: 0 for mode in MODE_PATTERNS}

    for mode, patterns in MODE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, prompt_lower):
                scores[mode] += 1

    # Get highest scoring mode
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)

    # Default to building if no clear match
    return "building"


def hook_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hook handler for mode detection.

    Called by the AAL hook system before processing input.
    """
    prompt = data.get("prompt", "")

    detected_mode = detect_mode(prompt)

    return {
        "detected_mode": detected_mode,
        "metadata": {
            "mode_detection": {
                "mode": detected_mode,
                "confidence": 0.8 if detected_mode else 0.5,
            }
        }
    }


def main():
    """CLI interface for testing."""
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        # Read from stdin for hook integration
        prompt = sys.stdin.read().strip()

    if not prompt:
        print(json.dumps({"error": "No prompt provided"}))
        sys.exit(1)

    result = hook_handler({"prompt": prompt})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
