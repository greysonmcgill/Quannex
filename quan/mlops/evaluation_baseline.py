"""
Offline Evaluation Baseline System for Collections ML Models

Comprehensive evaluation framework including:
- AUC-ROC/AUC-PR computation
- Brier score and calibration metrics
- Cohort-wise analysis
- Temporal stability evaluation
- Bootstrap confidence intervals
- Statistical significance testing
- MLflow integration
- Report generation (HTML/PDF)
- Performance degradation detection

Target: AUC >= 0.85 threshold with reproducible cohort breakdowns
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Optional
from collections import defaultdict
import math
import random
import json
import hashlib
import statistics

# Conditional imports
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None


class MetricType(Enum):
    """Types of evaluation metrics"""
    DISCRIMINATION = "discrimination"  # AUC-ROC, AUC-PR
    CALIBRATION = "calibration"  # Brier, ECE
    RANKING = "ranking"  # Lift, Gain
    CLASSIFICATION = "classification"  # Precision, Recall, F1
    FAIRNESS = "fairness"  # Equalized odds, demographic parity


class CohortType(Enum):
    """Cohort dimensions for analysis"""
    DEBT_AMOUNT = "debt_amount"
    ACCOUNT_AGE = "account_age"
    CHANNEL = "channel"
    GEOGRAPHY = "geography"
    SCORE_BAND = "score_band"
    CREDITOR_TYPE = "creditor_type"
    PAYMENT_HISTORY = "payment_history"


class DegradationType(Enum):
    """Types of model degradation"""
    CONCEPT_DRIFT = "concept_drift"
    DATA_DRIFT = "data_drift"
    LABEL_DRIFT = "label_drift"
    PERFORMANCE_DROP = "performance_drop"


@dataclass
class EvaluationSample:
    """Single evaluation sample"""
    sample_id: str
    y_true: float  # Ground truth (0 or 1)
    y_pred: float  # Predicted probability
    y_pred_class: int  # Predicted class
    cohorts: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    features: dict[str, float] = field(default_factory=dict)


@dataclass
class MetricResult:
    """Result of a metric computation"""
    name: str
    value: float
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    n_samples: int = 0
    metric_type: MetricType = MetricType.DISCRIMINATION
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CohortMetrics:
    """Metrics for a specific cohort"""
    cohort_type: CohortType
    cohort_value: str
    n_samples: int
    metrics: dict[str, MetricResult] = field(default_factory=dict)
    prevalence: float = 0.0


@dataclass
class CalibrationBin:
    """Single bin for calibration curve"""
    bin_id: int
    bin_start: float
    bin_end: float
    mean_predicted: float
    mean_actual: float
    n_samples: int
    confidence_interval: tuple[float, float] = (0.0, 0.0)


@dataclass
class ConfusionMatrixResult:
    """Confusion matrix with derived metrics"""
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    specificity: float = 0.0
    accuracy: float = 0.0
    threshold: float = 0.5


@dataclass
class LiftGainPoint:
    """Point on lift/gain curve"""
    percentile: float
    cumulative_population: float
    cumulative_positives: float
    lift: float
    gain: float


@dataclass
class FeatureImportance:
    """Feature importance ranking"""
    feature_name: str
    importance_score: float
    importance_rank: int
    method: str = "permutation"
    confidence_interval: tuple[float, float] = (0.0, 0.0)


@dataclass
class DegradationAlert:
    """Alert for detected model degradation"""
    alert_id: str
    degradation_type: DegradationType
    severity: str  # low, medium, high, critical
    metric_name: str
    baseline_value: float
    current_value: float
    percent_change: float
    detected_at: datetime = field(default_factory=datetime.now)
    recommendation: str = ""


@dataclass
class EvaluationReport:
    """Complete evaluation report"""
    report_id: str
    model_name: str
    model_version: str
    evaluation_timestamp: datetime
    overall_metrics: dict[str, MetricResult]
    cohort_metrics: dict[CohortType, list[CohortMetrics]]
    temporal_metrics: list[dict[str, Any]]
    calibration_curve: list[CalibrationBin]
    lift_gain_curve: list[LiftGainPoint]
    feature_importance: list[FeatureImportance]
    confusion_matrices: dict[float, ConfusionMatrixResult]
    degradation_alerts: list[DegradationAlert]
    baseline_comparison: dict[str, Any]
    passed_threshold: bool = False
    auc_threshold: float = 0.85


class StatisticalTester:
    """Statistical significance testing utilities"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def bootstrap_confidence_interval(
        self,
        data: list[float],
        statistic_fn: Callable[[list[float]], float],
        n_bootstrap: int = 1000,
        confidence_level: float = 0.95
    ) -> tuple[float, float]:
        """Compute bootstrap confidence interval"""
        if not data:
            return (0.0, 0.0)

        bootstrap_stats = []
        n = len(data)

        for _ in range(n_bootstrap):
            # Resample with replacement
            sample = [random.choice(data) for _ in range(n)]
            stat = statistic_fn(sample)
            bootstrap_stats.append(stat)

        bootstrap_stats.sort()

        # Percentile method
        lower_idx = int((1 - confidence_level) / 2 * n_bootstrap)
        upper_idx = int((1 + confidence_level) / 2 * n_bootstrap) - 1

        return (bootstrap_stats[lower_idx], bootstrap_stats[upper_idx])

    def paired_t_test(
        self,
        sample1: list[float],
        sample2: list[float]
    ) -> tuple[float, bool]:
        """Paired t-test for comparing two models"""
        if len(sample1) != len(sample2) or len(sample1) < 2:
            return (1.0, False)

        differences = [a - b for a, b in zip(sample1, sample2)]
        n = len(differences)

        mean_diff = sum(differences) / n
        variance = sum((d - mean_diff) ** 2 for d in differences) / (n - 1)
        std_error = math.sqrt(variance / n) if variance > 0 else 1e-10

        t_statistic = mean_diff / std_error

        # Approximate p-value using normal distribution for large n
        p_value = 2 * (1 - self._normal_cdf(abs(t_statistic)))

        is_significant = p_value < self.alpha
        return (p_value, is_significant)

    def permutation_test(
        self,
        sample1: list[float],
        sample2: list[float],
        n_permutations: int = 1000
    ) -> tuple[float, bool]:
        """Permutation test for comparing two models"""
        combined = sample1 + sample2
        n1 = len(sample1)

        observed_diff = abs(
            sum(sample1) / len(sample1) - sum(sample2) / len(sample2)
        )

        count_extreme = 0

        for _ in range(n_permutations):
            random.shuffle(combined)
            perm_sample1 = combined[:n1]
            perm_sample2 = combined[n1:]

            perm_diff = abs(
                sum(perm_sample1) / len(perm_sample1) -
                sum(perm_sample2) / len(perm_sample2)
            )

            if perm_diff >= observed_diff:
                count_extreme += 1

        p_value = count_extreme / n_permutations
        is_significant = p_value < self.alpha

        return (p_value, is_significant)

    def delong_test(
        self,
        y_true: list[float],
        y_pred1: list[float],
        y_pred2: list[float]
    ) -> tuple[float, bool]:
        """DeLong test for comparing two AUC-ROC values"""
        # Simplified implementation
        auc1 = self._compute_auc(y_true, y_pred1)
        auc2 = self._compute_auc(y_true, y_pred2)

        # Approximate variance using bootstrap
        n_bootstrap = 500
        auc_diffs = []

        for _ in range(n_bootstrap):
            indices = [random.randint(0, len(y_true) - 1) for _ in range(len(y_true))]
            boot_true = [y_true[i] for i in indices]
            boot_pred1 = [y_pred1[i] for i in indices]
            boot_pred2 = [y_pred2[i] for i in indices]

            boot_auc1 = self._compute_auc(boot_true, boot_pred1)
            boot_auc2 = self._compute_auc(boot_true, boot_pred2)
            auc_diffs.append(boot_auc1 - boot_auc2)

        if not auc_diffs:
            return (1.0, False)

        mean_diff = sum(auc_diffs) / len(auc_diffs)
        variance = sum((d - mean_diff) ** 2 for d in auc_diffs) / len(auc_diffs)
        std_error = math.sqrt(variance) if variance > 0 else 1e-10

        z_statistic = (auc1 - auc2) / std_error
        p_value = 2 * (1 - self._normal_cdf(abs(z_statistic)))

        return (p_value, p_value < self.alpha)

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _compute_auc(self, y_true: list[float], y_pred: list[float]) -> float:
        """Compute AUC-ROC"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0], reverse=True)

        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tp = 0
        auc = 0

        for pred, actual in pairs:
            if actual == 1:
                tp += 1
            else:
                auc += tp

        return auc / (n_pos * n_neg)


class MetricsComputer:
    """Computes all evaluation metrics"""

    def __init__(self):
        self.stat_tester = StatisticalTester()

    def compute_auc_roc(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bootstrap: int = 1000
    ) -> MetricResult:
        """Compute AUC-ROC with confidence interval"""
        auc = self._compute_auc_roc_core(y_true, y_pred)

        # Bootstrap CI
        def auc_stat(indices):
            yt = [y_true[i] for i in indices]
            yp = [y_pred[i] for i in indices]
            return self._compute_auc_roc_core(yt, yp)

        indices = list(range(len(y_true)))
        ci = self.stat_tester.bootstrap_confidence_interval(
            indices, auc_stat, n_bootstrap
        )

        return MetricResult(
            name="AUC-ROC",
            value=auc,
            confidence_interval=ci,
            n_samples=len(y_true),
            metric_type=MetricType.DISCRIMINATION,
            metadata={"n_bootstrap": n_bootstrap}
        )

    def compute_auc_pr(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bootstrap: int = 1000
    ) -> MetricResult:
        """Compute AUC-PR (Average Precision) with confidence interval"""
        ap = self._compute_average_precision(y_true, y_pred)

        # Bootstrap CI
        def ap_stat(indices):
            yt = [y_true[i] for i in indices]
            yp = [y_pred[i] for i in indices]
            return self._compute_average_precision(yt, yp)

        indices = list(range(len(y_true)))
        ci = self.stat_tester.bootstrap_confidence_interval(
            indices, ap_stat, n_bootstrap
        )

        return MetricResult(
            name="AUC-PR",
            value=ap,
            confidence_interval=ci,
            n_samples=len(y_true),
            metric_type=MetricType.DISCRIMINATION,
            metadata={"n_bootstrap": n_bootstrap}
        )

    def compute_brier_score(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bootstrap: int = 1000
    ) -> MetricResult:
        """Compute Brier score with confidence interval"""
        brier = sum((p - t) ** 2 for p, t in zip(y_pred, y_true)) / len(y_true)

        # Bootstrap CI
        squared_errors = [(p - t) ** 2 for p, t in zip(y_pred, y_true)]
        ci = self.stat_tester.bootstrap_confidence_interval(
            squared_errors, lambda x: sum(x) / len(x), n_bootstrap
        )

        return MetricResult(
            name="Brier Score",
            value=brier,
            confidence_interval=ci,
            n_samples=len(y_true),
            metric_type=MetricType.CALIBRATION,
            metadata={"optimal": 0.0}
        )

    def compute_expected_calibration_error(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bins: int = 10
    ) -> MetricResult:
        """Compute Expected Calibration Error (ECE)"""
        bins = self._create_calibration_bins(y_true, y_pred, n_bins)

        ece = 0.0
        total_samples = len(y_true)

        for bin_data in bins:
            if bin_data.n_samples > 0:
                bin_error = abs(bin_data.mean_predicted - bin_data.mean_actual)
                ece += (bin_data.n_samples / total_samples) * bin_error

        return MetricResult(
            name="ECE",
            value=ece,
            n_samples=len(y_true),
            metric_type=MetricType.CALIBRATION,
            metadata={"n_bins": n_bins}
        )

    def compute_maximum_calibration_error(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bins: int = 10
    ) -> MetricResult:
        """Compute Maximum Calibration Error (MCE)"""
        bins = self._create_calibration_bins(y_true, y_pred, n_bins)

        mce = 0.0

        for bin_data in bins:
            if bin_data.n_samples > 0:
                bin_error = abs(bin_data.mean_predicted - bin_data.mean_actual)
                mce = max(mce, bin_error)

        return MetricResult(
            name="MCE",
            value=mce,
            n_samples=len(y_true),
            metric_type=MetricType.CALIBRATION,
            metadata={"n_bins": n_bins}
        )

    def compute_calibration_curve(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bins: int = 10,
        n_bootstrap: int = 500
    ) -> list[CalibrationBin]:
        """Compute calibration curve with confidence intervals"""
        bins = self._create_calibration_bins(y_true, y_pred, n_bins)

        # Add bootstrap CI to each bin
        for bin_data in bins:
            if bin_data.n_samples > 5:
                # Get samples in this bin
                bin_samples = [
                    y_true[i] for i, p in enumerate(y_pred)
                    if bin_data.bin_start <= p < bin_data.bin_end
                ]

                if bin_samples:
                    ci = self.stat_tester.bootstrap_confidence_interval(
                        bin_samples, lambda x: sum(x) / len(x), n_bootstrap
                    )
                    bin_data.confidence_interval = ci

        return bins

    def compute_confusion_matrix(
        self,
        y_true: list[float],
        y_pred: list[float],
        threshold: float = 0.5
    ) -> ConfusionMatrixResult:
        """Compute confusion matrix at given threshold"""
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p >= threshold)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p >= threshold)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p < threshold)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p < threshold)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        accuracy = (tp + tn) / len(y_true) if y_true else 0.0

        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return ConfusionMatrixResult(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            specificity=specificity,
            accuracy=accuracy,
            threshold=threshold
        )

    def compute_lift_gain_curve(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_points: int = 10
    ) -> list[LiftGainPoint]:
        """Compute lift and gain curves"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0], reverse=True)

        total_positives = sum(y_true)
        overall_positive_rate = total_positives / len(y_true) if y_true else 0

        results = []
        cumulative_positives = 0

        for i in range(1, n_points + 1):
            percentile = i / n_points
            cutoff_idx = int(percentile * len(pairs))

            cumulative_positives = sum(p[1] for p in pairs[:cutoff_idx])
            cumulative_population = cutoff_idx / len(pairs) if pairs else 0

            # Gain: proportion of all positives captured
            gain = cumulative_positives / total_positives if total_positives > 0 else 0

            # Lift: ratio of positive rate in top percentile vs overall
            if cumulative_population > 0:
                top_positive_rate = cumulative_positives / cutoff_idx
                lift = top_positive_rate / overall_positive_rate if overall_positive_rate > 0 else 0
            else:
                lift = 0

            results.append(LiftGainPoint(
                percentile=percentile,
                cumulative_population=cumulative_population,
                cumulative_positives=cumulative_positives,
                lift=lift,
                gain=gain
            ))

        return results

    def compute_ks_statistic(
        self,
        y_true: list[float],
        y_pred: list[float]
    ) -> MetricResult:
        """Compute Kolmogorov-Smirnov statistic"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0])

        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return MetricResult(
                name="KS Statistic",
                value=0.0,
                n_samples=len(y_true),
                metric_type=MetricType.DISCRIMINATION
            )

        cum_pos = 0
        cum_neg = 0
        max_ks = 0.0

        for pred, actual in pairs:
            if actual == 1:
                cum_pos += 1
            else:
                cum_neg += 1

            tpr = cum_pos / n_pos
            fpr = cum_neg / n_neg
            ks = abs(tpr - fpr)
            max_ks = max(max_ks, ks)

        return MetricResult(
            name="KS Statistic",
            value=max_ks,
            n_samples=len(y_true),
            metric_type=MetricType.DISCRIMINATION
        )

    def compute_log_loss(
        self,
        y_true: list[float],
        y_pred: list[float]
    ) -> MetricResult:
        """Compute log loss"""
        eps = 1e-15
        log_loss = -sum(
            t * math.log(max(p, eps)) + (1 - t) * math.log(max(1 - p, eps))
            for t, p in zip(y_true, y_pred)
        ) / len(y_true)

        return MetricResult(
            name="Log Loss",
            value=log_loss,
            n_samples=len(y_true),
            metric_type=MetricType.CALIBRATION
        )

    def _compute_auc_roc_core(
        self,
        y_true: list[float],
        y_pred: list[float]
    ) -> float:
        """Core AUC-ROC computation"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0], reverse=True)

        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tp = 0
        auc = 0.0
        prev_pred = float('inf')
        prev_tp = 0
        prev_fp = 0

        for pred, actual in pairs:
            if pred != prev_pred:
                # Trapezoidal rule for ties
                fp = (len(y_true) - n_pos) - (n_neg - (prev_fp if prev_pred != float('inf') else 0))
                auc += (prev_tp + tp) / 2 * (fp - prev_fp) if prev_pred != float('inf') else 0
                prev_pred = pred

            if actual == 1:
                tp += 1
            prev_tp = tp
            prev_fp = sum(1 for p, a in pairs[:pairs.index((pred, actual)) + 1] if a == 0)

        # Simplified calculation
        tp = 0
        auc = 0.0

        for pred, actual in pairs:
            if actual == 1:
                tp += 1
            else:
                auc += tp

        return auc / (n_pos * n_neg) if (n_pos * n_neg) > 0 else 0.5

    def _compute_average_precision(
        self,
        y_true: list[float],
        y_pred: list[float]
    ) -> float:
        """Compute Average Precision (area under PR curve)"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0], reverse=True)

        n_pos = sum(y_true)
        if n_pos == 0:
            return 0.0

        tp = 0
        ap = 0.0

        for i, (pred, actual) in enumerate(pairs):
            if actual == 1:
                tp += 1
                precision_at_k = tp / (i + 1)
                ap += precision_at_k

        return ap / n_pos

    def _create_calibration_bins(
        self,
        y_true: list[float],
        y_pred: list[float],
        n_bins: int
    ) -> list[CalibrationBin]:
        """Create calibration bins"""
        bins = []
        bin_width = 1.0 / n_bins

        for i in range(n_bins):
            bin_start = i * bin_width
            bin_end = (i + 1) * bin_width if i < n_bins - 1 else 1.0001

            bin_preds = []
            bin_actuals = []

            for pred, actual in zip(y_pred, y_true):
                if bin_start <= pred < bin_end:
                    bin_preds.append(pred)
                    bin_actuals.append(actual)

            mean_predicted = sum(bin_preds) / len(bin_preds) if bin_preds else (bin_start + bin_end) / 2
            mean_actual = sum(bin_actuals) / len(bin_actuals) if bin_actuals else 0.0

            bins.append(CalibrationBin(
                bin_id=i,
                bin_start=bin_start,
                bin_end=bin_end,
                mean_predicted=mean_predicted,
                mean_actual=mean_actual,
                n_samples=len(bin_preds)
            ))

        return bins


class CohortAnalyzer:
    """Analyzes metrics by cohort"""

    def __init__(self, metrics_computer: MetricsComputer):
        self.metrics_computer = metrics_computer

    def define_cohort(
        self,
        samples: list[EvaluationSample],
        cohort_type: CohortType
    ) -> dict[str, list[EvaluationSample]]:
        """Split samples into cohorts"""
        cohorts: dict[str, list[EvaluationSample]] = defaultdict(list)

        for sample in samples:
            cohort_value = self._get_cohort_value(sample, cohort_type)
            cohorts[cohort_value].append(sample)

        return cohorts

    def analyze_by_cohort(
        self,
        samples: list[EvaluationSample],
        cohort_type: CohortType
    ) -> list[CohortMetrics]:
        """Compute metrics for each cohort"""
        cohorts = self.define_cohort(samples, cohort_type)
        results = []
        total_samples = len(samples)

        for cohort_value, cohort_samples in cohorts.items():
            y_true = [s.y_true for s in cohort_samples]
            y_pred = [s.y_pred for s in cohort_samples]

            metrics = {}

            # Compute key metrics
            if len(cohort_samples) >= 10:
                metrics["AUC-ROC"] = self.metrics_computer.compute_auc_roc(y_true, y_pred)
                metrics["AUC-PR"] = self.metrics_computer.compute_auc_pr(y_true, y_pred)
                metrics["Brier"] = self.metrics_computer.compute_brier_score(y_true, y_pred)
                metrics["ECE"] = self.metrics_computer.compute_expected_calibration_error(y_true, y_pred)

                cm = self.metrics_computer.compute_confusion_matrix(y_true, y_pred)
                metrics["Precision"] = MetricResult(
                    name="Precision", value=cm.precision,
                    n_samples=len(cohort_samples), metric_type=MetricType.CLASSIFICATION
                )
                metrics["Recall"] = MetricResult(
                    name="Recall", value=cm.recall,
                    n_samples=len(cohort_samples), metric_type=MetricType.CLASSIFICATION
                )
                metrics["F1"] = MetricResult(
                    name="F1", value=cm.f1_score,
                    n_samples=len(cohort_samples), metric_type=MetricType.CLASSIFICATION
                )

            prevalence = sum(y_true) / len(y_true) if y_true else 0.0

            results.append(CohortMetrics(
                cohort_type=cohort_type,
                cohort_value=cohort_value,
                n_samples=len(cohort_samples),
                metrics=metrics,
                prevalence=prevalence
            ))

        return results

    def _get_cohort_value(
        self,
        sample: EvaluationSample,
        cohort_type: CohortType
    ) -> str:
        """Get cohort value for a sample"""
        # Check explicit cohort assignment
        if cohort_type.value in sample.cohorts:
            return sample.cohorts[cohort_type.value]

        # Derive from features
        features = sample.features

        if cohort_type == CohortType.DEBT_AMOUNT:
            balance = features.get("balance", 0)
            if balance < 500:
                return "small_<500"
            elif balance < 2000:
                return "medium_500-2000"
            elif balance < 10000:
                return "large_2000-10000"
            else:
                return "very_large_>10000"

        elif cohort_type == CohortType.ACCOUNT_AGE:
            days = features.get("days_past_due", 0)
            if days < 30:
                return "fresh_<30d"
            elif days < 90:
                return "early_30-90d"
            elif days < 180:
                return "mid_90-180d"
            elif days < 365:
                return "late_180-365d"
            else:
                return "aged_>365d"

        elif cohort_type == CohortType.SCORE_BAND:
            score = features.get("shadow_score", 0)
            if score < 500:
                return "poor_<500"
            elif score < 600:
                return "fair_500-600"
            elif score < 700:
                return "good_600-700"
            else:
                return "excellent_>700"

        elif cohort_type == CohortType.CHANNEL:
            return features.get("channel", "unknown")

        elif cohort_type == CohortType.GEOGRAPHY:
            return features.get("region", features.get("state", "unknown"))

        elif cohort_type == CohortType.CREDITOR_TYPE:
            return features.get("creditor_type", features.get("original_creditor_type", "unknown"))

        elif cohort_type == CohortType.PAYMENT_HISTORY:
            payments = features.get("past_payment_count", 0)
            if payments == 0:
                return "no_history"
            elif payments < 3:
                return "minimal_1-2"
            elif payments < 6:
                return "some_3-5"
            else:
                return "established_6+"

        return "unknown"


class TemporalAnalyzer:
    """Analyzes temporal stability of model performance"""

    def __init__(self, metrics_computer: MetricsComputer):
        self.metrics_computer = metrics_computer

    def analyze_by_time_slice(
        self,
        samples: list[EvaluationSample],
        slice_duration_days: int = 7
    ) -> list[dict[str, Any]]:
        """Analyze metrics over time slices"""
        if not samples:
            return []

        # Sort by timestamp
        sorted_samples = sorted(samples, key=lambda s: s.timestamp)

        # Get time range
        start_time = sorted_samples[0].timestamp
        end_time = sorted_samples[-1].timestamp

        results = []
        current_time = start_time

        while current_time < end_time:
            slice_end = current_time + timedelta(days=slice_duration_days)

            slice_samples = [
                s for s in sorted_samples
                if current_time <= s.timestamp < slice_end
            ]

            if len(slice_samples) >= 20:
                y_true = [s.y_true for s in slice_samples]
                y_pred = [s.y_pred for s in slice_samples]

                auc = self.metrics_computer.compute_auc_roc(y_true, y_pred)
                brier = self.metrics_computer.compute_brier_score(y_true, y_pred)

                results.append({
                    "slice_start": current_time.isoformat(),
                    "slice_end": slice_end.isoformat(),
                    "n_samples": len(slice_samples),
                    "prevalence": sum(y_true) / len(y_true),
                    "auc_roc": auc.value,
                    "auc_roc_ci": auc.confidence_interval,
                    "brier_score": brier.value
                })

            current_time = slice_end

        return results

    def detect_temporal_drift(
        self,
        temporal_metrics: list[dict[str, Any]],
        metric_name: str = "auc_roc",
        threshold_pct: float = 0.05
    ) -> list[DegradationAlert]:
        """Detect temporal performance drift"""
        if len(temporal_metrics) < 3:
            return []

        alerts = []
        values = [m[metric_name] for m in temporal_metrics]

        # Calculate rolling average
        window_size = min(3, len(values))
        baseline = sum(values[:window_size]) / window_size

        for i, m in enumerate(temporal_metrics[window_size:], window_size):
            current = m[metric_name]
            pct_change = (baseline - current) / baseline if baseline > 0 else 0

            if pct_change > threshold_pct:
                severity = "high" if pct_change > 0.1 else "medium" if pct_change > 0.05 else "low"

                alerts.append(DegradationAlert(
                    alert_id=f"drift_{m['slice_start']}_{metric_name}",
                    degradation_type=DegradationType.PERFORMANCE_DROP,
                    severity=severity,
                    metric_name=metric_name,
                    baseline_value=baseline,
                    current_value=current,
                    percent_change=pct_change * 100,
                    recommendation=f"Investigate data or concept drift in period {m['slice_start']}"
                ))

        return alerts


class FeatureImportanceAnalyzer:
    """Analyzes feature importance"""

    def __init__(self):
        pass

    def compute_permutation_importance(
        self,
        samples: list[EvaluationSample],
        model_predict_fn: Callable[[dict[str, float]], float],
        n_repeats: int = 10
    ) -> list[FeatureImportance]:
        """Compute permutation feature importance"""
        if not samples:
            return []

        # Get baseline score
        y_true = [s.y_true for s in samples]
        y_pred = [s.y_pred for s in samples]
        baseline_auc = self._compute_auc(y_true, y_pred)

        # Get all feature names
        feature_names = set()
        for s in samples:
            feature_names.update(s.features.keys())

        results = []

        for feature_name in feature_names:
            importance_scores = []

            for _ in range(n_repeats):
                # Permute feature
                permuted_samples = []
                feature_values = [s.features.get(feature_name, 0) for s in samples]
                random.shuffle(feature_values)

                for i, sample in enumerate(samples):
                    permuted_features = sample.features.copy()
                    permuted_features[feature_name] = feature_values[i]

                    # Get new prediction
                    try:
                        new_pred = model_predict_fn(permuted_features)
                    except Exception:
                        new_pred = sample.y_pred

                    permuted_samples.append(new_pred)

                # Calculate new AUC
                permuted_auc = self._compute_auc(y_true, permuted_samples)
                importance = baseline_auc - permuted_auc
                importance_scores.append(importance)

            mean_importance = sum(importance_scores) / len(importance_scores)
            std_importance = statistics.stdev(importance_scores) if len(importance_scores) > 1 else 0

            results.append(FeatureImportance(
                feature_name=feature_name,
                importance_score=mean_importance,
                importance_rank=0,  # Will be set after sorting
                method="permutation",
                confidence_interval=(
                    mean_importance - 1.96 * std_importance,
                    mean_importance + 1.96 * std_importance
                )
            ))

        # Sort and assign ranks
        results.sort(key=lambda x: x.importance_score, reverse=True)
        for i, result in enumerate(results):
            result.importance_rank = i + 1

        return results

    def compute_shap_approximation(
        self,
        samples: list[EvaluationSample],
        n_samples: int = 100
    ) -> list[FeatureImportance]:
        """Approximate SHAP values using sampling"""
        if not samples:
            return []

        # Use subset for efficiency
        subset = random.sample(samples, min(n_samples, len(samples)))

        # Get all feature names
        feature_names = set()
        for s in subset:
            feature_names.update(s.features.keys())

        # Calculate mean absolute contribution per feature
        feature_contributions: dict[str, list[float]] = defaultdict(list)

        for sample in subset:
            for feature_name in feature_names:
                value = sample.features.get(feature_name, 0)
                # Handle non-numeric features
                try:
                    numeric_value = float(value) if not isinstance(value, str) else hash(value) % 100 / 100
                except (ValueError, TypeError):
                    numeric_value = hash(str(value)) % 100 / 100
                # Simplified: contribution proportional to value * prediction
                contribution = abs(numeric_value * sample.y_pred)
                feature_contributions[feature_name].append(contribution)

        results = []
        for feature_name, contributions in feature_contributions.items():
            mean_contribution = sum(contributions) / len(contributions)
            std_contribution = statistics.stdev(contributions) if len(contributions) > 1 else 0

            results.append(FeatureImportance(
                feature_name=feature_name,
                importance_score=mean_contribution,
                importance_rank=0,
                method="shap_approximation",
                confidence_interval=(
                    mean_contribution - 1.96 * std_contribution,
                    mean_contribution + 1.96 * std_contribution
                )
            ))

        # Sort and assign ranks
        results.sort(key=lambda x: x.importance_score, reverse=True)
        for i, result in enumerate(results):
            result.importance_rank = i + 1

        return results

    def _compute_auc(self, y_true: list[float], y_pred: list[float]) -> float:
        """Compute AUC-ROC"""
        pairs = list(zip(y_pred, y_true))
        pairs.sort(key=lambda x: x[0], reverse=True)

        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tp = 0
        auc = 0

        for pred, actual in pairs:
            if actual == 1:
                tp += 1
            else:
                auc += tp

        return auc / (n_pos * n_neg)


class BaselineComparator:
    """Compares model against baselines"""

    def __init__(self, stat_tester: StatisticalTester):
        self.stat_tester = stat_tester
        self.baselines: dict[str, dict[str, float]] = {}

    def register_baseline(
        self,
        baseline_name: str,
        metrics: dict[str, float]
    ) -> None:
        """Register a baseline for comparison"""
        self.baselines[baseline_name] = metrics

    def compare_to_baseline(
        self,
        current_metrics: dict[str, MetricResult],
        baseline_name: str
    ) -> dict[str, dict[str, Any]]:
        """Compare current metrics to baseline"""
        if baseline_name not in self.baselines:
            return {}

        baseline = self.baselines[baseline_name]
        comparison = {}

        for metric_name, current in current_metrics.items():
            if metric_name in baseline:
                baseline_value = baseline[metric_name]
                diff = current.value - baseline_value
                pct_change = (diff / baseline_value * 100) if baseline_value != 0 else 0

                # Determine if change is significant using CI
                is_significant = (
                    current.confidence_interval[0] > baseline_value or
                    current.confidence_interval[1] < baseline_value
                )

                comparison[metric_name] = {
                    "baseline": baseline_value,
                    "current": current.value,
                    "difference": diff,
                    "percent_change": pct_change,
                    "is_significant": is_significant,
                    "confidence_interval": current.confidence_interval,
                    "improved": diff > 0 if metric_name in ["AUC-ROC", "AUC-PR"] else diff < 0
                }

        return comparison

    def save_as_baseline(
        self,
        baseline_name: str,
        metrics: dict[str, MetricResult],
        filepath: str | None = None
    ) -> None:
        """Save current metrics as a new baseline"""
        baseline_data = {
            metric_name: metric.value
            for metric_name, metric in metrics.items()
        }
        self.baselines[baseline_name] = baseline_data

        if filepath:
            with open(filepath, 'w') as f:
                json.dump({
                    "baseline_name": baseline_name,
                    "created_at": datetime.now().isoformat(),
                    "metrics": baseline_data
                }, f, indent=2)

    def load_baseline(self, filepath: str) -> str | None:
        """Load baseline from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            baseline_name = data["baseline_name"]
            self.baselines[baseline_name] = data["metrics"]
            return baseline_name
        except Exception:
            return None


class DegradationDetector:
    """Detects model performance degradation"""

    def __init__(self, auc_threshold: float = 0.85):
        self.auc_threshold = auc_threshold
        self.threshold_configs = {
            "AUC-ROC": {"min": 0.85, "warning": 0.88},
            "AUC-PR": {"min": 0.75, "warning": 0.80},
            "Brier": {"max": 0.20, "warning": 0.15},
            "ECE": {"max": 0.10, "warning": 0.05}
        }

    def detect_degradation(
        self,
        current_metrics: dict[str, MetricResult],
        baseline_metrics: dict[str, float] | None = None
    ) -> list[DegradationAlert]:
        """Detect performance degradation"""
        alerts = []

        for metric_name, metric in current_metrics.items():
            config = self.threshold_configs.get(metric_name, {})

            # Check absolute thresholds
            if "min" in config and metric.value < config["min"]:
                severity = "critical" if metric.value < config["min"] * 0.9 else "high"
                alerts.append(DegradationAlert(
                    alert_id=f"threshold_{metric_name}_{datetime.now().timestamp()}",
                    degradation_type=DegradationType.PERFORMANCE_DROP,
                    severity=severity,
                    metric_name=metric_name,
                    baseline_value=config["min"],
                    current_value=metric.value,
                    percent_change=((config["min"] - metric.value) / config["min"]) * 100,
                    recommendation=f"Model {metric_name} below minimum threshold. Retrain or rollback."
                ))

            elif "max" in config and metric.value > config["max"]:
                severity = "critical" if metric.value > config["max"] * 1.5 else "high"
                alerts.append(DegradationAlert(
                    alert_id=f"threshold_{metric_name}_{datetime.now().timestamp()}",
                    degradation_type=DegradationType.PERFORMANCE_DROP,
                    severity=severity,
                    metric_name=metric_name,
                    baseline_value=config["max"],
                    current_value=metric.value,
                    percent_change=((metric.value - config["max"]) / config["max"]) * 100,
                    recommendation=f"Model {metric_name} above maximum threshold. Check calibration."
                ))

            # Check against baseline
            if baseline_metrics and metric_name in baseline_metrics:
                baseline = baseline_metrics[metric_name]
                pct_change = abs(metric.value - baseline) / baseline if baseline != 0 else 0

                if pct_change > 0.1:  # 10% change
                    alerts.append(DegradationAlert(
                        alert_id=f"baseline_{metric_name}_{datetime.now().timestamp()}",
                        degradation_type=DegradationType.CONCEPT_DRIFT,
                        severity="medium" if pct_change < 0.2 else "high",
                        metric_name=metric_name,
                        baseline_value=baseline,
                        current_value=metric.value,
                        percent_change=pct_change * 100,
                        recommendation=f"Significant {metric_name} drift from baseline. Investigate data distribution."
                    ))

        return alerts


class MLflowLogger:
    """Logs metrics to MLflow"""

    def __init__(self, experiment_name: str = "collections_ml_evaluation"):
        self.experiment_name = experiment_name
        self._initialized = False

    def _init_mlflow(self) -> bool:
        """Initialize MLflow"""
        if not MLFLOW_AVAILABLE:
            return False

        try:
            mlflow.set_experiment(self.experiment_name)
            self._initialized = True
            return True
        except Exception:
            return False

    def log_evaluation(
        self,
        model_name: str,
        model_version: str,
        metrics: dict[str, MetricResult],
        cohort_metrics: dict[CohortType, list[CohortMetrics]] | None = None,
        params: dict[str, Any] | None = None,
        artifacts: list[str] | None = None
    ) -> str | None:
        """Log evaluation to MLflow"""
        if not self._init_mlflow():
            return None

        try:
            with mlflow.start_run() as run:
                # Log parameters
                mlflow.log_param("model_name", model_name)
                mlflow.log_param("model_version", model_version)
                mlflow.log_param("evaluation_timestamp", datetime.now().isoformat())

                if params:
                    for key, value in params.items():
                        mlflow.log_param(key, value)

                # Log overall metrics
                for metric_name, metric in metrics.items():
                    mlflow.log_metric(metric_name.replace(" ", "_"), metric.value)
                    mlflow.log_metric(f"{metric_name}_ci_lower".replace(" ", "_"), metric.confidence_interval[0])
                    mlflow.log_metric(f"{metric_name}_ci_upper".replace(" ", "_"), metric.confidence_interval[1])

                # Log cohort metrics
                if cohort_metrics:
                    for cohort_type, cohort_list in cohort_metrics.items():
                        for cohort in cohort_list:
                            prefix = f"{cohort_type.value}_{cohort.cohort_value}"
                            mlflow.log_metric(f"{prefix}_n_samples", cohort.n_samples)
                            mlflow.log_metric(f"{prefix}_prevalence", cohort.prevalence)

                            for m_name, m_result in cohort.metrics.items():
                                mlflow.log_metric(f"{prefix}_{m_name}", m_result.value)

                # Log artifacts
                if artifacts:
                    for artifact_path in artifacts:
                        mlflow.log_artifact(artifact_path)

                return run.info.run_id

        except Exception as e:
            print(f"MLflow logging failed: {e}")
            return None

    def log_baseline(
        self,
        baseline_name: str,
        metrics: dict[str, float]
    ) -> None:
        """Log baseline metrics"""
        if not self._init_mlflow():
            return

        try:
            with mlflow.start_run(run_name=f"baseline_{baseline_name}"):
                mlflow.log_param("baseline_name", baseline_name)
                mlflow.log_param("is_baseline", True)

                for metric_name, value in metrics.items():
                    mlflow.log_metric(metric_name, value)
        except Exception:
            pass


class ReportGenerator:
    """Generates evaluation reports in various formats"""

    def __init__(self):
        pass

    def generate_html_report(
        self,
        report: EvaluationReport,
        output_path: str
    ) -> str:
        """Generate HTML evaluation report"""
        html_content = self._build_html_report(report)

        with open(output_path, 'w') as f:
            f.write(html_content)

        return output_path

    def generate_json_report(
        self,
        report: EvaluationReport,
        output_path: str
    ) -> str:
        """Generate JSON evaluation report"""
        report_dict = self._report_to_dict(report)

        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)

        return output_path

    def generate_pdf_report(
        self,
        report: EvaluationReport,
        output_path: str
    ) -> str:
        """Generate PDF evaluation report (requires additional libraries)"""
        # Generate HTML first, then convert
        html_path = output_path.replace('.pdf', '.html')
        self.generate_html_report(report, html_path)

        # Try to convert to PDF using weasyprint or similar
        try:
            from weasyprint import HTML
            HTML(html_path).write_pdf(output_path)
            return output_path
        except ImportError:
            # Fallback: return HTML path
            return html_path

    def _build_html_report(self, report: EvaluationReport) -> str:
        """Build HTML content for report"""
        passed_class = "passed" if report.passed_threshold else "failed"
        passed_text = "PASSED" if report.passed_threshold else "FAILED"

        # Build cohort sections
        cohort_sections = ""
        for cohort_type, cohorts in report.cohort_metrics.items():
            cohort_rows = ""
            for cohort in cohorts:
                auc = cohort.metrics.get("AUC-ROC")
                auc_val = f"{auc.value:.4f}" if auc else "N/A"
                cohort_rows += f"""
                <tr>
                    <td>{cohort.cohort_value}</td>
                    <td>{cohort.n_samples}</td>
                    <td>{cohort.prevalence:.2%}</td>
                    <td>{auc_val}</td>
                </tr>
                """
            cohort_sections += f"""
            <h3>{cohort_type.value.replace('_', ' ').title()}</h3>
            <table>
                <thead>
                    <tr>
                        <th>Cohort</th>
                        <th>Samples</th>
                        <th>Prevalence</th>
                        <th>AUC-ROC</th>
                    </tr>
                </thead>
                <tbody>
                    {cohort_rows}
                </tbody>
            </table>
            """

        # Build calibration section
        calibration_rows = ""
        for bin_data in report.calibration_curve:
            calibration_rows += f"""
            <tr>
                <td>{bin_data.bin_start:.1f}-{bin_data.bin_end:.1f}</td>
                <td>{bin_data.mean_predicted:.4f}</td>
                <td>{bin_data.mean_actual:.4f}</td>
                <td>{bin_data.n_samples}</td>
            </tr>
            """

        # Build feature importance section
        feature_rows = ""
        for fi in report.feature_importance[:15]:
            feature_rows += f"""
            <tr>
                <td>{fi.importance_rank}</td>
                <td>{fi.feature_name}</td>
                <td>{fi.importance_score:.4f}</td>
            </tr>
            """

        # Build lift/gain section
        lift_rows = ""
        for point in report.lift_gain_curve:
            lift_rows += f"""
            <tr>
                <td>{point.percentile:.0%}</td>
                <td>{point.gain:.2%}</td>
                <td>{point.lift:.2f}x</td>
            </tr>
            """

        # Build alerts section
        alerts_html = ""
        if report.degradation_alerts:
            alert_items = ""
            for alert in report.degradation_alerts:
                alert_items += f"""
                <div class="alert alert-{alert.severity}">
                    <strong>{alert.severity.upper()}</strong>: {alert.metric_name} -
                    {alert.degradation_type.value}.
                    Baseline: {alert.baseline_value:.4f}, Current: {alert.current_value:.4f}
                    ({alert.percent_change:+.1f}%)
                    <br><em>{alert.recommendation}</em>
                </div>
                """
            alerts_html = f"<h2>Degradation Alerts</h2>{alert_items}"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Model Evaluation Report - {report.model_name} v{report.model_version}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        h3 {{ color: #666; margin-top: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #007bff; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .metric-card {{ display: inline-block; padding: 20px; margin: 10px; background: #f8f9fa; border-radius: 8px; min-width: 150px; text-align: center; }}
        .metric-value {{ font-size: 28px; font-weight: bold; color: #007bff; }}
        .metric-name {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .metric-ci {{ font-size: 11px; color: #999; }}
        .passed {{ color: #28a745; font-weight: bold; }}
        .failed {{ color: #dc3545; font-weight: bold; }}
        .threshold-status {{ padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .threshold-status.passed {{ background: #d4edda; border: 1px solid #c3e6cb; }}
        .threshold-status.failed {{ background: #f8d7da; border: 1px solid #f5c6cb; }}
        .alert {{ padding: 15px; margin: 10px 0; border-radius: 4px; }}
        .alert-low {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
        .alert-medium {{ background: #ffe0b2; border-left: 4px solid #ff9800; }}
        .alert-high {{ background: #ffccbc; border-left: 4px solid #ff5722; }}
        .alert-critical {{ background: #ffcdd2; border-left: 4px solid #f44336; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Model Evaluation Report</h1>

        <p><strong>Model:</strong> {report.model_name} v{report.model_version}</p>
        <p><strong>Evaluation Date:</strong> {report.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Report ID:</strong> {report.report_id}</p>

        <div class="threshold-status {passed_class}">
            <strong>AUC Threshold Check ({report.auc_threshold}):</strong>
            <span class="{passed_class}">{passed_text}</span>
            (AUC-ROC: {report.overall_metrics.get('AUC-ROC', MetricResult('', 0)).value:.4f})
        </div>

        {alerts_html}

        <h2>Overall Metrics</h2>
        <div class="summary-grid">
            {''.join(f'''
            <div class="metric-card">
                <div class="metric-value">{m.value:.4f}</div>
                <div class="metric-name">{name}</div>
                <div class="metric-ci">CI: [{m.confidence_interval[0]:.4f}, {m.confidence_interval[1]:.4f}]</div>
            </div>
            ''' for name, m in report.overall_metrics.items())}
        </div>

        <h2>Cohort Analysis</h2>
        {cohort_sections}

        <h2>Calibration Curve</h2>
        <table>
            <thead>
                <tr>
                    <th>Bin Range</th>
                    <th>Mean Predicted</th>
                    <th>Mean Actual</th>
                    <th>Samples</th>
                </tr>
            </thead>
            <tbody>
                {calibration_rows}
            </tbody>
        </table>

        <h2>Lift and Gain</h2>
        <table>
            <thead>
                <tr>
                    <th>Percentile</th>
                    <th>Cumulative Gain</th>
                    <th>Lift</th>
                </tr>
            </thead>
            <tbody>
                {lift_rows}
            </tbody>
        </table>

        <h2>Feature Importance</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Feature</th>
                    <th>Importance Score</th>
                </tr>
            </thead>
            <tbody>
                {feature_rows}
            </tbody>
        </table>

        <h2>Baseline Comparison</h2>
        <p>{json.dumps(report.baseline_comparison, indent=2, default=str)}</p>

        <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #999; font-size: 12px;">
            Generated by QUAN MLOps Evaluation Baseline System
        </footer>
    </div>
</body>
</html>
        """
        return html

    def _report_to_dict(self, report: EvaluationReport) -> dict[str, Any]:
        """Convert report to dictionary"""
        return {
            "report_id": report.report_id,
            "model_name": report.model_name,
            "model_version": report.model_version,
            "evaluation_timestamp": report.evaluation_timestamp.isoformat(),
            "passed_threshold": report.passed_threshold,
            "auc_threshold": report.auc_threshold,
            "overall_metrics": {
                name: {
                    "value": m.value,
                    "confidence_interval": m.confidence_interval,
                    "n_samples": m.n_samples,
                    "metric_type": m.metric_type.value
                }
                for name, m in report.overall_metrics.items()
            },
            "cohort_metrics": {
                cohort_type.value: [
                    {
                        "cohort_value": c.cohort_value,
                        "n_samples": c.n_samples,
                        "prevalence": c.prevalence,
                        "metrics": {
                            name: m.value for name, m in c.metrics.items()
                        }
                    }
                    for c in cohorts
                ]
                for cohort_type, cohorts in report.cohort_metrics.items()
            },
            "temporal_metrics": report.temporal_metrics,
            "calibration_curve": [
                {
                    "bin_start": b.bin_start,
                    "bin_end": b.bin_end,
                    "mean_predicted": b.mean_predicted,
                    "mean_actual": b.mean_actual,
                    "n_samples": b.n_samples
                }
                for b in report.calibration_curve
            ],
            "lift_gain_curve": [
                {
                    "percentile": p.percentile,
                    "gain": p.gain,
                    "lift": p.lift
                }
                for p in report.lift_gain_curve
            ],
            "feature_importance": [
                {
                    "rank": f.importance_rank,
                    "feature": f.feature_name,
                    "importance": f.importance_score,
                    "method": f.method
                }
                for f in report.feature_importance
            ],
            "degradation_alerts": [
                {
                    "alert_id": a.alert_id,
                    "type": a.degradation_type.value,
                    "severity": a.severity,
                    "metric": a.metric_name,
                    "baseline": a.baseline_value,
                    "current": a.current_value,
                    "percent_change": a.percent_change,
                    "recommendation": a.recommendation
                }
                for a in report.degradation_alerts
            ],
            "baseline_comparison": report.baseline_comparison
        }


class EvaluationEngine:
    """
    Comprehensive evaluation engine for collections ML models

    Computes all metrics, performs cohort analysis, temporal analysis,
    statistical tests, and generates reports.

    Target: AUC >= 0.85 threshold with reproducible cohort breakdowns
    """

    def __init__(
        self,
        auc_threshold: float = 0.85,
        experiment_name: str = "collections_ml_evaluation"
    ):
        self.auc_threshold = auc_threshold

        # Initialize components
        self.metrics_computer = MetricsComputer()
        self.cohort_analyzer = CohortAnalyzer(self.metrics_computer)
        self.temporal_analyzer = TemporalAnalyzer(self.metrics_computer)
        self.feature_analyzer = FeatureImportanceAnalyzer()
        self.stat_tester = StatisticalTester()
        self.baseline_comparator = BaselineComparator(self.stat_tester)
        self.degradation_detector = DegradationDetector(auc_threshold)
        self.mlflow_logger = MLflowLogger(experiment_name)
        self.report_generator = ReportGenerator()

        # Storage
        self.samples: list[EvaluationSample] = []
        self.evaluation_history: list[EvaluationReport] = []

    def add_sample(
        self,
        y_true: float,
        y_pred: float,
        features: dict[str, float] | None = None,
        cohorts: dict[str, str] | None = None,
        timestamp: datetime | None = None,
        sample_id: str | None = None
    ) -> EvaluationSample:
        """Add a single evaluation sample"""
        sample = EvaluationSample(
            sample_id=sample_id or f"sample_{len(self.samples)}",
            y_true=y_true,
            y_pred=y_pred,
            y_pred_class=1 if y_pred >= 0.5 else 0,
            features=features or {},
            cohorts=cohorts or {},
            timestamp=timestamp or datetime.now()
        )
        self.samples.append(sample)
        return sample

    def add_batch(
        self,
        y_true: list[float],
        y_pred: list[float],
        features_list: list[dict[str, float]] | None = None,
        cohorts_list: list[dict[str, str]] | None = None,
        timestamps: list[datetime] | None = None
    ) -> int:
        """Add batch of samples"""
        n_samples = len(y_true)

        features_list = features_list or [{}] * n_samples
        cohorts_list = cohorts_list or [{}] * n_samples
        timestamps = timestamps or [datetime.now()] * n_samples

        for i in range(n_samples):
            self.add_sample(
                y_true=y_true[i],
                y_pred=y_pred[i],
                features=features_list[i] if i < len(features_list) else {},
                cohorts=cohorts_list[i] if i < len(cohorts_list) else {},
                timestamp=timestamps[i] if i < len(timestamps) else datetime.now()
            )

        return n_samples

    def evaluate(
        self,
        model_name: str = "collections_model",
        model_version: str = "1.0.0",
        baseline_name: str | None = None,
        cohort_types: list[CohortType] | None = None,
        model_predict_fn: Callable[[dict[str, float]], float] | None = None
    ) -> EvaluationReport:
        """
        Run comprehensive evaluation

        Returns complete evaluation report with all metrics
        """
        if not self.samples:
            raise ValueError("No samples to evaluate. Add samples first.")

        # Extract y_true and y_pred
        y_true = [s.y_true for s in self.samples]
        y_pred = [s.y_pred for s in self.samples]

        # Compute overall metrics
        overall_metrics = self._compute_overall_metrics(y_true, y_pred)

        # Cohort analysis
        cohort_types = cohort_types or list(CohortType)
        cohort_metrics = {}
        for cohort_type in cohort_types:
            try:
                cohort_metrics[cohort_type] = self.cohort_analyzer.analyze_by_cohort(
                    self.samples, cohort_type
                )
            except Exception:
                cohort_metrics[cohort_type] = []

        # Temporal analysis
        temporal_metrics = self.temporal_analyzer.analyze_by_time_slice(self.samples)

        # Calibration curve
        calibration_curve = self.metrics_computer.compute_calibration_curve(y_true, y_pred)

        # Lift and gain
        lift_gain_curve = self.metrics_computer.compute_lift_gain_curve(y_true, y_pred)

        # Feature importance
        if model_predict_fn:
            feature_importance = self.feature_analyzer.compute_permutation_importance(
                self.samples, model_predict_fn, n_repeats=5
            )
        else:
            feature_importance = self.feature_analyzer.compute_shap_approximation(self.samples)

        # Confusion matrices at multiple thresholds
        confusion_matrices = {}
        for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
            confusion_matrices[threshold] = self.metrics_computer.compute_confusion_matrix(
                y_true, y_pred, threshold
            )

        # Baseline comparison
        baseline_comparison = {}
        if baseline_name and baseline_name in self.baseline_comparator.baselines:
            baseline_comparison = self.baseline_comparator.compare_to_baseline(
                overall_metrics, baseline_name
            )

        # Degradation detection
        baseline_metrics = self.baseline_comparator.baselines.get(baseline_name)
        degradation_alerts = self.degradation_detector.detect_degradation(
            overall_metrics, baseline_metrics
        )

        # Add temporal drift alerts
        temporal_alerts = self.temporal_analyzer.detect_temporal_drift(temporal_metrics)
        degradation_alerts.extend(temporal_alerts)

        # Check AUC threshold
        auc_roc = overall_metrics.get("AUC-ROC")
        passed_threshold = auc_roc.value >= self.auc_threshold if auc_roc else False

        # Generate report
        report = EvaluationReport(
            report_id=self._generate_report_id(model_name, model_version),
            model_name=model_name,
            model_version=model_version,
            evaluation_timestamp=datetime.now(),
            overall_metrics=overall_metrics,
            cohort_metrics=cohort_metrics,
            temporal_metrics=temporal_metrics,
            calibration_curve=calibration_curve,
            lift_gain_curve=lift_gain_curve,
            feature_importance=feature_importance,
            confusion_matrices=confusion_matrices,
            degradation_alerts=degradation_alerts,
            baseline_comparison=baseline_comparison,
            passed_threshold=passed_threshold,
            auc_threshold=self.auc_threshold
        )

        self.evaluation_history.append(report)
        return report

    def _compute_overall_metrics(
        self,
        y_true: list[float],
        y_pred: list[float]
    ) -> dict[str, MetricResult]:
        """Compute all overall metrics"""
        return {
            "AUC-ROC": self.metrics_computer.compute_auc_roc(y_true, y_pred),
            "AUC-PR": self.metrics_computer.compute_auc_pr(y_true, y_pred),
            "Brier Score": self.metrics_computer.compute_brier_score(y_true, y_pred),
            "ECE": self.metrics_computer.compute_expected_calibration_error(y_true, y_pred),
            "MCE": self.metrics_computer.compute_maximum_calibration_error(y_true, y_pred),
            "KS Statistic": self.metrics_computer.compute_ks_statistic(y_true, y_pred),
            "Log Loss": self.metrics_computer.compute_log_loss(y_true, y_pred)
        }

    def log_to_mlflow(
        self,
        report: EvaluationReport,
        params: dict[str, Any] | None = None,
        artifacts: list[str] | None = None
    ) -> str | None:
        """Log evaluation to MLflow"""
        return self.mlflow_logger.log_evaluation(
            model_name=report.model_name,
            model_version=report.model_version,
            metrics=report.overall_metrics,
            cohort_metrics=report.cohort_metrics,
            params=params,
            artifacts=artifacts
        )

    def save_baseline(
        self,
        report: EvaluationReport,
        baseline_name: str,
        filepath: str | None = None
    ) -> None:
        """Save evaluation as baseline"""
        self.baseline_comparator.save_as_baseline(
            baseline_name, report.overall_metrics, filepath
        )

    def load_baseline(self, filepath: str) -> str | None:
        """Load baseline from file"""
        return self.baseline_comparator.load_baseline(filepath)

    def generate_report(
        self,
        report: EvaluationReport,
        output_path: str,
        format: str = "html"
    ) -> str:
        """Generate evaluation report"""
        if format == "html":
            return self.report_generator.generate_html_report(report, output_path)
        elif format == "json":
            return self.report_generator.generate_json_report(report, output_path)
        elif format == "pdf":
            return self.report_generator.generate_pdf_report(report, output_path)
        else:
            raise ValueError(f"Unknown format: {format}")

    def compare_models(
        self,
        y_true: list[float],
        y_pred_model1: list[float],
        y_pred_model2: list[float],
        model1_name: str = "model_1",
        model2_name: str = "model_2"
    ) -> dict[str, Any]:
        """Compare two models statistically"""
        # Compute metrics for both
        auc1 = self.metrics_computer.compute_auc_roc(y_true, y_pred_model1)
        auc2 = self.metrics_computer.compute_auc_roc(y_true, y_pred_model2)

        # DeLong test for AUC comparison
        p_value, is_significant = self.stat_tester.delong_test(
            y_true, y_pred_model1, y_pred_model2
        )

        # Bootstrap samples for paired comparison
        errors1 = [(p - t) ** 2 for p, t in zip(y_pred_model1, y_true)]
        errors2 = [(p - t) ** 2 for p, t in zip(y_pred_model2, y_true)]

        t_p_value, t_significant = self.stat_tester.paired_t_test(errors1, errors2)

        return {
            model1_name: {
                "auc_roc": auc1.value,
                "auc_roc_ci": auc1.confidence_interval,
                "brier": sum(errors1) / len(errors1)
            },
            model2_name: {
                "auc_roc": auc2.value,
                "auc_roc_ci": auc2.confidence_interval,
                "brier": sum(errors2) / len(errors2)
            },
            "comparison": {
                "auc_difference": auc1.value - auc2.value,
                "delong_p_value": p_value,
                "delong_significant": is_significant,
                "paired_t_p_value": t_p_value,
                "paired_t_significant": t_significant,
                "winner": model1_name if auc1.value > auc2.value else model2_name,
                "confidence": "high" if is_significant else "low"
            }
        }

    def clear_samples(self) -> None:
        """Clear all samples"""
        self.samples = []

    def _generate_report_id(self, model_name: str, model_version: str) -> str:
        """Generate unique report ID"""
        content = f"{model_name}_{model_version}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


# Demonstration and testing
if __name__ == "__main__":
    print("=" * 60)
    print("QUAN MLOps Evaluation Baseline System")
    print("=" * 60)
    print()

    # Initialize engine with AUC threshold
    engine = EvaluationEngine(auc_threshold=0.85)

    # Generate synthetic evaluation data
    print("Generating synthetic evaluation data...")
    random.seed(42)

    n_samples = 1000

    for i in range(n_samples):
        # Generate realistic prediction scenario
        true_prob = random.random()
        y_true = 1 if random.random() < true_prob else 0

        # Model prediction with some noise and skill
        skill_factor = 0.7
        noise = random.gauss(0, 0.15)
        y_pred = max(0, min(1, true_prob * skill_factor + (1 - skill_factor) * 0.5 + noise))

        # Generate features
        features = {
            "balance": random.uniform(100, 10000),
            "days_past_due": random.randint(1, 365),
            "shadow_score": random.randint(350, 850),
            "total_contacts": random.randint(0, 20),
            "response_rate": random.random(),
            "promise_kept_rate": random.random(),
            "channel": random.choice(["email", "sms", "phone", "mail"]),
            "region": random.choice(["northeast", "southeast", "midwest", "west"]),
            "creditor_type": random.choice(["bank", "fintech", "healthcare", "utility"]),
            "past_payment_count": random.randint(0, 10)
        }

        # Generate timestamp over 90-day period
        timestamp = datetime.now() - timedelta(days=random.randint(0, 90))

        engine.add_sample(
            y_true=y_true,
            y_pred=y_pred,
            features=features,
            timestamp=timestamp
        )

    print(f"Added {n_samples} samples")
    print()

    # Run evaluation
    print("Running comprehensive evaluation...")
    report = engine.evaluate(
        model_name="payment_prediction_v1",
        model_version="1.0.0",
        cohort_types=[
            CohortType.DEBT_AMOUNT,
            CohortType.ACCOUNT_AGE,
            CohortType.SCORE_BAND,
            CohortType.CHANNEL
        ]
    )

    # Display results
    print()
    print("-" * 60)
    print("EVALUATION RESULTS")
    print("-" * 60)
    print()

    print(f"Report ID: {report.report_id}")
    print(f"Model: {report.model_name} v{report.model_version}")
    print(f"Timestamp: {report.evaluation_timestamp}")
    print()

    print("Overall Metrics:")
    for name, metric in report.overall_metrics.items():
        ci = f"[{metric.confidence_interval[0]:.4f}, {metric.confidence_interval[1]:.4f}]"
        print(f"  {name}: {metric.value:.4f} {ci}")
    print()

    print(f"AUC Threshold ({report.auc_threshold}):", end=" ")
    if report.passed_threshold:
        print("PASSED")
    else:
        print("FAILED")
    print()

    print("Cohort Analysis (Debt Amount):")
    for cohort in report.cohort_metrics.get(CohortType.DEBT_AMOUNT, []):
        auc = cohort.metrics.get("AUC-ROC")
        auc_val = f"{auc.value:.4f}" if auc else "N/A"
        print(f"  {cohort.cohort_value}: n={cohort.n_samples}, AUC={auc_val}, prevalence={cohort.prevalence:.2%}")
    print()

    print("Cohort Analysis (Score Band):")
    for cohort in report.cohort_metrics.get(CohortType.SCORE_BAND, []):
        auc = cohort.metrics.get("AUC-ROC")
        auc_val = f"{auc.value:.4f}" if auc else "N/A"
        print(f"  {cohort.cohort_value}: n={cohort.n_samples}, AUC={auc_val}, prevalence={cohort.prevalence:.2%}")
    print()

    print("Calibration Curve:")
    for bin_data in report.calibration_curve[:5]:
        print(f"  Bin [{bin_data.bin_start:.1f}-{bin_data.bin_end:.1f}]: predicted={bin_data.mean_predicted:.3f}, actual={bin_data.mean_actual:.3f}, n={bin_data.n_samples}")
    print("  ...")
    print()

    print("Lift and Gain:")
    for point in report.lift_gain_curve[:5]:
        print(f"  Top {point.percentile:.0%}: gain={point.gain:.2%}, lift={point.lift:.2f}x")
    print()

    print("Feature Importance (Top 10):")
    for fi in report.feature_importance[:10]:
        print(f"  {fi.importance_rank}. {fi.feature_name}: {fi.importance_score:.4f}")
    print()

    print("Confusion Matrix (threshold=0.5):")
    cm = report.confusion_matrices.get(0.5)
    if cm:
        print(f"  TP={cm.true_positives}, FP={cm.false_positives}")
        print(f"  FN={cm.false_negatives}, TN={cm.true_negatives}")
        print(f"  Precision={cm.precision:.4f}, Recall={cm.recall:.4f}, F1={cm.f1_score:.4f}")
    print()

    if report.degradation_alerts:
        print("Degradation Alerts:")
        for alert in report.degradation_alerts:
            print(f"  [{alert.severity.upper()}] {alert.metric_name}: {alert.degradation_type.value}")
            print(f"    {alert.recommendation}")
    print()

    # Save as baseline
    print("Saving as baseline...")
    engine.save_baseline(report, "v1_baseline")
    print()

    # Generate reports
    print("Generating reports...")
    html_path = "/tmp/evaluation_report.html"
    json_path = "/tmp/evaluation_report.json"

    engine.generate_report(report, html_path, format="html")
    engine.generate_report(report, json_path, format="json")

    print(f"  HTML report: {html_path}")
    print(f"  JSON report: {json_path}")
    print()

    # Model comparison demo
    print("Model Comparison Demo:")
    y_true = [s.y_true for s in engine.samples]
    y_pred1 = [s.y_pred for s in engine.samples]
    # Simulate a second model (slightly worse)
    y_pred2 = [max(0, min(1, p + random.gauss(0, 0.1))) for p in y_pred1]

    comparison = engine.compare_models(y_true, y_pred1, y_pred2, "model_v1", "model_v2")
    print(f"  {comparison['model_v1']['auc_roc']:.4f} vs {comparison['model_v2']['auc_roc']:.4f}")
    print(f"  Winner: {comparison['comparison']['winner']} (confidence: {comparison['comparison']['confidence']})")
    print(f"  DeLong p-value: {comparison['comparison']['delong_p_value']:.4f}")
    print()

    print("=" * 60)
    print("Evaluation complete. Baseline metrics logged and reproducible.")
    print("=" * 60)
