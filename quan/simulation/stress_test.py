"""
Scale Stress Test Simulator

Tests QUAN system at different scale levels to identify breaking points,
optimize infrastructure costs, and generate capacity planning recommendations.

Scale Levels:
- Startup:    10K accounts/day
- Growth:     100K accounts/day
- Scale:      1M accounts/day
- Enterprise: 10M accounts/day
"""

import asyncio
import random
import statistics
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from collections import defaultdict
from quan.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# SCALE LEVEL DEFINITIONS
# =============================================================================

class ScaleLevel(Enum):
    """Scale levels for stress testing"""
    STARTUP = "startup"         # 10K accounts/day
    GROWTH = "growth"           # 100K accounts/day
    SCALE = "scale"             # 1M accounts/day
    ENTERPRISE = "enterprise"   # 10M accounts/day


@dataclass
class ScaleLevelConfig:
    """Configuration for each scale level"""
    name: str
    accounts_per_day: int
    description: str

    # Target metrics
    target_throughput_per_second: float
    target_recovery_rate: float
    max_latency_ms: float

    # Staffing
    min_agents: int
    max_agents: int
    accounts_per_agent: int


SCALE_CONFIGS = {
    ScaleLevel.STARTUP: ScaleLevelConfig(
        name="Startup",
        accounts_per_day=10_000,
        description="Early-stage operation, single region",
        target_throughput_per_second=0.12,  # 10K / 86400
        target_recovery_rate=0.30,
        max_latency_ms=500,
        min_agents=10,
        max_agents=50,
        accounts_per_agent=200,
    ),
    ScaleLevel.GROWTH: ScaleLevelConfig(
        name="Growth",
        accounts_per_day=100_000,
        description="Scaling operation, multi-region",
        target_throughput_per_second=1.16,  # 100K / 86400
        target_recovery_rate=0.32,
        max_latency_ms=300,
        min_agents=100,
        max_agents=500,
        accounts_per_agent=200,
    ),
    ScaleLevel.SCALE: ScaleLevelConfig(
        name="Scale",
        accounts_per_day=1_000_000,
        description="Full-scale operation, distributed infrastructure",
        target_throughput_per_second=11.6,  # 1M / 86400
        target_recovery_rate=0.33,
        max_latency_ms=200,
        min_agents=500,
        max_agents=2500,
        accounts_per_agent=400,
    ),
    ScaleLevel.ENTERPRISE: ScaleLevelConfig(
        name="Enterprise",
        accounts_per_day=10_000_000,
        description="Enterprise-grade, global infrastructure",
        target_throughput_per_second=116.0,  # 10M / 86400
        target_recovery_rate=0.35,
        max_latency_ms=150,
        min_agents=2500,
        max_agents=10000,
        accounts_per_agent=1000,
    ),
}


# =============================================================================
# INFRASTRUCTURE COST MODEL
# =============================================================================

@dataclass
class InfrastructureCosts:
    """Realistic infrastructure cost model"""

    # Compute (per hour)
    compute_small_hourly: float = 0.05      # t3.small equivalent
    compute_medium_hourly: float = 0.20     # t3.medium
    compute_large_hourly: float = 0.80      # c5.xlarge
    compute_xlarge_hourly: float = 3.20     # c5.4xlarge

    # Database (per hour)
    db_small_hourly: float = 0.10           # db.t3.small
    db_medium_hourly: float = 0.40          # db.r5.large
    db_large_hourly: float = 1.60           # db.r5.xlarge
    db_xlarge_hourly: float = 6.40          # db.r5.4xlarge

    # Storage (per GB/month)
    storage_ssd_monthly: float = 0.10       # gp3
    storage_hdd_monthly: float = 0.03       # sc1
    storage_archive_monthly: float = 0.004  # Glacier

    # Networking (per GB transfer)
    data_transfer_out: float = 0.09
    data_transfer_region: float = 0.01

    # Caching (per hour)
    cache_small_hourly: float = 0.017       # cache.t3.micro
    cache_medium_hourly: float = 0.068      # cache.r5.large
    cache_large_hourly: float = 0.272       # cache.r5.xlarge

    # Message queue (per million requests)
    queue_per_million: float = 0.40

    # CDN (per TB)
    cdn_per_tb: float = 0.085


@dataclass
class ChannelCosts:
    """Per-message/call costs for communication channels"""

    # SMS costs
    sms_outbound: float = 0.0079            # Twilio outbound SMS
    sms_inbound: float = 0.0079             # Twilio inbound SMS
    sms_mms_outbound: float = 0.02          # MMS

    # Email costs
    email_transactional: float = 0.0001     # SendGrid (per email)
    email_marketing: float = 0.00035        # Marketing tier
    email_validation: float = 0.003         # Email validation

    # Voice costs
    voice_outbound_per_min: float = 0.014   # Twilio voice
    voice_inbound_per_min: float = 0.0085   # Inbound
    voice_ai_per_min: float = 0.05          # AI voice (extra)
    avg_call_duration_min: float = 2.5      # Average call length

    # Mail costs
    mail_letter: float = 0.65               # First-class letter
    mail_certified: float = 4.50            # Certified mail
    mail_bulk_discount: float = 0.40        # Bulk rate

    # Skip trace / data append
    skip_trace_basic: float = 0.25          # Basic lookup
    skip_trace_premium: float = 1.50        # Full skip trace
    data_append: float = 0.05               # Data appending


@dataclass
class ChannelRateLimits:
    """API rate limits for communication channels"""

    # SMS (Twilio)
    sms_per_second: int = 100               # Messages per second
    sms_per_phone_per_second: int = 1       # Per phone number
    sms_daily_per_recipient: int = 5        # Per recipient per day

    # Email (SendGrid)
    email_per_second: int = 1000            # Emails per second
    email_hourly_limit: int = 100_000       # Per hour
    email_daily_limit: int = 2_000_000      # Per day

    # Voice (Twilio)
    voice_concurrent_calls: int = 500       # Concurrent calls
    voice_cps: int = 30                     # Calls per second
    voice_daily_per_recipient: int = 3      # Per recipient per day

    # Payment APIs
    stripe_per_second: int = 100            # API requests/second
    stripe_connect_per_second: int = 25     # Connect requests

    # Skip trace APIs
    skip_trace_per_minute: int = 100        # Lookups per minute
    skip_trace_daily_limit: int = 10_000    # Daily limit


# =============================================================================
# STRESS TEST RESULTS
# =============================================================================

@dataclass
class ChannelStressResult:
    """Results for a single channel under stress"""
    channel: str
    messages_attempted: int = 0
    messages_delivered: int = 0
    messages_failed: int = 0
    rate_limit_hits: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    cost_total: Decimal = Decimal("0")
    saturation_pct: float = 0.0
    breaking_point_reached: bool = False


@dataclass
class InfraStressResult:
    """Infrastructure stress test results"""
    compute_utilization: float = 0.0
    memory_utilization: float = 0.0
    db_connections_used: int = 0
    db_connections_max: int = 0
    cache_hit_rate: float = 0.0
    queue_depth: int = 0
    queue_max_depth: int = 0
    error_rate: float = 0.0


@dataclass
class BreakingPoint:
    """Identified breaking point"""
    component: str
    metric: str
    threshold: float
    actual_value: float
    scale_level: str
    accounts_at_break: int
    recommendation: str


@dataclass
class CostAnalysis:
    """Cost analysis at scale"""
    scale_level: str
    accounts_per_day: int

    # Infrastructure costs (daily)
    compute_daily: Decimal = Decimal("0")
    database_daily: Decimal = Decimal("0")
    storage_daily: Decimal = Decimal("0")
    networking_daily: Decimal = Decimal("0")
    cache_daily: Decimal = Decimal("0")
    queue_daily: Decimal = Decimal("0")

    # Channel costs (daily)
    sms_daily: Decimal = Decimal("0")
    email_daily: Decimal = Decimal("0")
    voice_daily: Decimal = Decimal("0")
    mail_daily: Decimal = Decimal("0")
    skip_trace_daily: Decimal = Decimal("0")

    # Agent costs (daily)
    agent_cost_daily: Decimal = Decimal("0")
    agents_required: int = 0

    # Totals
    total_daily: Decimal = Decimal("0")
    cost_per_account: Decimal = Decimal("0")
    cost_per_dollar_collected: Decimal = Decimal("0")

    # Efficiency metrics
    economies_of_scale_factor: float = 1.0
    marginal_cost_trend: str = "linear"


@dataclass
class ScaleStressResult:
    """Complete stress test result for a scale level"""
    scale_level: ScaleLevel
    config: ScaleLevelConfig

    # Processing metrics
    accounts_processed: int = 0
    throughput_achieved: float = 0.0
    throughput_target: float = 0.0
    throughput_pct: float = 0.0

    # Recovery metrics
    recovery_rate: float = 0.0
    total_collected: Decimal = Decimal("0")
    avg_collection: Decimal = Decimal("0")

    # Channel results
    channel_results: Dict[str, ChannelStressResult] = field(default_factory=dict)

    # Infrastructure results
    infra_result: InfraStressResult = field(default_factory=InfraStressResult)

    # Cost analysis
    cost_analysis: CostAnalysis = None

    # Breaking points
    breaking_points: List[BreakingPoint] = field(default_factory=list)

    # Agent metrics
    agents_deployed: int = 0
    accounts_per_agent: float = 0.0
    agent_utilization: float = 0.0

    # Quality metrics
    quality_score: float = 0.0
    compliance_risk_score: float = 0.0

    # Recommendations
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CapacityPlanningMatrix:
    """Capacity planning output"""

    # Per-scale metrics
    accounts_per_infra_dollar: Dict[str, float] = field(default_factory=dict)
    optimal_batch_sizes: Dict[str, int] = field(default_factory=dict)

    # Peak handling
    peak_multiplier: float = 2.5  # Peak = 2.5x average
    burst_capacity_accounts: Dict[str, int] = field(default_factory=dict)

    # Scale-up triggers
    scale_up_thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Infrastructure requirements
    infra_requirements: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Cost projections
    monthly_costs: Dict[str, Decimal] = field(default_factory=dict)
    annual_costs: Dict[str, Decimal] = field(default_factory=dict)

    # ROI projections
    breakeven_points: Dict[str, int] = field(default_factory=dict)

    # Recommendations
    recommended_starting_scale: str = ""
    growth_path: List[str] = field(default_factory=list)


# =============================================================================
# STRESS TEST SIMULATOR
# =============================================================================

class ScaleStressTestSimulator:
    """
    Comprehensive stress test simulator for QUAN system.

    Tests system behavior at multiple scale levels, identifies breaking points,
    and generates capacity planning recommendations.
    """

    def __init__(self):
        self.infra_costs = InfrastructureCosts()
        self.channel_costs = ChannelCosts()
        self.rate_limits = ChannelRateLimits()

        self.results: Dict[ScaleLevel, ScaleStressResult] = {}
        self.breaking_points: List[BreakingPoint] = []

        # Simulation state
        self.current_time = datetime.utcnow()

    async def run_full_stress_test(
        self,
        levels: List[ScaleLevel] = None,
        simulation_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Run stress tests across all scale levels.
        """

        if levels is None:
            levels = list(ScaleLevel)

        print("=" * 90)
        print("  QUAN RECOVERY - SCALE STRESS TEST SIMULATOR")
        print("  Testing System Limits and Capacity Planning")
        print("=" * 90)

        for level in levels:
            config = SCALE_CONFIGS[level]
            print(f"\n{'='*90}")
            print(f"  SCALE LEVEL: {config.name.upper()}")
            print(f"  {config.description}")
            print(f"  Target: {config.accounts_per_day:,} accounts/day")
            print(f"{'='*90}")

            result = await self._run_scale_test(level, simulation_hours)
            self.results[level] = result

            self._print_scale_results(result)

        # Generate capacity planning matrix
        capacity_matrix = self._generate_capacity_matrix()

        # Print final analysis
        self._print_final_analysis(capacity_matrix)

        return {
            "results": self.results,
            "breaking_points": self.breaking_points,
            "capacity_matrix": capacity_matrix,
        }

    async def _run_scale_test(
        self,
        level: ScaleLevel,
        hours: int,
    ) -> ScaleStressResult:
        """Run stress test for a single scale level"""

        config = SCALE_CONFIGS[level]

        result = ScaleStressResult(
            scale_level=level,
            config=config,
            throughput_target=config.target_throughput_per_second,
        )

        # Calculate accounts to process
        accounts_to_process = int(config.accounts_per_day * (hours / 24))

        # Simulate processing
        await self._simulate_processing(result, accounts_to_process, hours)

        # Test channel capacity
        await self._test_channel_capacity(result, accounts_to_process)

        # Test infrastructure
        await self._test_infrastructure(result, accounts_to_process)

        # Calculate costs
        result.cost_analysis = self._calculate_costs(level, config, result)

        # Identify breaking points
        self._identify_breaking_points(result)

        # Calculate quality and compliance metrics
        self._calculate_quality_metrics(result)

        # Generate recommendations
        result.recommendations = self._generate_recommendations(result)

        return result

    async def _simulate_processing(
        self,
        result: ScaleStressResult,
        accounts: int,
        hours: int,
    ):
        """Simulate account processing at scale"""

        config = result.config

        # Calculate agents needed
        agents_needed = max(
            config.min_agents,
            min(config.max_agents, accounts // config.accounts_per_agent)
        )

        result.agents_deployed = agents_needed
        result.accounts_per_agent = accounts / agents_needed

        # Simulate throughput with realistic variance
        base_throughput = accounts / (hours * 3600)

        # Add variance for realistic simulation
        throughput_samples = []
        for _ in range(100):
            # Throughput varies +/- 20%
            sample = base_throughput * random.uniform(0.8, 1.2)
            throughput_samples.append(sample)

        result.throughput_achieved = statistics.mean(throughput_samples)
        result.throughput_pct = (result.throughput_achieved / config.target_throughput_per_second) * 100

        # Calculate recovery based on scale effects
        # Larger scale = slightly better recovery due to better data
        scale_bonus = min(0.05, math.log10(accounts) * 0.01)
        result.recovery_rate = min(0.45, config.target_recovery_rate + scale_bonus)

        # Simulate collections
        avg_balance = Decimal("185.00")  # Average micro-loan balance
        result.accounts_processed = accounts
        result.total_collected = avg_balance * Decimal(str(accounts * result.recovery_rate))
        result.avg_collection = result.total_collected / accounts if accounts > 0 else Decimal("0")

        # Agent utilization
        optimal_accounts = agents_needed * config.accounts_per_agent
        result.agent_utilization = min(1.0, accounts / optimal_accounts)

    async def _test_channel_capacity(
        self,
        result: ScaleStressResult,
        accounts: int,
    ):
        """Test each communication channel under load"""

        # Channel distribution (typical)
        channel_distribution = {
            "sms": 0.45,      # 45% SMS
            "email": 0.35,   # 35% Email
            "voice": 0.15,   # 15% Voice
            "mail": 0.05,    # 5% Mail
        }

        # Average contacts per account
        avg_contacts_per_account = 3.5

        for channel, pct in channel_distribution.items():
            channel_accounts = int(accounts * pct)
            messages = int(channel_accounts * avg_contacts_per_account)

            channel_result = await self._stress_test_channel(
                channel, messages, accounts
            )
            result.channel_results[channel] = channel_result

    async def _stress_test_channel(
        self,
        channel: str,
        messages: int,
        total_accounts: int,
    ) -> ChannelStressResult:
        """Stress test a single channel"""

        result = ChannelStressResult(channel=channel)
        result.messages_attempted = messages

        # Get rate limits
        if channel == "sms":
            rate_limit = self.rate_limits.sms_per_second
            cost_per = self.channel_costs.sms_outbound
            # Calculate saturation
            seconds_needed = messages / rate_limit
            hours_available = 12  # 8am-8pm = 12 hours
            seconds_available = hours_available * 3600

        elif channel == "email":
            rate_limit = self.rate_limits.email_per_second
            cost_per = self.channel_costs.email_transactional
            seconds_needed = messages / rate_limit
            hours_available = 24
            seconds_available = hours_available * 3600

        elif channel == "voice":
            rate_limit = self.rate_limits.voice_cps
            cost_per = (self.channel_costs.voice_outbound_per_min *
                       self.channel_costs.avg_call_duration_min)
            # Voice is limited by concurrent calls
            avg_call_duration = self.channel_costs.avg_call_duration_min * 60
            calls_per_hour = (self.rate_limits.voice_concurrent_calls * 3600) / avg_call_duration
            hours_available = 12
            max_calls = int(calls_per_hour * hours_available)
            seconds_needed = messages / rate_limit
            seconds_available = hours_available * 3600

        else:  # mail
            rate_limit = 10000  # Physical mail processing limit
            cost_per = self.channel_costs.mail_letter
            seconds_needed = messages / rate_limit
            seconds_available = 8 * 3600  # 8 hour processing day

        # Calculate saturation
        result.saturation_pct = min(100, (seconds_needed / seconds_available) * 100)

        # Calculate rate limit hits
        if result.saturation_pct > 80:
            result.rate_limit_hits = int(messages * (result.saturation_pct - 80) / 100)

        # Calculate delivery success
        base_delivery_rate = {
            "sms": 0.95,
            "email": 0.92,
            "voice": 0.75,  # Lower due to no-answers
            "mail": 0.88,
        }.get(channel, 0.90)

        # Degradation at high saturation
        if result.saturation_pct > 90:
            degradation = (result.saturation_pct - 90) / 100
            base_delivery_rate *= (1 - degradation * 0.3)

        result.messages_delivered = int(messages * base_delivery_rate)
        result.messages_failed = messages - result.messages_delivered

        # Calculate latency
        base_latency = {
            "sms": 50,
            "email": 100,
            "voice": 200,
            "mail": 86400000,  # 1 day
        }.get(channel, 100)

        # Latency increases with load
        load_factor = 1 + (result.saturation_pct / 100)
        result.avg_latency_ms = base_latency * load_factor
        result.p99_latency_ms = result.avg_latency_ms * 3.5

        # Calculate cost
        result.cost_total = Decimal(str(messages * cost_per))

        # Check for breaking point
        if result.saturation_pct > 95:
            result.breaking_point_reached = True

        return result

    async def _test_infrastructure(
        self,
        result: ScaleStressResult,
        accounts: int,
    ):
        """Test infrastructure under load"""

        config = result.config

        # Calculate infrastructure load
        # Assume each account requires:
        # - 10 DB operations
        # - 5MB data processed
        # - 2 queue messages

        db_ops = accounts * 10
        data_gb = (accounts * 5) / 1024
        queue_msgs = accounts * 2

        # Database connections
        # Assume connection pooling with 100 connections per server
        connections_needed = min(1000, accounts // 100)

        result.infra_result = InfraStressResult(
            compute_utilization=min(0.95, accounts / (config.accounts_per_day * 1.2)),
            memory_utilization=min(0.90, accounts / (config.accounts_per_day * 1.1)),
            db_connections_used=connections_needed,
            db_connections_max=self._get_db_pool_size(config.accounts_per_day),
            cache_hit_rate=max(0.70, 0.95 - (accounts / config.accounts_per_day) * 0.1),
            queue_depth=int(queue_msgs * 0.1),  # 10% backlog
            queue_max_depth=100_000,
            error_rate=min(0.05, (accounts / config.accounts_per_day - 0.8) * 0.1),
        )

    def _get_db_pool_size(self, accounts_per_day: int) -> int:
        """Get appropriate DB connection pool size"""
        if accounts_per_day <= 10_000:
            return 100
        elif accounts_per_day <= 100_000:
            return 500
        elif accounts_per_day <= 1_000_000:
            return 2000
        else:
            return 10000

    def _calculate_costs(
        self,
        level: ScaleLevel,
        config: ScaleLevelConfig,
        result: ScaleStressResult,
    ) -> CostAnalysis:
        """Calculate detailed cost analysis"""

        accounts = config.accounts_per_day

        cost = CostAnalysis(
            scale_level=level.value,
            accounts_per_day=accounts,
        )

        # Infrastructure costs (24 hours)
        if accounts <= 10_000:
            # Startup: minimal infrastructure
            cost.compute_daily = Decimal(str(
                2 * self.infra_costs.compute_medium_hourly * 24
            ))
            cost.database_daily = Decimal(str(
                self.infra_costs.db_small_hourly * 24
            ))
            cost.cache_daily = Decimal(str(
                self.infra_costs.cache_small_hourly * 24
            ))
        elif accounts <= 100_000:
            # Growth: scaled infrastructure
            cost.compute_daily = Decimal(str(
                4 * self.infra_costs.compute_large_hourly * 24
            ))
            cost.database_daily = Decimal(str(
                self.infra_costs.db_medium_hourly * 24
            ))
            cost.cache_daily = Decimal(str(
                self.infra_costs.cache_medium_hourly * 24
            ))
        elif accounts <= 1_000_000:
            # Scale: significant infrastructure
            cost.compute_daily = Decimal(str(
                10 * self.infra_costs.compute_xlarge_hourly * 24
            ))
            cost.database_daily = Decimal(str(
                3 * self.infra_costs.db_large_hourly * 24
            ))
            cost.cache_daily = Decimal(str(
                3 * self.infra_costs.cache_large_hourly * 24
            ))
        else:
            # Enterprise: full scale
            cost.compute_daily = Decimal(str(
                50 * self.infra_costs.compute_xlarge_hourly * 24
            ))
            cost.database_daily = Decimal(str(
                10 * self.infra_costs.db_xlarge_hourly * 24
            ))
            cost.cache_daily = Decimal(str(
                10 * self.infra_costs.cache_large_hourly * 24
            ))

        # Storage (daily portion of monthly)
        storage_gb = accounts * 0.001  # 1KB per account
        cost.storage_daily = Decimal(str(
            storage_gb * self.infra_costs.storage_ssd_monthly / 30
        ))

        # Networking
        data_transfer_gb = accounts * 0.0001  # 100KB per account
        cost.networking_daily = Decimal(str(
            data_transfer_gb * self.infra_costs.data_transfer_out
        ))

        # Queue costs
        queue_messages = accounts * 5  # 5 messages per account
        cost.queue_daily = Decimal(str(
            (queue_messages / 1_000_000) * self.infra_costs.queue_per_million
        ))

        # Channel costs from results
        for channel, ch_result in result.channel_results.items():
            if channel == "sms":
                cost.sms_daily = ch_result.cost_total
            elif channel == "email":
                cost.email_daily = ch_result.cost_total
            elif channel == "voice":
                cost.voice_daily = ch_result.cost_total
            elif channel == "mail":
                cost.mail_daily = ch_result.cost_total

        # Skip trace (20% of accounts need it)
        skip_trace_accounts = int(accounts * 0.20)
        cost.skip_trace_daily = Decimal(str(
            skip_trace_accounts * self.channel_costs.skip_trace_basic
        ))

        # Agent costs
        cost.agents_required = result.agents_deployed
        agent_daily_cost = Decimal("250")  # $250/day per agent (salary + overhead)
        cost.agent_cost_daily = agent_daily_cost * cost.agents_required

        # Calculate totals
        cost.total_daily = (
            cost.compute_daily + cost.database_daily + cost.storage_daily +
            cost.networking_daily + cost.cache_daily + cost.queue_daily +
            cost.sms_daily + cost.email_daily + cost.voice_daily +
            cost.mail_daily + cost.skip_trace_daily + cost.agent_cost_daily
        )

        # Per-account and per-dollar metrics
        if accounts > 0:
            cost.cost_per_account = cost.total_daily / accounts

        if result.total_collected > 0:
            cost.cost_per_dollar_collected = cost.total_daily / result.total_collected

        # Economies of scale
        baseline_cost_per_account = Decimal("2.50")  # At startup scale
        if cost.cost_per_account > 0:
            cost.economies_of_scale_factor = float(
                baseline_cost_per_account / cost.cost_per_account
            )

        # Determine cost trend
        if cost.economies_of_scale_factor > 1.5:
            cost.marginal_cost_trend = "decreasing (strong economies of scale)"
        elif cost.economies_of_scale_factor > 1.1:
            cost.marginal_cost_trend = "decreasing (moderate economies of scale)"
        else:
            cost.marginal_cost_trend = "linear"

        return cost

    def _identify_breaking_points(self, result: ScaleStressResult):
        """Identify system breaking points"""

        config = result.config

        # Check channel saturation
        for channel, ch_result in result.channel_results.items():
            if ch_result.saturation_pct > 90:
                bp = BreakingPoint(
                    component=f"{channel.upper()} Channel",
                    metric="saturation",
                    threshold=90.0,
                    actual_value=ch_result.saturation_pct,
                    scale_level=config.name,
                    accounts_at_break=int(
                        config.accounts_per_day * (90 / ch_result.saturation_pct)
                    ),
                    recommendation=f"Add parallel {channel} providers or increase rate limits"
                )
                self.breaking_points.append(bp)
                result.breaking_points.append(bp)

        # Check infrastructure
        infra = result.infra_result

        if infra.compute_utilization > 0.85:
            bp = BreakingPoint(
                component="Compute",
                metric="CPU utilization",
                threshold=85.0,
                actual_value=infra.compute_utilization * 100,
                scale_level=config.name,
                accounts_at_break=int(
                    config.accounts_per_day * (0.85 / infra.compute_utilization)
                ),
                recommendation="Scale out compute nodes or optimize processing"
            )
            self.breaking_points.append(bp)
            result.breaking_points.append(bp)

        if infra.db_connections_used >= infra.db_connections_max * 0.9:
            bp = BreakingPoint(
                component="Database",
                metric="connection pool",
                threshold=90.0,
                actual_value=(infra.db_connections_used / infra.db_connections_max) * 100,
                scale_level=config.name,
                accounts_at_break=int(
                    config.accounts_per_day * 0.9 *
                    (infra.db_connections_max / infra.db_connections_used)
                ),
                recommendation="Add read replicas or implement connection pooling"
            )
            self.breaking_points.append(bp)
            result.breaking_points.append(bp)

        if infra.error_rate > 0.02:
            bp = BreakingPoint(
                component="System",
                metric="error rate",
                threshold=2.0,
                actual_value=infra.error_rate * 100,
                scale_level=config.name,
                accounts_at_break=int(
                    config.accounts_per_day * (0.02 / infra.error_rate)
                ),
                recommendation="Implement circuit breakers and retry mechanisms"
            )
            self.breaking_points.append(bp)
            result.breaking_points.append(bp)

    def _calculate_quality_metrics(self, result: ScaleStressResult):
        """Calculate quality and compliance metrics"""

        # Quality score based on multiple factors
        factors = []

        # Throughput achievement (0-1)
        throughput_score = min(1.0, result.throughput_pct / 100)
        factors.append(throughput_score * 0.25)

        # Recovery rate vs target (0-1)
        recovery_score = min(1.0, result.recovery_rate / result.config.target_recovery_rate)
        factors.append(recovery_score * 0.30)

        # Channel delivery success (0-1)
        delivery_scores = []
        for ch_result in result.channel_results.values():
            if ch_result.messages_attempted > 0:
                rate = ch_result.messages_delivered / ch_result.messages_attempted
                delivery_scores.append(rate)
        if delivery_scores:
            factors.append(statistics.mean(delivery_scores) * 0.25)

        # Error rate (inverse, 0-1)
        error_score = max(0, 1 - (result.infra_result.error_rate * 10))
        factors.append(error_score * 0.20)

        result.quality_score = sum(factors) * 100

        # Compliance risk score
        # Higher at larger scales due to more potential violations
        base_risk = 0.05
        scale_factor = math.log10(result.config.accounts_per_day) / 7  # Normalized

        # Channel saturation increases risk
        max_saturation = max(
            ch.saturation_pct for ch in result.channel_results.values()
        ) if result.channel_results else 0
        saturation_risk = max_saturation / 200  # 0.5 at 100% saturation

        # Error rate contributes to risk
        error_risk = result.infra_result.error_rate * 2

        result.compliance_risk_score = min(1.0, base_risk + scale_factor + saturation_risk + error_risk)

    def _generate_recommendations(self, result: ScaleStressResult) -> List[str]:
        """Generate recommendations based on test results"""

        recommendations = []
        config = result.config

        # Throughput recommendations
        if result.throughput_pct < 80:
            recommendations.append(
                f"CRITICAL: Throughput at {result.throughput_pct:.0f}% of target. "
                f"Add {int((1 - result.throughput_pct/100) * config.max_agents)} more processing agents."
            )

        # Channel-specific recommendations
        for channel, ch_result in result.channel_results.items():
            if ch_result.saturation_pct > 80:
                if channel == "sms":
                    recommendations.append(
                        f"SMS capacity at {ch_result.saturation_pct:.0f}%. "
                        f"Add secondary SMS provider (MessageBird, Vonage) for load balancing."
                    )
                elif channel == "voice":
                    recommendations.append(
                        f"Voice capacity at {ch_result.saturation_pct:.0f}%. "
                        f"Increase concurrent call limits or add AI voice overflow handling."
                    )
                elif channel == "email":
                    recommendations.append(
                        f"Email capacity at {ch_result.saturation_pct:.0f}%. "
                        f"Consider dedicated IP pools and warming schedule."
                    )

        # Infrastructure recommendations
        infra = result.infra_result

        if infra.compute_utilization > 0.75:
            recommendations.append(
                f"Compute at {infra.compute_utilization*100:.0f}% utilization. "
                f"Pre-provision additional capacity for {config.accounts_per_day * 1.5:,.0f} accounts."
            )

        if infra.cache_hit_rate < 0.85:
            recommendations.append(
                f"Cache hit rate at {infra.cache_hit_rate*100:.0f}%. "
                f"Increase cache size and implement more aggressive caching strategies."
            )

        if infra.error_rate > 0.01:
            recommendations.append(
                f"Error rate at {infra.error_rate*100:.2f}%. "
                f"Implement circuit breakers and graceful degradation patterns."
            )

        # Cost recommendations
        if result.cost_analysis:
            if result.cost_analysis.cost_per_dollar_collected > Decimal("0.10"):
                recommendations.append(
                    f"Cost per dollar collected at ${result.cost_analysis.cost_per_dollar_collected:.3f}. "
                    f"Optimize channel mix - shift from voice to SMS where effective."
                )

            if result.cost_analysis.economies_of_scale_factor < 1.2:
                recommendations.append(
                    f"Weak economies of scale ({result.cost_analysis.economies_of_scale_factor:.2f}x). "
                    f"Consolidate infrastructure and negotiate volume discounts."
                )

        # Compliance recommendations
        if result.compliance_risk_score > 0.3:
            recommendations.append(
                f"Compliance risk elevated ({result.compliance_risk_score:.0%}). "
                f"Implement additional monitoring, reduce contact frequency, and audit queue."
            )

        # Agent efficiency
        if result.accounts_per_agent > config.accounts_per_agent * 1.2:
            recommendations.append(
                f"Agents overloaded at {result.accounts_per_agent:.0f} accounts/agent. "
                f"Hire {int((result.accounts_per_agent / config.accounts_per_agent - 1) * result.agents_deployed)} additional agents."
            )

        return recommendations

    def _generate_capacity_matrix(self) -> CapacityPlanningMatrix:
        """Generate capacity planning matrix from all results"""

        matrix = CapacityPlanningMatrix()

        for level, result in self.results.items():
            level_name = level.value
            config = result.config

            # Accounts per infrastructure dollar
            if result.cost_analysis:
                infra_cost = (
                    result.cost_analysis.compute_daily +
                    result.cost_analysis.database_daily +
                    result.cost_analysis.cache_daily +
                    result.cost_analysis.storage_daily
                )
                if infra_cost > 0:
                    matrix.accounts_per_infra_dollar[level_name] = float(
                        config.accounts_per_day / infra_cost
                    )

            # Optimal batch sizes
            # Based on throughput and channel capacity
            min_channel_capacity = min(
                ch.messages_attempted / max(1, ch.rate_limit_hits + 1)
                for ch in result.channel_results.values()
            ) if result.channel_results else 1000

            matrix.optimal_batch_sizes[level_name] = int(
                min(10000, min_channel_capacity / 10)
            )

            # Burst capacity (80% of breaking point)
            if result.breaking_points:
                min_break = min(bp.accounts_at_break for bp in result.breaking_points)
                matrix.burst_capacity_accounts[level_name] = int(min_break * 0.8)
            else:
                matrix.burst_capacity_accounts[level_name] = int(
                    config.accounts_per_day * 1.5
                )

            # Scale-up thresholds
            matrix.scale_up_thresholds[level_name] = {
                "cpu_utilization": 0.75,
                "memory_utilization": 0.80,
                "queue_depth": 50000,
                "error_rate": 0.02,
                "channel_saturation": 0.85,
            }

            # Infrastructure requirements
            matrix.infra_requirements[level_name] = self._get_infra_requirements(level, config)

            # Cost projections
            if result.cost_analysis:
                matrix.monthly_costs[level_name] = result.cost_analysis.total_daily * 30
                matrix.annual_costs[level_name] = result.cost_analysis.total_daily * 365

                # Breakeven (accounts needed to cover costs)
                # Assume $55 average collection and 30% recovery
                avg_profit_per_account = Decimal("55") * Decimal("0.30") * Decimal("0.40")  # 40% margin
                if avg_profit_per_account > 0:
                    matrix.breakeven_points[level_name] = int(
                        result.cost_analysis.total_daily / avg_profit_per_account
                    )

        # Determine recommended starting scale
        if matrix.accounts_per_infra_dollar:
            # Find best efficiency at manageable scale
            for level_name in ["startup", "growth"]:
                if level_name in matrix.accounts_per_infra_dollar:
                    matrix.recommended_starting_scale = level_name
                    break

        # Growth path
        matrix.growth_path = ["startup", "growth", "scale", "enterprise"]

        return matrix

    def _get_infra_requirements(
        self,
        level: ScaleLevel,
        config: ScaleLevelConfig,
    ) -> Dict[str, Any]:
        """Get infrastructure requirements for scale level"""

        if level == ScaleLevel.STARTUP:
            return {
                "compute_nodes": 2,
                "compute_type": "t3.medium",
                "db_type": "db.t3.small",
                "db_replicas": 1,
                "cache_nodes": 1,
                "cache_type": "cache.t3.micro",
                "regions": 1,
                "estimated_monthly": "$500-1,000",
            }
        elif level == ScaleLevel.GROWTH:
            return {
                "compute_nodes": 4,
                "compute_type": "c5.xlarge",
                "db_type": "db.r5.large",
                "db_replicas": 2,
                "cache_nodes": 2,
                "cache_type": "cache.r5.large",
                "regions": 2,
                "estimated_monthly": "$3,000-5,000",
            }
        elif level == ScaleLevel.SCALE:
            return {
                "compute_nodes": 10,
                "compute_type": "c5.4xlarge",
                "db_type": "db.r5.xlarge",
                "db_replicas": 3,
                "cache_nodes": 3,
                "cache_type": "cache.r5.xlarge",
                "regions": 3,
                "estimated_monthly": "$15,000-25,000",
            }
        else:  # Enterprise
            return {
                "compute_nodes": 50,
                "compute_type": "c5.4xlarge",
                "db_type": "db.r5.4xlarge",
                "db_replicas": 5,
                "cache_nodes": 10,
                "cache_type": "cache.r5.xlarge",
                "regions": 5,
                "estimated_monthly": "$75,000-150,000",
            }

    def _print_scale_results(self, result: ScaleStressResult):
        """Print results for a single scale level"""

        config = result.config

        print(f"\n  PROCESSING METRICS:")
        print(f"    Accounts Processed:    {result.accounts_processed:,}")
        print(f"    Throughput Achieved:   {result.throughput_achieved:.2f}/sec "
              f"({result.throughput_pct:.0f}% of target)")
        print(f"    Recovery Rate:         {result.recovery_rate*100:.1f}%")
        print(f"    Total Collected:       ${result.total_collected:,.2f}")

        print(f"\n  AGENT METRICS:")
        print(f"    Agents Deployed:       {result.agents_deployed:,}")
        print(f"    Accounts/Agent:        {result.accounts_per_agent:.0f}")
        print(f"    Agent Utilization:     {result.agent_utilization*100:.0f}%")

        print(f"\n  CHANNEL CAPACITY:")
        print(f"    {'Channel':<10} {'Attempted':>12} {'Delivered':>12} {'Saturation':>12} {'Cost':>14}")
        print(f"    {'-'*60}")
        for channel, ch in sorted(result.channel_results.items()):
            print(f"    {channel.upper():<10} {ch.messages_attempted:>12,} "
                  f"{ch.messages_delivered:>12,} {ch.saturation_pct:>11.0f}% "
                  f"${ch.cost_total:>13,.2f}")

        print(f"\n  INFRASTRUCTURE:")
        infra = result.infra_result
        print(f"    Compute Utilization:   {infra.compute_utilization*100:.0f}%")
        print(f"    Memory Utilization:    {infra.memory_utilization*100:.0f}%")
        print(f"    DB Connections:        {infra.db_connections_used}/{infra.db_connections_max}")
        print(f"    Cache Hit Rate:        {infra.cache_hit_rate*100:.0f}%")
        print(f"    Error Rate:            {infra.error_rate*100:.2f}%")

        if result.cost_analysis:
            cost = result.cost_analysis
            print(f"\n  COST ANALYSIS:")
            print(f"    Total Daily Cost:      ${cost.total_daily:,.2f}")
            print(f"    Cost per Account:      ${cost.cost_per_account:.4f}")
            print(f"    Cost per $1 Collected: ${cost.cost_per_dollar_collected:.4f}")
            print(f"    Economies of Scale:    {cost.economies_of_scale_factor:.2f}x")
            print(f"    Cost Trend:            {cost.marginal_cost_trend}")

        if result.breaking_points:
            print(f"\n  BREAKING POINTS IDENTIFIED:")
            for bp in result.breaking_points:
                print(f"    - {bp.component}: {bp.metric} at {bp.actual_value:.0f}% "
                      f"(threshold: {bp.threshold:.0f}%)")
                print(f"      Breaks at: {bp.accounts_at_break:,} accounts")

        print(f"\n  QUALITY METRICS:")
        print(f"    Quality Score:         {result.quality_score:.0f}/100")
        print(f"    Compliance Risk:       {result.compliance_risk_score*100:.0f}%")

        if result.recommendations:
            print(f"\n  RECOMMENDATIONS:")
            for i, rec in enumerate(result.recommendations[:5], 1):
                print(f"    {i}. {rec}")

    def _print_final_analysis(self, matrix: CapacityPlanningMatrix):
        """Print final capacity planning analysis"""

        print("\n" + "=" * 90)
        print("  CAPACITY PLANNING MATRIX")
        print("=" * 90)

        print(f"\n  EFFICIENCY BY SCALE:")
        print(f"    {'Scale Level':<15} {'Accounts/Infra$':>18} {'Optimal Batch':>15} {'Burst Capacity':>18}")
        print(f"    {'-'*70}")
        for level in ["startup", "growth", "scale", "enterprise"]:
            if level in matrix.accounts_per_infra_dollar:
                print(f"    {level.upper():<15} "
                      f"{matrix.accounts_per_infra_dollar[level]:>18,.0f} "
                      f"{matrix.optimal_batch_sizes[level]:>15,} "
                      f"{matrix.burst_capacity_accounts[level]:>18,}")

        print(f"\n  INFRASTRUCTURE REQUIREMENTS:")
        for level, reqs in matrix.infra_requirements.items():
            print(f"\n    {level.upper()}:")
            print(f"      Compute:   {reqs['compute_nodes']}x {reqs['compute_type']}")
            print(f"      Database:  {reqs['db_type']} + {reqs['db_replicas']} replicas")
            print(f"      Cache:     {reqs['cache_nodes']}x {reqs['cache_type']}")
            print(f"      Regions:   {reqs['regions']}")
            print(f"      Est. Cost: {reqs['estimated_monthly']}/month")

        print(f"\n  COST PROJECTIONS:")
        print(f"    {'Scale Level':<15} {'Monthly Cost':>18} {'Annual Cost':>18} {'Breakeven/Day':>18}")
        print(f"    {'-'*70}")
        for level in ["startup", "growth", "scale", "enterprise"]:
            if level in matrix.monthly_costs:
                print(f"    {level.upper():<15} "
                      f"${matrix.monthly_costs[level]:>17,.0f} "
                      f"${matrix.annual_costs[level]:>17,.0f} "
                      f"{matrix.breakeven_points.get(level, 0):>18,}")

        print(f"\n  SCALE-UP TRIGGERS (Universal):")
        sample_thresholds = list(matrix.scale_up_thresholds.values())[0] if matrix.scale_up_thresholds else {}
        for metric, threshold in sample_thresholds.items():
            if metric == "queue_depth":
                print(f"    - {metric.replace('_', ' ').title()}: {threshold:,.0f} messages")
            else:
                print(f"    - {metric.replace('_', ' ').title()}: {threshold*100:.0f}%")

        print(f"\n  PEAK HANDLING STRATEGY:")
        print(f"    Peak Multiplier:       {matrix.peak_multiplier}x average load")
        print(f"    Pre-warming Required:  15 minutes before peak")
        print(f"    Auto-scale Cooldown:   5 minutes")

        print(f"\n  RECOMMENDED GROWTH PATH:")
        print(f"    Starting Scale:        {matrix.recommended_starting_scale.upper()}")
        print(f"    Growth Path:           {' -> '.join(s.upper() for s in matrix.growth_path)}")

        # All breaking points summary
        print(f"\n  ALL BREAKING POINTS SUMMARY:")
        if self.breaking_points:
            sorted_bps = sorted(self.breaking_points, key=lambda x: x.accounts_at_break)
            print(f"    {'Scale':<12} {'Component':<20} {'Break Point':>15} {'Recommendation':<40}")
            print(f"    {'-'*90}")
            for bp in sorted_bps[:10]:
                print(f"    {bp.scale_level:<12} {bp.component:<20} "
                      f"{bp.accounts_at_break:>15,} {bp.recommendation[:40]}")
        else:
            print(f"    No breaking points identified at tested scales.")

        print("\n" + "=" * 90)
        print("  STRESS TEST COMPLETE")
        print("=" * 90)


# =============================================================================
# CLI RUNNER
# =============================================================================

async def run_stress_test():
    """Run the complete stress test suite"""

    simulator = ScaleStressTestSimulator()

    results = await simulator.run_full_stress_test(
        levels=[
            ScaleLevel.STARTUP,
            ScaleLevel.GROWTH,
            ScaleLevel.SCALE,
            ScaleLevel.ENTERPRISE,
        ],
        simulation_hours=24,
    )

    return results


async def run_single_level_test(level: str = "growth"):
    """Run stress test for a single scale level"""

    level_map = {
        "startup": ScaleLevel.STARTUP,
        "growth": ScaleLevel.GROWTH,
        "scale": ScaleLevel.SCALE,
        "enterprise": ScaleLevel.ENTERPRISE,
    }

    if level.lower() not in level_map:
        print(f"Invalid level: {level}. Choose from: {list(level_map.keys())}")
        return None

    simulator = ScaleStressTestSimulator()

    results = await simulator.run_full_stress_test(
        levels=[level_map[level.lower()]],
        simulation_hours=24,
    )

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        level = sys.argv[1]
        asyncio.run(run_single_level_test(level))
    else:
        asyncio.run(run_stress_test())
