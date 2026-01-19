"""
Negotiation Parameter Tuner

Advanced simulation engine for optimizing debt collection negotiation strategies
using game theory principles and behavioral modeling.

Key Features:
- Multi-strategy negotiation modeling
- Game theory (Nash equilibrium, backward induction)
- Risk-adjusted expected value calculations
- 50,000 negotiation simulations
- Optimal strategy by debtor profile
"""

import asyncio
import random
import statistics
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import defaultdict
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CALIBRATED MODEL CONSTANTS
# =============================================================================

# Industry calibrated baseline parameters
CALIBRATED_RECOVERY_RATE = 0.47  # 47% recovery
CALIBRATED_AVG_BALANCE = Decimal("400")  # $400 average
CALIBRATED_SETTLEMENT_RATE = 0.35  # 35% typical settlement


# =============================================================================
# NEGOTIATION STRATEGY DEFINITIONS
# =============================================================================

class NegotiationApproach(Enum):
    """Primary negotiation approach"""
    FULL_PAYMENT_FIRST = "full_payment_first"
    IMMEDIATE_SETTLEMENT = "immediate_settlement"
    GRADUATED_CONCESSION = "graduated_concession"
    PAYMENT_PLAN_FOCUS = "payment_plan_focus"
    HYBRID_ADAPTIVE = "hybrid_adaptive"


class UrgencyLevel(Enum):
    """Urgency messaging level"""
    LOW = "low"           # Gentle reminders
    MEDIUM = "medium"     # Standard collection tone
    HIGH = "high"         # Emphasize consequences
    CRITICAL = "critical" # Final notice, escalation warning


class CounterOfferLevel(Enum):
    """Counter offer aggressiveness as percentage of balance"""
    CONSERVATIVE = 0.80   # 80% of balance
    MODERATE = 0.70       # 70% of balance
    AGGRESSIVE = 0.60     # 60% of balance
    VERY_AGGRESSIVE = 0.50  # 50% of balance


class DebtorSegment(Enum):
    """Debtor profile segments"""
    WILLING_ABLE = "willing_able"         # Can and will pay
    WILLING_UNABLE = "willing_unable"     # Wants to pay but can't
    UNWILLING_ABLE = "unwilling_able"     # Can pay but avoids
    UNWILLING_UNABLE = "unwilling_unable" # Can't and won't pay
    DISPUTE_PRONE = "dispute_prone"       # Likely to dispute
    STRATEGIC_DEFAULT = "strategic_default" # Knows the system


@dataclass
class SettlementAuthority:
    """Settlement authority floors by segment"""
    segment: DebtorSegment
    min_settlement_pct: float  # Minimum acceptable settlement
    max_settlement_pct: float  # Starting offer
    escalation_threshold: int  # Days before escalating authority
    supervisor_floor: float    # Supervisor can go this low
    director_floor: float      # Director can go this low


# Settlement authority by segment
SETTLEMENT_AUTHORITY: Dict[DebtorSegment, SettlementAuthority] = {
    DebtorSegment.WILLING_ABLE: SettlementAuthority(
        segment=DebtorSegment.WILLING_ABLE,
        min_settlement_pct=0.85,
        max_settlement_pct=1.00,
        escalation_threshold=14,
        supervisor_floor=0.75,
        director_floor=0.65
    ),
    DebtorSegment.WILLING_UNABLE: SettlementAuthority(
        segment=DebtorSegment.WILLING_UNABLE,
        min_settlement_pct=0.50,
        max_settlement_pct=0.80,
        escalation_threshold=7,
        supervisor_floor=0.40,
        director_floor=0.30
    ),
    DebtorSegment.UNWILLING_ABLE: SettlementAuthority(
        segment=DebtorSegment.UNWILLING_ABLE,
        min_settlement_pct=0.70,
        max_settlement_pct=1.00,
        escalation_threshold=21,
        supervisor_floor=0.60,
        director_floor=0.50
    ),
    DebtorSegment.UNWILLING_UNABLE: SettlementAuthority(
        segment=DebtorSegment.UNWILLING_UNABLE,
        min_settlement_pct=0.35,
        max_settlement_pct=0.60,
        escalation_threshold=7,
        supervisor_floor=0.25,
        director_floor=0.20
    ),
    DebtorSegment.DISPUTE_PRONE: SettlementAuthority(
        segment=DebtorSegment.DISPUTE_PRONE,
        min_settlement_pct=0.45,
        max_settlement_pct=0.75,
        escalation_threshold=10,
        supervisor_floor=0.35,
        director_floor=0.25
    ),
    DebtorSegment.STRATEGIC_DEFAULT: SettlementAuthority(
        segment=DebtorSegment.STRATEGIC_DEFAULT,
        min_settlement_pct=0.40,
        max_settlement_pct=0.70,
        escalation_threshold=14,
        supervisor_floor=0.30,
        director_floor=0.25
    ),
}


@dataclass
class PaymentPlanTerms:
    """Payment plan configuration"""
    min_down_payment_pct: float  # Minimum down payment as % of balance
    max_term_months: int         # Maximum plan duration
    min_monthly_payment: Decimal # Minimum monthly payment
    interest_rate: float         # Monthly interest (0 for hardship)
    re_default_threshold: int    # Missed payments before re-default
    flexibility_level: str       # "rigid", "moderate", "flexible"


# Payment plan flexibility levels
PAYMENT_PLAN_TIERS: Dict[str, PaymentPlanTerms] = {
    "rigid": PaymentPlanTerms(
        min_down_payment_pct=0.25,
        max_term_months=6,
        min_monthly_payment=Decimal("50"),
        interest_rate=0.01,
        re_default_threshold=1,
        flexibility_level="rigid"
    ),
    "moderate": PaymentPlanTerms(
        min_down_payment_pct=0.15,
        max_term_months=12,
        min_monthly_payment=Decimal("25"),
        interest_rate=0.005,
        re_default_threshold=2,
        flexibility_level="moderate"
    ),
    "flexible": PaymentPlanTerms(
        min_down_payment_pct=0.10,
        max_term_months=18,
        min_monthly_payment=Decimal("15"),
        interest_rate=0.0,
        re_default_threshold=3,
        flexibility_level="flexible"
    ),
    "hardship": PaymentPlanTerms(
        min_down_payment_pct=0.05,
        max_term_months=24,
        min_monthly_payment=Decimal("10"),
        interest_rate=0.0,
        re_default_threshold=3,
        flexibility_level="hardship"
    ),
}


# =============================================================================
# NEGOTIATION STRATEGY DATACLASSES
# =============================================================================

@dataclass
class NegotiationStrategy:
    """Complete negotiation strategy configuration"""
    name: str
    approach: NegotiationApproach
    counter_offer_levels: List[float]  # Sequence of offers (% of balance)
    urgency_levels: List[UrgencyLevel] # Urgency by contact attempt
    payment_plan_tier: str
    settlement_flexibility: float  # 0-1, higher = more willing to settle
    concession_timing: List[int]   # Days between concessions
    max_negotiation_rounds: int


# Pre-defined negotiation strategies
NEGOTIATION_STRATEGIES: Dict[str, NegotiationStrategy] = {
    "aggressive_full": NegotiationStrategy(
        name="Aggressive Full Payment",
        approach=NegotiationApproach.FULL_PAYMENT_FIRST,
        counter_offer_levels=[1.00, 0.95, 0.90, 0.85, 0.80],
        urgency_levels=[UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.HIGH, UrgencyLevel.CRITICAL, UrgencyLevel.CRITICAL],
        payment_plan_tier="rigid",
        settlement_flexibility=0.2,
        concession_timing=[7, 5, 5, 3],
        max_negotiation_rounds=5
    ),
    "immediate_settlement": NegotiationStrategy(
        name="Immediate Settlement Offer",
        approach=NegotiationApproach.IMMEDIATE_SETTLEMENT,
        counter_offer_levels=[0.70, 0.60, 0.50, 0.45, 0.40],
        urgency_levels=[UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.HIGH],
        payment_plan_tier="moderate",
        settlement_flexibility=0.8,
        concession_timing=[5, 4, 3, 3],
        max_negotiation_rounds=5
    ),
    "graduated_concession": NegotiationStrategy(
        name="Graduated Concession",
        approach=NegotiationApproach.GRADUATED_CONCESSION,
        counter_offer_levels=[1.00, 0.85, 0.75, 0.65, 0.55, 0.50],
        urgency_levels=[UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.HIGH, UrgencyLevel.CRITICAL],
        payment_plan_tier="moderate",
        settlement_flexibility=0.5,
        concession_timing=[10, 7, 5, 4, 3],
        max_negotiation_rounds=6
    ),
    "payment_plan_focus": NegotiationStrategy(
        name="Payment Plan Focus",
        approach=NegotiationApproach.PAYMENT_PLAN_FOCUS,
        counter_offer_levels=[1.00, 1.00, 0.90, 0.85, 0.80],
        urgency_levels=[UrgencyLevel.LOW, UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH],
        payment_plan_tier="flexible",
        settlement_flexibility=0.3,
        concession_timing=[14, 10, 7, 5],
        max_negotiation_rounds=5
    ),
    "hybrid_adaptive": NegotiationStrategy(
        name="Hybrid Adaptive",
        approach=NegotiationApproach.HYBRID_ADAPTIVE,
        counter_offer_levels=[0.90, 0.80, 0.70, 0.60, 0.50, 0.45],
        urgency_levels=[UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.HIGH, UrgencyLevel.CRITICAL],
        payment_plan_tier="moderate",
        settlement_flexibility=0.6,
        concession_timing=[7, 5, 4, 3, 3],
        max_negotiation_rounds=6
    ),
}


# =============================================================================
# DEBTOR MODEL
# =============================================================================

@dataclass
class DebtorProfile:
    """Detailed debtor profile for negotiation simulation"""
    debtor_id: str
    segment: DebtorSegment
    balance: Decimal

    # Financial capacity
    income_bracket: str  # "low", "medium", "high"
    disposable_income: Decimal
    other_debts: int

    # Behavioral traits
    payment_threshold: float    # Min settlement % they'll accept
    urgency_sensitivity: float  # 0-1, how much urgency affects them
    negotiation_skill: float    # 0-1, how skilled at negotiating
    patience: float             # 0-1, how long they'll negotiate

    # Response characteristics
    response_probability: float
    dispute_probability: float
    plan_adherence_rate: float  # Probability of completing payment plan

    # State tracking
    current_offer: float = 1.0
    negotiation_round: int = 0
    days_in_negotiation: int = 0
    has_responded: bool = False
    accepted_offer: Optional[float] = None
    on_payment_plan: bool = False
    plan_payments_made: int = 0
    plan_payments_missed: int = 0


@dataclass
class NegotiationOutcome:
    """Result of a single negotiation simulation"""
    debtor_id: str
    strategy_name: str
    segment: DebtorSegment
    balance: Decimal

    # Outcome
    accepted: bool
    settlement_rate: float  # % of balance paid
    amount_collected: Decimal

    # Process metrics
    negotiation_rounds: int
    days_to_resolution: int
    final_urgency: UrgencyLevel

    # Payment type
    payment_type: str  # "full", "settlement", "plan", "none"
    plan_months: int = 0
    re_defaulted: bool = False

    # Friction metrics
    dispute_raised: bool = False
    escalation_needed: bool = False
    customer_friction_score: float = 0.0


# =============================================================================
# GAME THEORY ENGINE
# =============================================================================

class GameTheoryEngine:
    """
    Game theory calculations for optimal negotiation strategies.

    Implements:
    - Nash equilibrium for settlement offers
    - Backward induction for optimal concession timing
    - Risk-adjusted expected value calculations
    """

    def __init__(self):
        self.equilibrium_cache: Dict[str, float] = {}

    def calculate_nash_equilibrium(
        self,
        debtor: DebtorProfile,
        strategy: NegotiationStrategy,
        current_round: int
    ) -> float:
        """
        Calculate Nash equilibrium settlement offer.

        The equilibrium is where neither party benefits from unilaterally
        changing their strategy.

        Collector's payoff: settlement_rate * balance - collection_costs
        Debtor's payoff: (1 - settlement_rate) * balance - hassle_costs
        """
        cache_key = f"{debtor.segment.value}_{strategy.name}_{current_round}"
        if cache_key in self.equilibrium_cache:
            return self.equilibrium_cache[cache_key]

        # Debtor's reservation price (minimum they'd rationally accept)
        # Based on their payment threshold and negotiation skill
        debtor_floor = debtor.payment_threshold * (1 - debtor.negotiation_skill * 0.2)

        # Collector's reservation price (minimum acceptable)
        authority = SETTLEMENT_AUTHORITY.get(debtor.segment)
        if authority:
            if current_round <= 2:
                collector_floor = authority.min_settlement_pct
            elif current_round <= 4:
                collector_floor = authority.supervisor_floor
            else:
                collector_floor = authority.director_floor
        else:
            collector_floor = 0.35

        # Nash equilibrium: split the difference adjusted by bargaining power
        bargaining_power = 0.5 + (strategy.settlement_flexibility - 0.5) * 0.3

        if debtor_floor >= collector_floor:
            # Zone of possible agreement exists
            equilibrium = collector_floor + (debtor_floor - collector_floor) * bargaining_power
        else:
            # No natural equilibrium, use collector's best offer
            equilibrium = collector_floor

        # Adjust for urgency effect
        urgency_mult = {
            UrgencyLevel.LOW: 1.0,
            UrgencyLevel.MEDIUM: 0.98,
            UrgencyLevel.HIGH: 0.95,
            UrgencyLevel.CRITICAL: 0.92
        }

        if current_round < len(strategy.urgency_levels):
            urgency = strategy.urgency_levels[current_round]
            equilibrium *= urgency_mult.get(urgency, 1.0)

        equilibrium = max(0.20, min(1.0, equilibrium))
        self.equilibrium_cache[cache_key] = equilibrium

        return equilibrium

    def backward_induction_optimal_timing(
        self,
        debtor: DebtorProfile,
        strategy: NegotiationStrategy,
        remaining_rounds: int,
        current_offer: float
    ) -> Tuple[int, float]:
        """
        Use backward induction to determine optimal concession timing.

        Works backward from the final round to determine when each
        concession should be made to maximize expected value.

        Returns: (optimal_days_to_wait, optimal_concession_amount)
        """
        if remaining_rounds <= 0:
            return (0, 0.0)

        # Terminal payoff if no agreement
        terminal_value = 0.0

        # Work backward through rounds
        round_values = []

        for r in range(remaining_rounds, 0, -1):
            round_idx = len(strategy.counter_offer_levels) - r
            if round_idx < 0 or round_idx >= len(strategy.counter_offer_levels):
                continue

            offer = strategy.counter_offer_levels[round_idx]

            # Probability of acceptance at this offer
            acceptance_prob = self._calculate_acceptance_probability(
                debtor, offer, r, strategy
            )

            # Expected value of accepting now
            ev_accept = acceptance_prob * offer * float(debtor.balance)

            # Expected value of waiting (discounted future value)
            if r < remaining_rounds:
                ev_wait = round_values[-1][1] * 0.98  # 2% time discount
            else:
                ev_wait = terminal_value

            # Continuation value
            ev_continue = (1 - acceptance_prob) * ev_wait

            # Total expected value this round
            ev_total = ev_accept + ev_continue

            # Optimal timing
            timing_idx = round_idx
            if timing_idx < len(strategy.concession_timing):
                days_to_wait = strategy.concession_timing[timing_idx]
            else:
                days_to_wait = 3

            # Adjust timing based on debtor patience
            patience_adj = int(days_to_wait * debtor.patience)
            optimal_days = max(1, patience_adj)

            round_values.append((optimal_days, ev_total, offer))

        if round_values:
            # Return first round's optimal values
            optimal = round_values[-1]
            concession = current_offer - strategy.counter_offer_levels[0] if strategy.counter_offer_levels else 0
            return (optimal[0], abs(concession))

        return (3, 0.05)  # Default: wait 3 days, 5% concession

    def _calculate_acceptance_probability(
        self,
        debtor: DebtorProfile,
        offer: float,
        rounds_remaining: int,
        strategy: NegotiationStrategy
    ) -> float:
        """Calculate probability debtor accepts given offer"""

        # Base acceptance: how close is offer to their threshold?
        if offer <= debtor.payment_threshold:
            base_accept = 0.7 + 0.25 * (debtor.payment_threshold - offer) / debtor.payment_threshold
        else:
            distance = offer - debtor.payment_threshold
            base_accept = max(0.05, 0.7 - distance * 2)

        # Adjust for urgency
        urgency_idx = len(strategy.counter_offer_levels) - rounds_remaining
        if urgency_idx < len(strategy.urgency_levels):
            urgency = strategy.urgency_levels[urgency_idx]
            urgency_boost = debtor.urgency_sensitivity * {
                UrgencyLevel.LOW: 0.0,
                UrgencyLevel.MEDIUM: 0.05,
                UrgencyLevel.HIGH: 0.12,
                UrgencyLevel.CRITICAL: 0.20
            }.get(urgency, 0)
            base_accept += urgency_boost

        # Adjust for patience (impatient debtors accept sooner)
        patience_factor = 1.0 - (debtor.patience * 0.2 * rounds_remaining / 5)
        base_accept *= patience_factor

        return max(0.01, min(0.95, base_accept))

    def calculate_risk_adjusted_expected_value(
        self,
        debtor: DebtorProfile,
        strategy: NegotiationStrategy,
        offer: float,
        days_elapsed: int
    ) -> Dict[str, float]:
        """
        Calculate risk-adjusted expected value of current negotiation state.

        Considers:
        - Probability of acceptance
        - Probability of dispute
        - Time value of money
        - Re-default risk for payment plans
        - Collection cost
        """
        balance = float(debtor.balance)

        # Acceptance probability
        rounds_remaining = strategy.max_negotiation_rounds - debtor.negotiation_round
        p_accept = self._calculate_acceptance_probability(
            debtor, offer, rounds_remaining, strategy
        )

        # Dispute probability increases with urgency
        base_dispute = debtor.dispute_probability
        urgency_idx = min(debtor.negotiation_round, len(strategy.urgency_levels) - 1)
        if urgency_idx >= 0:
            urgency = strategy.urgency_levels[urgency_idx]
            dispute_mult = {
                UrgencyLevel.LOW: 0.8,
                UrgencyLevel.MEDIUM: 1.0,
                UrgencyLevel.HIGH: 1.3,
                UrgencyLevel.CRITICAL: 1.6
            }.get(urgency, 1.0)
            p_dispute = min(0.5, base_dispute * dispute_mult)
        else:
            p_dispute = base_dispute

        # Time discount (2% per 30 days)
        time_discount = 0.98 ** (days_elapsed / 30)

        # Expected value from immediate settlement
        ev_settlement = p_accept * offer * balance * time_discount

        # Expected value from payment plan
        plan_tier = PAYMENT_PLAN_TIERS.get(strategy.payment_plan_tier, PAYMENT_PLAN_TIERS["moderate"])
        p_plan_success = debtor.plan_adherence_rate
        plan_recovery = offer * balance * p_plan_success * 0.95  # 5% plan admin cost
        ev_plan = (1 - p_accept) * 0.3 * plan_recovery * time_discount  # 30% go to plans

        # Expected loss from disputes
        ev_dispute = p_dispute * balance * 0.15  # Disputes cost ~15% in handling

        # Collection cost
        cost_per_contact = 0.50
        contacts = debtor.negotiation_round + 1
        collection_cost = cost_per_contact * contacts

        # Net expected value
        gross_ev = ev_settlement + ev_plan - ev_dispute
        net_ev = gross_ev - collection_cost

        # Risk metrics
        variance = (p_accept * (1 - p_accept) * (offer * balance) ** 2)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        # Sharpe-like ratio (return per unit risk)
        risk_adjusted_return = net_ev / (std_dev + 1) if std_dev > 0 else net_ev

        return {
            "gross_ev": gross_ev,
            "net_ev": net_ev,
            "ev_settlement": ev_settlement,
            "ev_plan": ev_plan,
            "ev_dispute": ev_dispute,
            "collection_cost": collection_cost,
            "p_accept": p_accept,
            "p_dispute": p_dispute,
            "time_discount": time_discount,
            "variance": variance,
            "std_dev": std_dev,
            "risk_adjusted_return": risk_adjusted_return,
            "sharpe_ratio": risk_adjusted_return / 100 if risk_adjusted_return > 0 else 0
        }


# =============================================================================
# NEGOTIATION SIMULATOR
# =============================================================================

class NegotiationSimulator:
    """
    Main simulation engine for negotiation parameter tuning.

    Runs 50,000 negotiation simulations across:
    - Multiple strategies
    - Multiple debtor segments
    - Varying balance ranges
    """

    def __init__(self):
        self.game_engine = GameTheoryEngine()
        self.outcomes: List[NegotiationOutcome] = []
        self.strategy_metrics: Dict[str, Dict] = {}
        self.segment_metrics: Dict[str, Dict] = {}
        self.settlement_curves: Dict[str, List[Tuple[float, float]]] = {}

    def generate_debtor_portfolio(self, num_debtors: int) -> List[DebtorProfile]:
        """Generate realistic debtor portfolio"""
        debtors = []

        # Segment distribution (calibrated to real data)
        segment_weights = {
            DebtorSegment.WILLING_ABLE: 0.15,
            DebtorSegment.WILLING_UNABLE: 0.30,
            DebtorSegment.UNWILLING_ABLE: 0.20,
            DebtorSegment.UNWILLING_UNABLE: 0.20,
            DebtorSegment.DISPUTE_PRONE: 0.10,
            DebtorSegment.STRATEGIC_DEFAULT: 0.05,
        }

        for i in range(num_debtors):
            # Select segment
            segment = random.choices(
                list(segment_weights.keys()),
                weights=list(segment_weights.values())
            )[0]

            # Generate balance (log-normal, centered on $400)
            balance = Decimal(str(
                max(25, min(2000, random.lognormvariate(math.log(400), 0.7)))
            )).quantize(Decimal("0.01"))

            # Income bracket based on segment
            if segment in [DebtorSegment.WILLING_ABLE, DebtorSegment.UNWILLING_ABLE]:
                income_weights = [0.2, 0.4, 0.4]
            elif segment == DebtorSegment.WILLING_UNABLE:
                income_weights = [0.6, 0.3, 0.1]
            else:
                income_weights = [0.4, 0.4, 0.2]

            income = random.choices(["low", "medium", "high"], weights=income_weights)[0]

            # Disposable income
            disposable_base = {"low": 100, "medium": 300, "high": 600}
            disposable = Decimal(str(
                max(0, random.gauss(disposable_base[income], disposable_base[income] * 0.3))
            )).quantize(Decimal("0.01"))

            # Behavioral traits based on segment
            traits = self._generate_segment_traits(segment)

            debtor = DebtorProfile(
                debtor_id=f"DBT-{i:06d}",
                segment=segment,
                balance=balance,
                income_bracket=income,
                disposable_income=disposable,
                other_debts=random.choices([0, 1, 2, 3, 4, 5], weights=[0.3, 0.25, 0.2, 0.12, 0.08, 0.05])[0],
                payment_threshold=traits["payment_threshold"],
                urgency_sensitivity=traits["urgency_sensitivity"],
                negotiation_skill=traits["negotiation_skill"],
                patience=traits["patience"],
                response_probability=traits["response_probability"],
                dispute_probability=traits["dispute_probability"],
                plan_adherence_rate=traits["plan_adherence_rate"]
            )

            debtors.append(debtor)

        return debtors

    def _generate_segment_traits(self, segment: DebtorSegment) -> Dict[str, float]:
        """Generate behavioral traits based on segment"""

        base_traits = {
            DebtorSegment.WILLING_ABLE: {
                "payment_threshold": random.uniform(0.70, 0.95),
                "urgency_sensitivity": random.uniform(0.3, 0.6),
                "negotiation_skill": random.uniform(0.2, 0.5),
                "patience": random.uniform(0.3, 0.6),
                "response_probability": random.uniform(0.6, 0.85),
                "dispute_probability": random.uniform(0.02, 0.08),
                "plan_adherence_rate": random.uniform(0.80, 0.95)
            },
            DebtorSegment.WILLING_UNABLE: {
                "payment_threshold": random.uniform(0.25, 0.50),
                "urgency_sensitivity": random.uniform(0.5, 0.8),
                "negotiation_skill": random.uniform(0.1, 0.4),
                "patience": random.uniform(0.4, 0.7),
                "response_probability": random.uniform(0.5, 0.75),
                "dispute_probability": random.uniform(0.05, 0.15),
                "plan_adherence_rate": random.uniform(0.40, 0.65)
            },
            DebtorSegment.UNWILLING_ABLE: {
                "payment_threshold": random.uniform(0.40, 0.65),
                "urgency_sensitivity": random.uniform(0.4, 0.7),
                "negotiation_skill": random.uniform(0.4, 0.7),
                "patience": random.uniform(0.5, 0.8),
                "response_probability": random.uniform(0.3, 0.55),
                "dispute_probability": random.uniform(0.08, 0.20),
                "plan_adherence_rate": random.uniform(0.60, 0.80)
            },
            DebtorSegment.UNWILLING_UNABLE: {
                "payment_threshold": random.uniform(0.15, 0.35),
                "urgency_sensitivity": random.uniform(0.2, 0.5),
                "negotiation_skill": random.uniform(0.2, 0.5),
                "patience": random.uniform(0.6, 0.9),
                "response_probability": random.uniform(0.15, 0.35),
                "dispute_probability": random.uniform(0.10, 0.25),
                "plan_adherence_rate": random.uniform(0.20, 0.45)
            },
            DebtorSegment.DISPUTE_PRONE: {
                "payment_threshold": random.uniform(0.30, 0.55),
                "urgency_sensitivity": random.uniform(0.1, 0.4),
                "negotiation_skill": random.uniform(0.5, 0.8),
                "patience": random.uniform(0.7, 0.95),
                "response_probability": random.uniform(0.4, 0.65),
                "dispute_probability": random.uniform(0.30, 0.60),
                "plan_adherence_rate": random.uniform(0.50, 0.70)
            },
            DebtorSegment.STRATEGIC_DEFAULT: {
                "payment_threshold": random.uniform(0.20, 0.40),
                "urgency_sensitivity": random.uniform(0.1, 0.3),
                "negotiation_skill": random.uniform(0.7, 0.95),
                "patience": random.uniform(0.8, 0.98),
                "response_probability": random.uniform(0.25, 0.45),
                "dispute_probability": random.uniform(0.15, 0.35),
                "plan_adherence_rate": random.uniform(0.55, 0.75)
            }
        }

        return base_traits.get(segment, base_traits[DebtorSegment.UNWILLING_UNABLE])

    async def simulate_negotiation(
        self,
        debtor: DebtorProfile,
        strategy: NegotiationStrategy
    ) -> NegotiationOutcome:
        """Simulate a complete negotiation with a debtor"""

        # Initialize outcome tracking
        accepted = False
        final_offer = 1.0
        days_elapsed = 0
        dispute_raised = False
        escalation_needed = False
        friction_score = 0.0
        payment_type = "none"
        plan_months = 0
        re_defaulted = False

        # Run negotiation rounds
        for round_num in range(strategy.max_negotiation_rounds):
            debtor.negotiation_round = round_num

            # Calculate current offer
            if round_num < len(strategy.counter_offer_levels):
                current_offer = strategy.counter_offer_levels[round_num]
            else:
                current_offer = strategy.counter_offer_levels[-1]

            debtor.current_offer = current_offer
            final_offer = current_offer

            # Check for response
            if random.random() > debtor.response_probability:
                # No response, add waiting time
                if round_num < len(strategy.concession_timing):
                    days_elapsed += strategy.concession_timing[round_num]
                else:
                    days_elapsed += 3
                continue

            debtor.has_responded = True

            # Check for dispute
            dispute_check = random.random()
            if dispute_check < debtor.dispute_probability:
                dispute_raised = True
                friction_score += 0.3

                # 40% of disputes block collection
                if random.random() < 0.4:
                    break

            # Calculate Nash equilibrium offer
            nash_offer = self.game_engine.calculate_nash_equilibrium(
                debtor, strategy, round_num
            )

            # Calculate risk-adjusted EV
            ev_metrics = self.game_engine.calculate_risk_adjusted_expected_value(
                debtor, strategy, current_offer, days_elapsed
            )

            # Determine acceptance using game theory
            p_accept = ev_metrics["p_accept"]

            # Adjust for urgency
            if round_num < len(strategy.urgency_levels):
                urgency = strategy.urgency_levels[round_num]
                urgency_boost = debtor.urgency_sensitivity * {
                    UrgencyLevel.LOW: 0.0,
                    UrgencyLevel.MEDIUM: 0.03,
                    UrgencyLevel.HIGH: 0.08,
                    UrgencyLevel.CRITICAL: 0.15
                }.get(urgency, 0)
                p_accept = min(0.95, p_accept + urgency_boost)

                # Track friction from high urgency
                if urgency in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL]:
                    friction_score += 0.1

            # Check if offer meets debtor's threshold
            if current_offer <= debtor.payment_threshold + 0.05:
                # Close to threshold, higher chance of acceptance
                p_accept = min(0.95, p_accept + 0.15)

            # Decision point
            if random.random() < p_accept:
                accepted = True
                debtor.accepted_offer = current_offer

                # Determine payment type
                if current_offer >= 0.95:
                    payment_type = "full"
                elif current_offer < 0.60:
                    payment_type = "settlement"
                else:
                    # Might do payment plan
                    plan_tier = PAYMENT_PLAN_TIERS.get(strategy.payment_plan_tier)
                    if plan_tier and float(debtor.balance) > float(plan_tier.min_monthly_payment) * 3:
                        if random.random() < 0.4:  # 40% prefer plans
                            payment_type = "plan"
                            plan_months = min(
                                plan_tier.max_term_months,
                                int(float(debtor.balance * Decimal(str(current_offer))) / float(plan_tier.min_monthly_payment))
                            )
                            debtor.on_payment_plan = True
                        else:
                            payment_type = "settlement"
                    else:
                        payment_type = "settlement"

                break

            # Check if escalation needed
            authority = SETTLEMENT_AUTHORITY.get(debtor.segment)
            if authority and days_elapsed > authority.escalation_threshold:
                escalation_needed = True
                friction_score += 0.15

            # Add inter-round delay
            if round_num < len(strategy.concession_timing):
                days_elapsed += strategy.concession_timing[round_num]
            else:
                days_elapsed += 3

            debtor.days_in_negotiation = days_elapsed

        # Simulate payment plan outcome if applicable
        if payment_type == "plan" and plan_months > 0:
            # Simulate plan completion
            payments_made = 0
            payments_missed = 0
            plan_tier = PAYMENT_PLAN_TIERS.get(strategy.payment_plan_tier, PAYMENT_PLAN_TIERS["moderate"])

            for month in range(plan_months):
                if random.random() < debtor.plan_adherence_rate:
                    payments_made += 1
                else:
                    payments_missed += 1
                    if payments_missed >= plan_tier.re_default_threshold:
                        re_defaulted = True
                        break

            debtor.plan_payments_made = payments_made
            debtor.plan_payments_missed = payments_missed

            # Adjust collection rate for partial plan completion
            if re_defaulted:
                final_offer *= (payments_made / plan_months)
                friction_score += 0.2

        # Calculate amount collected
        if accepted and not (re_defaulted and payment_type == "plan"):
            amount_collected = debtor.balance * Decimal(str(final_offer))
        elif payment_type == "plan" and re_defaulted:
            # Partial plan collection
            plan_tier = PAYMENT_PLAN_TIERS.get(strategy.payment_plan_tier, PAYMENT_PLAN_TIERS["moderate"])
            amount_collected = plan_tier.min_monthly_payment * debtor.plan_payments_made
        else:
            amount_collected = Decimal("0")

        # Determine final urgency
        final_urgency = strategy.urgency_levels[-1] if strategy.urgency_levels else UrgencyLevel.MEDIUM
        if debtor.negotiation_round < len(strategy.urgency_levels):
            final_urgency = strategy.urgency_levels[debtor.negotiation_round]

        return NegotiationOutcome(
            debtor_id=debtor.debtor_id,
            strategy_name=strategy.name,
            segment=debtor.segment,
            balance=debtor.balance,
            accepted=accepted,
            settlement_rate=final_offer if accepted else 0.0,
            amount_collected=amount_collected.quantize(Decimal("0.01")),
            negotiation_rounds=debtor.negotiation_round + 1,
            days_to_resolution=days_elapsed,
            final_urgency=final_urgency,
            payment_type=payment_type,
            plan_months=plan_months,
            re_defaulted=re_defaulted,
            dispute_raised=dispute_raised,
            escalation_needed=escalation_needed,
            customer_friction_score=min(1.0, friction_score)
        )

    async def run_simulation(
        self,
        num_simulations: int = 50000,
        strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run full negotiation simulation.

        Executes 50,000 negotiations across multiple strategies and debtor segments.
        """

        print("\n" + "=" * 80)
        print("  NEGOTIATION PARAMETER TUNER")
        print("  Game Theory-Driven Strategy Optimization")
        print("=" * 80)

        print(f"\n  Calibrated Parameters:")
        print(f"    Base Recovery Rate: {CALIBRATED_RECOVERY_RATE*100:.0f}%")
        print(f"    Average Balance:    ${CALIBRATED_AVG_BALANCE}")
        print(f"    Typical Settlement: {CALIBRATED_SETTLEMENT_RATE*100:.0f}%")

        # Select strategies to test
        if strategies is None:
            strategies = list(NEGOTIATION_STRATEGIES.keys())

        print(f"\n  Testing {len(strategies)} strategies across {num_simulations:,} simulations...")

        # Generate debtor portfolio
        debtors_per_strategy = num_simulations // len(strategies)
        total_debtors = debtors_per_strategy * len(strategies)

        print(f"  Generating {total_debtors:,} debtor profiles...")
        all_debtors = self.generate_debtor_portfolio(total_debtors)

        # Initialize metrics tracking
        for strategy_name in strategies:
            self.strategy_metrics[strategy_name] = {
                "total_balance": Decimal("0"),
                "total_collected": Decimal("0"),
                "acceptances": 0,
                "total_accounts": 0,
                "rounds_total": 0,
                "days_total": 0,
                "disputes": 0,
                "escalations": 0,
                "re_defaults": 0,
                "friction_total": 0.0,
                "by_segment": defaultdict(lambda: {
                    "count": 0, "collected": Decimal("0"), "balance": Decimal("0")
                }),
                "settlement_rates": []
            }

        for segment in DebtorSegment:
            self.segment_metrics[segment.value] = {
                "total_accounts": 0,
                "total_balance": Decimal("0"),
                "total_collected": Decimal("0"),
                "best_strategy": None,
                "best_recovery": 0.0,
                "by_strategy": {}
            }

        # Run simulations
        print("\n  Running simulations...\n")
        print("  " + "-" * 76)
        print(f"  {'Strategy':<25} {'Accounts':>10} {'Accept%':>10} {'Collect%':>10} {'Avg Days':>10} {'Friction':>10}")
        print("  " + "-" * 76)

        debtor_idx = 0
        for strategy_name in strategies:
            strategy = NEGOTIATION_STRATEGIES[strategy_name]
            strategy_debtors = all_debtors[debtor_idx:debtor_idx + debtors_per_strategy]
            debtor_idx += debtors_per_strategy

            # Process in batches for progress tracking
            batch_size = 1000
            for batch_start in range(0, len(strategy_debtors), batch_size):
                batch = strategy_debtors[batch_start:batch_start + batch_size]

                tasks = [
                    self.simulate_negotiation(debtor, strategy)
                    for debtor in batch
                ]

                outcomes = await asyncio.gather(*tasks)

                for outcome in outcomes:
                    self.outcomes.append(outcome)

                    # Update strategy metrics
                    sm = self.strategy_metrics[strategy_name]
                    sm["total_balance"] += outcome.balance
                    sm["total_collected"] += outcome.amount_collected
                    sm["total_accounts"] += 1
                    sm["rounds_total"] += outcome.negotiation_rounds
                    sm["days_total"] += outcome.days_to_resolution
                    sm["friction_total"] += outcome.customer_friction_score

                    if outcome.accepted:
                        sm["acceptances"] += 1
                        sm["settlement_rates"].append(outcome.settlement_rate)
                    if outcome.dispute_raised:
                        sm["disputes"] += 1
                    if outcome.escalation_needed:
                        sm["escalations"] += 1
                    if outcome.re_defaulted:
                        sm["re_defaults"] += 1

                    # Segment tracking
                    seg = outcome.segment.value
                    sm["by_segment"][seg]["count"] += 1
                    sm["by_segment"][seg]["collected"] += outcome.amount_collected
                    sm["by_segment"][seg]["balance"] += outcome.balance

                    # Update segment metrics
                    self.segment_metrics[seg]["total_accounts"] += 1
                    self.segment_metrics[seg]["total_balance"] += outcome.balance
                    self.segment_metrics[seg]["total_collected"] += outcome.amount_collected

            # Print progress
            sm = self.strategy_metrics[strategy_name]
            accept_rate = sm["acceptances"] / sm["total_accounts"] * 100 if sm["total_accounts"] > 0 else 0
            collect_rate = float(sm["total_collected"] / sm["total_balance"]) * 100 if sm["total_balance"] > 0 else 0
            avg_days = sm["days_total"] / sm["total_accounts"] if sm["total_accounts"] > 0 else 0
            avg_friction = sm["friction_total"] / sm["total_accounts"] if sm["total_accounts"] > 0 else 0

            print(f"  {strategy_name:<25} {sm['total_accounts']:>10,} {accept_rate:>9.1f}% {collect_rate:>9.1f}% {avg_days:>10.1f} {avg_friction:>10.2f}")

        print("  " + "-" * 76)

        # Calculate final results
        results = self._calculate_final_results()

        # Print detailed results
        self._print_results(results)

        return results

    def _calculate_final_results(self) -> Dict[str, Any]:
        """Calculate comprehensive results from simulation"""

        results = {
            "total_simulations": len(self.outcomes),
            "strategies": {},
            "segments": {},
            "optimal_by_segment": {},
            "settlement_curves": {},
            "expected_revenue_per_account": {}
        }

        # Strategy-level results
        for name, metrics in self.strategy_metrics.items():
            if metrics["total_accounts"] == 0:
                continue

            acceptance_rate = metrics["acceptances"] / metrics["total_accounts"]
            collection_rate = float(metrics["total_collected"] / metrics["total_balance"])
            avg_settlement = statistics.mean(metrics["settlement_rates"]) if metrics["settlement_rates"] else 0

            results["strategies"][name] = {
                "total_accounts": metrics["total_accounts"],
                "total_balance": float(metrics["total_balance"]),
                "total_collected": float(metrics["total_collected"]),
                "acceptance_rate": acceptance_rate,
                "collection_rate": collection_rate,
                "avg_settlement_rate": avg_settlement,
                "avg_rounds": metrics["rounds_total"] / metrics["total_accounts"],
                "avg_days_to_resolution": metrics["days_total"] / metrics["total_accounts"],
                "dispute_rate": metrics["disputes"] / metrics["total_accounts"],
                "escalation_rate": metrics["escalations"] / metrics["total_accounts"],
                "re_default_rate": metrics["re_defaults"] / max(1, metrics["acceptances"]),
                "avg_friction_score": metrics["friction_total"] / metrics["total_accounts"],
                "expected_revenue_per_account": float(metrics["total_collected"]) / metrics["total_accounts"]
            }

            # Settlement curve (offer level vs acceptance rate)
            strategy = NEGOTIATION_STRATEGIES.get(name)
            if strategy:
                curve = []
                for offer in strategy.counter_offer_levels:
                    # Calculate acceptance at this offer level
                    accepted_at_offer = sum(
                        1 for o in self.outcomes
                        if o.strategy_name == name and o.accepted and o.settlement_rate >= offer - 0.05
                    )
                    total_at_offer = sum(
                        1 for o in self.outcomes if o.strategy_name == name
                    )
                    rate = accepted_at_offer / total_at_offer if total_at_offer > 0 else 0
                    curve.append((offer, rate))
                results["settlement_curves"][name] = curve

        # Segment-level results and optimal strategy by segment
        for seg_name, seg_metrics in self.segment_metrics.items():
            if seg_metrics["total_accounts"] == 0:
                continue

            segment_recovery = float(seg_metrics["total_collected"] / seg_metrics["total_balance"])

            results["segments"][seg_name] = {
                "total_accounts": seg_metrics["total_accounts"],
                "total_balance": float(seg_metrics["total_balance"]),
                "total_collected": float(seg_metrics["total_collected"]),
                "overall_recovery_rate": segment_recovery,
                "avg_balance": float(seg_metrics["total_balance"]) / seg_metrics["total_accounts"]
            }

            # Find optimal strategy for this segment
            best_strategy = None
            best_recovery = 0.0

            for strategy_name, strategy_metrics in self.strategy_metrics.items():
                seg_data = strategy_metrics["by_segment"].get(seg_name, {})
                if seg_data.get("balance", 0) > 0:
                    recovery = float(seg_data["collected"] / seg_data["balance"])
                    if recovery > best_recovery:
                        best_recovery = recovery
                        best_strategy = strategy_name

            results["optimal_by_segment"][seg_name] = {
                "strategy": best_strategy,
                "recovery_rate": best_recovery,
                "improvement_vs_avg": best_recovery - segment_recovery if segment_recovery > 0 else 0
            }

        # Expected revenue per account by strategy
        for name, strat_data in results["strategies"].items():
            results["expected_revenue_per_account"][name] = strat_data["expected_revenue_per_account"]

        return results

    def _print_results(self, results: Dict[str, Any]):
        """Print comprehensive results"""

        print("\n" + "=" * 80)
        print("  SIMULATION RESULTS")
        print("=" * 80)

        # Overall statistics
        total_balance = sum(s["total_balance"] for s in results["strategies"].values())
        total_collected = sum(s["total_collected"] for s in results["strategies"].values())
        overall_recovery = total_collected / total_balance if total_balance > 0 else 0

        print(f"\n  OVERALL METRICS:")
        print(f"    Total Simulations:     {results['total_simulations']:,}")
        print(f"    Total Balance:         ${total_balance:,.2f}")
        print(f"    Total Collected:       ${total_collected:,.2f}")
        print(f"    Overall Recovery Rate: {overall_recovery*100:.1f}%")

        # Strategy comparison
        print(f"\n  STRATEGY COMPARISON:")
        print("  " + "-" * 76)
        print(f"  {'Strategy':<25} {'Accept%':>10} {'Collect%':>10} {'Settlement':>10} {'Days':>8} {'Friction':>10}")
        print("  " + "-" * 76)

        sorted_strategies = sorted(
            results["strategies"].items(),
            key=lambda x: x[1]["collection_rate"],
            reverse=True
        )

        for name, data in sorted_strategies:
            print(f"  {name:<25} {data['acceptance_rate']*100:>9.1f}% "
                  f"{data['collection_rate']*100:>9.1f}% "
                  f"{data['avg_settlement_rate']*100:>9.1f}% "
                  f"{data['avg_days_to_resolution']:>8.1f} "
                  f"{data['avg_friction_score']:>10.2f}")

        print("  " + "-" * 76)

        # Re-default and dispute rates
        print(f"\n  RISK METRICS BY STRATEGY:")
        print("  " + "-" * 66)
        print(f"  {'Strategy':<25} {'Dispute%':>12} {'Escalation%':>12} {'Re-Default%':>12}")
        print("  " + "-" * 66)

        for name, data in sorted_strategies:
            print(f"  {name:<25} {data['dispute_rate']*100:>11.1f}% "
                  f"{data['escalation_rate']*100:>11.1f}% "
                  f"{data['re_default_rate']*100:>11.1f}%")

        print("  " + "-" * 66)

        # Optimal strategy by segment
        print(f"\n  OPTIMAL STRATEGY BY DEBTOR SEGMENT:")
        print("  " + "-" * 72)
        print(f"  {'Segment':<25} {'Optimal Strategy':<25} {'Recovery%':>10} {'Lift':>10}")
        print("  " + "-" * 72)

        for seg_name, opt_data in results["optimal_by_segment"].items():
            improvement = opt_data["improvement_vs_avg"] * 100
            sign = "+" if improvement >= 0 else ""
            print(f"  {seg_name:<25} {opt_data['strategy']:<25} "
                  f"{opt_data['recovery_rate']*100:>9.1f}% {sign}{improvement:>9.1f}%")

        print("  " + "-" * 72)

        # Settlement offer curves
        print(f"\n  SETTLEMENT OFFER CURVES:")
        print("  (Offer % of balance -> Cumulative acceptance rate)")
        print("  " + "-" * 72)

        for strategy_name, curve in results["settlement_curves"].items():
            curve_str = " -> ".join([f"{offer*100:.0f}%:{rate*100:.1f}%" for offer, rate in curve[:4]])
            print(f"  {strategy_name:<25} {curve_str}")

        print("  " + "-" * 72)

        # Expected revenue per account
        print(f"\n  EXPECTED REVENUE PER ACCOUNT:")
        print("  " + "-" * 50)

        sorted_revenue = sorted(
            results["expected_revenue_per_account"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        for name, revenue in sorted_revenue:
            print(f"  {name:<30} ${revenue:>15.2f}")

        print("  " + "-" * 50)

        # Segment performance
        print(f"\n  SEGMENT PERFORMANCE:")
        print("  " + "-" * 66)
        print(f"  {'Segment':<25} {'Accounts':>10} {'Avg Balance':>12} {'Recovery%':>12}")
        print("  " + "-" * 66)

        for seg_name, seg_data in results["segments"].items():
            print(f"  {seg_name:<25} {seg_data['total_accounts']:>10,} "
                  f"${seg_data['avg_balance']:>11.2f} "
                  f"{seg_data['overall_recovery_rate']*100:>11.1f}%")

        print("  " + "-" * 66)

        # Best overall strategy
        best_strategy = max(results["strategies"].items(), key=lambda x: x[1]["collection_rate"])

        print(f"\n  RECOMMENDATION:")
        print(f"    Best Overall Strategy: {best_strategy[0]}")
        print(f"    Expected Collection Rate: {best_strategy[1]['collection_rate']*100:.1f}%")
        print(f"    Expected Revenue/Account: ${best_strategy[1]['expected_revenue_per_account']:.2f}")
        print(f"    Average Days to Resolve:  {best_strategy[1]['avg_days_to_resolution']:.1f}")

        print("\n" + "=" * 80)


# =============================================================================
# ADVANCED ANALYTICS
# =============================================================================

class NegotiationAnalytics:
    """
    Advanced analytics for negotiation simulation results.
    """

    def __init__(self, outcomes: List[NegotiationOutcome]):
        self.outcomes = outcomes

    def calculate_strategy_efficiency_frontier(self) -> List[Tuple[str, float, float]]:
        """
        Calculate efficiency frontier: recovery rate vs friction tradeoff.

        Returns strategies on the efficient frontier (Pareto optimal).
        """
        strategy_points = defaultdict(lambda: {"recovery": [], "friction": []})

        for outcome in self.outcomes:
            if outcome.accepted:
                recovery = float(outcome.amount_collected / outcome.balance)
            else:
                recovery = 0
            strategy_points[outcome.strategy_name]["recovery"].append(recovery)
            strategy_points[outcome.strategy_name]["friction"].append(outcome.customer_friction_score)

        # Calculate averages
        points = []
        for name, data in strategy_points.items():
            avg_recovery = statistics.mean(data["recovery"]) if data["recovery"] else 0
            avg_friction = statistics.mean(data["friction"]) if data["friction"] else 0
            points.append((name, avg_recovery, avg_friction))

        # Find Pareto frontier
        frontier = []
        for point in points:
            is_dominated = False
            for other in points:
                # Check if other dominates point (higher recovery AND lower friction)
                if other[1] > point[1] and other[2] < point[2]:
                    is_dominated = True
                    break
            if not is_dominated:
                frontier.append(point)

        return sorted(frontier, key=lambda x: x[1], reverse=True)

    def calculate_segment_strategy_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Create matrix of expected recovery by segment and strategy.
        """
        matrix = defaultdict(lambda: defaultdict(list))

        for outcome in self.outcomes:
            if outcome.accepted:
                recovery = float(outcome.amount_collected / outcome.balance)
            else:
                recovery = 0
            matrix[outcome.segment.value][outcome.strategy_name].append(recovery)

        # Calculate averages
        result = {}
        for segment, strategies in matrix.items():
            result[segment] = {}
            for strategy, recoveries in strategies.items():
                result[segment][strategy] = statistics.mean(recoveries) if recoveries else 0

        return result

    def calculate_optimal_concession_schedule(
        self,
        segment: DebtorSegment
    ) -> List[Tuple[int, float]]:
        """
        Calculate optimal concession schedule for a segment.

        Returns: List of (day, optimal_offer_pct) tuples
        """
        segment_outcomes = [o for o in self.outcomes if o.segment == segment and o.accepted]

        if not segment_outcomes:
            return [(0, 1.0), (7, 0.85), (14, 0.70), (21, 0.60), (30, 0.50)]

        # Group by resolution day
        day_settlements = defaultdict(list)
        for outcome in segment_outcomes:
            day_settlements[outcome.days_to_resolution].append(outcome.settlement_rate)

        # Find optimal offer at each time point
        schedule = []
        for day in sorted(day_settlements.keys()):
            avg_settlement = statistics.mean(day_settlements[day])
            schedule.append((day, avg_settlement))

        # Smooth the schedule
        if len(schedule) > 1:
            smoothed = [(schedule[0][0], schedule[0][1])]
            for i in range(1, len(schedule)):
                smoothed_rate = 0.7 * schedule[i][1] + 0.3 * smoothed[-1][1]
                smoothed.append((schedule[i][0], smoothed_rate))
            return smoothed[:10]  # Return top 10 points

        return schedule


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_negotiation_tuner():
    """Run the full negotiation parameter tuning simulation"""

    simulator = NegotiationSimulator()

    # Run 50,000 simulations
    results = await simulator.run_simulation(num_simulations=50000)

    # Run additional analytics
    analytics = NegotiationAnalytics(simulator.outcomes)

    print("\n" + "=" * 80)
    print("  ADVANCED ANALYTICS")
    print("=" * 80)

    # Efficiency frontier
    print(f"\n  EFFICIENCY FRONTIER (Pareto Optimal Strategies):")
    print("  " + "-" * 56)
    print(f"  {'Strategy':<25} {'Recovery%':>12} {'Friction':>12}")
    print("  " + "-" * 56)

    frontier = analytics.calculate_strategy_efficiency_frontier()
    for name, recovery, friction in frontier:
        print(f"  {name:<25} {recovery*100:>11.1f}% {friction:>12.3f}")

    print("  " + "-" * 56)

    # Segment-strategy matrix
    print(f"\n  SEGMENT-STRATEGY RECOVERY MATRIX:")
    matrix = analytics.calculate_segment_strategy_matrix()

    strategies = list(NEGOTIATION_STRATEGIES.keys())
    header = "  " + f"{'Segment':<20}" + "".join([f"{s[:12]:>14}" for s in strategies[:4]])
    print(header)
    print("  " + "-" * (20 + 14 * min(4, len(strategies))))

    for segment, strat_data in matrix.items():
        row = f"  {segment:<20}"
        for strat in strategies[:4]:
            recovery = strat_data.get(strat, 0) * 100
            row += f"{recovery:>13.1f}%"
        print(row)

    print("  " + "-" * (20 + 14 * min(4, len(strategies))))

    # Optimal concession schedules
    print(f"\n  OPTIMAL CONCESSION SCHEDULES BY SEGMENT:")

    for segment in [DebtorSegment.WILLING_UNABLE, DebtorSegment.UNWILLING_ABLE]:
        schedule = analytics.calculate_optimal_concession_schedule(segment)
        print(f"\n  {segment.value}:")
        schedule_str = " -> ".join([f"D{d}:{r*100:.0f}%" for d, r in schedule[:5]])
        print(f"    {schedule_str}")

    print("\n" + "=" * 80)

    return results


# =============================================================================
# MODULE INIT
# =============================================================================

def create_init_file():
    """Create __init__.py for the optimization module"""
    init_content = '''"""
Optimization module for Collection Intelligence platform.

Contains parameter tuning engines for:
- Negotiation strategies
- Settlement offers
- Payment plans
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

__all__ = [
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
]
'''
    return init_content


if __name__ == "__main__":
    asyncio.run(run_negotiation_tuner())
