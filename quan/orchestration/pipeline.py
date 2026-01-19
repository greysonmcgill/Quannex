"""
Master Pipeline Orchestrator - Central Nervous System for QUAN Collections

This module serves as the unified orchestration layer connecting all QUAN components:
- Ingestion Pipeline: API, batch processing, webhooks, validation
- Workflow Engine: State machine, transitions, parallel execution
- Contact Orchestration: Channel selection, timing, compliance
- Settlement Pipeline: Offers, counter-offers, approvals
- Payment Pipeline: Initiation, tracking, reconciliation
- Resolution Pipeline: Completion, restoration, reporting
- Monitoring & Metrics: Real-time visibility, SLA tracking
- Scaling Controls: Throughput, backpressure, priority queuing
- Inter-Module Communication: Event bus, state persistence

Architecture:
    Creditor API --> Ingestion --> Workflow Engine --> Contact/Settlement --> Payment --> Resolution
                         |              ^                     |                 |            |
                         v              |                     v                 v            v
                   Shadow Bureau   Event Bus <-------- Monitoring <----- Reconciliation  Bureau Reporting
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union,
    TypeVar, Generic, Awaitable
)
from functools import wraps
import traceback

logger = logging.getLogger(__name__)


# =============================================================================
# PIPELINE STAGE DEFINITIONS
# =============================================================================

class PipelineStage(Enum):
    """Master pipeline stages - the complete debt lifecycle"""
    # Ingestion
    ACQUIRE = "acquire"           # Debt received from creditor
    VALIDATE = "validate"         # Data validation and enrichment
    REGISTER = "register"         # Shadow Bureau registration

    # Location
    LOCATE = "locate"             # Skip tracing, contact discovery
    ENRICH = "enrich"             # Data enrichment
    SCORE = "score"               # ML scoring and segmentation

    # Contact
    CONTACT = "contact"           # Initial contact attempt
    ENGAGE = "engage"             # Active engagement
    FOLLOW_UP = "follow_up"       # Follow-up contacts

    # Negotiation
    NEGOTIATE = "negotiate"       # Settlement negotiation
    COUNTER = "counter"           # Counter-offer processing
    APPROVE = "approve"           # Settlement approval

    # Collection
    COLLECT = "collect"           # Payment collection
    VERIFY = "verify"             # Payment verification
    RECONCILE = "reconcile"       # Financial reconciliation

    # Closure
    CLOSE = "close"               # Account closure
    RESTORE = "restore"           # Credit restoration
    REPORT = "report"             # Bureau reporting


class DebtStatus(Enum):
    """Status of debt account in the system"""
    PENDING = "pending"
    ACTIVE = "active"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    PAYMENT_PLAN = "payment_plan"
    SETTLING = "settling"
    COLLECTED = "collected"
    DISPUTED = "disputed"
    UNCOLLECTIBLE = "uncollectible"
    CLOSED = "closed"
    RESTORED = "restored"


class Priority(Enum):
    """Processing priority levels"""
    CRITICAL = 1      # Immediate processing
    HIGH = 2          # Within 1 hour
    NORMAL = 3        # Within 4 hours
    LOW = 4           # Within 24 hours
    BATCH = 5         # Batch processing


class ChannelType(Enum):
    """Communication channels"""
    VOICE = "voice"
    SMS = "sms"
    EMAIL = "email"
    LETTER = "letter"
    PORTAL = "portal"
    CHAT = "chat"


class EventType(Enum):
    """Event types for inter-module communication"""
    # Lifecycle events
    DEBT_ACQUIRED = "debt.acquired"
    DEBT_VALIDATED = "debt.validated"
    DEBT_REGISTERED = "debt.registered"

    # Contact events
    CONTACT_ATTEMPTED = "contact.attempted"
    CONTACT_SUCCESSFUL = "contact.successful"
    CONTACT_FAILED = "contact.failed"
    RESPONSE_RECEIVED = "response.received"

    # Negotiation events
    OFFER_SENT = "offer.sent"
    OFFER_ACCEPTED = "offer.accepted"
    OFFER_REJECTED = "offer.rejected"
    COUNTER_RECEIVED = "counter.received"
    SETTLEMENT_APPROVED = "settlement.approved"

    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_PLAN_CREATED = "payment_plan.created"
    PAYMENT_PLAN_COMPLETED = "payment_plan.completed"

    # Resolution events
    ACCOUNT_CLOSED = "account.closed"
    RESTORATION_ISSUED = "restoration.issued"
    BUREAU_REPORTED = "bureau.reported"

    # System events
    SLA_BREACH = "sla.breach"
    BOTTLENECK_DETECTED = "bottleneck.detected"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker.open"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DebtRecord:
    """Core debt record flowing through the pipeline"""
    id: str
    account_id: str
    creditor_id: str
    creditor_name: str

    # Consumer information
    consumer_id: str
    consumer_name: str
    consumer_email: Optional[str] = None
    consumer_phone: Optional[str] = None
    consumer_address: Optional[Dict[str, str]] = None

    # Financial details
    original_balance: Decimal = Decimal("0")
    current_balance: Decimal = Decimal("0")
    charge_off_date: Optional[datetime] = None
    days_past_due: int = 0

    # Pipeline state
    stage: PipelineStage = PipelineStage.ACQUIRE
    status: DebtStatus = DebtStatus.PENDING
    priority: Priority = Priority.NORMAL

    # Scoring
    recovery_probability: float = 0.0
    optimal_settlement_rate: float = 0.0
    risk_score: float = 0.0

    # Contact information
    optimal_channel: Optional[ChannelType] = None
    optimal_contact_time: Optional[int] = None
    contact_attempts: int = 0
    last_contact: Optional[datetime] = None

    # Settlement
    current_offer: Optional[Decimal] = None
    settlement_amount: Optional[Decimal] = None

    # Payments
    total_paid: Decimal = Decimal("0")
    payment_plan_id: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.original_balance, (int, float)):
            self.original_balance = Decimal(str(self.original_balance))
        if isinstance(self.current_balance, (int, float)):
            self.current_balance = Decimal(str(self.current_balance))


@dataclass
class PipelineEvent:
    """Event for inter-module communication"""
    id: str
    event_type: EventType
    debt_id: str
    stage: PipelineStage
    timestamp: datetime
    payload: Dict[str, Any]
    correlation_id: str
    causation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "debt_id": self.debt_id,
            "stage": self.stage.value,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


@dataclass
class StageTransition:
    """Record of stage transition"""
    from_stage: PipelineStage
    to_stage: PipelineStage
    debt_id: str
    timestamp: datetime
    trigger: str
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class PipelineMetrics:
    """Real-time pipeline metrics"""
    stage: PipelineStage
    count_in_stage: int = 0
    avg_time_in_stage_ms: float = 0.0
    throughput_per_hour: float = 0.0
    conversion_rate: float = 0.0
    error_rate: float = 0.0
    sla_breach_count: int = 0


@dataclass
class SLADefinition:
    """SLA definition for pipeline stages"""
    stage: PipelineStage
    max_time_hours: float
    target_conversion_rate: float
    max_error_rate: float


# =============================================================================
# EVENT BUS - INTER-MODULE COMMUNICATION
# =============================================================================

class EventBus:
    """
    Asynchronous event bus for inter-module communication

    Features:
    - Pub/sub pattern for loose coupling
    - Event persistence for replay
    - Dead letter queue for failed events
    - Correlation tracking
    """

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_store: List[PipelineEvent] = []
        self._dead_letter_queue: List[Tuple[PipelineEvent, Exception]] = []
        self._correlation_map: Dict[str, List[str]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to an event type"""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """Unsubscribe from an event type"""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: PipelineEvent) -> None:
        """Publish an event to all subscribers"""
        # Store event
        self._event_store.append(event)

        # Track correlation
        self._correlation_map[event.correlation_id].append(event.id)

        # Notify subscribers
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.event_type.value}: {e}")
                self._dead_letter_queue.append((event, e))

    def get_events_by_correlation(self, correlation_id: str) -> List[PipelineEvent]:
        """Get all events with a correlation ID"""
        event_ids = self._correlation_map.get(correlation_id, [])
        return [e for e in self._event_store if e.id in event_ids]

    def get_events_by_debt(self, debt_id: str) -> List[PipelineEvent]:
        """Get all events for a debt"""
        return [e for e in self._event_store if e.debt_id == debt_id]

    def get_dead_letters(self) -> List[Tuple[PipelineEvent, Exception]]:
        """Get dead letter queue"""
        return self._dead_letter_queue.copy()

    def clear_dead_letters(self) -> None:
        """Clear dead letter queue"""
        self._dead_letter_queue.clear()


# =============================================================================
# STATE MACHINE
# =============================================================================

class StateMachine:
    """
    State machine for debt lifecycle management

    Manages:
    - Valid state transitions
    - Transition rules and triggers
    - State history
    - Rollback capability
    """

    # Valid transitions between stages
    TRANSITIONS: Dict[PipelineStage, List[PipelineStage]] = {
        PipelineStage.ACQUIRE: [PipelineStage.VALIDATE],
        PipelineStage.VALIDATE: [PipelineStage.REGISTER, PipelineStage.ACQUIRE],
        PipelineStage.REGISTER: [PipelineStage.LOCATE],
        PipelineStage.LOCATE: [PipelineStage.ENRICH],
        PipelineStage.ENRICH: [PipelineStage.SCORE],
        PipelineStage.SCORE: [PipelineStage.CONTACT],
        PipelineStage.CONTACT: [PipelineStage.ENGAGE, PipelineStage.FOLLOW_UP, PipelineStage.NEGOTIATE],
        PipelineStage.ENGAGE: [PipelineStage.NEGOTIATE, PipelineStage.FOLLOW_UP],
        PipelineStage.FOLLOW_UP: [PipelineStage.ENGAGE, PipelineStage.NEGOTIATE, PipelineStage.CLOSE],
        PipelineStage.NEGOTIATE: [PipelineStage.COUNTER, PipelineStage.APPROVE, PipelineStage.FOLLOW_UP],
        PipelineStage.COUNTER: [PipelineStage.NEGOTIATE, PipelineStage.APPROVE],
        PipelineStage.APPROVE: [PipelineStage.COLLECT],
        PipelineStage.COLLECT: [PipelineStage.VERIFY, PipelineStage.NEGOTIATE],
        PipelineStage.VERIFY: [PipelineStage.RECONCILE, PipelineStage.COLLECT],
        PipelineStage.RECONCILE: [PipelineStage.CLOSE],
        PipelineStage.CLOSE: [PipelineStage.RESTORE],
        PipelineStage.RESTORE: [PipelineStage.REPORT],
        PipelineStage.REPORT: [],  # Terminal state
    }

    def __init__(self):
        self._history: Dict[str, List[StageTransition]] = defaultdict(list)
        self._transition_rules: Dict[Tuple[PipelineStage, PipelineStage], Callable] = {}

    def can_transition(self, from_stage: PipelineStage, to_stage: PipelineStage) -> bool:
        """Check if transition is valid"""
        valid_targets = self.TRANSITIONS.get(from_stage, [])
        return to_stage in valid_targets

    def register_rule(
        self,
        from_stage: PipelineStage,
        to_stage: PipelineStage,
        rule: Callable[[DebtRecord], bool]
    ) -> None:
        """Register a transition rule"""
        self._transition_rules[(from_stage, to_stage)] = rule

    def check_rules(
        self,
        from_stage: PipelineStage,
        to_stage: PipelineStage,
        debt: DebtRecord
    ) -> Tuple[bool, Optional[str]]:
        """Check if transition rules allow the transition"""
        rule = self._transition_rules.get((from_stage, to_stage))
        if rule is None:
            return True, None

        try:
            if rule(debt):
                return True, None
            return False, "Transition rule rejected"
        except Exception as e:
            return False, str(e)

    def record_transition(self, transition: StageTransition) -> None:
        """Record a state transition"""
        self._history[transition.debt_id].append(transition)

    def get_history(self, debt_id: str) -> List[StageTransition]:
        """Get transition history for a debt"""
        return self._history.get(debt_id, [])

    def get_time_in_stage(self, debt_id: str, stage: PipelineStage) -> Optional[timedelta]:
        """Get time spent in a specific stage"""
        history = self._history.get(debt_id, [])

        entry_time = None
        for transition in history:
            if transition.to_stage == stage:
                entry_time = transition.timestamp
            elif entry_time and transition.from_stage == stage:
                return transition.timestamp - entry_time

        # Still in stage
        if entry_time:
            return datetime.utcnow() - entry_time

        return None


# =============================================================================
# INGESTION PIPELINE
# =============================================================================

class IngestionPipeline:
    """
    Data ingestion pipeline handling multiple input sources

    Supports:
    - REST API endpoints for real-time submission
    - Batch file processing (CSV, JSON, XML)
    - Webhook integration for real-time events
    - Data validation and enrichment
    - Shadow Bureau registration
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._validators: Dict[str, Callable] = {}
        self._enrichers: List[Callable] = []
        self._batch_queue: asyncio.Queue = asyncio.Queue()
        self._webhook_handlers: Dict[str, Callable] = {}

    def register_validator(self, source_type: str, validator: Callable) -> None:
        """Register a validator for a source type"""
        self._validators[source_type] = validator

    def register_enricher(self, enricher: Callable) -> None:
        """Register a data enricher"""
        self._enrichers.append(enricher)

    def register_webhook(self, event_type: str, handler: Callable) -> None:
        """Register a webhook handler"""
        self._webhook_handlers[event_type] = handler

    async def ingest_single(
        self,
        data: Dict[str, Any],
        source_type: str,
        creditor_id: str
    ) -> Tuple[Optional[DebtRecord], Optional[str]]:
        """Ingest a single debt record"""

        # Validate
        validator = self._validators.get(source_type)
        if validator:
            is_valid, error = await self._run_validator(validator, data)
            if not is_valid:
                return None, f"Validation failed: {error}"

        # Create debt record
        debt = self._create_debt_record(data, creditor_id)

        # Enrich
        for enricher in self._enrichers:
            try:
                debt = await self._run_enricher(enricher, debt)
            except Exception as e:
                logger.warning(f"Enricher failed: {e}")

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.DEBT_ACQUIRED,
            debt_id=debt.id,
            stage=PipelineStage.ACQUIRE,
            timestamp=datetime.utcnow(),
            payload={"source_type": source_type, "creditor_id": creditor_id},
            correlation_id=debt.id,
        ))

        return debt, None

    async def ingest_batch(
        self,
        records: List[Dict[str, Any]],
        source_type: str,
        creditor_id: str,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """Ingest a batch of records"""

        results = {
            "total": len(records),
            "successful": 0,
            "failed": 0,
            "debts": [],
            "errors": [],
        }

        if parallel:
            # Parallel processing
            tasks = [
                self.ingest_single(record, source_type, creditor_id)
                for record in records
            ]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    results["failed"] += 1
                    results["errors"].append({
                        "index": i,
                        "error": str(result)
                    })
                elif result[0] is not None:
                    results["successful"] += 1
                    results["debts"].append(result[0])
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "index": i,
                        "error": result[1]
                    })
        else:
            # Sequential processing
            for i, record in enumerate(records):
                debt, error = await self.ingest_single(record, source_type, creditor_id)
                if debt:
                    results["successful"] += 1
                    results["debts"].append(debt)
                else:
                    results["failed"] += 1
                    results["errors"].append({"index": i, "error": error})

        return results

    async def process_file(
        self,
        file_path: str,
        file_type: str,
        source_type: str,
        creditor_id: str
    ) -> Dict[str, Any]:
        """Process a batch file"""

        # Parse file based on type
        records = await self._parse_file(file_path, file_type)

        # Process batch
        return await self.ingest_batch(records, source_type, creditor_id)

    async def handle_webhook(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming webhook"""

        handler = self._webhook_handlers.get(event_type)
        if not handler:
            return {"status": "error", "message": f"Unknown event type: {event_type}"}

        try:
            result = await handler(payload)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Webhook handler error: {e}")
            return {"status": "error", "message": str(e)}

    def _create_debt_record(self, data: Dict[str, Any], creditor_id: str) -> DebtRecord:
        """Create a DebtRecord from raw data"""
        return DebtRecord(
            id=str(uuid.uuid4()),
            account_id=data.get("account_id", str(uuid.uuid4())),
            creditor_id=creditor_id,
            creditor_name=data.get("creditor_name", "Unknown"),
            consumer_id=data.get("consumer_id", str(uuid.uuid4())),
            consumer_name=data.get("consumer_name", data.get("debtor_name", "Unknown")),
            consumer_email=data.get("email", data.get("debtor_email")),
            consumer_phone=data.get("phone", data.get("debtor_phone")),
            consumer_address=data.get("address", data.get("debtor_address")),
            original_balance=Decimal(str(data.get("original_balance", data.get("balance", 0)))),
            current_balance=Decimal(str(data.get("current_balance", data.get("balance", 0)))),
            charge_off_date=data.get("charge_off_date"),
            days_past_due=data.get("days_past_due", data.get("days_overdue", 0)),
            metadata=data.get("metadata", {}),
        )

    async def _run_validator(
        self,
        validator: Callable,
        data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Run validator on data"""
        try:
            if asyncio.iscoroutinefunction(validator):
                result = await validator(data)
            else:
                result = validator(data)
            return result if isinstance(result, tuple) else (result, None)
        except Exception as e:
            return False, str(e)

    async def _run_enricher(self, enricher: Callable, debt: DebtRecord) -> DebtRecord:
        """Run enricher on debt record"""
        if asyncio.iscoroutinefunction(enricher):
            return await enricher(debt)
        return enricher(debt)

    async def _parse_file(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """Parse file into records"""
        # Simulated - in production would parse actual files
        return []


# =============================================================================
# CONTACT ORCHESTRATION
# =============================================================================

class ContactOrchestrator:
    """
    Multi-channel contact orchestration

    Features:
    - Channel selection based on consumer preferences and regulations
    - Timing optimization for contact attempts
    - Compliance pre-check before every contact
    - Empathy Engine integration
    - Response handling and routing
    """

    # Channel priority order
    CHANNEL_PRIORITY = [
        ChannelType.SMS,
        ChannelType.EMAIL,
        ChannelType.VOICE,
        ChannelType.LETTER,
    ]

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._channel_handlers: Dict[ChannelType, Callable] = {}
        self._compliance_checker: Optional[Callable] = None
        self._empathy_engine: Optional[Any] = None
        self._contact_log: Dict[str, List[Dict]] = defaultdict(list)

    def register_channel_handler(self, channel: ChannelType, handler: Callable) -> None:
        """Register a handler for a channel"""
        self._channel_handlers[channel] = handler

    def set_compliance_checker(self, checker: Callable) -> None:
        """Set the compliance checker"""
        self._compliance_checker = checker

    def set_empathy_engine(self, engine: Any) -> None:
        """Set the Empathy Engine"""
        self._empathy_engine = engine

    async def select_channel(self, debt: DebtRecord) -> Tuple[ChannelType, str]:
        """Select optimal channel for contact"""

        # Check for consumer preference
        if debt.optimal_channel:
            return debt.optimal_channel, "consumer_preference"

        # Check ML recommendation
        if debt.metadata.get("recommended_channel"):
            channel_name = debt.metadata["recommended_channel"]
            try:
                return ChannelType(channel_name), "ml_recommendation"
            except ValueError:
                pass

        # Check available contact info
        available_channels = []
        if debt.consumer_phone:
            available_channels.extend([ChannelType.SMS, ChannelType.VOICE])
        if debt.consumer_email:
            available_channels.append(ChannelType.EMAIL)
        if debt.consumer_address:
            available_channels.append(ChannelType.LETTER)

        # Return first available by priority
        for channel in self.CHANNEL_PRIORITY:
            if channel in available_channels:
                return channel, "priority_selection"

        return ChannelType.EMAIL, "default"

    async def get_optimal_timing(self, debt: DebtRecord) -> Dict[str, Any]:
        """Get optimal timing for contact"""

        # Check for ML-predicted optimal time
        if debt.optimal_contact_time is not None:
            optimal_hour = debt.optimal_contact_time
        else:
            # Default to afternoon (higher response rate)
            optimal_hour = 14

        # Check for payday pattern
        payday_info = debt.metadata.get("payday_pattern")

        return {
            "optimal_hour": optimal_hour,
            "optimal_day_of_week": debt.metadata.get("optimal_day", 2),  # Tuesday
            "payday_pattern": payday_info,
            "avoid_hours": [0, 1, 2, 3, 4, 5, 6, 7, 21, 22, 23],  # Reg F compliance
            "timezone": debt.metadata.get("timezone", "America/New_York"),
        }

    async def check_compliance(self, debt: DebtRecord, channel: ChannelType) -> Tuple[bool, Optional[str]]:
        """Pre-check compliance before contact"""

        if not self._compliance_checker:
            return True, None

        try:
            account_dict = {
                "account_id": debt.account_id,
                "state": debt.metadata.get("state"),
                "timezone": debt.metadata.get("timezone"),
            }

            if asyncio.iscoroutinefunction(self._compliance_checker):
                return await self._compliance_checker(account_dict, channel.value)
            return self._compliance_checker(account_dict, channel.value)
        except Exception as e:
            logger.error(f"Compliance check error: {e}")
            return False, str(e)

    async def initiate_contact(
        self,
        debt: DebtRecord,
        channel: Optional[ChannelType] = None,
        message_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate contact attempt"""

        # Select channel if not specified
        if channel is None:
            channel, reason = await self.select_channel(debt)
        else:
            reason = "manual_selection"

        # Compliance pre-check
        can_contact, compliance_error = await self.check_compliance(debt, channel)
        if not can_contact:
            return {
                "success": False,
                "error": compliance_error,
                "channel": channel.value,
                "blocked_by": "compliance",
            }

        # Get Empathy Engine strategy if available
        strategy = None
        if self._empathy_engine:
            try:
                strategy = await self._get_empathy_strategy(debt)
            except Exception as e:
                logger.warning(f"Empathy Engine error: {e}")

        # Execute contact
        handler = self._channel_handlers.get(channel)
        if not handler:
            return {
                "success": False,
                "error": f"No handler for channel: {channel.value}",
                "channel": channel.value,
            }

        try:
            start_time = time.time()

            if asyncio.iscoroutinefunction(handler):
                result = await handler(debt, message_template, strategy)
            else:
                result = handler(debt, message_template, strategy)

            duration_ms = (time.time() - start_time) * 1000

            # Log contact
            contact_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "channel": channel.value,
                "reason": reason,
                "result": result,
                "duration_ms": duration_ms,
                "strategy": strategy,
            }
            self._contact_log[debt.id].append(contact_record)

            # Publish event
            event_type = EventType.CONTACT_SUCCESSFUL if result.get("success") else EventType.CONTACT_FAILED
            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                debt_id=debt.id,
                stage=PipelineStage.CONTACT,
                timestamp=datetime.utcnow(),
                payload=contact_record,
                correlation_id=debt.id,
            ))

            return {
                "success": result.get("success", False),
                "channel": channel.value,
                "result": result,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            logger.error(f"Contact error: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel": channel.value,
            }

    async def handle_response(
        self,
        debt: DebtRecord,
        channel: ChannelType,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming response from consumer"""

        # Analyze response with Empathy Engine if available
        analysis = None
        if self._empathy_engine:
            try:
                analysis = await self._analyze_response(debt, response)
            except Exception as e:
                logger.warning(f"Response analysis error: {e}")

        # Determine next action
        next_action = self._determine_next_action(debt, response, analysis)

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.RESPONSE_RECEIVED,
            debt_id=debt.id,
            stage=debt.stage,
            timestamp=datetime.utcnow(),
            payload={
                "channel": channel.value,
                "response": response,
                "analysis": analysis,
                "next_action": next_action,
            },
            correlation_id=debt.id,
        ))

        return {
            "received": True,
            "analysis": analysis,
            "next_action": next_action,
        }

    def get_contact_history(self, debt_id: str) -> List[Dict]:
        """Get contact history for a debt"""
        return self._contact_log.get(debt_id, [])

    async def _get_empathy_strategy(self, debt: DebtRecord) -> Dict[str, Any]:
        """Get strategy from Empathy Engine"""
        # Integration point with Empathy Engine
        return {
            "persona": "empathetic",
            "tone": "supportive",
            "urgency_level": 3,
        }

    async def _analyze_response(
        self,
        debt: DebtRecord,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze response using Empathy Engine"""
        return {
            "sentiment": "neutral",
            "intent": "inquiry",
            "payment_likelihood": 0.4,
        }

    def _determine_next_action(
        self,
        debt: DebtRecord,
        response: Dict[str, Any],
        analysis: Optional[Dict[str, Any]]
    ) -> str:
        """Determine next action based on response"""

        if analysis and analysis.get("intent") == "payment":
            return "route_to_settlement"
        elif analysis and analysis.get("intent") == "dispute":
            return "route_to_dispute"
        elif analysis and analysis.get("intent") == "hardship":
            return "route_to_hardship"
        else:
            return "continue_engagement"


# =============================================================================
# SETTLEMENT PIPELINE
# =============================================================================

class SettlementPipeline:
    """
    Settlement negotiation pipeline

    Features:
    - Intelligent offer generation
    - Counter-offer processing
    - Approval workflows
    - Payment plan setup
    - Documentation generation
    """

    # Default settlement parameters
    DEFAULT_OPENING_OFFER = 0.50  # 50% of balance
    MIN_SETTLEMENT = 0.15  # 15% minimum
    MAX_SETTLEMENT = 1.00  # 100% maximum

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._offer_generator: Optional[Callable] = None
        self._approval_rules: List[Callable] = []
        self._pending_offers: Dict[str, Dict] = {}
        self._approved_settlements: Dict[str, Dict] = {}

    def set_offer_generator(self, generator: Callable) -> None:
        """Set the offer generator"""
        self._offer_generator = generator

    def add_approval_rule(self, rule: Callable) -> None:
        """Add an approval rule"""
        self._approval_rules.append(rule)

    async def generate_offer(self, debt: DebtRecord) -> Dict[str, Any]:
        """Generate settlement offer"""

        if self._offer_generator:
            try:
                if asyncio.iscoroutinefunction(self._offer_generator):
                    offer = await self._offer_generator(debt)
                else:
                    offer = self._offer_generator(debt)
            except Exception as e:
                logger.warning(f"Offer generator error: {e}, using default")
                offer = self._default_offer(debt)
        else:
            offer = self._default_offer(debt)

        # Store pending offer
        offer_id = str(uuid.uuid4())
        offer_record = {
            "offer_id": offer_id,
            "debt_id": debt.id,
            "created_at": datetime.utcnow().isoformat(),
            "offer": offer,
            "status": "pending",
        }
        self._pending_offers[offer_id] = offer_record

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.OFFER_SENT,
            debt_id=debt.id,
            stage=PipelineStage.NEGOTIATE,
            timestamp=datetime.utcnow(),
            payload=offer_record,
            correlation_id=debt.id,
        ))

        return offer_record

    async def process_response(
        self,
        offer_id: str,
        response: str,
        counter_amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Process response to settlement offer"""

        offer_record = self._pending_offers.get(offer_id)
        if not offer_record:
            return {"error": "Offer not found"}

        debt_id = offer_record["debt_id"]

        if response == "accept":
            # Offer accepted - route to approval
            offer_record["status"] = "accepted"
            result = await self._route_to_approval(offer_record)

            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=EventType.OFFER_ACCEPTED,
                debt_id=debt_id,
                stage=PipelineStage.NEGOTIATE,
                timestamp=datetime.utcnow(),
                payload=offer_record,
                correlation_id=debt_id,
            ))

            return result

        elif response == "reject":
            offer_record["status"] = "rejected"

            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=EventType.OFFER_REJECTED,
                debt_id=debt_id,
                stage=PipelineStage.NEGOTIATE,
                timestamp=datetime.utcnow(),
                payload=offer_record,
                correlation_id=debt_id,
            ))

            return {"status": "rejected", "offer_id": offer_id}

        elif response == "counter" and counter_amount:
            # Process counter-offer
            return await self._process_counter(offer_record, counter_amount)

        return {"error": "Invalid response"}

    async def approve_settlement(
        self,
        debt: DebtRecord,
        settlement_amount: Decimal
    ) -> Dict[str, Any]:
        """Approve and finalize settlement"""

        # Run approval rules
        for rule in self._approval_rules:
            try:
                if asyncio.iscoroutinefunction(rule):
                    approved, reason = await rule(debt, settlement_amount)
                else:
                    approved, reason = rule(debt, settlement_amount)

                if not approved:
                    return {"approved": False, "reason": reason}
            except Exception as e:
                logger.error(f"Approval rule error: {e}")
                return {"approved": False, "reason": str(e)}

        # Settlement approved
        settlement_record = {
            "settlement_id": str(uuid.uuid4()),
            "debt_id": debt.id,
            "original_balance": str(debt.current_balance),
            "settlement_amount": str(settlement_amount),
            "settlement_rate": float(settlement_amount / debt.current_balance),
            "approved_at": datetime.utcnow().isoformat(),
            "status": "approved",
        }

        self._approved_settlements[debt.id] = settlement_record

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.SETTLEMENT_APPROVED,
            debt_id=debt.id,
            stage=PipelineStage.APPROVE,
            timestamp=datetime.utcnow(),
            payload=settlement_record,
            correlation_id=debt.id,
        ))

        return {"approved": True, "settlement": settlement_record}

    async def create_payment_plan(
        self,
        debt: DebtRecord,
        settlement_amount: Decimal,
        num_payments: int,
        frequency: str = "monthly",
        start_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create a payment plan for settlement"""

        if start_date is None:
            start_date = datetime.utcnow() + timedelta(days=7)

        payment_amount = (settlement_amount / num_payments).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Build payment schedule
        schedule = []
        current_date = start_date

        for i in range(num_payments):
            schedule.append({
                "payment_number": i + 1,
                "due_date": current_date.isoformat(),
                "amount": str(payment_amount),
                "status": "pending",
            })

            # Advance date based on frequency
            if frequency == "weekly":
                current_date += timedelta(weeks=1)
            elif frequency == "biweekly":
                current_date += timedelta(weeks=2)
            else:  # monthly
                current_date += timedelta(days=30)

        plan_record = {
            "plan_id": str(uuid.uuid4()),
            "debt_id": debt.id,
            "settlement_amount": str(settlement_amount),
            "num_payments": num_payments,
            "payment_amount": str(payment_amount),
            "frequency": frequency,
            "start_date": start_date.isoformat(),
            "schedule": schedule,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.PAYMENT_PLAN_CREATED,
            debt_id=debt.id,
            stage=PipelineStage.APPROVE,
            timestamp=datetime.utcnow(),
            payload=plan_record,
            correlation_id=debt.id,
        ))

        return plan_record

    def _default_offer(self, debt: DebtRecord) -> Dict[str, Any]:
        """Generate default offer"""

        # Use recovery probability to adjust offer
        recovery_prob = debt.recovery_probability or 0.3

        # Higher recovery probability = higher opening offer
        offer_rate = max(
            self.MIN_SETTLEMENT,
            min(self.MAX_SETTLEMENT, self.DEFAULT_OPENING_OFFER + (recovery_prob - 0.5) * 0.2)
        )

        offer_amount = (debt.current_balance * Decimal(str(offer_rate))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "amount": str(offer_amount),
            "rate": offer_rate,
            "valid_until": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "payment_options": ["lump_sum", "payment_plan"],
        }

    async def _route_to_approval(self, offer_record: Dict) -> Dict[str, Any]:
        """Route accepted offer to approval workflow"""
        return {
            "status": "pending_approval",
            "offer_id": offer_record["offer_id"],
        }

    async def _process_counter(
        self,
        offer_record: Dict,
        counter_amount: Decimal
    ) -> Dict[str, Any]:
        """Process counter-offer"""

        debt_id = offer_record["debt_id"]

        counter_record = {
            "original_offer_id": offer_record["offer_id"],
            "counter_amount": str(counter_amount),
            "received_at": datetime.utcnow().isoformat(),
        }

        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.COUNTER_RECEIVED,
            debt_id=debt_id,
            stage=PipelineStage.COUNTER,
            timestamp=datetime.utcnow(),
            payload=counter_record,
            correlation_id=debt_id,
        ))

        return {"status": "counter_received", "counter": counter_record}


# =============================================================================
# PAYMENT PIPELINE
# =============================================================================

class PaymentPipeline:
    """
    Payment processing pipeline

    Features:
    - Payment initiation
    - Status tracking
    - Intelligent retry logic
    - Reconciliation triggers
    - Trust accounting updates
    """

    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAYS = [1, 4, 24]  # Hours between retries

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._payment_processor: Optional[Callable] = None
        self._pending_payments: Dict[str, Dict] = {}
        self._completed_payments: Dict[str, List[Dict]] = defaultdict(list)
        self._retry_queue: asyncio.Queue = asyncio.Queue()

    def set_payment_processor(self, processor: Callable) -> None:
        """Set the payment processor"""
        self._payment_processor = processor

    async def initiate_payment(
        self,
        debt: DebtRecord,
        amount: Decimal,
        payment_method: Dict[str, Any],
        payment_type: str = "one_time"
    ) -> Dict[str, Any]:
        """Initiate a payment"""

        payment_id = str(uuid.uuid4())

        payment_record = {
            "payment_id": payment_id,
            "debt_id": debt.id,
            "amount": str(amount),
            "payment_method": payment_method,
            "payment_type": payment_type,
            "initiated_at": datetime.utcnow().isoformat(),
            "status": "initiated",
            "attempts": 0,
        }

        self._pending_payments[payment_id] = payment_record

        # Process payment
        result = await self._process_payment(payment_record)

        return result

    async def _process_payment(self, payment_record: Dict) -> Dict[str, Any]:
        """Process a payment through the payment processor"""

        payment_record["attempts"] += 1

        if self._payment_processor:
            try:
                if asyncio.iscoroutinefunction(self._payment_processor):
                    result = await self._payment_processor(payment_record)
                else:
                    result = self._payment_processor(payment_record)
            except Exception as e:
                result = {"success": False, "error": str(e)}
        else:
            # Simulated success
            result = {"success": True, "processor_id": f"sim_{uuid.uuid4().hex[:8]}"}

        if result.get("success"):
            payment_record["status"] = "completed"
            payment_record["completed_at"] = datetime.utcnow().isoformat()
            payment_record["processor_result"] = result

            # Move to completed
            debt_id = payment_record["debt_id"]
            self._completed_payments[debt_id].append(payment_record)
            del self._pending_payments[payment_record["payment_id"]]

            # Publish success event
            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=EventType.PAYMENT_RECEIVED,
                debt_id=debt_id,
                stage=PipelineStage.COLLECT,
                timestamp=datetime.utcnow(),
                payload=payment_record,
                correlation_id=debt_id,
            ))

            # Trigger reconciliation
            await self._trigger_reconciliation(debt_id, payment_record)

            return {"success": True, "payment": payment_record}
        else:
            # Payment failed
            payment_record["status"] = "failed"
            payment_record["last_error"] = result.get("error")
            payment_record["last_attempt"] = datetime.utcnow().isoformat()

            # Check for retry
            if payment_record["attempts"] < self.MAX_RETRY_ATTEMPTS:
                await self._schedule_retry(payment_record)
                return {
                    "success": False,
                    "scheduled_retry": True,
                    "retry_attempt": payment_record["attempts"] + 1,
                    "error": result.get("error"),
                }

            # Publish failure event
            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=EventType.PAYMENT_FAILED,
                debt_id=payment_record["debt_id"],
                stage=PipelineStage.COLLECT,
                timestamp=datetime.utcnow(),
                payload=payment_record,
                correlation_id=payment_record["debt_id"],
            ))

            return {"success": False, "error": result.get("error"), "payment": payment_record}

    async def check_payment_status(self, payment_id: str) -> Optional[Dict]:
        """Check status of a payment"""

        if payment_id in self._pending_payments:
            return self._pending_payments[payment_id]

        # Search completed payments
        for debt_id, payments in self._completed_payments.items():
            for payment in payments:
                if payment["payment_id"] == payment_id:
                    return payment

        return None

    async def get_payments_for_debt(self, debt_id: str) -> List[Dict]:
        """Get all payments for a debt"""

        payments = []

        # Add pending
        for payment in self._pending_payments.values():
            if payment["debt_id"] == debt_id:
                payments.append(payment)

        # Add completed
        payments.extend(self._completed_payments.get(debt_id, []))

        return payments

    async def _schedule_retry(self, payment_record: Dict) -> None:
        """Schedule a payment retry"""

        attempt = payment_record["attempts"]
        delay_hours = self.RETRY_DELAYS[attempt - 1] if attempt <= len(self.RETRY_DELAYS) else 24

        payment_record["next_retry"] = (
            datetime.utcnow() + timedelta(hours=delay_hours)
        ).isoformat()

        await self._retry_queue.put(payment_record)
        logger.info(f"Scheduled retry for payment {payment_record['payment_id']} in {delay_hours} hours")

    async def _trigger_reconciliation(self, debt_id: str, payment_record: Dict) -> None:
        """Trigger reconciliation for a completed payment"""

        # Calculate total paid
        total_paid = sum(
            Decimal(p["amount"]) for p in self._completed_payments[debt_id]
        )

        logger.info(f"Reconciliation triggered for debt {debt_id}: total paid = {total_paid}")

    async def process_retry_queue(self) -> None:
        """Process the retry queue (run as background task)"""

        while True:
            try:
                payment_record = await asyncio.wait_for(
                    self._retry_queue.get(),
                    timeout=60
                )

                # Check if it's time to retry
                next_retry = datetime.fromisoformat(payment_record["next_retry"])
                if datetime.utcnow() >= next_retry:
                    await self._process_payment(payment_record)
                else:
                    # Put back in queue
                    await self._retry_queue.put(payment_record)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Retry queue error: {e}")


# =============================================================================
# RESOLUTION PIPELINE
# =============================================================================

class ResolutionPipeline:
    """
    Account resolution pipeline

    Features:
    - Settlement completion verification
    - Restoration certificate issuance
    - Credit bureau reporting triggers
    - Client notification
    - Portfolio updates
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._resolved_accounts: Dict[str, Dict] = {}
        self._restoration_certificates: Dict[str, Dict] = {}
        self._bureau_reports: List[Dict] = []

    async def complete_settlement(
        self,
        debt: DebtRecord,
        settlement_record: Dict,
        total_paid: Decimal
    ) -> Dict[str, Any]:
        """Complete a settlement"""

        resolution_record = {
            "resolution_id": str(uuid.uuid4()),
            "debt_id": debt.id,
            "original_balance": str(debt.original_balance),
            "settlement_amount": settlement_record.get("settlement_amount"),
            "total_paid": str(total_paid),
            "resolution_type": "settlement",
            "resolved_at": datetime.utcnow().isoformat(),
        }

        self._resolved_accounts[debt.id] = resolution_record

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.ACCOUNT_CLOSED,
            debt_id=debt.id,
            stage=PipelineStage.CLOSE,
            timestamp=datetime.utcnow(),
            payload=resolution_record,
            correlation_id=debt.id,
        ))

        return resolution_record

    async def issue_restoration_certificate(
        self,
        debt: DebtRecord,
        resolution_record: Dict
    ) -> Dict[str, Any]:
        """Issue a credit restoration certificate"""

        certificate = {
            "certificate_id": str(uuid.uuid4()),
            "debt_id": debt.id,
            "consumer_id": debt.consumer_id,
            "consumer_name": debt.consumer_name,
            "creditor_name": debt.creditor_name,
            "original_balance": str(debt.original_balance),
            "resolution_type": resolution_record.get("resolution_type"),
            "resolved_at": resolution_record.get("resolved_at"),
            "issued_at": datetime.utcnow().isoformat(),
            "certificate_hash": self._generate_certificate_hash(debt, resolution_record),
            "status": "issued",
        }

        self._restoration_certificates[debt.id] = certificate

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.RESTORATION_ISSUED,
            debt_id=debt.id,
            stage=PipelineStage.RESTORE,
            timestamp=datetime.utcnow(),
            payload=certificate,
            correlation_id=debt.id,
        ))

        return certificate

    async def trigger_bureau_report(
        self,
        debt: DebtRecord,
        resolution_record: Dict,
        bureaus: List[str] = None
    ) -> Dict[str, Any]:
        """Trigger credit bureau reporting"""

        if bureaus is None:
            bureaus = ["equifax", "experian", "transunion"]

        report_record = {
            "report_id": str(uuid.uuid4()),
            "debt_id": debt.id,
            "consumer_id": debt.consumer_id,
            "resolution_type": resolution_record.get("resolution_type"),
            "bureaus": bureaus,
            "status": "pending",
            "triggered_at": datetime.utcnow().isoformat(),
        }

        self._bureau_reports.append(report_record)

        # Simulate bureau reporting
        for bureau in bureaus:
            # Would call actual bureau APIs
            logger.info(f"Reporting to {bureau} for debt {debt.id}")

        report_record["status"] = "submitted"
        report_record["submitted_at"] = datetime.utcnow().isoformat()

        # Publish event
        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.BUREAU_REPORTED,
            debt_id=debt.id,
            stage=PipelineStage.REPORT,
            timestamp=datetime.utcnow(),
            payload=report_record,
            correlation_id=debt.id,
        ))

        return report_record

    async def notify_client(
        self,
        debt: DebtRecord,
        resolution_record: Dict
    ) -> Dict[str, Any]:
        """Notify creditor client of resolution"""

        notification = {
            "notification_id": str(uuid.uuid4()),
            "creditor_id": debt.creditor_id,
            "debt_id": debt.id,
            "account_id": debt.account_id,
            "resolution_type": resolution_record.get("resolution_type"),
            "amount_collected": resolution_record.get("total_paid"),
            "resolved_at": resolution_record.get("resolved_at"),
            "notified_at": datetime.utcnow().isoformat(),
        }

        # Would send actual notification
        logger.info(f"Notifying client {debt.creditor_id} of resolution for {debt.id}")

        return notification

    def _generate_certificate_hash(
        self,
        debt: DebtRecord,
        resolution_record: Dict
    ) -> str:
        """Generate verification hash for certificate"""

        data = f"{debt.id}:{debt.consumer_id}:{resolution_record.get('resolved_at')}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# =============================================================================
# MONITORING & METRICS
# =============================================================================

class PipelineMonitor:
    """
    Real-time pipeline monitoring

    Features:
    - Real-time pipeline visibility
    - Stage conversion rates
    - Bottleneck identification
    - SLA tracking
    - Alert generation
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._stage_counts: Dict[PipelineStage, int] = defaultdict(int)
        self._stage_times: Dict[PipelineStage, List[float]] = defaultdict(list)
        self._conversions: Dict[Tuple[PipelineStage, PipelineStage], int] = defaultdict(int)
        self._errors: Dict[PipelineStage, int] = defaultdict(int)
        self._sla_definitions: Dict[PipelineStage, SLADefinition] = {}
        self._sla_breaches: List[Dict] = []
        self._alerts: List[Dict] = []

        # Subscribe to events
        self._setup_subscriptions()

    def _setup_subscriptions(self) -> None:
        """Set up event subscriptions"""

        # Subscribe to all event types for monitoring
        for event_type in EventType:
            self.event_bus.subscribe(event_type, self._handle_event)

    def _handle_event(self, event: PipelineEvent) -> None:
        """Handle incoming event for metrics"""

        # Update stage counts
        self._stage_counts[event.stage] += 1

        # Check for errors
        if "error" in event.payload:
            self._errors[event.stage] += 1

        # Check SLA
        self._check_sla(event)

    def define_sla(self, sla: SLADefinition) -> None:
        """Define SLA for a stage"""
        self._sla_definitions[sla.stage] = sla

    def record_stage_time(self, stage: PipelineStage, time_ms: float) -> None:
        """Record time spent in a stage"""
        self._stage_times[stage].append(time_ms)

    def record_conversion(self, from_stage: PipelineStage, to_stage: PipelineStage) -> None:
        """Record a stage conversion"""
        self._conversions[(from_stage, to_stage)] += 1

    def get_metrics(self, stage: Optional[PipelineStage] = None) -> Dict[str, Any]:
        """Get pipeline metrics"""

        if stage:
            return self._get_stage_metrics(stage)

        # All stages
        metrics = {}
        for s in PipelineStage:
            metrics[s.value] = self._get_stage_metrics(s)

        # Overall metrics
        total_in_pipeline = sum(self._stage_counts.values())
        total_errors = sum(self._errors.values())

        metrics["overall"] = {
            "total_in_pipeline": total_in_pipeline,
            "total_errors": total_errors,
            "error_rate": total_errors / max(total_in_pipeline, 1),
            "sla_breaches": len(self._sla_breaches),
        }

        return metrics

    def _get_stage_metrics(self, stage: PipelineStage) -> PipelineMetrics:
        """Get metrics for a specific stage"""

        times = self._stage_times.get(stage, [])
        count = self._stage_counts.get(stage, 0)
        errors = self._errors.get(stage, 0)

        # Calculate conversion rate
        outgoing = sum(
            c for (f, t), c in self._conversions.items() if f == stage
        )
        conversion_rate = outgoing / max(count, 1)

        # Calculate throughput (assuming last hour of data)
        throughput = count  # Simplified

        return PipelineMetrics(
            stage=stage,
            count_in_stage=count,
            avg_time_in_stage_ms=sum(times) / max(len(times), 1),
            throughput_per_hour=throughput,
            conversion_rate=conversion_rate,
            error_rate=errors / max(count, 1),
            sla_breach_count=sum(1 for b in self._sla_breaches if b["stage"] == stage.value),
        )

    def identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify pipeline bottlenecks"""

        bottlenecks = []

        for stage in PipelineStage:
            metrics = self._get_stage_metrics(stage)

            # Check for high time in stage
            if metrics.avg_time_in_stage_ms > 60000:  # > 1 minute
                bottlenecks.append({
                    "stage": stage.value,
                    "type": "high_latency",
                    "avg_time_ms": metrics.avg_time_in_stage_ms,
                })

            # Check for low conversion rate
            if metrics.conversion_rate < 0.5 and metrics.count_in_stage > 10:
                bottlenecks.append({
                    "stage": stage.value,
                    "type": "low_conversion",
                    "conversion_rate": metrics.conversion_rate,
                })

            # Check for high error rate
            if metrics.error_rate > 0.1:
                bottlenecks.append({
                    "stage": stage.value,
                    "type": "high_errors",
                    "error_rate": metrics.error_rate,
                })

        return bottlenecks

    def _check_sla(self, event: PipelineEvent) -> None:
        """Check if event triggers SLA breach"""

        sla = self._sla_definitions.get(event.stage)
        if not sla:
            return

        # Check error rate threshold
        metrics = self._get_stage_metrics(event.stage)
        if metrics.error_rate > sla.max_error_rate:
            breach = {
                "stage": event.stage.value,
                "type": "error_rate",
                "threshold": sla.max_error_rate,
                "actual": metrics.error_rate,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._sla_breaches.append(breach)
            self._generate_alert(breach)

    def _generate_alert(self, breach: Dict) -> None:
        """Generate alert for SLA breach"""

        alert = {
            "alert_id": str(uuid.uuid4()),
            "type": "sla_breach",
            "breach": breach,
            "generated_at": datetime.utcnow().isoformat(),
        }

        self._alerts.append(alert)
        logger.warning(f"SLA BREACH ALERT: {breach}")

        # Would send to alerting system

    def get_alerts(self, since: Optional[datetime] = None) -> List[Dict]:
        """Get alerts, optionally since a timestamp"""

        if since:
            return [
                a for a in self._alerts
                if datetime.fromisoformat(a["generated_at"]) >= since
            ]
        return self._alerts


# =============================================================================
# SCALING CONTROLS
# =============================================================================

class ScalingController:
    """
    Pipeline scaling and resource management

    Features:
    - Throughput management
    - Resource allocation
    - Priority queuing
    - Backpressure handling
    - Circuit breaker pattern
    """

    def __init__(self):
        self._rate_limiters: Dict[str, 'TokenBucket'] = {}
        self._circuit_breakers: Dict[str, 'CircuitBreaker'] = {}
        self._priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_workers: int = 0
        self._max_workers: int = 100
        self._backpressure_threshold: float = 0.8

    def configure_rate_limit(self, key: str, rate: float, burst: int) -> None:
        """Configure rate limiting for a key"""
        self._rate_limiters[key] = TokenBucket(rate, burst)

    def configure_circuit_breaker(
        self,
        key: str,
        failure_threshold: int = 5,
        reset_timeout: int = 60
    ) -> None:
        """Configure circuit breaker for a key"""
        self._circuit_breakers[key] = CircuitBreaker(failure_threshold, reset_timeout)

    async def acquire_rate_limit(self, key: str) -> bool:
        """Try to acquire rate limit token"""
        limiter = self._rate_limiters.get(key)
        if limiter:
            return limiter.consume()
        return True

    def check_circuit_breaker(self, key: str) -> bool:
        """Check if circuit breaker allows request"""
        breaker = self._circuit_breakers.get(key)
        if breaker:
            return breaker.allow_request()
        return True

    def record_success(self, key: str) -> None:
        """Record successful operation"""
        breaker = self._circuit_breakers.get(key)
        if breaker:
            breaker.record_success()

    def record_failure(self, key: str) -> None:
        """Record failed operation"""
        breaker = self._circuit_breakers.get(key)
        if breaker:
            breaker.record_failure()

    async def enqueue(self, priority: Priority, item: Any) -> None:
        """Add item to priority queue"""
        await self._priority_queue.put((priority.value, time.time(), item))

    async def dequeue(self) -> Any:
        """Get next item from priority queue"""
        _, _, item = await self._priority_queue.get()
        return item

    def check_backpressure(self) -> Tuple[bool, float]:
        """Check if backpressure should be applied"""
        if self._max_workers == 0:
            return False, 0.0

        load = self._active_workers / self._max_workers
        should_apply = load >= self._backpressure_threshold

        return should_apply, load

    def acquire_worker(self) -> bool:
        """Try to acquire a worker slot"""
        if self._active_workers < self._max_workers:
            self._active_workers += 1
            return True
        return False

    def release_worker(self) -> None:
        """Release a worker slot"""
        if self._active_workers > 0:
            self._active_workers -= 1


class TokenBucket:
    """Token bucket rate limiter"""

    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens"""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""

    def __init__(self, failure_threshold: int, reset_timeout: int):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure = None
        self.state = "closed"  # closed, open, half-open

    def allow_request(self) -> bool:
        """Check if request should be allowed"""

        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if timeout has elapsed
            if self.last_failure and \
               (time.time() - self.last_failure) > self.reset_timeout:
                self.state = "half-open"
                return True
            return False

        # half-open: allow one request
        return True

    def record_success(self) -> None:
        """Record successful operation"""
        if self.state == "half-open":
            self.state = "closed"
            self.failures = 0

    def record_failure(self) -> None:
        """Record failed operation"""
        self.failures += 1
        self.last_failure = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "open"


# =============================================================================
# MASTER PIPELINE ORCHESTRATOR
# =============================================================================

class MasterPipelineOrchestrator:
    """
    Master Pipeline Orchestrator - Central Nervous System

    Coordinates all pipeline components:
    - Ingestion
    - Workflow/State Machine
    - Contact Orchestration
    - Settlement
    - Payment
    - Resolution
    - Monitoring
    - Scaling
    """

    def __init__(self):
        # Core components
        self.event_bus = EventBus()
        self.state_machine = StateMachine()

        # Pipelines
        self.ingestion = IngestionPipeline(self.event_bus)
        self.contact = ContactOrchestrator(self.event_bus)
        self.settlement = SettlementPipeline(self.event_bus)
        self.payment = PaymentPipeline(self.event_bus)
        self.resolution = ResolutionPipeline(self.event_bus)

        # Infrastructure
        self.monitor = PipelineMonitor(self.event_bus)
        self.scaling = ScalingController()

        # State
        self._debts: Dict[str, DebtRecord] = {}
        self._active_workflows: Dict[str, asyncio.Task] = {}

        # Configure defaults
        self._configure_defaults()

    def _configure_defaults(self) -> None:
        """Configure default settings"""

        # Default rate limits
        self.scaling.configure_rate_limit("ingestion", rate=100, burst=500)
        self.scaling.configure_rate_limit("contact", rate=50, burst=100)
        self.scaling.configure_rate_limit("payment", rate=20, burst=50)

        # Default circuit breakers
        self.scaling.configure_circuit_breaker("payment_processor", failure_threshold=5)
        self.scaling.configure_circuit_breaker("contact_channel", failure_threshold=10)

        # Default SLAs
        self.monitor.define_sla(SLADefinition(
            stage=PipelineStage.VALIDATE,
            max_time_hours=1,
            target_conversion_rate=0.95,
            max_error_rate=0.05,
        ))
        self.monitor.define_sla(SLADefinition(
            stage=PipelineStage.CONTACT,
            max_time_hours=24,
            target_conversion_rate=0.30,
            max_error_rate=0.10,
        ))

        # Register default validators
        self.ingestion.register_validator("bnpl", self._default_validator)
        self.ingestion.register_validator("bank", self._default_validator)
        self.ingestion.register_validator("subscription", self._default_validator)

        # Register default channel handlers
        self.contact.register_channel_handler(ChannelType.SMS, self._default_sms_handler)
        self.contact.register_channel_handler(ChannelType.EMAIL, self._default_email_handler)
        self.contact.register_channel_handler(ChannelType.VOICE, self._default_voice_handler)

    async def ingest_debt(
        self,
        data: Dict[str, Any],
        source_type: str,
        creditor_id: str
    ) -> Tuple[Optional[DebtRecord], Optional[str]]:
        """Ingest a single debt into the pipeline"""

        # Check rate limit
        if not await self.scaling.acquire_rate_limit("ingestion"):
            return None, "Rate limit exceeded"

        # Ingest
        debt, error = await self.ingestion.ingest_single(data, source_type, creditor_id)

        if debt:
            self._debts[debt.id] = debt

            # Start workflow
            await self._start_workflow(debt)

        return debt, error

    async def ingest_portfolio(
        self,
        records: List[Dict[str, Any]],
        source_type: str,
        creditor_id: str
    ) -> Dict[str, Any]:
        """Ingest a portfolio of debts"""

        result = await self.ingestion.ingest_batch(records, source_type, creditor_id)

        # Store debts and start workflows
        for debt in result.get("debts", []):
            self._debts[debt.id] = debt
            await self._start_workflow(debt)

        return result

    async def _start_workflow(self, debt: DebtRecord) -> None:
        """Start the collection workflow for a debt"""

        task = asyncio.create_task(self._run_workflow(debt))
        self._active_workflows[debt.id] = task

    async def _run_workflow(self, debt: DebtRecord) -> None:
        """Run the complete collection workflow"""

        try:
            # VALIDATE
            debt = await self._stage_validate(debt)

            # REGISTER
            debt = await self._stage_register(debt)

            # LOCATE
            debt = await self._stage_locate(debt)

            # ENRICH
            debt = await self._stage_enrich(debt)

            # SCORE
            debt = await self._stage_score(debt)

            # CONTACT
            debt = await self._stage_contact(debt)

            # NEGOTIATE (if contacted)
            if debt.status == DebtStatus.CONTACTED:
                debt = await self._stage_negotiate(debt)

            # COLLECT (if settlement approved)
            if debt.status == DebtStatus.SETTLING:
                debt = await self._stage_collect(debt)

            # CLOSE (if collected)
            if debt.status == DebtStatus.COLLECTED:
                debt = await self._stage_close(debt)

            # RESTORE
            if debt.status == DebtStatus.CLOSED:
                debt = await self._stage_restore(debt)

            logger.info(f"Workflow completed for debt {debt.id}: {debt.status.value}")

        except Exception as e:
            logger.error(f"Workflow error for debt {debt.id}: {e}")
            logger.error(traceback.format_exc())
            debt.metadata["workflow_error"] = str(e)

        finally:
            self._debts[debt.id] = debt
            if debt.id in self._active_workflows:
                del self._active_workflows[debt.id]

    async def _transition_stage(
        self,
        debt: DebtRecord,
        to_stage: PipelineStage,
        trigger: str
    ) -> DebtRecord:
        """Transition debt to a new stage"""

        from_stage = debt.stage
        start_time = time.time()

        # Check if transition is valid
        if not self.state_machine.can_transition(from_stage, to_stage):
            raise ValueError(f"Invalid transition: {from_stage.value} -> {to_stage.value}")

        # Check transition rules
        allowed, reason = self.state_machine.check_rules(from_stage, to_stage, debt)
        if not allowed:
            raise ValueError(f"Transition blocked: {reason}")

        # Perform transition
        debt.stage = to_stage
        debt.updated_at = datetime.utcnow()

        duration_ms = (time.time() - start_time) * 1000

        # Record transition
        transition = StageTransition(
            from_stage=from_stage,
            to_stage=to_stage,
            debt_id=debt.id,
            timestamp=datetime.utcnow(),
            trigger=trigger,
            duration_ms=duration_ms,
            success=True,
        )
        self.state_machine.record_transition(transition)

        # Update metrics
        self.monitor.record_stage_time(from_stage, duration_ms)
        self.monitor.record_conversion(from_stage, to_stage)

        logger.info(f"Debt {debt.id}: {from_stage.value} -> {to_stage.value}")

        return debt

    async def _stage_validate(self, debt: DebtRecord) -> DebtRecord:
        """Validate stage"""

        debt = await self._transition_stage(debt, PipelineStage.VALIDATE, "ingestion_complete")

        # Validation logic
        valid = True
        errors = []

        if debt.current_balance <= 0:
            valid = False
            errors.append("Invalid balance")

        if not debt.consumer_name:
            valid = False
            errors.append("Missing consumer name")

        if valid:
            debt.status = DebtStatus.ACTIVE

            await self.event_bus.publish(PipelineEvent(
                id=str(uuid.uuid4()),
                event_type=EventType.DEBT_VALIDATED,
                debt_id=debt.id,
                stage=PipelineStage.VALIDATE,
                timestamp=datetime.utcnow(),
                payload={"valid": True},
                correlation_id=debt.id,
            ))
        else:
            debt.metadata["validation_errors"] = errors

        return debt

    async def _stage_register(self, debt: DebtRecord) -> DebtRecord:
        """Register with Shadow Bureau"""

        debt = await self._transition_stage(debt, PipelineStage.REGISTER, "validation_complete")

        # Shadow Bureau registration
        registration = {
            "consumer_id": debt.consumer_id,
            "debt_id": debt.id,
            "creditor_id": debt.creditor_id,
            "balance": str(debt.current_balance),
            "registered_at": datetime.utcnow().isoformat(),
        }

        debt.metadata["shadow_bureau_registration"] = registration

        await self.event_bus.publish(PipelineEvent(
            id=str(uuid.uuid4()),
            event_type=EventType.DEBT_REGISTERED,
            debt_id=debt.id,
            stage=PipelineStage.REGISTER,
            timestamp=datetime.utcnow(),
            payload=registration,
            correlation_id=debt.id,
        ))

        return debt

    async def _stage_locate(self, debt: DebtRecord) -> DebtRecord:
        """Skip tracing and contact discovery"""

        debt = await self._transition_stage(debt, PipelineStage.LOCATE, "registration_complete")

        # Simulated skip tracing
        skip_trace_result = {
            "phone_verified": debt.consumer_phone is not None,
            "email_verified": debt.consumer_email is not None,
            "address_verified": debt.consumer_address is not None,
        }

        debt.metadata["skip_trace"] = skip_trace_result

        return debt

    async def _stage_enrich(self, debt: DebtRecord) -> DebtRecord:
        """Data enrichment"""

        debt = await self._transition_stage(debt, PipelineStage.ENRICH, "locate_complete")

        # Simulated enrichment
        enrichment = {
            "income_estimate": 45000,
            "employment_status": "employed",
            "debt_to_income": 0.35,
        }

        debt.metadata["enrichment"] = enrichment

        return debt

    async def _stage_score(self, debt: DebtRecord) -> DebtRecord:
        """ML scoring"""

        debt = await self._transition_stage(debt, PipelineStage.SCORE, "enrichment_complete")

        # Simulated ML scoring
        import random
        debt.recovery_probability = random.uniform(0.2, 0.8)
        debt.optimal_settlement_rate = random.uniform(0.3, 0.7)
        debt.risk_score = random.uniform(0.1, 0.9)

        # Set optimal channel
        if debt.consumer_phone:
            debt.optimal_channel = ChannelType.SMS
        elif debt.consumer_email:
            debt.optimal_channel = ChannelType.EMAIL

        debt.optimal_contact_time = 14  # 2 PM

        return debt

    async def _stage_contact(self, debt: DebtRecord) -> DebtRecord:
        """Contact attempts"""

        debt = await self._transition_stage(debt, PipelineStage.CONTACT, "scoring_complete")

        # Initiate contact
        result = await self.contact.initiate_contact(debt)

        debt.contact_attempts += 1
        debt.last_contact = datetime.utcnow()

        if result.get("success"):
            debt.status = DebtStatus.CONTACTED
            debt = await self._transition_stage(debt, PipelineStage.ENGAGE, "contact_success")

        return debt

    async def _stage_negotiate(self, debt: DebtRecord) -> DebtRecord:
        """Settlement negotiation"""

        debt = await self._transition_stage(debt, PipelineStage.NEGOTIATE, "engagement_complete")
        debt.status = DebtStatus.NEGOTIATING

        # Generate offer
        offer = await self.settlement.generate_offer(debt)
        debt.current_offer = Decimal(offer["offer"]["amount"])

        # Simulate consumer response (for demo)
        import random
        if random.random() < debt.recovery_probability:
            # Consumer accepts
            result = await self.settlement.process_response(offer["offer_id"], "accept")

            debt = await self._transition_stage(debt, PipelineStage.APPROVE, "offer_accepted")

            # Approve settlement
            approval = await self.settlement.approve_settlement(debt, debt.current_offer)

            if approval.get("approved"):
                debt.settlement_amount = debt.current_offer
                debt.status = DebtStatus.SETTLING

        return debt

    async def _stage_collect(self, debt: DebtRecord) -> DebtRecord:
        """Payment collection"""

        debt = await self._transition_stage(debt, PipelineStage.COLLECT, "settlement_approved")

        # Initiate payment
        payment_method = {"type": "simulated", "token": "sim_token"}
        result = await self.payment.initiate_payment(
            debt,
            debt.settlement_amount,
            payment_method
        )

        if result.get("success"):
            debt.total_paid = debt.settlement_amount

            debt = await self._transition_stage(debt, PipelineStage.VERIFY, "payment_received")
            debt = await self._transition_stage(debt, PipelineStage.RECONCILE, "payment_verified")

            debt.status = DebtStatus.COLLECTED

        return debt

    async def _stage_close(self, debt: DebtRecord) -> DebtRecord:
        """Account closure"""

        debt = await self._transition_stage(debt, PipelineStage.CLOSE, "reconciliation_complete")

        # Get settlement record
        settlement_record = self.settlement._approved_settlements.get(debt.id, {})

        # Complete resolution
        resolution = await self.resolution.complete_settlement(
            debt,
            settlement_record,
            debt.total_paid
        )

        debt.status = DebtStatus.CLOSED
        debt.metadata["resolution"] = resolution

        # Notify client
        await self.resolution.notify_client(debt, resolution)

        return debt

    async def _stage_restore(self, debt: DebtRecord) -> DebtRecord:
        """Credit restoration"""

        debt = await self._transition_stage(debt, PipelineStage.RESTORE, "closure_complete")

        resolution = debt.metadata.get("resolution", {})

        # Issue restoration certificate
        certificate = await self.resolution.issue_restoration_certificate(debt, resolution)
        debt.metadata["restoration_certificate"] = certificate

        debt = await self._transition_stage(debt, PipelineStage.REPORT, "restoration_issued")

        # Trigger bureau reporting
        report = await self.resolution.trigger_bureau_report(debt, resolution)
        debt.metadata["bureau_report"] = report

        debt.status = DebtStatus.RESTORED

        return debt

    # Default handlers
    def _default_validator(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Default validator"""
        if not data.get("balance") and not data.get("original_balance"):
            return False, "Missing balance"
        return True, None

    async def _default_sms_handler(
        self,
        debt: DebtRecord,
        template: Optional[str],
        strategy: Optional[Dict]
    ) -> Dict[str, Any]:
        """Default SMS handler"""
        return {"success": True, "message_id": f"sms_{uuid.uuid4().hex[:8]}"}

    async def _default_email_handler(
        self,
        debt: DebtRecord,
        template: Optional[str],
        strategy: Optional[Dict]
    ) -> Dict[str, Any]:
        """Default email handler"""
        return {"success": True, "message_id": f"email_{uuid.uuid4().hex[:8]}"}

    async def _default_voice_handler(
        self,
        debt: DebtRecord,
        template: Optional[str],
        strategy: Optional[Dict]
    ) -> Dict[str, Any]:
        """Default voice handler"""
        return {"success": True, "call_id": f"call_{uuid.uuid4().hex[:8]}"}

    # Public API
    def get_debt(self, debt_id: str) -> Optional[DebtRecord]:
        """Get a debt by ID"""
        return self._debts.get(debt_id)

    def get_all_debts(self) -> List[DebtRecord]:
        """Get all debts"""
        return list(self._debts.values())

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get overall pipeline status"""

        stage_counts = defaultdict(int)
        status_counts = defaultdict(int)

        for debt in self._debts.values():
            stage_counts[debt.stage.value] += 1
            status_counts[debt.status.value] += 1

        return {
            "total_debts": len(self._debts),
            "active_workflows": len(self._active_workflows),
            "by_stage": dict(stage_counts),
            "by_status": dict(status_counts),
            "metrics": self.monitor.get_metrics(),
            "bottlenecks": self.monitor.identify_bottlenecks(),
        }

    def get_debt_timeline(self, debt_id: str) -> List[Dict]:
        """Get timeline of events for a debt"""

        events = self.event_bus.get_events_by_debt(debt_id)
        transitions = self.state_machine.get_history(debt_id)
        contacts = self.contact.get_contact_history(debt_id)

        timeline = []

        for event in events:
            timeline.append({
                "type": "event",
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "stage": event.stage.value,
                "payload": event.payload,
            })

        for transition in transitions:
            timeline.append({
                "type": "transition",
                "timestamp": transition.timestamp.isoformat(),
                "from_stage": transition.from_stage.value,
                "to_stage": transition.to_stage.value,
                "trigger": transition.trigger,
            })

        for contact in contacts:
            timeline.append({
                "type": "contact",
                "timestamp": contact["timestamp"],
                "channel": contact["channel"],
                "result": contact["result"],
            })

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])

        return timeline


# =============================================================================
# DEMONSTRATION
# =============================================================================

async def run_demo():
    """
    Demonstrate the complete debt lifecycle through the pipeline

    This demo shows:
    1. Debt ingestion from creditor
    2. Validation and Shadow Bureau registration
    3. Skip tracing and enrichment
    4. ML scoring and channel optimization
    5. Contact orchestration
    6. Settlement negotiation
    7. Payment processing
    8. Account closure and credit restoration
    """

    print("=" * 80)
    print("QUAN MASTER PIPELINE ORCHESTRATOR - DEMONSTRATION")
    print("=" * 80)
    print()

    # Initialize orchestrator
    orchestrator = MasterPipelineOrchestrator()

    print("Pipeline initialized with components:")
    print("  - Event Bus (async inter-module communication)")
    print("  - State Machine (workflow management)")
    print("  - Ingestion Pipeline (multi-source data intake)")
    print("  - Contact Orchestrator (multi-channel outreach)")
    print("  - Settlement Pipeline (negotiation management)")
    print("  - Payment Pipeline (collection processing)")
    print("  - Resolution Pipeline (closure and restoration)")
    print("  - Pipeline Monitor (real-time metrics)")
    print("  - Scaling Controller (throughput management)")
    print()

    # Sample debt data
    sample_debt = {
        "account_id": "ACC-2024-001234",
        "creditor_name": "FastCash BNPL",
        "consumer_name": "John Smith",
        "debtor_email": "john.smith@email.com",
        "debtor_phone": "+1-555-0123",
        "debtor_address": {
            "street": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "zip": "78701"
        },
        "balance": 487.50,
        "original_balance": 500.00,
        "days_overdue": 45,
        "charge_off_date": datetime(2024, 11, 1),
        "metadata": {
            "original_purchase": "Electronics",
            "payment_history": ["partial_payment"],
        }
    }

    print("=" * 80)
    print("STAGE 1: DEBT INGESTION")
    print("=" * 80)
    print()
    print("Incoming debt from creditor:")
    print(f"  Account ID: {sample_debt['account_id']}")
    print(f"  Creditor: {sample_debt['creditor_name']}")
    print(f"  Consumer: {sample_debt['consumer_name']}")
    print(f"  Balance: ${sample_debt['balance']:.2f}")
    print(f"  Days Overdue: {sample_debt['days_overdue']}")
    print()

    # Ingest the debt
    debt, error = await orchestrator.ingest_debt(
        sample_debt,
        source_type="bnpl",
        creditor_id="CRED-001"
    )

    if error:
        print(f"Ingestion error: {error}")
        return

    print(f"Debt ingested successfully!")
    print(f"  Internal ID: {debt.id}")
    print(f"  Initial Stage: {debt.stage.value}")
    print(f"  Initial Status: {debt.status.value}")
    print()

    # Wait for workflow to progress
    print("=" * 80)
    print("STAGE 2: AUTOMATED WORKFLOW PROCESSING")
    print("=" * 80)
    print()
    print("Workflow stages:")

    # Monitor progress
    for i in range(30):
        await asyncio.sleep(0.1)

        current_debt = orchestrator.get_debt(debt.id)
        if current_debt:
            if i % 5 == 0:
                print(f"  [{i/10:.1f}s] Stage: {current_debt.stage.value}, Status: {current_debt.status.value}")

            if current_debt.status == DebtStatus.RESTORED:
                break

    print()

    # Get final state
    final_debt = orchestrator.get_debt(debt.id)

    print("=" * 80)
    print("STAGE 3: FINAL RESULTS")
    print("=" * 80)
    print()
    print("Debt lifecycle completed!")
    print()
    print("Final State:")
    print(f"  Stage: {final_debt.stage.value}")
    print(f"  Status: {final_debt.status.value}")
    print(f"  Recovery Probability: {final_debt.recovery_probability:.2%}")
    print(f"  Settlement Rate: {final_debt.optimal_settlement_rate:.2%}")
    print()

    if final_debt.settlement_amount:
        print("Settlement Details:")
        print(f"  Original Balance: ${final_debt.original_balance:.2f}")
        print(f"  Settlement Amount: ${final_debt.settlement_amount:.2f}")
        print(f"  Savings: ${final_debt.original_balance - final_debt.settlement_amount:.2f}")
        print(f"  Total Paid: ${final_debt.total_paid:.2f}")
        print()

    if final_debt.metadata.get("restoration_certificate"):
        cert = final_debt.metadata["restoration_certificate"]
        print("Restoration Certificate:")
        print(f"  Certificate ID: {cert['certificate_id']}")
        print(f"  Hash: {cert['certificate_hash']}")
        print(f"  Issued: {cert['issued_at']}")
        print()

    if final_debt.metadata.get("bureau_report"):
        report = final_debt.metadata["bureau_report"]
        print("Bureau Reporting:")
        print(f"  Report ID: {report['report_id']}")
        print(f"  Bureaus: {', '.join(report['bureaus'])}")
        print(f"  Status: {report['status']}")
        print()

    # Show timeline
    print("=" * 80)
    print("STAGE 4: EVENT TIMELINE")
    print("=" * 80)
    print()

    timeline = orchestrator.get_debt_timeline(debt.id)
    for i, event in enumerate(timeline[:15]):  # Show first 15 events
        event_time = event["timestamp"]
        if isinstance(event_time, str):
            event_time = event_time.split("T")[1][:8]

        if event["type"] == "transition":
            print(f"  {event_time} | TRANSITION: {event['from_stage']} -> {event['to_stage']}")
        elif event["type"] == "event":
            print(f"  {event_time} | EVENT: {event['event_type']}")
        elif event["type"] == "contact":
            print(f"  {event_time} | CONTACT: {event['channel']} - {'Success' if event['result'].get('success') else 'Failed'}")

    if len(timeline) > 15:
        print(f"  ... and {len(timeline) - 15} more events")
    print()

    # Show pipeline status
    print("=" * 80)
    print("STAGE 5: PIPELINE STATUS")
    print("=" * 80)
    print()

    status = orchestrator.get_pipeline_status()
    print(f"Total Debts Processed: {status['total_debts']}")
    print(f"Active Workflows: {status['active_workflows']}")
    print()

    print("Debts by Stage:")
    for stage, count in status["by_stage"].items():
        print(f"  {stage}: {count}")
    print()

    print("Debts by Status:")
    for stat, count in status["by_status"].items():
        print(f"  {stat}: {count}")
    print()

    if status["bottlenecks"]:
        print("Bottlenecks Identified:")
        for bottleneck in status["bottlenecks"]:
            print(f"  - {bottleneck['stage']}: {bottleneck['type']}")
    else:
        print("No bottlenecks identified.")
    print()

    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("The Master Pipeline Orchestrator successfully processed a debt through:")
    print("  1. Ingestion and validation")
    print("  2. Shadow Bureau registration")
    print("  3. Skip tracing and data enrichment")
    print("  4. ML-based scoring and optimization")
    print("  5. Multi-channel contact orchestration")
    print("  6. Settlement negotiation")
    print("  7. Payment processing")
    print("  8. Account closure and credit restoration")
    print("  9. Bureau reporting")
    print()
    print("All events were tracked, metrics were collected, and the workflow")
    print("was managed through a state machine ensuring proper transitions.")

    return orchestrator, final_debt


# =============================================================================
# BATCH PROCESSING DEMO
# =============================================================================

async def run_batch_demo():
    """Demonstrate batch processing of a portfolio"""

    print("=" * 80)
    print("BATCH PROCESSING DEMONSTRATION")
    print("=" * 80)
    print()

    orchestrator = MasterPipelineOrchestrator()

    # Generate sample portfolio
    import random

    portfolio = []
    for i in range(10):
        portfolio.append({
            "account_id": f"ACC-2024-{i+1000:04d}",
            "creditor_name": random.choice(["FastCash BNPL", "QuickPay", "EasyCredit"]),
            "consumer_name": f"Consumer {i+1}",
            "debtor_email": f"consumer{i+1}@email.com",
            "debtor_phone": f"+1-555-{random.randint(1000, 9999):04d}",
            "balance": random.uniform(100, 1000),
            "days_overdue": random.randint(30, 180),
        })

    print(f"Processing portfolio of {len(portfolio)} debts...")
    print()

    # Ingest portfolio
    result = await orchestrator.ingest_portfolio(
        portfolio,
        source_type="bnpl",
        creditor_id="CRED-001"
    )

    print(f"Ingestion Results:")
    print(f"  Total: {result['total']}")
    print(f"  Successful: {result['successful']}")
    print(f"  Failed: {result['failed']}")
    print()

    # Wait for workflows
    print("Processing workflows...")
    for i in range(50):
        await asyncio.sleep(0.1)

        status = orchestrator.get_pipeline_status()
        active = status["active_workflows"]

        if i % 10 == 0:
            print(f"  [{i/10:.0f}s] Active workflows: {active}")

        if active == 0:
            break

    print()

    # Final status
    status = orchestrator.get_pipeline_status()

    print("Final Pipeline Status:")
    print(f"  Total Debts: {status['total_debts']}")
    print()

    print("By Status:")
    for stat, count in status["by_status"].items():
        print(f"  {stat}: {count}")

    # Calculate totals
    total_collected = Decimal("0")
    total_balance = Decimal("0")

    for debt in orchestrator.get_all_debts():
        total_balance += debt.original_balance
        total_collected += debt.total_paid

    print()
    print(f"Financial Summary:")
    print(f"  Total Portfolio Value: ${total_balance:.2f}")
    print(f"  Total Collected: ${total_collected:.2f}")
    print(f"  Collection Rate: {(total_collected / total_balance * 100) if total_balance > 0 else 0:.1f}%")

    return orchestrator


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print()
    print("QUAN Recovery - Master Pipeline Orchestrator")
    print("Central Nervous System for Collections Operations")
    print()

    # Run single debt demo
    asyncio.run(run_demo())

    print()
    print()

    # Run batch demo
    asyncio.run(run_batch_demo())
