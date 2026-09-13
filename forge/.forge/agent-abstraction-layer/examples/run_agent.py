#!/usr/bin/env python3
"""
Example: Running an AAL-wrapped agent.

This demonstrates how to use the Agent Abstraction Layer with
the Claude Agent SDK to create agents with:
- Confidence estimation
- Multi-path exploration
- Graceful degradation
- Drift detection

Usage:
    # With the actual SDK installed:
    python run_agent.py "Analyze this codebase"

    # In simulation mode (no SDK):
    python run_agent.py --simulate "Analyze this codebase"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from forge_agent_abstraction_layer.sdk_extension import (
    AALAgent,
    load_manifest,
    AALAgentOptions,
)
from forge_agent_abstraction_layer.sdk_extension.confidence import ConfidenceScore


async def run_with_aal(prompt: str, manifest_path: str, simulate: bool = False):
    """Run an agent with full AAL capabilities."""

    print(f"\n{'='*60}")
    print("AAL Agent Execution")
    print(f"{'='*60}\n")

    # Load manifest
    print(f"Loading manifest: {manifest_path}")
    manifest = load_manifest(manifest_path)
    print(f"  Agent: {manifest.metadata.name} v{manifest.metadata.version}")
    print(f"  Model: {manifest.entity.model if manifest.entity else 'default'}")

    # Create AAL agent
    options = AALAgentOptions(
        enable_exploration=True,
        enable_drift_detection=True,
        enable_degradation=True,
    )
    agent = AALAgent(manifest, options)

    print(f"\nPrompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"\n{'-'*60}")
    print("Executing...\n")

    # Run the agent
    result = await agent.run(prompt)

    # Display results
    print(f"\n{'-'*60}")
    print("RESULTS")
    print(f"{'-'*60}\n")

    print(f"Response:\n{result.content[:500]}{'...' if len(result.content) > 500 else ''}\n")

    print(f"Confidence: {result.confidence.overall:.2f}")
    if result.confidence.uncertainty_sources:
        print(f"  Uncertainties: {', '.join(result.confidence.uncertainty_sources)}")

    print(f"\nDegradation Level: {result.degradation_level.value}")
    print(f"Drift Detected: {result.drift_detected}")
    print(f"Duration: {result.duration_ms:.0f}ms")

    if result.exploration_result:
        print(f"\nExploration:")
        print(f"  Paths explored: {len(result.exploration_result.paths)}")
        print(f"  Strategy: {result.exploration_result.strategy_used}")
        print(f"  Consensus confidence: {result.exploration_result.consensus_confidence.overall:.2f}")

    # Get agent stats
    stats = agent.get_stats()
    print(f"\nAgent Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    return result


async def run_streaming(prompt: str, manifest_path: str):
    """Run an agent with streaming output."""

    print(f"\n{'='*60}")
    print("AAL Agent Streaming")
    print(f"{'='*60}\n")

    manifest = load_manifest(manifest_path)
    agent = AALAgent(manifest)

    print(f"Prompt: {prompt}\n")
    print("Response (streaming):\n")

    async for chunk in agent.stream(prompt):
        # Print just the new content
        sys.stdout.write(chunk.content[-20:] if len(chunk.content) > 20 else chunk.content)
        sys.stdout.flush()

        # Show confidence indicator
        if chunk.metadata.get("complete"):
            print(f"\n\n[Confidence: {chunk.confidence.overall:.2f}]")


async def demonstrate_degradation(manifest_path: str):
    """Demonstrate graceful degradation."""

    print(f"\n{'='*60}")
    print("Degradation Demonstration")
    print(f"{'='*60}\n")

    manifest = load_manifest(manifest_path)
    agent = AALAgent(manifest)

    print("Initial state:")
    print(f"  Level: {agent.degradation_manager.current_level.value}")
    print(f"  Tools enabled: {agent.degradation_manager.current_config.tools_enabled}")

    print("\nSimulating failures and degradation...\n")

    for i in range(4):
        level = agent.degradation_manager.descend(f"Simulated failure {i+1}")
        config = agent.degradation_manager.current_config
        print(f"After failure {i+1}:")
        print(f"  Level: {level.value}")
        print(f"  Description: {config.description}")
        print(f"  Tools enabled: {config.tools_enabled}")
        if config.disabled_tools:
            print(f"  Disabled tools: {config.disabled_tools}")
        print()

    print("Resetting to full capability...")
    agent.reset_degradation()
    print(f"  Level: {agent.degradation_manager.current_level.value}")


async def demonstrate_confidence(manifest_path: str):
    """Demonstrate confidence estimation."""

    print(f"\n{'='*60}")
    print("Confidence Estimation Demonstration")
    print(f"{'='*60}\n")

    manifest = load_manifest(manifest_path)
    agent = AALAgent(manifest)

    # Sample responses with different confidence indicators
    test_cases = [
        {
            "prompt": "What is 2+2?",
            "response": "The answer is 4. This is a basic arithmetic fact.",
            "expected": "high",
        },
        {
            "prompt": "Will it rain tomorrow?",
            "response": "I'm not sure, but it might rain. Perhaps checking the weather forecast would help.",
            "expected": "low (hedging)",
        },
        {
            "prompt": "Explain quantum computing",
            "response": "Quantum computing uses quantum mechanical phenomena. I believe it involves qubits that can exist in superposition, though I may be simplifying some aspects.",
            "expected": "medium (mixed signals)",
        },
    ]

    for case in test_cases:
        print(f"Prompt: {case['prompt']}")
        print(f"Response: {case['response'][:100]}...")

        confidence = agent.confidence_estimator.estimate(
            prompt=case["prompt"],
            response=case["response"],
            tool_calls=[],
        )

        print(f"\nConfidence Analysis:")
        print(f"  Overall: {confidence.overall:.2f}")
        print(f"  Linguistic certainty: {confidence.linguistic_certainty:.2f}")
        print(f"  Expected: {case['expected']}")
        print(f"  Reasoning: {confidence.reasoning}")
        print(f"\n{'-'*40}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run an AAL-wrapped agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_agent.py "Analyze this codebase"
    python run_agent.py --stream "Write a poem"
    python run_agent.py --demo degradation
    python run_agent.py --demo confidence
        """,
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        default="Hello, how can you help me?",
        help="The prompt to send to the agent",
    )

    parser.add_argument(
        "--manifest",
        default="agent.manifest.yaml",
        help="Path to agent manifest file",
    )

    parser.add_argument(
        "--stream",
        action="store_true",
        help="Use streaming mode",
    )

    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode (no actual SDK calls)",
    )

    parser.add_argument(
        "--demo",
        choices=["degradation", "confidence"],
        help="Run a demonstration",
    )

    args = parser.parse_args()

    # Find manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        # Try in current directory's parent
        alt_path = Path(__file__).parent.parent.parent.parent / args.manifest
        if alt_path.exists():
            manifest_path = alt_path
        else:
            print(f"Error: Manifest not found: {args.manifest}")
            sys.exit(1)

    # Run appropriate mode
    if args.demo == "degradation":
        asyncio.run(demonstrate_degradation(str(manifest_path)))
    elif args.demo == "confidence":
        asyncio.run(demonstrate_confidence(str(manifest_path)))
    elif args.stream:
        asyncio.run(run_streaming(args.prompt, str(manifest_path)))
    else:
        asyncio.run(run_with_aal(args.prompt, str(manifest_path), args.simulate))


if __name__ == "__main__":
    main()
