"""QUAN Pipeline Simulation Module"""

from quan.simulation.engine import (
    SimulationConfig,
    SimulationEngine,
    SimulationResult,
    SimulationAgent,
    SyntheticPortfolioGenerator,
    run_full_calibration,
)

from quan.simulation.stress_test import (
    ScaleLevel,
    ScaleLevelConfig,
    ScaleStressTestSimulator,
    ScaleStressResult,
    CapacityPlanningMatrix,
    InfrastructureCosts,
    ChannelCosts,
    ChannelRateLimits,
    BreakingPoint,
    CostAnalysis,
    run_stress_test,
    run_single_level_test,
)

from quan.simulation.consumer_simulator import (
    # Archetypes
    ConsumerArchetype,
    ARCHETYPE_DISTRIBUTION,
    ArchetypeProfile,
    ARCHETYPE_PROFILES,
    # Channels
    ContactChannel,
    CHANNEL_DISTRIBUTION,
    CHANNEL_RESPONSE_MULTIPLIERS,
    # Time patterns
    TimePatterns,
    # Balance tiers
    BalanceTier,
    BalanceTierProfile,
    BALANCE_TIER_PROFILES,
    # Real-world conditions
    LifeEvent,
    LifeEventImpact,
    LIFE_EVENT_IMPACTS,
    SeasonalPattern,
    EconomicCondition,
    # Multi-debt
    CreditorType,
    CREDITOR_PRIORITY,
    DebtPrioritization,
    # Interaction dynamics
    InteractionState,
    # Core simulation
    SimulatedConsumer,
    SimulatorConfig,
    ContactAttempt,
    ConsumerJourney,
    SimulationMetrics,
    ConsumerInteractionSimulator,
    # Runners
    run_batch_simulations,
    run_consumer_simulation,
)

__all__ = [
    # Core simulation
    "SimulationConfig",
    "SimulationEngine",
    "SimulationResult",
    "SimulationAgent",
    "SyntheticPortfolioGenerator",
    "run_full_calibration",
    # Stress testing
    "ScaleLevel",
    "ScaleLevelConfig",
    "ScaleStressTestSimulator",
    "ScaleStressResult",
    "CapacityPlanningMatrix",
    "InfrastructureCosts",
    "ChannelCosts",
    "ChannelRateLimits",
    "BreakingPoint",
    "CostAnalysis",
    "run_stress_test",
    "run_single_level_test",
    # Consumer simulation
    "ConsumerArchetype",
    "ARCHETYPE_DISTRIBUTION",
    "ArchetypeProfile",
    "ARCHETYPE_PROFILES",
    "ContactChannel",
    "CHANNEL_DISTRIBUTION",
    "CHANNEL_RESPONSE_MULTIPLIERS",
    "TimePatterns",
    "BalanceTier",
    "BalanceTierProfile",
    "BALANCE_TIER_PROFILES",
    "LifeEvent",
    "LifeEventImpact",
    "LIFE_EVENT_IMPACTS",
    "SeasonalPattern",
    "EconomicCondition",
    "CreditorType",
    "CREDITOR_PRIORITY",
    "DebtPrioritization",
    "InteractionState",
    "SimulatedConsumer",
    "SimulatorConfig",
    "ContactAttempt",
    "ConsumerJourney",
    "SimulationMetrics",
    "ConsumerInteractionSimulator",
    "run_batch_simulations",
    "run_consumer_simulation",
]
