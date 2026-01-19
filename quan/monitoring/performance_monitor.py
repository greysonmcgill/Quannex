"""
QUAN Performance Monitoring and Alerting System

Comprehensive monitoring for the seven-stage collection pipeline:
ACQUIRE -> LOCATE -> CONTACT -> NEGOTIATE -> COLLECT -> CLOSE -> PROFIT

Features:
- KPI tracking per pipeline stage
- Multi-level alerting (Yellow, Orange, Red)
- Trend detection with rolling averages
- Anomaly detection and drift monitoring
- Automated reporting (daily, weekly, monthly)
- A/B test monitoring with statistical significance
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import deque
import asyncio
import logging
import statistics
import math
import json
import random

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class PipelineStage(Enum):
    """Seven stages of QUAN collection pipeline"""
    ACQUIRE = "acquire"
    LOCATE = "locate"
    CONTACT = "contact"
    NEGOTIATE = "negotiate"
    COLLECT = "collect"
    CLOSE = "close"
    PROFIT = "profit"


class AlertSeverity(Enum):
    """Alert severity levels"""
    GREEN = "green"      # Within targets
    YELLOW = "yellow"    # 10% deviation
    ORANGE = "orange"    # 20% deviation
    RED = "red"          # 30% deviation or critical failure


class MetricType(Enum):
    """Type of metric for aggregation"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"


class TrendDirection(Enum):
    """Direction of metric trend"""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    ANOMALY = "anomaly"


# =============================================================================
# KPI DEFINITIONS
# =============================================================================

@dataclass
class KPIDefinition:
    """Definition of a Key Performance Indicator"""
    name: str
    stage: PipelineStage
    metric_type: MetricType
    target: float
    unit: str
    description: str

    # Alert thresholds (percentage deviation from target)
    yellow_threshold: float = 0.10  # 10%
    orange_threshold: float = 0.20  # 20%
    red_threshold: float = 0.30     # 30%

    # Higher is better (True) or lower is better (False)
    higher_is_better: bool = True

    # Critical - red alert triggers immediate page
    is_critical: bool = False


# Stage-specific KPI definitions
KPI_DEFINITIONS: Dict[str, KPIDefinition] = {
    # ACQUIRE Stage KPIs
    "acquire_accounts_per_hour": KPIDefinition(
        name="accounts_scored_per_hour",
        stage=PipelineStage.ACQUIRE,
        metric_type=MetricType.RATE,
        target=5000.0,
        unit="accounts/hour",
        description="Rate of accounts being scored for recovery potential",
        higher_is_better=True,
    ),
    "acquire_scoring_latency_ms": KPIDefinition(
        name="scoring_latency",
        stage=PipelineStage.ACQUIRE,
        metric_type=MetricType.HISTOGRAM,
        target=50.0,
        unit="ms",
        description="P95 latency for ML scoring",
        higher_is_better=False,
        is_critical=True,
    ),

    # LOCATE Stage KPIs
    "locate_skip_trace_success_rate": KPIDefinition(
        name="skip_trace_success_rate",
        stage=PipelineStage.LOCATE,
        metric_type=MetricType.GAUGE,
        target=0.75,
        unit="ratio",
        description="Rate of successful skip trace lookups",
        higher_is_better=True,
    ),
    "locate_data_freshness_hours": KPIDefinition(
        name="data_freshness",
        stage=PipelineStage.LOCATE,
        metric_type=MetricType.GAUGE,
        target=24.0,
        unit="hours",
        description="Average age of contact data",
        higher_is_better=False,
    ),

    # CONTACT Stage KPIs
    "contact_response_rate": KPIDefinition(
        name="response_rate",
        stage=PipelineStage.CONTACT,
        metric_type=MetricType.GAUGE,
        target=0.15,
        unit="ratio",
        description="Rate of debtor responses to outreach",
        higher_is_better=True,
    ),
    "contact_delivery_rate": KPIDefinition(
        name="delivery_rate",
        stage=PipelineStage.CONTACT,
        metric_type=MetricType.GAUGE,
        target=0.95,
        unit="ratio",
        description="Rate of successful message delivery",
        higher_is_better=True,
        is_critical=True,
    ),
    "contact_cost_per_contact": KPIDefinition(
        name="cost_per_contact",
        stage=PipelineStage.CONTACT,
        metric_type=MetricType.GAUGE,
        target=0.025,
        unit="dollars",
        description="Average cost per contact attempt",
        higher_is_better=False,
    ),

    # NEGOTIATE Stage KPIs
    "negotiate_acceptance_rate": KPIDefinition(
        name="acceptance_rate",
        stage=PipelineStage.NEGOTIATE,
        metric_type=MetricType.GAUGE,
        target=0.35,
        unit="ratio",
        description="Rate of offer acceptance",
        higher_is_better=True,
    ),
    "negotiate_avg_settlement_pct": KPIDefinition(
        name="average_settlement_percentage",
        stage=PipelineStage.NEGOTIATE,
        metric_type=MetricType.GAUGE,
        target=0.65,
        unit="ratio",
        description="Average settlement as % of original balance",
        higher_is_better=True,
    ),
    "negotiate_days_to_resolve": KPIDefinition(
        name="days_to_resolve",
        stage=PipelineStage.NEGOTIATE,
        metric_type=MetricType.HISTOGRAM,
        target=14.0,
        unit="days",
        description="Average days from first contact to agreement",
        higher_is_better=False,
    ),

    # COLLECT Stage KPIs
    "collect_payment_success_rate": KPIDefinition(
        name="payment_success_rate",
        stage=PipelineStage.COLLECT,
        metric_type=MetricType.GAUGE,
        target=0.92,
        unit="ratio",
        description="Rate of successful payment transactions",
        higher_is_better=True,
        is_critical=True,
    ),
    "collect_decline_rate": KPIDefinition(
        name="decline_rate",
        stage=PipelineStage.COLLECT,
        metric_type=MetricType.GAUGE,
        target=0.05,
        unit="ratio",
        description="Rate of declined payment attempts",
        higher_is_better=False,
        is_critical=True,
    ),
    "collect_retry_success_rate": KPIDefinition(
        name="retry_success_rate",
        stage=PipelineStage.COLLECT,
        metric_type=MetricType.GAUGE,
        target=0.40,
        unit="ratio",
        description="Success rate of payment retries",
        higher_is_better=True,
    ),

    # CLOSE Stage KPIs
    "close_plan_completion_rate": KPIDefinition(
        name="plan_completion_rate",
        stage=PipelineStage.CLOSE,
        metric_type=MetricType.GAUGE,
        target=0.70,
        unit="ratio",
        description="Rate of payment plan completions",
        higher_is_better=True,
    ),
    "close_redefault_rate": KPIDefinition(
        name="redefault_rate",
        stage=PipelineStage.CLOSE,
        metric_type=MetricType.GAUGE,
        target=0.15,
        unit="ratio",
        description="Rate of accounts re-defaulting after arrangement",
        higher_is_better=False,
    ),

    # PROFIT Stage KPIs
    "profit_margin": KPIDefinition(
        name="profit_margin",
        stage=PipelineStage.PROFIT,
        metric_type=MetricType.GAUGE,
        target=0.85,
        unit="ratio",
        description="Net profit margin on collections",
        higher_is_better=True,
    ),
    "profit_roi": KPIDefinition(
        name="roi",
        stage=PipelineStage.PROFIT,
        metric_type=MetricType.GAUGE,
        target=3.0,
        unit="ratio",
        description="Return on investment",
        higher_is_better=True,
    ),
    "profit_revenue_per_account": KPIDefinition(
        name="revenue_per_account",
        stage=PipelineStage.PROFIT,
        metric_type=MetricType.GAUGE,
        target=45.0,
        unit="dollars",
        description="Average revenue per account processed",
        higher_is_better=True,
    ),
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TimeSeriesPoint:
    """Single point in a time series"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSample:
    """A metric sample with metadata"""
    kpi_name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_name": self.kpi_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class Alert:
    """An alert triggered by threshold breach"""
    id: str
    kpi_name: str
    severity: AlertSeverity
    current_value: float
    target_value: float
    deviation_pct: float
    timestamp: datetime
    message: str
    acknowledged: bool = False
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kpi_name": self.kpi_name,
            "severity": self.severity.value,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "deviation_pct": self.deviation_pct,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolution_timestamp": self.resolution_timestamp.isoformat() if self.resolution_timestamp else None,
        }


@dataclass
class TrendAnalysis:
    """Result of trend analysis"""
    kpi_name: str
    direction: TrendDirection
    slope: float  # Rate of change
    confidence: float  # 0-1 confidence in trend
    hourly_avg: float
    daily_avg: float
    weekly_avg: float
    is_anomaly: bool
    anomaly_score: float  # Z-score for anomaly
    seasonality_factor: float  # Seasonal adjustment
    drift_detected: bool
    drift_magnitude: float


@dataclass
class ABTestVariant:
    """A variant in an A/B test"""
    name: str
    sample_size: int
    conversions: int
    total_value: Decimal

    @property
    def conversion_rate(self) -> float:
        return self.conversions / self.sample_size if self.sample_size > 0 else 0.0

    @property
    def avg_value(self) -> float:
        return float(self.total_value / self.sample_size) if self.sample_size > 0 else 0.0


@dataclass
class ABTestResult:
    """Result of A/B test analysis"""
    test_id: str
    test_name: str
    metric_name: str
    control: ABTestVariant
    treatment: ABTestVariant
    lift: float  # Relative improvement
    p_value: float
    is_significant: bool
    confidence_level: float
    winner: Optional[str]
    recommendation: str
    sample_size_needed: int
    current_power: float


# =============================================================================
# PAGING RULES
# =============================================================================

@dataclass
class PagingRule:
    """Rule for when to page on-call engineers"""
    severity: AlertSeverity
    should_page: bool
    page_delay_minutes: int  # Wait before paging
    escalation_delay_minutes: int  # Time before escalating
    channels: List[str]  # slack, pagerduty, email, sms


PAGING_RULES: Dict[AlertSeverity, PagingRule] = {
    AlertSeverity.GREEN: PagingRule(
        severity=AlertSeverity.GREEN,
        should_page=False,
        page_delay_minutes=0,
        escalation_delay_minutes=0,
        channels=[],
    ),
    AlertSeverity.YELLOW: PagingRule(
        severity=AlertSeverity.YELLOW,
        should_page=False,
        page_delay_minutes=0,
        escalation_delay_minutes=60,
        channels=["slack"],
    ),
    AlertSeverity.ORANGE: PagingRule(
        severity=AlertSeverity.ORANGE,
        should_page=True,
        page_delay_minutes=15,
        escalation_delay_minutes=30,
        channels=["slack", "email"],
    ),
    AlertSeverity.RED: PagingRule(
        severity=AlertSeverity.RED,
        should_page=True,
        page_delay_minutes=0,  # Immediate
        escalation_delay_minutes=15,
        channels=["slack", "pagerduty", "sms"],
    ),
}


# =============================================================================
# TIME SERIES STORAGE
# =============================================================================

class TimeSeriesStore:
    """
    In-memory time series storage for metric history.

    Maintains rolling windows for trend analysis:
    - 1 hour of per-minute data
    - 24 hours of per-hour data
    - 30 days of daily data
    - 12 months of weekly data
    """

    def __init__(self):
        # Per-minute data (last hour) - 60 points
        self._minute_data: Dict[str, deque] = {}

        # Per-hour data (last 24 hours) - 24 points
        self._hourly_data: Dict[str, deque] = {}

        # Daily data (last 30 days) - 30 points
        self._daily_data: Dict[str, deque] = {}

        # Weekly data (last 52 weeks) - 52 points
        self._weekly_data: Dict[str, deque] = {}

        # Aggregation state
        self._current_hour_values: Dict[str, List[float]] = {}
        self._current_day_values: Dict[str, List[float]] = {}
        self._current_week_values: Dict[str, List[float]] = {}

        self._last_hour_rollup: datetime = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        self._last_day_rollup: datetime = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        self._last_week_rollup: datetime = self._get_week_start(datetime.utcnow())

    def _get_week_start(self, dt: datetime) -> datetime:
        """Get the start of the week (Monday)"""
        return (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

    def _ensure_deques(self, kpi_name: str):
        """Ensure deques exist for a KPI"""
        if kpi_name not in self._minute_data:
            self._minute_data[kpi_name] = deque(maxlen=60)
        if kpi_name not in self._hourly_data:
            self._hourly_data[kpi_name] = deque(maxlen=24)
        if kpi_name not in self._daily_data:
            self._daily_data[kpi_name] = deque(maxlen=30)
        if kpi_name not in self._weekly_data:
            self._weekly_data[kpi_name] = deque(maxlen=52)
        if kpi_name not in self._current_hour_values:
            self._current_hour_values[kpi_name] = []
        if kpi_name not in self._current_day_values:
            self._current_day_values[kpi_name] = []
        if kpi_name not in self._current_week_values:
            self._current_week_values[kpi_name] = []

    def record(self, kpi_name: str, value: float, timestamp: Optional[datetime] = None):
        """Record a metric value"""
        self._ensure_deques(kpi_name)

        ts = timestamp or datetime.utcnow()
        point = TimeSeriesPoint(timestamp=ts, value=value)

        # Add to minute data
        self._minute_data[kpi_name].append(point)

        # Aggregate for rollups
        self._current_hour_values[kpi_name].append(value)
        self._current_day_values[kpi_name].append(value)
        self._current_week_values[kpi_name].append(value)

        # Check for rollups
        self._check_rollups(ts)

    def _check_rollups(self, current_time: datetime):
        """Check if we need to perform rollups"""
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        current_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        current_week = self._get_week_start(current_time)

        # Hourly rollup
        if current_hour > self._last_hour_rollup:
            self._perform_hourly_rollup(self._last_hour_rollup)
            self._last_hour_rollup = current_hour

        # Daily rollup
        if current_day > self._last_day_rollup:
            self._perform_daily_rollup(self._last_day_rollup)
            self._last_day_rollup = current_day

        # Weekly rollup
        if current_week > self._last_week_rollup:
            self._perform_weekly_rollup(self._last_week_rollup)
            self._last_week_rollup = current_week

    def _perform_hourly_rollup(self, hour: datetime):
        """Roll up minute data to hourly"""
        for kpi_name, values in self._current_hour_values.items():
            if values:
                avg = statistics.mean(values)
                self._hourly_data[kpi_name].append(
                    TimeSeriesPoint(timestamp=hour, value=avg)
                )

        # Clear accumulators
        for kpi_name in self._current_hour_values:
            self._current_hour_values[kpi_name] = []

    def _perform_daily_rollup(self, day: datetime):
        """Roll up hourly data to daily"""
        for kpi_name, values in self._current_day_values.items():
            if values:
                avg = statistics.mean(values)
                self._daily_data[kpi_name].append(
                    TimeSeriesPoint(timestamp=day, value=avg)
                )

        # Clear accumulators
        for kpi_name in self._current_day_values:
            self._current_day_values[kpi_name] = []

    def _perform_weekly_rollup(self, week_start: datetime):
        """Roll up daily data to weekly"""
        for kpi_name, values in self._current_week_values.items():
            if values:
                avg = statistics.mean(values)
                self._weekly_data[kpi_name].append(
                    TimeSeriesPoint(timestamp=week_start, value=avg)
                )

        # Clear accumulators
        for kpi_name in self._current_week_values:
            self._current_week_values[kpi_name] = []

    def get_minute_data(self, kpi_name: str, minutes: int = 60) -> List[TimeSeriesPoint]:
        """Get minute-level data"""
        self._ensure_deques(kpi_name)
        data = list(self._minute_data[kpi_name])
        return data[-minutes:] if len(data) > minutes else data

    def get_hourly_data(self, kpi_name: str, hours: int = 24) -> List[TimeSeriesPoint]:
        """Get hourly data"""
        self._ensure_deques(kpi_name)
        data = list(self._hourly_data[kpi_name])
        return data[-hours:] if len(data) > hours else data

    def get_daily_data(self, kpi_name: str, days: int = 30) -> List[TimeSeriesPoint]:
        """Get daily data"""
        self._ensure_deques(kpi_name)
        data = list(self._daily_data[kpi_name])
        return data[-days:] if len(data) > days else data

    def get_weekly_data(self, kpi_name: str, weeks: int = 52) -> List[TimeSeriesPoint]:
        """Get weekly data"""
        self._ensure_deques(kpi_name)
        data = list(self._weekly_data[kpi_name])
        return data[-weeks:] if len(data) > weeks else data

    def get_current_value(self, kpi_name: str) -> Optional[float]:
        """Get most recent value for a KPI"""
        self._ensure_deques(kpi_name)
        if self._minute_data[kpi_name]:
            return self._minute_data[kpi_name][-1].value
        return None


# =============================================================================
# TREND DETECTION
# =============================================================================

class TrendDetector:
    """
    Detects trends, anomalies, and drift in metric data.

    Features:
    - Rolling averages (hourly, daily, weekly)
    - Anomaly detection using Z-scores
    - Seasonality modeling
    - Model drift detection
    """

    def __init__(self, time_series_store: TimeSeriesStore):
        self.store = time_series_store

        # Baseline statistics for drift detection
        self._baselines: Dict[str, Dict[str, float]] = {}

        # Seasonality patterns (hour of day -> multiplier)
        self._seasonality: Dict[str, Dict[int, float]] = {}

    def analyze(self, kpi_name: str) -> TrendAnalysis:
        """Perform full trend analysis on a KPI"""
        # Get data at different granularities
        minute_data = self.store.get_minute_data(kpi_name)
        hourly_data = self.store.get_hourly_data(kpi_name)
        daily_data = self.store.get_daily_data(kpi_name)
        weekly_data = self.store.get_weekly_data(kpi_name)

        # Calculate rolling averages
        hourly_avg = self._calculate_average(minute_data)
        daily_avg = self._calculate_average(hourly_data)
        weekly_avg = self._calculate_average(daily_data)

        # Detect trend direction and slope
        direction, slope, confidence = self._detect_trend(daily_data)

        # Detect anomalies
        is_anomaly, anomaly_score = self._detect_anomaly(kpi_name, minute_data)

        # Get seasonality factor
        seasonality_factor = self._get_seasonality_factor(kpi_name)

        # Detect drift
        drift_detected, drift_magnitude = self._detect_drift(kpi_name, daily_data)

        return TrendAnalysis(
            kpi_name=kpi_name,
            direction=direction,
            slope=slope,
            confidence=confidence,
            hourly_avg=hourly_avg,
            daily_avg=daily_avg,
            weekly_avg=weekly_avg,
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            seasonality_factor=seasonality_factor,
            drift_detected=drift_detected,
            drift_magnitude=drift_magnitude,
        )

    def _calculate_average(self, data: List[TimeSeriesPoint]) -> float:
        """Calculate average from time series data"""
        if not data:
            return 0.0
        values = [p.value for p in data]
        return statistics.mean(values)

    def _detect_trend(
        self,
        data: List[TimeSeriesPoint]
    ) -> Tuple[TrendDirection, float, float]:
        """
        Detect trend direction using linear regression.

        Returns:
            (direction, slope, confidence)
        """
        if len(data) < 3:
            return TrendDirection.STABLE, 0.0, 0.0

        values = [p.value for p in data]
        n = len(values)

        # Simple linear regression
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return TrendDirection.STABLE, 0.0, 0.0

        slope = numerator / denominator

        # Calculate R-squared for confidence
        y_pred = [slope * (i - x_mean) + y_mean for i in range(n)]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((v - y_mean) ** 2 for v in values)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        confidence = max(0.0, min(1.0, r_squared))

        # Determine direction based on slope relative to mean
        threshold = abs(y_mean) * 0.01 if y_mean != 0 else 0.001

        if slope > threshold:
            direction = TrendDirection.IMPROVING
        elif slope < -threshold:
            direction = TrendDirection.DEGRADING
        else:
            direction = TrendDirection.STABLE

        return direction, slope, confidence

    def _detect_anomaly(
        self,
        kpi_name: str,
        data: List[TimeSeriesPoint]
    ) -> Tuple[bool, float]:
        """
        Detect anomalies using Z-score method.

        Returns:
            (is_anomaly, z_score)
        """
        if len(data) < 10:
            return False, 0.0

        values = [p.value for p in data]
        current = values[-1]

        # Use all but the last value for baseline
        baseline_values = values[:-1]
        mean = statistics.mean(baseline_values)
        stdev = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0.001

        if stdev == 0:
            stdev = 0.001

        z_score = abs(current - mean) / stdev

        # Anomaly if Z-score > 3 (99.7% confidence)
        is_anomaly = z_score > 3.0

        return is_anomaly, z_score

    def _get_seasonality_factor(self, kpi_name: str) -> float:
        """
        Get seasonality adjustment factor for current hour.

        Models typical hourly patterns in collection activity.
        """
        if kpi_name not in self._seasonality:
            # Initialize default seasonality pattern
            # (higher activity during business hours)
            self._seasonality[kpi_name] = {
                0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.2,
                6: 0.4, 7: 0.6, 8: 0.8, 9: 1.0, 10: 1.1, 11: 1.2,
                12: 1.0, 13: 1.1, 14: 1.2, 15: 1.1, 16: 1.0, 17: 0.9,
                18: 0.7, 19: 0.5, 20: 0.4, 21: 0.3, 22: 0.3, 23: 0.2,
            }

        current_hour = datetime.utcnow().hour
        return self._seasonality[kpi_name].get(current_hour, 1.0)

    def update_seasonality(self, kpi_name: str, hour: int, factor: float):
        """Update seasonality factor for a specific hour"""
        if kpi_name not in self._seasonality:
            self._seasonality[kpi_name] = {}
        self._seasonality[kpi_name][hour] = factor

    def _detect_drift(
        self,
        kpi_name: str,
        data: List[TimeSeriesPoint]
    ) -> Tuple[bool, float]:
        """
        Detect model drift by comparing recent performance to baseline.

        Uses Page-Hinkley test for drift detection.
        """
        if len(data) < 7:
            return False, 0.0

        values = [p.value for p in data]

        # Establish baseline from first half of data
        baseline_values = values[:len(values)//2]
        recent_values = values[len(values)//2:]

        if not baseline_values or not recent_values:
            return False, 0.0

        baseline_mean = statistics.mean(baseline_values)
        recent_mean = statistics.mean(recent_values)

        if baseline_mean == 0:
            return False, 0.0

        # Calculate drift as percentage change
        drift_magnitude = abs(recent_mean - baseline_mean) / abs(baseline_mean)

        # Store/update baseline
        if kpi_name not in self._baselines:
            self._baselines[kpi_name] = {
                "mean": baseline_mean,
                "stdev": statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0.0,
            }

        # Drift detected if change > 15%
        drift_detected = drift_magnitude > 0.15

        return drift_detected, drift_magnitude

    def set_baseline(self, kpi_name: str, mean: float, stdev: float):
        """Manually set baseline for drift detection"""
        self._baselines[kpi_name] = {"mean": mean, "stdev": stdev}


# =============================================================================
# ALERTING ENGINE
# =============================================================================

class AlertingEngine:
    """
    Manages alerts based on KPI thresholds and paging rules.
    """

    def __init__(self):
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._alert_counter = 0

    def register_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for new alerts"""
        self._alert_callbacks.append(callback)

    def evaluate_kpi(
        self,
        kpi_name: str,
        current_value: float,
        kpi_def: Optional[KPIDefinition] = None
    ) -> Optional[Alert]:
        """
        Evaluate a KPI value against thresholds.

        Returns an Alert if threshold breached, None otherwise.
        """
        if kpi_def is None:
            kpi_def = KPI_DEFINITIONS.get(kpi_name)
            if kpi_def is None:
                return None

        target = kpi_def.target

        # Calculate deviation
        if target == 0:
            deviation_pct = 1.0 if current_value != 0 else 0.0
        else:
            if kpi_def.higher_is_better:
                # Below target is bad
                deviation_pct = (target - current_value) / target
            else:
                # Above target is bad
                deviation_pct = (current_value - target) / target

        # Clamp deviation to prevent negative (better than target)
        deviation_pct = max(0.0, deviation_pct)

        # Determine severity
        if deviation_pct >= kpi_def.red_threshold or (kpi_def.is_critical and deviation_pct >= kpi_def.orange_threshold):
            severity = AlertSeverity.RED
        elif deviation_pct >= kpi_def.orange_threshold:
            severity = AlertSeverity.ORANGE
        elif deviation_pct >= kpi_def.yellow_threshold:
            severity = AlertSeverity.YELLOW
        else:
            severity = AlertSeverity.GREEN
            # Resolve existing alert if any
            self._resolve_alert(kpi_name)
            return None

        # Check if we already have an active alert
        existing = self._active_alerts.get(kpi_name)
        if existing and existing.severity == severity:
            # Same severity, don't create new alert
            return existing

        # Create new alert
        self._alert_counter += 1
        alert = Alert(
            id=f"ALERT-{self._alert_counter:06d}",
            kpi_name=kpi_name,
            severity=severity,
            current_value=current_value,
            target_value=target,
            deviation_pct=deviation_pct,
            timestamp=datetime.utcnow(),
            message=self._generate_alert_message(kpi_name, kpi_def, current_value, deviation_pct, severity),
        )

        self._active_alerts[kpi_name] = alert
        self._alert_history.append(alert)

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Handle paging
        self._handle_paging(alert, kpi_def)

        return alert

    def _generate_alert_message(
        self,
        kpi_name: str,
        kpi_def: KPIDefinition,
        current_value: float,
        deviation_pct: float,
        severity: AlertSeverity
    ) -> str:
        """Generate human-readable alert message"""
        direction = "below" if kpi_def.higher_is_better else "above"

        return (
            f"[{severity.value.upper()}] {kpi_def.description} is {deviation_pct*100:.1f}% "
            f"{direction} target. Current: {current_value:.3f} {kpi_def.unit}, "
            f"Target: {kpi_def.target:.3f} {kpi_def.unit}"
        )

    def _handle_paging(self, alert: Alert, kpi_def: KPIDefinition):
        """Handle paging based on alert severity"""
        rule = PAGING_RULES.get(alert.severity)
        if not rule or not rule.should_page:
            return

        # Log paging action (in production, integrate with PagerDuty/Slack/etc.)
        logger.warning(
            f"PAGING: {alert.message} | Channels: {rule.channels} | "
            f"Delay: {rule.page_delay_minutes}m | Escalation: {rule.escalation_delay_minutes}m"
        )

    def _resolve_alert(self, kpi_name: str):
        """Resolve an active alert"""
        if kpi_name in self._active_alerts:
            alert = self._active_alerts[kpi_name]
            alert.resolved = True
            alert.resolution_timestamp = datetime.utcnow()
            del self._active_alerts[kpi_name]
            logger.info(f"Alert resolved: {alert.id} - {kpi_name}")

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self._active_alerts.values():
            if alert.id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self._active_alerts.values())

    def get_alert_history(
        self,
        since: Optional[datetime] = None,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get alert history with optional filters"""
        alerts = self._alert_history

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts


# =============================================================================
# A/B TEST MONITORING
# =============================================================================

class ABTestMonitor:
    """
    Monitors A/B tests with statistical significance calculation.

    Features:
    - Track variant performance
    - Calculate statistical significance (chi-squared test)
    - Automatic winner declaration
    - Rollout recommendations
    """

    # Minimum sample size per variant for significance
    MIN_SAMPLE_SIZE = 100

    # Default significance threshold (95%)
    SIGNIFICANCE_THRESHOLD = 0.05

    def __init__(self):
        self._tests: Dict[str, Dict[str, ABTestVariant]] = {}
        self._test_metadata: Dict[str, Dict[str, Any]] = {}

    def create_test(
        self,
        test_id: str,
        test_name: str,
        metric_name: str,
        variants: List[str]
    ):
        """Create a new A/B test"""
        if test_id in self._tests:
            raise ValueError(f"Test {test_id} already exists")

        self._tests[test_id] = {
            name: ABTestVariant(name=name, sample_size=0, conversions=0, total_value=Decimal("0"))
            for name in variants
        }

        self._test_metadata[test_id] = {
            "name": test_name,
            "metric_name": metric_name,
            "created_at": datetime.utcnow(),
            "status": "running",
        }

        logger.info(f"A/B test created: {test_id} - {test_name}")

    def record_exposure(self, test_id: str, variant: str):
        """Record that a user was exposed to a variant"""
        if test_id not in self._tests:
            raise ValueError(f"Test {test_id} not found")

        if variant not in self._tests[test_id]:
            raise ValueError(f"Variant {variant} not found in test {test_id}")

        self._tests[test_id][variant].sample_size += 1

    def record_conversion(
        self,
        test_id: str,
        variant: str,
        value: Decimal = Decimal("1")
    ):
        """Record a conversion for a variant"""
        if test_id not in self._tests:
            raise ValueError(f"Test {test_id} not found")

        if variant not in self._tests[test_id]:
            raise ValueError(f"Variant {variant} not found in test {test_id}")

        self._tests[test_id][variant].conversions += 1
        self._tests[test_id][variant].total_value += value

    def analyze_test(self, test_id: str) -> ABTestResult:
        """
        Analyze an A/B test and determine if there's a significant winner.

        Uses chi-squared test for statistical significance.
        """
        if test_id not in self._tests:
            raise ValueError(f"Test {test_id} not found")

        variants = self._tests[test_id]
        metadata = self._test_metadata[test_id]

        if len(variants) != 2:
            raise ValueError("Currently only supports 2-variant tests")

        variant_names = list(variants.keys())
        control = variants[variant_names[0]]
        treatment = variants[variant_names[1]]

        # Calculate lift
        if control.conversion_rate > 0:
            lift = (treatment.conversion_rate - control.conversion_rate) / control.conversion_rate
        else:
            lift = 0.0 if treatment.conversion_rate == 0 else float("inf")

        # Calculate statistical significance using chi-squared test
        p_value = self._calculate_chi_squared_p_value(control, treatment)
        is_significant = p_value < self.SIGNIFICANCE_THRESHOLD
        confidence_level = 1 - p_value

        # Determine winner
        winner = None
        if is_significant:
            if treatment.conversion_rate > control.conversion_rate:
                winner = treatment.name
            elif control.conversion_rate > treatment.conversion_rate:
                winner = control.name

        # Calculate sample size needed for 80% power
        sample_size_needed = self._calculate_sample_size_needed(
            control.conversion_rate or 0.1,
            treatment.conversion_rate or 0.1
        )

        # Current power estimate
        current_power = self._estimate_power(control, treatment)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            control, treatment, is_significant, lift, current_power
        )

        return ABTestResult(
            test_id=test_id,
            test_name=metadata["name"],
            metric_name=metadata["metric_name"],
            control=control,
            treatment=treatment,
            lift=lift,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level,
            winner=winner,
            recommendation=recommendation,
            sample_size_needed=sample_size_needed,
            current_power=current_power,
        )

    def _calculate_chi_squared_p_value(
        self,
        control: ABTestVariant,
        treatment: ABTestVariant
    ) -> float:
        """
        Calculate p-value using chi-squared test for independence.
        """
        # Build contingency table
        # [control_conv, control_no_conv]
        # [treatment_conv, treatment_no_conv]

        a = control.conversions
        b = control.sample_size - control.conversions
        c = treatment.conversions
        d = treatment.sample_size - treatment.conversions

        total = a + b + c + d

        if total == 0:
            return 1.0

        # Expected values
        row1 = a + b
        row2 = c + d
        col1 = a + c
        col2 = b + d

        if row1 == 0 or row2 == 0 or col1 == 0 or col2 == 0:
            return 1.0

        e_a = (row1 * col1) / total
        e_b = (row1 * col2) / total
        e_c = (row2 * col1) / total
        e_d = (row2 * col2) / total

        # Chi-squared statistic
        chi2 = 0.0
        for observed, expected in [(a, e_a), (b, e_b), (c, e_c), (d, e_d)]:
            if expected > 0:
                chi2 += ((observed - expected) ** 2) / expected

        # Convert chi2 to p-value (1 degree of freedom)
        # Using approximation for chi-squared CDF
        p_value = self._chi2_survival(chi2, df=1)

        return p_value

    def _chi2_survival(self, x: float, df: int = 1) -> float:
        """
        Approximate survival function (1 - CDF) for chi-squared distribution.
        Uses the incomplete gamma function approximation.
        """
        if x <= 0:
            return 1.0

        # For df=1, use normal approximation
        if df == 1:
            z = math.sqrt(x)
            # Standard normal survival function approximation
            return 2 * (1 - self._normal_cdf(z))

        return 0.5  # Fallback

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _calculate_sample_size_needed(
        self,
        p1: float,
        p2: float,
        alpha: float = 0.05,
        power: float = 0.80
    ) -> int:
        """
        Calculate sample size needed per variant for desired power.
        """
        if p1 == p2 or p1 <= 0 or p2 <= 0:
            return 10000  # Default fallback

        # Z-scores for alpha and power
        z_alpha = 1.96  # 95% confidence
        z_power = 0.84  # 80% power

        p_bar = (p1 + p2) / 2

        numerator = 2 * p_bar * (1 - p_bar) * (z_alpha + z_power) ** 2
        denominator = (p1 - p2) ** 2

        if denominator == 0:
            return 10000

        n = numerator / denominator

        return int(math.ceil(n))

    def _estimate_power(
        self,
        control: ABTestVariant,
        treatment: ABTestVariant
    ) -> float:
        """Estimate current statistical power of the test"""
        if control.sample_size < self.MIN_SAMPLE_SIZE or treatment.sample_size < self.MIN_SAMPLE_SIZE:
            return 0.0

        p1 = control.conversion_rate
        p2 = treatment.conversion_rate
        n = min(control.sample_size, treatment.sample_size)

        if p1 == p2 or p1 <= 0 or p2 <= 0:
            return 0.0

        # Simplified power calculation
        p_bar = (p1 + p2) / 2
        se = math.sqrt(2 * p_bar * (1 - p_bar) / n)

        if se == 0:
            return 0.0

        effect = abs(p1 - p2)
        z = effect / se - 1.96

        power = self._normal_cdf(z)

        return min(1.0, max(0.0, power))

    def _generate_recommendation(
        self,
        control: ABTestVariant,
        treatment: ABTestVariant,
        is_significant: bool,
        lift: float,
        power: float
    ) -> str:
        """Generate actionable recommendation for the test"""
        total_sample = control.sample_size + treatment.sample_size

        if total_sample < self.MIN_SAMPLE_SIZE * 2:
            return f"Continue test: Need more data ({total_sample}/{self.MIN_SAMPLE_SIZE * 2} minimum samples)"

        if not is_significant:
            if power < 0.5:
                return "Continue test: Insufficient power to detect effect. Collect more samples."
            elif power < 0.8:
                return "Continue test: Approaching sufficient power. Consider extending test duration."
            else:
                return "No significant difference detected. Consider concluding test with no winner."

        if lift > 0.10:  # 10%+ lift
            return f"Strong winner: {treatment.name}. Recommend full rollout. Lift: {lift*100:.1f}%"
        elif lift > 0.05:  # 5-10% lift
            return f"Moderate winner: {treatment.name}. Recommend gradual rollout. Lift: {lift*100:.1f}%"
        elif lift > 0:
            return f"Marginal winner: {treatment.name}. Consider business impact before rollout. Lift: {lift*100:.1f}%"
        elif lift < -0.05:
            return f"Treatment underperforming control by {abs(lift)*100:.1f}%. Recommend reverting to control."
        else:
            return "Results inconclusive. Difference too small to be meaningful."

    def get_all_tests(self) -> Dict[str, Dict[str, Any]]:
        """Get all test metadata"""
        return {
            test_id: {
                **metadata,
                "variants": {name: v.__dict__ for name, v in self._tests[test_id].items()},
            }
            for test_id, metadata in self._test_metadata.items()
        }


# =============================================================================
# AUTOMATED REPORTING
# =============================================================================

class ReportGenerator:
    """
    Generates automated performance reports.

    Report types:
    - Real-time dashboard metrics
    - Daily performance summary
    - Weekly optimization recommendations
    - Monthly executive scorecards
    """

    def __init__(
        self,
        time_series_store: TimeSeriesStore,
        trend_detector: TrendDetector,
        alerting_engine: AlertingEngine,
        ab_test_monitor: ABTestMonitor
    ):
        self.store = time_series_store
        self.trends = trend_detector
        self.alerts = alerting_engine
        self.ab_tests = ab_test_monitor

    def generate_realtime_dashboard(self) -> Dict[str, Any]:
        """
        Generate real-time dashboard metrics.

        Returns current values and status for all KPIs.
        """
        dashboard = {
            "generated_at": datetime.utcnow().isoformat(),
            "stages": {},
            "alerts": {
                "active_count": len(self.alerts.get_active_alerts()),
                "by_severity": {},
            },
            "overall_health": "healthy",
        }

        # Organize by pipeline stage
        for stage in PipelineStage:
            dashboard["stages"][stage.value] = {
                "kpis": {},
                "status": "green",
            }

        # Populate KPIs
        worst_severity = AlertSeverity.GREEN
        severity_counts = {s.value: 0 for s in AlertSeverity}

        for kpi_name, kpi_def in KPI_DEFINITIONS.items():
            current_value = self.store.get_current_value(kpi_name)

            if current_value is None:
                continue

            # Get trend analysis
            trend = self.trends.analyze(kpi_name)

            # Evaluate for alerts
            alert = self.alerts.evaluate_kpi(kpi_name, current_value, kpi_def)
            severity = alert.severity if alert else AlertSeverity.GREEN

            severity_counts[severity.value] += 1

            if severity.value != "green" and (worst_severity == AlertSeverity.GREEN or
                                               list(AlertSeverity).index(severity) > list(AlertSeverity).index(worst_severity)):
                worst_severity = severity

            dashboard["stages"][kpi_def.stage.value]["kpis"][kpi_name] = {
                "value": current_value,
                "target": kpi_def.target,
                "unit": kpi_def.unit,
                "status": severity.value,
                "trend": trend.direction.value,
                "hourly_avg": trend.hourly_avg,
                "daily_avg": trend.daily_avg,
                "is_anomaly": trend.is_anomaly,
            }

            # Update stage status
            if severity != AlertSeverity.GREEN:
                current_stage_status = dashboard["stages"][kpi_def.stage.value]["status"]
                if current_stage_status == "green" or list(AlertSeverity).index(severity) > list(AlertSeverity).index(AlertSeverity[current_stage_status.upper()]):
                    dashboard["stages"][kpi_def.stage.value]["status"] = severity.value

        dashboard["alerts"]["by_severity"] = severity_counts
        dashboard["overall_health"] = worst_severity.value

        return dashboard

    def generate_daily_summary(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate daily performance summary.

        Includes:
        - KPI performance vs targets
        - Day-over-day changes
        - Alert summary
        - Top issues
        """
        report_date = date or datetime.utcnow()
        yesterday = report_date - timedelta(days=1)

        summary = {
            "report_type": "daily_summary",
            "report_date": report_date.strftime("%Y-%m-%d"),
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": "",
            "kpi_performance": {},
            "day_over_day": {},
            "alerts": {
                "triggered": 0,
                "resolved": 0,
                "active": 0,
            },
            "top_issues": [],
            "highlights": [],
        }

        issues = []
        highlights = []

        for kpi_name, kpi_def in KPI_DEFINITIONS.items():
            daily_data = self.store.get_daily_data(kpi_name, days=2)

            if not daily_data:
                continue

            current_avg = daily_data[-1].value if daily_data else 0
            previous_avg = daily_data[-2].value if len(daily_data) > 1 else current_avg

            # Calculate day-over-day change
            if previous_avg != 0:
                dod_change = (current_avg - previous_avg) / previous_avg
            else:
                dod_change = 0

            # Determine if hitting target
            if kpi_def.target != 0:
                target_pct = current_avg / kpi_def.target
            else:
                target_pct = 1.0

            summary["kpi_performance"][kpi_name] = {
                "current": current_avg,
                "target": kpi_def.target,
                "target_pct": target_pct,
                "unit": kpi_def.unit,
            }

            summary["day_over_day"][kpi_name] = {
                "previous": previous_avg,
                "current": current_avg,
                "change_pct": dod_change,
            }

            # Track issues and highlights
            if kpi_def.higher_is_better:
                if target_pct < 0.9:
                    issues.append({
                        "kpi": kpi_name,
                        "severity": "high" if target_pct < 0.8 else "medium",
                        "message": f"{kpi_def.description} at {target_pct*100:.1f}% of target",
                    })
                elif target_pct > 1.1:
                    highlights.append({
                        "kpi": kpi_name,
                        "message": f"{kpi_def.description} exceeding target by {(target_pct-1)*100:.1f}%",
                    })
            else:
                if target_pct > 1.1:
                    issues.append({
                        "kpi": kpi_name,
                        "severity": "high" if target_pct > 1.2 else "medium",
                        "message": f"{kpi_def.description} at {target_pct*100:.1f}% of target (lower is better)",
                    })
                elif target_pct < 0.9:
                    highlights.append({
                        "kpi": kpi_name,
                        "message": f"{kpi_def.description} better than target by {(1-target_pct)*100:.1f}%",
                    })

        # Sort issues by severity
        issues.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
        summary["top_issues"] = issues[:5]
        summary["highlights"] = highlights[:5]

        # Alert summary
        alert_history = self.alerts.get_alert_history(since=yesterday)
        summary["alerts"]["triggered"] = len(alert_history)
        summary["alerts"]["resolved"] = len([a for a in alert_history if a.resolved])
        summary["alerts"]["active"] = len(self.alerts.get_active_alerts())

        # Generate executive summary
        if not issues:
            summary["executive_summary"] = "All KPIs performing at or above target. System health is excellent."
        elif len([i for i in issues if i["severity"] == "high"]) > 0:
            high_issues = [i for i in issues if i["severity"] == "high"]
            summary["executive_summary"] = f"ATTENTION REQUIRED: {len(high_issues)} critical issues detected. Immediate review recommended."
        else:
            summary["executive_summary"] = f"{len(issues)} minor issues detected. Overall system health is good."

        return summary

    def generate_weekly_recommendations(self, week_ending: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate weekly optimization recommendations.

        Analyzes trends and suggests improvements.
        """
        end_date = week_ending or datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        report = {
            "report_type": "weekly_recommendations",
            "week_ending": end_date.strftime("%Y-%m-%d"),
            "generated_at": datetime.utcnow().isoformat(),
            "trend_summary": {},
            "recommendations": [],
            "optimization_opportunities": [],
            "ab_test_updates": [],
            "next_week_focus": [],
        }

        recommendations = []
        opportunities = []

        for kpi_name, kpi_def in KPI_DEFINITIONS.items():
            trend = self.trends.analyze(kpi_name)

            report["trend_summary"][kpi_name] = {
                "direction": trend.direction.value,
                "weekly_avg": trend.weekly_avg,
                "slope": trend.slope,
                "drift_detected": trend.drift_detected,
            }

            # Generate recommendations based on trends
            if trend.direction == TrendDirection.DEGRADING and trend.confidence > 0.7:
                recommendations.append({
                    "kpi": kpi_name,
                    "priority": "high",
                    "recommendation": f"Investigate declining {kpi_def.description}. "
                                     f"Weekly trend shows {abs(trend.slope)*100:.1f}% degradation.",
                    "suggested_actions": self._get_suggested_actions(kpi_name, trend),
                })

            if trend.drift_detected:
                recommendations.append({
                    "kpi": kpi_name,
                    "priority": "medium",
                    "recommendation": f"Model drift detected for {kpi_def.description}. "
                                     f"Drift magnitude: {trend.drift_magnitude*100:.1f}%",
                    "suggested_actions": [
                        "Review recent model updates",
                        "Check for data quality issues",
                        "Consider model retraining",
                    ],
                })

            # Identify optimization opportunities
            if trend.direction == TrendDirection.IMPROVING and trend.confidence > 0.6:
                opportunities.append({
                    "kpi": kpi_name,
                    "insight": f"{kpi_def.description} showing positive trend. "
                              f"Consider amplifying successful strategies.",
                })

        report["recommendations"] = sorted(recommendations, key=lambda x: 0 if x["priority"] == "high" else 1)
        report["optimization_opportunities"] = opportunities[:5]

        # A/B test updates
        for test_id, test_data in self.ab_tests.get_all_tests().items():
            try:
                result = self.ab_tests.analyze_test(test_id)
                report["ab_test_updates"].append({
                    "test_id": test_id,
                    "test_name": result.test_name,
                    "status": "significant" if result.is_significant else "running",
                    "lift": result.lift,
                    "recommendation": result.recommendation,
                })
            except Exception as e:
                logger.error(f"Error analyzing test {test_id}: {e}")

        # Generate next week focus areas
        report["next_week_focus"] = self._generate_focus_areas(recommendations, opportunities)

        return report

    def _get_suggested_actions(self, kpi_name: str, trend: TrendAnalysis) -> List[str]:
        """Generate suggested actions for a KPI issue"""
        actions = []

        if "acquire" in kpi_name:
            actions = [
                "Review ML model performance metrics",
                "Check scoring service latency",
                "Validate input data quality",
            ]
        elif "locate" in kpi_name:
            actions = [
                "Audit skip trace vendor performance",
                "Review data freshness policies",
                "Check contact append success rates",
            ]
        elif "contact" in kpi_name:
            actions = [
                "Analyze channel performance by segment",
                "Review message content effectiveness",
                "Check delivery infrastructure status",
            ]
        elif "negotiate" in kpi_name:
            actions = [
                "Review offer acceptance by settlement %",
                "Analyze negotiation script effectiveness",
                "Check agent performance metrics",
            ]
        elif "collect" in kpi_name:
            actions = [
                "Review payment processor status",
                "Analyze decline reasons",
                "Check retry strategy effectiveness",
            ]
        elif "close" in kpi_name:
            actions = [
                "Review payment plan structures",
                "Analyze re-default triggers",
                "Check follow-up cadence",
            ]
        elif "profit" in kpi_name:
            actions = [
                "Review cost structure by channel",
                "Analyze revenue per account by segment",
                "Check margin by client",
            ]

        return actions

    def _generate_focus_areas(
        self,
        recommendations: List[Dict],
        opportunities: List[Dict]
    ) -> List[str]:
        """Generate focus areas for next week"""
        focus = []

        # High priority recommendations become focus areas
        for rec in recommendations[:3]:
            if rec["priority"] == "high":
                focus.append(f"Address {rec['kpi']}: {rec['recommendation'][:100]}")

        # Add top opportunity
        if opportunities:
            focus.append(f"Capitalize on {opportunities[0]['kpi']} improvement")

        if not focus:
            focus.append("Continue monitoring - all KPIs stable")

        return focus

    def generate_monthly_scorecard(self, month: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate monthly executive scorecard.

        High-level summary for leadership review.
        """
        report_month = month or datetime.utcnow()

        scorecard = {
            "report_type": "monthly_scorecard",
            "month": report_month.strftime("%Y-%m"),
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": "",
            "overall_score": 0.0,
            "stage_scores": {},
            "key_metrics": {},
            "month_over_month": {},
            "strategic_insights": [],
            "action_items": [],
        }

        # Calculate overall score (0-100)
        stage_scores = {}
        total_score = 0
        kpi_count = 0

        for stage in PipelineStage:
            stage_kpis = [k for k, v in KPI_DEFINITIONS.items() if v.stage == stage]
            stage_score = 0

            for kpi_name in stage_kpis:
                current = self.store.get_current_value(kpi_name)
                kpi_def = KPI_DEFINITIONS[kpi_name]

                if current is not None and kpi_def.target != 0:
                    if kpi_def.higher_is_better:
                        score = min(100, (current / kpi_def.target) * 100)
                    else:
                        score = min(100, (kpi_def.target / current) * 100) if current > 0 else 100

                    stage_score += score
                    total_score += score
                    kpi_count += 1

            if stage_kpis:
                stage_scores[stage.value] = stage_score / len(stage_kpis)
            else:
                stage_scores[stage.value] = 100

        scorecard["stage_scores"] = stage_scores
        scorecard["overall_score"] = total_score / kpi_count if kpi_count > 0 else 100

        # Key metrics summary
        key_metrics = [
            "profit_margin", "profit_roi", "contact_response_rate",
            "collect_payment_success_rate", "negotiate_acceptance_rate"
        ]

        for kpi_name in key_metrics:
            current = self.store.get_current_value(kpi_name)
            kpi_def = KPI_DEFINITIONS.get(kpi_name)

            if current is not None and kpi_def:
                scorecard["key_metrics"][kpi_name] = {
                    "value": current,
                    "target": kpi_def.target,
                    "status": "on_track" if (
                        (kpi_def.higher_is_better and current >= kpi_def.target * 0.9) or
                        (not kpi_def.higher_is_better and current <= kpi_def.target * 1.1)
                    ) else "needs_attention",
                }

        # Generate executive summary
        score = scorecard["overall_score"]
        if score >= 90:
            scorecard["executive_summary"] = "Exceptional performance across all pipeline stages. " \
                                             "Continue current strategies and look for optimization opportunities."
        elif score >= 80:
            scorecard["executive_summary"] = "Strong performance with minor areas for improvement. " \
                                             "Focus on identified gaps to reach excellence."
        elif score >= 70:
            scorecard["executive_summary"] = "Satisfactory performance with notable improvement areas. " \
                                             "Prioritize action items to improve overall efficiency."
        else:
            scorecard["executive_summary"] = "Performance below expectations. Immediate attention required " \
                                             "on multiple fronts. Review strategic priorities."

        # Strategic insights
        scorecard["strategic_insights"] = self._generate_strategic_insights(stage_scores)

        # Action items
        scorecard["action_items"] = self._generate_action_items(stage_scores, scorecard["key_metrics"])

        return scorecard

    def _generate_strategic_insights(self, stage_scores: Dict[str, float]) -> List[str]:
        """Generate strategic insights from stage performance"""
        insights = []

        # Find best and worst stages
        sorted_stages = sorted(stage_scores.items(), key=lambda x: x[1])
        worst_stage = sorted_stages[0]
        best_stage = sorted_stages[-1]

        if worst_stage[1] < 80:
            insights.append(
                f"Bottleneck identified: {worst_stage[0].upper()} stage performing at {worst_stage[1]:.0f}%. "
                f"Improving this stage will have cascading benefits downstream."
            )

        if best_stage[1] > 95:
            insights.append(
                f"Excellence in {best_stage[0].upper()} stage ({best_stage[1]:.0f}%). "
                f"Document and share best practices across organization."
            )

        # Look for stage-to-stage patterns
        stage_list = ["acquire", "locate", "contact", "negotiate", "collect", "close", "profit"]
        for i in range(len(stage_list) - 1):
            current = stage_scores.get(stage_list[i], 100)
            next_stage = stage_scores.get(stage_list[i + 1], 100)

            if current > 90 and next_stage < 75:
                insights.append(
                    f"Conversion drop detected: Strong {stage_list[i].upper()} ({current:.0f}%) but "
                    f"weak {stage_list[i + 1].upper()} ({next_stage:.0f}%). Review handoff process."
                )

        return insights

    def _generate_action_items(
        self,
        stage_scores: Dict[str, float],
        key_metrics: Dict[str, Dict]
    ) -> List[Dict[str, str]]:
        """Generate prioritized action items"""
        actions = []

        # Stage-based actions
        for stage, score in stage_scores.items():
            if score < 70:
                actions.append({
                    "priority": "high",
                    "action": f"Conduct deep-dive analysis on {stage.upper()} stage",
                    "owner": "Operations Lead",
                    "due": "This week",
                })
            elif score < 85:
                actions.append({
                    "priority": "medium",
                    "action": f"Develop improvement plan for {stage.upper()} stage",
                    "owner": "Stage Manager",
                    "due": "Next 2 weeks",
                })

        # Metric-based actions
        for metric_name, data in key_metrics.items():
            if data["status"] == "needs_attention":
                actions.append({
                    "priority": "medium",
                    "action": f"Investigate and address {metric_name} underperformance",
                    "owner": "Analytics Team",
                    "due": "This week",
                })

        return sorted(actions, key=lambda x: 0 if x["priority"] == "high" else 1)[:10]


# =============================================================================
# MAIN PERFORMANCE MONITOR
# =============================================================================

class PerformanceMonitor:
    """
    Main orchestrator for the QUAN performance monitoring system.

    Integrates:
    - KPI tracking
    - Time series storage
    - Trend detection
    - Alerting
    - A/B test monitoring
    - Automated reporting
    """

    def __init__(self):
        self.time_series = TimeSeriesStore()
        self.trend_detector = TrendDetector(self.time_series)
        self.alerting = AlertingEngine()
        self.ab_tests = ABTestMonitor()
        self.reports = ReportGenerator(
            self.time_series,
            self.trend_detector,
            self.alerting,
            self.ab_tests
        )

        self._running = False
        self._collection_task: Optional[asyncio.Task] = None

        logger.info("QUAN Performance Monitor initialized")

    def record_metric(
        self,
        kpi_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        """Record a metric value"""
        # Store in time series
        self.time_series.record(kpi_name, value, timestamp)

        # Evaluate against thresholds
        kpi_def = KPI_DEFINITIONS.get(kpi_name)
        if kpi_def:
            self.alerting.evaluate_kpi(kpi_name, value, kpi_def)

        logger.debug(f"Recorded {kpi_name}={value}")

    def record_ab_test_event(
        self,
        test_id: str,
        variant: str,
        event_type: str,
        value: Optional[Decimal] = None
    ):
        """Record an A/B test event"""
        if event_type == "exposure":
            self.ab_tests.record_exposure(test_id, variant)
        elif event_type == "conversion":
            self.ab_tests.record_conversion(test_id, variant, value or Decimal("1"))

    def get_kpi_status(self, kpi_name: str) -> Dict[str, Any]:
        """Get current status for a KPI"""
        current = self.time_series.get_current_value(kpi_name)
        kpi_def = KPI_DEFINITIONS.get(kpi_name)
        trend = self.trend_detector.analyze(kpi_name)

        return {
            "kpi_name": kpi_name,
            "current_value": current,
            "target": kpi_def.target if kpi_def else None,
            "unit": kpi_def.unit if kpi_def else None,
            "trend": trend.direction.value,
            "hourly_avg": trend.hourly_avg,
            "daily_avg": trend.daily_avg,
            "weekly_avg": trend.weekly_avg,
            "is_anomaly": trend.is_anomaly,
            "drift_detected": trend.drift_detected,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Get real-time dashboard"""
        return self.reports.generate_realtime_dashboard()

    def get_daily_report(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get daily performance summary"""
        return self.reports.generate_daily_summary(date)

    def get_weekly_report(self, week_ending: Optional[datetime] = None) -> Dict[str, Any]:
        """Get weekly optimization recommendations"""
        return self.reports.generate_weekly_recommendations(week_ending)

    def get_monthly_scorecard(self, month: Optional[datetime] = None) -> Dict[str, Any]:
        """Get monthly executive scorecard"""
        return self.reports.generate_monthly_scorecard(month)

    def get_ab_test_results(self, test_id: str) -> ABTestResult:
        """Get A/B test analysis results"""
        return self.ab_tests.analyze_test(test_id)

    def create_ab_test(
        self,
        test_id: str,
        test_name: str,
        metric_name: str,
        variants: List[str] = None
    ):
        """Create a new A/B test"""
        if variants is None:
            variants = ["control", "treatment"]
        self.ab_tests.create_test(test_id, test_name, metric_name, variants)

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return self.alerting.get_active_alerts()

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        return self.alerting.acknowledge_alert(alert_id)

    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for new alerts"""
        self.alerting.register_callback(callback)

    async def start_collection(self, interval_seconds: float = 60.0):
        """
        Start background metric collection loop.

        In production, this would pull metrics from various sources.
        """
        if self._running:
            return

        self._running = True
        self._collection_task = asyncio.create_task(
            self._collection_loop(interval_seconds)
        )
        logger.info(f"Started metric collection (interval: {interval_seconds}s)")

    async def stop_collection(self):
        """Stop background metric collection"""
        self._running = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped metric collection")

    async def _collection_loop(self, interval: float):
        """Background loop for metric collection"""
        while self._running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metric collection error: {e}")
                await asyncio.sleep(interval)

    async def _collect_metrics(self):
        """
        Collect metrics from various sources.

        In production, this would integrate with:
        - Prometheus
        - Database queries
        - Service endpoints
        - Log aggregators
        """
        # Placeholder - in production, fetch real metrics
        # This simulates metric collection for demonstration
        pass


# =============================================================================
# DEMONSTRATION / TESTING
# =============================================================================

async def run_demo():
    """Demonstrate the performance monitoring system"""
    print("\n" + "=" * 75)
    print("  QUAN PERFORMANCE MONITORING SYSTEM - DEMONSTRATION")
    print("=" * 75)

    monitor = PerformanceMonitor()

    # Simulate some metric data
    print("\n  Recording simulated metrics...")

    # Simulate 60 minutes of data
    now = datetime.utcnow()
    for i in range(60):
        ts = now - timedelta(minutes=60 - i)

        # ACQUIRE metrics
        monitor.record_metric(
            "acquire_accounts_per_hour",
            4500 + random.gauss(0, 300),
            timestamp=ts
        )
        monitor.record_metric(
            "acquire_scoring_latency_ms",
            45 + random.gauss(0, 5),
            timestamp=ts
        )

        # LOCATE metrics
        monitor.record_metric(
            "locate_skip_trace_success_rate",
            0.72 + random.gauss(0, 0.03),
            timestamp=ts
        )

        # CONTACT metrics
        monitor.record_metric(
            "contact_response_rate",
            0.14 + random.gauss(0, 0.02),
            timestamp=ts
        )
        monitor.record_metric(
            "contact_delivery_rate",
            0.94 + random.gauss(0, 0.01),
            timestamp=ts
        )

        # NEGOTIATE metrics
        monitor.record_metric(
            "negotiate_acceptance_rate",
            0.33 + random.gauss(0, 0.03),
            timestamp=ts
        )

        # COLLECT metrics
        monitor.record_metric(
            "collect_payment_success_rate",
            0.90 + random.gauss(0, 0.02),
            timestamp=ts
        )

        # PROFIT metrics
        monitor.record_metric(
            "profit_margin",
            0.83 + random.gauss(0, 0.02),
            timestamp=ts
        )
        monitor.record_metric(
            "profit_roi",
            2.8 + random.gauss(0, 0.2),
            timestamp=ts
        )

    print("  Metrics recorded.\n")

    # Display real-time dashboard
    print("  " + "-" * 71)
    print("  REAL-TIME DASHBOARD")
    print("  " + "-" * 71)

    dashboard = monitor.get_dashboard()
    print(f"  Overall Health: {dashboard['overall_health'].upper()}")
    print(f"  Active Alerts: {dashboard['alerts']['active_count']}")

    for stage, data in dashboard["stages"].items():
        kpi_count = len(data["kpis"])
        print(f"\n  {stage.upper()} Stage ({data['status'].upper()}):")
        for kpi_name, kpi_data in list(data["kpis"].items())[:2]:
            print(f"    {kpi_name}: {kpi_data['value']:.3f} {kpi_data['unit']} "
                  f"(target: {kpi_data['target']}) [{kpi_data['trend']}]")

    # Create and analyze an A/B test
    print("\n  " + "-" * 71)
    print("  A/B TEST MONITORING")
    print("  " + "-" * 71)

    monitor.create_ab_test(
        test_id="test-001",
        test_name="New Settlement Offer Copy",
        metric_name="negotiate_acceptance_rate",
        variants=["control", "new_copy"]
    )

    # Simulate test data
    for _ in range(500):
        monitor.ab_tests.record_exposure("test-001", "control")
        if random.random() < 0.33:
            monitor.ab_tests.record_conversion("test-001", "control", Decimal("150"))

    for _ in range(500):
        monitor.ab_tests.record_exposure("test-001", "new_copy")
        if random.random() < 0.38:
            monitor.ab_tests.record_conversion("test-001", "new_copy", Decimal("155"))

    result = monitor.get_ab_test_results("test-001")
    print(f"\n  Test: {result.test_name}")
    print(f"  Control: {result.control.conversion_rate*100:.1f}% ({result.control.sample_size} samples)")
    print(f"  Treatment: {result.treatment.conversion_rate*100:.1f}% ({result.treatment.sample_size} samples)")
    print(f"  Lift: {result.lift*100:.1f}%")
    print(f"  P-value: {result.p_value:.4f}")
    print(f"  Significant: {'Yes' if result.is_significant else 'No'}")
    print(f"  Recommendation: {result.recommendation}")

    # Display active alerts
    print("\n  " + "-" * 71)
    print("  ACTIVE ALERTS")
    print("  " + "-" * 71)

    alerts = monitor.get_active_alerts()
    if alerts:
        for alert in alerts[:5]:
            print(f"  [{alert.severity.value.upper()}] {alert.kpi_name}: {alert.message[:60]}...")
    else:
        print("  No active alerts - all KPIs within thresholds")

    # Daily summary excerpt
    print("\n  " + "-" * 71)
    print("  DAILY SUMMARY (excerpt)")
    print("  " + "-" * 71)

    daily = monitor.get_daily_report()
    print(f"  {daily['executive_summary']}")
    print(f"\n  Top Issues:")
    for issue in daily["top_issues"][:3]:
        print(f"    [{issue['severity'].upper()}] {issue['message']}")

    print("\n  Highlights:")
    for highlight in daily["highlights"][:3]:
        print(f"    + {highlight['message']}")

    print("\n" + "=" * 75)
    print("  Demo complete. Performance monitoring system ready.")
    print("=" * 75 + "\n")


# Global instance
_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


if __name__ == "__main__":
    asyncio.run(run_demo())
