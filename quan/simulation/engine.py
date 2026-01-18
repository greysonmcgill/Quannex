"""
QUAN Pipeline Simulation Engine

Deploys maximum agents to calibrate pipelines under real-world conditions.
Stress tests all stages and calibrates ML models for maximum efficacy.
"""

import asyncio
import random
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging
import json
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================

@dataclass
class SimulationConfig:
    """Configuration for pipeline simulation"""

    # Scale
    num_accounts: int = 10_000
    num_agents: int = 100  # Concurrent processing agents
    max_concurrent_contacts: int = 500

    # Portfolio distribution (real-world)
    balance_distribution: Dict[str, float] = field(default_factory=lambda: {
        "micro": 0.45,      # $0-100: 45%
        "small": 0.30,      # $100-300: 30%
        "medium": 0.18,     # $300-700: 18%
        "large": 0.07,      # $700-1000: 7%
    })

    # Debtor behavior probabilities
    response_rate: float = 0.25          # 25% respond to contact
    pay_full_rate: float = 0.08          # 8% pay in full
    negotiate_rate: float = 0.65         # 65% of responders negotiate
    accept_first_offer: float = 0.15     # 15% accept first settlement
    dispute_rate: float = 0.05           # 5% dispute

    # Payment behavior
    payment_success_rate: float = 0.92   # 92% of payments succeed
    plan_completion_rate: float = 0.70   # 70% complete payment plans

    # Contact efficacy by channel
    channel_response_rates: Dict[str, float] = field(default_factory=lambda: {
        "sms": 0.28,
        "email": 0.12,
        "voice": 0.35,
        "mail": 0.08,
    })

    # Time simulation
    simulation_days: int = 90
    time_acceleration: float = 1000.0  # 1000x speed

    # Calibration
    calibration_iterations: int = 5
    target_recovery_rate: float = 0.35


@dataclass
class AgentMetrics:
    """Metrics for a single agent"""
    agent_id: int
    accounts_processed: int = 0
    accounts_recovered: int = 0
    total_collected: Decimal = Decimal("0")
    total_balance: Decimal = Decimal("0")
    avg_processing_time_ms: float = 0.0
    stage_times: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    errors: int = 0


@dataclass
class SimulationResult:
    """Results from simulation run"""

    # Overall metrics
    total_accounts: int = 0
    accounts_recovered: int = 0
    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    # Stage metrics
    stage_conversion: Dict[str, float] = field(default_factory=dict)
    stage_avg_time: Dict[str, float] = field(default_factory=dict)

    # Channel metrics
    channel_efficacy: Dict[str, float] = field(default_factory=dict)

    # Negotiation metrics
    avg_settlement_rate: float = 0.0
    full_pay_rate: float = 0.0
    plan_success_rate: float = 0.0

    # Agent metrics
    agent_metrics: List[AgentMetrics] = field(default_factory=list)

    # Performance
    total_runtime_seconds: float = 0.0
    throughput_accounts_per_second: float = 0.0

    # Calibration
    model_adjustments: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SYNTHETIC DATA GENERATION
# =============================================================================

class SyntheticPortfolioGenerator:
    """Generates realistic synthetic portfolios for simulation"""

    def __init__(self, config: SimulationConfig):
        self.config = config

        # Balance ranges
        self.balance_ranges = {
            "micro": (10, 100),
            "small": (100, 300),
            "medium": (300, 700),
            "large": (700, 1000),
        }

        # State distribution (top states by debt)
        self.state_distribution = {
            "CA": 0.12, "TX": 0.10, "FL": 0.08, "NY": 0.07,
            "IL": 0.05, "PA": 0.05, "OH": 0.04, "GA": 0.04,
            "NC": 0.04, "MI": 0.03, "OTHER": 0.38,
        }

        # Age distribution (days since charge-off)
        self.age_ranges = [
            (30, 90, 0.20),    # Fresh: 20%
            (90, 180, 0.30),   # Recent: 30%
            (180, 365, 0.30),  # Aged: 30%
            (365, 730, 0.20),  # Old: 20%
        ]

    def generate_portfolio(self, num_accounts: int) -> List[Dict]:
        """Generate synthetic portfolio"""

        accounts = []

        for i in range(num_accounts):
            account = self._generate_account(i)
            accounts.append(account)

        return accounts

    def _generate_account(self, idx: int) -> Dict:
        """Generate single synthetic account"""

        # Determine balance tier
        tier = self._sample_distribution(self.config.balance_distribution)
        min_bal, max_bal = self.balance_ranges[tier]
        balance = round(random.uniform(min_bal, max_bal), 2)

        # Determine state
        state = self._sample_distribution(self.state_distribution)
        if state == "OTHER":
            state = random.choice(["AZ", "CO", "WA", "MA", "VA", "NJ", "TN"])

        # Determine age
        age_days = self._sample_age()
        charge_off_date = datetime.utcnow() - timedelta(days=age_days)

        # Contact info availability
        has_phone = random.random() < 0.85
        has_email = random.random() < 0.60
        has_address = random.random() < 0.95

        # Debtor characteristics (affects behavior)
        employed = random.random() < 0.65
        has_bank = random.random() < 0.70
        previous_payments = random.random() < 0.15

        return {
            "account_id": f"SIM-{idx:06d}",
            "client_id": f"CLIENT-{random.randint(1, 10):03d}",
            "original_creditor": random.choice([
                "Klarna", "Affirm", "Afterpay", "Sezzle",
                "PayPal Credit", "Zip", "Perpay"
            ]),
            "balance": Decimal(str(balance)),
            "charge_off_date": charge_off_date,
            "debtor": {
                "name": f"Debtor {idx}",
                "phone": f"+1555{random.randint(1000000, 9999999)}" if has_phone else None,
                "email": f"debtor{idx}@example.com" if has_email else None,
                "address": f"{random.randint(100, 9999)} Main St" if has_address else None,
                "state": state,
                "employed": employed,
                "has_bank": has_bank,
                "previous_payments": previous_payments,
            },
            # Simulation behavior flags
            "_sim": {
                "will_respond": random.random() < self.config.response_rate,
                "will_pay_full": random.random() < self.config.pay_full_rate,
                "will_negotiate": random.random() < self.config.negotiate_rate,
                "will_dispute": random.random() < self.config.dispute_rate,
                "payment_success": random.random() < self.config.payment_success_rate,
                "will_complete_plan": random.random() < self.config.plan_completion_rate,
                "preferred_channel": random.choice(["sms", "email", "voice"]),
                "response_delay_hours": random.randint(1, 72),
                "max_settlement_pct": random.uniform(0.30, 0.80),
            },
        }

    def _sample_distribution(self, dist: Dict[str, float]) -> str:
        """Sample from probability distribution"""
        r = random.random()
        cumulative = 0.0
        for key, prob in dist.items():
            cumulative += prob
            if r <= cumulative:
                return key
        return list(dist.keys())[-1]

    def _sample_age(self) -> int:
        """Sample account age in days"""
        r = random.random()
        cumulative = 0.0
        for min_days, max_days, prob in self.age_ranges:
            cumulative += prob
            if r <= cumulative:
                return random.randint(min_days, max_days)
        return random.randint(30, 365)


# =============================================================================
# SIMULATED PIPELINE COMPONENTS
# =============================================================================

class SimulatedDebtorBehavior:
    """Simulates realistic debtor responses"""

    def __init__(self, config: SimulationConfig):
        self.config = config

    async def simulate_contact_response(
        self,
        account: Dict,
        channel: str,
        attempt: int,
    ) -> Dict:
        """Simulate debtor response to contact"""

        sim = account.get("_sim", {})

        # Base response rate from config
        base_rate = self.config.channel_response_rates.get(channel, 0.15)

        # Adjust for attempt number (decreasing returns)
        attempt_factor = max(0.3, 1.0 - (attempt * 0.1))

        # Adjust for preferred channel
        if channel == sim.get("preferred_channel"):
            channel_factor = 1.5
        else:
            channel_factor = 0.8

        # Calculate final response probability
        response_prob = base_rate * attempt_factor * channel_factor

        responded = random.random() < response_prob

        if not responded:
            return {"response_received": False}

        # Determine response type
        if sim.get("will_dispute"):
            intent = "dispute"
        elif sim.get("will_pay_full") and attempt <= 2:
            intent = "pay"
        elif sim.get("will_negotiate"):
            intent = "negotiate"
        else:
            intent = "pay" if random.random() < 0.3 else "negotiate"

        return {
            "response_received": True,
            "intent": intent,
            "response": self._generate_response_text(intent),
        }

    async def simulate_negotiation(
        self,
        account: Dict,
        our_offer: Decimal,
        offer_number: int,
    ) -> Dict:
        """Simulate debtor negotiation response"""

        sim = account.get("_sim", {})
        balance = account["balance"]

        our_offer_pct = float(our_offer / balance)
        debtor_max_pct = sim.get("max_settlement_pct", 0.50)

        # First offer - rarely accepted
        if offer_number == 1:
            if random.random() < self.config.accept_first_offer:
                return {"accepted": True}

            # Counter offer (low)
            counter_pct = random.uniform(0.20, 0.35)
            return {
                "accepted": False,
                "counter_offer": float(balance) * counter_pct,
            }

        # Subsequent offers - more likely to accept
        accept_prob = 0.1 + (offer_number * 0.15)

        # Higher accept probability if our offer is at/below their max
        if our_offer_pct <= debtor_max_pct:
            accept_prob += 0.3

        if random.random() < accept_prob:
            return {"accepted": True}

        # Counter (gradually increasing)
        counter_pct = min(
            debtor_max_pct,
            0.25 + (offer_number * 0.08) + random.uniform(-0.05, 0.05)
        )

        return {
            "accepted": False,
            "counter_offer": float(balance) * counter_pct,
        }

    async def simulate_payment(
        self,
        account: Dict,
        amount: Decimal,
    ) -> Dict:
        """Simulate payment attempt"""

        sim = account.get("_sim", {})

        success = sim.get("payment_success", True)

        if success:
            return {
                "success": True,
                "transaction_id": f"TXN-{random.randint(100000, 999999)}",
            }
        else:
            return {
                "success": False,
                "error": random.choice([
                    "Card declined",
                    "Insufficient funds",
                    "Invalid payment method",
                ]),
            }

    async def simulate_plan_payment(
        self,
        account: Dict,
        payment_number: int,
    ) -> Dict:
        """Simulate scheduled plan payment"""

        sim = account.get("_sim", {})

        # First payment usually succeeds
        if payment_number == 1:
            success = random.random() < 0.95
        else:
            # Subsequent payments based on completion rate
            completion_rate = sim.get("will_complete_plan", 0.70)
            success = random.random() < completion_rate

        return {
            "success": success,
            "payment_number": payment_number,
        }

    def _generate_response_text(self, intent: str) -> str:
        """Generate realistic response text"""

        responses = {
            "pay": [
                "I can pay this now",
                "What payment methods do you accept?",
                "I'll pay today",
            ],
            "negotiate": [
                "Can you offer a lower amount?",
                "I can only afford to pay part of this",
                "What's the best settlement you can offer?",
            ],
            "dispute": [
                "This is not my debt",
                "I already paid this",
                "I need validation of this debt",
            ],
        }

        return random.choice(responses.get(intent, ["Hello"]))


# =============================================================================
# SIMULATION AGENTS
# =============================================================================

class SimulationAgent:
    """Agent that processes accounts through simulated pipeline"""

    def __init__(
        self,
        agent_id: int,
        config: SimulationConfig,
        behavior: SimulatedDebtorBehavior,
    ):
        self.agent_id = agent_id
        self.config = config
        self.behavior = behavior
        self.metrics = AgentMetrics(agent_id=agent_id)

    async def process_account(self, account: Dict) -> Dict:
        """Process single account through full pipeline"""

        start_time = datetime.utcnow()

        result = {
            "account_id": account["account_id"],
            "balance": account["balance"],
            "collected": Decimal("0"),
            "status": "pending",
            "stages_completed": [],
            "contact_attempts": 0,
            "negotiation_rounds": 0,
        }

        try:
            # ACQUIRE
            stage_start = datetime.utcnow()
            score = await self._stage_acquire(account)
            result["score"] = score
            result["stages_completed"].append("acquire")
            self._record_stage_time("acquire", stage_start)

            # LOCATE
            stage_start = datetime.utcnow()
            located = await self._stage_locate(account)
            if not located:
                result["status"] = "no_contact"
                return result
            result["stages_completed"].append("locate")
            self._record_stage_time("locate", stage_start)

            # CONTACT loop
            max_contact_attempts = 21
            response = None

            for attempt in range(1, max_contact_attempts + 1):
                stage_start = datetime.utcnow()
                response = await self._stage_contact(account, attempt)
                result["contact_attempts"] = attempt
                self._record_stage_time("contact", stage_start)

                if response.get("response_received"):
                    break

                # Simulate time passing (accelerated)
                await asyncio.sleep(0.001)  # Minimal actual delay

            if not response or not response.get("response_received"):
                result["status"] = "no_response"
                result["stages_completed"].append("contact_exhausted")
                return result

            result["stages_completed"].append("contact")
            intent = response.get("intent", "negotiate")

            # Handle dispute
            if intent == "dispute":
                result["status"] = "disputed"
                return result

            # NEGOTIATE (if needed)
            if intent == "negotiate":
                stage_start = datetime.utcnow()
                negotiation = await self._stage_negotiate(account)
                result["negotiation_rounds"] = negotiation.get("rounds", 0)
                result["settlement_amount"] = negotiation.get("amount")
                result["stages_completed"].append("negotiate")
                self._record_stage_time("negotiate", stage_start)

                if not negotiation.get("success"):
                    result["status"] = "negotiation_failed"
                    return result

                payment_amount = Decimal(str(negotiation.get("amount", 0)))
            else:
                # Full payment
                payment_amount = account["balance"]

            # COLLECT
            stage_start = datetime.utcnow()
            payment = await self._stage_collect(account, payment_amount)
            result["stages_completed"].append("collect")
            self._record_stage_time("collect", stage_start)

            if not payment.get("success"):
                result["status"] = "payment_failed"
                return result

            result["collected"] = payment_amount

            # CLOSE
            stage_start = datetime.utcnow()
            result["stages_completed"].append("close")
            self._record_stage_time("close", stage_start)

            # PROFIT
            stage_start = datetime.utcnow()
            commission = payment_amount * Decimal("0.30")
            result["commission"] = commission
            result["stages_completed"].append("profit")
            result["status"] = "recovered"
            self._record_stage_time("profit", stage_start)

            # Update agent metrics
            self.metrics.accounts_recovered += 1
            self.metrics.total_collected += payment_amount

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self.metrics.errors += 1

        finally:
            self.metrics.accounts_processed += 1
            self.metrics.total_balance += account["balance"]

            # Record processing time
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.metrics.avg_processing_time_ms = (
                (self.metrics.avg_processing_time_ms * (self.metrics.accounts_processed - 1) + elapsed)
                / self.metrics.accounts_processed
            )

        return result

    async def _stage_acquire(self, account: Dict) -> float:
        """Simulate ACQUIRE stage - scoring"""

        balance = float(account["balance"])
        age_days = (datetime.utcnow() - account["charge_off_date"]).days
        has_phone = account["debtor"].get("phone") is not None
        has_email = account["debtor"].get("email") is not None
        employed = account["debtor"].get("employed", False)

        # Simple scoring model
        score = 0.5
        score += 0.1 if balance < 300 else -0.05
        score += 0.1 if age_days < 180 else -0.1
        score += 0.15 if has_phone else -0.1
        score += 0.05 if has_email else 0
        score += 0.1 if employed else -0.05

        # Add noise
        score += random.uniform(-0.1, 0.1)

        return max(0.1, min(0.9, score))

    async def _stage_locate(self, account: Dict) -> bool:
        """Simulate LOCATE stage"""

        has_phone = account["debtor"].get("phone") is not None
        has_email = account["debtor"].get("email") is not None

        # Simulate skip trace if needed
        if not has_phone and not has_email:
            # 60% chance skip trace finds something
            return random.random() < 0.60

        return True

    async def _stage_contact(self, account: Dict, attempt: int) -> Dict:
        """Simulate CONTACT stage"""

        # Determine channel based on attempt
        channels = ["sms", "email", "voice"]
        channel = channels[(attempt - 1) % len(channels)]

        return await self.behavior.simulate_contact_response(
            account, channel, attempt
        )

    async def _stage_negotiate(self, account: Dict) -> Dict:
        """Simulate NEGOTIATE stage"""

        balance = account["balance"]

        # Offer sequence: 100%, 80%, 70%, 60%, 50%, 45%
        offer_pcts = [1.0, 0.80, 0.70, 0.60, 0.50, 0.45]

        for i, pct in enumerate(offer_pcts, 1):
            our_offer = balance * Decimal(str(pct))

            result = await self.behavior.simulate_negotiation(
                account, our_offer, i
            )

            if result.get("accepted"):
                return {
                    "success": True,
                    "amount": float(our_offer),
                    "rounds": i,
                }

            # Check if their counter meets our floor
            counter = result.get("counter_offer")
            if counter and Decimal(str(counter)) >= balance * Decimal("0.40"):
                return {
                    "success": True,
                    "amount": counter,
                    "rounds": i,
                }

        return {"success": False, "rounds": len(offer_pcts)}

    async def _stage_collect(self, account: Dict, amount: Decimal) -> Dict:
        """Simulate COLLECT stage"""

        # Try up to 3 times
        for attempt in range(3):
            result = await self.behavior.simulate_payment(account, amount)
            if result.get("success"):
                return result

        return {"success": False}

    def _record_stage_time(self, stage: str, start: datetime) -> None:
        """Record stage processing time"""
        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        self.metrics.stage_times[stage].append(elapsed)


# =============================================================================
# MAIN SIMULATION ENGINE
# =============================================================================

class SimulationEngine:
    """
    Main simulation engine for QUAN pipeline calibration.

    Deploys maximum agents to stress-test and calibrate the system.
    """

    def __init__(self, config: SimulationConfig = None):
        self.config = config or SimulationConfig()
        self.generator = SyntheticPortfolioGenerator(self.config)
        self.behavior = SimulatedDebtorBehavior(self.config)
        self.results: List[SimulationResult] = []

    async def run_simulation(
        self,
        num_accounts: int = None,
        num_agents: int = None,
    ) -> SimulationResult:
        """
        Run full simulation with maximum agent deployment.
        """

        num_accounts = num_accounts or self.config.num_accounts
        num_agents = num_agents or self.config.num_agents

        logger.info(
            f"Starting simulation: {num_accounts} accounts, {num_agents} agents"
        )

        start_time = datetime.utcnow()

        # Generate portfolio
        logger.info("Generating synthetic portfolio...")
        portfolio = self.generator.generate_portfolio(num_accounts)

        # Create agents
        agents = [
            SimulationAgent(i, self.config, self.behavior)
            for i in range(num_agents)
        ]

        # Distribute accounts across agents
        account_queues = [[] for _ in range(num_agents)]
        for i, account in enumerate(portfolio):
            account_queues[i % num_agents].append(account)

        # Run agents concurrently
        logger.info(f"Deploying {num_agents} agents...")

        async def run_agent(agent: SimulationAgent, accounts: List[Dict]):
            results = []
            for account in accounts:
                result = await agent.process_account(account)
                results.append(result)
            return results

        tasks = [
            run_agent(agent, account_queues[i])
            for i, agent in enumerate(agents)
        ]

        all_results = await asyncio.gather(*tasks)

        # Flatten results
        account_results = []
        for agent_results in all_results:
            account_results.extend(agent_results)

        # Calculate metrics
        total_runtime = (datetime.utcnow() - start_time).total_seconds()

        result = self._compile_results(
            portfolio,
            account_results,
            agents,
            total_runtime,
        )

        self.results.append(result)

        logger.info(
            f"Simulation complete: {result.recovery_rate:.1%} recovery rate, "
            f"${result.total_collected:.2f} collected"
        )

        return result

    async def run_calibration(
        self,
        iterations: int = None,
    ) -> Dict[str, Any]:
        """
        Run multiple simulations to calibrate model parameters.
        """

        iterations = iterations or self.config.calibration_iterations

        logger.info(f"Starting calibration: {iterations} iterations")

        calibration_results = []

        for i in range(iterations):
            logger.info(f"Calibration iteration {i + 1}/{iterations}")

            # Run simulation
            result = await self.run_simulation()
            calibration_results.append(result)

            # Adjust parameters based on results
            self._adjust_parameters(result)

        # Compile calibration summary
        summary = self._compile_calibration_summary(calibration_results)

        return summary

    async def run_stress_test(
        self,
        max_accounts: int = 100_000,
        max_agents: int = 500,
    ) -> Dict[str, Any]:
        """
        Stress test to find system limits.
        """

        logger.info("Starting stress test...")

        stress_results = []

        # Test increasing scale
        scales = [
            (1000, 10),
            (5000, 50),
            (10000, 100),
            (25000, 200),
            (50000, 300),
            (100000, 500),
        ]

        for num_accounts, num_agents in scales:
            if num_accounts > max_accounts or num_agents > max_agents:
                break

            logger.info(f"Stress test: {num_accounts} accounts, {num_agents} agents")

            result = await self.run_simulation(num_accounts, num_agents)

            stress_results.append({
                "accounts": num_accounts,
                "agents": num_agents,
                "throughput": result.throughput_accounts_per_second,
                "recovery_rate": result.recovery_rate,
                "runtime": result.total_runtime_seconds,
            })

        return {
            "stress_results": stress_results,
            "max_throughput": max(r["throughput"] for r in stress_results),
            "optimal_config": max(stress_results, key=lambda x: x["throughput"]),
        }

    def _compile_results(
        self,
        portfolio: List[Dict],
        account_results: List[Dict],
        agents: List[SimulationAgent],
        runtime: float,
    ) -> SimulationResult:
        """Compile simulation results"""

        result = SimulationResult()

        # Overall metrics
        result.total_accounts = len(portfolio)
        result.total_balance = sum(a["balance"] for a in portfolio)

        recovered = [r for r in account_results if r["status"] == "recovered"]
        result.accounts_recovered = len(recovered)
        result.total_collected = sum(r.get("collected", Decimal("0")) for r in recovered)
        result.recovery_rate = result.accounts_recovered / result.total_accounts if result.total_accounts else 0

        # Stage conversion rates
        stage_counts = defaultdict(int)
        for r in account_results:
            for stage in r.get("stages_completed", []):
                stage_counts[stage] += 1

        result.stage_conversion = {
            stage: count / result.total_accounts
            for stage, count in stage_counts.items()
        }

        # Stage timing
        all_stage_times = defaultdict(list)
        for agent in agents:
            for stage, times in agent.metrics.stage_times.items():
                all_stage_times[stage].extend(times)

        result.stage_avg_time = {
            stage: statistics.mean(times) if times else 0
            for stage, times in all_stage_times.items()
        }

        # Negotiation metrics
        negotiated = [r for r in recovered if r.get("negotiation_rounds", 0) > 0]
        if negotiated:
            settlements = [r.get("settlement_amount", 0) for r in negotiated]
            balances = [float(r["balance"]) for r in negotiated]
            result.avg_settlement_rate = statistics.mean(
                s / b for s, b in zip(settlements, balances) if b > 0
            )

        full_pay = [r for r in recovered if r.get("negotiation_rounds", 0) == 0]
        result.full_pay_rate = len(full_pay) / len(recovered) if recovered else 0

        # Agent metrics
        result.agent_metrics = [agent.metrics for agent in agents]

        # Performance
        result.total_runtime_seconds = runtime
        result.throughput_accounts_per_second = result.total_accounts / runtime if runtime else 0

        return result

    def _adjust_parameters(self, result: SimulationResult) -> None:
        """Adjust simulation parameters based on results"""

        target = self.config.target_recovery_rate
        actual = result.recovery_rate

        # Adjust response rate if recovery is off target
        if actual < target * 0.9:
            # Under-performing - increase response rate slightly
            self.config.response_rate = min(0.40, self.config.response_rate * 1.05)
        elif actual > target * 1.1:
            # Over-performing - decrease response rate
            self.config.response_rate = max(0.15, self.config.response_rate * 0.95)

    def _compile_calibration_summary(
        self,
        results: List[SimulationResult],
    ) -> Dict[str, Any]:
        """Compile calibration summary"""

        recovery_rates = [r.recovery_rate for r in results]
        throughputs = [r.throughput_accounts_per_second for r in results]

        return {
            "iterations": len(results),
            "final_recovery_rate": recovery_rates[-1],
            "avg_recovery_rate": statistics.mean(recovery_rates),
            "recovery_rate_std": statistics.stdev(recovery_rates) if len(recovery_rates) > 1 else 0,
            "avg_throughput": statistics.mean(throughputs),
            "calibrated_config": {
                "response_rate": self.config.response_rate,
                "channel_response_rates": self.config.channel_response_rates,
            },
            "convergence": abs(recovery_rates[-1] - self.config.target_recovery_rate) < 0.02,
        }


# =============================================================================
# CLI RUNNER
# =============================================================================

async def run_full_calibration():
    """Run complete calibration workflow"""

    print("=" * 70)
    print("QUAN PIPELINE SIMULATION & CALIBRATION")
    print("=" * 70)

    config = SimulationConfig(
        num_accounts=10_000,
        num_agents=100,
        calibration_iterations=5,
        target_recovery_rate=0.35,
    )

    engine = SimulationEngine(config)

    # Run calibration
    print("\n[1/3] Running calibration...")
    calibration = await engine.run_calibration()

    print(f"\nCalibration Results:")
    print(f"  Final Recovery Rate: {calibration['final_recovery_rate']:.1%}")
    print(f"  Avg Recovery Rate: {calibration['avg_recovery_rate']:.1%}")
    print(f"  Std Dev: {calibration['recovery_rate_std']:.3f}")
    print(f"  Converged: {calibration['convergence']}")

    # Run stress test
    print("\n[2/3] Running stress test...")
    stress = await engine.run_stress_test(max_accounts=50_000, max_agents=200)

    print(f"\nStress Test Results:")
    print(f"  Max Throughput: {stress['max_throughput']:.1f} accounts/sec")
    print(f"  Optimal Config: {stress['optimal_config']}")

    # Final validation run
    print("\n[3/3] Running validation...")
    validation = await engine.run_simulation(
        num_accounts=25_000,
        num_agents=100,
    )

    print(f"\nValidation Results:")
    print(f"  Accounts: {validation.total_accounts:,}")
    print(f"  Recovered: {validation.accounts_recovered:,}")
    print(f"  Recovery Rate: {validation.recovery_rate:.1%}")
    print(f"  Total Collected: ${validation.total_collected:,.2f}")
    print(f"  Throughput: {validation.throughput_accounts_per_second:.1f} accounts/sec")

    print("\n" + "=" * 70)
    print("STAGE METRICS")
    print("=" * 70)

    for stage, rate in sorted(validation.stage_conversion.items()):
        time_ms = validation.stage_avg_time.get(stage, 0)
        print(f"  {stage.upper():15} | Conversion: {rate:6.1%} | Avg Time: {time_ms:6.1f}ms")

    print("\n" + "=" * 70)
    print("CALIBRATION COMPLETE")
    print("=" * 70)

    return {
        "calibration": calibration,
        "stress": stress,
        "validation": validation,
    }


if __name__ == "__main__":
    asyncio.run(run_full_calibration())
