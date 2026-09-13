"""
AAL SDK Extension - Extends Claude Agent SDK with uncertainty, fallibility, and observability.

This module wraps the Claude Agent SDK to add the capabilities that make
agents manageable as "stochastic, fallible, unintelligible, and changing entities."

Usage:
    from aal.sdk_extension import AALAgent, load_manifest

    # Load manifest and create agent
    manifest = load_manifest("agent.manifest.yaml")
    agent = AALAgent(manifest)

    # Run with full AAL capabilities
    result = await agent.run("Your task here")
"""

from .agent import AALAgent
from .manifest_loader import load_manifest, ManifestLoader
from .confidence import ConfidenceEstimator, ConfidenceScore
from .explorer import PathExplorer, ExplorationResult
from .degradation import DegradationManager
from .drift import DriftDetector, BehavioralBaseline
from .hooks import AALHookManager, hook

__version__ = "0.1.0"

__all__ = [
    "AALAgent",
    "load_manifest",
    "ManifestLoader",
    "ConfidenceEstimator",
    "ConfidenceScore",
    "PathExplorer",
    "ExplorationResult",
    "DegradationManager",
    "DriftDetector",
    "BehavioralBaseline",
    "AALHookManager",
    "hook",
]
