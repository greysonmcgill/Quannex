"""
Fairness and Bias Audit Framework for ML Models

Comprehensive framework for detecting, measuring, and mitigating bias in ML models
used for collections and credit decisioning.

Key Metrics Implemented:
- Demographic Parity Difference (DPD)
- Equal Opportunity Difference (EOD)
- Disparate Impact Ratio (DIR) - threshold > 0.8
- Equalized Odds
- Calibration Error across groups

Mitigation Strategies:
- Pre-processing: Reweighing
- In-processing: Adversarial debiasing hooks
- Post-processing: Threshold optimization, calibration adjustment

Compliance Standards:
- ECOA (Equal Credit Opportunity Act)
- FCRA (Fair Credit Reporting Act)
- State-level fair lending requirements
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Optional
import math
import logging
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# ==============================================================================
# CONSTANTS AND THRESHOLDS
# ==============================================================================

# Documented regulatory and industry thresholds
FAIRNESS_THRESHOLDS = {
    "disparate_impact_ratio": {
        "threshold": 0.8,
        "description": "Four-fifths rule: favorable outcome rate for protected class "
                       "must be at least 80% of favorable rate for reference class",
        "regulatory_source": "EEOC Uniform Guidelines, adapted for lending"
    },
    "demographic_parity_difference": {
        "threshold": 0.1,
        "description": "Absolute difference in positive outcome rates between groups "
                       "should not exceed 10%",
        "regulatory_source": "Industry best practice"
    },
    "equal_opportunity_difference": {
        "threshold": 0.1,
        "description": "Difference in true positive rates between groups should not "
                       "exceed 10%",
        "regulatory_source": "Academic fairness standards"
    },
    "equalized_odds_difference": {
        "threshold": 0.1,
        "description": "Maximum of TPR and FPR differences should not exceed 10%",
        "regulatory_source": "Hardt et al. 2016"
    },
    "calibration_error": {
        "threshold": 0.05,
        "description": "Calibration error per group should not exceed 5%",
        "regulatory_source": "Model risk management guidelines"
    }
}


class ProtectedAttribute(Enum):
    """Protected attributes under fair lending laws"""
    RACE = "race"
    ETHNICITY = "ethnicity"
    GENDER = "gender"
    AGE = "age"
    NATIONAL_ORIGIN = "national_origin"
    MARITAL_STATUS = "marital_status"
    RELIGION = "religion"
    DISABILITY_STATUS = "disability_status"
    FAMILIAL_STATUS = "familial_status"
    MILITARY_STATUS = "military_status"
    # Proxy attributes that may correlate with protected classes
    ZIP_CODE = "zip_code"
    LANGUAGE = "language"


class BiasType(Enum):
    """Types of algorithmic bias"""
    HISTORICAL = auto()  # Bias from historical data patterns
    REPRESENTATION = auto()  # Underrepresentation in training data
    MEASUREMENT = auto()  # Bias in feature measurement
    AGGREGATION = auto()  # One-size-fits-all model bias
    EVALUATION = auto()  # Bias in evaluation metrics
    DEPLOYMENT = auto()  # Bias emerging in deployment


class MitigationStrategy(Enum):
    """Bias mitigation strategies"""
    REWEIGHING = "reweighing"
    DISPARATE_IMPACT_REMOVER = "disparate_impact_remover"
    ADVERSARIAL_DEBIASING = "adversarial_debiasing"
    CALIBRATED_EQUALIZED_ODDS = "calibrated_equalized_odds"
    THRESHOLD_OPTIMIZER = "threshold_optimizer"
    REJECT_OPTION_CLASSIFICATION = "reject_option_classification"


class FairnessMetricType(Enum):
    """Types of fairness metrics"""
    DEMOGRAPHIC_PARITY = "demographic_parity"
    EQUAL_OPPORTUNITY = "equal_opportunity"
    EQUALIZED_ODDS = "equalized_odds"
    DISPARATE_IMPACT = "disparate_impact"
    CALIBRATION = "calibration"
    PREDICTIVE_PARITY = "predictive_parity"
    INDIVIDUAL_FAIRNESS = "individual_fairness"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class GroupStatistics:
    """Statistics for a demographic group"""
    group_name: str
    total_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    true_positive: int = 0
    true_negative: int = 0
    false_positive: int = 0
    false_negative: int = 0
    sum_predictions: float = 0.0
    sum_positive_predictions: float = 0.0

    @property
    def positive_rate(self) -> float:
        """Proportion of positive outcomes"""
        return self.positive_count / self.total_count if self.total_count > 0 else 0.0

    @property
    def true_positive_rate(self) -> float:
        """TPR = TP / (TP + FN) - Sensitivity/Recall"""
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FPR = FP / (FP + TN)"""
        denominator = self.false_positive + self.true_negative
        return self.false_positive / denominator if denominator > 0 else 0.0

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator > 0 else 0.0

    @property
    def predicted_positive_rate(self) -> float:
        """Rate of positive predictions"""
        return (self.true_positive + self.false_positive) / self.total_count if self.total_count > 0 else 0.0

    @property
    def avg_prediction(self) -> float:
        """Average prediction score"""
        return self.sum_predictions / self.total_count if self.total_count > 0 else 0.0

    @property
    def calibration_error(self) -> float:
        """Difference between avg prediction and actual positive rate"""
        return abs(self.avg_prediction - self.positive_rate)


@dataclass
class FairnessMetric:
    """Single fairness metric result"""
    metric_type: FairnessMetricType
    value: float
    threshold: float
    passes_threshold: bool
    reference_group: str
    comparison_group: str
    description: str
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    sample_size: int = 0


@dataclass
class BiasAlert:
    """Alert for detected bias"""
    alert_id: str
    severity: str  # "critical", "high", "medium", "low"
    bias_type: BiasType
    affected_attribute: ProtectedAttribute
    metric_name: str
    metric_value: float
    threshold: float
    affected_groups: list[str]
    description: str
    recommended_actions: list[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MitigationResult:
    """Result of applying mitigation strategy"""
    strategy: MitigationStrategy
    original_metrics: dict[str, float]
    mitigated_metrics: dict[str, float]
    improvement: dict[str, float]
    side_effects: dict[str, float]  # Impact on overall performance
    parameters_used: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FairnessReport:
    """Comprehensive fairness audit report"""
    report_id: str
    model_name: str
    model_version: str
    audit_timestamp: datetime
    dataset_size: int
    protected_attributes_analyzed: list[str]
    metrics: list[FairnessMetric]
    alerts: list[BiasAlert]
    overall_fairness_score: float
    passes_audit: bool
    mitigation_recommendations: list[dict[str, Any]]
    executive_summary: str
    detailed_findings: dict[str, Any]


# ==============================================================================
# SENSITIVE FEATURE IDENTIFICATION
# ==============================================================================

class SensitiveFeatureDetector:
    """
    Identifies potentially sensitive features that may correlate with protected attributes
    """

    # Features known to be proxies for protected attributes
    KNOWN_PROXIES = {
        ProtectedAttribute.RACE: [
            "zip_code", "postal_code", "neighborhood", "census_tract",
            "school_district", "first_name", "last_name", "surname"
        ],
        ProtectedAttribute.GENDER: [
            "first_name", "title", "prefix", "occupation"
        ],
        ProtectedAttribute.AGE: [
            "years_at_address", "years_employed", "graduation_year",
            "account_age", "credit_history_length"
        ],
        ProtectedAttribute.NATIONAL_ORIGIN: [
            "language_preference", "country_code", "area_code", "surname"
        ]
    }

    # Suspicious feature name patterns
    SUSPICIOUS_PATTERNS = [
        "race", "ethnic", "gender", "sex", "age", "religion", "national",
        "marital", "married", "spouse", "pregnant", "disability", "military",
        "veteran", "zip", "postal", "neighborhood"
    ]

    def __init__(self):
        self.detected_sensitive: dict[str, list[ProtectedAttribute]] = {}
        self.proxy_correlations: dict[str, dict[str, float]] = {}

    def detect_sensitive_features(
        self,
        feature_names: list[str]
    ) -> dict[str, list[ProtectedAttribute]]:
        """
        Detect potentially sensitive features from feature names

        Args:
            feature_names: List of feature names to analyze

        Returns:
            Dictionary mapping feature names to potential protected attributes
        """
        sensitive_mapping = {}

        for feature in feature_names:
            feature_lower = feature.lower()
            related_attributes = []

            # Check against known proxies
            for attr, proxies in self.KNOWN_PROXIES.items():
                if any(proxy in feature_lower for proxy in proxies):
                    related_attributes.append(attr)

            # Check suspicious patterns
            for pattern in self.SUSPICIOUS_PATTERNS:
                if pattern in feature_lower:
                    # Try to map to specific protected attribute
                    if "race" in feature_lower or "ethnic" in feature_lower:
                        if ProtectedAttribute.RACE not in related_attributes:
                            related_attributes.append(ProtectedAttribute.RACE)
                    elif "gender" in feature_lower or "sex" in feature_lower:
                        if ProtectedAttribute.GENDER not in related_attributes:
                            related_attributes.append(ProtectedAttribute.GENDER)
                    elif "age" in feature_lower:
                        if ProtectedAttribute.AGE not in related_attributes:
                            related_attributes.append(ProtectedAttribute.AGE)

            if related_attributes:
                sensitive_mapping[feature] = related_attributes

        self.detected_sensitive = sensitive_mapping
        return sensitive_mapping

    def compute_proxy_correlation(
        self,
        feature_data: dict[str, list[float]],
        protected_attribute_data: dict[str, list[int]]
    ) -> dict[str, dict[str, float]]:
        """
        Compute correlation between features and protected attributes

        Args:
            feature_data: Feature values by feature name
            protected_attribute_data: Protected attribute values by attribute name

        Returns:
            Correlation matrix between features and protected attributes
        """
        correlations = {}

        for feature_name, feature_values in feature_data.items():
            correlations[feature_name] = {}

            for attr_name, attr_values in protected_attribute_data.items():
                if len(feature_values) == len(attr_values):
                    corr = self._pearson_correlation(feature_values, attr_values)
                    correlations[feature_name][attr_name] = corr

        self.proxy_correlations = correlations
        return correlations

    def _pearson_correlation(self, x: list[float], y: list[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        n = len(x)
        if n == 0:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))

        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        denominator = math.sqrt(var_x * var_y)

        return numerator / denominator if denominator > 0 else 0.0

    def get_high_correlation_features(
        self,
        threshold: float = 0.3
    ) -> list[tuple[str, str, float]]:
        """Get features with high correlation to protected attributes"""
        high_corr = []

        for feature, attr_corrs in self.proxy_correlations.items():
            for attr, corr in attr_corrs.items():
                if abs(corr) >= threshold:
                    high_corr.append((feature, attr, corr))

        return sorted(high_corr, key=lambda x: abs(x[2]), reverse=True)


# ==============================================================================
# FAIRNESS METRICS CALCULATOR
# ==============================================================================

class FairnessMetricsCalculator:
    """
    Calculates all fairness metrics for model evaluation
    """

    def __init__(self):
        self.group_stats: dict[str, GroupStatistics] = {}
        self.reference_group: Optional[str] = None

    def compute_group_statistics(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        threshold: float = 0.5
    ) -> dict[str, GroupStatistics]:
        """
        Compute statistics for each demographic group

        Args:
            predictions: Model prediction scores (0-1)
            actuals: Actual outcomes (0 or 1)
            group_labels: Group label for each sample
            threshold: Classification threshold

        Returns:
            Statistics for each group
        """
        self.group_stats = {}

        for pred, actual, group in zip(predictions, actuals, group_labels):
            if group not in self.group_stats:
                self.group_stats[group] = GroupStatistics(group_name=group)

            stats = self.group_stats[group]
            stats.total_count += 1
            stats.sum_predictions += pred

            predicted_class = 1 if pred >= threshold else 0

            if actual == 1:
                stats.positive_count += 1
                stats.sum_positive_predictions += pred
                if predicted_class == 1:
                    stats.true_positive += 1
                else:
                    stats.false_negative += 1
            else:
                stats.negative_count += 1
                if predicted_class == 1:
                    stats.false_positive += 1
                else:
                    stats.true_negative += 1

        # Set reference group as the largest group
        if self.group_stats:
            self.reference_group = max(
                self.group_stats.keys(),
                key=lambda g: self.group_stats[g].total_count
            )

        return self.group_stats

    def demographic_parity_difference(
        self,
        group_a: str,
        group_b: str
    ) -> FairnessMetric:
        """
        Calculate Demographic Parity Difference

        DPD = P(Y_hat=1|A=a) - P(Y_hat=1|A=b)

        Measures whether positive prediction rates are equal across groups
        """
        stats_a = self.group_stats.get(group_a)
        stats_b = self.group_stats.get(group_b)

        if not stats_a or not stats_b:
            raise ValueError(f"Groups not found: {group_a}, {group_b}")

        rate_a = stats_a.predicted_positive_rate
        rate_b = stats_b.predicted_positive_rate

        dpd = rate_a - rate_b
        threshold = FAIRNESS_THRESHOLDS["demographic_parity_difference"]["threshold"]

        # Bootstrap confidence interval approximation
        n = min(stats_a.total_count, stats_b.total_count)
        se = math.sqrt(rate_a * (1 - rate_a) / stats_a.total_count +
                       rate_b * (1 - rate_b) / stats_b.total_count) if n > 0 else 0
        ci = (dpd - 1.96 * se, dpd + 1.96 * se)

        return FairnessMetric(
            metric_type=FairnessMetricType.DEMOGRAPHIC_PARITY,
            value=dpd,
            threshold=threshold,
            passes_threshold=abs(dpd) <= threshold,
            reference_group=group_a,
            comparison_group=group_b,
            description=f"Difference in positive prediction rates: {rate_a:.3f} vs {rate_b:.3f}",
            confidence_interval=ci,
            sample_size=stats_a.total_count + stats_b.total_count
        )

    def equal_opportunity_difference(
        self,
        group_a: str,
        group_b: str
    ) -> FairnessMetric:
        """
        Calculate Equal Opportunity Difference

        EOD = TPR_a - TPR_b

        Measures whether true positive rates are equal across groups
        (among those who should receive positive outcome)
        """
        stats_a = self.group_stats.get(group_a)
        stats_b = self.group_stats.get(group_b)

        if not stats_a or not stats_b:
            raise ValueError(f"Groups not found: {group_a}, {group_b}")

        tpr_a = stats_a.true_positive_rate
        tpr_b = stats_b.true_positive_rate

        eod = tpr_a - tpr_b
        threshold = FAIRNESS_THRESHOLDS["equal_opportunity_difference"]["threshold"]

        # Confidence interval
        n_a = stats_a.positive_count
        n_b = stats_b.positive_count
        se = math.sqrt(tpr_a * (1 - tpr_a) / max(n_a, 1) +
                       tpr_b * (1 - tpr_b) / max(n_b, 1))
        ci = (eod - 1.96 * se, eod + 1.96 * se)

        return FairnessMetric(
            metric_type=FairnessMetricType.EQUAL_OPPORTUNITY,
            value=eod,
            threshold=threshold,
            passes_threshold=abs(eod) <= threshold,
            reference_group=group_a,
            comparison_group=group_b,
            description=f"Difference in true positive rates: {tpr_a:.3f} vs {tpr_b:.3f}",
            confidence_interval=ci,
            sample_size=n_a + n_b
        )

    def disparate_impact_ratio(
        self,
        protected_group: str,
        reference_group: str
    ) -> FairnessMetric:
        """
        Calculate Disparate Impact Ratio (Four-Fifths Rule)

        DIR = P(Y_hat=1|A=protected) / P(Y_hat=1|A=reference)

        Threshold: DIR >= 0.8 (80% rule)

        IMPORTANT: Ratio below 0.8 indicates potential adverse impact
        """
        stats_protected = self.group_stats.get(protected_group)
        stats_reference = self.group_stats.get(reference_group)

        if not stats_protected or not stats_reference:
            raise ValueError(f"Groups not found: {protected_group}, {reference_group}")

        rate_protected = stats_protected.predicted_positive_rate
        rate_reference = stats_reference.predicted_positive_rate

        # Avoid division by zero
        if rate_reference == 0:
            dir_value = 1.0 if rate_protected == 0 else float('inf')
        else:
            dir_value = rate_protected / rate_reference

        threshold = FAIRNESS_THRESHOLDS["disparate_impact_ratio"]["threshold"]

        return FairnessMetric(
            metric_type=FairnessMetricType.DISPARATE_IMPACT,
            value=dir_value,
            threshold=threshold,
            passes_threshold=dir_value >= threshold,
            reference_group=reference_group,
            comparison_group=protected_group,
            description=f"Disparate Impact Ratio: {dir_value:.3f} "
                       f"(Protected rate: {rate_protected:.3f}, Reference rate: {rate_reference:.3f})",
            sample_size=stats_protected.total_count + stats_reference.total_count
        )

    def equalized_odds_assessment(
        self,
        group_a: str,
        group_b: str
    ) -> tuple[FairnessMetric, FairnessMetric]:
        """
        Assess Equalized Odds

        Requires both:
        1. Equal TPR across groups (Equal Opportunity)
        2. Equal FPR across groups

        Returns tuple of (TPR metric, FPR metric)
        """
        stats_a = self.group_stats.get(group_a)
        stats_b = self.group_stats.get(group_b)

        if not stats_a or not stats_b:
            raise ValueError(f"Groups not found: {group_a}, {group_b}")

        # TPR comparison
        tpr_diff = stats_a.true_positive_rate - stats_b.true_positive_rate
        threshold = FAIRNESS_THRESHOLDS["equalized_odds_difference"]["threshold"]

        tpr_metric = FairnessMetric(
            metric_type=FairnessMetricType.EQUALIZED_ODDS,
            value=tpr_diff,
            threshold=threshold,
            passes_threshold=abs(tpr_diff) <= threshold,
            reference_group=group_a,
            comparison_group=group_b,
            description=f"TPR difference: {stats_a.true_positive_rate:.3f} vs {stats_b.true_positive_rate:.3f}",
            sample_size=stats_a.positive_count + stats_b.positive_count
        )

        # FPR comparison
        fpr_diff = stats_a.false_positive_rate - stats_b.false_positive_rate

        fpr_metric = FairnessMetric(
            metric_type=FairnessMetricType.EQUALIZED_ODDS,
            value=fpr_diff,
            threshold=threshold,
            passes_threshold=abs(fpr_diff) <= threshold,
            reference_group=group_a,
            comparison_group=group_b,
            description=f"FPR difference: {stats_a.false_positive_rate:.3f} vs {stats_b.false_positive_rate:.3f}",
            sample_size=stats_a.negative_count + stats_b.negative_count
        )

        return tpr_metric, fpr_metric

    def calibration_across_groups(self) -> dict[str, FairnessMetric]:
        """
        Assess calibration (reliability) across groups

        Calibration: P(Y=1|score=s) should be approximately s for all groups

        Returns calibration error metric for each group
        """
        calibration_metrics = {}
        threshold = FAIRNESS_THRESHOLDS["calibration_error"]["threshold"]

        for group_name, stats in self.group_stats.items():
            cal_error = stats.calibration_error

            calibration_metrics[group_name] = FairnessMetric(
                metric_type=FairnessMetricType.CALIBRATION,
                value=cal_error,
                threshold=threshold,
                passes_threshold=cal_error <= threshold,
                reference_group=group_name,
                comparison_group="ideal_calibration",
                description=f"Calibration error for {group_name}: avg_pred={stats.avg_prediction:.3f}, "
                           f"actual_rate={stats.positive_rate:.3f}",
                sample_size=stats.total_count
            )

        return calibration_metrics


# ==============================================================================
# MITIGATION STRATEGIES
# ==============================================================================

class ReweighingMitigation:
    """
    Pre-processing mitigation: Reweighing

    Adjusts sample weights to achieve demographic parity in training data
    """

    def __init__(self):
        self.weights: dict[tuple[str, int], float] = {}

    def compute_weights(
        self,
        group_labels: list[str],
        outcomes: list[int]
    ) -> list[float]:
        """
        Compute reweighing weights to balance outcomes across groups

        Args:
            group_labels: Group label for each sample
            outcomes: Outcome (0 or 1) for each sample

        Returns:
            Weight for each sample
        """
        n = len(group_labels)

        # Count by group and outcome
        counts: dict[str, dict[int, int]] = defaultdict(lambda: {0: 0, 1: 0})
        for group, outcome in zip(group_labels, outcomes):
            counts[group][outcome] += 1

        # Calculate expected vs observed probabilities
        total_positive = sum(outcomes)
        total_negative = n - total_positive
        p_positive = total_positive / n if n > 0 else 0.5

        # Calculate weights
        weights = []
        for group, outcome in zip(group_labels, outcomes):
            group_total = counts[group][0] + counts[group][1]
            p_group = group_total / n if n > 0 else 0.5
            p_outcome_given_group = counts[group][outcome] / group_total if group_total > 0 else 0.5

            # Expected probability
            p_outcome = p_positive if outcome == 1 else (1 - p_positive)

            # Weight = P(outcome) * P(group) / P(outcome, group)
            p_outcome_and_group = counts[group][outcome] / n if n > 0 else 0.5

            if p_outcome_and_group > 0:
                weight = (p_outcome * p_group) / p_outcome_and_group
            else:
                weight = 1.0

            weights.append(weight)
            self.weights[(group, outcome)] = weight

        return weights

    def get_weight(self, group: str, outcome: int) -> float:
        """Get precomputed weight for group/outcome combination"""
        return self.weights.get((group, outcome), 1.0)


class ThresholdOptimizer:
    """
    Post-processing mitigation: Group-specific threshold optimization

    Finds optimal classification thresholds per group to achieve fairness
    while maximizing overall performance
    """

    def __init__(self, fairness_metric: FairnessMetricType = FairnessMetricType.DEMOGRAPHIC_PARITY):
        self.fairness_metric = fairness_metric
        self.group_thresholds: dict[str, float] = {}
        self.optimization_history: list[dict[str, Any]] = []

    def optimize_thresholds(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        fairness_weight: float = 0.5,
        search_granularity: int = 20
    ) -> dict[str, float]:
        """
        Find optimal thresholds for each group

        Args:
            predictions: Model prediction scores
            actuals: Actual outcomes
            group_labels: Group labels
            fairness_weight: Weight for fairness vs accuracy (0-1)
            search_granularity: Number of threshold values to try

        Returns:
            Optimal threshold for each group
        """
        groups = list(set(group_labels))
        best_thresholds = {g: 0.5 for g in groups}
        best_score = float('-inf')

        # Grid search over threshold combinations
        threshold_values = [i / search_granularity for i in range(1, search_granularity)]

        # For efficiency, optimize each group sequentially
        for target_group in groups:
            group_best_threshold = 0.5
            group_best_score = float('-inf')

            for threshold in threshold_values:
                test_thresholds = best_thresholds.copy()
                test_thresholds[target_group] = threshold

                # Calculate combined score
                accuracy = self._calculate_accuracy(
                    predictions, actuals, group_labels, test_thresholds
                )
                fairness = self._calculate_fairness(
                    predictions, actuals, group_labels, test_thresholds
                )

                combined_score = (1 - fairness_weight) * accuracy + fairness_weight * fairness

                if combined_score > group_best_score:
                    group_best_score = combined_score
                    group_best_threshold = threshold

            best_thresholds[target_group] = group_best_threshold

        self.group_thresholds = best_thresholds
        return best_thresholds

    def _calculate_accuracy(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        thresholds: dict[str, float]
    ) -> float:
        """Calculate overall accuracy with group-specific thresholds"""
        correct = 0
        for pred, actual, group in zip(predictions, actuals, group_labels):
            threshold = thresholds.get(group, 0.5)
            predicted_class = 1 if pred >= threshold else 0
            if predicted_class == actual:
                correct += 1
        return correct / len(predictions) if predictions else 0

    def _calculate_fairness(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        thresholds: dict[str, float]
    ) -> float:
        """Calculate fairness score (1 = perfectly fair, 0 = maximally unfair)"""
        # Calculate positive rates per group
        group_positive_rates: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

        for pred, actual, group in zip(predictions, actuals, group_labels):
            threshold = thresholds.get(group, 0.5)
            predicted_positive = 1 if pred >= threshold else 0
            current = group_positive_rates[group]
            group_positive_rates[group] = (current[0] + predicted_positive, current[1] + 1)

        rates = [pos / total if total > 0 else 0
                 for pos, total in group_positive_rates.values()]

        if not rates:
            return 1.0

        # Fairness as inverse of rate variance
        mean_rate = sum(rates) / len(rates)
        variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)

        # Convert to 0-1 score (lower variance = higher fairness)
        return 1 / (1 + variance * 10)

    def apply_thresholds(
        self,
        predictions: list[float],
        group_labels: list[str]
    ) -> list[int]:
        """Apply optimized thresholds to get predictions"""
        return [
            1 if pred >= self.group_thresholds.get(group, 0.5) else 0
            for pred, group in zip(predictions, group_labels)
        ]


class CalibratedEqualizedOddsMitigation:
    """
    Post-processing: Calibrated Equalized Odds

    Adjusts predictions to achieve equalized odds while maintaining calibration
    """

    def __init__(self):
        self.group_adjustments: dict[str, tuple[float, float]] = {}

    def fit(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        reference_group: str
    ) -> None:
        """
        Learn adjustment parameters

        Args:
            predictions: Model predictions
            actuals: Actual outcomes
            group_labels: Group labels
            reference_group: Reference group for equalization
        """
        # Calculate TPR and FPR for reference group
        calc = FairnessMetricsCalculator()
        calc.compute_group_statistics(predictions, actuals, group_labels)

        ref_stats = calc.group_stats[reference_group]
        ref_tpr = ref_stats.true_positive_rate
        ref_fpr = ref_stats.false_positive_rate

        # Calculate adjustments for each group
        for group, stats in calc.group_stats.items():
            if group == reference_group:
                self.group_adjustments[group] = (1.0, 0.0)  # No adjustment
            else:
                # Calculate scaling to match TPR and FPR
                tpr_scale = ref_tpr / stats.true_positive_rate if stats.true_positive_rate > 0 else 1.0
                fpr_scale = ref_fpr / stats.false_positive_rate if stats.false_positive_rate > 0 else 1.0

                # Average adjustment (simplified)
                scale = (tpr_scale + fpr_scale) / 2
                scale = max(0.5, min(2.0, scale))  # Bound adjustments

                self.group_adjustments[group] = (scale, 0.0)

    def transform(
        self,
        predictions: list[float],
        group_labels: list[str]
    ) -> list[float]:
        """Apply calibrated adjustments to predictions"""
        adjusted = []
        for pred, group in zip(predictions, group_labels):
            scale, offset = self.group_adjustments.get(group, (1.0, 0.0))
            adj_pred = pred * scale + offset
            adj_pred = max(0.0, min(1.0, adj_pred))  # Bound to [0, 1]
            adjusted.append(adj_pred)
        return adjusted


class AdversarialDebiasingHooks:
    """
    Hooks for adversarial debiasing during model training

    Provides callbacks and loss modifications for in-processing debiasing
    """

    def __init__(self, protected_attributes: list[str], adversary_weight: float = 1.0):
        self.protected_attributes = protected_attributes
        self.adversary_weight = adversary_weight
        self.hooks: dict[str, Callable] = {}
        self._setup_hooks()

    def _setup_hooks(self) -> None:
        """Setup debiasing hooks"""
        self.hooks = {
            "pre_forward": self._pre_forward_hook,
            "loss_modifier": self._adversarial_loss_modifier,
            "gradient_reversal": self._gradient_reversal_hook,
            "post_backward": self._post_backward_hook
        }

    def _pre_forward_hook(self, model_input: dict[str, Any]) -> dict[str, Any]:
        """Hook called before forward pass - can mask sensitive features"""
        # Mask protected attributes from main model input
        masked_input = model_input.copy()
        for attr in self.protected_attributes:
            if attr in masked_input:
                del masked_input[attr]
        return masked_input

    def _adversarial_loss_modifier(
        self,
        main_loss: float,
        adversary_predictions: list[float],
        protected_labels: list[int]
    ) -> float:
        """
        Modify loss to include adversarial component

        Total Loss = Main Loss - adversary_weight * Adversary Loss

        Adversary tries to predict protected attribute from representations
        Main model tries to fool adversary (maximize adversary loss)
        """
        # Calculate adversary loss (binary cross-entropy)
        eps = 1e-15
        adversary_loss = -sum(
            label * math.log(max(pred, eps)) + (1 - label) * math.log(max(1 - pred, eps))
            for pred, label in zip(adversary_predictions, protected_labels)
        ) / len(protected_labels) if protected_labels else 0

        # Subtract adversary loss (gradient reversal effect)
        modified_loss = main_loss - self.adversary_weight * adversary_loss

        return modified_loss

    def _gradient_reversal_hook(self, gradient: Any) -> Any:
        """
        Gradient reversal layer hook

        During backprop, reverses gradients flowing to representation layer
        from adversary, causing model to learn representations that don't
        contain protected attribute information
        """
        # In actual implementation, this would multiply gradient by -1
        # Here we return a flag indicating reversal should be applied
        return {"reverse": True, "original_gradient": gradient}

    def _post_backward_hook(self, model_state: dict[str, Any]) -> None:
        """Hook called after backward pass"""
        # Log debiasing metrics
        logger.debug(f"Adversarial debiasing step completed")

    def get_adversary_architecture(self, representation_dim: int) -> dict[str, Any]:
        """
        Get recommended adversary network architecture

        Returns configuration for adversary that predicts protected attributes
        """
        return {
            "type": "feedforward",
            "layers": [
                {"dim": representation_dim, "activation": "relu"},
                {"dim": 64, "activation": "relu"},
                {"dim": 32, "activation": "relu"},
                {"dim": len(self.protected_attributes), "activation": "sigmoid"}
            ],
            "dropout": 0.3,
            "optimizer": "adam",
            "learning_rate": 0.001
        }


# ==============================================================================
# PERFORMANCE GAP DETECTION
# ==============================================================================

class PerformanceGapDetector:
    """
    Detects significant performance gaps across demographic cohorts
    """

    def __init__(self, significance_threshold: float = 0.05):
        self.significance_threshold = significance_threshold
        self.gaps: list[dict[str, Any]] = []

    def detect_gaps(
        self,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        metrics: list[str] = None
    ) -> list[dict[str, Any]]:
        """
        Detect performance gaps across groups

        Args:
            predictions: Model predictions
            actuals: Actual outcomes
            group_labels: Group labels
            metrics: Metrics to compare (default: accuracy, precision, recall)

        Returns:
            List of detected gaps with statistical significance
        """
        if metrics is None:
            metrics = ["accuracy", "precision", "recall", "auc"]

        calc = FairnessMetricsCalculator()
        calc.compute_group_statistics(predictions, actuals, group_labels)

        groups = list(calc.group_stats.keys())
        detected_gaps = []

        for metric in metrics:
            metric_values = {}

            for group, stats in calc.group_stats.items():
                if metric == "accuracy":
                    correct = stats.true_positive + stats.true_negative
                    metric_values[group] = correct / stats.total_count if stats.total_count > 0 else 0
                elif metric == "precision":
                    metric_values[group] = stats.precision
                elif metric == "recall":
                    metric_values[group] = stats.true_positive_rate
                elif metric == "auc":
                    # Simplified AUC approximation
                    metric_values[group] = (stats.true_positive_rate +
                                            (1 - stats.false_positive_rate)) / 2

            # Compare all pairs
            for i, group_a in enumerate(groups):
                for group_b in groups[i+1:]:
                    gap = metric_values[group_a] - metric_values[group_b]

                    # Approximate significance test
                    n_a = calc.group_stats[group_a].total_count
                    n_b = calc.group_stats[group_b].total_count
                    se = math.sqrt(
                        metric_values[group_a] * (1 - metric_values[group_a]) / max(n_a, 1) +
                        metric_values[group_b] * (1 - metric_values[group_b]) / max(n_b, 1)
                    )

                    z_score = abs(gap) / se if se > 0 else 0
                    p_value = 2 * (1 - self._norm_cdf(z_score))  # Two-tailed

                    is_significant = p_value < self.significance_threshold

                    if abs(gap) > 0.05 or is_significant:  # Report meaningful gaps
                        detected_gaps.append({
                            "metric": metric,
                            "group_a": group_a,
                            "group_b": group_b,
                            "value_a": metric_values[group_a],
                            "value_b": metric_values[group_b],
                            "gap": gap,
                            "z_score": z_score,
                            "p_value": p_value,
                            "is_significant": is_significant,
                            "severity": self._classify_severity(gap, is_significant)
                        })

        self.gaps = detected_gaps
        return detected_gaps

    def _norm_cdf(self, x: float) -> float:
        """Standard normal CDF approximation"""
        return (1 + math.erf(x / math.sqrt(2))) / 2

    def _classify_severity(self, gap: float, is_significant: bool) -> str:
        """Classify gap severity"""
        abs_gap = abs(gap)
        if not is_significant:
            return "low"
        elif abs_gap > 0.2:
            return "critical"
        elif abs_gap > 0.1:
            return "high"
        else:
            return "medium"


# ==============================================================================
# CI/CD FAIRNESS TESTING
# ==============================================================================

class FairnessTestSuite:
    """
    Automated fairness testing suite for CI/CD integration
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.test_results: list[dict[str, Any]] = []

    def _default_config(self) -> dict[str, Any]:
        """Default test configuration"""
        return {
            "disparate_impact_threshold": 0.8,
            "demographic_parity_threshold": 0.1,
            "equal_opportunity_threshold": 0.1,
            "calibration_threshold": 0.05,
            "minimum_group_size": 30,
            "fail_on_warning": False,
            "protected_attributes": ["gender", "race", "age_group"]
        }

    def run_test(
        self,
        test_name: str,
        predictions: list[float],
        actuals: list[int],
        group_labels: list[str],
        threshold: float,
        metric_func: Callable
    ) -> dict[str, Any]:
        """Run a single fairness test"""
        try:
            metric_value = metric_func(predictions, actuals, group_labels)
            passed = metric_value >= threshold if "ratio" in test_name.lower() else abs(metric_value) <= threshold

            result = {
                "test_name": test_name,
                "status": "PASSED" if passed else "FAILED",
                "metric_value": metric_value,
                "threshold": threshold,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            result = {
                "test_name": test_name,
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

        self.test_results.append(result)
        return result

    def run_all_tests(
        self,
        predictions: list[float],
        actuals: list[int],
        group_data: dict[str, list[str]]
    ) -> dict[str, Any]:
        """
        Run complete fairness test suite

        Args:
            predictions: Model predictions
            actuals: Actual outcomes
            group_data: Dictionary of group labels by protected attribute

        Returns:
            Test suite results
        """
        self.test_results = []

        for attr_name, group_labels in group_data.items():
            if attr_name not in self.config["protected_attributes"]:
                continue

            calc = FairnessMetricsCalculator()
            calc.compute_group_statistics(predictions, actuals, group_labels)

            groups = list(calc.group_stats.keys())
            if len(groups) < 2:
                continue

            reference_group = max(groups, key=lambda g: calc.group_stats[g].total_count)

            for group in groups:
                if group == reference_group:
                    continue

                # Skip small groups
                if calc.group_stats[group].total_count < self.config["minimum_group_size"]:
                    continue

                # Test 1: Disparate Impact
                dir_metric = calc.disparate_impact_ratio(group, reference_group)
                self.test_results.append({
                    "test_name": f"disparate_impact_{attr_name}_{group}_vs_{reference_group}",
                    "status": "PASSED" if dir_metric.passes_threshold else "FAILED",
                    "metric_value": dir_metric.value,
                    "threshold": self.config["disparate_impact_threshold"],
                    "attribute": attr_name,
                    "groups": [group, reference_group]
                })

                # Test 2: Demographic Parity
                dpd_metric = calc.demographic_parity_difference(group, reference_group)
                self.test_results.append({
                    "test_name": f"demographic_parity_{attr_name}_{group}_vs_{reference_group}",
                    "status": "PASSED" if dpd_metric.passes_threshold else "FAILED",
                    "metric_value": dpd_metric.value,
                    "threshold": self.config["demographic_parity_threshold"],
                    "attribute": attr_name,
                    "groups": [group, reference_group]
                })

                # Test 3: Equal Opportunity
                eod_metric = calc.equal_opportunity_difference(group, reference_group)
                self.test_results.append({
                    "test_name": f"equal_opportunity_{attr_name}_{group}_vs_{reference_group}",
                    "status": "PASSED" if eod_metric.passes_threshold else "FAILED",
                    "metric_value": eod_metric.value,
                    "threshold": self.config["equal_opportunity_threshold"],
                    "attribute": attr_name,
                    "groups": [group, reference_group]
                })

        # Calculate calibration tests
        for attr_name, group_labels in group_data.items():
            calc = FairnessMetricsCalculator()
            calc.compute_group_statistics(predictions, actuals, group_labels)

            calibration_metrics = calc.calibration_across_groups()
            for group_name, cal_metric in calibration_metrics.items():
                self.test_results.append({
                    "test_name": f"calibration_{attr_name}_{group_name}",
                    "status": "PASSED" if cal_metric.passes_threshold else "FAILED",
                    "metric_value": cal_metric.value,
                    "threshold": self.config["calibration_threshold"],
                    "attribute": attr_name,
                    "group": group_name
                })

        # Summary
        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["status"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["status"] == "ERROR")

        return {
            "summary": {
                "total_tests": len(self.test_results),
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "pass_rate": passed / len(self.test_results) if self.test_results else 0
            },
            "overall_status": "PASSED" if failed == 0 and errors == 0 else "FAILED",
            "results": self.test_results,
            "timestamp": datetime.now().isoformat()
        }

    def generate_junit_xml(self) -> str:
        """Generate JUnit XML format for CI integration"""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']

        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["status"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["status"] == "ERROR")

        xml_lines.append(f'<testsuite name="FairnessTests" tests="{len(self.test_results)}" '
                        f'failures="{failed}" errors="{errors}">')

        for result in self.test_results:
            xml_lines.append(f'  <testcase name="{result["test_name"]}">')

            if result["status"] == "FAILED":
                xml_lines.append(f'    <failure message="Metric value {result.get("metric_value", "N/A")} '
                               f'did not meet threshold {result.get("threshold", "N/A")}"/>')
            elif result["status"] == "ERROR":
                xml_lines.append(f'    <error message="{result.get("error", "Unknown error")}"/>')

            xml_lines.append('  </testcase>')

        xml_lines.append('</testsuite>')

        return '\n'.join(xml_lines)


# ==============================================================================
# MAIN FAIRNESS AUDITOR CLASS
# ==============================================================================

class FairnessAuditor:
    """
    Comprehensive Fairness and Bias Audit Framework

    Main orchestrator for all fairness assessment and mitigation activities.

    Usage:
        auditor = FairnessAuditor(model_name="payment_predictor", model_version="1.0")

        # Run audit
        report = auditor.audit(
            predictions=model_predictions,
            actuals=actual_outcomes,
            protected_attributes={
                "gender": gender_labels,
                "race": race_labels,
                "age_group": age_labels
            }
        )

        # Check if passes
        if not report.passes_audit:
            # Get mitigation recommendations
            mitigations = auditor.recommend_mitigations()

            # Apply threshold optimization
            optimized_thresholds = auditor.optimize_thresholds(fairness_weight=0.7)
    """

    def __init__(
        self,
        model_name: str,
        model_version: str,
        config: Optional[dict[str, Any]] = None
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.config = config or self._default_config()

        # Components
        self.sensitive_detector = SensitiveFeatureDetector()
        self.metrics_calculator = FairnessMetricsCalculator()
        self.gap_detector = PerformanceGapDetector()
        self.threshold_optimizer = ThresholdOptimizer()
        self.reweighing = ReweighingMitigation()
        self.calibrated_eo = CalibratedEqualizedOddsMitigation()
        self.test_suite = FairnessTestSuite(config)

        # State
        self.last_predictions: list[float] = []
        self.last_actuals: list[int] = []
        self.last_group_data: dict[str, list[str]] = {}
        self.last_report: Optional[FairnessReport] = None
        self.alerts: list[BiasAlert] = []

    def _default_config(self) -> dict[str, Any]:
        """Default auditor configuration"""
        return {
            **FAIRNESS_THRESHOLDS,
            "protected_attributes": [attr.value for attr in ProtectedAttribute],
            "minimum_group_size": 30,
            "alert_on_threshold_violation": True,
            "generate_mitigation_recommendations": True
        }

    def audit(
        self,
        predictions: list[float],
        actuals: list[int],
        protected_attributes: dict[str, list[str]],
        feature_names: Optional[list[str]] = None
    ) -> FairnessReport:
        """
        Perform comprehensive fairness audit

        Args:
            predictions: Model prediction scores (0-1)
            actuals: Actual outcomes (0 or 1)
            protected_attributes: Dict mapping attribute name to group labels
            feature_names: Optional list of feature names to check for sensitivity

        Returns:
            Comprehensive FairnessReport
        """
        self.last_predictions = predictions
        self.last_actuals = actuals
        self.last_group_data = protected_attributes
        self.alerts = []

        report_id = f"fairness_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 1. Detect sensitive features if names provided
        sensitive_features = {}
        if feature_names:
            sensitive_features = self.sensitive_detector.detect_sensitive_features(feature_names)

        # 2. Calculate metrics for each protected attribute
        all_metrics = []
        detailed_findings = {"by_attribute": {}}

        for attr_name, group_labels in protected_attributes.items():
            # Compute group statistics
            self.metrics_calculator.compute_group_statistics(
                predictions, actuals, group_labels
            )

            groups = list(self.metrics_calculator.group_stats.keys())
            if len(groups) < 2:
                continue

            # Identify reference group (largest)
            reference_group = max(
                groups,
                key=lambda g: self.metrics_calculator.group_stats[g].total_count
            )

            attr_metrics = []
            attr_findings = {"reference_group": reference_group, "comparisons": []}

            for group in groups:
                if group == reference_group:
                    continue

                stats = self.metrics_calculator.group_stats[group]
                if stats.total_count < self.config.get("minimum_group_size", 30):
                    continue

                comparison = {"group": group, "metrics": {}}

                # Calculate all fairness metrics
                try:
                    # Disparate Impact Ratio
                    dir_metric = self.metrics_calculator.disparate_impact_ratio(
                        group, reference_group
                    )
                    attr_metrics.append(dir_metric)
                    comparison["metrics"]["disparate_impact"] = {
                        "value": dir_metric.value,
                        "passes": dir_metric.passes_threshold
                    }

                    # Check for alert
                    if not dir_metric.passes_threshold:
                        self._create_alert(
                            attr_name, BiasType.HISTORICAL, "disparate_impact",
                            dir_metric.value, 0.8, [group, reference_group]
                        )

                    # Demographic Parity
                    dpd_metric = self.metrics_calculator.demographic_parity_difference(
                        reference_group, group
                    )
                    attr_metrics.append(dpd_metric)
                    comparison["metrics"]["demographic_parity"] = {
                        "value": dpd_metric.value,
                        "passes": dpd_metric.passes_threshold
                    }

                    # Equal Opportunity
                    eod_metric = self.metrics_calculator.equal_opportunity_difference(
                        reference_group, group
                    )
                    attr_metrics.append(eod_metric)
                    comparison["metrics"]["equal_opportunity"] = {
                        "value": eod_metric.value,
                        "passes": eod_metric.passes_threshold
                    }

                    # Equalized Odds
                    tpr_metric, fpr_metric = self.metrics_calculator.equalized_odds_assessment(
                        reference_group, group
                    )
                    attr_metrics.extend([tpr_metric, fpr_metric])
                    comparison["metrics"]["equalized_odds"] = {
                        "tpr_diff": tpr_metric.value,
                        "fpr_diff": fpr_metric.value,
                        "passes": tpr_metric.passes_threshold and fpr_metric.passes_threshold
                    }

                except Exception as e:
                    logger.warning(f"Error calculating metrics for {attr_name}/{group}: {e}")

                attr_findings["comparisons"].append(comparison)

            # Calibration across groups
            calibration_metrics = self.metrics_calculator.calibration_across_groups()
            attr_metrics.extend(calibration_metrics.values())
            attr_findings["calibration"] = {
                group: {"error": m.value, "passes": m.passes_threshold}
                for group, m in calibration_metrics.items()
            }

            all_metrics.extend(attr_metrics)
            detailed_findings["by_attribute"][attr_name] = attr_findings

        # 3. Detect performance gaps
        for attr_name, group_labels in protected_attributes.items():
            gaps = self.gap_detector.detect_gaps(predictions, actuals, group_labels)
            detailed_findings["by_attribute"].setdefault(attr_name, {})["performance_gaps"] = gaps

        # 4. Calculate overall fairness score
        passing_metrics = sum(1 for m in all_metrics if m.passes_threshold)
        total_metrics = len(all_metrics)
        fairness_score = passing_metrics / total_metrics if total_metrics > 0 else 1.0

        # 5. Determine pass/fail
        critical_failures = sum(
            1 for m in all_metrics
            if m.metric_type == FairnessMetricType.DISPARATE_IMPACT and not m.passes_threshold
        )
        passes_audit = critical_failures == 0 and fairness_score >= 0.8

        # 6. Generate mitigation recommendations
        mitigation_recommendations = []
        if not passes_audit and self.config.get("generate_mitigation_recommendations", True):
            mitigation_recommendations = self._generate_mitigation_recommendations(all_metrics)

        # 7. Generate executive summary
        executive_summary = self._generate_executive_summary(
            all_metrics, passes_audit, fairness_score
        )

        # 8. Create report
        report = FairnessReport(
            report_id=report_id,
            model_name=self.model_name,
            model_version=self.model_version,
            audit_timestamp=datetime.now(),
            dataset_size=len(predictions),
            protected_attributes_analyzed=list(protected_attributes.keys()),
            metrics=all_metrics,
            alerts=self.alerts,
            overall_fairness_score=fairness_score,
            passes_audit=passes_audit,
            mitigation_recommendations=mitigation_recommendations,
            executive_summary=executive_summary,
            detailed_findings=detailed_findings
        )

        self.last_report = report
        return report

    def _create_alert(
        self,
        attribute: str,
        bias_type: BiasType,
        metric_name: str,
        metric_value: float,
        threshold: float,
        affected_groups: list[str]
    ) -> None:
        """Create a bias alert"""
        severity = "critical" if metric_name == "disparate_impact" else "high"

        recommended_actions = []
        if metric_name == "disparate_impact":
            recommended_actions = [
                "Review model features for proxy discrimination",
                "Consider reweighing training data",
                "Evaluate threshold adjustment for affected groups",
                "Document business justification if disparity is job-related"
            ]

        alert = BiasAlert(
            alert_id=f"alert_{datetime.now().timestamp()}",
            severity=severity,
            bias_type=bias_type,
            affected_attribute=ProtectedAttribute(attribute) if attribute in [a.value for a in ProtectedAttribute] else ProtectedAttribute.RACE,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            affected_groups=affected_groups,
            description=f"Fairness threshold violation detected: {metric_name}={metric_value:.3f} "
                       f"(threshold: {threshold})",
            recommended_actions=recommended_actions
        )

        self.alerts.append(alert)

    def _generate_mitigation_recommendations(
        self,
        metrics: list[FairnessMetric]
    ) -> list[dict[str, Any]]:
        """Generate mitigation strategy recommendations"""
        recommendations = []

        # Check which metrics are failing
        failing_metrics = [m for m in metrics if not m.passes_threshold]

        # Group by metric type
        failing_by_type = defaultdict(list)
        for m in failing_metrics:
            failing_by_type[m.metric_type].append(m)

        # Recommend strategies based on failures
        if FairnessMetricType.DISPARATE_IMPACT in failing_by_type:
            recommendations.append({
                "strategy": MitigationStrategy.REWEIGHING.value,
                "priority": "high",
                "description": "Apply sample reweighing to balance outcomes across groups",
                "expected_improvement": "Can improve disparate impact ratio by 10-30%",
                "tradeoffs": "May slightly reduce overall model accuracy"
            })
            recommendations.append({
                "strategy": MitigationStrategy.THRESHOLD_OPTIMIZER.value,
                "priority": "high",
                "description": "Optimize classification thresholds per group",
                "expected_improvement": "Can achieve compliance while preserving model scores",
                "tradeoffs": "Requires maintaining group membership at prediction time"
            })

        if FairnessMetricType.EQUAL_OPPORTUNITY in failing_by_type:
            recommendations.append({
                "strategy": MitigationStrategy.CALIBRATED_EQUALIZED_ODDS.value,
                "priority": "medium",
                "description": "Apply post-processing to equalize true positive rates",
                "expected_improvement": "Can equalize TPR across groups",
                "tradeoffs": "May affect calibration for some groups"
            })

        if FairnessMetricType.CALIBRATION in failing_by_type:
            recommendations.append({
                "strategy": "recalibration",
                "priority": "medium",
                "description": "Apply group-specific calibration adjustments",
                "expected_improvement": "Achieves calibration within 2-3%",
                "tradeoffs": "Requires retraining calibration layer"
            })

        # Always recommend adversarial debiasing for severe issues
        if len(failing_metrics) > 3:
            recommendations.append({
                "strategy": MitigationStrategy.ADVERSARIAL_DEBIASING.value,
                "priority": "high",
                "description": "Retrain model with adversarial debiasing",
                "expected_improvement": "Most comprehensive solution for multiple fairness violations",
                "tradeoffs": "Requires model retraining with modified architecture"
            })

        return recommendations

    def _generate_executive_summary(
        self,
        metrics: list[FairnessMetric],
        passes_audit: bool,
        fairness_score: float
    ) -> str:
        """Generate executive summary for report"""
        total = len(metrics)
        passing = sum(1 for m in metrics if m.passes_threshold)
        failing = total - passing

        status = "PASSED" if passes_audit else "FAILED"

        summary_parts = [
            f"Fairness Audit Status: {status}",
            f"Overall Fairness Score: {fairness_score:.1%}",
            f"Metrics Evaluated: {total}",
            f"Metrics Passing: {passing} ({passing/total:.1%})" if total > 0 else "No metrics evaluated",
            f"Metrics Failing: {failing}"
        ]

        if not passes_audit:
            # Add critical issues
            critical = [m for m in metrics
                       if m.metric_type == FairnessMetricType.DISPARATE_IMPACT
                       and not m.passes_threshold]
            if critical:
                summary_parts.append(
                    f"\nCRITICAL: {len(critical)} disparate impact violation(s) detected. "
                    "Immediate remediation required."
                )

        return "\n".join(summary_parts)

    def recommend_mitigations(self) -> list[dict[str, Any]]:
        """Get mitigation recommendations from last audit"""
        if not self.last_report:
            return []
        return self.last_report.mitigation_recommendations

    def optimize_thresholds(
        self,
        fairness_weight: float = 0.5
    ) -> dict[str, float]:
        """
        Optimize classification thresholds for fairness

        Args:
            fairness_weight: Weight for fairness vs accuracy (0-1)

        Returns:
            Optimized thresholds per group
        """
        if not self.last_predictions or not self.last_group_data:
            raise ValueError("Must run audit() before optimizing thresholds")

        # Use first protected attribute for optimization
        first_attr = list(self.last_group_data.keys())[0]
        group_labels = self.last_group_data[first_attr]

        return self.threshold_optimizer.optimize_thresholds(
            self.last_predictions,
            self.last_actuals,
            group_labels,
            fairness_weight=fairness_weight
        )

    def compute_reweighing_weights(self) -> list[float]:
        """
        Compute sample weights for reweighing mitigation

        Returns:
            Weight for each sample in last audit data
        """
        if not self.last_actuals or not self.last_group_data:
            raise ValueError("Must run audit() before computing weights")

        first_attr = list(self.last_group_data.keys())[0]
        group_labels = self.last_group_data[first_attr]

        return self.reweighing.compute_weights(group_labels, self.last_actuals)

    def get_adversarial_hooks(
        self,
        protected_attributes: list[str]
    ) -> AdversarialDebiasingHooks:
        """
        Get adversarial debiasing hooks for model training

        Args:
            protected_attributes: List of attributes to debias against

        Returns:
            AdversarialDebiasingHooks instance
        """
        return AdversarialDebiasingHooks(protected_attributes)

    def apply_calibrated_equalized_odds(
        self,
        predictions: list[float],
        group_labels: list[str],
        reference_group: str
    ) -> list[float]:
        """
        Apply calibrated equalized odds post-processing

        Args:
            predictions: Original predictions
            group_labels: Group labels
            reference_group: Reference group for equalization

        Returns:
            Adjusted predictions
        """
        if not self.last_actuals:
            raise ValueError("Must run audit() before applying CEO")

        self.calibrated_eo.fit(
            predictions, self.last_actuals, group_labels, reference_group
        )
        return self.calibrated_eo.transform(predictions, group_labels)

    def run_ci_tests(
        self,
        predictions: list[float],
        actuals: list[int],
        group_data: dict[str, list[str]]
    ) -> dict[str, Any]:
        """
        Run CI/CD fairness tests

        Args:
            predictions: Model predictions
            actuals: Actual outcomes
            group_data: Group labels by attribute

        Returns:
            Test results
        """
        return self.test_suite.run_all_tests(predictions, actuals, group_data)

    def generate_report_json(self) -> str:
        """Generate JSON report from last audit"""
        if not self.last_report:
            return "{}"

        # Convert report to serializable dict
        report_dict = {
            "report_id": self.last_report.report_id,
            "model_name": self.last_report.model_name,
            "model_version": self.last_report.model_version,
            "audit_timestamp": self.last_report.audit_timestamp.isoformat(),
            "dataset_size": self.last_report.dataset_size,
            "protected_attributes": self.last_report.protected_attributes_analyzed,
            "overall_fairness_score": self.last_report.overall_fairness_score,
            "passes_audit": self.last_report.passes_audit,
            "executive_summary": self.last_report.executive_summary,
            "metrics": [
                {
                    "type": m.metric_type.value,
                    "value": m.value,
                    "threshold": m.threshold,
                    "passes": m.passes_threshold,
                    "groups": [m.reference_group, m.comparison_group]
                }
                for m in self.last_report.metrics
            ],
            "alerts": [
                {
                    "id": a.alert_id,
                    "severity": a.severity,
                    "metric": a.metric_name,
                    "value": a.metric_value,
                    "description": a.description
                }
                for a in self.last_report.alerts
            ],
            "mitigation_recommendations": self.last_report.mitigation_recommendations
        }

        return json.dumps(report_dict, indent=2)


# ==============================================================================
# DEMONSTRATION
# ==============================================================================

if __name__ == "__main__":
    import random

    print("=" * 70)
    print("FAIRNESS AND BIAS AUDIT FRAMEWORK DEMONSTRATION")
    print("=" * 70)

    # Create sample data with bias
    random.seed(42)
    n_samples = 1000

    # Generate predictions and actuals with embedded bias
    predictions = []
    actuals = []
    gender_labels = []
    age_labels = []

    for i in range(n_samples):
        # Simulate bias: females and older individuals get lower scores
        gender = random.choice(["male", "female"])
        age_group = random.choice(["18-30", "31-50", "51+"])

        base_score = random.uniform(0.3, 0.7)

        # Add bias
        if gender == "female":
            base_score -= 0.1  # Bias against females
        if age_group == "51+":
            base_score -= 0.08  # Bias against older

        # Clip to valid range
        score = max(0.0, min(1.0, base_score + random.uniform(-0.15, 0.15)))

        # Actual outcome correlated with score but with noise
        actual = 1 if random.random() < score else 0

        predictions.append(score)
        actuals.append(actual)
        gender_labels.append(gender)
        age_labels.append(age_group)

    # Create auditor
    auditor = FairnessAuditor(
        model_name="payment_predictor",
        model_version="1.0.0"
    )

    # Run audit
    print("\n1. RUNNING FAIRNESS AUDIT")
    print("-" * 40)

    report = auditor.audit(
        predictions=predictions,
        actuals=actuals,
        protected_attributes={
            "gender": gender_labels,
            "age_group": age_labels
        }
    )

    print(f"\nExecutive Summary:\n{report.executive_summary}")

    # Show key metrics
    print("\n2. KEY FAIRNESS METRICS")
    print("-" * 40)

    for metric in report.metrics[:10]:  # Show first 10
        status = "PASS" if metric.passes_threshold else "FAIL"
        print(f"  [{status}] {metric.metric_type.value}: {metric.value:.3f} "
              f"(threshold: {metric.threshold}) - {metric.reference_group} vs {metric.comparison_group}")

    # Show alerts
    if report.alerts:
        print(f"\n3. BIAS ALERTS ({len(report.alerts)} total)")
        print("-" * 40)

        for alert in report.alerts[:5]:
            print(f"  [{alert.severity.upper()}] {alert.metric_name}: {alert.metric_value:.3f}")
            print(f"    Groups: {', '.join(alert.affected_groups)}")
            print(f"    Action: {alert.recommended_actions[0] if alert.recommended_actions else 'N/A'}")

    # Show mitigation recommendations
    if report.mitigation_recommendations:
        print(f"\n4. MITIGATION RECOMMENDATIONS")
        print("-" * 40)

        for rec in report.mitigation_recommendations:
            print(f"  Strategy: {rec['strategy']}")
            print(f"  Priority: {rec['priority']}")
            print(f"  Expected: {rec['expected_improvement']}")
            print()

    # Demonstrate threshold optimization
    print("\n5. THRESHOLD OPTIMIZATION")
    print("-" * 40)

    optimized = auditor.optimize_thresholds(fairness_weight=0.7)
    print("  Optimized thresholds by group:")
    for group, threshold in optimized.items():
        print(f"    {group}: {threshold:.3f}")

    # Run CI tests
    print("\n6. CI/CD TEST RESULTS")
    print("-" * 40)

    ci_results = auditor.run_ci_tests(
        predictions, actuals,
        {"gender": gender_labels, "age_group": age_labels}
    )

    print(f"  Status: {ci_results['overall_status']}")
    print(f"  Total Tests: {ci_results['summary']['total_tests']}")
    print(f"  Passed: {ci_results['summary']['passed']}")
    print(f"  Failed: {ci_results['summary']['failed']}")
    print(f"  Pass Rate: {ci_results['summary']['pass_rate']:.1%}")

    # Show documented thresholds
    print("\n7. DOCUMENTED FAIRNESS THRESHOLDS")
    print("-" * 40)

    for metric_name, info in FAIRNESS_THRESHOLDS.items():
        print(f"  {metric_name}:")
        print(f"    Threshold: {info['threshold']}")
        print(f"    Source: {info['regulatory_source']}")

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE")
    print(f"Overall Status: {'PASSED' if report.passes_audit else 'FAILED'}")
    print(f"Fairness Score: {report.overall_fairness_score:.1%}")
    print("=" * 70)
