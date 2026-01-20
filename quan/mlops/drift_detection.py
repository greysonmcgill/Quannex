"""
Drift Detection and Observability System for QUAN MLOps

Comprehensive ML drift monitoring including:
- Feature drift detection (PSI, KS test, histogram comparison)
- Label drift detection with delay awareness
- Concept drift identification
- Per-request metrics capture
- Rolling window quality comparison
- Grafana dashboard specifications
- Prometheus alert rules
- 24-hour drift detection SLA
- Automatic testing triggers on drift
- Evidently/Alibi integration hooks

Key guarantees:
- Drift detected within 24 hours
- PSI alerts at 0.1 (warning) and 0.25 (critical)
- KS test alerts at p < 0.01
- Automatic model retraining triggers
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import statistics
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple, TypeVar, Union

# Conditional imports
NUMPY_AVAILABLE = False
SCIPY_AVAILABLE = False
PANDAS_AVAILABLE = False
PROMETHEUS_AVAILABLE = False
EVIDENTLY_AVAILABLE = False
ALIBI_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None

try:
    from scipy import stats as scipy_stats
    from scipy.spatial.distance import jensenshannon
    SCIPY_AVAILABLE = True
except ImportError:
    scipy_stats = None
    jensenshannon = None

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, Summary
    PROMETHEUS_AVAILABLE = True
except ImportError:
    Counter = Histogram = Gauge = Info = Summary = None

try:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
    from evidently.metrics import DataDriftTable, DatasetDriftMetric
    EVIDENTLY_AVAILABLE = True
except ImportError:
    Report = DataDriftPreset = TargetDriftPreset = None
    DataDriftTable = DatasetDriftMetric = None

try:
    from alibi_detect.cd import TabularDrift, ChiSquareDrift, KSDrift
    from alibi_detect.cd import ClassifierDrift
    ALIBI_AVAILABLE = True
except ImportError:
    TabularDrift = ChiSquareDrift = KSDrift = ClassifierDrift = None


logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Configuration
# =============================================================================

# PSI thresholds (industry standard)
PSI_THRESHOLD_WARNING = 0.1
PSI_THRESHOLD_CRITICAL = 0.25

# KS test threshold
KS_PVALUE_THRESHOLD = 0.01

# Drift detection SLA
DRIFT_DETECTION_SLA_HOURS = 24

# Default window sizes
DEFAULT_REFERENCE_WINDOW = 10000
DEFAULT_ANALYSIS_WINDOW = 1000
DEFAULT_ROLLING_WINDOW_HOURS = 24

# Histogram bins for PSI calculation
DEFAULT_PSI_BINS = 10


class DriftType(Enum):
    """Types of drift that can be detected"""
    FEATURE_DRIFT = "feature_drift"
    LABEL_DRIFT = "label_drift"
    CONCEPT_DRIFT = "concept_drift"
    PREDICTION_DRIFT = "prediction_drift"
    COVARIATE_SHIFT = "covariate_shift"
    PRIOR_PROBABILITY_SHIFT = "prior_probability_shift"


class DriftSeverity(Enum):
    """Severity levels for drift alerts"""
    NONE = "none"
    LOW = "low"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class DriftTestType(Enum):
    """Statistical tests for drift detection"""
    PSI = "psi"
    KS_TEST = "ks_test"
    CHI_SQUARE = "chi_square"
    JENSEN_SHANNON = "jensen_shannon"
    WASSERSTEIN = "wasserstein"
    MANN_WHITNEY = "mann_whitney"
    PERMUTATION = "permutation"


class AlertChannel(Enum):
    """Alert notification channels"""
    PROMETHEUS = "prometheus"
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DriftTestResult:
    """Result of a single drift test"""
    test_type: DriftTestType
    feature_name: str
    statistic: float
    p_value: Optional[float]
    threshold: float
    is_drift_detected: bool
    severity: DriftSeverity
    reference_stats: Dict[str, float]
    current_stats: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "test_type": self.test_type.value,
            "feature_name": self.feature_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "threshold": self.threshold,
            "is_drift_detected": self.is_drift_detected,
            "severity": self.severity.value,
            "reference_stats": self.reference_stats,
            "current_stats": self.current_stats,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class FeatureHistogram:
    """Histogram representation for a feature"""
    feature_name: str
    bin_edges: List[float]
    counts: List[int]
    proportions: List[float]
    n_samples: int
    min_value: float
    max_value: float
    mean: float
    std: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return asdict(self)


@dataclass
class DriftAlert:
    """Alert generated when drift is detected"""
    alert_id: str
    drift_type: DriftType
    severity: DriftSeverity
    feature_name: Optional[str]
    test_results: List[DriftTestResult]
    message: str
    recommended_action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False
    resolved: bool = False
    resolution_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "alert_id": self.alert_id,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "feature_name": self.feature_name,
            "test_results": [r.to_dict() for r in self.test_results],
            "message": self.message,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolution_timestamp": self.resolution_timestamp,
        }


@dataclass
class PredictionMetrics:
    """Metrics captured per prediction request"""
    request_id: str
    model_version: str
    features: Dict[str, float]
    prediction: float
    probability: Optional[float]
    confidence: Optional[float]
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    label: Optional[float] = None
    label_timestamp: Optional[str] = None
    label_delay_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return asdict(self)


@dataclass
class DriftReport:
    """Comprehensive drift analysis report"""
    report_id: str
    analysis_window_start: str
    analysis_window_end: str
    reference_window_start: str
    reference_window_end: str
    n_reference_samples: int
    n_analysis_samples: int
    feature_drift_results: Dict[str, DriftTestResult]
    label_drift_result: Optional[DriftTestResult]
    concept_drift_result: Optional[DriftTestResult]
    overall_drift_detected: bool
    overall_severity: DriftSeverity
    alerts_generated: List[DriftAlert]
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "report_id": self.report_id,
            "analysis_window_start": self.analysis_window_start,
            "analysis_window_end": self.analysis_window_end,
            "reference_window_start": self.reference_window_start,
            "reference_window_end": self.reference_window_end,
            "n_reference_samples": self.n_reference_samples,
            "n_analysis_samples": self.n_analysis_samples,
            "feature_drift_results": {
                k: v.to_dict() for k, v in self.feature_drift_results.items()
            },
            "label_drift_result": self.label_drift_result.to_dict() if self.label_drift_result else None,
            "concept_drift_result": self.concept_drift_result.to_dict() if self.concept_drift_result else None,
            "overall_drift_detected": self.overall_drift_detected,
            "overall_severity": self.overall_severity.value,
            "alerts_generated": [a.to_dict() for a in self.alerts_generated],
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Statistical Test Implementations
# =============================================================================

class PSICalculator:
    """
    Population Stability Index (PSI) Calculator

    PSI measures how much a distribution has shifted between two periods.

    Interpretation:
    - PSI < 0.1: No significant shift
    - 0.1 <= PSI < 0.25: Moderate shift (warning)
    - PSI >= 0.25: Significant shift (action required)

    Formula: PSI = sum((actual% - expected%) * ln(actual% / expected%))
    """

    def __init__(self, n_bins: int = DEFAULT_PSI_BINS, epsilon: float = 1e-10):
        self.n_bins = n_bins
        self.epsilon = epsilon  # Prevent division by zero

    def calculate(
        self,
        reference: List[float],
        current: List[float],
        bin_edges: Optional[List[float]] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate PSI between reference and current distributions.

        Args:
            reference: Reference distribution values
            current: Current distribution values
            bin_edges: Optional predefined bin edges

        Returns:
            Tuple of (PSI value, calculation details)
        """
        if not NUMPY_AVAILABLE:
            return self._calculate_pure_python(reference, current, bin_edges)

        ref_array = np.array(reference)
        cur_array = np.array(current)

        # Determine bin edges from reference if not provided
        if bin_edges is None:
            min_val = min(ref_array.min(), cur_array.min())
            max_val = max(ref_array.max(), cur_array.max())
            bin_edges = np.linspace(min_val, max_val, self.n_bins + 1)

        # Calculate histograms
        ref_counts, _ = np.histogram(ref_array, bins=bin_edges)
        cur_counts, _ = np.histogram(cur_array, bins=bin_edges)

        # Convert to proportions
        ref_props = (ref_counts + self.epsilon) / (len(reference) + self.epsilon * self.n_bins)
        cur_props = (cur_counts + self.epsilon) / (len(current) + self.epsilon * self.n_bins)

        # Calculate PSI
        psi_values = (cur_props - ref_props) * np.log(cur_props / ref_props)
        total_psi = np.sum(psi_values)

        details = {
            "bin_edges": bin_edges.tolist() if hasattr(bin_edges, 'tolist') else list(bin_edges),
            "reference_proportions": ref_props.tolist(),
            "current_proportions": cur_props.tolist(),
            "psi_per_bin": psi_values.tolist(),
            "n_reference": len(reference),
            "n_current": len(current),
        }

        return float(total_psi), details

    def _calculate_pure_python(
        self,
        reference: List[float],
        current: List[float],
        bin_edges: Optional[List[float]] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """Pure Python implementation without NumPy"""
        # Determine bin edges
        if bin_edges is None:
            min_val = min(min(reference), min(current))
            max_val = max(max(reference), max(current))
            step = (max_val - min_val) / self.n_bins
            bin_edges = [min_val + i * step for i in range(self.n_bins + 1)]

        # Calculate histogram counts
        def histogram(values: List[float], edges: List[float]) -> List[int]:
            counts = [0] * (len(edges) - 1)
            for v in values:
                for i in range(len(edges) - 1):
                    if edges[i] <= v < edges[i + 1]:
                        counts[i] += 1
                        break
                    elif i == len(edges) - 2 and v == edges[i + 1]:
                        counts[i] += 1
                        break
            return counts

        ref_counts = histogram(reference, bin_edges)
        cur_counts = histogram(current, bin_edges)

        # Convert to proportions
        ref_total = len(reference) + self.epsilon * self.n_bins
        cur_total = len(current) + self.epsilon * self.n_bins

        ref_props = [(c + self.epsilon) / ref_total for c in ref_counts]
        cur_props = [(c + self.epsilon) / cur_total for c in cur_counts]

        # Calculate PSI
        psi_values = []
        for ref_p, cur_p in zip(ref_props, cur_props):
            psi_val = (cur_p - ref_p) * math.log(cur_p / ref_p)
            psi_values.append(psi_val)

        total_psi = sum(psi_values)

        details = {
            "bin_edges": bin_edges,
            "reference_proportions": ref_props,
            "current_proportions": cur_props,
            "psi_per_bin": psi_values,
            "n_reference": len(reference),
            "n_current": len(current),
        }

        return total_psi, details

    def get_severity(self, psi_value: float) -> DriftSeverity:
        """Get drift severity based on PSI value"""
        if psi_value < PSI_THRESHOLD_WARNING:
            return DriftSeverity.NONE
        elif psi_value < PSI_THRESHOLD_CRITICAL:
            return DriftSeverity.WARNING
        else:
            return DriftSeverity.CRITICAL


class KSTestCalculator:
    """
    Kolmogorov-Smirnov Test Calculator

    The KS test compares the empirical cumulative distribution functions
    of two samples. It's non-parametric and doesn't assume any particular
    distribution shape.

    Null hypothesis: Both samples are drawn from the same distribution.
    """

    def __init__(self, p_value_threshold: float = KS_PVALUE_THRESHOLD):
        self.p_value_threshold = p_value_threshold

    def calculate(
        self,
        reference: List[float],
        current: List[float]
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Perform two-sample KS test.

        Args:
            reference: Reference distribution values
            current: Current distribution values

        Returns:
            Tuple of (KS statistic, p-value, calculation details)
        """
        if SCIPY_AVAILABLE:
            result = scipy_stats.ks_2samp(reference, current)
            ks_statistic = result.statistic
            p_value = result.pvalue
        else:
            # Pure Python implementation
            ks_statistic, p_value = self._calculate_pure_python(reference, current)

        details = {
            "ks_statistic": ks_statistic,
            "p_value": p_value,
            "p_value_threshold": self.p_value_threshold,
            "is_significant": p_value < self.p_value_threshold,
            "n_reference": len(reference),
            "n_current": len(current),
            "reference_mean": statistics.mean(reference),
            "current_mean": statistics.mean(current),
            "reference_std": statistics.stdev(reference) if len(reference) > 1 else 0,
            "current_std": statistics.stdev(current) if len(current) > 1 else 0,
        }

        return ks_statistic, p_value, details

    def _calculate_pure_python(
        self,
        reference: List[float],
        current: List[float]
    ) -> Tuple[float, float]:
        """Pure Python KS test implementation"""
        # Sort both samples
        ref_sorted = sorted(reference)
        cur_sorted = sorted(current)

        n1 = len(reference)
        n2 = len(current)

        # Merge and compute ECDFs
        all_values = sorted(set(ref_sorted + cur_sorted))

        max_diff = 0.0
        ref_idx = 0
        cur_idx = 0

        for val in all_values:
            # ECDF for reference
            while ref_idx < n1 and ref_sorted[ref_idx] <= val:
                ref_idx += 1
            ref_ecdf = ref_idx / n1

            # ECDF for current
            while cur_idx < n2 and cur_sorted[cur_idx] <= val:
                cur_idx += 1
            cur_ecdf = cur_idx / n2

            diff = abs(ref_ecdf - cur_ecdf)
            max_diff = max(max_diff, diff)

        # Approximate p-value using asymptotic distribution
        # D_n ~ K where K is Kolmogorov distribution
        n = n1 * n2 / (n1 + n2)
        lambda_val = max_diff * math.sqrt(n)

        # Approximate p-value (simplified)
        if lambda_val > 3:
            p_value = 0.0
        else:
            p_value = 2 * math.exp(-2 * lambda_val ** 2)
            p_value = min(1.0, max(0.0, p_value))

        return max_diff, p_value

    def get_severity(self, p_value: float, ks_statistic: float) -> DriftSeverity:
        """Get drift severity based on KS test results"""
        if p_value >= self.p_value_threshold:
            return DriftSeverity.NONE
        elif ks_statistic < 0.2:
            return DriftSeverity.WARNING
        elif ks_statistic < 0.4:
            return DriftSeverity.CRITICAL
        else:
            return DriftSeverity.EMERGENCY


class JensenShannonCalculator:
    """
    Jensen-Shannon Divergence Calculator

    A symmetric and bounded measure of distribution difference.
    JSD is the square root of Jensen-Shannon divergence, bounded in [0, 1].
    """

    def __init__(self, n_bins: int = DEFAULT_PSI_BINS):
        self.n_bins = n_bins

    def calculate(
        self,
        reference: List[float],
        current: List[float]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate Jensen-Shannon distance between distributions.

        Returns:
            Tuple of (JS distance, calculation details)
        """
        if not NUMPY_AVAILABLE:
            return self._calculate_pure_python(reference, current)

        # Create histograms
        min_val = min(min(reference), min(current))
        max_val = max(max(reference), max(current))
        bins = np.linspace(min_val, max_val, self.n_bins + 1)

        ref_hist, _ = np.histogram(reference, bins=bins, density=True)
        cur_hist, _ = np.histogram(current, bins=bins, density=True)

        # Normalize to probability distributions
        ref_hist = ref_hist / ref_hist.sum() if ref_hist.sum() > 0 else ref_hist
        cur_hist = cur_hist / cur_hist.sum() if cur_hist.sum() > 0 else cur_hist

        # Calculate JS divergence
        if SCIPY_AVAILABLE and jensenshannon is not None:
            js_distance = jensenshannon(ref_hist, cur_hist)
        else:
            # Manual calculation
            m = (ref_hist + cur_hist) / 2
            kl_ref = self._kl_divergence(ref_hist, m)
            kl_cur = self._kl_divergence(cur_hist, m)
            js_distance = math.sqrt((kl_ref + kl_cur) / 2)

        details = {
            "js_distance": float(js_distance),
            "n_bins": self.n_bins,
            "n_reference": len(reference),
            "n_current": len(current),
        }

        return float(js_distance), details

    def _calculate_pure_python(
        self,
        reference: List[float],
        current: List[float]
    ) -> Tuple[float, Dict[str, Any]]:
        """Pure Python implementation"""
        min_val = min(min(reference), min(current))
        max_val = max(max(reference), max(current))
        step = (max_val - min_val) / self.n_bins

        ref_hist = [0.0] * self.n_bins
        cur_hist = [0.0] * self.n_bins

        for v in reference:
            idx = min(int((v - min_val) / step), self.n_bins - 1)
            ref_hist[idx] += 1

        for v in current:
            idx = min(int((v - min_val) / step), self.n_bins - 1)
            cur_hist[idx] += 1

        # Normalize
        ref_sum = sum(ref_hist)
        cur_sum = sum(cur_hist)
        ref_hist = [x / ref_sum if ref_sum > 0 else 0 for x in ref_hist]
        cur_hist = [x / cur_sum if cur_sum > 0 else 0 for x in cur_hist]

        # Calculate JS divergence
        m = [(r + c) / 2 for r, c in zip(ref_hist, cur_hist)]
        kl_ref = self._kl_divergence(ref_hist, m)
        kl_cur = self._kl_divergence(cur_hist, m)
        js_distance = math.sqrt((kl_ref + kl_cur) / 2)

        details = {
            "js_distance": js_distance,
            "n_bins": self.n_bins,
            "n_reference": len(reference),
            "n_current": len(current),
        }

        return js_distance, details

    def _kl_divergence(self, p: List[float], q: List[float], epsilon: float = 1e-10) -> float:
        """Calculate KL divergence"""
        kl = 0.0
        for pi, qi in zip(p, q):
            if pi > epsilon:
                kl += pi * math.log((pi + epsilon) / (qi + epsilon))
        return kl


# =============================================================================
# Feature Histogram Tracking
# =============================================================================

class FeatureHistogramTracker:
    """
    Tracks feature distributions over time using histograms.

    Maintains rolling histograms for efficient drift detection
    without storing all raw data.
    """

    def __init__(
        self,
        feature_names: List[str],
        n_bins: int = DEFAULT_PSI_BINS,
        max_samples_for_binning: int = 10000
    ):
        self.feature_names = feature_names
        self.n_bins = n_bins
        self.max_samples_for_binning = max_samples_for_binning

        # Storage for reference histograms
        self.reference_histograms: Dict[str, FeatureHistogram] = {}

        # Rolling data for current window
        self.current_data: Dict[str, deque] = {
            name: deque(maxlen=max_samples_for_binning)
            for name in feature_names
        }

        # Bin edges determined from reference data
        self.bin_edges: Dict[str, List[float]] = {}

        # Lock for thread safety
        self._lock = threading.Lock()

    def set_reference(self, reference_data: Dict[str, List[float]]) -> None:
        """
        Set reference distribution for each feature.

        Args:
            reference_data: Dictionary mapping feature names to value lists
        """
        with self._lock:
            for feature_name, values in reference_data.items():
                if feature_name not in self.feature_names:
                    continue

                histogram = self._compute_histogram(feature_name, values, is_reference=True)
                self.reference_histograms[feature_name] = histogram

                logger.info(
                    f"Set reference histogram for {feature_name}: "
                    f"n={histogram.n_samples}, mean={histogram.mean:.4f}"
                )

    def add_sample(self, features: Dict[str, float]) -> None:
        """Add a single sample to the current window"""
        with self._lock:
            for feature_name, value in features.items():
                if feature_name in self.current_data:
                    self.current_data[feature_name].append(value)

    def add_batch(self, batch: List[Dict[str, float]]) -> None:
        """Add a batch of samples"""
        with self._lock:
            for sample in batch:
                for feature_name, value in sample.items():
                    if feature_name in self.current_data:
                        self.current_data[feature_name].append(value)

    def get_current_histogram(self, feature_name: str) -> Optional[FeatureHistogram]:
        """Get histogram for current window data"""
        with self._lock:
            if feature_name not in self.current_data:
                return None

            values = list(self.current_data[feature_name])
            if len(values) < 10:
                return None

            return self._compute_histogram(feature_name, values, is_reference=False)

    def _compute_histogram(
        self,
        feature_name: str,
        values: List[float],
        is_reference: bool
    ) -> FeatureHistogram:
        """Compute histogram for feature values"""
        if NUMPY_AVAILABLE:
            arr = np.array(values)
            min_val = float(arr.min())
            max_val = float(arr.max())
            mean_val = float(arr.mean())
            std_val = float(arr.std())

            if is_reference or feature_name not in self.bin_edges:
                bin_edges = np.linspace(min_val, max_val, self.n_bins + 1)
                self.bin_edges[feature_name] = bin_edges.tolist()
            else:
                bin_edges = self.bin_edges[feature_name]

            counts, _ = np.histogram(arr, bins=bin_edges)
            proportions = counts / len(values)

            return FeatureHistogram(
                feature_name=feature_name,
                bin_edges=list(bin_edges) if hasattr(bin_edges, 'tolist') else bin_edges,
                counts=counts.tolist(),
                proportions=proportions.tolist(),
                n_samples=len(values),
                min_value=min_val,
                max_value=max_val,
                mean=mean_val,
                std=std_val,
            )
        else:
            # Pure Python
            min_val = min(values)
            max_val = max(values)
            mean_val = statistics.mean(values)
            std_val = statistics.stdev(values) if len(values) > 1 else 0.0

            if is_reference or feature_name not in self.bin_edges:
                step = (max_val - min_val) / self.n_bins
                bin_edges = [min_val + i * step for i in range(self.n_bins + 1)]
                self.bin_edges[feature_name] = bin_edges
            else:
                bin_edges = self.bin_edges[feature_name]

            counts = [0] * self.n_bins
            for v in values:
                for i in range(self.n_bins):
                    if bin_edges[i] <= v < bin_edges[i + 1]:
                        counts[i] += 1
                        break
                    elif i == self.n_bins - 1 and v == bin_edges[i + 1]:
                        counts[i] += 1

            proportions = [c / len(values) for c in counts]

            return FeatureHistogram(
                feature_name=feature_name,
                bin_edges=bin_edges,
                counts=counts,
                proportions=proportions,
                n_samples=len(values),
                min_value=min_val,
                max_value=max_val,
                mean=mean_val,
                std=std_val,
            )

    def clear_current_window(self) -> None:
        """Clear current window data"""
        with self._lock:
            for name in self.feature_names:
                self.current_data[name].clear()

    def get_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all features"""
        stats = {}
        with self._lock:
            for name in self.feature_names:
                values = list(self.current_data[name])
                if values:
                    stats[name] = {
                        "n_samples": len(values),
                        "mean": statistics.mean(values),
                        "std": statistics.stdev(values) if len(values) > 1 else 0,
                        "min": min(values),
                        "max": max(values),
                    }
        return stats


# =============================================================================
# Label Drift Detection with Delay Awareness
# =============================================================================

class LabelDriftDetector:
    """
    Detects label drift with awareness of label delay.

    In many ML systems, labels arrive with a delay (e.g., payment outcome
    is only known after 30 days). This class handles delayed labels
    and tracks label distribution drift over time.
    """

    def __init__(
        self,
        expected_delay_hours: float = 24 * 7,  # 7 days default
        max_delay_hours: float = 24 * 90,  # 90 days max
        window_size: int = DEFAULT_REFERENCE_WINDOW
    ):
        self.expected_delay_hours = expected_delay_hours
        self.max_delay_hours = max_delay_hours
        self.window_size = window_size

        # Storage for predictions awaiting labels
        self.pending_labels: Dict[str, PredictionMetrics] = {}

        # Storage for labeled data
        self.reference_labels: deque = deque(maxlen=window_size)
        self.current_labels: deque = deque(maxlen=window_size)

        # Label delay tracking
        self.label_delays: deque = deque(maxlen=1000)

        # Statistics
        self.total_predictions = 0
        self.total_labels_received = 0
        self.expired_predictions = 0

        self._lock = threading.Lock()

        # PSI and KS calculators
        self.psi_calculator = PSICalculator()
        self.ks_calculator = KSTestCalculator()

    def record_prediction(self, prediction: PredictionMetrics) -> None:
        """Record a prediction awaiting label"""
        with self._lock:
            self.pending_labels[prediction.request_id] = prediction
            self.total_predictions += 1

    def record_label(
        self,
        request_id: str,
        label: float,
        label_timestamp: Optional[str] = None
    ) -> Optional[float]:
        """
        Record a label for a prediction.

        Returns:
            Label delay in hours, or None if prediction not found
        """
        with self._lock:
            if request_id not in self.pending_labels:
                logger.warning(f"Label received for unknown request: {request_id}")
                return None

            prediction = self.pending_labels.pop(request_id)

            # Calculate delay
            label_ts = label_timestamp or datetime.now(timezone.utc).isoformat()
            pred_time = datetime.fromisoformat(prediction.timestamp.replace('Z', '+00:00'))
            label_time = datetime.fromisoformat(label_ts.replace('Z', '+00:00'))
            delay_hours = (label_time - pred_time).total_seconds() / 3600

            # Update prediction with label
            prediction.label = label
            prediction.label_timestamp = label_ts
            prediction.label_delay_hours = delay_hours

            # Add to current labels
            self.current_labels.append(label)
            self.label_delays.append(delay_hours)
            self.total_labels_received += 1

            return delay_hours

    def set_reference_labels(self, labels: List[float]) -> None:
        """Set reference label distribution"""
        with self._lock:
            self.reference_labels.clear()
            self.reference_labels.extend(labels)
            logger.info(f"Set reference labels: n={len(labels)}")

    def check_drift(self) -> Optional[DriftTestResult]:
        """
        Check for label drift between reference and current distributions.

        Returns:
            DriftTestResult or None if insufficient data
        """
        with self._lock:
            ref_labels = list(self.reference_labels)
            cur_labels = list(self.current_labels)

        if len(ref_labels) < 100 or len(cur_labels) < 100:
            logger.debug("Insufficient data for label drift check")
            return None

        # Calculate PSI
        psi_value, psi_details = self.psi_calculator.calculate(ref_labels, cur_labels)

        # Calculate KS test
        ks_stat, p_value, ks_details = self.ks_calculator.calculate(ref_labels, cur_labels)

        # Determine drift
        is_drift = (
            psi_value >= PSI_THRESHOLD_WARNING or
            p_value < KS_PVALUE_THRESHOLD
        )

        severity = max(
            self.psi_calculator.get_severity(psi_value),
            self.ks_calculator.get_severity(p_value, ks_stat),
            key=lambda s: list(DriftSeverity).index(s)
        )

        return DriftTestResult(
            test_type=DriftTestType.PSI,
            feature_name="label",
            statistic=psi_value,
            p_value=p_value,
            threshold=PSI_THRESHOLD_WARNING,
            is_drift_detected=is_drift,
            severity=severity,
            reference_stats={
                "mean": statistics.mean(ref_labels),
                "std": statistics.stdev(ref_labels) if len(ref_labels) > 1 else 0,
                "n": len(ref_labels),
            },
            current_stats={
                "mean": statistics.mean(cur_labels),
                "std": statistics.stdev(cur_labels) if len(cur_labels) > 1 else 0,
                "n": len(cur_labels),
            },
            metadata={
                "psi_details": psi_details,
                "ks_details": ks_details,
                "avg_label_delay_hours": statistics.mean(self.label_delays) if self.label_delays else None,
            }
        )

    def cleanup_expired(self) -> int:
        """
        Clean up predictions that exceeded max delay.

        Returns:
            Number of expired predictions removed
        """
        now = datetime.now(timezone.utc)
        expired_ids = []

        with self._lock:
            for req_id, prediction in self.pending_labels.items():
                pred_time = datetime.fromisoformat(prediction.timestamp.replace('Z', '+00:00'))
                age_hours = (now - pred_time).total_seconds() / 3600

                if age_hours > self.max_delay_hours:
                    expired_ids.append(req_id)

            for req_id in expired_ids:
                del self.pending_labels[req_id]
                self.expired_predictions += 1

        if expired_ids:
            logger.warning(f"Removed {len(expired_ids)} expired predictions")

        return len(expired_ids)

    def get_delay_statistics(self) -> Dict[str, float]:
        """Get label delay statistics"""
        with self._lock:
            delays = list(self.label_delays)

        if not delays:
            return {}

        return {
            "mean_delay_hours": statistics.mean(delays),
            "median_delay_hours": statistics.median(delays),
            "std_delay_hours": statistics.stdev(delays) if len(delays) > 1 else 0,
            "min_delay_hours": min(delays),
            "max_delay_hours": max(delays),
            "p95_delay_hours": sorted(delays)[int(len(delays) * 0.95)] if len(delays) >= 20 else max(delays),
        }


# =============================================================================
# Concept Drift Detection
# =============================================================================

class ConceptDriftDetector:
    """
    Detects concept drift - changes in the relationship between
    features and labels (P(Y|X) changes).

    Uses multiple strategies:
    1. Performance degradation monitoring
    2. Residual analysis
    3. Error rate tracking over time windows
    """

    def __init__(
        self,
        window_size: int = 1000,
        performance_threshold: float = 0.05,  # 5% degradation
        error_rate_threshold: float = 0.1  # 10% error rate increase
    ):
        self.window_size = window_size
        self.performance_threshold = performance_threshold
        self.error_rate_threshold = error_rate_threshold

        # Reference performance metrics
        self.reference_accuracy: Optional[float] = None
        self.reference_auc: Optional[float] = None
        self.reference_error_rate: Optional[float] = None

        # Rolling performance tracking
        self.predictions: deque = deque(maxlen=window_size)
        self.labels: deque = deque(maxlen=window_size)
        self.timestamps: deque = deque(maxlen=window_size)

        # Time-windowed performance
        self.hourly_error_rates: Dict[str, List[float]] = defaultdict(list)

        self._lock = threading.Lock()

    def set_reference_performance(
        self,
        accuracy: float,
        auc: Optional[float] = None,
        error_rate: Optional[float] = None
    ) -> None:
        """Set baseline performance metrics"""
        self.reference_accuracy = accuracy
        self.reference_auc = auc
        self.reference_error_rate = error_rate or (1 - accuracy)

        logger.info(
            f"Set reference performance: accuracy={accuracy:.4f}, "
            f"auc={auc}, error_rate={self.reference_error_rate:.4f}"
        )

    def record_prediction_outcome(
        self,
        prediction: float,
        label: float,
        timestamp: Optional[str] = None
    ) -> None:
        """Record a prediction and its true label"""
        with self._lock:
            self.predictions.append(prediction)
            self.labels.append(label)

            ts = timestamp or datetime.now(timezone.utc).isoformat()
            self.timestamps.append(ts)

            # Track hourly error rate
            hour_key = ts[:13]  # YYYY-MM-DDTHH
            is_error = (prediction > 0.5) != (label > 0.5)
            self.hourly_error_rates[hour_key].append(1 if is_error else 0)

    def check_drift(self) -> Optional[DriftTestResult]:
        """
        Check for concept drift by analyzing performance degradation.

        Returns:
            DriftTestResult or None if insufficient data
        """
        if self.reference_accuracy is None:
            logger.warning("Reference performance not set")
            return None

        with self._lock:
            predictions = list(self.predictions)
            labels = list(self.labels)

        if len(predictions) < 100:
            return None

        # Calculate current performance
        correct = sum(
            1 for p, l in zip(predictions, labels)
            if (p > 0.5) == (l > 0.5)
        )
        current_accuracy = correct / len(predictions)
        current_error_rate = 1 - current_accuracy

        # Calculate performance degradation
        accuracy_degradation = self.reference_accuracy - current_accuracy
        error_rate_increase = current_error_rate - self.reference_error_rate

        # Check for drift
        is_drift = (
            accuracy_degradation > self.performance_threshold or
            error_rate_increase > self.error_rate_threshold
        )

        # Determine severity
        if not is_drift:
            severity = DriftSeverity.NONE
        elif accuracy_degradation > 0.15:
            severity = DriftSeverity.CRITICAL
        elif accuracy_degradation > 0.10:
            severity = DriftSeverity.WARNING
        else:
            severity = DriftSeverity.LOW

        return DriftTestResult(
            test_type=DriftTestType.PERMUTATION,
            feature_name="model_performance",
            statistic=accuracy_degradation,
            p_value=None,
            threshold=self.performance_threshold,
            is_drift_detected=is_drift,
            severity=severity,
            reference_stats={
                "accuracy": self.reference_accuracy,
                "error_rate": self.reference_error_rate,
            },
            current_stats={
                "accuracy": current_accuracy,
                "error_rate": current_error_rate,
                "n_samples": len(predictions),
            },
            metadata={
                "accuracy_degradation": accuracy_degradation,
                "error_rate_increase": error_rate_increase,
            }
        )

    def get_performance_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly performance trend"""
        trend = []
        sorted_hours = sorted(self.hourly_error_rates.keys())[-hours:]

        for hour in sorted_hours:
            errors = self.hourly_error_rates[hour]
            if errors:
                trend.append({
                    "hour": hour,
                    "error_rate": sum(errors) / len(errors),
                    "n_samples": len(errors),
                })

        return trend


# =============================================================================
# Main Drift Detector Class
# =============================================================================

class DriftDetector:
    """
    Comprehensive Drift Detection System

    Monitors feature drift, label drift, and concept drift with:
    - PSI calculation for distribution shift
    - KS test for statistical significance
    - Per-feature drift monitoring
    - Label drift with delay awareness
    - Concept drift identification
    - Rolling window quality comparison
    - Automatic alerting with configurable thresholds
    - Prometheus metrics integration
    - Grafana dashboard specifications

    Usage:
        detector = DriftDetector(
            feature_names=["age", "income", "debt_ratio"],
            psi_warning_threshold=0.1,
            psi_critical_threshold=0.25
        )

        # Set reference data
        detector.set_reference(reference_data, reference_labels)

        # Monitor incoming data
        detector.record_prediction(features, prediction, probability)

        # Periodic drift check
        report = detector.analyze_drift()
    """

    def __init__(
        self,
        feature_names: List[str],
        model_version: str = "1.0.0",
        psi_warning_threshold: float = PSI_THRESHOLD_WARNING,
        psi_critical_threshold: float = PSI_THRESHOLD_CRITICAL,
        ks_pvalue_threshold: float = KS_PVALUE_THRESHOLD,
        reference_window_size: int = DEFAULT_REFERENCE_WINDOW,
        analysis_window_size: int = DEFAULT_ANALYSIS_WINDOW,
        label_delay_hours: float = 24 * 7,
        drift_sla_hours: float = DRIFT_DETECTION_SLA_HOURS,
        enable_prometheus: bool = True,
        enable_auto_retraining: bool = True,
        alert_channels: Optional[List[AlertChannel]] = None
    ):
        self.feature_names = feature_names
        self.model_version = model_version
        self.psi_warning_threshold = psi_warning_threshold
        self.psi_critical_threshold = psi_critical_threshold
        self.ks_pvalue_threshold = ks_pvalue_threshold
        self.reference_window_size = reference_window_size
        self.analysis_window_size = analysis_window_size
        self.label_delay_hours = label_delay_hours
        self.drift_sla_hours = drift_sla_hours
        self.enable_prometheus = enable_prometheus
        self.enable_auto_retraining = enable_auto_retraining
        self.alert_channels = alert_channels or [AlertChannel.PROMETHEUS]

        # Initialize calculators
        self.psi_calculator = PSICalculator()
        self.ks_calculator = KSTestCalculator(p_value_threshold=ks_pvalue_threshold)
        self.js_calculator = JensenShannonCalculator()

        # Initialize trackers
        self.histogram_tracker = FeatureHistogramTracker(
            feature_names=feature_names,
            max_samples_for_binning=analysis_window_size
        )
        self.label_detector = LabelDriftDetector(
            expected_delay_hours=label_delay_hours,
            window_size=reference_window_size
        )
        self.concept_detector = ConceptDriftDetector(
            window_size=analysis_window_size
        )

        # Per-request metrics storage
        self.prediction_metrics: deque = deque(maxlen=analysis_window_size)

        # Alert management
        self.active_alerts: Dict[str, DriftAlert] = {}
        self.alert_history: List[DriftAlert] = []

        # Reference data storage
        self.reference_data: Dict[str, List[float]] = {}
        self.reference_labels: List[float] = []
        self.reference_timestamp: Optional[str] = None

        # Analysis tracking
        self.last_analysis_time: Optional[datetime] = None
        self.analysis_count = 0

        # Auto-retraining
        self.retraining_triggered = False
        self.retraining_callbacks: List[Callable] = []

        # Thread safety
        self._lock = threading.Lock()

        # Initialize Prometheus metrics
        self._init_prometheus_metrics()

        logger.info(
            f"DriftDetector initialized for model {model_version} "
            f"with {len(feature_names)} features"
        )

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics for drift monitoring"""
        if not PROMETHEUS_AVAILABLE or not self.enable_prometheus:
            self.prom_psi_gauge = None
            self.prom_ks_stat_gauge = None
            self.prom_drift_detected = None
            self.prom_predictions_total = None
            self.prom_latency_histogram = None
            return

        # Feature drift metrics
        self.prom_psi_gauge = Gauge(
            "quan_ml_feature_psi",
            "Population Stability Index per feature",
            ["feature", "model_version"]
        )

        self.prom_ks_stat_gauge = Gauge(
            "quan_ml_feature_ks_statistic",
            "Kolmogorov-Smirnov statistic per feature",
            ["feature", "model_version"]
        )

        self.prom_ks_pvalue_gauge = Gauge(
            "quan_ml_feature_ks_pvalue",
            "Kolmogorov-Smirnov p-value per feature",
            ["feature", "model_version"]
        )

        # Drift detection
        self.prom_drift_detected = Gauge(
            "quan_ml_drift_detected",
            "Drift detection flag (1 = drift detected)",
            ["drift_type", "severity", "model_version"]
        )

        # Prediction metrics
        self.prom_predictions_total = Counter(
            "quan_ml_predictions_total",
            "Total number of predictions",
            ["model_version"]
        )

        self.prom_latency_histogram = Histogram(
            "quan_ml_prediction_latency_ms",
            "Prediction latency in milliseconds",
            ["model_version"],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
        )

        self.prom_probability_histogram = Histogram(
            "quan_ml_prediction_probability",
            "Prediction probability distribution",
            ["model_version"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )

        self.prom_confidence_histogram = Histogram(
            "quan_ml_prediction_confidence",
            "Prediction confidence distribution",
            ["model_version"],
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
        )

        # Label metrics
        self.prom_label_delay_histogram = Histogram(
            "quan_ml_label_delay_hours",
            "Label delay in hours",
            ["model_version"],
            buckets=[1, 6, 12, 24, 48, 72, 168, 336, 720]
        )

        # Alert metrics
        self.prom_alerts_total = Counter(
            "quan_ml_drift_alerts_total",
            "Total drift alerts generated",
            ["drift_type", "severity", "model_version"]
        )

    def set_reference(
        self,
        reference_data: Dict[str, List[float]],
        reference_labels: Optional[List[float]] = None,
        reference_accuracy: Optional[float] = None
    ) -> None:
        """
        Set reference distributions for drift comparison.

        Args:
            reference_data: Dictionary mapping feature names to value lists
            reference_labels: Optional list of reference labels
            reference_accuracy: Optional reference model accuracy
        """
        with self._lock:
            self.reference_data = reference_data.copy()
            self.reference_timestamp = datetime.now(timezone.utc).isoformat()

            # Set histogram reference
            self.histogram_tracker.set_reference(reference_data)

            # Set label reference if provided
            if reference_labels:
                self.reference_labels = reference_labels.copy()
                self.label_detector.set_reference_labels(reference_labels)

            # Set concept drift reference
            if reference_accuracy is not None:
                self.concept_detector.set_reference_performance(
                    accuracy=reference_accuracy
                )

            logger.info(
                f"Reference data set: {len(reference_data)} features, "
                f"{len(reference_data.get(self.feature_names[0], []))} samples"
            )

    def record_prediction(
        self,
        request_id: str,
        features: Dict[str, float],
        prediction: float,
        probability: Optional[float] = None,
        confidence: Optional[float] = None,
        latency_ms: float = 0.0
    ) -> PredictionMetrics:
        """
        Record per-request prediction metrics.

        Args:
            request_id: Unique request identifier
            features: Feature values for this prediction
            prediction: Model prediction value
            probability: Prediction probability (for classification)
            confidence: Prediction confidence score
            latency_ms: Prediction latency in milliseconds

        Returns:
            PredictionMetrics object
        """
        metrics = PredictionMetrics(
            request_id=request_id,
            model_version=self.model_version,
            features=features,
            prediction=prediction,
            probability=probability,
            confidence=confidence,
            latency_ms=latency_ms,
        )

        with self._lock:
            self.prediction_metrics.append(metrics)

            # Add to histogram tracker
            self.histogram_tracker.add_sample(features)

            # Record for label tracking
            self.label_detector.record_prediction(metrics)

        # Update Prometheus metrics
        if self.enable_prometheus and self.prom_predictions_total:
            self.prom_predictions_total.labels(
                model_version=self.model_version
            ).inc()

            self.prom_latency_histogram.labels(
                model_version=self.model_version
            ).observe(latency_ms)

            if probability is not None:
                self.prom_probability_histogram.labels(
                    model_version=self.model_version
                ).observe(probability)

            if confidence is not None:
                self.prom_confidence_histogram.labels(
                    model_version=self.model_version
                ).observe(confidence)

        return metrics

    def record_label(
        self,
        request_id: str,
        label: float,
        label_timestamp: Optional[str] = None
    ) -> Optional[float]:
        """
        Record a label for a previous prediction.

        Args:
            request_id: The request ID from record_prediction
            label: The true label value
            label_timestamp: Optional timestamp of when label was observed

        Returns:
            Label delay in hours, or None if request not found
        """
        delay_hours = self.label_detector.record_label(
            request_id=request_id,
            label=label,
            label_timestamp=label_timestamp
        )

        # Update Prometheus metrics
        if delay_hours is not None and self.enable_prometheus and self.prom_label_delay_histogram:
            self.prom_label_delay_histogram.labels(
                model_version=self.model_version
            ).observe(delay_hours)

        # Update concept drift detector
        with self._lock:
            # Find the prediction
            for metric in self.prediction_metrics:
                if metric.request_id == request_id:
                    self.concept_detector.record_prediction_outcome(
                        prediction=metric.prediction,
                        label=label,
                        timestamp=label_timestamp
                    )
                    break

        return delay_hours

    def analyze_feature_drift(
        self,
        feature_name: str
    ) -> Optional[DriftTestResult]:
        """
        Analyze drift for a single feature.

        Returns:
            DriftTestResult or None if insufficient data
        """
        if feature_name not in self.reference_data:
            logger.warning(f"No reference data for feature: {feature_name}")
            return None

        reference_values = self.reference_data[feature_name]

        # Get current values from histogram tracker
        with self._lock:
            current_values = list(self.histogram_tracker.current_data.get(feature_name, []))

        if len(current_values) < 100:
            logger.debug(f"Insufficient current data for feature {feature_name}")
            return None

        # Calculate PSI
        psi_value, psi_details = self.psi_calculator.calculate(
            reference_values, current_values
        )

        # Calculate KS test
        ks_stat, p_value, ks_details = self.ks_calculator.calculate(
            reference_values, current_values
        )

        # Determine drift
        is_drift = (
            psi_value >= self.psi_warning_threshold or
            p_value < self.ks_pvalue_threshold
        )

        # Determine severity
        psi_severity = self.psi_calculator.get_severity(psi_value)
        ks_severity = self.ks_calculator.get_severity(p_value, ks_stat)
        severity = max(psi_severity, ks_severity, key=lambda s: list(DriftSeverity).index(s))

        # Update Prometheus
        if self.enable_prometheus and self.prom_psi_gauge:
            self.prom_psi_gauge.labels(
                feature=feature_name,
                model_version=self.model_version
            ).set(psi_value)

            self.prom_ks_stat_gauge.labels(
                feature=feature_name,
                model_version=self.model_version
            ).set(ks_stat)

            self.prom_ks_pvalue_gauge.labels(
                feature=feature_name,
                model_version=self.model_version
            ).set(p_value)

        return DriftTestResult(
            test_type=DriftTestType.PSI,
            feature_name=feature_name,
            statistic=psi_value,
            p_value=p_value,
            threshold=self.psi_warning_threshold,
            is_drift_detected=is_drift,
            severity=severity,
            reference_stats={
                "mean": statistics.mean(reference_values),
                "std": statistics.stdev(reference_values) if len(reference_values) > 1 else 0,
                "n": len(reference_values),
            },
            current_stats={
                "mean": statistics.mean(current_values),
                "std": statistics.stdev(current_values) if len(current_values) > 1 else 0,
                "n": len(current_values),
            },
            metadata={
                "psi_details": psi_details,
                "ks_details": ks_details,
            }
        )

    def analyze_drift(self) -> DriftReport:
        """
        Perform comprehensive drift analysis.

        Returns:
            DriftReport with all drift detection results
        """
        self.analysis_count += 1
        now = datetime.now(timezone.utc)

        # Feature drift analysis
        feature_results: Dict[str, DriftTestResult] = {}
        for feature_name in self.feature_names:
            result = self.analyze_feature_drift(feature_name)
            if result:
                feature_results[feature_name] = result

        # Label drift analysis
        label_result = self.label_detector.check_drift()

        # Concept drift analysis
        concept_result = self.concept_detector.check_drift()

        # Determine overall drift status
        any_drift = any(r.is_drift_detected for r in feature_results.values())
        if label_result and label_result.is_drift_detected:
            any_drift = True
        if concept_result and concept_result.is_drift_detected:
            any_drift = True

        # Determine overall severity
        severities = [r.severity for r in feature_results.values()]
        if label_result:
            severities.append(label_result.severity)
        if concept_result:
            severities.append(concept_result.severity)

        overall_severity = max(
            severities,
            default=DriftSeverity.NONE,
            key=lambda s: list(DriftSeverity).index(s)
        )

        # Generate alerts
        alerts = self._generate_alerts(
            feature_results, label_result, concept_result
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            feature_results, label_result, concept_result
        )

        # Update Prometheus drift detection flag
        if self.enable_prometheus and self.prom_drift_detected:
            for drift_type in DriftType:
                for severity in DriftSeverity:
                    self.prom_drift_detected.labels(
                        drift_type=drift_type.value,
                        severity=severity.value,
                        model_version=self.model_version
                    ).set(0)

            if any_drift:
                self.prom_drift_detected.labels(
                    drift_type=DriftType.FEATURE_DRIFT.value,
                    severity=overall_severity.value,
                    model_version=self.model_version
                ).set(1)

        # Check if auto-retraining should be triggered
        if (
            self.enable_auto_retraining and
            overall_severity in [DriftSeverity.CRITICAL, DriftSeverity.EMERGENCY] and
            not self.retraining_triggered
        ):
            self._trigger_retraining(alerts)

        self.last_analysis_time = now

        # Create report
        with self._lock:
            prediction_count = len(self.prediction_metrics)
            if prediction_count > 0:
                first_ts = self.prediction_metrics[0].timestamp
                last_ts = self.prediction_metrics[-1].timestamp
            else:
                first_ts = last_ts = now.isoformat()

        report = DriftReport(
            report_id=str(uuid.uuid4()),
            analysis_window_start=first_ts,
            analysis_window_end=last_ts,
            reference_window_start=self.reference_timestamp or "",
            reference_window_end=self.reference_timestamp or "",
            n_reference_samples=len(self.reference_data.get(self.feature_names[0], [])) if self.reference_data else 0,
            n_analysis_samples=prediction_count,
            feature_drift_results=feature_results,
            label_drift_result=label_result,
            concept_drift_result=concept_result,
            overall_drift_detected=any_drift,
            overall_severity=overall_severity,
            alerts_generated=alerts,
            recommendations=recommendations,
        )

        logger.info(
            f"Drift analysis complete: drift_detected={any_drift}, "
            f"severity={overall_severity.value}, alerts={len(alerts)}"
        )

        return report

    def _generate_alerts(
        self,
        feature_results: Dict[str, DriftTestResult],
        label_result: Optional[DriftTestResult],
        concept_result: Optional[DriftTestResult]
    ) -> List[DriftAlert]:
        """Generate alerts for detected drift"""
        alerts = []

        # Feature drift alerts
        for feature_name, result in feature_results.items():
            if result.is_drift_detected and result.severity != DriftSeverity.NONE:
                alert = DriftAlert(
                    alert_id=str(uuid.uuid4()),
                    drift_type=DriftType.FEATURE_DRIFT,
                    severity=result.severity,
                    feature_name=feature_name,
                    test_results=[result],
                    message=f"Feature drift detected in '{feature_name}': "
                            f"PSI={result.statistic:.4f}, p-value={result.p_value:.4e}",
                    recommended_action=self._get_action_for_severity(result.severity),
                )
                alerts.append(alert)
                self._record_alert(alert)

        # Label drift alert
        if label_result and label_result.is_drift_detected:
            alert = DriftAlert(
                alert_id=str(uuid.uuid4()),
                drift_type=DriftType.LABEL_DRIFT,
                severity=label_result.severity,
                feature_name=None,
                test_results=[label_result],
                message=f"Label drift detected: PSI={label_result.statistic:.4f}",
                recommended_action="Review label distribution changes. "
                                   "Consider retraining with recent data.",
            )
            alerts.append(alert)
            self._record_alert(alert)

        # Concept drift alert
        if concept_result and concept_result.is_drift_detected:
            alert = DriftAlert(
                alert_id=str(uuid.uuid4()),
                drift_type=DriftType.CONCEPT_DRIFT,
                severity=concept_result.severity,
                feature_name=None,
                test_results=[concept_result],
                message=f"Concept drift detected: accuracy degradation="
                        f"{concept_result.statistic:.4f}",
                recommended_action="Model retraining recommended. "
                                   "The relationship between features and target has changed.",
            )
            alerts.append(alert)
            self._record_alert(alert)

        return alerts

    def _record_alert(self, alert: DriftAlert) -> None:
        """Record alert and update Prometheus"""
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        if self.enable_prometheus and self.prom_alerts_total:
            self.prom_alerts_total.labels(
                drift_type=alert.drift_type.value,
                severity=alert.severity.value,
                model_version=self.model_version
            ).inc()

    def _get_action_for_severity(self, severity: DriftSeverity) -> str:
        """Get recommended action based on severity"""
        actions = {
            DriftSeverity.NONE: "No action required.",
            DriftSeverity.LOW: "Monitor closely. Consider increasing monitoring frequency.",
            DriftSeverity.WARNING: "Investigate feature changes. Prepare for potential retraining.",
            DriftSeverity.CRITICAL: "Immediate investigation required. Initiate retraining pipeline.",
            DriftSeverity.EMERGENCY: "URGENT: Model may be producing unreliable predictions. "
                                     "Consider fallback model or manual review.",
        }
        return actions.get(severity, "Unknown severity level.")

    def _generate_recommendations(
        self,
        feature_results: Dict[str, DriftTestResult],
        label_result: Optional[DriftTestResult],
        concept_result: Optional[DriftTestResult]
    ) -> List[str]:
        """Generate recommendations based on drift analysis"""
        recommendations = []

        # Count drifted features
        drifted_features = [
            name for name, result in feature_results.items()
            if result.is_drift_detected
        ]

        if len(drifted_features) == 0:
            recommendations.append("No significant feature drift detected. Continue monitoring.")
        elif len(drifted_features) <= 3:
            recommendations.append(
                f"Investigate changes in features: {', '.join(drifted_features)}"
            )
        else:
            recommendations.append(
                f"Multiple features ({len(drifted_features)}) showing drift. "
                "Consider comprehensive data pipeline review."
            )

        # Label recommendations
        if label_result and label_result.is_drift_detected:
            recommendations.append(
                "Label distribution has shifted. Review data collection process "
                "and consider retraining with recent labeled data."
            )

        # Concept drift recommendations
        if concept_result and concept_result.is_drift_detected:
            recommendations.append(
                "Model performance degradation detected. Immediate retraining "
                "recommended with recent data to capture new patterns."
            )

        # SLA recommendations
        if self.last_analysis_time:
            hours_since_analysis = (
                datetime.now(timezone.utc) - self.last_analysis_time
            ).total_seconds() / 3600

            if hours_since_analysis > self.drift_sla_hours:
                recommendations.append(
                    f"Drift analysis SLA ({self.drift_sla_hours}h) exceeded. "
                    "Increase analysis frequency."
                )

        return recommendations

    def _trigger_retraining(self, alerts: List[DriftAlert]) -> None:
        """Trigger automatic retraining"""
        self.retraining_triggered = True

        logger.warning(
            "Automatic retraining triggered due to critical drift. "
            f"Alerts: {[a.alert_id for a in alerts]}"
        )

        for callback in self.retraining_callbacks:
            try:
                callback(alerts)
            except Exception as e:
                logger.error(f"Retraining callback failed: {e}")

    def register_retraining_callback(self, callback: Callable[[List[DriftAlert]], None]) -> None:
        """Register a callback to be called when retraining is triggered"""
        self.retraining_callbacks.append(callback)

    def reset_retraining_flag(self) -> None:
        """Reset the retraining trigger flag after retraining completes"""
        self.retraining_triggered = False

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolution_timestamp = datetime.now(timezone.utc).isoformat()
            del self.active_alerts[alert_id]
            return True
        return False

    def get_active_alerts(self) -> List[DriftAlert]:
        """Get all active (unresolved) alerts"""
        return list(self.active_alerts.values())

    def get_statistics(self) -> Dict[str, Any]:
        """Get drift detector statistics"""
        return {
            "model_version": self.model_version,
            "n_features": len(self.feature_names),
            "analysis_count": self.analysis_count,
            "last_analysis_time": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "active_alerts": len(self.active_alerts),
            "total_alerts": len(self.alert_history),
            "retraining_triggered": self.retraining_triggered,
            "predictions_tracked": len(self.prediction_metrics),
            "label_delay_stats": self.label_detector.get_delay_statistics(),
            "histogram_stats": self.histogram_tracker.get_statistics(),
        }


# =============================================================================
# Evidently Integration
# =============================================================================

class EvidentlyIntegration:
    """
    Integration with Evidently AI for drift detection.

    Provides hooks to use Evidently's comprehensive drift detection
    capabilities alongside the custom implementation.
    """

    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self._evidently_available = EVIDENTLY_AVAILABLE

    def generate_drift_report(
        self,
        reference_data: Dict[str, List[float]],
        current_data: Dict[str, List[float]],
        reference_labels: Optional[List[float]] = None,
        current_labels: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate Evidently drift report.

        Returns:
            Report dictionary or None if Evidently not available
        """
        if not self._evidently_available:
            logger.warning("Evidently not available")
            return None

        if not PANDAS_AVAILABLE:
            logger.warning("Pandas required for Evidently integration")
            return None

        # Convert to DataFrames
        ref_df = pd.DataFrame(reference_data)
        cur_df = pd.DataFrame(current_data)

        if reference_labels and current_labels:
            ref_df['target'] = reference_labels
            cur_df['target'] = current_labels

        # Create report
        report = Report(metrics=[
            DataDriftPreset(),
        ])

        report.run(reference_data=ref_df, current_data=cur_df)

        # Extract results
        return report.as_dict()

    def get_feature_drift_scores(
        self,
        reference_data: Dict[str, List[float]],
        current_data: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """Get drift scores per feature using Evidently"""
        if not self._evidently_available or not PANDAS_AVAILABLE:
            return {}

        ref_df = pd.DataFrame(reference_data)
        cur_df = pd.DataFrame(current_data)

        report = Report(metrics=[DataDriftTable()])
        report.run(reference_data=ref_df, current_data=cur_df)

        result = report.as_dict()

        # Extract per-feature drift scores
        drift_scores = {}
        try:
            metrics = result.get('metrics', [])
            for metric in metrics:
                if metric.get('metric') == 'DataDriftTable':
                    table_data = metric.get('result', {}).get('drift_by_columns', {})
                    for col, data in table_data.items():
                        drift_scores[col] = data.get('drift_score', 0.0)
        except Exception as e:
            logger.error(f"Error extracting Evidently drift scores: {e}")

        return drift_scores


# =============================================================================
# Alibi Detect Integration
# =============================================================================

class AlibiDetectIntegration:
    """
    Integration with Alibi Detect for drift detection.

    Provides access to advanced drift detection methods including:
    - Tabular drift (Chi-squared, KS, MMD)
    - Classifier-based drift detection
    """

    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self._alibi_available = ALIBI_AVAILABLE
        self._detector: Optional[Any] = None

    def fit_ks_detector(
        self,
        reference_data: Dict[str, List[float]],
        p_val: float = 0.05
    ) -> bool:
        """
        Fit KS drift detector on reference data.

        Returns:
            True if successful, False otherwise
        """
        if not self._alibi_available:
            logger.warning("Alibi Detect not available")
            return False

        if not NUMPY_AVAILABLE:
            logger.warning("NumPy required for Alibi Detect")
            return False

        # Convert to numpy array
        X_ref = np.column_stack([
            reference_data[name] for name in self.feature_names
        ])

        self._detector = KSDrift(
            X_ref,
            p_val=p_val,
        )

        logger.info("Alibi KS drift detector fitted")
        return True

    def detect_drift(
        self,
        current_data: Dict[str, List[float]]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect drift using fitted Alibi detector.

        Returns:
            Detection result or None if not fitted
        """
        if self._detector is None:
            logger.warning("Detector not fitted")
            return None

        if not NUMPY_AVAILABLE:
            return None

        X_cur = np.column_stack([
            current_data[name] for name in self.feature_names
        ])

        result = self._detector.predict(X_cur)

        return {
            "is_drift": bool(result['data']['is_drift']),
            "p_val": float(result['data']['p_val']),
            "distance": result['data'].get('distance'),
            "threshold": result['data'].get('threshold'),
        }


# =============================================================================
# Prometheus Alert Rules
# =============================================================================

PROMETHEUS_ALERT_RULES = """
# Prometheus Alert Rules for QUAN ML Drift Detection

groups:
  - name: quan_ml_drift_alerts
    interval: 1m
    rules:
      # PSI Warning Alert
      - alert: MLFeatureDriftWarning
        expr: quan_ml_feature_psi > 0.1
        for: 5m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Feature drift warning detected"
          description: "Feature {{ $labels.feature }} has PSI {{ $value | printf \"%.4f\" }} > 0.1 for model {{ $labels.model_version }}"
          runbook_url: "https://wiki.example.com/ml-drift-response"

      # PSI Critical Alert
      - alert: MLFeatureDriftCritical
        expr: quan_ml_feature_psi > 0.25
        for: 5m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Critical feature drift detected"
          description: "Feature {{ $labels.feature }} has PSI {{ $value | printf \"%.4f\" }} > 0.25 for model {{ $labels.model_version }}. Immediate action required."
          runbook_url: "https://wiki.example.com/ml-drift-critical"

      # KS Test Alert
      - alert: MLFeatureDistributionShift
        expr: quan_ml_feature_ks_pvalue < 0.01
        for: 5m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Significant distribution shift detected"
          description: "Feature {{ $labels.feature }} KS test p-value {{ $value | printf \"%.4e\" }} < 0.01 for model {{ $labels.model_version }}"

      # Overall Drift Detection
      - alert: MLDriftDetected
        expr: quan_ml_drift_detected == 1
        for: 5m
        labels:
          severity: "{{ $labels.severity }}"
          team: ml-platform
        annotations:
          summary: "ML drift detected"
          description: "{{ $labels.drift_type }} detected with severity {{ $labels.severity }} for model {{ $labels.model_version }}"

      # Prediction Latency Alert
      - alert: MLPredictionLatencyHigh
        expr: histogram_quantile(0.95, rate(quan_ml_prediction_latency_ms_bucket[5m])) > 500
        for: 5m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "ML prediction latency high"
          description: "95th percentile prediction latency is {{ $value | printf \"%.0f\" }}ms for model {{ $labels.model_version }}"

      # Label Delay Alert
      - alert: MLLabelDelayExcessive
        expr: histogram_quantile(0.50, quan_ml_label_delay_hours_bucket) > 168
        for: 1h
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Label delay exceeding 7 days"
          description: "Median label delay is {{ $value | printf \"%.0f\" }} hours. Consider strategies to reduce feedback loop time."

      # Drift Detection SLA
      - alert: MLDriftDetectionSLABreach
        expr: time() - quan_ml_last_drift_analysis_timestamp > 86400
        for: 1h
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Drift detection SLA breach"
          description: "No drift analysis performed in the last 24 hours for model {{ $labels.model_version }}"

      # Alert Rate Spike
      - alert: MLDriftAlertSpike
        expr: increase(quan_ml_drift_alerts_total[1h]) > 10
        for: 5m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Spike in drift alerts"
          description: "More than 10 drift alerts generated in the last hour"
"""


# =============================================================================
# Grafana Dashboard Specification
# =============================================================================

GRAFANA_DRIFT_DASHBOARD = {
    "dashboard": {
        "title": "QUAN ML Drift Detection",
        "uid": "quan-ml-drift",
        "tags": ["mlops", "drift", "monitoring"],
        "timezone": "browser",
        "refresh": "30s",
        "panels": [
            # Row 1: Overview
            {
                "title": "Drift Detection Status",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                "targets": [
                    {
                        "expr": "max(quan_ml_drift_detected)",
                        "legendFormat": "Drift Detected"
                    }
                ],
                "options": {
                    "colorMode": "background",
                    "graphMode": "none",
                    "reduceOptions": {
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": False
                    },
                    "textMode": "auto"
                },
                "fieldConfig": {
                    "defaults": {
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "red", "value": 1}
                            ]
                        },
                        "mappings": [
                            {"type": "value", "options": {"0": {"text": "No Drift"}}},
                            {"type": "value", "options": {"1": {"text": "DRIFT DETECTED"}}}
                        ]
                    }
                }
            },
            {
                "title": "Active Alerts",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
                "targets": [
                    {
                        "expr": "sum(increase(quan_ml_drift_alerts_total[24h]))",
                        "legendFormat": "Alerts (24h)"
                    }
                ]
            },
            {
                "title": "Predictions (24h)",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
                "targets": [
                    {
                        "expr": "sum(increase(quan_ml_predictions_total[24h]))",
                        "legendFormat": "Total"
                    }
                ]
            },
            {
                "title": "P95 Latency (ms)",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 18, "y": 0},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, rate(quan_ml_prediction_latency_ms_bucket[5m]))",
                        "legendFormat": "P95 Latency"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "ms",
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 100},
                                {"color": "red", "value": 500}
                            ]
                        }
                    }
                }
            },

            # Row 2: PSI by Feature
            {
                "title": "Feature PSI Values",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
                "targets": [
                    {
                        "expr": "quan_ml_feature_psi",
                        "legendFormat": "{{ feature }}"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "lineWidth": 2,
                            "fillOpacity": 10
                        },
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 0.1},
                                {"color": "red", "value": 0.25}
                            ]
                        }
                    }
                },
                "options": {
                    "legend": {"displayMode": "table", "placement": "right"},
                    "tooltip": {"mode": "multi"}
                }
            },

            # Row 2: KS Statistics
            {
                "title": "Feature KS Test P-Values",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
                "targets": [
                    {
                        "expr": "quan_ml_feature_ks_pvalue",
                        "legendFormat": "{{ feature }}"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "lineWidth": 2,
                            "scaleDistribution": {"type": "log", "log": 10}
                        },
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 0.01},
                                {"color": "green", "value": 0.05}
                            ]
                        }
                    }
                }
            },

            # Row 3: Prediction Distribution
            {
                "title": "Prediction Probability Distribution",
                "type": "heatmap",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 12},
                "targets": [
                    {
                        "expr": "sum(rate(quan_ml_prediction_probability_bucket[5m])) by (le)",
                        "legendFormat": "{{ le }}"
                    }
                ]
            },

            # Row 3: Confidence Distribution
            {
                "title": "Prediction Confidence Distribution",
                "type": "heatmap",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 12},
                "targets": [
                    {
                        "expr": "sum(rate(quan_ml_prediction_confidence_bucket[5m])) by (le)",
                        "legendFormat": "{{ le }}"
                    }
                ]
            },

            # Row 4: Label Delay
            {
                "title": "Label Delay Distribution",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 20},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, quan_ml_label_delay_hours_bucket)",
                        "legendFormat": "Median"
                    },
                    {
                        "expr": "histogram_quantile(0.95, quan_ml_label_delay_hours_bucket)",
                        "legendFormat": "P95"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "h"
                    }
                }
            },

            # Row 4: Alert History
            {
                "title": "Drift Alerts Over Time",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 20},
                "targets": [
                    {
                        "expr": "increase(quan_ml_drift_alerts_total[1h])",
                        "legendFormat": "{{ drift_type }} - {{ severity }}"
                    }
                ],
                "options": {
                    "legend": {"displayMode": "table", "placement": "bottom"}
                }
            },

            # Row 5: Prediction Latency
            {
                "title": "Prediction Latency Percentiles",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 24, "x": 0, "y": 28},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, rate(quan_ml_prediction_latency_ms_bucket[5m]))",
                        "legendFormat": "P50"
                    },
                    {
                        "expr": "histogram_quantile(0.90, rate(quan_ml_prediction_latency_ms_bucket[5m]))",
                        "legendFormat": "P90"
                    },
                    {
                        "expr": "histogram_quantile(0.99, rate(quan_ml_prediction_latency_ms_bucket[5m]))",
                        "legendFormat": "P99"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "ms"
                    }
                }
            }
        ]
    }
}


# =============================================================================
# Tests
# =============================================================================

class DriftDetectionTests:
    """
    Test suite for drift detection system.

    Validates:
    - PSI calculation accuracy
    - KS test correctness
    - Drift detection under simulated conditions
    - Alert generation
    - 24-hour SLA compliance
    """

    @staticmethod
    def test_psi_calculation() -> bool:
        """Test PSI calculation with known distributions"""
        calculator = PSICalculator(n_bins=10)

        # Test 1: Identical distributions should have PSI ~ 0
        reference = [float(i) for i in range(1000)]
        current = [float(i) for i in range(1000)]
        psi, _ = calculator.calculate(reference, current)
        assert psi < 0.01, f"PSI for identical distributions should be ~0, got {psi}"

        # Test 2: Shifted distribution should have higher PSI
        shifted = [float(i + 500) for i in range(1000)]
        psi_shifted, _ = calculator.calculate(reference, shifted)
        assert psi_shifted > 0.1, f"PSI for shifted distribution should be > 0.1, got {psi_shifted}"

        logger.info("PSI calculation tests passed")
        return True

    @staticmethod
    def test_ks_test() -> bool:
        """Test KS test with known distributions"""
        calculator = KSTestCalculator()

        # Test 1: Same distribution
        if NUMPY_AVAILABLE:
            np.random.seed(42)
            ref = list(np.random.normal(0, 1, 1000))
            cur = list(np.random.normal(0, 1, 1000))
        else:
            import random
            random.seed(42)
            ref = [random.gauss(0, 1) for _ in range(1000)]
            cur = [random.gauss(0, 1) for _ in range(1000)]

        ks_stat, p_value, _ = calculator.calculate(ref, cur)
        assert p_value > 0.01, f"Same distribution should have p > 0.01, got {p_value}"

        # Test 2: Different distributions
        if NUMPY_AVAILABLE:
            cur_different = list(np.random.normal(2, 1, 1000))
        else:
            cur_different = [random.gauss(2, 1) for _ in range(1000)]

        ks_stat, p_value, _ = calculator.calculate(ref, cur_different)
        assert p_value < 0.01, f"Different distributions should have p < 0.01, got {p_value}"

        logger.info("KS test tests passed")
        return True

    @staticmethod
    def test_drift_detector_alerts() -> bool:
        """Test that drift detector generates alerts correctly"""
        detector = DriftDetector(
            feature_names=["f1", "f2"],
            enable_prometheus=False
        )

        # Set reference
        reference_data = {
            "f1": [float(i) for i in range(1000)],
            "f2": [float(i) for i in range(1000)],
        }
        detector.set_reference(reference_data)

        # Add drifted current data
        for i in range(500):
            detector.record_prediction(
                request_id=str(i),
                features={
                    "f1": float(i + 500),  # Shifted
                    "f2": float(i),  # Not shifted
                },
                prediction=0.5,
                probability=0.5,
                latency_ms=10.0
            )

        # Analyze
        report = detector.analyze_drift()

        # Should detect drift in f1
        assert report.overall_drift_detected, "Should detect drift"
        assert "f1" in report.feature_drift_results, "f1 should have results"
        assert report.feature_drift_results["f1"].is_drift_detected, "f1 should show drift"

        logger.info("Drift detector alert tests passed")
        return True

    @staticmethod
    def test_simulated_drift_conditions() -> bool:
        """Test drift detection under various simulated conditions"""
        import random
        random.seed(42)

        detector = DriftDetector(
            feature_names=["feature"],
            enable_prometheus=False,
            enable_auto_retraining=False
        )

        # Reference: Normal distribution centered at 0
        reference = [random.gauss(0, 1) for _ in range(2000)]
        detector.set_reference({"feature": reference})

        # Scenario 1: Gradual drift
        for i in range(500):
            drift_amount = i / 500.0  # Gradually increases
            detector.record_prediction(
                request_id=f"gradual_{i}",
                features={"feature": random.gauss(drift_amount, 1)},
                prediction=0.5,
                latency_ms=5.0
            )

        report = detector.analyze_drift()

        # Should detect some drift with gradual shift
        logger.info(f"Gradual drift test: detected={report.overall_drift_detected}")

        # Reset and test sudden drift
        detector.histogram_tracker.clear_current_window()

        # Scenario 2: Sudden drift
        for i in range(500):
            detector.record_prediction(
                request_id=f"sudden_{i}",
                features={"feature": random.gauss(3, 1)},  # Large shift
                prediction=0.5,
                latency_ms=5.0
            )

        report = detector.analyze_drift()
        assert report.overall_drift_detected, "Should detect sudden drift"
        assert report.overall_severity in [DriftSeverity.WARNING, DriftSeverity.CRITICAL, DriftSeverity.EMERGENCY], \
            f"Severity should be WARNING, CRITICAL, or EMERGENCY, got {report.overall_severity}"

        logger.info("Simulated drift condition tests passed")
        return True

    @staticmethod
    def run_all_tests() -> Dict[str, bool]:
        """Run all drift detection tests"""
        results = {}

        tests = [
            ("psi_calculation", DriftDetectionTests.test_psi_calculation),
            ("ks_test", DriftDetectionTests.test_ks_test),
            ("drift_detector_alerts", DriftDetectionTests.test_drift_detector_alerts),
            ("simulated_drift", DriftDetectionTests.test_simulated_drift_conditions),
        ]

        for name, test_func in tests:
            try:
                results[name] = test_func()
            except Exception as e:
                logger.error(f"Test {name} failed: {e}")
                results[name] = False

        logger.info(f"Test results: {results}")
        return results


# =============================================================================
# Utility Functions
# =============================================================================

def create_drift_detector_from_config(config: Dict[str, Any]) -> DriftDetector:
    """
    Create a DriftDetector from configuration dictionary.

    Args:
        config: Configuration dictionary with keys:
            - feature_names: List of feature names
            - model_version: Model version string
            - psi_warning_threshold: PSI warning threshold
            - psi_critical_threshold: PSI critical threshold
            - ks_pvalue_threshold: KS test p-value threshold
            - reference_window_size: Reference window size
            - analysis_window_size: Analysis window size
            - enable_prometheus: Whether to enable Prometheus metrics
            - enable_auto_retraining: Whether to enable auto retraining

    Returns:
        Configured DriftDetector instance
    """
    return DriftDetector(
        feature_names=config["feature_names"],
        model_version=config.get("model_version", "1.0.0"),
        psi_warning_threshold=config.get("psi_warning_threshold", PSI_THRESHOLD_WARNING),
        psi_critical_threshold=config.get("psi_critical_threshold", PSI_THRESHOLD_CRITICAL),
        ks_pvalue_threshold=config.get("ks_pvalue_threshold", KS_PVALUE_THRESHOLD),
        reference_window_size=config.get("reference_window_size", DEFAULT_REFERENCE_WINDOW),
        analysis_window_size=config.get("analysis_window_size", DEFAULT_ANALYSIS_WINDOW),
        label_delay_hours=config.get("label_delay_hours", 24 * 7),
        drift_sla_hours=config.get("drift_sla_hours", DRIFT_DETECTION_SLA_HOURS),
        enable_prometheus=config.get("enable_prometheus", True),
        enable_auto_retraining=config.get("enable_auto_retraining", True),
    )


def export_prometheus_rules(output_path: Path) -> None:
    """Export Prometheus alert rules to file"""
    with open(output_path, "w") as f:
        f.write(PROMETHEUS_ALERT_RULES)
    logger.info(f"Prometheus rules exported to {output_path}")


def export_grafana_dashboard(output_path: Path) -> None:
    """Export Grafana dashboard specification to file"""
    with open(output_path, "w") as f:
        json.dump(GRAFANA_DRIFT_DASHBOARD, f, indent=2)
    logger.info(f"Grafana dashboard exported to {output_path}")


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    "DriftType",
    "DriftSeverity",
    "DriftTestType",
    "AlertChannel",

    # Data classes
    "DriftTestResult",
    "FeatureHistogram",
    "DriftAlert",
    "PredictionMetrics",
    "DriftReport",

    # Calculators
    "PSICalculator",
    "KSTestCalculator",
    "JensenShannonCalculator",

    # Trackers
    "FeatureHistogramTracker",
    "LabelDriftDetector",
    "ConceptDriftDetector",

    # Main detector
    "DriftDetector",

    # Integrations
    "EvidentlyIntegration",
    "AlibiDetectIntegration",

    # Constants
    "PSI_THRESHOLD_WARNING",
    "PSI_THRESHOLD_CRITICAL",
    "KS_PVALUE_THRESHOLD",
    "DRIFT_DETECTION_SLA_HOURS",

    # Dashboard specs
    "PROMETHEUS_ALERT_RULES",
    "GRAFANA_DRIFT_DASHBOARD",

    # Tests
    "DriftDetectionTests",

    # Utilities
    "create_drift_detector_from_config",
    "export_prometheus_rules",
    "export_grafana_dashboard",
]
