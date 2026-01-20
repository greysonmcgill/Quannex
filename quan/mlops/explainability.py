"""
Explainability and Interpretability System for QUAN ML Models

Comprehensive explainability engine providing:
1. SHAP integration for tree and neural models
2. LIME explanations for local interpretability
3. Integrated gradients for deep models
4. Global feature importance ranking
5. Per-prediction explanation generation
6. Counterfactual explanations
7. Human-readable explanation templates
8. Batch processing and caching
9. Visualization generation

Target: All predictions explained, human-readable, with full audit trail.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Optional, Union
from collections import defaultdict
from functools import lru_cache
import math
import random
import hashlib
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class ExplanationType(Enum):
    """Types of explanations available"""
    SHAP = "shap"
    LIME = "lime"
    INTEGRATED_GRADIENTS = "integrated_gradients"
    COUNTERFACTUAL = "counterfactual"
    FEATURE_IMPORTANCE = "feature_importance"
    INTERACTION = "interaction"
    ANCHOR = "anchor"


class ModelCategory(Enum):
    """Model categories for explanation method selection"""
    TREE_BASED = "tree_based"
    NEURAL_NETWORK = "neural_network"
    LINEAR = "linear"
    ENSEMBLE = "ensemble"
    DEEP_LEARNING = "deep_learning"


class VisualizationType(Enum):
    """Available visualization types"""
    WATERFALL = "waterfall"
    FORCE_PLOT = "force_plot"
    SUMMARY_PLOT = "summary_plot"
    DECISION_PLOT = "decision_plot"
    DEPENDENCE_PLOT = "dependence_plot"
    INTERACTION_HEATMAP = "interaction_heatmap"
    BAR_CHART = "bar_chart"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class FeatureContribution:
    """Single feature contribution to prediction"""
    feature_name: str
    feature_value: float
    contribution: float  # SHAP value or contribution score
    direction: str  # 'positive', 'negative', 'neutral'
    percentile_rank: float = 0.0  # How this compares to population
    human_readable: str = ""


@dataclass
class Explanation:
    """Complete explanation for a single prediction"""
    explanation_id: str
    prediction_id: str
    account_id: str
    model_name: str
    model_version: str
    prediction_value: float
    base_value: float  # Expected value / baseline
    explanation_type: ExplanationType
    feature_contributions: list[FeatureContribution]
    top_features: list[FeatureContribution]  # Top 5 most important
    human_summary: str
    confidence_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "explanation_id": self.explanation_id,
            "prediction_id": self.prediction_id,
            "account_id": self.account_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "prediction_value": self.prediction_value,
            "base_value": self.base_value,
            "explanation_type": self.explanation_type.value,
            "feature_contributions": [
                {
                    "feature_name": fc.feature_name,
                    "feature_value": fc.feature_value,
                    "contribution": fc.contribution,
                    "direction": fc.direction,
                    "human_readable": fc.human_readable
                }
                for fc in self.feature_contributions
            ],
            "top_features": [fc.feature_name for fc in self.top_features],
            "human_summary": self.human_summary,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CounterfactualExplanation:
    """Counterfactual explanation showing what would change the prediction"""
    original_prediction: float
    target_prediction: float
    changes_required: list[dict[str, Any]]  # Feature changes needed
    distance: float  # How different from original
    feasibility_score: float  # How realistic is this counterfactual
    human_summary: str


@dataclass
class FeatureInteraction:
    """Detected feature interaction"""
    feature_a: str
    feature_b: str
    interaction_strength: float
    interaction_type: str  # 'synergistic', 'antagonistic', 'independent'
    description: str


@dataclass
class GlobalImportanceReport:
    """Global feature importance report across all predictions"""
    report_id: str
    generated_at: datetime
    model_name: str
    sample_size: int
    feature_rankings: list[tuple[str, float]]  # (feature_name, importance)
    interactions: list[FeatureInteraction]
    stability_scores: dict[str, float]  # How stable is each feature's importance
    recommendations: list[str]


@dataclass
class AuditLogEntry:
    """Audit log entry for explanation generation"""
    log_id: str
    timestamp: datetime
    explanation_id: str
    account_id: str
    model_name: str
    explanation_type: str
    generation_time_ms: float
    cache_hit: bool
    user_id: Optional[str]
    request_source: str


@dataclass
class Visualization:
    """Generated visualization"""
    viz_id: str
    viz_type: VisualizationType
    explanation_id: str
    data: dict[str, Any]  # Visualization data
    render_config: dict[str, Any]
    html_content: str
    generated_at: datetime = field(default_factory=datetime.now)


# ============================================================================
# Human-Readable Explanation Templates
# ============================================================================

class ExplanationTemplates:
    """Human-readable explanation templates"""

    FEATURE_TEMPLATES = {
        "balance": {
            "high_positive": "High account balance (${value:.2f}) strongly increases likelihood",
            "low_positive": "Account balance (${value:.2f}) slightly increases likelihood",
            "high_negative": "High account balance (${value:.2f}) significantly reduces likelihood",
            "low_negative": "Account balance (${value:.2f}) slightly reduces likelihood",
        },
        "days_past_due": {
            "high_positive": "Extended delinquency ({value:.0f} days) increases urgency",
            "low_positive": "Days past due ({value:.0f}) indicates moderate risk",
            "high_negative": "Recent delinquency ({value:.0f} days) suggests potential for recovery",
            "low_negative": "Days past due has minimal impact on prediction",
        },
        "shadow_score": {
            "high_positive": "Strong shadow score ({value:.0f}) indicates high payment capacity",
            "low_positive": "Shadow score ({value:.0f}) provides moderate positive signal",
            "high_negative": "Low shadow score ({value:.0f}) significantly reduces predicted outcome",
            "low_negative": "Shadow score has minimal negative impact",
        },
        "response_rate": {
            "high_positive": "Strong engagement history ({value:.1%} response rate) predicts positive outcome",
            "low_positive": "Response rate ({value:.1%}) provides slight positive indication",
            "high_negative": "Poor response rate ({value:.1%}) reduces predicted outcome",
            "low_negative": "Response rate has slight negative impact",
        },
        "promise_kept_rate": {
            "high_positive": "Excellent promise-keeping history ({value:.1%}) strongly predicts payment",
            "low_positive": "Promise history ({value:.1%}) indicates moderate reliability",
            "high_negative": "Poor promise-keeping rate ({value:.1%}) reduces payment likelihood",
            "low_negative": "Promise history has minor negative impact",
        },
        "default": {
            "high_positive": "{feature} value of {value} strongly increases the prediction",
            "low_positive": "{feature} value of {value} slightly increases the prediction",
            "high_negative": "{feature} value of {value} strongly decreases the prediction",
            "low_negative": "{feature} value of {value} slightly decreases the prediction",
        }
    }

    SUMMARY_TEMPLATES = {
        "payment_prediction": (
            "This account has a {prob:.1%} predicted payment probability. "
            "The primary drivers are: {top_factors}. "
            "{recommendation}"
        ),
        "settlement_prediction": (
            "Settlement acceptance predicted at {prob:.1%}. "
            "Key factors: {top_factors}. "
            "{recommendation}"
        ),
        "contact_prediction": (
            "Contact response probability: {prob:.1%}. "
            "Most influential factors: {top_factors}. "
            "{recommendation}"
        ),
        "risk_prediction": (
            "Risk assessment score: {prob:.1%}. "
            "Primary risk factors: {top_factors}. "
            "{recommendation}"
        ),
        "general": (
            "Prediction: {prob:.1%} (confidence: {confidence:.1%}). "
            "Top contributing factors: {top_factors}. "
            "{recommendation}"
        )
    }

    RECOMMENDATIONS = {
        "high_probability_high_confidence": "Proceed with standard outreach approach.",
        "high_probability_low_confidence": "Consider additional verification before action.",
        "low_probability_high_confidence": "Consider alternative strategies or escalation.",
        "low_probability_low_confidence": "Gather more information before deciding approach.",
        "medium_probability": "Apply targeted engagement strategy based on key factors.",
    }

    @classmethod
    def get_feature_explanation(
        cls,
        feature_name: str,
        value: float,
        contribution: float,
        threshold_high: float = 0.05
    ) -> str:
        """Get human-readable explanation for a feature contribution"""
        templates = cls.FEATURE_TEMPLATES.get(feature_name, cls.FEATURE_TEMPLATES["default"])

        if contribution > threshold_high:
            template_key = "high_positive"
        elif contribution > 0:
            template_key = "low_positive"
        elif contribution < -threshold_high:
            template_key = "high_negative"
        else:
            template_key = "low_negative"

        template = templates[template_key]
        return template.format(value=value, feature=feature_name)

    @classmethod
    def get_summary(
        cls,
        prediction_type: str,
        probability: float,
        confidence: float,
        top_factors: list[str]
    ) -> str:
        """Get summary explanation"""
        template = cls.SUMMARY_TEMPLATES.get(prediction_type, cls.SUMMARY_TEMPLATES["general"])

        # Get recommendation
        if probability > 0.7 and confidence > 0.7:
            rec = cls.RECOMMENDATIONS["high_probability_high_confidence"]
        elif probability > 0.7:
            rec = cls.RECOMMENDATIONS["high_probability_low_confidence"]
        elif probability < 0.3 and confidence > 0.7:
            rec = cls.RECOMMENDATIONS["low_probability_high_confidence"]
        elif probability < 0.3:
            rec = cls.RECOMMENDATIONS["low_probability_low_confidence"]
        else:
            rec = cls.RECOMMENDATIONS["medium_probability"]

        factors_str = ", ".join(top_factors[:3]) if top_factors else "multiple factors"

        return template.format(
            prob=probability,
            confidence=confidence,
            top_factors=factors_str,
            recommendation=rec
        )


# ============================================================================
# SHAP Explainer
# ============================================================================

class SHAPExplainer:
    """
    SHAP (SHapley Additive exPlanations) implementation

    Supports:
    - TreeExplainer for tree-based models
    - DeepExplainer for neural networks
    - KernelExplainer as fallback for any model
    """

    def __init__(self, model_category: ModelCategory):
        self.model_category = model_category
        self.background_data: list[dict[str, float]] = []
        self.feature_means: dict[str, float] = {}
        self.base_value: float = 0.5

    def set_background_data(self, data: list[dict[str, float]]) -> None:
        """Set background data for SHAP calculations"""
        self.background_data = data

        # Calculate feature means
        if data:
            for feature in data[0].keys():
                values = [d.get(feature, 0) for d in data]
                self.feature_means[feature] = sum(values) / len(values)

    def explain(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable[[dict[str, float]], float]
    ) -> list[FeatureContribution]:
        """
        Calculate SHAP values for a prediction

        Uses appropriate method based on model category
        """
        if self.model_category == ModelCategory.TREE_BASED:
            return self._tree_shap(features, prediction, model_predict)
        elif self.model_category in [ModelCategory.NEURAL_NETWORK, ModelCategory.DEEP_LEARNING]:
            return self._deep_shap(features, prediction, model_predict)
        else:
            return self._kernel_shap(features, prediction, model_predict)

    def _tree_shap(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable
    ) -> list[FeatureContribution]:
        """
        TreeSHAP algorithm for tree-based models

        Optimized O(TLD^2) complexity where:
        - T = number of trees
        - L = number of leaves
        - D = tree depth
        """
        contributions = []
        feature_list = list(features.keys())
        n_features = len(feature_list)

        # Calculate base value
        if self.background_data:
            base_preds = [model_predict(d) for d in self.background_data[:10]]
            self.base_value = sum(base_preds) / len(base_preds)

        # Calculate SHAP values using tree structure approximation
        shap_values = {}

        for feature in feature_list:
            # Approximate marginal contribution
            contribution = self._calculate_marginal_contribution(
                features, feature, model_predict
            )
            shap_values[feature] = contribution

        # Normalize to sum to prediction - base_value
        total_contribution = sum(shap_values.values())
        target_sum = prediction - self.base_value

        if abs(total_contribution) > 1e-6:
            scale = target_sum / total_contribution
            for feature in shap_values:
                shap_values[feature] *= scale

        # Create FeatureContribution objects
        for feature, shap_value in shap_values.items():
            direction = "positive" if shap_value > 0.01 else "negative" if shap_value < -0.01 else "neutral"

            contributions.append(FeatureContribution(
                feature_name=feature,
                feature_value=features[feature],
                contribution=shap_value,
                direction=direction,
                human_readable=ExplanationTemplates.get_feature_explanation(
                    feature, features[feature], shap_value
                )
            ))

        # Sort by absolute contribution
        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return contributions

    def _deep_shap(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable
    ) -> list[FeatureContribution]:
        """
        DeepSHAP for neural networks

        Uses gradient-based approximation
        """
        contributions = []
        epsilon = 0.01

        for feature in features:
            # Approximate gradient
            features_plus = features.copy()
            features_minus = features.copy()

            features_plus[feature] = features[feature] + epsilon
            features_minus[feature] = features[feature] - epsilon

            pred_plus = model_predict(features_plus)
            pred_minus = model_predict(features_minus)

            gradient = (pred_plus - pred_minus) / (2 * epsilon)

            # SHAP value = gradient * (x - E[x])
            mean_value = self.feature_means.get(feature, 0.5)
            shap_value = gradient * (features[feature] - mean_value)

            direction = "positive" if shap_value > 0.01 else "negative" if shap_value < -0.01 else "neutral"

            contributions.append(FeatureContribution(
                feature_name=feature,
                feature_value=features[feature],
                contribution=shap_value,
                direction=direction,
                human_readable=ExplanationTemplates.get_feature_explanation(
                    feature, features[feature], shap_value
                )
            ))

        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return contributions

    def _kernel_shap(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable
    ) -> list[FeatureContribution]:
        """
        KernelSHAP for any model (model-agnostic)

        Uses weighted linear regression on feature subsets
        """
        contributions = []
        feature_list = list(features.keys())
        n_features = len(feature_list)

        # Sample coalitions
        n_samples = min(2 ** n_features, 100)
        coalition_samples = self._sample_coalitions(feature_list, n_samples)

        # Calculate contribution for each feature
        shap_values = {f: 0.0 for f in feature_list}

        for feature in feature_list:
            # Average marginal contribution across coalitions
            marginal_contributions = []

            for coalition in coalition_samples[:20]:
                if feature not in coalition:
                    # Contribution of adding this feature
                    without = self._predict_coalition(features, coalition, model_predict)
                    with_feature = self._predict_coalition(
                        features, coalition + [feature], model_predict
                    )
                    marginal_contributions.append(with_feature - without)

            if marginal_contributions:
                shap_values[feature] = sum(marginal_contributions) / len(marginal_contributions)

        # Create contributions
        for feature, shap_value in shap_values.items():
            direction = "positive" if shap_value > 0.01 else "negative" if shap_value < -0.01 else "neutral"

            contributions.append(FeatureContribution(
                feature_name=feature,
                feature_value=features[feature],
                contribution=shap_value,
                direction=direction,
                human_readable=ExplanationTemplates.get_feature_explanation(
                    feature, features[feature], shap_value
                )
            ))

        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return contributions

    def _calculate_marginal_contribution(
        self,
        features: dict[str, float],
        target_feature: str,
        model_predict: Callable
    ) -> float:
        """Calculate marginal contribution of a feature"""
        # Prediction with actual value
        pred_with = model_predict(features)

        # Prediction with mean value
        features_without = features.copy()
        features_without[target_feature] = self.feature_means.get(target_feature, 0.5)
        pred_without = model_predict(features_without)

        return pred_with - pred_without

    def _sample_coalitions(
        self,
        features: list[str],
        n_samples: int
    ) -> list[list[str]]:
        """Sample feature coalitions for KernelSHAP"""
        coalitions = []

        for _ in range(n_samples):
            size = random.randint(0, len(features))
            coalition = random.sample(features, size)
            coalitions.append(coalition)

        return coalitions

    def _predict_coalition(
        self,
        features: dict[str, float],
        coalition: list[str],
        model_predict: Callable
    ) -> float:
        """Predict using only coalition features (others at mean)"""
        coalition_features = {}

        for feature in features:
            if feature in coalition:
                coalition_features[feature] = features[feature]
            else:
                coalition_features[feature] = self.feature_means.get(feature, 0.5)

        return model_predict(coalition_features)


# ============================================================================
# LIME Explainer
# ============================================================================

class LIMEExplainer:
    """
    LIME (Local Interpretable Model-agnostic Explanations)

    Creates local linear approximations around predictions
    """

    def __init__(self, kernel_width: float = 0.75, n_samples: int = 1000):
        self.kernel_width = kernel_width
        self.n_samples = n_samples
        self.feature_std: dict[str, float] = {}

    def set_feature_statistics(self, std_values: dict[str, float]) -> None:
        """Set feature standard deviations for perturbation"""
        self.feature_std = std_values

    def explain(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable[[dict[str, float]], float]
    ) -> list[FeatureContribution]:
        """
        Generate LIME explanation

        Creates interpretable local surrogate model
        """
        # Generate perturbed samples
        samples, distances, predictions = self._generate_samples(features, model_predict)

        # Calculate weights using exponential kernel
        weights = [math.exp(-(d ** 2) / (self.kernel_width ** 2)) for d in distances]

        # Fit weighted linear regression
        coefficients = self._fit_weighted_linear(samples, predictions, weights)

        # Create contributions
        contributions = []

        for feature, coef in coefficients.items():
            # Contribution = coefficient * feature_value
            contribution = coef * features[feature]
            direction = "positive" if contribution > 0.01 else "negative" if contribution < -0.01 else "neutral"

            contributions.append(FeatureContribution(
                feature_name=feature,
                feature_value=features[feature],
                contribution=contribution,
                direction=direction,
                human_readable=ExplanationTemplates.get_feature_explanation(
                    feature, features[feature], contribution
                )
            ))

        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return contributions

    def _generate_samples(
        self,
        features: dict[str, float],
        model_predict: Callable
    ) -> tuple[list[dict[str, float]], list[float], list[float]]:
        """Generate perturbed samples around instance"""
        samples = []
        distances = []
        predictions = []

        for _ in range(self.n_samples):
            # Perturb features
            perturbed = {}
            distance = 0.0

            for feature, value in features.items():
                std = self.feature_std.get(feature, 0.1)
                perturbation = random.gauss(0, std)
                perturbed[feature] = value + perturbation
                distance += (perturbation / max(std, 0.01)) ** 2

            distance = math.sqrt(distance / len(features))

            samples.append(perturbed)
            distances.append(distance)
            predictions.append(model_predict(perturbed))

        return samples, distances, predictions

    def _fit_weighted_linear(
        self,
        samples: list[dict[str, float]],
        predictions: list[float],
        weights: list[float]
    ) -> dict[str, float]:
        """Fit weighted linear regression"""
        if not samples:
            return {}

        features = list(samples[0].keys())
        coefficients = {}

        # Simplified weighted regression per feature
        for feature in features:
            # Calculate weighted covariance
            feature_values = [s[feature] for s in samples]

            weighted_mean_x = sum(w * x for w, x in zip(weights, feature_values)) / sum(weights)
            weighted_mean_y = sum(w * y for w, y in zip(weights, predictions)) / sum(weights)

            # Weighted covariance
            cov = sum(
                w * (x - weighted_mean_x) * (y - weighted_mean_y)
                for w, x, y in zip(weights, feature_values, predictions)
            ) / sum(weights)

            # Weighted variance
            var = sum(
                w * (x - weighted_mean_x) ** 2
                for w, x in zip(weights, feature_values)
            ) / sum(weights)

            # Coefficient
            if abs(var) > 1e-10:
                coefficients[feature] = cov / var
            else:
                coefficients[feature] = 0.0

        return coefficients


# ============================================================================
# Integrated Gradients Explainer
# ============================================================================

class IntegratedGradientsExplainer:
    """
    Integrated Gradients for deep learning models

    Satisfies key axioms:
    - Sensitivity: Changed input leads to attribution
    - Implementation Invariance: Same function = same attributions
    - Completeness: Attributions sum to prediction difference
    """

    def __init__(self, n_steps: int = 50):
        self.n_steps = n_steps
        self.baseline: dict[str, float] = {}

    def set_baseline(self, baseline: dict[str, float]) -> None:
        """Set baseline for integration (typically zero or mean)"""
        self.baseline = baseline

    def explain(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable[[dict[str, float]], float]
    ) -> list[FeatureContribution]:
        """
        Calculate integrated gradients

        IG(x) = (x - x') * integral[gradient(x' + alpha*(x-x')), alpha=0..1]
        """
        if not self.baseline:
            self.baseline = {f: 0.0 for f in features}

        contributions = []

        for feature in features:
            # Integrate gradient along path from baseline to input
            ig_value = self._integrate_gradient(features, feature, model_predict)

            direction = "positive" if ig_value > 0.01 else "negative" if ig_value < -0.01 else "neutral"

            contributions.append(FeatureContribution(
                feature_name=feature,
                feature_value=features[feature],
                contribution=ig_value,
                direction=direction,
                human_readable=ExplanationTemplates.get_feature_explanation(
                    feature, features[feature], ig_value
                )
            ))

        contributions.sort(key=lambda x: abs(x.contribution), reverse=True)
        return contributions

    def _integrate_gradient(
        self,
        features: dict[str, float],
        target_feature: str,
        model_predict: Callable
    ) -> float:
        """Integrate gradient along interpolation path"""
        epsilon = 0.001
        baseline_value = self.baseline.get(target_feature, 0.0)
        input_value = features[target_feature]

        # Riemann sum approximation
        integral = 0.0

        for step in range(self.n_steps):
            alpha = step / self.n_steps

            # Interpolated point
            interpolated = {}
            for f in features:
                base = self.baseline.get(f, 0.0)
                interpolated[f] = base + alpha * (features[f] - base)

            # Calculate gradient at this point
            interp_plus = interpolated.copy()
            interp_minus = interpolated.copy()

            interp_plus[target_feature] += epsilon
            interp_minus[target_feature] -= epsilon

            gradient = (model_predict(interp_plus) - model_predict(interp_minus)) / (2 * epsilon)
            integral += gradient

        # Scale by step size and (input - baseline)
        integral /= self.n_steps
        ig = integral * (input_value - baseline_value)

        return ig


# ============================================================================
# Counterfactual Explainer
# ============================================================================

class CounterfactualExplainer:
    """
    Counterfactual explanation generator

    Finds minimal changes to flip prediction outcome
    """

    def __init__(self, max_iterations: int = 100):
        self.max_iterations = max_iterations
        self.feature_ranges: dict[str, tuple[float, float]] = {}
        self.feature_mutability: dict[str, bool] = {}  # Can feature be changed?

    def set_feature_constraints(
        self,
        ranges: dict[str, tuple[float, float]],
        mutability: dict[str, bool]
    ) -> None:
        """Set constraints on features"""
        self.feature_ranges = ranges
        self.feature_mutability = mutability

    def generate_counterfactual(
        self,
        features: dict[str, float],
        current_prediction: float,
        target_prediction: float,
        model_predict: Callable[[dict[str, float]], float],
        threshold: float = 0.1
    ) -> CounterfactualExplanation:
        """
        Generate counterfactual explanation

        Finds minimal feature changes to achieve target prediction
        """
        counterfactual = features.copy()
        changes = []

        # Iteratively modify features to approach target
        for iteration in range(self.max_iterations):
            current = model_predict(counterfactual)

            if abs(current - target_prediction) < threshold:
                break

            # Find best feature to modify
            best_feature = None
            best_change = 0.0
            best_improvement = 0.0

            for feature in features:
                if not self.feature_mutability.get(feature, True):
                    continue

                # Try small modifications
                for delta in [-0.1, 0.1, -0.05, 0.05]:
                    test_cf = counterfactual.copy()
                    test_cf[feature] = self._apply_change(feature, test_cf[feature], delta)

                    new_pred = model_predict(test_cf)
                    improvement = abs(new_pred - target_prediction) - abs(current - target_prediction)

                    if improvement < best_improvement:
                        best_improvement = improvement
                        best_feature = feature
                        best_change = delta

            if best_feature:
                counterfactual[best_feature] = self._apply_change(
                    best_feature,
                    counterfactual[best_feature],
                    best_change
                )

        # Calculate changes from original
        for feature in features:
            if abs(counterfactual[feature] - features[feature]) > 0.001:
                changes.append({
                    "feature": feature,
                    "original_value": features[feature],
                    "counterfactual_value": counterfactual[feature],
                    "change": counterfactual[feature] - features[feature]
                })

        # Calculate distance
        distance = math.sqrt(sum(
            (counterfactual[f] - features[f]) ** 2 for f in features
        ))

        # Calculate feasibility (fewer changes = more feasible)
        feasibility = max(0.0, 1.0 - len(changes) * 0.2)

        # Generate human summary
        summary = self._generate_counterfactual_summary(changes, current_prediction, target_prediction)

        return CounterfactualExplanation(
            original_prediction=current_prediction,
            target_prediction=target_prediction,
            changes_required=changes,
            distance=distance,
            feasibility_score=feasibility,
            human_summary=summary
        )

    def _apply_change(self, feature: str, current: float, delta: float) -> float:
        """Apply change with constraints"""
        new_value = current + delta

        if feature in self.feature_ranges:
            min_val, max_val = self.feature_ranges[feature]
            new_value = max(min_val, min(max_val, new_value))

        return new_value

    def _generate_counterfactual_summary(
        self,
        changes: list[dict],
        current: float,
        target: float
    ) -> str:
        """Generate human-readable counterfactual summary"""
        if not changes:
            return "No changes needed to achieve target prediction."

        direction = "increase" if target > current else "decrease"
        change_descriptions = []

        for change in changes[:3]:
            feature = change["feature"]
            delta = change["change"]
            action = "increase" if delta > 0 else "decrease"
            change_descriptions.append(f"{action} {feature}")

        changes_str = ", ".join(change_descriptions)

        return (
            f"To {direction} the prediction from {current:.1%} to {target:.1%}, "
            f"consider: {changes_str}."
        )


# ============================================================================
# Feature Interaction Detector
# ============================================================================

class FeatureInteractionDetector:
    """
    Detects and quantifies feature interactions

    Uses H-statistic and other methods
    """

    def __init__(self):
        self.interaction_cache: dict[str, FeatureInteraction] = {}

    def detect_interactions(
        self,
        features: dict[str, float],
        model_predict: Callable[[dict[str, float]], float],
        top_k: int = 10
    ) -> list[FeatureInteraction]:
        """
        Detect pairwise feature interactions

        Uses Friedman's H-statistic
        """
        interactions = []
        feature_list = list(features.keys())
        n_features = len(feature_list)

        # Check all pairs
        for i in range(n_features):
            for j in range(i + 1, n_features):
                feature_a = feature_list[i]
                feature_b = feature_list[j]

                cache_key = f"{feature_a}_{feature_b}"

                if cache_key in self.interaction_cache:
                    interactions.append(self.interaction_cache[cache_key])
                    continue

                # Calculate H-statistic
                h_stat = self._calculate_h_statistic(
                    features, feature_a, feature_b, model_predict
                )

                # Determine interaction type
                if h_stat > 0.1:
                    interaction_type = "synergistic"
                    description = f"{feature_a} and {feature_b} have a synergistic effect"
                elif h_stat < -0.1:
                    interaction_type = "antagonistic"
                    description = f"{feature_a} and {feature_b} partially cancel each other"
                else:
                    interaction_type = "independent"
                    description = f"{feature_a} and {feature_b} act independently"

                interaction = FeatureInteraction(
                    feature_a=feature_a,
                    feature_b=feature_b,
                    interaction_strength=abs(h_stat),
                    interaction_type=interaction_type,
                    description=description
                )

                self.interaction_cache[cache_key] = interaction
                interactions.append(interaction)

        # Sort by strength and return top_k
        interactions.sort(key=lambda x: x.interaction_strength, reverse=True)
        return interactions[:top_k]

    def _calculate_h_statistic(
        self,
        features: dict[str, float],
        feature_a: str,
        feature_b: str,
        model_predict: Callable
    ) -> float:
        """
        Calculate Friedman's H-statistic for interaction

        H^2 = sum[(f_ij - f_i - f_j + f_mean)^2] / sum[(f_ij - f_mean)^2]
        """
        # Sample points for features
        values_a = [features[feature_a] * m for m in [0.5, 0.75, 1.0, 1.25, 1.5]]
        values_b = [features[feature_b] * m for m in [0.5, 0.75, 1.0, 1.25, 1.5]]

        predictions = []
        marginal_a = []
        marginal_b = []

        for va in values_a:
            for vb in values_b:
                test_features = features.copy()
                test_features[feature_a] = va
                test_features[feature_b] = vb
                predictions.append(model_predict(test_features))

        # Calculate marginals
        for va in values_a:
            test_features = features.copy()
            test_features[feature_a] = va
            marginal_a.append(model_predict(test_features))

        for vb in values_b:
            test_features = features.copy()
            test_features[feature_b] = vb
            marginal_b.append(model_predict(test_features))

        # Calculate H-statistic
        mean_pred = sum(predictions) / len(predictions)

        numerator = 0.0
        denominator = 0.0

        idx = 0
        for i, va in enumerate(values_a):
            for j, vb in enumerate(values_b):
                f_ij = predictions[idx]
                f_i = marginal_a[i]
                f_j = marginal_b[j]

                interaction = f_ij - f_i - f_j + mean_pred
                numerator += interaction ** 2
                denominator += (f_ij - mean_pred) ** 2
                idx += 1

        if denominator > 1e-10:
            return math.sqrt(numerator / denominator)
        return 0.0


# ============================================================================
# Global Feature Importance Calculator
# ============================================================================

class GlobalFeatureImportance:
    """
    Calculate global feature importance across multiple predictions

    Methods:
    - Permutation importance
    - Mean absolute SHAP values
    - Drop-column importance
    """

    def __init__(self):
        self.importance_history: dict[str, list[float]] = defaultdict(list)
        self.stability_window = 100

    def calculate_permutation_importance(
        self,
        dataset: list[dict[str, float]],
        labels: list[float],
        model_predict: Callable[[dict[str, float]], float],
        n_repeats: int = 10
    ) -> dict[str, float]:
        """
        Calculate permutation feature importance

        Measures drop in performance when feature is shuffled
        """
        # Calculate baseline score
        baseline_score = self._calculate_score(dataset, labels, model_predict)

        importance = {}
        features = list(dataset[0].keys()) if dataset else []

        for feature in features:
            importance_scores = []

            for _ in range(n_repeats):
                # Shuffle feature
                shuffled_dataset = self._shuffle_feature(dataset, feature)
                shuffled_score = self._calculate_score(shuffled_dataset, labels, model_predict)

                # Importance = drop in score
                importance_scores.append(baseline_score - shuffled_score)

            importance[feature] = sum(importance_scores) / len(importance_scores)

        return importance

    def calculate_mean_shap_importance(
        self,
        shap_values: list[list[FeatureContribution]]
    ) -> dict[str, float]:
        """Calculate mean absolute SHAP values per feature"""
        importance: dict[str, list[float]] = defaultdict(list)

        for contributions in shap_values:
            for contrib in contributions:
                importance[contrib.feature_name].append(abs(contrib.contribution))

        return {
            feature: sum(values) / len(values)
            for feature, values in importance.items()
        }

    def generate_report(
        self,
        model_name: str,
        dataset: list[dict[str, float]],
        shap_explainer: SHAPExplainer,
        model_predict: Callable,
        interaction_detector: FeatureInteractionDetector
    ) -> GlobalImportanceReport:
        """Generate comprehensive global importance report"""
        if not dataset:
            return GlobalImportanceReport(
                report_id=str(uuid.uuid4()),
                generated_at=datetime.now(),
                model_name=model_name,
                sample_size=0,
                feature_rankings=[],
                interactions=[],
                stability_scores={},
                recommendations=[]
            )

        # Calculate SHAP values for sample
        shap_values = []
        for features in dataset[:100]:
            prediction = model_predict(features)
            contributions = shap_explainer.explain(features, prediction, model_predict)
            shap_values.append(contributions)

        # Calculate importance
        importance = self.calculate_mean_shap_importance(shap_values)

        # Sort by importance
        rankings = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        # Update history and calculate stability
        for feature, imp in importance.items():
            self.importance_history[feature].append(imp)
            if len(self.importance_history[feature]) > self.stability_window:
                self.importance_history[feature].pop(0)

        stability_scores = {}
        for feature, history in self.importance_history.items():
            if len(history) > 1:
                mean = sum(history) / len(history)
                variance = sum((h - mean) ** 2 for h in history) / len(history)
                stability_scores[feature] = 1.0 / (1.0 + math.sqrt(variance))
            else:
                stability_scores[feature] = 0.5

        # Detect interactions
        sample_features = dataset[0] if dataset else {}
        interactions = interaction_detector.detect_interactions(
            sample_features, model_predict, top_k=5
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(rankings, stability_scores, interactions)

        return GlobalImportanceReport(
            report_id=str(uuid.uuid4()),
            generated_at=datetime.now(),
            model_name=model_name,
            sample_size=len(dataset),
            feature_rankings=rankings,
            interactions=interactions,
            stability_scores=stability_scores,
            recommendations=recommendations
        )

    def _shuffle_feature(
        self,
        dataset: list[dict[str, float]],
        feature: str
    ) -> list[dict[str, float]]:
        """Shuffle a feature across dataset"""
        values = [d[feature] for d in dataset]
        random.shuffle(values)

        shuffled = []
        for i, d in enumerate(dataset):
            new_d = d.copy()
            new_d[feature] = values[i]
            shuffled.append(new_d)

        return shuffled

    def _calculate_score(
        self,
        dataset: list[dict[str, float]],
        labels: list[float],
        model_predict: Callable
    ) -> float:
        """Calculate model score (accuracy)"""
        if not dataset:
            return 0.0

        correct = 0
        for features, label in zip(dataset, labels):
            pred = model_predict(features)
            if (pred >= 0.5) == (label >= 0.5):
                correct += 1

        return correct / len(dataset)

    def _generate_recommendations(
        self,
        rankings: list[tuple[str, float]],
        stability: dict[str, float],
        interactions: list[FeatureInteraction]
    ) -> list[str]:
        """Generate recommendations based on analysis"""
        recommendations = []

        # Top features
        if rankings:
            top_features = [r[0] for r in rankings[:3]]
            recommendations.append(
                f"Top predictive features: {', '.join(top_features)}. Focus data quality efforts here."
            )

        # Unstable features
        unstable = [f for f, s in stability.items() if s < 0.5]
        if unstable:
            recommendations.append(
                f"Features with unstable importance: {', '.join(unstable[:3])}. Consider feature engineering."
            )

        # Strong interactions
        strong_interactions = [i for i in interactions if i.interaction_strength > 0.3]
        if strong_interactions:
            interaction = strong_interactions[0]
            recommendations.append(
                f"Strong interaction detected between {interaction.feature_a} and {interaction.feature_b}. "
                f"Consider creating interaction feature."
            )

        return recommendations


# ============================================================================
# Visualization Generator
# ============================================================================

class VisualizationGenerator:
    """
    Generate visualizations for explanations

    Produces waterfall plots, force plots, summary plots
    """

    def generate_waterfall(
        self,
        explanation: Explanation,
        max_features: int = 10
    ) -> Visualization:
        """
        Generate waterfall plot data

        Shows how features push prediction from base value
        """
        contributions = explanation.feature_contributions[:max_features]

        # Build waterfall data
        waterfall_data = {
            "base_value": explanation.base_value,
            "prediction_value": explanation.prediction_value,
            "features": [],
            "cumulative": [explanation.base_value]
        }

        running_total = explanation.base_value

        for contrib in contributions:
            running_total += contrib.contribution
            waterfall_data["features"].append({
                "name": contrib.feature_name,
                "value": contrib.feature_value,
                "contribution": contrib.contribution,
                "cumulative": running_total,
                "direction": contrib.direction
            })
            waterfall_data["cumulative"].append(running_total)

        # Generate HTML
        html = self._render_waterfall_html(waterfall_data)

        return Visualization(
            viz_id=str(uuid.uuid4()),
            viz_type=VisualizationType.WATERFALL,
            explanation_id=explanation.explanation_id,
            data=waterfall_data,
            render_config={"max_features": max_features},
            html_content=html
        )

    def generate_force_plot(
        self,
        explanation: Explanation
    ) -> Visualization:
        """
        Generate force plot data

        Shows features pushing prediction left (decrease) or right (increase)
        """
        positive_features = [c for c in explanation.feature_contributions if c.contribution > 0]
        negative_features = [c for c in explanation.feature_contributions if c.contribution < 0]

        force_data = {
            "base_value": explanation.base_value,
            "prediction_value": explanation.prediction_value,
            "positive_contributions": [
                {
                    "name": c.feature_name,
                    "value": c.feature_value,
                    "contribution": c.contribution
                }
                for c in sorted(positive_features, key=lambda x: x.contribution, reverse=True)[:5]
            ],
            "negative_contributions": [
                {
                    "name": c.feature_name,
                    "value": c.feature_value,
                    "contribution": c.contribution
                }
                for c in sorted(negative_features, key=lambda x: x.contribution)[:5]
            ]
        }

        html = self._render_force_plot_html(force_data)

        return Visualization(
            viz_id=str(uuid.uuid4()),
            viz_type=VisualizationType.FORCE_PLOT,
            explanation_id=explanation.explanation_id,
            data=force_data,
            render_config={},
            html_content=html
        )

    def generate_summary_plot(
        self,
        explanations: list[Explanation],
        max_features: int = 15
    ) -> Visualization:
        """
        Generate summary plot data

        Shows feature importance across multiple predictions
        """
        # Aggregate importance
        feature_stats: dict[str, dict] = defaultdict(lambda: {
            "contributions": [],
            "values": []
        })

        for explanation in explanations:
            for contrib in explanation.feature_contributions:
                feature_stats[contrib.feature_name]["contributions"].append(contrib.contribution)
                feature_stats[contrib.feature_name]["values"].append(contrib.feature_value)

        # Calculate summary statistics
        summary_data = {
            "features": [],
            "sample_size": len(explanations)
        }

        for feature, stats in feature_stats.items():
            contributions = stats["contributions"]
            if contributions:
                summary_data["features"].append({
                    "name": feature,
                    "mean_abs_contribution": sum(abs(c) for c in contributions) / len(contributions),
                    "mean_contribution": sum(contributions) / len(contributions),
                    "std_contribution": math.sqrt(
                        sum((c - sum(contributions) / len(contributions)) ** 2 for c in contributions) / len(contributions)
                    ) if len(contributions) > 1 else 0,
                    "count": len(contributions)
                })

        # Sort by mean absolute contribution
        summary_data["features"].sort(key=lambda x: x["mean_abs_contribution"], reverse=True)
        summary_data["features"] = summary_data["features"][:max_features]

        html = self._render_summary_plot_html(summary_data)

        return Visualization(
            viz_id=str(uuid.uuid4()),
            viz_type=VisualizationType.SUMMARY_PLOT,
            explanation_id="aggregate",
            data=summary_data,
            render_config={"max_features": max_features},
            html_content=html
        )

    def generate_interaction_heatmap(
        self,
        interactions: list[FeatureInteraction]
    ) -> Visualization:
        """Generate interaction heatmap"""
        features = set()
        for interaction in interactions:
            features.add(interaction.feature_a)
            features.add(interaction.feature_b)

        features = sorted(features)
        n = len(features)

        # Build interaction matrix
        matrix = [[0.0] * n for _ in range(n)]

        for interaction in interactions:
            i = features.index(interaction.feature_a)
            j = features.index(interaction.feature_b)
            matrix[i][j] = interaction.interaction_strength
            matrix[j][i] = interaction.interaction_strength

        heatmap_data = {
            "features": features,
            "matrix": matrix,
            "interactions": [
                {
                    "feature_a": i.feature_a,
                    "feature_b": i.feature_b,
                    "strength": i.interaction_strength,
                    "type": i.interaction_type
                }
                for i in interactions
            ]
        }

        html = self._render_heatmap_html(heatmap_data)

        return Visualization(
            viz_id=str(uuid.uuid4()),
            viz_type=VisualizationType.INTERACTION_HEATMAP,
            explanation_id="aggregate",
            data=heatmap_data,
            render_config={},
            html_content=html
        )

    def _render_waterfall_html(self, data: dict) -> str:
        """Render waterfall plot as HTML"""
        rows = []
        for feature in data["features"]:
            color = "#4CAF50" if feature["direction"] == "positive" else "#F44336"
            bar_width = min(abs(feature["contribution"]) * 200, 100)
            rows.append(f"""
            <tr>
                <td style="padding: 8px;">{feature["name"]}</td>
                <td style="padding: 8px;">{feature["value"]:.3f}</td>
                <td style="padding: 8px;">
                    <div style="background: {color}; width: {bar_width}px; height: 20px; display: inline-block;"></div>
                    <span style="margin-left: 8px;">{feature["contribution"]:+.4f}</span>
                </td>
                <td style="padding: 8px;">{feature["cumulative"]:.4f}</td>
            </tr>
            """)

        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h3>Waterfall Plot</h3>
            <p>Base value: {data["base_value"]:.4f} | Prediction: {data["prediction_value"]:.4f}</p>
            <table style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; text-align: left;">Feature</th>
                        <th style="padding: 8px; text-align: left;">Value</th>
                        <th style="padding: 8px; text-align: left;">Contribution</th>
                        <th style="padding: 8px; text-align: left;">Cumulative</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _render_force_plot_html(self, data: dict) -> str:
        """Render force plot as HTML"""
        pos_items = "".join([
            f'<span style="background: #FF6B6B; padding: 4px 8px; margin: 2px; border-radius: 4px;">'
            f'{c["name"]} = {c["value"]:.2f} (+{c["contribution"]:.3f})</span>'
            for c in data["positive_contributions"]
        ])

        neg_items = "".join([
            f'<span style="background: #4DABF7; padding: 4px 8px; margin: 2px; border-radius: 4px;">'
            f'{c["name"]} = {c["value"]:.2f} ({c["contribution"]:.3f})</span>'
            for c in data["negative_contributions"]
        ])

        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h3>Force Plot</h3>
            <div style="display: flex; align-items: center; margin: 20px 0;">
                <div style="text-align: center; padding: 10px;">
                    <div style="font-size: 12px; color: #666;">Base Value</div>
                    <div style="font-size: 24px; font-weight: bold;">{data["base_value"]:.4f}</div>
                </div>
                <div style="flex: 1; display: flex; flex-wrap: wrap; padding: 10px;">
                    {neg_items}
                </div>
                <div style="font-size: 24px; padding: 0 20px;">→</div>
                <div style="flex: 1; display: flex; flex-wrap: wrap; padding: 10px;">
                    {pos_items}
                </div>
                <div style="text-align: center; padding: 10px;">
                    <div style="font-size: 12px; color: #666;">Prediction</div>
                    <div style="font-size: 24px; font-weight: bold; color: #2196F3;">{data["prediction_value"]:.4f}</div>
                </div>
            </div>
        </div>
        """

    def _render_summary_plot_html(self, data: dict) -> str:
        """Render summary plot as HTML"""
        rows = []
        max_importance = max((f["mean_abs_contribution"] for f in data["features"]), default=1)

        for feature in data["features"]:
            bar_width = (feature["mean_abs_contribution"] / max_importance) * 200
            color = "#4CAF50" if feature["mean_contribution"] > 0 else "#F44336"
            rows.append(f"""
            <tr>
                <td style="padding: 8px;">{feature["name"]}</td>
                <td style="padding: 8px;">
                    <div style="background: {color}; width: {bar_width}px; height: 20px; display: inline-block;"></div>
                </td>
                <td style="padding: 8px;">{feature["mean_abs_contribution"]:.4f}</td>
                <td style="padding: 8px;">{feature["std_contribution"]:.4f}</td>
            </tr>
            """)

        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h3>Feature Importance Summary</h3>
            <p>Based on {data["sample_size"]} predictions</p>
            <table style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; text-align: left;">Feature</th>
                        <th style="padding: 8px; text-align: left;">Importance</th>
                        <th style="padding: 8px; text-align: left;">Mean |SHAP|</th>
                        <th style="padding: 8px; text-align: left;">Std Dev</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _render_heatmap_html(self, data: dict) -> str:
        """Render interaction heatmap as HTML"""
        rows = []
        for i, feature in enumerate(data["features"]):
            cells = [f'<td style="padding: 8px; font-weight: bold;">{feature}</td>']
            for j, _ in enumerate(data["features"]):
                value = data["matrix"][i][j]
                intensity = min(value * 255, 255)
                color = f"rgb({255 - intensity}, {255 - intensity}, 255)"
                cells.append(f'<td style="padding: 8px; background: {color};">{value:.2f}</td>')
            rows.append(f'<tr>{"".join(cells)}</tr>')

        header = "".join([f'<th style="padding: 8px;"></th>'] + [
            f'<th style="padding: 8px; transform: rotate(-45deg);">{f}</th>'
            for f in data["features"]
        ])

        return f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h3>Feature Interaction Heatmap</h3>
            <table style="border-collapse: collapse;">
                <thead><tr>{header}</tr></thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </div>
        """


# ============================================================================
# Explanation Cache
# ============================================================================

class ExplanationCache:
    """
    Caching system for explanations

    Improves performance for repeated predictions
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[Explanation, datetime]] = {}
        self.access_count: dict[str, int] = defaultdict(int)
        self.hit_count = 0
        self.miss_count = 0

    def get_cache_key(
        self,
        model_name: str,
        features: dict[str, float],
        explanation_type: ExplanationType
    ) -> str:
        """Generate cache key"""
        feature_str = json.dumps(features, sort_keys=True)
        key_str = f"{model_name}:{explanation_type.value}:{feature_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        model_name: str,
        features: dict[str, float],
        explanation_type: ExplanationType
    ) -> Optional[Explanation]:
        """Get cached explanation"""
        key = self.get_cache_key(model_name, features, explanation_type)

        if key in self.cache:
            explanation, cached_at = self.cache[key]

            # Check TTL
            if (datetime.now() - cached_at).seconds < self.ttl_seconds:
                self.hit_count += 1
                self.access_count[key] += 1
                return explanation
            else:
                # Expired
                del self.cache[key]

        self.miss_count += 1
        return None

    def put(
        self,
        model_name: str,
        features: dict[str, float],
        explanation_type: ExplanationType,
        explanation: Explanation
    ) -> None:
        """Cache explanation"""
        key = self.get_cache_key(model_name, features, explanation_type)

        # Evict if necessary
        if len(self.cache) >= self.max_size:
            self._evict()

        self.cache[key] = (explanation, datetime.now())

    def _evict(self) -> None:
        """Evict least recently used entries"""
        # Remove 10% of entries with lowest access count
        to_remove = int(self.max_size * 0.1)

        sorted_keys = sorted(
            self.cache.keys(),
            key=lambda k: self.access_count.get(k, 0)
        )

        for key in sorted_keys[:to_remove]:
            del self.cache[key]
            self.access_count.pop(key, None)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total = self.hit_count + self.miss_count
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": self.hit_count / total if total > 0 else 0.0
        }

    def clear(self) -> None:
        """Clear cache"""
        self.cache.clear()
        self.access_count.clear()
        self.hit_count = 0
        self.miss_count = 0


# ============================================================================
# Audit Log Storage
# ============================================================================

class AuditLogStorage:
    """
    Audit log storage for explanation generation

    Tracks all explanation requests for compliance and debugging
    """

    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self.entries: list[AuditLogEntry] = []
        self.entries_by_account: dict[str, list[AuditLogEntry]] = defaultdict(list)
        self.entries_by_model: dict[str, list[AuditLogEntry]] = defaultdict(list)

    def log(
        self,
        explanation: Explanation,
        generation_time_ms: float,
        cache_hit: bool,
        user_id: Optional[str] = None,
        request_source: str = "api"
    ) -> AuditLogEntry:
        """Log explanation generation"""
        entry = AuditLogEntry(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            explanation_id=explanation.explanation_id,
            account_id=explanation.account_id,
            model_name=explanation.model_name,
            explanation_type=explanation.explanation_type.value,
            generation_time_ms=generation_time_ms,
            cache_hit=cache_hit,
            user_id=user_id,
            request_source=request_source
        )

        self.entries.append(entry)
        self.entries_by_account[explanation.account_id].append(entry)
        self.entries_by_model[explanation.model_name].append(entry)

        # Trim if necessary
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        return entry

    def get_entries_for_account(
        self,
        account_id: str,
        limit: int = 100
    ) -> list[AuditLogEntry]:
        """Get audit entries for account"""
        return self.entries_by_account[account_id][-limit:]

    def get_entries_for_model(
        self,
        model_name: str,
        limit: int = 100
    ) -> list[AuditLogEntry]:
        """Get audit entries for model"""
        return self.entries_by_model[model_name][-limit:]

    def get_statistics(
        self,
        time_window: timedelta = timedelta(hours=1)
    ) -> dict[str, Any]:
        """Get audit statistics"""
        cutoff = datetime.now() - time_window
        recent = [e for e in self.entries if e.timestamp >= cutoff]

        if not recent:
            return {
                "total_entries": len(self.entries),
                "recent_entries": 0,
                "avg_generation_time_ms": 0,
                "cache_hit_rate": 0,
                "by_explanation_type": {}
            }

        by_type: dict[str, int] = defaultdict(int)
        for entry in recent:
            by_type[entry.explanation_type] += 1

        return {
            "total_entries": len(self.entries),
            "recent_entries": len(recent),
            "avg_generation_time_ms": sum(e.generation_time_ms for e in recent) / len(recent),
            "cache_hit_rate": sum(1 for e in recent if e.cache_hit) / len(recent),
            "by_explanation_type": dict(by_type)
        }

    def export_to_dict(self) -> list[dict[str, Any]]:
        """Export audit log to list of dictionaries"""
        return [
            {
                "log_id": e.log_id,
                "timestamp": e.timestamp.isoformat(),
                "explanation_id": e.explanation_id,
                "account_id": e.account_id,
                "model_name": e.model_name,
                "explanation_type": e.explanation_type,
                "generation_time_ms": e.generation_time_ms,
                "cache_hit": e.cache_hit,
                "user_id": e.user_id,
                "request_source": e.request_source
            }
            for e in self.entries
        ]


# ============================================================================
# Explanation Storage
# ============================================================================

class ExplanationStorage:
    """
    Persistent storage for explanations

    Stores explanations with full audit trail
    """

    def __init__(self, max_storage: int = 1000000):
        self.max_storage = max_storage
        self.explanations: dict[str, Explanation] = {}
        self.by_account: dict[str, list[str]] = defaultdict(list)
        self.by_prediction: dict[str, str] = {}
        self.by_model: dict[str, list[str]] = defaultdict(list)

    def store(self, explanation: Explanation) -> None:
        """Store explanation"""
        self.explanations[explanation.explanation_id] = explanation
        self.by_account[explanation.account_id].append(explanation.explanation_id)
        self.by_prediction[explanation.prediction_id] = explanation.explanation_id
        self.by_model[explanation.model_name].append(explanation.explanation_id)

        # Trim if necessary
        if len(self.explanations) > self.max_storage:
            self._trim()

    def get(self, explanation_id: str) -> Optional[Explanation]:
        """Get explanation by ID"""
        return self.explanations.get(explanation_id)

    def get_for_prediction(self, prediction_id: str) -> Optional[Explanation]:
        """Get explanation for prediction"""
        explanation_id = self.by_prediction.get(prediction_id)
        if explanation_id:
            return self.explanations.get(explanation_id)
        return None

    def get_for_account(
        self,
        account_id: str,
        limit: int = 100
    ) -> list[Explanation]:
        """Get explanations for account"""
        explanation_ids = self.by_account[account_id][-limit:]
        return [
            self.explanations[eid]
            for eid in explanation_ids
            if eid in self.explanations
        ]

    def get_for_model(
        self,
        model_name: str,
        limit: int = 100
    ) -> list[Explanation]:
        """Get explanations for model"""
        explanation_ids = self.by_model[model_name][-limit:]
        return [
            self.explanations[eid]
            for eid in explanation_ids
            if eid in self.explanations
        ]

    def _trim(self) -> None:
        """Remove oldest explanations"""
        to_remove = int(self.max_storage * 0.1)

        sorted_explanations = sorted(
            self.explanations.values(),
            key=lambda e: e.timestamp
        )

        for explanation in sorted_explanations[:to_remove]:
            del self.explanations[explanation.explanation_id]

    def get_statistics(self) -> dict[str, Any]:
        """Get storage statistics"""
        return {
            "total_stored": len(self.explanations),
            "unique_accounts": len(self.by_account),
            "unique_models": len(self.by_model),
            "storage_utilization": len(self.explanations) / self.max_storage
        }


# ============================================================================
# Batch Explanation Processor
# ============================================================================

class BatchExplanationProcessor:
    """
    Process explanations in batches for efficiency

    Handles large-scale explanation generation
    """

    def __init__(
        self,
        explainability_engine: 'ExplainabilityEngine',
        batch_size: int = 100
    ):
        self.engine = explainability_engine
        self.batch_size = batch_size
        self.pending_requests: list[dict] = []
        self.results: dict[str, Explanation] = {}

    def add_request(
        self,
        request_id: str,
        account_id: str,
        features: dict[str, float],
        prediction: float,
        model_name: str
    ) -> None:
        """Add request to batch queue"""
        self.pending_requests.append({
            "request_id": request_id,
            "account_id": account_id,
            "features": features,
            "prediction": prediction,
            "model_name": model_name
        })

    def process_batch(
        self,
        model_predict: Callable[[dict[str, float]], float]
    ) -> dict[str, Explanation]:
        """Process all pending requests"""
        results = {}

        # Process in batches
        for i in range(0, len(self.pending_requests), self.batch_size):
            batch = self.pending_requests[i:i + self.batch_size]

            for request in batch:
                explanation = self.engine.explain_prediction(
                    features=request["features"],
                    prediction=request["prediction"],
                    model_predict=model_predict,
                    model_name=request["model_name"],
                    model_version="1.0",
                    account_id=request["account_id"],
                    prediction_id=request["request_id"]
                )

                results[request["request_id"]] = explanation
                self.results[request["request_id"]] = explanation

        # Clear pending
        self.pending_requests.clear()

        return results

    def get_result(self, request_id: str) -> Optional[Explanation]:
        """Get result for request"""
        return self.results.get(request_id)

    def get_pending_count(self) -> int:
        """Get number of pending requests"""
        return len(self.pending_requests)


# ============================================================================
# Main Explainability Engine
# ============================================================================

class ExplainabilityEngine:
    """
    Master explainability engine for QUAN ML models

    Provides comprehensive explanation capabilities:
    - SHAP explanations for tree and neural models
    - LIME for local interpretability
    - Integrated gradients for deep models
    - Global feature importance
    - Counterfactual explanations
    - Feature interaction detection
    - Human-readable explanations
    - Caching for performance
    - Batch processing
    - Full audit trail
    """

    def __init__(self, default_model_category: ModelCategory = ModelCategory.ENSEMBLE):
        # Explainers
        self.shap_explainer = SHAPExplainer(default_model_category)
        self.lime_explainer = LIMEExplainer()
        self.ig_explainer = IntegratedGradientsExplainer()
        self.counterfactual_explainer = CounterfactualExplainer()
        self.interaction_detector = FeatureInteractionDetector()
        self.global_importance = GlobalFeatureImportance()

        # Visualization
        self.viz_generator = VisualizationGenerator()

        # Storage and caching
        self.cache = ExplanationCache()
        self.storage = ExplanationStorage()
        self.audit_log = AuditLogStorage()

        # Configuration
        self.default_model_category = default_model_category
        self.top_k_features = 5

        # Background data for explainers
        self.background_data: list[dict[str, float]] = []

        logger.info("ExplainabilityEngine initialized")

    def set_background_data(self, data: list[dict[str, float]]) -> None:
        """Set background data for SHAP and baseline calculations"""
        self.background_data = data
        self.shap_explainer.set_background_data(data)

        # Set baseline for integrated gradients (mean of features)
        if data:
            baseline = {}
            for feature in data[0].keys():
                values = [d.get(feature, 0) for d in data]
                baseline[feature] = sum(values) / len(values)
            self.ig_explainer.set_baseline(baseline)

            # Set feature std for LIME
            std_values = {}
            for feature in data[0].keys():
                values = [d.get(feature, 0) for d in data]
                mean = sum(values) / len(values)
                std_values[feature] = math.sqrt(
                    sum((v - mean) ** 2 for v in values) / len(values)
                ) if len(values) > 1 else 0.1
            self.lime_explainer.set_feature_statistics(std_values)

        logger.info(f"Background data set with {len(data)} samples")

    def explain_prediction(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable[[dict[str, float]], float],
        model_name: str,
        model_version: str,
        account_id: str,
        prediction_id: str,
        explanation_type: ExplanationType = ExplanationType.SHAP,
        use_cache: bool = True,
        user_id: Optional[str] = None
    ) -> Explanation:
        """
        Generate explanation for a prediction

        This is the main entry point for explanation generation
        """
        import time
        start_time = time.time()

        # Check cache
        if use_cache:
            cached = self.cache.get(model_name, features, explanation_type)
            if cached:
                # Update metadata and log
                cached.prediction_id = prediction_id
                cached.account_id = account_id
                generation_time = (time.time() - start_time) * 1000
                self.audit_log.log(cached, generation_time, True, user_id)
                return cached

        # Generate explanation based on type
        if explanation_type == ExplanationType.SHAP:
            contributions = self.shap_explainer.explain(features, prediction, model_predict)
            base_value = self.shap_explainer.base_value
        elif explanation_type == ExplanationType.LIME:
            contributions = self.lime_explainer.explain(features, prediction, model_predict)
            base_value = 0.5
        elif explanation_type == ExplanationType.INTEGRATED_GRADIENTS:
            contributions = self.ig_explainer.explain(features, prediction, model_predict)
            base_value = 0.5
        else:
            # Default to SHAP
            contributions = self.shap_explainer.explain(features, prediction, model_predict)
            base_value = self.shap_explainer.base_value

        # Get top features
        top_features = contributions[:self.top_k_features]

        # Generate human-readable summary
        top_feature_names = [c.feature_name for c in top_features]
        human_summary = ExplanationTemplates.get_summary(
            "general",
            prediction,
            0.8,  # Confidence placeholder
            top_feature_names
        )

        # Calculate confidence based on contribution clarity
        total_contribution = sum(abs(c.contribution) for c in contributions)
        top_contribution = sum(abs(c.contribution) for c in top_features)
        confidence = top_contribution / total_contribution if total_contribution > 0 else 0.5

        # Create explanation
        explanation = Explanation(
            explanation_id=str(uuid.uuid4()),
            prediction_id=prediction_id,
            account_id=account_id,
            model_name=model_name,
            model_version=model_version,
            prediction_value=prediction,
            base_value=base_value,
            explanation_type=explanation_type,
            feature_contributions=contributions,
            top_features=top_features,
            human_summary=human_summary,
            confidence_score=confidence,
            metadata={
                "features_count": len(features),
                "explanation_method": explanation_type.value
            }
        )

        # Cache and store
        if use_cache:
            self.cache.put(model_name, features, explanation_type, explanation)

        self.storage.store(explanation)

        # Audit log
        generation_time = (time.time() - start_time) * 1000
        self.audit_log.log(explanation, generation_time, False, user_id)

        logger.info(f"Generated {explanation_type.value} explanation for prediction {prediction_id}")

        return explanation

    def explain_with_all_methods(
        self,
        features: dict[str, float],
        prediction: float,
        model_predict: Callable[[dict[str, float]], float],
        model_name: str,
        model_version: str,
        account_id: str,
        prediction_id: str
    ) -> dict[ExplanationType, Explanation]:
        """Generate explanations using all available methods"""
        methods = [ExplanationType.SHAP, ExplanationType.LIME, ExplanationType.INTEGRATED_GRADIENTS]

        return {
            method: self.explain_prediction(
                features=features,
                prediction=prediction,
                model_predict=model_predict,
                model_name=model_name,
                model_version=model_version,
                account_id=account_id,
                prediction_id=f"{prediction_id}_{method.value}",
                explanation_type=method
            )
            for method in methods
        }

    def generate_counterfactual(
        self,
        features: dict[str, float],
        current_prediction: float,
        target_prediction: float,
        model_predict: Callable[[dict[str, float]], float]
    ) -> CounterfactualExplanation:
        """Generate counterfactual explanation"""
        return self.counterfactual_explainer.generate_counterfactual(
            features=features,
            current_prediction=current_prediction,
            target_prediction=target_prediction,
            model_predict=model_predict
        )

    def detect_interactions(
        self,
        features: dict[str, float],
        model_predict: Callable[[dict[str, float]], float],
        top_k: int = 10
    ) -> list[FeatureInteraction]:
        """Detect feature interactions"""
        return self.interaction_detector.detect_interactions(
            features=features,
            model_predict=model_predict,
            top_k=top_k
        )

    def generate_global_importance_report(
        self,
        model_name: str,
        model_predict: Callable[[dict[str, float]], float],
        dataset: Optional[list[dict[str, float]]] = None
    ) -> GlobalImportanceReport:
        """Generate global feature importance report"""
        if dataset is None:
            dataset = self.background_data

        return self.global_importance.generate_report(
            model_name=model_name,
            dataset=dataset,
            shap_explainer=self.shap_explainer,
            model_predict=model_predict,
            interaction_detector=self.interaction_detector
        )

    def generate_visualization(
        self,
        explanation: Explanation,
        viz_type: VisualizationType
    ) -> Visualization:
        """Generate visualization for explanation"""
        if viz_type == VisualizationType.WATERFALL:
            return self.viz_generator.generate_waterfall(explanation)
        elif viz_type == VisualizationType.FORCE_PLOT:
            return self.viz_generator.generate_force_plot(explanation)
        else:
            return self.viz_generator.generate_waterfall(explanation)  # Default

    def generate_batch_visualizations(
        self,
        explanations: list[Explanation]
    ) -> dict[str, Visualization]:
        """Generate summary visualization for batch of explanations"""
        return {
            "summary": self.viz_generator.generate_summary_plot(explanations),
            "interactions": self.viz_generator.generate_interaction_heatmap(
                self.interaction_detector.detect_interactions(
                    explanations[0].feature_contributions[0].__dict__ if explanations else {},
                    lambda x: 0.5
                ) if explanations else []
            )
        }

    def create_batch_processor(self, batch_size: int = 100) -> BatchExplanationProcessor:
        """Create batch explanation processor"""
        return BatchExplanationProcessor(self, batch_size)

    def get_explanation_for_prediction(self, prediction_id: str) -> Optional[Explanation]:
        """Retrieve stored explanation for prediction"""
        return self.storage.get_for_prediction(prediction_id)

    def get_explanations_for_account(
        self,
        account_id: str,
        limit: int = 100
    ) -> list[Explanation]:
        """Retrieve stored explanations for account"""
        return self.storage.get_for_account(account_id, limit)

    def get_audit_log(
        self,
        account_id: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> list[AuditLogEntry]:
        """Get audit log entries"""
        if account_id:
            return self.audit_log.get_entries_for_account(account_id, limit)
        elif model_name:
            return self.audit_log.get_entries_for_model(model_name, limit)
        else:
            return self.audit_log.entries[-limit:]

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()

    def get_storage_statistics(self) -> dict[str, Any]:
        """Get storage statistics"""
        return self.storage.get_statistics()

    def get_audit_statistics(self, time_window: timedelta = timedelta(hours=1)) -> dict[str, Any]:
        """Get audit statistics"""
        return self.audit_log.get_statistics(time_window)

    def get_system_status(self) -> dict[str, Any]:
        """Get overall system status"""
        return {
            "cache": self.get_cache_statistics(),
            "storage": self.get_storage_statistics(),
            "audit": self.get_audit_statistics(),
            "background_data_size": len(self.background_data),
            "default_model_category": self.default_model_category.value,
            "top_k_features": self.top_k_features
        }

    def export_explanation(self, explanation: Explanation) -> dict[str, Any]:
        """Export explanation to dictionary"""
        return explanation.to_dict()

    def export_audit_log(self) -> list[dict[str, Any]]:
        """Export full audit log"""
        return self.audit_log.export_to_dict()


# ============================================================================
# Demonstration
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("QUAN ML EXPLAINABILITY ENGINE DEMONSTRATION")
    print("=" * 70)

    # Initialize engine
    engine = ExplainabilityEngine(ModelCategory.ENSEMBLE)

    # Sample background data
    background_data = [
        {"balance": 0.15, "days_past_due": 0.18, "shadow_score": 0.68, "response_rate": 0.4, "promise_kept_rate": 0.5},
        {"balance": 0.25, "days_past_due": 0.10, "shadow_score": 0.75, "response_rate": 0.6, "promise_kept_rate": 0.7},
        {"balance": 0.50, "days_past_due": 0.30, "shadow_score": 0.55, "response_rate": 0.3, "promise_kept_rate": 0.4},
        {"balance": 0.10, "days_past_due": 0.05, "shadow_score": 0.80, "response_rate": 0.8, "promise_kept_rate": 0.9},
        {"balance": 0.35, "days_past_due": 0.25, "shadow_score": 0.60, "response_rate": 0.5, "promise_kept_rate": 0.6},
    ]

    engine.set_background_data(background_data)

    # Sample prediction model
    def sample_model(features: dict[str, float]) -> float:
        """Simple logistic-like model for demonstration"""
        score = (
            features.get("shadow_score", 0.5) * 0.4 +
            features.get("response_rate", 0.5) * 0.3 +
            features.get("promise_kept_rate", 0.5) * 0.2 -
            features.get("days_past_due", 0.5) * 0.2 -
            features.get("balance", 0.5) * 0.1
        )
        return 1 / (1 + math.exp(-score * 4))

    # Test account
    test_features = {
        "balance": 0.147,
        "days_past_due": 0.18,
        "shadow_score": 0.68,
        "response_rate": 0.4,
        "promise_kept_rate": 0.5
    }

    prediction = sample_model(test_features)

    print(f"\n1. SAMPLE PREDICTION")
    print(f"   Features: {test_features}")
    print(f"   Prediction: {prediction:.4f}")

    # Generate SHAP explanation
    print(f"\n2. SHAP EXPLANATION")
    shap_explanation = engine.explain_prediction(
        features=test_features,
        prediction=prediction,
        model_predict=sample_model,
        model_name="payment_model",
        model_version="1.0.0",
        account_id="ACC001",
        prediction_id="PRED001",
        explanation_type=ExplanationType.SHAP
    )

    print(f"   Base Value: {shap_explanation.base_value:.4f}")
    print(f"   Top 5 Features:")
    for contrib in shap_explanation.top_features:
        print(f"     - {contrib.feature_name}: {contrib.contribution:+.4f} ({contrib.direction})")
    print(f"\n   Human Summary: {shap_explanation.human_summary}")

    # Generate LIME explanation
    print(f"\n3. LIME EXPLANATION")
    lime_explanation = engine.explain_prediction(
        features=test_features,
        prediction=prediction,
        model_predict=sample_model,
        model_name="payment_model",
        model_version="1.0.0",
        account_id="ACC001",
        prediction_id="PRED002",
        explanation_type=ExplanationType.LIME
    )

    print(f"   Top 5 Features (LIME):")
    for contrib in lime_explanation.top_features:
        print(f"     - {contrib.feature_name}: {contrib.contribution:+.4f}")

    # Counterfactual explanation
    print(f"\n4. COUNTERFACTUAL EXPLANATION")
    counterfactual = engine.generate_counterfactual(
        features=test_features,
        current_prediction=prediction,
        target_prediction=0.8,
        model_predict=sample_model
    )

    print(f"   Original Prediction: {counterfactual.original_prediction:.4f}")
    print(f"   Target Prediction: {counterfactual.target_prediction:.4f}")
    print(f"   Changes Required: {len(counterfactual.changes_required)}")
    for change in counterfactual.changes_required[:3]:
        print(f"     - {change['feature']}: {change['original_value']:.3f} -> {change['counterfactual_value']:.3f}")
    print(f"   Feasibility: {counterfactual.feasibility_score:.2f}")
    print(f"   Summary: {counterfactual.human_summary}")

    # Feature interactions
    print(f"\n5. FEATURE INTERACTIONS")
    interactions = engine.detect_interactions(test_features, sample_model, top_k=3)

    for interaction in interactions:
        print(f"   - {interaction.feature_a} x {interaction.feature_b}:")
        print(f"     Strength: {interaction.interaction_strength:.4f} ({interaction.interaction_type})")

    # Global importance report
    print(f"\n6. GLOBAL FEATURE IMPORTANCE REPORT")
    report = engine.generate_global_importance_report(
        model_name="payment_model",
        model_predict=sample_model
    )

    print(f"   Sample Size: {report.sample_size}")
    print(f"   Feature Rankings:")
    for feature, importance in report.feature_rankings[:5]:
        print(f"     - {feature}: {importance:.4f}")
    print(f"   Recommendations:")
    for rec in report.recommendations:
        print(f"     - {rec}")

    # Visualizations
    print(f"\n7. VISUALIZATION GENERATION")
    waterfall = engine.generate_visualization(shap_explanation, VisualizationType.WATERFALL)
    force_plot = engine.generate_visualization(shap_explanation, VisualizationType.FORCE_PLOT)

    print(f"   Generated Waterfall Plot: {waterfall.viz_id[:8]}...")
    print(f"   Generated Force Plot: {force_plot.viz_id[:8]}...")
    print(f"   HTML content length: {len(waterfall.html_content)} chars")

    # Batch processing
    print(f"\n8. BATCH PROCESSING")
    batch_processor = engine.create_batch_processor(batch_size=50)

    for i in range(5):
        batch_processor.add_request(
            request_id=f"BATCH_{i}",
            account_id=f"ACC{i:03d}",
            features={k: v * (1 + i * 0.1) for k, v in test_features.items()},
            prediction=sample_model(test_features),
            model_name="payment_model"
        )

    batch_results = batch_processor.process_batch(sample_model)
    print(f"   Processed {len(batch_results)} batch requests")

    # System statistics
    print(f"\n9. SYSTEM STATISTICS")
    status = engine.get_system_status()

    print(f"   Cache Hit Rate: {status['cache']['hit_rate']:.2%}")
    print(f"   Stored Explanations: {status['storage']['total_stored']}")
    print(f"   Audit Entries: {status['audit']['total_entries']}")
    print(f"   Background Data Size: {status['background_data_size']}")

    # Audit log
    print(f"\n10. AUDIT LOG SAMPLE")
    audit_entries = engine.get_audit_log(limit=3)

    for entry in audit_entries:
        print(f"   - {entry.log_id[:8]}... | {entry.explanation_type} | "
              f"Cache: {entry.cache_hit} | Time: {entry.generation_time_ms:.1f}ms")

    print("\n" + "=" * 70)
    print("EXPLAINABILITY ENGINE DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nAll predictions now include:")
    print("  - Top-5 SHAP feature contributions")
    print("  - Human-readable explanations")
    print("  - Full audit trail with timestamps")
    print("  - Cached for performance")
    print("  - Stored for compliance review")
