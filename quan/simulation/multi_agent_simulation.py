"""
Multi-Variable Collection Simulation

Comprehensive parameter sweep to identify optimal collection strategies
across multiple dimensions:
- Contact cadence intervals
- Maximum contact attempts
- Channel mix strategies
- Settlement thresholds
- Payment plan terms

Uses 50,000 accounts from sub-$1K micro-debt universe with
industry-calibrated conversion probabilities (47% recovery baseline).
"""

import asyncio
import random
import statistics
import itertools
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

from quan.simulation.sub_1k_simulation import (
    SUB_1K_UNIVERSE, MicroDebtType, MicroDebtProfile, Sub1KAccount
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================

class ChannelMix(Enum):
    """Channel priority strategies"""
    SMS_FIRST = "sms_first"
    EMAIL_FIRST = "email_first"
    BALANCED = "balanced"


@dataclass
class ChannelWeights:
    """Channel weights for different strategies"""
    sms: float
    email: float
    push: float

    @classmethod
    def from_strategy(cls, strategy: ChannelMix) -> 'ChannelWeights':
        """Create weights from strategy enum"""
        if strategy == ChannelMix.SMS_FIRST:
            return cls(sms=0.60, email=0.25, push=0.15)
        elif strategy == ChannelMix.EMAIL_FIRST:
            return cls(sms=0.25, email=0.60, push=0.15)
        else:  # BALANCED
            return cls(sms=0.40, email=0.40, push=0.20)


@dataclass
class SimulationParameters:
    """Parameters for a single simulation run"""
    # Contact strategy
    contact_cadence_days: int = 3
    max_contact_attempts: int = 9
    channel_mix: ChannelMix = ChannelMix.BALANCED

    # Settlement parameters
    settlement_threshold_pct: float = 0.50  # Minimum acceptable settlement %

    # Payment plan options
    payment_plan_months: int = 3

    # Re-engagement settings
    re_engagement_delay_days: int = 14
    max_re_engagements: int = 3

    def get_param_key(self) -> str:
        """Generate unique key for this parameter combination"""
        return (f"cad{self.contact_cadence_days}_"
                f"max{self.max_contact_attempts}_"
                f"ch{self.channel_mix.value}_"
                f"set{int(self.settlement_threshold_pct*100)}_"
                f"plan{self.payment_plan_months}")


@dataclass
class CostParameters:
    """Cost accounting parameters"""
    # Per-contact costs
    cost_per_sms: Decimal = Decimal("0.02")
    cost_per_email: Decimal = Decimal("0.005")
    cost_per_push: Decimal = Decimal("0.01")

    # Payment processing costs
    cost_per_payment: Decimal = Decimal("0.18")
    cost_per_payment_plan_setup: Decimal = Decimal("0.50")
    cost_per_plan_payment: Decimal = Decimal("0.12")

    # Labor costs (500 agents at $120/day)
    num_agents: int = 500
    cost_per_agent_day: Decimal = Decimal("120")

    # Platform overhead
    platform_pct: Decimal = Decimal("0.03")  # 3% of collections
    compliance_pct: Decimal = Decimal("0.015")  # 1.5% of collections

    # Settlement costs
    settlement_processing: Decimal = Decimal("0.25")


@dataclass
class SimulationMetrics:
    """Metrics tracked for each simulation run"""
    # Recovery metrics
    total_accounts: int = 0
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    # Account outcomes
    accounts_full_paid: int = 0
    accounts_settled: int = 0
    accounts_on_plan: int = 0
    accounts_partial: int = 0
    accounts_uncollected: int = 0

    # Cost metrics
    total_cost: Decimal = Decimal("0")
    cost_per_dollar: float = 0.0
    profit_margin: float = 0.0
    roi: float = 0.0

    # Time metrics
    avg_time_to_first_payment: float = 0.0
    median_time_to_first_payment: float = 0.0
    time_to_first_payment_p95: float = 0.0

    # Customer satisfaction proxies
    dispute_count: int = 0
    complaint_count: int = 0
    cease_comm_requests: int = 0
    satisfaction_score: float = 0.0  # 0-100 scale

    # Contact metrics
    total_contacts: int = 0
    contacts_per_recovery: float = 0.0

    # Settlement metrics
    settlement_count: int = 0
    avg_settlement_pct: float = 0.0

    # Payment plan metrics
    plan_count: int = 0
    plan_completion_rate: float = 0.0

    # Confidence interval data
    recovery_samples: List[float] = field(default_factory=list)
    cost_samples: List[float] = field(default_factory=list)
    time_samples: List[float] = field(default_factory=list)


@dataclass
class ConfidenceInterval:
    """Confidence interval statistics"""
    mean: float
    std_dev: float
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    sample_size: int

    @classmethod
    def from_samples(cls, samples: List[float], confidence: float = 0.95) -> 'ConfidenceInterval':
        """Calculate CI from samples"""
        if not samples or len(samples) < 2:
            return cls(mean=0, std_dev=0, ci_lower=0, ci_upper=0, sample_size=0)

        n = len(samples)
        mean = statistics.mean(samples)
        std_dev = statistics.stdev(samples)

        # Z-score for 95% confidence
        z = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645

        margin = z * (std_dev / math.sqrt(n))

        return cls(
            mean=mean,
            std_dev=std_dev,
            ci_lower=mean - margin,
            ci_upper=mean + margin,
            sample_size=n
        )


@dataclass
class ResultsMatrixEntry:
    """Entry in the results matrix"""
    parameters: SimulationParameters
    metrics: SimulationMetrics

    # Confidence intervals
    recovery_ci: Optional[ConfidenceInterval] = None
    cost_ci: Optional[ConfidenceInterval] = None
    time_ci: Optional[ConfidenceInterval] = None
    satisfaction_ci: Optional[ConfidenceInterval] = None

    # Ranking scores
    overall_score: float = 0.0
    recovery_rank: int = 0
    cost_rank: int = 0
    time_rank: int = 0
    satisfaction_rank: int = 0


# =============================================================================
# SIMULATION ACCOUNT
# =============================================================================

@dataclass
class MultiAgentAccount:
    """Account for multi-variable simulation"""
    account_id: str
    debt_type: MicroDebtType
    balance: Decimal
    original_balance: Decimal

    # Debtor profile
    age: int
    has_mobile: bool
    is_digital_native: bool
    payment_willingness: float
    income_bracket: str  # "low", "medium", "high"

    # Contact validation
    phone_valid: bool = True
    email_valid: bool = True

    # Behavioral traits
    dispute_prone: bool = False
    complaint_prone: bool = False
    hardship_claim: bool = False
    settlement_only: bool = False
    needs_payment_plan: bool = False

    # State tracking
    status: str = "active"
    contact_attempts: int = 0
    last_contact_day: int = -999
    first_payment_day: int = -1
    re_engagement_attempts: int = 0

    # Payment tracking
    payments_made: int = 0
    total_paid: Decimal = Decimal("0")
    has_saved_payment: bool = False
    on_payment_plan: bool = False
    plan_payments_remaining: int = 0
    plan_payment_amount: Decimal = Decimal("0")

    # Satisfaction proxies
    filed_dispute: bool = False
    filed_complaint: bool = False
    requested_cease_comm: bool = False


# =============================================================================
# MULTI-VARIABLE SIMULATOR
# =============================================================================

class MultiVariableSimulator:
    """
    Comprehensive multi-variable collection simulation.

    Tests parameter combinations to identify optimal strategies
    with statistical confidence intervals.
    """

    # Industry-calibrated baseline (47% recovery target for sub-$1K)
    BASE_RECOVERY_TARGET = 0.47

    # Conversion probability factors
    CONVERSION_FACTORS = {
        "base_rate": 0.30,  # Per-contact base conversion
        "digital_native_bonus": 0.15,
        "mobile_bonus": 0.08,
        "saved_payment_bonus": 0.25,
        "first_contact_penalty": 0.30,
        "contact_decay_rate": 0.12,
        "re_engagement_boost": 0.15,
        "settlement_boost": 0.20,
        "payment_plan_boost": 0.18,
    }

    # Satisfaction impact factors
    SATISFACTION_FACTORS = {
        "base_satisfaction": 75.0,
        "per_extra_contact": -1.5,  # Beyond 6 contacts
        "dispute_penalty": -15.0,
        "complaint_penalty": -20.0,
        "settlement_offer_bonus": 5.0,
        "payment_plan_bonus": 8.0,
        "quick_resolution_bonus": 10.0,  # < 14 days
    }

    def __init__(
        self,
        cost_params: Optional[CostParameters] = None,
        num_accounts: int = 50000,
        simulation_days: int = 90,
        bootstrap_iterations: int = 5
    ):
        self.cost_params = cost_params or CostParameters()
        self.num_accounts = num_accounts
        self.simulation_days = simulation_days
        self.bootstrap_iterations = bootstrap_iterations

        self.accounts: List[MultiAgentAccount] = []
        self.results_matrix: Dict[str, ResultsMatrixEntry] = {}

    def generate_portfolio(self) -> List[MultiAgentAccount]:
        """Generate diversified portfolio across all debt types"""
        accounts = []

        # Calculate account distribution by market size
        market_totals = sum(p.accounts_millions for p in SUB_1K_UNIVERSE.values())

        account_num = 0
        for dt, profile in SUB_1K_UNIVERSE.items():
            # Proportional allocation
            type_count = int(self.num_accounts * (profile.accounts_millions / market_totals))

            for _ in range(type_count):
                # Generate balance (skewed toward lower end)
                raw = random.random() ** 0.6
                balance = (
                    profile.min_balance +
                    Decimal(str(raw)) * (profile.max_balance - profile.min_balance)
                ).quantize(Decimal("0.01"))

                # Demographics
                age = max(18, min(75, int(random.gauss(profile.avg_age, 12))))
                has_mobile = random.random() < profile.mobile_rate
                is_digital = random.random() < profile.digital_native_rate

                # Income bracket based on age and debt type
                if dt in [MicroDebtType.PAYDAY, MicroDebtType.PERSONAL_MICRO]:
                    income_weights = [0.55, 0.35, 0.10]
                elif dt in [MicroDebtType.BNPL, MicroDebtType.SUBSCRIPTION]:
                    income_weights = [0.30, 0.45, 0.25]
                else:
                    income_weights = [0.40, 0.40, 0.20]
                income_bracket = random.choices(
                    ["low", "medium", "high"],
                    weights=income_weights
                )[0]

                # Payment willingness
                willingness = profile.base_recovery_rate
                if is_digital:
                    willingness += 0.15
                if age < 35:
                    willingness += 0.08
                elif age > 55:
                    willingness -= 0.05
                if income_bracket == "high":
                    willingness += 0.10
                elif income_bracket == "low":
                    willingness -= 0.08
                willingness = max(0.10, min(0.85, willingness + random.gauss(0, 0.10)))

                # Behavioral traits (realistic distributions)
                dispute_prone = random.random() < 0.08
                complaint_prone = random.random() < 0.05
                hardship_claim = random.random() < 0.15 if income_bracket == "low" else random.random() < 0.05
                settlement_only = random.random() < 0.20 if willingness < 0.40 else random.random() < 0.08
                needs_payment_plan = random.random() < 0.25 if income_bracket == "low" else random.random() < 0.10

                account = MultiAgentAccount(
                    account_id=f"MAS-{account_num:06d}",
                    debt_type=dt,
                    balance=balance,
                    original_balance=balance,
                    age=age,
                    has_mobile=has_mobile,
                    is_digital_native=is_digital,
                    payment_willingness=willingness,
                    income_bracket=income_bracket,
                    phone_valid=random.random() < 0.88,
                    email_valid=random.random() < 0.75,
                    dispute_prone=dispute_prone,
                    complaint_prone=complaint_prone,
                    hardship_claim=hardship_claim,
                    settlement_only=settlement_only,
                    needs_payment_plan=needs_payment_plan
                )

                accounts.append(account)
                account_num += 1

        return accounts

    def reset_accounts(self, accounts: List[MultiAgentAccount]) -> List[MultiAgentAccount]:
        """Reset accounts for a new simulation run"""
        reset_accounts = []
        for acc in accounts:
            reset_acc = MultiAgentAccount(
                account_id=acc.account_id,
                debt_type=acc.debt_type,
                balance=acc.original_balance,
                original_balance=acc.original_balance,
                age=acc.age,
                has_mobile=acc.has_mobile,
                is_digital_native=acc.is_digital_native,
                payment_willingness=acc.payment_willingness,
                income_bracket=acc.income_bracket,
                phone_valid=acc.phone_valid,
                email_valid=acc.email_valid,
                dispute_prone=acc.dispute_prone,
                complaint_prone=acc.complaint_prone,
                hardship_claim=acc.hardship_claim,
                settlement_only=acc.settlement_only,
                needs_payment_plan=acc.needs_payment_plan
            )
            reset_accounts.append(reset_acc)
        return reset_accounts

    def calculate_conversion_probability(
        self,
        account: MultiAgentAccount,
        params: SimulationParameters,
        offer_settlement: bool = False,
        offer_plan: bool = False
    ) -> float:
        """
        Calculate conversion probability based on account and strategy.

        Industry-calibrated for 47% recovery baseline.
        """
        profile = SUB_1K_UNIVERSE[account.debt_type]

        # Base probability from debt type
        prob = profile.base_recovery_rate * self.CONVERSION_FACTORS["base_rate"]

        # Willingness multiplier
        willingness_mult = 0.5 + (account.payment_willingness * 0.5)
        prob *= willingness_mult

        # Digital characteristics
        if account.is_digital_native:
            prob *= (1 + self.CONVERSION_FACTORS["digital_native_bonus"])
        if account.has_mobile:
            prob *= (1 + self.CONVERSION_FACTORS["mobile_bonus"])
        if account.has_saved_payment:
            prob *= (1 + self.CONVERSION_FACTORS["saved_payment_bonus"])

        # Contact history effects
        if account.contact_attempts == 0:
            prob *= (1 - self.CONVERSION_FACTORS["first_contact_penalty"])
        elif account.contact_attempts > 3:
            excess = account.contact_attempts - 3
            decay = self.CONVERSION_FACTORS["contact_decay_rate"]
            prob *= ((1 - decay) ** excess)

        # Re-engagement boost
        if account.re_engagement_attempts > 0:
            prob *= (1 + self.CONVERSION_FACTORS["re_engagement_boost"])

        # Settlement offer boost
        if offer_settlement and account.settlement_only:
            prob *= (1 + self.CONVERSION_FACTORS["settlement_boost"])
        elif offer_settlement:
            prob *= (1 + self.CONVERSION_FACTORS["settlement_boost"] * 0.5)

        # Payment plan boost
        if offer_plan and account.needs_payment_plan:
            prob *= (1 + self.CONVERSION_FACTORS["payment_plan_boost"])
        elif offer_plan:
            prob *= (1 + self.CONVERSION_FACTORS["payment_plan_boost"] * 0.4)

        # Hardship adjustment
        if account.hardship_claim:
            prob *= 0.75

        # Contact validity
        if not account.phone_valid and not account.email_valid:
            prob *= 0.30
        elif not account.phone_valid:
            prob *= 0.70
        elif not account.email_valid:
            prob *= 0.85

        # Cap at realistic maximum
        return min(0.55, max(0.02, prob))

    def simulate_contact(
        self,
        account: MultiAgentAccount,
        params: SimulationParameters,
        day: int,
        channel_weights: ChannelWeights
    ) -> Tuple[bool, Decimal, str]:
        """
        Simulate a contact attempt.

        Returns: (success, amount_collected, outcome_type)
        """
        profile = SUB_1K_UNIVERSE[account.debt_type]
        balance = account.balance

        # Determine if we offer settlement or payment plan
        offer_settlement = (
            account.contact_attempts >= 3 or
            account.settlement_only or
            account.hardship_claim
        )
        offer_plan = (
            account.contact_attempts >= 2 and
            (account.needs_payment_plan or account.income_bracket == "low")
        )

        # Calculate conversion probability
        prob = self.calculate_conversion_probability(
            account, params, offer_settlement, offer_plan
        )

        # Check for negative outcomes first
        if account.dispute_prone and random.random() < 0.15:
            account.filed_dispute = True
            account.status = "disputed"
            return False, Decimal("0"), "dispute"

        if account.complaint_prone and random.random() < 0.10:
            account.filed_complaint = True
            prob *= 0.5  # Reduces willingness

        # Excessive contact may trigger cease communication
        if account.contact_attempts > params.max_contact_attempts * 0.8:
            if random.random() < 0.05:
                account.requested_cease_comm = True
                account.status = "cease_comm"
                return False, Decimal("0"), "cease_comm"

        # Check conversion
        if random.random() >= prob:
            return False, Decimal("0"), "no_response"

        # Successful contact - determine payment type
        amount = Decimal("0")
        outcome_type = "no_response"

        # Settlement path
        if offer_settlement and random.random() < 0.35:
            settlement_pct = random.uniform(
                params.settlement_threshold_pct,
                min(0.85, params.settlement_threshold_pct + 0.25)
            )
            amount = (balance * Decimal(str(settlement_pct))).quantize(Decimal("0.01"))
            outcome_type = "settlement"
            account.status = "settled"

        # Payment plan path
        elif offer_plan and random.random() < 0.30:
            # Set up payment plan
            monthly_payment = (balance / params.payment_plan_months).quantize(Decimal("0.01"))
            account.on_payment_plan = True
            account.plan_payments_remaining = params.payment_plan_months
            account.plan_payment_amount = monthly_payment

            # First payment
            amount = monthly_payment
            account.plan_payments_remaining -= 1
            outcome_type = "payment_plan"
            account.status = "on_plan"

        # Full payment
        elif random.random() < 0.80:
            amount = balance
            outcome_type = "full_payment"
            account.status = "collected"

        # Partial payment
        else:
            partial_pct = random.uniform(0.35, 0.75)
            amount = (balance * Decimal(str(partial_pct))).quantize(Decimal("0.01"))
            outcome_type = "partial"
            account.status = "partial"

        # Update account
        account.balance -= amount
        account.total_paid += amount
        account.payments_made += 1

        if account.first_payment_day < 0:
            account.first_payment_day = day

        # Digital payment - save method
        digital_prob = profile.digital_payment_rate
        if account.is_digital_native:
            digital_prob += 0.15
        if random.random() < min(0.95, digital_prob) and random.random() < 0.70:
            account.has_saved_payment = True

        if account.balance <= 0:
            account.status = "collected"

        return True, amount, outcome_type

    def process_payment_plans(
        self,
        accounts: List[MultiAgentAccount],
        day: int
    ) -> Tuple[Decimal, int, int]:
        """Process scheduled payment plan payments"""
        collected = Decimal("0")
        successful = 0
        failed = 0

        for account in accounts:
            if not account.on_payment_plan or account.plan_payments_remaining <= 0:
                continue

            # Monthly check (every 30 days)
            if day % 30 != 0:
                continue

            # Payment success probability
            prob = 0.75 + (account.payment_willingness * 0.20)
            if account.has_saved_payment:
                prob += 0.10

            if random.random() < prob:
                amount = account.plan_payment_amount
                account.balance -= amount
                account.total_paid += amount
                account.payments_made += 1
                account.plan_payments_remaining -= 1
                collected += amount
                successful += 1

                if account.plan_payments_remaining <= 0:
                    account.on_payment_plan = False
                    account.status = "collected"
            else:
                failed += 1
                # Give one retry
                if random.random() < 0.50:
                    account.plan_payments_remaining += 1  # Extend plan
                else:
                    account.on_payment_plan = False
                    account.status = "plan_defaulted"

        return collected, successful, failed

    def calculate_costs(
        self,
        metrics: SimulationMetrics,
        params: SimulationParameters,
        channel_weights: ChannelWeights,
        days_run: int
    ) -> Decimal:
        """Calculate total costs for simulation run"""
        # Channel costs
        sms_contacts = int(metrics.total_contacts * channel_weights.sms)
        email_contacts = int(metrics.total_contacts * channel_weights.email)
        push_contacts = int(metrics.total_contacts * channel_weights.push)

        channel_cost = (
            self.cost_params.cost_per_sms * sms_contacts +
            self.cost_params.cost_per_email * email_contacts +
            self.cost_params.cost_per_push * push_contacts
        )

        # Payment processing
        regular_payments = metrics.accounts_full_paid + metrics.accounts_partial
        payment_cost = self.cost_params.cost_per_payment * regular_payments

        # Settlement processing
        settlement_cost = self.cost_params.settlement_processing * metrics.settlement_count

        # Payment plan costs
        plan_setup_cost = self.cost_params.cost_per_payment_plan_setup * metrics.plan_count

        # Labor costs (prorated by account volume)
        utilization = min(1.0, self.num_accounts / 100000)  # 100K capacity
        labor_cost = (
            self.cost_params.cost_per_agent_day *
            self.cost_params.num_agents *
            days_run *
            Decimal(str(utilization))
        )

        # Platform and compliance overhead
        platform_cost = metrics.total_collected * self.cost_params.platform_pct
        compliance_cost = metrics.total_collected * self.cost_params.compliance_pct

        total_cost = (
            channel_cost + payment_cost + settlement_cost +
            plan_setup_cost + labor_cost + platform_cost + compliance_cost
        )

        return total_cost

    def calculate_satisfaction_score(
        self,
        account: MultiAgentAccount,
        params: SimulationParameters
    ) -> float:
        """Calculate customer satisfaction proxy score (0-100)"""
        score = self.SATISFACTION_FACTORS["base_satisfaction"]

        # Contact frequency impact
        excess_contacts = max(0, account.contact_attempts - 6)
        score += excess_contacts * self.SATISFACTION_FACTORS["per_extra_contact"]

        # Dispute and complaint impact
        if account.filed_dispute:
            score += self.SATISFACTION_FACTORS["dispute_penalty"]
        if account.filed_complaint:
            score += self.SATISFACTION_FACTORS["complaint_penalty"]

        # Positive outcomes
        if account.status == "settled":
            score += self.SATISFACTION_FACTORS["settlement_offer_bonus"]
        if account.on_payment_plan or account.status == "collected":
            score += self.SATISFACTION_FACTORS["payment_plan_bonus"]

        # Quick resolution bonus
        if account.first_payment_day > 0 and account.first_payment_day < 14:
            score += self.SATISFACTION_FACTORS["quick_resolution_bonus"]

        return max(0, min(100, score))

    async def run_single_simulation(
        self,
        accounts: List[MultiAgentAccount],
        params: SimulationParameters
    ) -> SimulationMetrics:
        """Run a single simulation with given parameters"""
        metrics = SimulationMetrics()
        channel_weights = ChannelWeights.from_strategy(params.channel_mix)

        # Track outcomes
        first_payment_days = []
        settlement_pcts = []
        satisfaction_scores = []

        metrics.total_accounts = len(accounts)
        metrics.total_balance = sum(a.original_balance for a in accounts)

        # Run simulation days
        for day in range(self.simulation_days):
            # Process existing payment plans
            plan_collected, _, _ = self.process_payment_plans(accounts, day)
            metrics.total_collected += plan_collected

            # Process active accounts
            for account in accounts:
                if account.status in ["collected", "settled", "disputed", "cease_comm"]:
                    continue

                # Check contact cadence
                days_since = day - account.last_contact_day
                if days_since < params.contact_cadence_days:
                    continue

                # Check contact limits
                should_contact = False

                if account.contact_attempts < params.max_contact_attempts:
                    should_contact = True
                elif (days_since > params.re_engagement_delay_days and
                      account.re_engagement_attempts < params.max_re_engagements):
                    should_contact = True
                    account.re_engagement_attempts += 1

                if not should_contact:
                    continue

                # Execute contact
                success, amount, outcome = self.simulate_contact(
                    account, params, day, channel_weights
                )

                account.contact_attempts += 1
                account.last_contact_day = day
                metrics.total_contacts += 1

                if success:
                    metrics.total_collected += amount

                    if account.first_payment_day > 0:
                        first_payment_days.append(account.first_payment_day)

                    if outcome == "settlement":
                        metrics.settlement_count += 1
                        pct = float(amount / account.original_balance)
                        settlement_pcts.append(pct)
                    elif outcome == "payment_plan":
                        metrics.plan_count += 1

                # Track negative outcomes
                if outcome == "dispute":
                    metrics.dispute_count += 1
                if account.filed_complaint:
                    metrics.complaint_count += 1
                if outcome == "cease_comm":
                    metrics.cease_comm_requests += 1

        # Calculate final metrics
        for account in accounts:
            if account.status == "collected":
                metrics.accounts_full_paid += 1
            elif account.status == "settled":
                metrics.accounts_settled += 1
            elif account.on_payment_plan:
                metrics.accounts_on_plan += 1
            elif account.status == "partial":
                metrics.accounts_partial += 1
            else:
                metrics.accounts_uncollected += 1

            # Satisfaction score
            sat_score = self.calculate_satisfaction_score(account, params)
            satisfaction_scores.append(sat_score)

        # Recovery metrics
        if metrics.total_balance > 0:
            metrics.recovery_rate = float(metrics.total_collected / metrics.total_balance)

        # Time metrics
        if first_payment_days:
            metrics.avg_time_to_first_payment = statistics.mean(first_payment_days)
            metrics.median_time_to_first_payment = statistics.median(first_payment_days)
            sorted_days = sorted(first_payment_days)
            p95_idx = int(len(sorted_days) * 0.95)
            metrics.time_to_first_payment_p95 = sorted_days[min(p95_idx, len(sorted_days)-1)]

        # Cost metrics
        metrics.total_cost = self.calculate_costs(
            metrics, params, channel_weights, self.simulation_days
        )

        if metrics.total_collected > 0:
            metrics.cost_per_dollar = float(metrics.total_cost / metrics.total_collected)
            net = metrics.total_collected - metrics.total_cost
            metrics.profit_margin = float(net / metrics.total_collected)
            metrics.roi = float(net / metrics.total_cost) if metrics.total_cost > 0 else 0

        # Contacts per recovery
        recovered = metrics.accounts_full_paid + metrics.accounts_settled + metrics.accounts_on_plan
        if recovered > 0:
            metrics.contacts_per_recovery = metrics.total_contacts / recovered

        # Settlement metrics
        if settlement_pcts:
            metrics.avg_settlement_pct = statistics.mean(settlement_pcts)

        # Payment plan completion (estimate)
        if metrics.plan_count > 0:
            completed_plans = sum(1 for a in accounts if a.status == "collected" and a.payments_made > 1)
            metrics.plan_completion_rate = completed_plans / metrics.plan_count

        # Satisfaction score
        if satisfaction_scores:
            metrics.satisfaction_score = statistics.mean(satisfaction_scores)

        return metrics

    async def run_parameter_sweep(self) -> Dict[str, ResultsMatrixEntry]:
        """Run full parameter sweep with bootstrap confidence intervals"""

        # Define parameter combinations
        cadences = [3, 5, 7, 10]
        max_contacts = [6, 9, 12, 15]
        channel_mixes = [ChannelMix.SMS_FIRST, ChannelMix.EMAIL_FIRST, ChannelMix.BALANCED]
        settlement_thresholds = [0.40, 0.50, 0.60, 0.70]
        payment_plans = [2, 3, 6]

        # Generate all combinations
        all_combinations = list(itertools.product(
            cadences, max_contacts, channel_mixes, settlement_thresholds, payment_plans
        ))

        total_combinations = len(all_combinations)
        print(f"\n{'='*80}")
        print("  QUAN MULTI-VARIABLE COLLECTION SIMULATION")
        print(f"{'='*80}")
        print(f"\n  Configuration:")
        print(f"    Accounts:        {self.num_accounts:,}")
        print(f"    Simulation Days: {self.simulation_days}")
        print(f"    Bootstrap Runs:  {self.bootstrap_iterations}")
        print(f"    Combinations:    {total_combinations}")
        print(f"\n  Parameter Space:")
        print(f"    Cadences:        {cadences}")
        print(f"    Max Contacts:    {max_contacts}")
        print(f"    Channel Mixes:   {[c.value for c in channel_mixes]}")
        print(f"    Settlement %:    {[int(s*100) for s in settlement_thresholds]}")
        print(f"    Payment Plans:   {payment_plans} months")

        print(f"\n  Running {total_combinations * self.bootstrap_iterations} total simulations...")
        print("-" * 80)

        # Generate base portfolio once
        base_accounts = self.generate_portfolio()

        results = {}

        for combo_idx, (cad, max_c, ch_mix, settle, plan) in enumerate(all_combinations):
            params = SimulationParameters(
                contact_cadence_days=cad,
                max_contact_attempts=max_c,
                channel_mix=ch_mix,
                settlement_threshold_pct=settle,
                payment_plan_months=plan
            )

            param_key = params.get_param_key()

            # Bootstrap iterations for confidence intervals
            recovery_samples = []
            cost_samples = []
            time_samples = []
            satisfaction_samples = []

            aggregated_metrics = None

            for boot_iter in range(self.bootstrap_iterations):
                # Reset accounts for each iteration
                accounts = self.reset_accounts(base_accounts)

                # Run simulation
                metrics = await self.run_single_simulation(accounts, params)

                recovery_samples.append(metrics.recovery_rate)
                cost_samples.append(metrics.cost_per_dollar)
                time_samples.append(metrics.avg_time_to_first_payment)
                satisfaction_samples.append(metrics.satisfaction_score)

                if aggregated_metrics is None:
                    aggregated_metrics = metrics
                else:
                    # Average the metrics
                    aggregated_metrics.recovery_rate = (
                        aggregated_metrics.recovery_rate * boot_iter + metrics.recovery_rate
                    ) / (boot_iter + 1)
                    aggregated_metrics.cost_per_dollar = (
                        aggregated_metrics.cost_per_dollar * boot_iter + metrics.cost_per_dollar
                    ) / (boot_iter + 1)

            # Store samples in metrics
            aggregated_metrics.recovery_samples = recovery_samples
            aggregated_metrics.cost_samples = cost_samples
            aggregated_metrics.time_samples = time_samples

            # Calculate confidence intervals
            recovery_ci = ConfidenceInterval.from_samples(recovery_samples)
            cost_ci = ConfidenceInterval.from_samples(cost_samples)
            time_ci = ConfidenceInterval.from_samples(time_samples)
            satisfaction_ci = ConfidenceInterval.from_samples(satisfaction_samples)

            entry = ResultsMatrixEntry(
                parameters=params,
                metrics=aggregated_metrics,
                recovery_ci=recovery_ci,
                cost_ci=cost_ci,
                time_ci=time_ci,
                satisfaction_ci=satisfaction_ci
            )

            results[param_key] = entry

            # Progress output
            if (combo_idx + 1) % 20 == 0 or combo_idx == 0:
                print(f"  [{combo_idx+1:3d}/{total_combinations}] "
                      f"Cad:{cad} Max:{max_c:2d} Ch:{ch_mix.value:12s} "
                      f"Set:{int(settle*100)}% Plan:{plan}mo | "
                      f"Rec:{recovery_ci.mean*100:5.1f}% "
                      f"[{recovery_ci.ci_lower*100:.1f}-{recovery_ci.ci_upper*100:.1f}] "
                      f"Cost:${cost_ci.mean:.3f}")

        self.results_matrix = results
        return results

    def rank_results(self) -> List[ResultsMatrixEntry]:
        """Rank results by composite score"""
        entries = list(self.results_matrix.values())

        # Calculate composite scores
        # Weights: Recovery 35%, Cost 25%, Time 20%, Satisfaction 20%
        weights = {
            "recovery": 0.35,
            "cost": 0.25,
            "time": 0.20,
            "satisfaction": 0.20
        }

        # Normalize metrics
        recovery_vals = [e.recovery_ci.mean for e in entries]
        cost_vals = [e.cost_ci.mean for e in entries]
        time_vals = [e.time_ci.mean for e in entries]
        sat_vals = [e.satisfaction_ci.mean for e in entries]

        max_recovery = max(recovery_vals) if recovery_vals else 1
        min_cost = min(cost_vals) if cost_vals else 0.01
        max_cost = max(cost_vals) if cost_vals else 1
        min_time = min(time_vals) if time_vals else 1
        max_time = max(time_vals) if time_vals else 30
        max_sat = max(sat_vals) if sat_vals else 100

        for entry in entries:
            # Higher recovery is better (normalize 0-1)
            recovery_score = entry.recovery_ci.mean / max_recovery if max_recovery > 0 else 0

            # Lower cost is better (invert and normalize)
            cost_range = max_cost - min_cost
            cost_score = 1 - (entry.cost_ci.mean - min_cost) / cost_range if cost_range > 0 else 0.5

            # Lower time is better (invert and normalize)
            time_range = max_time - min_time
            time_score = 1 - (entry.time_ci.mean - min_time) / time_range if time_range > 0 else 0.5

            # Higher satisfaction is better
            sat_score = entry.satisfaction_ci.mean / max_sat if max_sat > 0 else 0

            entry.overall_score = (
                weights["recovery"] * recovery_score +
                weights["cost"] * cost_score +
                weights["time"] * time_score +
                weights["satisfaction"] * sat_score
            )

        # Sort by overall score
        entries.sort(key=lambda x: x.overall_score, reverse=True)

        # Assign ranks
        for i, entry in enumerate(entries):
            entry.recovery_rank = sorted(
                range(len(entries)),
                key=lambda x: entries[x].recovery_ci.mean,
                reverse=True
            ).index(i) + 1
            entry.cost_rank = sorted(
                range(len(entries)),
                key=lambda x: entries[x].cost_ci.mean
            ).index(i) + 1
            entry.time_rank = sorted(
                range(len(entries)),
                key=lambda x: entries[x].time_ci.mean
            ).index(i) + 1
            entry.satisfaction_rank = sorted(
                range(len(entries)),
                key=lambda x: entries[x].satisfaction_ci.mean,
                reverse=True
            ).index(i) + 1

        return entries

    def print_results_matrix(self, top_n: int = 20):
        """Print comprehensive results matrix"""
        ranked = self.rank_results()

        print(f"\n{'='*100}")
        print("  RESULTS MATRIX - OPTIMAL PARAMETER COMBINATIONS")
        print(f"{'='*100}")

        # Summary statistics
        all_recoveries = [e.recovery_ci.mean for e in ranked]
        all_costs = [e.cost_ci.mean for e in ranked]

        print(f"\n  SUMMARY STATISTICS (across {len(ranked)} combinations):")
        print(f"    Recovery Rate:  Min {min(all_recoveries)*100:.1f}%, "
              f"Max {max(all_recoveries)*100:.1f}%, "
              f"Avg {statistics.mean(all_recoveries)*100:.1f}%")
        print(f"    Cost per $1:    Min ${min(all_costs):.3f}, "
              f"Max ${max(all_costs):.3f}, "
              f"Avg ${statistics.mean(all_costs):.3f}")

        # Top results table
        print(f"\n  TOP {top_n} PARAMETER COMBINATIONS:")
        print("  " + "-" * 96)
        print(f"  {'Rank':<5} {'Cadence':>7} {'MaxCont':>7} {'Channel':>12} {'Settle':>7} "
              f"{'Plan':>5} {'Recovery':>12} {'Cost/$':>10} {'Time':>8} {'Sat':>6} {'Score':>7}")
        print("  " + "-" * 96)

        for i, entry in enumerate(ranked[:top_n]):
            p = entry.parameters
            r = entry.recovery_ci
            c = entry.cost_ci
            t = entry.time_ci
            s = entry.satisfaction_ci

            recovery_str = f"{r.mean*100:.1f}%"
            ci_str = f"[{r.ci_lower*100:.1f}-{r.ci_upper*100:.1f}]"

            print(f"  {i+1:<5} {p.contact_cadence_days:>5}d  {p.max_contact_attempts:>7} "
                  f"{p.channel_mix.value:>12} {int(p.settlement_threshold_pct*100):>6}% "
                  f"{p.payment_plan_months:>4}mo "
                  f"{recovery_str:>6} {ci_str:<6} "
                  f"${c.mean:>8.3f} {t.mean:>7.1f}d {s.mean:>5.0f} "
                  f"{entry.overall_score:>7.3f}")

        print("  " + "-" * 96)

        # Best by metric
        print(f"\n  BEST BY INDIVIDUAL METRIC:")

        best_recovery = max(ranked, key=lambda x: x.recovery_ci.mean)
        best_cost = min(ranked, key=lambda x: x.cost_ci.mean)
        best_time = min(ranked, key=lambda x: x.time_ci.mean)
        best_sat = max(ranked, key=lambda x: x.satisfaction_ci.mean)

        def format_params(p):
            return f"Cad:{p.contact_cadence_days}d Max:{p.max_contact_attempts} Ch:{p.channel_mix.value} Set:{int(p.settlement_threshold_pct*100)}% Plan:{p.payment_plan_months}mo"

        print(f"    Best Recovery:     {best_recovery.recovery_ci.mean*100:.1f}% | {format_params(best_recovery.parameters)}")
        print(f"    Best Cost:         ${best_cost.cost_ci.mean:.3f}  | {format_params(best_cost.parameters)}")
        print(f"    Best Time:         {best_time.time_ci.mean:.1f}d   | {format_params(best_time.parameters)}")
        print(f"    Best Satisfaction: {best_sat.satisfaction_ci.mean:.0f}    | {format_params(best_sat.parameters)}")

        # Pareto optimal solutions
        print(f"\n  PARETO OPTIMAL SOLUTIONS (non-dominated):")
        pareto = self._find_pareto_optimal(ranked)
        print("  " + "-" * 96)

        for i, entry in enumerate(pareto[:10]):
            p = entry.parameters
            r = entry.recovery_ci
            c = entry.cost_ci

            print(f"  {i+1:<3} Cad:{p.contact_cadence_days}d Max:{p.max_contact_attempts:2d} "
                  f"Ch:{p.channel_mix.value:12s} Set:{int(p.settlement_threshold_pct*100)}% "
                  f"Plan:{p.payment_plan_months}mo | "
                  f"Rec:{r.mean*100:.1f}% Cost:${c.mean:.3f} "
                  f"ROI:{entry.metrics.roi*100:.0f}%")

        # Analysis by parameter
        print(f"\n  PARAMETER IMPACT ANALYSIS:")
        self._analyze_parameter_impact(ranked)

        print(f"\n{'='*100}")

        return ranked

    def _find_pareto_optimal(self, entries: List[ResultsMatrixEntry]) -> List[ResultsMatrixEntry]:
        """Find Pareto optimal solutions (maximize recovery, minimize cost)"""
        pareto = []

        for entry in entries:
            dominated = False
            for other in entries:
                if (other.recovery_ci.mean > entry.recovery_ci.mean and
                    other.cost_ci.mean <= entry.cost_ci.mean):
                    dominated = True
                    break
                if (other.recovery_ci.mean >= entry.recovery_ci.mean and
                    other.cost_ci.mean < entry.cost_ci.mean):
                    dominated = True
                    break

            if not dominated:
                pareto.append(entry)

        pareto.sort(key=lambda x: x.recovery_ci.mean, reverse=True)
        return pareto

    def _analyze_parameter_impact(self, ranked: List[ResultsMatrixEntry]):
        """Analyze impact of each parameter on outcomes"""

        # Cadence impact
        cadence_recovery = {}
        for entry in ranked:
            cad = entry.parameters.contact_cadence_days
            if cad not in cadence_recovery:
                cadence_recovery[cad] = []
            cadence_recovery[cad].append(entry.recovery_ci.mean)

        print(f"\n    Contact Cadence Impact:")
        for cad in sorted(cadence_recovery.keys()):
            avg = statistics.mean(cadence_recovery[cad]) * 100
            print(f"      {cad} days: {avg:.1f}% avg recovery")

        # Max contacts impact
        contacts_recovery = {}
        for entry in ranked:
            max_c = entry.parameters.max_contact_attempts
            if max_c not in contacts_recovery:
                contacts_recovery[max_c] = []
            contacts_recovery[max_c].append(entry.recovery_ci.mean)

        print(f"\n    Max Contacts Impact:")
        for max_c in sorted(contacts_recovery.keys()):
            avg = statistics.mean(contacts_recovery[max_c]) * 100
            print(f"      {max_c} attempts: {avg:.1f}% avg recovery")

        # Channel mix impact
        channel_recovery = {}
        for entry in ranked:
            ch = entry.parameters.channel_mix.value
            if ch not in channel_recovery:
                channel_recovery[ch] = []
            channel_recovery[ch].append(entry.recovery_ci.mean)

        print(f"\n    Channel Mix Impact:")
        for ch in sorted(channel_recovery.keys()):
            avg = statistics.mean(channel_recovery[ch]) * 100
            print(f"      {ch}: {avg:.1f}% avg recovery")

        # Settlement threshold impact
        settle_recovery = {}
        for entry in ranked:
            settle = int(entry.parameters.settlement_threshold_pct * 100)
            if settle not in settle_recovery:
                settle_recovery[settle] = []
            settle_recovery[settle].append(entry.recovery_ci.mean)

        print(f"\n    Settlement Threshold Impact:")
        for settle in sorted(settle_recovery.keys()):
            avg = statistics.mean(settle_recovery[settle]) * 100
            print(f"      {settle}%: {avg:.1f}% avg recovery")

        # Payment plan impact
        plan_recovery = {}
        for entry in ranked:
            plan = entry.parameters.payment_plan_months
            if plan not in plan_recovery:
                plan_recovery[plan] = []
            plan_recovery[plan].append(entry.recovery_ci.mean)

        print(f"\n    Payment Plan Term Impact:")
        for plan in sorted(plan_recovery.keys()):
            avg = statistics.mean(plan_recovery[plan]) * 100
            print(f"      {plan} months: {avg:.1f}% avg recovery")


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_multi_variable_simulation():
    """Run the full multi-variable collection simulation"""

    # Configure simulation
    simulator = MultiVariableSimulator(
        num_accounts=50000,
        simulation_days=90,
        bootstrap_iterations=5
    )

    # Run parameter sweep
    results = await simulator.run_parameter_sweep()

    # Print results matrix
    ranked = simulator.print_results_matrix(top_n=25)

    # Print top recommendation
    if ranked:
        best = ranked[0]
        p = best.parameters

        print(f"\n  RECOMMENDED OPTIMAL CONFIGURATION:")
        print(f"  " + "=" * 50)
        print(f"    Contact Cadence:     {p.contact_cadence_days} days")
        print(f"    Max Contact Attempts: {p.max_contact_attempts}")
        print(f"    Channel Strategy:    {p.channel_mix.value}")
        print(f"    Settlement Floor:    {int(p.settlement_threshold_pct * 100)}%")
        print(f"    Payment Plan Term:   {p.payment_plan_months} months")
        print(f"\n  EXPECTED PERFORMANCE:")
        print(f"    Recovery Rate:       {best.recovery_ci.mean*100:.1f}% "
              f"[95% CI: {best.recovery_ci.ci_lower*100:.1f}%-{best.recovery_ci.ci_upper*100:.1f}%]")
        print(f"    Cost per Dollar:     ${best.cost_ci.mean:.3f} "
              f"[95% CI: ${best.cost_ci.ci_lower:.3f}-${best.cost_ci.ci_upper:.3f}]")
        print(f"    Time to Payment:     {best.time_ci.mean:.1f} days")
        print(f"    Satisfaction Score:  {best.satisfaction_ci.mean:.0f}/100")
        print(f"    ROI:                 {best.metrics.roi*100:.0f}%")
        print(f"  " + "=" * 50)

    return simulator, ranked


if __name__ == "__main__":
    asyncio.run(run_multi_variable_simulation())
