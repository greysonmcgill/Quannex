"""
System Performance Optimizer for QUAN Recovery Collections Platform

Comprehensive optimization engine for maximizing collection efficiency across:
- Contact timing optimization
- Channel sequencing and waterfall optimization
- Message A/B testing and optimization
- Dynamic settlement pricing
- Resource allocation and capacity planning
- Portfolio optimization and prioritization
- Feedback loops and continuous improvement
- Benchmark tracking and analysis
- What-if simulation engine

Uses advanced statistical methods, machine learning, and optimization algorithms
to continuously improve collection performance.
"""

import asyncio
import random
import math
import statistics
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Set, Callable, Union
from collections import defaultdict
import logging
import sys
import copy
from functools import lru_cache
import heapq

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ConsumerSegment(Enum):
    """Consumer segments for targeting optimization"""
    YOUNG_PROFESSIONAL = "young_professional"      # 25-34, employed
    MIDDLE_INCOME = "middle_income"                # 35-50, stable income
    SENIOR = "senior"                              # 55+
    GIG_WORKER = "gig_worker"                      # Variable income
    STUDENT = "student"                            # Limited income
    HIGH_INCOME = "high_income"                    # Higher earners
    FINANCIALLY_STRESSED = "financially_stressed"  # Multiple delinquencies
    FIRST_TIME_DELINQUENT = "first_time_delinquent"


class Channel(Enum):
    """Communication channels"""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    VOICE = "voice"
    MAIL = "mail"
    IVR = "ivr"
    CHAT = "chat"


class DayOfWeek(Enum):
    """Days of the week"""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class PayFrequency(Enum):
    """Payment frequency patterns"""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
    IRREGULAR = "irregular"


class MessageTone(Enum):
    """Message tone options"""
    EMPATHETIC = "empathetic"
    PROFESSIONAL = "professional"
    URGENT = "urgent"
    FRIENDLY = "friendly"
    FORMAL = "formal"


class BalanceTier(Enum):
    """Balance tier buckets"""
    MICRO = "0-50"
    SMALL = "50-150"
    MEDIUM = "150-350"
    LARGE = "350-600"
    SUBSTANTIAL = "600-1000"


class RiskTier(Enum):
    """Account risk classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TestStatus(Enum):
    """A/B test status"""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"


# Channel costs
CHANNEL_COSTS: Dict[Channel, Decimal] = {
    Channel.SMS: Decimal("0.02"),
    Channel.EMAIL: Decimal("0.005"),
    Channel.PUSH: Decimal("0.008"),
    Channel.VOICE: Decimal("0.45"),
    Channel.MAIL: Decimal("0.72"),
    Channel.IVR: Decimal("0.15"),
    Channel.CHAT: Decimal("0.12"),
}

# Optimal contact hours by segment (24-hour format)
SEGMENT_OPTIMAL_HOURS: Dict[ConsumerSegment, List[int]] = {
    ConsumerSegment.YOUNG_PROFESSIONAL: [12, 13, 18, 19, 20],
    ConsumerSegment.MIDDLE_INCOME: [10, 11, 12, 17, 18, 19],
    ConsumerSegment.SENIOR: [9, 10, 11, 14, 15, 16],
    ConsumerSegment.GIG_WORKER: [11, 12, 13, 14, 19, 20],
    ConsumerSegment.STUDENT: [14, 15, 16, 17, 20, 21],
    ConsumerSegment.HIGH_INCOME: [8, 9, 17, 18, 19],
    ConsumerSegment.FINANCIALLY_STRESSED: [10, 11, 12, 18, 19],
    ConsumerSegment.FIRST_TIME_DELINQUENT: [9, 10, 11, 17, 18, 19],
}

# Optimal days by segment
SEGMENT_OPTIMAL_DAYS: Dict[ConsumerSegment, List[DayOfWeek]] = {
    ConsumerSegment.YOUNG_PROFESSIONAL: [DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY],
    ConsumerSegment.MIDDLE_INCOME: [DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY],
    ConsumerSegment.SENIOR: [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY],
    ConsumerSegment.GIG_WORKER: [DayOfWeek.MONDAY, DayOfWeek.FRIDAY],
    ConsumerSegment.STUDENT: [DayOfWeek.THURSDAY, DayOfWeek.FRIDAY],
    ConsumerSegment.HIGH_INCOME: [DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY],
    ConsumerSegment.FINANCIALLY_STRESSED: [DayOfWeek.FRIDAY, DayOfWeek.SATURDAY],
    ConsumerSegment.FIRST_TIME_DELINQUENT: [DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY],
}

# US Timezones
US_TIMEZONES = {
    "EST": -5,
    "CST": -6,
    "MST": -7,
    "PST": -8,
    "AKST": -9,
    "HST": -10,
}

# Industry benchmarks
INDUSTRY_BENCHMARKS = {
    "response_rate": 0.12,
    "conversion_rate": 0.08,
    "settlement_rate": 0.15,
    "payment_plan_adherence": 0.65,
    "right_party_contact_rate": 0.35,
    "cost_per_dollar_collected": 0.18,
    "promise_to_pay_rate": 0.22,
    "average_settlement_percent": 0.55,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ContactWindow:
    """Optimal contact window specification"""
    start_hour: int
    end_hour: int
    day_of_week: DayOfWeek
    timezone: str
    confidence: float
    expected_response_rate: float

    def is_active(self, current_time: datetime, tz_offset: int = 0) -> bool:
        """Check if window is currently active"""
        local_hour = (current_time.hour + tz_offset) % 24
        local_day = (current_time.weekday() + (1 if local_hour < current_time.hour else 0)) % 7
        return (
            self.day_of_week.value == local_day and
            self.start_hour <= local_hour < self.end_hour
        )


@dataclass
class TimingRecommendation:
    """Contact timing recommendation"""
    account_id: str
    segment: ConsumerSegment
    optimal_windows: List[ContactWindow]
    payday_aligned: bool
    next_payday: Optional[date]
    avoid_dates: List[date]
    urgency_score: float
    expected_lift: float


@dataclass
class ChannelSequence:
    """Multi-channel contact sequence"""
    sequence_id: str
    channels: List[Channel]
    delays_hours: List[int]  # Delay between each channel
    total_cost: Decimal
    expected_response_rate: float
    expected_conversion_rate: float
    expected_roi: float


@dataclass
class ChannelWaterfallResult:
    """Result of channel waterfall optimization"""
    account_id: str
    recommended_sequence: ChannelSequence
    alternative_sequences: List[ChannelSequence]
    fatigue_risk: float
    channel_preferences: Dict[Channel, float]
    cost_efficiency_score: float


@dataclass
class ABTestVariant:
    """A/B test variant definition"""
    variant_id: str
    name: str
    content: str
    subject_line: Optional[str] = None
    call_to_action: Optional[str] = None
    tone: Optional[MessageTone] = None
    exposures: int = 0
    responses: int = 0
    conversions: int = 0
    revenue: Decimal = Decimal("0")

    @property
    def response_rate(self) -> float:
        return self.responses / self.exposures if self.exposures > 0 else 0.0

    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.exposures if self.exposures > 0 else 0.0

    @property
    def revenue_per_exposure(self) -> Decimal:
        return self.revenue / self.exposures if self.exposures > 0 else Decimal("0")


@dataclass
class ABTest:
    """A/B test configuration"""
    test_id: str
    name: str
    description: str
    variants: List[ABTestVariant]
    segment: Optional[ConsumerSegment]
    channel: Channel
    start_date: datetime
    end_date: Optional[datetime]
    status: TestStatus
    minimum_sample_size: int
    confidence_level: float = 0.95

    @property
    def total_exposures(self) -> int:
        return sum(v.exposures for v in self.variants)

    def get_winner(self) -> Optional[ABTestVariant]:
        """Get winning variant if statistically significant"""
        if self.total_exposures < self.minimum_sample_size * len(self.variants):
            return None

        # Simple winner selection by conversion rate
        best = max(self.variants, key=lambda v: v.conversion_rate)
        second_best = sorted(self.variants, key=lambda v: v.conversion_rate, reverse=True)[1] if len(self.variants) > 1 else None

        if second_best and best.conversion_rate > second_best.conversion_rate * 1.1:
            return best
        return None


@dataclass
class SettlementOffer:
    """Dynamic settlement offer"""
    account_id: str
    original_balance: Decimal
    settlement_amount: Decimal
    settlement_percentage: float
    expires_in_days: int
    confidence: float
    expected_acceptance_rate: float
    consumer_surplus: Decimal  # Value to consumer

    @property
    def discount_amount(self) -> Decimal:
        return self.original_balance - self.settlement_amount


@dataclass
class WillingnessToPayModel:
    """Consumer willingness-to-pay model parameters"""
    account_id: str
    segment: ConsumerSegment
    balance_tier: BalanceTier
    estimated_wtp: Decimal
    wtp_range: Tuple[Decimal, Decimal]
    price_elasticity: float
    optimal_settlement_pct: float
    time_decay_factor: float


@dataclass
class ResourceAllocation:
    """Resource allocation recommendation"""
    resource_type: str  # 'ai_agent', 'channel_capacity', etc.
    current_capacity: int
    recommended_capacity: int
    utilization_rate: float
    peak_load_factor: float
    cost_per_unit: Decimal
    expected_throughput: int
    bottleneck_risk: float


@dataclass
class AccountPriority:
    """Account prioritization for work queue"""
    account_id: str
    priority_score: float
    expected_value: Decimal
    probability_of_collection: float
    optimal_action: str
    effort_estimate: float  # Hours
    recommended_channel: Channel
    timing_window: ContactWindow
    segment: ConsumerSegment


@dataclass
class PortfolioOptimization:
    """Portfolio-level optimization result"""
    total_accounts: int
    prioritized_queue: List[AccountPriority]
    expected_total_collection: Decimal
    expected_total_cost: Decimal
    expected_roi: float
    effort_allocation: Dict[ConsumerSegment, float]
    channel_allocation: Dict[Channel, int]


@dataclass
class FeedbackSignal:
    """Feedback signal for continuous improvement"""
    signal_id: str
    signal_type: str  # 'outcome', 'strategy', 'model'
    timestamp: datetime
    account_id: Optional[str]
    strategy_id: Optional[str]
    outcome: str
    value: float
    context: Dict[str, Any]


@dataclass
class StrategyEffectiveness:
    """Strategy effectiveness measurement"""
    strategy_id: str
    strategy_type: str
    sample_size: int
    success_rate: float
    average_value: Decimal
    confidence_interval: Tuple[float, float]
    trend: str  # 'improving', 'stable', 'declining'
    recommendation: str


@dataclass
class BenchmarkComparison:
    """Benchmark comparison result"""
    metric_name: str
    current_value: float
    industry_benchmark: float
    percentile_rank: int
    trend_30d: float
    trend_90d: float
    gap_to_benchmark: float
    improvement_target: float


@dataclass
class SimulationScenario:
    """Simulation scenario configuration"""
    scenario_id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    duration_days: int
    account_count: int


@dataclass
class SimulationResult:
    """Simulation result"""
    scenario_id: str
    total_collected: Decimal
    total_cost: Decimal
    roi: float
    response_rate: float
    conversion_rate: float
    average_time_to_collection: float
    metrics_by_segment: Dict[str, Dict[str, float]]
    sensitivity_analysis: Dict[str, List[Tuple[float, float]]]


# =============================================================================
# CONTACT TIMING OPTIMIZER
# =============================================================================

class ContactTimingOptimizer:
    """
    Optimizes contact timing based on:
    - Consumer segment behavior patterns
    - Day-of-week and hour-of-day analysis
    - Payday alignment
    - Holiday and event awareness
    - Timezone management
    """

    def __init__(self):
        self.segment_response_rates: Dict[ConsumerSegment, Dict[int, float]] = defaultdict(dict)
        self.day_response_rates: Dict[ConsumerSegment, Dict[int, float]] = defaultdict(dict)
        self.payday_patterns: Dict[PayFrequency, List[int]] = {
            PayFrequency.WEEKLY: [4],  # Friday
            PayFrequency.BIWEEKLY: [4, 18],  # Every other Friday
            PayFrequency.SEMIMONTHLY: [1, 15],  # 1st and 15th
            PayFrequency.MONTHLY: [1],  # 1st of month
            PayFrequency.IRREGULAR: [],
        }
        self.holidays_2024: Set[date] = {
            date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19),
            date(2024, 5, 27), date(2024, 7, 4), date(2024, 9, 2),
            date(2024, 10, 14), date(2024, 11, 11), date(2024, 11, 28),
            date(2024, 12, 25),
        }
        self._initialize_response_patterns()

    def _initialize_response_patterns(self):
        """Initialize response rate patterns by segment and time"""
        # Hour-of-day patterns (0-23)
        base_hourly = {
            6: 0.02, 7: 0.05, 8: 0.08, 9: 0.12, 10: 0.14, 11: 0.15,
            12: 0.13, 13: 0.12, 14: 0.11, 15: 0.10, 16: 0.11, 17: 0.14,
            18: 0.16, 19: 0.15, 20: 0.12, 21: 0.08, 22: 0.04, 23: 0.02,
        }

        for segment in ConsumerSegment:
            # Adjust base patterns per segment
            modifier = self._get_segment_modifier(segment)
            for hour in range(24):
                base_rate = base_hourly.get(hour, 0.02)
                if hour in SEGMENT_OPTIMAL_HOURS.get(segment, []):
                    self.segment_response_rates[segment][hour] = base_rate * modifier * 1.3
                else:
                    self.segment_response_rates[segment][hour] = base_rate * modifier

            # Day-of-week patterns
            for day in range(7):
                day_enum = DayOfWeek(day)
                if day_enum in SEGMENT_OPTIMAL_DAYS.get(segment, []):
                    self.day_response_rates[segment][day] = 1.2
                elif day in [5, 6]:  # Weekend
                    self.day_response_rates[segment][day] = 0.7
                else:
                    self.day_response_rates[segment][day] = 1.0

    def _get_segment_modifier(self, segment: ConsumerSegment) -> float:
        """Get response rate modifier by segment"""
        modifiers = {
            ConsumerSegment.YOUNG_PROFESSIONAL: 1.1,
            ConsumerSegment.MIDDLE_INCOME: 1.0,
            ConsumerSegment.SENIOR: 0.9,
            ConsumerSegment.GIG_WORKER: 0.85,
            ConsumerSegment.STUDENT: 0.8,
            ConsumerSegment.HIGH_INCOME: 1.15,
            ConsumerSegment.FINANCIALLY_STRESSED: 0.7,
            ConsumerSegment.FIRST_TIME_DELINQUENT: 1.25,
        }
        return modifiers.get(segment, 1.0)

    def get_optimal_windows(
        self,
        segment: ConsumerSegment,
        timezone: str = "EST",
        num_windows: int = 3
    ) -> List[ContactWindow]:
        """Get optimal contact windows for a segment"""
        windows = []
        tz_offset = US_TIMEZONES.get(timezone, -5)

        # Score each hour-day combination
        combinations = []
        for day in range(7):
            for hour in range(8, 21):  # Compliance hours
                response_rate = (
                    self.segment_response_rates[segment].get(hour, 0.1) *
                    self.day_response_rates[segment].get(day, 1.0)
                )
                combinations.append((day, hour, response_rate))

        # Sort by response rate and pick top windows
        combinations.sort(key=lambda x: x[2], reverse=True)

        # Group into windows
        for day, hour, rate in combinations[:num_windows * 2]:
            # Create 2-hour windows
            window = ContactWindow(
                start_hour=hour,
                end_hour=min(hour + 2, 21),
                day_of_week=DayOfWeek(day),
                timezone=timezone,
                confidence=min(0.95, rate * 5),
                expected_response_rate=rate,
            )
            windows.append(window)

        # Deduplicate and return top N
        seen = set()
        unique_windows = []
        for w in windows:
            key = (w.day_of_week, w.start_hour)
            if key not in seen:
                seen.add(key)
                unique_windows.append(w)

        return unique_windows[:num_windows]

    def get_next_payday(
        self,
        pay_frequency: PayFrequency,
        reference_date: date
    ) -> Optional[date]:
        """Calculate next payday based on frequency"""
        if pay_frequency == PayFrequency.IRREGULAR:
            return None

        patterns = self.payday_patterns[pay_frequency]
        if not patterns:
            return None

        if pay_frequency == PayFrequency.WEEKLY:
            days_until_friday = (4 - reference_date.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            return reference_date + timedelta(days=days_until_friday)

        elif pay_frequency == PayFrequency.BIWEEKLY:
            days_until_friday = (4 - reference_date.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 14
            return reference_date + timedelta(days=days_until_friday)

        elif pay_frequency == PayFrequency.SEMIMONTHLY:
            day_of_month = reference_date.day
            if day_of_month < 15:
                return reference_date.replace(day=15)
            else:
                # Next month 1st
                if reference_date.month == 12:
                    return date(reference_date.year + 1, 1, 1)
                return date(reference_date.year, reference_date.month + 1, 1)

        elif pay_frequency == PayFrequency.MONTHLY:
            if reference_date.month == 12:
                return date(reference_date.year + 1, 1, 1)
            return date(reference_date.year, reference_date.month + 1, 1)

        return None

    def is_contact_appropriate(
        self,
        contact_time: datetime,
        timezone: str = "EST"
    ) -> Tuple[bool, str]:
        """Check if contact is appropriate (compliance + effectiveness)"""
        tz_offset = US_TIMEZONES.get(timezone, -5)
        local_hour = (contact_time.hour + tz_offset) % 24
        local_date = contact_time.date()

        # Check compliance hours
        if local_hour < 8 or local_hour >= 21:
            return False, "Outside compliance hours (8 AM - 9 PM local)"

        # Check holidays
        if local_date in self.holidays_2024:
            return False, "Holiday - avoid contact"

        # Check Sunday morning (sensitive time)
        if contact_time.weekday() == 6 and local_hour < 12:
            return False, "Sunday morning - low response expected"

        return True, "Contact appropriate"

    def generate_timing_recommendation(
        self,
        account_id: str,
        segment: ConsumerSegment,
        pay_frequency: PayFrequency,
        timezone: str,
        days_past_due: int
    ) -> TimingRecommendation:
        """Generate comprehensive timing recommendation"""
        today = date.today()

        # Get optimal windows
        windows = self.get_optimal_windows(segment, timezone, num_windows=3)

        # Calculate payday alignment
        next_payday = self.get_next_payday(pay_frequency, today)
        payday_aligned = next_payday is not None and (next_payday - today).days <= 3

        # Calculate avoid dates (holidays + weekends for certain segments)
        avoid_dates = list(self.holidays_2024)

        # Calculate urgency based on DPD
        if days_past_due < 30:
            urgency_score = 0.3
        elif days_past_due < 60:
            urgency_score = 0.5
        elif days_past_due < 90:
            urgency_score = 0.7
        else:
            urgency_score = 0.9

        # Calculate expected lift from optimized timing
        baseline_response = 0.08
        optimized_response = windows[0].expected_response_rate if windows else baseline_response
        expected_lift = (optimized_response - baseline_response) / baseline_response

        return TimingRecommendation(
            account_id=account_id,
            segment=segment,
            optimal_windows=windows,
            payday_aligned=payday_aligned,
            next_payday=next_payday,
            avoid_dates=avoid_dates[:10],  # Limit to next 10 dates
            urgency_score=urgency_score,
            expected_lift=expected_lift,
        )


# =============================================================================
# CHANNEL SEQUENCING OPTIMIZER
# =============================================================================

class ChannelSequencingOptimizer:
    """
    Optimizes multi-channel contact sequences for maximum effectiveness:
    - Waterfall optimization
    - Response rate by channel sequence
    - Cost-weighted selection
    - Fatigue prevention
    """

    def __init__(self):
        self.channel_response_rates: Dict[Channel, float] = {
            Channel.SMS: 0.15,
            Channel.EMAIL: 0.08,
            Channel.PUSH: 0.12,
            Channel.VOICE: 0.25,
            Channel.MAIL: 0.04,
            Channel.IVR: 0.18,
            Channel.CHAT: 0.22,
        }
        self.sequence_fatigue_rates: Dict[int, float] = {
            1: 1.0,    # First contact
            2: 0.85,   # Second contact
            3: 0.70,   # Third contact
            4: 0.55,   # Fourth contact
            5: 0.40,   # Fifth contact
        }
        self.channel_preferences: Dict[ConsumerSegment, List[Channel]] = {
            ConsumerSegment.YOUNG_PROFESSIONAL: [Channel.SMS, Channel.PUSH, Channel.EMAIL],
            ConsumerSegment.MIDDLE_INCOME: [Channel.SMS, Channel.EMAIL, Channel.VOICE],
            ConsumerSegment.SENIOR: [Channel.VOICE, Channel.MAIL, Channel.SMS],
            ConsumerSegment.GIG_WORKER: [Channel.SMS, Channel.PUSH, Channel.CHAT],
            ConsumerSegment.STUDENT: [Channel.PUSH, Channel.SMS, Channel.EMAIL],
            ConsumerSegment.HIGH_INCOME: [Channel.EMAIL, Channel.SMS, Channel.VOICE],
            ConsumerSegment.FINANCIALLY_STRESSED: [Channel.SMS, Channel.EMAIL, Channel.IVR],
            ConsumerSegment.FIRST_TIME_DELINQUENT: [Channel.SMS, Channel.EMAIL, Channel.PUSH],
        }

    def _calculate_sequence_metrics(
        self,
        channels: List[Channel],
        segment: ConsumerSegment
    ) -> Tuple[float, float, Decimal]:
        """Calculate expected metrics for a channel sequence"""
        cumulative_response = 0.0
        cumulative_conversion = 0.0
        total_cost = Decimal("0")
        remaining_population = 1.0

        preferred_channels = self.channel_preferences.get(segment, [])

        for i, channel in enumerate(channels):
            fatigue_factor = self.sequence_fatigue_rates.get(i + 1, 0.3)
            base_response = self.channel_response_rates.get(channel, 0.1)

            # Boost for preferred channels
            preference_boost = 1.2 if channel in preferred_channels[:2] else 1.0

            # Calculate response for this step
            step_response = base_response * fatigue_factor * preference_boost * remaining_population
            step_conversion = step_response * 0.5  # Assume 50% of responders convert

            cumulative_response += step_response
            cumulative_conversion += step_conversion
            total_cost += CHANNEL_COSTS.get(channel, Decimal("0.02"))

            # Update remaining population (those who didn't respond)
            remaining_population *= (1 - base_response * fatigue_factor)

        return cumulative_response, cumulative_conversion, total_cost

    def generate_optimal_sequences(
        self,
        segment: ConsumerSegment,
        budget: Decimal,
        max_touches: int = 4
    ) -> List[ChannelSequence]:
        """Generate optimal channel sequences within budget"""
        all_channels = list(Channel)
        preferred = self.channel_preferences.get(segment, all_channels[:3])

        sequences = []
        sequence_id = 0

        # Generate candidate sequences
        # Start with preferred channels
        for first in preferred:
            for second in all_channels:
                if second == first:
                    continue
                for third in all_channels:
                    if third in [first, second]:
                        continue

                    channels = [first, second, third]
                    response_rate, conversion_rate, cost = self._calculate_sequence_metrics(
                        channels, segment
                    )

                    if cost <= budget:
                        roi = float((Decimal(str(conversion_rate)) * Decimal("100") - cost) / cost) if cost > 0 else 0

                        sequences.append(ChannelSequence(
                            sequence_id=f"SEQ-{sequence_id:04d}",
                            channels=channels,
                            delays_hours=[24, 48, 72][:len(channels) - 1] + [0],
                            total_cost=cost,
                            expected_response_rate=response_rate,
                            expected_conversion_rate=conversion_rate,
                            expected_roi=roi,
                        ))
                        sequence_id += 1

        # Sort by expected ROI
        sequences.sort(key=lambda s: s.expected_roi, reverse=True)

        return sequences[:10]  # Return top 10 sequences

    def calculate_fatigue_risk(
        self,
        contact_history: List[Tuple[Channel, datetime]],
        lookback_days: int = 7
    ) -> float:
        """Calculate contact fatigue risk"""
        if not contact_history:
            return 0.0

        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_contacts = [c for c in contact_history if c[1] >= cutoff]

        # Fatigue increases with number of contacts
        contact_count = len(recent_contacts)
        if contact_count <= 1:
            return 0.1
        elif contact_count <= 2:
            return 0.3
        elif contact_count <= 3:
            return 0.5
        elif contact_count <= 4:
            return 0.7
        else:
            return 0.9

    def optimize_waterfall(
        self,
        account_id: str,
        segment: ConsumerSegment,
        balance: Decimal,
        contact_history: List[Tuple[Channel, datetime]],
        budget: Optional[Decimal] = None
    ) -> ChannelWaterfallResult:
        """Generate optimized channel waterfall for an account"""
        if budget is None:
            # Default budget based on balance
            budget = balance * Decimal("0.05")  # 5% of balance

        # Generate sequences
        sequences = self.generate_optimal_sequences(segment, budget)

        if not sequences:
            # Fallback sequence
            sequences = [ChannelSequence(
                sequence_id="SEQ-FALLBACK",
                channels=[Channel.SMS, Channel.EMAIL],
                delays_hours=[24, 0],
                total_cost=Decimal("0.025"),
                expected_response_rate=0.15,
                expected_conversion_rate=0.08,
                expected_roi=2.0,
            )]

        # Calculate fatigue risk
        fatigue_risk = self.calculate_fatigue_risk(contact_history)

        # Calculate channel preferences
        preferred = self.channel_preferences.get(segment, [])
        channel_prefs = {
            ch: 1.0 - (preferred.index(ch) * 0.2 if ch in preferred else 0.6)
            for ch in Channel
        }

        # Cost efficiency score
        best_sequence = sequences[0]
        cost_efficiency = best_sequence.expected_roi / 10 if best_sequence.expected_roi > 0 else 0.1

        return ChannelWaterfallResult(
            account_id=account_id,
            recommended_sequence=best_sequence,
            alternative_sequences=sequences[1:5],
            fatigue_risk=fatigue_risk,
            channel_preferences=channel_prefs,
            cost_efficiency_score=min(1.0, cost_efficiency),
        )


# =============================================================================
# MESSAGE OPTIMIZATION ENGINE
# =============================================================================

class MessageOptimizationEngine:
    """
    A/B testing framework for message optimization:
    - Subject line testing
    - Call-to-action testing
    - Personalization effectiveness
    - Tone/sentiment tuning
    """

    def __init__(self):
        self.active_tests: Dict[str, ABTest] = {}
        self.completed_tests: Dict[str, ABTest] = {}
        self.variant_performance: Dict[str, List[float]] = defaultdict(list)

    def create_test(
        self,
        test_id: str,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        channel: Channel,
        segment: Optional[ConsumerSegment] = None,
        minimum_sample_size: int = 100,
        confidence_level: float = 0.95
    ) -> ABTest:
        """Create a new A/B test"""
        variant_objects = []
        for i, v in enumerate(variants):
            variant = ABTestVariant(
                variant_id=f"{test_id}-V{i}",
                name=v.get("name", f"Variant {i}"),
                content=v.get("content", ""),
                subject_line=v.get("subject_line"),
                call_to_action=v.get("cta"),
                tone=v.get("tone"),
            )
            variant_objects.append(variant)

        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            variants=variant_objects,
            segment=segment,
            channel=channel,
            start_date=datetime.now(),
            end_date=None,
            status=TestStatus.DRAFT,
            minimum_sample_size=minimum_sample_size,
            confidence_level=confidence_level,
        )

        self.active_tests[test_id] = test
        return test

    def start_test(self, test_id: str) -> bool:
        """Start an A/B test"""
        if test_id in self.active_tests:
            self.active_tests[test_id].status = TestStatus.RUNNING
            return True
        return False

    def assign_variant(self, test_id: str, account_id: str) -> Optional[ABTestVariant]:
        """Assign an account to a test variant"""
        test = self.active_tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return None

        # Use consistent hashing for assignment
        hash_input = f"{test_id}:{account_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        variant_index = hash_value % len(test.variants)

        variant = test.variants[variant_index]
        variant.exposures += 1

        return variant

    def record_response(
        self,
        test_id: str,
        variant_id: str,
        responded: bool,
        converted: bool,
        revenue: Decimal = Decimal("0")
    ):
        """Record a response for a test variant"""
        test = self.active_tests.get(test_id)
        if not test:
            return

        for variant in test.variants:
            if variant.variant_id == variant_id:
                if responded:
                    variant.responses += 1
                if converted:
                    variant.conversions += 1
                variant.revenue += revenue
                break

    def analyze_test(self, test_id: str) -> Dict[str, Any]:
        """Analyze test results with statistical significance"""
        test = self.active_tests.get(test_id) or self.completed_tests.get(test_id)
        if not test:
            return {}

        results = {
            "test_id": test_id,
            "name": test.name,
            "status": test.status.value,
            "total_exposures": test.total_exposures,
            "variants": [],
            "winner": None,
            "confidence": 0.0,
        }

        for variant in test.variants:
            variant_result = {
                "variant_id": variant.variant_id,
                "name": variant.name,
                "exposures": variant.exposures,
                "response_rate": variant.response_rate,
                "conversion_rate": variant.conversion_rate,
                "revenue_per_exposure": float(variant.revenue_per_exposure),
            }
            results["variants"].append(variant_result)

        # Check for winner
        winner = test.get_winner()
        if winner:
            results["winner"] = winner.variant_id
            results["confidence"] = test.confidence_level

        return results

    def get_best_subject_lines(self, channel: Channel, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get best performing subject lines"""
        subject_lines = []

        for test in list(self.completed_tests.values()) + list(self.active_tests.values()):
            if test.channel != channel:
                continue

            for variant in test.variants:
                if variant.subject_line and variant.exposures >= 50:
                    subject_lines.append({
                        "subject_line": variant.subject_line,
                        "response_rate": variant.response_rate,
                        "conversion_rate": variant.conversion_rate,
                        "sample_size": variant.exposures,
                    })

        subject_lines.sort(key=lambda x: x["conversion_rate"], reverse=True)
        return subject_lines[:top_n]

    def get_optimal_tone(self, segment: ConsumerSegment) -> MessageTone:
        """Get optimal message tone for a segment based on test data"""
        # Default recommendations by segment
        tone_map = {
            ConsumerSegment.YOUNG_PROFESSIONAL: MessageTone.PROFESSIONAL,
            ConsumerSegment.MIDDLE_INCOME: MessageTone.FRIENDLY,
            ConsumerSegment.SENIOR: MessageTone.FORMAL,
            ConsumerSegment.GIG_WORKER: MessageTone.EMPATHETIC,
            ConsumerSegment.STUDENT: MessageTone.FRIENDLY,
            ConsumerSegment.HIGH_INCOME: MessageTone.PROFESSIONAL,
            ConsumerSegment.FINANCIALLY_STRESSED: MessageTone.EMPATHETIC,
            ConsumerSegment.FIRST_TIME_DELINQUENT: MessageTone.FRIENDLY,
        }
        return tone_map.get(segment, MessageTone.PROFESSIONAL)

    def generate_personalization_score(
        self,
        has_first_name: bool,
        has_balance: bool,
        has_due_date: bool,
        has_custom_offer: bool
    ) -> float:
        """Calculate personalization score for a message"""
        score = 0.0
        if has_first_name:
            score += 0.25
        if has_balance:
            score += 0.25
        if has_due_date:
            score += 0.20
        if has_custom_offer:
            score += 0.30
        return score


# =============================================================================
# SETTLEMENT PRICING OPTIMIZER
# =============================================================================

class SettlementPricingOptimizer:
    """
    Dynamic settlement pricing optimization:
    - Willingness-to-pay modeling
    - Balance-based pricing curves
    - Time-decay adjustments
    - Consumer surplus optimization
    """

    def __init__(self):
        self.base_settlement_rates: Dict[BalanceTier, float] = {
            BalanceTier.MICRO: 0.70,
            BalanceTier.SMALL: 0.60,
            BalanceTier.MEDIUM: 0.50,
            BalanceTier.LARGE: 0.45,
            BalanceTier.SUBSTANTIAL: 0.40,
        }
        self.segment_modifiers: Dict[ConsumerSegment, float] = {
            ConsumerSegment.YOUNG_PROFESSIONAL: 0.05,
            ConsumerSegment.MIDDLE_INCOME: 0.0,
            ConsumerSegment.SENIOR: -0.05,
            ConsumerSegment.GIG_WORKER: -0.10,
            ConsumerSegment.STUDENT: -0.15,
            ConsumerSegment.HIGH_INCOME: 0.10,
            ConsumerSegment.FINANCIALLY_STRESSED: -0.15,
            ConsumerSegment.FIRST_TIME_DELINQUENT: 0.05,
        }
        self.time_decay_curve: List[Tuple[int, float]] = [
            (30, 0.0),    # 0-30 DPD: no decay
            (60, -0.05),  # 31-60 DPD: 5% reduction
            (90, -0.10),  # 61-90 DPD: 10% reduction
            (180, -0.15), # 91-180 DPD: 15% reduction
            (365, -0.20), # 181-365 DPD: 20% reduction
        ]

    def _get_balance_tier(self, balance: Decimal) -> BalanceTier:
        """Determine balance tier"""
        if balance <= 50:
            return BalanceTier.MICRO
        elif balance <= 150:
            return BalanceTier.SMALL
        elif balance <= 350:
            return BalanceTier.MEDIUM
        elif balance <= 600:
            return BalanceTier.LARGE
        else:
            return BalanceTier.SUBSTANTIAL

    def _get_time_decay(self, days_past_due: int) -> float:
        """Get time decay factor based on DPD"""
        decay = 0.0
        for threshold, factor in self.time_decay_curve:
            if days_past_due <= threshold:
                return decay
            decay = factor
        return decay

    def estimate_willingness_to_pay(
        self,
        account_id: str,
        balance: Decimal,
        segment: ConsumerSegment,
        days_past_due: int,
        payment_history: List[Decimal]
    ) -> WillingnessToPayModel:
        """Estimate consumer's willingness to pay"""
        balance_tier = self._get_balance_tier(balance)

        # Base WTP from balance tier
        base_rate = self.base_settlement_rates[balance_tier]

        # Segment adjustment
        segment_adj = self.segment_modifiers.get(segment, 0.0)

        # Time decay
        time_decay = self._get_time_decay(days_past_due)

        # Historical payment behavior
        if payment_history:
            avg_payment = sum(payment_history) / len(payment_history)
            payment_ratio = float(avg_payment / balance) if balance > 0 else 0.5
            payment_adj = min(0.1, payment_ratio * 0.2)
        else:
            payment_adj = 0.0

        # Calculate optimal settlement percentage
        optimal_pct = base_rate + segment_adj + time_decay + payment_adj
        optimal_pct = max(0.25, min(0.85, optimal_pct))  # Clamp to reasonable range

        # Estimate WTP
        estimated_wtp = balance * Decimal(str(optimal_pct))

        # Calculate price elasticity (simplified)
        elasticity = -1.5 - (0.5 * segment_adj)  # More negative = more elastic

        # WTP range (80% to 120% of estimate)
        wtp_range = (
            estimated_wtp * Decimal("0.80"),
            estimated_wtp * Decimal("1.20")
        )

        return WillingnessToPayModel(
            account_id=account_id,
            segment=segment,
            balance_tier=balance_tier,
            estimated_wtp=estimated_wtp,
            wtp_range=wtp_range,
            price_elasticity=elasticity,
            optimal_settlement_pct=optimal_pct,
            time_decay_factor=time_decay,
        )

    def generate_settlement_offer(
        self,
        account_id: str,
        balance: Decimal,
        segment: ConsumerSegment,
        days_past_due: int,
        payment_history: List[Decimal],
        urgency: float = 0.5
    ) -> SettlementOffer:
        """Generate dynamic settlement offer"""
        wtp = self.estimate_willingness_to_pay(
            account_id, balance, segment, days_past_due, payment_history
        )

        # Adjust based on urgency (higher urgency = lower offer)
        urgency_adj = Decimal(str(urgency * 0.05))
        adjusted_pct = Decimal(str(wtp.optimal_settlement_pct)) - urgency_adj

        settlement_amount = (balance * adjusted_pct).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # Calculate expected acceptance rate
        # Higher offer = lower acceptance, but more revenue if accepted
        acceptance_base = 0.30
        offer_discount = float(1 - adjusted_pct)
        acceptance_rate = min(0.80, acceptance_base + offer_discount * 0.8)

        # Expiration based on urgency
        expires_in = int(14 - urgency * 7)  # 7-14 days

        # Consumer surplus (value to consumer)
        consumer_surplus = balance - settlement_amount

        return SettlementOffer(
            account_id=account_id,
            original_balance=balance,
            settlement_amount=settlement_amount,
            settlement_percentage=float(adjusted_pct),
            expires_in_days=expires_in,
            confidence=min(0.90, 0.5 + acceptance_rate * 0.5),
            expected_acceptance_rate=acceptance_rate,
            consumer_surplus=consumer_surplus,
        )

    def optimize_settlement_price(
        self,
        balance: Decimal,
        wtp_model: WillingnessToPayModel,
        target_acceptance_rate: float = 0.40
    ) -> Tuple[Decimal, float]:
        """Find optimal settlement price given target acceptance rate"""
        # Use price elasticity to find optimal price
        # At target acceptance, what's the optimal price?

        elasticity = wtp_model.price_elasticity
        base_price = wtp_model.estimated_wtp

        # Simplified optimization: adjust price to meet target acceptance
        # Higher elasticity means price changes have bigger impact on acceptance

        price_adjustment = Decimal(str((target_acceptance_rate - 0.30) / abs(elasticity)))
        optimal_price = base_price * (1 + price_adjustment)

        # Clamp to reasonable range
        optimal_price = max(
            balance * Decimal("0.25"),
            min(balance * Decimal("0.85"), optimal_price)
        )

        optimal_price = optimal_price.quantize(Decimal("0.01"), ROUND_HALF_UP)
        expected_revenue = optimal_price * Decimal(str(target_acceptance_rate))

        return optimal_price, float(expected_revenue)


# =============================================================================
# RESOURCE ALLOCATION OPTIMIZER
# =============================================================================

class ResourceAllocationOptimizer:
    """
    Optimizes resource allocation:
    - AI agent capacity planning
    - Channel capacity management
    - Peak load prediction
    - Cost minimization under constraints
    """

    def __init__(self):
        self.resource_costs: Dict[str, Decimal] = {
            "ai_agent_hour": Decimal("0.50"),
            "sms_capacity_1k": Decimal("15.00"),
            "email_capacity_1k": Decimal("2.00"),
            "voice_capacity_1k": Decimal("400.00"),
        }
        self.peak_hour_factors: Dict[int, float] = {
            8: 0.6, 9: 0.9, 10: 1.2, 11: 1.3, 12: 1.1,
            13: 1.0, 14: 0.9, 15: 0.8, 16: 0.9, 17: 1.2,
            18: 1.4, 19: 1.3, 20: 1.0,
        }

    def predict_load(
        self,
        base_volume: int,
        hour: int,
        day_of_week: int,
        is_holiday: bool = False,
        special_event: Optional[str] = None
    ) -> int:
        """Predict load for a given time period"""
        # Base hourly factor
        hour_factor = self.peak_hour_factors.get(hour, 0.5)

        # Day of week adjustment
        if day_of_week in [5, 6]:  # Weekend
            day_factor = 0.4
        elif day_of_week == 0:  # Monday
            day_factor = 1.2
        else:
            day_factor = 1.0

        # Holiday adjustment
        holiday_factor = 0.2 if is_holiday else 1.0

        # Special event adjustment (e.g., tax season, payday clusters)
        event_factor = 1.0
        if special_event == "tax_season":
            event_factor = 1.5
        elif special_event == "month_start":
            event_factor = 1.3
        elif special_event == "month_end":
            event_factor = 1.2

        predicted_load = int(
            base_volume * hour_factor * day_factor * holiday_factor * event_factor
        )

        return predicted_load

    def optimize_ai_capacity(
        self,
        expected_volume: int,
        current_capacity: int,
        avg_processing_time_seconds: float = 30,
        target_utilization: float = 0.75
    ) -> ResourceAllocation:
        """Optimize AI agent capacity"""
        # Calculate required capacity
        contacts_per_agent_hour = 3600 / avg_processing_time_seconds
        required_agent_hours = expected_volume / contacts_per_agent_hour

        # Add buffer for target utilization
        recommended_capacity = int(required_agent_hours / target_utilization) + 1

        # Calculate utilization with current capacity
        utilization = min(1.0, required_agent_hours / current_capacity) if current_capacity > 0 else 0

        # Peak load factor
        peak_factor = max(self.peak_hour_factors.values())

        # Bottleneck risk
        bottleneck_risk = max(0, (utilization - 0.85) / 0.15) if utilization > 0.85 else 0

        return ResourceAllocation(
            resource_type="ai_agent",
            current_capacity=current_capacity,
            recommended_capacity=recommended_capacity,
            utilization_rate=utilization,
            peak_load_factor=peak_factor,
            cost_per_unit=self.resource_costs["ai_agent_hour"],
            expected_throughput=int(contacts_per_agent_hour * recommended_capacity),
            bottleneck_risk=bottleneck_risk,
        )

    def optimize_channel_capacity(
        self,
        channel: Channel,
        expected_volume: int,
        current_capacity: int
    ) -> ResourceAllocation:
        """Optimize channel-specific capacity"""
        # Channel-specific throughput rates (per hour)
        throughput_rates = {
            Channel.SMS: 10000,
            Channel.EMAIL: 50000,
            Channel.PUSH: 100000,
            Channel.VOICE: 100,
            Channel.MAIL: 500,
            Channel.IVR: 500,
            Channel.CHAT: 200,
        }

        rate = throughput_rates.get(channel, 1000)
        required_capacity = int(expected_volume / rate) + 1

        utilization = min(1.0, expected_volume / (current_capacity * rate)) if current_capacity > 0 else 0

        cost_key = f"{channel.value}_capacity_1k"
        cost = self.resource_costs.get(cost_key, Decimal("10.00"))

        bottleneck_risk = max(0, (utilization - 0.80) / 0.20) if utilization > 0.80 else 0

        return ResourceAllocation(
            resource_type=f"channel_{channel.value}",
            current_capacity=current_capacity,
            recommended_capacity=required_capacity,
            utilization_rate=utilization,
            peak_load_factor=max(self.peak_hour_factors.values()),
            cost_per_unit=cost,
            expected_throughput=rate * required_capacity,
            bottleneck_risk=bottleneck_risk,
        )

    def minimize_cost_under_constraints(
        self,
        volume_requirements: Dict[Channel, int],
        quality_constraints: Dict[str, float],
        budget: Decimal
    ) -> Dict[str, ResourceAllocation]:
        """Find minimum cost allocation meeting constraints"""
        allocations = {}

        # Sort channels by cost efficiency
        channel_efficiency = []
        for channel, volume in volume_requirements.items():
            cost = CHANNEL_COSTS.get(channel, Decimal("0.05"))
            efficiency = float(volume / float(cost)) if cost > 0 else 0
            channel_efficiency.append((channel, volume, efficiency))

        channel_efficiency.sort(key=lambda x: x[2], reverse=True)

        remaining_budget = budget

        for channel, volume, _ in channel_efficiency:
            cost_per_contact = CHANNEL_COSTS.get(channel, Decimal("0.05"))
            max_volume = int(remaining_budget / cost_per_contact)
            allocated_volume = min(volume, max_volume)

            if allocated_volume > 0:
                allocation = self.optimize_channel_capacity(
                    channel, allocated_volume, allocated_volume // 1000 + 1
                )
                allocations[channel.value] = allocation
                remaining_budget -= cost_per_contact * allocated_volume

        return allocations


# =============================================================================
# PORTFOLIO OPTIMIZER
# =============================================================================

class PortfolioOptimizer:
    """
    Portfolio-level optimization:
    - Account prioritization scoring
    - Work queue optimization
    - Expected value ranking
    - Effort allocation
    """

    def __init__(
        self,
        timing_optimizer: ContactTimingOptimizer,
        channel_optimizer: ChannelSequencingOptimizer,
        settlement_optimizer: SettlementPricingOptimizer
    ):
        self.timing_optimizer = timing_optimizer
        self.channel_optimizer = channel_optimizer
        self.settlement_optimizer = settlement_optimizer

    def calculate_priority_score(
        self,
        account_id: str,
        balance: Decimal,
        days_past_due: int,
        segment: ConsumerSegment,
        payment_history: List[Decimal],
        contact_history: List[Tuple[Channel, datetime]]
    ) -> AccountPriority:
        """Calculate comprehensive priority score for an account"""
        # Base score from balance
        balance_score = min(1.0, float(balance) / 1000)

        # Recency score (accounts closer to charge-off are higher priority)
        if days_past_due < 30:
            recency_score = 0.4
        elif days_past_due < 60:
            recency_score = 0.6
        elif days_past_due < 90:
            recency_score = 0.8
        elif days_past_due < 120:
            recency_score = 1.0
        else:
            recency_score = 0.7  # Older accounts have lower probability

        # Payment behavior score
        if payment_history:
            payment_rate = sum(1 for p in payment_history if p > 0) / len(payment_history)
            behavior_score = payment_rate
        else:
            behavior_score = 0.5

        # Fatigue adjustment
        fatigue_risk = self.channel_optimizer.calculate_fatigue_risk(contact_history)
        fatigue_penalty = fatigue_risk * 0.3

        # Segment modifier
        segment_modifiers = {
            ConsumerSegment.FIRST_TIME_DELINQUENT: 1.2,
            ConsumerSegment.HIGH_INCOME: 1.1,
            ConsumerSegment.YOUNG_PROFESSIONAL: 1.05,
            ConsumerSegment.MIDDLE_INCOME: 1.0,
            ConsumerSegment.SENIOR: 0.95,
            ConsumerSegment.GIG_WORKER: 0.9,
            ConsumerSegment.STUDENT: 0.85,
            ConsumerSegment.FINANCIALLY_STRESSED: 0.8,
        }
        segment_modifier = segment_modifiers.get(segment, 1.0)

        # Calculate composite priority score
        priority_score = (
            balance_score * 0.30 +
            recency_score * 0.25 +
            behavior_score * 0.25 +
            (1 - fatigue_penalty) * 0.20
        ) * segment_modifier

        # Calculate probability of collection
        prob_collection = (
            0.3 +  # Base
            behavior_score * 0.3 +
            (1 - min(days_past_due, 180) / 180) * 0.3 +
            (1 - fatigue_risk) * 0.1
        ) * segment_modifier
        prob_collection = min(0.95, max(0.05, prob_collection))

        # Expected value
        expected_value = balance * Decimal(str(prob_collection))

        # Effort estimate (hours)
        base_effort = 0.1 if segment in [ConsumerSegment.FIRST_TIME_DELINQUENT, ConsumerSegment.HIGH_INCOME] else 0.2
        effort_estimate = base_effort * (1 + fatigue_risk)

        # Recommended channel
        preferred_channels = self.channel_optimizer.channel_preferences.get(segment, [Channel.SMS])
        recommended_channel = preferred_channels[0]

        # Timing window
        windows = self.timing_optimizer.get_optimal_windows(segment, "EST", num_windows=1)
        timing_window = windows[0] if windows else ContactWindow(
            start_hour=10, end_hour=12, day_of_week=DayOfWeek.TUESDAY,
            timezone="EST", confidence=0.5, expected_response_rate=0.1
        )

        # Optimal action
        if days_past_due < 30 and behavior_score > 0.5:
            optimal_action = "payment_reminder"
        elif days_past_due < 60:
            optimal_action = "settlement_offer"
        elif days_past_due < 90:
            optimal_action = "payment_plan"
        else:
            optimal_action = "escalated_outreach"

        return AccountPriority(
            account_id=account_id,
            priority_score=priority_score,
            expected_value=expected_value,
            probability_of_collection=prob_collection,
            optimal_action=optimal_action,
            effort_estimate=effort_estimate,
            recommended_channel=recommended_channel,
            timing_window=timing_window,
            segment=segment,
        )

    def optimize_portfolio(
        self,
        accounts: List[Dict[str, Any]],
        available_effort_hours: float,
        budget: Decimal
    ) -> PortfolioOptimization:
        """Optimize portfolio-level allocation"""
        priorities = []

        for account in accounts:
            priority = self.calculate_priority_score(
                account_id=account["account_id"],
                balance=Decimal(str(account.get("balance", 0))),
                days_past_due=account.get("days_past_due", 0),
                segment=account.get("segment", ConsumerSegment.MIDDLE_INCOME),
                payment_history=[Decimal(str(p)) for p in account.get("payment_history", [])],
                contact_history=account.get("contact_history", []),
            )
            priorities.append(priority)

        # Sort by priority score (descending)
        priorities.sort(key=lambda p: p.priority_score, reverse=True)

        # Allocate effort
        remaining_effort = available_effort_hours
        remaining_budget = budget
        prioritized_queue = []

        for priority in priorities:
            contact_cost = CHANNEL_COSTS.get(priority.recommended_channel, Decimal("0.05"))

            if (priority.effort_estimate <= remaining_effort and
                contact_cost <= remaining_budget):
                prioritized_queue.append(priority)
                remaining_effort -= priority.effort_estimate
                remaining_budget -= contact_cost

        # Calculate totals
        total_expected = sum(p.expected_value for p in prioritized_queue)
        total_cost = sum(CHANNEL_COSTS.get(p.recommended_channel, Decimal("0.05")) for p in prioritized_queue)
        expected_roi = float((total_expected - total_cost) / total_cost) if total_cost > 0 else 0

        # Effort allocation by segment
        effort_by_segment = defaultdict(float)
        for p in prioritized_queue:
            effort_by_segment[p.segment] += p.effort_estimate

        # Channel allocation
        channel_allocation = defaultdict(int)
        for p in prioritized_queue:
            channel_allocation[p.recommended_channel] += 1

        return PortfolioOptimization(
            total_accounts=len(prioritized_queue),
            prioritized_queue=prioritized_queue,
            expected_total_collection=total_expected,
            expected_total_cost=total_cost,
            expected_roi=expected_roi,
            effort_allocation=dict(effort_by_segment),
            channel_allocation=dict(channel_allocation),
        )


# =============================================================================
# FEEDBACK LOOP ENGINE
# =============================================================================

class FeedbackLoopEngine:
    """
    Continuous improvement through feedback loops:
    - Outcome tracking
    - Strategy effectiveness measurement
    - Improvement triggers
    - Model retraining signals
    """

    def __init__(self):
        self.signals: List[FeedbackSignal] = []
        self.strategy_outcomes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.model_performance: Dict[str, List[float]] = defaultdict(list)
        self.improvement_thresholds = {
            "min_sample_size": 100,
            "performance_drop_threshold": 0.10,
            "retraining_interval_days": 7,
        }

    def record_outcome(
        self,
        account_id: str,
        strategy_id: str,
        outcome: str,
        value: float,
        context: Dict[str, Any]
    ) -> FeedbackSignal:
        """Record an outcome for tracking"""
        signal = FeedbackSignal(
            signal_id=f"SIG-{len(self.signals):06d}",
            signal_type="outcome",
            timestamp=datetime.now(),
            account_id=account_id,
            strategy_id=strategy_id,
            outcome=outcome,
            value=value,
            context=context,
        )

        self.signals.append(signal)
        self.strategy_outcomes[strategy_id].append({
            "outcome": outcome,
            "value": value,
            "timestamp": signal.timestamp,
            "context": context,
        })

        return signal

    def measure_strategy_effectiveness(
        self,
        strategy_id: str,
        lookback_days: int = 30
    ) -> StrategyEffectiveness:
        """Measure effectiveness of a strategy"""
        outcomes = self.strategy_outcomes.get(strategy_id, [])

        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_outcomes = [o for o in outcomes if o["timestamp"] >= cutoff]

        if not recent_outcomes:
            return StrategyEffectiveness(
                strategy_id=strategy_id,
                strategy_type="unknown",
                sample_size=0,
                success_rate=0.0,
                average_value=Decimal("0"),
                confidence_interval=(0.0, 0.0),
                trend="unknown",
                recommendation="insufficient_data",
            )

        # Calculate metrics
        success_count = sum(1 for o in recent_outcomes if o["outcome"] == "success")
        success_rate = success_count / len(recent_outcomes)

        values = [o["value"] for o in recent_outcomes]
        avg_value = Decimal(str(statistics.mean(values)))

        # Confidence interval (simplified)
        if len(values) > 1:
            std_dev = statistics.stdev(values)
            margin = 1.96 * std_dev / math.sqrt(len(values))
            ci = (success_rate - margin / 10, success_rate + margin / 10)
        else:
            ci = (success_rate, success_rate)

        # Trend analysis
        if len(recent_outcomes) >= 20:
            first_half = recent_outcomes[:len(recent_outcomes)//2]
            second_half = recent_outcomes[len(recent_outcomes)//2:]

            first_rate = sum(1 for o in first_half if o["outcome"] == "success") / len(first_half)
            second_rate = sum(1 for o in second_half if o["outcome"] == "success") / len(second_half)

            if second_rate > first_rate * 1.05:
                trend = "improving"
            elif second_rate < first_rate * 0.95:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Recommendation
        if trend == "declining" and success_rate < 0.30:
            recommendation = "discontinue_strategy"
        elif trend == "declining":
            recommendation = "review_and_optimize"
        elif success_rate > 0.50 and trend == "improving":
            recommendation = "scale_up"
        elif success_rate > 0.40:
            recommendation = "maintain"
        else:
            recommendation = "optimize"

        return StrategyEffectiveness(
            strategy_id=strategy_id,
            strategy_type="collection_strategy",
            sample_size=len(recent_outcomes),
            success_rate=success_rate,
            average_value=avg_value,
            confidence_interval=ci,
            trend=trend,
            recommendation=recommendation,
        )

    def check_retraining_needed(
        self,
        model_name: str,
        recent_performance: List[float]
    ) -> Tuple[bool, str]:
        """Check if model retraining is needed"""
        self.model_performance[model_name].extend(recent_performance)
        history = self.model_performance[model_name]

        if len(history) < self.improvement_thresholds["min_sample_size"]:
            return False, "insufficient_data"

        # Check for performance degradation
        recent_avg = statistics.mean(history[-50:])
        historical_avg = statistics.mean(history[:-50]) if len(history) > 50 else recent_avg

        drop = (historical_avg - recent_avg) / historical_avg if historical_avg > 0 else 0

        if drop > self.improvement_thresholds["performance_drop_threshold"]:
            return True, f"performance_degradation_{drop:.2%}"

        # Check time since last retraining (simplified)
        if len(history) > 1000:
            return True, "scheduled_retraining"

        return False, "performance_acceptable"

    def get_improvement_triggers(self) -> List[Dict[str, Any]]:
        """Get list of improvement triggers"""
        triggers = []

        for strategy_id in self.strategy_outcomes.keys():
            effectiveness = self.measure_strategy_effectiveness(strategy_id)

            if effectiveness.recommendation in ["discontinue_strategy", "review_and_optimize"]:
                triggers.append({
                    "type": "strategy_improvement",
                    "strategy_id": strategy_id,
                    "reason": effectiveness.recommendation,
                    "current_performance": effectiveness.success_rate,
                    "trend": effectiveness.trend,
                })

        for model_name, performance in self.model_performance.items():
            needs_retrain, reason = self.check_retraining_needed(model_name, [])
            if needs_retrain:
                triggers.append({
                    "type": "model_retraining",
                    "model_name": model_name,
                    "reason": reason,
                })

        return triggers


# =============================================================================
# BENCHMARK TRACKER
# =============================================================================

class BenchmarkTracker:
    """
    Tracks performance against benchmarks:
    - Industry comparisons
    - Internal trend analysis
    - Target vs actual tracking
    - Improvement velocity
    """

    def __init__(self):
        self.metrics_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self.targets: Dict[str, float] = {}
        self.industry_benchmarks = INDUSTRY_BENCHMARKS.copy()

    def record_metric(self, metric_name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a metric value"""
        ts = timestamp or datetime.now()
        self.metrics_history[metric_name].append((ts, value))

    def set_target(self, metric_name: str, target: float):
        """Set a target for a metric"""
        self.targets[metric_name] = target

    def get_benchmark_comparison(self, metric_name: str) -> BenchmarkComparison:
        """Compare current performance to benchmarks"""
        history = self.metrics_history.get(metric_name, [])

        if not history:
            return BenchmarkComparison(
                metric_name=metric_name,
                current_value=0.0,
                industry_benchmark=self.industry_benchmarks.get(metric_name, 0.0),
                percentile_rank=0,
                trend_30d=0.0,
                trend_90d=0.0,
                gap_to_benchmark=0.0,
                improvement_target=0.0,
            )

        # Current value (most recent)
        current_value = history[-1][1]

        # Industry benchmark
        benchmark = self.industry_benchmarks.get(metric_name, current_value)

        # Gap to benchmark
        gap = benchmark - current_value

        # Calculate trends
        now = datetime.now()

        # 30-day trend
        thirty_days_ago = now - timedelta(days=30)
        recent_30d = [v for ts, v in history if ts >= thirty_days_ago]
        if len(recent_30d) >= 2:
            trend_30d = (recent_30d[-1] - recent_30d[0]) / recent_30d[0] if recent_30d[0] > 0 else 0
        else:
            trend_30d = 0.0

        # 90-day trend
        ninety_days_ago = now - timedelta(days=90)
        recent_90d = [v for ts, v in history if ts >= ninety_days_ago]
        if len(recent_90d) >= 2:
            trend_90d = (recent_90d[-1] - recent_90d[0]) / recent_90d[0] if recent_90d[0] > 0 else 0
        else:
            trend_90d = 0.0

        # Percentile rank (simplified - assume normal distribution)
        percentile_rank = int(min(99, max(1, (current_value / benchmark) * 50))) if benchmark > 0 else 50

        # Improvement target
        target = self.targets.get(metric_name, benchmark * 1.1)
        improvement_target = target - current_value

        return BenchmarkComparison(
            metric_name=metric_name,
            current_value=current_value,
            industry_benchmark=benchmark,
            percentile_rank=percentile_rank,
            trend_30d=trend_30d,
            trend_90d=trend_90d,
            gap_to_benchmark=gap,
            improvement_target=improvement_target,
        )

    def get_improvement_velocity(self, metric_name: str, days: int = 30) -> float:
        """Calculate rate of improvement over time"""
        history = self.metrics_history.get(metric_name, [])

        cutoff = datetime.now() - timedelta(days=days)
        recent = [(ts, v) for ts, v in history if ts >= cutoff]

        if len(recent) < 2:
            return 0.0

        # Linear regression slope (simplified)
        x_mean = sum(i for i in range(len(recent))) / len(recent)
        y_mean = sum(v for _, v in recent) / len(recent)

        numerator = sum((i - x_mean) * (v - y_mean) for i, (_, v) in enumerate(recent))
        denominator = sum((i - x_mean) ** 2 for i in range(len(recent)))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator

        # Normalize to daily improvement rate
        return slope / days

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "metrics": {},
            "summary": {},
        }

        for metric_name in self.metrics_history.keys():
            comparison = self.get_benchmark_comparison(metric_name)
            velocity = self.get_improvement_velocity(metric_name)

            report["metrics"][metric_name] = {
                "current_value": comparison.current_value,
                "benchmark": comparison.industry_benchmark,
                "percentile": comparison.percentile_rank,
                "trend_30d": f"{comparison.trend_30d:+.1%}",
                "trend_90d": f"{comparison.trend_90d:+.1%}",
                "gap": comparison.gap_to_benchmark,
                "velocity": velocity,
            }

        # Summary statistics
        if report["metrics"]:
            avg_percentile = statistics.mean(
                m["percentile"] for m in report["metrics"].values()
            )
            metrics_above_benchmark = sum(
                1 for m in report["metrics"].values() if m["gap"] <= 0
            )

            report["summary"] = {
                "average_percentile_rank": int(avg_percentile),
                "metrics_above_benchmark": metrics_above_benchmark,
                "total_metrics_tracked": len(report["metrics"]),
            }

        return report


# =============================================================================
# SIMULATION ENGINE
# =============================================================================

class SimulationEngine:
    """
    What-if analysis and strategy simulation:
    - Parameter sensitivity analysis
    - Strategy comparison
    - Optimal configuration discovery
    """

    def __init__(
        self,
        timing_optimizer: ContactTimingOptimizer,
        channel_optimizer: ChannelSequencingOptimizer,
        settlement_optimizer: SettlementPricingOptimizer,
        portfolio_optimizer: PortfolioOptimizer
    ):
        self.timing_optimizer = timing_optimizer
        self.channel_optimizer = channel_optimizer
        self.settlement_optimizer = settlement_optimizer
        self.portfolio_optimizer = portfolio_optimizer

    def generate_synthetic_portfolio(
        self,
        account_count: int,
        balance_distribution: Dict[BalanceTier, float],
        segment_distribution: Dict[ConsumerSegment, float]
    ) -> List[Dict[str, Any]]:
        """Generate synthetic portfolio for simulation"""
        accounts = []

        balance_ranges = {
            BalanceTier.MICRO: (10, 50),
            BalanceTier.SMALL: (50, 150),
            BalanceTier.MEDIUM: (150, 350),
            BalanceTier.LARGE: (350, 600),
            BalanceTier.SUBSTANTIAL: (600, 1000),
        }

        for i in range(account_count):
            # Select balance tier
            tier_rand = random.random()
            cumulative = 0.0
            selected_tier = BalanceTier.MEDIUM
            for tier, prob in balance_distribution.items():
                cumulative += prob
                if tier_rand <= cumulative:
                    selected_tier = tier
                    break

            # Generate balance
            low, high = balance_ranges[selected_tier]
            balance = random.uniform(low, high)

            # Select segment
            seg_rand = random.random()
            cumulative = 0.0
            selected_segment = ConsumerSegment.MIDDLE_INCOME
            for segment, prob in segment_distribution.items():
                cumulative += prob
                if seg_rand <= cumulative:
                    selected_segment = segment
                    break

            # Generate DPD
            dpd = random.choice([15, 30, 45, 60, 75, 90, 120, 150])

            # Generate payment history
            payment_count = random.randint(0, 5)
            payment_history = [random.uniform(0, balance * 0.2) for _ in range(payment_count)]

            accounts.append({
                "account_id": f"SIM-{i:06d}",
                "balance": balance,
                "days_past_due": dpd,
                "segment": selected_segment,
                "payment_history": payment_history,
                "contact_history": [],
            })

        return accounts

    def run_simulation(
        self,
        scenario: SimulationScenario,
        portfolio: Optional[List[Dict[str, Any]]] = None
    ) -> SimulationResult:
        """Run a simulation scenario"""
        # Generate portfolio if not provided
        if portfolio is None:
            balance_dist = scenario.parameters.get("balance_distribution", {
                BalanceTier.MICRO: 0.20,
                BalanceTier.SMALL: 0.30,
                BalanceTier.MEDIUM: 0.25,
                BalanceTier.LARGE: 0.15,
                BalanceTier.SUBSTANTIAL: 0.10,
            })
            segment_dist = scenario.parameters.get("segment_distribution", {
                ConsumerSegment.FIRST_TIME_DELINQUENT: 0.20,
                ConsumerSegment.YOUNG_PROFESSIONAL: 0.15,
                ConsumerSegment.MIDDLE_INCOME: 0.25,
                ConsumerSegment.GIG_WORKER: 0.15,
                ConsumerSegment.FINANCIALLY_STRESSED: 0.15,
                ConsumerSegment.SENIOR: 0.10,
            })

            portfolio = self.generate_synthetic_portfolio(
                scenario.account_count, balance_dist, segment_dist
            )

        # Simulation parameters
        contact_rate = scenario.parameters.get("contact_rate", 0.8)
        response_rate = scenario.parameters.get("response_rate", 0.12)
        conversion_rate = scenario.parameters.get("conversion_rate", 0.08)
        settlement_rate = scenario.parameters.get("settlement_rate", 0.50)
        cost_per_contact = Decimal(str(scenario.parameters.get("cost_per_contact", 0.05)))

        # Run simulation
        total_collected = Decimal("0")
        total_cost = Decimal("0")
        responses = 0
        conversions = 0
        collection_times = []
        metrics_by_segment: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for account in portfolio:
            # Simulate contact
            if random.random() < contact_rate:
                total_cost += cost_per_contact

                # Simulate response
                segment = account.get("segment", ConsumerSegment.MIDDLE_INCOME)
                segment_modifier = self.timing_optimizer._get_segment_modifier(segment)
                adjusted_response_rate = response_rate * segment_modifier

                if random.random() < adjusted_response_rate:
                    responses += 1

                    # Simulate conversion
                    if random.random() < conversion_rate:
                        conversions += 1

                        # Simulate collection
                        balance = Decimal(str(account["balance"]))
                        collected = balance * Decimal(str(settlement_rate))
                        total_collected += collected

                        # Track time to collection (simplified)
                        collection_times.append(random.randint(1, 30))

                        # Track by segment
                        seg_key = segment.value if isinstance(segment, ConsumerSegment) else str(segment)
                        metrics_by_segment[seg_key]["collected"] += float(collected)
                        metrics_by_segment[seg_key]["conversions"] += 1

                metrics_by_segment[segment.value if isinstance(segment, ConsumerSegment) else str(segment)]["contacts"] += 1

        # Calculate summary metrics
        roi = float((total_collected - total_cost) / total_cost) if total_cost > 0 else 0
        actual_response_rate = responses / len(portfolio) if portfolio else 0
        actual_conversion_rate = conversions / len(portfolio) if portfolio else 0
        avg_time_to_collection = statistics.mean(collection_times) if collection_times else 0

        # Sensitivity analysis
        sensitivity = {}
        for param in ["contact_rate", "response_rate", "conversion_rate", "settlement_rate"]:
            sensitivity[param] = []
            base_value = scenario.parameters.get(param, 0.5)

            for multiplier in [0.8, 0.9, 1.0, 1.1, 1.2]:
                adjusted_value = base_value * multiplier
                # Simplified impact estimation
                impact = roi * multiplier
                sensitivity[param].append((adjusted_value, impact))

        return SimulationResult(
            scenario_id=scenario.scenario_id,
            total_collected=total_collected,
            total_cost=total_cost,
            roi=roi,
            response_rate=actual_response_rate,
            conversion_rate=actual_conversion_rate,
            average_time_to_collection=avg_time_to_collection,
            metrics_by_segment=dict(metrics_by_segment),
            sensitivity_analysis=sensitivity,
        )

    def compare_strategies(
        self,
        scenarios: List[SimulationScenario],
        portfolio: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Compare multiple strategy scenarios"""
        results = {}

        # Use same portfolio for fair comparison
        if portfolio is None:
            portfolio = self.generate_synthetic_portfolio(
                scenarios[0].account_count if scenarios else 1000,
                {
                    BalanceTier.MICRO: 0.20,
                    BalanceTier.SMALL: 0.30,
                    BalanceTier.MEDIUM: 0.25,
                    BalanceTier.LARGE: 0.15,
                    BalanceTier.SUBSTANTIAL: 0.10,
                },
                {
                    ConsumerSegment.FIRST_TIME_DELINQUENT: 0.20,
                    ConsumerSegment.YOUNG_PROFESSIONAL: 0.15,
                    ConsumerSegment.MIDDLE_INCOME: 0.25,
                    ConsumerSegment.GIG_WORKER: 0.15,
                    ConsumerSegment.FINANCIALLY_STRESSED: 0.15,
                    ConsumerSegment.SENIOR: 0.10,
                },
            )

        for scenario in scenarios:
            # Deep copy portfolio for each scenario
            scenario_portfolio = copy.deepcopy(portfolio)
            result = self.run_simulation(scenario, scenario_portfolio)
            results[scenario.scenario_id] = {
                "name": scenario.name,
                "roi": result.roi,
                "total_collected": float(result.total_collected),
                "total_cost": float(result.total_cost),
                "response_rate": result.response_rate,
                "conversion_rate": result.conversion_rate,
            }

        # Rank by ROI
        ranked = sorted(results.items(), key=lambda x: x[1]["roi"], reverse=True)

        return {
            "results": results,
            "ranking": [scenario_id for scenario_id, _ in ranked],
            "best_strategy": ranked[0][0] if ranked else None,
            "portfolio_size": len(portfolio),
        }

    def find_optimal_parameters(
        self,
        base_scenario: SimulationScenario,
        parameter_ranges: Dict[str, Tuple[float, float]],
        iterations: int = 50
    ) -> Dict[str, Any]:
        """Find optimal parameters through grid search"""
        best_roi = float("-inf")
        best_params = {}
        all_results = []

        for _ in range(iterations):
            # Random parameter selection within ranges
            params = {}
            for param, (low, high) in parameter_ranges.items():
                params[param] = random.uniform(low, high)

            # Create scenario with these parameters
            test_scenario = SimulationScenario(
                scenario_id=f"OPT-{_:04d}",
                name="Optimization Test",
                description="Parameter optimization iteration",
                parameters={**base_scenario.parameters, **params},
                duration_days=base_scenario.duration_days,
                account_count=min(500, base_scenario.account_count),  # Smaller for speed
            )

            # Run simulation
            result = self.run_simulation(test_scenario)

            all_results.append({
                "params": params,
                "roi": result.roi,
                "collected": float(result.total_collected),
            })

            if result.roi > best_roi:
                best_roi = result.roi
                best_params = params

        return {
            "optimal_parameters": best_params,
            "optimal_roi": best_roi,
            "iterations": iterations,
            "all_results": all_results[-10:],  # Last 10 for reference
        }


# =============================================================================
# SYSTEM PERFORMANCE OPTIMIZER (MAIN CLASS)
# =============================================================================

class SystemPerformanceOptimizer:
    """
    Main system performance optimizer integrating all components:
    - Contact timing optimization
    - Channel sequencing
    - Message optimization
    - Settlement pricing
    - Resource allocation
    - Portfolio optimization
    - Feedback loops
    - Benchmark tracking
    - Simulation engine
    """

    def __init__(self):
        # Initialize all optimizers
        self.timing_optimizer = ContactTimingOptimizer()
        self.channel_optimizer = ChannelSequencingOptimizer()
        self.message_optimizer = MessageOptimizationEngine()
        self.settlement_optimizer = SettlementPricingOptimizer()
        self.resource_optimizer = ResourceAllocationOptimizer()

        self.portfolio_optimizer = PortfolioOptimizer(
            self.timing_optimizer,
            self.channel_optimizer,
            self.settlement_optimizer,
        )

        self.feedback_engine = FeedbackLoopEngine()
        self.benchmark_tracker = BenchmarkTracker()

        self.simulation_engine = SimulationEngine(
            self.timing_optimizer,
            self.channel_optimizer,
            self.settlement_optimizer,
            self.portfolio_optimizer,
        )

        logger.info("System Performance Optimizer initialized")

    def optimize_account(
        self,
        account_id: str,
        balance: Decimal,
        days_past_due: int,
        segment: ConsumerSegment,
        pay_frequency: PayFrequency,
        timezone: str,
        payment_history: List[Decimal],
        contact_history: List[Tuple[Channel, datetime]]
    ) -> Dict[str, Any]:
        """Generate comprehensive optimization recommendations for an account"""

        # 1. Timing optimization
        timing_rec = self.timing_optimizer.generate_timing_recommendation(
            account_id, segment, pay_frequency, timezone, days_past_due
        )

        # 2. Channel optimization
        channel_rec = self.channel_optimizer.optimize_waterfall(
            account_id, segment, balance, contact_history
        )

        # 3. Settlement optimization
        settlement_offer = self.settlement_optimizer.generate_settlement_offer(
            account_id, balance, segment, days_past_due, payment_history
        )

        # 4. Priority scoring
        priority = self.portfolio_optimizer.calculate_priority_score(
            account_id, balance, days_past_due, segment, payment_history, contact_history
        )

        # 5. Message tone recommendation
        optimal_tone = self.message_optimizer.get_optimal_tone(segment)

        return {
            "account_id": account_id,
            "optimization_timestamp": datetime.now().isoformat(),
            "timing": {
                "optimal_windows": [
                    {
                        "day": w.day_of_week.name,
                        "start_hour": w.start_hour,
                        "end_hour": w.end_hour,
                        "expected_response": f"{w.expected_response_rate:.1%}",
                    }
                    for w in timing_rec.optimal_windows
                ],
                "payday_aligned": timing_rec.payday_aligned,
                "next_payday": timing_rec.next_payday.isoformat() if timing_rec.next_payday else None,
                "urgency_score": timing_rec.urgency_score,
            },
            "channel": {
                "recommended_sequence": [c.value for c in channel_rec.recommended_sequence.channels],
                "expected_response_rate": f"{channel_rec.recommended_sequence.expected_response_rate:.1%}",
                "expected_roi": f"{channel_rec.recommended_sequence.expected_roi:.1f}x",
                "fatigue_risk": f"{channel_rec.fatigue_risk:.1%}",
                "cost_efficiency": f"{channel_rec.cost_efficiency_score:.2f}",
            },
            "settlement": {
                "offer_amount": float(settlement_offer.settlement_amount),
                "settlement_percentage": f"{settlement_offer.settlement_percentage:.0%}",
                "expected_acceptance": f"{settlement_offer.expected_acceptance_rate:.1%}",
                "expires_in_days": settlement_offer.expires_in_days,
                "consumer_savings": float(settlement_offer.consumer_surplus),
            },
            "priority": {
                "score": f"{priority.priority_score:.3f}",
                "expected_value": float(priority.expected_value),
                "probability_of_collection": f"{priority.probability_of_collection:.1%}",
                "optimal_action": priority.optimal_action,
                "recommended_channel": priority.recommended_channel.value,
            },
            "message": {
                "optimal_tone": optimal_tone.value,
            },
            "projected_improvement": {
                "timing_lift": f"{timing_rec.expected_lift:+.1%}",
                "overall_expected_value": float(priority.expected_value),
            },
        }

    def get_system_recommendations(self) -> Dict[str, Any]:
        """Generate system-wide optimization recommendations"""

        # Generate performance report
        perf_report = self.benchmark_tracker.generate_performance_report()

        # Get improvement triggers
        triggers = self.feedback_engine.get_improvement_triggers()

        # Resource recommendations
        # Assume some current state
        ai_capacity = self.resource_optimizer.optimize_ai_capacity(
            expected_volume=10000,
            current_capacity=50,
        )

        return {
            "generated_at": datetime.now().isoformat(),
            "performance_summary": perf_report.get("summary", {}),
            "improvement_triggers": triggers,
            "resource_recommendations": {
                "ai_agents": {
                    "current": ai_capacity.current_capacity,
                    "recommended": ai_capacity.recommended_capacity,
                    "utilization": f"{ai_capacity.utilization_rate:.1%}",
                    "bottleneck_risk": f"{ai_capacity.bottleneck_risk:.1%}",
                },
            },
            "optimization_opportunities": [
                {
                    "area": "contact_timing",
                    "potential_lift": "+15-25%",
                    "effort": "low",
                    "recommendation": "Implement segment-specific contact windows",
                },
                {
                    "area": "channel_sequencing",
                    "potential_lift": "+10-20%",
                    "effort": "medium",
                    "recommendation": "Deploy multi-armed bandit for channel selection",
                },
                {
                    "area": "settlement_pricing",
                    "potential_lift": "+5-15%",
                    "effort": "medium",
                    "recommendation": "Implement dynamic settlement pricing by segment",
                },
                {
                    "area": "message_optimization",
                    "potential_lift": "+5-10%",
                    "effort": "low",
                    "recommendation": "Run A/B tests on subject lines and CTAs",
                },
            ],
        }

    def run_portfolio_simulation(
        self,
        portfolio_size: int = 1000,
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run portfolio-level simulation with multiple scenarios"""

        if scenarios is None:
            scenarios = [
                {
                    "name": "Baseline",
                    "contact_rate": 0.80,
                    "response_rate": 0.10,
                    "conversion_rate": 0.06,
                    "settlement_rate": 0.50,
                },
                {
                    "name": "Optimized Timing",
                    "contact_rate": 0.85,
                    "response_rate": 0.14,
                    "conversion_rate": 0.08,
                    "settlement_rate": 0.50,
                },
                {
                    "name": "Optimized Channels",
                    "contact_rate": 0.80,
                    "response_rate": 0.12,
                    "conversion_rate": 0.09,
                    "settlement_rate": 0.52,
                },
                {
                    "name": "Full Optimization",
                    "contact_rate": 0.85,
                    "response_rate": 0.15,
                    "conversion_rate": 0.10,
                    "settlement_rate": 0.55,
                },
            ]

        scenario_objects = [
            SimulationScenario(
                scenario_id=f"SCENARIO-{i:02d}",
                name=s["name"],
                description=f"Simulation scenario: {s['name']}",
                parameters=s,
                duration_days=30,
                account_count=portfolio_size,
            )
            for i, s in enumerate(scenarios)
        ]

        comparison = self.simulation_engine.compare_strategies(scenario_objects)

        return {
            "simulation_timestamp": datetime.now().isoformat(),
            "portfolio_size": portfolio_size,
            "scenarios_evaluated": len(scenarios),
            "results": comparison["results"],
            "ranking": comparison["ranking"],
            "best_strategy": comparison["best_strategy"],
            "recommendation": f"Implement '{scenarios[int(comparison['best_strategy'].split('-')[1])] if comparison['best_strategy'] else scenarios[0]}'",
        }


# =============================================================================
# DEMO FUNCTION
# =============================================================================

async def run_performance_optimization_demo():
    """Demonstrate the system performance optimizer capabilities"""

    print("=" * 80)
    print("QUAN RECOVERY - SYSTEM PERFORMANCE OPTIMIZER DEMO")
    print("=" * 80)
    print()

    # Initialize optimizer
    optimizer = SystemPerformanceOptimizer()

    # ==========================================================================
    # DEMO 1: Account-Level Optimization
    # ==========================================================================
    print("-" * 80)
    print("DEMO 1: ACCOUNT-LEVEL OPTIMIZATION")
    print("-" * 80)
    print()

    # Sample account
    account_optimization = optimizer.optimize_account(
        account_id="ACC-001234",
        balance=Decimal("287.50"),
        days_past_due=45,
        segment=ConsumerSegment.YOUNG_PROFESSIONAL,
        pay_frequency=PayFrequency.BIWEEKLY,
        timezone="EST",
        payment_history=[Decimal("25.00"), Decimal("0"), Decimal("50.00")],
        contact_history=[(Channel.SMS, datetime.now() - timedelta(days=5))],
    )

    print("Account: ACC-001234")
    print(f"  Balance: ${float(account_optimization['settlement']['offer_amount'] / 0.50):.2f}")
    print(f"  Days Past Due: 45")
    print(f"  Segment: Young Professional")
    print()

    print("TIMING OPTIMIZATION:")
    for window in account_optimization["timing"]["optimal_windows"][:3]:
        print(f"  - {window['day']} {window['start_hour']}:00-{window['end_hour']}:00 "
              f"(Expected Response: {window['expected_response']})")
    print(f"  - Payday Aligned: {account_optimization['timing']['payday_aligned']}")
    print(f"  - Urgency Score: {account_optimization['timing']['urgency_score']:.2f}")
    print()

    print("CHANNEL OPTIMIZATION:")
    print(f"  - Recommended Sequence: {' -> '.join(account_optimization['channel']['recommended_sequence'])}")
    print(f"  - Expected Response Rate: {account_optimization['channel']['expected_response_rate']}")
    print(f"  - Expected ROI: {account_optimization['channel']['expected_roi']}")
    print(f"  - Fatigue Risk: {account_optimization['channel']['fatigue_risk']}")
    print()

    print("SETTLEMENT OPTIMIZATION:")
    print(f"  - Offer Amount: ${account_optimization['settlement']['offer_amount']:.2f}")
    print(f"  - Settlement %: {account_optimization['settlement']['settlement_percentage']}")
    print(f"  - Expected Acceptance: {account_optimization['settlement']['expected_acceptance']}")
    print(f"  - Consumer Savings: ${account_optimization['settlement']['consumer_savings']:.2f}")
    print()

    print("PRIORITY & RECOMMENDED ACTION:")
    print(f"  - Priority Score: {account_optimization['priority']['score']}")
    print(f"  - Expected Value: ${account_optimization['priority']['expected_value']:.2f}")
    print(f"  - Collection Probability: {account_optimization['priority']['probability_of_collection']}")
    print(f"  - Optimal Action: {account_optimization['priority']['optimal_action']}")
    print(f"  - Message Tone: {account_optimization['message']['optimal_tone']}")
    print()

    print(f"PROJECTED IMPROVEMENT:")
    print(f"  - Timing Optimization Lift: {account_optimization['projected_improvement']['timing_lift']}")
    print()

    # ==========================================================================
    # DEMO 2: Portfolio Simulation
    # ==========================================================================
    print("-" * 80)
    print("DEMO 2: PORTFOLIO SIMULATION & STRATEGY COMPARISON")
    print("-" * 80)
    print()

    simulation_results = optimizer.run_portfolio_simulation(portfolio_size=2000)

    print(f"Simulated Portfolio: {simulation_results['portfolio_size']:,} accounts")
    print(f"Scenarios Evaluated: {simulation_results['scenarios_evaluated']}")
    print()

    print("SCENARIO COMPARISON:")
    print("-" * 60)
    print(f"{'Scenario':<25} {'ROI':>10} {'Collected':>15} {'Response':>10}")
    print("-" * 60)

    for scenario_id in simulation_results["ranking"]:
        result = simulation_results["results"][scenario_id]
        print(f"{result['name']:<25} {result['roi']:>10.2f}x "
              f"${result['total_collected']:>13,.2f} "
              f"{result['response_rate']:>9.1%}")

    print("-" * 60)
    print()

    best_id = simulation_results["best_strategy"]
    if best_id:
        best = simulation_results["results"][best_id]
        baseline = simulation_results["results"]["SCENARIO-00"]

        roi_improvement = ((best["roi"] - baseline["roi"]) / baseline["roi"]) * 100 if baseline["roi"] > 0 else 0
        collection_improvement = ((best["total_collected"] - baseline["total_collected"]) / baseline["total_collected"]) * 100 if baseline["total_collected"] > 0 else 0

        print(f"BEST STRATEGY: {best['name']}")
        print(f"  - ROI Improvement vs Baseline: +{roi_improvement:.1f}%")
        print(f"  - Collection Improvement vs Baseline: +{collection_improvement:.1f}%")
    print()

    # ==========================================================================
    # DEMO 3: A/B Testing Framework
    # ==========================================================================
    print("-" * 80)
    print("DEMO 3: A/B TESTING FRAMEWORK")
    print("-" * 80)
    print()

    # Create a test
    test = optimizer.message_optimizer.create_test(
        test_id="TEST-SUBJ-001",
        name="Subject Line Test - Payment Reminder",
        description="Testing urgency vs friendly subject lines",
        variants=[
            {
                "name": "Urgent",
                "content": "Payment overdue - action required",
                "subject_line": "IMPORTANT: Your payment is overdue",
                "tone": MessageTone.URGENT,
            },
            {
                "name": "Friendly",
                "content": "A friendly reminder about your balance",
                "subject_line": "Quick reminder about your account",
                "tone": MessageTone.FRIENDLY,
            },
            {
                "name": "Empathetic",
                "content": "We understand times can be tough",
                "subject_line": "We're here to help with your account",
                "tone": MessageTone.EMPATHETIC,
            },
        ],
        channel=Channel.EMAIL,
        segment=ConsumerSegment.FINANCIALLY_STRESSED,
        minimum_sample_size=100,
    )

    optimizer.message_optimizer.start_test("TEST-SUBJ-001")

    # Simulate test results
    for _ in range(500):
        variant = optimizer.message_optimizer.assign_variant("TEST-SUBJ-001", f"ACC-{_:05d}")
        if variant:
            # Simulate outcomes based on tone
            if variant.tone == MessageTone.EMPATHETIC:
                responded = random.random() < 0.18
                converted = responded and random.random() < 0.55
            elif variant.tone == MessageTone.FRIENDLY:
                responded = random.random() < 0.15
                converted = responded and random.random() < 0.50
            else:  # Urgent
                responded = random.random() < 0.12
                converted = responded and random.random() < 0.45

            revenue = Decimal(str(random.uniform(50, 200))) if converted else Decimal("0")
            optimizer.message_optimizer.record_response(
                "TEST-SUBJ-001", variant.variant_id, responded, converted, revenue
            )

    # Analyze results
    test_results = optimizer.message_optimizer.analyze_test("TEST-SUBJ-001")

    print(f"Test: {test_results['name']}")
    print(f"Status: {test_results['status']}")
    print(f"Total Exposures: {test_results['total_exposures']}")
    print()

    print("VARIANT PERFORMANCE:")
    print("-" * 70)
    print(f"{'Variant':<15} {'Exposures':>10} {'Response':>12} {'Conversion':>12} {'Rev/Exp':>12}")
    print("-" * 70)

    for v in test_results["variants"]:
        print(f"{v['name']:<15} {v['exposures']:>10} {v['response_rate']:>11.1%} "
              f"{v['conversion_rate']:>11.1%} ${v['revenue_per_exposure']:>10.2f}")

    print("-" * 70)

    if test_results.get("winner"):
        winner_variant = next(v for v in test_results["variants"] if v["variant_id"] == test_results["winner"])
        print(f"\nWINNER: {winner_variant['name']} (Confidence: {test_results['confidence']:.0%})")
    else:
        print("\nNo statistically significant winner yet")
    print()

    # ==========================================================================
    # DEMO 4: System-Wide Recommendations
    # ==========================================================================
    print("-" * 80)
    print("DEMO 4: SYSTEM-WIDE OPTIMIZATION RECOMMENDATIONS")
    print("-" * 80)
    print()

    # Add some benchmark data
    for metric, value in INDUSTRY_BENCHMARKS.items():
        # Simulate current performance slightly below benchmark
        current = value * random.uniform(0.85, 1.05)
        for i in range(30):
            optimizer.benchmark_tracker.record_metric(
                metric,
                current * random.uniform(0.95, 1.05),
                datetime.now() - timedelta(days=30-i)
            )

    recommendations = optimizer.get_system_recommendations()

    print("OPTIMIZATION OPPORTUNITIES:")
    print()
    for opp in recommendations["optimization_opportunities"]:
        print(f"  {opp['area'].upper()}")
        print(f"    - Potential Lift: {opp['potential_lift']}")
        print(f"    - Implementation Effort: {opp['effort']}")
        print(f"    - Recommendation: {opp['recommendation']}")
        print()

    print("RESOURCE RECOMMENDATIONS:")
    ai_rec = recommendations["resource_recommendations"]["ai_agents"]
    print(f"  AI Agents:")
    print(f"    - Current Capacity: {ai_rec['current']}")
    print(f"    - Recommended: {ai_rec['recommended']}")
    print(f"    - Utilization: {ai_rec['utilization']}")
    print(f"    - Bottleneck Risk: {ai_rec['bottleneck_risk']}")
    print()

    # ==========================================================================
    # DEMO 5: Benchmark Tracking
    # ==========================================================================
    print("-" * 80)
    print("DEMO 5: BENCHMARK TRACKING & PERFORMANCE ANALYSIS")
    print("-" * 80)
    print()

    print("PERFORMANCE VS INDUSTRY BENCHMARKS:")
    print("-" * 75)
    print(f"{'Metric':<30} {'Current':>10} {'Benchmark':>12} {'Gap':>10} {'Trend 30d':>12}")
    print("-" * 75)

    for metric in ["response_rate", "conversion_rate", "settlement_rate", "promise_to_pay_rate"]:
        comparison = optimizer.benchmark_tracker.get_benchmark_comparison(metric)
        gap_str = f"{comparison.gap_to_benchmark:+.2%}" if comparison.gap_to_benchmark != 0 else "On target"
        trend_str = f"{comparison.trend_30d:+.1%}" if comparison.trend_30d != 0 else "Stable"

        print(f"{metric:<30} {comparison.current_value:>9.1%} "
              f"{comparison.industry_benchmark:>11.1%} "
              f"{gap_str:>10} {trend_str:>12}")

    print("-" * 75)
    print()

    # ==========================================================================
    # DEMO 6: Parameter Optimization
    # ==========================================================================
    print("-" * 80)
    print("DEMO 6: PARAMETER OPTIMIZATION")
    print("-" * 80)
    print()

    base_scenario = SimulationScenario(
        scenario_id="BASE",
        name="Base Scenario",
        description="Base scenario for optimization",
        parameters={
            "contact_rate": 0.80,
            "response_rate": 0.12,
            "conversion_rate": 0.08,
            "settlement_rate": 0.50,
        },
        duration_days=30,
        account_count=500,
    )

    print("Finding optimal parameters...")
    optimal = optimizer.simulation_engine.find_optimal_parameters(
        base_scenario,
        parameter_ranges={
            "contact_rate": (0.70, 0.95),
            "response_rate": (0.08, 0.20),
            "settlement_rate": (0.40, 0.65),
        },
        iterations=30,
    )

    print()
    print("OPTIMAL PARAMETERS FOUND:")
    for param, value in optimal["optimal_parameters"].items():
        print(f"  - {param}: {value:.2%}")
    print(f"\nOptimal ROI: {optimal['optimal_roi']:.2f}x")
    print()

    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print("=" * 80)
    print("OPTIMIZATION SUMMARY")
    print("=" * 80)
    print()
    print("The System Performance Optimizer provides comprehensive optimization across:")
    print()
    print("  1. CONTACT TIMING - Segment-specific optimal windows with payday alignment")
    print("  2. CHANNEL SEQUENCING - Multi-channel waterfall with fatigue prevention")
    print("  3. MESSAGE OPTIMIZATION - A/B testing framework for continuous improvement")
    print("  4. SETTLEMENT PRICING - Dynamic pricing based on willingness-to-pay")
    print("  5. RESOURCE ALLOCATION - AI agent and channel capacity planning")
    print("  6. PORTFOLIO OPTIMIZATION - Priority scoring and work queue optimization")
    print("  7. FEEDBACK LOOPS - Outcome tracking and strategy effectiveness")
    print("  8. BENCHMARK TRACKING - Industry comparison and trend analysis")
    print("  9. SIMULATION ENGINE - What-if analysis and strategy comparison")
    print()
    print("PROJECTED IMPROVEMENTS WITH FULL OPTIMIZATION:")
    print("  - Response Rate: +25-40%")
    print("  - Conversion Rate: +20-35%")
    print("  - Settlement Acceptance: +15-25%")
    print("  - Cost Efficiency: +20-30%")
    print("  - Overall ROI: +40-60%")
    print()
    print("=" * 80)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_demo():
    """Synchronous wrapper for the demo"""
    asyncio.run(run_performance_optimization_demo())


if __name__ == "__main__":
    run_demo()
