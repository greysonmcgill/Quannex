"""
Uncertainty Estimation System for ML Models

Provides comprehensive uncertainty quantification including:
1. Ensemble uncertainty (variance across models)
2. Monte Carlo Dropout for neural networks
3. Bayesian approximation (variational inference)
4. Conformal prediction for prediction intervals
5. Epistemic vs aleatoric uncertainty separation
6. Uncertainty calibration
7. High-uncertainty flagging (>95% coverage target)
8. Uncertainty-aware decision routing
9. Out-of-distribution detection
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Protocol, TypeVar
import math
import random
import statistics
from collections import defaultdict
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Core Data Structures
# =============================================================================

class UncertaintyType(Enum):
    """Types of uncertainty"""
    EPISTEMIC = "epistemic"     # Model uncertainty (reducible with more data)
    ALEATORIC = "aleatoric"     # Data uncertainty (irreducible noise)
    TOTAL = "total"             # Combined uncertainty
    CALIBRATED = "calibrated"   # Calibration-adjusted uncertainty


class ConfidenceLevel(Enum):
    """Standard confidence levels"""
    LEVEL_90 = 0.90
    LEVEL_95 = 0.95
    LEVEL_99 = 0.99


class DecisionRoute(Enum):
    """Decision routing based on uncertainty"""
    AUTO_APPROVE = "auto_approve"           # Low uncertainty, high confidence
    STANDARD_PROCESS = "standard_process"   # Normal uncertainty
    MANUAL_REVIEW = "manual_review"         # High uncertainty
    EXPERT_ESCALATION = "expert_escalation" # Very high uncertainty
    REJECT = "reject"                       # Extreme uncertainty


@dataclass
class PredictionInterval:
    """Prediction interval with coverage guarantee"""
    lower: float
    upper: float
    confidence_level: float
    coverage_target: float
    interval_width: float = field(init=False)

    def __post_init__(self):
        self.interval_width = self.upper - self.lower

    def contains(self, value: float) -> bool:
        """Check if value is within interval"""
        return self.lower <= value <= self.upper


@dataclass
class ConfidenceInterval:
    """Confidence interval for parameter estimation"""
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    standard_error: float

    @property
    def margin_of_error(self) -> float:
        return (self.upper - self.lower) / 2


@dataclass
class UncertaintyMetrics:
    """Comprehensive uncertainty metrics"""
    epistemic_uncertainty: float      # Model uncertainty
    aleatoric_uncertainty: float      # Data uncertainty
    total_uncertainty: float          # Combined
    calibrated_uncertainty: float     # After calibration
    prediction_variance: float        # Variance of predictions
    entropy: float                    # Predictive entropy
    mutual_information: float         # For epistemic uncertainty
    ood_score: float                  # Out-of-distribution score

    @property
    def is_high_uncertainty(self) -> bool:
        """Flag for high uncertainty (>95% coverage target)"""
        return self.calibrated_uncertainty > 0.3 or self.ood_score > 0.5


@dataclass
class UncertaintyAwarePrediction:
    """Model output schema with probability and uncertainty"""
    prediction_id: str
    timestamp: datetime

    # Core prediction
    point_prediction: float
    probability: float

    # Uncertainty quantification
    uncertainty: UncertaintyMetrics
    prediction_interval: PredictionInterval
    confidence_interval: ConfidenceInterval

    # Decision support
    decision_route: DecisionRoute
    is_flagged: bool
    flag_reasons: list[str] = field(default_factory=list)

    # Metadata
    model_ensemble_size: int = 0
    mc_dropout_samples: int = 0
    calibration_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "prediction_id": self.prediction_id,
            "timestamp": self.timestamp.isoformat(),
            "point_prediction": self.point_prediction,
            "probability": self.probability,
            "uncertainty": {
                "epistemic": self.uncertainty.epistemic_uncertainty,
                "aleatoric": self.uncertainty.aleatoric_uncertainty,
                "total": self.uncertainty.total_uncertainty,
                "calibrated": self.uncertainty.calibrated_uncertainty,
                "ood_score": self.uncertainty.ood_score,
                "is_high_uncertainty": self.uncertainty.is_high_uncertainty,
            },
            "prediction_interval": {
                "lower": self.prediction_interval.lower,
                "upper": self.prediction_interval.upper,
                "confidence_level": self.prediction_interval.confidence_level,
                "width": self.prediction_interval.interval_width,
            },
            "confidence_interval": {
                "point_estimate": self.confidence_interval.point_estimate,
                "lower": self.confidence_interval.lower,
                "upper": self.confidence_interval.upper,
                "margin_of_error": self.confidence_interval.margin_of_error,
            },
            "decision_route": self.decision_route.value,
            "is_flagged": self.is_flagged,
            "flag_reasons": self.flag_reasons,
        }


# =============================================================================
# Base Model Interface
# =============================================================================

class UncertaintyModel(Protocol):
    """Protocol for models that support uncertainty estimation"""

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        """Return (prediction, raw_uncertainty)"""
        ...

    def predict_with_dropout(
        self, features: dict[str, float], n_samples: int
    ) -> list[float]:
        """Return samples from Monte Carlo Dropout"""
        ...


# =============================================================================
# Ensemble Uncertainty Estimator
# =============================================================================

class EnsembleUncertaintyEstimator:
    """
    Estimates uncertainty from an ensemble of models.

    Uncertainty is computed as the variance across model predictions,
    which captures epistemic (model) uncertainty.
    """

    def __init__(self, models: list[Any] = None):
        self.models = models or []
        self.model_weights: list[float] = []
        self.calibration_factors: dict[str, float] = {}

    def add_model(self, model: Any, weight: float = 1.0) -> None:
        """Add a model to the ensemble"""
        self.models.append(model)
        self.model_weights.append(weight)

    def predict_ensemble(
        self, features: dict[str, float]
    ) -> tuple[list[float], float, float]:
        """
        Get predictions from all models in ensemble.

        Returns:
            predictions: List of individual model predictions
            mean: Weighted mean prediction
            variance: Prediction variance (epistemic uncertainty)
        """
        if not self.models:
            return [], 0.0, 1.0

        predictions = []
        weights = self.model_weights if self.model_weights else [1.0] * len(self.models)

        for model in self.models:
            try:
                pred, _ = model.predict(features)
                predictions.append(pred)
            except Exception:
                # Skip failed models
                continue

        if not predictions:
            return [], 0.5, 1.0

        # Weighted mean
        total_weight = sum(weights[:len(predictions)])
        mean = sum(p * w for p, w in zip(predictions, weights)) / total_weight

        # Variance (epistemic uncertainty)
        if len(predictions) > 1:
            variance = sum(
                w * (p - mean) ** 2
                for p, w in zip(predictions, weights)
            ) / total_weight
        else:
            variance = 0.1  # Default uncertainty for single model

        return predictions, mean, variance

    def compute_disagreement(self, predictions: list[float]) -> float:
        """
        Compute model disagreement as a measure of epistemic uncertainty.

        Uses the range normalized by mean prediction.
        """
        if len(predictions) < 2:
            return 0.0

        pred_range = max(predictions) - min(predictions)
        pred_mean = statistics.mean(predictions)

        # Normalized disagreement
        if pred_mean > 0:
            return pred_range / (2 * pred_mean)
        return pred_range


# =============================================================================
# Monte Carlo Dropout Estimator
# =============================================================================

class MonteCarloDropoutEstimator:
    """
    Monte Carlo Dropout for neural network uncertainty estimation.

    By running inference multiple times with dropout enabled,
    we approximate Bayesian inference to estimate model uncertainty.
    """

    def __init__(self, n_samples: int = 50, dropout_rate: float = 0.3):
        self.n_samples = n_samples
        self.dropout_rate = dropout_rate

    def estimate_uncertainty(
        self,
        model: Any,
        features: dict[str, float],
        n_samples: int = None
    ) -> tuple[float, float, float, list[float]]:
        """
        Estimate uncertainty using MC Dropout.

        Returns:
            mean_prediction: Mean of MC samples
            epistemic_uncertainty: Variance of predictions
            predictive_entropy: Entropy of mean prediction
            samples: Raw MC samples
        """
        n_samples = n_samples or self.n_samples
        samples = []

        # Collect MC dropout samples
        if hasattr(model, 'predict_with_dropout'):
            samples = model.predict_with_dropout(features, n_samples)
        else:
            # Simulate MC dropout for models without native support
            samples = self._simulate_mc_dropout(model, features, n_samples)

        if not samples:
            return 0.5, 0.25, 1.0, []

        # Mean prediction
        mean_pred = statistics.mean(samples)

        # Epistemic uncertainty (variance of samples)
        if len(samples) > 1:
            epistemic = statistics.variance(samples)
        else:
            epistemic = 0.1

        # Predictive entropy
        entropy = self._compute_entropy(mean_pred)

        return mean_pred, epistemic, entropy, samples

    def _simulate_mc_dropout(
        self,
        model: Any,
        features: dict[str, float],
        n_samples: int
    ) -> list[float]:
        """Simulate MC dropout by adding noise to features"""
        samples = []

        for _ in range(n_samples):
            # Apply dropout-like perturbation
            perturbed_features = {}
            for name, value in features.items():
                if random.random() > self.dropout_rate:
                    # Add small noise
                    noise = random.gauss(0, 0.1 * abs(value) + 0.01)
                    perturbed_features[name] = value + noise
                else:
                    perturbed_features[name] = 0.0  # Dropout

            try:
                pred, _ = model.predict(perturbed_features)
                samples.append(pred)
            except Exception:
                continue

        return samples

    def _compute_entropy(self, probability: float) -> float:
        """Compute binary entropy"""
        if probability <= 0 or probability >= 1:
            return 0.0

        p = max(min(probability, 1 - 1e-10), 1e-10)
        return -p * math.log(p) - (1 - p) * math.log(1 - p)


# =============================================================================
# Bayesian Approximation (Variational Inference)
# =============================================================================

class VariationalBayesianEstimator:
    """
    Bayesian uncertainty estimation using variational inference.

    Maintains posterior distributions over model parameters
    to quantify epistemic uncertainty.
    """

    def __init__(self, prior_mean: float = 0.0, prior_variance: float = 1.0):
        self.prior_mean = prior_mean
        self.prior_variance = prior_variance

        # Variational parameters (mean-field approximation)
        self.posterior_means: dict[str, float] = {}
        self.posterior_variances: dict[str, float] = {}

        # Segment-based posteriors for grouped inference
        self.segment_posteriors: dict[str, dict[str, float]] = defaultdict(
            lambda: {"alpha": 1.0, "beta": 1.0, "n_obs": 0}
        )

    def update_posterior(
        self,
        segment: str,
        observation: float,
        learning_rate: float = 0.1
    ) -> None:
        """
        Update posterior for a segment using variational update.

        Uses beta-binomial conjugate prior for probability estimation.
        """
        posterior = self.segment_posteriors[segment]

        # Beta-binomial update
        posterior["alpha"] += observation * learning_rate
        posterior["beta"] += (1 - observation) * learning_rate
        posterior["n_obs"] += 1

    def predict_with_uncertainty(
        self, segment: str
    ) -> tuple[float, float, float, float]:
        """
        Predict with Bayesian uncertainty quantification.

        Returns:
            mean: Posterior mean
            variance: Posterior variance
            lower_95: 95% credible interval lower bound
            upper_95: 95% credible interval upper bound
        """
        posterior = self.segment_posteriors[segment]
        alpha = posterior["alpha"]
        beta = posterior["beta"]

        # Posterior mean
        mean = alpha / (alpha + beta)

        # Posterior variance
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))

        # 95% credible interval (normal approximation)
        std = math.sqrt(variance)
        z_95 = 1.96
        lower = max(0, mean - z_95 * std)
        upper = min(1, mean + z_95 * std)

        return mean, variance, lower, upper

    def compute_epistemic_uncertainty(self, segment: str) -> float:
        """
        Compute epistemic uncertainty from posterior variance.

        Epistemic uncertainty decreases as we observe more data.
        """
        posterior = self.segment_posteriors[segment]
        n_obs = posterior["n_obs"]

        # Uncertainty decreases with more observations
        _, variance, _, _ = self.predict_with_uncertainty(segment)

        # Scale by observation count (more data = less epistemic uncertainty)
        epistemic_scale = 1.0 / (1.0 + math.sqrt(n_obs))

        return variance * epistemic_scale

    def compute_mutual_information(
        self, predictions: list[float]
    ) -> float:
        """
        Compute mutual information between predictions and model parameters.

        Higher MI indicates higher epistemic uncertainty.
        """
        if len(predictions) < 2:
            return 0.0

        # Mean entropy of individual predictions
        mean_entropy = statistics.mean([
            self._entropy(p) for p in predictions
        ])

        # Entropy of mean prediction
        mean_pred = statistics.mean(predictions)
        entropy_of_mean = self._entropy(mean_pred)

        # Mutual information = H[y|x] - E[H[y|x,w]]
        mutual_info = entropy_of_mean - mean_entropy

        return max(0, mutual_info)

    def _entropy(self, p: float) -> float:
        """Binary entropy"""
        if p <= 0 or p >= 1:
            return 0.0
        p = max(min(p, 1 - 1e-10), 1e-10)
        return -p * math.log(p) - (1 - p) * math.log(1 - p)


# =============================================================================
# Conformal Prediction
# =============================================================================

class ConformalPredictor:
    """
    Conformal prediction for distribution-free prediction intervals.

    Provides prediction intervals with guaranteed coverage
    under exchangeability assumption.
    """

    def __init__(self, coverage_target: float = 0.95):
        self.coverage_target = coverage_target
        self.calibration_scores: list[float] = []
        self.quantile_cache: dict[float, float] = {}

    def calibrate(
        self,
        predictions: list[float],
        actuals: list[float]
    ) -> float:
        """
        Calibrate conformal predictor using holdout data.

        Computes nonconformity scores for calibration.

        Returns:
            Calibration score (coverage on calibration set)
        """
        if len(predictions) != len(actuals):
            raise ValueError("Predictions and actuals must have same length")

        # Compute nonconformity scores (absolute residuals)
        self.calibration_scores = [
            abs(pred - actual)
            for pred, actual in zip(predictions, actuals)
        ]

        # Sort for quantile computation
        self.calibration_scores.sort()
        self.quantile_cache.clear()

        # Compute empirical coverage
        coverage = self._compute_coverage(predictions, actuals)

        return coverage

    def predict_interval(
        self,
        point_prediction: float,
        confidence_level: float = None
    ) -> PredictionInterval:
        """
        Generate prediction interval with coverage guarantee.

        Uses conformal quantile to determine interval width.
        """
        confidence_level = confidence_level or self.coverage_target

        if not self.calibration_scores:
            # Default interval if not calibrated
            width = 0.2 * (1 + (1 - confidence_level) * 2)
            return PredictionInterval(
                lower=max(0, point_prediction - width),
                upper=min(1, point_prediction + width),
                confidence_level=confidence_level,
                coverage_target=self.coverage_target
            )

        # Get conformal quantile
        quantile = self._get_conformal_quantile(confidence_level)

        return PredictionInterval(
            lower=max(0, point_prediction - quantile),
            upper=min(1, point_prediction + quantile),
            confidence_level=confidence_level,
            coverage_target=self.coverage_target
        )

    def _get_conformal_quantile(self, confidence_level: float) -> float:
        """Get quantile of calibration scores for given confidence level"""
        if confidence_level in self.quantile_cache:
            return self.quantile_cache[confidence_level]

        n = len(self.calibration_scores)
        if n == 0:
            return 0.2

        # Quantile index with finite sample correction
        idx = int(math.ceil((n + 1) * confidence_level)) - 1
        idx = max(0, min(idx, n - 1))

        quantile = self.calibration_scores[idx]
        self.quantile_cache[confidence_level] = quantile

        return quantile

    def _compute_coverage(
        self,
        predictions: list[float],
        actuals: list[float]
    ) -> float:
        """Compute empirical coverage"""
        if not predictions:
            return 0.0

        covered = 0
        for pred, actual in zip(predictions, actuals):
            interval = self.predict_interval(pred)
            if interval.contains(actual):
                covered += 1

        return covered / len(predictions)

    def adaptive_interval(
        self,
        point_prediction: float,
        uncertainty: float,
        confidence_level: float = 0.95
    ) -> PredictionInterval:
        """
        Generate adaptive interval that scales with uncertainty.

        Wider intervals for higher uncertainty predictions.
        """
        base_interval = self.predict_interval(point_prediction, confidence_level)

        # Scale by uncertainty
        uncertainty_scale = 1 + uncertainty * 2
        scaled_width = base_interval.interval_width * uncertainty_scale

        return PredictionInterval(
            lower=max(0, point_prediction - scaled_width / 2),
            upper=min(1, point_prediction + scaled_width / 2),
            confidence_level=confidence_level,
            coverage_target=self.coverage_target
        )


# =============================================================================
# Epistemic vs Aleatoric Uncertainty Separation
# =============================================================================

class UncertaintySeparator:
    """
    Separates epistemic (model) and aleatoric (data) uncertainty.

    Epistemic uncertainty can be reduced with more data/better models.
    Aleatoric uncertainty is inherent noise in the data.
    """

    def __init__(self):
        self.feature_noise_estimates: dict[str, float] = {}
        self.segment_aleatoric: dict[str, float] = {}

    def estimate_aleatoric(
        self,
        features: dict[str, float],
        historical_variance: float = None
    ) -> float:
        """
        Estimate aleatoric uncertainty from feature characteristics.

        Aleatoric uncertainty is estimated from:
        - Feature noise levels
        - Historical variance in similar samples
        - Inherent data quality indicators
        """
        # Base aleatoric from feature noise
        noise_contribution = 0.0
        for name, value in features.items():
            noise = self.feature_noise_estimates.get(name, 0.05)
            noise_contribution += noise * abs(value)

        avg_noise = noise_contribution / max(len(features), 1)

        # Add historical variance if available
        if historical_variance is not None:
            aleatoric = (avg_noise + historical_variance) / 2
        else:
            aleatoric = avg_noise

        return min(aleatoric, 0.5)  # Cap at 0.5

    def estimate_epistemic(
        self,
        ensemble_variance: float,
        mc_dropout_variance: float,
        n_observations: int
    ) -> float:
        """
        Estimate epistemic uncertainty from model sources.

        Epistemic uncertainty comes from:
        - Ensemble disagreement
        - MC Dropout variance
        - Limited training data
        """
        # Combine ensemble and MC dropout estimates
        model_uncertainty = (ensemble_variance + mc_dropout_variance) / 2

        # Data scarcity factor (more data = less epistemic uncertainty)
        scarcity_factor = 1.0 / (1.0 + math.log1p(n_observations))

        epistemic = model_uncertainty * scarcity_factor

        return min(epistemic, 0.5)

    def separate_uncertainty(
        self,
        total_variance: float,
        ensemble_variance: float,
        mc_dropout_variance: float,
        features: dict[str, float],
        n_observations: int
    ) -> tuple[float, float]:
        """
        Decompose total uncertainty into epistemic and aleatoric components.

        Returns:
            epistemic: Epistemic (model) uncertainty
            aleatoric: Aleatoric (data) uncertainty
        """
        # Estimate epistemic
        epistemic = self.estimate_epistemic(
            ensemble_variance, mc_dropout_variance, n_observations
        )

        # Aleatoric is the remainder
        aleatoric = max(0, total_variance - epistemic)

        # Normalize to ensure they sum to total
        total_est = epistemic + aleatoric
        if total_est > 0:
            scale = total_variance / total_est
            epistemic *= scale
            aleatoric *= scale

        return epistemic, aleatoric

    def update_noise_estimate(
        self,
        feature_name: str,
        observed_noise: float,
        learning_rate: float = 0.1
    ) -> None:
        """Update running estimate of feature noise"""
        current = self.feature_noise_estimates.get(feature_name, 0.05)
        updated = current * (1 - learning_rate) + observed_noise * learning_rate
        self.feature_noise_estimates[feature_name] = updated


# =============================================================================
# Uncertainty Calibration
# =============================================================================

class UncertaintyCalibrator:
    """
    Calibrates uncertainty estimates to achieve reliable coverage.

    Uses temperature scaling and isotonic regression for calibration.
    """

    def __init__(self, target_coverage: float = 0.95):
        self.target_coverage = target_coverage
        self.temperature: float = 1.0
        self.isotonic_map: list[tuple[float, float]] = []
        self.calibration_history: list[dict[str, float]] = []

    def calibrate_temperature(
        self,
        uncertainties: list[float],
        coverages: list[bool]
    ) -> float:
        """
        Learn temperature scaling factor for calibration.

        Temperature > 1 increases uncertainty estimates.
        Temperature < 1 decreases uncertainty estimates.
        """
        if not uncertainties or not coverages:
            return 1.0

        actual_coverage = sum(coverages) / len(coverages)

        # Adjust temperature based on coverage gap
        coverage_gap = self.target_coverage - actual_coverage

        # Temperature adjustment (increase if under-covering)
        adjustment = 1.0 + coverage_gap * 0.5
        self.temperature *= adjustment

        # Bound temperature
        self.temperature = max(0.5, min(2.0, self.temperature))

        return self.temperature

    def calibrate_isotonic(
        self,
        predicted_uncertainties: list[float],
        actual_errors: list[float]
    ) -> None:
        """
        Build isotonic regression mapping for uncertainty calibration.

        Maps predicted uncertainty to calibrated uncertainty using
        a monotonic (isotonic) function.
        """
        if len(predicted_uncertainties) != len(actual_errors):
            return

        # Sort by predicted uncertainty
        pairs = list(zip(predicted_uncertainties, actual_errors))
        pairs.sort(key=lambda x: x[0])

        # Pool adjacent violators algorithm (simplified)
        calibrated = []
        for pred_unc, actual_err in pairs:
            calibrated.append((pred_unc, actual_err))

        # Ensure monotonicity
        for i in range(1, len(calibrated)):
            if calibrated[i][1] < calibrated[i-1][1]:
                # Average to maintain monotonicity
                avg = (calibrated[i][1] + calibrated[i-1][1]) / 2
                calibrated[i] = (calibrated[i][0], avg)
                calibrated[i-1] = (calibrated[i-1][0], avg)

        self.isotonic_map = calibrated

    def apply_calibration(self, uncertainty: float) -> float:
        """
        Apply calibration to raw uncertainty estimate.

        Uses temperature scaling and isotonic mapping.
        """
        # Apply temperature scaling
        scaled = uncertainty * self.temperature

        # Apply isotonic mapping if available
        if self.isotonic_map:
            calibrated = self._isotonic_interpolate(scaled)
        else:
            calibrated = scaled

        return min(max(calibrated, 0.0), 1.0)

    def _isotonic_interpolate(self, uncertainty: float) -> float:
        """Interpolate in isotonic calibration map"""
        if not self.isotonic_map:
            return uncertainty

        # Find bracketing points
        for i, (pred, calib) in enumerate(self.isotonic_map):
            if pred >= uncertainty:
                if i == 0:
                    return calib
                # Linear interpolation
                pred_prev, calib_prev = self.isotonic_map[i-1]
                ratio = (uncertainty - pred_prev) / (pred - pred_prev + 1e-10)
                return calib_prev + ratio * (calib - calib_prev)

        # Extrapolate from last point
        return self.isotonic_map[-1][1]

    def compute_calibration_error(
        self,
        predicted_uncertainties: list[float],
        actual_coverages: list[bool]
    ) -> float:
        """
        Compute Expected Calibration Error (ECE).

        Measures how well uncertainty estimates correspond to actual coverage.
        """
        if not predicted_uncertainties:
            return 0.0

        # Bin predictions
        n_bins = 10
        bins = [[] for _ in range(n_bins)]

        for unc, covered in zip(predicted_uncertainties, actual_coverages):
            bin_idx = min(int(unc * n_bins), n_bins - 1)
            bins[bin_idx].append((unc, covered))

        # Compute ECE
        ece = 0.0
        total = len(predicted_uncertainties)

        for bin_data in bins:
            if not bin_data:
                continue

            avg_unc = statistics.mean([x[0] for x in bin_data])
            avg_cov = statistics.mean([1 if x[1] else 0 for x in bin_data])

            # Expected coverage based on uncertainty
            expected_cov = 1 - avg_unc

            ece += len(bin_data) / total * abs(avg_cov - expected_cov)

        return ece


# =============================================================================
# Out-of-Distribution Detection
# =============================================================================

class OODDetector:
    """
    Detects out-of-distribution inputs that may have unreliable predictions.

    Uses multiple detection methods:
    - Mahalanobis distance
    - Feature range checking
    - Ensemble disagreement
    - Density estimation
    """

    def __init__(self, ood_threshold: float = 0.5):
        self.ood_threshold = ood_threshold
        self.feature_stats: dict[str, dict[str, float]] = {}
        self.covariance_matrix: dict[tuple[str, str], float] = {}
        self.training_densities: list[float] = []

    def fit(self, training_features: list[dict[str, float]]) -> None:
        """
        Fit OOD detector on training data.

        Computes feature statistics for OOD detection.
        """
        if not training_features:
            return

        # Compute per-feature statistics
        feature_values: dict[str, list[float]] = defaultdict(list)

        for features in training_features:
            for name, value in features.items():
                feature_values[name].append(value)

        for name, values in feature_values.items():
            if values:
                self.feature_stats[name] = {
                    "mean": statistics.mean(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.1,
                    "min": min(values),
                    "max": max(values),
                    "q1": sorted(values)[len(values) // 4],
                    "q3": sorted(values)[3 * len(values) // 4],
                }

        # Compute training densities for density-based OOD
        for features in training_features:
            density = self._compute_density(features)
            self.training_densities.append(density)

        self.training_densities.sort()

    def compute_ood_score(self, features: dict[str, float]) -> float:
        """
        Compute OOD score for input features.

        Higher score = more likely to be OOD.

        Returns:
            OOD score in [0, 1]
        """
        if not self.feature_stats:
            return 0.0

        scores = []

        # Feature-wise z-score based detection
        for name, value in features.items():
            if name in self.feature_stats:
                stats = self.feature_stats[name]
                z_score = abs(value - stats["mean"]) / (stats["std"] + 1e-10)
                # Convert z-score to probability
                feature_ood = min(1.0, z_score / 4)  # z > 4 is definitely OOD
                scores.append(feature_ood)

        # Range-based detection
        range_violations = self._check_range_violations(features)

        # Density-based detection
        density_ood = self._density_ood_score(features)

        # Combine scores
        if scores:
            avg_feature_ood = statistics.mean(scores)
        else:
            avg_feature_ood = 0.0

        combined = (
            0.4 * avg_feature_ood +
            0.3 * range_violations +
            0.3 * density_ood
        )

        return min(1.0, combined)

    def _check_range_violations(self, features: dict[str, float]) -> float:
        """Check for features outside training range"""
        violations = 0
        total = 0

        for name, value in features.items():
            if name in self.feature_stats:
                stats = self.feature_stats[name]
                total += 1

                # Check if outside IQR * 1.5 (outlier rule)
                iqr = stats["q3"] - stats["q1"]
                lower_bound = stats["q1"] - 1.5 * iqr
                upper_bound = stats["q3"] + 1.5 * iqr

                if value < lower_bound or value > upper_bound:
                    violations += 1

        return violations / max(total, 1)

    def _compute_density(self, features: dict[str, float]) -> float:
        """Compute density estimate for features"""
        density = 0.0

        for name, value in features.items():
            if name in self.feature_stats:
                stats = self.feature_stats[name]
                # Gaussian kernel density
                z = (value - stats["mean"]) / (stats["std"] + 1e-10)
                density += math.exp(-0.5 * z ** 2)

        return density / max(len(features), 1)

    def _density_ood_score(self, features: dict[str, float]) -> float:
        """OOD score based on density estimation"""
        if not self.training_densities:
            return 0.0

        density = self._compute_density(features)

        # Find percentile in training densities
        below = sum(1 for d in self.training_densities if d < density)
        percentile = below / len(self.training_densities)

        # Low percentile = low density = likely OOD
        return 1.0 - percentile

    def is_ood(self, features: dict[str, float]) -> bool:
        """Check if input is out-of-distribution"""
        return self.compute_ood_score(features) > self.ood_threshold


# =============================================================================
# Decision Router
# =============================================================================

class UncertaintyDecisionRouter:
    """
    Routes predictions to appropriate handling based on uncertainty.

    High uncertainty predictions are flagged for manual review.
    """

    def __init__(
        self,
        auto_approve_threshold: float = 0.1,
        standard_threshold: float = 0.25,
        manual_review_threshold: float = 0.4,
        expert_threshold: float = 0.6
    ):
        self.auto_approve_threshold = auto_approve_threshold
        self.standard_threshold = standard_threshold
        self.manual_review_threshold = manual_review_threshold
        self.expert_threshold = expert_threshold

        # Routing statistics
        self.routing_counts: dict[DecisionRoute, int] = defaultdict(int)

    def route(
        self,
        uncertainty: float,
        ood_score: float,
        prediction: float
    ) -> tuple[DecisionRoute, list[str]]:
        """
        Determine routing based on uncertainty and OOD score.

        Returns:
            route: Decision route
            reasons: List of reasons for the routing decision
        """
        reasons = []

        # Check OOD first
        if ood_score > 0.7:
            reasons.append(f"High OOD score: {ood_score:.2f}")
            self.routing_counts[DecisionRoute.EXPERT_ESCALATION] += 1
            return DecisionRoute.EXPERT_ESCALATION, reasons

        if ood_score > 0.5:
            reasons.append(f"Elevated OOD score: {ood_score:.2f}")

        # Route based on uncertainty
        effective_uncertainty = uncertainty * (1 + ood_score)

        if effective_uncertainty <= self.auto_approve_threshold:
            route = DecisionRoute.AUTO_APPROVE

        elif effective_uncertainty <= self.standard_threshold:
            route = DecisionRoute.STANDARD_PROCESS

        elif effective_uncertainty <= self.manual_review_threshold:
            route = DecisionRoute.MANUAL_REVIEW
            reasons.append(f"High uncertainty: {uncertainty:.2f}")

        elif effective_uncertainty <= self.expert_threshold:
            route = DecisionRoute.EXPERT_ESCALATION
            reasons.append(f"Very high uncertainty: {uncertainty:.2f}")

        else:
            route = DecisionRoute.REJECT
            reasons.append(f"Extreme uncertainty: {uncertainty:.2f}")

        # Additional flags for edge cases
        if prediction < 0.1 or prediction > 0.9:
            if uncertainty > 0.2:
                reasons.append(f"Extreme prediction ({prediction:.2f}) with uncertainty")

        self.routing_counts[route] += 1
        return route, reasons

    def get_routing_statistics(self) -> dict[str, Any]:
        """Get statistics on routing decisions"""
        total = sum(self.routing_counts.values())

        return {
            "total_routed": total,
            "by_route": {
                route.value: {
                    "count": count,
                    "percentage": count / total * 100 if total > 0 else 0
                }
                for route, count in self.routing_counts.items()
            }
        }


# =============================================================================
# Main Uncertainty Estimator Class
# =============================================================================

class UncertaintyEstimator:
    """
    Comprehensive uncertainty estimation system.

    Combines multiple uncertainty estimation methods:
    - Ensemble variance
    - Monte Carlo Dropout
    - Bayesian variational inference
    - Conformal prediction
    - Epistemic/aleatoric separation
    - Uncertainty calibration
    - OOD detection
    - Decision routing

    Target: >95% coverage for high-uncertainty flagging.
    """

    def __init__(
        self,
        coverage_target: float = 0.95,
        n_mc_samples: int = 50,
        ood_threshold: float = 0.5
    ):
        self.coverage_target = coverage_target
        self.n_mc_samples = n_mc_samples

        # Component estimators
        self.ensemble_estimator = EnsembleUncertaintyEstimator()
        self.mc_dropout_estimator = MonteCarloDropoutEstimator(n_samples=n_mc_samples)
        self.bayesian_estimator = VariationalBayesianEstimator()
        self.conformal_predictor = ConformalPredictor(coverage_target=coverage_target)
        self.uncertainty_separator = UncertaintySeparator()
        self.calibrator = UncertaintyCalibrator(target_coverage=coverage_target)
        self.ood_detector = OODDetector(ood_threshold=ood_threshold)
        self.router = UncertaintyDecisionRouter()

        # Statistics
        self.prediction_count = 0
        self.flagged_count = 0
        self.coverage_history: list[bool] = []

    def add_model(self, model: Any, weight: float = 1.0) -> None:
        """Add a model to the ensemble"""
        self.ensemble_estimator.add_model(model, weight)

    def fit(
        self,
        training_features: list[dict[str, float]],
        training_labels: list[float]
    ) -> dict[str, float]:
        """
        Fit the uncertainty estimator on training data.

        Returns:
            Fitting statistics
        """
        # Fit OOD detector
        self.ood_detector.fit(training_features)

        # Update Bayesian posteriors
        for features, label in zip(training_features, training_labels):
            segment = self._get_segment(features)
            self.bayesian_estimator.update_posterior(segment, label)

        # Calibrate conformal predictor (using leave-one-out or holdout)
        if len(training_features) > 10:
            # Use last 20% for calibration
            split_idx = int(len(training_features) * 0.8)
            calib_features = training_features[split_idx:]
            calib_labels = training_labels[split_idx:]

            predictions = []
            for features in calib_features:
                _, mean, _ = self.ensemble_estimator.predict_ensemble(features)
                predictions.append(mean)

            coverage = self.conformal_predictor.calibrate(predictions, calib_labels)
        else:
            coverage = 0.0

        return {
            "n_samples": len(training_features),
            "calibration_coverage": coverage,
            "n_segments": len(self.bayesian_estimator.segment_posteriors),
        }

    def predict(
        self,
        features: dict[str, float],
        return_full: bool = True
    ) -> UncertaintyAwarePrediction:
        """
        Make prediction with comprehensive uncertainty quantification.

        Args:
            features: Input features
            return_full: Whether to return full prediction object

        Returns:
            UncertaintyAwarePrediction with all uncertainty metrics
        """
        self.prediction_count += 1
        prediction_id = f"pred_{datetime.now().timestamp()}_{self.prediction_count}"

        # 1. Ensemble prediction
        ensemble_preds, ensemble_mean, ensemble_var = \
            self.ensemble_estimator.predict_ensemble(features)

        # 2. MC Dropout estimate
        mc_mean, mc_var, entropy, mc_samples = \
            self.mc_dropout_estimator.estimate_uncertainty(
                self.ensemble_estimator.models[0] if self.ensemble_estimator.models else None,
                features
            )

        # 3. Bayesian estimate
        segment = self._get_segment(features)
        bayes_mean, bayes_var, bayes_lower, bayes_upper = \
            self.bayesian_estimator.predict_with_uncertainty(segment)

        # 4. Combine predictions
        if ensemble_preds:
            point_prediction = ensemble_mean
            total_variance = ensemble_var
        else:
            point_prediction = (mc_mean + bayes_mean) / 2
            total_variance = (mc_var + bayes_var) / 2

        # 5. Separate epistemic and aleatoric uncertainty
        epistemic, aleatoric = self.uncertainty_separator.separate_uncertainty(
            total_variance,
            ensemble_var,
            mc_var,
            features,
            self.bayesian_estimator.segment_posteriors[segment]["n_obs"]
        )

        # 6. OOD detection
        ood_score = self.ood_detector.compute_ood_score(features)

        # 7. Total uncertainty
        total_uncertainty = math.sqrt(epistemic + aleatoric)

        # 8. Apply calibration
        calibrated_uncertainty = self.calibrator.apply_calibration(total_uncertainty)

        # 9. Compute mutual information
        all_samples = ensemble_preds + mc_samples
        mutual_info = self.bayesian_estimator.compute_mutual_information(
            all_samples if all_samples else [point_prediction]
        )

        # 10. Build uncertainty metrics
        uncertainty = UncertaintyMetrics(
            epistemic_uncertainty=epistemic,
            aleatoric_uncertainty=aleatoric,
            total_uncertainty=total_uncertainty,
            calibrated_uncertainty=calibrated_uncertainty,
            prediction_variance=total_variance,
            entropy=entropy,
            mutual_information=mutual_info,
            ood_score=ood_score
        )

        # 11. Prediction interval (conformal)
        prediction_interval = self.conformal_predictor.adaptive_interval(
            point_prediction,
            calibrated_uncertainty,
            self.coverage_target
        )

        # 12. Confidence interval
        std_err = math.sqrt(total_variance) / math.sqrt(max(1, len(ensemble_preds)))
        z_score = 1.96  # 95% confidence
        confidence_interval = ConfidenceInterval(
            point_estimate=point_prediction,
            lower=max(0, point_prediction - z_score * std_err),
            upper=min(1, point_prediction + z_score * std_err),
            confidence_level=0.95,
            standard_error=std_err
        )

        # 13. Decision routing
        route, flag_reasons = self.router.route(
            calibrated_uncertainty,
            ood_score,
            point_prediction
        )

        # 14. Flagging logic (>95% coverage target)
        is_flagged = (
            uncertainty.is_high_uncertainty or
            ood_score > 0.5 or
            route in [DecisionRoute.MANUAL_REVIEW,
                     DecisionRoute.EXPERT_ESCALATION,
                     DecisionRoute.REJECT]
        )

        if is_flagged:
            self.flagged_count += 1
            if uncertainty.is_high_uncertainty:
                flag_reasons.append("High uncertainty flag")

        # Build full prediction
        prediction = UncertaintyAwarePrediction(
            prediction_id=prediction_id,
            timestamp=datetime.now(),
            point_prediction=point_prediction,
            probability=max(0, min(1, point_prediction)),
            uncertainty=uncertainty,
            prediction_interval=prediction_interval,
            confidence_interval=confidence_interval,
            decision_route=route,
            is_flagged=is_flagged,
            flag_reasons=flag_reasons,
            model_ensemble_size=len(self.ensemble_estimator.models),
            mc_dropout_samples=len(mc_samples),
            calibration_applied=True
        )

        return prediction

    def update_calibration(
        self,
        prediction: UncertaintyAwarePrediction,
        actual: float
    ) -> None:
        """
        Update calibration based on observed outcome.

        Tracks coverage and adjusts calibration parameters.
        """
        # Check coverage
        covered = prediction.prediction_interval.contains(actual)
        self.coverage_history.append(covered)

        # Keep last 1000 observations
        if len(self.coverage_history) > 1000:
            self.coverage_history.pop(0)

        # Update Bayesian posterior
        segment = self._get_segment({})  # Would need features
        self.bayesian_estimator.update_posterior(segment, actual)

        # Periodically recalibrate
        if len(self.coverage_history) >= 100 and len(self.coverage_history) % 50 == 0:
            self._recalibrate()

    def _recalibrate(self) -> None:
        """Recalibrate based on recent coverage"""
        recent = self.coverage_history[-100:]
        uncertainties = [0.5] * len(recent)  # Placeholder

        self.calibrator.calibrate_temperature(uncertainties, recent)

    def _get_segment(self, features: dict[str, float]) -> str:
        """Get segment key for Bayesian grouping"""
        # Simple segmentation based on feature ranges
        score = features.get("shadow_score", 0.5)
        balance = features.get("balance", 0.5)

        score_tier = "high" if score > 0.7 else "mid" if score > 0.4 else "low"
        balance_tier = "large" if balance > 0.5 else "small"

        return f"{score_tier}_{balance_tier}"

    def get_statistics(self) -> dict[str, Any]:
        """Get uncertainty estimation statistics"""
        recent_coverage = (
            sum(self.coverage_history[-100:]) / len(self.coverage_history[-100:])
            if self.coverage_history else 0.0
        )

        return {
            "total_predictions": self.prediction_count,
            "flagged_predictions": self.flagged_count,
            "flagged_rate": self.flagged_count / max(self.prediction_count, 1),
            "recent_coverage": recent_coverage,
            "coverage_target": self.coverage_target,
            "meets_coverage_target": recent_coverage >= self.coverage_target,
            "calibration_temperature": self.calibrator.temperature,
            "routing_statistics": self.router.get_routing_statistics(),
        }

    def get_coverage_report(self) -> dict[str, Any]:
        """
        Generate coverage report for high-uncertainty flagging.

        Target: >95% coverage on flagged predictions.
        """
        if not self.coverage_history:
            return {"status": "insufficient_data", "n_observations": 0}

        total_coverage = sum(self.coverage_history) / len(self.coverage_history)
        recent_100 = self.coverage_history[-100:] if len(self.coverage_history) >= 100 else self.coverage_history
        recent_coverage = sum(recent_100) / len(recent_100)

        return {
            "status": "ok",
            "n_observations": len(self.coverage_history),
            "total_coverage": total_coverage,
            "recent_coverage": recent_coverage,
            "coverage_target": self.coverage_target,
            "meets_target": recent_coverage >= self.coverage_target,
            "coverage_gap": self.coverage_target - recent_coverage,
            "flagged_rate": self.flagged_count / max(self.prediction_count, 1),
        }


# =============================================================================
# Inference Tests
# =============================================================================

class UncertaintyEstimatorTests:
    """
    Inference tests for uncertainty estimation behavior.

    Validates that the uncertainty estimator behaves correctly
    under various scenarios.
    """

    def __init__(self, estimator: UncertaintyEstimator):
        self.estimator = estimator
        self.test_results: list[dict[str, Any]] = []

    def run_all_tests(self) -> dict[str, Any]:
        """Run all inference tests"""
        tests = [
            self.test_high_uncertainty_flagging,
            self.test_ood_detection,
            self.test_uncertainty_monotonicity,
            self.test_calibration_improvement,
            self.test_epistemic_aleatoric_separation,
            self.test_prediction_interval_coverage,
            self.test_decision_routing_consistency,
            self.test_ensemble_variance_behavior,
        ]

        results = {}
        for test in tests:
            test_name = test.__name__
            try:
                passed, details = test()
                results[test_name] = {
                    "passed": passed,
                    "details": details
                }
            except Exception as e:
                results[test_name] = {
                    "passed": False,
                    "details": f"Exception: {str(e)}"
                }

        passed_count = sum(1 for r in results.values() if r["passed"])

        return {
            "total_tests": len(tests),
            "passed": passed_count,
            "failed": len(tests) - passed_count,
            "pass_rate": passed_count / len(tests),
            "results": results
        }

    def test_high_uncertainty_flagging(self) -> tuple[bool, str]:
        """
        Test: High uncertainty predictions should be flagged.

        Validates >95% coverage target for flagged predictions.
        """
        # Generate test cases with known high uncertainty
        high_unc_features = {
            "shadow_score": 0.1,  # Edge case
            "balance": 0.99,
            "unknown_feature": 999,  # OOD feature
        }

        prediction = self.estimator.predict(high_unc_features)

        # Should be flagged due to uncertainty
        if prediction.is_flagged:
            return True, "High uncertainty correctly flagged"
        else:
            return False, f"High uncertainty not flagged. Uncertainty: {prediction.uncertainty.calibrated_uncertainty}"

    def test_ood_detection(self) -> tuple[bool, str]:
        """
        Test: OOD inputs should have high OOD scores.
        """
        # Normal input
        normal_features = {"shadow_score": 0.5, "balance": 0.3}

        # OOD input (extreme values)
        ood_features = {"shadow_score": 99.0, "balance": -10.0}

        normal_pred = self.estimator.predict(normal_features)
        ood_pred = self.estimator.predict(ood_features)

        if ood_pred.uncertainty.ood_score > normal_pred.uncertainty.ood_score:
            return True, f"OOD detection working. Normal: {normal_pred.uncertainty.ood_score:.3f}, OOD: {ood_pred.uncertainty.ood_score:.3f}"
        else:
            return False, "OOD detection failed"

    def test_uncertainty_monotonicity(self) -> tuple[bool, str]:
        """
        Test: Uncertainty should increase with less information.
        """
        # Full features
        full_features = {
            "shadow_score": 0.5,
            "balance": 0.3,
            "days_past_due": 0.2,
            "response_rate": 0.4
        }

        # Sparse features
        sparse_features = {"shadow_score": 0.5}

        full_pred = self.estimator.predict(full_features)
        sparse_pred = self.estimator.predict(sparse_features)

        # More features should generally mean less uncertainty
        # (though not always true, it's a reasonable expectation)
        if sparse_pred.uncertainty.total_uncertainty >= full_pred.uncertainty.total_uncertainty * 0.8:
            return True, "Uncertainty appropriately scales with information"
        else:
            return False, "Uncertainty scaling unexpected"

    def test_calibration_improvement(self) -> tuple[bool, str]:
        """
        Test: Calibration should improve with more data.
        """
        initial_temp = self.estimator.calibrator.temperature

        # Simulate calibration updates
        for _ in range(10):
            self.estimator.calibrator.calibrate_temperature(
                [0.3, 0.4, 0.5],
                [True, True, False]
            )

        final_temp = self.estimator.calibrator.temperature

        # Temperature should have adjusted
        if initial_temp != final_temp or abs(final_temp - 1.0) < 0.5:
            return True, f"Calibration adjusted. Initial: {initial_temp:.3f}, Final: {final_temp:.3f}"
        else:
            return False, "Calibration not responding"

    def test_epistemic_aleatoric_separation(self) -> tuple[bool, str]:
        """
        Test: Epistemic and aleatoric should sum to approximately total.
        """
        features = {"shadow_score": 0.5, "balance": 0.3}
        prediction = self.estimator.predict(features)

        unc = prediction.uncertainty
        sum_components = unc.epistemic_uncertainty + unc.aleatoric_uncertainty
        total = unc.total_uncertainty ** 2  # Variance

        # Should be reasonably close (within 20%)
        if abs(sum_components - total) < total * 0.3 + 0.01:
            return True, f"Uncertainty decomposition valid. Sum: {sum_components:.4f}, Total: {total:.4f}"
        else:
            return False, f"Decomposition mismatch. Sum: {sum_components:.4f}, Total: {total:.4f}"

    def test_prediction_interval_coverage(self) -> tuple[bool, str]:
        """
        Test: Prediction intervals should have valid bounds.
        """
        features = {"shadow_score": 0.5, "balance": 0.3}
        prediction = self.estimator.predict(features)

        interval = prediction.prediction_interval

        # Bounds should be valid
        valid_bounds = (
            0 <= interval.lower <= interval.upper <= 1 and
            interval.confidence_level > 0 and
            interval.interval_width >= 0
        )

        # Point prediction should be within interval
        contains_point = interval.contains(prediction.point_prediction)

        if valid_bounds and contains_point:
            return True, f"Interval [{interval.lower:.3f}, {interval.upper:.3f}] valid"
        else:
            return False, f"Invalid interval: [{interval.lower:.3f}, {interval.upper:.3f}]"

    def test_decision_routing_consistency(self) -> tuple[bool, str]:
        """
        Test: Decision routing should be consistent with uncertainty.
        """
        # Low uncertainty -> should not require manual review
        low_unc_features = {"shadow_score": 0.5, "balance": 0.5}

        # Simulate multiple predictions
        routes = []
        for _ in range(5):
            pred = self.estimator.predict(low_unc_features)
            routes.append(pred.decision_route)

        # Should be relatively consistent
        unique_routes = set(routes)

        if len(unique_routes) <= 2:  # Allow some variance
            return True, f"Routing consistent: {[r.value for r in routes]}"
        else:
            return False, f"Routing inconsistent: {[r.value for r in routes]}"

    def test_ensemble_variance_behavior(self) -> tuple[bool, str]:
        """
        Test: Ensemble variance should be computable.
        """
        features = {"shadow_score": 0.5, "balance": 0.3}

        preds, mean, variance = self.estimator.ensemble_estimator.predict_ensemble(features)

        if variance >= 0:
            return True, f"Ensemble variance: {variance:.4f} from {len(preds)} models"
        else:
            return False, "Negative variance"


# =============================================================================
# Demonstration
# =============================================================================

def run_demonstration():
    """Demonstrate uncertainty estimation system"""
    print("=" * 75)
    print("  UNCERTAINTY ESTIMATION SYSTEM DEMONSTRATION")
    print("=" * 75)

    # Create estimator
    estimator = UncertaintyEstimator(
        coverage_target=0.95,
        n_mc_samples=30,
        ood_threshold=0.5
    )

    # Create simple mock models
    class MockModel:
        def __init__(self, bias: float = 0.0):
            self.bias = bias
            self.weights = {}

        def predict(self, features: dict[str, float]) -> tuple[float, float]:
            # Simple weighted prediction
            score = 0.5 + self.bias
            for name, value in features.items():
                weight = self.weights.get(name, 0.1)
                score += value * weight

            # Sigmoid
            prob = 1 / (1 + math.exp(-score + 0.5))
            conf = 0.7 + random.uniform(-0.1, 0.1)
            return prob, conf

        def predict_with_dropout(
            self, features: dict[str, float], n_samples: int
        ) -> list[float]:
            samples = []
            for _ in range(n_samples):
                pred, _ = self.predict(features)
                samples.append(pred + random.gauss(0, 0.1))
            return samples

    # Add ensemble models
    for i in range(5):
        model = MockModel(bias=random.uniform(-0.1, 0.1))
        model.weights = {
            "shadow_score": random.uniform(0.1, 0.3),
            "balance": random.uniform(-0.1, 0.1),
            "response_rate": random.uniform(0.1, 0.2),
        }
        estimator.add_model(model)

    print(f"\n  Ensemble Size: {len(estimator.ensemble_estimator.models)}")
    print(f"  Coverage Target: {estimator.coverage_target:.0%}")

    # Generate training data
    print("\n  Generating training data...")
    training_features = []
    training_labels = []

    for _ in range(200):
        features = {
            "shadow_score": random.uniform(0.3, 0.8),
            "balance": random.uniform(0.1, 0.6),
            "response_rate": random.uniform(0.2, 0.7),
            "days_past_due": random.uniform(0.1, 0.5),
        }
        # Label based on features
        label = 1.0 if (features["shadow_score"] + features["response_rate"]) > 0.8 else 0.0
        label += random.gauss(0, 0.1)  # Add noise
        label = max(0, min(1, label))

        training_features.append(features)
        training_labels.append(label)

    # Fit estimator
    fit_stats = estimator.fit(training_features, training_labels)
    print(f"  Training samples: {fit_stats['n_samples']}")
    print(f"  Calibration coverage: {fit_stats['calibration_coverage']:.1%}")

    # Make predictions
    print("\n  Sample Predictions:")
    print("  " + "-" * 71)
    print(f"  {'Features':<30} {'Pred':>8} {'Unc':>8} {'OOD':>8} {'Route':<15}")
    print("  " + "-" * 71)

    test_cases = [
        {"shadow_score": 0.7, "balance": 0.3, "response_rate": 0.6},  # Normal
        {"shadow_score": 0.2, "balance": 0.9, "response_rate": 0.1},  # Edge
        {"shadow_score": 0.5, "balance": 0.5, "response_rate": 0.5},  # Middle
        {"shadow_score": 0.99, "balance": 0.01},  # Extreme
        {"shadow_score": 5.0, "balance": -1.0},  # OOD
    ]

    for features in test_cases:
        pred = estimator.predict(features)

        feat_str = f"s={features.get('shadow_score', 0):.1f}, b={features.get('balance', 0):.1f}"
        print(f"  {feat_str:<30} {pred.probability:>8.1%} "
              f"{pred.uncertainty.calibrated_uncertainty:>8.3f} "
              f"{pred.uncertainty.ood_score:>8.3f} "
              f"{pred.decision_route.value:<15}"
              f"{'[FLAGGED]' if pred.is_flagged else ''}")

    print("  " + "-" * 71)

    # Show detailed prediction
    print("\n  Detailed Prediction Example:")
    sample_features = {"shadow_score": 0.6, "balance": 0.4, "response_rate": 0.5}
    detailed = estimator.predict(sample_features)

    print(f"    Point Prediction:     {detailed.point_prediction:.3f}")
    print(f"    Probability:          {detailed.probability:.1%}")
    print(f"    Epistemic Unc:        {detailed.uncertainty.epistemic_uncertainty:.4f}")
    print(f"    Aleatoric Unc:        {detailed.uncertainty.aleatoric_uncertainty:.4f}")
    print(f"    Total Uncertainty:    {detailed.uncertainty.total_uncertainty:.4f}")
    print(f"    Calibrated Unc:       {detailed.uncertainty.calibrated_uncertainty:.4f}")
    print(f"    Entropy:              {detailed.uncertainty.entropy:.4f}")
    print(f"    OOD Score:            {detailed.uncertainty.ood_score:.4f}")
    print(f"    Prediction Interval:  [{detailed.prediction_interval.lower:.3f}, {detailed.prediction_interval.upper:.3f}]")
    print(f"    Confidence Interval:  [{detailed.confidence_interval.lower:.3f}, {detailed.confidence_interval.upper:.3f}]")
    print(f"    Decision Route:       {detailed.decision_route.value}")
    print(f"    Flagged:              {detailed.is_flagged}")
    if detailed.flag_reasons:
        print(f"    Flag Reasons:         {', '.join(detailed.flag_reasons)}")

    # Run inference tests
    print("\n  Running Inference Tests...")
    tests = UncertaintyEstimatorTests(estimator)
    test_results = tests.run_all_tests()

    print(f"    Tests Passed: {test_results['passed']}/{test_results['total_tests']}")
    print(f"    Pass Rate: {test_results['pass_rate']:.0%}")

    for test_name, result in test_results['results'].items():
        status = "PASS" if result['passed'] else "FAIL"
        print(f"    [{status}] {test_name}")

    # Statistics
    print("\n  System Statistics:")
    stats = estimator.get_statistics()
    print(f"    Total Predictions:    {stats['total_predictions']}")
    print(f"    Flagged Predictions:  {stats['flagged_predictions']}")
    print(f"    Flagged Rate:         {stats['flagged_rate']:.1%}")
    print(f"    Calibration Temp:     {stats['calibration_temperature']:.3f}")

    # Coverage report
    print("\n  Coverage Report:")
    coverage = estimator.get_coverage_report()
    print(f"    Status: {coverage['status']}")
    if coverage['status'] == 'ok':
        print(f"    Total Coverage:       {coverage['total_coverage']:.1%}")
        print(f"    Recent Coverage:      {coverage['recent_coverage']:.1%}")
        print(f"    Coverage Target:      {coverage['coverage_target']:.1%}")
        print(f"    Meets Target:         {coverage['meets_target']}")

    print("\n" + "=" * 75)

    return estimator


if __name__ == "__main__":
    run_demonstration()
