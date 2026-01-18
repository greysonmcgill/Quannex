"""Comprehensive monitoring and observability"""

from typing import Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager
import time
import logging

from quan.config import settings

logger = logging.getLogger(__name__)

# Conditional imports
try:
    from prometheus_client import Counter, Histogram, Gauge, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed")

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("opentelemetry not installed")


class QuanMetrics:
    """Comprehensive monitoring and observability"""

    def __init__(self):
        self._init_prometheus()
        self._init_tracing()
        self.logger = self._setup_structured_logging()

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics"""

        if not PROMETHEUS_AVAILABLE:
            self.accounts_processed = None
            self.recovery_rate = None
            self.processing_time = None
            self.payment_amount = None
            self.active_campaigns = None
            return

        self.accounts_processed = Counter(
            "quan_accounts_processed_total",
            "Total accounts processed",
            ["stage", "status"],
        )

        self.recovery_rate = Gauge(
            "quan_recovery_rate",
            "Current recovery rate",
            ["client_id"],
        )

        self.processing_time = Histogram(
            "quan_processing_duration_seconds",
            "Time to process account",
            ["stage"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        self.payment_amount = Histogram(
            "quan_payment_amount_dollars",
            "Payment amounts",
            ["method"],
            buckets=[10, 50, 100, 250, 500, 1000, 5000],
        )

        self.active_campaigns = Gauge(
            "quan_active_campaigns",
            "Number of active campaigns",
        )

        self.compliance_violations = Counter(
            "quan_compliance_violations_total",
            "Compliance violations detected",
            ["type"],
        )

        self.api_requests = Counter(
            "quan_api_requests_total",
            "API requests",
            ["endpoint", "method", "status"],
        )

        self.api_latency = Histogram(
            "quan_api_latency_seconds",
            "API request latency",
            ["endpoint"],
        )

    def _init_tracing(self) -> None:
        """Initialize distributed tracing"""

        if not OTEL_AVAILABLE:
            self.tracer = None
            return

        self.tracer = trace.get_tracer("quan-recovery")

    def _setup_structured_logging(self) -> logging.Logger:
        """Setup JSON structured logging"""

        quan_logger = logging.getLogger("quan")

        try:
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler()
            formatter = jsonlogger.JsonFormatter(
                "%(timestamp)s %(level)s %(name)s %(message)s"
            )
            handler.setFormatter(formatter)
            quan_logger.addHandler(handler)
        except ImportError:
            pass

        quan_logger.setLevel(logging.INFO)
        return quan_logger

    @contextmanager
    def track_processing(self, account_id: str, stage: str):
        """Context manager to track account processing"""

        start_time = time.time()
        span = None

        if self.tracer:
            span = self.tracer.start_span(f"process_{stage}")
            span.set_attribute("account.id", account_id)
            span.set_attribute("stage", stage)

        try:
            self.logger.info(
                "Processing started",
                extra={
                    "account_id": account_id,
                    "stage": stage,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            yield span

            # Success
            if self.accounts_processed:
                self.accounts_processed.labels(stage=stage, status="success").inc()

            if span:
                span.set_status(Status(StatusCode.OK))

        except Exception as e:
            # Error
            if self.accounts_processed:
                self.accounts_processed.labels(stage=stage, status="error").inc()

            if span:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))

            self.logger.error(
                "Processing error",
                extra={
                    "account_id": account_id,
                    "stage": stage,
                    "error": str(e),
                },
            )
            raise

        finally:
            duration = time.time() - start_time

            if self.processing_time:
                self.processing_time.labels(stage=stage).observe(duration)

            if span:
                span.end()

            self.logger.info(
                "Processing completed",
                extra={
                    "account_id": account_id,
                    "stage": stage,
                    "duration_seconds": duration,
                },
            )

    def record_payment(
        self,
        amount: float,
        method: str,
        account_id: str,
    ) -> None:
        """Record payment metrics"""

        if self.payment_amount:
            self.payment_amount.labels(method=method).observe(amount)

        self.logger.info(
            "Payment recorded",
            extra={
                "account_id": account_id,
                "amount": amount,
                "method": method,
            },
        )

    def record_compliance_violation(
        self,
        violation_type: str,
        account_id: str,
        details: str,
    ) -> None:
        """Record compliance violation"""

        if self.compliance_violations:
            self.compliance_violations.labels(type=violation_type).inc()

        self.logger.warning(
            "Compliance violation",
            extra={
                "account_id": account_id,
                "violation_type": violation_type,
                "details": details,
            },
        )

    def update_recovery_rate(
        self,
        client_id: str,
        rate: float,
    ) -> None:
        """Update recovery rate gauge"""

        if self.recovery_rate:
            self.recovery_rate.labels(client_id=client_id).set(rate)

    def update_active_campaigns(self, count: int) -> None:
        """Update active campaigns gauge"""

        if self.active_campaigns:
            self.active_campaigns.set(count)

    @contextmanager
    def track_api_request(self, endpoint: str, method: str):
        """Track API request metrics"""

        start_time = time.time()
        status = "success"

        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.time() - start_time

            if self.api_requests:
                self.api_requests.labels(
                    endpoint=endpoint,
                    method=method,
                    status=status,
                ).inc()

            if self.api_latency:
                self.api_latency.labels(endpoint=endpoint).observe(duration)


class MetricsCollector:
    """Collect and aggregate metrics"""

    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._start_time = datetime.utcnow()

    def increment(self, name: str, value: int = 1, labels: Dict = None) -> None:
        """Increment a counter"""
        key = self._make_key(name, labels)
        self._metrics[key] = self._metrics.get(key, 0) + value

    def set_gauge(self, name: str, value: float, labels: Dict = None) -> None:
        """Set a gauge value"""
        key = self._make_key(name, labels)
        self._metrics[key] = value

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Dict = None,
    ) -> None:
        """Record histogram value"""
        key = self._make_key(name, labels)
        if key not in self._metrics:
            self._metrics[key] = []
        self._metrics[key].append(value)

    def _make_key(self, name: str, labels: Optional[Dict]) -> str:
        """Create metric key from name and labels"""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return {
            "metrics": self._metrics,
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "collected_at": datetime.utcnow().isoformat(),
        }


# Grafana Dashboard Configuration
GRAFANA_DASHBOARD = {
    "dashboard": {
        "title": "QUAN Recovery Metrics",
        "refresh": "10s",
        "panels": [
            {
                "title": "Recovery Rate",
                "targets": [
                    {
                        "expr": "quan_recovery_rate",
                        "legendFormat": "{{client_id}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            },
            {
                "title": "Accounts Processed",
                "targets": [
                    {
                        "expr": "rate(quan_accounts_processed_total[5m])",
                        "legendFormat": "{{stage}} - {{status}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            },
            {
                "title": "Processing Latency (p95)",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(quan_processing_duration_seconds_bucket[5m]))",
                        "legendFormat": "{{stage}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            },
            {
                "title": "Payment Distribution",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, quan_payment_amount_dollars_bucket)",
                        "legendFormat": "Median",
                    },
                    {
                        "expr": "histogram_quantile(0.95, quan_payment_amount_dollars_bucket)",
                        "legendFormat": "95th percentile",
                    },
                ],
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            },
            {
                "title": "Active Campaigns",
                "targets": [
                    {
                        "expr": "quan_active_campaigns",
                        "legendFormat": "Campaigns",
                    }
                ],
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16},
            },
            {
                "title": "Compliance Violations",
                "targets": [
                    {
                        "expr": "sum(rate(quan_compliance_violations_total[1h])) by (type)",
                        "legendFormat": "{{type}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
            },
        ],
    }
}


# Global metrics instance
_metrics: Optional[QuanMetrics] = None


def get_metrics() -> QuanMetrics:
    """Get global metrics instance"""
    global _metrics
    if _metrics is None:
        _metrics = QuanMetrics()
    return _metrics
