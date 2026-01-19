"""
Lifecycle ROI Optimizer

Comprehensive account lifecycle modeling and portfolio optimization engine.
Calculates full-stack economics including:
- Acquisition costs
- Processing costs by stage
- Channel costs
- Payment processing fees
- Compliance overhead
- Re-engagement costs

Optimizes portfolio mix for maximum ROI with segment-level P&L analysis.

Calibrated Baseline Metrics:
- Cost per dollar collected: $0.21
- Profit margin: 78%
- ROI: 371%
"""

import asyncio
import random
import statistics
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# COST STRUCTURE MODELS
# =============================================================================

@dataclass
class AcquisitionCosts:
    """Costs to acquire and onboard a debt portfolio"""
    purchase_price_pct: float = 0.08  # 8 cents on the dollar for micro-debt
    data_enrichment: Decimal = Decimal("0.15")  # Per account
    skip_tracing: Decimal = Decimal("0.25")  # Per account requiring trace
    skip_trace_rate: float = 0.35  # % needing skip trace
    onboarding_overhead: Decimal = Decimal("0.05")  # Per account


@dataclass
class ProcessingCosts:
    """Costs by collection stage"""
    # Initial outreach stage
    initial_setup: Decimal = Decimal("0.02")  # Per account
    initial_contact_cost: Decimal = Decimal("0.015")  # Per contact

    # Active collection stage
    active_monitoring: Decimal = Decimal("0.01")  # Per account/day
    escalation_cost: Decimal = Decimal("0.05")  # Per escalation

    # Payment processing stage
    payment_setup: Decimal = Decimal("0.10")  # Per payment method setup
    payment_processing_pct: float = 0.029  # 2.9% of payment
    payment_processing_fixed: Decimal = Decimal("0.30")  # Fixed per transaction

    # Resolution stage
    settlement_processing: Decimal = Decimal("0.50")  # Per settlement
    dispute_handling: Decimal = Decimal("2.50")  # Per dispute

    # Account closure
    closure_processing: Decimal = Decimal("0.05")  # Per closed account


@dataclass
class ChannelCosts:
    """Costs per communication channel"""
    sms_cost: Decimal = Decimal("0.02")
    email_cost: Decimal = Decimal("0.005")
    push_notification: Decimal = Decimal("0.01")
    voice_outbound: Decimal = Decimal("0.15")  # Automated IVR
    voice_agent: Decimal = Decimal("2.50")  # Live agent call
    letter_mail: Decimal = Decimal("0.85")  # Physical mail

    # Channel mix weights (digital-first strategy)
    sms_weight: float = 0.50
    email_weight: float = 0.35
    push_weight: float = 0.10
    voice_weight: float = 0.03
    mail_weight: float = 0.02


@dataclass
class ComplianceCosts:
    """Regulatory compliance overhead"""
    base_compliance_pct: float = 0.015  # 1.5% of collections
    tcpa_compliance: Decimal = Decimal("0.005")  # Per contact
    fcra_compliance: Decimal = Decimal("0.01")  # Per account
    state_licensing: Decimal = Decimal("0.002")  # Per account (amortized)
    audit_reserve_pct: float = 0.005  # 0.5% reserve for audits
    legal_reserve_pct: float = 0.01  # 1% reserve for legal


@dataclass
class ReEngagementCosts:
    """Costs for re-engaging broken/dormant plans"""
    campaign_setup: Decimal = Decimal("0.10")  # Per campaign
    per_attempt_cost: Decimal = Decimal("0.03")  # Per re-engagement attempt
    incentive_cost_pct: float = 0.05  # 5% discount/incentive
    win_back_overhead: Decimal = Decimal("0.25")  # Successful win-back processing


@dataclass
class LifecycleCostModel:
    """Complete lifecycle cost structure"""
    acquisition: AcquisitionCosts = field(default_factory=AcquisitionCosts)
    processing: ProcessingCosts = field(default_factory=ProcessingCosts)
    channels: ChannelCosts = field(default_factory=ChannelCosts)
    compliance: ComplianceCosts = field(default_factory=ComplianceCosts)
    re_engagement: ReEngagementCosts = field(default_factory=ReEngagementCosts)

    # Agent/platform costs
    agent_cost_per_day: Decimal = Decimal("120")  # Per agent
    platform_cost_pct: float = 0.03  # 3% platform overhead

    # Target calibration
    target_cost_per_dollar: float = 0.21
    target_margin: float = 0.78
    target_roi: float = 3.71


# =============================================================================
# SEGMENT DEFINITIONS
# =============================================================================

class DebtTypeSegment(Enum):
    """Debt type segments for analysis"""
    BNPL = "buy_now_pay_later"
    SUBSCRIPTION = "subscription"
    UTILITY = "utility"
    TELECOM = "telecom"
    MEDICAL_SMALL = "medical_small"
    PAYDAY = "payday"
    RETAIL = "retail"
    PERSONAL_MICRO = "personal_micro"


class BalanceTier(Enum):
    """Balance tiers for profitability analysis"""
    MICRO = "micro"          # $0-100
    SMALL = "small"          # $100-250
    MEDIUM = "medium"        # $250-500
    STANDARD = "standard"    # $500-750
    UPPER = "upper"          # $750-1000


@dataclass
class SegmentProfile:
    """Profile for each debt segment"""
    segment: DebtTypeSegment
    name: str
    min_balance: Decimal
    max_balance: Decimal
    base_recovery_rate: float
    avg_contacts_to_convert: float
    digital_rate: float
    dispute_rate: float
    avg_days_to_collect: int
    payment_plan_rate: float
    re_engagement_success: float


# Segment profiles with realistic characteristics
SEGMENT_PROFILES: Dict[DebtTypeSegment, SegmentProfile] = {
    DebtTypeSegment.BNPL: SegmentProfile(
        segment=DebtTypeSegment.BNPL,
        name="Buy Now Pay Later",
        min_balance=Decimal("25"),
        max_balance=Decimal("500"),
        base_recovery_rate=0.38,
        avg_contacts_to_convert=3.2,
        digital_rate=0.88,
        dispute_rate=0.12,
        avg_days_to_collect=21,
        payment_plan_rate=0.25,
        re_engagement_success=0.35
    ),
    DebtTypeSegment.SUBSCRIPTION: SegmentProfile(
        segment=DebtTypeSegment.SUBSCRIPTION,
        name="Subscription Services",
        min_balance=Decimal("20"),
        max_balance=Decimal("300"),
        base_recovery_rate=0.45,
        avg_contacts_to_convert=2.5,
        digital_rate=0.92,
        dispute_rate=0.15,
        avg_days_to_collect=18,
        payment_plan_rate=0.15,
        re_engagement_success=0.40
    ),
    DebtTypeSegment.UTILITY: SegmentProfile(
        segment=DebtTypeSegment.UTILITY,
        name="Utility Arrears",
        min_balance=Decimal("50"),
        max_balance=Decimal("600"),
        base_recovery_rate=0.42,
        avg_contacts_to_convert=4.0,
        digital_rate=0.58,
        dispute_rate=0.10,
        avg_days_to_collect=32,
        payment_plan_rate=0.45,
        re_engagement_success=0.30
    ),
    DebtTypeSegment.TELECOM: SegmentProfile(
        segment=DebtTypeSegment.TELECOM,
        name="Telecom Debt",
        min_balance=Decimal("50"),
        max_balance=Decimal("500"),
        base_recovery_rate=0.35,
        avg_contacts_to_convert=4.5,
        digital_rate=0.75,
        dispute_rate=0.18,
        avg_days_to_collect=35,
        payment_plan_rate=0.35,
        re_engagement_success=0.28
    ),
    DebtTypeSegment.MEDICAL_SMALL: SegmentProfile(
        segment=DebtTypeSegment.MEDICAL_SMALL,
        name="Small Medical Debt",
        min_balance=Decimal("50"),
        max_balance=Decimal("1000"),
        base_recovery_rate=0.28,
        avg_contacts_to_convert=5.5,
        digital_rate=0.52,
        dispute_rate=0.12,
        avg_days_to_collect=45,
        payment_plan_rate=0.55,
        re_engagement_success=0.22
    ),
    DebtTypeSegment.PAYDAY: SegmentProfile(
        segment=DebtTypeSegment.PAYDAY,
        name="Payday Loans",
        min_balance=Decimal("50"),
        max_balance=Decimal("500"),
        base_recovery_rate=0.32,
        avg_contacts_to_convert=4.0,
        digital_rate=0.70,
        dispute_rate=0.08,
        avg_days_to_collect=28,
        payment_plan_rate=0.40,
        re_engagement_success=0.32
    ),
    DebtTypeSegment.RETAIL: SegmentProfile(
        segment=DebtTypeSegment.RETAIL,
        name="Retail Credit",
        min_balance=Decimal("50"),
        max_balance=Decimal("800"),
        base_recovery_rate=0.38,
        avg_contacts_to_convert=4.2,
        digital_rate=0.70,
        dispute_rate=0.10,
        avg_days_to_collect=38,
        payment_plan_rate=0.35,
        re_engagement_success=0.30
    ),
    DebtTypeSegment.PERSONAL_MICRO: SegmentProfile(
        segment=DebtTypeSegment.PERSONAL_MICRO,
        name="Personal Micro-Loans",
        min_balance=Decimal("100"),
        max_balance=Decimal("1000"),
        base_recovery_rate=0.40,
        avg_contacts_to_convert=4.8,
        digital_rate=0.72,
        dispute_rate=0.05,
        avg_days_to_collect=42,
        payment_plan_rate=0.50,
        re_engagement_success=0.28
    ),
}


BALANCE_TIER_BOUNDS: Dict[BalanceTier, Tuple[Decimal, Decimal]] = {
    BalanceTier.MICRO: (Decimal("0"), Decimal("100")),
    BalanceTier.SMALL: (Decimal("100"), Decimal("250")),
    BalanceTier.MEDIUM: (Decimal("250"), Decimal("500")),
    BalanceTier.STANDARD: (Decimal("500"), Decimal("750")),
    BalanceTier.UPPER: (Decimal("750"), Decimal("1000")),
}


# =============================================================================
# ACCOUNT LIFECYCLE MODEL
# =============================================================================

@dataclass
class AccountLifecycle:
    """Complete account lifecycle tracking"""
    account_id: str
    segment: DebtTypeSegment
    balance_tier: BalanceTier
    original_balance: Decimal
    current_balance: Decimal

    # Acquisition phase
    acquisition_cost: Decimal = Decimal("0")

    # Collection phase
    contact_attempts: int = 0
    contacts_by_channel: Dict[str, int] = field(default_factory=dict)
    processing_cost: Decimal = Decimal("0")
    channel_cost: Decimal = Decimal("0")

    # Payment phase
    payments_made: int = 0
    total_collected: Decimal = Decimal("0")
    payment_processing_cost: Decimal = Decimal("0")
    is_digital_payment: bool = False
    has_payment_plan: bool = False

    # Compliance
    compliance_cost: Decimal = Decimal("0")
    had_dispute: bool = False
    dispute_cost: Decimal = Decimal("0")

    # Re-engagement
    re_engagement_attempts: int = 0
    re_engagement_cost: Decimal = Decimal("0")
    was_re_engaged: bool = False

    # Status
    status: str = "active"  # active, partial, collected, written_off
    days_to_collect: int = 0
    collection_day: int = -1
    last_contact_day: int = -1  # Track last contact for cadence

    def total_cost(self) -> Decimal:
        """Calculate total lifecycle cost"""
        return (
            self.acquisition_cost +
            self.processing_cost +
            self.channel_cost +
            self.payment_processing_cost +
            self.compliance_cost +
            self.dispute_cost +
            self.re_engagement_cost
        )

    def net_margin(self) -> Decimal:
        """Calculate net margin"""
        if self.total_collected > 0:
            return self.total_collected - self.total_cost()
        return Decimal("0") - self.total_cost()

    def roi_multiple(self) -> float:
        """Calculate ROI multiple"""
        cost = self.total_cost()
        if cost > 0:
            return float((self.total_collected - cost) / cost)
        return 0.0


@dataclass
class SegmentMetrics:
    """Aggregated metrics for a segment"""
    segment_name: str
    accounts: int = 0
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")

    # Calculated metrics
    ltv: Decimal = Decimal("0")  # Lifetime value per account
    cost_to_collect: Decimal = Decimal("0")  # Cost per dollar collected
    net_margin: Decimal = Decimal("0")
    net_margin_pct: float = 0.0
    roi_multiple: float = 0.0
    payback_period_days: float = 0.0

    # Operational metrics
    avg_contacts: float = 0.0
    digital_rate: float = 0.0
    avg_days_to_collect: float = 0.0
    recovery_rate: float = 0.0

    # Breakdown
    accounts_collected: int = 0
    accounts_partial: int = 0
    accounts_written_off: int = 0


@dataclass
class PortfolioOptimization:
    """Portfolio optimization recommendations"""
    # Debt type prioritization
    debt_type_ranking: List[Tuple[str, float, str]] = field(default_factory=list)

    # Balance tier profitability
    balance_tier_ranking: List[Tuple[str, float, str]] = field(default_factory=list)

    # Optimal cutoffs
    optimal_contact_cutoff: int = 0
    optimal_day_cutoff: int = 0
    optimal_cost_threshold: Decimal = Decimal("0")

    # Re-engagement thresholds
    re_engagement_min_balance: Decimal = Decimal("0")
    re_engagement_max_attempts: int = 0
    write_off_threshold_days: int = 0

    # Capital efficiency
    capital_efficiency_score: float = 0.0
    recommended_portfolio_mix: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# LIFECYCLE ROI OPTIMIZER
# =============================================================================

class LifecycleROIOptimizer:
    """
    Complete lifecycle ROI optimization engine.

    Models full account economics and optimizes portfolio for maximum returns.
    """

    # Calibrated baselines
    BASELINE_COST_PER_DOLLAR = 0.21
    BASELINE_MARGIN = 0.78
    BASELINE_ROI = 3.71

    def __init__(self, cost_model: Optional[LifecycleCostModel] = None):
        self.cost_model = cost_model or LifecycleCostModel()
        self.accounts: List[AccountLifecycle] = []
        self.segment_metrics: Dict[str, SegmentMetrics] = {}
        self.tier_metrics: Dict[str, SegmentMetrics] = {}
        self.optimization: Optional[PortfolioOptimization] = None

        # Simulation tracking
        self.daily_collections: List[Decimal] = []
        self.daily_costs: List[Decimal] = []
        self.cumulative_roi: List[float] = []

    def _get_balance_tier(self, balance: Decimal) -> BalanceTier:
        """Determine balance tier for an account"""
        for tier, (min_bal, max_bal) in BALANCE_TIER_BOUNDS.items():
            if min_bal <= balance < max_bal:
                return tier
        return BalanceTier.UPPER  # Default for >= $750

    def _calculate_acquisition_cost(
        self,
        balance: Decimal,
        needs_skip_trace: bool
    ) -> Decimal:
        """Calculate acquisition cost for an account"""
        acq = self.cost_model.acquisition

        # Purchase price
        purchase = balance * Decimal(str(acq.purchase_price_pct))

        # Data enrichment
        enrichment = acq.data_enrichment

        # Skip tracing (if needed)
        skip = acq.skip_tracing if needs_skip_trace else Decimal("0")

        # Onboarding overhead
        overhead = acq.onboarding_overhead

        return (purchase + enrichment + skip + overhead).quantize(Decimal("0.01"))

    def _calculate_channel_cost(
        self,
        num_contacts: int,
        channel_mix: Optional[Dict[str, float]] = None
    ) -> Tuple[Decimal, Dict[str, int]]:
        """Calculate channel costs for contacts"""
        ch = self.cost_model.channels

        if channel_mix is None:
            channel_mix = {
                "sms": ch.sms_weight,
                "email": ch.email_weight,
                "push": ch.push_weight,
                "voice": ch.voice_weight,
                "mail": ch.mail_weight
            }

        cost = Decimal("0")
        contacts_by_channel = {}

        for channel, weight in channel_mix.items():
            count = int(num_contacts * weight)
            contacts_by_channel[channel] = count

            if channel == "sms":
                cost += ch.sms_cost * count
            elif channel == "email":
                cost += ch.email_cost * count
            elif channel == "push":
                cost += ch.push_notification * count
            elif channel == "voice":
                # Mix of IVR and agent
                ivr_count = int(count * 0.8)
                agent_count = count - ivr_count
                cost += ch.voice_outbound * ivr_count
                cost += ch.voice_agent * agent_count
            elif channel == "mail":
                cost += ch.letter_mail * count

        return cost.quantize(Decimal("0.01")), contacts_by_channel

    def _calculate_payment_processing_cost(
        self,
        amount: Decimal,
        is_plan: bool = False
    ) -> Decimal:
        """Calculate payment processing costs"""
        proc = self.cost_model.processing

        # Percentage fee
        pct_fee = amount * Decimal(str(proc.payment_processing_pct))

        # Fixed fee
        fixed_fee = proc.payment_processing_fixed

        # Setup cost for payment plans
        setup = proc.payment_setup if is_plan else Decimal("0")

        return (pct_fee + fixed_fee + setup).quantize(Decimal("0.01"))

    def _calculate_compliance_cost(
        self,
        amount_collected: Decimal,
        num_contacts: int,
        had_dispute: bool
    ) -> Tuple[Decimal, Decimal]:
        """Calculate compliance costs"""
        comp = self.cost_model.compliance

        # Base compliance overhead
        base = amount_collected * Decimal(str(comp.base_compliance_pct))

        # Per-contact TCPA compliance
        tcpa = comp.tcpa_compliance * num_contacts

        # FCRA compliance
        fcra = comp.fcra_compliance

        # State licensing (amortized)
        state = comp.state_licensing

        # Reserves
        audit_reserve = amount_collected * Decimal(str(comp.audit_reserve_pct))
        legal_reserve = amount_collected * Decimal(str(comp.legal_reserve_pct))

        compliance_cost = (base + tcpa + fcra + state + audit_reserve + legal_reserve).quantize(Decimal("0.01"))

        # Dispute handling cost (if applicable)
        dispute_cost = self.cost_model.processing.dispute_handling if had_dispute else Decimal("0")

        return compliance_cost, dispute_cost

    def _calculate_re_engagement_cost(
        self,
        attempts: int,
        collected_amount: Decimal
    ) -> Decimal:
        """Calculate re-engagement costs"""
        re = self.cost_model.re_engagement

        if attempts == 0:
            return Decimal("0")

        # Campaign setup
        setup = re.campaign_setup

        # Per-attempt costs
        attempt_cost = re.per_attempt_cost * attempts

        # Incentive cost (discount on collected)
        if collected_amount > 0:
            incentive = collected_amount * Decimal(str(re.incentive_cost_pct))
            overhead = re.win_back_overhead
        else:
            incentive = Decimal("0")
            overhead = Decimal("0")

        return (setup + attempt_cost + incentive + overhead).quantize(Decimal("0.01"))

    def generate_account(
        self,
        account_id: str,
        segment: DebtTypeSegment
    ) -> AccountLifecycle:
        """Generate a single account with realistic characteristics"""
        profile = SEGMENT_PROFILES[segment]

        # Generate balance
        raw = random.random() ** 0.6  # Skew toward lower
        balance = (
            profile.min_balance +
            Decimal(str(raw)) * (profile.max_balance - profile.min_balance)
        ).quantize(Decimal("0.01"))

        tier = self._get_balance_tier(balance)

        # Calculate acquisition cost
        needs_skip = random.random() < self.cost_model.acquisition.skip_trace_rate
        acq_cost = self._calculate_acquisition_cost(balance, needs_skip)

        return AccountLifecycle(
            account_id=account_id,
            segment=segment,
            balance_tier=tier,
            original_balance=balance,
            current_balance=balance,
            acquisition_cost=acq_cost,
            contacts_by_channel={}
        )

    def generate_portfolio(self, num_accounts: int) -> List[AccountLifecycle]:
        """Generate portfolio across all segments"""
        logger.info(f"Generating {num_accounts:,} account portfolio...")

        # Market-weighted distribution
        weights = {
            DebtTypeSegment.BNPL: 0.22,
            DebtTypeSegment.SUBSCRIPTION: 0.10,
            DebtTypeSegment.UTILITY: 0.10,
            DebtTypeSegment.TELECOM: 0.15,
            DebtTypeSegment.MEDICAL_SMALL: 0.15,
            DebtTypeSegment.PAYDAY: 0.08,
            DebtTypeSegment.RETAIL: 0.12,
            DebtTypeSegment.PERSONAL_MICRO: 0.08,
        }

        self.accounts = []
        account_num = 0

        for segment, weight in weights.items():
            count = int(num_accounts * weight)
            for _ in range(count):
                account = self.generate_account(
                    f"LCY-{segment.value[:3].upper()}-{account_num:06d}",
                    segment
                )
                self.accounts.append(account)
                account_num += 1

        # Fill remaining
        while len(self.accounts) < num_accounts:
            segment = random.choice(list(SEGMENT_PROFILES.keys()))
            account = self.generate_account(
                f"LCY-{segment.value[:3].upper()}-{account_num:06d}",
                segment
            )
            self.accounts.append(account)
            account_num += 1

        total_balance = sum(a.original_balance for a in self.accounts)
        avg_balance = total_balance / len(self.accounts)

        logger.info(f"Portfolio generated: {len(self.accounts):,} accounts")
        logger.info(f"Total balance: ${total_balance:,.2f}")
        logger.info(f"Average balance: ${avg_balance:.2f}")

        return self.accounts

    def simulate_collection(
        self,
        account: AccountLifecycle,
        day: int,
        max_contacts: int = 10
    ) -> Tuple[bool, Decimal]:
        """Simulate collection attempt on an account"""
        profile = SEGMENT_PROFILES[account.segment]

        # Skip if already collected
        if account.status == "collected":
            return False, Decimal("0")

        # Check contact limits
        if account.contact_attempts >= max_contacts:
            return False, Decimal("0")

        # Calculate conversion probability
        base_prob = profile.base_recovery_rate * 0.30  # Per-contact probability

        # Adjust for contact count
        if account.contact_attempts == 0:
            prob = base_prob * 0.7  # First contact lower
        elif account.contact_attempts <= 3:
            prob = base_prob * 1.0  # Peak
        else:
            decay = 0.88
            excess = account.contact_attempts - 3
            prob = base_prob * (decay ** excess)

        # Re-engagement bonus
        if account.was_re_engaged:
            prob *= 1.15

        # Balance tier adjustment
        if account.balance_tier == BalanceTier.MICRO:
            prob *= 0.85  # Harder to collect very small
        elif account.balance_tier in [BalanceTier.STANDARD, BalanceTier.UPPER]:
            prob *= 1.10  # More motivated to pay larger

        prob = min(0.50, prob)

        # Calculate contact costs
        channel_cost, contacts = self._calculate_channel_cost(1)
        account.channel_cost += channel_cost
        for ch, cnt in contacts.items():
            account.contacts_by_channel[ch] = account.contacts_by_channel.get(ch, 0) + cnt

        # Processing cost per contact
        account.processing_cost += self.cost_model.processing.initial_contact_cost

        account.contact_attempts += 1
        account.last_contact_day = day  # Track for cadence

        # Check for conversion
        if random.random() < prob:
            # Determine payment amount
            is_full = random.random() < 0.85
            if is_full:
                amount = account.current_balance
            else:
                pct = random.uniform(0.4, 0.8)
                amount = (account.current_balance * Decimal(str(pct))).quantize(Decimal("0.01"))

            # Payment plan check
            is_plan = random.random() < profile.payment_plan_rate
            account.has_payment_plan = is_plan

            # Digital payment check
            account.is_digital_payment = random.random() < profile.digital_rate

            # Payment processing cost
            payment_cost = self._calculate_payment_processing_cost(amount, is_plan)
            account.payment_processing_cost += payment_cost

            # Dispute check
            if random.random() < profile.dispute_rate:
                account.had_dispute = True

            # Compliance cost
            comp_cost, disp_cost = self._calculate_compliance_cost(
                amount, account.contact_attempts, account.had_dispute
            )
            account.compliance_cost += comp_cost
            account.dispute_cost += disp_cost

            # Update account
            account.current_balance -= amount
            account.total_collected += amount
            account.payments_made += 1
            account.days_to_collect = day
            account.collection_day = day

            if account.current_balance <= 0:
                account.status = "collected"
                account.processing_cost += self.cost_model.processing.closure_processing
            else:
                account.status = "partial"

            return True, amount

        return False, Decimal("0")

    def simulate_re_engagement(
        self,
        account: AccountLifecycle,
        day: int
    ) -> Tuple[bool, Decimal]:
        """Simulate re-engagement for dormant account"""
        profile = SEGMENT_PROFILES[account.segment]

        if account.status == "collected":
            return False, Decimal("0")

        # Calculate re-engagement probability
        prob = profile.re_engagement_success

        # Adjust for previous attempts
        if account.re_engagement_attempts > 0:
            prob *= (0.7 ** account.re_engagement_attempts)

        # Balance adjustment
        if account.current_balance < Decimal("50"):
            prob *= 0.5  # Very small balances hard to re-engage

        prob = min(0.40, prob)

        # Record attempt
        account.re_engagement_attempts += 1

        if random.random() < prob:
            account.was_re_engaged = True

            # Calculate amount (often with settlement)
            settlement_rate = random.uniform(0.6, 0.9)
            amount = (account.current_balance * Decimal(str(settlement_rate))).quantize(Decimal("0.01"))

            # Re-engagement cost
            re_cost = self._calculate_re_engagement_cost(
                account.re_engagement_attempts, amount
            )
            account.re_engagement_cost += re_cost

            # Payment processing
            payment_cost = self._calculate_payment_processing_cost(amount)
            account.payment_processing_cost += payment_cost

            # Update account
            account.current_balance = Decimal("0")
            account.total_collected += amount
            account.payments_made += 1
            account.status = "collected"
            account.collection_day = day
            account.processing_cost += self.cost_model.processing.settlement_processing

            return True, amount
        else:
            # Just the attempt cost
            account.re_engagement_cost += self.cost_model.re_engagement.per_attempt_cost
            return False, Decimal("0")

    async def run_simulation(
        self,
        num_accounts: int = 100000,
        simulation_days: int = 90,
        max_contacts: int = 10,
        re_engagement_after_days: int = 14,
        max_re_engagements: int = 3
    ) -> Dict[str, Any]:
        """Run full lifecycle simulation"""
        print("\n" + "=" * 80)
        print("  LIFECYCLE ROI OPTIMIZER")
        print("  Full Account Economics Simulation")
        print("=" * 80)

        print(f"\n  Calibrated Baselines:")
        print(f"    Cost per Dollar: ${self.BASELINE_COST_PER_DOLLAR:.2f}")
        print(f"    Margin:          {self.BASELINE_MARGIN*100:.0f}%")
        print(f"    ROI:             {self.BASELINE_ROI*100:.0f}%")

        # Generate portfolio
        self.generate_portfolio(num_accounts)

        print(f"\n  Running {simulation_days}-day simulation...")
        print(f"    Max contacts: {max_contacts}")
        print(f"    Re-engagement after: {re_engagement_after_days} days")

        # Initialize tracking
        self.daily_collections = []
        self.daily_costs = []

        total_balance = sum(a.original_balance for a in self.accounts)

        # Run simulation
        for day in range(simulation_days):
            daily_collected = Decimal("0")
            daily_cost = Decimal("0")

            for account in self.accounts:
                if account.status == "collected":
                    continue

                # Determine days since last contact
                days_since_contact = day - account.last_contact_day if account.last_contact_day >= 0 else 999

                # Active collection phase
                if account.contact_attempts < max_contacts:
                    # Apply contact cadence (every 2-3 days) or first contact
                    if days_since_contact >= 2 or account.contact_attempts == 0:
                        success, amount = self.simulate_collection(account, day, max_contacts)
                        if success:
                            daily_collected += amount

                # Re-engagement phase (after max contacts exhausted)
                elif (days_since_contact >= re_engagement_after_days and
                      account.re_engagement_attempts < max_re_engagements and
                      account.current_balance > Decimal("25")):
                    success, amount = self.simulate_re_engagement(account, day)
                    if success:
                        daily_collected += amount
                    account.last_contact_day = day  # Track re-engagement contact

                # Write-off check (after exhausting all options)
                elif (account.contact_attempts >= max_contacts and
                      account.re_engagement_attempts >= max_re_engagements and
                      account.status not in ["collected", "written_off"]):
                    account.status = "written_off"

            self.daily_collections.append(daily_collected)

            # Progress logging
            if day > 0 and day % 15 == 0:
                current_collected = sum(a.total_collected for a in self.accounts)
                rate = float(current_collected / total_balance) * 100
                print(f"    Day {day:3d}: Recovery {rate:5.1f}%, Collected ${current_collected:,.0f}")

        # Calculate final metrics
        results = self._calculate_final_metrics()

        # Generate optimization recommendations
        self._generate_optimization()

        return results

    def _calculate_final_metrics(self) -> Dict[str, Any]:
        """Calculate all final metrics"""
        total_balance = sum(a.original_balance for a in self.accounts)
        total_collected = sum(a.total_collected for a in self.accounts)
        total_cost = sum(a.total_cost() for a in self.accounts)

        # Overall metrics
        recovery_rate = float(total_collected / total_balance) if total_balance > 0 else 0
        cost_per_dollar = float(total_cost / total_collected) if total_collected > 0 else 0
        net_margin = total_collected - total_cost
        margin_pct = float(net_margin / total_collected) if total_collected > 0 else 0
        roi = float(net_margin / total_cost) if total_cost > 0 else 0

        # Status counts
        collected = sum(1 for a in self.accounts if a.status == "collected")
        partial = sum(1 for a in self.accounts if a.status == "partial")
        written_off = sum(1 for a in self.accounts if a.status == "written_off")

        # Segment-level metrics
        self.segment_metrics = {}
        for segment in DebtTypeSegment:
            seg_accounts = [a for a in self.accounts if a.segment == segment]
            if not seg_accounts:
                continue

            seg_balance = sum(a.original_balance for a in seg_accounts)
            seg_collected = sum(a.total_collected for a in seg_accounts)
            seg_cost = sum(a.total_cost() for a in seg_accounts)

            seg_metrics = SegmentMetrics(segment_name=segment.value)
            seg_metrics.accounts = len(seg_accounts)
            seg_metrics.total_balance = seg_balance
            seg_metrics.total_collected = seg_collected
            seg_metrics.total_cost = seg_cost

            # LTV (average collected per account)
            seg_metrics.ltv = seg_collected / len(seg_accounts)

            # Cost to collect
            if seg_collected > 0:
                seg_metrics.cost_to_collect = seg_cost / seg_collected
                seg_metrics.net_margin = seg_collected - seg_cost
                seg_metrics.net_margin_pct = float(seg_metrics.net_margin / seg_collected)
                seg_metrics.roi_multiple = float((seg_collected - seg_cost) / seg_cost) if seg_cost > 0 else 0

            # Recovery rate
            if seg_balance > 0:
                seg_metrics.recovery_rate = float(seg_collected / seg_balance)

            # Operational metrics
            total_contacts = sum(a.contact_attempts for a in seg_accounts)
            seg_metrics.avg_contacts = total_contacts / len(seg_accounts)
            seg_metrics.digital_rate = sum(1 for a in seg_accounts if a.is_digital_payment) / max(1, sum(1 for a in seg_accounts if a.payments_made > 0))

            collected_accounts = [a for a in seg_accounts if a.status == "collected" and a.days_to_collect > 0]
            if collected_accounts:
                seg_metrics.avg_days_to_collect = statistics.mean(a.days_to_collect for a in collected_accounts)
                seg_metrics.payback_period_days = seg_metrics.avg_days_to_collect

            seg_metrics.accounts_collected = sum(1 for a in seg_accounts if a.status == "collected")
            seg_metrics.accounts_partial = sum(1 for a in seg_accounts if a.status == "partial")
            seg_metrics.accounts_written_off = sum(1 for a in seg_accounts if a.status == "written_off")

            self.segment_metrics[segment.value] = seg_metrics

        # Balance tier metrics
        self.tier_metrics = {}
        for tier in BalanceTier:
            tier_accounts = [a for a in self.accounts if a.balance_tier == tier]
            if not tier_accounts:
                continue

            tier_balance = sum(a.original_balance for a in tier_accounts)
            tier_collected = sum(a.total_collected for a in tier_accounts)
            tier_cost = sum(a.total_cost() for a in tier_accounts)

            tier_met = SegmentMetrics(segment_name=tier.value)
            tier_met.accounts = len(tier_accounts)
            tier_met.total_balance = tier_balance
            tier_met.total_collected = tier_collected
            tier_met.total_cost = tier_cost

            if tier_collected > 0:
                tier_met.ltv = tier_collected / len(tier_accounts)
                tier_met.cost_to_collect = tier_cost / tier_collected
                tier_met.net_margin = tier_collected - tier_cost
                tier_met.net_margin_pct = float(tier_met.net_margin / tier_collected)
                tier_met.roi_multiple = float((tier_collected - tier_cost) / tier_cost) if tier_cost > 0 else 0

            if tier_balance > 0:
                tier_met.recovery_rate = float(tier_collected / tier_balance)

            self.tier_metrics[tier.value] = tier_met

        return {
            "portfolio": {
                "accounts": len(self.accounts),
                "total_balance": float(total_balance),
                "total_collected": float(total_collected),
                "total_cost": float(total_cost),
                "net_margin": float(net_margin),
            },
            "performance": {
                "recovery_rate": recovery_rate,
                "cost_per_dollar": cost_per_dollar,
                "margin_pct": margin_pct,
                "roi_multiple": roi,
            },
            "status": {
                "collected": collected,
                "partial": partial,
                "written_off": written_off,
            },
            "segments": {k: self._metrics_to_dict(v) for k, v in self.segment_metrics.items()},
            "tiers": {k: self._metrics_to_dict(v) for k, v in self.tier_metrics.items()},
        }

    def _metrics_to_dict(self, m: SegmentMetrics) -> Dict[str, Any]:
        """Convert segment metrics to dict"""
        return {
            "accounts": m.accounts,
            "total_balance": float(m.total_balance),
            "total_collected": float(m.total_collected),
            "total_cost": float(m.total_cost),
            "ltv": float(m.ltv),
            "cost_to_collect": float(m.cost_to_collect),
            "net_margin": float(m.net_margin),
            "net_margin_pct": m.net_margin_pct,
            "roi_multiple": m.roi_multiple,
            "recovery_rate": m.recovery_rate,
            "avg_contacts": m.avg_contacts,
            "digital_rate": m.digital_rate,
            "avg_days_to_collect": m.avg_days_to_collect,
            "payback_period_days": m.payback_period_days,
        }

    def _generate_optimization(self):
        """Generate portfolio optimization recommendations"""
        self.optimization = PortfolioOptimization()

        # Rank debt types by ROI
        segment_ranking = []
        for name, metrics in self.segment_metrics.items():
            roi = metrics.roi_multiple
            margin = metrics.net_margin_pct
            if roi > self.BASELINE_ROI * 1.1:
                rec = "PRIORITIZE - Above baseline"
            elif roi > self.BASELINE_ROI * 0.9:
                rec = "MAINTAIN - At baseline"
            else:
                rec = "REDUCE - Below baseline"
            segment_ranking.append((name, roi, rec))

        self.optimization.debt_type_ranking = sorted(
            segment_ranking, key=lambda x: x[1], reverse=True
        )

        # Rank balance tiers by profitability
        tier_ranking = []
        for name, metrics in self.tier_metrics.items():
            margin = metrics.net_margin_pct
            if margin > self.BASELINE_MARGIN:
                rec = "HIGH PROFIT - Expand"
            elif margin > self.BASELINE_MARGIN * 0.9:
                rec = "PROFITABLE - Maintain"
            else:
                rec = "LOW MARGIN - Review strategy"
            tier_ranking.append((name, margin, rec))

        self.optimization.balance_tier_ranking = sorted(
            tier_ranking, key=lambda x: x[1], reverse=True
        )

        # Calculate optimal cutoffs
        contact_roi = {}
        for contacts in range(1, 13):
            accounts_at_contact = [
                a for a in self.accounts
                if a.contact_attempts >= contacts and a.status == "collected"
            ]
            if accounts_at_contact:
                avg_roi = statistics.mean(a.roi_multiple() for a in accounts_at_contact)
                contact_roi[contacts] = avg_roi

        # Find contact count where ROI drops below 100%
        optimal_contacts = max(contact_roi.keys()) if contact_roi else 8
        for contacts, roi in sorted(contact_roi.items()):
            if roi < 1.0:
                optimal_contacts = max(1, contacts - 1)
                break
        self.optimization.optimal_contact_cutoff = optimal_contacts

        # Day cutoff (when marginal ROI goes negative)
        collected_by_day = {}
        for a in self.accounts:
            if a.status == "collected" and a.collection_day >= 0:
                day = a.collection_day
                if day not in collected_by_day:
                    collected_by_day[day] = {"collected": Decimal("0"), "cost": Decimal("0")}
                collected_by_day[day]["collected"] += a.total_collected
                collected_by_day[day]["cost"] += a.total_cost()

        optimal_day = 60
        cumulative_collected = Decimal("0")
        cumulative_cost = Decimal("0")
        for day in sorted(collected_by_day.keys()):
            cumulative_collected += collected_by_day[day]["collected"]
            cumulative_cost += collected_by_day[day]["cost"]
            marginal_roi = (
                float((collected_by_day[day]["collected"] - collected_by_day[day]["cost"]) /
                      collected_by_day[day]["cost"])
                if collected_by_day[day]["cost"] > 0 else 0
            )
            if marginal_roi < 0.5:  # Less than 50% marginal ROI
                optimal_day = day
                break
        self.optimization.optimal_day_cutoff = optimal_day

        # Re-engagement thresholds
        re_engaged = [a for a in self.accounts if a.was_re_engaged]
        if re_engaged:
            profitable_re = [a for a in re_engaged if a.roi_multiple() > 0]
            if profitable_re:
                min_bal = min(a.original_balance for a in profitable_re)
                self.optimization.re_engagement_min_balance = min_bal
        else:
            self.optimization.re_engagement_min_balance = Decimal("50")

        # Max re-engagement attempts (where success rate drops below 10%)
        self.optimization.re_engagement_max_attempts = 3
        self.optimization.write_off_threshold_days = 75

        # Cost threshold
        avg_cost = sum(a.total_cost() for a in self.accounts) / len(self.accounts)
        self.optimization.optimal_cost_threshold = avg_cost * Decimal("1.5")

        # Capital efficiency
        total_invested = sum(a.acquisition_cost + a.total_cost() for a in self.accounts)
        total_return = sum(a.total_collected for a in self.accounts)
        self.optimization.capital_efficiency_score = float(total_return / total_invested) if total_invested > 0 else 0

        # Recommended portfolio mix (based on ROI ranking)
        total_roi = sum(m.roi_multiple for m in self.segment_metrics.values() if m.roi_multiple > 0)
        if total_roi > 0:
            for name, metrics in self.segment_metrics.items():
                if metrics.roi_multiple > 0:
                    weight = metrics.roi_multiple / total_roi
                    self.optimization.recommended_portfolio_mix[name] = round(weight, 3)

    def print_results(self, results: Dict[str, Any]):
        """Print comprehensive results"""
        print("\n" + "=" * 80)
        print("  LIFECYCLE ROI SIMULATION RESULTS")
        print("=" * 80)

        # Portfolio summary
        p = results["portfolio"]
        perf = results["performance"]
        status = results["status"]

        print(f"\n  PORTFOLIO SUMMARY:")
        print(f"    Total Accounts:      {p['accounts']:,}")
        print(f"    Total Balance:       ${p['total_balance']:,.2f}")
        print(f"    Total Collected:     ${p['total_collected']:,.2f}")
        print(f"    Total Cost:          ${p['total_cost']:,.2f}")
        print(f"    Net Margin:          ${p['net_margin']:,.2f}")

        print(f"\n  PERFORMANCE vs BASELINE:")
        print(f"    {'Metric':<25} {'Actual':>12} {'Baseline':>12} {'Delta':>12}")
        print("    " + "-" * 53)

        cost_delta = perf['cost_per_dollar'] - self.BASELINE_COST_PER_DOLLAR
        print(f"    {'Cost per Dollar':<25} ${perf['cost_per_dollar']:>10.3f} "
              f"${self.BASELINE_COST_PER_DOLLAR:>10.2f} "
              f"{'+'if cost_delta > 0 else ''}{cost_delta:>+10.3f}")

        margin_delta = perf['margin_pct'] - self.BASELINE_MARGIN
        print(f"    {'Profit Margin':<25} {perf['margin_pct']*100:>10.1f}% "
              f"{self.BASELINE_MARGIN*100:>10.0f}% "
              f"{'+'if margin_delta > 0 else ''}{margin_delta*100:>+10.1f}%")

        roi_delta = perf['roi_multiple'] - self.BASELINE_ROI
        print(f"    {'ROI Multiple':<25} {perf['roi_multiple']*100:>10.0f}% "
              f"{self.BASELINE_ROI*100:>10.0f}% "
              f"{'+'if roi_delta > 0 else ''}{roi_delta*100:>+10.0f}%")

        print(f"    {'Recovery Rate':<25} {perf['recovery_rate']*100:>10.1f}%")

        print(f"\n  ACCOUNT STATUS:")
        print(f"    Collected:           {status['collected']:,} ({status['collected']/p['accounts']*100:.1f}%)")
        print(f"    Partial:             {status['partial']:,} ({status['partial']/p['accounts']*100:.1f}%)")
        print(f"    Written Off:         {status['written_off']:,} ({status['written_off']/p['accounts']*100:.1f}%)")

        # Segment P&L
        print(f"\n  SEGMENT-LEVEL P&L:")
        print("  " + "-" * 76)
        print(f"  {'Segment':<20} {'LTV':>10} {'Cost/$ ':>10} {'Margin':>10} {'ROI':>10} {'Recovery':>10}")
        print("  " + "-" * 76)

        for name, m in sorted(self.segment_metrics.items(),
                             key=lambda x: x[1].roi_multiple, reverse=True):
            print(f"  {name:<20} ${m.ltv:>8.2f} ${m.cost_to_collect:>9.3f} "
                  f"{m.net_margin_pct*100:>9.1f}% {m.roi_multiple*100:>9.0f}% "
                  f"{m.recovery_rate*100:>9.1f}%")

        print("  " + "-" * 76)

        # Balance tier analysis
        print(f"\n  BALANCE TIER PROFITABILITY:")
        print("  " + "-" * 76)
        print(f"  {'Tier':<15} {'Accounts':>10} {'Avg Bal':>12} {'Margin':>10} {'ROI':>10} {'Recovery':>10}")
        print("  " + "-" * 76)

        for tier in BalanceTier:
            if tier.value in self.tier_metrics:
                m = self.tier_metrics[tier.value]
                avg_bal = float(m.total_balance) / m.accounts if m.accounts > 0 else 0
                print(f"  {tier.value:<15} {m.accounts:>10,} ${avg_bal:>10.2f} "
                      f"{m.net_margin_pct*100:>9.1f}% {m.roi_multiple*100:>9.0f}% "
                      f"{m.recovery_rate*100:>9.1f}%")

        print("  " + "-" * 76)

        # Optimization recommendations
        if self.optimization:
            self._print_optimization()

    def _print_optimization(self):
        """Print optimization recommendations"""
        opt = self.optimization

        print(f"\n  PORTFOLIO OPTIMIZATION RECOMMENDATIONS:")
        print("  " + "-" * 76)

        print(f"\n  Debt Type Priority (by ROI):")
        for rank, (name, roi, rec) in enumerate(opt.debt_type_ranking[:5], 1):
            print(f"    {rank}. {name:<25} ROI: {roi*100:>6.0f}%  {rec}")

        print(f"\n  Balance Tier Ranking (by Margin):")
        for rank, (name, margin, rec) in enumerate(opt.balance_tier_ranking, 1):
            print(f"    {rank}. {name:<15} Margin: {margin*100:>6.1f}%  {rec}")

        print(f"\n  Optimal Collection Cutoffs:")
        print(f"    Max Contacts Before Escalation:  {opt.optimal_contact_cutoff}")
        print(f"    Max Days Before Write-off:       {opt.optimal_day_cutoff}")
        print(f"    Max Cost Threshold per Account:  ${opt.optimal_cost_threshold:.2f}")

        print(f"\n  Re-engagement Decision Thresholds:")
        print(f"    Minimum Balance for Re-engage:   ${opt.re_engagement_min_balance:.2f}")
        print(f"    Max Re-engagement Attempts:      {opt.re_engagement_max_attempts}")
        print(f"    Write-off After Days Dormant:    {opt.write_off_threshold_days}")

        print(f"\n  Capital Efficiency:")
        print(f"    Efficiency Score:                {opt.capital_efficiency_score:.2f}x")

        print(f"\n  Recommended Portfolio Mix:")
        for name, weight in sorted(opt.recommended_portfolio_mix.items(),
                                   key=lambda x: x[1], reverse=True):
            print(f"    {name:<25} {weight*100:>6.1f}%")

        # Margin improvement opportunities
        print(f"\n  MARGIN IMPROVEMENT OPPORTUNITIES:")
        print("  " + "-" * 76)

        # Find underperforming segments
        underperformers = [
            (name, m) for name, m in self.segment_metrics.items()
            if m.net_margin_pct < self.BASELINE_MARGIN * 0.9
        ]

        if underperformers:
            print(f"\n  Underperforming Segments (< 90% of baseline margin):")
            for name, m in underperformers:
                gap = self.BASELINE_MARGIN - m.net_margin_pct
                potential = float(m.total_collected) * gap
                print(f"    {name}: {m.net_margin_pct*100:.1f}% margin "
                      f"(gap: {gap*100:.1f}%, potential: ${potential:,.0f})")

        # High cost segments
        high_cost = [
            (name, m) for name, m in self.segment_metrics.items()
            if float(m.cost_to_collect) > self.BASELINE_COST_PER_DOLLAR * 1.2
        ]

        if high_cost:
            print(f"\n  High Cost Segments (> 120% of baseline cost):")
            for name, m in high_cost:
                excess = float(m.cost_to_collect) - self.BASELINE_COST_PER_DOLLAR
                savings = float(m.total_collected) * excess
                print(f"    {name}: ${m.cost_to_collect:.3f}/$ "
                      f"(excess: ${excess:.3f}, savings potential: ${savings:,.0f})")

        # Digital opportunity
        low_digital = [
            (name, m) for name, m in self.segment_metrics.items()
            if m.digital_rate < 0.70
        ]

        if low_digital:
            print(f"\n  Digital Payment Optimization (< 70% digital):")
            for name, m in low_digital:
                digital_savings = (0.85 - m.digital_rate) * float(m.total_collected) * 0.02
                print(f"    {name}: {m.digital_rate*100:.0f}% digital "
                      f"(potential savings: ${digital_savings:,.0f})")

        print("\n" + "=" * 80)


async def run_lifecycle_optimization():
    """Run full lifecycle ROI optimization"""
    optimizer = LifecycleROIOptimizer()

    results = await optimizer.run_simulation(
        num_accounts=100000,
        simulation_days=90,
        max_contacts=10,
        re_engagement_after_days=14,
        max_re_engagements=3
    )

    optimizer.print_results(results)

    return results, optimizer


def main():
    """Main entry point"""
    results, optimizer = asyncio.run(run_lifecycle_optimization())
    return results


if __name__ == "__main__":
    main()
