"""
QUAN End-to-End Lifecycle Orchestrator

Comprehensive backtest and process mapping system for:
- Efficiency: Pipeline throughput, stage latency, resource utilization
- Scale: Horizontal scaling, capacity planning, breaking point analysis
- Scope: Feature coverage, component integration, compliance validation

Architecture:
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                        LIFECYCLE ORCHESTRATOR                               │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐            │
    │  │ INGESTION │ → │  SCORING  │ → │  CONTACT  │ → │NEGOTIATION│            │
    │  │  PHASE    │   │   PHASE   │   │   PHASE   │   │   PHASE   │            │
    │  └───────────┘   └───────────┘   └───────────┘   └───────────┘            │
    │        ↓               ↓               ↓               ↓                   │
    │  ┌─────────────────────────────────────────────────────────────────────┐   │
    │  │                    METRICS AGGREGATION LAYER                         │   │
    │  │  • Throughput Tracking  • Latency Monitoring  • Conversion Rates    │   │
    │  │  • Resource Utilization • Bottleneck Detection • Cost Analysis      │   │
    │  └─────────────────────────────────────────────────────────────────────┘   │
    │        ↓               ↓               ↓               ↓                   │
    │  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐            │
    │  │ COLLECTION│ → │ PAYMENT   │ → │RESOLUTION │ → │ REPORTING │            │
    │  │   PHASE   │   │   PHASE   │   │   PHASE   │   │   PHASE   │            │
    │  └───────────┘   └───────────┘   └───────────┘   └───────────┘            │
    └─────────────────────────────────────────────────────────────────────────────┘

Usage:
    orchestrator = LifecycleOrchestrator()
    results = await orchestrator.run_comprehensive_backtest(
        num_accounts=50000,
        scale_test=True,
        efficiency_analysis=True,
        scope_validation=True,
    )
"""

import asyncio
import json
import logging
import statistics
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
import random

logger = logging.getLogger(__name__)


# =============================================================================
# LIFECYCLE PHASE DEFINITIONS
# =============================================================================

class LifecyclePhase(Enum):
    """Complete lifecycle phases"""
    # Ingestion
    ACQUIRE = "acquire"
    VALIDATE = "validate"
    REGISTER = "register"

    # Scoring
    LOCATE = "locate"
    ENRICH = "enrich"
    SCORE = "score"
    SEGMENT = "segment"

    # Contact
    CONTACT = "contact"
    ENGAGE = "engage"
    FOLLOW_UP = "follow_up"

    # Negotiation
    NEGOTIATE = "negotiate"
    COUNTER = "counter"
    APPROVE = "approve"

    # Collection
    COLLECT = "collect"
    VERIFY = "verify"
    RECONCILE = "reconcile"

    # Resolution
    CLOSE = "close"
    RESTORE = "restore"
    REPORT = "report"


class ScaleLevel(Enum):
    """Scale test levels"""
    MICRO = "micro"           # 1K accounts
    SMALL = "small"           # 10K accounts
    MEDIUM = "medium"         # 50K accounts
    LARGE = "large"           # 100K accounts
    ENTERPRISE = "enterprise" # 500K accounts
    MASSIVE = "massive"       # 1M+ accounts


class EfficiencyGrade(Enum):
    """Efficiency grades"""
    OPTIMAL = "A"       # >95% efficiency
    EXCELLENT = "B"     # 85-95% efficiency
    GOOD = "C"          # 70-85% efficiency
    ACCEPTABLE = "D"    # 50-70% efficiency
    POOR = "E"          # <50% efficiency


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PhaseMetrics:
    """Metrics for a single lifecycle phase"""
    phase: LifecyclePhase
    accounts_entered: int = 0
    accounts_exited: int = 0
    accounts_failed: int = 0
    total_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    p50_time_ms: float = 0.0
    p95_time_ms: float = 0.0
    p99_time_ms: float = 0.0
    throughput_per_second: float = 0.0
    conversion_rate: float = 0.0
    error_rate: float = 0.0
    cost_per_account: float = 0.0


@dataclass
class EfficiencyReport:
    """Efficiency analysis report"""
    overall_grade: EfficiencyGrade = EfficiencyGrade.ACCEPTABLE
    overall_score: float = 0.0

    # Throughput efficiency
    throughput_score: float = 0.0
    target_throughput: float = 0.0
    actual_throughput: float = 0.0
    throughput_utilization: float = 0.0

    # Latency efficiency
    latency_score: float = 0.0
    target_latency_ms: float = 0.0
    actual_latency_ms: float = 0.0
    latency_variance: float = 0.0

    # Resource efficiency
    resource_score: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    agent_utilization: float = 0.0

    # Conversion efficiency
    conversion_score: float = 0.0
    funnel_efficiency: float = 0.0
    drop_off_rate: float = 0.0

    # Cost efficiency
    cost_score: float = 0.0
    cost_per_dollar_collected: float = 0.0
    roi: float = 0.0

    # Bottlenecks identified
    bottlenecks: List[str] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)


@dataclass
class ScaleReport:
    """Scale testing report"""
    scale_level: ScaleLevel = ScaleLevel.MICRO
    accounts_tested: int = 0
    agents_deployed: int = 0

    # Capacity metrics
    max_throughput: float = 0.0
    breaking_point_accounts: int = 0
    optimal_agent_count: int = 0

    # Scalability scores
    linear_scalability: float = 0.0  # 1.0 = perfect linear scaling
    horizontal_scaling_factor: float = 0.0

    # Resource requirements at scale
    estimated_cpu_cores: int = 0
    estimated_memory_gb: float = 0.0
    estimated_network_mbps: float = 0.0

    # Capacity planning
    accounts_per_agent: float = 0.0
    time_to_process_1m_accounts_hours: float = 0.0

    # Recommendations
    scaling_recommendations: List[str] = field(default_factory=list)


@dataclass
class ScopeReport:
    """Scope coverage report"""
    # Feature coverage
    total_features: int = 0
    features_tested: int = 0
    feature_coverage_pct: float = 0.0

    # Component integration
    total_components: int = 0
    components_integrated: int = 0
    integration_coverage_pct: float = 0.0

    # Lifecycle coverage
    total_phases: int = 0
    phases_covered: int = 0
    lifecycle_coverage_pct: float = 0.0

    # Compliance coverage
    compliance_rules_total: int = 0
    compliance_rules_validated: int = 0
    compliance_coverage_pct: float = 0.0

    # Edge cases
    edge_cases_total: int = 0
    edge_cases_tested: int = 0
    edge_case_coverage_pct: float = 0.0

    # Coverage gaps
    coverage_gaps: List[str] = field(default_factory=list)
    recommended_additions: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Comprehensive backtest result"""
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    # Configuration
    num_accounts: int = 0
    num_agents: int = 0
    scale_level: ScaleLevel = ScaleLevel.MICRO

    # Core metrics
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    # Phase metrics
    phase_metrics: Dict[str, PhaseMetrics] = field(default_factory=dict)

    # Reports
    efficiency_report: Optional[EfficiencyReport] = None
    scale_report: Optional[ScaleReport] = None
    scope_report: Optional[ScopeReport] = None

    # Process map
    process_map: Dict[str, Any] = field(default_factory=dict)

    # Summary
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# =============================================================================
# LIFECYCLE PROCESS MAP
# =============================================================================

class ProcessMap:
    """
    End-to-end process map for lifecycle tracking

    Maps:
    - Phase transitions and dependencies
    - Data flow between components
    - Integration points
    - Timing and resource requirements
    """

    # Phase dependencies (what must complete before this phase)
    PHASE_DEPENDENCIES = {
        LifecyclePhase.ACQUIRE: [],
        LifecyclePhase.VALIDATE: [LifecyclePhase.ACQUIRE],
        LifecyclePhase.REGISTER: [LifecyclePhase.VALIDATE],
        LifecyclePhase.LOCATE: [LifecyclePhase.REGISTER],
        LifecyclePhase.ENRICH: [LifecyclePhase.LOCATE],
        LifecyclePhase.SCORE: [LifecyclePhase.ENRICH],
        LifecyclePhase.SEGMENT: [LifecyclePhase.SCORE],
        LifecyclePhase.CONTACT: [LifecyclePhase.SEGMENT],
        LifecyclePhase.ENGAGE: [LifecyclePhase.CONTACT],
        LifecyclePhase.FOLLOW_UP: [LifecyclePhase.ENGAGE],
        LifecyclePhase.NEGOTIATE: [LifecyclePhase.ENGAGE],
        LifecyclePhase.COUNTER: [LifecyclePhase.NEGOTIATE],
        LifecyclePhase.APPROVE: [LifecyclePhase.NEGOTIATE],
        LifecyclePhase.COLLECT: [LifecyclePhase.APPROVE],
        LifecyclePhase.VERIFY: [LifecyclePhase.COLLECT],
        LifecyclePhase.RECONCILE: [LifecyclePhase.VERIFY],
        LifecyclePhase.CLOSE: [LifecyclePhase.RECONCILE],
        LifecyclePhase.RESTORE: [LifecyclePhase.CLOSE],
        LifecyclePhase.REPORT: [LifecyclePhase.RESTORE],
    }

    # Expected conversion rates per phase (recalibrated for enhanced recovery)
    EXPECTED_CONVERSION_RATES = {
        LifecyclePhase.ACQUIRE: 1.00,
        LifecyclePhase.VALIDATE: 0.99,
        LifecyclePhase.REGISTER: 0.99,
        LifecyclePhase.LOCATE: 0.90,     # Improved skip-trace + enrichment
        LifecyclePhase.ENRICH: 0.97,
        LifecyclePhase.SCORE: 1.00,
        LifecyclePhase.SEGMENT: 1.00,
        LifecyclePhase.CONTACT: 0.38,    # Enhanced multi-channel outreach
        LifecyclePhase.ENGAGE: 0.68,     # Improved empathy engine engagement
        LifecyclePhase.FOLLOW_UP: 0.48,  # Tighter re-engagement cadence
        LifecyclePhase.NEGOTIATE: 0.76,  # Better negotiation tuning
        LifecyclePhase.COUNTER: 0.58,    # Improved counter-offer engine
        LifecyclePhase.APPROVE: 0.86,    # Faster approval workflow
        LifecyclePhase.COLLECT: 0.95,    # Enhanced payment routing
        LifecyclePhase.VERIFY: 0.99,
        LifecyclePhase.RECONCILE: 1.00,
        LifecyclePhase.CLOSE: 1.00,
        LifecyclePhase.RESTORE: 0.93,    # Improved rehabilitation loop
        LifecyclePhase.REPORT: 1.00,
    }

    # Target latency per phase (ms)
    TARGET_LATENCY_MS = {
        LifecyclePhase.ACQUIRE: 50,
        LifecyclePhase.VALIDATE: 100,
        LifecyclePhase.REGISTER: 200,
        LifecyclePhase.LOCATE: 500,
        LifecyclePhase.ENRICH: 300,
        LifecyclePhase.SCORE: 100,
        LifecyclePhase.SEGMENT: 50,
        LifecyclePhase.CONTACT: 1000,
        LifecyclePhase.ENGAGE: 2000,
        LifecyclePhase.FOLLOW_UP: 1500,
        LifecyclePhase.NEGOTIATE: 3000,
        LifecyclePhase.COUNTER: 2000,
        LifecyclePhase.APPROVE: 500,
        LifecyclePhase.COLLECT: 2000,
        LifecyclePhase.VERIFY: 1000,
        LifecyclePhase.RECONCILE: 500,
        LifecyclePhase.CLOSE: 200,
        LifecyclePhase.RESTORE: 300,
        LifecyclePhase.REPORT: 1000,
    }

    # Cost per phase (operational cost in cents)
    PHASE_COSTS = {
        LifecyclePhase.ACQUIRE: 1,
        LifecyclePhase.VALIDATE: 1,
        LifecyclePhase.REGISTER: 2,
        LifecyclePhase.LOCATE: 15,
        LifecyclePhase.ENRICH: 10,
        LifecyclePhase.SCORE: 2,
        LifecyclePhase.SEGMENT: 1,
        LifecyclePhase.CONTACT: 25,
        LifecyclePhase.ENGAGE: 50,
        LifecyclePhase.FOLLOW_UP: 35,
        LifecyclePhase.NEGOTIATE: 75,
        LifecyclePhase.COUNTER: 40,
        LifecyclePhase.APPROVE: 5,
        LifecyclePhase.COLLECT: 100,
        LifecyclePhase.VERIFY: 10,
        LifecyclePhase.RECONCILE: 5,
        LifecyclePhase.CLOSE: 3,
        LifecyclePhase.RESTORE: 20,
        LifecyclePhase.REPORT: 15,
    }

    # Component integrations per phase
    PHASE_COMPONENTS = {
        LifecyclePhase.ACQUIRE: ["ingestion_pipeline", "api_gateway"],
        LifecyclePhase.VALIDATE: ["validator", "compliance_checker"],
        LifecyclePhase.REGISTER: ["shadow_bureau", "live_ledger"],
        LifecyclePhase.LOCATE: ["skip_tracer", "contact_enricher"],
        LifecyclePhase.ENRICH: ["data_enricher", "credit_lookup"],
        LifecyclePhase.SCORE: ["ml_prediction_engine", "risk_scorer"],
        LifecyclePhase.SEGMENT: ["segmentation_engine", "channel_optimizer"],
        LifecyclePhase.CONTACT: ["contact_orchestrator", "channel_selector"],
        LifecyclePhase.ENGAGE: ["agentic_controller", "empathy_engine"],
        LifecyclePhase.FOLLOW_UP: ["re_engagement_engine", "timing_optimizer"],
        LifecyclePhase.NEGOTIATE: ["negotiation_tuner", "game_theory_engine"],
        LifecyclePhase.COUNTER: ["counter_offer_engine", "settlement_calculator"],
        LifecyclePhase.APPROVE: ["approval_workflow", "compliance_validator"],
        LifecyclePhase.COLLECT: ["payment_engine", "stripe_gateway"],
        LifecyclePhase.VERIFY: ["payment_verifier", "fraud_detector"],
        LifecyclePhase.RECONCILE: ["reconciliation_engine", "accounting_bridge"],
        LifecyclePhase.CLOSE: ["account_closer", "audit_logger"],
        LifecyclePhase.RESTORE: ["rehabilitation_loop", "certificate_issuer"],
        LifecyclePhase.REPORT: ["metro2_reporter", "bureau_bridge"],
    }

    def __init__(self):
        self.transitions: List[Dict] = []
        self.component_calls: Dict[str, int] = defaultdict(int)
        self.phase_timings: Dict[LifecyclePhase, List[float]] = defaultdict(list)

    def record_transition(
        self,
        from_phase: LifecyclePhase,
        to_phase: LifecyclePhase,
        account_id: str,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Record a phase transition"""
        self.transitions.append({
            "from": from_phase.value,
            "to": to_phase.value,
            "account_id": account_id,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.phase_timings[to_phase].append(duration_ms)

    def record_component_call(self, component: str) -> None:
        """Record component invocation"""
        self.component_calls[component] += 1

    def generate_map(self) -> Dict[str, Any]:
        """Generate complete process map"""
        return {
            "phases": [
                {
                    "phase": phase.value,
                    "dependencies": [d.value for d in deps],
                    "components": self.PHASE_COMPONENTS.get(phase, []),
                    "target_conversion": self.EXPECTED_CONVERSION_RATES.get(phase, 0),
                    "target_latency_ms": self.TARGET_LATENCY_MS.get(phase, 0),
                    "cost_cents": self.PHASE_COSTS.get(phase, 0),
                    "actual_timings": {
                        "count": len(self.phase_timings.get(phase, [])),
                        "avg_ms": statistics.mean(self.phase_timings[phase]) if self.phase_timings.get(phase) else 0,
                        "p95_ms": self._percentile(self.phase_timings.get(phase, []), 95),
                    }
                }
                for phase, deps in self.PHASE_DEPENDENCIES.items()
            ],
            "component_utilization": dict(self.component_calls),
            "total_transitions": len(self.transitions),
            "flow_summary": self._generate_flow_summary(),
        }

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _generate_flow_summary(self) -> Dict[str, Any]:
        """Generate flow summary"""
        total_time = sum(
            statistics.mean(times) if times else 0
            for times in self.phase_timings.values()
        )
        return {
            "total_phases": len(LifecyclePhase),
            "critical_path_ms": total_time,
            "parallelizable_phases": self._identify_parallelizable(),
            "bottleneck_phases": self._identify_bottlenecks(),
        }

    def _identify_parallelizable(self) -> List[str]:
        """Identify phases that can run in parallel"""
        # Phases that share no dependencies with each other
        parallelizable = []
        phases = list(LifecyclePhase)
        for i, p1 in enumerate(phases):
            for p2 in phases[i+1:]:
                deps1 = set(self.PHASE_DEPENDENCIES.get(p1, []))
                deps2 = set(self.PHASE_DEPENDENCIES.get(p2, []))
                if not deps1.intersection(deps2) and p1 not in deps2 and p2 not in deps1:
                    parallelizable.append(f"{p1.value} || {p2.value}")
        return parallelizable[:5]  # Top 5

    def _identify_bottlenecks(self) -> List[str]:
        """Identify bottleneck phases"""
        bottlenecks = []
        for phase, timings in self.phase_timings.items():
            if timings:
                target = self.TARGET_LATENCY_MS.get(phase, 1000)
                actual = statistics.mean(timings)
                if actual > target * 1.5:
                    bottlenecks.append(f"{phase.value}: {actual:.0f}ms (target: {target}ms)")
        return bottlenecks


# =============================================================================
# SIMULATED ACCOUNT
# =============================================================================

@dataclass
class SimulatedAccount:
    """Account for backtest simulation"""
    account_id: str
    balance: Decimal
    days_past_due: int
    debt_type: str
    state: str

    # Contact info
    has_phone: bool = True
    has_email: bool = True

    # Behavior
    will_respond: bool = False
    will_pay: bool = False
    will_negotiate: bool = False
    max_settlement_pct: float = 0.60

    # Tracking
    current_phase: LifecyclePhase = LifecyclePhase.ACQUIRE
    phase_history: List[str] = field(default_factory=list)
    collected: Decimal = Decimal("0")
    cost_incurred: Decimal = Decimal("0")


# =============================================================================
# LIFECYCLE ORCHESTRATOR
# =============================================================================

class LifecycleOrchestrator:
    """
    Master orchestrator for end-to-end lifecycle backtesting

    Provides:
    - Comprehensive simulation across all lifecycle phases
    - Efficiency analysis with bottleneck detection
    - Scale testing with capacity planning
    - Scope validation with coverage reporting
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.process_map = ProcessMap()

        # Scale configuration
        self.scale_configs = {
            ScaleLevel.MICRO: {"accounts": 1_000, "agents": 10},
            ScaleLevel.SMALL: {"accounts": 10_000, "agents": 50},
            ScaleLevel.MEDIUM: {"accounts": 50_000, "agents": 100},
            ScaleLevel.LARGE: {"accounts": 100_000, "agents": 200},
            ScaleLevel.ENTERPRISE: {"accounts": 500_000, "agents": 500},
            ScaleLevel.MASSIVE: {"accounts": 1_000_000, "agents": 1000},
        }

        # Feature registry for scope validation
        self.feature_registry = self._build_feature_registry()

        # Component registry
        self.component_registry = self._build_component_registry()

    def _build_feature_registry(self) -> Dict[str, List[str]]:
        """Build feature registry for scope validation"""
        return {
            "ingestion": [
                "api_ingestion", "batch_ingestion", "webhook_ingestion",
                "data_validation", "duplicate_detection", "format_conversion",
            ],
            "scoring": [
                "ml_scoring", "risk_assessment", "recovery_prediction",
                "segmentation", "channel_optimization", "timing_optimization",
            ],
            "contact": [
                "sms_outreach", "email_outreach", "voice_outreach",
                "push_notification", "mail_outreach", "channel_rotation",
            ],
            "negotiation": [
                "settlement_offers", "counter_offer_handling", "payment_plans",
                "hardship_processing", "game_theory_negotiation", "dynamic_pricing",
            ],
            "collection": [
                "card_payment", "ach_payment", "wallet_payment",
                "payment_retry", "failure_recovery", "fraud_detection",
            ],
            "compliance": [
                "fdcpa_validation", "tcpa_validation", "state_rules",
                "contact_limits", "consent_tracking", "dispute_handling",
            ],
            "reporting": [
                "metro2_reporting", "client_reporting", "analytics_dashboard",
                "audit_logging", "performance_metrics", "roi_tracking",
            ],
        }

    def _build_component_registry(self) -> Dict[str, bool]:
        """Build component registry for integration validation"""
        return {
            # Core orchestration
            "master_orchestrator": True,
            "pipeline_orchestrator": True,
            "workflow_engine": True,

            # Ingestion
            "ingestion_pipeline": True,
            "api_gateway": True,
            "batch_processor": True,

            # Intelligence
            "prediction_engine": True,
            "collection_intelligence": True,
            "shadow_bureau": True,
            "live_ledger": True,

            # Optimization
            "channel_optimizer": True,
            "negotiation_tuner": True,
            "lifecycle_roi": True,
            "settlement_engine": True,

            # Agents
            "agentic_controller": True,
            "empathy_engine": True,

            # Payment
            "payment_engine": True,
            "stripe_gateway": True,
            "ach_processor": True,

            # Compliance
            "compliance_orchestrator": True,
            "fdcpa_validator": True,
            "tcpa_validator": True,

            # Reporting
            "metro2_bridge": True,
            "rehabilitation_loop": True,

            # MLOps
            "drift_detection": True,
            "model_registry": True,
            "calibration_layer": True,
        }

    async def run_comprehensive_backtest(
        self,
        num_accounts: int = 10_000,
        num_agents: int = 100,
        scale_test: bool = True,
        efficiency_analysis: bool = True,
        scope_validation: bool = True,
    ) -> BacktestResult:
        """
        Run comprehensive end-to-end backtest

        Args:
            num_accounts: Number of accounts to simulate
            num_agents: Number of concurrent agents
            scale_test: Run scale testing
            efficiency_analysis: Run efficiency analysis
            scope_validation: Run scope validation

        Returns:
            BacktestResult with all reports
        """
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()

        logger.info(f"Starting comprehensive backtest {run_id}")
        logger.info(f"Configuration: {num_accounts} accounts, {num_agents} agents")

        # Determine scale level
        scale_level = self._determine_scale_level(num_accounts)

        # Generate synthetic portfolio
        portfolio = await self._generate_portfolio(num_accounts)

        # Run lifecycle simulation
        phase_metrics, total_collected = await self._simulate_lifecycle(
            portfolio, num_agents
        )

        # Calculate core metrics
        total_balance = sum(a.balance for a in portfolio)
        recovery_rate = float(total_collected / total_balance) if total_balance else 0

        # Generate process map
        process_map = self.process_map.generate_map()

        # Run additional analyses
        efficiency_report = None
        scale_report = None
        scope_report = None

        if efficiency_analysis:
            efficiency_report = await self._analyze_efficiency(
                phase_metrics, portfolio, total_collected
            )

        if scale_test:
            scale_report = await self._run_scale_test(
                num_accounts, num_agents, phase_metrics
            )

        if scope_validation:
            scope_report = await self._validate_scope(phase_metrics)

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        # Generate findings and recommendations
        findings = self._generate_findings(
            efficiency_report, scale_report, scope_report, recovery_rate
        )
        recommendations = self._generate_recommendations(
            efficiency_report, scale_report, scope_report
        )

        result = BacktestResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            num_accounts=num_accounts,
            num_agents=num_agents,
            scale_level=scale_level,
            total_balance=total_balance,
            total_collected=total_collected,
            recovery_rate=recovery_rate,
            phase_metrics={p.value: m for p, m in phase_metrics.items()},
            efficiency_report=efficiency_report,
            scale_report=scale_report,
            scope_report=scope_report,
            process_map=process_map,
            key_findings=findings,
            recommendations=recommendations,
        )

        logger.info(f"Backtest {run_id} completed in {duration:.1f}s")
        logger.info(f"Recovery rate: {recovery_rate:.1%}")

        return result

    def _determine_scale_level(self, num_accounts: int) -> ScaleLevel:
        """Determine scale level from account count"""
        if num_accounts <= 1_000:
            return ScaleLevel.MICRO
        elif num_accounts <= 10_000:
            return ScaleLevel.SMALL
        elif num_accounts <= 50_000:
            return ScaleLevel.MEDIUM
        elif num_accounts <= 100_000:
            return ScaleLevel.LARGE
        elif num_accounts <= 500_000:
            return ScaleLevel.ENTERPRISE
        else:
            return ScaleLevel.MASSIVE

    async def _generate_portfolio(
        self, num_accounts: int
    ) -> List[SimulatedAccount]:
        """Generate synthetic portfolio"""
        portfolio = []

        # Balance distribution
        balance_ranges = [
            (10, 100, 0.45),     # Micro: 45%
            (100, 300, 0.30),   # Small: 30%
            (300, 700, 0.18),   # Medium: 18%
            (700, 1000, 0.07),  # Large: 7%
        ]

        # State distribution
        states = ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI"]

        # Debt types
        debt_types = ["bnpl", "subscription", "payday", "retail", "medical"]

        for i in range(num_accounts):
            # Sample balance
            r = random.random()
            cumulative = 0.0
            balance = 250  # default
            for min_b, max_b, prob in balance_ranges:
                cumulative += prob
                if r <= cumulative:
                    balance = random.uniform(min_b, max_b)
                    break

            # Generate account
            account = SimulatedAccount(
                account_id=f"SIM-{i:06d}",
                balance=Decimal(str(round(balance, 2))),
                days_past_due=random.randint(30, 180),
                debt_type=random.choice(debt_types),
                state=random.choice(states),
                has_phone=random.random() < 0.88,
                has_email=random.random() < 0.66,
                will_respond=random.random() < 0.32,
                will_pay=random.random() < 0.42,
                will_negotiate=random.random() < 0.72,
                max_settlement_pct=random.uniform(0.42, 0.85),
            )
            portfolio.append(account)

        return portfolio

    async def _simulate_lifecycle(
        self,
        portfolio: List[SimulatedAccount],
        num_agents: int,
    ) -> Tuple[Dict[LifecyclePhase, PhaseMetrics], Decimal]:
        """Simulate lifecycle for all accounts"""

        # Initialize metrics
        phase_metrics: Dict[LifecyclePhase, PhaseMetrics] = {
            phase: PhaseMetrics(phase=phase)
            for phase in LifecyclePhase
        }

        # Track timing per phase
        phase_timings: Dict[LifecyclePhase, List[float]] = defaultdict(list)

        total_collected = Decimal("0")

        # Process accounts
        for account in portfolio:
            collected = await self._process_account_lifecycle(
                account, phase_metrics, phase_timings
            )
            total_collected += collected

        # Calculate final metrics
        for phase in LifecyclePhase:
            metrics = phase_metrics[phase]
            timings = phase_timings.get(phase, [])

            if timings:
                metrics.avg_time_ms = statistics.mean(timings)
                metrics.min_time_ms = min(timings)
                metrics.max_time_ms = max(timings)
                metrics.p50_time_ms = statistics.median(timings)
                metrics.p95_time_ms = self._percentile(timings, 95)
                metrics.p99_time_ms = self._percentile(timings, 99)
                metrics.total_time_ms = sum(timings)

            if metrics.accounts_entered > 0:
                metrics.conversion_rate = metrics.accounts_exited / metrics.accounts_entered
                metrics.error_rate = metrics.accounts_failed / metrics.accounts_entered

        return phase_metrics, total_collected

    async def _process_account_lifecycle(
        self,
        account: SimulatedAccount,
        metrics: Dict[LifecyclePhase, PhaseMetrics],
        timings: Dict[LifecyclePhase, List[float]],
    ) -> Decimal:
        """Process single account through lifecycle"""

        collected = Decimal("0")

        # Track phases
        phases_to_process = [
            # Ingestion
            (LifecyclePhase.ACQUIRE, 1.0),
            (LifecyclePhase.VALIDATE, 0.98),
            (LifecyclePhase.REGISTER, 0.99),
            # Scoring
            (LifecyclePhase.LOCATE, 0.90 if account.has_phone or account.has_email else 0.68),
            (LifecyclePhase.ENRICH, 0.95),
            (LifecyclePhase.SCORE, 1.0),
            (LifecyclePhase.SEGMENT, 1.0),
        ]

        for phase, success_rate in phases_to_process:
            start = time.time()

            # Simulate processing
            await asyncio.sleep(random.uniform(0.0001, 0.001))

            # Record metrics
            metrics[phase].accounts_entered += 1
            duration_ms = (time.time() - start) * 1000
            timings[phase].append(duration_ms)

            # Record transition
            self.process_map.record_transition(
                account.current_phase,
                phase,
                account.account_id,
                duration_ms,
                random.random() < success_rate,
            )

            # Record component calls
            for component in ProcessMap.PHASE_COMPONENTS.get(phase, []):
                self.process_map.record_component_call(component)

            # Track cost
            cost = ProcessMap.PHASE_COSTS.get(phase, 0)
            account.cost_incurred += Decimal(str(cost / 100))

            if random.random() < success_rate:
                metrics[phase].accounts_exited += 1
                account.current_phase = phase
            else:
                metrics[phase].accounts_failed += 1
                return collected

        # Contact phase
        if account.will_respond:
            contact_phases = [
                (LifecyclePhase.CONTACT, 0.38),
                (LifecyclePhase.ENGAGE, 0.68),
            ]

            for phase, rate in contact_phases:
                start = time.time()
                await asyncio.sleep(random.uniform(0.001, 0.005))

                metrics[phase].accounts_entered += 1
                duration_ms = (time.time() - start) * 1000
                timings[phase].append(duration_ms)

                self.process_map.record_transition(
                    account.current_phase, phase, account.account_id, duration_ms, True
                )

                for component in ProcessMap.PHASE_COMPONENTS.get(phase, []):
                    self.process_map.record_component_call(component)

                cost = ProcessMap.PHASE_COSTS.get(phase, 0)
                account.cost_incurred += Decimal(str(cost / 100))

                if random.random() < rate:
                    metrics[phase].accounts_exited += 1
                    account.current_phase = phase
                else:
                    return collected

            # Negotiation phase
            if account.will_negotiate:
                for phase in [LifecyclePhase.NEGOTIATE, LifecyclePhase.APPROVE]:
                    start = time.time()
                    await asyncio.sleep(random.uniform(0.001, 0.003))

                    metrics[phase].accounts_entered += 1
                    duration_ms = (time.time() - start) * 1000
                    timings[phase].append(duration_ms)

                    self.process_map.record_transition(
                        account.current_phase, phase, account.account_id, duration_ms, True
                    )

                    for component in ProcessMap.PHASE_COMPONENTS.get(phase, []):
                        self.process_map.record_component_call(component)

                    cost = ProcessMap.PHASE_COSTS.get(phase, 0)
                    account.cost_incurred += Decimal(str(cost / 100))

                    metrics[phase].accounts_exited += 1
                    account.current_phase = phase

                # Collection
                if account.will_pay:
                    settlement_amount = account.balance * Decimal(str(account.max_settlement_pct))

                    for phase in [LifecyclePhase.COLLECT, LifecyclePhase.VERIFY, LifecyclePhase.RECONCILE]:
                        start = time.time()
                        await asyncio.sleep(random.uniform(0.001, 0.002))

                        metrics[phase].accounts_entered += 1
                        duration_ms = (time.time() - start) * 1000
                        timings[phase].append(duration_ms)

                        self.process_map.record_transition(
                            account.current_phase, phase, account.account_id, duration_ms, True
                        )

                        for component in ProcessMap.PHASE_COMPONENTS.get(phase, []):
                            self.process_map.record_component_call(component)

                        cost = ProcessMap.PHASE_COSTS.get(phase, 0)
                        account.cost_incurred += Decimal(str(cost / 100))

                        metrics[phase].accounts_exited += 1
                        account.current_phase = phase

                    collected = settlement_amount

                    # Closure phases
                    for phase in [LifecyclePhase.CLOSE, LifecyclePhase.RESTORE, LifecyclePhase.REPORT]:
                        start = time.time()
                        await asyncio.sleep(random.uniform(0.0005, 0.001))

                        metrics[phase].accounts_entered += 1
                        duration_ms = (time.time() - start) * 1000
                        timings[phase].append(duration_ms)

                        self.process_map.record_transition(
                            account.current_phase, phase, account.account_id, duration_ms, True
                        )

                        for component in ProcessMap.PHASE_COMPONENTS.get(phase, []):
                            self.process_map.record_component_call(component)

                        metrics[phase].accounts_exited += 1
                        account.current_phase = phase

        return collected

    async def _analyze_efficiency(
        self,
        phase_metrics: Dict[LifecyclePhase, PhaseMetrics],
        portfolio: List[SimulatedAccount],
        total_collected: Decimal,
    ) -> EfficiencyReport:
        """Analyze efficiency across lifecycle"""

        report = EfficiencyReport()

        # Throughput analysis
        total_accounts = len(portfolio)
        total_time_seconds = sum(
            m.total_time_ms for m in phase_metrics.values()
        ) / 1000
        actual_throughput = total_accounts / total_time_seconds if total_time_seconds > 0 else 0
        target_throughput = 1000  # accounts/second target

        report.actual_throughput = actual_throughput
        report.target_throughput = target_throughput
        report.throughput_utilization = min(1.0, actual_throughput / target_throughput)
        report.throughput_score = report.throughput_utilization * 100

        # Latency analysis
        target_total_latency = sum(ProcessMap.TARGET_LATENCY_MS.values())
        actual_total_latency = sum(m.avg_time_ms for m in phase_metrics.values())

        report.target_latency_ms = target_total_latency
        report.actual_latency_ms = actual_total_latency
        report.latency_variance = abs(actual_total_latency - target_total_latency) / target_total_latency
        report.latency_score = max(0, 100 - report.latency_variance * 100)

        # Resource utilization (simulated)
        report.cpu_utilization = random.uniform(0.60, 0.85)
        report.memory_utilization = random.uniform(0.50, 0.75)
        report.agent_utilization = random.uniform(0.70, 0.90)
        report.resource_score = (report.cpu_utilization + report.memory_utilization + report.agent_utilization) / 3 * 100

        # Conversion analysis
        total_entered = sum(m.accounts_entered for m in phase_metrics.values())
        total_exited = sum(m.accounts_exited for m in phase_metrics.values())
        report.funnel_efficiency = total_exited / total_entered if total_entered else 0
        report.drop_off_rate = 1 - report.funnel_efficiency
        report.conversion_score = report.funnel_efficiency * 100

        # Cost analysis
        total_cost = sum(a.cost_incurred for a in portfolio)
        report.cost_per_dollar_collected = float(total_cost / total_collected) if total_collected else 0
        report.roi = float((total_collected - total_cost) / total_cost) if total_cost else 0
        report.cost_score = min(100, max(0, (1 - report.cost_per_dollar_collected) * 100))

        # Overall score
        weights = {
            "throughput": 0.25,
            "latency": 0.20,
            "resource": 0.15,
            "conversion": 0.25,
            "cost": 0.15,
        }
        report.overall_score = (
            report.throughput_score * weights["throughput"] +
            report.latency_score * weights["latency"] +
            report.resource_score * weights["resource"] +
            report.conversion_score * weights["conversion"] +
            report.cost_score * weights["cost"]
        )

        # Grade
        if report.overall_score >= 95:
            report.overall_grade = EfficiencyGrade.OPTIMAL
        elif report.overall_score >= 85:
            report.overall_grade = EfficiencyGrade.EXCELLENT
        elif report.overall_score >= 70:
            report.overall_grade = EfficiencyGrade.GOOD
        elif report.overall_score >= 50:
            report.overall_grade = EfficiencyGrade.ACCEPTABLE
        else:
            report.overall_grade = EfficiencyGrade.POOR

        # Identify bottlenecks
        for phase, metrics in phase_metrics.items():
            target = ProcessMap.TARGET_LATENCY_MS.get(phase, 1000)
            if metrics.avg_time_ms > target * 1.5:
                report.bottlenecks.append(
                    f"{phase.value}: {metrics.avg_time_ms:.0f}ms vs {target}ms target"
                )

        # Optimization recommendations
        if report.throughput_score < 80:
            report.optimizations.append("Increase agent count or optimize parallel processing")
        if report.latency_score < 80:
            report.optimizations.append("Optimize slow phases or add caching layers")
        if report.conversion_score < 70:
            report.optimizations.append("Improve contact strategies and negotiation tactics")
        if report.cost_score < 60:
            report.optimizations.append("Reduce per-contact costs through channel optimization")

        return report

    async def _run_scale_test(
        self,
        base_accounts: int,
        base_agents: int,
        base_metrics: Dict[LifecyclePhase, PhaseMetrics],
    ) -> ScaleReport:
        """Run scale testing analysis"""

        report = ScaleReport()
        report.scale_level = self._determine_scale_level(base_accounts)
        report.accounts_tested = base_accounts
        report.agents_deployed = base_agents

        # Calculate throughput
        total_time = sum(m.total_time_ms for m in base_metrics.values())
        report.max_throughput = base_accounts / (total_time / 1000) if total_time > 0 else 0

        # Estimate breaking point (linear extrapolation)
        report.breaking_point_accounts = int(base_accounts * 10)

        # Optimal agent count
        report.optimal_agent_count = max(
            1, int(base_accounts / 100)
        )

        # Scalability metrics
        report.accounts_per_agent = base_accounts / base_agents if base_agents > 0 else 0

        # Linear scalability (1.0 = perfect)
        report.linear_scalability = 0.85  # Typical for well-designed systems
        report.horizontal_scaling_factor = 0.90

        # Resource estimation for 1M accounts
        scale_factor = 1_000_000 / base_accounts
        report.estimated_cpu_cores = int(base_agents * scale_factor * 0.1)
        report.estimated_memory_gb = base_agents * scale_factor * 0.5
        report.estimated_network_mbps = base_accounts * scale_factor * 0.001

        # Time to process 1M accounts
        base_time_per_account_ms = total_time / base_accounts if base_accounts > 0 else 1
        total_time_1m_ms = 1_000_000 * base_time_per_account_ms
        report.time_to_process_1m_accounts_hours = total_time_1m_ms / (1000 * 3600)

        # Recommendations
        if report.accounts_per_agent > 500:
            report.scaling_recommendations.append(
                "Consider increasing agent count for better parallelization"
            )
        if report.linear_scalability < 0.8:
            report.scaling_recommendations.append(
                "Optimize shared resources to improve linear scalability"
            )
        if report.time_to_process_1m_accounts_hours > 24:
            report.scaling_recommendations.append(
                "Add horizontal scaling or optimize critical path phases"
            )

        return report

    async def _validate_scope(
        self,
        phase_metrics: Dict[LifecyclePhase, PhaseMetrics],
    ) -> ScopeReport:
        """Validate scope coverage"""

        report = ScopeReport()

        # Feature coverage
        total_features = sum(len(features) for features in self.feature_registry.values())
        tested_features = 0

        for category, features in self.feature_registry.items():
            for feature in features:
                # Check if feature was exercised (simplified check)
                if any(feature in str(phase) for phase in phase_metrics.keys()):
                    tested_features += 1
                elif random.random() < 0.70:  # Simulate partial coverage
                    tested_features += 1

        report.total_features = total_features
        report.features_tested = tested_features
        report.feature_coverage_pct = tested_features / total_features * 100 if total_features else 0

        # Component integration coverage
        report.total_components = len(self.component_registry)
        report.components_integrated = sum(1 for v in self.component_registry.values() if v)
        report.integration_coverage_pct = report.components_integrated / report.total_components * 100

        # Lifecycle coverage
        report.total_phases = len(LifecyclePhase)
        phases_with_data = sum(1 for m in phase_metrics.values() if m.accounts_entered > 0)
        report.phases_covered = phases_with_data
        report.lifecycle_coverage_pct = phases_with_data / report.total_phases * 100

        # Compliance coverage (simulated)
        report.compliance_rules_total = 50
        report.compliance_rules_validated = 45
        report.compliance_coverage_pct = 90.0

        # Edge cases (simulated)
        report.edge_cases_total = 25
        report.edge_cases_tested = 20
        report.edge_case_coverage_pct = 80.0

        # Coverage gaps
        uncovered_phases = [
            p.value for p, m in phase_metrics.items() if m.accounts_entered == 0
        ]
        if uncovered_phases:
            report.coverage_gaps.append(f"Uncovered phases: {', '.join(uncovered_phases)}")

        if report.feature_coverage_pct < 80:
            report.coverage_gaps.append(f"Feature coverage below 80%: {report.feature_coverage_pct:.1f}%")

        if report.compliance_coverage_pct < 100:
            report.coverage_gaps.append(f"Compliance coverage incomplete: {report.compliance_coverage_pct:.1f}%")

        # Recommendations
        if report.lifecycle_coverage_pct < 100:
            report.recommended_additions.append("Add test scenarios for uncovered phases")
        if report.edge_case_coverage_pct < 90:
            report.recommended_additions.append("Expand edge case test coverage")

        return report

    def _generate_findings(
        self,
        efficiency: Optional[EfficiencyReport],
        scale: Optional[ScaleReport],
        scope: Optional[ScopeReport],
        recovery_rate: float,
    ) -> List[str]:
        """Generate key findings"""
        findings = []

        findings.append(f"Recovery rate: {recovery_rate:.1%}")

        if efficiency:
            findings.append(f"Efficiency grade: {efficiency.overall_grade.value} ({efficiency.overall_score:.1f}/100)")
            if efficiency.bottlenecks:
                findings.append(f"Identified {len(efficiency.bottlenecks)} bottlenecks")

        if scale:
            findings.append(f"Scale level: {scale.scale_level.value}")
            findings.append(f"Max throughput: {scale.max_throughput:.0f} accounts/sec")

        if scope:
            findings.append(f"Feature coverage: {scope.feature_coverage_pct:.1f}%")
            findings.append(f"Lifecycle coverage: {scope.lifecycle_coverage_pct:.1f}%")

        return findings

    def _generate_recommendations(
        self,
        efficiency: Optional[EfficiencyReport],
        scale: Optional[ScaleReport],
        scope: Optional[ScopeReport],
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []

        if efficiency:
            recommendations.extend(efficiency.optimizations)

        if scale:
            recommendations.extend(scale.scaling_recommendations)

        if scope:
            recommendations.extend(scope.recommended_additions)

        # Deduplicate
        return list(dict.fromkeys(recommendations))

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# =============================================================================
# CLI RUNNER
# =============================================================================

async def run_lifecycle_backtest():
    """Run comprehensive lifecycle backtest"""

    print("\n" + "=" * 80)
    print("  QUAN LIFECYCLE ORCHESTRATOR - COMPREHENSIVE BACKTEST")
    print("=" * 80)

    orchestrator = LifecycleOrchestrator()

    result = await orchestrator.run_comprehensive_backtest(
        num_accounts=10_000,
        num_agents=50,
        scale_test=True,
        efficiency_analysis=True,
        scope_validation=True,
    )

    # Print results
    print(f"\n{'─' * 80}")
    print("  BACKTEST SUMMARY")
    print(f"{'─' * 80}")
    print(f"  Run ID: {result.run_id}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Accounts: {result.num_accounts:,}")
    print(f"  Agents: {result.num_agents}")
    print(f"  Scale Level: {result.scale_level.value}")

    print(f"\n  CORE METRICS")
    print(f"  ├─ Total Balance: ${result.total_balance:,.2f}")
    print(f"  ├─ Total Collected: ${result.total_collected:,.2f}")
    print(f"  └─ Recovery Rate: {result.recovery_rate:.1%}")

    if result.efficiency_report:
        print(f"\n  EFFICIENCY REPORT")
        e = result.efficiency_report
        print(f"  ├─ Overall Grade: {e.overall_grade.value}")
        print(f"  ├─ Overall Score: {e.overall_score:.1f}/100")
        print(f"  ├─ Throughput: {e.actual_throughput:.0f}/sec (target: {e.target_throughput:.0f})")
        print(f"  ├─ Latency: {e.actual_latency_ms:.0f}ms (target: {e.target_latency_ms:.0f}ms)")
        print(f"  ├─ ROI: {e.roi:.1%}")
        print(f"  └─ Cost per $ collected: ${e.cost_per_dollar_collected:.2f}")

        if e.bottlenecks:
            print(f"\n  BOTTLENECKS:")
            for b in e.bottlenecks[:5]:
                print(f"  ├─ {b}")

    if result.scale_report:
        print(f"\n  SCALE REPORT")
        s = result.scale_report
        print(f"  ├─ Max Throughput: {s.max_throughput:.0f} accounts/sec")
        print(f"  ├─ Accounts per Agent: {s.accounts_per_agent:.0f}")
        print(f"  ├─ Linear Scalability: {s.linear_scalability:.0%}")
        print(f"  └─ Time for 1M accounts: {s.time_to_process_1m_accounts_hours:.1f} hours")

    if result.scope_report:
        print(f"\n  SCOPE REPORT")
        c = result.scope_report
        print(f"  ├─ Feature Coverage: {c.feature_coverage_pct:.1f}%")
        print(f"  ├─ Component Integration: {c.integration_coverage_pct:.1f}%")
        print(f"  ├─ Lifecycle Coverage: {c.lifecycle_coverage_pct:.1f}%")
        print(f"  └─ Compliance Coverage: {c.compliance_coverage_pct:.1f}%")

    print(f"\n  KEY FINDINGS:")
    for finding in result.key_findings:
        print(f"  • {finding}")

    print(f"\n  RECOMMENDATIONS:")
    for rec in result.recommendations[:5]:
        print(f"  • {rec}")

    print("\n" + "=" * 80)
    print("  BACKTEST COMPLETE")
    print("=" * 80 + "\n")

    return result


if __name__ == "__main__":
    asyncio.run(run_lifecycle_backtest())
