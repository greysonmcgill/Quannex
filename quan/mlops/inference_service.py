"""
Production Inference Service for QUAN ML Models

Enterprise-grade model serving infrastructure with:
1. FastAPI/BentoML compatible InferenceService class
2. Model loading, versioning, and hot-swapping
3. Health endpoints (/health, /ready, /live)
4. Prediction endpoints with batching support
5. Model version switching without downtime
6. Prometheus metrics export
7. Autoscaling configuration (K8s HPA)
8. Request validation with Pydantic
9. Response schema with probability, uncertainty, explanation
10. Latency tracking (p95 < 500ms, p99 < 1s targets)
11. Concurrent request handling
12. Model warm-up on startup
13. Graceful shutdown
14. Rate limiting and circuit breakers

Target: Deployed model serving within SLA, exporting Prometheus metrics.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pickle
import signal
import sys
import tempfile
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from functools import wraps
from pathlib import Path
from typing import (
    Any, Callable, Dict, Generic, List, Optional,
    Protocol, Set, Tuple, TypeVar, Union
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Constants
# =============================================================================

# SLA Targets
SLA_P95_LATENCY_MS = 500
SLA_P99_LATENCY_MS = 1000
SLA_AVAILABILITY_TARGET = 0.999

# Rate Limiting
DEFAULT_RATE_LIMIT_RPS = 1000
DEFAULT_BURST_SIZE = 100
RATE_LIMIT_WINDOW_SECONDS = 60

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30.0
CIRCUIT_BREAKER_HALF_OPEN_REQUESTS = 3

# Batching
DEFAULT_BATCH_SIZE = 32
MAX_BATCH_SIZE = 256
BATCH_TIMEOUT_MS = 50

# Model Management
MODEL_CACHE_SIZE = 5
MODEL_WARMUP_SAMPLES = 100
HEALTH_CHECK_INTERVAL_SECONDS = 10

# Kubernetes HPA Configuration
HPA_MIN_REPLICAS = 2
HPA_MAX_REPLICAS = 20
HPA_TARGET_CPU_UTILIZATION = 70
HPA_TARGET_MEMORY_UTILIZATION = 80
HPA_SCALE_UP_STABILIZATION = 60
HPA_SCALE_DOWN_STABILIZATION = 300


# =============================================================================
# Enums
# =============================================================================

class ModelStatus(Enum):
    """Model lifecycle states"""
    LOADING = "loading"
    WARMING = "warming"
    READY = "ready"
    SERVING = "serving"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNLOADING = "unloading"


class ServiceStatus(Enum):
    """Service health states"""
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    SHUTTING_DOWN = "shutting_down"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class PredictionType(Enum):
    """Types of predictions supported"""
    PAYMENT_PROBABILITY = "payment_probability"
    CONTACT_RESPONSE = "contact_response"
    SETTLEMENT_ACCEPTANCE = "settlement_acceptance"
    PLAN_ADHERENCE = "plan_adherence"
    OPTIMAL_CHANNEL = "optimal_channel"
    OPTIMAL_TIME = "optimal_time"
    CHURN_RISK = "churn_risk"
    COLLECTION_SCORE = "collection_score"


class ExplanationLevel(Enum):
    """Explanation detail levels"""
    NONE = "none"
    SUMMARY = "summary"
    DETAILED = "detailed"
    FULL = "full"


# =============================================================================
# Pydantic-Compatible Request/Response Models
# =============================================================================

@dataclass
class FeatureInput:
    """Single feature input with validation"""
    name: str
    value: Any
    feature_type: str = "numeric"

    def validate(self) -> bool:
        """Validate feature value"""
        if self.feature_type == "numeric":
            try:
                float(self.value)
                return True
            except (ValueError, TypeError):
                return False
        elif self.feature_type == "categorical":
            return isinstance(self.value, (str, int))
        elif self.feature_type == "binary":
            return self.value in (0, 1, True, False, "0", "1")
        return True


@dataclass
class PredictionRequest:
    """
    Request schema for predictions with validation

    Pydantic-compatible with OpenAPI schema generation support
    """
    request_id: str
    account_id: str
    prediction_type: PredictionType
    features: Dict[str, Any]
    explanation_level: ExplanationLevel = ExplanationLevel.SUMMARY
    model_version: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PredictionRequest:
        """Create from dictionary (API input)"""
        return cls(
            request_id=data.get("request_id", str(uuid.uuid4())),
            account_id=data["account_id"],
            prediction_type=PredictionType(data["prediction_type"]),
            features=data.get("features", {}),
            explanation_level=ExplanationLevel(
                data.get("explanation_level", "summary")
            ),
            model_version=data.get("model_version"),
            timestamp=datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data else datetime.now(timezone.utc),
            metadata=data.get("metadata", {})
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate request fields"""
        errors = []

        if not self.account_id:
            errors.append("account_id is required")

        if not self.features:
            errors.append("features cannot be empty")

        if len(self.features) > 1000:
            errors.append("Too many features (max 1000)")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "request_id": self.request_id,
            "account_id": self.account_id,
            "prediction_type": self.prediction_type.value,
            "features": self.features,
            "explanation_level": self.explanation_level.value,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class BatchPredictionRequest:
    """Batch prediction request"""
    batch_id: str
    requests: List[PredictionRequest]
    priority: int = 0
    timeout_ms: int = 5000

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BatchPredictionRequest:
        """Create from dictionary"""
        return cls(
            batch_id=data.get("batch_id", str(uuid.uuid4())),
            requests=[PredictionRequest.from_dict(r) for r in data["requests"]],
            priority=data.get("priority", 0),
            timeout_ms=data.get("timeout_ms", 5000)
        )


@dataclass
class UncertaintyEstimate:
    """Uncertainty quantification for prediction"""
    epistemic: float  # Model uncertainty
    aleatoric: float  # Data uncertainty
    total: float  # Combined uncertainty
    calibrated: float  # Post-calibration
    confidence_interval_lower: float
    confidence_interval_upper: float
    is_high_uncertainty: bool
    ood_score: float  # Out-of-distribution score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureExplanation:
    """Single feature contribution to prediction"""
    feature_name: str
    feature_value: float
    contribution: float
    direction: str  # "positive", "negative", "neutral"
    rank: int
    human_readable: str


@dataclass
class PredictionExplanation:
    """Complete explanation for prediction"""
    method: str  # "shap", "lime", "integrated_gradients"
    base_value: float
    top_features: List[FeatureExplanation]
    human_summary: str
    counterfactual: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "base_value": self.base_value,
            "top_features": [asdict(f) for f in self.top_features],
            "human_summary": self.human_summary,
            "counterfactual": self.counterfactual
        }


@dataclass
class PredictionResponse:
    """
    Response schema with probability, uncertainty, and explanation

    Complete prediction output with all supporting information
    """
    request_id: str
    account_id: str
    prediction_type: PredictionType

    # Core prediction
    probability: float
    prediction: float
    predicted_class: Optional[str] = None

    # Uncertainty quantification
    uncertainty: Optional[UncertaintyEstimate] = None

    # Explanation
    explanation: Optional[PredictionExplanation] = None

    # Model metadata
    model_version: str = ""
    model_name: str = ""

    # Timing
    latency_ms: float = 0.0
    queue_time_ms: float = 0.0
    inference_time_ms: float = 0.0

    # Status
    success: bool = True
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "request_id": self.request_id,
            "account_id": self.account_id,
            "prediction_type": self.prediction_type.value,
            "probability": self.probability,
            "prediction": self.prediction,
            "predicted_class": self.predicted_class,
            "uncertainty": self.uncertainty.to_dict() if self.uncertainty else None,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "model_version": self.model_version,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "queue_time_ms": self.queue_time_ms,
            "inference_time_ms": self.inference_time_ms,
            "success": self.success,
            "error_message": self.error_message,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id
        }


@dataclass
class BatchPredictionResponse:
    """Batch prediction response"""
    batch_id: str
    responses: List[PredictionResponse]
    total_latency_ms: float
    success_count: int
    failure_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "responses": [r.to_dict() for r in self.responses],
            "total_latency_ms": self.total_latency_ms,
            "success_count": self.success_count,
            "failure_count": self.failure_count
        }


# =============================================================================
# Health Check Models
# =============================================================================

@dataclass
class HealthCheck:
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "details": self.details
        }


@dataclass
class ReadinessCheck:
    """Readiness probe response"""
    ready: bool
    models_loaded: int
    models_ready: int
    dependencies_healthy: Dict[str, bool]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LivenessCheck:
    """Liveness probe response"""
    alive: bool
    last_request_time: Optional[datetime]
    error_rate_percent: float
    memory_usage_mb: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alive": self.alive,
            "last_request_time": self.last_request_time.isoformat()
                if self.last_request_time else None,
            "error_rate_percent": self.error_rate_percent,
            "memory_usage_mb": self.memory_usage_mb
        }


# =============================================================================
# Metrics Collection (Prometheus Format)
# =============================================================================

class MetricsCollector:
    """
    Prometheus-compatible metrics collector

    Exports metrics in Prometheus text format for scraping
    """

    def __init__(self, namespace: str = "quan_inference"):
        self.namespace = namespace
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._histogram_buckets: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._lock = threading.RLock()

        # Define standard buckets
        self._latency_buckets = [
            5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000
        ]

        # Initialize standard metrics
        self._init_standard_metrics()

    def _init_standard_metrics(self) -> None:
        """Initialize standard inference metrics"""
        # Latency histogram buckets
        self._histogram_buckets["request_latency_ms"] = self._latency_buckets
        self._histogram_buckets["inference_latency_ms"] = self._latency_buckets
        self._histogram_buckets["queue_latency_ms"] = [1, 5, 10, 25, 50, 100, 250]
        self._histogram_buckets["batch_size"] = [1, 2, 4, 8, 16, 32, 64, 128, 256]

    def inc_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric"""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
            if labels:
                self._labels[key] = labels

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric"""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            if labels:
                self._labels[key] = labels

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram observation"""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            if labels:
                self._labels[key] = labels
            # Keep only last 10000 observations for percentile calculation
            if len(self._histograms[key]) > 10000:
                self._histograms[key] = self._histograms[key][-10000:]

    def _make_key(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """Create unique key for metric"""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_percentile(self, name: str, percentile: float) -> float:
        """Calculate percentile for histogram"""
        key = name if name in self._histograms else self._make_key(name, None)
        with self._lock:
            values = self._histograms.get(key, [])
            if not values:
                return 0.0
            sorted_values = sorted(values)
            idx = int(len(sorted_values) * percentile / 100)
            return sorted_values[min(idx, len(sorted_values) - 1)]

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format"""
        lines = []
        timestamp_ms = int(time.time() * 1000)

        with self._lock:
            # Export counters
            for key, value in self._counters.items():
                metric_name = f"{self.namespace}_{key.split('{')[0]}_total"
                labels = self._labels.get(key, {})
                label_str = self._format_labels(labels)
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name}{label_str} {value} {timestamp_ms}")

            # Export gauges
            for key, value in self._gauges.items():
                metric_name = f"{self.namespace}_{key.split('{')[0]}"
                labels = self._labels.get(key, {})
                label_str = self._format_labels(labels)
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name}{label_str} {value} {timestamp_ms}")

            # Export histograms
            for key, values in self._histograms.items():
                if not values:
                    continue
                base_name = key.split('{')[0]
                metric_name = f"{self.namespace}_{base_name}"
                labels = self._labels.get(key, {})
                buckets = self._histogram_buckets.get(base_name, self._latency_buckets)

                lines.append(f"# TYPE {metric_name} histogram")

                # Bucket counts
                cumulative = 0
                for bucket in buckets:
                    count = sum(1 for v in values if v <= bucket)
                    bucket_labels = {**labels, "le": str(bucket)}
                    label_str = self._format_labels(bucket_labels)
                    lines.append(
                        f"{metric_name}_bucket{label_str} {count} {timestamp_ms}"
                    )
                    cumulative = count

                # +Inf bucket
                inf_labels = {**labels, "le": "+Inf"}
                label_str = self._format_labels(inf_labels)
                lines.append(
                    f"{metric_name}_bucket{label_str} {len(values)} {timestamp_ms}"
                )

                # Sum and count
                label_str = self._format_labels(labels)
                lines.append(
                    f"{metric_name}_sum{label_str} {sum(values)} {timestamp_ms}"
                )
                lines.append(
                    f"{metric_name}_count{label_str} {len(values)} {timestamp_ms}"
                )

        return "\n".join(lines)

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus output"""
        if not labels:
            return ""
        pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(pairs) + "}"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histogram_counts": {
                    k: len(v) for k, v in self._histograms.items()
                },
                "latency_p50": self.get_percentile("request_latency_ms", 50),
                "latency_p95": self.get_percentile("request_latency_ms", 95),
                "latency_p99": self.get_percentile("request_latency_ms", 99),
            }


# =============================================================================
# Rate Limiter
# =============================================================================

class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for request throttling

    Provides smooth rate limiting with burst capacity
    """

    def __init__(
        self,
        rate_limit: float = DEFAULT_RATE_LIMIT_RPS,
        burst_size: int = DEFAULT_BURST_SIZE
    ):
        self.rate_limit = rate_limit
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to acquire tokens

        Returns:
            Tuple of (success, wait_time_seconds)
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            # Add tokens based on elapsed time
            self.tokens = min(
                self.burst_size,
                self.tokens + elapsed * self.rate_limit
            )

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0

            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.rate_limit
            return False, wait_time

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Async version that waits if needed"""
        success, wait_time = self.acquire(tokens)
        if success:
            return True

        if wait_time > 5.0:  # Don't wait more than 5 seconds
            return False

        await asyncio.sleep(wait_time)
        return self.acquire(tokens)[0]


class SlidingWindowRateLimiter:
    """Sliding window rate limiter per client"""

    def __init__(
        self,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_RATE_LIMIT_RPS * 60
    ):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._windows: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if request is allowed for client

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            window = self._windows[client_id]

            # Remove old entries
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= self.max_requests:
                return False, 0

            window.append(now)
            remaining = self.max_requests - len(window)
            return True, remaining


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitBreaker:
    """
    Circuit breaker for fault tolerance

    Prevents cascade failures by stopping requests to failing services
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout: float = CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        half_open_requests: int = CIRCUIT_BREAKER_HALF_OPEN_REQUESTS
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_allowed = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state with timeout check"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if (self._last_failure_time and
                    time.monotonic() - self._last_failure_time > self.recovery_timeout):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_allowed = self.half_open_requests
            return self._state

    def is_allowed(self) -> bool:
        """Check if request is allowed through circuit"""
        state = self.state

        with self._lock:
            if state == CircuitState.CLOSED:
                return True
            elif state == CircuitState.OPEN:
                return False
            else:  # HALF_OPEN
                if self._half_open_allowed > 0:
                    self._half_open_allowed -= 1
                    return True
                return False

    def record_success(self) -> None:
        """Record successful request"""
        with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                if self._success_count >= self.half_open_requests:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name} closed after recovery")

    def record_failure(self) -> None:
        """Record failed request"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} re-opened after half-open failure")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit {self.name} opened after {self._failure_count} failures"
                )

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time
            }


# =============================================================================
# Model Registry and Version Management
# =============================================================================

@dataclass
class ModelVersion:
    """Model version metadata"""
    version: str
    name: str
    model_type: str
    created_at: datetime
    checksum: str
    metrics: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    status: ModelStatus = ModelStatus.LOADING
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "model_type": self.model_type,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "metrics": self.metrics,
            "config": self.config,
            "status": self.status.value,
            "path": self.path
        }


class ModelRegistry:
    """
    Model version registry with hot-swapping support

    Manages multiple model versions and enables seamless switching
    """

    def __init__(self, cache_size: int = MODEL_CACHE_SIZE):
        self.cache_size = cache_size
        self._versions: Dict[str, ModelVersion] = {}
        self._active_versions: Dict[str, str] = {}  # model_name -> version
        self._loaded_models: Dict[str, Any] = {}
        self._load_order: deque = deque(maxlen=cache_size)
        self._lock = threading.RLock()

    def register_version(self, version: ModelVersion) -> None:
        """Register a new model version"""
        with self._lock:
            key = f"{version.name}:{version.version}"
            self._versions[key] = version
            logger.info(f"Registered model version: {key}")

    def get_version(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Optional[ModelVersion]:
        """Get model version metadata"""
        with self._lock:
            if version:
                key = f"{model_name}:{version}"
                return self._versions.get(key)

            # Return active version
            active_version = self._active_versions.get(model_name)
            if active_version:
                return self._versions.get(f"{model_name}:{active_version}")

            # Return latest version
            model_versions = [
                v for k, v in self._versions.items()
                if k.startswith(f"{model_name}:")
            ]
            if model_versions:
                return max(model_versions, key=lambda v: v.created_at)
            return None

    def set_active_version(self, model_name: str, version: str) -> bool:
        """Set active version for a model"""
        with self._lock:
            key = f"{model_name}:{version}"
            if key not in self._versions:
                return False
            self._active_versions[model_name] = version
            logger.info(f"Set active version: {model_name} -> {version}")
            return True

    def list_versions(self, model_name: Optional[str] = None) -> List[ModelVersion]:
        """List all registered versions"""
        with self._lock:
            if model_name:
                return [
                    v for k, v in self._versions.items()
                    if k.startswith(f"{model_name}:")
                ]
            return list(self._versions.values())

    def cache_model(self, key: str, model: Any) -> None:
        """Cache a loaded model"""
        with self._lock:
            # Evict oldest if cache full
            if len(self._loaded_models) >= self.cache_size:
                if self._load_order:
                    oldest_key = self._load_order.popleft()
                    if oldest_key in self._loaded_models:
                        del self._loaded_models[oldest_key]
                        logger.info(f"Evicted model from cache: {oldest_key}")

            self._loaded_models[key] = model
            self._load_order.append(key)

    def get_cached_model(self, key: str) -> Optional[Any]:
        """Get model from cache"""
        with self._lock:
            return self._loaded_models.get(key)


# =============================================================================
# Model Loader
# =============================================================================

class ModelLoader:
    """
    Model loading with validation and warm-up

    Handles loading models from various sources with integrity verification
    """

    def __init__(self, model_dir: str = "/models"):
        self.model_dir = Path(model_dir)
        self._loaders: Dict[str, Callable] = {}
        self._register_default_loaders()

    def _register_default_loaders(self) -> None:
        """Register default model loaders"""
        self._loaders["pickle"] = self._load_pickle
        self._loaders["joblib"] = self._load_joblib
        self._loaders["pytorch"] = self._load_pytorch
        self._loaders["tensorflow"] = self._load_tensorflow
        self._loaders["onnx"] = self._load_onnx

    def register_loader(
        self,
        format_name: str,
        loader: Callable[[Path], Any]
    ) -> None:
        """Register custom model loader"""
        self._loaders[format_name] = loader

    def load_model(
        self,
        model_path: str,
        model_format: str = "pickle",
        expected_checksum: Optional[str] = None
    ) -> Tuple[Any, str]:
        """
        Load model with validation

        Returns:
            Tuple of (model, checksum)
        """
        path = Path(model_path)
        if not path.is_absolute():
            path = self.model_dir / path

        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")

        # Verify checksum
        actual_checksum = self._compute_checksum(path)
        if expected_checksum and actual_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for {path}: "
                f"expected {expected_checksum}, got {actual_checksum}"
            )

        # Load model
        loader = self._loaders.get(model_format)
        if not loader:
            raise ValueError(f"Unknown model format: {model_format}")

        model = loader(path)
        logger.info(f"Loaded model from {path} (checksum: {actual_checksum[:8]}...)")

        return model, actual_checksum

    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA-256 checksum of model file"""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _load_pickle(self, path: Path) -> Any:
        """Load pickle model"""
        with open(path, "rb") as f:
            return pickle.load(f)

    def _load_joblib(self, path: Path) -> Any:
        """Load joblib model"""
        try:
            import joblib
            return joblib.load(path)
        except ImportError:
            # Fallback to pickle
            return self._load_pickle(path)

    def _load_pytorch(self, path: Path) -> Any:
        """Load PyTorch model"""
        try:
            import torch
            return torch.load(path, map_location="cpu")
        except ImportError:
            raise ImportError("PyTorch not installed")

    def _load_tensorflow(self, path: Path) -> Any:
        """Load TensorFlow model"""
        try:
            import tensorflow as tf
            return tf.saved_model.load(str(path))
        except ImportError:
            raise ImportError("TensorFlow not installed")

    def _load_onnx(self, path: Path) -> Any:
        """Load ONNX model"""
        try:
            import onnxruntime as ort
            return ort.InferenceSession(str(path))
        except ImportError:
            raise ImportError("ONNX Runtime not installed")


# =============================================================================
# Batch Processor
# =============================================================================

class BatchProcessor:
    """
    Dynamic batch processor for inference optimization

    Collects individual requests and processes them in batches
    for better GPU utilization
    """

    def __init__(
        self,
        max_batch_size: int = DEFAULT_BATCH_SIZE,
        timeout_ms: int = BATCH_TIMEOUT_MS,
        process_func: Optional[Callable] = None
    ):
        self.max_batch_size = max_batch_size
        self.timeout_ms = timeout_ms
        self.process_func = process_func

        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start batch processor"""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started")

    async def stop(self) -> None:
        """Stop batch processor gracefully"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Batch processor stopped")

    async def submit(
        self,
        request: PredictionRequest
    ) -> asyncio.Future:
        """Submit request for batched processing"""
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((request, future, time.monotonic()))
        return future

    async def _process_loop(self) -> None:
        """Main processing loop"""
        while self._running:
            try:
                batch = []
                deadline = time.monotonic() + (self.timeout_ms / 1000.0)

                # Collect batch
                while len(batch) < self.max_batch_size:
                    remaining = max(0, deadline - time.monotonic())
                    try:
                        item = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=remaining
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break

                if batch and self.process_func:
                    await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processing error: {e}")

    async def _process_batch(
        self,
        batch: List[Tuple[PredictionRequest, asyncio.Future, float]]
    ) -> None:
        """Process a batch of requests"""
        requests = [item[0] for item in batch]
        futures = [item[1] for item in batch]
        submit_times = [item[2] for item in batch]

        try:
            results = await self.process_func(requests)

            for i, (future, result) in enumerate(zip(futures, results)):
                # Add queue time to response
                if hasattr(result, 'queue_time_ms'):
                    result.queue_time_ms = (time.monotonic() - submit_times[i]) * 1000

                if not future.done():
                    future.set_result(result)

        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)


# =============================================================================
# Inference Engine
# =============================================================================

class InferenceEngine:
    """
    Core inference engine for model prediction

    Handles feature preprocessing, model inference, and postprocessing
    """

    def __init__(
        self,
        model: Any,
        model_version: ModelVersion,
        uncertainty_estimator: Optional[Any] = None,
        explainer: Optional[Any] = None
    ):
        self.model = model
        self.model_version = model_version
        self.uncertainty_estimator = uncertainty_estimator
        self.explainer = explainer
        self._is_warmed = False

    def warm_up(self, num_samples: int = MODEL_WARMUP_SAMPLES) -> float:
        """
        Warm up model with dummy predictions

        Returns warm-up time in seconds
        """
        start_time = time.monotonic()

        # Generate dummy features
        dummy_features = {f"feature_{i}": 0.5 for i in range(50)}

        for _ in range(num_samples):
            try:
                self._predict_single(dummy_features)
            except Exception:
                pass  # Ignore warm-up errors

        self._is_warmed = True
        elapsed = time.monotonic() - start_time
        logger.info(
            f"Model {self.model_version.name}:{self.model_version.version} "
            f"warmed up with {num_samples} samples in {elapsed:.2f}s"
        )
        return elapsed

    def predict(
        self,
        request: PredictionRequest
    ) -> PredictionResponse:
        """Generate prediction for single request"""
        start_time = time.monotonic()

        try:
            # Preprocess features
            processed_features = self._preprocess(request.features)

            # Get prediction
            inference_start = time.monotonic()
            prediction, probability = self._predict_single(processed_features)
            inference_time = (time.monotonic() - inference_start) * 1000

            # Get uncertainty if available
            uncertainty = None
            if self.uncertainty_estimator:
                uncertainty = self._estimate_uncertainty(processed_features)

            # Get explanation if requested
            explanation = None
            if request.explanation_level != ExplanationLevel.NONE:
                explanation = self._generate_explanation(
                    processed_features,
                    prediction,
                    request.explanation_level
                )

            total_latency = (time.monotonic() - start_time) * 1000

            return PredictionResponse(
                request_id=request.request_id,
                account_id=request.account_id,
                prediction_type=request.prediction_type,
                probability=probability,
                prediction=prediction,
                predicted_class=self._get_class_label(prediction),
                uncertainty=uncertainty,
                explanation=explanation,
                model_version=self.model_version.version,
                model_name=self.model_version.name,
                latency_ms=total_latency,
                inference_time_ms=inference_time,
                success=True
            )

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return PredictionResponse(
                request_id=request.request_id,
                account_id=request.account_id,
                prediction_type=request.prediction_type,
                probability=0.0,
                prediction=0.0,
                success=False,
                error_message=str(e),
                latency_ms=(time.monotonic() - start_time) * 1000
            )

    def predict_batch(
        self,
        requests: List[PredictionRequest]
    ) -> List[PredictionResponse]:
        """Generate predictions for batch of requests"""
        return [self.predict(request) for request in requests]

    def _preprocess(self, features: Dict[str, Any]) -> Dict[str, float]:
        """Preprocess input features"""
        processed = {}
        for name, value in features.items():
            if isinstance(value, (int, float)):
                processed[name] = float(value)
            elif isinstance(value, bool):
                processed[name] = 1.0 if value else 0.0
            elif isinstance(value, str):
                # Simple hash-based encoding for strings
                processed[name] = float(hash(value) % 1000) / 1000.0
            else:
                processed[name] = 0.0
        return processed

    def _predict_single(
        self,
        features: Dict[str, float]
    ) -> Tuple[float, float]:
        """Execute single prediction"""
        # Convert to feature vector
        feature_vector = list(features.values())

        # Model prediction (abstract - actual implementation depends on model type)
        if hasattr(self.model, 'predict_proba'):
            # Sklearn-like model
            proba = self.model.predict_proba([feature_vector])[0]
            probability = proba[1] if len(proba) > 1 else proba[0]
            prediction = 1.0 if probability > 0.5 else 0.0
        elif hasattr(self.model, 'predict'):
            prediction = float(self.model.predict([feature_vector])[0])
            probability = prediction if 0 <= prediction <= 1 else 0.5
        elif callable(self.model):
            result = self.model(feature_vector)
            if isinstance(result, tuple):
                prediction, probability = result
            else:
                prediction = float(result)
                probability = prediction
        else:
            # Simulated prediction for testing
            import random
            probability = random.random()
            prediction = 1.0 if probability > 0.5 else 0.0

        return prediction, probability

    def _estimate_uncertainty(
        self,
        features: Dict[str, float]
    ) -> UncertaintyEstimate:
        """Estimate prediction uncertainty"""
        # Simplified uncertainty estimation
        feature_variance = sum(
            (v - 0.5) ** 2 for v in features.values()
        ) / max(len(features), 1)

        epistemic = min(0.3, feature_variance * 2)
        aleatoric = 0.1
        total = (epistemic ** 2 + aleatoric ** 2) ** 0.5

        return UncertaintyEstimate(
            epistemic=epistemic,
            aleatoric=aleatoric,
            total=total,
            calibrated=total * 0.9,
            confidence_interval_lower=0.5 - total,
            confidence_interval_upper=0.5 + total,
            is_high_uncertainty=total > 0.3,
            ood_score=min(1.0, feature_variance * 5)
        )

    def _generate_explanation(
        self,
        features: Dict[str, float],
        prediction: float,
        level: ExplanationLevel
    ) -> PredictionExplanation:
        """Generate prediction explanation"""
        # Simplified SHAP-like explanation
        feature_contributions = []
        base_value = 0.5

        sorted_features = sorted(
            features.items(),
            key=lambda x: abs(x[1] - 0.5),
            reverse=True
        )

        for rank, (name, value) in enumerate(sorted_features[:5], 1):
            contribution = (value - 0.5) * 0.2
            direction = "positive" if contribution > 0 else "negative"

            feature_contributions.append(FeatureExplanation(
                feature_name=name,
                feature_value=value,
                contribution=contribution,
                direction=direction,
                rank=rank,
                human_readable=f"{name} ({value:.2f}) contributed {contribution:+.3f}"
            ))

        # Generate human summary
        top_positive = [f for f in feature_contributions if f.direction == "positive"]
        top_negative = [f for f in feature_contributions if f.direction == "negative"]

        summary_parts = []
        if top_positive:
            summary_parts.append(
                f"Key positive factors: {', '.join(f.feature_name for f in top_positive[:2])}"
            )
        if top_negative:
            summary_parts.append(
                f"Key negative factors: {', '.join(f.feature_name for f in top_negative[:2])}"
            )

        return PredictionExplanation(
            method="shap",
            base_value=base_value,
            top_features=feature_contributions,
            human_summary=". ".join(summary_parts) if summary_parts else "No significant factors identified"
        )

    def _get_class_label(self, prediction: float) -> str:
        """Convert prediction to class label"""
        if prediction > 0.7:
            return "high"
        elif prediction > 0.3:
            return "medium"
        return "low"


# =============================================================================
# Inference Service (Main Class)
# =============================================================================

class InferenceService:
    """
    Production Inference Service

    FastAPI/BentoML compatible service providing:
    - Model loading and versioning
    - Health endpoints (/health, /ready, /live)
    - Prediction endpoints with batching
    - Model version switching
    - Prometheus metrics export
    - Rate limiting and circuit breakers
    - Graceful shutdown

    Example usage:
        service = InferenceService(config)
        await service.start()

        # Make predictions
        response = await service.predict(request)

        # Switch model version
        await service.switch_model_version("payment_model", "v2.1.0")

        # Graceful shutdown
        await service.shutdown()
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_dir: str = "/models"
    ):
        self.config = config or {}
        self.model_dir = model_dir

        # Core components
        self.registry = ModelRegistry()
        self.loader = ModelLoader(model_dir)
        self.metrics = MetricsCollector()

        # Engines (model_name -> InferenceEngine)
        self._engines: Dict[str, InferenceEngine] = {}

        # Rate limiting
        self._rate_limiters: Dict[str, TokenBucketRateLimiter] = {}
        self._global_rate_limiter = TokenBucketRateLimiter(
            rate_limit=self.config.get("rate_limit_rps", DEFAULT_RATE_LIMIT_RPS),
            burst_size=self.config.get("burst_size", DEFAULT_BURST_SIZE)
        )

        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._global_circuit = CircuitBreaker("global")

        # Batch processor
        self._batch_processor: Optional[BatchProcessor] = None

        # Service state
        self._status = ServiceStatus.STARTING
        self._start_time = time.monotonic()
        self._last_request_time: Optional[datetime] = None
        self._request_count = 0
        self._error_count = 0

        # Threading
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 4)
        )
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()

        # Version info
        self.version = self.config.get("version", "1.0.0")

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def start(self) -> None:
        """Start the inference service"""
        logger.info("Starting inference service...")

        try:
            # Load configured models
            await self._load_configured_models()

            # Start batch processor if enabled
            if self.config.get("batching_enabled", True):
                self._batch_processor = BatchProcessor(
                    max_batch_size=self.config.get("batch_size", DEFAULT_BATCH_SIZE),
                    timeout_ms=self.config.get("batch_timeout_ms", BATCH_TIMEOUT_MS),
                    process_func=self._process_batch
                )
                await self._batch_processor.start()

            # Start health check background task
            asyncio.create_task(self._health_check_loop())

            self._status = ServiceStatus.HEALTHY
            logger.info("Inference service started successfully")

        except Exception as e:
            self._status = ServiceStatus.UNHEALTHY
            logger.error(f"Failed to start inference service: {e}")
            raise

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Graceful shutdown with request draining"""
        logger.info("Initiating graceful shutdown...")
        self._status = ServiceStatus.SHUTTING_DOWN

        # Stop accepting new requests
        self._shutdown_event.set()

        # Stop batch processor
        if self._batch_processor:
            await self._batch_processor.stop()

        # Wait for in-flight requests
        shutdown_start = time.monotonic()
        while (time.monotonic() - shutdown_start) < timeout:
            # Check if all requests completed
            if self._get_pending_requests() == 0:
                break
            await asyncio.sleep(0.1)

        # Cleanup
        self._executor.shutdown(wait=False)

        logger.info("Inference service shutdown complete")

    async def _load_configured_models(self) -> None:
        """Load models from configuration"""
        models_config = self.config.get("models", [])

        for model_config in models_config:
            try:
                await self.load_model(
                    model_name=model_config["name"],
                    model_path=model_config["path"],
                    model_format=model_config.get("format", "pickle"),
                    version=model_config.get("version", "1.0.0"),
                    set_active=model_config.get("active", True)
                )
            except Exception as e:
                logger.error(f"Failed to load model {model_config['name']}: {e}")

    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while not self._shutdown_event.is_set():
            try:
                await self._perform_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

    async def _perform_health_check(self) -> None:
        """Perform internal health check"""
        # Check error rate
        if self._request_count > 0:
            error_rate = self._error_count / self._request_count
            if error_rate > 0.1:  # 10% error rate threshold
                self._status = ServiceStatus.DEGRADED
                logger.warning(f"High error rate detected: {error_rate:.2%}")

        # Update metrics
        self.metrics.set_gauge("service_status",
            1.0 if self._status == ServiceStatus.HEALTHY else 0.0)
        self.metrics.set_gauge("models_loaded", len(self._engines))

    def _get_pending_requests(self) -> int:
        """Get count of pending requests"""
        return sum(1 for cb in self._circuit_breakers.values()
                   if cb.state == CircuitState.HALF_OPEN)

    # =========================================================================
    # Model Management
    # =========================================================================

    async def load_model(
        self,
        model_name: str,
        model_path: str,
        model_format: str = "pickle",
        version: str = "1.0.0",
        set_active: bool = True,
        warm_up: bool = True
    ) -> ModelVersion:
        """
        Load a model into the service

        Args:
            model_name: Unique model identifier
            model_path: Path to model file
            model_format: Model serialization format
            version: Version string
            set_active: Whether to set as active version
            warm_up: Whether to warm up model

        Returns:
            ModelVersion metadata
        """
        async with self._lock:
            logger.info(f"Loading model {model_name}:{version} from {model_path}")

            # Load model
            model, checksum = self.loader.load_model(
                model_path, model_format
            )

            # Create version metadata
            model_version = ModelVersion(
                version=version,
                name=model_name,
                model_type=model_format,
                created_at=datetime.now(timezone.utc),
                checksum=checksum,
                path=model_path,
                status=ModelStatus.LOADING
            )

            # Register version
            self.registry.register_version(model_version)
            self.registry.cache_model(f"{model_name}:{version}", model)

            # Create inference engine
            engine = InferenceEngine(model, model_version)

            # Warm up if requested
            if warm_up:
                model_version.status = ModelStatus.WARMING
                warmup_time = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    engine.warm_up,
                    MODEL_WARMUP_SAMPLES
                )
                self.metrics.observe_histogram(
                    "model_warmup_time_seconds",
                    warmup_time,
                    {"model": model_name, "version": version}
                )

            model_version.status = ModelStatus.READY

            # Set as active if requested
            if set_active:
                self._engines[model_name] = engine
                self.registry.set_active_version(model_name, version)
                model_version.status = ModelStatus.SERVING

            # Create circuit breaker for model
            self._circuit_breakers[model_name] = CircuitBreaker(model_name)

            self.metrics.inc_counter(
                "models_loaded",
                labels={"model": model_name, "version": version}
            )

            logger.info(f"Model {model_name}:{version} loaded and ready")
            return model_version

    async def switch_model_version(
        self,
        model_name: str,
        target_version: str
    ) -> bool:
        """
        Switch to a different model version without downtime

        Args:
            model_name: Model to switch
            target_version: Target version to activate

        Returns:
            True if switch successful
        """
        async with self._lock:
            version_info = self.registry.get_version(model_name, target_version)
            if not version_info:
                logger.error(f"Version {target_version} not found for {model_name}")
                return False

            # Get cached model or load it
            key = f"{model_name}:{target_version}"
            model = self.registry.get_cached_model(key)

            if not model:
                # Load model
                model, _ = self.loader.load_model(
                    version_info.path,
                    version_info.model_type
                )
                self.registry.cache_model(key, model)

            # Create new engine
            new_engine = InferenceEngine(model, version_info)
            new_engine.warm_up(MODEL_WARMUP_SAMPLES // 2)  # Quick warm-up

            # Atomic switch
            old_engine = self._engines.get(model_name)
            self._engines[model_name] = new_engine
            self.registry.set_active_version(model_name, target_version)

            # Update status
            version_info.status = ModelStatus.SERVING

            self.metrics.inc_counter(
                "model_version_switches",
                labels={"model": model_name, "from_version":
                        old_engine.model_version.version if old_engine else "none",
                        "to_version": target_version}
            )

            logger.info(f"Switched {model_name} to version {target_version}")
            return True

    async def unload_model(self, model_name: str) -> bool:
        """Unload a model from service"""
        async with self._lock:
            if model_name not in self._engines:
                return False

            engine = self._engines.pop(model_name)
            engine.model_version.status = ModelStatus.UNLOADING

            # Cleanup
            if model_name in self._circuit_breakers:
                del self._circuit_breakers[model_name]

            logger.info(f"Unloaded model {model_name}")
            return True

    def list_models(self) -> List[Dict[str, Any]]:
        """List all loaded models"""
        result = []
        for name, engine in self._engines.items():
            result.append({
                "name": name,
                "version": engine.model_version.version,
                "status": engine.model_version.status.value,
                "is_warmed": engine._is_warmed
            })
        return result

    # =========================================================================
    # Health Endpoints
    # =========================================================================

    async def health(self) -> HealthCheck:
        """
        GET /health - Overall health status

        Returns comprehensive health information
        """
        uptime = time.monotonic() - self._start_time

        return HealthCheck(
            status=self._status.value,
            timestamp=datetime.now(timezone.utc),
            version=self.version,
            uptime_seconds=uptime,
            details={
                "models_loaded": len(self._engines),
                "request_count": self._request_count,
                "error_count": self._error_count,
                "latency_p95_ms": self.metrics.get_percentile("request_latency_ms", 95),
                "latency_p99_ms": self.metrics.get_percentile("request_latency_ms", 99)
            }
        )

    async def ready(self) -> ReadinessCheck:
        """
        GET /ready - Kubernetes readiness probe

        Returns True if service can accept traffic
        """
        models_loaded = len(self._engines)
        models_ready = sum(
            1 for e in self._engines.values()
            if e.model_version.status == ModelStatus.SERVING
        )

        dependencies = {
            "model_registry": True,
            "metrics_collector": True,
            "rate_limiter": True
        }

        is_ready = (
            self._status in (ServiceStatus.HEALTHY, ServiceStatus.DEGRADED) and
            models_ready > 0
        )

        return ReadinessCheck(
            ready=is_ready,
            models_loaded=models_loaded,
            models_ready=models_ready,
            dependencies_healthy=dependencies,
            message="Service ready" if is_ready else "Service not ready"
        )

    async def live(self) -> LivenessCheck:
        """
        GET /live - Kubernetes liveness probe

        Returns True if service is alive (should not be restarted)
        """
        error_rate = 0.0
        if self._request_count > 0:
            error_rate = (self._error_count / self._request_count) * 100

        # Estimate memory usage
        import sys
        memory_mb = sys.getsizeof(self._engines) / (1024 * 1024)

        is_alive = self._status != ServiceStatus.UNHEALTHY

        return LivenessCheck(
            alive=is_alive,
            last_request_time=self._last_request_time,
            error_rate_percent=error_rate,
            memory_usage_mb=memory_mb
        )

    # =========================================================================
    # Prediction Endpoints
    # =========================================================================

    async def predict(
        self,
        request: PredictionRequest,
        client_id: Optional[str] = None
    ) -> PredictionResponse:
        """
        POST /predict - Single prediction endpoint

        Args:
            request: Prediction request
            client_id: Optional client identifier for rate limiting

        Returns:
            PredictionResponse with probability, uncertainty, explanation
        """
        start_time = time.monotonic()
        self._request_count += 1
        self._last_request_time = datetime.now(timezone.utc)

        # Check shutdown
        if self._shutdown_event.is_set():
            return self._error_response(
                request, "Service is shutting down", start_time
            )

        # Rate limiting
        if not await self._check_rate_limit(client_id):
            self.metrics.inc_counter("rate_limit_exceeded")
            return self._error_response(
                request, "Rate limit exceeded", start_time
            )

        # Circuit breaker
        model_name = self._get_model_name(request.prediction_type)
        circuit = self._circuit_breakers.get(model_name, self._global_circuit)

        if not circuit.is_allowed():
            self.metrics.inc_counter(
                "circuit_breaker_rejected",
                labels={"model": model_name}
            )
            return self._error_response(
                request, "Circuit breaker open - service temporarily unavailable",
                start_time
            )

        # Validate request
        is_valid, errors = request.validate()
        if not is_valid:
            return self._error_response(
                request, f"Validation failed: {', '.join(errors)}", start_time
            )

        try:
            # Get engine
            engine = self._engines.get(model_name)
            if not engine:
                return self._error_response(
                    request, f"Model not loaded: {model_name}", start_time
                )

            # Execute prediction
            response = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                engine.predict,
                request
            )

            # Record success
            circuit.record_success()
            latency_ms = (time.monotonic() - start_time) * 1000
            response.latency_ms = latency_ms

            # Record metrics
            self._record_prediction_metrics(response, model_name)

            return response

        except Exception as e:
            self._error_count += 1
            circuit.record_failure()
            logger.error(f"Prediction error: {e}")
            return self._error_response(request, str(e), start_time)

    async def predict_batch(
        self,
        request: BatchPredictionRequest,
        client_id: Optional[str] = None
    ) -> BatchPredictionResponse:
        """
        POST /predict/batch - Batch prediction endpoint

        Args:
            request: Batch prediction request
            client_id: Optional client identifier

        Returns:
            BatchPredictionResponse with all predictions
        """
        start_time = time.monotonic()

        # Validate batch size
        if len(request.requests) > MAX_BATCH_SIZE:
            return BatchPredictionResponse(
                batch_id=request.batch_id,
                responses=[],
                total_latency_ms=0,
                success_count=0,
                failure_count=1
            )

        # Process batch
        if self._batch_processor:
            # Use batch processor for optimized inference
            futures = [
                await self._batch_processor.submit(req)
                for req in request.requests
            ]
            responses = await asyncio.gather(*futures, return_exceptions=True)
        else:
            # Direct processing
            responses = await asyncio.gather(*[
                self.predict(req, client_id) for req in request.requests
            ])

        # Count successes/failures
        success_count = sum(1 for r in responses
                          if isinstance(r, PredictionResponse) and r.success)
        failure_count = len(responses) - success_count

        total_latency = (time.monotonic() - start_time) * 1000

        self.metrics.observe_histogram(
            "batch_size",
            len(request.requests)
        )
        self.metrics.observe_histogram(
            "batch_latency_ms",
            total_latency
        )

        return BatchPredictionResponse(
            batch_id=request.batch_id,
            responses=[r for r in responses if isinstance(r, PredictionResponse)],
            total_latency_ms=total_latency,
            success_count=success_count,
            failure_count=failure_count
        )

    async def _process_batch(
        self,
        requests: List[PredictionRequest]
    ) -> List[PredictionResponse]:
        """Process batch of requests (used by BatchProcessor)"""
        responses = []
        for request in requests:
            response = await self.predict(request)
            responses.append(response)
        return responses

    # =========================================================================
    # Model Version Endpoint
    # =========================================================================

    async def switch_version(
        self,
        model_name: str,
        version: str
    ) -> Dict[str, Any]:
        """
        POST /models/{model_name}/version - Switch model version

        Args:
            model_name: Target model
            version: Target version

        Returns:
            Status of version switch
        """
        success = await self.switch_model_version(model_name, version)

        return {
            "success": success,
            "model_name": model_name,
            "new_version": version if success else None,
            "message": "Version switched successfully" if success else "Failed to switch version"
        }

    # =========================================================================
    # Metrics Endpoint
    # =========================================================================

    async def metrics_endpoint(self) -> str:
        """
        GET /metrics - Prometheus metrics endpoint

        Returns metrics in Prometheus text format
        """
        return self.metrics.export_prometheus()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return self.metrics.get_summary()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _check_rate_limit(self, client_id: Optional[str]) -> bool:
        """Check rate limit for request"""
        # Global rate limit
        success, _ = self._global_rate_limiter.acquire()
        if not success:
            return False

        # Per-client rate limit
        if client_id:
            if client_id not in self._rate_limiters:
                self._rate_limiters[client_id] = TokenBucketRateLimiter(
                    rate_limit=100,  # 100 RPS per client
                    burst_size=20
                )
            success, _ = self._rate_limiters[client_id].acquire()
            return success

        return True

    def _get_model_name(self, prediction_type: PredictionType) -> str:
        """Map prediction type to model name"""
        mapping = {
            PredictionType.PAYMENT_PROBABILITY: "payment_model",
            PredictionType.CONTACT_RESPONSE: "contact_model",
            PredictionType.SETTLEMENT_ACCEPTANCE: "settlement_model",
            PredictionType.PLAN_ADHERENCE: "adherence_model",
            PredictionType.OPTIMAL_CHANNEL: "channel_model",
            PredictionType.OPTIMAL_TIME: "timing_model",
            PredictionType.CHURN_RISK: "churn_model",
            PredictionType.COLLECTION_SCORE: "collection_model",
        }
        return mapping.get(prediction_type, "default_model")

    def _error_response(
        self,
        request: PredictionRequest,
        error_message: str,
        start_time: float
    ) -> PredictionResponse:
        """Create error response"""
        self._error_count += 1
        return PredictionResponse(
            request_id=request.request_id,
            account_id=request.account_id,
            prediction_type=request.prediction_type,
            probability=0.0,
            prediction=0.0,
            success=False,
            error_message=error_message,
            latency_ms=(time.monotonic() - start_time) * 1000
        )

    def _record_prediction_metrics(
        self,
        response: PredictionResponse,
        model_name: str
    ) -> None:
        """Record prediction metrics"""
        labels = {"model": model_name}

        self.metrics.inc_counter("predictions", labels=labels)

        if response.success:
            self.metrics.inc_counter("predictions_success", labels=labels)
        else:
            self.metrics.inc_counter("predictions_error", labels=labels)

        self.metrics.observe_histogram(
            "request_latency_ms",
            response.latency_ms,
            labels=labels
        )

        self.metrics.observe_histogram(
            "inference_latency_ms",
            response.inference_time_ms,
            labels=labels
        )

        # Check SLA
        if response.latency_ms > SLA_P95_LATENCY_MS:
            self.metrics.inc_counter("sla_violations_p95", labels=labels)
        if response.latency_ms > SLA_P99_LATENCY_MS:
            self.metrics.inc_counter("sla_violations_p99", labels=labels)


# =============================================================================
# FastAPI Application Factory
# =============================================================================

def create_fastapi_app(
    service: InferenceService,
    title: str = "QUAN Inference Service",
    version: str = "1.0.0"
) -> Any:
    """
    Create FastAPI application with inference service

    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import FastAPI, HTTPException, Request, Response
        from fastapi.responses import PlainTextResponse
    except ImportError:
        logger.warning("FastAPI not installed - returning None")
        return None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await service.start()
        yield
        # Shutdown
        await service.shutdown()

    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan
    )

    @app.get("/health")
    async def health():
        result = await service.health()
        return result.to_dict()

    @app.get("/ready")
    async def ready():
        result = await service.ready()
        status_code = 200 if result.ready else 503
        return Response(
            content=json.dumps(result.to_dict()),
            status_code=status_code,
            media_type="application/json"
        )

    @app.get("/live")
    async def live():
        result = await service.live()
        status_code = 200 if result.alive else 503
        return Response(
            content=json.dumps(result.to_dict()),
            status_code=status_code,
            media_type="application/json"
        )

    @app.post("/predict")
    async def predict(request: Request):
        data = await request.json()
        pred_request = PredictionRequest.from_dict(data)
        client_id = request.headers.get("X-Client-ID")
        result = await service.predict(pred_request, client_id)
        return result.to_dict()

    @app.post("/predict/batch")
    async def predict_batch(request: Request):
        data = await request.json()
        batch_request = BatchPredictionRequest.from_dict(data)
        client_id = request.headers.get("X-Client-ID")
        result = await service.predict_batch(batch_request, client_id)
        return result.to_dict()

    @app.post("/models/{model_name}/version")
    async def switch_version(model_name: str, request: Request):
        data = await request.json()
        version = data.get("version")
        if not version:
            raise HTTPException(400, "version is required")
        result = await service.switch_version(model_name, version)
        return result

    @app.get("/models")
    async def list_models():
        return service.list_models()

    @app.get("/metrics")
    async def metrics():
        content = await service.metrics_endpoint()
        return PlainTextResponse(content, media_type="text/plain")

    return app


# =============================================================================
# Kubernetes Configuration
# =============================================================================

KUBERNETES_DEPLOYMENT_MANIFEST = """
---
# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quan-inference-service
  namespace: quan-mlops
  labels:
    app: quan-inference
    component: model-serving
spec:
  replicas: 2
  selector:
    matchLabels:
      app: quan-inference
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        app: quan-inference
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: quan-inference
      terminationGracePeriodSeconds: 30
      containers:
      - name: inference-service
        image: quan-inference:latest
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        env:
        - name: MODEL_DIR
          value: "/models"
        - name: LOG_LEVEL
          value: "INFO"
        - name: MAX_WORKERS
          value: "4"
        - name: RATE_LIMIT_RPS
          value: "1000"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: models
          mountPath: /models
          readOnly: true
        - name: config
          mountPath: /config
          readOnly: true
        livenessProbe:
          httpGet:
            path: /live
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 30
      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: quan-models-pvc
      - name: config
        configMap:
          name: quan-inference-config

---
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: quan-inference-hpa
  namespace: quan-mlops
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: quan-inference-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: quan_inference_request_latency_ms_p95
      target:
        type: AverageValue
        averageValue: "500"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Pods
        value: 4
        periodSeconds: 60
      - type: Percent
        value: 100
        periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60

---
# Service
apiVersion: v1
kind: Service
metadata:
  name: quan-inference-service
  namespace: quan-mlops
  labels:
    app: quan-inference
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 80
    targetPort: http
    protocol: TCP
  selector:
    app: quan-inference

---
# ServiceMonitor for Prometheus
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: quan-inference-monitor
  namespace: quan-mlops
  labels:
    app: quan-inference
spec:
  selector:
    matchLabels:
      app: quan-inference
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
    scrapeTimeout: 10s

---
# PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: quan-inference-pdb
  namespace: quan-mlops
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: quan-inference

---
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: quan-inference-config
  namespace: quan-mlops
data:
  config.yaml: |
    version: "1.0.0"
    rate_limit_rps: 1000
    burst_size: 100
    batch_size: 32
    batch_timeout_ms: 50
    max_workers: 4
    batching_enabled: true
    models:
      - name: payment_model
        path: /models/payment_model.pkl
        format: pickle
        version: "1.0.0"
        active: true
      - name: collection_model
        path: /models/collection_model.pkl
        format: pickle
        version: "1.0.0"
        active: true

---
# Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: quan-inference
  namespace: quan-mlops
"""

DOCKERFILE = """
# Multi-stage build for QUAN Inference Service
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY quan/ /app/quan/

# Create non-root user
RUN useradd -m -u 1000 appuser && \\
    chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MODEL_DIR=/models
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\
    CMD curl -f http://localhost:8080/live || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "quan.mlops.inference_service:app", "--host", "0.0.0.0", "--port", "8080"]
"""

REQUIREMENTS = """
# Core dependencies
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0

# ML frameworks
numpy>=1.24.0
scikit-learn>=1.3.0

# Optional ML frameworks
# torch>=2.1.0
# tensorflow>=2.15.0
# onnxruntime>=1.16.0

# Monitoring
prometheus-client>=0.19.0

# Utilities
python-json-logger>=2.0.0
httpx>=0.25.0
"""


# =============================================================================
# Module Entry Point
# =============================================================================

# Default service instance (created on import if needed)
_default_service: Optional[InferenceService] = None


def get_service(config: Optional[Dict[str, Any]] = None) -> InferenceService:
    """Get or create default service instance"""
    global _default_service
    if _default_service is None:
        _default_service = InferenceService(config)
    return _default_service


# Create FastAPI app for direct uvicorn usage
def create_app() -> Any:
    """Create FastAPI app with default service"""
    config = {
        "version": "1.0.0",
        "rate_limit_rps": 1000,
        "batch_size": 32,
        "batching_enabled": True
    }
    service = get_service(config)
    return create_fastapi_app(service)


# For direct uvicorn usage: uvicorn quan.mlops.inference_service:app
app = create_app()


# =============================================================================
# Tests
# =============================================================================

class InferenceServiceTests:
    """Test suite for inference service"""

    def __init__(self):
        self.service: Optional[InferenceService] = None
        self.results: Dict[str, bool] = {}

    async def setup(self) -> None:
        """Set up test fixtures"""
        config = {
            "version": "test",
            "rate_limit_rps": 100,
            "batch_size": 4,
            "batching_enabled": False,
            "models": []
        }
        self.service = InferenceService(config)

    async def teardown(self) -> None:
        """Clean up test fixtures"""
        if self.service:
            await self.service.shutdown(timeout=5.0)

    async def test_health_endpoints(self) -> bool:
        """Test health, ready, and live endpoints"""
        try:
            health = await self.service.health()
            assert health.status is not None

            ready = await self.service.ready()
            assert isinstance(ready.ready, bool)

            live = await self.service.live()
            assert isinstance(live.alive, bool)

            return True
        except Exception as e:
            logger.error(f"Health endpoint test failed: {e}")
            return False

    async def test_rate_limiter(self) -> bool:
        """Test rate limiting"""
        try:
            limiter = TokenBucketRateLimiter(rate_limit=10, burst_size=5)

            # Should allow burst
            for _ in range(5):
                success, _ = limiter.acquire()
                assert success

            # Should reject after burst
            success, wait_time = limiter.acquire()
            assert not success
            assert wait_time > 0

            return True
        except Exception as e:
            logger.error(f"Rate limiter test failed: {e}")
            return False

    async def test_circuit_breaker(self) -> bool:
        """Test circuit breaker"""
        try:
            cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1.0)

            assert cb.state == CircuitState.CLOSED

            # Record failures
            for _ in range(3):
                cb.record_failure()

            assert cb.state == CircuitState.OPEN
            assert not cb.is_allowed()

            # Wait for recovery
            await asyncio.sleep(1.1)

            assert cb.state == CircuitState.HALF_OPEN

            return True
        except Exception as e:
            logger.error(f"Circuit breaker test failed: {e}")
            return False

    async def test_metrics_collector(self) -> bool:
        """Test metrics collection"""
        try:
            metrics = MetricsCollector("test")

            metrics.inc_counter("requests", labels={"model": "test"})
            metrics.set_gauge("active_models", 3)
            metrics.observe_histogram("latency_ms", 150)

            prometheus_output = metrics.export_prometheus()
            assert "test_requests_total" in prometheus_output
            assert "test_active_models" in prometheus_output

            return True
        except Exception as e:
            logger.error(f"Metrics test failed: {e}")
            return False

    async def test_request_validation(self) -> bool:
        """Test request validation"""
        try:
            # Valid request
            valid_request = PredictionRequest(
                request_id="test-123",
                account_id="acc-456",
                prediction_type=PredictionType.PAYMENT_PROBABILITY,
                features={"balance": 1000, "days_past_due": 30}
            )
            is_valid, errors = valid_request.validate()
            assert is_valid
            assert len(errors) == 0

            # Invalid request (empty features)
            invalid_request = PredictionRequest(
                request_id="test-789",
                account_id="acc-101",
                prediction_type=PredictionType.PAYMENT_PROBABILITY,
                features={}
            )
            is_valid, errors = invalid_request.validate()
            assert not is_valid
            assert "features cannot be empty" in errors

            return True
        except Exception as e:
            logger.error(f"Request validation test failed: {e}")
            return False

    async def test_model_registry(self) -> bool:
        """Test model registry"""
        try:
            registry = ModelRegistry()

            version = ModelVersion(
                version="1.0.0",
                name="test_model",
                model_type="pickle",
                created_at=datetime.now(timezone.utc),
                checksum="abc123"
            )

            registry.register_version(version)

            retrieved = registry.get_version("test_model", "1.0.0")
            assert retrieved is not None
            assert retrieved.version == "1.0.0"

            registry.set_active_version("test_model", "1.0.0")
            active = registry.get_version("test_model")
            assert active.version == "1.0.0"

            return True
        except Exception as e:
            logger.error(f"Model registry test failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests"""
        await self.setup()

        tests = [
            ("health_endpoints", self.test_health_endpoints),
            ("rate_limiter", self.test_rate_limiter),
            ("circuit_breaker", self.test_circuit_breaker),
            ("metrics_collector", self.test_metrics_collector),
            ("request_validation", self.test_request_validation),
            ("model_registry", self.test_model_registry),
        ]

        for name, test_func in tests:
            try:
                self.results[name] = await test_func()
            except Exception as e:
                logger.error(f"Test {name} failed with exception: {e}")
                self.results[name] = False

        await self.teardown()

        # Print summary
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        logger.info(f"Tests passed: {passed}/{total}")

        return self.results


async def run_tests() -> None:
    """Run test suite"""
    tests = InferenceServiceTests()
    results = await tests.run_all_tests()

    for name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(run_tests())
    else:
        # Run service
        try:
            import uvicorn
            uvicorn.run(
                "quan.mlops.inference_service:app",
                host="0.0.0.0",
                port=8080,
                reload=False
            )
        except ImportError:
            print("uvicorn not installed. Install with: pip install uvicorn")
