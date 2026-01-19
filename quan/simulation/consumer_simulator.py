"""
Consumer Interaction Simulator

Realistic simulation of consumer behaviors in debt collection scenarios.
Models archetypes, response patterns, payment behaviors, and real-world conditions
to generate synthetic consumer journeys that match industry collection metrics.

Key Features:
- 6 Consumer Archetypes with realistic distributions
- Channel preference and response latency modeling
- Payment behavior with settlement and plan dynamics
- Real-world conditions (economic stress, seasonality, life events)
- Interaction dynamics (fatigue, trust, escalation)
"""

import asyncio
import random
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
import logging
import numpy as np
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONSUMER ARCHETYPES
# =============================================================================

class ConsumerArchetype(Enum):
    """
    Consumer archetypes based on debt collection behavior patterns.

    Distribution reflects real-world collection portfolio composition.
    """
    PROMPT_PAYER = "prompt_payer"      # 15% - Respond quickly, pay when contacted
    NEGOTIATOR = "negotiator"          # 25% - Want deals, will settle for less
    PLAN_KEEPER = "plan_keeper"        # 20% - Need payment plans, generally reliable
    PLAN_BREAKER = "plan_breaker"      # 15% - Make promises, break them
    GHOST = "ghost"                    # 20% - Never respond to anything
    HOSTILE = "hostile"                # 5%  - Threaten legal action, complaints


ARCHETYPE_DISTRIBUTION = {
    ConsumerArchetype.PROMPT_PAYER: 0.15,
    ConsumerArchetype.NEGOTIATOR: 0.25,
    ConsumerArchetype.PLAN_KEEPER: 0.20,
    ConsumerArchetype.PLAN_BREAKER: 0.15,
    ConsumerArchetype.GHOST: 0.20,
    ConsumerArchetype.HOSTILE: 0.05,
}


@dataclass
class ArchetypeProfile:
    """Behavioral profile for each consumer archetype"""
    archetype: ConsumerArchetype

    # Response characteristics
    base_response_rate: float           # Base probability of responding to contact
    response_latency_mean: float        # Mean response time in hours (lognormal)
    response_latency_sigma: float       # Sigma for lognormal distribution

    # Payment characteristics
    full_payment_probability: float     # Probability of paying in full
    settlement_acceptance_base: float   # Base settlement acceptance rate
    plan_adherence_rate: float          # Payment plan adherence probability

    # Interaction dynamics
    fatigue_sensitivity: float          # How quickly they tire of contact (0-1)
    trust_building_rate: float          # How quickly trust builds (0-1)
    escalation_threshold: int           # Contacts before potential escalation

    # Channel preferences (must sum to 1.0)
    channel_preferences: Dict[str, float] = field(default_factory=dict)

    # Behavioral flags
    disputes_debts: bool = False
    files_complaints: bool = False
    threatens_legal: bool = False
    requires_validation: bool = False


# Archetype profiles with industry-calibrated parameters
ARCHETYPE_PROFILES: Dict[ConsumerArchetype, ArchetypeProfile] = {
    ConsumerArchetype.PROMPT_PAYER: ArchetypeProfile(
        archetype=ConsumerArchetype.PROMPT_PAYER,
        base_response_rate=0.75,
        response_latency_mean=2.5,      # ~2.5 hours average
        response_latency_sigma=0.8,
        full_payment_probability=0.85,
        settlement_acceptance_base=0.30,  # Often prefer to pay full
        plan_adherence_rate=0.95,
        fatigue_sensitivity=0.15,
        trust_building_rate=0.25,
        escalation_threshold=10,
        channel_preferences={"sms": 0.50, "email": 0.35, "voice": 0.10, "mail": 0.05},
    ),
    ConsumerArchetype.NEGOTIATOR: ArchetypeProfile(
        archetype=ConsumerArchetype.NEGOTIATOR,
        base_response_rate=0.55,
        response_latency_mean=8.0,      # ~8 hours, strategic delay
        response_latency_sigma=1.2,
        full_payment_probability=0.15,
        settlement_acceptance_base=0.70,
        plan_adherence_rate=0.75,
        fatigue_sensitivity=0.25,
        trust_building_rate=0.20,
        escalation_threshold=8,
        channel_preferences={"sms": 0.40, "email": 0.40, "voice": 0.15, "mail": 0.05},
    ),
    ConsumerArchetype.PLAN_KEEPER: ArchetypeProfile(
        archetype=ConsumerArchetype.PLAN_KEEPER,
        base_response_rate=0.50,
        response_latency_mean=12.0,     # ~12 hours, need time to review
        response_latency_sigma=1.0,
        full_payment_probability=0.10,
        settlement_acceptance_base=0.40,
        plan_adherence_rate=0.82,
        fatigue_sensitivity=0.20,
        trust_building_rate=0.30,
        escalation_threshold=12,
        channel_preferences={"sms": 0.45, "email": 0.30, "voice": 0.15, "mail": 0.10},
    ),
    ConsumerArchetype.PLAN_BREAKER: ArchetypeProfile(
        archetype=ConsumerArchetype.PLAN_BREAKER,
        base_response_rate=0.40,
        response_latency_mean=24.0,     # ~24 hours, often delayed
        response_latency_sigma=1.5,
        full_payment_probability=0.05,
        settlement_acceptance_base=0.55,
        plan_adherence_rate=0.35,       # Key differentiator - low adherence
        fatigue_sensitivity=0.40,
        trust_building_rate=0.10,
        escalation_threshold=6,
        channel_preferences={"sms": 0.50, "email": 0.25, "voice": 0.15, "mail": 0.10},
    ),
    ConsumerArchetype.GHOST: ArchetypeProfile(
        archetype=ConsumerArchetype.GHOST,
        base_response_rate=0.05,        # Rarely respond
        response_latency_mean=72.0,     # If they do, very delayed
        response_latency_sigma=2.0,
        full_payment_probability=0.60,  # If they pay, often in full
        settlement_acceptance_base=0.50,
        plan_adherence_rate=0.40,
        fatigue_sensitivity=0.60,
        trust_building_rate=0.05,
        escalation_threshold=15,
        channel_preferences={"sms": 0.40, "email": 0.30, "voice": 0.10, "mail": 0.20},
    ),
    ConsumerArchetype.HOSTILE: ArchetypeProfile(
        archetype=ConsumerArchetype.HOSTILE,
        base_response_rate=0.65,        # Respond to complain
        response_latency_mean=4.0,      # Quick to anger
        response_latency_sigma=1.0,
        full_payment_probability=0.20,
        settlement_acceptance_base=0.25,
        plan_adherence_rate=0.50,
        fatigue_sensitivity=0.70,
        trust_building_rate=0.05,
        escalation_threshold=3,
        channel_preferences={"sms": 0.30, "email": 0.25, "voice": 0.20, "mail": 0.25},
        disputes_debts=True,
        files_complaints=True,
        threatens_legal=True,
        requires_validation=True,
    ),
}


# =============================================================================
# CHANNEL DEFINITIONS
# =============================================================================

class ContactChannel(Enum):
    """Communication channels for debt collection"""
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    MAIL = "mail"


# Overall channel preference distribution (market-wide)
CHANNEL_DISTRIBUTION = {
    ContactChannel.SMS: 0.45,
    ContactChannel.EMAIL: 0.30,
    ContactChannel.VOICE: 0.15,
    ContactChannel.MAIL: 0.10,
}

# Channel-specific response multipliers
CHANNEL_RESPONSE_MULTIPLIERS = {
    ContactChannel.SMS: 1.15,     # SMS has highest engagement
    ContactChannel.EMAIL: 0.85,   # Email often ignored
    ContactChannel.VOICE: 1.20,   # Voice is effective but costly
    ContactChannel.MAIL: 0.60,    # Mail has lowest response
}


# =============================================================================
# TIME-BASED PATTERNS
# =============================================================================

@dataclass
class TimePatterns:
    """Time-based response and payment patterns"""

    # Hour of day response multipliers (0-23)
    hourly_response: Dict[int, float] = field(default_factory=lambda: {
        0: 0.15, 1: 0.10, 2: 0.08, 3: 0.05, 4: 0.05, 5: 0.10,
        6: 0.40, 7: 0.65, 8: 0.85, 9: 1.00, 10: 1.10, 11: 1.15,
        12: 1.05, 13: 1.00, 14: 0.95, 15: 0.90, 16: 0.95, 17: 1.10,
        18: 1.20, 19: 1.15, 20: 1.05, 21: 0.85, 22: 0.55, 23: 0.30,
    })

    # Day of week multipliers (0=Monday, 6=Sunday)
    daily_response: Dict[int, float] = field(default_factory=lambda: {
        0: 0.95,   # Monday - people catching up
        1: 1.10,   # Tuesday - peak engagement
        2: 1.05,   # Wednesday
        3: 1.00,   # Thursday
        4: 0.90,   # Friday - mentally checked out
        5: 0.70,   # Saturday - weekend
        6: 0.65,   # Sunday - lowest
    })

    # Payday proximity effect (days from payday, 0=payday)
    payday_multipliers: Dict[int, float] = field(default_factory=lambda: {
        -7: 0.60, -6: 0.65, -5: 0.70, -4: 0.75, -3: 0.80,
        -2: 0.90, -1: 1.00, 0: 1.50, 1: 1.40, 2: 1.25,
        3: 1.10, 4: 1.00, 5: 0.95, 6: 0.90, 7: 0.85,
    })


# =============================================================================
# BALANCE TIER DEFINITIONS
# =============================================================================

class BalanceTier(Enum):
    """Balance tiers affect payment behavior"""
    MICRO = "micro"           # $0-100
    SMALL = "small"           # $100-300
    MEDIUM = "medium"         # $300-700
    LARGE = "large"           # $700-1500
    SIGNIFICANT = "significant"  # $1500+


@dataclass
class BalanceTierProfile:
    """Payment behavior by balance tier"""
    tier: BalanceTier
    min_balance: Decimal
    max_balance: Decimal
    full_payment_multiplier: float      # Multiplier on full payment probability
    settlement_floor: float             # Minimum settlement percentage accepted
    avg_plan_months: int                # Typical payment plan length
    plan_completion_rate: float         # Plan completion probability


BALANCE_TIER_PROFILES: Dict[BalanceTier, BalanceTierProfile] = {
    BalanceTier.MICRO: BalanceTierProfile(
        tier=BalanceTier.MICRO,
        min_balance=Decimal("0"),
        max_balance=Decimal("100"),
        full_payment_multiplier=1.50,    # Much more likely to pay in full
        settlement_floor=0.70,           # High floor for small amounts
        avg_plan_months=2,
        plan_completion_rate=0.90,
    ),
    BalanceTier.SMALL: BalanceTierProfile(
        tier=BalanceTier.SMALL,
        min_balance=Decimal("100"),
        max_balance=Decimal("300"),
        full_payment_multiplier=1.20,
        settlement_floor=0.55,
        avg_plan_months=3,
        plan_completion_rate=0.80,
    ),
    BalanceTier.MEDIUM: BalanceTierProfile(
        tier=BalanceTier.MEDIUM,
        min_balance=Decimal("300"),
        max_balance=Decimal("700"),
        full_payment_multiplier=0.85,
        settlement_floor=0.45,
        avg_plan_months=4,
        plan_completion_rate=0.70,
    ),
    BalanceTier.LARGE: BalanceTierProfile(
        tier=BalanceTier.LARGE,
        min_balance=Decimal("700"),
        max_balance=Decimal("1500"),
        full_payment_multiplier=0.60,
        settlement_floor=0.40,
        avg_plan_months=6,
        plan_completion_rate=0.60,
    ),
    BalanceTier.SIGNIFICANT: BalanceTierProfile(
        tier=BalanceTier.SIGNIFICANT,
        min_balance=Decimal("1500"),
        max_balance=Decimal("999999"),
        full_payment_multiplier=0.35,
        settlement_floor=0.35,
        avg_plan_months=12,
        plan_completion_rate=0.50,
    ),
}


def get_balance_tier(balance: Decimal) -> BalanceTier:
    """Determine balance tier from amount"""
    for tier, profile in BALANCE_TIER_PROFILES.items():
        if profile.min_balance <= balance < profile.max_balance:
            return tier
    return BalanceTier.SIGNIFICANT


# =============================================================================
# REAL-WORLD CONDITIONS
# =============================================================================

class LifeEvent(Enum):
    """Life events that impact payment ability"""
    NONE = "none"
    JOB_LOSS = "job_loss"
    MEDICAL_EMERGENCY = "medical_emergency"
    DIVORCE = "divorce"
    DEATH_IN_FAMILY = "death_in_family"
    NEW_BABY = "new_baby"
    MAJOR_REPAIR = "major_repair"      # Car/home repair
    SEASONAL_LAYOFF = "seasonal_layoff"


@dataclass
class LifeEventImpact:
    """Impact of life events on payment behavior"""
    event: LifeEvent
    payment_ability_multiplier: float   # 0-1, how much it reduces ability
    response_rate_multiplier: float     # How it affects response rate
    duration_days: int                  # How long the impact lasts
    probability: float                  # Base probability of occurrence


LIFE_EVENT_IMPACTS: Dict[LifeEvent, LifeEventImpact] = {
    LifeEvent.NONE: LifeEventImpact(
        event=LifeEvent.NONE,
        payment_ability_multiplier=1.0,
        response_rate_multiplier=1.0,
        duration_days=0,
        probability=0.85,
    ),
    LifeEvent.JOB_LOSS: LifeEventImpact(
        event=LifeEvent.JOB_LOSS,
        payment_ability_multiplier=0.25,
        response_rate_multiplier=0.70,
        duration_days=90,
        probability=0.05,
    ),
    LifeEvent.MEDICAL_EMERGENCY: LifeEventImpact(
        event=LifeEvent.MEDICAL_EMERGENCY,
        payment_ability_multiplier=0.40,
        response_rate_multiplier=0.60,
        duration_days=60,
        probability=0.04,
    ),
    LifeEvent.DIVORCE: LifeEventImpact(
        event=LifeEvent.DIVORCE,
        payment_ability_multiplier=0.50,
        response_rate_multiplier=0.65,
        duration_days=120,
        probability=0.02,
    ),
    LifeEvent.DEATH_IN_FAMILY: LifeEventImpact(
        event=LifeEvent.DEATH_IN_FAMILY,
        payment_ability_multiplier=0.55,
        response_rate_multiplier=0.40,
        duration_days=45,
        probability=0.01,
    ),
    LifeEvent.NEW_BABY: LifeEventImpact(
        event=LifeEvent.NEW_BABY,
        payment_ability_multiplier=0.65,
        response_rate_multiplier=0.80,
        duration_days=90,
        probability=0.02,
    ),
    LifeEvent.MAJOR_REPAIR: LifeEventImpact(
        event=LifeEvent.MAJOR_REPAIR,
        payment_ability_multiplier=0.70,
        response_rate_multiplier=0.90,
        duration_days=30,
        probability=0.04,
    ),
    LifeEvent.SEASONAL_LAYOFF: LifeEventImpact(
        event=LifeEvent.SEASONAL_LAYOFF,
        payment_ability_multiplier=0.45,
        response_rate_multiplier=0.75,
        duration_days=60,
        probability=0.03,
    ),
}


@dataclass
class SeasonalPattern:
    """Seasonal payment patterns"""

    # Month multipliers (1-12)
    monthly_payment_multipliers: Dict[int, float] = field(default_factory=lambda: {
        1: 0.85,   # January - post-holiday debt
        2: 1.25,   # February - tax refunds start
        3: 1.35,   # March - peak tax refund
        4: 1.20,   # April - tax refunds continue
        5: 1.00,   # May - normalizing
        6: 0.95,   # June - summer spending
        7: 0.90,   # July - vacation season
        8: 0.85,   # August - back to school
        9: 0.95,   # September - normalizing
        10: 1.00,  # October - stable
        11: 0.90,  # November - pre-holiday
        12: 0.80,  # December - holiday spending
    })


@dataclass
class EconomicCondition:
    """Economic stress periods"""
    name: str
    unemployment_rate: float         # Local unemployment rate
    payment_multiplier: float        # Effect on payment ability
    is_recession: bool = False


# =============================================================================
# MULTI-DEBT PRIORITIZATION
# =============================================================================

class CreditorType(Enum):
    """Types of creditors for prioritization"""
    MORTGAGE = "mortgage"
    AUTO_LOAN = "auto_loan"
    UTILITY = "utility"
    MEDICAL = "medical"
    CREDIT_CARD = "credit_card"
    RETAIL = "retail"
    BNPL = "bnpl"
    PERSONAL_LOAN = "personal_loan"
    PAYDAY = "payday"
    COLLECTION_AGENCY = "collection_agency"


# Priority ranking (1 = highest priority)
CREDITOR_PRIORITY: Dict[CreditorType, int] = {
    CreditorType.MORTGAGE: 1,           # Housing is top priority
    CreditorType.AUTO_LOAN: 2,          # Need car for work
    CreditorType.UTILITY: 3,            # Keep lights on
    CreditorType.MEDICAL: 4,            # Health-related
    CreditorType.CREDIT_CARD: 5,        # Active credit
    CreditorType.RETAIL: 6,             # Store cards
    CreditorType.BNPL: 7,               # Recent, digital
    CreditorType.PERSONAL_LOAN: 8,      # Lower priority
    CreditorType.PAYDAY: 9,             # Often ignored
    CreditorType.COLLECTION_AGENCY: 10, # Lowest priority
}


@dataclass
class DebtPrioritization:
    """Consumer's debt payment prioritization"""
    num_active_debts: int
    creditor_types: List[CreditorType]
    our_position: int                   # Our position in their priority

    def get_priority_multiplier(self) -> float:
        """
        Calculate payment probability multiplier based on our priority position.
        Higher position = lower multiplier (less likely to get paid)
        """
        if self.num_active_debts <= 1:
            return 1.0

        # Calculate based on position
        base = 1.0 - (self.our_position - 1) * 0.08

        # More debts = more competition
        debt_penalty = max(0.70, 1.0 - (self.num_active_debts - 1) * 0.05)

        return max(0.40, base * debt_penalty)


# =============================================================================
# INTERACTION DYNAMICS
# =============================================================================

@dataclass
class InteractionState:
    """Tracks interaction dynamics with a consumer"""

    # Contact fatigue
    total_contacts: int = 0
    contacts_this_week: int = 0
    contacts_this_month: int = 0
    fatigue_level: float = 0.0         # 0-1, increases with contacts

    # Trust level
    trust_score: float = 0.5           # 0-1, starts neutral
    positive_interactions: int = 0
    negative_interactions: int = 0

    # Escalation status
    has_disputed: bool = False
    has_complained: bool = False
    has_threatened_legal: bool = False
    requested_cease_comm: bool = False

    # De-escalation tracking
    de_escalation_attempts: int = 0
    successful_de_escalations: int = 0

    # Response patterns
    last_response_channel: Optional[ContactChannel] = None
    preferred_channel_identified: bool = False
    response_times: List[float] = field(default_factory=list)

    def update_fatigue(self, archetype_sensitivity: float):
        """Update fatigue level based on contact"""
        self.total_contacts += 1
        self.contacts_this_week += 1
        self.contacts_this_month += 1

        # Calculate fatigue increase
        weekly_factor = min(1.0, self.contacts_this_week / 7)
        monthly_factor = min(1.0, self.contacts_this_month / 21)

        fatigue_increase = archetype_sensitivity * (
            0.05 + (weekly_factor * 0.10) + (monthly_factor * 0.05)
        )

        self.fatigue_level = min(1.0, self.fatigue_level + fatigue_increase)

    def update_trust(self, positive: bool, archetype_rate: float):
        """Update trust based on interaction outcome"""
        if positive:
            self.positive_interactions += 1
            trust_change = archetype_rate * 0.10
            self.trust_score = min(1.0, self.trust_score + trust_change)
        else:
            self.negative_interactions += 1
            trust_change = archetype_rate * 0.15
            self.trust_score = max(0.0, self.trust_score - trust_change)

    def reset_weekly_counters(self):
        """Reset weekly contact counters"""
        self.contacts_this_week = 0

    def reset_monthly_counters(self):
        """Reset monthly contact counters"""
        self.contacts_this_month = 0
        # Fatigue decays over time
        self.fatigue_level = max(0.0, self.fatigue_level - 0.20)

    def get_response_multiplier(self) -> float:
        """Calculate response multiplier from interaction state"""
        # Fatigue reduces response
        fatigue_effect = 1.0 - (self.fatigue_level * 0.50)

        # Trust increases response
        trust_effect = 0.80 + (self.trust_score * 0.40)

        # Negative events severely impact
        if self.requested_cease_comm:
            return 0.0
        if self.has_complained:
            return fatigue_effect * trust_effect * 0.50
        if self.has_disputed:
            return fatigue_effect * trust_effect * 0.70

        return fatigue_effect * trust_effect


# =============================================================================
# SIMULATED CONSUMER
# =============================================================================

@dataclass
class SimulatedConsumer:
    """A fully simulated consumer with behavioral modeling"""

    consumer_id: str
    archetype: ConsumerArchetype
    balance: Decimal
    original_balance: Decimal

    # Profile reference
    profile: ArchetypeProfile = field(default=None)
    balance_tier: BalanceTier = field(default=None)
    tier_profile: BalanceTierProfile = field(default=None)

    # Time and economic context
    payday_day_of_month: int = 15      # 1st or 15th typical
    time_patterns: TimePatterns = field(default_factory=TimePatterns)
    seasonal_pattern: SeasonalPattern = field(default_factory=SeasonalPattern)

    # Life events
    current_life_event: LifeEvent = LifeEvent.NONE
    life_event_start_day: int = -1

    # Multi-debt context
    debt_prioritization: Optional[DebtPrioritization] = None

    # Interaction state
    interaction_state: InteractionState = field(default_factory=InteractionState)

    # Payment tracking
    payments_made: int = 0
    total_paid: Decimal = Decimal("0")
    on_payment_plan: bool = False
    plan_payments_remaining: int = 0
    plan_payment_amount: Decimal = Decimal("0")
    consecutive_plan_payments: int = 0
    failed_payments: int = 0

    # Status
    status: str = "active"
    first_contact_day: int = -1
    first_payment_day: int = -1
    last_contact_day: int = -1
    last_payment_day: int = -1

    # Settlement tracking
    settlement_offers_received: int = 0
    best_settlement_offered: float = 1.0  # As percentage of balance

    def __post_init__(self):
        """Initialize derived fields"""
        if self.profile is None:
            self.profile = ARCHETYPE_PROFILES[self.archetype]
        if self.balance_tier is None:
            self.balance_tier = get_balance_tier(self.balance)
        if self.tier_profile is None:
            self.tier_profile = BALANCE_TIER_PROFILES[self.balance_tier]


# =============================================================================
# CONSUMER SIMULATOR ENGINE
# =============================================================================

@dataclass
class SimulatorConfig:
    """Configuration for consumer simulator"""

    # Scale
    num_consumers: int = 10000
    simulation_days: int = 90

    # Contact limits (FDCPA compliance)
    max_weekly_contacts: int = 7
    max_monthly_contacts: int = 21
    min_contact_interval_hours: int = 24

    # Settlement parameters
    min_settlement_pct: float = 0.35
    max_settlement_pct: float = 0.80

    # Payment plan parameters
    min_plan_months: int = 2
    max_plan_months: int = 12

    # Economic conditions
    base_unemployment_rate: float = 0.04
    recession_mode: bool = False

    # Life event probability multiplier
    life_event_frequency: float = 1.0

    # Random seed for reproducibility
    random_seed: Optional[int] = None


@dataclass
class ContactAttempt:
    """Record of a contact attempt"""
    day: int
    hour: int
    channel: ContactChannel
    responded: bool
    response_time_hours: float
    outcome: str                       # "no_response", "positive", "negative", "payment", etc.
    amount_collected: Decimal = Decimal("0")
    notes: str = ""


@dataclass
class ConsumerJourney:
    """Complete journey record for a consumer"""
    consumer: SimulatedConsumer
    contacts: List[ContactAttempt] = field(default_factory=list)

    # Outcome tracking
    total_collected: Decimal = Decimal("0")
    final_status: str = "active"

    # Journey metrics
    days_to_first_payment: int = -1
    total_contacts_to_resolution: int = 0
    channels_used: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Behavioral insights
    identified_preferred_channel: Optional[ContactChannel] = None
    experienced_life_event: bool = False
    escalation_occurred: bool = False
    de_escalation_successful: bool = False


@dataclass
class SimulationMetrics:
    """Aggregated simulation metrics"""

    # Overall
    total_consumers: int = 0
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    # By archetype
    archetype_metrics: Dict[str, Dict] = field(default_factory=dict)

    # By channel
    channel_metrics: Dict[str, Dict] = field(default_factory=dict)

    # By balance tier
    tier_metrics: Dict[str, Dict] = field(default_factory=dict)

    # Response patterns
    avg_response_rate: float = 0.0
    avg_response_time_hours: float = 0.0

    # Payment patterns
    full_payment_rate: float = 0.0
    settlement_rate: float = 0.0
    plan_completion_rate: float = 0.0
    avg_settlement_pct: float = 0.0

    # Interaction metrics
    avg_contacts_per_consumer: float = 0.0
    contacts_per_dollar: float = 0.0
    avg_fatigue_at_resolution: float = 0.0

    # Negative outcomes
    dispute_rate: float = 0.0
    complaint_rate: float = 0.0
    cease_comm_rate: float = 0.0

    # Time metrics
    avg_days_to_first_payment: float = 0.0
    median_days_to_resolution: float = 0.0


class ConsumerInteractionSimulator:
    """
    Main simulation engine for consumer interactions.

    Generates synthetic consumer journeys with realistic variance
    matching real-world collection metrics.
    """

    def __init__(self, config: SimulatorConfig = None):
        self.config = config or SimulatorConfig()

        if self.config.random_seed:
            random.seed(self.config.random_seed)
            np.random.seed(self.config.random_seed)

        self.consumers: List[SimulatedConsumer] = []
        self.journeys: List[ConsumerJourney] = []
        self.current_day: int = 0
        self.current_month: int = 1

        # Economic context
        self.economic_condition = EconomicCondition(
            name="normal",
            unemployment_rate=self.config.base_unemployment_rate,
            payment_multiplier=1.0,
            is_recession=self.config.recession_mode,
        )

        if self.config.recession_mode:
            self.economic_condition.unemployment_rate = 0.08
            self.economic_condition.payment_multiplier = 0.75

    def generate_consumers(self, num_consumers: int = None) -> List[SimulatedConsumer]:
        """Generate consumer population with realistic distributions"""

        n = num_consumers or self.config.num_consumers
        consumers = []

        logger.info(f"Generating {n:,} consumers...")

        for i in range(n):
            # Sample archetype
            archetype = self._sample_archetype()
            profile = ARCHETYPE_PROFILES[archetype]

            # Generate balance
            balance = self._generate_balance(archetype)
            tier = get_balance_tier(balance)
            tier_profile = BALANCE_TIER_PROFILES[tier]

            # Generate payday (1st or 15th, with some variation)
            payday = random.choice([1, 15])
            payday += random.randint(-2, 2)
            payday = max(1, min(28, payday))

            # Generate multi-debt context
            debt_prioritization = self._generate_debt_context()

            # Initial life event (most start with none)
            life_event = self._sample_life_event()

            consumer = SimulatedConsumer(
                consumer_id=f"CON-{i:07d}",
                archetype=archetype,
                balance=balance,
                original_balance=balance,
                profile=profile,
                balance_tier=tier,
                tier_profile=tier_profile,
                payday_day_of_month=payday,
                current_life_event=life_event,
                life_event_start_day=0 if life_event != LifeEvent.NONE else -1,
                debt_prioritization=debt_prioritization,
            )

            consumers.append(consumer)

        self.consumers = consumers

        # Log distribution
        archetype_counts = defaultdict(int)
        for c in consumers:
            archetype_counts[c.archetype.value] += 1

        logger.info("Archetype distribution:")
        for arch, count in sorted(archetype_counts.items()):
            logger.info(f"  {arch}: {count} ({count/n*100:.1f}%)")

        return consumers

    def _sample_archetype(self) -> ConsumerArchetype:
        """Sample archetype from distribution"""
        r = random.random()
        cumulative = 0.0
        for archetype, prob in ARCHETYPE_DISTRIBUTION.items():
            cumulative += prob
            if r <= cumulative:
                return archetype
        return ConsumerArchetype.GHOST

    def _generate_balance(self, archetype: ConsumerArchetype) -> Decimal:
        """Generate balance with archetype-influenced distribution"""

        # Base distribution parameters
        if archetype == ConsumerArchetype.PROMPT_PAYER:
            # Tend toward smaller balances (easier to pay)
            mu, sigma = 4.5, 0.8
        elif archetype == ConsumerArchetype.NEGOTIATOR:
            # Medium to larger balances
            mu, sigma = 5.2, 0.9
        elif archetype == ConsumerArchetype.PLAN_KEEPER:
            # Medium balances
            mu, sigma = 5.0, 0.85
        elif archetype == ConsumerArchetype.PLAN_BREAKER:
            # Tend toward larger (harder to pay)
            mu, sigma = 5.5, 0.95
        elif archetype == ConsumerArchetype.GHOST:
            # Mixed distribution
            mu, sigma = 5.0, 1.0
        else:  # HOSTILE
            # Often dispute larger amounts
            mu, sigma = 5.3, 0.9

        # Generate lognormal balance
        raw_balance = np.random.lognormal(mu, sigma)

        # Cap at reasonable range
        balance = max(25, min(10000, raw_balance))

        return Decimal(str(round(balance, 2)))

    def _generate_debt_context(self) -> DebtPrioritization:
        """Generate multi-debt prioritization context"""

        # Number of active debts (most have 2-5)
        num_debts = random.choices(
            [1, 2, 3, 4, 5, 6, 7],
            weights=[0.15, 0.25, 0.25, 0.15, 0.10, 0.05, 0.05]
        )[0]

        # Sample creditor types
        all_types = list(CreditorType)
        creditor_types = random.sample(all_types, min(num_debts, len(all_types)))

        # We're a collection agency - typically low priority
        our_type = CreditorType.COLLECTION_AGENCY
        if our_type not in creditor_types:
            creditor_types.append(our_type)

        # Sort by priority
        creditor_types.sort(key=lambda x: CREDITOR_PRIORITY[x])

        our_position = creditor_types.index(our_type) + 1

        return DebtPrioritization(
            num_active_debts=len(creditor_types),
            creditor_types=creditor_types,
            our_position=our_position,
        )

    def _sample_life_event(self) -> LifeEvent:
        """Sample initial life event"""
        r = random.random() / self.config.life_event_frequency
        cumulative = 0.0
        for event, impact in LIFE_EVENT_IMPACTS.items():
            cumulative += impact.probability
            if r <= cumulative:
                return event
        return LifeEvent.NONE

    def simulate_contact(
        self,
        consumer: SimulatedConsumer,
        day: int,
        hour: int,
        channel: ContactChannel,
    ) -> ContactAttempt:
        """
        Simulate a single contact attempt with full behavioral modeling.
        """

        profile = consumer.profile
        tier_profile = consumer.tier_profile
        interaction = consumer.interaction_state

        # Calculate base response probability
        base_prob = profile.base_response_rate

        # Channel effect
        channel_mult = CHANNEL_RESPONSE_MULTIPLIERS[channel]

        # Check channel preference
        pref_mult = profile.channel_preferences.get(channel.value, 0.25)
        channel_mult *= (0.7 + pref_mult * 0.6)

        # Time-of-day effect
        hour_mult = consumer.time_patterns.hourly_response.get(hour, 0.8)

        # Day-of-week effect
        day_of_week = day % 7
        dow_mult = consumer.time_patterns.daily_response.get(day_of_week, 0.9)

        # Payday proximity effect
        day_of_month = (day % 30) + 1
        days_from_payday = day_of_month - consumer.payday_day_of_month
        if days_from_payday > 15:
            days_from_payday -= 30
        elif days_from_payday < -15:
            days_from_payday += 30
        payday_mult = consumer.time_patterns.payday_multipliers.get(
            days_from_payday, 0.85
        )

        # Seasonal effect
        month = (day // 30) % 12 + 1
        seasonal_mult = consumer.seasonal_pattern.monthly_payment_multipliers.get(
            month, 1.0
        )

        # Life event effect
        life_event_mult = 1.0
        if consumer.current_life_event != LifeEvent.NONE:
            impact = LIFE_EVENT_IMPACTS[consumer.current_life_event]
            days_since_event = day - consumer.life_event_start_day
            if days_since_event <= impact.duration_days:
                life_event_mult = impact.response_rate_multiplier

        # Multi-debt priority effect
        priority_mult = 1.0
        if consumer.debt_prioritization:
            priority_mult = consumer.debt_prioritization.get_priority_multiplier()

        # Interaction state effect
        interaction_mult = interaction.get_response_multiplier()

        # Economic condition effect
        economic_mult = self.economic_condition.payment_multiplier

        # Calculate final response probability
        response_prob = (
            base_prob *
            channel_mult *
            hour_mult *
            dow_mult *
            payday_mult *
            seasonal_mult *
            life_event_mult *
            priority_mult *
            interaction_mult *
            economic_mult
        )

        # Cap at realistic bounds
        response_prob = max(0.01, min(0.95, response_prob))

        # Determine if responded
        responded = random.random() < response_prob

        # Update interaction state
        interaction.update_fatigue(profile.fatigue_sensitivity)

        # Calculate response time if responded
        response_time = 0.0
        if responded:
            # Lognormal response time
            response_time = np.random.lognormal(
                np.log(profile.response_latency_mean),
                profile.response_latency_sigma
            )
            response_time = max(0.1, min(168, response_time))  # Cap at 1 week
            interaction.response_times.append(response_time)

            if interaction.last_response_channel is None:
                interaction.last_response_channel = channel

        # Determine outcome
        outcome = "no_response"
        amount_collected = Decimal("0")
        notes = ""

        if responded:
            outcome, amount_collected, notes = self._determine_outcome(
                consumer, day, channel
            )

            # Update trust based on outcome
            positive_outcome = outcome in ["payment", "plan_setup", "settlement"]
            interaction.update_trust(positive_outcome, profile.trust_building_rate)

        # Track contact
        if consumer.first_contact_day < 0:
            consumer.first_contact_day = day
        consumer.last_contact_day = day

        return ContactAttempt(
            day=day,
            hour=hour,
            channel=channel,
            responded=responded,
            response_time_hours=response_time,
            outcome=outcome,
            amount_collected=amount_collected,
            notes=notes,
        )

    def _determine_outcome(
        self,
        consumer: SimulatedConsumer,
        day: int,
        channel: ContactChannel,
    ) -> Tuple[str, Decimal, str]:
        """Determine outcome of a successful contact"""

        profile = consumer.profile
        tier_profile = consumer.tier_profile
        interaction = consumer.interaction_state

        balance = consumer.balance

        # Check for escalation triggers first
        if self._check_escalation(consumer):
            return self._handle_escalation(consumer)

        # Life event impact on payment ability
        payment_ability = 1.0
        if consumer.current_life_event != LifeEvent.NONE:
            impact = LIFE_EVENT_IMPACTS[consumer.current_life_event]
            days_since = day - consumer.life_event_start_day
            if days_since <= impact.duration_days:
                payment_ability = impact.payment_ability_multiplier

        # Calculate payment probability
        full_pay_prob = (
            profile.full_payment_probability *
            tier_profile.full_payment_multiplier *
            payment_ability
        )

        # Check for full payment
        if random.random() < full_pay_prob:
            consumer.balance = Decimal("0")
            consumer.payments_made += 1
            consumer.total_paid += balance
            consumer.status = "paid_in_full"
            if consumer.first_payment_day < 0:
                consumer.first_payment_day = day
            consumer.last_payment_day = day
            return ("payment", balance, "Full payment")

        # Check for settlement
        settlement_prob = profile.settlement_acceptance_base * payment_ability

        # Settlement more likely if we've offered good terms
        if consumer.best_settlement_offered < 0.60:
            settlement_prob *= 1.25

        if random.random() < settlement_prob and consumer.settlement_offers_received > 0:
            # Accept settlement
            settlement_pct = consumer.best_settlement_offered
            amount = (balance * Decimal(str(settlement_pct))).quantize(Decimal("0.01"))
            consumer.balance = Decimal("0")
            consumer.payments_made += 1
            consumer.total_paid += amount
            consumer.status = "settled"
            if consumer.first_payment_day < 0:
                consumer.first_payment_day = day
            consumer.last_payment_day = day
            return ("settlement", amount, f"Settlement at {settlement_pct*100:.0f}%")

        # Check for payment plan setup
        plan_prob = 0.30 if consumer.archetype in [
            ConsumerArchetype.PLAN_KEEPER,
            ConsumerArchetype.PLAN_BREAKER,
            ConsumerArchetype.NEGOTIATOR,
        ] else 0.15

        if random.random() < plan_prob and not consumer.on_payment_plan:
            months = tier_profile.avg_plan_months
            monthly_amount = (balance / months).quantize(Decimal("0.01"))
            consumer.on_payment_plan = True
            consumer.plan_payments_remaining = months
            consumer.plan_payment_amount = monthly_amount
            consumer.status = "on_plan"

            # First payment often happens immediately
            if random.random() < 0.70:
                consumer.balance -= monthly_amount
                consumer.payments_made += 1
                consumer.total_paid += monthly_amount
                consumer.plan_payments_remaining -= 1
                consumer.consecutive_plan_payments = 1
                if consumer.first_payment_day < 0:
                    consumer.first_payment_day = day
                consumer.last_payment_day = day
                return ("plan_setup", monthly_amount, f"Plan: {months}mo @ ${monthly_amount}")

            return ("plan_setup", Decimal("0"), f"Plan: {months}mo @ ${monthly_amount}")

        # Partial payment
        if random.random() < 0.20 * payment_ability:
            pct = random.uniform(0.15, 0.40)
            amount = (balance * Decimal(str(pct))).quantize(Decimal("0.01"))
            consumer.balance -= amount
            consumer.payments_made += 1
            consumer.total_paid += amount
            consumer.status = "partial"
            if consumer.first_payment_day < 0:
                consumer.first_payment_day = day
            consumer.last_payment_day = day
            return ("partial_payment", amount, "Partial payment")

        # No payment - various reasons
        if consumer.archetype == ConsumerArchetype.NEGOTIATOR:
            return ("request_settlement", Decimal("0"), "Requesting better settlement")
        elif consumer.archetype == ConsumerArchetype.PLAN_KEEPER:
            return ("request_plan", Decimal("0"), "Requesting payment plan")
        elif consumer.archetype == ConsumerArchetype.PLAN_BREAKER:
            return ("promise", Decimal("0"), "Promise to pay later")
        else:
            return ("no_payment", Decimal("0"), "Unable/unwilling to pay")

    def _check_escalation(self, consumer: SimulatedConsumer) -> bool:
        """Check if escalation should be triggered"""

        profile = consumer.profile
        interaction = consumer.interaction_state

        # Already escalated
        if interaction.has_complained or interaction.has_disputed:
            return False

        # Check escalation threshold
        if interaction.total_contacts >= profile.escalation_threshold:
            return random.random() < 0.15

        # Hostile archetype more likely to escalate
        if consumer.archetype == ConsumerArchetype.HOSTILE:
            return random.random() < 0.20

        # High fatigue can trigger escalation
        if interaction.fatigue_level > 0.80:
            return random.random() < 0.10

        return False

    def _handle_escalation(
        self,
        consumer: SimulatedConsumer
    ) -> Tuple[str, Decimal, str]:
        """Handle escalation events"""

        profile = consumer.profile
        interaction = consumer.interaction_state

        # Determine escalation type
        if profile.disputes_debts and random.random() < 0.50:
            interaction.has_disputed = True
            consumer.status = "disputed"
            return ("dispute", Decimal("0"), "Debt disputed")

        if profile.files_complaints and random.random() < 0.40:
            interaction.has_complained = True
            return ("complaint", Decimal("0"), "Complaint filed")

        if profile.threatens_legal and random.random() < 0.30:
            interaction.has_threatened_legal = True
            return ("legal_threat", Decimal("0"), "Legal action threatened")

        if random.random() < 0.50:
            interaction.requested_cease_comm = True
            consumer.status = "cease_comm"
            return ("cease_comm", Decimal("0"), "Cease communication requested")

        return ("escalation_warning", Decimal("0"), "Consumer expressed frustration")

    def process_payment_plan(
        self,
        consumer: SimulatedConsumer,
        day: int
    ) -> Tuple[bool, Decimal]:
        """Process scheduled payment plan payment"""

        if not consumer.on_payment_plan or consumer.plan_payments_remaining <= 0:
            return False, Decimal("0")

        profile = consumer.profile
        tier_profile = consumer.tier_profile

        # Base adherence rate
        adherence = profile.plan_adherence_rate

        # Adjust for consecutive payments (momentum)
        if consumer.consecutive_plan_payments > 0:
            adherence += 0.05 * min(3, consumer.consecutive_plan_payments)

        # Adjust for tier
        adherence *= (tier_profile.plan_completion_rate / 0.70)

        # Life event impact
        if consumer.current_life_event != LifeEvent.NONE:
            impact = LIFE_EVENT_IMPACTS[consumer.current_life_event]
            days_since = day - consumer.life_event_start_day
            if days_since <= impact.duration_days:
                adherence *= impact.payment_ability_multiplier

        # Economic impact
        adherence *= self.economic_condition.payment_multiplier

        if random.random() < adherence:
            # Successful payment
            amount = consumer.plan_payment_amount
            consumer.balance -= amount
            consumer.payments_made += 1
            consumer.total_paid += amount
            consumer.plan_payments_remaining -= 1
            consumer.consecutive_plan_payments += 1
            consumer.last_payment_day = day

            if consumer.plan_payments_remaining <= 0:
                consumer.on_payment_plan = False
                consumer.status = "paid_in_full"

            return True, amount
        else:
            # Failed payment
            consumer.failed_payments += 1
            consumer.consecutive_plan_payments = 0

            # After 2 failed payments, plan likely broken
            if consumer.failed_payments >= 2:
                consumer.on_payment_plan = False
                consumer.status = "plan_broken"

            return False, Decimal("0")

    def simulate_retry_behavior(
        self,
        consumer: SimulatedConsumer,
        day: int
    ) -> Optional[Decimal]:
        """Simulate retry after failed payment"""

        if consumer.failed_payments == 0:
            return None

        profile = consumer.profile

        # Retry probability decreases with failures
        retry_prob = max(0.10, 0.50 - (consumer.failed_payments * 0.15))

        # Plan keepers more likely to retry
        if consumer.archetype == ConsumerArchetype.PLAN_KEEPER:
            retry_prob += 0.20
        elif consumer.archetype == ConsumerArchetype.PLAN_BREAKER:
            retry_prob -= 0.15

        if random.random() < retry_prob:
            # Retry successful
            amount = consumer.plan_payment_amount
            consumer.balance -= amount
            consumer.payments_made += 1
            consumer.total_paid += amount
            consumer.failed_payments = max(0, consumer.failed_payments - 1)
            consumer.last_payment_day = day

            if consumer.on_payment_plan:
                consumer.plan_payments_remaining -= 1
                if consumer.plan_payments_remaining <= 0:
                    consumer.on_payment_plan = False
                    consumer.status = "paid_in_full"

            return amount

        return None

    def offer_settlement(
        self,
        consumer: SimulatedConsumer,
        settlement_pct: float
    ):
        """Make a settlement offer to consumer"""
        consumer.settlement_offers_received += 1
        if settlement_pct < consumer.best_settlement_offered:
            consumer.best_settlement_offered = settlement_pct

    def trigger_life_event(
        self,
        consumer: SimulatedConsumer,
        day: int
    ):
        """Potentially trigger a life event"""

        # Can only have one active life event
        if consumer.current_life_event != LifeEvent.NONE:
            # Check if current event has ended
            impact = LIFE_EVENT_IMPACTS[consumer.current_life_event]
            days_since = day - consumer.life_event_start_day
            if days_since <= impact.duration_days:
                return
            else:
                consumer.current_life_event = LifeEvent.NONE

        # Sample new event
        event = self._sample_life_event()
        if event != LifeEvent.NONE:
            consumer.current_life_event = event
            consumer.life_event_start_day = day

    async def run_simulation(self) -> SimulationMetrics:
        """Run full simulation across all consumers"""

        if not self.consumers:
            self.generate_consumers()

        logger.info(f"Running {self.config.simulation_days}-day simulation "
                   f"for {len(self.consumers):,} consumers...")

        # Initialize journeys
        self.journeys = [
            ConsumerJourney(consumer=c) for c in self.consumers
        ]

        journey_map = {j.consumer.consumer_id: j for j in self.journeys}

        # Run simulation days
        for day in range(self.config.simulation_days):
            self.current_day = day
            self.current_month = (day // 30) % 12 + 1

            # Weekly counter reset
            if day % 7 == 0:
                for c in self.consumers:
                    c.interaction_state.reset_weekly_counters()

            # Monthly counter reset
            if day % 30 == 0:
                for c in self.consumers:
                    c.interaction_state.reset_monthly_counters()

            # Process each consumer
            for consumer in self.consumers:
                if consumer.status in ["paid_in_full", "settled", "ceased", "disputed"]:
                    continue

                journey = journey_map[consumer.consumer_id]

                # Potentially trigger life event
                if random.random() < 0.01 * self.config.life_event_frequency:
                    self.trigger_life_event(consumer, day)
                    if consumer.current_life_event != LifeEvent.NONE:
                        journey.experienced_life_event = True

                # Process payment plan if active
                if consumer.on_payment_plan and day % 30 == consumer.payday_day_of_month:
                    success, amount = self.process_payment_plan(consumer, day)
                    if success:
                        journey.total_collected += amount
                    elif consumer.status == "plan_broken":
                        # Try retry
                        retry_amount = self.simulate_retry_behavior(consumer, day)
                        if retry_amount:
                            journey.total_collected += retry_amount

                # Determine if we should contact
                should_contact = self._should_contact(consumer, day)

                if should_contact:
                    # Select channel
                    channel = self._select_channel(consumer)

                    # Select hour (business hours weighted)
                    hour = random.choices(
                        list(range(8, 21)),
                        weights=[0.05, 0.10, 0.15, 0.15, 0.10, 0.08,
                                0.08, 0.08, 0.08, 0.05, 0.05, 0.02, 0.01]
                    )[0]

                    # Make settlement offer periodically
                    if consumer.interaction_state.total_contacts % 3 == 2:
                        settlement_pct = random.uniform(
                            self.config.min_settlement_pct,
                            self.config.max_settlement_pct
                        )
                        self.offer_settlement(consumer, settlement_pct)

                    # Execute contact
                    contact = self.simulate_contact(consumer, day, hour, channel)
                    journey.contacts.append(contact)
                    journey.channels_used[channel.value] += 1

                    if contact.amount_collected > 0:
                        journey.total_collected += contact.amount_collected

                    # Track escalation
                    if contact.outcome in ["dispute", "complaint", "legal_threat", "cease_comm"]:
                        journey.escalation_occurred = True

            # Progress logging
            if day > 0 and day % 15 == 0:
                collected = sum(j.total_collected for j in self.journeys)
                total_bal = sum(c.original_balance for c in self.consumers)
                rate = float(collected / total_bal) * 100 if total_bal > 0 else 0
                logger.info(f"  Day {day}: Recovery {rate:.1f}%")

        # Calculate final metrics
        metrics = self._calculate_metrics()

        return metrics

    def _should_contact(self, consumer: SimulatedConsumer, day: int) -> bool:
        """Determine if we should contact this consumer today"""

        interaction = consumer.interaction_state

        # Already resolved
        if consumer.status in ["paid_in_full", "settled", "cease_comm", "disputed"]:
            return False

        # Respect cease communication
        if interaction.requested_cease_comm:
            return False

        # Check contact limits
        if interaction.contacts_this_week >= self.config.max_weekly_contacts:
            return False
        if interaction.contacts_this_month >= self.config.max_monthly_contacts:
            return False

        # Check minimum interval
        if consumer.last_contact_day >= 0:
            hours_since = (day - consumer.last_contact_day) * 24
            if hours_since < self.config.min_contact_interval_hours:
                return False

        # Contact probability based on strategy
        # More frequent early, taper off
        if interaction.total_contacts == 0:
            return True  # Always make first contact
        elif interaction.total_contacts < 5:
            return random.random() < 0.70
        elif interaction.total_contacts < 10:
            return random.random() < 0.50
        else:
            return random.random() < 0.30

    def _select_channel(self, consumer: SimulatedConsumer) -> ContactChannel:
        """Select communication channel for contact"""

        profile = consumer.profile
        interaction = consumer.interaction_state

        # If we've identified preferred channel, weight toward it
        if interaction.preferred_channel_identified and interaction.last_response_channel:
            if random.random() < 0.60:
                return interaction.last_response_channel

        # Otherwise use archetype preferences
        channels = list(ContactChannel)
        weights = [profile.channel_preferences.get(c.value, 0.25) for c in channels]

        return random.choices(channels, weights=weights)[0]

    def _calculate_metrics(self) -> SimulationMetrics:
        """Calculate comprehensive simulation metrics"""

        metrics = SimulationMetrics()

        metrics.total_consumers = len(self.consumers)
        metrics.total_balance = sum(c.original_balance for c in self.consumers)
        metrics.total_collected = sum(j.total_collected for j in self.journeys)

        if metrics.total_balance > 0:
            metrics.recovery_rate = float(metrics.total_collected / metrics.total_balance)

        # By archetype
        for archetype in ConsumerArchetype:
            arch_consumers = [c for c in self.consumers if c.archetype == archetype]
            if not arch_consumers:
                continue

            arch_journeys = [
                j for j in self.journeys
                if j.consumer.archetype == archetype
            ]

            total_bal = sum(c.original_balance for c in arch_consumers)
            total_coll = sum(j.total_collected for j in arch_journeys)
            total_contacts = sum(len(j.contacts) for j in arch_journeys)
            responses = sum(
                1 for j in arch_journeys
                for c in j.contacts if c.responded
            )

            metrics.archetype_metrics[archetype.value] = {
                "count": len(arch_consumers),
                "balance": float(total_bal),
                "collected": float(total_coll),
                "recovery_rate": float(total_coll / total_bal) if total_bal > 0 else 0,
                "total_contacts": total_contacts,
                "response_rate": responses / total_contacts if total_contacts > 0 else 0,
            }

        # By channel
        for channel in ContactChannel:
            ch_contacts = [
                c for j in self.journeys
                for c in j.contacts if c.channel == channel
            ]
            if not ch_contacts:
                continue

            responses = sum(1 for c in ch_contacts if c.responded)
            collected = sum(c.amount_collected for c in ch_contacts)

            metrics.channel_metrics[channel.value] = {
                "contacts": len(ch_contacts),
                "responses": responses,
                "response_rate": responses / len(ch_contacts),
                "collected": float(collected),
            }

        # By balance tier
        for tier in BalanceTier:
            tier_consumers = [c for c in self.consumers if c.balance_tier == tier]
            if not tier_consumers:
                continue

            tier_journeys = [
                j for j in self.journeys
                if j.consumer.balance_tier == tier
            ]

            total_bal = sum(c.original_balance for c in tier_consumers)
            total_coll = sum(j.total_collected for j in tier_journeys)

            metrics.tier_metrics[tier.value] = {
                "count": len(tier_consumers),
                "balance": float(total_bal),
                "collected": float(total_coll),
                "recovery_rate": float(total_coll / total_bal) if total_bal > 0 else 0,
            }

        # Response patterns
        all_contacts = [c for j in self.journeys for c in j.contacts]
        if all_contacts:
            responses = [c for c in all_contacts if c.responded]
            metrics.avg_response_rate = len(responses) / len(all_contacts)

            response_times = [c.response_time_hours for c in responses if c.response_time_hours > 0]
            if response_times:
                metrics.avg_response_time_hours = statistics.mean(response_times)

        # Payment patterns
        full_paid = [c for c in self.consumers if c.status == "paid_in_full"]
        settled = [c for c in self.consumers if c.status == "settled"]

        resolved = len(full_paid) + len(settled)
        if resolved > 0:
            metrics.full_payment_rate = len(full_paid) / resolved
            metrics.settlement_rate = len(settled) / resolved

        # Plan completion
        had_plan = [c for c in self.consumers if c.payments_made > 1 or c.on_payment_plan]
        completed_plan = [c for c in had_plan if c.status == "paid_in_full"]
        if had_plan:
            metrics.plan_completion_rate = len(completed_plan) / len(had_plan)

        # Settlement percentages
        settlement_pcts = [
            float(c.total_paid / c.original_balance)
            for c in settled
            if c.original_balance > 0
        ]
        if settlement_pcts:
            metrics.avg_settlement_pct = statistics.mean(settlement_pcts)

        # Interaction metrics
        all_contacts_count = len(all_contacts)
        if metrics.total_consumers > 0:
            metrics.avg_contacts_per_consumer = all_contacts_count / metrics.total_consumers

        if metrics.total_collected > 0:
            metrics.contacts_per_dollar = all_contacts_count / float(metrics.total_collected)

        # Fatigue at resolution
        resolved_consumers = [c for c in self.consumers if c.status in ["paid_in_full", "settled"]]
        if resolved_consumers:
            fatigue_levels = [c.interaction_state.fatigue_level for c in resolved_consumers]
            metrics.avg_fatigue_at_resolution = statistics.mean(fatigue_levels)

        # Negative outcomes
        disputed = len([c for c in self.consumers if c.interaction_state.has_disputed])
        complained = len([c for c in self.consumers if c.interaction_state.has_complained])
        ceased = len([c for c in self.consumers if c.interaction_state.requested_cease_comm])

        metrics.dispute_rate = disputed / metrics.total_consumers if metrics.total_consumers > 0 else 0
        metrics.complaint_rate = complained / metrics.total_consumers if metrics.total_consumers > 0 else 0
        metrics.cease_comm_rate = ceased / metrics.total_consumers if metrics.total_consumers > 0 else 0

        # Time metrics
        first_payment_days = [
            c.first_payment_day
            for c in self.consumers
            if c.first_payment_day >= 0
        ]
        if first_payment_days:
            metrics.avg_days_to_first_payment = statistics.mean(first_payment_days)
            metrics.median_days_to_resolution = statistics.median(first_payment_days)

        return metrics

    def print_results(self, metrics: SimulationMetrics):
        """Print comprehensive simulation results"""

        print("\n" + "=" * 80)
        print("  CONSUMER INTERACTION SIMULATION RESULTS")
        print("=" * 80)

        print(f"\n  OVERALL METRICS:")
        print(f"    Total Consumers:     {metrics.total_consumers:,}")
        print(f"    Total Balance:       ${metrics.total_balance:,.2f}")
        print(f"    Total Collected:     ${metrics.total_collected:,.2f}")
        print(f"    Recovery Rate:       {metrics.recovery_rate*100:.1f}%")

        print(f"\n  RESPONSE PATTERNS:")
        print(f"    Avg Response Rate:   {metrics.avg_response_rate*100:.1f}%")
        print(f"    Avg Response Time:   {metrics.avg_response_time_hours:.1f} hours")
        print(f"    Contacts/Consumer:   {metrics.avg_contacts_per_consumer:.1f}")
        print(f"    Contacts/$1:         {metrics.contacts_per_dollar:.3f}")

        print(f"\n  PAYMENT OUTCOMES:")
        print(f"    Full Payment Rate:   {metrics.full_payment_rate*100:.1f}%")
        print(f"    Settlement Rate:     {metrics.settlement_rate*100:.1f}%")
        print(f"    Avg Settlement %:    {metrics.avg_settlement_pct*100:.1f}%")
        print(f"    Plan Completion:     {metrics.plan_completion_rate*100:.1f}%")

        print(f"\n  TIME METRICS:")
        print(f"    Avg Days to Payment: {metrics.avg_days_to_first_payment:.1f}")
        print(f"    Median Resolution:   {metrics.median_days_to_resolution:.1f} days")

        print(f"\n  NEGATIVE OUTCOMES:")
        print(f"    Dispute Rate:        {metrics.dispute_rate*100:.2f}%")
        print(f"    Complaint Rate:      {metrics.complaint_rate*100:.2f}%")
        print(f"    Cease Comm Rate:     {metrics.cease_comm_rate*100:.2f}%")
        print(f"    Avg Fatigue Level:   {metrics.avg_fatigue_at_resolution*100:.1f}%")

        print(f"\n  BY ARCHETYPE:")
        print("  " + "-" * 76)
        print(f"  {'Archetype':<15} {'Count':>8} {'Balance':>12} {'Collected':>12} "
              f"{'Rate':>8} {'Response':>10}")
        print("  " + "-" * 76)

        for arch, data in sorted(metrics.archetype_metrics.items()):
            print(f"  {arch:<15} {data['count']:>8,} ${data['balance']:>10,.0f} "
                  f"${data['collected']:>10,.0f} {data['recovery_rate']*100:>7.1f}% "
                  f"{data['response_rate']*100:>9.1f}%")

        print("  " + "-" * 76)

        print(f"\n  BY CHANNEL:")
        print("  " + "-" * 60)
        print(f"  {'Channel':<10} {'Contacts':>10} {'Responses':>10} "
              f"{'Rate':>10} {'Collected':>12}")
        print("  " + "-" * 60)

        for ch, data in sorted(metrics.channel_metrics.items()):
            print(f"  {ch:<10} {data['contacts']:>10,} {data['responses']:>10,} "
                  f"{data['response_rate']*100:>9.1f}% ${data['collected']:>10,.0f}")

        print("  " + "-" * 60)

        print(f"\n  BY BALANCE TIER:")
        print("  " + "-" * 60)
        print(f"  {'Tier':<12} {'Count':>8} {'Balance':>12} "
              f"{'Collected':>12} {'Rate':>10}")
        print("  " + "-" * 60)

        for tier, data in sorted(metrics.tier_metrics.items()):
            print(f"  {tier:<12} {data['count']:>8,} ${data['balance']:>10,.0f} "
                  f"${data['collected']:>10,.0f} {data['recovery_rate']*100:>9.1f}%")

        print("  " + "-" * 60)

        print("\n" + "=" * 80)


# =============================================================================
# BATCH SIMULATION RUNNER
# =============================================================================

async def run_batch_simulations(
    num_simulations: int = 5,
    consumers_per_sim: int = 10000,
    days_per_sim: int = 90,
) -> List[SimulationMetrics]:
    """Run multiple simulations for statistical analysis"""

    print(f"\n{'='*80}")
    print("  BATCH CONSUMER SIMULATION")
    print(f"{'='*80}")
    print(f"\n  Configuration:")
    print(f"    Simulations:      {num_simulations}")
    print(f"    Consumers/sim:    {consumers_per_sim:,}")
    print(f"    Days/sim:         {days_per_sim}")
    print(f"\n  Running simulations...")
    print("-" * 80)

    all_metrics = []

    for i in range(num_simulations):
        config = SimulatorConfig(
            num_consumers=consumers_per_sim,
            simulation_days=days_per_sim,
            random_seed=42 + i,
        )

        simulator = ConsumerInteractionSimulator(config)
        metrics = await simulator.run_simulation()
        all_metrics.append(metrics)

        print(f"  Sim {i+1}: Recovery {metrics.recovery_rate*100:.1f}%, "
              f"Response {metrics.avg_response_rate*100:.1f}%, "
              f"Collected ${metrics.total_collected:,.0f}")

    # Aggregate statistics
    recovery_rates = [m.recovery_rate for m in all_metrics]
    response_rates = [m.avg_response_rate for m in all_metrics]

    print("-" * 80)
    print(f"\n  AGGREGATE STATISTICS ({num_simulations} simulations):")
    print(f"    Recovery Rate:  {statistics.mean(recovery_rates)*100:.1f}% "
          f"(+/- {statistics.stdev(recovery_rates)*100:.1f}%)")
    print(f"    Response Rate:  {statistics.mean(response_rates)*100:.1f}% "
          f"(+/- {statistics.stdev(response_rates)*100:.1f}%)")

    print(f"\n  INDUSTRY BENCHMARK COMPARISON:")
    print(f"    QUAN Simulated:  {statistics.mean(recovery_rates)*100:.1f}%")
    print(f"    Industry Avg:    25-35%")
    print(f"    Match Status:    {'ALIGNED' if 0.25 <= statistics.mean(recovery_rates) <= 0.45 else 'REVIEW NEEDED'}")

    print("\n" + "=" * 80)

    return all_metrics


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_consumer_simulation():
    """Run the full consumer interaction simulation"""

    config = SimulatorConfig(
        num_consumers=10000,
        simulation_days=90,
        random_seed=42,
    )

    simulator = ConsumerInteractionSimulator(config)
    metrics = await simulator.run_simulation()
    simulator.print_results(metrics)

    return simulator, metrics


if __name__ == "__main__":
    asyncio.run(run_consumer_simulation())
