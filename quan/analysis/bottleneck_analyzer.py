"""
Workflow Bottleneck Analyzer for Collection Pipeline

Analyzes the complete collection pipeline stages:
ACQUIRE -> LOCATE -> CONTACT -> NEGOTIATE -> COLLECT -> CLOSE -> PROFIT

Identifies bottlenecks, calculates metrics, and generates optimization
recommendations focused on sub-$1K micro-debt collections.
"""

import asyncio
import random
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from quan.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# PIPELINE STAGE DEFINITIONS
# =============================================================================

class PipelineStage(Enum):
    """Collection pipeline stages"""
    ACQUIRE = "acquire"       # Portfolio acquisition and ingestion
    LOCATE = "locate"         # Skip tracing and contact info validation
    CONTACT = "contact"       # Initial and follow-up contact attempts
    NEGOTIATE = "negotiate"   # Payment negotiation and settlement
    COLLECT = "collect"       # Payment processing and capture
    CLOSE = "close"           # Account closure and reconciliation
    PROFIT = "profit"         # Revenue recognition and reporting


class DropOffReason(Enum):
    """Reasons for account drop-off at each stage"""
    # ACQUIRE stage
    INVALID_DATA = "invalid_data"
    DUPLICATE_ACCOUNT = "duplicate_account"
    COMPLIANCE_BLOCK = "compliance_block"
    BANKRUPTCY_FILED = "bankruptcy_filed"

    # LOCATE stage
    SKIP_TRACE_FAILED = "skip_trace_failed"
    NO_VALID_CONTACT = "no_valid_contact"
    WRONG_PARTY_CONTACT = "wrong_party_contact"
    DECEASED = "deceased"

    # CONTACT stage
    NO_RESPONSE = "no_response"
    CEASE_REQUESTED = "cease_requested"
    DISPUTED = "disputed"
    CONTACT_LIMIT_REACHED = "contact_limit_reached"

    # NEGOTIATE stage
    REFUSED_TO_PAY = "refused_to_pay"
    HARDSHIP_UNCOLLECTABLE = "hardship_uncollectable"
    SETTLEMENT_REJECTED = "settlement_rejected"
    NEGOTIATION_TIMEOUT = "negotiation_timeout"

    # COLLECT stage
    PAYMENT_FAILED = "payment_failed"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CHARGEBACK = "chargeback"
    PAYMENT_PLAN_DEFAULT = "payment_plan_default"

    # CLOSE stage
    WRITE_OFF = "write_off"
    RETURNED_TO_CLIENT = "returned_to_client"
    SOLD_TO_TERTIARY = "sold_to_tertiary"


@dataclass
class StageTransition:
    """Represents a transition between pipeline stages"""
    from_stage: PipelineStage
    to_stage: PipelineStage
    success_rate: float
    avg_time_hours: float
    drop_off_reasons: Dict[DropOffReason, float]  # reason -> probability


# =============================================================================
# MICRO-DEBT SPECIFIC STAGE PROFILES
# =============================================================================

@dataclass
class MicroDebtStageProfile:
    """Stage performance profile for sub-$1K micro-debt"""
    stage: PipelineStage

    # Conversion metrics
    base_conversion_rate: float
    digital_boost: float  # Additional conversion from digital-first approach

    # Time metrics (hours)
    min_time: float
    avg_time: float
    max_time: float

    # Cost metrics (per account)
    fixed_cost: Decimal
    variable_cost_per_attempt: Decimal
    max_attempts: int

    # Resource utilization
    ai_automation_rate: float  # Percentage handled by AI
    human_escalation_rate: float

    # Drop-off distribution
    drop_off_distribution: Dict[DropOffReason, float]


# Industry-calibrated stage profiles for sub-$1K micro-debt
MICRO_DEBT_STAGE_PROFILES: Dict[PipelineStage, MicroDebtStageProfile] = {
    PipelineStage.ACQUIRE: MicroDebtStageProfile(
        stage=PipelineStage.ACQUIRE,
        base_conversion_rate=0.95,
        digital_boost=0.02,
        min_time=0.1,
        avg_time=0.5,
        max_time=2.0,
        fixed_cost=Decimal("0.05"),
        variable_cost_per_attempt=Decimal("0.01"),
        max_attempts=1,
        ai_automation_rate=0.98,
        human_escalation_rate=0.02,
        drop_off_distribution={
            DropOffReason.INVALID_DATA: 0.02,
            DropOffReason.DUPLICATE_ACCOUNT: 0.015,
            DropOffReason.COMPLIANCE_BLOCK: 0.01,
            DropOffReason.BANKRUPTCY_FILED: 0.005,
        }
    ),

    PipelineStage.LOCATE: MicroDebtStageProfile(
        stage=PipelineStage.LOCATE,
        base_conversion_rate=0.88,
        digital_boost=0.05,
        min_time=0.5,
        avg_time=4.0,
        max_time=48.0,
        fixed_cost=Decimal("0.10"),
        variable_cost_per_attempt=Decimal("0.15"),
        max_attempts=3,
        ai_automation_rate=0.90,
        human_escalation_rate=0.10,
        drop_off_distribution={
            DropOffReason.SKIP_TRACE_FAILED: 0.05,
            DropOffReason.NO_VALID_CONTACT: 0.04,
            DropOffReason.WRONG_PARTY_CONTACT: 0.02,
            DropOffReason.DECEASED: 0.01,
        }
    ),

    PipelineStage.CONTACT: MicroDebtStageProfile(
        stage=PipelineStage.CONTACT,
        base_conversion_rate=0.42,
        digital_boost=0.12,  # SMS/email advantage
        min_time=2.0,
        avg_time=72.0,
        max_time=336.0,  # 14 days max
        fixed_cost=Decimal("0.05"),
        variable_cost_per_attempt=Decimal("0.03"),  # SMS/email much cheaper than calls
        max_attempts=8,
        ai_automation_rate=0.85,
        human_escalation_rate=0.15,
        drop_off_distribution={
            DropOffReason.NO_RESPONSE: 0.35,
            DropOffReason.CEASE_REQUESTED: 0.08,
            DropOffReason.DISPUTED: 0.10,
            DropOffReason.CONTACT_LIMIT_REACHED: 0.05,
        }
    ),

    PipelineStage.NEGOTIATE: MicroDebtStageProfile(
        stage=PipelineStage.NEGOTIATE,
        base_conversion_rate=0.65,
        digital_boost=0.08,
        min_time=0.5,
        avg_time=24.0,
        max_time=168.0,  # 7 days
        fixed_cost=Decimal("0.10"),
        variable_cost_per_attempt=Decimal("0.05"),
        max_attempts=5,
        ai_automation_rate=0.75,
        human_escalation_rate=0.25,
        drop_off_distribution={
            DropOffReason.REFUSED_TO_PAY: 0.15,
            DropOffReason.HARDSHIP_UNCOLLECTABLE: 0.10,
            DropOffReason.SETTLEMENT_REJECTED: 0.05,
            DropOffReason.NEGOTIATION_TIMEOUT: 0.05,
        }
    ),

    PipelineStage.COLLECT: MicroDebtStageProfile(
        stage=PipelineStage.COLLECT,
        base_conversion_rate=0.88,
        digital_boost=0.06,
        min_time=0.1,
        avg_time=2.0,
        max_time=72.0,
        fixed_cost=Decimal("0.15"),
        variable_cost_per_attempt=Decimal("0.08"),
        max_attempts=4,
        ai_automation_rate=0.95,
        human_escalation_rate=0.05,
        drop_off_distribution={
            DropOffReason.PAYMENT_FAILED: 0.05,
            DropOffReason.INSUFFICIENT_FUNDS: 0.04,
            DropOffReason.CHARGEBACK: 0.02,
            DropOffReason.PAYMENT_PLAN_DEFAULT: 0.01,
        }
    ),

    PipelineStage.CLOSE: MicroDebtStageProfile(
        stage=PipelineStage.CLOSE,
        base_conversion_rate=0.99,
        digital_boost=0.005,
        min_time=0.1,
        avg_time=1.0,
        max_time=24.0,
        fixed_cost=Decimal("0.02"),
        variable_cost_per_attempt=Decimal("0.01"),
        max_attempts=1,
        ai_automation_rate=0.99,
        human_escalation_rate=0.01,
        drop_off_distribution={
            DropOffReason.WRITE_OFF: 0.005,
            DropOffReason.RETURNED_TO_CLIENT: 0.003,
            DropOffReason.SOLD_TO_TERTIARY: 0.002,
        }
    ),

    PipelineStage.PROFIT: MicroDebtStageProfile(
        stage=PipelineStage.PROFIT,
        base_conversion_rate=1.0,
        digital_boost=0.0,
        min_time=0.1,
        avg_time=0.5,
        max_time=1.0,
        fixed_cost=Decimal("0.01"),
        variable_cost_per_attempt=Decimal("0.00"),
        max_attempts=1,
        ai_automation_rate=1.0,
        human_escalation_rate=0.0,
        drop_off_distribution={}
    ),
}


# =============================================================================
# RETRY STRATEGY DEFINITIONS
# =============================================================================

@dataclass
class RetryStrategy:
    """Retry strategy configuration for a stage"""
    max_retries: int
    base_delay_hours: float
    backoff_multiplier: float
    max_delay_hours: float
    success_rate_per_retry: List[float]  # Success rate for each retry attempt
    channel_rotation: List[str]  # Channels to rotate through


OPTIMAL_RETRY_STRATEGIES: Dict[PipelineStage, RetryStrategy] = {
    PipelineStage.ACQUIRE: RetryStrategy(
        max_retries=1,
        base_delay_hours=0.5,
        backoff_multiplier=1.0,
        max_delay_hours=1.0,
        success_rate_per_retry=[0.50],
        channel_rotation=["api_resubmit"]
    ),

    PipelineStage.LOCATE: RetryStrategy(
        max_retries=3,
        base_delay_hours=24.0,
        backoff_multiplier=1.5,
        max_delay_hours=168.0,
        success_rate_per_retry=[0.40, 0.25, 0.15],
        channel_rotation=["primary_skip", "secondary_skip", "social_lookup"]
    ),

    PipelineStage.CONTACT: RetryStrategy(
        max_retries=8,
        base_delay_hours=48.0,
        backoff_multiplier=1.2,
        max_delay_hours=336.0,
        success_rate_per_retry=[0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03],
        channel_rotation=["sms", "email", "sms", "push", "email", "sms", "email", "mail"]
    ),

    PipelineStage.NEGOTIATE: RetryStrategy(
        max_retries=5,
        base_delay_hours=24.0,
        backoff_multiplier=1.3,
        max_delay_hours=168.0,
        success_rate_per_retry=[0.30, 0.25, 0.20, 0.15, 0.10],
        channel_rotation=["ai_offer", "ai_counter", "human_agent", "final_offer", "settlement"]
    ),

    PipelineStage.COLLECT: RetryStrategy(
        max_retries=4,
        base_delay_hours=24.0,
        backoff_multiplier=1.5,
        max_delay_hours=120.0,
        success_rate_per_retry=[0.60, 0.40, 0.25, 0.15],
        channel_rotation=["card_retry", "ach_retry", "alt_card", "payment_plan"]
    ),

    PipelineStage.CLOSE: RetryStrategy(
        max_retries=1,
        base_delay_hours=1.0,
        backoff_multiplier=1.0,
        max_delay_hours=24.0,
        success_rate_per_retry=[0.90],
        channel_rotation=["auto_close"]
    ),

    PipelineStage.PROFIT: RetryStrategy(
        max_retries=0,
        base_delay_hours=0.0,
        backoff_multiplier=1.0,
        max_delay_hours=0.0,
        success_rate_per_retry=[],
        channel_rotation=[]
    ),
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SimulatedAccount:
    """Account being simulated through the pipeline"""
    account_id: str
    balance: Decimal
    debt_type: str

    # Characteristics that affect conversion
    is_digital_native: bool
    has_valid_phone: bool
    has_valid_email: bool
    payment_willingness: float  # 0-1

    # Tracking
    current_stage: PipelineStage
    stage_history: List[Dict] = field(default_factory=list)
    total_time_hours: float = 0.0
    total_cost: Decimal = Decimal("0")
    attempts_per_stage: Dict[str, int] = field(default_factory=dict)

    # Outcome
    final_status: str = "in_progress"
    amount_collected: Decimal = Decimal("0")
    drop_off_reason: Optional[DropOffReason] = None


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage"""
    stage: PipelineStage

    # Volume metrics
    accounts_entered: int = 0
    accounts_converted: int = 0
    accounts_dropped: int = 0

    # Conversion metrics
    conversion_rate: float = 0.0
    conversion_rate_with_retries: float = 0.0

    # Time metrics (hours)
    min_time: float = float('inf')
    avg_time: float = 0.0
    max_time: float = 0.0
    p50_time: float = 0.0
    p90_time: float = 0.0
    p99_time: float = 0.0

    # Cost metrics
    total_cost: Decimal = Decimal("0")
    avg_cost_per_account: Decimal = Decimal("0")
    cost_per_conversion: Decimal = Decimal("0")
    cost_contribution_pct: float = 0.0

    # Retry metrics
    total_attempts: int = 0
    avg_attempts: float = 0.0
    retry_success_rate: float = 0.0

    # Resource utilization
    ai_handled_count: int = 0
    human_escalation_count: int = 0
    ai_utilization_rate: float = 0.0

    # Drop-off analysis
    drop_off_reasons: Dict[str, int] = field(default_factory=dict)
    drop_off_rate_by_reason: Dict[str, float] = field(default_factory=dict)

    # Collection amounts (for later stages)
    total_balance_entered: Decimal = Decimal("0")
    total_amount_collected: Decimal = Decimal("0")

    # Raw time data for percentile calculations
    _time_data: List[float] = field(default_factory=list)


@dataclass
class TransitionMetrics:
    """Metrics for stage-to-stage transitions"""
    from_stage: PipelineStage
    to_stage: PipelineStage

    accounts_attempted: int = 0
    accounts_succeeded: int = 0
    accounts_failed: int = 0

    success_rate: float = 0.0
    failure_rate: float = 0.0

    avg_transition_time_hours: float = 0.0
    failure_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass
class OptimizationRecommendation:
    """Recommendation for bottleneck optimization"""
    stage: PipelineStage
    priority: int  # 1 = highest
    category: str  # "conversion", "speed", "cost", "retry"

    title: str
    description: str

    current_metric: float
    target_metric: float
    improvement_pct: float

    implementation_effort: str  # "low", "medium", "high"
    expected_roi: float

    specific_actions: List[str]


@dataclass
class BottleneckReport:
    """Complete bottleneck analysis report"""
    analysis_timestamp: datetime
    simulation_config: Dict[str, Any]

    # Overall metrics
    total_accounts_simulated: int
    total_accounts_collected: int
    overall_conversion_rate: float
    overall_collection_rate: float

    total_balance: Decimal
    total_collected: Decimal
    total_cost: Decimal

    net_revenue: Decimal
    profit_margin: float
    roi: float

    avg_pipeline_time_hours: float
    avg_cost_per_account: Decimal

    # Stage-by-stage metrics
    stage_metrics: Dict[PipelineStage, StageMetrics]

    # Transition metrics
    transition_metrics: List[TransitionMetrics]

    # Bottleneck identification
    primary_bottleneck: PipelineStage
    secondary_bottlenecks: List[PipelineStage]
    bottleneck_scores: Dict[PipelineStage, float]

    # Recommendations
    recommendations: List[OptimizationRecommendation]

    # Projected improvements
    projected_improvement: Dict[str, Any]


# =============================================================================
# BOTTLENECK ANALYZER
# =============================================================================

class BottleneckAnalyzer:
    """
    Workflow bottleneck analyzer for collection pipeline.

    Simulates accounts through the complete pipeline and identifies
    bottlenecks with optimization recommendations.
    """

    def __init__(
        self,
        num_accounts: int = 100_000,
        avg_balance: Decimal = Decimal("275"),
        digital_native_rate: float = 0.70,
        simulation_seed: Optional[int] = None
    ):
        self.num_accounts = num_accounts
        self.avg_balance = avg_balance
        self.digital_native_rate = digital_native_rate

        if simulation_seed:
            random.seed(simulation_seed)

        # Simulation state
        self.accounts: List[SimulatedAccount] = []
        self.stage_metrics: Dict[PipelineStage, StageMetrics] = {}
        self.transition_metrics: List[TransitionMetrics] = []

        # Results
        self.report: Optional[BottleneckReport] = None

        # Initialize stage metrics
        for stage in PipelineStage:
            self.stage_metrics[stage] = StageMetrics(stage=stage)

    def generate_accounts(self) -> List[SimulatedAccount]:
        """Generate simulated account portfolio"""
        accounts = []

        debt_types = [
            ("bnpl", 0.30),
            ("subscription", 0.15),
            ("payday", 0.12),
            ("telecom", 0.15),
            ("utility", 0.10),
            ("medical_small", 0.10),
            ("retail_small", 0.08),
        ]

        for i in range(self.num_accounts):
            # Select debt type
            r = random.random()
            cumulative = 0
            debt_type = "bnpl"
            for dt, prob in debt_types:
                cumulative += prob
                if r < cumulative:
                    debt_type = dt
                    break

            # Generate balance (log-normal for realistic distribution)
            base_balance = float(self.avg_balance)
            balance = Decimal(str(
                max(25, min(999, random.lognormvariate(
                    statistics.log(base_balance), 0.6
                )))
            )).quantize(Decimal("0.01"))

            # Generate characteristics
            is_digital = random.random() < self.digital_native_rate

            account = SimulatedAccount(
                account_id=f"SIM-{i:07d}",
                balance=balance,
                debt_type=debt_type,
                is_digital_native=is_digital,
                has_valid_phone=random.random() < (0.92 if is_digital else 0.78),
                has_valid_email=random.random() < (0.88 if is_digital else 0.65),
                payment_willingness=random.betavariate(2, 5) + (0.15 if is_digital else 0),
                current_stage=PipelineStage.ACQUIRE,
            )
            accounts.append(account)

        self.accounts = accounts
        return accounts

    def simulate_stage(
        self,
        account: SimulatedAccount,
        stage: PipelineStage
    ) -> Tuple[bool, float, Decimal, Optional[DropOffReason]]:
        """
        Simulate account processing through a single stage.

        Returns: (success, time_hours, cost, drop_off_reason)
        """
        profile = MICRO_DEBT_STAGE_PROFILES[stage]
        retry_strategy = OPTIMAL_RETRY_STRATEGIES[stage]

        # Calculate effective conversion rate
        base_rate = profile.base_conversion_rate

        # Digital native boost
        if account.is_digital_native:
            base_rate += profile.digital_boost

        # Stage-specific adjustments
        if stage == PipelineStage.LOCATE:
            if not account.has_valid_phone and not account.has_valid_email:
                base_rate *= 0.5

        elif stage == PipelineStage.CONTACT:
            # Contact stage heavily affected by valid contact info
            if account.has_valid_phone:
                base_rate *= 1.1
            else:
                base_rate *= 0.7

            if account.has_valid_email:
                base_rate *= 1.05

            # Willingness affects response
            base_rate *= (0.5 + account.payment_willingness * 0.5)

        elif stage == PipelineStage.NEGOTIATE:
            # Negotiation success tied to willingness
            base_rate *= (0.4 + account.payment_willingness * 0.6)

        elif stage == PipelineStage.COLLECT:
            # Collection success high once negotiated
            if account.is_digital_native:
                base_rate = min(0.98, base_rate * 1.05)

        # Simulate attempts
        attempts = 0
        success = False
        total_time = 0.0
        total_cost = profile.fixed_cost

        # First attempt
        attempts += 1
        success = random.random() < base_rate

        # Generate time for first attempt
        attempt_time = random.uniform(
            profile.min_time,
            profile.avg_time
        )
        total_time += attempt_time
        total_cost += profile.variable_cost_per_attempt

        # Retry logic
        if not success and retry_strategy.max_retries > 0:
            delay = retry_strategy.base_delay_hours

            for retry_num in range(retry_strategy.max_retries):
                if retry_num >= len(retry_strategy.success_rate_per_retry):
                    break

                retry_rate = retry_strategy.success_rate_per_retry[retry_num]

                # Boost retry rate for digital natives
                if account.is_digital_native:
                    retry_rate *= 1.15

                attempts += 1
                total_time += delay
                total_cost += profile.variable_cost_per_attempt

                if random.random() < retry_rate:
                    success = True
                    break

                # Apply backoff
                delay = min(
                    delay * retry_strategy.backoff_multiplier,
                    retry_strategy.max_delay_hours
                )

        # Determine drop-off reason if failed
        drop_off_reason = None
        if not success:
            reasons = list(profile.drop_off_distribution.keys())
            probs = list(profile.drop_off_distribution.values())
            if reasons:
                # Normalize probabilities
                total_prob = sum(probs)
                if total_prob > 0:
                    probs = [p / total_prob for p in probs]
                    drop_off_reason = random.choices(reasons, weights=probs)[0]

        # Track attempts
        stage_key = stage.value
        if stage_key not in account.attempts_per_stage:
            account.attempts_per_stage[stage_key] = 0
        account.attempts_per_stage[stage_key] += attempts

        return success, total_time, total_cost, drop_off_reason

    async def simulate_pipeline(self) -> None:
        """Simulate all accounts through the complete pipeline"""
        logger.info(f"Simulating {self.num_accounts:,} accounts through pipeline...")

        if not self.accounts:
            self.generate_accounts()

        pipeline_order = [
            PipelineStage.ACQUIRE,
            PipelineStage.LOCATE,
            PipelineStage.CONTACT,
            PipelineStage.NEGOTIATE,
            PipelineStage.COLLECT,
            PipelineStage.CLOSE,
            PipelineStage.PROFIT,
        ]

        # Process each account through the pipeline
        for account in self.accounts:
            account_balance = account.balance

            for stage in pipeline_order:
                # Record entry into stage
                metrics = self.stage_metrics[stage]
                metrics.accounts_entered += 1
                metrics.total_balance_entered += account_balance

                # Simulate the stage
                success, time_hours, cost, drop_off_reason = self.simulate_stage(
                    account, stage
                )

                # Update account
                account.total_time_hours += time_hours
                account.total_cost += cost
                account.current_stage = stage

                # Record stage metrics
                metrics.total_cost += cost
                metrics.total_attempts += account.attempts_per_stage.get(stage.value, 1)
                metrics._time_data.append(time_hours)

                # Determine AI vs human handling
                profile = MICRO_DEBT_STAGE_PROFILES[stage]
                if random.random() < profile.ai_automation_rate:
                    metrics.ai_handled_count += 1
                else:
                    metrics.human_escalation_count += 1

                # Record stage history
                account.stage_history.append({
                    "stage": stage.value,
                    "success": success,
                    "time_hours": time_hours,
                    "cost": float(cost),
                    "attempts": account.attempts_per_stage.get(stage.value, 1),
                })

                if success:
                    metrics.accounts_converted += 1

                    # For COLLECT stage, record collection
                    if stage == PipelineStage.COLLECT:
                        # Simulate settlement amount (avg 65% of balance for sub-$1K)
                        settlement_pct = random.uniform(0.55, 0.95)
                        amount = (account_balance * Decimal(str(settlement_pct))).quantize(
                            Decimal("0.01")
                        )
                        account.amount_collected = amount
                        metrics.total_amount_collected += amount

                    # For PROFIT stage, mark as collected
                    if stage == PipelineStage.PROFIT:
                        account.final_status = "collected"
                else:
                    metrics.accounts_dropped += 1
                    account.final_status = f"dropped_at_{stage.value}"
                    account.drop_off_reason = drop_off_reason

                    # Record drop-off reason
                    if drop_off_reason:
                        reason_key = drop_off_reason.value
                        if reason_key not in metrics.drop_off_reasons:
                            metrics.drop_off_reasons[reason_key] = 0
                        metrics.drop_off_reasons[reason_key] += 1

                    # Stop processing this account
                    break

        logger.info("Pipeline simulation complete")

    def calculate_metrics(self) -> None:
        """Calculate all metrics from simulation results"""
        total_cost = Decimal("0")

        for stage in PipelineStage:
            metrics = self.stage_metrics[stage]

            if metrics.accounts_entered > 0:
                # Conversion rate
                metrics.conversion_rate = (
                    metrics.accounts_converted / metrics.accounts_entered
                )

                # Cost metrics
                metrics.avg_cost_per_account = (
                    metrics.total_cost / metrics.accounts_entered
                )

                if metrics.accounts_converted > 0:
                    metrics.cost_per_conversion = (
                        metrics.total_cost / metrics.accounts_converted
                    )

                # Attempt metrics
                metrics.avg_attempts = (
                    metrics.total_attempts / metrics.accounts_entered
                )

                # AI utilization
                total_handled = metrics.ai_handled_count + metrics.human_escalation_count
                if total_handled > 0:
                    metrics.ai_utilization_rate = (
                        metrics.ai_handled_count / total_handled
                    )

                # Time metrics
                if metrics._time_data:
                    metrics.min_time = min(metrics._time_data)
                    metrics.max_time = max(metrics._time_data)
                    metrics.avg_time = statistics.mean(metrics._time_data)

                    sorted_times = sorted(metrics._time_data)
                    n = len(sorted_times)
                    metrics.p50_time = sorted_times[int(n * 0.50)]
                    metrics.p90_time = sorted_times[int(n * 0.90)]
                    metrics.p99_time = sorted_times[min(int(n * 0.99), n - 1)]

                # Drop-off rate by reason
                for reason, count in metrics.drop_off_reasons.items():
                    metrics.drop_off_rate_by_reason[reason] = (
                        count / metrics.accounts_entered
                    )

            total_cost += metrics.total_cost

        # Calculate cost contribution percentages
        if total_cost > 0:
            for stage in PipelineStage:
                metrics = self.stage_metrics[stage]
                metrics.cost_contribution_pct = float(
                    metrics.total_cost / total_cost * 100
                )

        # Calculate transition metrics
        pipeline_order = list(PipelineStage)
        for i in range(len(pipeline_order) - 1):
            from_stage = pipeline_order[i]
            to_stage = pipeline_order[i + 1]

            from_metrics = self.stage_metrics[from_stage]
            to_metrics = self.stage_metrics[to_stage]

            transition = TransitionMetrics(
                from_stage=from_stage,
                to_stage=to_stage,
                accounts_attempted=from_metrics.accounts_entered,
                accounts_succeeded=to_metrics.accounts_entered,
                accounts_failed=from_metrics.accounts_dropped,
            )

            if transition.accounts_attempted > 0:
                transition.success_rate = (
                    transition.accounts_succeeded / transition.accounts_attempted
                )
                transition.failure_rate = (
                    transition.accounts_failed / transition.accounts_attempted
                )

            # Calculate avg transition time
            times = []
            for account in self.accounts:
                for hist in account.stage_history:
                    if hist["stage"] == from_stage.value:
                        times.append(hist["time_hours"])
            if times:
                transition.avg_transition_time_hours = statistics.mean(times)

            transition.failure_reasons = from_metrics.drop_off_reasons.copy()

            self.transition_metrics.append(transition)

    def identify_bottlenecks(self) -> Tuple[PipelineStage, List[PipelineStage], Dict[PipelineStage, float]]:
        """
        Identify primary and secondary bottlenecks.

        Bottleneck score based on:
        - Drop-off rate (40%)
        - Time in stage (30%)
        - Cost contribution (20%)
        - Retry exhaustion rate (10%)
        """
        scores = {}

        for stage in PipelineStage:
            metrics = self.stage_metrics[stage]
            profile = MICRO_DEBT_STAGE_PROFILES[stage]

            if metrics.accounts_entered == 0:
                scores[stage] = 0
                continue

            # Drop-off impact (40%)
            expected_conversion = profile.base_conversion_rate
            actual_conversion = metrics.conversion_rate
            drop_off_score = max(0, expected_conversion - actual_conversion) * 40

            # Time impact (30%)
            expected_time = profile.avg_time
            actual_time = metrics.avg_time
            time_score = min(30, max(0, (actual_time - expected_time) / expected_time * 30))

            # Cost impact (20%)
            cost_score = metrics.cost_contribution_pct * 0.2

            # Retry exhaustion (10%)
            expected_attempts = profile.max_attempts / 2
            actual_attempts = metrics.avg_attempts
            retry_score = min(10, max(0, (actual_attempts - expected_attempts) / expected_attempts * 10))

            scores[stage] = drop_off_score + time_score + cost_score + retry_score

        # Sort by score
        sorted_stages = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_stages[0][0] if sorted_stages else PipelineStage.CONTACT
        secondary = [s[0] for s in sorted_stages[1:3] if s[1] > 5]

        return primary, secondary, scores

    def generate_recommendations(
        self,
        primary_bottleneck: PipelineStage,
        secondary_bottlenecks: List[PipelineStage]
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations for identified bottlenecks"""
        recommendations = []
        priority = 1

        all_bottlenecks = [primary_bottleneck] + secondary_bottlenecks

        for stage in all_bottlenecks:
            metrics = self.stage_metrics[stage]
            profile = MICRO_DEBT_STAGE_PROFILES[stage]

            # Conversion rate recommendation
            if metrics.conversion_rate < profile.base_conversion_rate:
                gap = profile.base_conversion_rate - metrics.conversion_rate
                target = min(profile.base_conversion_rate + profile.digital_boost, 0.95)

                actions = self._get_conversion_actions(stage, metrics)

                recommendations.append(OptimizationRecommendation(
                    stage=stage,
                    priority=priority,
                    category="conversion",
                    title=f"Improve {stage.value.title()} Conversion Rate",
                    description=f"Current conversion is {metrics.conversion_rate:.1%}, "
                               f"below expected {profile.base_conversion_rate:.1%}. "
                               f"Target {target:.1%} with optimizations.",
                    current_metric=metrics.conversion_rate,
                    target_metric=target,
                    improvement_pct=(target - metrics.conversion_rate) / metrics.conversion_rate * 100,
                    implementation_effort="medium",
                    expected_roi=gap * self.num_accounts * float(self.avg_balance) * 0.3,
                    specific_actions=actions,
                ))
                priority += 1

            # Time optimization recommendation
            if metrics.avg_time > profile.avg_time * 1.2:
                target_time = profile.avg_time

                actions = self._get_speed_actions(stage, metrics)

                recommendations.append(OptimizationRecommendation(
                    stage=stage,
                    priority=priority,
                    category="speed",
                    title=f"Reduce {stage.value.title()} Processing Time",
                    description=f"Average time {metrics.avg_time:.1f}h exceeds target "
                               f"{target_time:.1f}h by {(metrics.avg_time/target_time - 1)*100:.0f}%.",
                    current_metric=metrics.avg_time,
                    target_metric=target_time,
                    improvement_pct=(metrics.avg_time - target_time) / metrics.avg_time * 100,
                    implementation_effort="low",
                    expected_roi=self.num_accounts * 0.01,  # Faster collection = better cash flow
                    specific_actions=actions,
                ))
                priority += 1

            # Cost optimization recommendation
            if metrics.cost_contribution_pct > 25:
                target_cost_pct = 20.0

                actions = self._get_cost_actions(stage, metrics)

                recommendations.append(OptimizationRecommendation(
                    stage=stage,
                    priority=priority,
                    category="cost",
                    title=f"Reduce {stage.value.title()} Cost Contribution",
                    description=f"Stage contributes {metrics.cost_contribution_pct:.1f}% of total cost. "
                               f"Target reduction to {target_cost_pct:.1f}%.",
                    current_metric=metrics.cost_contribution_pct,
                    target_metric=target_cost_pct,
                    improvement_pct=(metrics.cost_contribution_pct - target_cost_pct) / metrics.cost_contribution_pct * 100,
                    implementation_effort="medium",
                    expected_roi=float(metrics.total_cost) * 0.2,
                    specific_actions=actions,
                ))
                priority += 1

            # Retry strategy optimization
            if metrics.avg_attempts > profile.max_attempts * 0.7:
                actions = self._get_retry_actions(stage, metrics)

                recommendations.append(OptimizationRecommendation(
                    stage=stage,
                    priority=priority,
                    category="retry",
                    title=f"Optimize {stage.value.title()} Retry Strategy",
                    description=f"Average {metrics.avg_attempts:.1f} attempts indicates "
                               f"retry exhaustion. Optimize retry timing and channels.",
                    current_metric=metrics.avg_attempts,
                    target_metric=profile.max_attempts * 0.5,
                    improvement_pct=30.0,
                    implementation_effort="low",
                    expected_roi=float(metrics.total_cost) * 0.15,
                    specific_actions=actions,
                ))
                priority += 1

        # Add top drop-off reason recommendations
        for stage in all_bottlenecks[:2]:
            metrics = self.stage_metrics[stage]

            if metrics.drop_off_reasons:
                top_reason = max(metrics.drop_off_reasons.items(), key=lambda x: x[1])
                reason_name, reason_count = top_reason
                reason_pct = reason_count / metrics.accounts_entered * 100

                if reason_pct > 5:
                    actions = self._get_dropoff_actions(stage, reason_name)

                    recommendations.append(OptimizationRecommendation(
                        stage=stage,
                        priority=priority,
                        category="drop_off",
                        title=f"Address '{reason_name}' Drop-off in {stage.value.title()}",
                        description=f"'{reason_name}' causes {reason_pct:.1f}% drop-off "
                                   f"({reason_count:,} accounts). Targeted intervention needed.",
                        current_metric=reason_pct,
                        target_metric=reason_pct * 0.5,
                        improvement_pct=50.0,
                        implementation_effort="medium",
                        expected_roi=reason_count * float(self.avg_balance) * 0.25,
                        specific_actions=actions,
                    ))
                    priority += 1

        return recommendations

    def _get_conversion_actions(self, stage: PipelineStage, metrics: StageMetrics) -> List[str]:
        """Get specific actions to improve conversion"""
        actions_map = {
            PipelineStage.ACQUIRE: [
                "Implement real-time data validation at ingestion",
                "Add fuzzy matching for duplicate detection",
                "Pre-screen for bankruptcy via API integration",
                "Enhance compliance pre-checks with state-specific rules",
            ],
            PipelineStage.LOCATE: [
                "Integrate secondary skip trace provider for failed lookups",
                "Add social media contact discovery",
                "Implement address validation and standardization",
                "Use phone carrier lookup to validate mobile numbers",
            ],
            PipelineStage.CONTACT: [
                "Optimize SMS timing based on engagement data",
                "Implement A/B testing for message templates",
                "Add push notification channel for app users",
                "Personalize contact frequency based on debtor profile",
                "Use ML to predict optimal contact time per account",
            ],
            PipelineStage.NEGOTIATE: [
                "Deploy AI-powered settlement recommendation engine",
                "Implement dynamic settlement offers based on willingness",
                "Add hardship program pathways for eligible accounts",
                "Create payment plan options with flexible terms",
            ],
            PipelineStage.COLLECT: [
                "Enable one-click payment with saved methods",
                "Add Apple Pay and Google Pay integration",
                "Implement smart retry with alternative payment methods",
                "Optimize payment timing around paycheck cycles",
            ],
            PipelineStage.CLOSE: [
                "Automate reconciliation with client systems",
                "Implement instant payment confirmation",
                "Add digital receipt delivery options",
            ],
            PipelineStage.PROFIT: [
                "Optimize revenue recognition timing",
                "Implement real-time margin tracking",
            ],
        }
        return actions_map.get(stage, ["Review stage-specific optimizations"])

    def _get_speed_actions(self, stage: PipelineStage, metrics: StageMetrics) -> List[str]:
        """Get specific actions to improve processing speed"""
        actions_map = {
            PipelineStage.ACQUIRE: [
                "Implement batch processing with parallel validation",
                "Cache compliance check results",
                "Use async processing for non-blocking ingestion",
            ],
            PipelineStage.LOCATE: [
                "Implement parallel skip trace queries",
                "Cache recent lookup results",
                "Prioritize digital-native accounts for faster location",
            ],
            PipelineStage.CONTACT: [
                "Reduce retry delay for high-probability accounts",
                "Implement concurrent multi-channel outreach",
                "Auto-escalate non-responsive accounts earlier",
            ],
            PipelineStage.NEGOTIATE: [
                "Pre-approve settlement ranges to reduce negotiation rounds",
                "Implement instant approval for standard offers",
                "Use AI to predict acceptable settlement faster",
            ],
            PipelineStage.COLLECT: [
                "Implement instant payment confirmation",
                "Use faster ACH processing (same-day ACH)",
                "Enable immediate retry for declined cards",
            ],
            PipelineStage.CLOSE: [
                "Automate account closure workflow",
                "Implement real-time status updates to clients",
            ],
            PipelineStage.PROFIT: [
                "Automate revenue recognition",
            ],
        }
        return actions_map.get(stage, ["Implement stage-specific speed optimizations"])

    def _get_cost_actions(self, stage: PipelineStage, metrics: StageMetrics) -> List[str]:
        """Get specific actions to reduce costs"""
        actions_map = {
            PipelineStage.ACQUIRE: [
                "Negotiate volume discounts with data providers",
                "Implement selective validation (risk-based)",
            ],
            PipelineStage.LOCATE: [
                "Use tiered skip trace (cheap first, expensive only if needed)",
                "Implement internal data enrichment before external calls",
                "Cache and reuse recent lookups across portfolios",
            ],
            PipelineStage.CONTACT: [
                "Prioritize SMS/email over voice calls (10x cheaper)",
                "Implement smart contact sequencing to minimize attempts",
                "Use predictive models to skip low-probability contacts",
                "Reduce max contact attempts for very low score accounts",
            ],
            PipelineStage.NEGOTIATE: [
                "Automate standard settlement offers (reduce human time)",
                "Use AI negotiation for first 3 rounds",
                "Implement self-service negotiation portal",
            ],
            PipelineStage.COLLECT: [
                "Negotiate lower payment processing fees",
                "Incentivize ACH over card payments (lower fees)",
                "Implement stored payment methods to reduce failures",
            ],
            PipelineStage.CLOSE: [
                "Automate reconciliation to reduce manual work",
            ],
            PipelineStage.PROFIT: [
                "Optimize reporting frequency to reduce compute",
            ],
        }
        return actions_map.get(stage, ["Review stage cost structure"])

    def _get_retry_actions(self, stage: PipelineStage, metrics: StageMetrics) -> List[str]:
        """Get specific actions to optimize retry strategy"""
        actions_map = {
            PipelineStage.LOCATE: [
                "Increase delay between skip trace retries",
                "Use different data sources for each retry",
                "Implement waterfall lookup strategy",
            ],
            PipelineStage.CONTACT: [
                "Implement exponential backoff for non-responders",
                "Rotate channels more aggressively (SMS -> email -> push)",
                "Reduce total attempts for accounts with zero engagement",
                "Add 're-engagement' campaign after cooling-off period",
            ],
            PipelineStage.NEGOTIATE: [
                "Reduce negotiation rounds with AI-optimized offers",
                "Implement final offer earlier in sequence",
                "Add time-limited offers to accelerate decisions",
            ],
            PipelineStage.COLLECT: [
                "Smart retry timing based on bank processing windows",
                "Try alternative payment methods after first failure",
                "Implement payment plan fallback after 2 failed attempts",
            ],
        }
        return actions_map.get(stage, ["Optimize retry timing and channels"])

    def _get_dropoff_actions(self, stage: PipelineStage, reason: str) -> List[str]:
        """Get specific actions to address drop-off reasons"""
        actions_map = {
            "invalid_data": [
                "Implement data cleansing at source",
                "Add real-time validation feedback to data providers",
                "Create data quality scorecards for clients",
            ],
            "skip_trace_failed": [
                "Add fallback skip trace providers",
                "Implement social media lookup as secondary source",
                "Use address history for alternative contacts",
            ],
            "no_response": [
                "Test different message templates and timing",
                "Add new contact channels (push, app)",
                "Implement re-engagement campaigns",
                "Use predictive models to optimize contact strategy",
            ],
            "disputed": [
                "Streamline dispute resolution workflow",
                "Implement automated dispute documentation",
                "Add proactive dispute prevention messaging",
            ],
            "refused_to_pay": [
                "Improve settlement offer personalization",
                "Add hardship screening and payment plan options",
                "Implement empathy-focused communication",
            ],
            "payment_failed": [
                "Add smart retry with alternative payment methods",
                "Implement stored payment credentials",
                "Optimize retry timing around paycheck cycles",
            ],
            "insufficient_funds": [
                "Implement payment timing optimization",
                "Add payment splitting options",
                "Offer flexible payment dates",
            ],
        }
        return actions_map.get(reason, [
            f"Investigate root cause of '{reason}'",
            "Implement targeted intervention program",
            "Add monitoring and alerting for this issue",
        ])

    def generate_report(self) -> BottleneckReport:
        """Generate complete bottleneck analysis report"""
        # Calculate metrics
        self.calculate_metrics()

        # Identify bottlenecks
        primary, secondary, scores = self.identify_bottlenecks()

        # Generate recommendations
        recommendations = self.generate_recommendations(primary, secondary)

        # Calculate overall metrics
        total_balance = sum(a.balance for a in self.accounts)
        total_collected = sum(a.amount_collected for a in self.accounts)
        total_cost = sum(a.total_cost for a in self.accounts)

        collected_accounts = sum(1 for a in self.accounts if a.final_status == "collected")

        net_revenue = total_collected - total_cost
        profit_margin = float(net_revenue / total_collected) if total_collected > 0 else 0
        roi = float(net_revenue / total_cost) if total_cost > 0 else 0

        avg_pipeline_time = statistics.mean(a.total_time_hours for a in self.accounts)
        avg_cost = total_cost / len(self.accounts)

        # Project improvements
        total_improvement = sum(r.expected_roi for r in recommendations)
        projected_improvement = {
            "total_expected_revenue_increase": total_improvement,
            "projected_conversion_lift": 0.05,  # 5% lift from recommendations
            "projected_cost_reduction": 0.15,   # 15% cost reduction
            "projected_time_reduction": 0.20,   # 20% time reduction
            "projected_new_recovery_rate": (
                collected_accounts / len(self.accounts) * 1.05
            ),
        }

        self.report = BottleneckReport(
            analysis_timestamp=datetime.utcnow(),
            simulation_config={
                "num_accounts": self.num_accounts,
                "avg_balance": float(self.avg_balance),
                "digital_native_rate": self.digital_native_rate,
            },
            total_accounts_simulated=len(self.accounts),
            total_accounts_collected=collected_accounts,
            overall_conversion_rate=collected_accounts / len(self.accounts),
            overall_collection_rate=float(total_collected / total_balance) if total_balance > 0 else 0,
            total_balance=total_balance,
            total_collected=total_collected,
            total_cost=total_cost,
            net_revenue=net_revenue,
            profit_margin=profit_margin,
            roi=roi,
            avg_pipeline_time_hours=avg_pipeline_time,
            avg_cost_per_account=avg_cost,
            stage_metrics=self.stage_metrics,
            transition_metrics=self.transition_metrics,
            primary_bottleneck=primary,
            secondary_bottlenecks=secondary,
            bottleneck_scores=scores,
            recommendations=recommendations,
            projected_improvement=projected_improvement,
        )

        return self.report

    async def run_analysis(self) -> BottleneckReport:
        """Run complete bottleneck analysis"""
        logger.info("Starting bottleneck analysis...")
        logger.info(f"Configuration: {self.num_accounts:,} accounts, "
                   f"avg balance ${self.avg_balance}")

        # Generate accounts
        self.generate_accounts()

        # Run simulation
        await self.simulate_pipeline()

        # Generate report
        report = self.generate_report()

        logger.info("Bottleneck analysis complete")
        return report


# =============================================================================
# REPORT PRINTING
# =============================================================================

def print_bottleneck_report(report: BottleneckReport) -> None:
    """Print formatted bottleneck analysis report"""

    print("\n" + "=" * 85)
    print("  QUAN COLLECTION INTELLIGENCE - WORKFLOW BOTTLENECK ANALYSIS")
    print("  Sub-$1K Micro-Debt Pipeline Optimization Report")
    print("=" * 85)

    print(f"\n  Analysis Timestamp: {report.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Accounts Simulated: {report.total_accounts_simulated:,}")

    # Overall Performance
    print(f"\n  OVERALL PIPELINE PERFORMANCE")
    print("  " + "-" * 81)
    print(f"    Total Balance:           ${report.total_balance:,.2f}")
    print(f"    Total Collected:         ${report.total_collected:,.2f}")
    print(f"    Overall Recovery Rate:   {report.overall_collection_rate:.1%}")
    print(f"    Accounts Collected:      {report.total_accounts_collected:,} "
          f"({report.overall_conversion_rate:.1%})")
    print(f"    Total Cost:              ${report.total_cost:,.2f}")
    print(f"    Net Revenue:             ${report.net_revenue:,.2f}")
    print(f"    Profit Margin:           {report.profit_margin:.1%}")
    print(f"    ROI:                     {report.roi:.0%}")
    print(f"    Avg Pipeline Time:       {report.avg_pipeline_time_hours:.1f} hours")
    print(f"    Avg Cost per Account:    ${report.avg_cost_per_account:.3f}")

    # Stage-by-Stage Metrics
    print(f"\n  STAGE-BY-STAGE ANALYSIS")
    print("  " + "-" * 81)
    print(f"  {'Stage':<12} {'Entered':>10} {'Converted':>10} {'Rate':>8} "
          f"{'Avg Time':>10} {'Cost %':>8} {'AI Rate':>8}")
    print("  " + "-" * 81)

    for stage in PipelineStage:
        metrics = report.stage_metrics[stage]
        print(f"  {stage.value:<12} {metrics.accounts_entered:>10,} "
              f"{metrics.accounts_converted:>10,} "
              f"{metrics.conversion_rate:>7.1%} "
              f"{metrics.avg_time:>9.1f}h "
              f"{metrics.cost_contribution_pct:>7.1f}% "
              f"{metrics.ai_utilization_rate:>7.1%}")

    # Bottleneck Identification
    print(f"\n  BOTTLENECK IDENTIFICATION")
    print("  " + "-" * 81)
    print(f"    PRIMARY BOTTLENECK:     {report.primary_bottleneck.value.upper()}")
    if report.secondary_bottlenecks:
        print(f"    Secondary Bottlenecks:  {', '.join(s.value for s in report.secondary_bottlenecks)}")

    print(f"\n    Bottleneck Scores (higher = worse):")
    sorted_scores = sorted(report.bottleneck_scores.items(), key=lambda x: x[1], reverse=True)
    for stage, score in sorted_scores[:5]:
        bar = "#" * int(score / 2)
        print(f"      {stage.value:<12} {score:>6.1f}  {bar}")

    # Drop-off Analysis
    print(f"\n  TOP DROP-OFF REASONS BY STAGE")
    print("  " + "-" * 81)

    for stage in [PipelineStage.CONTACT, PipelineStage.NEGOTIATE, PipelineStage.LOCATE]:
        metrics = report.stage_metrics[stage]
        if metrics.drop_off_reasons:
            print(f"\n    {stage.value.upper()}:")
            sorted_reasons = sorted(metrics.drop_off_reasons.items(), key=lambda x: x[1], reverse=True)
            for reason, count in sorted_reasons[:3]:
                pct = count / metrics.accounts_entered * 100
                print(f"      - {reason:<30} {count:>7,} ({pct:.1f}%)")

    # Transition Metrics
    print(f"\n  STAGE TRANSITION ANALYSIS")
    print("  " + "-" * 81)
    print(f"  {'Transition':<25} {'Attempted':>12} {'Success':>10} {'Failed':>10} {'Rate':>8}")
    print("  " + "-" * 81)

    for trans in report.transition_metrics:
        label = f"{trans.from_stage.value} -> {trans.to_stage.value}"
        print(f"  {label:<25} {trans.accounts_attempted:>12,} "
              f"{trans.accounts_succeeded:>10,} "
              f"{trans.accounts_failed:>10,} "
              f"{trans.success_rate:>7.1%}")

    # Recommendations
    print(f"\n  OPTIMIZATION RECOMMENDATIONS")
    print("  " + "=" * 81)

    for i, rec in enumerate(report.recommendations[:8], 1):
        print(f"\n  [{i}] {rec.title}")
        print(f"      Stage: {rec.stage.value.upper()} | Priority: {rec.priority} | "
              f"Category: {rec.category}")
        print(f"      {rec.description}")
        print(f"      Current: {rec.current_metric:.2f} -> Target: {rec.target_metric:.2f} "
              f"(+{rec.improvement_pct:.0f}%)")
        print(f"      Effort: {rec.implementation_effort} | Expected ROI: ${rec.expected_roi:,.0f}")
        print(f"      Actions:")
        for action in rec.specific_actions[:3]:
            print(f"        - {action}")

    # Projected Improvements
    print(f"\n  PROJECTED IMPROVEMENTS (If All Recommendations Implemented)")
    print("  " + "-" * 81)
    proj = report.projected_improvement
    print(f"    Expected Revenue Increase:    ${proj['total_expected_revenue_increase']:,.0f}")
    print(f"    Projected Conversion Lift:    +{proj['projected_conversion_lift']:.0%}")
    print(f"    Projected Cost Reduction:     -{proj['projected_cost_reduction']:.0%}")
    print(f"    Projected Time Reduction:     -{proj['projected_time_reduction']:.0%}")
    print(f"    New Projected Recovery Rate:  {proj['projected_new_recovery_rate']:.1%}")

    print("\n" + "=" * 85)
    print("  END OF BOTTLENECK ANALYSIS REPORT")
    print("=" * 85 + "\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_bottleneck_analysis(
    num_accounts: int = 100_000,
    avg_balance: Decimal = Decimal("275"),
    digital_native_rate: float = 0.70,
    seed: Optional[int] = None
) -> BottleneckReport:
    """Run complete bottleneck analysis and print report"""

    analyzer = BottleneckAnalyzer(
        num_accounts=num_accounts,
        avg_balance=avg_balance,
        digital_native_rate=digital_native_rate,
        simulation_seed=seed,
    )

    report = await analyzer.run_analysis()
    print_bottleneck_report(report)

    return report


if __name__ == "__main__":
    asyncio.run(run_bottleneck_analysis(
        num_accounts=100_000,
        avg_balance=Decimal("275"),
        digital_native_rate=0.70,
        seed=42  # For reproducibility
    ))
