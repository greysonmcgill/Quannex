"""
Collection Intelligence System

Backward-compatible re-export from quan.intelligence module.
"""

from quan.intelligence.engine import (
    CollectionIntelligence,
    PortfolioState,
    CollectionStrategy,
)

# Backward compatibility aliases
QuantumEngine = CollectionIntelligence
QuantumState = PortfolioState

__all__ = [
    "CollectionIntelligence",
    "PortfolioState",
    "CollectionStrategy",
    # Legacy aliases
    "QuantumEngine",
    "QuantumState",
]
