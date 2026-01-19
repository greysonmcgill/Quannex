"""
Master Orchestration Engine - The Central Nervous System of the Shadow Bureau

This engine orchestrates all Shadow Bureau components into a unified, event-driven
collection platform. It manages the complete lifecycle of every account from
intake to resolution.

Architecture:
    +-------------------+
    |   Event Bus       |  <-- Kafka-style pub/sub
    +-------------------+
           |
    +------+------+
    |             |
    v             v
+--------+  +----------+
| Sagas  |  | Handlers |
+--------+  +----------+
    |             |
    +------+------+
           |
    +------v------+
    | Components  |
    +-------------+
    | Empathy     |
    | Ledger      |
    | Rehab       |
    | Payment     |
    | Compliance  |
    | Settlement  |
    | Marketplace |
    +-------------+

Key Features:
1. Account Lifecycle State Machine
2. Event Sourcing for Full Audit Trail
3. Saga Pattern for Distributed Transactions
4. Real-Time Decisioning Engine
5. Component Health Monitoring
6. Scalability with Backpressure
7. Batch Processing for Scheduled Operations
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Type, Union
from functools import wraps
import heapq

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# ACCOUNT LIFECYCLE STATE MACHINE
# =============================================================================

class AccountState(Enum):
    """Account states in the collection lifecycle"""
    # Intake Phase
    INTAKE = "intake"                    # Initial data received
    VALIDATING = "validating"            # Data validation in progress
    SCORING = "scoring"                  # AI scoring underway

    # Strategy Phase
    STRATEGY_PENDING = "strategy_pending"  # Awaiting strategy assignment
    STRATEGY_ASSIGNED = "strategy_assigned"  # Strategy determined

    # Active Collection Phase
    CONTACT_QUEUE = "contact_queue"      # Ready for contact
    CONTACTING = "contacting"            # Contact in progress
    CONTACTED = "contacted"              # Contact made, awaiting response
    RESPONDING = "responding"            # Consumer responding
    NEGOTIATING = "negotiating"          # Active negotiation

    # Resolution Phase
    PAYMENT_PENDING = "payment_pending"  # Payment arrangement made
    PAYMENT_PROCESSING = "payment_processing"  # Processing payment
    PARTIAL_PAID = "partial_paid"        # Partial payment received
    PAID_IN_FULL = "paid_in_full"        # Full payment received
    SETTLED = "settled"                  # Settlement accepted

    # Terminal States
    RESOLVED = "resolved"                # Successfully resolved
    WRITTEN_OFF = "written_off"          # Deemed uncollectible
    DISPUTED = "disputed"                # Under dispute
    BANKRUPTCY = "bankruptcy"            # Bankruptcy filed
    DECEASED = "deceased"                # Consumer deceased

    # Special States
    PAUSED = "paused"                    # Temporarily paused
    ESCALATED = "escalated"              # Escalated to supervisor
    RE_ENGAGEMENT = "re_engagement"      # Re-engagement campaign
    COMPLIANCE_HOLD = "compliance_hold"  # Compliance review required


class StateTransition:
    """Valid state transitions with conditions"""

    TRANSITIONS: Dict[AccountState, List[AccountState]] = {
        AccountState.INTAKE: [AccountState.VALIDATING],
        AccountState.VALIDATING: [AccountState.SCORING, AccountState.COMPLIANCE_HOLD],
        AccountState.SCORING: [AccountState.STRATEGY_PENDING],
        AccountState.STRATEGY_PENDING: [AccountState.STRATEGY_ASSIGNED],
        AccountState.STRATEGY_ASSIGNED: [AccountState.CONTACT_QUEUE],
        AccountState.CONTACT_QUEUE: [AccountState.CONTACTING, AccountState.PAUSED],
        AccountState.CONTACTING: [
            AccountState.CONTACTED, AccountState.CONTACT_QUEUE,
            AccountState.PAUSED, AccountState.COMPLIANCE_HOLD
        ],
        AccountState.CONTACTED: [
            AccountState.RESPONDING, AccountState.CONTACT_QUEUE,
            AccountState.RE_ENGAGEMENT, AccountState.WRITTEN_OFF
        ],
        AccountState.RESPONDING: [
            AccountState.NEGOTIATING, AccountState.DISPUTED,
            AccountState.PAYMENT_PENDING
        ],
        AccountState.NEGOTIATING: [
            AccountState.PAYMENT_PENDING, AccountState.SETTLED,
            AccountState.CONTACTED, AccountState.ESCALATED
        ],
        AccountState.PAYMENT_PENDING: [
            AccountState.PAYMENT_PROCESSING, AccountState.NEGOTIATING,
            AccountState.CONTACTED
        ],
        AccountState.PAYMENT_PROCESSING: [
            AccountState.PARTIAL_PAID, AccountState.PAID_IN_FULL,
            AccountState.PAYMENT_PENDING
        ],
        AccountState.PARTIAL_PAID: [
            AccountState.PAYMENT_PENDING, AccountState.PAID_IN_FULL,
            AccountState.NEGOTIATING
        ],
        AccountState.PAID_IN_FULL: [AccountState.RESOLVED],
        AccountState.SETTLED: [AccountState.RESOLVED],
        AccountState.PAUSED: [
            AccountState.CONTACT_QUEUE, AccountState.RE_ENGAGEMENT,
            AccountState.WRITTEN_OFF
        ],
        AccountState.ESCALATED: [
            AccountState.NEGOTIATING, AccountState.WRITTEN_OFF,
            AccountState.COMPLIANCE_HOLD
        ],
        AccountState.RE_ENGAGEMENT: [
            AccountState.CONTACT_QUEUE, AccountState.WRITTEN_OFF
        ],
        AccountState.COMPLIANCE_HOLD: [
            AccountState.CONTACT_QUEUE, AccountState.WRITTEN_OFF,
            AccountState.DISPUTED
        ],
        AccountState.DISPUTED: [
            AccountState.CONTACT_QUEUE, AccountState.WRITTEN_OFF
        ],
    }

    @classmethod
    def can_transition(cls, from_state: AccountState, to_state: AccountState) -> bool:
        """Check if transition is valid"""
        valid_targets = cls.TRANSITIONS.get(from_state, [])
        return to_state in valid_targets


# =============================================================================
# EVENT DEFINITIONS
# =============================================================================

class EventType(Enum):
    """All event types in the system"""
    # Account Lifecycle Events
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_VALIDATED = "account.validated"
    ACCOUNT_SCORED = "account.scored"
    ACCOUNT_STRATEGY_ASSIGNED = "account.strategy_assigned"
    ACCOUNT_STATE_CHANGED = "account.state_changed"

    # Contact Events
    CONTACT_QUEUED = "contact.queued"
    CONTACT_INITIATED = "contact.initiated"
    CONTACT_DELIVERED = "contact.delivered"
    CONTACT_FAILED = "contact.failed"
    CONTACT_RESPONSE_RECEIVED = "contact.response_received"

    # Negotiation Events
    NEGOTIATION_STARTED = "negotiation.started"
    OFFER_MADE = "offer.made"
    OFFER_ACCEPTED = "offer.accepted"
    OFFER_REJECTED = "offer.rejected"
    COUNTEROFFER_RECEIVED = "counteroffer.received"

    # Payment Events
    PAYMENT_PROMISED = "payment.promised"
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_PARTIAL = "payment.partial"

    # Resolution Events
    ACCOUNT_RESOLVED = "account.resolved"
    ACCOUNT_WRITTEN_OFF = "account.written_off"
    ACCOUNT_DISPUTED = "account.disputed"

    # Rehabilitation Events
    TRUST_SCORE_UPDATED = "trust.score_updated"
    ACHIEVEMENT_EARNED = "achievement.earned"
    RESTORATION_ISSUED = "restoration.issued"

    # Compliance Events
    COMPLIANCE_CHECK_PASSED = "compliance.passed"
    COMPLIANCE_CHECK_FAILED = "compliance.failed"
    COMPLIANCE_HOLD_PLACED = "compliance.hold_placed"

    # System Events
    BATCH_JOB_STARTED = "batch.job_started"
    BATCH_JOB_COMPLETED = "batch.job_completed"
    COMPONENT_HEALTH_CHECK = "component.health_check"
    SAGA_STARTED = "saga.started"
    SAGA_COMPLETED = "saga.completed"
    SAGA_FAILED = "saga.failed"


@dataclass
class Event:
    """Base event structure for event sourcing"""
    event_id: str
    event_type: EventType
    aggregate_id: str  # Account ID or system identifier
    aggregate_type: str
    timestamp: datetime
    version: int
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "data": self.data,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    @classmethod
    def create(
        cls,
        event_type: EventType,
        aggregate_id: str,
        aggregate_type: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        version: int = 1,
    ) -> "Event":
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            timestamp=datetime.utcnow(),
            version=version,
            data=data,
            correlation_id=correlation_id or str(uuid.uuid4()),
            causation_id=causation_id,
        )


# =============================================================================
# EVENT BUS (KAFKA-STYLE)
# =============================================================================

class EventHandler(ABC):
    """Base class for event handlers"""

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event"""
        pass

    @property
    @abstractmethod
    def handled_events(self) -> List[EventType]:
        """List of event types this handler processes"""
        pass


@dataclass
class DeadLetterEntry:
    """Entry in the dead letter queue"""
    event: Event
    error: str
    handler: str
    attempts: int
    first_failure: datetime
    last_failure: datetime


class EventBus:
    """
    Kafka-style event bus with:
    - Topic-based pub/sub
    - Consumer groups
    - Dead letter queue
    - Event replay capability
    - Backpressure handling
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        max_retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        self.max_queue_size = max_queue_size
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds

        # Event storage for replay
        self._event_store: List[Event] = []
        self._event_store_lock = threading.Lock()

        # Handlers by event type
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)

        # Processing queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)

        # Dead letter queue
        self._dead_letter_queue: List[DeadLetterEntry] = []
        self._dlq_lock = threading.Lock()

        # Metrics
        self._events_published = 0
        self._events_processed = 0
        self._events_failed = 0

        # Control flags
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe a handler to its declared event types"""
        for event_type in handler.handled_events:
            self._handlers[event_type].append(handler)
            logger.debug(f"Handler {handler.__class__.__name__} subscribed to {event_type.value}")

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe a handler"""
        for event_type in handler.handled_events:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> bool:
        """
        Publish an event to the bus.
        Returns False if backpressure is applied.
        """
        # Store for replay
        with self._event_store_lock:
            self._event_store.append(event)

        # Check backpressure
        if self._queue.full():
            logger.warning(f"Event bus backpressure: queue full, rejecting {event.event_type.value}")
            return False

        try:
            await self._queue.put(event)
            self._events_published += 1
            return True
        except asyncio.QueueFull:
            return False

    async def start(self) -> None:
        """Start the event processing loop"""
        if self._running:
            return

        self._running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the event processing loop"""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped")

    async def _process_loop(self) -> None:
        """Main processing loop"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    async def _dispatch_event(self, event: Event, attempt: int = 1) -> None:
        """Dispatch event to all handlers"""
        handlers = self._handlers.get(event.event_type, [])

        for handler in handlers:
            try:
                await handler.handle(event)
                self._events_processed += 1
            except Exception as e:
                logger.error(
                    f"Handler {handler.__class__.__name__} failed for "
                    f"{event.event_type.value}: {e}"
                )

                if attempt < self.max_retry_attempts:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)
                    await self._dispatch_event(event, attempt + 1)
                else:
                    self._send_to_dlq(event, str(e), handler.__class__.__name__, attempt)

    def _send_to_dlq(
        self,
        event: Event,
        error: str,
        handler: str,
        attempts: int
    ) -> None:
        """Send failed event to dead letter queue"""
        now = datetime.utcnow()
        entry = DeadLetterEntry(
            event=event,
            error=error,
            handler=handler,
            attempts=attempts,
            first_failure=now,
            last_failure=now,
        )

        with self._dlq_lock:
            self._dead_letter_queue.append(entry)
            self._events_failed += 1

        logger.warning(f"Event {event.event_id} sent to DLQ after {attempts} attempts")

    def get_events_for_aggregate(
        self,
        aggregate_id: str,
        from_version: int = 0
    ) -> List[Event]:
        """Get all events for an aggregate (for replay/rehydration)"""
        with self._event_store_lock:
            return [
                e for e in self._event_store
                if e.aggregate_id == aggregate_id and e.version >= from_version
            ]

    def get_metrics(self) -> Dict[str, Any]:
        """Get event bus metrics"""
        return {
            "events_published": self._events_published,
            "events_processed": self._events_processed,
            "events_failed": self._events_failed,
            "queue_size": self._queue.qsize(),
            "queue_capacity": self.max_queue_size,
            "dead_letter_queue_size": len(self._dead_letter_queue),
            "handlers_registered": sum(len(h) for h in self._handlers.values()),
        }


# =============================================================================
# SAGA PATTERN FOR DISTRIBUTED TRANSACTIONS
# =============================================================================

class SagaState(Enum):
    """Saga execution states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SagaStep:
    """Individual step in a saga"""
    name: str
    execute: Callable[..., Coroutine]
    compensate: Callable[..., Coroutine]
    timeout_seconds: float = 30.0


@dataclass
class SagaExecution:
    """Tracks saga execution state"""
    saga_id: str
    saga_type: str
    state: SagaState
    context: Dict[str, Any]
    completed_steps: List[str]
    current_step: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Saga:
    """
    Saga pattern implementation for distributed transactions.

    Each saga consists of ordered steps with compensating actions.
    If any step fails, previous steps are compensated in reverse order.
    """

    def __init__(
        self,
        saga_type: str,
        steps: List[SagaStep],
        event_bus: EventBus,
    ):
        self.saga_type = saga_type
        self.steps = steps
        self.event_bus = event_bus

    async def execute(self, context: Dict[str, Any]) -> SagaExecution:
        """Execute the saga"""
        saga_id = str(uuid.uuid4())
        execution = SagaExecution(
            saga_id=saga_id,
            saga_type=self.saga_type,
            state=SagaState.RUNNING,
            context=context,
            completed_steps=[],
            current_step=None,
            started_at=datetime.utcnow(),
        )

        # Publish saga started event
        await self.event_bus.publish(Event.create(
            event_type=EventType.SAGA_STARTED,
            aggregate_id=saga_id,
            aggregate_type="saga",
            data={"saga_type": self.saga_type, "context": context},
        ))

        try:
            for step in self.steps:
                execution.current_step = step.name

                try:
                    # Execute step with timeout
                    result = await asyncio.wait_for(
                        step.execute(context),
                        timeout=step.timeout_seconds
                    )
                    context.update(result or {})
                    execution.completed_steps.append(step.name)

                except asyncio.TimeoutError:
                    raise Exception(f"Step {step.name} timed out")

            execution.state = SagaState.COMPLETED
            execution.completed_at = datetime.utcnow()

            await self.event_bus.publish(Event.create(
                event_type=EventType.SAGA_COMPLETED,
                aggregate_id=saga_id,
                aggregate_type="saga",
                data={"saga_type": self.saga_type, "result": context},
            ))

        except Exception as e:
            execution.error = str(e)
            execution.state = SagaState.COMPENSATING
            logger.error(f"Saga {saga_id} failed at step {execution.current_step}: {e}")

            # Compensate in reverse order
            await self._compensate(execution, context)

            await self.event_bus.publish(Event.create(
                event_type=EventType.SAGA_FAILED,
                aggregate_id=saga_id,
                aggregate_type="saga",
                data={"saga_type": self.saga_type, "error": str(e)},
            ))

        return execution

    async def _compensate(
        self,
        execution: SagaExecution,
        context: Dict[str, Any]
    ) -> None:
        """Execute compensating actions in reverse order"""
        for step_name in reversed(execution.completed_steps):
            step = next((s for s in self.steps if s.name == step_name), None)
            if step:
                try:
                    await step.compensate(context)
                    logger.info(f"Compensated step: {step_name}")
                except Exception as e:
                    logger.error(f"Compensation failed for {step_name}: {e}")

        execution.state = SagaState.FAILED
        execution.completed_at = datetime.utcnow()


# =============================================================================
# PRIORITY QUEUE FOR ACCOUNT WORKLOAD DISTRIBUTION
# =============================================================================

@dataclass
class PriorityAccount:
    """Account with priority for queue management"""
    account_id: str
    priority: float  # Higher = more urgent
    balance: Decimal
    days_past_due: int
    recovery_probability: float
    last_contact: Optional[datetime]
    next_action_time: datetime
    state: AccountState
    assigned_worker: Optional[str] = None

    def __lt__(self, other: "PriorityAccount") -> bool:
        # Higher priority = earlier processing
        return self.priority > other.priority


class PriorityQueueManager:
    """
    Manages account prioritization and workload distribution.

    Priority factors:
    - Balance (higher = higher priority)
    - Days past due (older = higher priority up to a point)
    - Recovery probability (higher = higher priority)
    - Time since last contact
    - Strategy urgency
    """

    def __init__(self):
        self._queue: List[PriorityAccount] = []
        self._by_id: Dict[str, PriorityAccount] = {}
        self._lock = threading.Lock()

        # Worker assignments
        self._workers: Dict[str, List[str]] = defaultdict(list)  # worker_id -> [account_ids]
        self._max_accounts_per_worker = 100

    def calculate_priority(
        self,
        balance: Decimal,
        days_past_due: int,
        recovery_probability: float,
        last_contact: Optional[datetime],
        urgency_boost: float = 0.0,
    ) -> float:
        """Calculate account priority score"""
        # Balance factor (0-30 points, log scale for micro-debts)
        balance_score = min(30, float(balance) / 50)

        # DPD factor (0-25 points, peaks at 45-90 days)
        if days_past_due < 30:
            dpd_score = days_past_due / 2
        elif days_past_due < 90:
            dpd_score = 15 + (days_past_due - 30) / 6
        else:
            dpd_score = max(5, 25 - (days_past_due - 90) / 30)

        # Recovery probability (0-25 points)
        recovery_score = recovery_probability * 25

        # Recency factor (0-20 points, higher if not contacted recently)
        if last_contact:
            days_since = (datetime.utcnow() - last_contact).days
            recency_score = min(20, days_since / 2)
        else:
            recency_score = 20  # Never contacted = high priority

        return balance_score + dpd_score + recovery_score + recency_score + urgency_boost

    def add_account(self, account: PriorityAccount) -> None:
        """Add account to priority queue"""
        with self._lock:
            if account.account_id in self._by_id:
                self.update_priority(account.account_id, account.priority)
                return

            heapq.heappush(self._queue, account)
            self._by_id[account.account_id] = account

    def get_next_account(self, worker_id: Optional[str] = None) -> Optional[PriorityAccount]:
        """Get next highest priority account"""
        with self._lock:
            # Filter by action time
            now = datetime.utcnow()
            ready_accounts = [
                a for a in self._queue
                if a.next_action_time <= now and a.assigned_worker is None
            ]

            if not ready_accounts:
                return None

            # Sort by priority and get highest
            ready_accounts.sort(reverse=True)
            account = ready_accounts[0]

            # Assign to worker if specified
            if worker_id:
                if len(self._workers[worker_id]) < self._max_accounts_per_worker:
                    account.assigned_worker = worker_id
                    self._workers[worker_id].append(account.account_id)
                else:
                    return None  # Worker at capacity

            return account

    def get_batch(
        self,
        batch_size: int,
        worker_id: Optional[str] = None
    ) -> List[PriorityAccount]:
        """Get batch of accounts for processing"""
        batch = []
        for _ in range(batch_size):
            account = self.get_next_account(worker_id)
            if account:
                batch.append(account)
            else:
                break
        return batch

    def update_priority(self, account_id: str, new_priority: float) -> None:
        """Update account priority"""
        with self._lock:
            if account_id in self._by_id:
                account = self._by_id[account_id]
                account.priority = new_priority
                heapq.heapify(self._queue)

    def remove_account(self, account_id: str) -> None:
        """Remove account from queue"""
        with self._lock:
            if account_id in self._by_id:
                account = self._by_id.pop(account_id)
                self._queue = [a for a in self._queue if a.account_id != account_id]
                heapq.heapify(self._queue)

                # Remove from worker assignment
                if account.assigned_worker:
                    if account_id in self._workers[account.assigned_worker]:
                        self._workers[account.assigned_worker].remove(account_id)

    def release_account(self, account_id: str) -> None:
        """Release account back to queue for reassignment"""
        with self._lock:
            if account_id in self._by_id:
                account = self._by_id[account_id]
                if account.assigned_worker:
                    if account_id in self._workers[account.assigned_worker]:
                        self._workers[account.assigned_worker].remove(account_id)
                    account.assigned_worker = None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self._lock:
            now = datetime.utcnow()
            ready = sum(1 for a in self._queue if a.next_action_time <= now)

            return {
                "total_queued": len(self._queue),
                "ready_for_action": ready,
                "assigned": sum(1 for a in self._queue if a.assigned_worker),
                "unassigned": sum(1 for a in self._queue if not a.assigned_worker),
                "workers_active": len([w for w, accts in self._workers.items() if accts]),
                "avg_priority": sum(a.priority for a in self._queue) / len(self._queue) if self._queue else 0,
            }


# =============================================================================
# REAL-TIME DECISIONING ENGINE
# =============================================================================

class DecisionType(Enum):
    """Types of real-time decisions"""
    CHANNEL_SELECTION = "channel_selection"
    OFFER_OPTIMIZATION = "offer_optimization"
    STRATEGY_ADJUSTMENT = "strategy_adjustment"
    TIMING_OPTIMIZATION = "timing_optimization"
    ESCALATION_CHECK = "escalation_check"
    COMPLIANCE_VALIDATION = "compliance_validation"


@dataclass
class Decision:
    """Real-time decision result"""
    decision_id: str
    decision_type: DecisionType
    account_id: str
    recommendation: str
    confidence: float
    alternatives: List[Dict[str, Any]]
    reasoning: List[str]
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RealTimeDecisionEngine:
    """
    Real-time decisioning for:
    - Account prioritization
    - Channel selection
    - Offer optimization
    - Dynamic strategy adjustment
    """

    def __init__(self):
        self._decision_cache: Dict[str, Decision] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        self._decision_count = 0
        self._total_latency_ms = 0.0

    async def decide_channel(
        self,
        account_id: str,
        account_data: Dict[str, Any],
        contact_history: List[Dict[str, Any]],
    ) -> Decision:
        """Select optimal contact channel"""
        start_time = time.time()

        # Extract features
        has_phone = account_data.get("phone") is not None
        has_email = account_data.get("email") is not None
        has_app = account_data.get("has_mobile_app", False)
        age = account_data.get("age", 35)
        is_digital_native = account_data.get("is_digital_native", True)
        balance = Decimal(str(account_data.get("balance", 0)))

        # Channel scoring
        scores = {}
        reasoning = []

        if has_phone:
            sms_score = 0.7
            if is_digital_native:
                sms_score += 0.2
            if age < 35:
                sms_score += 0.1
            scores["sms"] = sms_score
            reasoning.append(f"SMS score: {sms_score:.2f} (digital native: {is_digital_native})")

        if has_email:
            email_score = 0.5
            if balance > 200:
                email_score += 0.2
            if len([c for c in contact_history if c.get("channel") == "sms"]) > 2:
                email_score += 0.15  # Diversify after SMS attempts
            scores["email"] = email_score
            reasoning.append(f"Email score: {email_score:.2f}")

        if has_app:
            push_score = 0.65
            if is_digital_native:
                push_score += 0.15
            scores["push"] = push_score
            reasoning.append(f"Push score: {push_score:.2f}")

        if balance > 300:
            voice_score = 0.4
            if account_data.get("days_past_due", 0) > 60:
                voice_score += 0.3
            scores["voice"] = voice_score
            reasoning.append(f"Voice score: {voice_score:.2f}")

        # Select best channel
        if not scores:
            best_channel = "mail"
            confidence = 0.3
        else:
            best_channel = max(scores, key=scores.get)
            confidence = scores[best_channel]

        latency_ms = (time.time() - start_time) * 1000

        decision = Decision(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.CHANNEL_SELECTION,
            account_id=account_id,
            recommendation=best_channel,
            confidence=confidence,
            alternatives=[
                {"channel": ch, "score": sc}
                for ch, sc in sorted(scores.items(), key=lambda x: -x[1])
            ],
            reasoning=reasoning,
            latency_ms=latency_ms,
        )

        self._record_decision(decision)
        return decision

    async def optimize_offer(
        self,
        account_id: str,
        balance: Decimal,
        recovery_probability: float,
        negotiation_round: int,
        previous_offers: List[float],
    ) -> Decision:
        """Optimize settlement offer"""
        start_time = time.time()

        reasoning = []

        # Base offer calculation
        base_offer_pct = max(0.30, min(0.95, recovery_probability + 0.2))
        reasoning.append(f"Base offer from recovery prob: {base_offer_pct:.2%}")

        # Adjust for negotiation round
        round_adjustment = negotiation_round * 0.05
        offer_pct = max(0.25, base_offer_pct - round_adjustment)
        reasoning.append(f"Round {negotiation_round} adjustment: -{round_adjustment:.2%}")

        # Adjust for balance size
        if float(balance) < 100:
            offer_pct = max(0.40, offer_pct)  # Higher floor for micro-debts
            reasoning.append("Micro-debt floor applied: 40%")

        # Generate alternatives
        alternatives = [
            {"type": "lump_sum", "percentage": offer_pct, "amount": float(balance * Decimal(str(offer_pct)))},
            {"type": "two_pay", "percentage": offer_pct + 0.10, "amount": float(balance * Decimal(str(offer_pct + 0.10)))},
            {"type": "payment_plan", "percentage": offer_pct + 0.20, "amount": float(balance * Decimal(str(offer_pct + 0.20)))},
        ]

        latency_ms = (time.time() - start_time) * 1000

        decision = Decision(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.OFFER_OPTIMIZATION,
            account_id=account_id,
            recommendation=f"{offer_pct:.2%} settlement ({float(balance * Decimal(str(offer_pct))):.2f})",
            confidence=min(0.95, recovery_probability + 0.1),
            alternatives=alternatives,
            reasoning=reasoning,
            latency_ms=latency_ms,
        )

        self._record_decision(decision)
        return decision

    async def should_escalate(
        self,
        account_id: str,
        contact_attempts: int,
        days_without_response: int,
        balance: Decimal,
        current_state: AccountState,
    ) -> Decision:
        """Determine if account should be escalated"""
        start_time = time.time()

        reasons = []
        escalate_score = 0.0

        # Contact attempt threshold
        if contact_attempts >= 5:
            escalate_score += 0.3
            reasons.append(f"High contact attempts: {contact_attempts}")

        # Days without response
        if days_without_response > 14:
            escalate_score += 0.25
            reasons.append(f"No response in {days_without_response} days")

        # Balance threshold
        if float(balance) > 500:
            escalate_score += 0.2
            reasons.append(f"High balance: ${balance}")

        # State considerations
        if current_state == AccountState.NEGOTIATING:
            escalate_score += 0.15
            reasons.append("Stalled negotiation")

        should_escalate = escalate_score >= 0.5

        latency_ms = (time.time() - start_time) * 1000

        decision = Decision(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.ESCALATION_CHECK,
            account_id=account_id,
            recommendation="escalate" if should_escalate else "continue",
            confidence=escalate_score if should_escalate else 1 - escalate_score,
            alternatives=[],
            reasoning=reasons,
            latency_ms=latency_ms,
        )

        self._record_decision(decision)
        return decision

    def _record_decision(self, decision: Decision) -> None:
        """Record decision for metrics"""
        self._decision_count += 1
        self._total_latency_ms += decision.latency_ms
        self._decision_cache[decision.decision_id] = decision

    def get_metrics(self) -> Dict[str, Any]:
        """Get decision engine metrics"""
        return {
            "total_decisions": self._decision_count,
            "avg_latency_ms": self._total_latency_ms / self._decision_count if self._decision_count > 0 else 0,
            "cache_size": len(self._decision_cache),
        }


# =============================================================================
# CIRCUIT BREAKER FOR EXTERNAL SERVICES
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for external service calls"""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
            return self._state

    def can_execute(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
            return False
        return False

    def record_success(self) -> None:
        with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name}: Closed (recovered)")

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: Re-opened")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: Opened")


# =============================================================================
# COMPONENT HEALTH MONITORING
# =============================================================================

@dataclass
class ComponentHealth:
    """Health status of a component"""
    name: str
    status: str  # healthy, degraded, unhealthy
    latency_ms: float
    error_rate: float
    last_check: datetime
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """
    Monitors health of all Shadow Bureau components:
    - Empathy Engine
    - Live Ledger
    - Rehabilitation Loop
    - Payment Engine
    - Compliance Orchestrator
    - Settlement Engine
    - Asset Marketplace
    """

    def __init__(self):
        self._components: Dict[str, ComponentHealth] = {}
        self._check_interval = 30  # seconds
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

        # Health check functions
        self._health_checks: Dict[str, Callable[[], Coroutine]] = {}

    def register_component(
        self,
        name: str,
        health_check: Callable[[], Coroutine],
    ) -> None:
        """Register a component for monitoring"""
        self._health_checks[name] = health_check
        self._components[name] = ComponentHealth(
            name=name,
            status="unknown",
            latency_ms=0,
            error_rate=0,
            last_check=datetime.utcnow(),
        )

    async def start(self) -> None:
        """Start health monitoring"""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("Health monitor started")

    async def stop(self) -> None:
        """Stop health monitoring"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

    async def _check_loop(self) -> None:
        """Periodic health check loop"""
        while self._running:
            await self._run_all_checks()
            await asyncio.sleep(self._check_interval)

    async def _run_all_checks(self) -> None:
        """Run health checks on all components"""
        for name, check_func in self._health_checks.items():
            await self._run_check(name, check_func)

    async def _run_check(
        self,
        name: str,
        check_func: Callable[[], Coroutine],
    ) -> None:
        """Run single health check"""
        start_time = time.time()

        try:
            result = await asyncio.wait_for(check_func(), timeout=10.0)
            latency_ms = (time.time() - start_time) * 1000

            self._components[name] = ComponentHealth(
                name=name,
                status="healthy",
                latency_ms=latency_ms,
                error_rate=0,
                last_check=datetime.utcnow(),
                metadata=result if isinstance(result, dict) else {},
            )

        except asyncio.TimeoutError:
            self._components[name].status = "unhealthy"
            self._components[name].last_error = "Health check timeout"
            self._components[name].last_check = datetime.utcnow()

        except Exception as e:
            self._components[name].status = "unhealthy"
            self._components[name].last_error = str(e)
            self._components[name].last_check = datetime.utcnow()

    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        components = list(self._components.values())

        healthy_count = sum(1 for c in components if c.status == "healthy")
        degraded_count = sum(1 for c in components if c.status == "degraded")
        unhealthy_count = sum(1 for c in components if c.status == "unhealthy")

        overall_status = "healthy"
        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "healthy_components": healthy_count,
            "degraded_components": degraded_count,
            "unhealthy_components": unhealthy_count,
            "components": {
                c.name: {
                    "status": c.status,
                    "latency_ms": c.latency_ms,
                    "last_check": c.last_check.isoformat(),
                    "last_error": c.last_error,
                }
                for c in components
            },
        }


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

class BatchJobType(Enum):
    """Types of batch jobs"""
    NIGHTLY_SCORING = "nightly_scoring"
    WEEKLY_STRATEGY_RECALIBRATION = "weekly_strategy_recalibration"
    MONTHLY_PORTFOLIO_REBALANCING = "monthly_portfolio_rebalancing"
    QUARTERLY_MODEL_RETRAINING = "quarterly_model_retraining"
    DAILY_COMPLIANCE_AUDIT = "daily_compliance_audit"
    DAILY_METRICS_AGGREGATION = "daily_metrics_aggregation"


@dataclass
class BatchJob:
    """Batch job definition"""
    job_id: str
    job_type: BatchJobType
    schedule: str  # cron expression or keyword
    last_run: Optional[datetime]
    next_run: datetime
    status: str  # pending, running, completed, failed
    accounts_processed: int = 0
    duration_seconds: float = 0
    error: Optional[str] = None


class BatchProcessor:
    """
    Handles batch operations:
    - Nightly scoring updates
    - Weekly strategy recalibration
    - Monthly portfolio rebalancing
    - Quarterly model retraining triggers
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._jobs: Dict[str, BatchJob] = {}
        self._job_handlers: Dict[BatchJobType, Callable] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # Register default jobs
        self._register_default_jobs()

    def _register_default_jobs(self) -> None:
        """Register default batch jobs"""
        now = datetime.utcnow()

        jobs = [
            BatchJob(
                job_id="nightly_scoring",
                job_type=BatchJobType.NIGHTLY_SCORING,
                schedule="daily_2am",
                last_run=None,
                next_run=now.replace(hour=2, minute=0, second=0) + timedelta(days=1),
                status="pending",
            ),
            BatchJob(
                job_id="weekly_strategy",
                job_type=BatchJobType.WEEKLY_STRATEGY_RECALIBRATION,
                schedule="weekly_sunday_3am",
                last_run=None,
                next_run=now + timedelta(days=(6 - now.weekday()) % 7 + 1),
                status="pending",
            ),
            BatchJob(
                job_id="monthly_rebalance",
                job_type=BatchJobType.MONTHLY_PORTFOLIO_REBALANCING,
                schedule="monthly_1st_4am",
                last_run=None,
                next_run=(now.replace(day=1) + timedelta(days=32)).replace(day=1),
                status="pending",
            ),
            BatchJob(
                job_id="quarterly_retrain",
                job_type=BatchJobType.QUARTERLY_MODEL_RETRAINING,
                schedule="quarterly",
                last_run=None,
                next_run=now + timedelta(days=90),
                status="pending",
            ),
            BatchJob(
                job_id="daily_compliance",
                job_type=BatchJobType.DAILY_COMPLIANCE_AUDIT,
                schedule="daily_1am",
                last_run=None,
                next_run=now.replace(hour=1, minute=0, second=0) + timedelta(days=1),
                status="pending",
            ),
        ]

        for job in jobs:
            self._jobs[job.job_id] = job

    def register_handler(
        self,
        job_type: BatchJobType,
        handler: Callable[[BatchJob], Coroutine],
    ) -> None:
        """Register handler for a job type"""
        self._job_handlers[job_type] = handler

    async def start(self) -> None:
        """Start batch scheduler"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Batch processor started")

    async def stop(self) -> None:
        """Stop batch scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self._running:
            now = datetime.utcnow()

            for job in self._jobs.values():
                if job.next_run <= now and job.status == "pending":
                    await self._execute_job(job)

            await asyncio.sleep(60)  # Check every minute

    async def _execute_job(self, job: BatchJob) -> None:
        """Execute a batch job"""
        job.status = "running"
        start_time = time.time()

        await self.event_bus.publish(Event.create(
            event_type=EventType.BATCH_JOB_STARTED,
            aggregate_id=job.job_id,
            aggregate_type="batch_job",
            data={"job_type": job.job_type.value},
        ))

        try:
            handler = self._job_handlers.get(job.job_type)
            if handler:
                result = await handler(job)
                job.accounts_processed = result.get("accounts_processed", 0)

            job.status = "completed"
            job.last_run = datetime.utcnow()
            job.duration_seconds = time.time() - start_time

            # Schedule next run
            self._schedule_next_run(job)

            await self.event_bus.publish(Event.create(
                event_type=EventType.BATCH_JOB_COMPLETED,
                aggregate_id=job.job_id,
                aggregate_type="batch_job",
                data={
                    "job_type": job.job_type.value,
                    "accounts_processed": job.accounts_processed,
                    "duration_seconds": job.duration_seconds,
                },
            ))

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.duration_seconds = time.time() - start_time
            logger.error(f"Batch job {job.job_id} failed: {e}")

            # Schedule retry
            job.next_run = datetime.utcnow() + timedelta(hours=1)
            job.status = "pending"

    def _schedule_next_run(self, job: BatchJob) -> None:
        """Calculate next run time"""
        now = datetime.utcnow()

        if "daily" in job.schedule:
            job.next_run = now + timedelta(days=1)
        elif "weekly" in job.schedule:
            job.next_run = now + timedelta(weeks=1)
        elif "monthly" in job.schedule:
            job.next_run = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        elif "quarterly" in job.schedule:
            job.next_run = now + timedelta(days=90)

        job.status = "pending"

    async def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a job"""
        job = self._jobs.get(job_id)
        if not job:
            return False

        await self._execute_job(job)
        return True

    def get_job_status(self) -> List[Dict[str, Any]]:
        """Get status of all jobs"""
        return [
            {
                "job_id": job.job_id,
                "job_type": job.job_type.value,
                "status": job.status,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "next_run": job.next_run.isoformat(),
                "accounts_processed": job.accounts_processed,
                "duration_seconds": job.duration_seconds,
                "error": job.error,
            }
            for job in self._jobs.values()
        ]


# =============================================================================
# METRICS DASHBOARD
# =============================================================================

@dataclass
class MetricsSnapshot:
    """Point-in-time metrics snapshot"""
    timestamp: datetime

    # Volume metrics
    total_accounts: int
    active_accounts: int
    accounts_in_queue: int

    # Performance metrics
    contacts_today: int
    responses_today: int
    payments_today: int
    resolution_rate: float

    # Financial metrics
    total_balance: Decimal
    collected_today: Decimal
    collected_mtd: Decimal
    collected_ytd: Decimal

    # Efficiency metrics
    avg_decision_latency_ms: float
    event_throughput_per_sec: float
    queue_wait_time_avg_min: float

    # Health metrics
    component_health: Dict[str, str]
    circuit_breaker_states: Dict[str, str]
    error_rate: float


class MetricsDashboard:
    """
    Real-time metrics dashboard for:
    - Business KPIs
    - Technical performance
    - Component health
    - Error tracking
    """

    def __init__(self):
        self._snapshots: List[MetricsSnapshot] = []
        self._max_snapshots = 1440  # 24 hours at 1-minute intervals

        # Counters (reset daily)
        self._contacts_today = 0
        self._responses_today = 0
        self._payments_today = 0
        self._collected_today = Decimal("0")

        # Cumulative counters
        self._collected_mtd = Decimal("0")
        self._collected_ytd = Decimal("0")

        # Error tracking
        self._errors: List[Dict[str, Any]] = []
        self._error_count_window: List[datetime] = []

    def record_contact(self) -> None:
        self._contacts_today += 1

    def record_response(self) -> None:
        self._responses_today += 1

    def record_payment(self, amount: Decimal) -> None:
        self._payments_today += 1
        self._collected_today += amount
        self._collected_mtd += amount
        self._collected_ytd += amount

    def record_error(self, component: str, error: str) -> None:
        now = datetime.utcnow()
        self._errors.append({
            "timestamp": now.isoformat(),
            "component": component,
            "error": error,
        })
        self._error_count_window.append(now)

        # Keep only last hour
        cutoff = now - timedelta(hours=1)
        self._error_count_window = [t for t in self._error_count_window if t > cutoff]

    def capture_snapshot(
        self,
        queue_manager: PriorityQueueManager,
        decision_engine: RealTimeDecisionEngine,
        event_bus: EventBus,
        health_monitor: HealthMonitor,
        circuit_breakers: Dict[str, CircuitBreaker],
        total_accounts: int,
        active_accounts: int,
        total_balance: Decimal,
    ) -> MetricsSnapshot:
        """Capture current metrics snapshot"""
        now = datetime.utcnow()

        queue_stats = queue_manager.get_queue_stats()
        decision_metrics = decision_engine.get_metrics()
        event_metrics = event_bus.get_metrics()
        health = health_monitor.get_health_summary()

        # Calculate error rate (errors per hour)
        error_rate = len(self._error_count_window) / 60  # per minute average

        snapshot = MetricsSnapshot(
            timestamp=now,
            total_accounts=total_accounts,
            active_accounts=active_accounts,
            accounts_in_queue=queue_stats["total_queued"],
            contacts_today=self._contacts_today,
            responses_today=self._responses_today,
            payments_today=self._payments_today,
            resolution_rate=self._payments_today / max(1, self._contacts_today),
            total_balance=total_balance,
            collected_today=self._collected_today,
            collected_mtd=self._collected_mtd,
            collected_ytd=self._collected_ytd,
            avg_decision_latency_ms=decision_metrics["avg_latency_ms"],
            event_throughput_per_sec=event_metrics["events_processed"] / 60,
            queue_wait_time_avg_min=0,  # Would calculate from queue data
            component_health={c: d["status"] for c, d in health["components"].items()},
            circuit_breaker_states={n: cb.state.value for n, cb in circuit_breakers.items()},
            error_rate=error_rate,
        )

        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        return snapshot

    def reset_daily_counters(self) -> None:
        """Reset daily counters (called at midnight)"""
        self._contacts_today = 0
        self._responses_today = 0
        self._payments_today = 0
        self._collected_today = Decimal("0")

    def reset_monthly_counters(self) -> None:
        """Reset monthly counters (called on 1st)"""
        self._collected_mtd = Decimal("0")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for dashboard display"""
        if not self._snapshots:
            return {"status": "no_data"}

        latest = self._snapshots[-1]

        return {
            "timestamp": latest.timestamp.isoformat(),
            "kpis": {
                "total_accounts": latest.total_accounts,
                "active_accounts": latest.active_accounts,
                "accounts_in_queue": latest.accounts_in_queue,
                "contacts_today": latest.contacts_today,
                "responses_today": latest.responses_today,
                "payments_today": latest.payments_today,
                "resolution_rate": f"{latest.resolution_rate:.1%}",
                "collected_today": float(latest.collected_today),
                "collected_mtd": float(latest.collected_mtd),
            },
            "performance": {
                "avg_decision_latency_ms": f"{latest.avg_decision_latency_ms:.1f}",
                "event_throughput_per_sec": f"{latest.event_throughput_per_sec:.1f}",
                "error_rate": f"{latest.error_rate:.2f}/min",
            },
            "health": {
                "components": latest.component_health,
                "circuit_breakers": latest.circuit_breaker_states,
            },
            "recent_errors": self._errors[-10:],
        }


# =============================================================================
# MASTER ORCHESTRATION ENGINE
# =============================================================================

class MasterOrchestrationEngine:
    """
    The Central Nervous System of the Shadow Bureau.

    Orchestrates all components:
    - Empathy Engine (contact generation)
    - Live Ledger (data persistence)
    - Rehabilitation Loop (gamification)
    - Risk Engine (limits and controls)
    - Payment Engine (collection)
    - Compliance Orchestrator (validation)
    - Settlement Engine (optimization)
    - Asset Marketplace (securitization)
    """

    def __init__(self):
        # Core infrastructure
        self.event_bus = EventBus()
        self.priority_queue = PriorityQueueManager()
        self.decision_engine = RealTimeDecisionEngine()
        self.health_monitor = HealthMonitor()
        self.batch_processor = BatchProcessor(self.event_bus)
        self.metrics_dashboard = MetricsDashboard()

        # Circuit breakers for external services
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            "empathy_engine": CircuitBreaker("empathy_engine"),
            "live_ledger": CircuitBreaker("live_ledger"),
            "rehabilitation_loop": CircuitBreaker("rehabilitation_loop"),
            "payment_engine": CircuitBreaker("payment_engine"),
            "compliance_engine": CircuitBreaker("compliance_engine"),
            "settlement_engine": CircuitBreaker("settlement_engine"),
            "marketplace": CircuitBreaker("marketplace"),
        }

        # Component references (lazy loaded)
        self._empathy_engine = None
        self._live_ledger = None
        self._rehabilitation_loop = None
        self._payment_processor = None
        self._compliance_engine = None
        self._marketplace = None

        # Account state tracking
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._account_versions: Dict[str, int] = {}

        # Sagas for complex workflows
        self._sagas: Dict[str, Saga] = {}
        self._register_sagas()

        # Register event handlers
        self._register_handlers()

        # Register health checks
        self._register_health_checks()

        # Register batch handlers
        self._register_batch_handlers()

        self._running = False
        logger.info("MasterOrchestrationEngine initialized")

    # =========================================================================
    # LAZY COMPONENT LOADING
    # =========================================================================

    def _get_empathy_engine(self):
        """Lazy load Empathy Engine"""
        if self._empathy_engine is None:
            try:
                from quan.shadow_bureau.empathy_engine import EmpathyEngine
                self._empathy_engine = EmpathyEngine()
            except ImportError as e:
                logger.warning(f"Could not load Empathy Engine: {e}")
        return self._empathy_engine

    def _get_live_ledger(self):
        """Lazy load Live Ledger"""
        if self._live_ledger is None:
            try:
                from quan.shadow_bureau.live_ledger import LiveLedger
                self._live_ledger = LiveLedger()
            except ImportError as e:
                logger.warning(f"Could not load Live Ledger: {e}")
        return self._live_ledger

    def _get_rehabilitation_loop(self):
        """Lazy load Rehabilitation Loop"""
        if self._rehabilitation_loop is None:
            try:
                from quan.shadow_bureau.rehabilitation_loop import RehabilitationLoop
                self._rehabilitation_loop = RehabilitationLoop()
            except ImportError as e:
                logger.warning(f"Could not load Rehabilitation Loop: {e}")
        return self._rehabilitation_loop

    def _get_payment_processor(self):
        """Lazy load Payment Processor"""
        if self._payment_processor is None:
            try:
                from quan.payments.processor import PaymentProcessor
                self._payment_processor = PaymentProcessor()
            except ImportError as e:
                logger.warning(f"Could not load Payment Processor: {e}")
        return self._payment_processor

    def _get_compliance_engine(self):
        """Lazy load Compliance Engine"""
        if self._compliance_engine is None:
            try:
                from quan.compliance.engine import ComplianceEngine
                self._compliance_engine = ComplianceEngine()
            except ImportError as e:
                logger.warning(f"Could not load Compliance Engine: {e}")
        return self._compliance_engine

    def _get_marketplace(self):
        """Lazy load Asset Marketplace"""
        if self._marketplace is None:
            try:
                from quan.shadow_bureau.asset_marketplace import DistressedAssetMarketplace
                self._marketplace = DistressedAssetMarketplace()
            except ImportError as e:
                logger.warning(f"Could not load Asset Marketplace: {e}")
        return self._marketplace

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def _register_handlers(self) -> None:
        """Register event handlers"""
        # Account lifecycle handler
        class AccountLifecycleHandler(EventHandler):
            def __init__(self, engine: "MasterOrchestrationEngine"):
                self.engine = engine

            @property
            def handled_events(self) -> List[EventType]:
                return [
                    EventType.ACCOUNT_CREATED,
                    EventType.ACCOUNT_STATE_CHANGED,
                    EventType.PAYMENT_COMPLETED,
                    EventType.ACCOUNT_RESOLVED,
                ]

            async def handle(self, event: Event) -> None:
                if event.event_type == EventType.ACCOUNT_CREATED:
                    await self.engine._handle_account_created(event)
                elif event.event_type == EventType.ACCOUNT_STATE_CHANGED:
                    await self.engine._handle_state_change(event)
                elif event.event_type == EventType.PAYMENT_COMPLETED:
                    await self.engine._handle_payment_completed(event)
                elif event.event_type == EventType.ACCOUNT_RESOLVED:
                    await self.engine._handle_account_resolved(event)

        self.event_bus.subscribe(AccountLifecycleHandler(self))

        # Contact handler
        class ContactHandler(EventHandler):
            def __init__(self, engine: "MasterOrchestrationEngine"):
                self.engine = engine

            @property
            def handled_events(self) -> List[EventType]:
                return [
                    EventType.CONTACT_QUEUED,
                    EventType.CONTACT_DELIVERED,
                    EventType.CONTACT_RESPONSE_RECEIVED,
                ]

            async def handle(self, event: Event) -> None:
                if event.event_type == EventType.CONTACT_QUEUED:
                    self.engine.metrics_dashboard.record_contact()
                elif event.event_type == EventType.CONTACT_RESPONSE_RECEIVED:
                    self.engine.metrics_dashboard.record_response()

        self.event_bus.subscribe(ContactHandler(self))

    def _register_sagas(self) -> None:
        """Register saga workflows"""
        # Account intake saga
        intake_steps = [
            SagaStep(
                name="validate_data",
                execute=self._saga_validate_data,
                compensate=self._saga_compensate_validation,
            ),
            SagaStep(
                name="score_account",
                execute=self._saga_score_account,
                compensate=self._saga_compensate_scoring,
            ),
            SagaStep(
                name="assign_strategy",
                execute=self._saga_assign_strategy,
                compensate=self._saga_compensate_strategy,
            ),
            SagaStep(
                name="queue_for_contact",
                execute=self._saga_queue_for_contact,
                compensate=self._saga_compensate_queue,
            ),
        ]

        self._sagas["account_intake"] = Saga(
            saga_type="account_intake",
            steps=intake_steps,
            event_bus=self.event_bus,
        )

        # Payment processing saga
        payment_steps = [
            SagaStep(
                name="validate_payment",
                execute=self._saga_validate_payment,
                compensate=self._saga_compensate_payment_validation,
            ),
            SagaStep(
                name="process_payment",
                execute=self._saga_process_payment,
                compensate=self._saga_refund_payment,
            ),
            SagaStep(
                name="update_ledger",
                execute=self._saga_update_ledger,
                compensate=self._saga_compensate_ledger,
            ),
            SagaStep(
                name="issue_restoration",
                execute=self._saga_issue_restoration,
                compensate=self._saga_compensate_restoration,
            ),
        ]

        self._sagas["payment_processing"] = Saga(
            saga_type="payment_processing",
            steps=payment_steps,
            event_bus=self.event_bus,
        )

    def _register_health_checks(self) -> None:
        """Register component health checks"""
        async def check_empathy_engine():
            engine = self._get_empathy_engine()
            if engine:
                return {"status": "connected", "rules_loaded": len(engine.compliance_rules)}
            return {"status": "unavailable"}

        async def check_live_ledger():
            ledger = self._get_live_ledger()
            if ledger:
                return {
                    "status": "connected",
                    "records": len(ledger.debt_records),
                    "profiles": len(ledger.consumer_profiles),
                }
            return {"status": "unavailable"}

        async def check_rehabilitation():
            loop = self._get_rehabilitation_loop()
            if loop:
                return {
                    "status": "connected",
                    "trust_scores": len(loop.trust_scores),
                    "certificates": len(loop.certificates),
                }
            return {"status": "unavailable"}

        self.health_monitor.register_component("empathy_engine", check_empathy_engine)
        self.health_monitor.register_component("live_ledger", check_live_ledger)
        self.health_monitor.register_component("rehabilitation_loop", check_rehabilitation)

    def _register_batch_handlers(self) -> None:
        """Register batch job handlers"""
        async def handle_nightly_scoring(job: BatchJob) -> Dict[str, Any]:
            """Re-score all active accounts"""
            accounts_processed = 0

            for account_id, account_data in self._accounts.items():
                if account_data.get("state") in [
                    AccountState.CONTACT_QUEUE.value,
                    AccountState.CONTACTED.value,
                    AccountState.NEGOTIATING.value,
                ]:
                    # Recalculate priority
                    new_priority = self.priority_queue.calculate_priority(
                        balance=Decimal(str(account_data.get("balance", 0))),
                        days_past_due=account_data.get("days_past_due", 0),
                        recovery_probability=account_data.get("recovery_probability", 0.5),
                        last_contact=account_data.get("last_contact"),
                    )
                    self.priority_queue.update_priority(account_id, new_priority)
                    accounts_processed += 1

            return {"accounts_processed": accounts_processed}

        async def handle_daily_compliance(job: BatchJob) -> Dict[str, Any]:
            """Audit today's contacts for compliance"""
            # Would audit all contacts made today
            return {"accounts_processed": 0, "violations_found": 0}

        self.batch_processor.register_handler(
            BatchJobType.NIGHTLY_SCORING,
            handle_nightly_scoring
        )
        self.batch_processor.register_handler(
            BatchJobType.DAILY_COMPLIANCE_AUDIT,
            handle_daily_compliance
        )

    # =========================================================================
    # SAGA STEP IMPLEMENTATIONS
    # =========================================================================

    async def _saga_validate_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate incoming account data"""
        account_data = context.get("account_data", {})

        # Basic validation
        required_fields = ["account_id", "balance", "creditor_id"]
        for field in required_fields:
            if field not in account_data:
                raise ValueError(f"Missing required field: {field}")

        # Compliance validation
        compliance = self._get_compliance_engine()
        if compliance:
            is_valid, error = await compliance.validate_contact(
                account_data,
                "intake",
            )
            if not is_valid:
                raise ValueError(f"Compliance validation failed: {error}")

        return {"validated": True}

    async def _saga_compensate_validation(self, context: Dict[str, Any]) -> None:
        """Compensate validation step"""
        account_id = context.get("account_data", {}).get("account_id")
        if account_id and account_id in self._accounts:
            del self._accounts[account_id]

    async def _saga_score_account(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Score the account"""
        account_data = context.get("account_data", {})

        ledger = self._get_live_ledger()
        if ledger:
            # Query existing profile if any
            consumer_id = account_data.get("consumer_id")
            profile = ledger.query_consumer(consumer_id) if consumer_id else None

            if profile:
                recovery_probability = profile.get("payment_score", 50) / 100
            else:
                # Default scoring based on DPD and balance
                dpd = account_data.get("days_past_due", 0)
                balance = account_data.get("balance", 0)

                base_prob = 0.5
                dpd_adj = -0.01 * min(dpd, 90)  # Up to -0.9 for old debts
                balance_adj = 0.1 if float(balance) < 200 else 0  # Micro-debt bonus

                recovery_probability = max(0.1, min(0.9, base_prob + dpd_adj + balance_adj))

            context["recovery_probability"] = recovery_probability
        else:
            context["recovery_probability"] = 0.5

        return {"scored": True, "recovery_probability": context["recovery_probability"]}

    async def _saga_compensate_scoring(self, context: Dict[str, Any]) -> None:
        """Compensate scoring step"""
        pass  # No compensation needed for scoring

    async def _saga_assign_strategy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assign collection strategy"""
        recovery_prob = context.get("recovery_probability", 0.5)
        balance = context.get("account_data", {}).get("balance", 0)

        # Strategy selection based on probability and balance
        if recovery_prob > 0.6:
            if float(balance) < 200:
                strategy = "quick_settlement"
            else:
                strategy = "full_pay_focus"
        elif recovery_prob > 0.3:
            strategy = "graduated_concession"
        else:
            strategy = "immediate_settlement"

        context["strategy"] = strategy
        return {"strategy_assigned": True, "strategy": strategy}

    async def _saga_compensate_strategy(self, context: Dict[str, Any]) -> None:
        """Compensate strategy assignment"""
        pass

    async def _saga_queue_for_contact(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Add account to contact queue"""
        account_data = context.get("account_data", {})
        account_id = account_data.get("account_id")

        priority = self.priority_queue.calculate_priority(
            balance=Decimal(str(account_data.get("balance", 0))),
            days_past_due=account_data.get("days_past_due", 0),
            recovery_probability=context.get("recovery_probability", 0.5),
            last_contact=None,
        )

        priority_account = PriorityAccount(
            account_id=account_id,
            priority=priority,
            balance=Decimal(str(account_data.get("balance", 0))),
            days_past_due=account_data.get("days_past_due", 0),
            recovery_probability=context.get("recovery_probability", 0.5),
            last_contact=None,
            next_action_time=datetime.utcnow(),
            state=AccountState.CONTACT_QUEUE,
        )

        self.priority_queue.add_account(priority_account)

        return {"queued": True, "priority": priority}

    async def _saga_compensate_queue(self, context: Dict[str, Any]) -> None:
        """Remove account from queue"""
        account_id = context.get("account_data", {}).get("account_id")
        if account_id:
            self.priority_queue.remove_account(account_id)

    async def _saga_validate_payment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment details"""
        payment_data = context.get("payment_data", {})
        amount = Decimal(str(payment_data.get("amount", 0)))

        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        return {"payment_validated": True}

    async def _saga_compensate_payment_validation(self, context: Dict[str, Any]) -> None:
        pass

    async def _saga_process_payment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process the payment"""
        processor = self._get_payment_processor()
        if not processor:
            raise Exception("Payment processor unavailable")

        account_data = context.get("account_data", {})
        payment_data = context.get("payment_data", {})

        result = await processor.process_payment(
            account=account_data,
            payment_method=payment_data.get("payment_method", {}),
            amount=Decimal(str(payment_data.get("amount", 0))),
        )

        if not result.success:
            raise Exception(f"Payment failed: {result.error}")

        context["transaction_id"] = result.transaction_id
        context["amount_paid"] = result.amount

        return {"payment_processed": True, "transaction_id": result.transaction_id}

    async def _saga_refund_payment(self, context: Dict[str, Any]) -> None:
        """Refund the payment"""
        transaction_id = context.get("transaction_id")
        if transaction_id:
            logger.info(f"Refunding payment {transaction_id}")
            # Would call processor.refund()

    async def _saga_update_ledger(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update Live Ledger with payment"""
        ledger = self._get_live_ledger()
        if ledger:
            account_id = context.get("account_data", {}).get("account_id")
            amount = context.get("amount_paid", Decimal("0"))

            # Find and update record
            for record_id, record in ledger.debt_records.items():
                if record.consumer_id == account_id:
                    ledger.record_interaction(
                        record_id,
                        "payment",
                        response_received=True,
                        payment_received=float(amount),
                    )
                    break

        return {"ledger_updated": True}

    async def _saga_compensate_ledger(self, context: Dict[str, Any]) -> None:
        """Reverse ledger update"""
        # Would reverse the payment record
        pass

    async def _saga_issue_restoration(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Issue restoration certificate"""
        rehab = self._get_rehabilitation_loop()
        if rehab:
            account_data = context.get("account_data", {})
            amount = context.get("amount_paid", Decimal("0"))

            # Record payment
            result = rehab.record_payment(
                consumer_id=account_data.get("consumer_id"),
                amount=float(amount),
                on_time=True,
                resolves_debt=float(amount) >= float(account_data.get("balance", 0)),
            )

            # Issue certificate if resolved
            if float(amount) >= float(account_data.get("balance", 0)):
                cert = rehab.issue_restoration_certificate(
                    consumer_id=account_data.get("consumer_id"),
                    creditor_id=account_data.get("creditor_id"),
                    creditor_name=account_data.get("creditor_name", "Unknown"),
                    original_amount=float(account_data.get("balance", 0)),
                    resolved_amount=float(amount),
                    resolution_type="paid_in_full",
                )
                context["certificate_id"] = cert.certificate_id

        return {"restoration_issued": True}

    async def _saga_compensate_restoration(self, context: Dict[str, Any]) -> None:
        """Revoke restoration certificate"""
        # Would revoke the certificate
        pass

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def _handle_account_created(self, event: Event) -> None:
        """Handle new account creation"""
        account_id = event.aggregate_id
        account_data = event.data

        # Store account
        self._accounts[account_id] = {
            **account_data,
            "state": AccountState.INTAKE.value,
            "created_at": event.timestamp.isoformat(),
        }
        self._account_versions[account_id] = event.version

    async def _handle_state_change(self, event: Event) -> None:
        """Handle account state change"""
        account_id = event.aggregate_id
        new_state = event.data.get("new_state")

        if account_id in self._accounts:
            self._accounts[account_id]["state"] = new_state
            self._accounts[account_id]["state_changed_at"] = event.timestamp.isoformat()

    async def _handle_payment_completed(self, event: Event) -> None:
        """Handle completed payment"""
        account_id = event.aggregate_id
        amount = Decimal(str(event.data.get("amount", 0)))

        self.metrics_dashboard.record_payment(amount)

        if account_id in self._accounts:
            current_paid = Decimal(str(self._accounts[account_id].get("total_paid", 0)))
            self._accounts[account_id]["total_paid"] = float(current_paid + amount)

    async def _handle_account_resolved(self, event: Event) -> None:
        """Handle account resolution"""
        account_id = event.aggregate_id

        # Remove from queue
        self.priority_queue.remove_account(account_id)

        if account_id in self._accounts:
            self._accounts[account_id]["state"] = AccountState.RESOLVED.value
            self._accounts[account_id]["resolved_at"] = event.timestamp.isoformat()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def ingest_account(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest a new account into the system.

        Triggers the account intake saga:
        Validate -> Score -> Assign Strategy -> Queue for Contact
        """
        account_id = account_data.get("account_id") or str(uuid.uuid4())
        account_data["account_id"] = account_id

        # Publish creation event
        await self.event_bus.publish(Event.create(
            event_type=EventType.ACCOUNT_CREATED,
            aggregate_id=account_id,
            aggregate_type="account",
            data=account_data,
        ))

        # Execute intake saga
        saga = self._sagas.get("account_intake")
        if saga:
            execution = await saga.execute({"account_data": account_data})

            if execution.state == SagaState.COMPLETED:
                # Update account with saga results
                self._accounts[account_id].update({
                    "recovery_probability": execution.context.get("recovery_probability"),
                    "strategy": execution.context.get("strategy"),
                    "priority": execution.context.get("priority"),
                    "state": AccountState.CONTACT_QUEUE.value,
                })

                return {
                    "success": True,
                    "account_id": account_id,
                    "saga_id": execution.saga_id,
                    "strategy": execution.context.get("strategy"),
                    "priority": execution.context.get("priority"),
                }
            else:
                return {
                    "success": False,
                    "account_id": account_id,
                    "saga_id": execution.saga_id,
                    "error": execution.error,
                }

        return {"success": False, "error": "Intake saga not registered"}

    async def process_next_accounts(
        self,
        batch_size: int = 10,
        worker_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get and process next batch of accounts"""
        batch = self.priority_queue.get_batch(batch_size, worker_id)
        results = []

        for priority_account in batch:
            result = await self._process_single_account(priority_account)
            results.append(result)

        return results

    async def _process_single_account(
        self,
        priority_account: PriorityAccount
    ) -> Dict[str, Any]:
        """Process a single account from the queue"""
        account_id = priority_account.account_id
        account_data = self._accounts.get(account_id, {})

        # Compliance check
        cb = self._circuit_breakers["compliance_engine"]
        if cb.can_execute():
            try:
                compliance = self._get_compliance_engine()
                if compliance:
                    is_valid, error = await compliance.validate_contact(
                        account_data,
                        "outbound",
                    )
                    if not is_valid:
                        # Put on compliance hold
                        await self._transition_state(
                            account_id,
                            AccountState.COMPLIANCE_HOLD,
                            {"reason": error}
                        )
                        cb.record_success()
                        return {"account_id": account_id, "action": "compliance_hold", "reason": error}
                cb.record_success()
            except Exception as e:
                cb.record_failure()
                logger.error(f"Compliance check failed: {e}")

        # Channel decision
        channel_decision = await self.decision_engine.decide_channel(
            account_id,
            account_data,
            account_data.get("contact_history", []),
        )

        # Execute contact via Empathy Engine
        cb = self._circuit_breakers["empathy_engine"]
        if cb.can_execute():
            try:
                empathy = self._get_empathy_engine()
                if empathy:
                    result = empathy.execute_autonomous_contact(
                        consumer_id=account_data.get("consumer_id", account_id),
                        balance=float(account_data.get("balance", 0)),
                        creditor=account_data.get("creditor_name", "Unknown"),
                        channel=channel_decision.recommendation,
                    )

                    # Update account
                    self._accounts[account_id]["last_contact"] = datetime.utcnow().isoformat()
                    self._accounts[account_id]["contact_count"] = account_data.get("contact_count", 0) + 1

                    # Publish contact event
                    await self.event_bus.publish(Event.create(
                        event_type=EventType.CONTACT_DELIVERED,
                        aggregate_id=account_id,
                        aggregate_type="account",
                        data={
                            "channel": channel_decision.recommendation,
                            "persona": result.get("persona"),
                            "message_hash": result.get("audit_hash"),
                        },
                    ))

                    # Update state
                    await self._transition_state(account_id, AccountState.CONTACTED)

                    # Update queue for next action
                    priority_account.last_contact = datetime.utcnow()
                    priority_account.next_action_time = datetime.utcnow() + timedelta(days=2)
                    priority_account.state = AccountState.CONTACTED
                    self.priority_queue.release_account(account_id)

                    cb.record_success()

                    return {
                        "account_id": account_id,
                        "action": "contacted",
                        "channel": channel_decision.recommendation,
                        "persona": result.get("persona"),
                    }
                cb.record_success()
            except Exception as e:
                cb.record_failure()
                logger.error(f"Contact execution failed: {e}")

        # Release account for retry
        self.priority_queue.release_account(account_id)
        return {"account_id": account_id, "action": "failed", "error": "Contact failed"}

    async def process_payment(
        self,
        account_id: str,
        payment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a payment for an account"""
        account_data = self._accounts.get(account_id)
        if not account_data:
            return {"success": False, "error": "Account not found"}

        # Execute payment saga
        saga = self._sagas.get("payment_processing")
        if saga:
            execution = await saga.execute({
                "account_data": account_data,
                "payment_data": payment_data,
            })

            if execution.state == SagaState.COMPLETED:
                amount = execution.context.get("amount_paid", Decimal("0"))

                # Publish payment event
                await self.event_bus.publish(Event.create(
                    event_type=EventType.PAYMENT_COMPLETED,
                    aggregate_id=account_id,
                    aggregate_type="account",
                    data={
                        "amount": float(amount),
                        "transaction_id": execution.context.get("transaction_id"),
                    },
                ))

                # Check if fully paid
                balance = Decimal(str(account_data.get("balance", 0)))
                if amount >= balance:
                    await self._transition_state(account_id, AccountState.PAID_IN_FULL)

                    await self.event_bus.publish(Event.create(
                        event_type=EventType.ACCOUNT_RESOLVED,
                        aggregate_id=account_id,
                        aggregate_type="account",
                        data={"resolution_type": "paid_in_full"},
                    ))
                else:
                    await self._transition_state(account_id, AccountState.PARTIAL_PAID)

                return {
                    "success": True,
                    "account_id": account_id,
                    "amount": float(amount),
                    "transaction_id": execution.context.get("transaction_id"),
                    "certificate_id": execution.context.get("certificate_id"),
                }
            else:
                return {
                    "success": False,
                    "account_id": account_id,
                    "error": execution.error,
                }

        return {"success": False, "error": "Payment saga not registered"}

    async def _transition_state(
        self,
        account_id: str,
        new_state: AccountState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition account to new state"""
        if account_id not in self._accounts:
            return False

        current_state_str = self._accounts[account_id].get("state")
        try:
            current_state = AccountState(current_state_str)
        except (ValueError, TypeError):
            current_state = AccountState.INTAKE

        if not StateTransition.can_transition(current_state, new_state):
            logger.warning(
                f"Invalid state transition for {account_id}: "
                f"{current_state.value} -> {new_state.value}"
            )
            return False

        self._accounts[account_id]["state"] = new_state.value
        self._accounts[account_id]["state_history"] = self._accounts[account_id].get("state_history", [])
        self._accounts[account_id]["state_history"].append({
            "from": current_state.value,
            "to": new_state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata,
        })

        # Increment version
        self._account_versions[account_id] = self._account_versions.get(account_id, 0) + 1

        await self.event_bus.publish(Event.create(
            event_type=EventType.ACCOUNT_STATE_CHANGED,
            aggregate_id=account_id,
            aggregate_type="account",
            data={
                "from_state": current_state.value,
                "new_state": new_state.value,
                "metadata": metadata,
            },
            version=self._account_versions[account_id],
        ))

        return True

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the orchestration engine"""
        if self._running:
            return

        self._running = True

        await self.event_bus.start()
        await self.health_monitor.start()
        await self.batch_processor.start()

        logger.info("MasterOrchestrationEngine started")

    async def stop(self) -> None:
        """Stop the orchestration engine"""
        self._running = False

        await self.batch_processor.stop()
        await self.health_monitor.stop()
        await self.event_bus.stop()

        logger.info("MasterOrchestrationEngine stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get engine status"""
        return {
            "running": self._running,
            "accounts_tracked": len(self._accounts),
            "event_bus": self.event_bus.get_metrics(),
            "queue": self.priority_queue.get_queue_stats(),
            "decisions": self.decision_engine.get_metrics(),
            "health": self.health_monitor.get_health_summary(),
            "batch_jobs": self.batch_processor.get_job_status(),
            "circuit_breakers": {
                name: cb.state.value
                for name, cb in self._circuit_breakers.items()
            },
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Get metrics dashboard data"""
        return self.metrics_dashboard.get_dashboard_data()


# =============================================================================
# DEMONSTRATION
# =============================================================================

async def demo_master_engine():
    """Demonstrate the Master Orchestration Engine"""
    print("\n" + "=" * 80)
    print("  MASTER ORCHESTRATION ENGINE - SHADOW BUREAU DEMO")
    print("=" * 80)

    engine = MasterOrchestrationEngine()
    await engine.start()

    # Ingest sample accounts
    print("\n  Ingesting sample accounts...")
    print("  " + "-" * 76)

    sample_accounts = [
        {
            "consumer_id": "C001",
            "creditor_id": "KLARNA",
            "creditor_name": "Klarna",
            "balance": 147.50,
            "days_past_due": 45,
            "phone": "+15551234567",
            "email": "consumer1@example.com",
            "has_mobile_app": True,
            "is_digital_native": True,
            "age": 28,
        },
        {
            "consumer_id": "C002",
            "creditor_id": "AFTERPAY",
            "creditor_name": "Afterpay",
            "balance": 89.00,
            "days_past_due": 30,
            "phone": "+15559876543",
            "email": "consumer2@example.com",
            "age": 35,
        },
        {
            "consumer_id": "C003",
            "creditor_id": "AFFIRM",
            "creditor_name": "Affirm",
            "balance": 312.00,
            "days_past_due": 60,
            "email": "consumer3@example.com",
            "age": 42,
        },
    ]

    for account in sample_accounts:
        result = await engine.ingest_account(account)
        print(f"\n  Account: {result.get('account_id', 'Unknown')[:12]}...")
        print(f"    Status: {'SUCCESS' if result.get('success') else 'FAILED'}")
        if result.get("success"):
            print(f"    Strategy: {result.get('strategy')}")
            print(f"    Priority: {result.get('priority', 0):.1f}")
        else:
            print(f"    Error: {result.get('error')}")

    # Process accounts from queue
    print("\n" + "-" * 80)
    print("  Processing accounts from queue...")
    print("  " + "-" * 76)

    results = await engine.process_next_accounts(batch_size=3)
    for result in results:
        print(f"\n  Account: {result.get('account_id', 'Unknown')[:12]}...")
        print(f"    Action: {result.get('action')}")
        if result.get("channel"):
            print(f"    Channel: {result.get('channel')}")
        if result.get("persona"):
            print(f"    Persona: {result.get('persona')}")

    # Simulate a payment
    print("\n" + "-" * 80)
    print("  Processing payment...")
    print("  " + "-" * 76)

    if engine._accounts:
        account_id = list(engine._accounts.keys())[0]
        payment_result = await engine.process_payment(
            account_id,
            {
                "amount": 100.00,
                "payment_method": {
                    "type": "card",
                    "token": "tok_test_123",
                },
            },
        )
        print(f"\n  Account: {account_id[:12]}...")
        print(f"    Status: {'SUCCESS' if payment_result.get('success') else 'FAILED'}")
        if payment_result.get("success"):
            print(f"    Amount: ${payment_result.get('amount', 0):.2f}")
            print(f"    Transaction: {payment_result.get('transaction_id', 'N/A')}")

    # Show engine status
    print("\n" + "-" * 80)
    print("  ENGINE STATUS")
    print("  " + "-" * 76)

    status = engine.get_status()
    print(f"\n  Running: {status['running']}")
    print(f"  Accounts Tracked: {status['accounts_tracked']}")

    print(f"\n  Event Bus:")
    print(f"    Published: {status['event_bus']['events_published']}")
    print(f"    Processed: {status['event_bus']['events_processed']}")
    print(f"    Failed: {status['event_bus']['events_failed']}")

    print(f"\n  Queue:")
    print(f"    Total Queued: {status['queue']['total_queued']}")
    print(f"    Ready for Action: {status['queue']['ready_for_action']}")

    print(f"\n  Decision Engine:")
    print(f"    Decisions Made: {status['decisions']['total_decisions']}")
    print(f"    Avg Latency: {status['decisions']['avg_latency_ms']:.2f}ms")

    print(f"\n  Circuit Breakers:")
    for name, state in status['circuit_breakers'].items():
        print(f"    {name}: {state}")

    print(f"\n  Batch Jobs:")
    for job in status['batch_jobs'][:3]:
        print(f"    {job['job_id']}: {job['status']} (next: {job['next_run'][:10]})")

    await engine.stop()

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_master_engine())
