"""
Master Collection Orchestrator

The brain of the collection system that ties everything together:
- Integrates all optimization engines into a unified runtime
- Implements real-time decision making
- Creates feedback loops for continuous learning
- Provides API endpoints for account processing
- Implements graceful degradation with fallbacks

Orchestration Flow:
    Account -> Channel Selection -> Strategy Selection -> Action Decision
         |           ^                    ^                    ^
         |           |                    |                    |
         v           |                    |                    |
    Feedback Loop ---+--------------------+--------------------+
         |
         v
    Model Weight Updates -> Re-optimization Triggers
"""

import asyncio
import random
import time
import threading
import logging
import json
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from functools import wraps
import traceback
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ActionType(Enum):
    """Types of collection actions"""
    CONTACT_SMS = "contact_sms"
    CONTACT_EMAIL = "contact_email"
    CONTACT_PUSH = "contact_push"
    CONTACT_VOICE = "contact_voice"
    CONTACT_MAIL = "contact_mail"
    NEGOTIATE_FULL = "negotiate_full"
    NEGOTIATE_SETTLEMENT = "negotiate_settlement"
    NEGOTIATE_PLAN = "negotiate_plan"
    ESCALATE = "escalate"
    PAUSE = "pause"
    RE_ENGAGE = "re_engage"
    WRITE_OFF = "write_off"
    CLOSE = "close"


class AccountStatus(Enum):
    """Account status in the collection lifecycle"""
    NEW = "new"
    ACTIVE = "active"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    PAYMENT_PENDING = "payment_pending"
    PARTIAL = "partial"
    COLLECTED = "collected"
    PAUSED = "paused"
    ESCALATED = "escalated"
    WRITTEN_OFF = "written_off"
    CLOSED = "closed"


class DecisionOutcome(Enum):
    """Outcomes of collection decisions"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NO_RESPONSE = "no_response"
    REFUSED = "refused"
    DISPUTED = "disputed"
    PAYMENT_FAILED = "payment_failed"
    ERROR = "error"


class OptimizationComponent(Enum):
    """Optimization components in the system"""
    CHANNEL_OPTIMIZER = "channel_optimizer"
    NEGOTIATION_TUNER = "negotiation_tuner"
    LIFECYCLE_OPTIMIZER = "lifecycle_optimizer"
    BOTTLENECK_ANALYZER = "bottleneck_analyzer"


# Default fallback configuration
DEFAULT_FALLBACK_CONFIG = {
    "default_channel_sequence": ["sms", "email", "sms", "push", "voice"],
    "default_negotiation_strategy": "graduated_concession",
    "max_contact_attempts": 8,
    "re_engagement_threshold_days": 14,
    "write_off_threshold_days": 90,
    "min_balance_for_voice": Decimal("100"),
    "escalation_balance_threshold": Decimal("500"),
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Account:
    """Account representation for orchestration"""
    account_id: str
    balance: Decimal
    original_balance: Decimal
    days_past_due: int
    debt_type: str

    # Contact information
    phone: Optional[str] = None
    email: Optional[str] = None
    has_mobile_app: bool = False

    # Demographics
    age: Optional[int] = None
    is_digital_native: bool = True

    # State tracking
    status: AccountStatus = AccountStatus.NEW
    contact_attempts: int = 0
    last_contact_date: Optional[datetime] = None
    last_response_date: Optional[datetime] = None
    total_paid: Decimal = Decimal("0")
    current_strategy: Optional[str] = None

    # Channel history
    channel_history: List[Dict] = field(default_factory=list)

    # Negotiation state
    current_offer: Optional[float] = None
    offers_made: int = 0

    # Scores and predictions
    recovery_probability: float = 0.5
    optimal_channel: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "account_id": self.account_id,
            "balance": float(self.balance),
            "original_balance": float(self.original_balance),
            "days_past_due": self.days_past_due,
            "debt_type": self.debt_type,
            "phone": self.phone,
            "email": self.email,
            "has_mobile_app": self.has_mobile_app,
            "age": self.age,
            "is_digital_native": self.is_digital_native,
            "status": self.status.value,
            "contact_attempts": self.contact_attempts,
            "total_paid": float(self.total_paid),
            "recovery_probability": self.recovery_probability,
            "optimal_channel": self.optimal_channel,
        }


@dataclass
class CollectionStrategy:
    """Strategy recommendation from orchestrator"""
    account_id: str
    recommended_action: ActionType
    channel: Optional[str] = None
    negotiation_strategy: Optional[str] = None
    offer_amount: Optional[Decimal] = None
    offer_percentage: Optional[float] = None
    urgency_level: str = "medium"
    timing_recommendation: Optional[datetime] = None
    fallback_action: Optional[ActionType] = None
    confidence_score: float = 0.5
    reasoning: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of an executed action"""
    account_id: str
    action: ActionType
    outcome: DecisionOutcome
    amount_collected: Decimal = Decimal("0")
    response_received: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for the orchestrator"""
    total_decisions: int = 0
    successful_decisions: int = 0
    total_collected: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    predictions: List[float] = field(default_factory=list)
    actuals: List[float] = field(default_factory=list)
    decision_times: List[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful_decisions / self.total_decisions if self.total_decisions > 0 else 0.0

    @property
    def prediction_accuracy(self) -> float:
        if len(self.predictions) < 10:
            return 0.0
        # Mean absolute error
        errors = [abs(p - a) for p, a in zip(self.predictions, self.actuals)]
        mae = sum(errors) / len(errors)
        return max(0, 1 - mae)

    @property
    def avg_decision_time_ms(self) -> float:
        return statistics.mean(self.decision_times) * 1000 if self.decision_times else 0.0


@dataclass
class PortfolioStats:
    """Portfolio-level statistics"""
    total_accounts: int = 0
    active_accounts: int = 0
    collected_accounts: int = 0
    written_off_accounts: int = 0
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    recovery_rate: float = 0.0
    cost_per_dollar: float = 0.0
    roi: float = 0.0
    avg_days_to_collect: float = 0.0
    channel_distribution: Dict[str, int] = field(default_factory=dict)
    strategy_distribution: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external dependencies.

    Prevents cascade failures by opening the circuit when
    too many failures occur.
    """

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
                # Check if we should transition to half-open
                if self._last_failure_time:
                    elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
            return self._state

    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
        return False  # OPEN state

    def record_success(self):
        """Record successful operation"""
        with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name}: Closed (recovered)")

    def record_failure(self):
        """Record failed operation"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: Re-opened (half-open failure)")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: Opened (threshold reached)")

    def reset(self):
        """Manually reset the circuit"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


def circuit_protected(circuit: CircuitBreaker):
    """Decorator for circuit-protected operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not circuit.can_execute():
                raise CircuitBreakerOpenError(f"Circuit {circuit.name} is open")
            try:
                result = await func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure()
                raise
        return wrapper
    return decorator


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter with backpressure handling.
    """

    def __init__(
        self,
        name: str,
        rate: float = 100.0,  # Requests per second
        burst: int = 200,      # Max burst size
    ):
        self.name = name
        self.rate = rate
        self.burst = burst

        self._tokens = burst
        self._last_update = time.time()
        self._lock = threading.Lock()
        self._waiting_count = 0

    def _update_tokens(self):
        """Update available tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_update = now

    def acquire(self, tokens: int = 1, timeout: float = 10.0) -> bool:
        """
        Acquire tokens with optional blocking.

        Returns True if tokens acquired, False if timeout.
        """
        deadline = time.time() + timeout

        while True:
            with self._lock:
                self._update_tokens()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                # Calculate wait time
                needed = tokens - self._tokens
                wait_time = needed / self.rate

            if time.time() + wait_time > deadline:
                return False

            self._waiting_count += 1
            time.sleep(min(wait_time, 0.1))
            self._waiting_count -= 1

    @property
    def current_load(self) -> float:
        """Get current load as percentage of capacity"""
        with self._lock:
            self._update_tokens()
            return 1.0 - (self._tokens / self.burst)

    @property
    def is_under_pressure(self) -> bool:
        """Check if rate limiter is under pressure"""
        return self.current_load > 0.8 or self._waiting_count > 10


# =============================================================================
# DECISION AUDIT LOG
# =============================================================================

@dataclass
class DecisionLogEntry:
    """Entry in the decision audit log"""
    timestamp: datetime
    account_id: str
    decision_type: str
    action: ActionType
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    component_used: List[str]
    fallback_used: bool
    confidence: float
    latency_ms: float
    outcome: Optional[DecisionOutcome] = None
    outcome_recorded_at: Optional[datetime] = None


class DecisionAuditLog:
    """
    Audit log for all orchestrator decisions.

    Enables:
    - Compliance auditing
    - Model debugging
    - Performance analysis
    - Learning from outcomes
    """

    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self._entries: List[DecisionLogEntry] = []
        self._entries_by_account: Dict[str, List[DecisionLogEntry]] = defaultdict(list)
        self._lock = threading.Lock()

    def log_decision(
        self,
        account_id: str,
        decision_type: str,
        action: ActionType,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        components: List[str],
        fallback_used: bool,
        confidence: float,
        latency_ms: float,
    ) -> str:
        """Log a decision"""
        entry = DecisionLogEntry(
            timestamp=datetime.utcnow(),
            account_id=account_id,
            decision_type=decision_type,
            action=action,
            inputs=inputs,
            outputs=outputs,
            component_used=components,
            fallback_used=fallback_used,
            confidence=confidence,
            latency_ms=latency_ms,
        )

        with self._lock:
            self._entries.append(entry)
            self._entries_by_account[account_id].append(entry)

            # Trim if needed
            if len(self._entries) > self.max_entries:
                removed = self._entries[:1000]
                self._entries = self._entries[1000:]
                # Clean up by-account index
                for e in removed:
                    if e in self._entries_by_account.get(e.account_id, []):
                        self._entries_by_account[e.account_id].remove(e)

        return f"{account_id}:{entry.timestamp.isoformat()}"

    def record_outcome(
        self,
        account_id: str,
        outcome: DecisionOutcome,
        timestamp: Optional[datetime] = None,
    ):
        """Record outcome for most recent decision"""
        with self._lock:
            entries = self._entries_by_account.get(account_id, [])
            if entries:
                latest = entries[-1]
                if latest.outcome is None:
                    latest.outcome = outcome
                    latest.outcome_recorded_at = timestamp or datetime.utcnow()

    def get_account_history(self, account_id: str) -> List[DecisionLogEntry]:
        """Get decision history for an account"""
        with self._lock:
            return list(self._entries_by_account.get(account_id, []))

    def get_recent_decisions(
        self,
        hours: int = 24,
        decision_type: Optional[str] = None,
    ) -> List[DecisionLogEntry]:
        """Get recent decisions"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            entries = [e for e in self._entries if e.timestamp >= cutoff]
            if decision_type:
                entries = [e for e in entries if e.decision_type == decision_type]
            return entries

    def get_fallback_rate(self, hours: int = 24) -> float:
        """Get rate of fallback usage"""
        entries = self.get_recent_decisions(hours)
        if not entries:
            return 0.0
        return sum(1 for e in entries if e.fallback_used) / len(entries)

    def export_for_learning(
        self,
        hours: int = 168,  # 1 week
    ) -> List[Dict[str, Any]]:
        """Export completed decisions for model training"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self._lock:
            completed = [
                e for e in self._entries
                if e.timestamp >= cutoff and e.outcome is not None
            ]
            return [
                {
                    "inputs": e.inputs,
                    "action": e.action.value,
                    "outcome": e.outcome.value,
                    "confidence": e.confidence,
                }
                for e in completed
            ]


# =============================================================================
# FEEDBACK LOOP
# =============================================================================

class FeedbackLoop:
    """
    Feedback loop for continuous learning.

    Tracks:
    - Actual vs predicted outcomes
    - Model drift detection
    - Automatic re-optimization triggers
    """

    def __init__(
        self,
        drift_threshold: float = 0.15,
        evaluation_window: int = 1000,
        min_samples_for_drift: int = 100,
    ):
        self.drift_threshold = drift_threshold
        self.evaluation_window = evaluation_window
        self.min_samples_for_drift = min_samples_for_drift

        # Prediction tracking by component
        self._predictions: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self._lock = threading.Lock()

        # Drift detection
        self._drift_detected: Dict[str, bool] = {}
        self._last_drift_check: Dict[str, datetime] = {}

        # Callbacks for re-optimization
        self._reoptimization_callbacks: List[Callable] = []

    def record_prediction(
        self,
        component: str,
        predicted: float,
        actual: float,
    ):
        """Record a prediction and its actual outcome"""
        with self._lock:
            self._predictions[component].append((predicted, actual))

            # Keep only recent
            if len(self._predictions[component]) > self.evaluation_window:
                self._predictions[component] = self._predictions[component][-self.evaluation_window:]

    def check_drift(self, component: str) -> Tuple[bool, float]:
        """
        Check for performance drift in a component.

        Returns (drift_detected, drift_magnitude)
        """
        with self._lock:
            samples = self._predictions.get(component, [])

        if len(samples) < self.min_samples_for_drift:
            return False, 0.0

        # Calculate MAE for recent vs older samples
        mid = len(samples) // 2
        old_samples = samples[:mid]
        recent_samples = samples[mid:]

        old_mae = sum(abs(p - a) for p, a in old_samples) / len(old_samples)
        recent_mae = sum(abs(p - a) for p, a in recent_samples) / len(recent_samples)

        drift_magnitude = abs(recent_mae - old_mae)
        drift_detected = drift_magnitude > self.drift_threshold

        if drift_detected:
            self._drift_detected[component] = True
            logger.warning(
                f"Performance drift detected in {component}: "
                f"magnitude={drift_magnitude:.3f}, threshold={self.drift_threshold}"
            )

        return drift_detected, drift_magnitude

    def get_component_accuracy(self, component: str) -> float:
        """Get current accuracy for a component"""
        with self._lock:
            samples = self._predictions.get(component, [])

        if len(samples) < 10:
            return 0.5  # Default

        mae = sum(abs(p - a) for p, a in samples[-100:]) / min(100, len(samples))
        return max(0, 1 - mae)

    def register_reoptimization_callback(self, callback: Callable):
        """Register callback for re-optimization triggers"""
        self._reoptimization_callbacks.append(callback)

    def trigger_reoptimization(self, component: str, reason: str):
        """Trigger re-optimization for a component"""
        logger.info(f"Triggering re-optimization for {component}: {reason}")
        for callback in self._reoptimization_callbacks:
            try:
                callback(component, reason)
            except Exception as e:
                logger.error(f"Re-optimization callback error: {e}")

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary of all components"""
        summary = {}
        for component in self._predictions:
            drift, magnitude = self.check_drift(component)
            accuracy = self.get_component_accuracy(component)
            summary[component] = {
                "accuracy": accuracy,
                "drift_detected": drift,
                "drift_magnitude": magnitude,
                "samples": len(self._predictions[component]),
            }
        return summary


# =============================================================================
# MODEL WEIGHT MANAGER
# =============================================================================

class ModelWeightManager:
    """
    Manages model weights for ensemble decisions.

    Dynamically adjusts weights based on:
    - Recent performance
    - Segment-specific accuracy
    - External factors
    """

    def __init__(self):
        # Base weights
        self._weights: Dict[str, float] = {
            OptimizationComponent.CHANNEL_OPTIMIZER.value: 0.30,
            OptimizationComponent.NEGOTIATION_TUNER.value: 0.30,
            OptimizationComponent.LIFECYCLE_OPTIMIZER.value: 0.25,
            OptimizationComponent.BOTTLENECK_ANALYZER.value: 0.15,
        }

        # Segment-specific weight overrides
        self._segment_weights: Dict[str, Dict[str, float]] = {}

        # Performance tracking for weight adjustment
        self._performance_history: Dict[str, List[float]] = defaultdict(list)

        self._lock = threading.Lock()

    def get_weights(
        self,
        segment: Optional[str] = None,
    ) -> Dict[str, float]:
        """Get current weights, optionally for a segment"""
        with self._lock:
            if segment and segment in self._segment_weights:
                return self._segment_weights[segment].copy()
            return self._weights.copy()

    def update_weight(
        self,
        component: str,
        new_weight: float,
        segment: Optional[str] = None,
    ):
        """Update weight for a component"""
        with self._lock:
            if segment:
                if segment not in self._segment_weights:
                    self._segment_weights[segment] = self._weights.copy()
                self._segment_weights[segment][component] = new_weight
            else:
                self._weights[component] = new_weight

    def record_performance(
        self,
        component: str,
        accuracy: float,
    ):
        """Record performance for adaptive weighting"""
        with self._lock:
            self._performance_history[component].append(accuracy)

            # Keep last 100
            if len(self._performance_history[component]) > 100:
                self._performance_history[component] = self._performance_history[component][-100:]

    def rebalance_weights(self):
        """Rebalance weights based on recent performance"""
        with self._lock:
            # Calculate average recent accuracy
            accuracies = {}
            for comp, history in self._performance_history.items():
                if history:
                    accuracies[comp] = statistics.mean(history[-50:])

            if not accuracies:
                return

            # Normalize to sum to 1.0
            total = sum(accuracies.values())
            if total > 0:
                for comp, acc in accuracies.items():
                    self._weights[comp] = acc / total

                logger.info(f"Rebalanced weights: {self._weights}")


# =============================================================================
# MASTER COLLECTION ORCHESTRATOR
# =============================================================================

class MasterCollectionOrchestrator:
    """
    Master orchestrator that integrates all optimization engines.

    The brain of the collection system that:
    1. Selects optimal channels for contact attempts
    2. Chooses negotiation strategies based on debtor profiles
    3. Decides when to escalate, pause, or write-off
    4. Allocates resources across portfolio segments
    5. Maintains feedback loops for continuous learning
    """

    def __init__(
        self,
        enable_fallbacks: bool = True,
        rate_limit: float = 100.0,
        circuit_failure_threshold: int = 5,
    ):
        self.enable_fallbacks = enable_fallbacks

        # Initialize optimization engines (lazy loading)
        self._channel_optimizer = None
        self._negotiation_tuner = None
        self._lifecycle_optimizer = None
        self._bottleneck_analyzer = None

        # Circuit breakers for each component
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            OptimizationComponent.CHANNEL_OPTIMIZER.value: CircuitBreaker(
                "channel_optimizer", circuit_failure_threshold
            ),
            OptimizationComponent.NEGOTIATION_TUNER.value: CircuitBreaker(
                "negotiation_tuner", circuit_failure_threshold
            ),
            OptimizationComponent.LIFECYCLE_OPTIMIZER.value: CircuitBreaker(
                "lifecycle_optimizer", circuit_failure_threshold
            ),
            OptimizationComponent.BOTTLENECK_ANALYZER.value: CircuitBreaker(
                "bottleneck_analyzer", circuit_failure_threshold
            ),
        }

        # Rate limiter
        self._rate_limiter = RateLimiter("orchestrator", rate_limit)

        # Decision audit log
        self._audit_log = DecisionAuditLog()

        # Feedback loop
        self._feedback = FeedbackLoop()
        self._feedback.register_reoptimization_callback(self._handle_reoptimization)

        # Model weight manager
        self._weight_manager = ModelWeightManager()

        # Performance metrics
        self._metrics = PerformanceMetrics()

        # Account cache for efficient lookups
        self._account_cache: Dict[str, Account] = {}
        self._cache_lock = threading.Lock()

        # Segment strategies cache
        self._segment_strategies: Dict[str, Dict[str, Any]] = {}

        # Fallback configuration
        self._fallback_config = DEFAULT_FALLBACK_CONFIG.copy()

        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._running = False

        logger.info("MasterCollectionOrchestrator initialized")

    # =========================================================================
    # LAZY LOADING OF OPTIMIZATION ENGINES
    # =========================================================================

    def _get_channel_optimizer(self):
        """Lazy load channel optimizer"""
        if self._channel_optimizer is None:
            try:
                from quan.optimization.channel_optimizer import ChannelOptimizationEngine
                self._channel_optimizer = ChannelOptimizationEngine()
                logger.info("Channel optimizer loaded")
            except ImportError as e:
                logger.warning(f"Could not load channel optimizer: {e}")
        return self._channel_optimizer

    def _get_negotiation_tuner(self):
        """Lazy load negotiation tuner"""
        if self._negotiation_tuner is None:
            try:
                from quan.optimization.negotiation_tuner import (
                    NegotiationSimulator,
                    GameTheoryEngine,
                    NEGOTIATION_STRATEGIES,
                )
                self._negotiation_tuner = {
                    "simulator": NegotiationSimulator(),
                    "game_engine": GameTheoryEngine(),
                    "strategies": NEGOTIATION_STRATEGIES,
                }
                logger.info("Negotiation tuner loaded")
            except ImportError as e:
                logger.warning(f"Could not load negotiation tuner: {e}")
        return self._negotiation_tuner

    def _get_lifecycle_optimizer(self):
        """Lazy load lifecycle optimizer"""
        if self._lifecycle_optimizer is None:
            try:
                from quan.optimization.lifecycle_roi import LifecycleROIOptimizer
                self._lifecycle_optimizer = LifecycleROIOptimizer()
                logger.info("Lifecycle optimizer loaded")
            except ImportError as e:
                logger.warning(f"Could not load lifecycle optimizer: {e}")
        return self._lifecycle_optimizer

    def _get_bottleneck_analyzer(self):
        """Lazy load bottleneck analyzer"""
        if self._bottleneck_analyzer is None:
            try:
                from quan.analysis.bottleneck_analyzer import BottleneckAnalyzer
                self._bottleneck_analyzer = BottleneckAnalyzer()
                logger.info("Bottleneck analyzer loaded")
            except ImportError as e:
                logger.warning(f"Could not load bottleneck analyzer: {e}")
        return self._bottleneck_analyzer

    # =========================================================================
    # CORE API ENDPOINTS
    # =========================================================================

    async def process_account(self, account: Account) -> CollectionStrategy:
        """
        Process account and generate collection strategy.

        Main API endpoint that:
        1. Selects optimal channel
        2. Chooses negotiation strategy
        3. Determines action and timing
        4. Provides confidence score and reasoning

        Args:
            account: Account to process

        Returns:
            CollectionStrategy with recommended action
        """
        start_time = time.time()
        components_used = []
        fallback_used = False

        # Rate limiting
        if not self._rate_limiter.acquire(timeout=5.0):
            logger.warning(f"Rate limit exceeded for account {account.account_id}")
            return self._generate_fallback_strategy(account, "rate_limited")

        try:
            # Cache account
            with self._cache_lock:
                self._account_cache[account.account_id] = account

            # Gather insights from all available components
            insights = await self._gather_insights(account)
            components_used = insights.get("components_used", [])

            # Check if we had to fall back
            if insights.get("fallback_used"):
                fallback_used = True

            # Synthesize strategy from insights
            strategy = self._synthesize_strategy(account, insights)

            # Calculate confidence
            strategy.confidence_score = self._calculate_confidence(insights, strategy)

            # Record decision
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.decision_times.append(time.time() - start_time)
            self._metrics.total_decisions += 1

            self._audit_log.log_decision(
                account_id=account.account_id,
                decision_type="process_account",
                action=strategy.recommended_action,
                inputs=account.to_dict(),
                outputs={
                    "action": strategy.recommended_action.value,
                    "channel": strategy.channel,
                    "strategy": strategy.negotiation_strategy,
                    "confidence": strategy.confidence_score,
                },
                components=components_used,
                fallback_used=fallback_used,
                confidence=strategy.confidence_score,
                latency_ms=latency_ms,
            )

            return strategy

        except Exception as e:
            logger.error(f"Error processing account {account.account_id}: {e}")
            logger.debug(traceback.format_exc())
            return self._generate_fallback_strategy(account, f"error: {str(e)}")

    async def get_next_action(self, account_id: str) -> Dict[str, Any]:
        """
        Get next recommended action for an account.

        Simpler endpoint that returns just the next action to take.

        Args:
            account_id: Account identifier

        Returns:
            Dictionary with action details
        """
        # Get account from cache
        with self._cache_lock:
            account = self._account_cache.get(account_id)

        if not account:
            return {
                "account_id": account_id,
                "action": None,
                "error": "Account not found in cache",
                "suggestion": "Call process_account first",
            }

        # Get strategy
        strategy = await self.process_account(account)

        return {
            "account_id": account_id,
            "action": strategy.recommended_action.value,
            "channel": strategy.channel,
            "timing": strategy.timing_recommendation.isoformat() if strategy.timing_recommendation else None,
            "urgency": strategy.urgency_level,
            "confidence": strategy.confidence_score,
            "fallback_action": strategy.fallback_action.value if strategy.fallback_action else None,
        }

    async def update_outcome(
        self,
        account_id: str,
        result: ActionResult,
    ) -> None:
        """
        Update system with outcome of an action.

        Feeds the outcome back into the learning loop.

        Args:
            account_id: Account identifier
            result: Result of the executed action
        """
        # Update audit log
        self._audit_log.record_outcome(account_id, result.outcome)

        # Update account state
        with self._cache_lock:
            account = self._account_cache.get(account_id)
            if account:
                if result.outcome == DecisionOutcome.SUCCESS:
                    account.total_paid += result.amount_collected
                    if account.total_paid >= account.balance:
                        account.status = AccountStatus.COLLECTED
                    else:
                        account.status = AccountStatus.PARTIAL
                    self._metrics.successful_decisions += 1
                    self._metrics.total_collected += result.amount_collected

                elif result.outcome == DecisionOutcome.PARTIAL_SUCCESS:
                    account.total_paid += result.amount_collected
                    account.status = AccountStatus.PARTIAL
                    self._metrics.total_collected += result.amount_collected

                elif result.outcome == DecisionOutcome.NO_RESPONSE:
                    account.contact_attempts += 1
                    account.last_contact_date = result.timestamp

                elif result.outcome == DecisionOutcome.REFUSED:
                    account.contact_attempts += 1
                    account.last_response_date = result.timestamp

                elif result.outcome == DecisionOutcome.DISPUTED:
                    account.status = AccountStatus.PAUSED

                # Record channel usage
                if result.action in [
                    ActionType.CONTACT_SMS,
                    ActionType.CONTACT_EMAIL,
                    ActionType.CONTACT_PUSH,
                    ActionType.CONTACT_VOICE,
                    ActionType.CONTACT_MAIL,
                ]:
                    channel = result.action.value.replace("contact_", "")
                    account.channel_history.append({
                        "channel": channel,
                        "timestamp": result.timestamp.isoformat(),
                        "outcome": result.outcome.value,
                    })

        # Update feedback loop
        # Get the prediction that was made
        history = self._audit_log.get_account_history(account_id)
        if history:
            last_decision = history[-1]
            predicted = last_decision.confidence
            actual = 1.0 if result.outcome in [
                DecisionOutcome.SUCCESS,
                DecisionOutcome.PARTIAL_SUCCESS,
            ] else 0.0

            # Record to feedback loop by component
            for component in last_decision.component_used:
                self._feedback.record_prediction(component, predicted, actual)

            # Update metrics
            self._metrics.predictions.append(predicted)
            self._metrics.actuals.append(actual)

        # Check for drift periodically
        if self._metrics.total_decisions % 100 == 0:
            for component in OptimizationComponent:
                drift, magnitude = self._feedback.check_drift(component.value)
                if drift:
                    self._feedback.trigger_reoptimization(
                        component.value,
                        f"drift detected: {magnitude:.3f}",
                    )

        logger.debug(f"Updated outcome for {account_id}: {result.outcome.value}")

    async def get_portfolio_stats(self) -> PortfolioStats:
        """
        Get current portfolio statistics.

        Returns:
            PortfolioStats with aggregate metrics
        """
        with self._cache_lock:
            accounts = list(self._account_cache.values())

        if not accounts:
            return PortfolioStats()

        stats = PortfolioStats(
            total_accounts=len(accounts),
            active_accounts=sum(1 for a in accounts if a.status in [
                AccountStatus.NEW, AccountStatus.ACTIVE, AccountStatus.CONTACTED,
                AccountStatus.NEGOTIATING,
            ]),
            collected_accounts=sum(1 for a in accounts if a.status == AccountStatus.COLLECTED),
            written_off_accounts=sum(1 for a in accounts if a.status == AccountStatus.WRITTEN_OFF),
            total_balance=sum(a.original_balance for a in accounts),
            total_collected=sum(a.total_paid for a in accounts),
            total_cost=self._metrics.total_cost,
        )

        if stats.total_balance > 0:
            stats.recovery_rate = float(stats.total_collected / stats.total_balance)

        if stats.total_collected > 0:
            stats.cost_per_dollar = float(stats.total_cost / stats.total_collected)

        if stats.total_cost > 0:
            stats.roi = float((stats.total_collected - stats.total_cost) / stats.total_cost)

        # Channel distribution
        for account in accounts:
            for entry in account.channel_history:
                channel = entry.get("channel", "unknown")
                stats.channel_distribution[channel] = stats.channel_distribution.get(channel, 0) + 1

        # Strategy distribution
        for account in accounts:
            if account.current_strategy:
                stats.strategy_distribution[account.current_strategy] = \
                    stats.strategy_distribution.get(account.current_strategy, 0) + 1

        return stats

    # =========================================================================
    # INSIGHT GATHERING
    # =========================================================================

    async def _gather_insights(self, account: Account) -> Dict[str, Any]:
        """Gather insights from all available optimization engines"""
        insights = {
            "components_used": [],
            "fallback_used": False,
            "channel_recommendation": None,
            "negotiation_recommendation": None,
            "lifecycle_recommendation": None,
            "bottleneck_insights": None,
        }

        # Channel optimization insight
        channel_insight = await self._get_channel_insight(account)
        if channel_insight:
            insights["channel_recommendation"] = channel_insight
            insights["components_used"].append(OptimizationComponent.CHANNEL_OPTIMIZER.value)
        else:
            insights["fallback_used"] = True

        # Negotiation insight
        negotiation_insight = await self._get_negotiation_insight(account)
        if negotiation_insight:
            insights["negotiation_recommendation"] = negotiation_insight
            insights["components_used"].append(OptimizationComponent.NEGOTIATION_TUNER.value)
        else:
            insights["fallback_used"] = True

        # Lifecycle insight
        lifecycle_insight = await self._get_lifecycle_insight(account)
        if lifecycle_insight:
            insights["lifecycle_recommendation"] = lifecycle_insight
            insights["components_used"].append(OptimizationComponent.LIFECYCLE_OPTIMIZER.value)
        else:
            insights["fallback_used"] = True

        # Bottleneck insights (async, less critical)
        try:
            bottleneck_insight = await self._get_bottleneck_insight(account)
            if bottleneck_insight:
                insights["bottleneck_insights"] = bottleneck_insight
                insights["components_used"].append(OptimizationComponent.BOTTLENECK_ANALYZER.value)
        except Exception:
            pass  # Non-critical

        return insights

    async def _get_channel_insight(self, account: Account) -> Optional[Dict[str, Any]]:
        """Get channel selection insight"""
        circuit = self._circuit_breakers[OptimizationComponent.CHANNEL_OPTIMIZER.value]

        if not circuit.can_execute():
            logger.debug("Channel optimizer circuit open, using fallback")
            return None

        try:
            optimizer = self._get_channel_optimizer()
            if not optimizer:
                return None

            # Build segment key for the account
            from quan.optimization.channel_optimizer import (
                SegmentKey, DebtType, BalanceTier, DPDBucket, Channel
            )

            # Map debt type
            debt_type_map = {
                "payday": DebtType.PAYDAY,
                "bnpl": DebtType.BNPL,
                "subscription": DebtType.SUBSCRIPTION,
                "utility": DebtType.UTILITY,
                "medical": DebtType.MEDICAL,
                "retail": DebtType.RETAIL,
                "telecom": DebtType.TELECOM,
                "overdraft": DebtType.OVERDRAFT,
            }
            debt_type = debt_type_map.get(account.debt_type.lower(), DebtType.RETAIL)

            # Map balance tier
            balance = float(account.balance)
            if balance <= 100:
                balance_tier = BalanceTier.TIER_0_100
            elif balance <= 250:
                balance_tier = BalanceTier.TIER_100_250
            elif balance <= 500:
                balance_tier = BalanceTier.TIER_250_500
            elif balance <= 750:
                balance_tier = BalanceTier.TIER_500_750
            else:
                balance_tier = BalanceTier.TIER_750_1000

            # Map DPD bucket
            dpd = account.days_past_due
            if dpd <= 30:
                dpd_bucket = DPDBucket.DPD_0_30
            elif dpd <= 60:
                dpd_bucket = DPDBucket.DPD_31_60
            elif dpd <= 90:
                dpd_bucket = DPDBucket.DPD_61_90
            elif dpd <= 180:
                dpd_bucket = DPDBucket.DPD_91_180
            else:
                dpd_bucket = DPDBucket.DPD_180_PLUS

            # Determine age group
            age = account.age or 35
            if age < 25:
                age_group = "gen_z"
            elif age < 40:
                age_group = "millennial"
            elif age < 55:
                age_group = "gen_x"
            else:
                age_group = "boomer_plus"

            segment = SegmentKey(
                debt_type=debt_type,
                balance_tier=balance_tier,
                dpd_bucket=dpd_bucket,
                age_group=age_group,
                is_digital_native=account.is_digital_native,
                has_mobile=account.phone is not None,
                has_email=account.email is not None,
            )

            # Get channel recommendation from bandit
            used_channels = set(
                entry.get("channel") for entry in account.channel_history
            )
            channel_enum_map = {
                "sms": Channel.SMS,
                "email": Channel.EMAIL,
                "push": Channel.PUSH,
                "voice": Channel.VOICE,
                "mail": Channel.MAIL,
            }
            exclude_channels = {
                channel_enum_map[ch] for ch in used_channels
                if ch in channel_enum_map and len(used_channels) < 3
            }

            selected_channel = optimizer.bandit.select_channel(
                segment,
                exclude_channels=exclude_channels if exclude_channels else None,
            )

            # Get rankings
            rankings = optimizer.bandit.get_channel_rankings(segment)

            circuit.record_success()

            return {
                "selected_channel": selected_channel.value,
                "rankings": [(ch.value, score) for ch, score in rankings[:3]],
                "segment": str(segment),
            }

        except Exception as e:
            circuit.record_failure()
            logger.warning(f"Channel optimizer error: {e}")
            return None

    async def _get_negotiation_insight(self, account: Account) -> Optional[Dict[str, Any]]:
        """Get negotiation strategy insight"""
        circuit = self._circuit_breakers[OptimizationComponent.NEGOTIATION_TUNER.value]

        if not circuit.can_execute():
            return None

        try:
            tuner = self._get_negotiation_tuner()
            if not tuner:
                return None

            strategies = tuner["strategies"]
            game_engine = tuner["game_engine"]

            # Determine debtor segment
            from quan.optimization.negotiation_tuner import DebtorSegment

            # Simple segment classification based on account characteristics
            if account.recovery_probability > 0.6:
                if float(account.balance) <= 250:
                    segment = DebtorSegment.WILLING_ABLE
                else:
                    segment = DebtorSegment.WILLING_UNABLE
            elif account.recovery_probability > 0.3:
                segment = DebtorSegment.UNWILLING_ABLE
            else:
                segment = DebtorSegment.UNWILLING_UNABLE

            # Select strategy based on segment
            if segment == DebtorSegment.WILLING_ABLE:
                recommended_strategy = "aggressive_full"
            elif segment == DebtorSegment.WILLING_UNABLE:
                recommended_strategy = "payment_plan_focus"
            elif segment == DebtorSegment.UNWILLING_ABLE:
                recommended_strategy = "graduated_concession"
            else:
                recommended_strategy = "immediate_settlement"

            strategy_config = strategies.get(recommended_strategy)

            # Calculate settlement offer
            current_round = account.offers_made
            if strategy_config and current_round < len(strategy_config.counter_offer_levels):
                offer_pct = strategy_config.counter_offer_levels[current_round]
            else:
                offer_pct = 0.70  # Default

            offer_amount = account.balance * Decimal(str(offer_pct))

            # Determine urgency
            if current_round < len(strategy_config.urgency_levels) if strategy_config else False:
                urgency = strategy_config.urgency_levels[current_round].value
            else:
                urgency = "medium"

            circuit.record_success()

            return {
                "strategy": recommended_strategy,
                "segment": segment.value,
                "offer_percentage": offer_pct,
                "offer_amount": float(offer_amount),
                "urgency": urgency,
                "max_rounds": strategy_config.max_negotiation_rounds if strategy_config else 5,
            }

        except Exception as e:
            circuit.record_failure()
            logger.warning(f"Negotiation tuner error: {e}")
            return None

    async def _get_lifecycle_insight(self, account: Account) -> Optional[Dict[str, Any]]:
        """Get lifecycle optimization insight"""
        circuit = self._circuit_breakers[OptimizationComponent.LIFECYCLE_OPTIMIZER.value]

        if not circuit.can_execute():
            return None

        try:
            optimizer = self._get_lifecycle_optimizer()
            if not optimizer:
                return None

            # Get optimization recommendations
            recommendations = {}

            # Determine if account should be escalated
            should_escalate = (
                account.contact_attempts >= 5 and
                float(account.balance) >= float(self._fallback_config["escalation_balance_threshold"])
            )

            # Determine if account should be paused
            days_since_contact = 0
            if account.last_contact_date:
                days_since_contact = (datetime.utcnow() - account.last_contact_date).days

            should_pause = (
                account.contact_attempts >= 3 and
                days_since_contact < 3  # Recently contacted
            )

            # Determine if account should be written off
            should_write_off = (
                account.days_past_due > int(self._fallback_config["write_off_threshold_days"]) and
                account.contact_attempts >= int(self._fallback_config["max_contact_attempts"]) and
                float(account.total_paid) == 0
            )

            # Determine if re-engagement is appropriate
            should_re_engage = (
                days_since_contact >= int(self._fallback_config["re_engagement_threshold_days"]) and
                account.status in [AccountStatus.PAUSED, AccountStatus.CONTACTED] and
                account.contact_attempts < int(self._fallback_config["max_contact_attempts"]) * 2
            )

            # Calculate expected ROI for continued collection
            cost_estimate = Decimal("0.50") * account.contact_attempts
            expected_recovery = account.balance * Decimal(str(account.recovery_probability))
            expected_roi = float((expected_recovery - cost_estimate) / cost_estimate) if cost_estimate > 0 else 0

            circuit.record_success()

            return {
                "should_escalate": should_escalate,
                "should_pause": should_pause,
                "should_write_off": should_write_off,
                "should_re_engage": should_re_engage,
                "expected_roi": expected_roi,
                "cost_estimate": float(cost_estimate),
                "days_since_contact": days_since_contact,
            }

        except Exception as e:
            circuit.record_failure()
            logger.warning(f"Lifecycle optimizer error: {e}")
            return None

    async def _get_bottleneck_insight(self, account: Account) -> Optional[Dict[str, Any]]:
        """Get bottleneck analysis insight"""
        circuit = self._circuit_breakers[OptimizationComponent.BOTTLENECK_ANALYZER.value]

        if not circuit.can_execute():
            return None

        try:
            analyzer = self._get_bottleneck_analyzer()
            if not analyzer:
                return None

            # Get stage-specific recommendations
            # Map account status to pipeline stage
            from quan.analysis.bottleneck_analyzer import PipelineStage

            status_to_stage = {
                AccountStatus.NEW: PipelineStage.ACQUIRE,
                AccountStatus.ACTIVE: PipelineStage.LOCATE,
                AccountStatus.CONTACTED: PipelineStage.CONTACT,
                AccountStatus.NEGOTIATING: PipelineStage.NEGOTIATE,
                AccountStatus.PAYMENT_PENDING: PipelineStage.COLLECT,
                AccountStatus.COLLECTED: PipelineStage.CLOSE,
            }

            current_stage = status_to_stage.get(account.status, PipelineStage.CONTACT)

            circuit.record_success()

            return {
                "current_stage": current_stage.value,
                "stage_priority": "high" if current_stage in [
                    PipelineStage.CONTACT, PipelineStage.NEGOTIATE
                ] else "normal",
            }

        except Exception as e:
            circuit.record_failure()
            logger.warning(f"Bottleneck analyzer error: {e}")
            return None

    # =========================================================================
    # STRATEGY SYNTHESIS
    # =========================================================================

    def _synthesize_strategy(
        self,
        account: Account,
        insights: Dict[str, Any],
    ) -> CollectionStrategy:
        """Synthesize strategy from gathered insights"""

        channel_rec = insights.get("channel_recommendation")
        negotiation_rec = insights.get("negotiation_recommendation")
        lifecycle_rec = insights.get("lifecycle_recommendation")

        reasoning = []

        # Determine primary action based on lifecycle state
        if lifecycle_rec:
            if lifecycle_rec.get("should_write_off"):
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.WRITE_OFF,
                    confidence_score=0.8,
                    reasoning=["Account meets write-off criteria"],
                )

            if lifecycle_rec.get("should_escalate"):
                reasoning.append("Account requires escalation due to high balance and failed attempts")
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.ESCALATE,
                    confidence_score=0.7,
                    reasoning=reasoning,
                )

            if lifecycle_rec.get("should_pause"):
                reasoning.append("Account should be paused - recently contacted")
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.PAUSE,
                    timing_recommendation=datetime.utcnow() + timedelta(days=3),
                    confidence_score=0.6,
                    reasoning=reasoning,
                )

            if lifecycle_rec.get("should_re_engage"):
                reasoning.append("Account ready for re-engagement campaign")
                # Fall through to channel selection

        # Determine action type based on account status
        if account.status in [AccountStatus.NEW, AccountStatus.ACTIVE]:
            # Initial contact needed
            action_prefix = ActionType.CONTACT_SMS

            if channel_rec:
                channel = channel_rec.get("selected_channel", "sms")
                action_map = {
                    "sms": ActionType.CONTACT_SMS,
                    "email": ActionType.CONTACT_EMAIL,
                    "push": ActionType.CONTACT_PUSH,
                    "voice": ActionType.CONTACT_VOICE,
                    "mail": ActionType.CONTACT_MAIL,
                }
                action_prefix = action_map.get(channel, ActionType.CONTACT_SMS)
                reasoning.append(f"Channel optimizer selected: {channel}")
            else:
                # Fallback channel selection
                channel = self._fallback_channel_selection(account)
                action_map = {
                    "sms": ActionType.CONTACT_SMS,
                    "email": ActionType.CONTACT_EMAIL,
                    "push": ActionType.CONTACT_PUSH,
                    "voice": ActionType.CONTACT_VOICE,
                    "mail": ActionType.CONTACT_MAIL,
                }
                action_prefix = action_map.get(channel, ActionType.CONTACT_SMS)
                reasoning.append(f"Fallback channel selected: {channel}")

            return CollectionStrategy(
                account_id=account.account_id,
                recommended_action=action_prefix,
                channel=channel_rec.get("selected_channel") if channel_rec else channel,
                negotiation_strategy=negotiation_rec.get("strategy") if negotiation_rec else self._fallback_config["default_negotiation_strategy"],
                urgency_level=negotiation_rec.get("urgency", "medium") if negotiation_rec else "medium",
                fallback_action=ActionType.CONTACT_EMAIL if action_prefix != ActionType.CONTACT_EMAIL else ActionType.CONTACT_SMS,
                reasoning=reasoning,
            )

        elif account.status in [AccountStatus.CONTACTED, AccountStatus.NEGOTIATING]:
            # Negotiation phase
            if negotiation_rec:
                strategy = negotiation_rec.get("strategy", "graduated_concession")
                offer_pct = negotiation_rec.get("offer_percentage", 0.70)
                offer_amt = Decimal(str(negotiation_rec.get("offer_amount", float(account.balance) * 0.70)))
                urgency = negotiation_rec.get("urgency", "medium")

                reasoning.append(f"Negotiation strategy: {strategy}")
                reasoning.append(f"Offer: {offer_pct*100:.0f}% (${offer_amt:.2f})")

                # Determine negotiation action
                if offer_pct >= 0.95:
                    action = ActionType.NEGOTIATE_FULL
                elif offer_pct >= 0.60:
                    action = ActionType.NEGOTIATE_SETTLEMENT
                else:
                    action = ActionType.NEGOTIATE_PLAN

                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=action,
                    channel=channel_rec.get("selected_channel") if channel_rec else "sms",
                    negotiation_strategy=strategy,
                    offer_amount=offer_amt,
                    offer_percentage=offer_pct,
                    urgency_level=urgency,
                    reasoning=reasoning,
                )
            else:
                # Fallback negotiation
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.NEGOTIATE_SETTLEMENT,
                    negotiation_strategy=self._fallback_config["default_negotiation_strategy"],
                    offer_percentage=0.70,
                    offer_amount=account.balance * Decimal("0.70"),
                    urgency_level="medium",
                    reasoning=["Fallback negotiation strategy"],
                )

        elif account.status == AccountStatus.PARTIAL:
            # Follow up on partial payment
            reasoning.append("Following up on partial payment")
            return CollectionStrategy(
                account_id=account.account_id,
                recommended_action=ActionType.CONTACT_SMS,
                channel="sms",
                negotiation_strategy="payment_plan_focus",
                urgency_level="low",
                reasoning=reasoning,
            )

        elif account.status == AccountStatus.PAUSED:
            if lifecycle_rec and lifecycle_rec.get("should_re_engage"):
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.RE_ENGAGE,
                    channel=channel_rec.get("selected_channel") if channel_rec else "sms",
                    reasoning=["Re-engagement campaign triggered"],
                )
            else:
                return CollectionStrategy(
                    account_id=account.account_id,
                    recommended_action=ActionType.PAUSE,
                    timing_recommendation=datetime.utcnow() + timedelta(days=7),
                    reasoning=["Account remains paused"],
                )

        # Default fallback
        return self._generate_fallback_strategy(account, "no_matching_state")

    def _fallback_channel_selection(self, account: Account) -> str:
        """Fallback channel selection when optimizer unavailable"""
        sequence = self._fallback_config["default_channel_sequence"]

        # Get next channel in sequence
        attempts = account.contact_attempts
        if attempts < len(sequence):
            channel = sequence[attempts]
        else:
            channel = "sms"  # Default to SMS

        # Validate channel availability
        if channel == "sms" and not account.phone:
            channel = "email" if account.email else "mail"
        elif channel == "email" and not account.email:
            channel = "sms" if account.phone else "mail"
        elif channel == "push" and not account.has_mobile_app:
            channel = "sms" if account.phone else "email"
        elif channel == "voice" and float(account.balance) < float(self._fallback_config["min_balance_for_voice"]):
            channel = "sms"  # Voice too expensive for small balance

        return channel

    def _generate_fallback_strategy(
        self,
        account: Account,
        reason: str,
    ) -> CollectionStrategy:
        """Generate fallback strategy when normal processing fails"""
        channel = self._fallback_channel_selection(account)

        action_map = {
            "sms": ActionType.CONTACT_SMS,
            "email": ActionType.CONTACT_EMAIL,
            "push": ActionType.CONTACT_PUSH,
            "voice": ActionType.CONTACT_VOICE,
            "mail": ActionType.CONTACT_MAIL,
        }

        return CollectionStrategy(
            account_id=account.account_id,
            recommended_action=action_map.get(channel, ActionType.CONTACT_SMS),
            channel=channel,
            negotiation_strategy=self._fallback_config["default_negotiation_strategy"],
            urgency_level="medium",
            fallback_action=ActionType.CONTACT_EMAIL if channel != "email" else ActionType.CONTACT_SMS,
            confidence_score=0.3,  # Low confidence for fallback
            reasoning=[f"Fallback strategy: {reason}"],
            metadata={"fallback_reason": reason},
        )

    def _calculate_confidence(
        self,
        insights: Dict[str, Any],
        strategy: CollectionStrategy,
    ) -> float:
        """Calculate confidence score for a strategy"""
        base_confidence = 0.5

        # Boost for each component that contributed
        components = insights.get("components_used", [])
        component_boost = len(components) * 0.1

        # Reduce for fallback usage
        if insights.get("fallback_used"):
            base_confidence -= 0.15

        # Get weights
        weights = self._weight_manager.get_weights()

        # Weight by component accuracy
        accuracy_factor = 0
        for component in components:
            accuracy = self._feedback.get_component_accuracy(component)
            weight = weights.get(component, 0.25)
            accuracy_factor += accuracy * weight

        confidence = base_confidence + component_boost + accuracy_factor * 0.3

        # Clamp to valid range
        return max(0.1, min(0.95, confidence))

    # =========================================================================
    # RE-OPTIMIZATION HANDLING
    # =========================================================================

    def _handle_reoptimization(self, component: str, reason: str):
        """Handle re-optimization trigger"""
        logger.info(f"Re-optimization triggered for {component}: {reason}")

        # Reset circuit breaker to allow fresh attempts
        if component in self._circuit_breakers:
            self._circuit_breakers[component].reset()

        # Rebalance weights
        self._weight_manager.rebalance_weights()

        # Clear segment strategy cache
        self._segment_strategies.clear()

        # Log for audit
        self._audit_log.log_decision(
            account_id="SYSTEM",
            decision_type="reoptimization",
            action=ActionType.CLOSE,  # Placeholder
            inputs={"component": component, "reason": reason},
            outputs={"weights_rebalanced": True},
            components=[component],
            fallback_used=False,
            confidence=1.0,
            latency_ms=0,
        )

    # =========================================================================
    # HEALTH AND MONITORING
    # =========================================================================

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the orchestrator"""
        circuit_status = {
            name: {
                "state": circuit.state.value,
                "failure_count": circuit._failure_count,
            }
            for name, circuit in self._circuit_breakers.items()
        }

        feedback_health = self._feedback.get_health_summary()

        return {
            "status": "healthy" if all(
                c["state"] != "open" for c in circuit_status.values()
            ) else "degraded",
            "circuits": circuit_status,
            "rate_limiter": {
                "load": self._rate_limiter.current_load,
                "under_pressure": self._rate_limiter.is_under_pressure,
            },
            "metrics": {
                "total_decisions": self._metrics.total_decisions,
                "success_rate": self._metrics.success_rate,
                "prediction_accuracy": self._metrics.prediction_accuracy,
                "avg_decision_time_ms": self._metrics.avg_decision_time_ms,
            },
            "feedback": feedback_health,
            "fallback_rate": self._audit_log.get_fallback_rate(),
            "weights": self._weight_manager.get_weights(),
            "cached_accounts": len(self._account_cache),
        }

    def get_decision_analytics(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get analytics on recent decisions"""
        recent = self._audit_log.get_recent_decisions(hours)

        if not recent:
            return {"message": "No recent decisions"}

        # Action distribution
        action_dist = defaultdict(int)
        for entry in recent:
            action_dist[entry.action.value] += 1

        # Component usage
        component_usage = defaultdict(int)
        for entry in recent:
            for comp in entry.component_used:
                component_usage[comp] += 1

        # Outcome distribution (for completed decisions)
        outcome_dist = defaultdict(int)
        for entry in recent:
            if entry.outcome:
                outcome_dist[entry.outcome.value] += 1

        # Average confidence
        confidences = [e.confidence for e in recent]
        avg_confidence = statistics.mean(confidences) if confidences else 0

        # Average latency
        latencies = [e.latency_ms for e in recent]
        avg_latency = statistics.mean(latencies) if latencies else 0

        return {
            "period_hours": hours,
            "total_decisions": len(recent),
            "action_distribution": dict(action_dist),
            "component_usage": dict(component_usage),
            "outcome_distribution": dict(outcome_dist),
            "average_confidence": avg_confidence,
            "average_latency_ms": avg_latency,
            "fallback_rate": sum(1 for e in recent if e.fallback_used) / len(recent),
        }

    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================

    async def start(self):
        """Start background tasks"""
        if self._running:
            return

        self._running = True

        # Start periodic tasks
        self._background_tasks.append(
            asyncio.create_task(self._periodic_health_check())
        )
        self._background_tasks.append(
            asyncio.create_task(self._periodic_weight_rebalance())
        )

        logger.info("MasterCollectionOrchestrator started")

    async def stop(self):
        """Stop background tasks"""
        self._running = False

        for task in self._background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._background_tasks.clear()
        logger.info("MasterCollectionOrchestrator stopped")

    async def _periodic_health_check(self):
        """Periodic health check task"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute

                # Check for drift
                for component in OptimizationComponent:
                    drift, magnitude = self._feedback.check_drift(component.value)
                    if drift:
                        self._feedback.trigger_reoptimization(
                            component.value,
                            f"periodic drift check: {magnitude:.3f}",
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _periodic_weight_rebalance(self):
        """Periodic weight rebalancing"""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                self._weight_manager.rebalance_weights()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Weight rebalance error: {e}")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_orchestrator_instance: Optional[MasterCollectionOrchestrator] = None


def get_orchestrator() -> MasterCollectionOrchestrator:
    """Get singleton orchestrator instance"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MasterCollectionOrchestrator()
    return _orchestrator_instance


# =============================================================================
# MAIN DEMONSTRATION
# =============================================================================

async def demo_orchestrator():
    """Demonstrate orchestrator capabilities"""
    print("\n" + "=" * 80)
    print("  MASTER COLLECTION ORCHESTRATOR DEMONSTRATION")
    print("=" * 80)

    orchestrator = get_orchestrator()
    await orchestrator.start()

    # Create sample accounts
    sample_accounts = [
        Account(
            account_id="DEMO-001",
            balance=Decimal("275.50"),
            original_balance=Decimal("275.50"),
            days_past_due=35,
            debt_type="bnpl",
            phone="+15551234567",
            email="customer1@example.com",
            has_mobile_app=True,
            age=28,
            is_digital_native=True,
            recovery_probability=0.65,
        ),
        Account(
            account_id="DEMO-002",
            balance=Decimal("850.00"),
            original_balance=Decimal("850.00"),
            days_past_due=75,
            debt_type="medical",
            phone="+15559876543",
            email="customer2@example.com",
            age=55,
            is_digital_native=False,
            recovery_probability=0.35,
        ),
        Account(
            account_id="DEMO-003",
            balance=Decimal("125.00"),
            original_balance=Decimal("125.00"),
            days_past_due=15,
            debt_type="subscription",
            email="customer3@example.com",
            has_mobile_app=True,
            age=22,
            is_digital_native=True,
            recovery_probability=0.75,
        ),
    ]

    print("\n  Processing sample accounts...")
    print("  " + "-" * 76)

    for account in sample_accounts:
        print(f"\n  Account: {account.account_id}")
        print(f"    Balance: ${account.balance}")
        print(f"    DPD: {account.days_past_due}")
        print(f"    Debt Type: {account.debt_type}")

        # Process account
        strategy = await orchestrator.process_account(account)

        print(f"\n    Recommended Action: {strategy.recommended_action.value}")
        print(f"    Channel: {strategy.channel or 'N/A'}")
        print(f"    Strategy: {strategy.negotiation_strategy or 'N/A'}")
        print(f"    Urgency: {strategy.urgency_level}")
        print(f"    Confidence: {strategy.confidence_score:.2f}")
        if strategy.offer_percentage:
            print(f"    Offer: {strategy.offer_percentage*100:.0f}% (${strategy.offer_amount:.2f})")
        print(f"    Reasoning: {', '.join(strategy.reasoning)}")

        # Simulate outcome
        if random.random() < strategy.confidence_score:
            outcome = DecisionOutcome.SUCCESS
            amount = account.balance * Decimal(str(random.uniform(0.5, 1.0)))
        else:
            outcome = random.choice([
                DecisionOutcome.NO_RESPONSE,
                DecisionOutcome.REFUSED,
            ])
            amount = Decimal("0")

        result = ActionResult(
            account_id=account.account_id,
            action=strategy.recommended_action,
            outcome=outcome,
            amount_collected=amount,
            response_received=outcome != DecisionOutcome.NO_RESPONSE,
        )

        await orchestrator.update_outcome(account.account_id, result)
        print(f"    Simulated Outcome: {outcome.value}")
        if amount > 0:
            print(f"    Amount Collected: ${amount:.2f}")

    # Get portfolio stats
    print("\n" + "-" * 80)
    print("  PORTFOLIO STATISTICS")
    print("-" * 80)

    stats = await orchestrator.get_portfolio_stats()
    print(f"\n    Total Accounts: {stats.total_accounts}")
    print(f"    Active Accounts: {stats.active_accounts}")
    print(f"    Total Balance: ${stats.total_balance:.2f}")
    print(f"    Total Collected: ${stats.total_collected:.2f}")
    print(f"    Recovery Rate: {stats.recovery_rate:.1%}")

    # Get health status
    print("\n" + "-" * 80)
    print("  ORCHESTRATOR HEALTH STATUS")
    print("-" * 80)

    health = orchestrator.get_health_status()
    print(f"\n    Status: {health['status']}")
    print(f"    Rate Limiter Load: {health['rate_limiter']['load']:.1%}")
    print(f"    Total Decisions: {health['metrics']['total_decisions']}")
    print(f"    Avg Decision Time: {health['metrics']['avg_decision_time_ms']:.1f}ms")
    print(f"    Fallback Rate: {health['fallback_rate']:.1%}")

    print(f"\n    Circuit Breakers:")
    for name, status in health['circuits'].items():
        print(f"      {name}: {status['state']}")

    print(f"\n    Component Weights:")
    for comp, weight in health['weights'].items():
        print(f"      {comp}: {weight:.2f}")

    # Get analytics
    print("\n" + "-" * 80)
    print("  DECISION ANALYTICS (Last 24h)")
    print("-" * 80)

    analytics = orchestrator.get_decision_analytics(hours=24)
    print(f"\n    Total Decisions: {analytics.get('total_decisions', 0)}")
    print(f"    Average Confidence: {analytics.get('average_confidence', 0):.2f}")
    print(f"    Average Latency: {analytics.get('average_latency_ms', 0):.1f}ms")

    if analytics.get('action_distribution'):
        print(f"\n    Action Distribution:")
        for action, count in analytics['action_distribution'].items():
            print(f"      {action}: {count}")

    await orchestrator.stop()

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_orchestrator())
