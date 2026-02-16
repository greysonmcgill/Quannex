"""
Model Calibration Layer for ML Predictions

Provides comprehensive calibration infrastructure for ensuring well-calibrated
probability predictions. Implements multiple calibration methods including:

1. Platt Scaling (Logistic Regression Calibration)
2. Isotonic Regression Calibration
3. Temperature Scaling for Neural Networks
4. Beta Calibration
5. Venn-ABERS Calibration for Valid Probabilities

Includes metrics, diagnostics, and automatic calibrator selection.

Target: ECE < 0.025 and calibration slope/intercept near 1.0/0.0 on validation set.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Optional, Union
import logging
import math
import random
from collections import defaultdict
import bisect
import copy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

class CalibratorType(Enum):
    """Supported calibration methods"""
    PLATT_SCALING = "platt_scaling"
    ISOTONIC_REGRESSION = "isotonic_regression"
    TEMPERATURE_SCALING = "temperature_scaling"
    BETA_CALIBRATION = "beta_calibration"
    VENN_ABERS = "venn_abers"
    HISTOGRAM_BINNING = "histogram_binning"
    ENSEMBLE = "ensemble"


@dataclass
class CalibrationMetrics:
    """Metrics for evaluating calibration quality"""
    ece: float = 0.0                    # Expected Calibration Error
    mce: float = 0.0                    # Maximum Calibration Error
    brier_score: float = 0.0            # Brier Score
    log_loss: float = 0.0               # Log Loss / Cross-Entropy
    calibration_slope: float = 1.0      # Slope from calibration curve fitting
    calibration_intercept: float = 0.0  # Intercept from calibration curve fitting
    reliability_score: float = 0.0      # Overall reliability measure
    sharpness: float = 0.0              # Sharpness of predictions
    refinement: float = 0.0             # Refinement component of Brier

    # Per-bin statistics
    bin_accuracies: list[float] = field(default_factory=list)
    bin_confidences: list[float] = field(default_factory=list)
    bin_counts: list[int] = field(default_factory=list)

    def meets_target(self, ece_threshold: float = 0.025) -> bool:
        """Check if calibration meets target thresholds (tightened for enhanced recovery)"""
        slope_ok = 0.92 <= self.calibration_slope <= 1.08
        intercept_ok = -0.04 <= self.calibration_intercept <= 0.04
        ece_ok = self.ece < ece_threshold
        return slope_ok and intercept_ok and ece_ok

    def summary(self) -> dict[str, Any]:
        """Generate summary dictionary"""
        return {
            "ece": round(self.ece, 4),
            "mce": round(self.mce, 4),
            "brier_score": round(self.brier_score, 4),
            "log_loss": round(self.log_loss, 4),
            "calibration_slope": round(self.calibration_slope, 4),
            "calibration_intercept": round(self.calibration_intercept, 4),
            "reliability_score": round(self.reliability_score, 4),
            "sharpness": round(self.sharpness, 4),
            "meets_target": self.meets_target()
        }


@dataclass
class CohortCalibration:
    """Calibration results for a specific cohort"""
    cohort_name: str
    cohort_filter: dict[str, Any]
    sample_size: int
    metrics: CalibrationMetrics
    calibrator_type: CalibratorType
    fit_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReliabilityDiagram:
    """Data for generating reliability diagrams"""
    n_bins: int
    bin_edges: list[float]
    bin_centers: list[float]
    bin_accuracies: list[float]
    bin_confidences: list[float]
    bin_counts: list[int]
    perfect_calibration_line: list[tuple[float, float]]
    gap_areas: list[float]

    def to_plot_data(self) -> dict[str, Any]:
        """Convert to format suitable for plotting libraries"""
        return {
            "n_bins": self.n_bins,
            "bin_centers": self.bin_centers,
            "accuracies": self.bin_accuracies,
            "confidences": self.bin_confidences,
            "counts": self.bin_counts,
            "gaps": self.gap_areas,
            "perfect_line": [(x, x) for x in [0.0, 0.25, 0.5, 0.75, 1.0]]
        }


@dataclass
class CalibrationDataset:
    """Held-out calibration dataset management"""
    predictions: list[float]
    labels: list[int]
    features: Optional[list[dict[str, Any]]] = None
    cohort_ids: Optional[list[str]] = None
    timestamps: Optional[list[datetime]] = None
    weights: Optional[list[float]] = None

    def __post_init__(self):
        if len(self.predictions) != len(self.labels):
            raise ValueError("Predictions and labels must have same length")

        if self.weights is None:
            self.weights = [1.0] * len(self.predictions)

    @property
    def size(self) -> int:
        return len(self.predictions)

    def split(self, train_fraction: float = 0.7) -> tuple['CalibrationDataset', 'CalibrationDataset']:
        """Split dataset into train and validation sets"""
        indices = list(range(self.size))
        random.shuffle(indices)

        split_idx = int(self.size * train_fraction)
        train_idx = indices[:split_idx]
        val_idx = indices[split_idx:]

        def subset(idx_list):
            return CalibrationDataset(
                predictions=[self.predictions[i] for i in idx_list],
                labels=[self.labels[i] for i in idx_list],
                features=[self.features[i] for i in idx_list] if self.features else None,
                cohort_ids=[self.cohort_ids[i] for i in idx_list] if self.cohort_ids else None,
                timestamps=[self.timestamps[i] for i in idx_list] if self.timestamps else None,
                weights=[self.weights[i] for i in idx_list] if self.weights else None
            )

        return subset(train_idx), subset(val_idx)

    def get_cohort_data(self, cohort_id: str) -> 'CalibrationDataset':
        """Extract data for a specific cohort"""
        if not self.cohort_ids:
            raise ValueError("No cohort IDs defined in dataset")

        indices = [i for i, cid in enumerate(self.cohort_ids) if cid == cohort_id]

        return CalibrationDataset(
            predictions=[self.predictions[i] for i in indices],
            labels=[self.labels[i] for i in indices],
            features=[self.features[i] for i in indices] if self.features else None,
            cohort_ids=[self.cohort_ids[i] for i in indices],
            timestamps=[self.timestamps[i] for i in indices] if self.timestamps else None,
            weights=[self.weights[i] for i in indices] if self.weights else None
        )

    def bootstrap_sample(self) -> 'CalibrationDataset':
        """Generate bootstrap sample of the dataset"""
        indices = [random.randint(0, self.size - 1) for _ in range(self.size)]

        return CalibrationDataset(
            predictions=[self.predictions[i] for i in indices],
            labels=[self.labels[i] for i in indices],
            features=[self.features[i] for i in indices] if self.features else None,
            cohort_ids=[self.cohort_ids[i] for i in indices] if self.cohort_ids else None,
            timestamps=[self.timestamps[i] for i in indices] if self.timestamps else None,
            weights=[self.weights[i] for i in indices] if self.weights else None
        )


# ============================================================================
# Base Calibrator Interface
# ============================================================================

class BaseCalibrator(ABC):
    """Abstract base class for all calibration methods"""

    def __init__(self, calibrator_type: CalibratorType):
        self.calibrator_type = calibrator_type
        self.is_fitted = False
        self.fit_timestamp: Optional[datetime] = None
        self.training_metrics: Optional[CalibrationMetrics] = None

    @abstractmethod
    def fit(self, predictions: list[float], labels: list[int]) -> 'BaseCalibrator':
        """Fit the calibrator on training data"""
        pass

    @abstractmethod
    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply calibration to predictions"""
        pass

    def fit_calibrate(self, predictions: list[float], labels: list[int]) -> list[float]:
        """Fit and transform in one step (for cross-validation)"""
        self.fit(predictions, labels)
        return self.calibrate(predictions)

    def get_params(self) -> dict[str, Any]:
        """Get calibrator parameters"""
        return {"type": self.calibrator_type.value, "is_fitted": self.is_fitted}


# ============================================================================
# Platt Scaling (Logistic Regression Calibration)
# ============================================================================

class PlattScalingCalibrator(BaseCalibrator):
    """
    Platt Scaling: Fits a logistic regression on the predictions.

    Maps raw predictions through: P(y=1|f) = 1 / (1 + exp(A*f + B))

    Optimal for models that produce uncalibrated sigmoid outputs.
    Particularly effective for SVMs and boosted trees.
    """

    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6):
        super().__init__(CalibratorType.PLATT_SCALING)
        self.A: float = 0.0  # Slope parameter
        self.B: float = 0.0  # Intercept parameter
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def fit(self, predictions: list[float], labels: list[int]) -> 'PlattScalingCalibrator':
        """
        Fit Platt scaling parameters using maximum likelihood optimization.

        Uses the algorithm from Platt (1999) with regularization to avoid
        perfect separation issues.
        """
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Target probabilities with label smoothing (Platt's approach)
        n_pos = sum(labels)
        n_neg = n - n_pos

        if n_pos == 0 or n_neg == 0:
            logger.warning("Only one class present in calibration data")
            self.A = 0.0
            self.B = 0.0
            self.is_fitted = True
            return self

        # Smoothed targets to avoid numerical issues
        t_pos = (n_pos + 1) / (n_pos + 2)
        t_neg = 1 / (n_neg + 2)

        targets = [t_pos if l == 1 else t_neg for l in labels]

        # Initialize parameters
        self.A = 0.0
        self.B = math.log((n_neg + 1) / (n_pos + 1))

        # Newton's method optimization
        hi_target = t_pos
        lo_target = t_neg

        for iteration in range(self.max_iterations):
            # Compute sigmoid predictions
            h1 = 0.0  # First derivative
            h2 = 0.0  # Second derivative (diagonal Hessian approximation)
            h3 = 0.0  # Cross derivative

            for i, f in enumerate(predictions):
                fApB = f * self.A + self.B

                # Clamp for numerical stability
                fApB = max(-500, min(500, fApB))

                # Numerical stability for sigmoid
                if fApB >= 0:
                    exp_neg = math.exp(-fApB)
                    p = 1.0 / (1.0 + exp_neg)
                    q = exp_neg / (1.0 + exp_neg)
                else:
                    exp_val = math.exp(fApB)
                    p = exp_val / (1.0 + exp_val)
                    q = 1.0 / (1.0 + exp_val)

                d2 = p * q
                h2 += f * f * d2
                h3 += f * d2
                h1 += f * (targets[i] - p)
                self.B += d2

            # Regularization to avoid singular Hessian
            h2 += 1e-8

            # Update using simplified Newton step
            if abs(h2) > 1e-10:
                delta_A = h1 / h2
                self.A += delta_A * 0.5  # Dampened update

            if abs(h3) > 1e-10:
                g1 = 0.0
                for i in range(n):
                    z = -predictions[i] * self.A - self.B
                    # Clamp z to prevent overflow
                    z = max(-500, min(500, z))
                    if z >= 0:
                        p = 1.0 / (1.0 + math.exp(-z))
                    else:
                        exp_z = math.exp(z)
                        p = exp_z / (1.0 + exp_z)
                    g1 += targets[i] - p
                delta_B = g1 / n
                self.B += delta_B * 0.5

            # Check convergence
            if iteration > 0 and abs(h1) < self.tolerance:
                break

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        logger.info(f"PlattScaling fitted: A={self.A:.4f}, B={self.B:.4f}")
        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply Platt scaling calibration"""
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        calibrated = []
        for f in predictions:
            fApB = f * self.A + self.B

            # Clamp for numerical stability
            fApB = max(-500, min(500, fApB))

            # Numerical stability for sigmoid
            if fApB >= 0:
                p = 1.0 / (1.0 + math.exp(-fApB))
            else:
                exp_val = math.exp(fApB)
                p = exp_val / (1.0 + exp_val)

            calibrated.append(p)

        return calibrated

    def get_params(self) -> dict[str, Any]:
        """Get Platt scaling parameters"""
        params = super().get_params()
        params.update({
            "A": self.A,
            "B": self.B,
            "max_iterations": self.max_iterations
        })
        return params


# ============================================================================
# Isotonic Regression Calibration
# ============================================================================

class IsotonicRegressionCalibrator(BaseCalibrator):
    """
    Isotonic Regression: Non-parametric calibration ensuring monotonicity.

    Fits a monotonically increasing step function that maps predictions
    to calibrated probabilities. Uses Pool Adjacent Violators (PAV) algorithm.

    Advantages:
    - More flexible than Platt scaling
    - Preserves ranking of predictions
    - Works well with any model type

    Disadvantages:
    - May overfit with small datasets
    - Creates discontinuous calibration function
    """

    def __init__(self, out_of_bounds: str = "clip"):
        super().__init__(CalibratorType.ISOTONIC_REGRESSION)
        self.x_values: list[float] = []  # Fitted prediction values
        self.y_values: list[float] = []  # Fitted calibrated probabilities
        self.out_of_bounds = out_of_bounds  # "clip", "extrapolate", or "nan"

    def fit(self, predictions: list[float], labels: list[int]) -> 'IsotonicRegressionCalibrator':
        """
        Fit isotonic regression using Pool Adjacent Violators (PAV) algorithm.
        """
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Sort by predictions
        sorted_indices = sorted(range(n), key=lambda i: predictions[i])
        sorted_preds = [predictions[i] for i in sorted_indices]
        sorted_labels = [float(labels[i]) for i in sorted_indices]

        # PAV algorithm
        y = sorted_labels.copy()
        weights = [1.0] * n

        # Pool Adjacent Violators
        i = 0
        while i < n - 1:
            if y[i] > y[i + 1]:
                # Pool: merge adjacent blocks
                # Find extent of violation
                j = i + 1
                while j < n - 1 and y[j] > y[j + 1]:
                    j += 1

                # Pool from i to j
                total_weight = sum(weights[i:j + 1])
                pooled_value = sum(y[k] * weights[k] for k in range(i, j + 1)) / total_weight

                for k in range(i, j + 1):
                    y[k] = pooled_value

                # Backtrack to check for new violations
                if i > 0:
                    i -= 1
                else:
                    i = j + 1
            else:
                i += 1

        # Store unique points for interpolation
        self.x_values = []
        self.y_values = []

        prev_x = None
        for i in range(n):
            x, y_val = sorted_preds[i], y[i]
            if prev_x is None or x != prev_x:
                self.x_values.append(x)
                self.y_values.append(y_val)
                prev_x = x
            else:
                # Average for same x values
                self.y_values[-1] = (self.y_values[-1] + y_val) / 2

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        logger.info(f"IsotonicRegression fitted with {len(self.x_values)} interpolation points")
        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply isotonic regression calibration using linear interpolation"""
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        calibrated = []

        for p in predictions:
            if p <= self.x_values[0]:
                if self.out_of_bounds == "clip":
                    cal_p = self.y_values[0]
                elif self.out_of_bounds == "extrapolate" and len(self.x_values) >= 2:
                    # Linear extrapolation
                    slope = (self.y_values[1] - self.y_values[0]) / (self.x_values[1] - self.x_values[0] + 1e-10)
                    cal_p = self.y_values[0] + slope * (p - self.x_values[0])
                    cal_p = max(0.0, min(1.0, cal_p))
                else:
                    cal_p = self.y_values[0]
            elif p >= self.x_values[-1]:
                if self.out_of_bounds == "clip":
                    cal_p = self.y_values[-1]
                elif self.out_of_bounds == "extrapolate" and len(self.x_values) >= 2:
                    slope = (self.y_values[-1] - self.y_values[-2]) / (self.x_values[-1] - self.x_values[-2] + 1e-10)
                    cal_p = self.y_values[-1] + slope * (p - self.x_values[-1])
                    cal_p = max(0.0, min(1.0, cal_p))
                else:
                    cal_p = self.y_values[-1]
            else:
                # Binary search for interpolation
                idx = bisect.bisect_right(self.x_values, p) - 1
                idx = max(0, min(idx, len(self.x_values) - 2))

                # Linear interpolation
                x0, x1 = self.x_values[idx], self.x_values[idx + 1]
                y0, y1 = self.y_values[idx], self.y_values[idx + 1]

                if x1 - x0 > 1e-10:
                    t = (p - x0) / (x1 - x0)
                    cal_p = y0 + t * (y1 - y0)
                else:
                    cal_p = (y0 + y1) / 2

            calibrated.append(max(0.0, min(1.0, cal_p)))

        return calibrated

    def get_params(self) -> dict[str, Any]:
        """Get isotonic regression parameters"""
        params = super().get_params()
        params.update({
            "n_interpolation_points": len(self.x_values),
            "out_of_bounds": self.out_of_bounds
        })
        return params


# ============================================================================
# Temperature Scaling for Neural Networks
# ============================================================================

class TemperatureScalingCalibrator(BaseCalibrator):
    """
    Temperature Scaling: Single-parameter calibration for neural networks.

    Divides logits by temperature T before applying softmax:
    P(y=1|z) = sigmoid(z / T)

    Simple yet effective for modern neural networks.
    Preserves accuracy while improving calibration.
    """

    def __init__(
        self,
        initial_temperature: float = 1.0,
        learning_rate: float = 0.01,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ):
        super().__init__(CalibratorType.TEMPERATURE_SCALING)
        self.temperature: float = initial_temperature
        self.learning_rate = learning_rate
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def _predictions_to_logits(self, predictions: list[float]) -> list[float]:
        """Convert probability predictions to logits"""
        logits = []
        for p in predictions:
            # Clip to avoid log(0) or log(1)
            p = max(1e-7, min(1 - 1e-7, p))
            logit = math.log(p / (1 - p))
            logits.append(logit)
        return logits

    def _logits_to_predictions(self, logits: list[float], temperature: float) -> list[float]:
        """Convert temperature-scaled logits back to probabilities"""
        predictions = []
        for z in logits:
            scaled_z = z / temperature
            # Numerically stable sigmoid
            if scaled_z >= 0:
                p = 1 / (1 + math.exp(-scaled_z))
            else:
                exp_z = math.exp(scaled_z)
                p = exp_z / (1 + exp_z)
            predictions.append(p)
        return predictions

    def _compute_nll(self, predictions: list[float], labels: list[int]) -> float:
        """Compute negative log-likelihood loss"""
        nll = 0.0
        for p, y in zip(predictions, labels):
            p = max(1e-7, min(1 - 1e-7, p))
            if y == 1:
                nll -= math.log(p)
            else:
                nll -= math.log(1 - p)
        return nll / len(predictions)

    def fit(self, predictions: list[float], labels: list[int]) -> 'TemperatureScalingCalibrator':
        """
        Fit temperature parameter using gradient descent on NLL.
        """
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Convert predictions to logits
        logits = self._predictions_to_logits(predictions)

        # Optimize temperature using gradient descent
        self.temperature = 1.0
        prev_loss = float('inf')

        for iteration in range(self.max_iterations):
            # Forward pass
            scaled_preds = self._logits_to_predictions(logits, self.temperature)
            loss = self._compute_nll(scaled_preds, labels)

            # Compute gradient of NLL w.r.t. temperature
            gradient = 0.0
            for i, (z, y, p) in enumerate(zip(logits, labels, scaled_preds)):
                # d(NLL)/d(T) = -sum((y - p) * z / T^2)
                gradient += -(y - p) * z / (self.temperature ** 2)
            gradient /= n

            # Update temperature
            self.temperature -= self.learning_rate * gradient

            # Ensure temperature stays positive
            self.temperature = max(0.1, min(10.0, self.temperature))

            # Check convergence
            if abs(prev_loss - loss) < self.tolerance:
                break
            prev_loss = loss

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        logger.info(f"TemperatureScaling fitted: T={self.temperature:.4f}")
        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply temperature scaling calibration"""
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        logits = self._predictions_to_logits(predictions)
        return self._logits_to_predictions(logits, self.temperature)

    def get_params(self) -> dict[str, Any]:
        """Get temperature scaling parameters"""
        params = super().get_params()
        params.update({
            "temperature": self.temperature,
            "learning_rate": self.learning_rate,
            "max_iterations": self.max_iterations
        })
        return params


# ============================================================================
# Beta Calibration
# ============================================================================

class BetaCalibrator(BaseCalibrator):
    """
    Beta Calibration: Uses beta distribution to model calibration.

    Maps predictions through: P(y=1|f) = 1 / (1 + 1/exp(a*log(f/(1-f)) + b))

    More flexible than Platt scaling, handles different types of
    miscalibration including asymmetric errors.

    Reference: Kull et al., "Beta calibration: a well-founded and
    easily implemented improvement on logistic calibration for binary classifiers"
    """

    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6):
        super().__init__(CalibratorType.BETA_CALIBRATION)
        self.a: float = 1.0   # Scale parameter for positive class
        self.b: float = 0.0   # Shift parameter
        self.c: float = 1.0   # Scale parameter for negative class (optional)
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self._use_three_params = False

    def _log_odds(self, p: float) -> float:
        """Compute log-odds (logit) safely"""
        p = max(1e-7, min(1 - 1e-7, p))
        return math.log(p / (1 - p))

    def _beta_transform(self, f: float) -> float:
        """Apply beta calibration transformation"""
        logit_f = self._log_odds(f)
        transformed = self.a * logit_f + self.b

        # Sigmoid
        if transformed >= 0:
            return 1 / (1 + math.exp(-transformed))
        else:
            exp_t = math.exp(transformed)
            return exp_t / (1 + exp_t)

    def fit(self, predictions: list[float], labels: list[int]) -> 'BetaCalibrator':
        """
        Fit beta calibration parameters using maximum likelihood.
        """
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Convert to log-odds space
        log_odds = [self._log_odds(p) for p in predictions]

        # Initialize parameters
        self.a = 1.0
        self.b = 0.0

        # Gradient descent optimization
        lr = 0.1
        prev_loss = float('inf')

        for iteration in range(self.max_iterations):
            # Compute predictions and loss
            total_loss = 0.0
            grad_a = 0.0
            grad_b = 0.0

            for i, (lo, y) in enumerate(zip(log_odds, labels)):
                # Forward pass
                z = self.a * lo + self.b
                if z >= 0:
                    p = 1 / (1 + math.exp(-z))
                else:
                    exp_z = math.exp(z)
                    p = exp_z / (1 + exp_z)

                # NLL loss
                p_clip = max(1e-7, min(1 - 1e-7, p))
                if y == 1:
                    total_loss -= math.log(p_clip)
                else:
                    total_loss -= math.log(1 - p_clip)

                # Gradients
                error = y - p
                grad_a += -error * lo
                grad_b += -error

            # Update parameters
            self.a -= lr * grad_a / n
            self.b -= lr * grad_b / n

            # Constrain a to be positive
            self.a = max(0.1, self.a)

            total_loss /= n

            # Check convergence
            if abs(prev_loss - total_loss) < self.tolerance:
                break
            prev_loss = total_loss

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        logger.info(f"BetaCalibration fitted: a={self.a:.4f}, b={self.b:.4f}")
        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply beta calibration"""
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        return [self._beta_transform(p) for p in predictions]

    def get_params(self) -> dict[str, Any]:
        """Get beta calibration parameters"""
        params = super().get_params()
        params.update({
            "a": self.a,
            "b": self.b,
            "c": self.c if self._use_three_params else None
        })
        return params


# ============================================================================
# Venn-ABERS Calibration
# ============================================================================

class VennABERSCalibrator(BaseCalibrator):
    """
    Venn-ABERS Calibration: Provides valid probability bounds.

    Instead of a single calibrated probability, provides an interval [p0, p1]
    that is guaranteed to contain the true probability under exchangeability.

    Key properties:
    - Validity: The calibrated probability interval contains the true probability
    - Uses isotonic regression as the underlying calibrator
    - Provides multi-probabilistic predictions

    Reference: Vovk and Petej, "Venn-Abers predictors" (2012)
    """

    def __init__(self):
        super().__init__(CalibratorType.VENN_ABERS)
        self.iso_calibrator_0: Optional[IsotonicRegressionCalibrator] = None
        self.iso_calibrator_1: Optional[IsotonicRegressionCalibrator] = None
        self._predictions: list[float] = []
        self._labels: list[int] = []

    def fit(self, predictions: list[float], labels: list[int]) -> 'VennABERSCalibrator':
        """
        Fit Venn-ABERS calibrator by training two isotonic regressors.
        """
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Store training data for online updates
        self._predictions = predictions.copy()
        self._labels = labels.copy()

        # Fit isotonic regressor assuming new point is class 0
        self.iso_calibrator_0 = IsotonicRegressionCalibrator()
        labels_with_0 = labels + [0]  # Hypothetical class 0
        preds_for_0 = predictions  # Will be updated in calibrate
        self.iso_calibrator_0.fit(predictions, labels)

        # Fit isotonic regressor assuming new point is class 1
        self.iso_calibrator_1 = IsotonicRegressionCalibrator()
        labels_with_1 = labels + [1]  # Hypothetical class 1
        self.iso_calibrator_1.fit(predictions, labels)

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        logger.info("VennABERS fitted with isotonic regressors")
        return self

    def calibrate_with_bounds(self, predictions: list[float]) -> list[tuple[float, float, float]]:
        """
        Apply Venn-ABERS calibration returning probability bounds.

        Returns:
            List of (p0, p1, point_estimate) tuples where:
            - p0: Lower probability bound (assuming instance is class 0)
            - p1: Upper probability bound (assuming instance is class 1)
            - point_estimate: Recommended single probability value
        """
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        results = []

        for pred in predictions:
            # Calibrate assuming the new point is class 0
            extended_preds_0 = self._predictions + [pred]
            extended_labels_0 = self._labels + [0]
            temp_iso_0 = IsotonicRegressionCalibrator()
            temp_iso_0.fit(extended_preds_0, extended_labels_0)
            p0 = temp_iso_0.calibrate([pred])[0]

            # Calibrate assuming the new point is class 1
            extended_preds_1 = self._predictions + [pred]
            extended_labels_1 = self._labels + [1]
            temp_iso_1 = IsotonicRegressionCalibrator()
            temp_iso_1.fit(extended_preds_1, extended_labels_1)
            p1 = temp_iso_1.calibrate([pred])[0]

            # Ensure p0 <= p1
            if p0 > p1:
                p0, p1 = p1, p0

            # Point estimate: average of bounds
            point_estimate = (p0 + p1) / 2

            results.append((p0, p1, point_estimate))

        return results

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply Venn-ABERS calibration returning point estimates"""
        bounds = self.calibrate_with_bounds(predictions)
        return [b[2] for b in bounds]  # Return point estimates

    def get_probability_interval(self, prediction: float) -> tuple[float, float]:
        """Get probability interval for a single prediction"""
        bounds = self.calibrate_with_bounds([prediction])
        return bounds[0][0], bounds[0][1]

    def get_params(self) -> dict[str, Any]:
        """Get Venn-ABERS parameters"""
        params = super().get_params()
        params.update({
            "training_size": len(self._predictions),
            "provides_bounds": True
        })
        return params


# ============================================================================
# Histogram Binning Calibrator
# ============================================================================

class HistogramBinningCalibrator(BaseCalibrator):
    """
    Histogram Binning: Simple non-parametric calibration.

    Divides predictions into bins and uses the empirical accuracy
    in each bin as the calibrated probability.
    """

    def __init__(self, n_bins: int = 15, strategy: str = "uniform"):
        super().__init__(CalibratorType.HISTOGRAM_BINNING)
        self.n_bins = n_bins
        self.strategy = strategy  # "uniform" or "quantile"
        self.bin_edges: list[float] = []
        self.bin_values: list[float] = []
        self.bin_counts: list[int] = []

    def fit(self, predictions: list[float], labels: list[int]) -> 'HistogramBinningCalibrator':
        """Fit histogram binning calibrator"""
        n = len(predictions)
        if n == 0:
            raise ValueError("Cannot fit on empty data")

        # Determine bin edges
        if self.strategy == "uniform":
            self.bin_edges = [i / self.n_bins for i in range(self.n_bins + 1)]
        else:  # quantile
            sorted_preds = sorted(predictions)
            self.bin_edges = [0.0]
            for i in range(1, self.n_bins):
                idx = int(i * n / self.n_bins)
                self.bin_edges.append(sorted_preds[idx])
            self.bin_edges.append(1.0)

        # Compute bin values (empirical accuracy)
        self.bin_values = []
        self.bin_counts = []

        for i in range(self.n_bins):
            left, right = self.bin_edges[i], self.bin_edges[i + 1]

            bin_labels = [
                labels[j] for j, p in enumerate(predictions)
                if left <= p < right or (i == self.n_bins - 1 and p == right)
            ]

            if bin_labels:
                self.bin_values.append(sum(bin_labels) / len(bin_labels))
                self.bin_counts.append(len(bin_labels))
            else:
                # Empty bin - use midpoint as default
                self.bin_values.append((left + right) / 2)
                self.bin_counts.append(0)

        self.is_fitted = True
        self.fit_timestamp = datetime.now()

        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply histogram binning calibration"""
        if not self.is_fitted:
            raise RuntimeError("Calibrator must be fitted before calibrating")

        calibrated = []

        for p in predictions:
            # Find bin
            bin_idx = 0
            for i in range(self.n_bins):
                if p >= self.bin_edges[i]:
                    bin_idx = i
            bin_idx = min(bin_idx, self.n_bins - 1)

            calibrated.append(self.bin_values[bin_idx])

        return calibrated


# ============================================================================
# Calibration Metrics Calculator
# ============================================================================

class CalibrationMetricsCalculator:
    """
    Computes calibration metrics for evaluating model calibration.
    """

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def compute_ece(
        self,
        predictions: list[float],
        labels: list[int],
        weights: Optional[list[float]] = None
    ) -> float:
        """
        Compute Expected Calibration Error (ECE).

        ECE = sum(bin_weight * |accuracy - confidence|) for all bins
        """
        n = len(predictions)
        if n == 0:
            return 0.0

        if weights is None:
            weights = [1.0] * n

        # Create bins
        bin_accuracies = [0.0] * self.n_bins
        bin_confidences = [0.0] * self.n_bins
        bin_weights = [0.0] * self.n_bins

        for p, y, w in zip(predictions, labels, weights):
            bin_idx = min(int(p * self.n_bins), self.n_bins - 1)
            bin_accuracies[bin_idx] += w * y
            bin_confidences[bin_idx] += w * p
            bin_weights[bin_idx] += w

        # Compute ECE
        total_weight = sum(bin_weights)
        ece = 0.0

        for i in range(self.n_bins):
            if bin_weights[i] > 0:
                acc = bin_accuracies[i] / bin_weights[i]
                conf = bin_confidences[i] / bin_weights[i]
                ece += (bin_weights[i] / total_weight) * abs(acc - conf)

        return ece

    def compute_mce(self, predictions: list[float], labels: list[int]) -> float:
        """
        Compute Maximum Calibration Error (MCE).

        MCE = max(|accuracy - confidence|) across all bins
        """
        n = len(predictions)
        if n == 0:
            return 0.0

        max_gap = 0.0

        for i in range(self.n_bins):
            left, right = i / self.n_bins, (i + 1) / self.n_bins

            bin_preds = [(p, y) for p, y in zip(predictions, labels) if left <= p < right]

            if bin_preds:
                acc = sum(y for _, y in bin_preds) / len(bin_preds)
                conf = sum(p for p, _ in bin_preds) / len(bin_preds)
                gap = abs(acc - conf)
                max_gap = max(max_gap, gap)

        return max_gap

    def compute_brier_score(self, predictions: list[float], labels: list[int]) -> float:
        """
        Compute Brier Score.

        Brier = mean((prediction - label)^2)
        """
        n = len(predictions)
        if n == 0:
            return 0.0

        return sum((p - y) ** 2 for p, y in zip(predictions, labels)) / n

    def compute_log_loss(self, predictions: list[float], labels: list[int]) -> float:
        """
        Compute Log Loss / Cross-Entropy.
        """
        n = len(predictions)
        if n == 0:
            return 0.0

        eps = 1e-15
        ll = 0.0

        for p, y in zip(predictions, labels):
            p = max(eps, min(1 - eps, p))
            if y == 1:
                ll -= math.log(p)
            else:
                ll -= math.log(1 - p)

        return ll / n

    def compute_calibration_curve(
        self,
        predictions: list[float],
        labels: list[int]
    ) -> tuple[float, float]:
        """
        Fit a calibration curve and return slope and intercept.

        Uses linear regression on (confidence, accuracy) pairs.
        """
        # Compute bin-wise statistics
        bin_accuracies = []
        bin_confidences = []

        for i in range(self.n_bins):
            left, right = i / self.n_bins, (i + 1) / self.n_bins

            bin_preds = [(p, y) for p, y in zip(predictions, labels) if left <= p < right]

            if len(bin_preds) >= 5:  # Minimum samples per bin
                acc = sum(y for _, y in bin_preds) / len(bin_preds)
                conf = sum(p for p, _ in bin_preds) / len(bin_preds)
                bin_accuracies.append(acc)
                bin_confidences.append(conf)

        if len(bin_confidences) < 2:
            return 1.0, 0.0  # Default to perfect calibration

        # Linear regression: accuracy = slope * confidence + intercept
        n = len(bin_confidences)
        x_mean = sum(bin_confidences) / n
        y_mean = sum(bin_accuracies) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(bin_confidences, bin_accuracies))
        denominator = sum((x - x_mean) ** 2 for x in bin_confidences)

        if abs(denominator) < 1e-10:
            slope = 1.0
        else:
            slope = numerator / denominator

        intercept = y_mean - slope * x_mean

        return slope, intercept

    def compute_sharpness(self, predictions: list[float]) -> float:
        """
        Compute sharpness (variance of predictions).

        Higher sharpness means more confident predictions.
        """
        n = len(predictions)
        if n == 0:
            return 0.0

        mean_p = sum(predictions) / n
        return sum((p - mean_p) ** 2 for p in predictions) / n

    def compute_all_metrics(
        self,
        predictions: list[float],
        labels: list[int]
    ) -> CalibrationMetrics:
        """Compute all calibration metrics"""
        slope, intercept = self.compute_calibration_curve(predictions, labels)

        # Compute per-bin statistics for the metrics object
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []

        for i in range(self.n_bins):
            left, right = i / self.n_bins, (i + 1) / self.n_bins
            bin_preds = [(p, y) for p, y in zip(predictions, labels) if left <= p < right]

            if bin_preds:
                bin_accuracies.append(sum(y for _, y in bin_preds) / len(bin_preds))
                bin_confidences.append(sum(p for p, _ in bin_preds) / len(bin_preds))
                bin_counts.append(len(bin_preds))
            else:
                bin_accuracies.append((left + right) / 2)
                bin_confidences.append((left + right) / 2)
                bin_counts.append(0)

        ece = self.compute_ece(predictions, labels)
        mce = self.compute_mce(predictions, labels)
        brier = self.compute_brier_score(predictions, labels)

        return CalibrationMetrics(
            ece=ece,
            mce=mce,
            brier_score=brier,
            log_loss=self.compute_log_loss(predictions, labels),
            calibration_slope=slope,
            calibration_intercept=intercept,
            reliability_score=1.0 - ece,  # Higher is better
            sharpness=self.compute_sharpness(predictions),
            refinement=brier - ece,  # Decomposition of Brier
            bin_accuracies=bin_accuracies,
            bin_confidences=bin_confidences,
            bin_counts=bin_counts
        )


# ============================================================================
# Reliability Diagram Generator
# ============================================================================

class ReliabilityDiagramGenerator:
    """
    Generates reliability diagrams for visualizing calibration.
    """

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins

    def generate(
        self,
        predictions: list[float],
        labels: list[int]
    ) -> ReliabilityDiagram:
        """Generate reliability diagram data"""
        bin_edges = [i / self.n_bins for i in range(self.n_bins + 1)]
        bin_centers = [(i + 0.5) / self.n_bins for i in range(self.n_bins)]
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []
        gap_areas = []

        for i in range(self.n_bins):
            left, right = bin_edges[i], bin_edges[i + 1]

            bin_preds = [
                (p, y) for p, y in zip(predictions, labels)
                if left <= p < right or (i == self.n_bins - 1 and p == right)
            ]

            if bin_preds:
                acc = sum(y for _, y in bin_preds) / len(bin_preds)
                conf = sum(p for p, _ in bin_preds) / len(bin_preds)
                count = len(bin_preds)
            else:
                acc = bin_centers[i]
                conf = bin_centers[i]
                count = 0

            bin_accuracies.append(acc)
            bin_confidences.append(conf)
            bin_counts.append(count)
            gap_areas.append(abs(acc - conf) * count)

        return ReliabilityDiagram(
            n_bins=self.n_bins,
            bin_edges=bin_edges,
            bin_centers=bin_centers,
            bin_accuracies=bin_accuracies,
            bin_confidences=bin_confidences,
            bin_counts=bin_counts,
            perfect_calibration_line=[(x, x) for x in [0.0, 0.25, 0.5, 0.75, 1.0]],
            gap_areas=gap_areas
        )

    def generate_ascii_diagram(
        self,
        predictions: list[float],
        labels: list[int],
        width: int = 60,
        height: int = 20
    ) -> str:
        """Generate ASCII reliability diagram for terminal display"""
        diagram = self.generate(predictions, labels)

        lines = []
        lines.append("Reliability Diagram")
        lines.append("=" * width)
        lines.append("")
        lines.append("Accuracy")
        lines.append("  ^")

        # Create grid
        for row in range(height, -1, -1):
            y_val = row / height
            line = f"{y_val:.1f}|"

            for col in range(self.n_bins):
                x_start = col * (width - 4) // self.n_bins
                x_end = (col + 1) * (width - 4) // self.n_bins

                acc = diagram.bin_accuracies[col]
                conf = diagram.bin_confidences[col]
                count = diagram.bin_counts[col]

                # Check if this row should have a bar
                if count > 0 and row / height <= acc < (row + 1) / height:
                    line += "#" * (x_end - x_start)
                elif row / height <= conf < (row + 1) / height:
                    line += "." * (x_end - x_start)
                else:
                    line += " " * (x_end - x_start)

            lines.append(line)

        lines.append("   " + "-" * (width - 4) + "> Confidence")
        lines.append("   0.0" + " " * (width - 12) + "1.0")
        lines.append("")
        lines.append("Legend: # = Accuracy, . = Confidence")

        return "\n".join(lines)


# ============================================================================
# Automatic Calibrator Selection
# ============================================================================

class AutoCalibratorSelector:
    """
    Automatically selects the best calibration method for a given dataset.

    Uses cross-validation to compare different calibration methods and
    selects the one with the best ECE on held-out data.
    """

    def __init__(
        self,
        calibrators: Optional[list[CalibratorType]] = None,
        n_folds: int = 5,
        target_ece: float = 0.03
    ):
        if calibrators is None:
            self.calibrators = [
                CalibratorType.PLATT_SCALING,
                CalibratorType.ISOTONIC_REGRESSION,
                CalibratorType.TEMPERATURE_SCALING,
                CalibratorType.BETA_CALIBRATION,
                CalibratorType.HISTOGRAM_BINNING
            ]
        else:
            self.calibrators = calibrators

        self.n_folds = n_folds
        self.target_ece = target_ece
        self.selection_results: dict[CalibratorType, dict[str, Any]] = {}

    def _create_calibrator(self, calibrator_type: CalibratorType) -> BaseCalibrator:
        """Factory method to create calibrator instances"""
        if calibrator_type == CalibratorType.PLATT_SCALING:
            return PlattScalingCalibrator()
        elif calibrator_type == CalibratorType.ISOTONIC_REGRESSION:
            return IsotonicRegressionCalibrator()
        elif calibrator_type == CalibratorType.TEMPERATURE_SCALING:
            return TemperatureScalingCalibrator()
        elif calibrator_type == CalibratorType.BETA_CALIBRATION:
            return BetaCalibrator()
        elif calibrator_type == CalibratorType.VENN_ABERS:
            return VennABERSCalibrator()
        elif calibrator_type == CalibratorType.HISTOGRAM_BINNING:
            return HistogramBinningCalibrator()
        else:
            raise ValueError(f"Unknown calibrator type: {calibrator_type}")

    def select(
        self,
        predictions: list[float],
        labels: list[int]
    ) -> tuple[CalibratorType, BaseCalibrator]:
        """
        Select the best calibrator using cross-validation.

        Returns:
            Tuple of (best_calibrator_type, fitted_calibrator)
        """
        n = len(predictions)
        metrics_calc = CalibrationMetricsCalculator()

        # Shuffle data
        indices = list(range(n))
        random.shuffle(indices)

        # Split into folds
        fold_size = n // self.n_folds
        folds = [indices[i * fold_size:(i + 1) * fold_size] for i in range(self.n_folds)]

        # Handle remainder
        for i, idx in enumerate(indices[self.n_folds * fold_size:]):
            folds[i % self.n_folds].append(idx)

        # Evaluate each calibrator
        for cal_type in self.calibrators:
            fold_eces = []
            fold_mces = []
            fold_briers = []

            for fold_idx in range(self.n_folds):
                # Split data
                val_indices = folds[fold_idx]
                train_indices = [idx for i, fold in enumerate(folds) if i != fold_idx for idx in fold]

                train_preds = [predictions[i] for i in train_indices]
                train_labels = [labels[i] for i in train_indices]
                val_preds = [predictions[i] for i in val_indices]
                val_labels = [labels[i] for i in val_indices]

                # Fit and calibrate
                try:
                    calibrator = self._create_calibrator(cal_type)
                    calibrator.fit(train_preds, train_labels)
                    calibrated = calibrator.calibrate(val_preds)

                    # Compute metrics
                    ece = metrics_calc.compute_ece(calibrated, val_labels)
                    mce = metrics_calc.compute_mce(calibrated, val_labels)
                    brier = metrics_calc.compute_brier_score(calibrated, val_labels)

                    fold_eces.append(ece)
                    fold_mces.append(mce)
                    fold_briers.append(brier)
                except Exception as e:
                    logger.warning(f"Calibrator {cal_type.value} failed on fold {fold_idx}: {e}")
                    fold_eces.append(1.0)  # Penalty for failure
                    fold_mces.append(1.0)
                    fold_briers.append(1.0)

            # Store results
            self.selection_results[cal_type] = {
                "mean_ece": sum(fold_eces) / len(fold_eces),
                "std_ece": (sum((x - sum(fold_eces) / len(fold_eces)) ** 2 for x in fold_eces) / len(fold_eces)) ** 0.5,
                "mean_mce": sum(fold_mces) / len(fold_mces),
                "mean_brier": sum(fold_briers) / len(fold_briers),
                "meets_target": sum(fold_eces) / len(fold_eces) < self.target_ece
            }

        # Select best calibrator based on ECE
        best_type = min(
            self.selection_results.keys(),
            key=lambda ct: self.selection_results[ct]["mean_ece"]
        )

        # Fit on full dataset
        best_calibrator = self._create_calibrator(best_type)
        best_calibrator.fit(predictions, labels)

        logger.info(f"Selected calibrator: {best_type.value} (ECE: {self.selection_results[best_type]['mean_ece']:.4f})")

        return best_type, best_calibrator

    def get_selection_report(self) -> dict[str, Any]:
        """Get detailed selection report"""
        return {
            "calibrators_evaluated": [ct.value for ct in self.calibrators],
            "results": {ct.value: res for ct, res in self.selection_results.items()},
            "best_calibrator": min(
                self.selection_results.keys(),
                key=lambda ct: self.selection_results[ct]["mean_ece"]
            ).value if self.selection_results else None
        }


# ============================================================================
# Cohort Calibration Analyzer
# ============================================================================

class CohortCalibrationAnalyzer:
    """
    Analyzes calibration quality across different cohorts.

    Identifies cohorts with poor calibration and recommends
    cohort-specific calibrators.
    """

    def __init__(
        self,
        cohort_definitions: Optional[dict[str, Callable[[dict], bool]]] = None
    ):
        self.cohort_definitions = cohort_definitions or {}
        self.cohort_results: dict[str, CohortCalibration] = {}

    def add_cohort(self, name: str, filter_fn: Callable[[dict], bool]):
        """Add a cohort definition"""
        self.cohort_definitions[name] = filter_fn

    def analyze(
        self,
        dataset: CalibrationDataset,
        calibrator: Optional[BaseCalibrator] = None
    ) -> dict[str, CohortCalibration]:
        """
        Analyze calibration across all defined cohorts.
        """
        metrics_calc = CalibrationMetricsCalculator()

        # If no features, cannot do cohort analysis
        if not dataset.features:
            logger.warning("No features in dataset - cannot perform cohort analysis")
            return {}

        # Apply calibration if calibrator provided
        if calibrator and calibrator.is_fitted:
            predictions = calibrator.calibrate(dataset.predictions)
        else:
            predictions = dataset.predictions

        # Analyze each cohort
        for cohort_name, filter_fn in self.cohort_definitions.items():
            # Get cohort indices
            cohort_indices = [
                i for i, features in enumerate(dataset.features)
                if filter_fn(features)
            ]

            if len(cohort_indices) < 10:
                logger.warning(f"Cohort '{cohort_name}' has fewer than 10 samples - skipping")
                continue

            cohort_preds = [predictions[i] for i in cohort_indices]
            cohort_labels = [dataset.labels[i] for i in cohort_indices]

            # Compute metrics
            metrics = metrics_calc.compute_all_metrics(cohort_preds, cohort_labels)

            # Store result
            self.cohort_results[cohort_name] = CohortCalibration(
                cohort_name=cohort_name,
                cohort_filter={"function": filter_fn.__name__ if hasattr(filter_fn, '__name__') else str(filter_fn)},
                sample_size=len(cohort_indices),
                metrics=metrics,
                calibrator_type=calibrator.calibrator_type if calibrator else CalibratorType.PLATT_SCALING
            )

        return self.cohort_results

    def get_poorly_calibrated_cohorts(self, ece_threshold: float = 0.05) -> list[str]:
        """Get list of cohorts with ECE above threshold"""
        return [
            name for name, result in self.cohort_results.items()
            if result.metrics.ece > ece_threshold
        ]

    def get_summary_report(self) -> dict[str, Any]:
        """Generate cohort calibration summary"""
        if not self.cohort_results:
            return {"error": "No cohort analysis performed yet"}

        return {
            "cohorts_analyzed": len(self.cohort_results),
            "cohort_metrics": {
                name: {
                    "sample_size": result.sample_size,
                    "ece": result.metrics.ece,
                    "mce": result.metrics.mce,
                    "slope": result.metrics.calibration_slope,
                    "intercept": result.metrics.calibration_intercept,
                    "meets_target": result.metrics.meets_target()
                }
                for name, result in self.cohort_results.items()
            },
            "poorly_calibrated": self.get_poorly_calibrated_cohorts()
        }


# ============================================================================
# Post-Hoc Calibration Pipeline
# ============================================================================

class PostHocCalibrationPipeline:
    """
    Complete post-hoc calibration pipeline.

    Provides end-to-end calibration workflow including:
    - Dataset management
    - Automatic calibrator selection
    - Cross-validation
    - Cohort analysis
    - Metrics tracking
    """

    def __init__(
        self,
        target_ece: float = 0.03,
        target_slope: tuple[float, float] = (0.9, 1.1),
        target_intercept: tuple[float, float] = (-0.05, 0.05)
    ):
        self.target_ece = target_ece
        self.target_slope = target_slope
        self.target_intercept = target_intercept

        self.calibrator: Optional[BaseCalibrator] = None
        self.calibrator_type: Optional[CalibratorType] = None
        self.train_metrics: Optional[CalibrationMetrics] = None
        self.val_metrics: Optional[CalibrationMetrics] = None

        self.metrics_calculator = CalibrationMetricsCalculator()
        self.diagram_generator = ReliabilityDiagramGenerator()
        self.cohort_analyzer = CohortCalibrationAnalyzer()
        self.auto_selector = AutoCalibratorSelector(target_ece=target_ece)

        self.pipeline_history: list[dict[str, Any]] = []

    def fit(
        self,
        dataset: CalibrationDataset,
        calibrator_type: Optional[CalibratorType] = None,
        validation_split: float = 0.2
    ) -> 'PostHocCalibrationPipeline':
        """
        Fit the calibration pipeline.

        Args:
            dataset: Calibration dataset
            calibrator_type: Specific calibrator to use, or None for auto-selection
            validation_split: Fraction of data for validation
        """
        # Split dataset
        train_data, val_data = dataset.split(1 - validation_split)

        # Select or create calibrator
        if calibrator_type is None:
            self.calibrator_type, self.calibrator = self.auto_selector.select(
                train_data.predictions,
                train_data.labels
            )
        else:
            self.calibrator_type = calibrator_type
            self.calibrator = self.auto_selector._create_calibrator(calibrator_type)
            self.calibrator.fit(train_data.predictions, train_data.labels)

        # Compute training metrics
        train_calibrated = self.calibrator.calibrate(train_data.predictions)
        self.train_metrics = self.metrics_calculator.compute_all_metrics(
            train_calibrated,
            train_data.labels
        )

        # Compute validation metrics
        val_calibrated = self.calibrator.calibrate(val_data.predictions)
        self.val_metrics = self.metrics_calculator.compute_all_metrics(
            val_calibrated,
            val_data.labels
        )

        # Log results
        logger.info(f"Pipeline fitted with {self.calibrator_type.value}")
        logger.info(f"  Train ECE: {self.train_metrics.ece:.4f}")
        logger.info(f"  Val ECE: {self.val_metrics.ece:.4f}")
        logger.info(f"  Val Slope: {self.val_metrics.calibration_slope:.4f}")
        logger.info(f"  Val Intercept: {self.val_metrics.calibration_intercept:.4f}")

        # Record history
        self.pipeline_history.append({
            "timestamp": datetime.now().isoformat(),
            "calibrator": self.calibrator_type.value,
            "train_size": train_data.size,
            "val_size": val_data.size,
            "train_ece": self.train_metrics.ece,
            "val_ece": self.val_metrics.ece,
            "meets_target": self.val_metrics.meets_target(self.target_ece)
        })

        return self

    def calibrate(self, predictions: list[float]) -> list[float]:
        """Apply fitted calibration to new predictions"""
        if self.calibrator is None or not self.calibrator.is_fitted:
            raise RuntimeError("Pipeline must be fitted before calibrating")

        return self.calibrator.calibrate(predictions)

    def evaluate(
        self,
        predictions: list[float],
        labels: list[int]
    ) -> CalibrationMetrics:
        """Evaluate calibration on new data"""
        if self.calibrator is None:
            raise RuntimeError("Pipeline must be fitted before evaluating")

        calibrated = self.calibrator.calibrate(predictions)
        return self.metrics_calculator.compute_all_metrics(calibrated, labels)

    def generate_reliability_diagram(
        self,
        predictions: list[float],
        labels: list[int],
        apply_calibration: bool = True
    ) -> ReliabilityDiagram:
        """Generate reliability diagram for predictions"""
        if apply_calibration and self.calibrator is not None:
            preds = self.calibrator.calibrate(predictions)
        else:
            preds = predictions

        return self.diagram_generator.generate(preds, labels)

    def add_cohort_definition(self, name: str, filter_fn: Callable[[dict], bool]):
        """Add a cohort definition for analysis"""
        self.cohort_analyzer.add_cohort(name, filter_fn)

    def analyze_cohorts(self, dataset: CalibrationDataset) -> dict[str, CohortCalibration]:
        """Analyze calibration across cohorts"""
        return self.cohort_analyzer.analyze(dataset, self.calibrator)

    def meets_targets(self) -> bool:
        """Check if calibration meets all target criteria"""
        if self.val_metrics is None:
            return False

        return self.val_metrics.meets_target(self.target_ece)

    def get_summary(self) -> dict[str, Any]:
        """Get pipeline summary"""
        return {
            "calibrator_type": self.calibrator_type.value if self.calibrator_type else None,
            "is_fitted": self.calibrator is not None and self.calibrator.is_fitted,
            "train_metrics": self.train_metrics.summary() if self.train_metrics else None,
            "val_metrics": self.val_metrics.summary() if self.val_metrics else None,
            "meets_targets": self.meets_targets(),
            "targets": {
                "ece": self.target_ece,
                "slope_range": self.target_slope,
                "intercept_range": self.target_intercept
            },
            "auto_selection_report": self.auto_selector.get_selection_report(),
            "history_length": len(self.pipeline_history)
        }


# ============================================================================
# Main Calibration Engine
# ============================================================================

class CalibrationEngine:
    """
    Main calibration engine providing high-level API for model calibration.

    Features:
    - Multiple calibration methods
    - Automatic method selection
    - Cohort-specific calibration
    - Comprehensive metrics
    - Reliability diagrams

    Target: ECE < 0.03, calibration slope near 1.0, intercept near 0.0
    """

    # Target thresholds
    TARGET_ECE = 0.03
    TARGET_SLOPE_RANGE = (0.9, 1.1)
    TARGET_INTERCEPT_RANGE = (-0.05, 0.05)

    def __init__(self):
        self.pipelines: dict[str, PostHocCalibrationPipeline] = {}
        self.active_pipeline: Optional[str] = None
        self.calibration_history: list[dict[str, Any]] = []

        logger.info("CalibrationEngine initialized")
        logger.info(f"  Target ECE: < {self.TARGET_ECE}")
        logger.info(f"  Target Slope: {self.TARGET_SLOPE_RANGE}")
        logger.info(f"  Target Intercept: {self.TARGET_INTERCEPT_RANGE}")

    def create_pipeline(
        self,
        name: str,
        target_ece: Optional[float] = None
    ) -> PostHocCalibrationPipeline:
        """Create a new calibration pipeline"""
        pipeline = PostHocCalibrationPipeline(
            target_ece=target_ece or self.TARGET_ECE,
            target_slope=self.TARGET_SLOPE_RANGE,
            target_intercept=self.TARGET_INTERCEPT_RANGE
        )

        self.pipelines[name] = pipeline
        self.active_pipeline = name

        logger.info(f"Created pipeline: {name}")
        return pipeline

    def fit_pipeline(
        self,
        pipeline_name: str,
        predictions: list[float],
        labels: list[int],
        features: Optional[list[dict[str, Any]]] = None,
        cohort_ids: Optional[list[str]] = None,
        calibrator_type: Optional[CalibratorType] = None
    ) -> CalibrationMetrics:
        """
        Fit a calibration pipeline on provided data.
        """
        if pipeline_name not in self.pipelines:
            self.create_pipeline(pipeline_name)

        pipeline = self.pipelines[pipeline_name]

        # Create dataset
        dataset = CalibrationDataset(
            predictions=predictions,
            labels=labels,
            features=features,
            cohort_ids=cohort_ids
        )

        # Fit pipeline
        pipeline.fit(dataset, calibrator_type)

        # Record history
        self.calibration_history.append({
            "timestamp": datetime.now().isoformat(),
            "pipeline": pipeline_name,
            "calibrator": pipeline.calibrator_type.value,
            "train_ece": pipeline.train_metrics.ece,
            "val_ece": pipeline.val_metrics.ece,
            "meets_target": pipeline.meets_targets()
        })

        return pipeline.val_metrics

    def calibrate(
        self,
        predictions: list[float],
        pipeline_name: Optional[str] = None
    ) -> list[float]:
        """Apply calibration to predictions"""
        name = pipeline_name or self.active_pipeline

        if name is None or name not in self.pipelines:
            raise ValueError(f"Pipeline '{name}' not found")

        return self.pipelines[name].calibrate(predictions)

    def evaluate(
        self,
        predictions: list[float],
        labels: list[int],
        pipeline_name: Optional[str] = None,
        apply_calibration: bool = True
    ) -> CalibrationMetrics:
        """Evaluate calibration quality"""
        metrics_calc = CalibrationMetricsCalculator()

        if not apply_calibration:
            # No calibration needed, just compute metrics on raw predictions
            return metrics_calc.compute_all_metrics(predictions, labels)

        name = pipeline_name or self.active_pipeline

        if name is None or name not in self.pipelines:
            raise ValueError(f"Pipeline '{name}' not found")

        pipeline = self.pipelines[name]
        calibrated = pipeline.calibrate(predictions)
        return metrics_calc.compute_all_metrics(calibrated, labels)

    def compare_calibrators(
        self,
        predictions: list[float],
        labels: list[int],
        calibrators: Optional[list[CalibratorType]] = None
    ) -> dict[str, CalibrationMetrics]:
        """Compare different calibration methods"""
        if calibrators is None:
            calibrators = [
                CalibratorType.PLATT_SCALING,
                CalibratorType.ISOTONIC_REGRESSION,
                CalibratorType.TEMPERATURE_SCALING,
                CalibratorType.BETA_CALIBRATION,
                CalibratorType.HISTOGRAM_BINNING
            ]

        metrics_calc = CalibrationMetricsCalculator()
        auto_selector = AutoCalibratorSelector()

        results = {}

        # Original (uncalibrated)
        results["uncalibrated"] = metrics_calc.compute_all_metrics(predictions, labels)

        # Each calibrator
        for cal_type in calibrators:
            try:
                calibrator = auto_selector._create_calibrator(cal_type)
                calibrator.fit(predictions, labels)
                calibrated = calibrator.calibrate(predictions)
                results[cal_type.value] = metrics_calc.compute_all_metrics(calibrated, labels)
            except Exception as e:
                logger.warning(f"Calibrator {cal_type.value} failed: {e}")

        return results

    def get_reliability_diagram(
        self,
        predictions: list[float],
        labels: list[int],
        pipeline_name: Optional[str] = None,
        apply_calibration: bool = True
    ) -> ReliabilityDiagram:
        """Generate reliability diagram"""
        name = pipeline_name or self.active_pipeline

        if apply_calibration and name and name in self.pipelines:
            preds = self.pipelines[name].calibrate(predictions)
        else:
            preds = predictions

        generator = ReliabilityDiagramGenerator()
        return generator.generate(preds, labels)

    def get_status(self) -> dict[str, Any]:
        """Get engine status"""
        return {
            "pipelines": list(self.pipelines.keys()),
            "active_pipeline": self.active_pipeline,
            "targets": {
                "ece": self.TARGET_ECE,
                "slope_range": self.TARGET_SLOPE_RANGE,
                "intercept_range": self.TARGET_INTERCEPT_RANGE
            },
            "history_length": len(self.calibration_history),
            "pipeline_summaries": {
                name: pipeline.get_summary()
                for name, pipeline in self.pipelines.items()
            }
        }


# ============================================================================
# Demonstration
# ============================================================================

def demonstrate_calibration():
    """Demonstrate calibration layer functionality"""
    print("=" * 75)
    print("  MODEL CALIBRATION LAYER DEMONSTRATION")
    print("  Target: ECE < 0.03, Slope ~ 1.0, Intercept ~ 0.0")
    print("=" * 75)
    print()

    # Generate synthetic uncalibrated predictions
    random.seed(42)
    n_samples = 1000

    # Create biased predictions (overconfident)
    true_probs = [random.random() for _ in range(n_samples)]
    labels = [1 if random.random() < p else 0 for p in true_probs]

    # Make predictions overconfident (push toward extremes)
    predictions = []
    for p in true_probs:
        # Add bias and noise
        biased = p ** 0.7  # Overconfident transformation
        noisy = biased + random.gauss(0, 0.1)
        predictions.append(max(0.01, min(0.99, noisy)))

    print(f"Generated {n_samples} synthetic predictions")
    print(f"  Positive rate: {sum(labels) / len(labels):.1%}")
    print()

    # Initialize engine
    engine = CalibrationEngine()

    # Evaluate uncalibrated predictions
    print("-" * 75)
    print("UNCALIBRATED PREDICTIONS:")
    print("-" * 75)

    uncal_metrics = engine.evaluate(predictions, labels, apply_calibration=False)
    print(f"  ECE:       {uncal_metrics.ece:.4f}")
    print(f"  MCE:       {uncal_metrics.mce:.4f}")
    print(f"  Brier:     {uncal_metrics.brier_score:.4f}")
    print(f"  Slope:     {uncal_metrics.calibration_slope:.4f}")
    print(f"  Intercept: {uncal_metrics.calibration_intercept:.4f}")
    print(f"  Meets Target: {uncal_metrics.meets_target()}")
    print()

    # Compare different calibrators
    print("-" * 75)
    print("CALIBRATOR COMPARISON:")
    print("-" * 75)

    comparison = engine.compare_calibrators(predictions, labels)

    print(f"{'Method':<25} {'ECE':>10} {'MCE':>10} {'Slope':>10} {'Intercept':>10}")
    print("-" * 65)

    for method, metrics in sorted(comparison.items(), key=lambda x: x[1].ece):
        print(f"{method:<25} {metrics.ece:>10.4f} {metrics.mce:>10.4f} "
              f"{metrics.calibration_slope:>10.4f} {metrics.calibration_intercept:>10.4f}")
    print()

    # Fit full pipeline with auto-selection
    print("-" * 75)
    print("FITTING CALIBRATION PIPELINE (Auto-Selection):")
    print("-" * 75)

    metrics = engine.fit_pipeline(
        "production",
        predictions,
        labels
    )

    print()
    print(f"Selected: {engine.pipelines['production'].calibrator_type.value}")
    print(f"  Val ECE:       {metrics.ece:.4f}")
    print(f"  Val MCE:       {metrics.mce:.4f}")
    print(f"  Val Slope:     {metrics.calibration_slope:.4f}")
    print(f"  Val Intercept: {metrics.calibration_intercept:.4f}")
    print(f"  Meets Target:  {metrics.meets_target()}")
    print()

    # Apply calibration and verify
    print("-" * 75)
    print("CALIBRATED PREDICTIONS:")
    print("-" * 75)

    calibrated_preds = engine.calibrate(predictions)
    cal_metrics = CalibrationMetricsCalculator().compute_all_metrics(calibrated_preds, labels)

    print(f"  ECE:       {cal_metrics.ece:.4f} (target < 0.03)")
    print(f"  MCE:       {cal_metrics.mce:.4f}")
    print(f"  Slope:     {cal_metrics.calibration_slope:.4f} (target 0.9-1.1)")
    print(f"  Intercept: {cal_metrics.calibration_intercept:.4f} (target -0.05 to 0.05)")
    print()

    # Demonstrate individual calibrators
    print("-" * 75)
    print("INDIVIDUAL CALIBRATOR EXAMPLES:")
    print("-" * 75)
    print()

    # Platt Scaling
    platt = PlattScalingCalibrator()
    platt.fit(predictions, labels)
    print(f"Platt Scaling:  A={platt.A:.4f}, B={platt.B:.4f}")

    # Temperature Scaling
    temp = TemperatureScalingCalibrator()
    temp.fit(predictions, labels)
    print(f"Temperature:    T={temp.temperature:.4f}")

    # Beta Calibration
    beta = BetaCalibrator()
    beta.fit(predictions, labels)
    print(f"Beta:           a={beta.a:.4f}, b={beta.b:.4f}")

    # Isotonic points
    iso = IsotonicRegressionCalibrator()
    iso.fit(predictions, labels)
    print(f"Isotonic:       {len(iso.x_values)} interpolation points")

    # Venn-ABERS bounds example
    venn = VennABERSCalibrator()
    venn.fit(predictions, labels)
    p0, p1 = venn.get_probability_interval(0.7)
    print(f"Venn-ABERS:     P(0.7) -> [{p0:.3f}, {p1:.3f}]")
    print()

    # Pipeline summary
    print("-" * 75)
    print("PIPELINE STATUS:")
    print("-" * 75)

    status = engine.get_status()
    print(f"  Active Pipeline: {status['active_pipeline']}")
    print(f"  Total Pipelines: {len(status['pipelines'])}")
    print(f"  History Length:  {status['history_length']}")
    print()

    print("=" * 75)
    print("  CALIBRATION COMPLETE")
    print(f"  Final ECE: {cal_metrics.ece:.4f} (Target: < 0.03)")
    print(f"  Status: {'PASSED' if cal_metrics.ece < 0.03 else 'NEEDS IMPROVEMENT'}")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_calibration()
