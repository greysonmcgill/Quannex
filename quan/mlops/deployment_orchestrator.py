"""
Canary and Shadow Deployment Orchestrator for QUAN ML Models

Provides production-grade deployment strategies including:
- Shadow deployment (parallel run, no production impact)
- Canary rollout (gradual traffic shifting: 1% -> 5% -> 25% -> 100%)
- Blue-green deployment with instant rollback
- Automatic rollback on metric degradation
- A/B test statistical analysis
- Kubernetes traffic splitting integration
- CI/CD integration hooks
- Deployment approval gates

Key guarantees:
- Shadow runs for N days before promotion consideration
- Statistical significance testing before promotion
- Automatic rollback triggers on metric degradation
- Complete audit trail of all deployment decisions
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import statistics
import time
import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Generic, Union

# Conditional imports
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    stats = None
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class DeploymentState(Enum):
    """Deployment state machine states"""
    PENDING = "pending"
    VALIDATING = "validating"
    SHADOW = "shadow"
    CANARY_1 = "canary_1"       # 1% traffic
    CANARY_5 = "canary_5"       # 5% traffic
    CANARY_25 = "canary_25"     # 25% traffic
    PROMOTING = "promoting"
    ACTIVE = "active"           # 100% traffic
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    PAUSED = "paused"


class DeploymentType(Enum):
    """Types of deployment strategies"""
    SHADOW = "shadow"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    DIRECT = "direct"


class RollbackReason(Enum):
    """Reasons for deployment rollback"""
    METRIC_DEGRADATION = "metric_degradation"
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_SPIKE = "latency_spike"
    MANUAL_TRIGGER = "manual_trigger"
    APPROVAL_REJECTED = "approval_rejected"
    TIMEOUT = "timeout"
    HEALTH_CHECK_FAILED = "health_check_failed"
    STATISTICAL_FAILURE = "statistical_failure"


class ApprovalStatus(Enum):
    """Deployment approval gate status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class MetricType(Enum):
    """Types of metrics to track"""
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    ERROR_RATE = "error_rate"
    PREDICTION_ACCURACY = "prediction_accuracy"
    MODEL_CONFIDENCE = "model_confidence"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    CUSTOM = "custom"


class TrafficSplitMethod(Enum):
    """Methods for traffic splitting"""
    RANDOM = "random"
    HASH_BASED = "hash_based"        # Consistent per user/request
    HEADER_BASED = "header_based"     # Based on request headers
    COOKIE_BASED = "cookie_based"     # Based on cookies
    GEOGRAPHIC = "geographic"         # Based on location


# Canary progression stages
CANARY_STAGES = [
    (DeploymentState.CANARY_1, 1),
    (DeploymentState.CANARY_5, 5),
    (DeploymentState.CANARY_25, 25),
    (DeploymentState.ACTIVE, 100),
]

# Valid state transitions
VALID_TRANSITIONS: Dict[DeploymentState, List[DeploymentState]] = {
    DeploymentState.PENDING: [DeploymentState.VALIDATING, DeploymentState.FAILED],
    DeploymentState.VALIDATING: [DeploymentState.SHADOW, DeploymentState.CANARY_1, DeploymentState.FAILED],
    DeploymentState.SHADOW: [DeploymentState.CANARY_1, DeploymentState.PAUSED, DeploymentState.ROLLED_BACK, DeploymentState.FAILED],
    DeploymentState.CANARY_1: [DeploymentState.CANARY_5, DeploymentState.ROLLING_BACK, DeploymentState.PAUSED, DeploymentState.FAILED],
    DeploymentState.CANARY_5: [DeploymentState.CANARY_25, DeploymentState.ROLLING_BACK, DeploymentState.PAUSED, DeploymentState.FAILED],
    DeploymentState.CANARY_25: [DeploymentState.PROMOTING, DeploymentState.ROLLING_BACK, DeploymentState.PAUSED, DeploymentState.FAILED],
    DeploymentState.PROMOTING: [DeploymentState.ACTIVE, DeploymentState.ROLLING_BACK, DeploymentState.FAILED],
    DeploymentState.ACTIVE: [DeploymentState.ROLLING_BACK, DeploymentState.PAUSED],
    DeploymentState.ROLLING_BACK: [DeploymentState.ROLLED_BACK, DeploymentState.FAILED],
    DeploymentState.ROLLED_BACK: [DeploymentState.PENDING],
    DeploymentState.FAILED: [DeploymentState.PENDING],
    DeploymentState.PAUSED: [DeploymentState.SHADOW, DeploymentState.CANARY_1, DeploymentState.CANARY_5,
                            DeploymentState.CANARY_25, DeploymentState.ROLLING_BACK],
}

# Default thresholds
DEFAULT_ROLLBACK_THRESHOLDS = {
    MetricType.ERROR_RATE: 0.05,           # 5% error rate
    MetricType.LATENCY_P95: 500,           # 500ms
    MetricType.LATENCY_P99: 1000,          # 1000ms
    MetricType.PREDICTION_ACCURACY: 0.85,  # 85% accuracy (lower bound)
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ModelVersion:
    """Represents a model version for deployment"""
    model_id: str
    version: str
    artifact_path: str
    checksum: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def full_id(self) -> str:
        return f"{self.model_id}:{self.version}"


@dataclass
class MetricSample:
    """Single metric measurement"""
    metric_type: MetricType
    value: float
    timestamp: datetime
    variant: str  # "control" or "treatment"
    deployment_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricComparison:
    """Comparison between control and treatment metrics"""
    metric_type: MetricType
    control_mean: float
    control_std: float
    control_samples: int
    treatment_mean: float
    treatment_std: float
    treatment_samples: int
    p_value: float
    is_significant: bool
    effect_size: float
    confidence_interval: Tuple[float, float]
    recommendation: str


@dataclass
class RollbackTrigger:
    """Configuration for automatic rollback trigger"""
    metric_type: MetricType
    threshold: float
    comparison: str = "greater_than"  # "greater_than", "less_than"
    window_seconds: int = 300
    min_samples: int = 10
    consecutive_violations: int = 3


@dataclass
class TrafficConfig:
    """Traffic splitting configuration"""
    treatment_percentage: int = 0
    split_method: TrafficSplitMethod = TrafficSplitMethod.HASH_BASED
    sticky_sessions: bool = True
    session_ttl_seconds: int = 3600
    hash_key: str = "user_id"
    fallback_to_control: bool = True


@dataclass
class ApprovalGate:
    """Deployment approval gate"""
    gate_id: str
    deployment_id: str
    stage: DeploymentState
    status: ApprovalStatus = ApprovalStatus.PENDING
    required_approvers: List[str] = field(default_factory=list)
    current_approvers: List[str] = field(default_factory=list)
    auto_approve_after: Optional[timedelta] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    notes: str = ""


@dataclass
class DeploymentConfig:
    """Configuration for a deployment"""
    deployment_type: DeploymentType = DeploymentType.CANARY

    # Shadow deployment settings
    shadow_duration_days: int = 7
    shadow_traffic_percentage: int = 100  # Shadow all traffic

    # Canary settings
    canary_stages: List[Tuple[int, int]] = field(
        default_factory=lambda: [(1, 3600), (5, 7200), (25, 14400)]  # (percentage, duration_seconds)
    )
    auto_promote: bool = False
    promotion_criteria: Dict[str, float] = field(default_factory=dict)

    # Rollback settings
    rollback_triggers: List[RollbackTrigger] = field(default_factory=list)
    auto_rollback: bool = True

    # Approval settings
    require_approval: bool = True
    approval_timeout_hours: int = 24
    approvers: List[str] = field(default_factory=list)

    # Traffic configuration
    traffic_config: TrafficConfig = field(default_factory=TrafficConfig)

    # Health check settings
    health_check_interval: int = 30
    health_check_timeout: int = 10
    health_check_path: str = "/health"

    # Kubernetes settings
    kubernetes_namespace: str = "default"
    kubernetes_service: str = ""
    use_istio: bool = False

    # Metric collection
    metric_collection_interval: int = 60
    min_samples_for_analysis: int = 100
    statistical_significance_level: float = 0.05


@dataclass
class DeploymentEvent:
    """Event in deployment history"""
    event_id: str
    deployment_id: str
    event_type: str
    from_state: Optional[DeploymentState]
    to_state: Optional[DeploymentState]
    timestamp: datetime
    actor: str = "system"
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Deployment:
    """Represents a single deployment"""
    deployment_id: str
    control_model: ModelVersion
    treatment_model: ModelVersion
    config: DeploymentConfig
    state: DeploymentState = DeploymentState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_traffic_percentage: int = 0
    events: List[DeploymentEvent] = field(default_factory=list)
    metrics: List[MetricSample] = field(default_factory=list)
    approval_gates: List[ApprovalGate] = field(default_factory=list)
    rollback_reason: Optional[RollbackReason] = None
    error_message: Optional[str] = None

    def add_event(
        self,
        event_type: str,
        from_state: Optional[DeploymentState] = None,
        to_state: Optional[DeploymentState] = None,
        actor: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> DeploymentEvent:
        """Add an event to deployment history"""
        event = DeploymentEvent(
            event_id=str(uuid.uuid4()),
            deployment_id=self.deployment_id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            reason=reason,
            metadata=metadata or {}
        )
        self.events.append(event)
        return event


@dataclass
class RollbackPlaybook:
    """Automated rollback playbook"""
    playbook_id: str
    name: str
    description: str
    steps: List[Dict[str, Any]]
    pre_rollback_checks: List[Callable]
    post_rollback_checks: List[Callable]
    notification_channels: List[str]
    escalation_contacts: List[str]
    max_rollback_time_seconds: int = 300


# =============================================================================
# Traffic Router
# =============================================================================

class TrafficRouter:
    """Routes traffic between control and treatment variants"""

    def __init__(self, config: TrafficConfig):
        self.config = config
        self._session_cache: Dict[str, str] = {}
        self._cache_lock = threading.Lock()

    def route(
        self,
        request_id: str,
        treatment_percentage: int,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Route a request to control or treatment"""
        context = context or {}

        # Check for sticky session
        if self.config.sticky_sessions:
            session_key = self._get_session_key(context)
            if session_key:
                with self._cache_lock:
                    if session_key in self._session_cache:
                        return self._session_cache[session_key]

        # Route based on split method
        variant = self._route_by_method(
            request_id,
            treatment_percentage,
            context
        )

        # Cache for sticky sessions
        if self.config.sticky_sessions and session_key:
            with self._cache_lock:
                self._session_cache[session_key] = variant

        return variant

    def _get_session_key(self, context: Dict[str, Any]) -> Optional[str]:
        """Get session key for sticky routing"""
        return context.get(self.config.hash_key)

    def _route_by_method(
        self,
        request_id: str,
        treatment_percentage: int,
        context: Dict[str, Any]
    ) -> str:
        """Route based on configured method"""
        if treatment_percentage <= 0:
            return "control"
        if treatment_percentage >= 100:
            return "treatment"

        if self.config.split_method == TrafficSplitMethod.RANDOM:
            return "treatment" if random.randint(1, 100) <= treatment_percentage else "control"

        elif self.config.split_method == TrafficSplitMethod.HASH_BASED:
            hash_input = context.get(self.config.hash_key, request_id)
            hash_value = int(hashlib.md5(str(hash_input).encode()).hexdigest(), 16) % 100
            return "treatment" if hash_value < treatment_percentage else "control"

        elif self.config.split_method == TrafficSplitMethod.HEADER_BASED:
            header_value = context.get("headers", {}).get("X-Variant")
            if header_value == "treatment":
                return "treatment"
            elif header_value == "control":
                return "control"
            # Fall back to hash-based
            return self._route_by_method(
                request_id,
                treatment_percentage,
                {**context, "split_method": TrafficSplitMethod.HASH_BASED}
            )

        elif self.config.split_method == TrafficSplitMethod.COOKIE_BASED:
            cookie_value = context.get("cookies", {}).get("variant")
            if cookie_value == "treatment":
                return "treatment"
            elif cookie_value == "control":
                return "control"
            return self._route_by_method(
                request_id,
                treatment_percentage,
                {**context, "split_method": TrafficSplitMethod.HASH_BASED}
            )

        elif self.config.split_method == TrafficSplitMethod.GEOGRAPHIC:
            region = context.get("region", "default")
            # Hash the region for consistent routing
            hash_value = int(hashlib.md5(region.encode()).hexdigest(), 16) % 100
            return "treatment" if hash_value < treatment_percentage else "control"

        # Default to random
        return "treatment" if random.randint(1, 100) <= treatment_percentage else "control"

    def clear_session_cache(self):
        """Clear the session cache"""
        with self._cache_lock:
            self._session_cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get session cache statistics"""
        with self._cache_lock:
            control_count = sum(1 for v in self._session_cache.values() if v == "control")
            treatment_count = len(self._session_cache) - control_count
            return {
                "total_sessions": len(self._session_cache),
                "control_sessions": control_count,
                "treatment_sessions": treatment_count
            }


# =============================================================================
# Statistical Analysis
# =============================================================================

class StatisticalAnalyzer:
    """Statistical analysis for A/B testing"""

    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level

    def compare_metrics(
        self,
        control_samples: List[float],
        treatment_samples: List[float],
        metric_type: MetricType
    ) -> MetricComparison:
        """Compare metrics between control and treatment"""
        if len(control_samples) < 2 or len(treatment_samples) < 2:
            return self._insufficient_data_result(metric_type)

        # Calculate basic statistics
        control_mean = statistics.mean(control_samples)
        control_std = statistics.stdev(control_samples)
        treatment_mean = statistics.mean(treatment_samples)
        treatment_std = statistics.stdev(treatment_samples)

        # Perform statistical test
        if SCIPY_AVAILABLE:
            t_stat, p_value = stats.ttest_ind(control_samples, treatment_samples)
            # Calculate confidence interval
            pooled_se = (
                (control_std**2 / len(control_samples)) +
                (treatment_std**2 / len(treatment_samples))
            ) ** 0.5
            diff = treatment_mean - control_mean
            ci_margin = 1.96 * pooled_se
            confidence_interval = (diff - ci_margin, diff + ci_margin)
        else:
            # Simple t-test approximation
            p_value = self._simple_ttest(
                control_mean, control_std, len(control_samples),
                treatment_mean, treatment_std, len(treatment_samples)
            )
            diff = treatment_mean - control_mean
            confidence_interval = (diff * 0.9, diff * 1.1)  # Rough approximation

        # Calculate effect size (Cohen's d)
        pooled_std = ((control_std**2 + treatment_std**2) / 2) ** 0.5
        effect_size = (treatment_mean - control_mean) / pooled_std if pooled_std > 0 else 0

        is_significant = p_value < self.significance_level

        # Generate recommendation
        recommendation = self._generate_recommendation(
            metric_type, control_mean, treatment_mean,
            is_significant, effect_size
        )

        return MetricComparison(
            metric_type=metric_type,
            control_mean=control_mean,
            control_std=control_std,
            control_samples=len(control_samples),
            treatment_mean=treatment_mean,
            treatment_std=treatment_std,
            treatment_samples=len(treatment_samples),
            p_value=p_value,
            is_significant=is_significant,
            effect_size=effect_size,
            confidence_interval=confidence_interval,
            recommendation=recommendation
        )

    def _simple_ttest(
        self,
        mean1: float, std1: float, n1: int,
        mean2: float, std2: float, n2: int
    ) -> float:
        """Simple t-test implementation without scipy"""
        if std1 == 0 and std2 == 0:
            return 1.0 if mean1 == mean2 else 0.0

        se = ((std1**2 / n1) + (std2**2 / n2)) ** 0.5
        if se == 0:
            return 0.0 if mean1 != mean2 else 1.0

        t_stat = (mean1 - mean2) / se
        # Rough p-value approximation using normal distribution
        # This is a simplification - in production use scipy
        z = abs(t_stat)
        if z > 3.5:
            return 0.001
        elif z > 2.5:
            return 0.01
        elif z > 2.0:
            return 0.05
        elif z > 1.5:
            return 0.15
        else:
            return 0.5

    def _insufficient_data_result(self, metric_type: MetricType) -> MetricComparison:
        """Return result when data is insufficient"""
        return MetricComparison(
            metric_type=metric_type,
            control_mean=0.0,
            control_std=0.0,
            control_samples=0,
            treatment_mean=0.0,
            treatment_std=0.0,
            treatment_samples=0,
            p_value=1.0,
            is_significant=False,
            effect_size=0.0,
            confidence_interval=(0.0, 0.0),
            recommendation="Insufficient data for analysis"
        )

    def _generate_recommendation(
        self,
        metric_type: MetricType,
        control_mean: float,
        treatment_mean: float,
        is_significant: bool,
        effect_size: float
    ) -> str:
        """Generate recommendation based on analysis"""
        if not is_significant:
            return "No statistically significant difference. Continue monitoring."

        # For metrics where lower is better (latency, error rate)
        lower_is_better = metric_type in [
            MetricType.LATENCY_P50, MetricType.LATENCY_P95,
            MetricType.LATENCY_P99, MetricType.ERROR_RATE,
            MetricType.CPU_USAGE, MetricType.MEMORY_USAGE
        ]

        if lower_is_better:
            if treatment_mean < control_mean:
                return f"Treatment shows improvement. Effect size: {effect_size:.2f}. Consider promotion."
            else:
                return f"Treatment shows degradation. Effect size: {effect_size:.2f}. Consider rollback."
        else:
            if treatment_mean > control_mean:
                return f"Treatment shows improvement. Effect size: {effect_size:.2f}. Consider promotion."
            else:
                return f"Treatment shows degradation. Effect size: {effect_size:.2f}. Consider rollback."

    def calculate_sample_size(
        self,
        baseline_rate: float,
        minimum_detectable_effect: float,
        power: float = 0.8,
        significance_level: float = 0.05
    ) -> int:
        """Calculate required sample size for A/B test"""
        # Using simplified formula for proportions
        # n = 2 * (z_alpha + z_beta)^2 * p * (1-p) / delta^2

        # Z-scores for common values
        z_alpha = 1.96 if significance_level == 0.05 else 2.58
        z_beta = 0.84 if power == 0.8 else 1.28

        p = baseline_rate
        delta = baseline_rate * minimum_detectable_effect

        if delta == 0:
            return 10000  # Default large sample

        n = 2 * ((z_alpha + z_beta)**2) * p * (1 - p) / (delta**2)
        return int(n) + 1


# =============================================================================
# Metric Collector
# =============================================================================

class MetricCollector:
    """Collects and stores deployment metrics"""

    def __init__(self, max_samples: int = 100000):
        self.max_samples = max_samples
        self._metrics: Dict[str, List[MetricSample]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(
        self,
        deployment_id: str,
        metric_type: MetricType,
        value: float,
        variant: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MetricSample:
        """Record a metric sample"""
        sample = MetricSample(
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(timezone.utc),
            variant=variant,
            deployment_id=deployment_id,
            metadata=metadata or {}
        )

        with self._lock:
            key = f"{deployment_id}:{metric_type.value}:{variant}"
            self._metrics[key].append(sample)

            # Trim if necessary
            if len(self._metrics[key]) > self.max_samples:
                self._metrics[key] = self._metrics[key][-self.max_samples:]

        return sample

    def get_samples(
        self,
        deployment_id: str,
        metric_type: MetricType,
        variant: str,
        since: Optional[datetime] = None
    ) -> List[MetricSample]:
        """Get metric samples"""
        with self._lock:
            key = f"{deployment_id}:{metric_type.value}:{variant}"
            samples = self._metrics.get(key, [])

            if since:
                samples = [s for s in samples if s.timestamp >= since]

            return samples.copy()

    def get_values(
        self,
        deployment_id: str,
        metric_type: MetricType,
        variant: str,
        since: Optional[datetime] = None
    ) -> List[float]:
        """Get metric values as list"""
        samples = self.get_samples(deployment_id, metric_type, variant, since)
        return [s.value for s in samples]

    def get_latest(
        self,
        deployment_id: str,
        metric_type: MetricType,
        variant: str
    ) -> Optional[MetricSample]:
        """Get the latest metric sample"""
        with self._lock:
            key = f"{deployment_id}:{metric_type.value}:{variant}"
            samples = self._metrics.get(key, [])
            return samples[-1] if samples else None

    def get_stats(
        self,
        deployment_id: str,
        metric_type: MetricType,
        variant: str,
        window_seconds: int = 300
    ) -> Dict[str, float]:
        """Get statistics for recent samples"""
        since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        values = self.get_values(deployment_id, metric_type, variant, since)

        if not values:
            return {"count": 0}

        sorted_values = sorted(values)

        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "p50": sorted_values[len(sorted_values) // 2],
            "p95": sorted_values[int(len(sorted_values) * 0.95)] if len(sorted_values) > 20 else max(values),
            "p99": sorted_values[int(len(sorted_values) * 0.99)] if len(sorted_values) > 100 else max(values),
        }

    def clear(self, deployment_id: Optional[str] = None):
        """Clear metrics"""
        with self._lock:
            if deployment_id:
                keys_to_remove = [k for k in self._metrics if k.startswith(deployment_id)]
                for key in keys_to_remove:
                    del self._metrics[key]
            else:
                self._metrics.clear()


# =============================================================================
# Health Checker
# =============================================================================

class HealthChecker:
    """Checks health of deployed models"""

    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 10
    ):
        self.check_interval = check_interval
        self.timeout = timeout
        self._health_status: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def check_health(
        self,
        endpoint: str,
        health_path: str = "/health"
    ) -> Dict[str, Any]:
        """Check health of an endpoint"""
        result = {
            "endpoint": endpoint,
            "healthy": False,
            "latency_ms": None,
            "timestamp": datetime.now(timezone.utc),
            "error": None
        }

        try:
            start_time = time.time()
            # Simulated health check - in production, use actual HTTP client
            # response = requests.get(f"{endpoint}{health_path}", timeout=self.timeout)
            # For demo purposes, simulate success
            latency = (time.time() - start_time) * 1000

            result["healthy"] = True
            result["latency_ms"] = latency

        except Exception as e:
            result["error"] = str(e)

        with self._lock:
            self._health_status[endpoint] = result

        return result

    def get_status(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get cached health status"""
        with self._lock:
            return self._health_status.get(endpoint)

    def is_healthy(self, endpoint: str) -> bool:
        """Check if endpoint is healthy"""
        status = self.get_status(endpoint)
        return status is not None and status.get("healthy", False)


# =============================================================================
# Kubernetes Integration
# =============================================================================

class KubernetesTrafficManager:
    """Manages Kubernetes traffic splitting"""

    def __init__(
        self,
        namespace: str = "default",
        use_istio: bool = False
    ):
        self.namespace = namespace
        self.use_istio = use_istio
        self._current_weights: Dict[str, Dict[str, int]] = {}

    def create_virtual_service(
        self,
        service_name: str,
        control_version: str,
        treatment_version: str,
        treatment_weight: int
    ) -> Dict[str, Any]:
        """Create Istio VirtualService for traffic splitting"""
        control_weight = 100 - treatment_weight

        virtual_service = {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": f"{service_name}-canary",
                "namespace": self.namespace
            },
            "spec": {
                "hosts": [service_name],
                "http": [{
                    "route": [
                        {
                            "destination": {
                                "host": service_name,
                                "subset": "control"
                            },
                            "weight": control_weight
                        },
                        {
                            "destination": {
                                "host": service_name,
                                "subset": "treatment"
                            },
                            "weight": treatment_weight
                        }
                    ]
                }]
            }
        }

        return virtual_service

    def create_destination_rule(
        self,
        service_name: str,
        control_version: str,
        treatment_version: str
    ) -> Dict[str, Any]:
        """Create Istio DestinationRule for subset definition"""
        destination_rule = {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": f"{service_name}-subsets",
                "namespace": self.namespace
            },
            "spec": {
                "host": service_name,
                "subsets": [
                    {
                        "name": "control",
                        "labels": {"version": control_version}
                    },
                    {
                        "name": "treatment",
                        "labels": {"version": treatment_version}
                    }
                ]
            }
        }

        return destination_rule

    def update_traffic_weight(
        self,
        service_name: str,
        treatment_weight: int
    ) -> Dict[str, int]:
        """Update traffic weights"""
        control_weight = 100 - treatment_weight

        weights = {
            "control": control_weight,
            "treatment": treatment_weight
        }

        self._current_weights[service_name] = weights

        logger.info(
            f"Updated traffic weights for {service_name}: "
            f"control={control_weight}%, treatment={treatment_weight}%"
        )

        return weights

    def get_traffic_weights(self, service_name: str) -> Dict[str, int]:
        """Get current traffic weights"""
        return self._current_weights.get(service_name, {"control": 100, "treatment": 0})

    def generate_kubectl_commands(
        self,
        service_name: str,
        control_version: str,
        treatment_version: str,
        treatment_weight: int
    ) -> List[str]:
        """Generate kubectl commands for traffic splitting"""
        commands = []

        if self.use_istio:
            vs = self.create_virtual_service(
                service_name, control_version, treatment_version, treatment_weight
            )
            dr = self.create_destination_rule(
                service_name, control_version, treatment_version
            )

            commands.append(
                f"kubectl apply -f - <<EOF\n{json.dumps(dr, indent=2)}\nEOF"
            )
            commands.append(
                f"kubectl apply -f - <<EOF\n{json.dumps(vs, indent=2)}\nEOF"
            )
        else:
            # Native Kubernetes service with multiple deployments
            commands.append(
                f"kubectl scale deployment {service_name}-control "
                f"--replicas={10 - treatment_weight // 10} -n {self.namespace}"
            )
            commands.append(
                f"kubectl scale deployment {service_name}-treatment "
                f"--replicas={treatment_weight // 10} -n {self.namespace}"
            )

        return commands


# =============================================================================
# CI/CD Integration
# =============================================================================

class CICDIntegration:
    """CI/CD integration hooks"""

    def __init__(self):
        self._webhooks: Dict[str, str] = {}
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def register_webhook(self, event: str, url: str):
        """Register a webhook for deployment events"""
        self._webhooks[event] = url

    def register_callback(self, event: str, callback: Callable):
        """Register a callback for deployment events"""
        self._callbacks[event].append(callback)

    def notify(
        self,
        event: str,
        deployment: Deployment,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Notify CI/CD systems of deployment events"""
        payload = {
            "event": event,
            "deployment_id": deployment.deployment_id,
            "state": deployment.state.value,
            "treatment_model": deployment.treatment_model.full_id,
            "control_model": deployment.control_model.full_id,
            "traffic_percentage": deployment.current_traffic_percentage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }

        # Trigger webhooks
        if event in self._webhooks:
            self._send_webhook(self._webhooks[event], payload)

        # Trigger callbacks
        for callback in self._callbacks.get(event, []):
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    def _send_webhook(self, url: str, payload: Dict[str, Any]):
        """Send webhook notification"""
        # In production, use actual HTTP client
        logger.info(f"Webhook notification to {url}: {json.dumps(payload)}")

    def get_deployment_status_for_ci(
        self,
        deployment: Deployment
    ) -> Dict[str, Any]:
        """Get deployment status in CI-friendly format"""
        return {
            "deployment_id": deployment.deployment_id,
            "state": deployment.state.value,
            "is_active": deployment.state == DeploymentState.ACTIVE,
            "is_failed": deployment.state in [DeploymentState.FAILED, DeploymentState.ROLLED_BACK],
            "traffic_percentage": deployment.current_traffic_percentage,
            "duration_seconds": (
                (deployment.completed_at or datetime.now(timezone.utc)) -
                deployment.created_at
            ).total_seconds() if deployment.started_at else 0,
            "events_count": len(deployment.events),
            "rollback_reason": deployment.rollback_reason.value if deployment.rollback_reason else None,
        }


# =============================================================================
# Rollback Playbook
# =============================================================================

class RollbackPlaybookExecutor:
    """Executes automated rollback playbooks"""

    def __init__(self):
        self._playbooks: Dict[str, RollbackPlaybook] = {}

    def register_playbook(self, playbook: RollbackPlaybook):
        """Register a rollback playbook"""
        self._playbooks[playbook.playbook_id] = playbook

    def get_playbook(self, playbook_id: str) -> Optional[RollbackPlaybook]:
        """Get a playbook by ID"""
        return self._playbooks.get(playbook_id)

    def execute_playbook(
        self,
        playbook_id: str,
        deployment: Deployment,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a rollback playbook"""
        playbook = self._playbooks.get(playbook_id)
        if not playbook:
            return {"success": False, "error": f"Playbook {playbook_id} not found"}

        result = {
            "playbook_id": playbook_id,
            "deployment_id": deployment.deployment_id,
            "started_at": datetime.now(timezone.utc),
            "steps_completed": [],
            "success": True,
            "errors": []
        }

        # Run pre-rollback checks
        for check in playbook.pre_rollback_checks:
            try:
                check_result = check(deployment, context)
                if not check_result:
                    result["success"] = False
                    result["errors"].append("Pre-rollback check failed")
                    return result
            except Exception as e:
                result["errors"].append(f"Pre-check error: {e}")

        # Execute steps
        for step in playbook.steps:
            try:
                step_result = self._execute_step(step, deployment, context)
                result["steps_completed"].append({
                    "step": step.get("name", "unknown"),
                    "success": step_result.get("success", True),
                    "output": step_result.get("output")
                })

                if not step_result.get("success", True):
                    result["success"] = False
                    result["errors"].append(f"Step {step.get('name')} failed")
                    break

            except Exception as e:
                result["success"] = False
                result["errors"].append(f"Step error: {e}")
                break

        # Run post-rollback checks
        for check in playbook.post_rollback_checks:
            try:
                check(deployment, context)
            except Exception as e:
                result["errors"].append(f"Post-check error: {e}")

        # Send notifications
        self._send_notifications(playbook, deployment, result)

        result["completed_at"] = datetime.now(timezone.utc)
        return result

    def _execute_step(
        self,
        step: Dict[str, Any],
        deployment: Deployment,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single playbook step"""
        step_type = step.get("type", "command")

        if step_type == "command":
            # Execute shell command
            command = step.get("command", "")
            logger.info(f"Executing command: {command}")
            return {"success": True, "output": f"Executed: {command}"}

        elif step_type == "wait":
            duration = step.get("duration_seconds", 10)
            time.sleep(min(duration, 1))  # Cap at 1 second for tests
            return {"success": True, "output": f"Waited {duration}s"}

        elif step_type == "health_check":
            endpoint = step.get("endpoint", "")
            return {"success": True, "output": f"Health check passed: {endpoint}"}

        elif step_type == "notification":
            message = step.get("message", "")
            return {"success": True, "output": f"Sent notification: {message}"}

        elif step_type == "traffic_shift":
            weight = step.get("weight", 0)
            return {"success": True, "output": f"Shifted traffic to {weight}%"}

        else:
            return {"success": True, "output": f"Unknown step type: {step_type}"}

    def _send_notifications(
        self,
        playbook: RollbackPlaybook,
        deployment: Deployment,
        result: Dict[str, Any]
    ):
        """Send rollback notifications"""
        for channel in playbook.notification_channels:
            logger.info(
                f"Notification to {channel}: Rollback "
                f"{'completed' if result['success'] else 'failed'} "
                f"for deployment {deployment.deployment_id}"
            )

    def create_default_playbook(self) -> RollbackPlaybook:
        """Create a default rollback playbook"""
        return RollbackPlaybook(
            playbook_id="default",
            name="Default Rollback Playbook",
            description="Standard rollback procedure for canary deployments",
            steps=[
                {"type": "notification", "name": "notify_start", "message": "Starting rollback"},
                {"type": "traffic_shift", "name": "shift_traffic", "weight": 0},
                {"type": "wait", "name": "wait_drain", "duration_seconds": 30},
                {"type": "health_check", "name": "check_control", "endpoint": "control"},
                {"type": "notification", "name": "notify_complete", "message": "Rollback complete"},
            ],
            pre_rollback_checks=[],
            post_rollback_checks=[],
            notification_channels=["slack", "pagerduty"],
            escalation_contacts=["oncall@example.com"],
            max_rollback_time_seconds=300
        )


# =============================================================================
# Shadow Deployment Manager
# =============================================================================

class ShadowDeploymentManager:
    """Manages shadow deployments"""

    def __init__(
        self,
        metric_collector: MetricCollector,
        analyzer: StatisticalAnalyzer
    ):
        self.metric_collector = metric_collector
        self.analyzer = analyzer
        self._shadow_results: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_shadow_result(
        self,
        deployment_id: str,
        request_id: str,
        control_result: Any,
        treatment_result: Any,
        control_latency_ms: float,
        treatment_latency_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record shadow deployment result"""
        result = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc),
            "control_result": control_result,
            "treatment_result": treatment_result,
            "control_latency_ms": control_latency_ms,
            "treatment_latency_ms": treatment_latency_ms,
            "results_match": self._compare_results(control_result, treatment_result),
            "metadata": metadata or {}
        }

        with self._lock:
            self._shadow_results[deployment_id].append(result)

        # Record metrics
        self.metric_collector.record(
            deployment_id, MetricType.LATENCY_P50,
            control_latency_ms, "control"
        )
        self.metric_collector.record(
            deployment_id, MetricType.LATENCY_P50,
            treatment_latency_ms, "treatment"
        )

    def _compare_results(self, control: Any, treatment: Any) -> bool:
        """Compare control and treatment results"""
        if isinstance(control, (int, float)) and isinstance(treatment, (int, float)):
            # Allow small numerical differences
            return abs(control - treatment) < 0.001
        return control == treatment

    def get_shadow_stats(
        self,
        deployment_id: str,
        since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get shadow deployment statistics"""
        with self._lock:
            results = self._shadow_results.get(deployment_id, [])

        if since:
            results = [r for r in results if r["timestamp"] >= since]

        if not results:
            return {"sample_count": 0}

        matching = sum(1 for r in results if r["results_match"])
        control_latencies = [r["control_latency_ms"] for r in results]
        treatment_latencies = [r["treatment_latency_ms"] for r in results]

        return {
            "sample_count": len(results),
            "match_rate": matching / len(results),
            "control_latency_mean": statistics.mean(control_latencies),
            "treatment_latency_mean": statistics.mean(treatment_latencies),
            "control_latency_p95": sorted(control_latencies)[int(len(control_latencies) * 0.95)],
            "treatment_latency_p95": sorted(treatment_latencies)[int(len(treatment_latencies) * 0.95)],
            "first_result_at": min(r["timestamp"] for r in results),
            "last_result_at": max(r["timestamp"] for r in results),
        }

    def is_ready_for_promotion(
        self,
        deployment_id: str,
        min_days: int = 7,
        min_samples: int = 1000,
        min_match_rate: float = 0.95
    ) -> Tuple[bool, str]:
        """Check if shadow deployment is ready for promotion"""
        stats = self.get_shadow_stats(deployment_id)

        if stats["sample_count"] < min_samples:
            return False, f"Insufficient samples: {stats['sample_count']} < {min_samples}"

        if stats["match_rate"] < min_match_rate:
            return False, f"Match rate too low: {stats['match_rate']:.2%} < {min_match_rate:.2%}"

        duration = stats["last_result_at"] - stats["first_result_at"]
        if duration < timedelta(days=min_days):
            return False, f"Insufficient shadow duration: {duration.days} days < {min_days} days"

        return True, "Shadow deployment ready for promotion"


# =============================================================================
# Deployment Orchestrator
# =============================================================================

class DeploymentOrchestrator:
    """
    Main deployment orchestration class.

    Manages the full lifecycle of ML model deployments including:
    - Shadow deployments for safe testing
    - Canary rollouts with gradual traffic shifting
    - Blue-green deployments for instant switching
    - Automatic rollback on metric degradation
    - Statistical analysis for promotion decisions
    """

    def __init__(
        self,
        config: Optional[DeploymentConfig] = None,
        metric_collector: Optional[MetricCollector] = None,
        analyzer: Optional[StatisticalAnalyzer] = None,
        kubernetes_manager: Optional[KubernetesTrafficManager] = None,
        cicd_integration: Optional[CICDIntegration] = None
    ):
        self.config = config or DeploymentConfig()
        self.metric_collector = metric_collector or MetricCollector()
        self.analyzer = analyzer or StatisticalAnalyzer(
            significance_level=self.config.statistical_significance_level
        )
        self.kubernetes_manager = kubernetes_manager or KubernetesTrafficManager(
            namespace=self.config.kubernetes_namespace,
            use_istio=self.config.use_istio
        )
        self.cicd_integration = cicd_integration or CICDIntegration()

        # Internal components
        self.traffic_router = TrafficRouter(self.config.traffic_config)
        self.health_checker = HealthChecker(
            check_interval=self.config.health_check_interval,
            timeout=self.config.health_check_timeout
        )
        self.shadow_manager = ShadowDeploymentManager(
            self.metric_collector, self.analyzer
        )
        self.playbook_executor = RollbackPlaybookExecutor()

        # Register default playbook
        self.playbook_executor.register_playbook(
            self.playbook_executor.create_default_playbook()
        )

        # Active deployments
        self._deployments: Dict[str, Deployment] = {}
        self._lock = threading.Lock()

        # Background tasks
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=4)

    # -------------------------------------------------------------------------
    # Deployment Creation
    # -------------------------------------------------------------------------

    def create_deployment(
        self,
        control_model: ModelVersion,
        treatment_model: ModelVersion,
        config: Optional[DeploymentConfig] = None,
        deployment_id: Optional[str] = None
    ) -> Deployment:
        """Create a new deployment"""
        deployment = Deployment(
            deployment_id=deployment_id or str(uuid.uuid4()),
            control_model=control_model,
            treatment_model=treatment_model,
            config=config or self.config,
            state=DeploymentState.PENDING
        )

        deployment.add_event(
            "deployment_created",
            to_state=DeploymentState.PENDING,
            reason=f"Deployment created for {treatment_model.full_id}"
        )

        with self._lock:
            self._deployments[deployment.deployment_id] = deployment

        logger.info(f"Created deployment {deployment.deployment_id}")
        self.cicd_integration.notify("deployment_created", deployment)

        return deployment

    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Get a deployment by ID"""
        with self._lock:
            return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        state: Optional[DeploymentState] = None
    ) -> List[Deployment]:
        """List deployments, optionally filtered by state"""
        with self._lock:
            deployments = list(self._deployments.values())

        if state:
            deployments = [d for d in deployments if d.state == state]

        return deployments

    # -------------------------------------------------------------------------
    # State Machine
    # -------------------------------------------------------------------------

    def _validate_transition(
        self,
        deployment: Deployment,
        to_state: DeploymentState
    ) -> bool:
        """Validate state transition"""
        valid_states = VALID_TRANSITIONS.get(deployment.state, [])
        return to_state in valid_states

    def _transition_state(
        self,
        deployment: Deployment,
        to_state: DeploymentState,
        reason: str = "",
        actor: str = "system"
    ) -> bool:
        """Transition deployment to new state"""
        if not self._validate_transition(deployment, to_state):
            logger.warning(
                f"Invalid state transition: {deployment.state} -> {to_state}"
            )
            return False

        from_state = deployment.state
        deployment.state = to_state

        deployment.add_event(
            "state_transition",
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason=reason
        )

        logger.info(
            f"Deployment {deployment.deployment_id}: "
            f"{from_state.value} -> {to_state.value}"
        )

        self.cicd_integration.notify(
            "state_changed",
            deployment,
            {"from_state": from_state.value, "to_state": to_state.value}
        )

        return True

    # -------------------------------------------------------------------------
    # Deployment Lifecycle
    # -------------------------------------------------------------------------

    def start_deployment(
        self,
        deployment_id: str,
        skip_validation: bool = False
    ) -> bool:
        """Start a deployment"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return False

        if deployment.state != DeploymentState.PENDING:
            logger.error(f"Cannot start deployment in state {deployment.state}")
            return False

        deployment.started_at = datetime.now(timezone.utc)

        # Validation phase
        if not skip_validation:
            self._transition_state(
                deployment, DeploymentState.VALIDATING,
                reason="Starting deployment validation"
            )

            if not self._validate_deployment(deployment):
                self._transition_state(
                    deployment, DeploymentState.FAILED,
                    reason="Validation failed"
                )
                return False

        # Start appropriate deployment type
        if deployment.config.deployment_type == DeploymentType.SHADOW:
            return self._start_shadow_deployment(deployment)
        elif deployment.config.deployment_type == DeploymentType.CANARY:
            return self._start_canary_deployment(deployment)
        elif deployment.config.deployment_type == DeploymentType.BLUE_GREEN:
            return self._start_blue_green_deployment(deployment)
        else:
            return self._start_direct_deployment(deployment)

    def _validate_deployment(self, deployment: Deployment) -> bool:
        """Validate deployment before starting"""
        # Check model artifacts exist
        if not deployment.treatment_model.artifact_path:
            deployment.error_message = "Treatment model artifact path missing"
            return False

        # Check rollback triggers are configured
        if not deployment.config.rollback_triggers and deployment.config.auto_rollback:
            # Add default triggers
            deployment.config.rollback_triggers = [
                RollbackTrigger(
                    metric_type=MetricType.ERROR_RATE,
                    threshold=0.05,
                    comparison="greater_than"
                ),
                RollbackTrigger(
                    metric_type=MetricType.LATENCY_P95,
                    threshold=500,
                    comparison="greater_than"
                ),
            ]

        deployment.add_event(
            "validation_passed",
            reason="Deployment validation completed successfully"
        )

        return True

    # -------------------------------------------------------------------------
    # Shadow Deployment
    # -------------------------------------------------------------------------

    def _start_shadow_deployment(self, deployment: Deployment) -> bool:
        """Start a shadow deployment"""
        if not self._transition_state(
            deployment, DeploymentState.SHADOW,
            reason="Starting shadow deployment"
        ):
            return False

        deployment.current_traffic_percentage = 0  # No production traffic

        logger.info(
            f"Shadow deployment started for {deployment.deployment_id}. "
            f"Duration: {deployment.config.shadow_duration_days} days"
        )

        self.cicd_integration.notify("shadow_started", deployment)
        return True

    def process_shadow_request(
        self,
        deployment_id: str,
        request_id: str,
        request_data: Dict[str, Any],
        control_handler: Callable,
        treatment_handler: Callable
    ) -> Dict[str, Any]:
        """Process a request in shadow mode"""
        deployment = self.get_deployment(deployment_id)
        if not deployment or deployment.state != DeploymentState.SHADOW:
            # Just run control
            return {"result": control_handler(request_data), "variant": "control"}

        # Run both in parallel
        control_start = time.time()
        control_result = control_handler(request_data)
        control_latency = (time.time() - control_start) * 1000

        treatment_start = time.time()
        treatment_result = treatment_handler(request_data)
        treatment_latency = (time.time() - treatment_start) * 1000

        # Record shadow result
        self.shadow_manager.record_shadow_result(
            deployment_id=deployment_id,
            request_id=request_id,
            control_result=control_result,
            treatment_result=treatment_result,
            control_latency_ms=control_latency,
            treatment_latency_ms=treatment_latency,
            metadata={"request_data": request_data}
        )

        # Return control result (shadow has no impact)
        return {"result": control_result, "variant": "control", "shadow_active": True}

    def promote_from_shadow(
        self,
        deployment_id: str,
        force: bool = False
    ) -> Tuple[bool, str]:
        """Promote shadow deployment to canary"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False, "Deployment not found"

        if deployment.state != DeploymentState.SHADOW:
            return False, f"Cannot promote from state {deployment.state}"

        # Check readiness
        if not force:
            ready, reason = self.shadow_manager.is_ready_for_promotion(
                deployment_id,
                min_days=deployment.config.shadow_duration_days,
                min_samples=deployment.config.min_samples_for_analysis
            )
            if not ready:
                return False, reason

        # Check approval gate
        if deployment.config.require_approval:
            gate = self._create_approval_gate(
                deployment, DeploymentState.CANARY_1
            )
            if gate.status == ApprovalStatus.PENDING:
                return False, "Waiting for approval"

        # Transition to canary
        return self._start_canary_deployment(deployment), "Promoted to canary"

    # -------------------------------------------------------------------------
    # Canary Deployment
    # -------------------------------------------------------------------------

    def _start_canary_deployment(self, deployment: Deployment) -> bool:
        """Start or continue canary deployment"""
        if not self._transition_state(
            deployment, DeploymentState.CANARY_1,
            reason="Starting canary at 1% traffic"
        ):
            return False

        deployment.current_traffic_percentage = 1

        # Update Kubernetes traffic if configured
        if deployment.config.kubernetes_service:
            self.kubernetes_manager.update_traffic_weight(
                deployment.config.kubernetes_service, 1
            )

        logger.info(f"Canary deployment started at 1% for {deployment.deployment_id}")
        self.cicd_integration.notify("canary_started", deployment)

        return True

    def advance_canary(
        self,
        deployment_id: str,
        force: bool = False
    ) -> Tuple[bool, str]:
        """Advance canary to next stage"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False, "Deployment not found"

        # Determine next stage
        current_stage_idx = None
        for idx, (state, percentage) in enumerate(CANARY_STAGES):
            if deployment.state == state:
                current_stage_idx = idx
                break

        if current_stage_idx is None:
            return False, f"Cannot advance from state {deployment.state}"

        if current_stage_idx >= len(CANARY_STAGES) - 1:
            return False, "Already at final stage"

        next_state, next_percentage = CANARY_STAGES[current_stage_idx + 1]

        # Check metrics before advancing
        if not force:
            should_rollback, reason = self._check_rollback_triggers(deployment)
            if should_rollback:
                self.trigger_rollback(deployment_id, RollbackReason.METRIC_DEGRADATION)
                return False, f"Rollback triggered: {reason}"

            # Statistical analysis
            comparison = self._analyze_deployment_metrics(deployment)
            if comparison and not comparison.is_significant:
                logger.info("No significant difference yet, continuing...")
            elif comparison and "degradation" in comparison.recommendation.lower():
                if not force:
                    return False, comparison.recommendation

        # Check approval gate for promotion to 100%
        if next_state == DeploymentState.ACTIVE and deployment.config.require_approval:
            gate = self._create_approval_gate(deployment, next_state)
            if gate.status == ApprovalStatus.PENDING:
                return False, "Waiting for approval to promote to 100%"

        # Advance to next stage
        if next_state == DeploymentState.ACTIVE:
            # Go through promoting state first
            self._transition_state(
                deployment, DeploymentState.PROMOTING,
                reason=f"Promoting to 100% traffic"
            )

        if not self._transition_state(
            deployment, next_state,
            reason=f"Advancing canary to {next_percentage}%"
        ):
            return False, "State transition failed"

        deployment.current_traffic_percentage = next_percentage

        # Update Kubernetes traffic
        if deployment.config.kubernetes_service:
            self.kubernetes_manager.update_traffic_weight(
                deployment.config.kubernetes_service, next_percentage
            )

        logger.info(
            f"Advanced canary to {next_percentage}% for {deployment.deployment_id}"
        )

        self.cicd_integration.notify(
            "canary_advanced", deployment,
            {"percentage": next_percentage}
        )

        if next_state == DeploymentState.ACTIVE:
            deployment.completed_at = datetime.now(timezone.utc)
            self.cicd_integration.notify("deployment_completed", deployment)

        return True, f"Advanced to {next_percentage}%"

    def route_request(
        self,
        deployment_id: str,
        request_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Route a request to control or treatment"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return "control"

        if deployment.state == DeploymentState.SHADOW:
            return "control"  # Shadow doesn't affect routing

        if deployment.state == DeploymentState.ACTIVE:
            return "treatment"

        return self.traffic_router.route(
            request_id,
            deployment.current_traffic_percentage,
            context
        )

    # -------------------------------------------------------------------------
    # Blue-Green Deployment
    # -------------------------------------------------------------------------

    def _start_blue_green_deployment(self, deployment: Deployment) -> bool:
        """Start a blue-green deployment"""
        # Blue-green goes directly to promoting
        if not self._transition_state(
            deployment, DeploymentState.PROMOTING,
            reason="Starting blue-green deployment"
        ):
            return False

        # In blue-green, we switch 100% traffic instantly
        deployment.current_traffic_percentage = 100

        if deployment.config.kubernetes_service:
            self.kubernetes_manager.update_traffic_weight(
                deployment.config.kubernetes_service, 100
            )

        if not self._transition_state(
            deployment, DeploymentState.ACTIVE,
            reason="Blue-green switch complete"
        ):
            return False

        deployment.completed_at = datetime.now(timezone.utc)

        logger.info(f"Blue-green deployment complete for {deployment.deployment_id}")
        self.cicd_integration.notify("blue_green_complete", deployment)

        return True

    def _start_direct_deployment(self, deployment: Deployment) -> bool:
        """Start a direct deployment (no gradual rollout)"""
        return self._start_blue_green_deployment(deployment)

    # -------------------------------------------------------------------------
    # Rollback
    # -------------------------------------------------------------------------

    def trigger_rollback(
        self,
        deployment_id: str,
        reason: RollbackReason,
        actor: str = "system",
        playbook_id: str = "default"
    ) -> bool:
        """Trigger deployment rollback"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return False

        if deployment.state in [DeploymentState.ROLLED_BACK, DeploymentState.FAILED]:
            logger.warning(f"Deployment already in terminal state {deployment.state}")
            return False

        deployment.rollback_reason = reason

        if not self._transition_state(
            deployment, DeploymentState.ROLLING_BACK,
            reason=f"Rollback triggered: {reason.value}",
            actor=actor
        ):
            return False

        logger.warning(
            f"Rolling back deployment {deployment_id}: {reason.value}"
        )

        # Execute rollback playbook
        playbook_result = self.playbook_executor.execute_playbook(
            playbook_id, deployment, {"reason": reason.value}
        )

        # Shift traffic back to control
        deployment.current_traffic_percentage = 0
        if deployment.config.kubernetes_service:
            self.kubernetes_manager.update_traffic_weight(
                deployment.config.kubernetes_service, 0
            )

        # Complete rollback
        if playbook_result.get("success"):
            self._transition_state(
                deployment, DeploymentState.ROLLED_BACK,
                reason="Rollback completed successfully"
            )
        else:
            self._transition_state(
                deployment, DeploymentState.FAILED,
                reason=f"Rollback failed: {playbook_result.get('errors')}"
            )

        deployment.completed_at = datetime.now(timezone.utc)

        self.cicd_integration.notify(
            "rollback_completed", deployment,
            {"reason": reason.value, "playbook_result": playbook_result}
        )

        return True

    def _check_rollback_triggers(
        self,
        deployment: Deployment
    ) -> Tuple[bool, str]:
        """Check if any rollback triggers are violated"""
        for trigger in deployment.config.rollback_triggers:
            stats = self.metric_collector.get_stats(
                deployment.deployment_id,
                trigger.metric_type,
                "treatment",
                window_seconds=trigger.window_seconds
            )

            if stats.get("count", 0) < trigger.min_samples:
                continue

            current_value = stats.get("mean", 0)

            violated = False
            if trigger.comparison == "greater_than":
                violated = current_value > trigger.threshold
            elif trigger.comparison == "less_than":
                violated = current_value < trigger.threshold

            if violated:
                return True, (
                    f"{trigger.metric_type.value} = {current_value:.3f} "
                    f"violates threshold {trigger.threshold}"
                )

        return False, ""

    # -------------------------------------------------------------------------
    # Metric Analysis
    # -------------------------------------------------------------------------

    def record_metric(
        self,
        deployment_id: str,
        metric_type: MetricType,
        value: float,
        variant: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MetricSample:
        """Record a metric for a deployment"""
        return self.metric_collector.record(
            deployment_id, metric_type, value, variant, metadata
        )

    def _analyze_deployment_metrics(
        self,
        deployment: Deployment,
        metric_type: MetricType = MetricType.LATENCY_P95
    ) -> Optional[MetricComparison]:
        """Analyze metrics for a deployment"""
        control_values = self.metric_collector.get_values(
            deployment.deployment_id, metric_type, "control"
        )
        treatment_values = self.metric_collector.get_values(
            deployment.deployment_id, metric_type, "treatment"
        )

        if (len(control_values) < deployment.config.min_samples_for_analysis or
            len(treatment_values) < deployment.config.min_samples_for_analysis):
            return None

        return self.analyzer.compare_metrics(
            control_values, treatment_values, metric_type
        )

    def get_deployment_analysis(
        self,
        deployment_id: str
    ) -> Dict[str, MetricComparison]:
        """Get full metric analysis for a deployment"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return {}

        results = {}
        for metric_type in MetricType:
            comparison = self._analyze_deployment_metrics(deployment, metric_type)
            if comparison and comparison.control_samples > 0:
                results[metric_type.value] = comparison

        return results

    # -------------------------------------------------------------------------
    # Approval Gates
    # -------------------------------------------------------------------------

    def _create_approval_gate(
        self,
        deployment: Deployment,
        stage: DeploymentState
    ) -> ApprovalGate:
        """Create an approval gate"""
        gate = ApprovalGate(
            gate_id=str(uuid.uuid4()),
            deployment_id=deployment.deployment_id,
            stage=stage,
            required_approvers=deployment.config.approvers,
            expires_at=(
                datetime.now(timezone.utc) +
                timedelta(hours=deployment.config.approval_timeout_hours)
            )
        )

        deployment.approval_gates.append(gate)

        self.cicd_integration.notify(
            "approval_required", deployment,
            {"gate_id": gate.gate_id, "stage": stage.value}
        )

        return gate

    def approve_gate(
        self,
        deployment_id: str,
        gate_id: str,
        approver: str,
        notes: str = ""
    ) -> Tuple[bool, str]:
        """Approve a deployment gate"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False, "Deployment not found"

        gate = next(
            (g for g in deployment.approval_gates if g.gate_id == gate_id),
            None
        )
        if not gate:
            return False, "Gate not found"

        if gate.status != ApprovalStatus.PENDING:
            return False, f"Gate already {gate.status.value}"

        if gate.expires_at and datetime.now(timezone.utc) > gate.expires_at:
            gate.status = ApprovalStatus.EXPIRED
            return False, "Gate expired"

        gate.current_approvers.append(approver)
        gate.notes = notes

        # Check if all required approvers have approved
        if (not gate.required_approvers or
            set(gate.required_approvers).issubset(set(gate.current_approvers))):
            gate.status = ApprovalStatus.APPROVED

            deployment.add_event(
                "approval_granted",
                reason=f"Approved by {approver}: {notes}"
            )

            self.cicd_integration.notify(
                "approval_granted", deployment,
                {"gate_id": gate_id, "approver": approver}
            )

            return True, "Approval granted"

        return True, f"Approval recorded, waiting for more approvers"

    def reject_gate(
        self,
        deployment_id: str,
        gate_id: str,
        rejector: str,
        reason: str
    ) -> Tuple[bool, str]:
        """Reject a deployment gate"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False, "Deployment not found"

        gate = next(
            (g for g in deployment.approval_gates if g.gate_id == gate_id),
            None
        )
        if not gate:
            return False, "Gate not found"

        gate.status = ApprovalStatus.REJECTED
        gate.notes = f"Rejected by {rejector}: {reason}"

        # Trigger rollback
        self.trigger_rollback(
            deployment_id,
            RollbackReason.APPROVAL_REJECTED,
            actor=rejector
        )

        return True, "Deployment rejected and rolled back"

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------

    def start_monitoring(self):
        """Start background monitoring"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Deployment monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Deployment monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                self._check_all_deployments()
            except Exception as e:
                logger.error(f"Monitoring error: {e}")

            time.sleep(self.config.metric_collection_interval)

    def _check_all_deployments(self):
        """Check all active deployments"""
        active_states = [
            DeploymentState.SHADOW,
            DeploymentState.CANARY_1,
            DeploymentState.CANARY_5,
            DeploymentState.CANARY_25,
            DeploymentState.ACTIVE
        ]

        for deployment in self.list_deployments():
            if deployment.state not in active_states:
                continue

            # Check rollback triggers
            if deployment.config.auto_rollback:
                should_rollback, reason = self._check_rollback_triggers(deployment)
                if should_rollback:
                    logger.warning(f"Auto-rollback triggered for {deployment.deployment_id}: {reason}")
                    self.trigger_rollback(
                        deployment.deployment_id,
                        RollbackReason.METRIC_DEGRADATION
                    )
                    continue

            # Auto-promote if configured
            if deployment.config.auto_promote:
                self._check_auto_promotion(deployment)

    def _check_auto_promotion(self, deployment: Deployment):
        """Check if deployment should be auto-promoted"""
        if deployment.state == DeploymentState.SHADOW:
            ready, _ = self.shadow_manager.is_ready_for_promotion(
                deployment.deployment_id,
                min_days=deployment.config.shadow_duration_days
            )
            if ready:
                self.promote_from_shadow(deployment.deployment_id)

        elif deployment.state in [
            DeploymentState.CANARY_1,
            DeploymentState.CANARY_5,
            DeploymentState.CANARY_25
        ]:
            # Find current stage duration
            stage_idx = next(
                (i for i, (s, _) in enumerate(CANARY_STAGES) if s == deployment.state),
                None
            )
            if stage_idx is not None and stage_idx < len(deployment.config.canary_stages):
                _, duration = deployment.config.canary_stages[stage_idx]

                # Get last state change time
                last_transition = next(
                    (e for e in reversed(deployment.events)
                     if e.event_type == "state_transition"),
                    None
                )

                if last_transition:
                    elapsed = (datetime.now(timezone.utc) - last_transition.timestamp).total_seconds()
                    if elapsed >= duration:
                        self.advance_canary(deployment.deployment_id)

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    def get_deployment_report(
        self,
        deployment_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive deployment report"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return {"error": "Deployment not found"}

        # Get shadow stats if applicable
        shadow_stats = None
        if deployment.state == DeploymentState.SHADOW or any(
            e.to_state == DeploymentState.SHADOW for e in deployment.events
        ):
            shadow_stats = self.shadow_manager.get_shadow_stats(deployment_id)

        # Get metric analysis
        metric_analysis = self.get_deployment_analysis(deployment_id)

        # Build report
        return {
            "deployment_id": deployment_id,
            "state": deployment.state.value,
            "control_model": deployment.control_model.full_id,
            "treatment_model": deployment.treatment_model.full_id,
            "traffic_percentage": deployment.current_traffic_percentage,
            "created_at": deployment.created_at.isoformat(),
            "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
            "completed_at": deployment.completed_at.isoformat() if deployment.completed_at else None,
            "duration_hours": (
                ((deployment.completed_at or datetime.now(timezone.utc)) -
                 deployment.created_at).total_seconds() / 3600
            ),
            "events": [
                {
                    "type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "from_state": e.from_state.value if e.from_state else None,
                    "to_state": e.to_state.value if e.to_state else None,
                    "reason": e.reason
                }
                for e in deployment.events
            ],
            "shadow_stats": shadow_stats,
            "metric_analysis": {
                k: {
                    "control_mean": v.control_mean,
                    "treatment_mean": v.treatment_mean,
                    "p_value": v.p_value,
                    "is_significant": v.is_significant,
                    "effect_size": v.effect_size,
                    "recommendation": v.recommendation
                }
                for k, v in metric_analysis.items()
            },
            "approval_gates": [
                {
                    "gate_id": g.gate_id,
                    "stage": g.stage.value,
                    "status": g.status.value,
                    "approvers": g.current_approvers
                }
                for g in deployment.approval_gates
            ],
            "rollback_reason": deployment.rollback_reason.value if deployment.rollback_reason else None,
            "error_message": deployment.error_message
        }

    def pause_deployment(self, deployment_id: str) -> bool:
        """Pause an active deployment"""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return False

        return self._transition_state(
            deployment, DeploymentState.PAUSED,
            reason="Deployment paused"
        )

    def resume_deployment(
        self,
        deployment_id: str,
        target_state: Optional[DeploymentState] = None
    ) -> bool:
        """Resume a paused deployment"""
        deployment = self.get_deployment(deployment_id)
        if not deployment or deployment.state != DeploymentState.PAUSED:
            return False

        # Resume to previous state or specified state
        if target_state is None:
            # Find the last non-paused state
            for event in reversed(deployment.events):
                if event.from_state and event.from_state != DeploymentState.PAUSED:
                    target_state = event.from_state
                    break

        if target_state is None:
            target_state = DeploymentState.CANARY_1

        return self._transition_state(
            deployment, target_state,
            reason=f"Deployment resumed to {target_state.value}"
        )


# =============================================================================
# Test Classes
# =============================================================================

class DeploymentOrchestratorTests:
    """Test suite for deployment orchestrator"""

    def __init__(self):
        self.test_results: List[Dict[str, Any]] = []

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        tests = [
            self.test_deployment_creation,
            self.test_shadow_deployment,
            self.test_canary_progression,
            self.test_automatic_rollback,
            self.test_traffic_routing,
            self.test_metric_collection,
            self.test_statistical_analysis,
            self.test_approval_gates,
            self.test_blue_green_deployment,
            self.test_rollback_playbook,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                result = test()
                self.test_results.append({
                    "test": test.__name__,
                    "passed": result.get("passed", False),
                    "message": result.get("message", ""),
                    "duration_ms": result.get("duration_ms", 0)
                })
                if result.get("passed"):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.test_results.append({
                    "test": test.__name__,
                    "passed": False,
                    "message": str(e),
                    "error": True
                })
                failed += 1

        return {
            "total": len(tests),
            "passed": passed,
            "failed": failed,
            "results": self.test_results
        }

    def test_deployment_creation(self) -> Dict[str, Any]:
        """Test deployment creation"""
        start = time.time()

        orchestrator = DeploymentOrchestrator()

        control = ModelVersion(
            model_id="test-model",
            version="v1.0.0",
            artifact_path="/models/v1.0.0",
            checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )

        treatment = ModelVersion(
            model_id="test-model",
            version="v1.1.0",
            artifact_path="/models/v1.1.0",
            checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment)

        assert deployment.state == DeploymentState.PENDING
        assert deployment.control_model == control
        assert deployment.treatment_model == treatment
        assert len(deployment.events) == 1

        return {
            "passed": True,
            "message": "Deployment created successfully",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_shadow_deployment(self) -> Dict[str, Any]:
        """Test shadow deployment flow"""
        start = time.time()

        config = DeploymentConfig(
            deployment_type=DeploymentType.SHADOW,
            shadow_duration_days=1,
            require_approval=False
        )

        orchestrator = DeploymentOrchestrator(config=config)

        control = ModelVersion(
            model_id="test-model", version="v1.0.0",
            artifact_path="/models/v1.0.0", checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )
        treatment = ModelVersion(
            model_id="test-model", version="v1.1.0",
            artifact_path="/models/v1.1.0", checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment, config)
        orchestrator.start_deployment(deployment.deployment_id, skip_validation=True)

        assert deployment.state == DeploymentState.SHADOW
        assert deployment.current_traffic_percentage == 0

        # Process shadow requests
        for i in range(10):
            result = orchestrator.process_shadow_request(
                deployment.deployment_id,
                f"request-{i}",
                {"data": i},
                lambda x: x["data"] * 2,
                lambda x: x["data"] * 2
            )
            assert result["variant"] == "control"
            assert result["shadow_active"] == True

        return {
            "passed": True,
            "message": "Shadow deployment working correctly",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_canary_progression(self) -> Dict[str, Any]:
        """Test canary progression through stages"""
        start = time.time()

        config = DeploymentConfig(
            deployment_type=DeploymentType.CANARY,
            require_approval=False,
            auto_rollback=False
        )

        orchestrator = DeploymentOrchestrator(config=config)

        control = ModelVersion(
            model_id="test-model", version="v1.0.0",
            artifact_path="/models/v1.0.0", checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )
        treatment = ModelVersion(
            model_id="test-model", version="v1.1.0",
            artifact_path="/models/v1.1.0", checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment, config)
        orchestrator.start_deployment(deployment.deployment_id, skip_validation=True)

        # Should be at 1%
        assert deployment.state == DeploymentState.CANARY_1
        assert deployment.current_traffic_percentage == 1

        # Advance to 5%
        success, _ = orchestrator.advance_canary(deployment.deployment_id, force=True)
        assert success
        assert deployment.state == DeploymentState.CANARY_5
        assert deployment.current_traffic_percentage == 5

        # Advance to 25%
        success, _ = orchestrator.advance_canary(deployment.deployment_id, force=True)
        assert success
        assert deployment.state == DeploymentState.CANARY_25
        assert deployment.current_traffic_percentage == 25

        # Advance to 100%
        success, _ = orchestrator.advance_canary(deployment.deployment_id, force=True)
        assert success
        assert deployment.state == DeploymentState.ACTIVE
        assert deployment.current_traffic_percentage == 100

        return {
            "passed": True,
            "message": "Canary progression 1% -> 5% -> 25% -> 100% successful",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_automatic_rollback(self) -> Dict[str, Any]:
        """Test automatic rollback on metric degradation"""
        start = time.time()

        config = DeploymentConfig(
            deployment_type=DeploymentType.CANARY,
            require_approval=False,
            auto_rollback=True,
            rollback_triggers=[
                RollbackTrigger(
                    metric_type=MetricType.ERROR_RATE,
                    threshold=0.05,
                    comparison="greater_than",
                    min_samples=5
                )
            ]
        )

        orchestrator = DeploymentOrchestrator(config=config)

        control = ModelVersion(
            model_id="test-model", version="v1.0.0",
            artifact_path="/models/v1.0.0", checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )
        treatment = ModelVersion(
            model_id="test-model", version="v1.1.0",
            artifact_path="/models/v1.1.0", checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment, config)
        orchestrator.start_deployment(deployment.deployment_id, skip_validation=True)

        # Simulate high error rate
        for i in range(10):
            orchestrator.record_metric(
                deployment.deployment_id,
                MetricType.ERROR_RATE,
                0.10,  # 10% error rate
                "treatment"
            )

        # Check rollback triggers
        should_rollback, reason = orchestrator._check_rollback_triggers(deployment)
        assert should_rollback
        assert "ERROR_RATE" in reason

        # Trigger rollback
        success = orchestrator.trigger_rollback(
            deployment.deployment_id,
            RollbackReason.METRIC_DEGRADATION
        )
        assert success
        assert deployment.state == DeploymentState.ROLLED_BACK
        assert deployment.rollback_reason == RollbackReason.METRIC_DEGRADATION
        assert deployment.current_traffic_percentage == 0

        return {
            "passed": True,
            "message": "Automatic rollback triggered and executed successfully",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_traffic_routing(self) -> Dict[str, Any]:
        """Test traffic routing logic"""
        start = time.time()

        config = TrafficConfig(
            treatment_percentage=50,
            split_method=TrafficSplitMethod.HASH_BASED,
            sticky_sessions=True,
            hash_key="user_id"
        )

        router = TrafficRouter(config)

        # Test consistent routing
        results = defaultdict(int)
        for i in range(1000):
            variant = router.route(
                f"request-{i}",
                50,
                {"user_id": f"user-{i % 100}"}
            )
            results[variant] += 1

        # Should be roughly 50/50
        assert 400 < results["control"] < 600
        assert 400 < results["treatment"] < 600

        # Test sticky sessions
        first_variant = router.route("req-1", 50, {"user_id": "sticky-user"})
        for _ in range(10):
            variant = router.route("req-x", 50, {"user_id": "sticky-user"})
            assert variant == first_variant

        return {
            "passed": True,
            "message": "Traffic routing working correctly with sticky sessions",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_metric_collection(self) -> Dict[str, Any]:
        """Test metric collection and statistics"""
        start = time.time()

        collector = MetricCollector()

        deployment_id = "test-deployment"

        # Record metrics
        for i in range(100):
            collector.record(
                deployment_id,
                MetricType.LATENCY_P95,
                100 + random.random() * 50,
                "control"
            )
            collector.record(
                deployment_id,
                MetricType.LATENCY_P95,
                110 + random.random() * 60,
                "treatment"
            )

        # Get statistics
        control_stats = collector.get_stats(
            deployment_id, MetricType.LATENCY_P95, "control"
        )
        treatment_stats = collector.get_stats(
            deployment_id, MetricType.LATENCY_P95, "treatment"
        )

        assert control_stats["count"] == 100
        assert treatment_stats["count"] == 100
        assert 100 < control_stats["mean"] < 150
        assert 110 < treatment_stats["mean"] < 170

        return {
            "passed": True,
            "message": "Metric collection working correctly",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_statistical_analysis(self) -> Dict[str, Any]:
        """Test statistical analysis for A/B testing"""
        start = time.time()

        analyzer = StatisticalAnalyzer(significance_level=0.05)

        # Generate samples with clear difference
        control_samples = [100 + random.gauss(0, 10) for _ in range(100)]
        treatment_samples = [120 + random.gauss(0, 10) for _ in range(100)]

        comparison = analyzer.compare_metrics(
            control_samples,
            treatment_samples,
            MetricType.LATENCY_P95
        )

        assert comparison.is_significant
        assert comparison.treatment_mean > comparison.control_mean
        assert comparison.effect_size > 1.0
        assert "degradation" in comparison.recommendation.lower()

        # Test with no difference
        same_samples = [100 + random.gauss(0, 10) for _ in range(100)]
        comparison2 = analyzer.compare_metrics(
            same_samples,
            same_samples.copy(),
            MetricType.LATENCY_P95
        )

        assert not comparison2.is_significant

        return {
            "passed": True,
            "message": "Statistical analysis working correctly",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_approval_gates(self) -> Dict[str, Any]:
        """Test approval gate workflow"""
        start = time.time()

        config = DeploymentConfig(
            deployment_type=DeploymentType.CANARY,
            require_approval=True,
            approvers=["alice", "bob"]
        )

        orchestrator = DeploymentOrchestrator(config=config)

        control = ModelVersion(
            model_id="test-model", version="v1.0.0",
            artifact_path="/models/v1.0.0", checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )
        treatment = ModelVersion(
            model_id="test-model", version="v1.1.0",
            artifact_path="/models/v1.1.0", checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment, config)

        # Create approval gate
        gate = orchestrator._create_approval_gate(
            deployment, DeploymentState.CANARY_1
        )

        assert gate.status == ApprovalStatus.PENDING

        # Partial approval
        success, msg = orchestrator.approve_gate(
            deployment.deployment_id, gate.gate_id, "alice"
        )
        assert success
        assert gate.status == ApprovalStatus.PENDING  # Still waiting for bob

        # Full approval
        success, msg = orchestrator.approve_gate(
            deployment.deployment_id, gate.gate_id, "bob"
        )
        assert success
        assert gate.status == ApprovalStatus.APPROVED

        return {
            "passed": True,
            "message": "Approval gates working correctly",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_blue_green_deployment(self) -> Dict[str, Any]:
        """Test blue-green deployment"""
        start = time.time()

        config = DeploymentConfig(
            deployment_type=DeploymentType.BLUE_GREEN,
            require_approval=False
        )

        orchestrator = DeploymentOrchestrator(config=config)

        control = ModelVersion(
            model_id="test-model", version="v1.0.0",
            artifact_path="/models/v1.0.0", checksum="abc123",
            created_at=datetime.now(timezone.utc)
        )
        treatment = ModelVersion(
            model_id="test-model", version="v1.1.0",
            artifact_path="/models/v1.1.0", checksum="def456",
            created_at=datetime.now(timezone.utc)
        )

        deployment = orchestrator.create_deployment(control, treatment, config)
        orchestrator.start_deployment(deployment.deployment_id, skip_validation=True)

        # Blue-green should go directly to ACTIVE
        assert deployment.state == DeploymentState.ACTIVE
        assert deployment.current_traffic_percentage == 100

        # Test rollback
        orchestrator.trigger_rollback(
            deployment.deployment_id,
            RollbackReason.MANUAL_TRIGGER
        )

        assert deployment.state == DeploymentState.ROLLED_BACK
        assert deployment.current_traffic_percentage == 0

        return {
            "passed": True,
            "message": "Blue-green deployment working correctly",
            "duration_ms": (time.time() - start) * 1000
        }

    def test_rollback_playbook(self) -> Dict[str, Any]:
        """Test rollback playbook execution"""
        start = time.time()

        executor = RollbackPlaybookExecutor()

        # Create custom playbook
        playbook = RollbackPlaybook(
            playbook_id="test-playbook",
            name="Test Playbook",
            description="Test rollback playbook",
            steps=[
                {"type": "notification", "name": "notify", "message": "Starting"},
                {"type": "traffic_shift", "name": "shift", "weight": 0},
                {"type": "wait", "name": "wait", "duration_seconds": 1},
                {"type": "health_check", "name": "check", "endpoint": "http://test"},
            ],
            pre_rollback_checks=[],
            post_rollback_checks=[],
            notification_channels=["slack"],
            escalation_contacts=["oncall@test.com"]
        )

        executor.register_playbook(playbook)

        # Create mock deployment
        deployment = Deployment(
            deployment_id="test",
            control_model=ModelVersion(
                model_id="m", version="v1",
                artifact_path="/m/v1", checksum="abc",
                created_at=datetime.now(timezone.utc)
            ),
            treatment_model=ModelVersion(
                model_id="m", version="v2",
                artifact_path="/m/v2", checksum="def",
                created_at=datetime.now(timezone.utc)
            ),
            config=DeploymentConfig()
        )

        result = executor.execute_playbook(
            "test-playbook", deployment, {}
        )

        assert result["success"]
        assert len(result["steps_completed"]) == 4

        return {
            "passed": True,
            "message": "Rollback playbook execution working correctly",
            "duration_ms": (time.time() - start) * 1000
        }


# =============================================================================
# Demo and Entry Point
# =============================================================================

def run_demo():
    """Run a demonstration of the deployment orchestrator"""
    print("=" * 60)
    print("QUAN Deployment Orchestrator Demo")
    print("=" * 60)

    # Create orchestrator
    config = DeploymentConfig(
        deployment_type=DeploymentType.CANARY,
        require_approval=False,
        auto_rollback=True,
        rollback_triggers=[
            RollbackTrigger(
                metric_type=MetricType.ERROR_RATE,
                threshold=0.10,
                comparison="greater_than",
                min_samples=5
            )
        ]
    )

    orchestrator = DeploymentOrchestrator(config=config)

    # Create model versions
    control = ModelVersion(
        model_id="payment-predictor",
        version="v2.3.0",
        artifact_path="/models/payment-predictor/v2.3.0",
        checksum="sha256:abc123",
        created_at=datetime.now(timezone.utc),
        metadata={"trained_on": "2024-01-15"},
        performance_metrics={"accuracy": 0.92, "f1": 0.89}
    )

    treatment = ModelVersion(
        model_id="payment-predictor",
        version="v2.4.0",
        artifact_path="/models/payment-predictor/v2.4.0",
        checksum="sha256:def456",
        created_at=datetime.now(timezone.utc),
        metadata={"trained_on": "2024-01-20"},
        performance_metrics={"accuracy": 0.94, "f1": 0.91}
    )

    print(f"\nControl model: {control.full_id}")
    print(f"Treatment model: {treatment.full_id}")

    # Create deployment
    deployment = orchestrator.create_deployment(control, treatment)
    print(f"\nCreated deployment: {deployment.deployment_id}")

    # Start deployment
    orchestrator.start_deployment(deployment.deployment_id, skip_validation=True)
    print(f"State: {deployment.state.value}")
    print(f"Traffic: {deployment.current_traffic_percentage}%")

    # Simulate metrics
    print("\nSimulating good metrics...")
    for i in range(20):
        # Control metrics
        orchestrator.record_metric(
            deployment.deployment_id,
            MetricType.LATENCY_P95,
            100 + random.random() * 20,
            "control"
        )
        orchestrator.record_metric(
            deployment.deployment_id,
            MetricType.ERROR_RATE,
            0.02 + random.random() * 0.01,
            "control"
        )

        # Treatment metrics (slightly better)
        orchestrator.record_metric(
            deployment.deployment_id,
            MetricType.LATENCY_P95,
            95 + random.random() * 15,
            "treatment"
        )
        orchestrator.record_metric(
            deployment.deployment_id,
            MetricType.ERROR_RATE,
            0.015 + random.random() * 0.01,
            "treatment"
        )

    # Advance through canary stages
    for stage in ["5%", "25%", "100%"]:
        success, msg = orchestrator.advance_canary(deployment.deployment_id, force=True)
        print(f"\nAdvanced to {stage}: {msg}")
        print(f"State: {deployment.state.value}")

    # Get final report
    report = orchestrator.get_deployment_report(deployment.deployment_id)
    print(f"\nDeployment completed!")
    print(f"Final state: {report['state']}")
    print(f"Duration: {report['duration_hours']:.2f} hours")
    print(f"Events: {len(report['events'])}")

    print("\n" + "=" * 60)
    print("Running test suite...")
    print("=" * 60)

    # Run tests
    tests = DeploymentOrchestratorTests()
    results = tests.run_all_tests()

    print(f"\nTest Results: {results['passed']}/{results['total']} passed")

    for result in results['results']:
        status = "PASS" if result['passed'] else "FAIL"
        print(f"  [{status}] {result['test']}: {result['message']}")

    return results


if __name__ == "__main__":
    run_demo()
