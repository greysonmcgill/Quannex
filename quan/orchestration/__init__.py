"""Workflow orchestration for collection campaigns"""

from .workflow import (
    CollectionStage,
    CollectionOrchestrator,
    ContactOrchestrator,
)

# Backward compatibility alias
QuantumOrchestrator = CollectionOrchestrator

__all__ = [
    "CollectionStage",
    "CollectionOrchestrator",
    "ContactOrchestrator",
    # Legacy alias
    "QuantumOrchestrator",
]
