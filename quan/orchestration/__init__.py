"""Workflow orchestration for collection campaigns"""

from .workflow import (
    CollectionStage,
    CollectionOrchestrator,
    ContactOrchestrator,
)

from .master_orchestrator import (
    MasterCollectionOrchestrator,
    Account,
    CollectionStrategy,
    ActionResult,
    ActionType,
    AccountStatus,
    DecisionOutcome,
    PortfolioStats,
    CircuitBreaker,
    RateLimiter,
    FeedbackLoop,
    DecisionAuditLog,
    get_orchestrator,
)

# Backward compatibility alias
QuantumOrchestrator = CollectionOrchestrator

__all__ = [
    # Workflow orchestration
    "CollectionStage",
    "CollectionOrchestrator",
    "ContactOrchestrator",
    # Master orchestrator
    "MasterCollectionOrchestrator",
    "Account",
    "CollectionStrategy",
    "ActionResult",
    "ActionType",
    "AccountStatus",
    "DecisionOutcome",
    "PortfolioStats",
    "CircuitBreaker",
    "RateLimiter",
    "FeedbackLoop",
    "DecisionAuditLog",
    "get_orchestrator",
    # Legacy alias
    "QuantumOrchestrator",
]
