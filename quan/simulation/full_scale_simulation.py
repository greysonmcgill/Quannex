"""
Full-Scale Universe Simulation with Growth Runway Modeling

Scales simulation to model the complete micro-loan marketplace
with 500 agents and 100,000+ accounts across all debt types.
"""

import asyncio
import random
import uuid
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import sys
import os

# Add path for imports
sys.path.insert(0, '/home/user/Quan')

from quan.models.micro_loan_universe import (
    MicroLoanUniverseGenerator, DebtType, MICRO_LOAN_UNIVERSE,
    DebtTypeProfile, get_market_summary
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ScaleConfig:
    """Configuration for full-scale simulation"""
    # Agent deployment
    num_agents: int = 500
    accounts_per_agent: int = 200  # Target accounts per agent

    # Portfolio scale
    total_accounts: int = 100000
    simulation_days: int = 180  # 6 months

    # Market mix (weights by debt type)
    debt_type_weights: Optional[Dict[DebtType, float]] = None

    # Collection parameters
    max_contact_attempts: int = 10
    max_payment_retries: int = 4
    re_engagement_threshold_days: int = 14
    max_re_engagement_campaigns: int = 4

    # Economic parameters (per-action costs)
    cost_per_contact: Decimal = Decimal("0.10")
    cost_per_payment_attempt: Decimal = Decimal("0.20")
    cost_per_re_engagement: Decimal = Decimal("0.40")
    cost_per_agent_day: Decimal = Decimal("150")  # Agent salary cost

    # Performance targets
    target_recovery_rate: float = 0.30
    target_profit_margin: float = 0.90


@dataclass
class GrowthScenario:
    """A growth scenario for runway projection"""
    name: str
    year: int
    market_penetration_pct: float
    accounts_acquired: int
    avg_balance: Decimal
    recovery_rate: float
    cost_per_dollar: float

    # Calculated fields
    total_balance: Decimal = Decimal("0")
    gross_collections: Decimal = Decimal("0")
    total_costs: Decimal = Decimal("0")
    net_revenue: Decimal = Decimal("0")
    profit_margin: float = 0.0
    agents_required: int = 0


@dataclass
class MarketPenetrationModel:
    """Model for market penetration growth"""
    starting_accounts: int
    starting_balance: Decimal
    annual_growth_rate: float
    market_share_year1: float
    market_share_year5: float

    # S-curve parameters
    inflection_year: float = 2.5
    max_penetration: float = 0.15


@dataclass
class ScaleSimulationResults:
    """Results from full-scale simulation"""
    # Portfolio metrics
    total_accounts: int = 0
    total_balance: Decimal = Decimal("0")

    # Collection metrics
    accounts_collected: int = 0
    accounts_partial: int = 0
    accounts_uncollected: int = 0
    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    # Activity metrics
    total_contacts: int = 0
    total_payments: int = 0
    total_retries: int = 0
    total_re_engagements: int = 0

    # Cost metrics
    total_cost: Decimal = Decimal("0")
    cost_per_dollar: float = 0.0
    profit_margin: float = 0.0
    roi: float = 0.0

    # By debt type
    results_by_type: Dict[str, Dict] = field(default_factory=dict)

    # Agent metrics
    num_agents: int = 0
    avg_accounts_per_agent: float = 0.0
    avg_collection_per_agent: Decimal = Decimal("0")

    # Time metrics
    simulation_days: int = 0
    convergence_day: int = 0


class FullScaleSimulator:
    """
    Full-scale simulation across the entire micro-loan universe.
    """

    def __init__(self, config: ScaleConfig):
        self.config = config
        self.generator = MicroLoanUniverseGenerator()
        self.portfolio: List[Dict[str, Any]] = []
        self.results = ScaleSimulationResults()

        # Simulation state
        self.current_day = 0
        self.daily_collections: List[Decimal] = []
        self.daily_rates: List[float] = []

        # Per debt type tracking
        self.type_metrics: Dict[str, Dict] = {}

    def generate_portfolio(self):
        """Generate full-scale portfolio across all debt types"""
        logger.info(f"Generating {self.config.total_accounts:,} account portfolio...")

        self.portfolio = self.generator.generate_full_portfolio(
            self.config.total_accounts,
            self.config.debt_type_weights
        )

        # Initialize type metrics
        for dt in DebtType:
            dt_accounts = [a for a in self.portfolio if a["debt_type"] == dt.value]
            if dt_accounts:
                self.type_metrics[dt.value] = {
                    "accounts": len(dt_accounts),
                    "balance": sum(Decimal(str(a["balance"])) for a in dt_accounts),
                    "collected": Decimal("0"),
                    "contacts": 0,
                    "payments": 0
                }

        self.results.total_accounts = len(self.portfolio)
        self.results.total_balance = sum(
            Decimal(str(a["balance"])) for a in self.portfolio
        )

        # Log portfolio summary
        logger.info(f"Portfolio generated: {self.results.total_accounts:,} accounts, "
                   f"${self.results.total_balance:,.2f} total balance")

        for dt, metrics in sorted(self.type_metrics.items(),
                                  key=lambda x: x[1]["balance"], reverse=True)[:5]:
            logger.info(f"  {dt}: {metrics['accounts']:,} accounts, "
                       f"${metrics['balance']:,.2f}")

    def simulate_collection_action(
        self,
        account: Dict[str, Any],
        day: int
    ) -> Tuple[bool, Decimal]:
        """Simulate a collection action on an account"""
        # Get debt type profile
        dt = account["debt_type"]
        profile = MICRO_LOAN_UNIVERSE.get(DebtType(dt))
        if not profile:
            return False, Decimal("0")

        # Calculate collection probability
        base_prob = profile.base_recovery_rate

        # Adjust for account characteristics
        collectability = account.get("collectability_score", 0.3)
        prob = base_prob * (0.5 + collectability)

        # Adjust for risk factors
        if account.get("is_bankruptcy"):
            prob = 0.02  # Nearly zero
        if account.get("has_dispute"):
            prob *= 0.5
        if account.get("sol_expired"):
            prob *= 0.7

        # Adjust for contact attempts (diminishing returns)
        attempts = account.get("_contact_attempts", 0)
        if attempts > 0:
            prob *= (0.9 ** attempts)

        # Re-engagement bonus
        if account.get("_in_re_engagement"):
            prob *= 1.25

        # Simulate outcome
        success = random.random() < prob

        amount_collected = Decimal("0")
        if success:
            balance = Decimal(str(account["balance"]))

            # Determine collection amount
            if account.get("settlement_candidate") and random.random() < 0.4:
                # Settlement at discount
                discount = random.uniform(0.3, 0.6)
                amount_collected = (balance * Decimal(str(1 - discount))).quantize(Decimal("0.01"))
            elif random.random() < 0.12:
                # Partial payment
                amount_collected = (balance * Decimal(str(random.uniform(0.3, 0.8)))).quantize(Decimal("0.01"))
            else:
                # Full payment
                amount_collected = balance

            # Update account
            account["balance"] = Decimal(str(account["balance"])) - amount_collected
            account["_payments_made"] = account.get("_payments_made", 0) + 1
            account["_total_paid"] = Decimal(str(account.get("_total_paid", 0))) + amount_collected
            account["_last_payment_day"] = day

            if account["balance"] <= 0:
                account["_status"] = "collected"
            else:
                account["_status"] = "partial"

            # Update type metrics
            self.type_metrics[dt]["collected"] += amount_collected
            self.type_metrics[dt]["payments"] += 1

        # Update contact tracking
        account["_contact_attempts"] = attempts + 1
        account["_last_contact_day"] = day
        self.type_metrics[dt]["contacts"] += 1

        return success, amount_collected

    async def run_simulation_day(self, day: int):
        """Run a single simulation day"""
        self.current_day = day
        daily_collected = Decimal("0")
        daily_contacts = 0
        daily_re_engagements = 0

        # Process each account
        for account in self.portfolio:
            # Skip collected accounts
            if account.get("_status") == "collected":
                continue

            # Calculate days since last contact
            last_contact = account.get("_last_contact_day", -999)
            days_since_contact = day - last_contact

            # Skip if recently contacted
            if days_since_contact < 3:
                continue

            contact_attempts = account.get("_contact_attempts", 0)
            re_engagement_attempts = account.get("_re_engagement_attempts", 0)

            # Determine action
            should_contact = False
            is_re_engagement = False

            # Fresh or retry accounts
            if contact_attempts < self.config.max_contact_attempts:
                should_contact = True

            # Re-engagement for dormant accounts
            elif (days_since_contact > self.config.re_engagement_threshold_days and
                  re_engagement_attempts < self.config.max_re_engagement_campaigns):
                should_contact = True
                is_re_engagement = True
                account["_in_re_engagement"] = True
                account["_re_engagement_attempts"] = re_engagement_attempts + 1
                daily_re_engagements += 1

            if should_contact:
                success, amount = self.simulate_collection_action(account, day)
                daily_collected += amount
                daily_contacts += 1

                if success:
                    account["_in_re_engagement"] = False

        # Update results
        self.results.total_collected += daily_collected
        self.results.total_contacts += daily_contacts
        self.results.total_re_engagements += daily_re_engagements

        self.daily_collections.append(daily_collected)

        # Calculate daily rate
        if self.results.total_balance > 0:
            rate = float(self.results.total_collected / self.results.total_balance)
            self.daily_rates.append(rate)

    def check_convergence(self) -> bool:
        """Check if simulation has converged"""
        if len(self.daily_rates) < 90:
            return False

        recent = self.daily_rates[-20:]
        if len(recent) < 2:
            return False

        std = statistics.stdev(recent)
        return std < 0.0005

    async def run_simulation(self) -> ScaleSimulationResults:
        """Run the full simulation"""
        # Generate portfolio
        self.generate_portfolio()

        logger.info(f"\nRunning {self.config.simulation_days}-day simulation "
                   f"with {self.config.num_agents} agents...")

        # Run simulation days
        for day in range(self.config.simulation_days):
            await self.run_simulation_day(day)

            # Progress logging
            if day > 0 and day % 30 == 0:
                rate = float(self.results.total_collected / self.results.total_balance) * 100
                logger.info(f"  Day {day}: Recovery {rate:.1f}%, "
                           f"Collected ${self.results.total_collected:,.2f}")

            # Check convergence
            if day > 90 and self.check_convergence():
                logger.info(f"  Converged at day {day}")
                self.results.convergence_day = day
                break

        # Calculate final metrics
        self._calculate_final_metrics()

        return self.results

    def _calculate_final_metrics(self):
        """Calculate final simulation metrics"""
        # Account status counts
        collected = sum(1 for a in self.portfolio if a.get("_status") == "collected")
        partial = sum(1 for a in self.portfolio if a.get("_status") == "partial")
        uncollected = self.results.total_accounts - collected - partial

        self.results.accounts_collected = collected
        self.results.accounts_partial = partial
        self.results.accounts_uncollected = uncollected

        # Recovery rate
        if self.results.total_balance > 0:
            self.results.recovery_rate = float(
                self.results.total_collected / self.results.total_balance
            )

        # Calculate costs
        self.results.total_cost = (
            self.config.cost_per_contact * self.results.total_contacts +
            self.config.cost_per_re_engagement * self.results.total_re_engagements +
            self.config.cost_per_agent_day * self.config.num_agents * self.config.simulation_days
        )

        # Cost metrics
        if self.results.total_collected > 0:
            self.results.cost_per_dollar = float(
                self.results.total_cost / self.results.total_collected
            )

            net = self.results.total_collected - self.results.total_cost
            self.results.profit_margin = float(net / self.results.total_collected)
            self.results.roi = float(net / self.results.total_cost)

        # Agent metrics
        self.results.num_agents = self.config.num_agents
        self.results.avg_accounts_per_agent = (
            self.results.total_accounts / self.config.num_agents
        )
        self.results.avg_collection_per_agent = (
            self.results.total_collected / self.config.num_agents
        )
        self.results.simulation_days = self.current_day + 1

        # Results by debt type
        for dt, metrics in self.type_metrics.items():
            if metrics["balance"] > 0:
                self.results.results_by_type[dt] = {
                    "accounts": metrics["accounts"],
                    "balance": float(metrics["balance"]),
                    "collected": float(metrics["collected"]),
                    "recovery_rate": float(metrics["collected"] / metrics["balance"]),
                    "contacts": metrics["contacts"],
                    "payments": metrics["payments"]
                }


class GrowthRunwayModel:
    """
    Models growth runway and market penetration over time.
    """

    def __init__(self):
        self.generator = MicroLoanUniverseGenerator()
        self.market_totals = self.generator.calculate_market_totals()

        # Total addressable market
        self.tam_billions = self.market_totals["total_market_size_billions"]
        self.tam_accounts_millions = self.market_totals["total_accounts_millions"]

    def s_curve_penetration(
        self,
        year: int,
        max_penetration: float = 0.10,
        inflection_year: float = 3.0,
        steepness: float = 1.5
    ) -> float:
        """Calculate market penetration using S-curve (logistic function)"""
        # Logistic growth: P(t) = L / (1 + e^(-k(t-t0)))
        import math
        penetration = max_penetration / (
            1 + math.exp(-steepness * (year - inflection_year))
        )
        return min(penetration, max_penetration)

    def project_growth(
        self,
        years: int = 5,
        starting_accounts: int = 10000,
        base_recovery_rate: float = 0.30,
        max_penetration: float = 0.10,
        efficiency_improvement_rate: float = 0.05
    ) -> List[GrowthScenario]:
        """Project growth over multiple years"""
        scenarios = []

        # Average balance from market data
        avg_balance = Decimal(str(
            self.tam_billions * 1e9 / (self.tam_accounts_millions * 1e6)
        ))

        for year in range(1, years + 1):
            # Calculate market penetration (S-curve)
            penetration = self.s_curve_penetration(year, max_penetration)

            # Calculate accounts (minimum of starting + growth, or penetration of TAM)
            organic_accounts = int(starting_accounts * (1.5 ** (year - 1)))
            penetration_accounts = int(self.tam_accounts_millions * 1e6 * penetration)
            accounts = min(organic_accounts, penetration_accounts)

            # Recovery rate improves with scale and learning
            recovery = base_recovery_rate + (efficiency_improvement_rate * (year - 1))
            recovery = min(0.45, recovery)  # Cap at 45%

            # Cost per dollar decreases with scale
            base_cost = 0.04
            scale_factor = 1 - (0.1 * min(year - 1, 3))  # Max 30% reduction
            cost_per_dollar = base_cost * scale_factor

            # Calculate financials
            total_balance = avg_balance * accounts
            gross_collections = total_balance * Decimal(str(recovery))
            total_costs = gross_collections * Decimal(str(cost_per_dollar))
            net_revenue = gross_collections - total_costs
            profit_margin = float(net_revenue / gross_collections) if gross_collections > 0 else 0

            # Agents required (200 accounts per agent)
            agents_required = max(10, accounts // 200)

            scenario = GrowthScenario(
                name=f"Year {year}",
                year=year,
                market_penetration_pct=penetration * 100,
                accounts_acquired=accounts,
                avg_balance=avg_balance,
                recovery_rate=recovery,
                cost_per_dollar=cost_per_dollar,
                total_balance=total_balance,
                gross_collections=gross_collections,
                total_costs=total_costs,
                net_revenue=net_revenue,
                profit_margin=profit_margin,
                agents_required=agents_required
            )

            scenarios.append(scenario)

        return scenarios

    def print_growth_projection(self, scenarios: List[GrowthScenario]):
        """Print growth projection table"""
        print("\n" + "=" * 90)
        print("  QUAN RECOVERY - 5-YEAR GROWTH RUNWAY PROJECTION")
        print("=" * 90)

        print(f"\n  Total Addressable Market: ${self.tam_billions:.1f}B across "
              f"{self.tam_accounts_millions:.1f}M accounts")

        print("\n  " + "-" * 86)
        print(f"  {'Year':<6} {'Penetration':>12} {'Accounts':>12} {'Balance':>14} "
              f"{'Collections':>14} {'Net Revenue':>14} {'Margin':>8}")
        print("  " + "-" * 86)

        for s in scenarios:
            print(f"  {s.name:<6} {s.market_penetration_pct:>11.2f}% "
                  f"{s.accounts_acquired:>12,} "
                  f"${float(s.total_balance)/1e6:>12,.1f}M "
                  f"${float(s.gross_collections)/1e6:>12,.1f}M "
                  f"${float(s.net_revenue)/1e6:>12,.1f}M "
                  f"{s.profit_margin*100:>7.1f}%")

        print("  " + "-" * 86)

        # Summary
        final = scenarios[-1]
        year1 = scenarios[0]

        print(f"\n  GROWTH SUMMARY:")
        print(f"    Account Growth:     {year1.accounts_acquired:,} → {final.accounts_acquired:,} "
              f"({final.accounts_acquired/year1.accounts_acquired:.1f}x)")
        print(f"    Revenue Growth:     ${float(year1.net_revenue)/1e6:.1f}M → ${float(final.net_revenue)/1e6:.1f}M "
              f"({float(final.net_revenue/year1.net_revenue):.1f}x)")
        print(f"    Agents Required:    {year1.agents_required} → {final.agents_required}")
        print(f"    Market Penetration: {year1.market_penetration_pct:.2f}% → {final.market_penetration_pct:.2f}%")

        print("\n" + "=" * 90)


async def run_full_scale_simulation():
    """Run full-scale simulation with growth runway modeling"""
    print("=" * 80)
    print("  QUAN RECOVERY - FULL UNIVERSE SIMULATION")
    print("  Maximum Agent Deployment with Growth Runway Modeling")
    print("=" * 80)

    # Print market summary
    print(get_market_summary())

    # Configure full-scale simulation
    config = ScaleConfig(
        num_agents=500,
        total_accounts=100000,
        simulation_days=180,
        max_contact_attempts=10,
        max_payment_retries=4,
        re_engagement_threshold_days=14,
        max_re_engagement_campaigns=4,
        cost_per_contact=Decimal("0.10"),
        cost_per_payment_attempt=Decimal("0.20"),
        cost_per_re_engagement=Decimal("0.40"),
        cost_per_agent_day=Decimal("150"),
    )

    print(f"\nSimulation Configuration:")
    print(f"  Agents:           {config.num_agents}")
    print(f"  Accounts:         {config.total_accounts:,}")
    print(f"  Duration:         {config.simulation_days} days")

    # Run simulation
    simulator = FullScaleSimulator(config)
    results = await simulator.run_simulation()

    # Print results
    print("\n" + "=" * 80)
    print("  SIMULATION RESULTS")
    print("=" * 80)

    print(f"\n  PORTFOLIO:")
    print(f"    Total Accounts:      {results.total_accounts:,}")
    print(f"    Total Balance:       ${results.total_balance:,.2f}")

    print(f"\n  RECOVERY:")
    print(f"    Collected:           ${results.total_collected:,.2f}")
    print(f"    Recovery Rate:       {results.recovery_rate*100:.1f}%")
    print(f"    Accounts Closed:     {results.accounts_collected:,} "
          f"({results.accounts_collected/results.total_accounts*100:.1f}%)")
    print(f"    Partial:             {results.accounts_partial:,}")
    print(f"    Uncollected:         {results.accounts_uncollected:,}")

    print(f"\n  ACTIVITY:")
    print(f"    Total Contacts:      {results.total_contacts:,}")
    print(f"    Re-engagements:      {results.total_re_engagements:,}")
    print(f"    Simulation Days:     {results.simulation_days}")
    print(f"    Converged Day:       {results.convergence_day}")

    print(f"\n  ECONOMICS:")
    print(f"    Total Cost:          ${results.total_cost:,.2f}")
    print(f"    Cost per $1:         ${results.cost_per_dollar:.3f}")
    print(f"    Profit Margin:       {results.profit_margin*100:.1f}%")
    print(f"    ROI:                 {results.roi*100:.0f}%")

    print(f"\n  AGENT PERFORMANCE:")
    print(f"    Agents Deployed:     {results.num_agents}")
    print(f"    Accounts/Agent:      {results.avg_accounts_per_agent:.0f}")
    print(f"    Collection/Agent:    ${results.avg_collection_per_agent:,.2f}")

    # Results by debt type
    print(f"\n  RESULTS BY DEBT TYPE:")
    print("  " + "-" * 76)
    print(f"  {'Type':<20} {'Accounts':>10} {'Balance':>14} {'Collected':>14} {'Rate':>8}")
    print("  " + "-" * 76)

    for dt, data in sorted(results.results_by_type.items(),
                          key=lambda x: x[1]["collected"], reverse=True):
        print(f"  {dt:<20} {data['accounts']:>10,} "
              f"${data['balance']:>13,.0f} ${data['collected']:>13,.0f} "
              f"{data['recovery_rate']*100:>7.1f}%")

    # Growth runway projection
    print("\n")
    growth_model = GrowthRunwayModel()
    scenarios = growth_model.project_growth(
        years=5,
        starting_accounts=config.total_accounts,
        base_recovery_rate=results.recovery_rate,
        max_penetration=0.08
    )
    growth_model.print_growth_projection(scenarios)

    return results, scenarios


if __name__ == "__main__":
    asyncio.run(run_full_scale_simulation())
