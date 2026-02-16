"""
Settlement Optimization Engine

Advanced engine for optimizing debt settlement offers using:
- Dynamic pricing with willingness-to-pay estimation
- Game theory-based negotiation strategies
- Portfolio-level optimization with bundling
- Machine learning for historical pattern learning
- Contextual bandits for offer selection
- Reinforcement learning for negotiation sequences

Key Features:
- Nash equilibrium calculation for settlement negotiations
- Bayesian updating on consumer type during negotiation
- Signaling effects and commitment device design
- Tax and regulatory constraint enforcement
- Cross-account settlement bundling
"""

import asyncio
import random
import math
import statistics
import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from collections import defaultdict
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Optimized industry baselines for maximum recovery
BASELINE_RECOVERY_RATE = 0.54
BASELINE_SETTLEMENT_RATE = 0.52
BASELINE_AVG_BALANCE = Decimal("375")

# Tax thresholds
IRS_1099C_THRESHOLD = Decimal("600")  # 1099-C required for forgiven debt >= $600
IRS_FORGIVENESS_TAXABLE = True

# Regulatory boundaries
MIN_SETTLEMENT_FLOOR = 0.10  # Absolute minimum 10%
MAX_SETTLEMENT_CAP = 1.00    # Cannot exceed balance
BANKRUPTCY_THRESHOLD = 0.20  # Below this, consumer may prefer bankruptcy

# Creditor-specific minimums (typical)
CREDITOR_MIN_SETTLEMENTS = {
    "medical": 0.15,
    "credit_card": 0.25,
    "personal_loan": 0.30,
    "auto_deficiency": 0.35,
    "student_private": 0.40,
    "payday": 0.20,
    "bnpl": 0.20,
    "telecom": 0.25,
    "utility": 0.35,
}


# =============================================================================
# ENUMERATIONS
# =============================================================================

class ConsumerType(Enum):
    """Consumer archetype for behavioral modeling"""
    STRATEGIC = "strategic"           # Knows system, maximizes discount
    DESPERATE = "desperate"           # Financially distressed, will take any reasonable deal
    ETHICAL = "ethical"               # Wants to pay, needs help
    AVOIDANT = "avoidant"             # Ignores problem, needs urgency
    LITIGIOUS = "litigious"           # Dispute-prone, legalistic
    UNINFORMED = "uninformed"         # Doesn't understand options


class NegotiationPhase(Enum):
    """Phase in negotiation lifecycle"""
    OPENING = "opening"
    EXPLORATION = "exploration"
    BARGAINING = "bargaining"
    CLOSING = "closing"
    FINAL = "final"


class OfferOutcome(Enum):
    """Outcome of a settlement offer"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTER = "counter"
    NO_RESPONSE = "no_response"
    DISPUTE = "dispute"
    HARDSHIP = "hardship_declared"


class ConstraintType(Enum):
    """Types of settlement constraints"""
    CREDITOR_MIN = "creditor_minimum"
    REGULATORY = "regulatory"
    TAX = "tax_threshold"
    ACCOUNTING = "accounting"
    LEGAL = "legal"
    BUSINESS = "business_rule"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConsumerProfile:
    """Comprehensive consumer profile for settlement optimization"""
    consumer_id: str

    # Financial state
    balance: Decimal
    original_balance: Decimal
    days_past_due: int
    account_age_days: int

    # Economic indicators
    estimated_income: Optional[Decimal] = None
    disposable_income_ratio: float = 0.20
    debt_to_income: float = 0.40
    other_debts_count: int = 0

    # Behavioral signals
    prior_payment_attempts: int = 0
    prior_settlement_attempts: int = 0
    response_rate: float = 0.30
    engagement_score: float = 0.50

    # Contact history
    contact_attempts: int = 0
    conversations: int = 0
    last_contact_days: int = 0

    # Predicted type (updated via Bayesian inference)
    predicted_type: ConsumerType = ConsumerType.UNINFORMED
    type_probabilities: Dict[ConsumerType, float] = field(default_factory=dict)

    # State tracking
    current_offer: Optional[float] = None
    negotiation_round: int = 0
    cumulative_signaling_cost: float = 0.0


@dataclass
class SettlementOffer:
    """Settlement offer structure"""
    offer_id: str
    consumer_id: str

    # Amounts
    balance: Decimal
    settlement_amount: Decimal
    settlement_rate: float

    # Terms
    payment_type: str  # "lump_sum", "payment_plan"
    plan_months: int = 0
    plan_down_payment: Decimal = Decimal("0")
    plan_monthly_amount: Decimal = Decimal("0")

    # Timing
    offer_timestamp: datetime = field(default_factory=datetime.utcnow)
    expiration_days: int = 14

    # Metadata
    offer_round: int = 1
    is_opening: bool = True
    is_final: bool = False

    # Game theory signals
    signaling_strength: float = 0.5  # How much this signals our position
    commitment_level: float = 0.5    # How binding this offer appears


@dataclass
class NegotiationState:
    """State of ongoing negotiation"""
    consumer_id: str

    # History
    offers_made: List[SettlementOffer] = field(default_factory=list)
    counter_offers_received: List[Decimal] = field(default_factory=list)

    # Current state
    current_phase: NegotiationPhase = NegotiationPhase.OPENING
    rounds_completed: int = 0
    days_elapsed: int = 0

    # Bayesian beliefs
    type_beliefs: Dict[ConsumerType, float] = field(default_factory=dict)
    willingness_to_pay_estimate: float = 0.50

    # Game theory tracking
    revealed_reservation_price: Optional[float] = None
    estimated_batna: float = 0.0  # Best Alternative To Negotiated Agreement
    commitment_accumulated: float = 0.0

    # Outcome
    resolved: bool = False
    outcome: Optional[OfferOutcome] = None
    final_settlement_rate: Optional[float] = None


@dataclass
class SettlementConstraint:
    """Constraint on settlement offers"""
    constraint_type: ConstraintType
    name: str
    min_rate: Optional[float] = None
    max_rate: Optional[float] = None
    description: str = ""
    is_hard: bool = True  # Hard = must enforce, Soft = prefer to enforce
    penalty: float = 0.0  # Penalty for violating soft constraint


@dataclass
class PortfolioBundle:
    """Bundle of accounts for cross-account optimization"""
    bundle_id: str
    consumer_id: str
    accounts: List[ConsumerProfile]
    total_balance: Decimal
    recommended_bundle_rate: float = 0.0
    synergy_score: float = 0.0  # Benefit from bundling


@dataclass
class SettlementSimulationResult:
    """Result of settlement simulation"""
    consumer_id: str
    strategy_name: str

    # Outcome
    settled: bool
    settlement_rate: float
    amount_collected: Decimal

    # Process metrics
    rounds_to_settlement: int
    days_to_settlement: int
    offers_made: int

    # Economics
    expected_value: float
    collection_cost: Decimal
    net_recovery: Decimal

    # Constraints
    constraints_violated: List[str] = field(default_factory=list)
    tax_implications: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# DYNAMIC PRICING ENGINE
# =============================================================================

class WillingnessToPayEstimator:
    """
    Estimates consumer willingness-to-pay using economic modeling.

    Factors:
    - Balance vs estimated income
    - Days past due decay curve
    - Account age discounting
    - Competitive positioning (bankruptcy threshold)
    """

    def __init__(self):
        # Calibrated parameters
        self.dpd_decay_rate = 0.003  # 0.3% per day
        self.age_discount_rate = 0.001  # 0.1% per day
        self.income_sensitivity = 0.25

    def estimate_wtp(self, consumer: ConsumerProfile) -> Tuple[float, Dict[str, float]]:
        """
        Estimate willingness-to-pay as settlement rate.

        Returns (wtp_rate, component_breakdown)
        """
        components = {}

        # Base WTP from debt-to-income
        base_wtp = self._income_based_wtp(consumer)
        components["income_based"] = base_wtp

        # DPD adjustment (higher DPD = lower WTP but more motivated)
        dpd_factor = self._dpd_adjustment(consumer.days_past_due)
        components["dpd_factor"] = dpd_factor

        # Account age discount (older = lower expectations)
        age_factor = self._age_adjustment(consumer.account_age_days)
        components["age_factor"] = age_factor

        # Engagement adjustment (responsive consumers may pay more)
        engagement_factor = self._engagement_adjustment(consumer)
        components["engagement_factor"] = engagement_factor

        # Bankruptcy threshold floor
        bankruptcy_floor = self._bankruptcy_positioning(consumer)
        components["bankruptcy_floor"] = bankruptcy_floor

        # Calculate final WTP
        raw_wtp = base_wtp * dpd_factor * age_factor * engagement_factor

        # Apply bankruptcy floor (consumer prefers settlement over bankruptcy)
        final_wtp = max(raw_wtp, bankruptcy_floor)
        components["final_wtp"] = final_wtp

        return final_wtp, components

    def _income_based_wtp(self, consumer: ConsumerProfile) -> float:
        """Calculate WTP from income-balance relationship"""

        if consumer.estimated_income and consumer.estimated_income > 0:
            balance_to_income = float(consumer.balance / consumer.estimated_income)

            # High balance relative to income = lower WTP
            if balance_to_income < 0.05:
                return 0.85  # Easy to pay, expect high settlement
            elif balance_to_income < 0.15:
                return 0.70
            elif balance_to_income < 0.30:
                return 0.55
            elif balance_to_income < 0.50:
                return 0.40
            else:
                return 0.30  # Heavy burden, expect low settlement

        # Default based on balance size
        balance = float(consumer.balance)
        if balance < 100:
            return 0.70  # Small, easier to pay
        elif balance < 300:
            return 0.55
        elif balance < 500:
            return 0.45
        elif balance < 1000:
            return 0.40
        else:
            return 0.35

    def _dpd_adjustment(self, dpd: int) -> float:
        """Adjust WTP based on days past due"""

        # Fresh debt: expect higher settlement
        # Aged debt: consumer has proven they can avoid, lower expectations

        if dpd <= 30:
            return 1.10  # Fresh, may pay full
        elif dpd <= 90:
            return 1.00  # Standard
        elif dpd <= 180:
            return 0.90
        elif dpd <= 365:
            return 0.80
        else:
            return 0.70  # Very aged, significant discount expected

    def _age_adjustment(self, account_age_days: int) -> float:
        """Adjust WTP based on total account age"""

        # Older accounts have more depreciation in expected value
        age_years = account_age_days / 365

        discount = 1.0 - (age_years * 0.05)  # 5% per year
        return max(0.60, discount)

    def _engagement_adjustment(self, consumer: ConsumerProfile) -> float:
        """Adjust WTP based on consumer engagement"""

        if consumer.engagement_score > 0.7:
            return 1.15  # Engaged = may pay more
        elif consumer.engagement_score > 0.4:
            return 1.00
        else:
            return 0.85  # Disengaged = lower expectations

    def _bankruptcy_positioning(self, consumer: ConsumerProfile) -> float:
        """
        Calculate floor based on bankruptcy alternative.

        Consumer should prefer settlement if:
        settlement_cost < bankruptcy_cost + stigma_cost
        """

        # Bankruptcy typically results in 0-10% recovery
        # Plus consumer incurs ~$1500 filing cost and 7-10 year credit hit

        estimated_bankruptcy_recovery = 0.05

        # Our offer should be competitive with bankruptcy
        # Offer slightly above what they'd lose in bankruptcy
        bankruptcy_floor = BANKRUPTCY_THRESHOLD

        # Adjust for balance (small balances rarely go to bankruptcy)
        if float(consumer.balance) < 500:
            bankruptcy_floor = 0.15  # Low balances rarely file
        elif float(consumer.balance) < 2000:
            bankruptcy_floor = 0.18
        else:
            bankruptcy_floor = 0.20

        return bankruptcy_floor


class BalanceSettlementCurveGenerator:
    """
    Generates settlement curves based on balance.

    Curve shape: higher balances typically settle at lower percentages
    due to absolute dollar amounts being more significant.
    """

    def __init__(self):
        # Optimized curve parameters for maximum acceptance
        self.curve_params = {
            "micro": {  # $0-100
                "optimal_rate": 0.70,
                "floor": 0.45,
                "elasticity": 0.35,
            },
            "small": {  # $100-300
                "optimal_rate": 0.60,
                "floor": 0.38,
                "elasticity": 0.42,
            },
            "medium": {  # $300-700
                "optimal_rate": 0.55,
                "floor": 0.32,
                "elasticity": 0.50,
            },
            "large": {  # $700-1500
                "optimal_rate": 0.50,
                "floor": 0.28,
                "elasticity": 0.58,
            },
            "major": {  # $1500+
                "optimal_rate": 0.45,
                "floor": 0.22,
                "elasticity": 0.65,
            },
        }

    def get_tier(self, balance: Decimal) -> str:
        """Determine balance tier"""

        bal = float(balance)
        if bal < 100:
            return "micro"
        elif bal < 300:
            return "small"
        elif bal < 700:
            return "medium"
        elif bal < 1500:
            return "large"
        else:
            return "major"

    def get_optimal_offer(
        self,
        balance: Decimal,
        dpd: int,
        urgency: float = 0.5
    ) -> Tuple[float, float, float]:
        """
        Get optimal opening offer, floor, and ceiling for balance.

        Returns (opening_offer_rate, floor_rate, ceiling_rate)
        """

        tier = self.get_tier(balance)
        params = self.curve_params[tier]

        optimal = params["optimal_rate"]
        floor = params["floor"]
        elasticity = params["elasticity"]

        # DPD adjustment
        if dpd > 365:
            optimal *= 0.85
            floor *= 0.85
        elif dpd > 180:
            optimal *= 0.92
            floor *= 0.90

        # Urgency adjustment (high urgency = start lower to close faster)
        if urgency > 0.7:
            optimal *= 0.95
        elif urgency < 0.3:
            optimal *= 1.05

        # Ceiling is always 100% (could offer full payment plan)
        ceiling = 1.00

        return (
            min(ceiling, max(floor, optimal)),
            floor,
            ceiling
        )

    def generate_offer_sequence(
        self,
        balance: Decimal,
        dpd: int,
        max_rounds: int = 6
    ) -> List[float]:
        """Generate sequence of offers for progressive negotiation"""

        opening, floor, _ = self.get_optimal_offer(balance, dpd)

        sequence = []

        # Start high, decrease gradually
        current = 1.00 if dpd < 90 else opening + 0.15
        step = (current - floor) / max_rounds

        for i in range(max_rounds):
            offer = max(floor, current - (step * i))
            sequence.append(round(offer, 2))

        return sequence


# =============================================================================
# GAME THEORY NEGOTIATION ENGINE
# =============================================================================

class NashEquilibriumCalculator:
    """
    Calculates Nash equilibrium for settlement negotiations.

    Two-player game:
    - Collector: maximize recovery amount
    - Consumer: minimize payment while avoiding consequences
    """

    def __init__(self):
        self.convergence_threshold = 0.001
        self.max_iterations = 100

    def calculate_equilibrium(
        self,
        consumer: ConsumerProfile,
        collector_floor: float,
        consumer_ceiling: float,
        consumer_type: ConsumerType
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate Nash equilibrium settlement rate.

        Returns (equilibrium_rate, analysis_details)
        """

        # Define payoff functions
        def collector_payoff(offer: float, accept_prob: float) -> float:
            """Collector payoff: expected recovery minus costs"""
            expected_recovery = offer * accept_prob * float(consumer.balance)
            cost = 0.50 * consumer.negotiation_round  # Cost per round
            return expected_recovery - cost

        def consumer_payoff(offer: float, accept: bool) -> float:
            """Consumer payoff: negative of amount paid, plus hassle costs"""
            if accept:
                return -offer * float(consumer.balance)
            else:
                # Continued negotiation has hassle cost
                hassle_cost = 10.0 * consumer.negotiation_round
                # Plus risk of worse outcome (interest, fees, legal action)
                risk_cost = 0.02 * float(consumer.balance) * consumer.negotiation_round
                return -hassle_cost - risk_cost

        # Calculate acceptance probability curve
        def acceptance_probability(offer: float) -> float:
            """Probability consumer accepts at this offer level"""

            # Base probability from distance to their threshold
            if offer <= consumer_ceiling:
                # Below their ceiling = high acceptance
                distance = consumer_ceiling - offer
                base_prob = 0.70 + distance * 0.50
            else:
                # Above their ceiling = low acceptance
                distance = offer - consumer_ceiling
                base_prob = max(0.05, 0.70 - distance * 2.0)

            # Adjust for consumer type
            type_adjustments = {
                ConsumerType.STRATEGIC: -0.15,  # Harder to close
                ConsumerType.DESPERATE: 0.20,   # Easier to close
                ConsumerType.ETHICAL: 0.10,
                ConsumerType.AVOIDANT: -0.10,
                ConsumerType.LITIGIOUS: -0.20,
                ConsumerType.UNINFORMED: 0.05,
            }

            adjustment = type_adjustments.get(consumer_type, 0)

            return max(0.01, min(0.99, base_prob + adjustment))

        # Find equilibrium through iterative best response
        collector_offer = (collector_floor + consumer_ceiling) / 2

        for iteration in range(self.max_iterations):
            old_offer = collector_offer

            # Collector's best response: maximize expected value
            best_offer = collector_floor
            best_ev = 0

            for offer in [
                x / 100.0 for x in range(
                    int(collector_floor * 100),
                    int(consumer_ceiling * 100) + 1,
                    2
                )
            ]:
                accept_prob = acceptance_probability(offer)
                ev = collector_payoff(offer, accept_prob)
                if ev > best_ev:
                    best_ev = ev
                    best_offer = offer

            collector_offer = best_offer

            # Check convergence
            if abs(collector_offer - old_offer) < self.convergence_threshold:
                break

        analysis = {
            "equilibrium_offer": collector_offer,
            "acceptance_probability": acceptance_probability(collector_offer),
            "collector_expected_value": collector_payoff(
                collector_offer,
                acceptance_probability(collector_offer)
            ),
            "iterations_to_converge": iteration + 1,
            "collector_floor": collector_floor,
            "consumer_ceiling": consumer_ceiling,
        }

        return collector_offer, analysis

    def find_zone_of_possible_agreement(
        self,
        collector_floor: float,
        consumer_ceiling: float
    ) -> Optional[Tuple[float, float]]:
        """
        Find ZOPA (Zone of Possible Agreement).

        Returns (lower_bound, upper_bound) or None if no overlap.
        """

        if consumer_ceiling >= collector_floor:
            return (collector_floor, consumer_ceiling)
        else:
            # No ZOPA - parties have no overlapping acceptable range
            return None


class BayesianTypeUpdater:
    """
    Updates beliefs about consumer type using Bayesian inference.

    Uses consumer behavior signals to update probability distribution
    over consumer types.
    """

    def __init__(self):
        # Optimized prior distribution for better targeting
        self.prior = {
            ConsumerType.STRATEGIC: 0.06,
            ConsumerType.DESPERATE: 0.28,
            ConsumerType.ETHICAL: 0.24,
            ConsumerType.AVOIDANT: 0.22,
            ConsumerType.LITIGIOUS: 0.05,
            ConsumerType.UNINFORMED: 0.15,
        }

        # Likelihood functions P(signal | type)
        self.signal_likelihoods = self._build_likelihood_functions()

    def _build_likelihood_functions(self) -> Dict[str, Dict[ConsumerType, float]]:
        """Build likelihood functions for each signal"""

        return {
            "quick_response": {
                ConsumerType.STRATEGIC: 0.70,
                ConsumerType.DESPERATE: 0.80,
                ConsumerType.ETHICAL: 0.75,
                ConsumerType.AVOIDANT: 0.15,
                ConsumerType.LITIGIOUS: 0.60,
                ConsumerType.UNINFORMED: 0.40,
            },
            "counter_offer": {
                ConsumerType.STRATEGIC: 0.90,
                ConsumerType.DESPERATE: 0.30,
                ConsumerType.ETHICAL: 0.50,
                ConsumerType.AVOIDANT: 0.20,
                ConsumerType.LITIGIOUS: 0.70,
                ConsumerType.UNINFORMED: 0.25,
            },
            "hardship_claim": {
                ConsumerType.STRATEGIC: 0.40,
                ConsumerType.DESPERATE: 0.85,
                ConsumerType.ETHICAL: 0.60,
                ConsumerType.AVOIDANT: 0.30,
                ConsumerType.LITIGIOUS: 0.50,
                ConsumerType.UNINFORMED: 0.45,
            },
            "dispute_filed": {
                ConsumerType.STRATEGIC: 0.50,
                ConsumerType.DESPERATE: 0.10,
                ConsumerType.ETHICAL: 0.10,
                ConsumerType.AVOIDANT: 0.25,
                ConsumerType.LITIGIOUS: 0.90,
                ConsumerType.UNINFORMED: 0.15,
            },
            "aggressive_counter": {
                ConsumerType.STRATEGIC: 0.85,
                ConsumerType.DESPERATE: 0.15,
                ConsumerType.ETHICAL: 0.20,
                ConsumerType.AVOIDANT: 0.10,
                ConsumerType.LITIGIOUS: 0.75,
                ConsumerType.UNINFORMED: 0.10,
            },
            "accepted_first_offer": {
                ConsumerType.STRATEGIC: 0.05,
                ConsumerType.DESPERATE: 0.60,
                ConsumerType.ETHICAL: 0.40,
                ConsumerType.AVOIDANT: 0.15,
                ConsumerType.LITIGIOUS: 0.10,
                ConsumerType.UNINFORMED: 0.35,
            },
            "payment_plan_request": {
                ConsumerType.STRATEGIC: 0.30,
                ConsumerType.DESPERATE: 0.75,
                ConsumerType.ETHICAL: 0.70,
                ConsumerType.AVOIDANT: 0.20,
                ConsumerType.LITIGIOUS: 0.25,
                ConsumerType.UNINFORMED: 0.50,
            },
            "no_response": {
                ConsumerType.STRATEGIC: 0.20,
                ConsumerType.DESPERATE: 0.25,
                ConsumerType.ETHICAL: 0.15,
                ConsumerType.AVOIDANT: 0.85,
                ConsumerType.LITIGIOUS: 0.30,
                ConsumerType.UNINFORMED: 0.50,
            },
        }

    def update_beliefs(
        self,
        current_beliefs: Dict[ConsumerType, float],
        observed_signal: str
    ) -> Dict[ConsumerType, float]:
        """
        Update beliefs using Bayes' rule.

        P(type | signal) = P(signal | type) * P(type) / P(signal)
        """

        if observed_signal not in self.signal_likelihoods:
            return current_beliefs

        likelihoods = self.signal_likelihoods[observed_signal]

        # Calculate P(signal) = sum over types of P(signal | type) * P(type)
        p_signal = sum(
            likelihoods.get(t, 0.5) * current_beliefs.get(t, self.prior[t])
            for t in ConsumerType
        )

        if p_signal == 0:
            return current_beliefs

        # Apply Bayes' rule
        updated = {}
        for consumer_type in ConsumerType:
            prior = current_beliefs.get(consumer_type, self.prior[consumer_type])
            likelihood = likelihoods.get(consumer_type, 0.5)
            posterior = (likelihood * prior) / p_signal
            updated[consumer_type] = posterior

        # Normalize (ensure sums to 1)
        total = sum(updated.values())
        if total > 0:
            updated = {k: v / total for k, v in updated.items()}

        return updated

    def get_most_likely_type(
        self,
        beliefs: Dict[ConsumerType, float]
    ) -> ConsumerType:
        """Get the most probable consumer type"""

        return max(beliefs.keys(), key=lambda t: beliefs.get(t, 0))

    def get_initial_beliefs(self, consumer: ConsumerProfile) -> Dict[ConsumerType, float]:
        """Get initial beliefs based on consumer profile"""

        beliefs = dict(self.prior)

        # Adjust based on observable features
        if consumer.prior_settlement_attempts > 0:
            # Previous negotiation experience suggests strategic
            beliefs[ConsumerType.STRATEGIC] *= 1.5

        if consumer.engagement_score < 0.3:
            # Low engagement suggests avoidant
            beliefs[ConsumerType.AVOIDANT] *= 1.5

        if consumer.debt_to_income > 0.5:
            # High DTI suggests desperate
            beliefs[ConsumerType.DESPERATE] *= 1.3

        # Normalize
        total = sum(beliefs.values())
        beliefs = {k: v / total for k, v in beliefs.items()}

        return beliefs


class SignalingDesigner:
    """
    Designs offer sequences to signal credible commitment.

    Uses signaling theory to:
    - Demonstrate resolve through costly actions
    - Build commitment through gradual concessions
    - Create urgency through expiration mechanisms
    """

    def __init__(self):
        self.signaling_costs = {
            "small_concession": 0.02,    # 2% cost to credibility
            "medium_concession": 0.05,   # 5% cost
            "large_concession": 0.10,    # 10% cost
            "deadline_extension": 0.08,  # Extending deadline signals weakness
            "final_offer": 0.15,         # Claiming "final" - costly if not true
        }

    def design_offer_sequence(
        self,
        opening_rate: float,
        floor_rate: float,
        consumer_type: ConsumerType,
        max_rounds: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Design signaling-aware offer sequence.

        Returns list of offers with timing and signaling metadata.
        """

        offers = []
        current_rate = opening_rate
        cumulative_commitment = 0.0

        # Concession pattern based on consumer type
        if consumer_type == ConsumerType.STRATEGIC:
            # Slow, small concessions - show resolve
            concession_pattern = [0.02, 0.03, 0.04, 0.04, 0.05, 0.05]
            urgency_pattern = [0.3, 0.4, 0.5, 0.6, 0.7, 0.9]
        elif consumer_type == ConsumerType.DESPERATE:
            # Faster concessions - close quickly
            concession_pattern = [0.05, 0.07, 0.08, 0.10, 0.10, 0.10]
            urgency_pattern = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        elif consumer_type == ConsumerType.ETHICAL:
            # Moderate concessions - fair dealing
            concession_pattern = [0.04, 0.05, 0.05, 0.06, 0.06, 0.07]
            urgency_pattern = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        else:
            # Default pattern
            concession_pattern = [0.03, 0.04, 0.05, 0.06, 0.07, 0.08]
            urgency_pattern = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        for round_num in range(min(max_rounds, len(concession_pattern))):
            concession = concession_pattern[round_num]
            urgency = urgency_pattern[round_num]

            # Calculate new offer
            new_rate = max(floor_rate, current_rate - concession)

            # Calculate signaling cost of this concession
            if concession < 0.03:
                signal_cost = self.signaling_costs["small_concession"]
            elif concession < 0.06:
                signal_cost = self.signaling_costs["medium_concession"]
            else:
                signal_cost = self.signaling_costs["large_concession"]

            cumulative_commitment += signal_cost

            # Determine if this should be marked as "final"
            is_final = (
                round_num >= max_rounds - 2 or
                new_rate <= floor_rate * 1.05
            )

            offers.append({
                "round": round_num + 1,
                "rate": new_rate,
                "concession_from_previous": current_rate - new_rate,
                "urgency_level": urgency,
                "is_final": is_final,
                "signaling_cost": signal_cost,
                "cumulative_commitment": cumulative_commitment,
                "expiration_days": max(3, 14 - (round_num * 2)),
                "commitment_device": self._get_commitment_device(round_num, is_final),
            })

            current_rate = new_rate

        return offers

    def _get_commitment_device(self, round_num: int, is_final: bool) -> str:
        """Get appropriate commitment device for this stage"""

        if is_final:
            return "final_offer_letter"
        elif round_num <= 1:
            return "standard_offer"
        elif round_num <= 3:
            return "limited_time_offer"
        else:
            return "escalation_warning"


# =============================================================================
# NEGOTIATION STRATEGY OPTIMIZER
# =============================================================================

class NegotiationStrategyOptimizer:
    """
    Optimizes negotiation strategy selection and execution.

    Combines:
    - Opening offer optimization
    - Counter-offer response modeling
    - Walk-away threshold calculation
    - Time pressure tactics (within ethical bounds)
    - Micro-payment alternatives
    """

    def __init__(self):
        self.wtp_estimator = WillingnessToPayEstimator()
        self.curve_generator = BalanceSettlementCurveGenerator()
        self.nash_calculator = NashEquilibriumCalculator()
        self.bayesian_updater = BayesianTypeUpdater()
        self.signaling_designer = SignalingDesigner()

    def optimize_opening_offer(
        self,
        consumer: ConsumerProfile,
        constraints: List[SettlementConstraint]
    ) -> SettlementOffer:
        """
        Calculate optimal opening offer.

        Balances:
        - Maximizing expected recovery
        - Minimizing negotiation length
        - Signaling appropriate strength
        """

        # Estimate willingness to pay
        wtp, wtp_components = self.wtp_estimator.estimate_wtp(consumer)

        # Get balance-based curves
        opening, floor, ceiling = self.curve_generator.get_optimal_offer(
            consumer.balance,
            consumer.days_past_due,
            urgency=0.5
        )

        # Apply constraints
        constrained_floor = floor
        for constraint in constraints:
            if constraint.min_rate and constraint.is_hard:
                constrained_floor = max(constrained_floor, constraint.min_rate)

        # Initialize beliefs about consumer type
        beliefs = self.bayesian_updater.get_initial_beliefs(consumer)
        consumer_type = self.bayesian_updater.get_most_likely_type(beliefs)

        # Calculate Nash equilibrium
        equilibrium, analysis = self.nash_calculator.calculate_equilibrium(
            consumer,
            constrained_floor,
            wtp,
            consumer_type
        )

        # Opening offer strategy
        # Start above equilibrium to leave room for negotiation
        opening_rate = min(ceiling, equilibrium * 1.20)

        # But not too aggressive for certain types
        if consumer_type == ConsumerType.DESPERATE:
            opening_rate = min(opening_rate, equilibrium * 1.10)
        elif consumer_type == ConsumerType.STRATEGIC:
            opening_rate = min(ceiling, opening_rate * 1.05)

        settlement_amount = consumer.balance * Decimal(str(opening_rate))

        return SettlementOffer(
            offer_id=f"OFR-{consumer.consumer_id}-001",
            consumer_id=consumer.consumer_id,
            balance=consumer.balance,
            settlement_amount=settlement_amount.quantize(Decimal("0.01")),
            settlement_rate=opening_rate,
            payment_type="lump_sum",
            offer_round=1,
            is_opening=True,
            signaling_strength=0.8,  # Opening offers signal strength
            commitment_level=0.3,     # Low commitment - room to negotiate
        )

    def generate_counter_response(
        self,
        state: NegotiationState,
        consumer: ConsumerProfile,
        consumer_counter: Decimal,
        constraints: List[SettlementConstraint]
    ) -> Tuple[Optional[SettlementOffer], str]:
        """
        Generate response to consumer's counter-offer.

        Returns (offer or None if walk away, strategy_reason)
        """

        # Update beliefs based on counter-offer signal
        counter_rate = float(consumer_counter / consumer.balance)

        if counter_rate < 0.25:
            signal = "aggressive_counter"
        elif counter_rate < 0.40:
            signal = "counter_offer"
        else:
            signal = "quick_response"

        updated_beliefs = self.bayesian_updater.update_beliefs(
            state.type_beliefs,
            signal
        )
        state.type_beliefs = updated_beliefs
        consumer_type = self.bayesian_updater.get_most_likely_type(updated_beliefs)

        # Get our floor
        floor = MIN_SETTLEMENT_FLOOR
        for constraint in constraints:
            if constraint.min_rate and constraint.is_hard:
                floor = max(floor, constraint.min_rate)

        # Calculate walk-away threshold
        walk_away = self._calculate_walk_away(consumer, floor, state)

        if counter_rate >= walk_away:
            # Consumer's offer is acceptable
            return self._create_acceptance_offer(consumer, consumer_counter), "counter_acceptable"

        # Calculate our response
        last_offer = state.offers_made[-1] if state.offers_made else None
        last_rate = last_offer.settlement_rate if last_offer else 1.0

        # How much to concede
        gap = last_rate - counter_rate

        if consumer_type == ConsumerType.STRATEGIC:
            # Small concessions for strategic types
            concession = gap * 0.25
        elif consumer_type == ConsumerType.DESPERATE:
            # Larger concessions to close quickly
            concession = gap * 0.45
        else:
            concession = gap * 0.35

        new_rate = max(walk_away, last_rate - concession)

        # Check if we've hit the floor
        if new_rate <= floor * 1.02:
            # Near floor - make final offer
            new_rate = floor
            is_final = True
        else:
            is_final = state.rounds_completed >= 4

        settlement_amount = consumer.balance * Decimal(str(new_rate))

        offer = SettlementOffer(
            offer_id=f"OFR-{consumer.consumer_id}-{state.rounds_completed + 1:03d}",
            consumer_id=consumer.consumer_id,
            balance=consumer.balance,
            settlement_amount=settlement_amount.quantize(Decimal("0.01")),
            settlement_rate=new_rate,
            payment_type="lump_sum",
            offer_round=state.rounds_completed + 1,
            is_opening=False,
            is_final=is_final,
            signaling_strength=0.7 if is_final else 0.5,
            commitment_level=0.8 if is_final else 0.5,
        )

        return offer, "counter_response"

    def _calculate_walk_away(
        self,
        consumer: ConsumerProfile,
        floor: float,
        state: NegotiationState
    ) -> float:
        """Calculate point at which we walk away from negotiation"""

        # Base walk-away is the floor
        walk_away = floor

        # Adjust for negotiation fatigue
        round_adjustment = 0.02 * state.rounds_completed
        walk_away = max(floor, walk_away - round_adjustment)

        # Adjust for account economics
        balance = float(consumer.balance)
        if balance < 100:
            # Small balance - lower walk-away acceptable
            walk_away *= 0.90

        return walk_away

    def _create_acceptance_offer(
        self,
        consumer: ConsumerProfile,
        amount: Decimal
    ) -> SettlementOffer:
        """Create offer accepting consumer's counter"""

        rate = float(amount / consumer.balance)

        return SettlementOffer(
            offer_id=f"OFR-{consumer.consumer_id}-ACC",
            consumer_id=consumer.consumer_id,
            balance=consumer.balance,
            settlement_amount=amount.quantize(Decimal("0.01")),
            settlement_rate=rate,
            payment_type="lump_sum",
            is_final=True,
            signaling_strength=1.0,
            commitment_level=1.0,
        )

    def generate_micro_payment_alternative(
        self,
        consumer: ConsumerProfile,
        target_rate: float,
        constraints: List[SettlementConstraint]
    ) -> SettlementOffer:
        """
        Generate micro-payment plan alternative.

        For consumers who can't pay lump sum but might
        make small recurring payments.
        """

        total_amount = consumer.balance * Decimal(str(target_rate))

        # Calculate affordable monthly based on balance
        balance = float(consumer.balance)
        if balance < 100:
            monthly = max(Decimal("10"), total_amount / 6)
            months = min(6, int(total_amount / monthly))
        elif balance < 300:
            monthly = max(Decimal("15"), total_amount / 9)
            months = min(9, int(total_amount / monthly))
        elif balance < 500:
            monthly = max(Decimal("25"), total_amount / 12)
            months = min(12, int(total_amount / monthly))
        else:
            monthly = max(Decimal("35"), total_amount / 18)
            months = min(18, int(total_amount / monthly))

        # Small down payment (10-15%)
        down_payment = (total_amount * Decimal("0.12")).quantize(Decimal("0.01"))
        remaining = total_amount - down_payment
        monthly = (remaining / months).quantize(Decimal("0.01"))

        return SettlementOffer(
            offer_id=f"OFR-{consumer.consumer_id}-PLAN",
            consumer_id=consumer.consumer_id,
            balance=consumer.balance,
            settlement_amount=total_amount.quantize(Decimal("0.01")),
            settlement_rate=target_rate,
            payment_type="payment_plan",
            plan_months=months,
            plan_down_payment=down_payment,
            plan_monthly_amount=monthly,
            signaling_strength=0.6,
            commitment_level=0.7,
        )


# =============================================================================
# PORTFOLIO OPTIMIZATION ENGINE
# =============================================================================

class PortfolioSettlementOptimizer:
    """
    Optimizes settlement across entire portfolio.

    Handles:
    - Cross-account bundling
    - Recovery rate vs speed tradeoffs
    - Cash flow timing optimization
    - Creditor preference alignment
    """

    def __init__(self):
        self.bundle_min_size = 2
        self.bundle_max_size = 5

    def create_account_bundles(
        self,
        accounts: List[ConsumerProfile]
    ) -> List[PortfolioBundle]:
        """
        Create bundles of accounts for combined settlement offers.

        Groups accounts by:
        - Same consumer (multiple debts)
        - Similar characteristics for batch processing
        """

        # Group by consumer ID
        consumer_accounts: Dict[str, List[ConsumerProfile]] = defaultdict(list)
        for account in accounts:
            consumer_accounts[account.consumer_id].append(account)

        bundles = []

        for consumer_id, accts in consumer_accounts.items():
            if len(accts) >= self.bundle_min_size:
                total_balance = sum(a.balance for a in accts)

                # Calculate synergy score (bundling benefit)
                synergy = self._calculate_bundle_synergy(accts)

                # Calculate recommended bundle rate
                recommended_rate = self._calculate_bundle_rate(accts)

                bundle = PortfolioBundle(
                    bundle_id=f"BND-{consumer_id}",
                    consumer_id=consumer_id,
                    accounts=accts,
                    total_balance=total_balance,
                    recommended_bundle_rate=recommended_rate,
                    synergy_score=synergy,
                )
                bundles.append(bundle)

        return bundles

    def _calculate_bundle_synergy(
        self,
        accounts: List[ConsumerProfile]
    ) -> float:
        """Calculate benefit of bundling these accounts"""

        if len(accounts) < 2:
            return 0.0

        # Synergy factors:
        # 1. Single contact point (reduced cost)
        contact_synergy = 0.10 * min(len(accounts), 5)

        # 2. Combined negotiation (leverage)
        total_balance = sum(float(a.balance) for a in accounts)
        leverage_synergy = 0.05 if total_balance > 500 else 0.02

        # 3. Simplified payment (one transaction)
        payment_synergy = 0.03

        return contact_synergy + leverage_synergy + payment_synergy

    def _calculate_bundle_rate(
        self,
        accounts: List[ConsumerProfile]
    ) -> float:
        """Calculate recommended settlement rate for bundle"""

        total_balance = sum(float(a.balance) for a in accounts)

        # Weight individual rates by balance
        weighted_rate = 0.0
        for account in accounts:
            wtp_estimator = WillingnessToPayEstimator()
            wtp, _ = wtp_estimator.estimate_wtp(account)
            weight = float(account.balance) / total_balance
            weighted_rate += wtp * weight

        # Apply bundle discount (consumer gets deal for settling multiple)
        bundle_discount = 0.05 * min(len(accounts) - 1, 3)

        return max(0.25, weighted_rate - bundle_discount)

    def optimize_cash_flow_timing(
        self,
        settlements: List[SettlementOffer],
        target_monthly: Decimal,
        horizon_months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Optimize settlement timing for cash flow targets.

        Returns schedule of when to push for closure.
        """

        monthly_schedule = []
        remaining = list(settlements)

        for month in range(horizon_months):
            month_settlements = []
            month_total = Decimal("0")

            # Sort by expected close probability
            remaining.sort(
                key=lambda s: s.settlement_rate * (1 - s.offer_round * 0.1),
                reverse=True
            )

            for settlement in remaining[:]:
                if month_total >= target_monthly:
                    break

                month_settlements.append(settlement)
                month_total += settlement.settlement_amount
                remaining.remove(settlement)

            monthly_schedule.append({
                "month": month + 1,
                "settlements": month_settlements,
                "expected_recovery": month_total,
                "accounts_remaining": len(remaining),
            })

        return monthly_schedule

    def calculate_recovery_speed_tradeoff(
        self,
        account: ConsumerProfile,
        constraints: List[SettlementConstraint]
    ) -> Dict[str, Tuple[float, int]]:
        """
        Calculate tradeoff between recovery rate and speed.

        Returns dict of strategy -> (expected_rate, expected_days)
        """

        wtp_estimator = WillingnessToPayEstimator()
        wtp, _ = wtp_estimator.estimate_wtp(account)

        floor = MIN_SETTLEMENT_FLOOR
        for constraint in constraints:
            if constraint.min_rate and constraint.is_hard:
                floor = max(floor, constraint.min_rate)

        strategies = {
            "aggressive_fast": (
                max(floor, wtp - 0.15),  # Lower rate
                14  # Faster close
            ),
            "moderate": (
                max(floor, wtp - 0.05),
                30
            ),
            "patient": (
                max(floor, wtp + 0.05),
                60
            ),
            "maximizing": (
                max(floor, wtp + 0.15),
                90
            ),
        }

        return strategies


# =============================================================================
# MACHINE LEARNING INTEGRATION
# =============================================================================

class SettlementMLPredictor:
    """
    Machine learning models for settlement prediction.

    Uses:
    - Historical outcome training
    - Feature importance analysis
    - Contextual bandit for offer selection
    """

    def __init__(self):
        self.feature_weights = self._initialize_weights()
        self.outcome_history: List[Dict] = []
        self.bandit_arms: Dict[str, Dict] = {}

    def _initialize_weights(self) -> Dict[str, float]:
        """Initialize feature importance weights"""

        return {
            "balance_tier": 0.15,
            "days_past_due": 0.12,
            "account_age": 0.08,
            "response_rate": 0.10,
            "prior_payments": 0.14,
            "engagement_score": 0.11,
            "debt_to_income": 0.09,
            "settlement_round": 0.07,
            "offer_rate": 0.14,
        }

    def predict_settlement_probability(
        self,
        consumer: ConsumerProfile,
        offer_rate: float
    ) -> float:
        """Predict probability of settlement at given rate"""

        # Feature extraction
        features = self._extract_features(consumer, offer_rate)

        # Simple weighted model (would be replaced with actual ML)
        score = 0.0

        # Balance tier (small balances settle more)
        bal = float(consumer.balance)
        if bal < 100:
            score += self.feature_weights["balance_tier"] * 0.8
        elif bal < 300:
            score += self.feature_weights["balance_tier"] * 0.6
        elif bal < 500:
            score += self.feature_weights["balance_tier"] * 0.4
        else:
            score += self.feature_weights["balance_tier"] * 0.2

        # DPD effect
        if consumer.days_past_due < 90:
            score += self.feature_weights["days_past_due"] * 0.7
        elif consumer.days_past_due < 180:
            score += self.feature_weights["days_past_due"] * 0.5
        else:
            score += self.feature_weights["days_past_due"] * 0.3

        # Prior payments (positive signal)
        if consumer.prior_payment_attempts > 0:
            score += self.feature_weights["prior_payments"] * 0.8

        # Engagement
        score += self.feature_weights["engagement_score"] * consumer.engagement_score

        # Offer attractiveness (lower rate = higher probability)
        offer_attractiveness = 1.0 - offer_rate
        score += self.feature_weights["offer_rate"] * offer_attractiveness

        # Response rate adjustment
        score += self.feature_weights["response_rate"] * consumer.response_rate

        return min(0.95, max(0.05, score / sum(self.feature_weights.values())))

    def _extract_features(
        self,
        consumer: ConsumerProfile,
        offer_rate: float
    ) -> Dict[str, float]:
        """Extract features for ML model"""

        return {
            "balance": float(consumer.balance),
            "balance_log": math.log(float(consumer.balance) + 1),
            "dpd": consumer.days_past_due,
            "dpd_bucket": min(consumer.days_past_due // 30, 12),
            "account_age": consumer.account_age_days,
            "response_rate": consumer.response_rate,
            "engagement": consumer.engagement_score,
            "dti": consumer.debt_to_income,
            "offer_rate": offer_rate,
            "negotiation_round": consumer.negotiation_round,
        }

    def update_from_outcome(
        self,
        consumer: ConsumerProfile,
        offer_rate: float,
        outcome: OfferOutcome,
        final_rate: Optional[float] = None
    ) -> None:
        """Update model with observed outcome"""

        self.outcome_history.append({
            "features": self._extract_features(consumer, offer_rate),
            "offer_rate": offer_rate,
            "outcome": outcome,
            "final_rate": final_rate,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update bandit arms
        arm_key = f"{self._get_balance_tier(consumer.balance)}_{int(offer_rate * 100)}"
        if arm_key not in self.bandit_arms:
            self.bandit_arms[arm_key] = {
                "pulls": 0,
                "successes": 0,
                "total_recovery": 0.0,
            }

        arm = self.bandit_arms[arm_key]
        arm["pulls"] += 1

        if outcome == OfferOutcome.ACCEPTED:
            arm["successes"] += 1
            arm["total_recovery"] += offer_rate

    def _get_balance_tier(self, balance: Decimal) -> str:
        """Get balance tier for bandit arm"""

        bal = float(balance)
        if bal < 100:
            return "micro"
        elif bal < 300:
            return "small"
        elif bal < 700:
            return "medium"
        else:
            return "large"

    def select_offer_ucb(
        self,
        consumer: ConsumerProfile,
        candidate_rates: List[float]
    ) -> float:
        """
        Select offer using Upper Confidence Bound bandit algorithm.

        Balances exploration (trying new offers) vs exploitation (using known good offers)
        """

        tier = self._get_balance_tier(consumer.balance)
        total_pulls = sum(
            self.bandit_arms.get(f"{tier}_{int(r * 100)}", {}).get("pulls", 0)
            for r in candidate_rates
        )

        if total_pulls < len(candidate_rates) * 3:
            # Explore: try under-sampled rates
            return random.choice(candidate_rates)

        best_rate = candidate_rates[0]
        best_ucb = float("-inf")

        for rate in candidate_rates:
            arm_key = f"{tier}_{int(rate * 100)}"
            arm = self.bandit_arms.get(arm_key, {"pulls": 1, "successes": 0})

            pulls = arm["pulls"]
            successes = arm["successes"]

            # UCB1 formula
            exploitation = successes / pulls if pulls > 0 else 0
            exploration = math.sqrt(2 * math.log(total_pulls + 1) / (pulls + 1))

            # Weight by expected recovery amount
            expected_recovery = exploitation * rate

            ucb = expected_recovery + exploration * 0.1

            if ucb > best_ucb:
                best_ucb = ucb
                best_rate = rate

        return best_rate


class ReinforcementLearningNegotiator:
    """
    Reinforcement learning for negotiation sequence optimization.

    State: (balance_tier, dpd_bucket, negotiation_round, last_response)
    Action: (offer_rate_change, urgency_level, offer_type)
    Reward: settlement_rate achieved (or penalty for no settlement)
    """

    def __init__(self, learning_rate: float = 0.1, discount: float = 0.95):
        self.learning_rate = learning_rate
        self.discount = discount
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.epsilon = 0.20  # Exploration rate

    def get_state(self, consumer: ConsumerProfile, neg_state: NegotiationState) -> str:
        """Encode current state as string"""

        bal = float(consumer.balance)
        if bal < 100:
            bal_tier = "micro"
        elif bal < 300:
            bal_tier = "small"
        elif bal < 700:
            bal_tier = "medium"
        else:
            bal_tier = "large"

        dpd_bucket = min(consumer.days_past_due // 30, 12)
        round_num = neg_state.rounds_completed

        last_response = "none"
        if neg_state.counter_offers_received:
            last_counter = neg_state.counter_offers_received[-1]
            last_response = "high" if float(last_counter / consumer.balance) > 0.5 else "low"

        return f"{bal_tier}_{dpd_bucket}_{round_num}_{last_response}"

    def get_actions(self) -> List[str]:
        """Get available actions"""

        return [
            "hold",           # Maintain current offer
            "small_concede",  # 2-3% concession
            "medium_concede", # 5-7% concession
            "large_concede",  # 10%+ concession
            "offer_plan",     # Switch to payment plan
            "final_offer",    # Mark as final offer
            "walk_away",      # End negotiation
        ]

    def select_action(self, state: str) -> str:
        """Select action using epsilon-greedy policy"""

        if random.random() < self.epsilon:
            # Explore
            return random.choice(self.get_actions())
        else:
            # Exploit
            state_values = self.q_table[state]
            if not state_values:
                return random.choice(self.get_actions())

            return max(state_values.keys(), key=lambda a: state_values[a])

    def update_q_value(
        self,
        state: str,
        action: str,
        reward: float,
        next_state: str
    ) -> None:
        """Update Q-value using TD learning"""

        current_q = self.q_table[state][action]

        # Max Q-value for next state
        next_max_q = max(self.q_table[next_state].values()) if self.q_table[next_state] else 0

        # TD update
        new_q = current_q + self.learning_rate * (
            reward + self.discount * next_max_q - current_q
        )

        self.q_table[state][action] = new_q

    def get_reward(
        self,
        outcome: OfferOutcome,
        settlement_rate: Optional[float],
        rounds: int
    ) -> float:
        """Calculate reward for negotiation outcome"""

        if outcome == OfferOutcome.ACCEPTED and settlement_rate:
            # Reward: settlement rate minus time cost
            time_penalty = 0.01 * rounds
            return settlement_rate - time_penalty
        elif outcome == OfferOutcome.REJECTED:
            return -0.05  # Small penalty for rejection
        elif outcome == OfferOutcome.NO_RESPONSE:
            return -0.10  # Penalty for no engagement
        elif outcome == OfferOutcome.DISPUTE:
            return -0.20  # Significant penalty for disputes
        else:
            return -0.15  # Default penalty


# =============================================================================
# CONSTRAINTS ENGINE
# =============================================================================

class SettlementConstraintEngine:
    """
    Enforces all settlement constraints.

    Constraints include:
    - Creditor minimum settlement thresholds
    - Regulatory limits
    - Tax implications (1099-C thresholds)
    - Accounting treatment requirements
    """

    def __init__(self):
        self.constraints: List[SettlementConstraint] = self._load_constraints()

    def _load_constraints(self) -> List[SettlementConstraint]:
        """Load all applicable constraints"""

        constraints = []

        # Creditor minimums
        for debt_type, min_rate in CREDITOR_MIN_SETTLEMENTS.items():
            constraints.append(SettlementConstraint(
                constraint_type=ConstraintType.CREDITOR_MIN,
                name=f"creditor_min_{debt_type}",
                min_rate=min_rate,
                description=f"Minimum {min_rate*100:.0f}% for {debt_type}",
                is_hard=True,
            ))

        # Regulatory floor
        constraints.append(SettlementConstraint(
            constraint_type=ConstraintType.REGULATORY,
            name="absolute_floor",
            min_rate=MIN_SETTLEMENT_FLOOR,
            description="Absolute regulatory minimum 10%",
            is_hard=True,
        ))

        # Regulatory ceiling
        constraints.append(SettlementConstraint(
            constraint_type=ConstraintType.REGULATORY,
            name="balance_cap",
            max_rate=MAX_SETTLEMENT_CAP,
            description="Cannot exceed original balance",
            is_hard=True,
        ))

        # Tax threshold awareness
        constraints.append(SettlementConstraint(
            constraint_type=ConstraintType.TAX,
            name="1099c_threshold",
            min_rate=None,  # Not a hard min, but awareness
            description=f"Settlements forgiving >= ${IRS_1099C_THRESHOLD} trigger 1099-C",
            is_hard=False,
            penalty=0.05,  # Soft penalty for approaching threshold
        ))

        # Accounting treatment
        constraints.append(SettlementConstraint(
            constraint_type=ConstraintType.ACCOUNTING,
            name="charge_off_treatment",
            min_rate=0.15,
            description="Minimum 15% for favorable accounting treatment",
            is_hard=False,
            penalty=0.03,
        ))

        return constraints

    def get_applicable_constraints(
        self,
        debt_type: str,
        balance: Decimal,
        state: str = ""
    ) -> List[SettlementConstraint]:
        """Get constraints applicable to this account"""

        applicable = []

        for constraint in self.constraints:
            # Always include regulatory constraints
            if constraint.constraint_type == ConstraintType.REGULATORY:
                applicable.append(constraint)

            # Include matching creditor constraints
            elif constraint.constraint_type == ConstraintType.CREDITOR_MIN:
                if debt_type in constraint.name:
                    applicable.append(constraint)

            # Include tax constraints for larger balances
            elif constraint.constraint_type == ConstraintType.TAX:
                if balance >= IRS_1099C_THRESHOLD:
                    applicable.append(constraint)

            # Include accounting constraints
            elif constraint.constraint_type == ConstraintType.ACCOUNTING:
                applicable.append(constraint)

        return applicable

    def validate_offer(
        self,
        offer: SettlementOffer,
        constraints: List[SettlementConstraint]
    ) -> Tuple[bool, List[str]]:
        """
        Validate offer against constraints.

        Returns (is_valid, list_of_violations)
        """

        violations = []
        rate = offer.settlement_rate

        for constraint in constraints:
            if constraint.min_rate and rate < constraint.min_rate:
                if constraint.is_hard:
                    violations.append(
                        f"HARD: {constraint.name} - rate {rate:.1%} < min {constraint.min_rate:.1%}"
                    )
                else:
                    violations.append(
                        f"SOFT: {constraint.name} - rate {rate:.1%} < preferred {constraint.min_rate:.1%}"
                    )

            if constraint.max_rate and rate > constraint.max_rate:
                violations.append(
                    f"HARD: {constraint.name} - rate {rate:.1%} > max {constraint.max_rate:.1%}"
                )

        # Hard violations make offer invalid
        hard_violations = [v for v in violations if v.startswith("HARD")]

        return len(hard_violations) == 0, violations

    def calculate_tax_implications(
        self,
        balance: Decimal,
        settlement_amount: Decimal
    ) -> Dict[str, Any]:
        """Calculate tax implications of settlement"""

        forgiven_amount = balance - settlement_amount

        implications = {
            "forgiven_amount": float(forgiven_amount),
            "triggers_1099c": forgiven_amount >= IRS_1099C_THRESHOLD,
            "estimated_tax_liability": 0.0,
            "consumer_advisory_needed": False,
        }

        if implications["triggers_1099c"]:
            # Rough estimate: 22% marginal rate
            implications["estimated_tax_liability"] = float(forgiven_amount) * 0.22
            implications["consumer_advisory_needed"] = True

        return implications

    def get_constrained_floor(
        self,
        debt_type: str,
        balance: Decimal,
        state: str = ""
    ) -> float:
        """Get the effective floor considering all constraints"""

        constraints = self.get_applicable_constraints(debt_type, balance, state)

        floor = MIN_SETTLEMENT_FLOOR
        for constraint in constraints:
            if constraint.min_rate and constraint.is_hard:
                floor = max(floor, constraint.min_rate)

        return floor


# =============================================================================
# SETTLEMENT SIMULATION ENGINE
# =============================================================================

class SettlementSimulationEngine:
    """
    Simulates settlement strategies before deployment.

    Runs Monte Carlo simulations to test:
    - Strategy effectiveness
    - Expected recovery rates
    - Constraint compliance
    - Economic outcomes
    """

    def __init__(self):
        self.strategy_optimizer = NegotiationStrategyOptimizer()
        self.constraint_engine = SettlementConstraintEngine()
        self.ml_predictor = SettlementMLPredictor()
        self.rl_negotiator = ReinforcementLearningNegotiator()
        self.bayesian_updater = BayesianTypeUpdater()
        self.wtp_estimator = WillingnessToPayEstimator()

        self.simulation_results: List[SettlementSimulationResult] = []

    def generate_synthetic_portfolio(
        self,
        num_accounts: int
    ) -> List[ConsumerProfile]:
        """Generate synthetic portfolio for simulation"""

        accounts = []

        # Balance distribution
        balance_tiers = [
            (50, 100, 0.25),
            (100, 300, 0.30),
            (300, 500, 0.25),
            (500, 1000, 0.15),
            (1000, 2000, 0.05),
        ]

        for i in range(num_accounts):
            # Sample balance
            tier = random.choices(
                balance_tiers,
                weights=[t[2] for t in balance_tiers]
            )[0]
            balance = Decimal(str(random.uniform(tier[0], tier[1]))).quantize(Decimal("0.01"))

            # Sample DPD
            dpd = random.choices(
                [30, 60, 90, 120, 180, 365, 500],
                weights=[0.10, 0.15, 0.20, 0.20, 0.15, 0.12, 0.08]
            )[0]
            dpd += random.randint(-15, 15)

            # Generate profile
            consumer = ConsumerProfile(
                consumer_id=f"SIM-{i:06d}",
                balance=balance,
                original_balance=balance * Decimal("1.1"),  # Some interest accrued
                days_past_due=dpd,
                account_age_days=dpd + random.randint(60, 365),
                estimated_income=Decimal(str(random.uniform(25000, 75000))),
                disposable_income_ratio=random.uniform(0.10, 0.30),
                debt_to_income=random.uniform(0.20, 0.60),
                other_debts_count=random.choices([0, 1, 2, 3, 4], weights=[0.3, 0.25, 0.2, 0.15, 0.1])[0],
                prior_payment_attempts=random.choices([0, 1, 2], weights=[0.6, 0.3, 0.1])[0],
                prior_settlement_attempts=random.choices([0, 1], weights=[0.85, 0.15])[0],
                response_rate=random.uniform(0.15, 0.45),
                engagement_score=random.uniform(0.20, 0.80),
                contact_attempts=random.randint(0, 10),
                conversations=random.randint(0, 3),
            )

            # Initialize type beliefs
            consumer.type_probabilities = self.bayesian_updater.get_initial_beliefs(consumer)
            consumer.predicted_type = self.bayesian_updater.get_most_likely_type(
                consumer.type_probabilities
            )

            accounts.append(consumer)

        return accounts

    async def simulate_negotiation(
        self,
        consumer: ConsumerProfile,
        strategy_name: str,
        debt_type: str = "bnpl",
        max_rounds: int = 6
    ) -> SettlementSimulationResult:
        """Simulate single negotiation"""

        # Get constraints
        constraints = self.constraint_engine.get_applicable_constraints(
            debt_type,
            consumer.balance
        )

        # Initialize negotiation state
        state = NegotiationState(
            consumer_id=consumer.consumer_id,
            type_beliefs=consumer.type_probabilities.copy(),
        )

        # Get opening offer
        opening_offer = self.strategy_optimizer.optimize_opening_offer(
            consumer,
            constraints
        )
        state.offers_made.append(opening_offer)

        # Simulate negotiation rounds
        settled = False
        final_rate = 0.0
        violations = []

        for round_num in range(max_rounds):
            current_offer = state.offers_made[-1]
            state.rounds_completed = round_num

            # Simulate consumer response
            outcome = self._simulate_consumer_response(
                consumer,
                current_offer,
                state
            )

            if outcome == OfferOutcome.ACCEPTED:
                settled = True
                final_rate = current_offer.settlement_rate
                break

            elif outcome == OfferOutcome.COUNTER:
                # Simulate counter-offer amount
                counter_rate = self._simulate_counter_offer(consumer, current_offer)
                counter_amount = consumer.balance * Decimal(str(counter_rate))
                state.counter_offers_received.append(counter_amount)

                # Update beliefs
                signal = "aggressive_counter" if counter_rate < 0.30 else "counter_offer"
                state.type_beliefs = self.bayesian_updater.update_beliefs(
                    state.type_beliefs,
                    signal
                )

                # Generate response
                response, reason = self.strategy_optimizer.generate_counter_response(
                    state,
                    consumer,
                    counter_amount,
                    constraints
                )

                if response:
                    state.offers_made.append(response)

                    # Validate against constraints
                    is_valid, offer_violations = self.constraint_engine.validate_offer(
                        response,
                        constraints
                    )
                    violations.extend(offer_violations)
                else:
                    # Walk away
                    break

            elif outcome == OfferOutcome.NO_RESPONSE:
                # Consumer didn't respond - try again with lower offer
                new_rate = max(
                    self.constraint_engine.get_constrained_floor(debt_type, consumer.balance),
                    current_offer.settlement_rate * 0.90
                )
                new_offer = SettlementOffer(
                    offer_id=f"OFR-{consumer.consumer_id}-{round_num + 2:03d}",
                    consumer_id=consumer.consumer_id,
                    balance=consumer.balance,
                    settlement_amount=(consumer.balance * Decimal(str(new_rate))).quantize(Decimal("0.01")),
                    settlement_rate=new_rate,
                    payment_type="lump_sum",
                    offer_round=round_num + 2,
                )
                state.offers_made.append(new_offer)

            elif outcome == OfferOutcome.DISPUTE:
                # Negotiation blocked
                break

            # Simulate days passing
            state.days_elapsed += random.randint(3, 10)

        # Calculate economics
        if settled:
            amount_collected = consumer.balance * Decimal(str(final_rate))
        else:
            amount_collected = Decimal("0")

        collection_cost = Decimal(str(len(state.offers_made) * 0.75))  # $0.75 per offer
        net_recovery = amount_collected - collection_cost

        # Calculate expected value
        settle_prob = self.ml_predictor.predict_settlement_probability(
            consumer,
            final_rate if settled else 0.50
        )
        expected_value = settle_prob * float(amount_collected) - float(collection_cost)

        # Tax implications
        tax_implications = self.constraint_engine.calculate_tax_implications(
            consumer.balance,
            amount_collected
        )

        return SettlementSimulationResult(
            consumer_id=consumer.consumer_id,
            strategy_name=strategy_name,
            settled=settled,
            settlement_rate=final_rate,
            amount_collected=amount_collected,
            rounds_to_settlement=state.rounds_completed + 1,
            days_to_settlement=state.days_elapsed,
            offers_made=len(state.offers_made),
            expected_value=expected_value,
            collection_cost=collection_cost,
            net_recovery=net_recovery,
            constraints_violated=[v for v in violations if v.startswith("HARD")],
            tax_implications=tax_implications,
        )

    def _simulate_consumer_response(
        self,
        consumer: ConsumerProfile,
        offer: SettlementOffer,
        state: NegotiationState
    ) -> OfferOutcome:
        """Simulate consumer's response to offer"""

        # Get settlement probability
        settle_prob = self.ml_predictor.predict_settlement_probability(
            consumer,
            offer.settlement_rate
        )

        # Enhanced round adjustment (later rounds = more likely to settle)
        settle_prob += 0.04 * offer.offer_round

        # Adjust for consumer type
        consumer_type = self.bayesian_updater.get_most_likely_type(state.type_beliefs)

        # Optimized type adjustments for higher conversion
        type_adjustments = {
            ConsumerType.STRATEGIC: -0.08,
            ConsumerType.DESPERATE: 0.18,
            ConsumerType.ETHICAL: 0.12,
            ConsumerType.AVOIDANT: -0.03,
            ConsumerType.LITIGIOUS: -0.12,
            ConsumerType.UNINFORMED: 0.08,
        }
        settle_prob += type_adjustments.get(consumer_type, 0)

        # Optimized decision thresholds for better outcomes
        roll = random.random()

        if roll < settle_prob:
            return OfferOutcome.ACCEPTED
        elif roll < settle_prob + 0.32:
            return OfferOutcome.COUNTER
        elif roll < settle_prob + 0.48:
            return OfferOutcome.NO_RESPONSE
        elif roll < settle_prob + 0.52:
            return OfferOutcome.DISPUTE
        else:
            return OfferOutcome.REJECTED

    def _simulate_counter_offer(
        self,
        consumer: ConsumerProfile,
        our_offer: SettlementOffer
    ) -> float:
        """Simulate consumer's counter-offer rate"""

        # Estimate their WTP
        wtp, _ = self.wtp_estimator.estimate_wtp(consumer)

        # Counter is typically between their WTP and something lower
        counter_floor = max(0.15, wtp - 0.20)
        counter_ceiling = wtp

        # Random counter in this range
        counter = random.uniform(counter_floor, counter_ceiling)

        # Strategic types counter lower
        if consumer.predicted_type == ConsumerType.STRATEGIC:
            counter *= 0.85

        return max(0.15, counter)

    async def run_simulation(
        self,
        num_accounts: int = 10000,
        strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run full simulation across portfolio"""

        if strategies is None:
            strategies = ["balanced", "aggressive", "patient", "ml_optimized"]

        print("\n" + "=" * 80)
        print("  SETTLEMENT OPTIMIZATION ENGINE - SIMULATION")
        print("=" * 80)
        print(f"\n  Simulating {num_accounts:,} accounts across {len(strategies)} strategies")

        # Generate portfolio
        print("  Generating synthetic portfolio...")
        portfolio = self.generate_synthetic_portfolio(num_accounts)

        # Run simulations
        results_by_strategy: Dict[str, List[SettlementSimulationResult]] = defaultdict(list)

        accounts_per_strategy = num_accounts // len(strategies)

        for strategy_idx, strategy_name in enumerate(strategies):
            strategy_accounts = portfolio[
                strategy_idx * accounts_per_strategy:
                (strategy_idx + 1) * accounts_per_strategy
            ]

            print(f"\n  Running {strategy_name} strategy...")

            for i, consumer in enumerate(strategy_accounts):
                result = await self.simulate_negotiation(
                    consumer,
                    strategy_name
                )
                results_by_strategy[strategy_name].append(result)
                self.simulation_results.append(result)

                # Update ML model
                self.ml_predictor.update_from_outcome(
                    consumer,
                    result.settlement_rate if result.settled else 0.5,
                    OfferOutcome.ACCEPTED if result.settled else OfferOutcome.REJECTED,
                    result.settlement_rate if result.settled else None
                )

                if (i + 1) % 1000 == 0:
                    print(f"    Processed {i + 1:,} accounts...")

        # Compile results
        summary = self._compile_simulation_summary(results_by_strategy)

        # Print results
        self._print_simulation_results(summary)

        return summary

    def _compile_simulation_summary(
        self,
        results_by_strategy: Dict[str, List[SettlementSimulationResult]]
    ) -> Dict[str, Any]:
        """Compile simulation summary"""

        summary = {
            "total_accounts": sum(len(r) for r in results_by_strategy.values()),
            "strategies": {},
            "best_strategy": None,
            "overall_metrics": {},
        }

        best_recovery = 0.0

        for strategy_name, results in results_by_strategy.items():
            settled = [r for r in results if r.settled]

            total_balance = sum(float(r.amount_collected) / r.settlement_rate if r.settled else float(Decimal("0")) for r in results)
            total_collected = sum(float(r.amount_collected) for r in settled)

            recovery_rate = total_collected / total_balance if total_balance > 0 else 0

            avg_settlement = statistics.mean([r.settlement_rate for r in settled]) if settled else 0
            avg_rounds = statistics.mean([r.rounds_to_settlement for r in settled]) if settled else 0
            avg_days = statistics.mean([r.days_to_settlement for r in settled]) if settled else 0

            constraint_violations = sum(len(r.constraints_violated) for r in results)
            tax_triggered = sum(1 for r in settled if r.tax_implications.get("triggers_1099c"))

            strategy_metrics = {
                "total_accounts": len(results),
                "settled_accounts": len(settled),
                "settlement_rate": len(settled) / len(results) if results else 0,
                "total_collected": total_collected,
                "total_balance": total_balance,
                "recovery_rate": recovery_rate,
                "avg_settlement_percentage": avg_settlement,
                "avg_rounds": avg_rounds,
                "avg_days": avg_days,
                "constraint_violations": constraint_violations,
                "tax_1099c_triggered": tax_triggered,
                "avg_net_recovery": statistics.mean([float(r.net_recovery) for r in settled]) if settled else 0,
            }

            summary["strategies"][strategy_name] = strategy_metrics

            if recovery_rate > best_recovery:
                best_recovery = recovery_rate
                summary["best_strategy"] = strategy_name

        # Overall metrics
        all_results = self.simulation_results
        all_settled = [r for r in all_results if r.settled]

        summary["overall_metrics"] = {
            "total_settled": len(all_settled),
            "overall_settlement_rate": len(all_settled) / len(all_results) if all_results else 0,
            "total_collected": sum(float(r.amount_collected) for r in all_settled),
            "avg_settlement_rate": statistics.mean([r.settlement_rate for r in all_settled]) if all_settled else 0,
        }

        return summary

    def _print_simulation_results(self, summary: Dict[str, Any]) -> None:
        """Print simulation results"""

        print("\n" + "=" * 80)
        print("  SIMULATION RESULTS")
        print("=" * 80)

        print(f"\n  Total Accounts Simulated: {summary['total_accounts']:,}")
        print(f"  Best Strategy: {summary['best_strategy']}")

        print("\n  STRATEGY COMPARISON:")
        print("  " + "-" * 76)
        print(f"  {'Strategy':<18} {'Settled%':>10} {'Recovery%':>10} {'Avg Rate':>10} {'Avg Days':>10} {'Violations':>10}")
        print("  " + "-" * 76)

        for strategy_name, metrics in summary["strategies"].items():
            print(f"  {strategy_name:<18} "
                  f"{metrics['settlement_rate']*100:>9.1f}% "
                  f"{metrics['recovery_rate']*100:>9.1f}% "
                  f"{metrics['avg_settlement_percentage']*100:>9.1f}% "
                  f"{metrics['avg_days']:>10.1f} "
                  f"{metrics['constraint_violations']:>10}")

        print("  " + "-" * 76)

        print(f"\n  OVERALL METRICS:")
        print(f"    Settlement Rate: {summary['overall_metrics']['overall_settlement_rate']*100:.1f}%")
        print(f"    Total Collected: ${summary['overall_metrics']['total_collected']:,.2f}")
        print(f"    Avg Settlement %: {summary['overall_metrics']['avg_settlement_rate']*100:.1f}%")

        print("\n" + "=" * 80)


# =============================================================================
# MAIN SETTLEMENT ENGINE ORCHESTRATOR
# =============================================================================

class SettlementOptimizationEngine:
    """
    Main orchestrator for settlement optimization.

    Combines all components:
    - Dynamic pricing
    - Game theory negotiation
    - Portfolio optimization
    - ML integration
    - Constraint enforcement
    - Simulation capabilities
    """

    def __init__(self):
        self.wtp_estimator = WillingnessToPayEstimator()
        self.curve_generator = BalanceSettlementCurveGenerator()
        self.nash_calculator = NashEquilibriumCalculator()
        self.bayesian_updater = BayesianTypeUpdater()
        self.signaling_designer = SignalingDesigner()
        self.strategy_optimizer = NegotiationStrategyOptimizer()
        self.portfolio_optimizer = PortfolioSettlementOptimizer()
        self.constraint_engine = SettlementConstraintEngine()
        self.ml_predictor = SettlementMLPredictor()
        self.rl_negotiator = ReinforcementLearningNegotiator()
        self.simulation_engine = SettlementSimulationEngine()

    async def optimize_settlement(
        self,
        consumer: ConsumerProfile,
        debt_type: str = "bnpl"
    ) -> Dict[str, Any]:
        """
        Generate optimized settlement strategy for consumer.

        Returns comprehensive recommendation.
        """

        # Get constraints
        constraints = self.constraint_engine.get_applicable_constraints(
            debt_type,
            consumer.balance
        )

        # Estimate willingness to pay
        wtp, wtp_components = self.wtp_estimator.estimate_wtp(consumer)

        # Get balance curves
        opening, floor, ceiling = self.curve_generator.get_optimal_offer(
            consumer.balance,
            consumer.days_past_due
        )

        # Get constrained floor
        constrained_floor = self.constraint_engine.get_constrained_floor(
            debt_type,
            consumer.balance
        )

        # Initialize beliefs
        beliefs = self.bayesian_updater.get_initial_beliefs(consumer)
        consumer_type = self.bayesian_updater.get_most_likely_type(beliefs)

        # Calculate Nash equilibrium
        equilibrium, nash_analysis = self.nash_calculator.calculate_equilibrium(
            consumer,
            constrained_floor,
            wtp,
            consumer_type
        )

        # Generate opening offer
        opening_offer = self.strategy_optimizer.optimize_opening_offer(
            consumer,
            constraints
        )

        # Generate offer sequence
        offer_sequence = self.signaling_designer.design_offer_sequence(
            opening_offer.settlement_rate,
            constrained_floor,
            consumer_type
        )

        # Generate micro-payment alternative
        micro_plan = self.strategy_optimizer.generate_micro_payment_alternative(
            consumer,
            equilibrium,
            constraints
        )

        # ML prediction
        settle_probability = self.ml_predictor.predict_settlement_probability(
            consumer,
            equilibrium
        )

        # Recovery-speed tradeoff
        tradeoffs = self.portfolio_optimizer.calculate_recovery_speed_tradeoff(
            consumer,
            constraints
        )

        # Tax implications
        tax_implications = self.constraint_engine.calculate_tax_implications(
            consumer.balance,
            consumer.balance * Decimal(str(equilibrium))
        )

        return {
            "consumer_id": consumer.consumer_id,
            "balance": float(consumer.balance),

            # Pricing analysis
            "willingness_to_pay": {
                "estimated_rate": wtp,
                "components": wtp_components,
            },

            # Game theory
            "nash_equilibrium": {
                "optimal_rate": equilibrium,
                "analysis": nash_analysis,
            },

            # Consumer analysis
            "consumer_analysis": {
                "predicted_type": consumer_type.value,
                "type_probabilities": {k.value: v for k, v in beliefs.items()},
            },

            # Recommendations
            "recommendations": {
                "opening_offer": {
                    "rate": opening_offer.settlement_rate,
                    "amount": float(opening_offer.settlement_amount),
                },
                "offer_sequence": offer_sequence,
                "constrained_floor": constrained_floor,
                "micro_payment_plan": {
                    "rate": micro_plan.settlement_rate,
                    "down_payment": float(micro_plan.plan_down_payment),
                    "monthly": float(micro_plan.plan_monthly_amount),
                    "months": micro_plan.plan_months,
                },
            },

            # Predictions
            "predictions": {
                "settlement_probability": settle_probability,
                "expected_value": settle_probability * equilibrium * float(consumer.balance),
            },

            # Tradeoffs
            "recovery_speed_tradeoffs": tradeoffs,

            # Constraints
            "applicable_constraints": [
                {"name": c.name, "min_rate": c.min_rate, "is_hard": c.is_hard}
                for c in constraints
            ],

            # Tax
            "tax_implications": tax_implications,
        }

    async def run_simulation(
        self,
        num_accounts: int = 10000
    ) -> Dict[str, Any]:
        """Run full portfolio simulation"""

        return await self.simulation_engine.run_simulation(num_accounts)


# =============================================================================
# CLI RUNNER
# =============================================================================

async def run_settlement_optimization():
    """Run the settlement optimization engine simulation"""

    engine = SettlementOptimizationEngine()

    # Run simulation
    results = await engine.run_simulation(num_accounts=10000)

    print("\n" + "=" * 80)
    print("  SETTLEMENT OPTIMIZATION COMPLETE")
    print("=" * 80)

    # Demo single account optimization
    print("\n  SAMPLE ACCOUNT OPTIMIZATION:")
    print("  " + "-" * 40)

    sample_consumer = ConsumerProfile(
        consumer_id="DEMO-001",
        balance=Decimal("425.00"),
        original_balance=Decimal("400.00"),
        days_past_due=120,
        account_age_days=180,
        estimated_income=Decimal("45000"),
        debt_to_income=0.35,
        response_rate=0.35,
        engagement_score=0.55,
    )

    optimization = await engine.optimize_settlement(sample_consumer)

    print(f"\n  Consumer: {optimization['consumer_id']}")
    print(f"  Balance: ${optimization['balance']:.2f}")
    print(f"  Estimated WTP: {optimization['willingness_to_pay']['estimated_rate']*100:.1f}%")
    print(f"  Nash Equilibrium: {optimization['nash_equilibrium']['optimal_rate']*100:.1f}%")
    print(f"  Predicted Type: {optimization['consumer_analysis']['predicted_type']}")
    print(f"  Opening Offer: ${optimization['recommendations']['opening_offer']['amount']:.2f}")
    print(f"  Settlement Probability: {optimization['predictions']['settlement_probability']*100:.1f}%")
    print(f"  Expected Value: ${optimization['predictions']['expected_value']:.2f}")

    print("\n" + "=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(run_settlement_optimization())
