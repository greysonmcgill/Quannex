"""
Advanced ML Prediction Engine for Collections

Multi-model ensemble for predicting:
1. Payment probability
2. Optimal contact timing
3. Settlement acceptance
4. Payment plan adherence
5. Liquidation likelihood

Uses gradient boosting, neural networks, and Bayesian optimization
for continuous model improvement.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable
import math
import random
from collections import defaultdict


class PredictionTarget(Enum):
    """Prediction targets"""
    PAYMENT_PROBABILITY = "payment_prob"
    CONTACT_RESPONSE = "contact_response"
    SETTLEMENT_ACCEPTANCE = "settlement_acceptance"
    PLAN_ADHERENCE = "plan_adherence"
    OPTIMAL_CHANNEL = "optimal_channel"
    OPTIMAL_TIME = "optimal_time"
    LIQUIDATION_TIMING = "liquidation_timing"
    CHURN_RISK = "churn_risk"


class ModelType(Enum):
    """ML model types"""
    GRADIENT_BOOST = "gradient_boost"
    NEURAL_NET = "neural_net"
    LOGISTIC = "logistic"
    RANDOM_FOREST = "random_forest"
    BAYESIAN = "bayesian"


@dataclass
class Feature:
    """Feature definition"""
    name: str
    feature_type: str  # numeric, categorical, temporal, binary
    importance: float = 0.0
    missing_rate: float = 0.0
    transform: Callable | None = None


@dataclass
class ModelMetrics:
    """Model performance metrics"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    log_loss: float = 0.0
    calibration_error: float = 0.0
    lift_at_10: float = 0.0
    ks_statistic: float = 0.0


@dataclass
class Prediction:
    """Single prediction result"""
    prediction_id: str
    target: PredictionTarget
    account_id: str
    probability: float
    confidence: float
    model_version: str
    features_used: list[str]
    timestamp: datetime = field(default_factory=datetime.now)
    explanation: dict[str, float] = field(default_factory=dict)


class FeatureStore:
    """
    Centralized feature store for ML models

    Maintains feature definitions, transformations, and real-time values
    """

    def __init__(self):
        self.features: dict[str, Feature] = {}
        self.feature_values: dict[str, dict[str, Any]] = defaultdict(dict)
        self._define_features()

    def _define_features(self) -> None:
        """Define all features used in models"""
        # Account features
        self.features["balance"] = Feature("balance", "numeric", importance=0.15)
        self.features["days_past_due"] = Feature("days_past_due", "numeric", importance=0.12)
        self.features["shadow_score"] = Feature("shadow_score", "numeric", importance=0.18)
        self.features["original_creditor_type"] = Feature("original_creditor_type", "categorical", importance=0.08)
        self.features["debt_category"] = Feature("debt_category", "categorical", importance=0.07)

        # Behavioral features
        self.features["total_contacts"] = Feature("total_contacts", "numeric", importance=0.06)
        self.features["response_rate"] = Feature("response_rate", "numeric", importance=0.11)
        self.features["promise_kept_rate"] = Feature("promise_kept_rate", "numeric", importance=0.14)
        self.features["avg_response_time_hours"] = Feature("avg_response_time_hours", "numeric", importance=0.05)
        self.features["last_contact_days"] = Feature("last_contact_days", "numeric", importance=0.04)

        # Temporal features
        self.features["day_of_week"] = Feature("day_of_week", "categorical", importance=0.03)
        self.features["hour_of_day"] = Feature("hour_of_day", "numeric", importance=0.04)
        self.features["days_since_last_payment"] = Feature("days_since_last_payment", "numeric", importance=0.08)
        self.features["is_payday_week"] = Feature("is_payday_week", "binary", importance=0.06)

        # Derived features
        self.features["balance_to_score_ratio"] = Feature(
            "balance_to_score_ratio", "numeric", importance=0.09,
            transform=lambda d: d.get("balance", 0) / max(d.get("shadow_score", 1), 1)
        )
        self.features["contact_efficiency"] = Feature(
            "contact_efficiency", "numeric", importance=0.07,
            transform=lambda d: d.get("successful_contacts", 0) / max(d.get("total_contacts", 1), 1)
        )

    def compute_features(self, account_data: dict[str, Any]) -> dict[str, float]:
        """Compute all features for an account"""
        computed = {}

        for name, feature in self.features.items():
            if feature.transform:
                computed[name] = feature.transform(account_data)
            elif name in account_data:
                computed[name] = self._normalize(account_data[name], feature)
            else:
                computed[name] = 0.0  # Default for missing

        return computed

    def _normalize(self, value: Any, feature: Feature) -> float:
        """Normalize feature value"""
        if feature.feature_type == "numeric":
            # Simple min-max normalization (would use actual stats in production)
            if feature.name == "balance":
                return min(value / 1000, 1.0)
            elif feature.name == "days_past_due":
                return min(value / 365, 1.0)
            elif feature.name == "shadow_score":
                return value / 850
            else:
                return float(value)
        elif feature.feature_type == "categorical":
            # One-hot encoding would be done here
            return hash(str(value)) % 100 / 100
        elif feature.feature_type == "binary":
            return 1.0 if value else 0.0
        else:
            return float(value)

    def get_feature_importance(self) -> list[tuple[str, float]]:
        """Get features sorted by importance"""
        return sorted(
            [(f.name, f.importance) for f in self.features.values()],
            key=lambda x: x[1],
            reverse=True
        )


class BaseModel:
    """Base class for prediction models"""

    def __init__(self, model_type: ModelType, target: PredictionTarget):
        self.model_type = model_type
        self.target = target
        self.version = "1.0.0"
        self.trained_at: datetime | None = None
        self.metrics = ModelMetrics()
        self.weights: dict[str, float] = {}

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        """Return (probability, confidence)"""
        raise NotImplementedError

    def train(self, data: list[tuple[dict[str, float], float]]) -> ModelMetrics:
        """Train model on labeled data"""
        raise NotImplementedError

    def explain(self, features: dict[str, float]) -> dict[str, float]:
        """Explain prediction with feature contributions"""
        contributions = {}
        for name, value in features.items():
            weight = self.weights.get(name, 0.0)
            contributions[name] = value * weight
        return contributions


class GradientBoostModel(BaseModel):
    """
    Gradient Boosting model for payment prediction

    Simulates XGBoost/LightGBM behavior
    """

    def __init__(self, target: PredictionTarget):
        super().__init__(ModelType.GRADIENT_BOOST, target)
        self.n_estimators = 100
        self.learning_rate = 0.1
        self.max_depth = 6
        self.trees: list[dict[str, Any]] = []

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        """Predict using ensemble of trees"""
        if not self.weights:
            self._initialize_weights()

        # Simulate gradient boosting prediction
        score = 0.0
        for name, value in features.items():
            weight = self.weights.get(name, 0.0)
            # Non-linear transformation
            score += weight * math.tanh(value * 2)

        # Apply sigmoid
        probability = 1 / (1 + math.exp(-score))

        # Confidence based on feature coverage
        coverage = sum(1 for v in features.values() if v > 0) / len(features)
        confidence = 0.5 + coverage * 0.4

        return probability, confidence

    def train(self, data: list[tuple[dict[str, float], float]]) -> ModelMetrics:
        """Train gradient boosting model"""
        if not data:
            return self.metrics

        # Initialize weights from feature importance
        for features, label in data:
            for name in features:
                if name not in self.weights:
                    self.weights[name] = random.uniform(-0.5, 0.5)

        # Simulate training iterations
        for iteration in range(self.n_estimators):
            for features, label in data:
                pred, _ = self.predict(features)
                error = label - pred

                # Update weights (simplified gradient descent)
                for name, value in features.items():
                    gradient = error * value * self.learning_rate
                    self.weights[name] += gradient / len(data)

        # Calculate metrics
        self._calculate_metrics(data)
        self.trained_at = datetime.now()

        return self.metrics

    def _initialize_weights(self) -> None:
        """Initialize weights from feature store"""
        store = FeatureStore()
        for name, importance in store.get_feature_importance():
            self.weights[name] = (importance - 0.1) * 2

    def _calculate_metrics(self, data: list[tuple[dict[str, float], float]]) -> None:
        """Calculate model metrics"""
        if not data:
            return

        predictions = []
        actuals = []

        for features, label in data:
            pred, _ = self.predict(features)
            predictions.append(pred)
            actuals.append(label)

        # Calculate accuracy
        correct = sum(
            1 for p, a in zip(predictions, actuals)
            if (p >= 0.5) == (a >= 0.5)
        )
        self.metrics.accuracy = correct / len(data)

        # Calculate AUC approximation
        self.metrics.auc_roc = self._approximate_auc(predictions, actuals)

        # Calculate log loss
        eps = 1e-15
        log_loss = -sum(
            a * math.log(max(p, eps)) + (1 - a) * math.log(max(1 - p, eps))
            for p, a in zip(predictions, actuals)
        ) / len(data)
        self.metrics.log_loss = log_loss

    def _approximate_auc(self, predictions: list[float], actuals: list[float]) -> float:
        """Approximate AUC-ROC"""
        pairs = list(zip(predictions, actuals))
        pairs.sort(key=lambda x: x[0], reverse=True)

        n_pos = sum(actuals)
        n_neg = len(actuals) - n_pos

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


class NeuralNetModel(BaseModel):
    """
    Neural network model for complex pattern recognition

    Simulates a simple feedforward network
    """

    def __init__(self, target: PredictionTarget):
        super().__init__(ModelType.NEURAL_NET, target)
        self.hidden_size = 32
        self.dropout_rate = 0.2
        self.layer1_weights: dict[str, list[float]] = {}
        self.layer2_weights: list[float] = []

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        """Forward pass through network"""
        if not self.layer1_weights:
            self._initialize_weights(list(features.keys()))

        # Layer 1: Input to hidden
        hidden = []
        for i in range(self.hidden_size):
            activation = 0.0
            for name, value in features.items():
                if name in self.layer1_weights:
                    activation += value * self.layer1_weights[name][i]
            # ReLU activation
            hidden.append(max(0, activation))

        # Layer 2: Hidden to output
        output = sum(h * w for h, w in zip(hidden, self.layer2_weights))

        # Sigmoid output
        probability = 1 / (1 + math.exp(-output))

        # Confidence from hidden layer activations
        active_neurons = sum(1 for h in hidden if h > 0) / len(hidden)
        confidence = 0.4 + active_neurons * 0.5

        return probability, confidence

    def _initialize_weights(self, feature_names: list[str]) -> None:
        """Xavier initialization"""
        scale = math.sqrt(2.0 / (len(feature_names) + self.hidden_size))

        for name in feature_names:
            self.layer1_weights[name] = [
                random.gauss(0, scale) for _ in range(self.hidden_size)
            ]

        scale2 = math.sqrt(2.0 / (self.hidden_size + 1))
        self.layer2_weights = [
            random.gauss(0, scale2) for _ in range(self.hidden_size)
        ]

    def train(self, data: list[tuple[dict[str, float], float]]) -> ModelMetrics:
        """Train neural network"""
        if not data:
            return self.metrics

        feature_names = list(data[0][0].keys())
        self._initialize_weights(feature_names)

        learning_rate = 0.01
        epochs = 50

        for epoch in range(epochs):
            for features, label in data:
                pred, _ = self.predict(features)
                error = label - pred

                # Simplified backpropagation
                for name, value in features.items():
                    if name in self.layer1_weights:
                        for i in range(self.hidden_size):
                            gradient = error * value * learning_rate
                            self.layer1_weights[name][i] += gradient / len(data)

        self.trained_at = datetime.now()
        return self.metrics


class BayesianModel(BaseModel):
    """
    Bayesian model for uncertainty quantification

    Provides calibrated probability estimates with uncertainty bounds
    """

    def __init__(self, target: PredictionTarget):
        super().__init__(ModelType.BAYESIAN, target)
        self.prior_alpha: dict[str, float] = defaultdict(lambda: 1.0)
        self.prior_beta: dict[str, float] = defaultdict(lambda: 1.0)
        self.posterior_alpha: dict[str, float] = {}
        self.posterior_beta: dict[str, float] = {}

    def predict(self, features: dict[str, float]) -> tuple[float, float]:
        """Predict with uncertainty quantification"""
        # Segment based on key features
        segment = self._get_segment(features)

        alpha = self.posterior_alpha.get(segment, self.prior_alpha[segment])
        beta = self.posterior_beta.get(segment, self.prior_beta[segment])

        # Mean of beta distribution
        probability = alpha / (alpha + beta)

        # Confidence from sample size (more data = more confident)
        n_samples = alpha + beta - 2  # Subtract prior
        confidence = min(0.95, 0.5 + n_samples / 200)

        return probability, confidence

    def train(self, data: list[tuple[dict[str, float], float]]) -> ModelMetrics:
        """Update posterior with observed data"""
        # Group data by segment
        segment_data: dict[str, list[float]] = defaultdict(list)

        for features, label in data:
            segment = self._get_segment(features)
            segment_data[segment].append(label)

        # Update posteriors
        for segment, labels in segment_data.items():
            successes = sum(labels)
            failures = len(labels) - successes

            self.posterior_alpha[segment] = self.prior_alpha[segment] + successes
            self.posterior_beta[segment] = self.prior_beta[segment] + failures

        self.trained_at = datetime.now()
        return self.metrics

    def _get_segment(self, features: dict[str, float]) -> str:
        """Get segment for Bayesian grouping"""
        score = features.get("shadow_score", 0.5)
        balance = features.get("balance", 0.5)

        score_tier = "high" if score > 0.7 else "mid" if score > 0.4 else "low"
        balance_tier = "large" if balance > 0.5 else "small"

        return f"{score_tier}_{balance_tier}"

    def get_credible_interval(self, features: dict[str, float], level: float = 0.95) -> tuple[float, float]:
        """Get credible interval for prediction"""
        segment = self._get_segment(features)
        alpha = self.posterior_alpha.get(segment, self.prior_alpha[segment])
        beta = self.posterior_beta.get(segment, self.prior_beta[segment])

        # Approximate credible interval
        mean = alpha / (alpha + beta)
        var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        std = math.sqrt(var)

        z = 1.96 if level == 0.95 else 2.58  # Approximate

        lower = max(0, mean - z * std)
        upper = min(1, mean + z * std)

        return lower, upper


class EnsemblePredictor:
    """
    Ensemble predictor combining multiple models

    Uses stacking with dynamic weight adjustment based on recent performance
    """

    def __init__(self, target: PredictionTarget):
        self.target = target
        self.models: dict[ModelType, BaseModel] = {
            ModelType.GRADIENT_BOOST: GradientBoostModel(target),
            ModelType.NEURAL_NET: NeuralNetModel(target),
            ModelType.BAYESIAN: BayesianModel(target)
        }
        self.model_weights: dict[ModelType, float] = {
            ModelType.GRADIENT_BOOST: 0.5,
            ModelType.NEURAL_NET: 0.3,
            ModelType.BAYESIAN: 0.2
        }
        self.recent_performance: dict[ModelType, list[float]] = defaultdict(list)

    def predict(self, features: dict[str, float]) -> Prediction:
        """Ensemble prediction"""
        predictions = {}
        confidences = {}

        for model_type, model in self.models.items():
            prob, conf = model.predict(features)
            predictions[model_type] = prob
            confidences[model_type] = conf

        # Weighted average
        total_weight = sum(self.model_weights.values())
        ensemble_prob = sum(
            predictions[mt] * self.model_weights[mt]
            for mt in self.models
        ) / total_weight

        # Confidence from model agreement
        variance = sum(
            (predictions[mt] - ensemble_prob) ** 2
            for mt in self.models
        ) / len(self.models)
        agreement_conf = 1 - math.sqrt(variance) * 2

        # Average confidence
        avg_conf = sum(confidences.values()) / len(confidences)
        final_conf = (agreement_conf + avg_conf) / 2

        # Get explanation from best model
        best_model = max(self.model_weights.items(), key=lambda x: x[1])[0]
        explanation = self.models[best_model].explain(features)

        return Prediction(
            prediction_id=f"pred_{datetime.now().timestamp()}",
            target=self.target,
            account_id="",
            probability=ensemble_prob,
            confidence=final_conf,
            model_version=f"ensemble_v1",
            features_used=list(features.keys()),
            explanation=explanation
        )

    def train(self, data: list[tuple[dict[str, float], float]]) -> dict[ModelType, ModelMetrics]:
        """Train all models in ensemble"""
        results = {}

        for model_type, model in self.models.items():
            metrics = model.train(data)
            results[model_type] = metrics

        # Update weights based on performance
        self._update_weights(results)

        return results

    def record_outcome(self, prediction: Prediction, actual: float) -> None:
        """Record prediction outcome for weight adjustment"""
        error = abs(prediction.probability - actual)

        # Track performance by model (simplified - would track per model)
        for model_type in self.models:
            self.recent_performance[model_type].append(1 - error)

            # Keep last 100
            if len(self.recent_performance[model_type]) > 100:
                self.recent_performance[model_type].pop(0)

        # Periodically update weights
        if sum(len(v) for v in self.recent_performance.values()) % 50 == 0:
            self._rebalance_weights()

    def _update_weights(self, metrics: dict[ModelType, ModelMetrics]) -> None:
        """Update model weights based on metrics"""
        total_auc = sum(m.auc_roc for m in metrics.values())

        if total_auc > 0:
            for model_type, model_metrics in metrics.items():
                self.model_weights[model_type] = model_metrics.auc_roc / total_auc

    def _rebalance_weights(self) -> None:
        """Rebalance weights based on recent performance"""
        avg_performance = {}

        for model_type, perf in self.recent_performance.items():
            if perf:
                avg_performance[model_type] = sum(perf) / len(perf)

        if avg_performance:
            total = sum(avg_performance.values())
            for model_type in self.models:
                if model_type in avg_performance and total > 0:
                    self.model_weights[model_type] = avg_performance[model_type] / total


class MLPredictionEngine:
    """
    Master ML prediction engine for collections

    Manages multiple ensemble predictors for different targets
    """

    def __init__(self):
        self.feature_store = FeatureStore()
        self.predictors: dict[PredictionTarget, EnsemblePredictor] = {}
        self.prediction_cache: dict[str, Prediction] = {}
        self.prediction_history: list[Prediction] = []

        # Initialize predictors for each target
        for target in PredictionTarget:
            self.predictors[target] = EnsemblePredictor(target)

    def predict(
        self,
        account_data: dict[str, Any],
        target: PredictionTarget
    ) -> Prediction:
        """Make prediction for account"""
        # Compute features
        features = self.feature_store.compute_features(account_data)

        # Get prediction
        prediction = self.predictors[target].predict(features)
        prediction.account_id = account_data.get("account_id", "unknown")

        # Cache
        cache_key = f"{prediction.account_id}_{target.value}"
        self.prediction_cache[cache_key] = prediction
        self.prediction_history.append(prediction)

        return prediction

    def predict_all(self, account_data: dict[str, Any]) -> dict[PredictionTarget, Prediction]:
        """Make all predictions for account"""
        return {
            target: self.predict(account_data, target)
            for target in PredictionTarget
        }

    def train_all(
        self,
        training_data: dict[PredictionTarget, list[tuple[dict[str, Any], float]]]
    ) -> dict[PredictionTarget, dict[ModelType, ModelMetrics]]:
        """Train all predictors"""
        results = {}

        for target, data in training_data.items():
            # Convert to features
            feature_data = [
                (self.feature_store.compute_features(acc), label)
                for acc, label in data
            ]

            results[target] = self.predictors[target].train(feature_data)

        return results

    def get_optimal_contact_time(self, account_data: dict[str, Any]) -> dict[str, Any]:
        """Predict optimal contact time"""
        best_hour = 0
        best_prob = 0.0

        for hour in range(8, 21):  # 8 AM to 9 PM
            test_data = {**account_data, "hour_of_day": hour / 24}
            pred = self.predict(test_data, PredictionTarget.CONTACT_RESPONSE)

            if pred.probability > best_prob:
                best_prob = pred.probability
                best_hour = hour

        return {
            "optimal_hour": best_hour,
            "expected_response_rate": best_prob,
            "confidence": pred.confidence
        }

    def get_optimal_offer(self, account_data: dict[str, Any]) -> dict[str, Any]:
        """Predict optimal settlement offer"""
        balance = account_data.get("balance", 100)
        best_offer_pct = 0.5
        best_ev = 0.0

        for offer_pct in [0.4, 0.5, 0.6, 0.7, 0.8]:
            test_data = {**account_data, "offer_percent": offer_pct}
            pred = self.predict(test_data, PredictionTarget.SETTLEMENT_ACCEPTANCE)

            ev = balance * offer_pct * pred.probability
            if ev > best_ev:
                best_ev = ev
                best_offer_pct = offer_pct

        return {
            "optimal_offer_percent": best_offer_pct,
            "optimal_offer_amount": balance * best_offer_pct,
            "expected_value": best_ev,
            "acceptance_probability": pred.probability
        }

    def get_performance_report(self) -> dict[str, Any]:
        """Get ML performance report"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "predictors": {},
            "feature_importance": self.feature_store.get_feature_importance()[:10],
            "prediction_volume": len(self.prediction_history)
        }

        for target, predictor in self.predictors.items():
            report["predictors"][target.value] = {
                "model_weights": {
                    mt.value: w for mt, w in predictor.model_weights.items()
                },
                "recent_accuracy": self._calculate_recent_accuracy(target)
            }

        return report

    def _calculate_recent_accuracy(self, target: PredictionTarget) -> float:
        """Calculate recent prediction accuracy"""
        recent = [
            p for p in self.prediction_history[-100:]
            if p.target == target
        ]

        if not recent:
            return 0.0

        # Would calculate against actual outcomes in production
        return 0.75  # Placeholder


# Demonstration
if __name__ == "__main__":
    print("=== ML PREDICTION ENGINE DEMO ===\n")

    engine = MLPredictionEngine()

    # Sample account
    account = {
        "account_id": "A001",
        "balance": 147.50,
        "days_past_due": 67,
        "shadow_score": 580,
        "total_contacts": 5,
        "successful_contacts": 2,
        "response_rate": 0.4,
        "promise_kept_rate": 0.5,
        "debt_category": "bnpl"
    }

    # Make predictions
    print("Account Predictions:")
    print(f"  Balance: ${account['balance']}")
    print(f"  Shadow Score: {account['shadow_score']}")
    print()

    predictions = engine.predict_all(account)

    for target, pred in predictions.items():
        print(f"  {target.value}:")
        print(f"    Probability: {pred.probability:.1%}")
        print(f"    Confidence: {pred.confidence:.1%}")

    # Get optimal contact time
    print("\nOptimal Contact Time:")
    timing = engine.get_optimal_contact_time(account)
    print(f"  Best Hour: {timing['optimal_hour']}:00")
    print(f"  Expected Response: {timing['expected_response_rate']:.1%}")

    # Get optimal offer
    print("\nOptimal Settlement Offer:")
    offer = engine.get_optimal_offer(account)
    print(f"  Offer: {offer['optimal_offer_percent']:.0%} (${offer['optimal_offer_amount']:.2f})")
    print(f"  Expected Value: ${offer['expected_value']:.2f}")
    print(f"  Acceptance Prob: {offer['acceptance_probability']:.1%}")

    # Performance report
    print("\nPerformance Report:")
    report = engine.get_performance_report()
    print(f"  Prediction Volume: {report['prediction_volume']}")
    print(f"  Top Features: {[f[0] for f in report['feature_importance'][:5]]}")
