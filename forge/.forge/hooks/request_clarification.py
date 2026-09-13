#!/usr/bin/env python3
"""
Hook: Request clarification on low confidence outputs.

When the agent's confidence is below threshold, this hook
can inject clarification requests or alternative suggestions.
"""

import json
import sys
from typing import Any, Dict, List


# Clarification templates based on uncertainty type
CLARIFICATION_TEMPLATES = {
    "hedging_language": [
        "I notice I'm uncertain about this. Could you provide more context?",
        "My response contains some uncertainty. Would you like me to explore this further?",
    ],
    "weak_grounding": [
        "I couldn't find strong support for this in the provided context. Do you have additional information?",
        "This answer isn't well-grounded in the available context. Should I search for more information?",
    ],
    "unreliable_tools": [
        "Some of the tools I used may have returned uncertain results. Would you like me to verify?",
        "The external sources I consulted may not be fully reliable. Should I cross-reference?",
    ],
    "inconsistent_with_history": [
        "This seems to differ from what I said earlier. Should I reconcile these?",
        "I notice a potential inconsistency with my previous responses. Would you like me to clarify?",
    ],
}


def get_clarification_suggestion(
    confidence: float,
    uncertainty_sources: List[str],
) -> str:
    """Generate a clarification suggestion based on uncertainty sources."""
    if not uncertainty_sources:
        return f"My confidence is {confidence:.0%}. Would you like me to elaborate?"

    # Get template for first uncertainty source
    source = uncertainty_sources[0]
    templates = CLARIFICATION_TEMPLATES.get(source, [])

    if templates:
        return templates[0]

    return f"I'm {confidence:.0%} confident in this response. Would you like more detail?"


def hook_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hook handler for low confidence situations.

    Called when output confidence is below threshold.
    """
    confidence = data.get("confidence", 0.5)
    response = data.get("response", {})

    # Get uncertainty sources if available
    uncertainty_sources = []
    if hasattr(response, 'confidence'):
        uncertainty_sources = getattr(response.confidence, 'uncertainty_sources', [])

    suggestion = get_clarification_suggestion(confidence, uncertainty_sources)

    return {
        "action": "append_clarification",
        "clarification": suggestion,
        "should_pause": confidence < 0.3,  # Very low confidence - pause for human
    }


def main():
    """CLI interface."""
    if len(sys.argv) > 1:
        # Test mode
        confidence = float(sys.argv[1])
        sources = sys.argv[2:] if len(sys.argv) > 2 else []
        suggestion = get_clarification_suggestion(confidence, sources)
        print(f"Confidence: {confidence}")
        print(f"Sources: {sources}")
        print(f"Suggestion: {suggestion}")
    else:
        # Hook mode
        data = json.loads(sys.stdin.read())
        result = hook_handler(data)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
