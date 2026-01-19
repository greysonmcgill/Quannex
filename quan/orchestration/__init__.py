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

from .pipeline import (
    # Core orchestrator
    MasterPipelineOrchestrator,
    # Enums
    PipelineStage,
    DebtStatus,
    Priority,
    ChannelType,
    EventType,
    # Data structures
    DebtRecord,
    PipelineEvent,
    StageTransition,
    PipelineMetrics,
    SLADefinition,
    # Components
    EventBus,
    StateMachine,
    IngestionPipeline,
    ContactOrchestrator as PipelineContactOrchestrator,
    SettlementPipeline,
    PaymentPipeline,
    ResolutionPipeline,
    PipelineMonitor,
    ScalingController,
    TokenBucket,
    CircuitBreaker as PipelineCircuitBreaker,
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
    # Master Pipeline Orchestrator
    "MasterPipelineOrchestrator",
    "PipelineStage",
    "DebtStatus",
    "Priority",
    "ChannelType",
    "EventType",
    "DebtRecord",
    "PipelineEvent",
    "StageTransition",
    "PipelineMetrics",
    "SLADefinition",
    "EventBus",
    "StateMachine",
    "IngestionPipeline",
    "PipelineContactOrchestrator",
    "SettlementPipeline",
    "PaymentPipeline",
    "ResolutionPipeline",
    "PipelineMonitor",
    "ScalingController",
    "TokenBucket",
    "PipelineCircuitBreaker",
    # Legacy alias
    "QuantumOrchestrator",
]
