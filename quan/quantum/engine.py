"""
Backward Compatibility Module

This module provides backward compatibility for code that imports from quan.quantum.
All new code should import from quan.intelligence directly.

The quantum terminology has been replaced with accurate technical descriptions:
- QuantumEngine -> CollectionIntelligence
- QuantumState -> PortfolioState
- quantum_analyze -> analyze_portfolio / generate_strategy
"""

# Re-export from intelligence module
from quan.intelligence.engine import (
    CollectionIntelligence,
    PortfolioState,
    CollectionStrategy,
)

# Backward compatibility aliases
QuantumEngine = CollectionIntelligence
QuantumState = PortfolioState
QuantumSignal = CollectionStrategy  # For legacy code

__all__ = [
    "CollectionIntelligence",
    "PortfolioState",
    "CollectionStrategy",
    # Legacy aliases
    "QuantumEngine",
    "QuantumState",
    "QuantumSignal",
]
