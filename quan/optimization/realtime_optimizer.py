"""
Real-Time Optimization System

Continuous optimization of collection parameters in real-time:
1. Dynamic strategy adjustment based on live performance
2. Channel mix optimization
3. Settlement offer calibration
4. Contact timing optimization
5. Resource allocation balancing
6. Feedback loop processing

Uses online learning algorithms for immediate adaptation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable
import math
import random
from collections import defaultdict, deque


class OptimizationDomain(Enum):
    """Domains that can be optimized"""
    STRATEGY = "strategy"
    CHANNEL = "channel"
    TIMING = "timing"
    SETTLEMENT = "settlement"
    RESOURCE = "resource"
    ROUTING = "routing"


class LearningAlgorithm(Enum):
    """Online learning algorithms"""
    THOMPSON_SAMPLING = "thompson"
    UCB1 = "ucb1"
    EPSILON_GREEDY = "epsilon_greedy"
    EXP3 = "exp3"
    GRADIENT_BANDIT = "gradient"


@dataclass
class OptimizationState:
    """Current state of optimization for a domain"""
    domain: OptimizationDomain
    current_best: str
    confidence: float
    last_updated: datetime
    exploration_rate: float = 0.1
    total_trials: int = 0
    total_reward: float = 0.0


@dataclass
class ArmStatistics:
    """Statistics for a bandit arm"""
    arm_id: str
    pulls: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    variance: float = 0.0
    last_pulled: datetime | None = None

    # Bayesian stats (for Thompson Sampling)
    alpha: float = 1.0  # Beta distribution parameter
    beta: float = 1.0


@dataclass
class OptimizationEvent:
    """Event recording an optimization decision and outcome"""
    event_id: str
    domain: OptimizationDomain
    arm_selected: str
    reward: float
    context: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class MultiArmedBandit:
    """
    Multi-Armed Bandit implementation for real-time optimization

    Supports multiple algorithms for different use cases
    """

    def __init__(
        self,
        arms: list[str],
        algorithm: LearningAlgorithm = LearningAlgorithm.THOMPSON_SAMPLING
    ):
        self.arms = {arm: ArmStatistics(arm_id=arm) for arm in arms}
        self.algorithm = algorithm
        self.total_pulls = 0
        self.history: list[tuple[str, float]] = []

    def select_arm(self, context: dict[str, Any] | None = None) -> str:
        """Select an arm based on the algorithm"""
        if self.algorithm == LearningAlgorithm.THOMPSON_SAMPLING:
            return self._thompson_sampling()
        elif self.algorithm == LearningAlgorithm.UCB1:
            return self._ucb1()
        elif self.algorithm == LearningAlgorithm.EPSILON_GREEDY:
            return self._epsilon_greedy()
        elif self.algorithm == LearningAlgorithm.EXP3:
            return self._exp3()
        else:
            return self._gradient_bandit()

    def update(self, arm_id: str, reward: float) -> None:
        """Update arm statistics with observed reward"""
        if arm_id not in self.arms:
            return

        arm = self.arms[arm_id]
        arm.pulls += 1
        arm.total_reward += reward
        arm.last_pulled = datetime.now()

        # Update running average
        old_avg = arm.avg_reward
        arm.avg_reward = arm.total_reward / arm.pulls

        # Update variance (Welford's algorithm)
        if arm.pulls > 1:
            arm.variance += (reward - old_avg) * (reward - arm.avg_reward)

        # Update Bayesian parameters
        if reward > 0.5:  # Success
            arm.alpha += 1
        else:
            arm.beta += 1

        self.total_pulls += 1
        self.history.append((arm_id, reward))

    def _thompson_sampling(self) -> str:
        """Thompson Sampling selection"""
        samples = {}
        for arm_id, arm in self.arms.items():
            # Sample from beta distribution
            samples[arm_id] = random.betavariate(arm.alpha, arm.beta)

        return max(samples.items(), key=lambda x: x[1])[0]

    def _ucb1(self) -> str:
        """Upper Confidence Bound selection"""
        if self.total_pulls < len(self.arms):
            # Explore all arms first
            for arm_id, arm in self.arms.items():
                if arm.pulls == 0:
                    return arm_id

        ucb_values = {}
        for arm_id, arm in self.arms.items():
            if arm.pulls == 0:
                ucb_values[arm_id] = float('inf')
            else:
                exploration = math.sqrt(2 * math.log(self.total_pulls) / arm.pulls)
                ucb_values[arm_id] = arm.avg_reward + exploration

        return max(ucb_values.items(), key=lambda x: x[1])[0]

    def _epsilon_greedy(self, epsilon: float = 0.1) -> str:
        """Epsilon-greedy selection"""
        if random.random() < epsilon:
            return random.choice(list(self.arms.keys()))
        else:
            return max(self.arms.items(), key=lambda x: x[1].avg_reward)[0]

    def _exp3(self, gamma: float = 0.1) -> str:
        """EXP3 for adversarial settings"""
        weights = {}
        total_weight = 0

        for arm_id, arm in self.arms.items():
            weight = math.exp(gamma * arm.total_reward / max(arm.pulls, 1))
            weights[arm_id] = weight
            total_weight += weight

        # Sample proportionally
        r = random.random() * total_weight
        cumsum = 0
        for arm_id, weight in weights.items():
            cumsum += weight
            if r <= cumsum:
                return arm_id

        return list(self.arms.keys())[-1]

    def _gradient_bandit(self, alpha: float = 0.1) -> str:
        """Gradient bandit with preference learning"""
        # Convert rewards to preferences
        preferences = {}
        avg_reward = sum(a.avg_reward for a in self.arms.values()) / len(self.arms)

        for arm_id, arm in self.arms.items():
            pref = (arm.avg_reward - avg_reward) * alpha
            preferences[arm_id] = pref

        # Softmax selection
        max_pref = max(preferences.values())
        exp_prefs = {k: math.exp(v - max_pref) for k, v in preferences.items()}
        total_exp = sum(exp_prefs.values())

        r = random.random() * total_exp
        cumsum = 0
        for arm_id, exp_pref in exp_prefs.items():
            cumsum += exp_pref
            if r <= cumsum:
                return arm_id

        return list(self.arms.keys())[-1]

    def get_statistics(self) -> dict[str, Any]:
        """Get current statistics for all arms"""
        return {
            arm_id: {
                "pulls": arm.pulls,
                "avg_reward": arm.avg_reward,
                "success_rate": arm.alpha / (arm.alpha + arm.beta),
                "confidence": 1 - (arm.beta / (arm.alpha + arm.beta + 10))
            }
            for arm_id, arm in self.arms.items()
        }


class ContextualBandit:
    """
    Contextual bandit for context-dependent optimization

    Uses linear regression to learn context-reward relationships
    """

    def __init__(self, arms: list[str], n_features: int):
        self.arms = arms
        self.n_features = n_features

        # Linear coefficients for each arm
        self.weights: dict[str, list[float]] = {
            arm: [0.0] * n_features for arm in arms
        }

        # Covariance matrices for uncertainty
        self.covariances: dict[str, list[list[float]]] = {
            arm: [[1.0 if i == j else 0.0 for j in range(n_features)]
                  for i in range(n_features)]
            for arm in arms
        }

        self.total_pulls = 0

    def select_arm(self, context: list[float]) -> str:
        """Select arm based on context using LinUCB"""
        if len(context) != self.n_features:
            context = context[:self.n_features] + [0.0] * (self.n_features - len(context))

        ucb_values = {}

        for arm in self.arms:
            # Predicted reward
            predicted = sum(w * c for w, c in zip(self.weights[arm], context))

            # Uncertainty bonus
            uncertainty = self._compute_uncertainty(arm, context)

            ucb_values[arm] = predicted + 2.0 * uncertainty

        return max(ucb_values.items(), key=lambda x: x[1])[0]

    def update(self, arm: str, context: list[float], reward: float) -> None:
        """Update model with observed reward"""
        if len(context) != self.n_features:
            context = context[:self.n_features] + [0.0] * (self.n_features - len(context))

        # Simple online update (would use ridge regression in production)
        alpha = 0.1
        predicted = sum(w * c for w, c in zip(self.weights[arm], context))
        error = reward - predicted

        for i in range(self.n_features):
            self.weights[arm][i] += alpha * error * context[i]

        self.total_pulls += 1

    def _compute_uncertainty(self, arm: str, context: list[float]) -> float:
        """Compute uncertainty for arm given context"""
        # Simplified uncertainty computation
        norm = math.sqrt(sum(c * c for c in context))
        base_uncertainty = 1.0 / (1.0 + self.total_pulls / len(self.arms) / 10)
        return base_uncertainty * max(0.1, norm)


class OnlineGradientOptimizer:
    """
    Online gradient descent for continuous parameter optimization

    Optimizes continuous parameters (like settlement percentages)
    """

    def __init__(
        self,
        parameter_name: str,
        min_value: float,
        max_value: float,
        initial_value: float | None = None
    ):
        self.parameter_name = parameter_name
        self.min_value = min_value
        self.max_value = max_value
        self.current_value = initial_value or (min_value + max_value) / 2

        self.learning_rate = 0.01
        self.momentum = 0.9
        self.velocity = 0.0

        self.history: list[tuple[float, float]] = []  # (value, reward)

    def get_value(self) -> float:
        """Get current parameter value with exploration noise"""
        noise = random.gauss(0, 0.05 * (self.max_value - self.min_value))
        return max(self.min_value, min(self.max_value, self.current_value + noise))

    def update(self, value_used: float, reward: float) -> None:
        """Update parameter based on reward"""
        self.history.append((value_used, reward))

        # Estimate gradient using finite differences
        if len(self.history) >= 2:
            recent = self.history[-10:]  # Last 10 observations

            # Group by above/below current value
            above = [(v, r) for v, r in recent if v > self.current_value]
            below = [(v, r) for v, r in recent if v <= self.current_value]

            if above and below:
                avg_above = sum(r for _, r in above) / len(above)
                avg_below = sum(r for _, r in below) / len(below)

                gradient = avg_above - avg_below

                # Update with momentum
                self.velocity = self.momentum * self.velocity + self.learning_rate * gradient
                self.current_value += self.velocity

                # Clamp to bounds
                self.current_value = max(self.min_value, min(self.max_value, self.current_value))

    def get_optimal_estimate(self) -> float:
        """Get estimated optimal value"""
        if len(self.history) < 10:
            return self.current_value

        # Fit quadratic to recent history
        recent = self.history[-50:]

        # Simple: return value with highest reward
        best_value, _ = max(recent, key=lambda x: x[1])

        # Blend with current estimate
        return 0.7 * self.current_value + 0.3 * best_value


class RealTimeOptimizer:
    """
    Master real-time optimization system

    Coordinates multiple optimization domains for maximum performance
    """

    def __init__(self):
        # Strategy optimization (which workflow)
        self.strategy_bandit = MultiArmedBandit(
            arms=["fast_track", "standard", "rehabilitation", "micro_auto", "high_touch"],
            algorithm=LearningAlgorithm.THOMPSON_SAMPLING
        )

        # Channel optimization
        self.channel_bandit = MultiArmedBandit(
            arms=["sms", "email", "voice", "push"],
            algorithm=LearningAlgorithm.UCB1
        )

        # Timing optimization (hour of day)
        self.timing_bandit = MultiArmedBandit(
            arms=[f"hour_{h}" for h in range(8, 21)],
            algorithm=LearningAlgorithm.THOMPSON_SAMPLING
        )

        # Settlement optimization
        self.settlement_optimizer = OnlineGradientOptimizer(
            parameter_name="settlement_percent",
            min_value=0.30,
            max_value=0.90,
            initial_value=0.55
        )

        # Contextual optimization for personalization
        self.contextual_bandit = ContextualBandit(
            arms=["aggressive", "moderate", "gentle"],
            n_features=5  # shadow_score, balance, dpd, contacts, responses
        )

        # Event history
        self.events: deque = deque(maxlen=10000)

        # Performance tracking
        self.domain_performance: dict[OptimizationDomain, list[float]] = defaultdict(list)

        # Real-time metrics
        self.metrics = {
            "total_decisions": 0,
            "total_reward": 0.0,
            "avg_reward": 0.0,
            "best_strategy": None,
            "best_channel": None,
            "optimal_settlement": 0.55
        }

    def optimize_strategy(self, account_context: dict[str, Any]) -> str:
        """Select optimal strategy for account"""
        strategy = self.strategy_bandit.select_arm(account_context)
        self.metrics["total_decisions"] += 1
        return strategy

    def optimize_channel(self, account_context: dict[str, Any]) -> str:
        """Select optimal channel for account"""
        channel = self.channel_bandit.select_arm(account_context)
        return channel

    def optimize_timing(self) -> int:
        """Select optimal contact hour"""
        hour_arm = self.timing_bandit.select_arm()
        return int(hour_arm.split("_")[1])

    def optimize_settlement(self, account_context: dict[str, Any]) -> float:
        """Get optimal settlement percentage"""
        base = self.settlement_optimizer.get_value()

        # Adjust for account context
        shadow_score = account_context.get("shadow_score", 500)
        if shadow_score > 650:
            return min(0.85, base + 0.10)  # Higher score = can ask more
        elif shadow_score < 400:
            return max(0.35, base - 0.10)  # Lower score = need to offer less

        return base

    def optimize_approach(self, context_vector: list[float]) -> str:
        """Select personalized approach using contextual bandit"""
        return self.contextual_bandit.select_arm(context_vector)

    def record_outcome(
        self,
        domain: OptimizationDomain,
        arm_or_value: str | float,
        reward: float,
        context: dict[str, Any] | None = None
    ) -> None:
        """Record outcome for learning"""
        if domain == OptimizationDomain.STRATEGY:
            self.strategy_bandit.update(str(arm_or_value), reward)
        elif domain == OptimizationDomain.CHANNEL:
            self.channel_bandit.update(str(arm_or_value), reward)
        elif domain == OptimizationDomain.TIMING:
            self.timing_bandit.update(f"hour_{arm_or_value}", reward)
        elif domain == OptimizationDomain.SETTLEMENT:
            self.settlement_optimizer.update(float(arm_or_value), reward)

        # Update metrics
        self.metrics["total_reward"] += reward
        self.metrics["avg_reward"] = self.metrics["total_reward"] / self.metrics["total_decisions"]

        # Track domain performance
        self.domain_performance[domain].append(reward)

        # Record event
        self.events.append(OptimizationEvent(
            event_id=f"evt_{len(self.events)}",
            domain=domain,
            arm_selected=str(arm_or_value),
            reward=reward,
            context=context or {}
        ))

        # Update best performers
        self._update_best_performers()

    def _update_best_performers(self) -> None:
        """Update best performer tracking"""
        # Best strategy
        strategy_stats = self.strategy_bandit.get_statistics()
        if strategy_stats:
            self.metrics["best_strategy"] = max(
                strategy_stats.items(),
                key=lambda x: x[1]["avg_reward"]
            )[0]

        # Best channel
        channel_stats = self.channel_bandit.get_statistics()
        if channel_stats:
            self.metrics["best_channel"] = max(
                channel_stats.items(),
                key=lambda x: x[1]["avg_reward"]
            )[0]

        # Optimal settlement
        self.metrics["optimal_settlement"] = self.settlement_optimizer.get_optimal_estimate()

    def get_recommendations(self, account_context: dict[str, Any]) -> dict[str, Any]:
        """Get all optimization recommendations for an account"""
        context_vector = [
            account_context.get("shadow_score", 500) / 850,
            account_context.get("balance", 100) / 500,
            account_context.get("days_past_due", 60) / 180,
            account_context.get("total_contacts", 0) / 10,
            account_context.get("response_rate", 0)
        ]

        return {
            "strategy": self.optimize_strategy(account_context),
            "channel": self.optimize_channel(account_context),
            "contact_hour": self.optimize_timing(),
            "settlement_percent": self.optimize_settlement(account_context),
            "approach": self.optimize_approach(context_vector),
            "confidence": self._calculate_confidence()
        }

    def _calculate_confidence(self) -> float:
        """Calculate overall optimization confidence"""
        if self.metrics["total_decisions"] < 100:
            return 0.3 + (self.metrics["total_decisions"] / 100) * 0.3

        return min(0.95, 0.6 + self.metrics["avg_reward"] * 0.3)

    def get_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics,
            "strategy_stats": self.strategy_bandit.get_statistics(),
            "channel_stats": self.channel_bandit.get_statistics(),
            "timing_stats": self.timing_bandit.get_statistics(),
            "settlement_optimal": self.settlement_optimizer.get_optimal_estimate(),
            "domain_performance": {
                d.value: {
                    "count": len(rewards),
                    "avg_reward": sum(rewards) / len(rewards) if rewards else 0
                }
                for d, rewards in self.domain_performance.items()
            },
            "recent_trend": self._calculate_trend()
        }

    def _calculate_trend(self) -> str:
        """Calculate recent performance trend"""
        if len(self.events) < 100:
            return "insufficient_data"

        recent = list(self.events)[-100:]
        first_half = recent[:50]
        second_half = recent[50:]

        avg_first = sum(e.reward for e in first_half) / 50
        avg_second = sum(e.reward for e in second_half) / 50

        if avg_second > avg_first * 1.05:
            return "improving"
        elif avg_second < avg_first * 0.95:
            return "declining"
        else:
            return "stable"


# Demonstration
if __name__ == "__main__":
    print("=== REAL-TIME OPTIMIZER DEMO ===\n")

    optimizer = RealTimeOptimizer()

    # Simulate optimization over many accounts
    print("Running optimization simulation...")

    for i in range(500):
        # Random account context
        account = {
            "shadow_score": random.randint(350, 750),
            "balance": random.uniform(25, 500),
            "days_past_due": random.randint(30, 180),
            "total_contacts": random.randint(0, 10),
            "response_rate": random.random() * 0.5
        }

        # Get recommendations
        recs = optimizer.get_recommendations(account)

        # Simulate outcomes (reward based on decisions)
        strategy_reward = 0.5 + random.random() * 0.3 if recs["strategy"] == "fast_track" else random.random() * 0.5
        channel_reward = 0.4 + random.random() * 0.4 if recs["channel"] == "sms" else random.random() * 0.3
        timing_reward = 0.5 + random.random() * 0.3 if 10 <= recs["contact_hour"] <= 14 else random.random() * 0.4

        # Record outcomes
        optimizer.record_outcome(OptimizationDomain.STRATEGY, recs["strategy"], strategy_reward, account)
        optimizer.record_outcome(OptimizationDomain.CHANNEL, recs["channel"], channel_reward, account)
        optimizer.record_outcome(OptimizationDomain.TIMING, recs["contact_hour"], timing_reward)
        optimizer.record_outcome(OptimizationDomain.SETTLEMENT, recs["settlement_percent"], random.random())

    # Get report
    report = optimizer.get_performance_report()

    print("\n=== OPTIMIZATION RESULTS ===")
    print(f"Total Decisions: {report['metrics']['total_decisions']}")
    print(f"Average Reward: {report['metrics']['avg_reward']:.3f}")
    print(f"Trend: {report['recent_trend']}")
    print()
    print("Best Performers:")
    print(f"  Strategy: {report['metrics']['best_strategy']}")
    print(f"  Channel: {report['metrics']['best_channel']}")
    print(f"  Settlement: {report['settlement_optimal']:.1%}")
    print()
    print("Strategy Statistics:")
    for strategy, stats in report['strategy_stats'].items():
        print(f"  {strategy}: {stats['avg_reward']:.3f} avg, {stats['pulls']} pulls")
