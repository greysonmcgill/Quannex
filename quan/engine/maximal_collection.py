"""
Maximal Collection Engine

The apex predator of the QUAN system. This engine orchestrates all
components to achieve maximum collection efficiency with minimum friction.

Key Principles:
1. Every account gets optimal treatment based on real-time intelligence
2. Resources are allocated dynamically based on expected ROI
3. Friction is continuously measured and minimized
4. Feedback loops drive continuous improvement
5. Unit economics are optimized at every decision point

Target Metrics:
- CTC: $0.50 or less per account
- Cost per dollar: $0.20 or less
- Recovery rate: 45-55% on sub-$500 debt
- ROI: 400%+ on micro-debt portfolios
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable
import asyncio
import hashlib
from collections import defaultdict
import random


class TreatmentStrategy(Enum):
    """Account treatment strategies"""
    FAST_TRACK = "fast_track"           # High probability, quick settlement
    STANDARD = "standard"               # Normal workflow
    REHABILITATION = "rehabilitation"   # Focus on rebuilding
    MICRO_AUTO = "micro_automated"      # Fully automated for tiny debts
    HIGH_TOUCH = "high_touch"           # Premium engagement for large balances
    PASSIVE = "passive"                 # Monitor only, tokenize
    LEGAL_PREP = "legal_prep"           # Preparing for legal action


class ChannelPriority(Enum):
    """Channel priority levels"""
    PRIMARY = 1
    SECONDARY = 2
    TERTIARY = 3
    FALLBACK = 4


@dataclass
class AccountState:
    """Current state of an account in the collection process"""
    account_id: str
    balance: float
    days_past_due: int
    shadow_score: int

    # Assignment
    strategy: TreatmentStrategy | None = None
    channel_sequence: list[str] = field(default_factory=list)
    current_channel_index: int = 0

    # Contact history
    total_contacts: int = 0
    successful_contacts: int = 0
    last_contact: datetime | None = None
    last_response: datetime | None = None

    # Negotiation state
    offers_made: int = 0
    last_offer: float | None = None
    counter_offers_received: int = 0
    best_counter: float | None = None

    # Payment state
    payment_promised: bool = False
    promise_date: datetime | None = None
    payment_plan_active: bool = False
    payments_made: int = 0
    total_paid: float = 0.0

    # Economics
    cost_incurred: float = 0.0
    expected_recovery: float = 0.0
    current_npv: float = 0.0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CollectionAction:
    """A collection action to be executed"""
    action_id: str
    account_id: str
    action_type: str  # contact, offer, payment_request, escalate, close
    channel: str
    priority: int
    parameters: dict[str, Any]
    scheduled_at: datetime
    executed_at: datetime | None = None
    result: str | None = None
    cost: float = 0.0


@dataclass
class OptimizationResult:
    """Result of optimization pass"""
    accounts_optimized: int
    strategies_assigned: dict[str, int]
    expected_recovery: float
    expected_cost: float
    expected_roi: float
    friction_score: float
    recommendations: list[str]


class ResourceAllocator:
    """
    Dynamically allocates resources based on expected ROI

    Resources are finite (contact capacity, agent time, capital).
    This allocator ensures they go to highest-value opportunities.
    """

    def __init__(self):
        self.daily_contact_capacity = 100000
        self.daily_voice_capacity = 5000
        self.daily_payment_capacity = 10000
        self.used_today = {
            "contact": 0,
            "voice": 0,
            "payment": 0
        }

    def allocate(
        self,
        account: AccountState,
        action_type: str
    ) -> tuple[bool, str]:
        """
        Attempt to allocate resources for an action

        Returns: (success, reason)
        """
        if action_type == "contact":
            if self.used_today["contact"] >= self.daily_contact_capacity:
                return False, "contact_capacity_exhausted"
            self.used_today["contact"] += 1
            return True, "allocated"

        elif action_type == "voice":
            if self.used_today["voice"] >= self.daily_voice_capacity:
                return False, "voice_capacity_exhausted"
            # Voice is expensive - only allocate for high-value
            if account.balance < 100 or account.shadow_score < 500:
                return False, "account_below_voice_threshold"
            self.used_today["voice"] += 1
            return True, "allocated"

        elif action_type == "payment":
            if self.used_today["payment"] >= self.daily_payment_capacity:
                return False, "payment_capacity_exhausted"
            self.used_today["payment"] += 1
            return True, "allocated"

        return True, "allocated"

    def get_utilization(self) -> dict[str, float]:
        """Get current resource utilization"""
        return {
            "contact": self.used_today["contact"] / self.daily_contact_capacity,
            "voice": self.used_today["voice"] / self.daily_voice_capacity,
            "payment": self.used_today["payment"] / self.daily_payment_capacity
        }

    def reset_daily(self) -> None:
        """Reset daily allocations"""
        self.used_today = {"contact": 0, "voice": 0, "payment": 0}


class StrategySelector:
    """
    Selects optimal strategy for each account

    Uses multi-armed bandit approach with Thompson Sampling
    to continuously learn which strategies work best for
    different account segments.
    """

    def __init__(self):
        # Beta distribution parameters for each strategy-segment pair
        self.strategy_performance: dict[str, dict[str, tuple[int, int]]] = defaultdict(
            lambda: {s.value: (1, 1) for s in TreatmentStrategy}
        )

    def select_strategy(self, account: AccountState) -> TreatmentStrategy:
        """Select optimal strategy using Thompson Sampling"""
        segment = self._get_segment(account)

        # Thompson sampling
        samples = {}
        for strategy, (alpha, beta) in self.strategy_performance[segment].items():
            # Sample from beta distribution
            samples[strategy] = random.betavariate(alpha, beta)

        # Select highest sample
        best = max(samples.items(), key=lambda x: x[1])
        return TreatmentStrategy(best[0])

    def record_outcome(
        self,
        account: AccountState,
        strategy: TreatmentStrategy,
        success: bool
    ) -> None:
        """Record outcome for learning"""
        segment = self._get_segment(account)
        alpha, beta = self.strategy_performance[segment][strategy.value]

        if success:
            self.strategy_performance[segment][strategy.value] = (alpha + 1, beta)
        else:
            self.strategy_performance[segment][strategy.value] = (alpha, beta + 1)

    def _get_segment(self, account: AccountState) -> str:
        """Get segment identifier for account"""
        score_tier = "high" if account.shadow_score >= 600 else "mid" if account.shadow_score >= 400 else "low"
        balance_tier = "micro" if account.balance < 50 else "small" if account.balance < 200 else "medium" if account.balance < 500 else "large"
        dpd_tier = "fresh" if account.days_past_due < 60 else "aged" if account.days_past_due < 120 else "stale"

        return f"{score_tier}_{balance_tier}_{dpd_tier}"

    def get_performance_report(self) -> dict[str, Any]:
        """Get performance report for all strategies"""
        report = {}
        for segment, strategies in self.strategy_performance.items():
            report[segment] = {
                strategy: alpha / (alpha + beta)
                for strategy, (alpha, beta) in strategies.items()
            }
        return report


class ChannelOptimizer:
    """
    Optimizes channel selection and sequencing

    Different consumers respond to different channels.
    This optimizer learns the best channel sequence for each segment.
    """

    def __init__(self):
        self.channel_performance: dict[str, dict[str, float]] = defaultdict(
            lambda: {"sms": 0.15, "email": 0.08, "voice": 0.25, "push": 0.05}
        )
        self.channel_costs = {
            "sms": 0.02,
            "email": 0.005,
            "voice": 0.15,
            "push": 0.001
        }

    def get_channel_sequence(self, account: AccountState) -> list[str]:
        """Get optimal channel sequence for account"""
        segment = self._get_segment(account)
        performance = self.channel_performance[segment]

        # Calculate ROI for each channel
        roi = {}
        for channel, response_rate in performance.items():
            cost = self.channel_costs[channel]
            expected_value = account.balance * 0.5 * response_rate  # Simplified
            roi[channel] = (expected_value - cost) / cost if cost > 0 else 0

        # Sort by ROI
        sorted_channels = sorted(roi.items(), key=lambda x: x[1], reverse=True)

        # Return sequence (skip negative ROI channels for micro debts)
        if account.balance < 50:
            return [c for c, r in sorted_channels if r > 0][:3]
        else:
            return [c for c, r in sorted_channels][:4]

    def record_response(
        self,
        account: AccountState,
        channel: str,
        responded: bool
    ) -> None:
        """Record channel response for learning"""
        segment = self._get_segment(account)
        current = self.channel_performance[segment][channel]

        # Exponential moving average update
        alpha = 0.1
        new_value = 1.0 if responded else 0.0
        self.channel_performance[segment][channel] = current * (1 - alpha) + new_value * alpha

    def _get_segment(self, account: AccountState) -> str:
        """Get segment identifier"""
        score_tier = "high" if account.shadow_score >= 600 else "mid" if account.shadow_score >= 400 else "low"
        return f"score_{score_tier}"


class SettlementOptimizer:
    """
    Optimizes settlement offers using game theory

    The goal is to find the optimal offer that maximizes
    P(accept) × offer_amount while minimizing negotiation rounds.
    """

    def __init__(self):
        self.acceptance_curves: dict[str, list[tuple[float, float]]] = defaultdict(
            lambda: [(0.4, 0.8), (0.5, 0.6), (0.6, 0.4), (0.7, 0.25), (0.8, 0.1)]
        )

    def get_optimal_offer(self, account: AccountState) -> dict[str, Any]:
        """Calculate optimal settlement offer"""
        segment = self._get_segment(account)
        curve = self.acceptance_curves[segment]

        # Find offer that maximizes expected value
        best_offer = None
        best_ev = 0

        for offer_pct, accept_prob in curve:
            ev = account.balance * offer_pct * accept_prob
            if ev > best_ev:
                best_ev = ev
                best_offer = {
                    "offer_percent": offer_pct,
                    "offer_amount": account.balance * offer_pct,
                    "acceptance_probability": accept_prob,
                    "expected_value": ev
                }

        # Adjust based on account history
        if account.counter_offers_received > 0 and account.best_counter:
            # They've countered - adjust towards their counter
            best_offer["offer_amount"] = (best_offer["offer_amount"] + account.best_counter) / 2
            best_offer["offer_percent"] = best_offer["offer_amount"] / account.balance

        # Consider payment plan for low liquidity
        if account.shadow_score < 450:
            best_offer["payment_plan"] = {
                "enabled": True,
                "weekly_amount": max(10, account.balance * best_offer["offer_percent"] / 8),
                "duration_weeks": 8
            }

        return best_offer

    def record_outcome(
        self,
        account: AccountState,
        offer_percent: float,
        accepted: bool
    ) -> None:
        """Record offer outcome for learning"""
        segment = self._get_segment(account)
        curve = self.acceptance_curves[segment]

        # Find closest point in curve and update
        for i, (pct, prob) in enumerate(curve):
            if abs(pct - offer_percent) < 0.05:
                # Update acceptance probability
                alpha = 0.1
                new_prob = 1.0 if accepted else 0.0
                curve[i] = (pct, prob * (1 - alpha) + new_prob * alpha)
                break

    def _get_segment(self, account: AccountState) -> str:
        """Get segment for settlement optimization"""
        score_tier = "high" if account.shadow_score >= 600 else "mid" if account.shadow_score >= 400 else "low"
        balance_tier = "small" if account.balance < 200 else "medium" if account.balance < 500 else "large"
        return f"{score_tier}_{balance_tier}"


class FrictionMinimizer:
    """
    Identifies and minimizes friction throughout the collection process

    Friction = anything that reduces collection probability or increases cost
    """

    def __init__(self):
        self.friction_log: list[dict[str, Any]] = []
        self.stage_metrics: dict[str, dict[str, float]] = defaultdict(
            lambda: {"throughput": 0, "conversion": 0, "latency_ms": 0}
        )

    def measure_friction(
        self,
        stage: str,
        input_count: int,
        output_count: int,
        latency_ms: float
    ) -> float:
        """Measure friction at a stage"""
        conversion = output_count / input_count if input_count > 0 else 0
        drop_off = 1 - conversion

        # Update metrics
        self.stage_metrics[stage]["throughput"] = input_count
        self.stage_metrics[stage]["conversion"] = conversion
        self.stage_metrics[stage]["latency_ms"] = latency_ms

        # Calculate friction score (0-1, lower is better)
        friction = drop_off * 0.7 + (min(latency_ms / 1000, 1) * 0.3)

        if friction > 0.3:  # High friction
            self.friction_log.append({
                "stage": stage,
                "friction": friction,
                "drop_off": drop_off,
                "latency_ms": latency_ms,
                "timestamp": datetime.now().isoformat()
            })

        return friction

    def get_friction_report(self) -> dict[str, Any]:
        """Get comprehensive friction report"""
        total_friction = sum(
            m["conversion"] for m in self.stage_metrics.values()
        ) / len(self.stage_metrics) if self.stage_metrics else 0

        problem_stages = [
            stage for stage, metrics in self.stage_metrics.items()
            if metrics["conversion"] < 0.5
        ]

        return {
            "overall_friction_score": 1 - total_friction,
            "problem_stages": problem_stages,
            "stage_metrics": dict(self.stage_metrics),
            "recent_issues": self.friction_log[-10:],
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> list[str]:
        """Generate friction reduction recommendations"""
        recs = []

        for stage, metrics in self.stage_metrics.items():
            if metrics["conversion"] < 0.3:
                recs.append(f"Critical: {stage} has {metrics['conversion']:.0%} conversion - investigate immediately")
            elif metrics["conversion"] < 0.5:
                recs.append(f"Warning: {stage} conversion at {metrics['conversion']:.0%} - optimize")

            if metrics["latency_ms"] > 500:
                recs.append(f"Performance: {stage} latency at {metrics['latency_ms']:.0f}ms - reduce")

        return recs


class MaximalCollectionEngine:
    """
    The master engine orchestrating all collection activities

    This is the brain of QUAN - it coordinates all components
    to achieve maximum collection efficiency.
    """

    def __init__(self):
        self.accounts: dict[str, AccountState] = {}
        self.action_queue: list[CollectionAction] = []
        self.completed_actions: list[CollectionAction] = []

        # Sub-components
        self.resource_allocator = ResourceAllocator()
        self.strategy_selector = StrategySelector()
        self.channel_optimizer = ChannelOptimizer()
        self.settlement_optimizer = SettlementOptimizer()
        self.friction_minimizer = FrictionMinimizer()

        # Metrics
        self.total_collected = 0.0
        self.total_cost = 0.0
        self.accounts_resolved = 0
        self.accounts_processed = 0

    def ingest_account(self, account_data: dict[str, Any]) -> AccountState:
        """Ingest a new account into the system"""
        account_id = account_data.get("account_id", hashlib.sha256(
            str(account_data).encode()
        ).hexdigest()[:12])

        account = AccountState(
            account_id=account_id,
            balance=account_data.get("balance", 0),
            days_past_due=account_data.get("days_past_due", 30),
            shadow_score=account_data.get("shadow_score", 500)
        )

        # Select strategy
        account.strategy = self.strategy_selector.select_strategy(account)

        # Get channel sequence
        account.channel_sequence = self.channel_optimizer.get_channel_sequence(account)

        # Calculate expected recovery
        account.expected_recovery = self._calculate_expected_recovery(account)

        # Calculate NPV
        account.current_npv = self._calculate_npv(account)

        self.accounts[account_id] = account
        return account

    def optimize_portfolio(self) -> OptimizationResult:
        """Run optimization pass on entire portfolio"""
        strategies_count: dict[str, int] = defaultdict(int)
        total_expected_recovery = 0.0
        total_expected_cost = 0.0

        for account in self.accounts.values():
            # Re-evaluate strategy
            new_strategy = self.strategy_selector.select_strategy(account)
            if new_strategy != account.strategy:
                account.strategy = new_strategy
                account.channel_sequence = self.channel_optimizer.get_channel_sequence(account)

            strategies_count[account.strategy.value] += 1

            # Update expected values
            account.expected_recovery = self._calculate_expected_recovery(account)
            account.current_npv = self._calculate_npv(account)

            total_expected_recovery += account.expected_recovery

            # Estimate cost based on strategy
            cost = self._estimate_cost(account)
            total_expected_cost += cost

        expected_roi = (
            (total_expected_recovery - total_expected_cost) / total_expected_cost
            if total_expected_cost > 0 else 0
        )

        # Measure friction
        friction_report = self.friction_minimizer.get_friction_report()

        return OptimizationResult(
            accounts_optimized=len(self.accounts),
            strategies_assigned=dict(strategies_count),
            expected_recovery=total_expected_recovery,
            expected_cost=total_expected_cost,
            expected_roi=expected_roi,
            friction_score=friction_report["overall_friction_score"],
            recommendations=friction_report["recommendations"]
        )

    def generate_actions(self, limit: int = 1000) -> list[CollectionAction]:
        """Generate prioritized action list"""
        actions = []

        # Sort accounts by NPV (highest first)
        sorted_accounts = sorted(
            self.accounts.values(),
            key=lambda a: a.current_npv,
            reverse=True
        )

        for account in sorted_accounts[:limit]:
            action = self._generate_action(account)
            if action:
                # Check resource availability
                can_allocate, reason = self.resource_allocator.allocate(
                    account, action.action_type
                )
                if can_allocate:
                    actions.append(action)
                    self.action_queue.append(action)

        return actions

    def execute_action(self, action: CollectionAction) -> dict[str, Any]:
        """Execute a collection action"""
        account = self.accounts.get(action.account_id)
        if not account:
            return {"success": False, "error": "account_not_found"}

        # Simulate execution
        result = self._simulate_action_execution(account, action)

        # Update account state
        account.total_contacts += 1
        account.cost_incurred += action.cost
        account.updated_at = datetime.now()

        if result["responded"]:
            account.successful_contacts += 1
            account.last_response = datetime.now()

            # Record for learning
            self.channel_optimizer.record_response(
                account, action.channel, True
            )

            if result.get("accepted_offer"):
                # Move to payment
                account.payment_promised = True
                account.promise_date = datetime.now()

                # Record settlement outcome
                self.settlement_optimizer.record_outcome(
                    account,
                    action.parameters.get("offer_percent", 0.5),
                    True
                )

        else:
            self.channel_optimizer.record_response(
                account, action.channel, False
            )

        # Update metrics
        self.total_cost += action.cost
        if result.get("payment_received"):
            self.total_collected += result["payment_received"]
            account.total_paid += result["payment_received"]

            if account.total_paid >= account.balance * 0.9:  # 90%+ = resolved
                self.accounts_resolved += 1

                # Record strategy success
                self.strategy_selector.record_outcome(account, account.strategy, True)

        self.accounts_processed += 1

        # Mark action complete
        action.executed_at = datetime.now()
        action.result = result.get("outcome", "completed")
        self.completed_actions.append(action)

        return result

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics"""
        total_balance = sum(a.balance for a in self.accounts.values())
        total_paid = sum(a.total_paid for a in self.accounts.values())

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio": {
                "total_accounts": len(self.accounts),
                "total_balance": total_balance,
                "accounts_resolved": self.accounts_resolved,
                "resolution_rate": self.accounts_resolved / len(self.accounts) if self.accounts else 0
            },
            "collections": {
                "total_collected": self.total_collected,
                "recovery_rate": total_paid / total_balance if total_balance > 0 else 0
            },
            "economics": {
                "total_cost": self.total_cost,
                "cost_per_dollar": self.total_cost / self.total_collected if self.total_collected > 0 else 0,
                "roi": (self.total_collected - self.total_cost) / self.total_cost if self.total_cost > 0 else 0,
                "cost_per_account": self.total_cost / self.accounts_processed if self.accounts_processed > 0 else 0
            },
            "operations": {
                "actions_executed": len(self.completed_actions),
                "actions_pending": len(self.action_queue),
                "resource_utilization": self.resource_allocator.get_utilization()
            },
            "optimization": {
                "strategy_performance": self.strategy_selector.get_performance_report(),
                "friction": self.friction_minimizer.get_friction_report()
            }
        }

    def _calculate_expected_recovery(self, account: AccountState) -> float:
        """Calculate expected recovery value"""
        # Base probability from shadow score
        base_prob = account.shadow_score / 850

        # Adjust for DPD
        if account.days_past_due < 60:
            dpd_factor = 1.1
        elif account.days_past_due < 120:
            dpd_factor = 1.0
        else:
            dpd_factor = 0.8

        # Adjust for balance
        if account.balance < 50:
            balance_factor = 1.2  # Micro debts easier
        elif account.balance > 500:
            balance_factor = 0.9  # Larger debts harder
        else:
            balance_factor = 1.0

        prob = base_prob * dpd_factor * balance_factor

        # Expected settlement amount (50-70% of balance)
        settlement_rate = 0.5 + (account.shadow_score / 850) * 0.2

        return account.balance * settlement_rate * min(1.0, prob)

    def _calculate_npv(self, account: AccountState) -> float:
        """Calculate NPV of account"""
        expected_recovery = account.expected_recovery
        expected_cost = self._estimate_cost(account)
        net = expected_recovery - expected_cost

        # Discount for time (assume 30 day resolution)
        discount_rate = 0.15 / 12  # 15% annual, monthly
        npv = net / (1 + discount_rate)

        return npv

    def _estimate_cost(self, account: AccountState) -> float:
        """Estimate cost to collect account"""
        if account.strategy == TreatmentStrategy.MICRO_AUTO:
            return 0.25  # Fully automated
        elif account.strategy == TreatmentStrategy.FAST_TRACK:
            return 0.35
        elif account.strategy == TreatmentStrategy.STANDARD:
            return 0.50
        elif account.strategy == TreatmentStrategy.REHABILITATION:
            return 0.75
        elif account.strategy == TreatmentStrategy.HIGH_TOUCH:
            return 1.50
        elif account.strategy == TreatmentStrategy.PASSIVE:
            return 0.10
        else:
            return 0.50

    def _generate_action(self, account: AccountState) -> CollectionAction | None:
        """Generate next action for account"""
        # Determine action type based on account state
        if account.payment_plan_active:
            action_type = "payment_reminder"
        elif account.payment_promised:
            action_type = "payment_request"
        elif account.successful_contacts > 0:
            action_type = "offer"
        else:
            action_type = "contact"

        # Get channel
        if account.current_channel_index < len(account.channel_sequence):
            channel = account.channel_sequence[account.current_channel_index]
        else:
            channel = "sms"  # Default fallback

        # Build parameters
        parameters = {}
        if action_type == "offer":
            offer = self.settlement_optimizer.get_optimal_offer(account)
            parameters = offer

        # Calculate cost
        cost = self.channel_optimizer.channel_costs.get(channel, 0.02)

        return CollectionAction(
            action_id=hashlib.sha256(
                f"{account.account_id}{datetime.now()}{random.random()}".encode()
            ).hexdigest()[:12],
            account_id=account.account_id,
            action_type=action_type,
            channel=channel,
            priority=1 if account.current_npv > 50 else 2 if account.current_npv > 20 else 3,
            parameters=parameters,
            scheduled_at=datetime.now(),
            cost=cost
        )

    def _simulate_action_execution(
        self,
        account: AccountState,
        action: CollectionAction
    ) -> dict[str, Any]:
        """Simulate action execution (for testing)"""
        # Response probability based on channel and account
        base_response = {
            "sms": 0.15,
            "email": 0.08,
            "voice": 0.25,
            "push": 0.05
        }.get(action.channel, 0.10)

        # Adjust for shadow score
        response_prob = base_response * (account.shadow_score / 500)

        responded = random.random() < response_prob

        result = {
            "responded": responded,
            "outcome": "response" if responded else "no_response"
        }

        if responded and action.action_type == "offer":
            # Acceptance probability
            offer_pct = action.parameters.get("offer_percent", 0.5)
            accept_prob = max(0.1, 0.8 - offer_pct)  # Lower offer = higher accept

            if random.random() < accept_prob:
                result["accepted_offer"] = True
                result["outcome"] = "accepted"

                # Simulate payment
                if random.random() < 0.8:  # 80% follow through
                    result["payment_received"] = action.parameters.get("offer_amount", account.balance * 0.5)

        return result


# Demonstration
if __name__ == "__main__":
    print("=== MAXIMAL COLLECTION ENGINE DEMO ===\n")

    engine = MaximalCollectionEngine()

    # Ingest sample accounts
    print("Ingesting accounts...")
    sample_accounts = [
        {"account_id": f"A{i:04d}", "balance": random.uniform(25, 500),
         "days_past_due": random.randint(30, 180),
         "shadow_score": random.randint(350, 750)}
        for i in range(1000)
    ]

    for acc_data in sample_accounts:
        engine.ingest_account(acc_data)

    print(f"Ingested {len(engine.accounts)} accounts")

    # Optimize portfolio
    print("\nOptimizing portfolio...")
    optimization = engine.optimize_portfolio()
    print(f"  Strategies assigned: {optimization.strategies_assigned}")
    print(f"  Expected recovery: ${optimization.expected_recovery:,.2f}")
    print(f"  Expected cost: ${optimization.expected_cost:,.2f}")
    print(f"  Expected ROI: {optimization.expected_roi:.0%}")
    print(f"  Friction score: {optimization.friction_score:.2f}")

    # Generate and execute actions
    print("\nExecuting collection actions...")
    for round_num in range(5):
        actions = engine.generate_actions(limit=200)
        for action in actions:
            engine.execute_action(action)

        metrics = engine.get_metrics()
        print(f"  Round {round_num + 1}: Collected ${metrics['collections']['total_collected']:,.2f}, "
              f"Cost ${metrics['economics']['total_cost']:,.2f}, "
              f"ROI {metrics['economics']['roi']:.0%}")

    # Final metrics
    print("\n=== FINAL METRICS ===")
    final = engine.get_metrics()
    print(f"Portfolio:")
    print(f"  Total accounts: {final['portfolio']['total_accounts']}")
    print(f"  Accounts resolved: {final['portfolio']['accounts_resolved']}")
    print(f"  Resolution rate: {final['portfolio']['resolution_rate']:.1%}")
    print(f"\nCollections:")
    print(f"  Total collected: ${final['collections']['total_collected']:,.2f}")
    print(f"  Recovery rate: {final['collections']['recovery_rate']:.1%}")
    print(f"\nEconomics:")
    print(f"  Total cost: ${final['economics']['total_cost']:,.2f}")
    print(f"  Cost per dollar: ${final['economics']['cost_per_dollar']:.2f}")
    print(f"  Cost per account: ${final['economics']['cost_per_account']:.2f}")
    print(f"  ROI: {final['economics']['roi']:.0%}")
