"""
Collection Intelligence System

ML-powered portfolio analysis and strategy optimization.
Uses standard machine learning techniques:
- Gradient boosting for payment probability
- Graph neural networks for debtor clustering
- Reinforcement learning for contact optimization
"""

from .engine import (
    CollectionIntelligence,
    PortfolioState,
    CollectionStrategy,
)

# Backward compatibility alias
QuantumEngine = CollectionIntelligence

__all__ = [
    "CollectionIntelligence",
    "PortfolioState",
    "CollectionStrategy",
    "QuantumEngine",
]
