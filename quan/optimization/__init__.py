"""
Optimization module for Collection Intelligence platform.

Contains parameter tuning engines for:
- Negotiation strategies
- Settlement offers
- Payment plans
- Channel optimization with multi-armed bandit selection
- Lifecycle ROI optimization with full account economics
- Cross-validation ensemble optimization with confidence intervals
"""

from .negotiation_tuner import (
    NegotiationSimulator,
    NegotiationStrategy,
    NegotiationApproach,
    DebtorSegment,
    GameTheoryEngine,
    NegotiationAnalytics,
    NEGOTIATION_STRATEGIES,
    SETTLEMENT_AUTHORITY,
    PAYMENT_PLAN_TIERS,
    run_negotiation_tuner,
)

from .channel_optimizer import (
    ChannelOptimizationEngine,
    MultiArmedBandit,
    ChannelEffectivenessModel,
    Channel,
    DebtType,
    BalanceTier,
    DPDBucket,
    DebtorDemographics,
    ChannelPerformance,
    SegmentKey,
    ChannelSequence,
    CHANNEL_COSTS,
    run_channel_optimization,
)

from .lifecycle_roi import (
    LifecycleROIOptimizer,
    LifecycleCostModel,
    AcquisitionCosts,
    ProcessingCosts,
    ChannelCosts,
    ComplianceCosts,
    ReEngagementCosts,
    AccountLifecycle,
    SegmentMetrics,
    PortfolioOptimization,
    DebtTypeSegment,
    SEGMENT_PROFILES,
    BALANCE_TIER_BOUNDS,
    run_lifecycle_optimization,
)

from .ensemble_optimizer import (
    EnsembleOptimizer,
    CrossValidationEngine,
    EnsembleModel,
    OverfittingDetector,
    BootstrapCI,
    OptimizerType,
    AccountData,
    FoldMetrics,
    CVResults,
    ConfidenceInterval,
    EnsembleWeight,
    OverfitAssessment,
    EnsemblePrediction,
    RobustRecommendation,
    CVAccountGenerator,
    OptimizerSimulator,
    CV_FOLDS,
    ACCOUNTS_PER_FOLD,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_CONFIDENCE_LEVEL,
    run_ensemble_optimization,
)

__all__ = [
    # Negotiation tuner
    "NegotiationSimulator",
    "NegotiationStrategy",
    "NegotiationApproach",
    "DebtorSegment",
    "GameTheoryEngine",
    "NegotiationAnalytics",
    "NEGOTIATION_STRATEGIES",
    "SETTLEMENT_AUTHORITY",
    "PAYMENT_PLAN_TIERS",
    "run_negotiation_tuner",
    # Channel optimizer
    "ChannelOptimizationEngine",
    "MultiArmedBandit",
    "ChannelEffectivenessModel",
    "Channel",
    "DebtType",
    "BalanceTier",
    "DPDBucket",
    "DebtorDemographics",
    "ChannelPerformance",
    "SegmentKey",
    "ChannelSequence",
    "CHANNEL_COSTS",
    "run_channel_optimization",
    # Lifecycle ROI optimizer
    "LifecycleROIOptimizer",
    "LifecycleCostModel",
    "AcquisitionCosts",
    "ProcessingCosts",
    "ChannelCosts",
    "ComplianceCosts",
    "ReEngagementCosts",
    "AccountLifecycle",
    "SegmentMetrics",
    "PortfolioOptimization",
    "DebtTypeSegment",
    "SEGMENT_PROFILES",
    "BALANCE_TIER_BOUNDS",
    "run_lifecycle_optimization",
    # Ensemble optimizer
    "EnsembleOptimizer",
    "CrossValidationEngine",
    "EnsembleModel",
    "OverfittingDetector",
    "BootstrapCI",
    "OptimizerType",
    "AccountData",
    "FoldMetrics",
    "CVResults",
    "ConfidenceInterval",
    "EnsembleWeight",
    "OverfitAssessment",
    "EnsemblePrediction",
    "RobustRecommendation",
    "CVAccountGenerator",
    "OptimizerSimulator",
    "CV_FOLDS",
    "ACCOUNTS_PER_FOLD",
    "BOOTSTRAP_SAMPLES",
    "BOOTSTRAP_CONFIDENCE_LEVEL",
    "run_ensemble_optimization",
]
