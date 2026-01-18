"""
Perpetual Collection Simulation

Integrates frictionless payments, perpetual monitoring, and
automated re-engagement for maximum collection efficiency.
"""

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class SimulationMode(Enum):
    """Simulation operational modes"""
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    ADAPTIVE = "adaptive"


@dataclass
class SimulatedAccount:
    """A simulated debtor account with behavioral attributes"""
    account_id: str
    balance: Decimal
    original_balance: Decimal

    # Debtor characteristics
    age: int
    income_bracket: str  # "low", "medium", "high"
    employment_status: str  # "employed", "unemployed", "self_employed", "retired"
    payment_willingness: float  # 0.0 - 1.0
    tech_savvy: float  # 0.0 - 1.0 (affects digital payment adoption)
    responsiveness: float  # 0.0 - 1.0

    # Contact info quality
    phone_valid: bool = True
    email_valid: bool = True
    address_valid: bool = True

    # State tracking
    status: str = "active"
    payments_made: int = 0
    total_paid: Decimal = Decimal("0")
    last_contact: Optional[datetime] = None
    last_payment: Optional[datetime] = None
    preferred_channel: Optional[str] = None
    preferred_payment_method: Optional[str] = None

    # Friction factors
    has_saved_payment: bool = False
    mobile_device: bool = True
    friction_tolerance: float = 0.5  # Higher = more tolerant of friction

    # Behavioral state
    engagement_fatigue: float = 0.0
    trust_level: float = 0.5
    urgency_perception: float = 0.5


@dataclass
class SimulationAgent:
    """A simulation agent handling accounts"""
    agent_id: str
    accounts_assigned: int = 0
    accounts_collected: int = 0
    total_collected: Decimal = Decimal("0")
    contacts_made: int = 0
    payments_processed: int = 0
    retries_executed: int = 0
    re_engagements_sent: int = 0

    # Performance metrics
    collection_rate: float = 0.0
    avg_time_to_collect: float = 0.0
    friction_score_avg: float = 0.0


@dataclass
class SimulationConfig:
    """Configuration for simulation run"""
    num_agents: int = 250
    num_accounts: int = 50000
    simulation_days: int = 90
    mode: SimulationMode = SimulationMode.ADAPTIVE

    # Portfolio distribution
    balance_distribution: Tuple[float, float, float] = (50, 500, 0.3)  # min, max, skew

    # Debtor characteristics
    avg_payment_willingness: float = 0.35
    avg_tech_savvy: float = 0.6
    avg_responsiveness: float = 0.3

    # System parameters
    max_contact_attempts: int = 8
    max_payment_retries: int = 3
    re_engagement_threshold_days: int = 14

    # Friction parameters
    base_conversion_rate: float = 0.35
    friction_impact: float = 0.3
    trust_boost_per_interaction: float = 0.02

    # Economic parameters
    cost_per_contact: Decimal = Decimal("0.15")
    cost_per_payment_attempt: Decimal = Decimal("0.25")
    cost_per_re_engagement: Decimal = Decimal("0.50")


@dataclass
class SimulationMetrics:
    """Metrics from simulation run"""
    total_accounts: int = 0
    accounts_collected: int = 0
    accounts_partial: int = 0
    accounts_defaulted: int = 0

    total_balance: Decimal = Decimal("0")
    total_collected: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")

    total_contacts: int = 0
    total_payments: int = 0
    total_retries: int = 0
    total_re_engagements: int = 0

    # Derived metrics
    recovery_rate: float = 0.0
    collection_efficiency: float = 0.0
    cost_per_dollar_collected: float = 0.0
    profit_margin: float = 0.0
    roi: float = 0.0

    # Friction metrics
    avg_friction_score: float = 0.0
    conversion_by_method: Dict[str, float] = field(default_factory=dict)
    time_to_first_payment_days: float = 0.0

    # Re-engagement metrics
    re_engagement_conversion_rate: float = 0.0
    settlement_acceptance_rate: float = 0.0


class PerpetualCollectionSimulator:
    """
    Main simulation engine that models perpetual collection flow:
    1. Account assignment to agents
    2. Initial contact and payment attempt
    3. Frictionless payment processing
    4. Automated retry on failure
    5. Re-engagement campaigns
    6. Payment plan monitoring
    7. Continuous loop until resolution
    """

    # Payment method friction scores (lower = better)
    PAYMENT_FRICTION = {
        "apple_pay": 0.1,
        "google_pay": 0.12,
        "saved_card": 0.15,
        "one_click_ach": 0.18,
        "new_card": 0.45,
        "ach": 0.50,
        "payment_link": 0.60,
        "phone_payment": 0.75,
    }

    # Method conversion rates
    METHOD_CONVERSION = {
        "apple_pay": 0.82,
        "google_pay": 0.80,
        "saved_card": 0.75,
        "one_click_ach": 0.70,
        "new_card": 0.42,
        "ach": 0.38,
        "payment_link": 0.32,
        "phone_payment": 0.25,
    }

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.accounts: Dict[str, SimulatedAccount] = {}
        self.agents: Dict[str, SimulationAgent] = {}
        self.metrics = SimulationMetrics()

        # Time simulation
        self.current_day = 0
        self.simulation_start = datetime.now()

        # Event tracking
        self.payment_events: List[Dict] = []
        self.contact_events: List[Dict] = []

        # Running totals for convergence check
        self.daily_collections: List[Decimal] = []
        self.daily_rates: List[float] = []

    def generate_portfolio(self):
        """Generate synthetic account portfolio"""
        logger.info(f"Generating portfolio of {self.config.num_accounts} accounts...")

        min_bal, max_bal, skew = self.config.balance_distribution

        for i in range(self.config.num_accounts):
            # Skewed balance distribution (more small debts)
            raw = random.random() ** (1 + skew)
            balance = Decimal(str(min_bal + raw * (max_bal - min_bal))).quantize(Decimal("0.01"))

            # Generate debtor characteristics
            age = random.randint(22, 75)
            income = random.choices(
                ["low", "medium", "high"],
                weights=[0.4, 0.45, 0.15]
            )[0]

            employment = random.choices(
                ["employed", "unemployed", "self_employed", "retired"],
                weights=[0.55, 0.2, 0.15, 0.1]
            )[0]

            # Base willingness adjusted by income and employment
            base_willingness = self.config.avg_payment_willingness
            if income == "high":
                base_willingness += 0.15
            elif income == "low":
                base_willingness -= 0.1

            if employment == "employed":
                base_willingness += 0.1
            elif employment == "unemployed":
                base_willingness -= 0.15

            willingness = max(0.1, min(0.9, base_willingness + random.gauss(0, 0.1)))

            # Tech savviness (younger = more tech savvy)
            tech_base = self.config.avg_tech_savvy
            if age < 35:
                tech_base += 0.2
            elif age > 55:
                tech_base -= 0.2
            tech_savvy = max(0.1, min(0.95, tech_base + random.gauss(0, 0.15)))

            # Responsiveness
            responsiveness = max(0.1, min(0.9,
                self.config.avg_responsiveness + random.gauss(0, 0.15)
            ))

            # Contact validity
            phone_valid = random.random() < 0.85
            email_valid = random.random() < 0.75
            address_valid = random.random() < 0.90

            # Mobile device ownership
            mobile = age < 70 and random.random() < (0.95 if age < 50 else 0.75)

            # Friction tolerance (income and age based)
            friction_tolerance = 0.5
            if income == "high":
                friction_tolerance -= 0.15  # Less tolerant
            if age > 50:
                friction_tolerance += 0.1  # More tolerant

            account = SimulatedAccount(
                account_id=f"ACC-{i:06d}",
                balance=balance,
                original_balance=balance,
                age=age,
                income_bracket=income,
                employment_status=employment,
                payment_willingness=willingness,
                tech_savvy=tech_savvy,
                responsiveness=responsiveness,
                phone_valid=phone_valid,
                email_valid=email_valid,
                address_valid=address_valid,
                mobile_device=mobile,
                friction_tolerance=friction_tolerance,
            )

            self.accounts[account.account_id] = account

        self.metrics.total_accounts = len(self.accounts)
        self.metrics.total_balance = sum(a.balance for a in self.accounts.values())

        logger.info(f"Generated {len(self.accounts)} accounts with "
                   f"total balance ${self.metrics.total_balance:,.2f}")

    def initialize_agents(self):
        """Initialize simulation agents"""
        logger.info(f"Initializing {self.config.num_agents} agents...")

        for i in range(self.config.num_agents):
            agent = SimulationAgent(agent_id=f"AGENT-{i:04d}")
            self.agents[agent.agent_id] = agent

        # Distribute accounts among agents
        accounts_list = list(self.accounts.keys())
        random.shuffle(accounts_list)

        accounts_per_agent = len(accounts_list) // self.config.num_agents

        agent_list = list(self.agents.values())
        for i, account_id in enumerate(accounts_list):
            agent = agent_list[i % self.config.num_agents]
            agent.accounts_assigned += 1

        logger.info(f"Distributed ~{accounts_per_agent} accounts per agent")

    def determine_payment_method(self, account: SimulatedAccount) -> str:
        """Determine best payment method for account"""
        methods = []

        # Digital wallet options for mobile users
        if account.mobile_device and account.tech_savvy > 0.5:
            if random.random() < 0.4:
                methods.append("apple_pay")
            if random.random() < 0.35:
                methods.append("google_pay")

        # Saved payment (if has previous payment)
        if account.has_saved_payment:
            methods.append("saved_card")
            methods.append("one_click_ach")

        # Standard options
        methods.extend(["new_card", "ach", "payment_link"])

        # Phone for less tech savvy
        if account.tech_savvy < 0.4:
            methods.append("phone_payment")

        # Select lowest friction method available
        methods.sort(key=lambda m: self.PAYMENT_FRICTION.get(m, 1.0))

        return methods[0] if methods else "payment_link"

    def calculate_conversion_probability(
        self,
        account: SimulatedAccount,
        method: str,
        is_retry: bool = False,
        is_re_engagement: bool = False
    ) -> float:
        """Calculate probability of successful payment"""
        # Base conversion for method
        base_rate = self.METHOD_CONVERSION.get(method, 0.3)

        # Adjust for debtor willingness
        willingness_factor = account.payment_willingness

        # Adjust for friction
        friction = self.PAYMENT_FRICTION.get(method, 0.5)
        friction_impact = friction * self.config.friction_impact
        if account.friction_tolerance > 0.5:
            friction_impact *= (1 - account.friction_tolerance)

        # Adjust for tech savviness (digital methods)
        tech_factor = 1.0
        if method in ["apple_pay", "google_pay", "saved_card", "one_click_ach"]:
            tech_factor = 0.7 + (0.3 * account.tech_savvy)

        # Trust adjustment
        trust_factor = 0.7 + (0.3 * account.trust_level)

        # Fatigue reduction
        fatigue_factor = 1.0 - (account.engagement_fatigue * 0.3)

        # Re-engagement bonus (offers/discounts)
        re_engagement_bonus = 1.2 if is_re_engagement else 1.0

        # Retry penalty
        retry_penalty = 0.85 if is_retry else 1.0

        # Calculate final probability
        probability = (
            base_rate *
            willingness_factor *
            (1 - friction_impact) *
            tech_factor *
            trust_factor *
            fatigue_factor *
            re_engagement_bonus *
            retry_penalty
        )

        return max(0.05, min(0.95, probability))

    async def simulate_contact(
        self,
        account: SimulatedAccount,
        agent: SimulationAgent
    ) -> Tuple[bool, str]:
        """Simulate contact attempt"""
        # Determine if contact successful based on responsiveness
        contact_success = random.random() < account.responsiveness

        # Update account state
        account.last_contact = datetime.now()
        account.engagement_fatigue = min(1.0, account.engagement_fatigue + 0.05)

        # Track contact
        agent.contacts_made += 1
        self.metrics.total_contacts += 1
        self.metrics.total_cost += self.config.cost_per_contact

        self.contact_events.append({
            "account_id": account.account_id,
            "day": self.current_day,
            "success": contact_success,
            "agent_id": agent.agent_id
        })

        if contact_success:
            # Update trust slightly for successful contact
            account.trust_level = min(1.0, account.trust_level +
                                     self.config.trust_boost_per_interaction)

        return contact_success, "contact_made" if contact_success else "no_answer"

    async def simulate_payment(
        self,
        account: SimulatedAccount,
        agent: SimulationAgent,
        is_retry: bool = False,
        is_re_engagement: bool = False,
        settlement_amount: Optional[Decimal] = None
    ) -> Tuple[bool, Decimal]:
        """Simulate payment attempt"""
        # Determine payment method
        method = self.determine_payment_method(account)

        # Calculate conversion probability
        prob = self.calculate_conversion_probability(
            account, method, is_retry, is_re_engagement
        )

        # Simulate payment
        success = random.random() < prob

        # Track attempt
        agent.payments_processed += 1
        self.metrics.total_payments += 1
        self.metrics.total_cost += self.config.cost_per_payment_attempt

        if is_retry:
            agent.retries_executed += 1
            self.metrics.total_retries += 1

        amount_paid = Decimal("0")

        if success:
            # Determine amount (full balance or settlement)
            if settlement_amount:
                amount_paid = settlement_amount
            else:
                # Some pay partial
                if random.random() < 0.15:
                    amount_paid = (account.balance * Decimal(str(
                        random.uniform(0.3, 0.8)
                    ))).quantize(Decimal("0.01"))
                else:
                    amount_paid = account.balance

            # Update account
            account.total_paid += amount_paid
            account.balance -= amount_paid
            account.payments_made += 1
            account.last_payment = datetime.now()
            account.has_saved_payment = random.random() < 0.7  # Save payment for next time
            account.preferred_payment_method = method

            # Reset fatigue on successful payment
            account.engagement_fatigue = max(0, account.engagement_fatigue - 0.2)
            account.trust_level = min(1.0, account.trust_level + 0.1)

            if account.balance <= 0:
                account.status = "collected"
            else:
                account.status = "partial"

            # Track metrics
            agent.total_collected += amount_paid
            agent.accounts_collected += 1
            self.metrics.total_collected += amount_paid

            # Track by method
            if method not in self.metrics.conversion_by_method:
                self.metrics.conversion_by_method[method] = []
            self.metrics.conversion_by_method[method].append(1)

        else:
            # Track failure
            if method not in self.metrics.conversion_by_method:
                self.metrics.conversion_by_method[method] = []
            self.metrics.conversion_by_method[method].append(0)

        self.payment_events.append({
            "account_id": account.account_id,
            "day": self.current_day,
            "success": success,
            "method": method,
            "amount": float(amount_paid),
            "is_retry": is_retry,
            "is_re_engagement": is_re_engagement
        })

        return success, amount_paid

    async def simulate_re_engagement(
        self,
        account: SimulatedAccount,
        agent: SimulationAgent
    ) -> Tuple[bool, Decimal]:
        """Simulate re-engagement campaign"""
        agent.re_engagements_sent += 1
        self.metrics.total_re_engagements += 1
        self.metrics.total_cost += self.config.cost_per_re_engagement

        # Calculate settlement offer (40-60% of balance)
        discount = random.uniform(0.4, 0.6)
        settlement = (account.balance * Decimal(str(1 - discount))).quantize(Decimal("0.01"))

        # Probability of accepting settlement
        base_prob = 0.25

        # Higher discount = higher acceptance
        discount_bonus = discount * 0.3

        # Financial hardship increases acceptance
        if account.income_bracket == "low" or account.employment_status == "unemployed":
            base_prob += 0.15

        # High fatigue reduces acceptance
        fatigue_penalty = account.engagement_fatigue * 0.2

        acceptance_prob = base_prob + discount_bonus - fatigue_penalty

        if random.random() < acceptance_prob:
            # Settlement accepted - process payment
            return await self.simulate_payment(
                account, agent,
                is_re_engagement=True,
                settlement_amount=settlement
            )

        return False, Decimal("0")

    async def run_day(self, day: int):
        """Simulate one day of collection activity"""
        self.current_day = day
        daily_collected = Decimal("0")

        # Get active accounts
        active_accounts = [
            a for a in self.accounts.values()
            if a.status not in ["collected"]
        ]

        # Shuffle for fair processing
        random.shuffle(active_accounts)

        # Each agent processes their share
        agent_list = list(self.agents.values())

        for i, account in enumerate(active_accounts):
            agent = agent_list[i % len(agent_list)]

            # Calculate days since events using simulation day
            if account.last_contact:
                days_since_contact = day - getattr(account, '_last_contact_day', 0)
            else:
                days_since_contact = 999

            if account.last_payment:
                days_since_payment = day - getattr(account, '_last_payment_day', 0)
            else:
                days_since_payment = 999

            # Track contact attempts
            contact_attempts = getattr(account, '_contact_attempts', 0)

            # Skip if recently contacted (wait 3-5 days between contacts)
            if days_since_contact < 3:
                continue

            # Fresh accounts or accounts needing retry contact
            if account.payments_made == 0 and contact_attempts < self.config.max_contact_attempts:
                contact_success, _ = await self.simulate_contact(account, agent)
                account._last_contact_day = day
                account._contact_attempts = contact_attempts + 1

                if contact_success:
                    success, amount = await self.simulate_payment(account, agent)
                    if success:
                        account._last_payment_day = day
                    daily_collected += amount
                elif contact_attempts >= 3 and days_since_contact > 7:
                    # Try re-engagement after multiple failed contacts
                    success, amount = await self.simulate_re_engagement(account, agent)
                    if success:
                        account._last_payment_day = day
                    daily_collected += amount

            # Partial payment accounts: follow up for remaining balance
            elif account.status == "partial" and days_since_payment > 7:
                contact_success, _ = await self.simulate_contact(account, agent)
                account._last_contact_day = day

                if contact_success:
                    success, amount = await self.simulate_payment(
                        account, agent, is_retry=True
                    )
                    if success:
                        account._last_payment_day = day
                    daily_collected += amount

            # Dormant accounts: re-engagement campaign
            elif days_since_contact > self.config.re_engagement_threshold_days:
                re_engagement_attempts = getattr(account, '_re_engagement_attempts', 0)

                if re_engagement_attempts < 3:  # Max 3 re-engagement campaigns
                    success, amount = await self.simulate_re_engagement(account, agent)
                    account._last_contact_day = day
                    account._re_engagement_attempts = re_engagement_attempts + 1

                    if success:
                        account._last_payment_day = day
                    daily_collected += amount

            # Apply daily fatigue decay
            account.engagement_fatigue = max(0, account.engagement_fatigue - 0.01)

        self.daily_collections.append(daily_collected)

        # Calculate daily rate
        current_rate = float(self.metrics.total_collected / self.metrics.total_balance)
        self.daily_rates.append(current_rate)

    def check_convergence(self) -> bool:
        """Check if simulation has converged"""
        # Need at least 60 days of data
        if len(self.daily_rates) < 60:
            return False

        recent_rates = self.daily_rates[-15:]
        std_dev = statistics.stdev(recent_rates)

        # Converged if rate is very stable over 15 days
        return std_dev < 0.001

    def calculate_final_metrics(self):
        """Calculate final simulation metrics"""
        # Account status counts
        collected = sum(1 for a in self.accounts.values() if a.status == "collected")
        partial = sum(1 for a in self.accounts.values() if a.status == "partial")
        active = sum(1 for a in self.accounts.values() if a.status == "active")

        self.metrics.accounts_collected = collected
        self.metrics.accounts_partial = partial
        self.metrics.accounts_defaulted = active

        # Recovery rate
        self.metrics.recovery_rate = float(
            self.metrics.total_collected / self.metrics.total_balance
        ) if self.metrics.total_balance > 0 else 0

        # Collection efficiency (collected accounts / total accounts)
        self.metrics.collection_efficiency = collected / self.metrics.total_accounts

        # Cost metrics
        if self.metrics.total_collected > 0:
            self.metrics.cost_per_dollar_collected = float(
                self.metrics.total_cost / self.metrics.total_collected
            )
        else:
            self.metrics.cost_per_dollar_collected = float('inf')

        # Profit margin
        net_revenue = self.metrics.total_collected - self.metrics.total_cost
        if self.metrics.total_collected > 0:
            self.metrics.profit_margin = float(net_revenue / self.metrics.total_collected)
        else:
            self.metrics.profit_margin = 0

        # ROI
        if self.metrics.total_cost > 0:
            self.metrics.roi = float(net_revenue / self.metrics.total_cost)
        else:
            self.metrics.roi = 0

        # Friction score
        friction_scores = []
        for method, results in self.metrics.conversion_by_method.items():
            if results:
                rate = sum(results) / len(results)
                friction = self.PAYMENT_FRICTION.get(method, 0.5)
                friction_scores.append(friction)
        self.metrics.avg_friction_score = (
            sum(friction_scores) / len(friction_scores) if friction_scores else 0.5
        )

        # Conversion by method (calculate rates)
        method_rates = {}
        for method, results in self.metrics.conversion_by_method.items():
            if results:
                method_rates[method] = sum(results) / len(results)
        self.metrics.conversion_by_method = method_rates

        # Re-engagement metrics
        re_engagement_payments = [
            e for e in self.payment_events
            if e.get("is_re_engagement") and e.get("success")
        ]
        if self.metrics.total_re_engagements > 0:
            self.metrics.re_engagement_conversion_rate = (
                len(re_engagement_payments) / self.metrics.total_re_engagements
            )
        else:
            self.metrics.re_engagement_conversion_rate = 0

    async def run_simulation(self, iterations: int = 1) -> List[SimulationMetrics]:
        """Run the full simulation"""
        all_metrics = []

        for iteration in range(iterations):
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration + 1}/{iterations}")
            logger.info(f"{'='*60}")

            # Reset state
            self.accounts = {}
            self.agents = {}
            self.metrics = SimulationMetrics()
            self.daily_collections = []
            self.daily_rates = []
            self.payment_events = []
            self.contact_events = []

            # Initialize
            self.generate_portfolio()
            self.initialize_agents()

            # Run simulation days
            for day in range(self.config.simulation_days):
                await self.run_day(day)

                # Progress logging every 10 days
                if day > 0 and day % 10 == 0:
                    rate = float(self.metrics.total_collected / self.metrics.total_balance) * 100
                    logger.info(f"  Day {day}: Recovery {rate:.1f}%, "
                               f"Collected ${self.metrics.total_collected:,.2f}")

                # Check convergence
                if day > 30 and self.check_convergence():
                    logger.info(f"  Converged at day {day}")
                    break

            # Calculate final metrics
            self.calculate_final_metrics()
            all_metrics.append(self.metrics)

            # Log iteration results
            self._log_iteration_results(iteration)

        return all_metrics

    def _log_iteration_results(self, iteration: int):
        """Log results for an iteration"""
        m = self.metrics

        print(f"\n{'='*60}")
        print(f"  ITERATION {iteration + 1} RESULTS")
        print(f"{'='*60}")

        print(f"\n  PORTFOLIO:")
        print(f"    Total Accounts:    {m.total_accounts:,}")
        print(f"    Total Balance:     ${m.total_balance:,.2f}")

        print(f"\n  RECOVERY:")
        print(f"    Collected:         ${m.total_collected:,.2f}")
        print(f"    Recovery Rate:     {m.recovery_rate*100:.1f}%")
        print(f"    Accounts Closed:   {m.accounts_collected:,} ({m.collection_efficiency*100:.1f}%)")
        print(f"    Partial:           {m.accounts_partial:,}")
        print(f"    Remaining:         {m.accounts_defaulted:,}")

        print(f"\n  ACTIVITY:")
        print(f"    Total Contacts:    {m.total_contacts:,}")
        print(f"    Total Payments:    {m.total_payments:,}")
        print(f"    Retries:           {m.total_retries:,}")
        print(f"    Re-engagements:    {m.total_re_engagements:,}")

        print(f"\n  ECONOMICS:")
        print(f"    Total Cost:        ${m.total_cost:,.2f}")
        print(f"    Cost per $1:       ${m.cost_per_dollar_collected:.3f}")
        print(f"    Profit Margin:     {m.profit_margin*100:.1f}%")
        print(f"    ROI:               {m.roi*100:.0f}%")

        print(f"\n  FRICTION ANALYSIS:")
        print(f"    Avg Friction:      {m.avg_friction_score:.2f}")
        print(f"    Re-engage Conv:    {m.re_engagement_conversion_rate*100:.1f}%")
        print(f"\n    Method Performance:")
        for method, rate in sorted(m.conversion_by_method.items(),
                                   key=lambda x: x[1], reverse=True):
            friction = self.PAYMENT_FRICTION.get(method, 0)
            print(f"      {method:20s} Conv: {rate*100:5.1f}%  Friction: {friction:.2f}")


async def run_maximum_deployment():
    """Run simulation with maximum agent deployment"""
    print("="*70)
    print("  QUAN PERPETUAL COLLECTION SIMULATION")
    print("  Maximum Agent Deployment with Frictionless Payments")
    print("="*70)

    config = SimulationConfig(
        num_agents=250,
        num_accounts=50000,
        simulation_days=90,
        mode=SimulationMode.ADAPTIVE,

        # Realistic debtor characteristics
        avg_payment_willingness=0.32,
        avg_tech_savvy=0.55,
        avg_responsiveness=0.28,

        # Collection parameters
        max_contact_attempts=8,
        max_payment_retries=3,
        re_engagement_threshold_days=14,

        # Economic reality
        base_conversion_rate=0.35,
        friction_impact=0.25,
        cost_per_contact=Decimal("0.12"),
        cost_per_payment_attempt=Decimal("0.22"),
        cost_per_re_engagement=Decimal("0.45"),
    )

    simulator = PerpetualCollectionSimulator(config)

    # Run 5 iterations for convergence
    print(f"\nRunning {5} iterations with {config.num_agents} agents...")
    print(f"Portfolio: {config.num_accounts:,} accounts")
    print(f"Simulation: {config.simulation_days} days per iteration\n")

    metrics_list = await simulator.run_simulation(iterations=5)

    # Aggregate results
    print("\n" + "="*70)
    print("  AGGREGATE RESULTS (5 ITERATIONS)")
    print("="*70)

    recovery_rates = [m.recovery_rate for m in metrics_list]
    profit_margins = [m.profit_margin for m in metrics_list]
    rois = [m.roi for m in metrics_list]

    avg_recovery = statistics.mean(recovery_rates)
    std_recovery = statistics.stdev(recovery_rates) if len(recovery_rates) > 1 else 0

    avg_margin = statistics.mean(profit_margins)
    avg_roi = statistics.mean(rois)

    print(f"\n  Recovery Rate:    {avg_recovery*100:.1f}% (+/- {std_recovery*100:.2f}%)")
    print(f"  Profit Margin:    {avg_margin*100:.1f}%")
    print(f"  ROI:              {avg_roi*100:.0f}%")

    # Convergence check
    if std_recovery < 0.01:
        print(f"\n  STATUS: CONVERGED")
    else:
        print(f"\n  STATUS: Further iterations may improve convergence")

    print("\n" + "="*70)

    return metrics_list


if __name__ == "__main__":
    asyncio.run(run_maximum_deployment())
