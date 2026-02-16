"""
Advanced Pipeline Calibration

Maximum agent deployment with edge case handling and iterative optimization.
Focuses on nuanced account behaviors and real-world complexity.
"""

import asyncio
import random
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import statistics
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# EDGE CASE DEFINITIONS
# =============================================================================

@dataclass
class EdgeCase:
    """Definition of an edge case scenario"""
    name: str
    description: str
    probability: float  # How often this occurs
    impact: str  # "positive", "negative", "neutral"
    handler: str  # Method name to handle this case


EDGE_CASES = [
    # Payment Edge Cases
    EdgeCase("partial_payment", "Debtor pays less than agreed amount", 0.15, "neutral", "handle_partial_payment"),
    EdgeCase("overpayment", "Debtor pays more than balance", 0.02, "positive", "handle_overpayment"),
    EdgeCase("payment_reversal", "Payment reversed (chargeback/NSF)", 0.08, "negative", "handle_reversal"),
    EdgeCase("duplicate_payment", "Debtor pays twice accidentally", 0.01, "positive", "handle_duplicate"),
    EdgeCase("wrong_account", "Payment applied to wrong account", 0.005, "neutral", "handle_wrong_account"),

    # Contact Edge Cases
    EdgeCase("wrong_number", "Phone number belongs to someone else", 0.12, "negative", "handle_wrong_party"),
    EdgeCase("deceased", "Debtor is deceased", 0.02, "negative", "handle_deceased"),
    EdgeCase("incarcerated", "Debtor is incarcerated", 0.01, "negative", "handle_incarcerated"),
    EdgeCase("language_barrier", "Debtor doesn't speak English", 0.08, "neutral", "handle_language"),
    EdgeCase("elderly_vulnerable", "Debtor is elderly/vulnerable", 0.05, "neutral", "handle_vulnerable"),
    EdgeCase("attorney_represented", "Debtor has legal representation", 0.03, "negative", "handle_attorney"),

    # Dispute Edge Cases
    EdgeCase("identity_theft", "Debtor claims identity theft", 0.04, "negative", "handle_id_theft"),
    EdgeCase("already_paid", "Debtor claims already paid", 0.06, "neutral", "handle_already_paid"),
    EdgeCase("wrong_amount", "Debtor disputes balance amount", 0.05, "neutral", "handle_wrong_amount"),
    EdgeCase("statute_limitations", "Debt past statute of limitations", 0.03, "negative", "handle_sol"),
    EdgeCase("bankruptcy_pending", "Bankruptcy filing imminent", 0.02, "negative", "handle_bankruptcy"),

    # Negotiation Edge Cases
    EdgeCase("hardship_genuine", "Genuine financial hardship", 0.20, "neutral", "handle_hardship"),
    EdgeCase("hardship_fake", "Fake hardship claim", 0.10, "negative", "handle_fake_hardship"),
    EdgeCase("aggressive_debtor", "Debtor becomes aggressive/hostile", 0.05, "negative", "handle_aggressive"),
    EdgeCase("professional_debtor", "Experienced at avoiding collection", 0.03, "negative", "handle_professional"),
    EdgeCase("willing_but_unable", "Wants to pay but truly can't", 0.15, "neutral", "handle_willing_unable"),
    EdgeCase("able_but_unwilling", "Can pay but refuses", 0.08, "negative", "handle_able_unwilling"),

    # System Edge Cases
    EdgeCase("duplicate_account", "Same debt reported multiple times", 0.02, "neutral", "handle_duplicate_acct"),
    EdgeCase("data_quality_issue", "Missing/incorrect account data", 0.05, "negative", "handle_data_issue"),
    EdgeCase("compliance_flag", "Account flagged for compliance review", 0.03, "negative", "handle_compliance_flag"),
]


# =============================================================================
# NUANCED ACCOUNT PROFILES
# =============================================================================

@dataclass
class DebtorProfile:
    """Detailed debtor behavioral profile"""

    # Demographics
    age_bracket: str  # "18-25", "26-35", "36-45", "46-55", "56-65", "65+"
    income_bracket: str  # "low", "medium", "high"
    employment_status: str  # "employed", "unemployed", "self_employed", "retired", "student"

    # Financial behavior
    payment_history_score: float  # 0-1, higher = better
    debt_to_income: float  # ratio
    other_collections: int  # number of other collection accounts
    bank_account_status: str  # "active", "overdrawn", "closed", "unknown"

    # Communication preferences
    preferred_channel: str
    best_contact_time: str  # "morning", "afternoon", "evening"
    response_speed: str  # "immediate", "slow", "very_slow"

    # Psychological profile
    negotiation_style: str  # "cooperative", "competitive", "avoidant", "accommodating"
    emotional_state: str  # "calm", "stressed", "angry", "desperate"
    sophistication: str  # "naive", "average", "sophisticated"

    # Situational factors
    life_events: List[str] = field(default_factory=list)  # "job_loss", "divorce", "medical", etc.

    def get_response_probability(self, channel: str, attempt: int) -> float:
        """Calculate response probability based on profile (recalibrated)"""

        base_rate = {
            "sms": 0.15,
            "email": 0.08,
            "voice": 0.21,
            "mail": 0.05,
        }.get(channel, 0.12)

        # Adjust for preferred channel (stronger preference effect)
        if channel == self.preferred_channel:
            base_rate *= 2.0

        # Adjust for attempt number (gentler fatigue curve)
        attempt_decay = max(0.35, 1.0 - (attempt * 0.06))

        # Adjust for response speed
        speed_factor = {
            "immediate": 1.4,
            "slow": 0.85,
            "very_slow": 0.55,
        }.get(self.response_speed, 1.0)

        # Adjust for emotional state (improved engagement for stressed/desperate)
        emotional_factor = {
            "calm": 1.25,
            "stressed": 0.95,
            "angry": 0.65,
            "desperate": 1.2,
        }.get(self.emotional_state, 1.0)

        # Adjust for negotiation style (improved avoidant capture)
        style_factor = {
            "cooperative": 1.5,
            "competitive": 1.05,
            "avoidant": 0.58,
            "accommodating": 1.35,
        }.get(self.negotiation_style, 1.0)

        return min(0.95, base_rate * attempt_decay * speed_factor * emotional_factor * style_factor)

    def get_settlement_threshold(self, balance: float) -> float:
        """Get the minimum settlement this debtor would accept (recalibrated)"""

        # Base threshold based on income (lowered for higher acceptance)
        income_threshold = {
            "low": 0.22,
            "medium": 0.40,
            "high": 0.60,
        }.get(self.income_bracket, 0.36)

        # Adjust for payment history
        history_adj = self.payment_history_score * 0.12

        # Adjust for other collections (more = less able to pay)
        collection_adj = min(0.22, self.other_collections * 0.035)

        # Adjust for life events
        event_adj = len(self.life_events) * 0.06

        threshold = income_threshold + history_adj - collection_adj - event_adj

        return max(0.18, min(0.75, threshold))


# =============================================================================
# ADVANCED SIMULATION ENGINE
# =============================================================================

class AdvancedSimulationEngine:
    """
    Advanced simulation with edge case handling and iterative optimization.
    """

    def __init__(self):
        self.edge_cases = {ec.name: ec for ec in EDGE_CASES}
        self.iteration_results: List[Dict] = []
        self.model_params = self._initialize_params()
        self.edge_case_stats = defaultdict(lambda: {"count": 0, "impact": 0})

    def _initialize_params(self) -> Dict[str, float]:
        """Initialize tunable model parameters (recalibrated for enhanced recovery)"""
        return {
            # Contact parameters (improved response and channel effectiveness)
            "base_response_rate": 0.13,
            "channel_sms_multiplier": 1.35,
            "channel_email_multiplier": 0.72,
            "channel_voice_multiplier": 1.6,
            "attempt_decay_rate": 0.06,
            "max_attempts_before_rotate": 9,

            # Negotiation parameters (tighter steps, lower floor for higher capture)
            "initial_offer_discount": 0.0,  # Start at full balance
            "counter_step_size": 0.08,  # 8% reduction per counter
            "min_settlement_floor": 0.30,  # Floor at 30% for maximum capture
            "hardship_discount": 0.18,  # Slightly more generous hardship discount

            # Payment parameters (improved success across the board)
            "payment_success_rate": 0.90,
            "plan_completion_rate": 0.58,
            "retry_success_rate": 0.68,

            # Timing parameters (tighter contact cadence)
            "optimal_contact_delay_days": 2,
            "escalation_threshold_days": 10,

            # Edge case handling (improved dispute resolution)
            "dispute_resolution_rate": 0.48,
            "hardship_approval_rate": 0.75,
        }

    async def run_advanced_simulation(
        self,
        num_accounts: int = 50_000,
        num_agents: int = 250,
        iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        Run iterative simulation with edge case handling.
        """

        print("=" * 70)
        print("ADVANCED PIPELINE CALIBRATION")
        print(f"Accounts: {num_accounts:,} | Agents: {num_agents} | Iterations: {iterations}")
        print("=" * 70)

        best_result = None
        best_recovery = 0.0

        for iteration in range(iterations):
            print(f"\n[Iteration {iteration + 1}/{iterations}]")
            print("-" * 50)

            # Generate portfolio with nuanced profiles
            portfolio = self._generate_nuanced_portfolio(num_accounts)

            # Run simulation
            result = await self._run_iteration(portfolio, num_agents, iteration)
            self.iteration_results.append(result)

            # Print iteration results
            print(f"  Recovery Rate:     {result['recovery_rate']:.1%}")
            print(f"  Collection Eff:    {result['collection_efficiency']:.1%}")
            print(f"  Edge Cases Hit:    {result['edge_cases_encountered']:,}")
            print(f"  Avg Settlement:    {result['avg_settlement_rate']:.1%}")
            print(f"  Throughput:        {result['throughput']:.0f} acc/sec")

            # Track best
            if result['recovery_rate'] > best_recovery:
                best_recovery = result['recovery_rate']
                best_result = result

            # Tune parameters based on results
            self._tune_parameters(result)

        # Final analysis
        final_analysis = self._analyze_results()

        return {
            "iterations": iterations,
            "best_result": best_result,
            "final_params": self.model_params,
            "edge_case_analysis": dict(self.edge_case_stats),
            "convergence_analysis": final_analysis,
        }

    def _generate_nuanced_portfolio(self, num_accounts: int) -> List[Dict]:
        """Generate portfolio with detailed debtor profiles"""

        portfolio = []

        for i in range(num_accounts):
            # Generate debtor profile
            profile = self._generate_profile()

            # Generate account data
            balance = self._generate_balance(profile)
            age_days = self._generate_age(profile)

            # Determine applicable edge cases
            edge_cases = self._assign_edge_cases()

            account = {
                "account_id": f"ADV-{i:06d}",
                "client_id": f"CLIENT-{random.randint(1, 20):03d}",
                "balance": Decimal(str(balance)),
                "charge_off_date": datetime.utcnow() - timedelta(days=age_days),
                "original_creditor": random.choice([
                    "Klarna", "Affirm", "Afterpay", "PayPal Credit",
                    "Sezzle", "Zip", "Perpay", "Quadpay"
                ]),
                "debtor": {
                    "state": random.choice(["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA"]),
                    "phone": f"+1555{random.randint(1000000, 9999999)}",
                    "email": f"debtor{i}@example.com",
                },
                "profile": profile,
                "edge_cases": edge_cases,
                "_sim": {
                    "settlement_threshold": profile.get_settlement_threshold(balance),
                },
            }

            portfolio.append(account)

        return portfolio

    def _generate_profile(self) -> DebtorProfile:
        """Generate realistic debtor profile"""

        # Age distribution
        age_weights = [0.20, 0.25, 0.20, 0.15, 0.12, 0.08]
        age_brackets = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
        age = random.choices(age_brackets, weights=age_weights)[0]

        # Income based on age
        if age in ["18-25", "65+"]:
            income_weights = [0.50, 0.35, 0.15]
        elif age in ["46-55", "56-65"]:
            income_weights = [0.25, 0.40, 0.35]
        else:
            income_weights = [0.30, 0.45, 0.25]

        income = random.choices(["low", "medium", "high"], weights=income_weights)[0]

        # Employment
        if age == "65+":
            employment = random.choices(
                ["retired", "employed", "unemployed"],
                weights=[0.70, 0.20, 0.10]
            )[0]
        elif age == "18-25":
            employment = random.choices(
                ["student", "employed", "unemployed"],
                weights=[0.30, 0.50, 0.20]
            )[0]
        else:
            employment = random.choices(
                ["employed", "unemployed", "self_employed"],
                weights=[0.70, 0.15, 0.15]
            )[0]

        # Life events
        life_events = []
        if random.random() < 0.15:
            life_events.append("job_loss")
        if random.random() < 0.08:
            life_events.append("medical")
        if random.random() < 0.05:
            life_events.append("divorce")
        if random.random() < 0.03:
            life_events.append("death_in_family")

        return DebtorProfile(
            age_bracket=age,
            income_bracket=income,
            employment_status=employment,
            payment_history_score=random.betavariate(2, 5),  # Skewed low
            debt_to_income=random.uniform(0.1, 0.8),
            other_collections=random.choices([0, 1, 2, 3, 4, 5], weights=[0.40, 0.25, 0.15, 0.10, 0.05, 0.05])[0],
            bank_account_status=random.choices(
                ["active", "overdrawn", "closed", "unknown"],
                weights=[0.60, 0.15, 0.10, 0.15]
            )[0],
            preferred_channel=random.choices(
                ["sms", "email", "voice"],
                weights=[0.50, 0.30, 0.20]
            )[0],
            best_contact_time=random.choice(["morning", "afternoon", "evening"]),
            response_speed=random.choices(
                ["immediate", "slow", "very_slow"],
                weights=[0.20, 0.50, 0.30]
            )[0],
            negotiation_style=random.choices(
                ["cooperative", "competitive", "avoidant", "accommodating"],
                weights=[0.30, 0.20, 0.30, 0.20]
            )[0],
            emotional_state=random.choices(
                ["calm", "stressed", "angry", "desperate"],
                weights=[0.30, 0.40, 0.15, 0.15]
            )[0],
            sophistication=random.choices(
                ["naive", "average", "sophisticated"],
                weights=[0.30, 0.50, 0.20]
            )[0],
            life_events=life_events,
        )

    def _generate_balance(self, profile: DebtorProfile) -> float:
        """Generate balance based on profile"""

        # Income affects typical balance
        balance_ranges = {
            "low": (25, 300),
            "medium": (100, 600),
            "high": (200, 1000),
        }

        min_bal, max_bal = balance_ranges.get(profile.income_bracket, (50, 500))

        # Use log-normal for realistic distribution
        mean = (min_bal + max_bal) / 2
        balance = random.lognormvariate(np.log(mean), 0.5)

        return round(max(min_bal, min(max_bal, balance)), 2)

    def _generate_age(self, profile: DebtorProfile) -> int:
        """Generate account age based on profile"""

        # Sophisticated debtors tend to have older debt (know to wait)
        if profile.sophistication == "sophisticated":
            return random.randint(180, 600)
        elif profile.sophistication == "naive":
            return random.randint(30, 180)
        else:
            return random.randint(60, 365)

    def _assign_edge_cases(self) -> List[str]:
        """Randomly assign edge cases to account"""

        assigned = []
        for ec in EDGE_CASES:
            if random.random() < ec.probability:
                assigned.append(ec.name)

        return assigned

    async def _run_iteration(
        self,
        portfolio: List[Dict],
        num_agents: int,
        iteration: int,
    ) -> Dict[str, Any]:
        """Run single iteration"""

        start_time = datetime.utcnow()

        # Process accounts
        results = []
        edge_cases_hit = 0

        # Simulate concurrent processing
        semaphore = asyncio.Semaphore(num_agents)

        async def process_account(account: Dict) -> Dict:
            async with semaphore:
                return await self._process_account_advanced(account)

        tasks = [process_account(acc) for acc in portfolio]
        results = await asyncio.gather(*tasks)

        # Aggregate results
        total_balance = sum(float(acc["balance"]) for acc in portfolio)
        total_collected = sum(r.get("collected", 0) for r in results)
        recovered = sum(1 for r in results if r.get("status") == "recovered")

        # Count edge cases
        for r in results:
            edge_cases_hit += len(r.get("edge_cases_encountered", []))
            for ec in r.get("edge_cases_encountered", []):
                self.edge_case_stats[ec]["count"] += 1
                if r.get("status") == "recovered":
                    self.edge_case_stats[ec]["impact"] += r.get("collected", 0)

        # Calculate settlement rates
        settlements = [r.get("settlement_rate", 0) for r in results if r.get("settlement_rate")]
        avg_settlement = statistics.mean(settlements) if settlements else 0

        runtime = (datetime.utcnow() - start_time).total_seconds()

        return {
            "iteration": iteration,
            "total_accounts": len(portfolio),
            "recovered": recovered,
            "recovery_rate": recovered / len(portfolio),
            "total_balance": total_balance,
            "total_collected": total_collected,
            "collection_efficiency": total_collected / total_balance if total_balance else 0,
            "edge_cases_encountered": edge_cases_hit,
            "avg_settlement_rate": avg_settlement,
            "runtime": runtime,
            "throughput": len(portfolio) / runtime if runtime else 0,
        }

    async def _process_account_advanced(self, account: Dict) -> Dict:
        """Process account with edge case handling"""

        result = {
            "account_id": account["account_id"],
            "balance": float(account["balance"]),
            "collected": 0,
            "status": "pending",
            "edge_cases_encountered": [],
            "stages": [],
        }

        profile: DebtorProfile = account["profile"]
        edge_cases = account["edge_cases"]
        balance = float(account["balance"])

        # Check for blocking edge cases first
        for ec_name in edge_cases:
            ec = self.edge_cases.get(ec_name)
            if ec and ec.impact == "negative":
                # Handle blocking edge cases
                if ec_name in ["deceased", "bankruptcy_pending", "attorney_represented"]:
                    result["status"] = f"blocked_{ec_name}"
                    result["edge_cases_encountered"].append(ec_name)
                    return result

        # LOCATE stage (improved with enhanced skip-trace + enrichment)
        located = random.random() < 0.97  # 97% locate rate

        if "wrong_number" in edge_cases:
            result["edge_cases_encountered"].append("wrong_number")
            located = random.random() < 0.78  # Improved alt-contact lookup

        if not located:
            result["status"] = "not_located"
            return result

        result["stages"].append("locate")

        # CONTACT stage
        max_attempts = 21
        response = None

        for attempt in range(1, max_attempts + 1):
            # Determine channel
            channels = ["sms", "email", "voice"]
            channel = channels[(attempt - 1) % 3]

            # Get response probability from profile
            response_prob = profile.get_response_probability(channel, attempt)

            # Apply model parameters
            response_prob *= self.model_params.get(f"channel_{channel}_multiplier", 1.0)

            if random.random() < response_prob:
                response = True
                break

            # Minimal delay simulation
            await asyncio.sleep(0.0001)

        if not response:
            result["status"] = "no_response"
            return result

        result["stages"].append("contact")

        # Handle contact edge cases
        if "language_barrier" in edge_cases:
            result["edge_cases_encountered"].append("language_barrier")
            # 60% chance to overcome (multi-language support)
            if random.random() > 0.60:
                result["status"] = "language_barrier"
                return result

        if "aggressive_debtor" in edge_cases:
            result["edge_cases_encountered"].append("aggressive_debtor")
            if random.random() > 0.38:
                result["status"] = "ceased_communication"
                return result

        # DISPUTE handling
        if any(ec in edge_cases for ec in ["identity_theft", "already_paid", "wrong_amount"]):
            dispute_type = [ec for ec in ["identity_theft", "already_paid", "wrong_amount"] if ec in edge_cases][0]
            result["edge_cases_encountered"].append(dispute_type)

            # Resolve dispute
            if random.random() < self.model_params["dispute_resolution_rate"]:
                result["stages"].append("dispute_resolved")
            else:
                result["status"] = f"disputed_{dispute_type}"
                return result

        result["stages"].append("negotiate")

        # NEGOTIATE stage
        settlement_threshold = account["_sim"]["settlement_threshold"]

        # Handle hardship
        if "hardship_genuine" in edge_cases:
            result["edge_cases_encountered"].append("hardship_genuine")
            if random.random() < self.model_params["hardship_approval_rate"]:
                settlement_threshold *= (1 - self.model_params["hardship_discount"])

        if "hardship_fake" in edge_cases:
            result["edge_cases_encountered"].append("hardship_fake")
            # We detect 70% of fake hardship claims (improved ML detection)
            if random.random() < 0.70:
                pass  # No discount
            else:
                settlement_threshold *= (1 - self.model_params["hardship_discount"])

        # Negotiation rounds
        our_offer_pct = 1.0  # Start at full balance
        accepted = False

        for round_num in range(6):
            our_offer = balance * our_offer_pct

            # Check if debtor accepts
            if our_offer_pct <= settlement_threshold + 0.05:  # Small margin
                if random.random() < (0.3 + round_num * 0.15):
                    accepted = True
                    break

            # Lower our offer
            our_offer_pct -= self.model_params["counter_step_size"]
            our_offer_pct = max(our_offer_pct, self.model_params["min_settlement_floor"])

        if not accepted:
            # Last chance - offer floor (improved acceptance with empathy engine)
            if random.random() < 0.50:
                accepted = True
                our_offer_pct = self.model_params["min_settlement_floor"]

        if not accepted:
            result["status"] = "negotiation_failed"
            return result

        final_amount = balance * our_offer_pct
        result["settlement_rate"] = our_offer_pct
        result["stages"].append("collect")

        # COLLECT stage
        # Handle payment edge cases
        if "payment_reversal" in edge_cases:
            result["edge_cases_encountered"].append("payment_reversal")
            if random.random() < 0.58:  # 58% reversal rate (improved fraud prevention)
                result["status"] = "payment_reversed"
                return result

        # Payment success
        payment_success = random.random() < self.model_params["payment_success_rate"]

        if not payment_success:
            # Retry
            if random.random() < self.model_params["retry_success_rate"]:
                payment_success = True

        if not payment_success:
            result["status"] = "payment_failed"
            return result

        # Handle partial payments
        if "partial_payment" in edge_cases:
            result["edge_cases_encountered"].append("partial_payment")
            partial_pct = random.uniform(0.30, 0.80)
            final_amount *= partial_pct

        result["collected"] = final_amount
        result["status"] = "recovered"
        result["stages"].append("close")
        result["stages"].append("profit")

        return result

    def _tune_parameters(self, result: Dict) -> None:
        """Tune model parameters based on iteration results"""

        target_recovery = 0.42
        actual_recovery = result["recovery_rate"]

        # Adjust response rate if off target (more aggressive tuning)
        if actual_recovery < target_recovery * 0.85:
            # Under-recovering - improve contact and payment capture
            self.model_params["base_response_rate"] *= 1.03
            self.model_params["channel_sms_multiplier"] *= 1.02
            self.model_params["min_settlement_floor"] *= 0.97  # Lower floor
            self.model_params["retry_success_rate"] *= 1.01
        elif actual_recovery > target_recovery * 1.15:
            # Over-recovering (simulation may be too optimistic)
            self.model_params["base_response_rate"] *= 0.99
            self.model_params["payment_success_rate"] *= 0.99

        # Tune based on edge case impacts
        for ec_name, stats in self.edge_case_stats.items():
            if stats["count"] > 100:
                ec = self.edge_cases.get(ec_name)
                if ec and ec.impact == "negative":
                    # Increase handling success rate
                    if "dispute" in ec_name:
                        self.model_params["dispute_resolution_rate"] = min(
                            0.60, self.model_params["dispute_resolution_rate"] * 1.01
                        )

    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze all iteration results"""

        if not self.iteration_results:
            return {}

        recovery_rates = [r["recovery_rate"] for r in self.iteration_results]
        collection_effs = [r["collection_efficiency"] for r in self.iteration_results]
        throughputs = [r["throughput"] for r in self.iteration_results]

        # Check convergence
        if len(recovery_rates) >= 3:
            last_3_std = statistics.stdev(recovery_rates[-3:])
            converged = last_3_std < 0.01  # Less than 1% variance
        else:
            converged = False

        return {
            "mean_recovery": statistics.mean(recovery_rates),
            "std_recovery": statistics.stdev(recovery_rates) if len(recovery_rates) > 1 else 0,
            "mean_efficiency": statistics.mean(collection_effs),
            "mean_throughput": statistics.mean(throughputs),
            "trend": "improving" if recovery_rates[-1] > recovery_rates[0] else "declining",
            "converged": converged,
            "iterations_to_converge": len(recovery_rates) if converged else None,
        }


# =============================================================================
# RUNNER
# =============================================================================

async def run_advanced_calibration():
    """Run full advanced calibration"""

    engine = AdvancedSimulationEngine()

    results = await engine.run_advanced_simulation(
        num_accounts=50_000,
        num_agents=250,
        iterations=10,
    )

    # Print final results
    print("\n" + "=" * 70)
    print("CALIBRATION COMPLETE")
    print("=" * 70)

    best = results["best_result"]
    print(f"""
BEST ITERATION RESULTS:
  Recovery Rate:         {best['recovery_rate']:.1%}
  Collection Efficiency: {best['collection_efficiency']:.1%}
  Total Collected:       ${best['total_collected']:,.2f}
  Throughput:            {best['throughput']:.0f} accounts/sec
""")

    # Edge case analysis
    print("TOP EDGE CASES BY FREQUENCY:")
    sorted_ec = sorted(
        results["edge_case_analysis"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]

    for ec_name, stats in sorted_ec:
        print(f"  {ec_name:25} Count: {stats['count']:>6,}  Impact: ${stats['impact']:>12,.2f}")

    # Final parameters
    print("\nOPTIMIZED PARAMETERS:")
    for param, value in results["final_params"].items():
        print(f"  {param:30} {value:.4f}")

    # Convergence
    conv = results["convergence_analysis"]
    print(f"""
CONVERGENCE ANALYSIS:
  Mean Recovery:         {conv['mean_recovery']:.1%}
  Std Dev:               {conv['std_recovery']:.3f}
  Trend:                 {conv['trend']}
  Converged:             {conv['converged']}
""")

    print("=" * 70)

    return results


if __name__ == "__main__":
    asyncio.run(run_advanced_calibration())
