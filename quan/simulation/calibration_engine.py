"""
Advanced Model Calibration Engine

Iteratively optimizes collection parameters for:
- Maximum recovery rate
- Minimum cost per dollar collected
- Risk-adjusted returns
- Optimal contact cadence
- Channel effectiveness
"""

import asyncio
import random
import statistics
import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CalibrationParameters:
    """Tunable parameters for model calibration"""
    # Contact strategy
    contact_cadence_days: int = 3
    max_contact_attempts: int = 8
    escalation_threshold: int = 3

    # Re-engagement
    re_engagement_delay_days: int = 10
    max_re_engagements: int = 3
    re_engagement_discount_pct: float = 0.20

    # Channel weights (must sum to 1.0)
    sms_weight: float = 0.55
    email_weight: float = 0.35
    push_weight: float = 0.10

    # Probability modifiers
    base_conversion_mult: float = 0.30
    digital_native_bonus: float = 0.10
    mobile_bonus: float = 0.05
    saved_payment_bonus: float = 0.25
    first_contact_penalty: float = 0.30
    contact_decay_rate: float = 0.12

    # Risk thresholds
    bankruptcy_block: bool = True
    dispute_reduction: float = 0.50
    sol_reduction: float = 0.30

    # Payment behavior
    full_payment_rate: float = 0.85
    partial_payment_min: float = 0.40
    partial_payment_max: float = 0.80
    save_payment_rate: float = 0.70


@dataclass
class CalibrationResult:
    """Result from a single calibration run"""
    iteration: int
    parameters: CalibrationParameters
    recovery_rate: float
    profit_margin: float
    cost_per_dollar: float
    roi: float
    digital_rate: float
    avg_days_to_collect: float
    risk_score: float
    efficiency_score: float

    # Composite fitness score
    fitness: float = 0.0


@dataclass
class RiskProfile:
    """Risk profile for collection strategy"""
    account_id: str
    risk_level: str  # "low", "medium", "high", "critical"
    risk_score: float
    risk_factors: List[str]
    recommended_strategy: str
    max_contacts: int
    preferred_channels: List[str]
    settlement_eligible: bool
    hardship_candidate: bool


class RiskStrategyEngine:
    """
    Risk-adjusted collection strategy engine.

    Segments accounts by risk and applies appropriate strategies.
    """

    def __init__(self):
        self.risk_profiles: Dict[str, RiskProfile] = {}

    def assess_risk(self, account: Dict[str, Any]) -> RiskProfile:
        """Assess risk and determine collection strategy"""
        risk_factors = []
        risk_score = 0.0

        # Balance-based risk
        balance = float(account.get("balance", 0))
        if balance > 800:
            risk_score += 0.1
            risk_factors.append("higher_balance")

        # Demographics risk
        age = account.get("age", 35)
        if age < 25:
            risk_score += 0.15
            risk_factors.append("young_demographic")
        elif age > 65:
            risk_score += 0.1
            risk_factors.append("senior_demographic")

        # Payment willingness
        willingness = account.get("payment_willingness", 0.5)
        if willingness < 0.3:
            risk_score += 0.25
            risk_factors.append("low_willingness")

        # Contact quality
        if not account.get("phone_valid", True):
            risk_score += 0.15
            risk_factors.append("invalid_phone")
        if not account.get("email_valid", True):
            risk_score += 0.1
            risk_factors.append("invalid_email")

        # Digital readiness
        if not account.get("is_digital_native", False):
            risk_score += 0.1
            risk_factors.append("not_digital_native")
        if not account.get("has_mobile", True):
            risk_score += 0.15
            risk_factors.append("no_mobile")

        # Previous failures
        contact_attempts = account.get("contact_attempts", 0)
        if contact_attempts > 5:
            risk_score += 0.2
            risk_factors.append("multiple_failed_contacts")

        # Cap at 1.0
        risk_score = min(1.0, risk_score)

        # Determine risk level
        if risk_score < 0.25:
            risk_level = "low"
            strategy = "standard"
            max_contacts = 8
            channels = ["sms", "email", "push"]
        elif risk_score < 0.50:
            risk_level = "medium"
            strategy = "enhanced"
            max_contacts = 10
            channels = ["sms", "email"]
        elif risk_score < 0.75:
            risk_level = "high"
            strategy = "intensive"
            max_contacts = 12
            channels = ["sms", "email", "push"]
        else:
            risk_level = "critical"
            strategy = "settlement_focus"
            max_contacts = 6
            channels = ["email", "sms"]

        # Settlement and hardship eligibility
        settlement_eligible = risk_score > 0.4 or balance > 500
        hardship_candidate = willingness < 0.35 or "low_willingness" in risk_factors

        profile = RiskProfile(
            account_id=account.get("account_id", ""),
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            recommended_strategy=strategy,
            max_contacts=max_contacts,
            preferred_channels=channels,
            settlement_eligible=settlement_eligible,
            hardship_candidate=hardship_candidate
        )

        self.risk_profiles[profile.account_id] = profile
        return profile

    def get_contact_strategy(
        self,
        profile: RiskProfile,
        contact_count: int
    ) -> Dict[str, Any]:
        """Get optimal contact strategy based on risk profile"""
        strategy = {
            "should_contact": True,
            "channel": profile.preferred_channels[0] if profile.preferred_channels else "sms",
            "message_type": "standard",
            "offer_settlement": False,
            "urgency_level": "normal"
        }

        # Adjust based on contact count
        if contact_count >= profile.max_contacts:
            strategy["should_contact"] = False
            return strategy

        # Escalation logic
        if contact_count >= 3 and profile.risk_level in ["high", "critical"]:
            strategy["offer_settlement"] = profile.settlement_eligible
            strategy["message_type"] = "settlement_offer"
            strategy["urgency_level"] = "high"

        # Channel rotation
        if contact_count > 0 and len(profile.preferred_channels) > 1:
            channel_idx = contact_count % len(profile.preferred_channels)
            strategy["channel"] = profile.preferred_channels[channel_idx]

        # Hardship messaging
        if profile.hardship_candidate and contact_count >= 2:
            strategy["message_type"] = "hardship_option"

        return strategy


class ChannelOptimizer:
    """
    Optimizes channel selection based on performance data.
    """

    def __init__(self):
        # Channel performance tracking
        self.channel_stats = {
            "sms": {"attempts": 0, "conversions": 0, "cost": Decimal("0.02")},
            "email": {"attempts": 0, "conversions": 0, "cost": Decimal("0.005")},
            "push": {"attempts": 0, "conversions": 0, "cost": Decimal("0.01")},
        }

    def record_attempt(self, channel: str, converted: bool):
        """Record a channel attempt"""
        if channel in self.channel_stats:
            self.channel_stats[channel]["attempts"] += 1
            if converted:
                self.channel_stats[channel]["conversions"] += 1

    def get_conversion_rates(self) -> Dict[str, float]:
        """Get conversion rates by channel"""
        rates = {}
        for channel, stats in self.channel_stats.items():
            if stats["attempts"] > 0:
                rates[channel] = stats["conversions"] / stats["attempts"]
            else:
                rates[channel] = 0.0
        return rates

    def get_cost_effectiveness(self) -> Dict[str, float]:
        """Get cost per conversion by channel"""
        effectiveness = {}
        for channel, stats in self.channel_stats.items():
            if stats["conversions"] > 0:
                total_cost = float(stats["cost"]) * stats["attempts"]
                effectiveness[channel] = total_cost / stats["conversions"]
            else:
                effectiveness[channel] = float("inf")
        return effectiveness

    def get_optimal_channel_mix(self) -> Dict[str, float]:
        """Calculate optimal channel mix based on performance"""
        rates = self.get_conversion_rates()
        costs = self.get_cost_effectiveness()

        # Score = conversion_rate / cost_per_conversion
        scores = {}
        total_score = 0

        for channel in self.channel_stats.keys():
            if rates.get(channel, 0) > 0 and costs.get(channel, float("inf")) < float("inf"):
                score = rates[channel] / (costs[channel] + 0.01)  # Avoid division by zero
                scores[channel] = score
                total_score += score
            else:
                scores[channel] = 0.1  # Minimum allocation

        # Normalize to weights
        if total_score > 0:
            weights = {ch: sc / total_score for ch, sc in scores.items()}
        else:
            weights = {"sms": 0.55, "email": 0.35, "push": 0.10}

        return weights


class CalibrationEngine:
    """
    Main calibration engine that iteratively optimizes parameters.
    """

    # Target metrics (industry benchmarks)
    TARGETS = {
        "recovery_rate": 0.35,  # 35% recovery for sub-$1K
        "profit_margin": 0.85,  # 85% margin
        "cost_per_dollar": 0.15,  # $0.15 per dollar collected
        "digital_rate": 0.80,  # 80% digital payments
        "days_to_collect": 5.0,  # 5 days average
    }

    # Parameter bounds
    BOUNDS = {
        "contact_cadence_days": (2, 7),
        "max_contact_attempts": (5, 12),
        "re_engagement_delay_days": (7, 21),
        "base_conversion_mult": (0.20, 0.40),
        "digital_native_bonus": (0.05, 0.20),
        "saved_payment_bonus": (0.15, 0.35),
        "contact_decay_rate": (0.08, 0.18),
        "full_payment_rate": (0.75, 0.92),
    }

    def __init__(self):
        self.risk_engine = RiskStrategyEngine()
        self.channel_optimizer = ChannelOptimizer()
        self.results: List[CalibrationResult] = []
        self.best_result: Optional[CalibrationResult] = None
        self.convergence_history: List[float] = []

    def calculate_fitness(self, result: CalibrationResult) -> float:
        """
        Calculate fitness score for a calibration result.

        Higher is better. Weighted combination of metrics.
        """
        # Weights for each metric
        weights = {
            "recovery": 0.30,
            "margin": 0.25,
            "efficiency": 0.20,
            "risk": 0.15,
            "speed": 0.10
        }

        # Normalize metrics against targets
        recovery_score = min(1.0, result.recovery_rate / self.TARGETS["recovery_rate"])
        margin_score = min(1.0, result.profit_margin / self.TARGETS["profit_margin"])
        efficiency_score = min(1.0, self.TARGETS["cost_per_dollar"] / max(0.01, result.cost_per_dollar))
        risk_score = 1.0 - result.risk_score  # Lower risk is better
        speed_score = min(1.0, self.TARGETS["days_to_collect"] / max(0.1, result.avg_days_to_collect))

        fitness = (
            weights["recovery"] * recovery_score +
            weights["margin"] * margin_score +
            weights["efficiency"] * efficiency_score +
            weights["risk"] * risk_score +
            weights["speed"] * speed_score
        )

        return fitness

    def mutate_parameters(
        self,
        params: CalibrationParameters,
        mutation_rate: float = 0.2
    ) -> CalibrationParameters:
        """Mutate parameters with small random changes"""
        new_params = copy.deepcopy(params)

        # Mutate numeric parameters
        if random.random() < mutation_rate:
            low, high = self.BOUNDS["contact_cadence_days"]
            new_params.contact_cadence_days = random.randint(low, high)

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["max_contact_attempts"]
            new_params.max_contact_attempts = random.randint(low, high)

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["re_engagement_delay_days"]
            new_params.re_engagement_delay_days = random.randint(low, high)

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["base_conversion_mult"]
            delta = (high - low) * random.uniform(-0.1, 0.1)
            new_params.base_conversion_mult = max(low, min(high,
                new_params.base_conversion_mult + delta
            ))

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["digital_native_bonus"]
            delta = (high - low) * random.uniform(-0.1, 0.1)
            new_params.digital_native_bonus = max(low, min(high,
                new_params.digital_native_bonus + delta
            ))

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["saved_payment_bonus"]
            delta = (high - low) * random.uniform(-0.1, 0.1)
            new_params.saved_payment_bonus = max(low, min(high,
                new_params.saved_payment_bonus + delta
            ))

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["contact_decay_rate"]
            delta = (high - low) * random.uniform(-0.1, 0.1)
            new_params.contact_decay_rate = max(low, min(high,
                new_params.contact_decay_rate + delta
            ))

        if random.random() < mutation_rate:
            low, high = self.BOUNDS["full_payment_rate"]
            delta = (high - low) * random.uniform(-0.1, 0.1)
            new_params.full_payment_rate = max(low, min(high,
                new_params.full_payment_rate + delta
            ))

        return new_params

    async def run_simulation_with_params(
        self,
        params: CalibrationParameters,
        num_accounts: int = 25000,
        simulation_days: int = 60
    ) -> CalibrationResult:
        """Run a simulation with specific parameters"""
        from quan.simulation.sub_1k_simulation import (
            SUB_1K_UNIVERSE, MicroDebtType, Sub1KAccount
        )

        # Generate accounts
        accounts = []
        total_balance = Decimal("0")
        market_totals = sum(p.accounts_millions for p in SUB_1K_UNIVERSE.values())

        account_num = 0
        for dt, profile in SUB_1K_UNIVERSE.items():
            type_count = int(num_accounts * (profile.accounts_millions / market_totals))

            for _ in range(type_count):
                raw = random.random() ** 0.6
                balance = (
                    profile.min_balance +
                    Decimal(str(raw)) * (profile.max_balance - profile.min_balance)
                ).quantize(Decimal("0.01"))

                age = max(18, min(75, int(random.gauss(profile.avg_age, 10))))
                has_mobile = random.random() < profile.mobile_rate
                is_digital = random.random() < profile.digital_native_rate

                willingness = profile.base_recovery_rate
                if is_digital:
                    willingness += 0.15
                willingness = max(0.1, min(0.85, willingness + random.gauss(0, 0.1)))

                account = {
                    "account_id": f"CAL-{account_num:06d}",
                    "debt_type": dt,
                    "balance": balance,
                    "original_balance": balance,
                    "age": age,
                    "has_mobile": has_mobile,
                    "is_digital_native": is_digital,
                    "payment_willingness": willingness,
                    "phone_valid": random.random() < 0.85,
                    "email_valid": random.random() < 0.72,
                    "status": "active",
                    "contact_attempts": 0,
                    "payments_made": 0,
                    "total_paid": Decimal("0"),
                    "last_contact_day": -999,
                    "has_saved_payment": False,
                    "re_engagement_attempts": 0
                }

                accounts.append(account)
                total_balance += balance
                account_num += 1

        # Run simulation
        total_collected = Decimal("0")
        total_contacts = 0
        digital_payments = 0
        total_payments = 0
        collection_days = []
        risk_scores = []

        for day in range(simulation_days):
            for account in accounts:
                if account["status"] == "collected":
                    continue

                days_since_contact = day - account["last_contact_day"]

                # Apply cadence
                if days_since_contact < params.contact_cadence_days:
                    continue

                # Risk assessment
                risk_profile = self.risk_engine.assess_risk(account)
                risk_scores.append(risk_profile.risk_score)

                # Check contact limits
                if account["contact_attempts"] >= params.max_contact_attempts:
                    # Re-engagement check
                    if (days_since_contact > params.re_engagement_delay_days and
                        account["re_engagement_attempts"] < params.max_re_engagements):
                        account["re_engagement_attempts"] += 1
                    else:
                        continue

                # Get strategy
                strategy = self.risk_engine.get_contact_strategy(
                    risk_profile, account["contact_attempts"]
                )

                if not strategy["should_contact"]:
                    continue

                # Calculate conversion probability
                profile = SUB_1K_UNIVERSE[account["debt_type"]]
                prob = profile.base_recovery_rate * params.base_conversion_mult

                willingness_mult = 0.5 + (account["payment_willingness"] * 0.5)
                prob *= willingness_mult

                if account["is_digital_native"]:
                    prob *= (1 + params.digital_native_bonus)
                if account["has_mobile"]:
                    prob *= (1 + params.mobile_bonus)
                if account["has_saved_payment"]:
                    prob *= (1 + params.saved_payment_bonus)

                # Contact decay
                if account["contact_attempts"] == 0:
                    prob *= (1 - params.first_contact_penalty)
                elif account["contact_attempts"] > 3:
                    excess = account["contact_attempts"] - 3
                    prob *= ((1 - params.contact_decay_rate) ** excess)

                # Re-engagement bonus
                if account["re_engagement_attempts"] > 0:
                    prob *= 1.12

                # Risk adjustments
                if risk_profile.risk_level == "critical":
                    prob *= 0.7
                elif risk_profile.risk_level == "high":
                    prob *= 0.85

                prob = min(0.50, prob)

                # Record contact
                total_contacts += 1
                account["contact_attempts"] += 1
                account["last_contact_day"] = day

                # Track channel
                self.channel_optimizer.record_attempt(strategy["channel"], False)

                # Check conversion
                if random.random() < prob:
                    balance = account["balance"]

                    # Settlement offer
                    if strategy["offer_settlement"] and random.random() < 0.4:
                        amount = (balance * Decimal(str(1 - params.re_engagement_discount_pct))).quantize(Decimal("0.01"))
                    elif random.random() < params.full_payment_rate:
                        amount = balance
                    else:
                        pct = random.uniform(params.partial_payment_min, params.partial_payment_max)
                        amount = (balance * Decimal(str(pct))).quantize(Decimal("0.01"))

                    # Digital payment?
                    digital_prob = profile.digital_payment_rate
                    if account["is_digital_native"]:
                        digital_prob += 0.15
                    is_digital = random.random() < min(0.95, digital_prob)

                    # Update account
                    account["balance"] -= amount
                    account["total_paid"] += amount
                    account["payments_made"] += 1

                    if is_digital and random.random() < params.save_payment_rate:
                        account["has_saved_payment"] = True

                    if account["balance"] <= 0:
                        account["status"] = "collected"
                    else:
                        account["status"] = "partial"

                    total_collected += amount
                    total_payments += 1
                    if is_digital:
                        digital_payments += 1
                    collection_days.append(day - account.get("first_contact_day", day))

                    # Update channel stats
                    self.channel_optimizer.record_attempt(strategy["channel"], True)

                    # Record first contact day
                    if "first_contact_day" not in account:
                        account["first_contact_day"] = day

        # Calculate metrics
        recovery_rate = float(total_collected / total_balance) if total_balance > 0 else 0

        # Cost calculation - FULL OPERATIONAL COSTS
        # Channel costs
        sms_contacts = int(total_contacts * params.sms_weight)
        email_contacts = int(total_contacts * params.email_weight)
        push_contacts = int(total_contacts * params.push_weight)

        channel_cost = (
            Decimal("0.02") * sms_contacts +
            Decimal("0.005") * email_contacts +
            Decimal("0.01") * push_contacts
        )

        # Payment processing cost (per transaction)
        payment_cost = Decimal("0.18") * total_payments

        # Agent labor cost: 500 agents at $120/day, prorated by accounts
        # For 25K accounts out of 100K capacity = 25% utilization
        num_agents = 500
        daily_labor = Decimal(str(num_agents * 120))
        labor_cost = daily_labor * simulation_days * Decimal("0.25")

        # Platform/infrastructure cost (3% of collections)
        platform_cost = total_collected * Decimal("0.03")

        # Compliance and overhead (1.5% of collections)
        overhead_cost = total_collected * Decimal("0.015")

        # Total cost
        cost = channel_cost + payment_cost + labor_cost + platform_cost + overhead_cost

        cost_per_dollar = float(cost / total_collected) if total_collected > 0 else float("inf")
        profit_margin = float((total_collected - cost) / total_collected) if total_collected > 0 else 0
        roi = float((total_collected - cost) / cost) if cost > 0 else 0

        digital_rate = digital_payments / total_payments if total_payments > 0 else 0
        avg_days = statistics.mean(collection_days) if collection_days else simulation_days
        avg_risk = statistics.mean(risk_scores) if risk_scores else 0.5

        # Efficiency score
        efficiency = (recovery_rate * profit_margin) / (cost_per_dollar + 0.01)

        result = CalibrationResult(
            iteration=len(self.results),
            parameters=params,
            recovery_rate=recovery_rate,
            profit_margin=profit_margin,
            cost_per_dollar=cost_per_dollar,
            roi=roi,
            digital_rate=digital_rate,
            avg_days_to_collect=avg_days,
            risk_score=avg_risk,
            efficiency_score=efficiency
        )

        result.fitness = self.calculate_fitness(result)
        return result

    async def calibrate(
        self,
        iterations: int = 10,
        accounts_per_run: int = 25000
    ) -> CalibrationResult:
        """Run calibration iterations to find optimal parameters"""
        print("\n" + "=" * 75)
        print("  QUAN MODEL CALIBRATION ENGINE")
        print("  Optimizing for Recovery, Efficiency, and Risk")
        print("=" * 75)

        # Start with default parameters
        current_params = CalibrationParameters()
        best_fitness = 0.0

        print(f"\n  Running {iterations} calibration iterations...")
        print(f"  Accounts per run: {accounts_per_run:,}")
        print(f"\n  Targets: Recovery {self.TARGETS['recovery_rate']*100:.0f}%, "
              f"Margin {self.TARGETS['profit_margin']*100:.0f}%, "
              f"Cost ${self.TARGETS['cost_per_dollar']:.2f}/dollar")

        print("\n  " + "-" * 71)
        print(f"  {'Iter':<6} {'Recovery':>10} {'Margin':>10} {'Cost/$':>10} {'ROI':>10} {'Fitness':>10}")
        print("  " + "-" * 71)

        for i in range(iterations):
            # Run simulation
            result = await self.run_simulation_with_params(
                current_params,
                num_accounts=accounts_per_run,
                simulation_days=60
            )

            self.results.append(result)
            self.convergence_history.append(result.fitness)

            # Print progress
            print(f"  {i+1:<6} {result.recovery_rate*100:>9.1f}% "
                  f"{result.profit_margin*100:>9.1f}% "
                  f"${result.cost_per_dollar:>9.3f} "
                  f"{result.roi*100:>9.0f}% "
                  f"{result.fitness:>10.4f}")

            # Update best
            if result.fitness > best_fitness:
                best_fitness = result.fitness
                self.best_result = result

            # Mutate parameters for next iteration
            # Higher mutation rate early, lower later
            mutation_rate = 0.4 * (1 - i / iterations) + 0.1
            current_params = self.mutate_parameters(current_params, mutation_rate)

            # Occasionally restart from best
            if i > 0 and i % 4 == 0 and self.best_result:
                current_params = self.mutate_parameters(
                    self.best_result.parameters,
                    mutation_rate * 0.5
                )

        print("  " + "-" * 71)

        # Print best result
        print(f"\n  BEST RESULT (Iteration {self.best_result.iteration + 1}):")
        print(f"    Recovery Rate:      {self.best_result.recovery_rate*100:.1f}%")
        print(f"    Profit Margin:      {self.best_result.profit_margin*100:.1f}%")
        print(f"    Cost per Dollar:    ${self.best_result.cost_per_dollar:.3f}")
        print(f"    ROI:                {self.best_result.roi*100:.0f}%")
        print(f"    Digital Rate:       {self.best_result.digital_rate*100:.1f}%")
        print(f"    Avg Days to Collect: {self.best_result.avg_days_to_collect:.1f}")
        print(f"    Fitness Score:      {self.best_result.fitness:.4f}")

        # Print optimal parameters
        bp = self.best_result.parameters
        print(f"\n  OPTIMAL PARAMETERS:")
        print(f"    Contact Cadence:    {bp.contact_cadence_days} days")
        print(f"    Max Contacts:       {bp.max_contact_attempts}")
        print(f"    Re-engage Delay:    {bp.re_engagement_delay_days} days")
        print(f"    Base Conversion:    {bp.base_conversion_mult:.2f}")
        print(f"    Digital Bonus:      {bp.digital_native_bonus:.2f}")
        print(f"    Saved Pay Bonus:    {bp.saved_payment_bonus:.2f}")
        print(f"    Decay Rate:         {bp.contact_decay_rate:.2f}")
        print(f"    Full Payment Rate:  {bp.full_payment_rate:.2f}")

        # Channel effectiveness
        print(f"\n  CHANNEL EFFECTIVENESS:")
        rates = self.channel_optimizer.get_conversion_rates()
        costs = self.channel_optimizer.get_cost_effectiveness()
        for ch in ["sms", "email", "push"]:
            print(f"    {ch.upper():<8} Conv: {rates.get(ch, 0)*100:>5.1f}%  "
                  f"Cost/Conv: ${costs.get(ch, 0):>.3f}")

        # Convergence analysis
        if len(self.convergence_history) > 3:
            recent = self.convergence_history[-3:]
            variance = statistics.variance(recent) if len(recent) > 1 else 0
            print(f"\n  CONVERGENCE:")
            print(f"    Recent Variance:    {variance:.6f}")
            print(f"    Status:             {'CONVERGED' if variance < 0.001 else 'IMPROVING'}")

        print("\n" + "=" * 75)

        return self.best_result


async def run_calibration():
    """Run the full calibration process"""
    engine = CalibrationEngine()
    result = await engine.calibrate(iterations=10, accounts_per_run=25000)
    return result


if __name__ == "__main__":
    asyncio.run(run_calibration())
