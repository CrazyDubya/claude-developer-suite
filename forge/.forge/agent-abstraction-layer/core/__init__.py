# Agent Abstraction Layer (AAL)
# A principled framework for working with stochastic, fallible,
# unintelligible, and changing AI entities.

from .primitives import (
    AgentEntity,
    AgentContext,
    AgentPermissions,
    AgentMemory,
    AgentOutput,
)
from .uncertainty import (
    ConfidenceScore,
    UncertaintyType,
    ExplorationStrategy,
    MultiPathExplorer,
)
from .fallibility import (
    ErrorClassification,
    RecoveryStrategy,
    DegradationLadder,
    HumanLoop,
)
from .observability import (
    AgentTrace,
    DecisionLog,
    BehavioralFingerprint,
    DriftDetector,
)
from .manifest import AgentManifest

__version__ = "0.1.0"
__all__ = [
    "AgentEntity",
    "AgentContext",
    "AgentPermissions",
    "AgentMemory",
    "AgentOutput",
    "ConfidenceScore",
    "UncertaintyType",
    "ExplorationStrategy",
    "MultiPathExplorer",
    "ErrorClassification",
    "RecoveryStrategy",
    "DegradationLadder",
    "HumanLoop",
    "AgentTrace",
    "DecisionLog",
    "BehavioralFingerprint",
    "DriftDetector",
    "AgentManifest",
]
