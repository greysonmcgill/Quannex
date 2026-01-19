"""
QUAN Unified Integration Layer

The connective tissue binding all system components into a cohesive,
frictionless collection machine. This layer ensures:

1. Seamless data flow between all modules
2. Optimal routing of accounts through the pipeline
3. Real-time feedback loops for continuous optimization
4. Minimal friction at every handoff point
5. Maximum collection efficiency through intelligent orchestration

Architecture: Event-driven with async processing for scale
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable
import asyncio
import hashlib
import json
from collections import defaultdict


class SystemModule(Enum):
    """All QUAN system modules"""
    INGESTION = "ingestion"
    SHADOW_BUREAU = "shadow_bureau"
    EMPATHY_ENGINE = "empathy_engine"
    LIVE_LEDGER = "live_ledger"
    REHABILITATION = "rehabilitation"
    COMPLIANCE = "compliance"
    RISK = "risk"
    SETTLEMENT = "settlement"
    PAYMENT = "payment"
    TOKENIZATION = "tokenization"
    REPORTING = "reporting"
    ANALYTICS = "analytics"
    ORCHESTRATION = "orchestration"


class EventType(Enum):
    """System event types for pub/sub"""
    # Debt lifecycle events
    DEBT_INGESTED = "debt.ingested"
    DEBT_ENRICHED = "debt.enriched"
    DEBT_SCORED = "debt.scored"
    DEBT_ASSIGNED = "debt.assigned"

    # Contact events
    CONTACT_SCHEDULED = "contact.scheduled"
    CONTACT_ATTEMPTED = "contact.attempted"
    CONTACT_COMPLETED = "contact.completed"
    RESPONSE_RECEIVED = "response.received"

    # Negotiation events
    NEGOTIATION_STARTED = "negotiation.started"
    OFFER_MADE = "offer.made"
    OFFER_ACCEPTED = "offer.accepted"
    OFFER_REJECTED = "offer.rejected"
    COUNTER_OFFER = "counter.offer"

    # Payment events
    PAYMENT_PROMISED = "payment.promised"
    PAYMENT_SCHEDULED = "payment.scheduled"
    PAYMENT_ATTEMPTED = "payment.attempted"
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"

    # Resolution events
    DEBT_RESOLVED = "debt.resolved"
    DEBT_SETTLED = "debt.settled"
    CERTIFICATE_ISSUED = "certificate.issued"

    # Risk events
    RISK_ESCALATED = "risk.escalated"
    RISK_MITIGATED = "risk.mitigated"
    COMPLIANCE_VIOLATION = "compliance.violation"

    # Tokenization events
    DEBT_TOKENIZED = "debt.tokenized"
    POOL_CREATED = "pool.created"
    TRANCHE_SOLD = "tranche.sold"

    # System events
    OPTIMIZATION_TRIGGERED = "optimization.triggered"
    FRICTION_DETECTED = "friction.detected"
    FEEDBACK_LOOP = "feedback.loop"


@dataclass
class SystemEvent:
    """Event for inter-module communication"""
    event_id: str
    event_type: EventType
    source_module: SystemModule
    target_module: SystemModule | None
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str | None = None
    causation_id: str | None = None
    priority: int = 5  # 1-10, lower is higher priority


@dataclass
class FrictionPoint:
    """Identified friction point in the system"""
    friction_id: str
    location: str  # module.function or module1 -> module2
    friction_type: str
    severity: float  # 0-1
    impact_accounts: int
    impact_revenue: float
    root_cause: str
    recommendation: str
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class IntegrationMetrics:
    """Real-time integration health metrics"""
    total_events_processed: int = 0
    events_per_second: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    friction_score: float = 0.0  # 0-100, lower is better
    module_health: dict[str, float] = field(default_factory=dict)
    bottlenecks: list[str] = field(default_factory=list)
    throughput_by_stage: dict[str, float] = field(default_factory=dict)


class EventBus:
    """
    Central event bus for pub/sub communication between modules

    Enables loose coupling while maintaining data consistency
    """

    def __init__(self):
        self.subscribers: dict[EventType, list[Callable]] = defaultdict(list)
        self.event_history: list[SystemEvent] = []
        self.pending_events: asyncio.Queue = asyncio.Queue()
        self.metrics = IntegrationMetrics()

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to an event type"""
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """Unsubscribe from an event type"""
        if handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)

    async def publish(self, event: SystemEvent) -> None:
        """Publish an event to all subscribers"""
        await self.pending_events.put(event)
        self.event_history.append(event)
        self.metrics.total_events_processed += 1

    async def process_events(self) -> None:
        """Process pending events (run in background)"""
        while True:
            event = await self.pending_events.get()
            start_time = datetime.now()

            for handler in self.subscribers.get(event.event_type, []):
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    self.metrics.error_rate += 0.001
                    print(f"Event handler error: {e}")

            latency = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics.avg_latency_ms = (
                self.metrics.avg_latency_ms * 0.9 + latency * 0.1
            )

            self.pending_events.task_done()


class ModuleConnector:
    """
    Connects and coordinates between specific modules

    Each connector handles the translation and routing between two modules,
    minimizing friction at the interface.
    """

    def __init__(
        self,
        source: SystemModule,
        target: SystemModule,
        event_bus: EventBus
    ):
        self.source = source
        self.target = target
        self.event_bus = event_bus
        self.transform_rules: list[Callable] = []
        self.validation_rules: list[Callable] = []
        self.metrics = {
            "messages_passed": 0,
            "transform_errors": 0,
            "validation_failures": 0,
            "avg_latency_ms": 0.0
        }

    def add_transform(self, transform_fn: Callable) -> None:
        """Add data transformation rule"""
        self.transform_rules.append(transform_fn)

    def add_validation(self, validation_fn: Callable) -> None:
        """Add validation rule"""
        self.validation_rules.append(validation_fn)

    async def pass_through(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Pass data from source to target with transforms and validation"""
        start = datetime.now()

        # Apply transforms
        transformed = data.copy()
        for transform in self.transform_rules:
            try:
                transformed = transform(transformed)
            except Exception as e:
                self.metrics["transform_errors"] += 1
                return None

        # Validate
        for validate in self.validation_rules:
            if not validate(transformed):
                self.metrics["validation_failures"] += 1
                return None

        self.metrics["messages_passed"] += 1
        latency = (datetime.now() - start).total_seconds() * 1000
        self.metrics["avg_latency_ms"] = (
            self.metrics["avg_latency_ms"] * 0.9 + latency * 0.1
        )

        return transformed


class FrictionAnalyzer:
    """
    Analyzes system for friction points and recommends optimizations

    Friction = anything that slows down or prevents collection:
    - Handoff delays between modules
    - Data transformation overhead
    - Compliance checks that block valid actions
    - Suboptimal routing decisions
    - Payment failures
    - Consumer response gaps
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.friction_points: list[FrictionPoint] = []
        self.stage_timings: dict[str, list[float]] = defaultdict(list)
        self.drop_off_rates: dict[str, float] = {}
        self.conversion_rates: dict[str, float] = {}

    def record_stage_timing(self, stage: str, duration_ms: float) -> None:
        """Record timing for a pipeline stage"""
        self.stage_timings[stage].append(duration_ms)

        # Check for timing anomalies
        if len(self.stage_timings[stage]) > 100:
            avg = sum(self.stage_timings[stage][-100:]) / 100
            if duration_ms > avg * 3:  # 3x slower than average
                self._create_friction_point(
                    location=stage,
                    friction_type="latency_spike",
                    severity=min(1.0, duration_ms / (avg * 10)),
                    root_cause=f"Stage {stage} took {duration_ms:.0f}ms vs {avg:.0f}ms average",
                    recommendation=f"Investigate {stage} for bottlenecks"
                )

    def record_conversion(
        self,
        from_stage: str,
        to_stage: str,
        converted: int,
        total: int
    ) -> None:
        """Record conversion between stages"""
        key = f"{from_stage}_to_{to_stage}"
        rate = converted / total if total > 0 else 0
        self.conversion_rates[key] = rate

        # Historical comparison
        if rate < 0.5:  # Less than 50% conversion
            self._create_friction_point(
                location=key,
                friction_type="low_conversion",
                severity=1.0 - rate,
                root_cause=f"Only {rate:.1%} converting from {from_stage} to {to_stage}",
                recommendation=f"Analyze why accounts stall at {from_stage}"
            )

    def record_drop_off(self, stage: str, dropped: int, reason: str) -> None:
        """Record accounts dropping off at a stage"""
        if stage not in self.drop_off_rates:
            self.drop_off_rates[stage] = 0
        self.drop_off_rates[stage] += dropped

        if dropped > 100:  # Significant drop-off
            self._create_friction_point(
                location=stage,
                friction_type="drop_off",
                severity=min(1.0, dropped / 1000),
                root_cause=reason,
                recommendation=f"Reduce drop-offs at {stage}"
            )

    def analyze_pipeline(self, pipeline_data: dict[str, Any]) -> dict[str, Any]:
        """Full pipeline friction analysis"""
        analysis = {
            "total_friction_score": 0.0,
            "critical_points": [],
            "optimization_opportunities": [],
            "estimated_recovery_impact": 0.0
        }

        # Calculate aggregate friction
        if self.friction_points:
            analysis["total_friction_score"] = sum(
                fp.severity for fp in self.friction_points
            ) / len(self.friction_points) * 100

            # Critical points (severity > 0.7)
            analysis["critical_points"] = [
                {
                    "location": fp.location,
                    "type": fp.friction_type,
                    "severity": fp.severity,
                    "recommendation": fp.recommendation
                }
                for fp in self.friction_points
                if fp.severity > 0.7 and not fp.resolved
            ]

        # Optimization opportunities
        for stage, timings in self.stage_timings.items():
            if len(timings) > 50:
                avg = sum(timings) / len(timings)
                p95 = sorted(timings)[int(len(timings) * 0.95)]
                if p95 > avg * 2:
                    analysis["optimization_opportunities"].append({
                        "stage": stage,
                        "current_avg_ms": avg,
                        "p95_ms": p95,
                        "potential_improvement": f"{(p95 - avg) / avg:.0%}"
                    })

        return analysis

    def _create_friction_point(
        self,
        location: str,
        friction_type: str,
        severity: float,
        root_cause: str,
        recommendation: str
    ) -> FrictionPoint:
        """Create and register a friction point"""
        fp = FrictionPoint(
            friction_id=hashlib.sha256(
                f"{location}{friction_type}{datetime.now()}".encode()
            ).hexdigest()[:12],
            location=location,
            friction_type=friction_type,
            severity=severity,
            impact_accounts=0,
            impact_revenue=0.0,
            root_cause=root_cause,
            recommendation=recommendation
        )
        self.friction_points.append(fp)
        return fp


class UnifiedIntegrationLayer:
    """
    The master integration layer coordinating all QUAN modules

    Responsibilities:
    1. Route data between modules with minimal latency
    2. Maintain data consistency across the system
    3. Monitor and minimize friction
    4. Optimize for maximum collection efficiency
    5. Provide real-time visibility into system health
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.friction_analyzer = FrictionAnalyzer(self.event_bus)
        self.connectors: dict[str, ModuleConnector] = {}
        self.module_states: dict[SystemModule, dict[str, Any]] = {}
        self.global_metrics = IntegrationMetrics()

        # Initialize connectors for critical paths
        self._setup_connectors()

        # Initialize event handlers
        self._setup_event_handlers()

    def _setup_connectors(self) -> None:
        """Setup module connectors for critical integration paths"""

        # Ingestion -> Shadow Bureau
        self.connectors["ingestion_to_shadow"] = ModuleConnector(
            SystemModule.INGESTION,
            SystemModule.SHADOW_BUREAU,
            self.event_bus
        )
        self.connectors["ingestion_to_shadow"].add_transform(
            lambda d: {**d, "shadow_enriched": True, "enriched_at": datetime.now().isoformat()}
        )

        # Shadow Bureau -> Empathy Engine
        self.connectors["shadow_to_empathy"] = ModuleConnector(
            SystemModule.SHADOW_BUREAU,
            SystemModule.EMPATHY_ENGINE,
            self.event_bus
        )
        self.connectors["shadow_to_empathy"].add_transform(
            lambda d: {
                **d,
                "contact_strategy": self._determine_contact_strategy(d),
                "persona_recommendation": self._recommend_persona(d)
            }
        )

        # Empathy Engine -> Settlement
        self.connectors["empathy_to_settlement"] = ModuleConnector(
            SystemModule.EMPATHY_ENGINE,
            SystemModule.SETTLEMENT,
            self.event_bus
        )

        # Settlement -> Payment
        self.connectors["settlement_to_payment"] = ModuleConnector(
            SystemModule.SETTLEMENT,
            SystemModule.PAYMENT,
            self.event_bus
        )
        self.connectors["settlement_to_payment"].add_validation(
            lambda d: d.get("settlement_amount", 0) > 0
        )

        # Payment -> Rehabilitation
        self.connectors["payment_to_rehab"] = ModuleConnector(
            SystemModule.PAYMENT,
            SystemModule.REHABILITATION,
            self.event_bus
        )

        # Resolution -> Tokenization
        self.connectors["resolution_to_token"] = ModuleConnector(
            SystemModule.REHABILITATION,
            SystemModule.TOKENIZATION,
            self.event_bus
        )

    def _setup_event_handlers(self) -> None:
        """Setup handlers for system events"""

        # Debt lifecycle handlers
        self.event_bus.subscribe(EventType.DEBT_INGESTED, self._handle_debt_ingested)
        self.event_bus.subscribe(EventType.DEBT_SCORED, self._handle_debt_scored)
        self.event_bus.subscribe(EventType.CONTACT_COMPLETED, self._handle_contact_completed)
        self.event_bus.subscribe(EventType.PAYMENT_SUCCESS, self._handle_payment_success)
        self.event_bus.subscribe(EventType.PAYMENT_FAILED, self._handle_payment_failed)
        self.event_bus.subscribe(EventType.DEBT_RESOLVED, self._handle_debt_resolved)

        # Friction handlers
        self.event_bus.subscribe(EventType.FRICTION_DETECTED, self._handle_friction)

    async def _handle_debt_ingested(self, event: SystemEvent) -> None:
        """Handle new debt ingestion"""
        start = datetime.now()

        # Enrich through Shadow Bureau
        enriched = await self.connectors["ingestion_to_shadow"].pass_through(
            event.payload
        )

        if enriched:
            # Publish enriched event
            await self.event_bus.publish(SystemEvent(
                event_id=hashlib.sha256(f"enriched_{datetime.now()}".encode()).hexdigest()[:16],
                event_type=EventType.DEBT_ENRICHED,
                source_module=SystemModule.SHADOW_BUREAU,
                target_module=SystemModule.EMPATHY_ENGINE,
                payload=enriched,
                correlation_id=event.correlation_id,
                causation_id=event.event_id
            ))

        latency = (datetime.now() - start).total_seconds() * 1000
        self.friction_analyzer.record_stage_timing("ingestion_to_enrichment", latency)

    async def _handle_debt_scored(self, event: SystemEvent) -> None:
        """Handle scored debt - route to appropriate workflow"""
        shadow_score = event.payload.get("shadow_score", 500)
        balance = event.payload.get("balance", 0)

        # Determine optimal workflow based on score and balance
        if shadow_score >= 700:
            workflow = "high_probability_fast_track"
        elif shadow_score >= 500:
            workflow = "standard_engagement"
        elif balance < 50:
            workflow = "micro_debt_automated"
        else:
            workflow = "rehabilitation_focused"

        event.payload["assigned_workflow"] = workflow

        await self.event_bus.publish(SystemEvent(
            event_id=hashlib.sha256(f"assigned_{datetime.now()}".encode()).hexdigest()[:16],
            event_type=EventType.DEBT_ASSIGNED,
            source_module=SystemModule.ORCHESTRATION,
            target_module=SystemModule.EMPATHY_ENGINE,
            payload=event.payload,
            correlation_id=event.correlation_id
        ))

    async def _handle_contact_completed(self, event: SystemEvent) -> None:
        """Handle completed contact - update all relevant modules"""
        # Update Live Ledger
        self.module_states.setdefault(SystemModule.LIVE_LEDGER, {})
        consumer_id = event.payload.get("consumer_id")
        if consumer_id:
            self.module_states[SystemModule.LIVE_LEDGER][consumer_id] = {
                "last_contact": datetime.now().isoformat(),
                "contact_result": event.payload.get("result"),
                "sentiment": event.payload.get("sentiment")
            }

        # Check for negotiation opportunity
        if event.payload.get("result") == "engaged":
            await self.event_bus.publish(SystemEvent(
                event_id=hashlib.sha256(f"negotiate_{datetime.now()}".encode()).hexdigest()[:16],
                event_type=EventType.NEGOTIATION_STARTED,
                source_module=SystemModule.EMPATHY_ENGINE,
                target_module=SystemModule.SETTLEMENT,
                payload=event.payload,
                correlation_id=event.correlation_id
            ))

    async def _handle_payment_success(self, event: SystemEvent) -> None:
        """Handle successful payment - trigger downstream updates"""
        # Update rehabilitation status
        consumer_id = event.payload.get("consumer_id")
        amount = event.payload.get("amount", 0)

        rehab_update = await self.connectors["payment_to_rehab"].pass_through({
            "consumer_id": consumer_id,
            "payment_amount": amount,
            "payment_date": datetime.now().isoformat(),
            "on_time": event.payload.get("on_time", True)
        })

        # Check if debt is fully resolved
        remaining = event.payload.get("remaining_balance", 0)
        if remaining <= 0:
            await self.event_bus.publish(SystemEvent(
                event_id=hashlib.sha256(f"resolved_{datetime.now()}".encode()).hexdigest()[:16],
                event_type=EventType.DEBT_RESOLVED,
                source_module=SystemModule.PAYMENT,
                target_module=SystemModule.REHABILITATION,
                payload={**event.payload, "resolution_type": "paid"},
                correlation_id=event.correlation_id
            ))

        # Record conversion
        self.friction_analyzer.record_conversion(
            "payment_attempt", "payment_success", 1, 1
        )

    async def _handle_payment_failed(self, event: SystemEvent) -> None:
        """Handle failed payment - trigger recovery workflow"""
        failure_reason = event.payload.get("failure_reason", "unknown")

        # Determine recovery action
        if failure_reason in ["insufficient_funds", "nsf"]:
            # Reschedule for next payday
            recovery_action = "reschedule_payday"
        elif failure_reason in ["card_declined", "expired"]:
            # Request updated payment method
            recovery_action = "request_update"
        else:
            # Fall back to re-engagement
            recovery_action = "re_engage"

        event.payload["recovery_action"] = recovery_action

        # Record friction
        self.friction_analyzer.record_drop_off(
            "payment",
            1,
            f"Payment failed: {failure_reason}"
        )

        # Publish recovery event
        await self.event_bus.publish(SystemEvent(
            event_id=hashlib.sha256(f"recover_{datetime.now()}".encode()).hexdigest()[:16],
            event_type=EventType.CONTACT_SCHEDULED,
            source_module=SystemModule.PAYMENT,
            target_module=SystemModule.EMPATHY_ENGINE,
            payload=event.payload,
            correlation_id=event.correlation_id
        ))

    async def _handle_debt_resolved(self, event: SystemEvent) -> None:
        """Handle debt resolution - issue certificate and update systems"""
        consumer_id = event.payload.get("consumer_id")

        # Issue restoration certificate
        certificate = {
            "certificate_id": hashlib.sha256(
                f"{consumer_id}{datetime.now()}".encode()
            ).hexdigest()[:24],
            "consumer_id": consumer_id,
            "resolution_date": datetime.now().isoformat(),
            "resolution_type": event.payload.get("resolution_type"),
            "amount_resolved": event.payload.get("amount", 0)
        }

        await self.event_bus.publish(SystemEvent(
            event_id=hashlib.sha256(f"cert_{datetime.now()}".encode()).hexdigest()[:16],
            event_type=EventType.CERTIFICATE_ISSUED,
            source_module=SystemModule.REHABILITATION,
            target_module=SystemModule.REPORTING,
            payload=certificate,
            correlation_id=event.correlation_id
        ))

        # Check for tokenization eligibility
        if event.payload.get("eligible_for_tokenization", True):
            await self.connectors["resolution_to_token"].pass_through(event.payload)

    async def _handle_friction(self, event: SystemEvent) -> None:
        """Handle detected friction - trigger optimization"""
        friction = event.payload

        # Auto-remediation for known patterns
        if friction.get("friction_type") == "latency_spike":
            # Scale up processing
            pass
        elif friction.get("friction_type") == "low_conversion":
            # Trigger A/B test for that stage
            pass
        elif friction.get("friction_type") == "drop_off":
            # Analyze and adjust workflow
            pass

    def _determine_contact_strategy(self, debt_data: dict[str, Any]) -> dict[str, Any]:
        """Determine optimal contact strategy based on consumer profile"""
        shadow_score = debt_data.get("shadow_score", 500)
        balance = debt_data.get("balance", 100)
        days_dpd = debt_data.get("days_past_due", 30)

        # High score, low balance -> SMS first, quick settlement
        if shadow_score >= 650 and balance < 200:
            return {
                "primary_channel": "sms",
                "urgency": "low",
                "offer_type": "immediate_settlement",
                "settlement_range": [0.5, 0.8]
            }

        # Medium score -> Multi-channel approach
        elif shadow_score >= 450:
            return {
                "primary_channel": "email",
                "secondary_channel": "sms",
                "urgency": "medium",
                "offer_type": "payment_plan",
                "plan_duration_weeks": 4 if balance < 100 else 8
            }

        # Low score -> Rehabilitation focus
        else:
            return {
                "primary_channel": "sms",
                "urgency": "low",
                "offer_type": "rehabilitation",
                "highlight_restoration": True,
                "micro_payment_amount": max(10, balance * 0.1)
            }

    def _recommend_persona(self, debt_data: dict[str, Any]) -> str:
        """Recommend AI persona based on consumer profile"""
        sentiment = debt_data.get("last_sentiment", "unknown")
        shadow_score = debt_data.get("shadow_score", 500)

        if sentiment == "hostile":
            return "analytical"  # De-escalate with facts
        elif sentiment == "anxious":
            return "empathetic"  # Build trust
        elif shadow_score < 400:
            return "rehabilitative"  # Offer hope
        elif shadow_score > 700:
            return "advisory"  # Close the deal
        else:
            return "authoritative"  # Create urgency

    async def process_account(self, account_data: dict[str, Any]) -> dict[str, Any]:
        """Process a single account through the full pipeline"""
        correlation_id = hashlib.sha256(
            f"{account_data.get('account_id')}{datetime.now()}".encode()
        ).hexdigest()[:16]

        # Publish ingestion event
        await self.event_bus.publish(SystemEvent(
            event_id=hashlib.sha256(f"ingest_{datetime.now()}".encode()).hexdigest()[:16],
            event_type=EventType.DEBT_INGESTED,
            source_module=SystemModule.INGESTION,
            target_module=SystemModule.SHADOW_BUREAU,
            payload=account_data,
            correlation_id=correlation_id
        ))

        return {
            "correlation_id": correlation_id,
            "status": "processing",
            "account_id": account_data.get("account_id")
        }

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health metrics"""
        friction_analysis = self.friction_analyzer.analyze_pipeline({})

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_health": self._calculate_health_score(),
            "event_bus": {
                "total_events": self.event_bus.metrics.total_events_processed,
                "avg_latency_ms": self.event_bus.metrics.avg_latency_ms,
                "error_rate": self.event_bus.metrics.error_rate
            },
            "connectors": {
                name: conn.metrics
                for name, conn in self.connectors.items()
            },
            "friction": friction_analysis,
            "recommendations": self._generate_recommendations(friction_analysis)
        }

    def _calculate_health_score(self) -> float:
        """Calculate overall system health (0-100)"""
        # Start at 100 and deduct for issues
        score = 100.0

        # Deduct for latency
        if self.event_bus.metrics.avg_latency_ms > 100:
            score -= min(20, self.event_bus.metrics.avg_latency_ms / 50)

        # Deduct for errors
        score -= self.event_bus.metrics.error_rate * 100

        # Deduct for friction
        if self.friction_analyzer.friction_points:
            avg_severity = sum(
                fp.severity for fp in self.friction_analyzer.friction_points
            ) / len(self.friction_analyzer.friction_points)
            score -= avg_severity * 30

        return max(0, score)

    def _generate_recommendations(
        self,
        friction_analysis: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Generate actionable recommendations"""
        recommendations = []

        for point in friction_analysis.get("critical_points", []):
            recommendations.append({
                "priority": "high",
                "area": point["location"],
                "action": point["recommendation"],
                "expected_impact": f"Reduce friction by {point['severity']:.0%}"
            })

        for opp in friction_analysis.get("optimization_opportunities", []):
            recommendations.append({
                "priority": "medium",
                "area": opp["stage"],
                "action": f"Optimize {opp['stage']} latency",
                "expected_impact": opp["potential_improvement"]
            })

        return recommendations


class MaximalCollectionOptimizer:
    """
    Optimizes the entire system for maximum collection efficiency

    Key strategies:
    1. Dynamic routing based on real-time performance
    2. A/B testing of strategies at every stage
    3. Continuous feedback loops for improvement
    4. Portfolio-level optimization across all accounts
    """

    def __init__(self, integration_layer: UnifiedIntegrationLayer):
        self.integration = integration_layer
        self.strategy_performance: dict[str, dict[str, float]] = {}
        self.ab_tests: dict[str, dict[str, Any]] = {}
        self.optimization_history: list[dict[str, Any]] = []

    def optimize_portfolio(
        self,
        accounts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Optimize treatment strategy for entire portfolio

        Returns accounts with optimal strategy assignments
        """
        optimized = []

        # Segment accounts
        segments = self._segment_accounts(accounts)

        for segment_name, segment_accounts in segments.items():
            # Get best performing strategy for segment
            best_strategy = self._get_best_strategy(segment_name)

            for account in segment_accounts:
                account["assigned_strategy"] = best_strategy
                account["expected_recovery"] = self._predict_recovery(
                    account, best_strategy
                )
                optimized.append(account)

        # Sort by expected recovery (prioritize high-value opportunities)
        optimized.sort(key=lambda x: x["expected_recovery"], reverse=True)

        return optimized

    def _segment_accounts(
        self,
        accounts: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Segment accounts for targeted treatment"""
        segments: dict[str, list[dict[str, Any]]] = {
            "high_score_low_balance": [],
            "high_score_high_balance": [],
            "medium_score": [],
            "low_score_rehabilitable": [],
            "low_score_micro": [],
            "uncollectible": []
        }

        for account in accounts:
            score = account.get("shadow_score", 500)
            balance = account.get("balance", 100)

            if score >= 650:
                if balance < 200:
                    segments["high_score_low_balance"].append(account)
                else:
                    segments["high_score_high_balance"].append(account)
            elif score >= 450:
                segments["medium_score"].append(account)
            elif balance < 50:
                segments["low_score_micro"].append(account)
            elif score >= 300:
                segments["low_score_rehabilitable"].append(account)
            else:
                segments["uncollectible"].append(account)

        return segments

    def _get_best_strategy(self, segment: str) -> dict[str, Any]:
        """Get best performing strategy for a segment"""
        default_strategies = {
            "high_score_low_balance": {
                "name": "quick_settlement",
                "channels": ["sms"],
                "offer_percent": 0.7,
                "urgency": "low",
                "max_contacts": 3
            },
            "high_score_high_balance": {
                "name": "premium_engagement",
                "channels": ["email", "sms", "voice"],
                "offer_percent": 0.85,
                "urgency": "medium",
                "max_contacts": 7
            },
            "medium_score": {
                "name": "standard_workflow",
                "channels": ["sms", "email"],
                "offer_percent": 0.6,
                "payment_plan": True,
                "max_contacts": 5
            },
            "low_score_rehabilitable": {
                "name": "rehabilitation_focus",
                "channels": ["sms"],
                "offer_percent": 0.4,
                "micro_payments": True,
                "highlight_restoration": True,
                "max_contacts": 10
            },
            "low_score_micro": {
                "name": "automated_micro",
                "channels": ["sms"],
                "offer_percent": 0.5,
                "single_payment_focus": True,
                "max_contacts": 3
            },
            "uncollectible": {
                "name": "passive_monitoring",
                "channels": [],
                "tokenize_for_sale": True,
                "max_contacts": 0
            }
        }

        # Check if we have performance data
        if segment in self.strategy_performance:
            perf = self.strategy_performance[segment]
            best = max(perf.items(), key=lambda x: x[1])
            if best[1] > 0.3:  # Only use if >30% recovery
                return {"name": best[0], **default_strategies.get(segment, {})}

        return default_strategies.get(segment, default_strategies["medium_score"])

    def _predict_recovery(
        self,
        account: dict[str, Any],
        strategy: dict[str, Any]
    ) -> float:
        """Predict expected recovery value for account with strategy"""
        balance = account.get("balance", 100)
        score = account.get("shadow_score", 500)

        # Base probability from score
        base_prob = score / 850 * 0.7  # Max 70% from score alone

        # Adjust for strategy fit
        if strategy.get("name") == "rehabilitation_focus" and score < 450:
            base_prob *= 1.2  # Rehabilitation works better for low scores
        elif strategy.get("name") == "quick_settlement" and score > 650:
            base_prob *= 1.3  # Quick settlement works for high scores

        # Adjust for balance
        if balance < 50:
            base_prob *= 1.1  # Micro debts resolve faster
        elif balance > 500:
            base_prob *= 0.9  # Larger debts harder to collect

        # Expected recovery
        settlement_percent = strategy.get("offer_percent", 0.6)
        return balance * settlement_percent * min(1.0, base_prob)

    def run_ab_test(
        self,
        test_name: str,
        segment: str,
        strategy_a: dict[str, Any],
        strategy_b: dict[str, Any],
        sample_size: int = 1000
    ) -> str:
        """Initialize an A/B test for strategy comparison"""
        test_id = hashlib.sha256(
            f"{test_name}{segment}{datetime.now()}".encode()
        ).hexdigest()[:12]

        self.ab_tests[test_id] = {
            "test_name": test_name,
            "segment": segment,
            "strategy_a": strategy_a,
            "strategy_b": strategy_b,
            "sample_size": sample_size,
            "results_a": {"count": 0, "recovered": 0.0},
            "results_b": {"count": 0, "recovered": 0.0},
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }

        return test_id

    def record_ab_result(
        self,
        test_id: str,
        variant: str,
        recovered: float
    ) -> None:
        """Record result for A/B test"""
        if test_id not in self.ab_tests:
            return

        test = self.ab_tests[test_id]
        key = f"results_{variant.lower()}"

        if key in test:
            test[key]["count"] += 1
            test[key]["recovered"] += recovered

            # Check for significance
            total_samples = test["results_a"]["count"] + test["results_b"]["count"]
            if total_samples >= test["sample_size"]:
                self._conclude_ab_test(test_id)

    def _conclude_ab_test(self, test_id: str) -> dict[str, Any]:
        """Conclude A/B test and determine winner"""
        test = self.ab_tests[test_id]

        # Calculate recovery rates
        rate_a = (
            test["results_a"]["recovered"] / test["results_a"]["count"]
            if test["results_a"]["count"] > 0 else 0
        )
        rate_b = (
            test["results_b"]["recovered"] / test["results_b"]["count"]
            if test["results_b"]["count"] > 0 else 0
        )

        # Determine winner (simple comparison, production would use statistical test)
        if rate_a > rate_b * 1.05:  # 5% improvement threshold
            winner = "a"
            winning_strategy = test["strategy_a"]
        elif rate_b > rate_a * 1.05:
            winner = "b"
            winning_strategy = test["strategy_b"]
        else:
            winner = "tie"
            winning_strategy = test["strategy_a"]  # Default to A

        # Update strategy performance
        segment = test["segment"]
        strategy_name = winning_strategy.get("name", "unknown")
        if segment not in self.strategy_performance:
            self.strategy_performance[segment] = {}
        self.strategy_performance[segment][strategy_name] = max(rate_a, rate_b)

        # Mark test complete
        test["status"] = "completed"
        test["winner"] = winner
        test["rate_a"] = rate_a
        test["rate_b"] = rate_b
        test["concluded_at"] = datetime.now().isoformat()

        # Record in history
        self.optimization_history.append({
            "type": "ab_test_concluded",
            "test_id": test_id,
            "segment": segment,
            "winner": winner,
            "improvement": abs(rate_a - rate_b) / min(rate_a, rate_b) if min(rate_a, rate_b) > 0 else 0,
            "timestamp": datetime.now().isoformat()
        })

        return test

    def get_optimization_report(self) -> dict[str, Any]:
        """Get comprehensive optimization report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "strategy_performance": self.strategy_performance,
            "active_tests": {
                tid: test for tid, test in self.ab_tests.items()
                if test["status"] == "running"
            },
            "completed_tests": len([
                t for t in self.ab_tests.values()
                if t["status"] == "completed"
            ]),
            "recent_optimizations": self.optimization_history[-10:],
            "recommendations": self._generate_optimization_recommendations()
        }

    def _generate_optimization_recommendations(self) -> list[dict[str, str]]:
        """Generate recommendations based on performance data"""
        recommendations = []

        # Check for underperforming segments
        for segment, strategies in self.strategy_performance.items():
            best_rate = max(strategies.values()) if strategies else 0
            if best_rate < 0.3:
                recommendations.append({
                    "segment": segment,
                    "issue": f"Low recovery rate ({best_rate:.1%})",
                    "recommendation": "Test alternative strategies or adjust offers"
                })

        # Check for untested segments
        all_segments = [
            "high_score_low_balance", "high_score_high_balance",
            "medium_score", "low_score_rehabilitable", "low_score_micro"
        ]
        for segment in all_segments:
            if segment not in self.strategy_performance:
                recommendations.append({
                    "segment": segment,
                    "issue": "No performance data",
                    "recommendation": "Run A/B tests to establish baseline"
                })

        return recommendations


# Demonstration
if __name__ == "__main__":
    import asyncio

    async def demo():
        print("=== UNIFIED INTEGRATION LAYER DEMO ===\n")

        # Initialize
        integration = UnifiedIntegrationLayer()
        optimizer = MaximalCollectionOptimizer(integration)

        # Start event processing
        asyncio.create_task(integration.event_bus.process_events())

        # Process sample accounts
        print("Processing sample accounts...")
        sample_accounts = [
            {"account_id": "A001", "balance": 147.50, "shadow_score": 680, "days_past_due": 45},
            {"account_id": "A002", "balance": 42.00, "shadow_score": 520, "days_past_due": 60},
            {"account_id": "A003", "balance": 285.00, "shadow_score": 380, "days_past_due": 90},
            {"account_id": "A004", "balance": 18.50, "shadow_score": 450, "days_past_due": 30},
            {"account_id": "A005", "balance": 500.00, "shadow_score": 720, "days_past_due": 45},
        ]

        for account in sample_accounts:
            result = await integration.process_account(account)
            print(f"  {account['account_id']}: {result['status']}")

        # Wait for events to process
        await asyncio.sleep(0.5)

        # Get system health
        print("\nSystem Health:")
        health = integration.get_system_health()
        print(f"  Overall Score: {health['overall_health']:.1f}/100")
        print(f"  Events Processed: {health['event_bus']['total_events']}")
        print(f"  Avg Latency: {health['event_bus']['avg_latency_ms']:.1f}ms")

        # Optimize portfolio
        print("\nOptimizing portfolio...")
        optimized = optimizer.optimize_portfolio(sample_accounts)
        for account in optimized[:3]:
            print(f"  {account['account_id']}: {account['assigned_strategy']['name']}")
            print(f"    Expected Recovery: ${account['expected_recovery']:.2f}")

        # Run A/B test
        print("\nInitiating A/B Test...")
        test_id = optimizer.run_ab_test(
            "quick_vs_standard",
            "high_score_low_balance",
            {"name": "quick_settlement", "offer_percent": 0.7},
            {"name": "standard_workflow", "offer_percent": 0.6}
        )
        print(f"  Test ID: {test_id}")

        # Simulate results
        for i in range(100):
            optimizer.record_ab_result(test_id, "a", 50 if i % 3 == 0 else 0)
            optimizer.record_ab_result(test_id, "b", 45 if i % 4 == 0 else 0)

        # Get optimization report
        print("\nOptimization Report:")
        report = optimizer.get_optimization_report()
        print(f"  Active Tests: {len(report['active_tests'])}")
        print(f"  Completed Tests: {report['completed_tests']}")
        if report['recommendations']:
            print(f"  Top Recommendation: {report['recommendations'][0]['recommendation']}")

    asyncio.run(demo())
