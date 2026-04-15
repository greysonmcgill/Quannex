#!/usr/bin/env python3
"""
BNPL 1M Account Simulation - Sub-$500 Balances

Runs a large-scale simulation of 1 million BNPL accounts
with balances capped at $500.
"""

import asyncio
import random
from decimal import Decimal
from datetime import datetime


from quan.models.micro_loan_universe import DebtType, MICRO_LOAN_UNIVERSE
from quan.simulation.full_scale_simulation import ScaleConfig, FullScaleSimulator


class BNPLSimulator(FullScaleSimulator):
    """Specialized BNPL simulator with balance cap"""

    def __init__(self, config: ScaleConfig, max_balance: Decimal = Decimal("500")):
        super().__init__(config)
        self.max_balance = max_balance

    def generate_portfolio(self):
        """Generate BNPL-only portfolio with balance cap"""
        print(f"\n  Generating {self.config.total_accounts:,} BNPL accounts (max ${self.max_balance})...")

        bnpl_profile = MICRO_LOAN_UNIVERSE[DebtType.BNPL]
        self.portfolio = []

        # Generate accounts in batches for memory efficiency
        batch_size = 100000
        total_generated = 0

        while total_generated < self.config.total_accounts:
            batch_count = min(batch_size, self.config.total_accounts - total_generated)

            for _ in range(batch_count):
                # Generate balance with skew, capped at max_balance
                raw = random.random() ** (1 + bnpl_profile.balance_skew)
                balance_range = float(min(self.max_balance, bnpl_profile.max_balance) - bnpl_profile.min_balance)
                balance = Decimal(str(float(bnpl_profile.min_balance) + raw * balance_range)).quantize(Decimal("0.01"))
                balance = min(balance, self.max_balance)

                # Generate account
                account = {
                    "account_id": f"BNPL-{total_generated + len(self.portfolio) + 1:08d}",
                    "debt_type": DebtType.BNPL.value,
                    "balance": balance,
                    "original_balance": balance,
                    "age_days": random.randint(30, 180),
                    "collectability_score": random.uniform(0.2, 0.8),
                    "has_dispute": random.random() < bnpl_profile.dispute_rate,
                    "is_bankruptcy": random.random() < bnpl_profile.bankruptcy_rate,
                    "settlement_candidate": random.random() < bnpl_profile.settlement_acceptance_rate,
                    "sol_expired": False,
                    "_status": "active",
                    "_contact_attempts": 0,
                    "_payments_made": 0,
                    "_total_paid": Decimal("0"),
                }
                self.portfolio.append(account)

            total_generated += batch_count
            pct = (total_generated / self.config.total_accounts) * 100
            print(f"    Generated {total_generated:,} accounts ({pct:.0f}%)")

        # Initialize type metrics
        self.type_metrics[DebtType.BNPL.value] = {
            "accounts": len(self.portfolio),
            "balance": sum(a["balance"] for a in self.portfolio),
            "collected": Decimal("0"),
            "contacts": 0,
            "payments": 0
        }

        self.results.total_accounts = len(self.portfolio)
        self.results.total_balance = self.type_metrics[DebtType.BNPL.value]["balance"]

        avg_balance = self.results.total_balance / len(self.portfolio)
        print(f"\n  Portfolio Summary:")
        print(f"    Total Accounts:  {self.results.total_accounts:,}")
        print(f"    Total Balance:   ${self.results.total_balance:,.2f}")
        print(f"    Avg Balance:     ${avg_balance:.2f}")
        print(f"    Max Balance:     ${self.max_balance}")


async def run_bnpl_simulation(num_accounts: int = 1000000, max_balance: int = 500):
    """Run BNPL-only simulation"""

    print("=" * 80)
    print("  QUAN RECOVERY - BNPL 1M ACCOUNT SIMULATION")
    print("=" * 80)
    print(f"\n  Configuration:")
    print(f"    Accounts:        {num_accounts:,}")
    print(f"    Max Balance:     ${max_balance}")
    print(f"    Debt Type:       BNPL (Buy Now Pay Later)")
    print(f"    Started:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # BNPL Profile info
    bnpl = MICRO_LOAN_UNIVERSE[DebtType.BNPL]
    print(f"\n  BNPL Debt Type Profile:")
    print(f"    Base Recovery:   {bnpl.base_recovery_rate*100:.0f}%")
    print(f"    Avg Days to Collect: {bnpl.avg_days_to_collect}")
    print(f"    Dispute Rate:    {bnpl.dispute_rate*100:.0f}%")
    print(f"    Settlement Rate: {bnpl.settlement_acceptance_rate*100:.0f}%")

    # Scale agents: 1 agent per 1000 accounts for large scale
    num_agents = max(100, num_accounts // 1000)

    config = ScaleConfig(
        num_agents=num_agents,
        total_accounts=num_accounts,
        simulation_days=90,  # 3 months
        max_contact_attempts=8,
        max_payment_retries=3,
        re_engagement_threshold_days=14,
        max_re_engagement_campaigns=3,
        cost_per_contact=Decimal("0.08"),  # Lower for BNPL
        cost_per_payment_attempt=Decimal("0.15"),
        cost_per_re_engagement=Decimal("0.30"),
        cost_per_agent_day=Decimal("120"),
        debt_type_weights={DebtType.BNPL: 1.0},  # BNPL only
    )

    print(f"\n  Simulation Parameters:")
    print(f"    Agents:          {config.num_agents:,}")
    print(f"    Duration:        {config.simulation_days} days")
    print(f"    Max Contacts:    {config.max_contact_attempts}")
    print(f"    Re-engagement:   Up to {config.max_re_engagement_campaigns} campaigns")

    # Run simulation
    print("\n" + "-" * 80)
    print("  RUNNING SIMULATION...")
    print("-" * 80)

    simulator = BNPLSimulator(config, max_balance=Decimal(str(max_balance)))
    start_time = datetime.now()
    results = await simulator.run_simulation()
    end_time = datetime.now()

    duration = (end_time - start_time).total_seconds()

    # Print results
    print("\n" + "=" * 80)
    print("  SIMULATION RESULTS")
    print("=" * 80)

    print(f"\n  PORTFOLIO PERFORMANCE:")
    print(f"    Total Accounts:      {results.total_accounts:,}")
    print(f"    Total Balance:       ${results.total_balance:,.2f}")
    print(f"    Total Collected:     ${results.total_collected:,.2f}")
    print(f"    Recovery Rate:       {results.recovery_rate*100:.2f}%")

    print(f"\n  COLLECTION BREAKDOWN:")
    print(f"    Accounts Collected:  {results.accounts_collected:,} ({results.accounts_collected/results.total_accounts*100:.1f}%)")
    print(f"    Partial Payments:    {results.accounts_partial:,} ({results.accounts_partial/results.total_accounts*100:.1f}%)")
    print(f"    Uncollected:         {results.accounts_uncollected:,} ({results.accounts_uncollected/results.total_accounts*100:.1f}%)")

    print(f"\n  ACTIVITY METRICS:")
    print(f"    Total Contacts:      {results.total_contacts:,}")
    print(f"    Re-engagements:      {results.total_re_engagements:,}")
    print(f"    Contacts/Account:    {results.total_contacts/results.total_accounts:.2f}")
    print(f"    Accounts/Day:        {results.total_accounts/results.simulation_days:,.0f}")

    print(f"\n  FINANCIAL PERFORMANCE:")
    print(f"    Total Cost:          ${results.total_cost:,.2f}")
    print(f"    Cost per $1:         ${results.cost_per_dollar:.4f}")
    print(f"    Net Revenue:         ${float(results.total_collected) - float(results.total_cost):,.2f}")
    print(f"    Profit Margin:       {results.profit_margin*100:.1f}%")
    print(f"    ROI:                 {results.roi*100:.0f}%")

    print(f"\n  AGENT EFFICIENCY:")
    print(f"    Agents Deployed:     {results.num_agents:,}")
    print(f"    Accounts/Agent:      {results.avg_accounts_per_agent:,.0f}")
    print(f"    Collection/Agent:    ${results.avg_collection_per_agent:,.2f}")

    print(f"\n  SIMULATION STATS:")
    print(f"    Duration:            {duration:.1f} seconds")
    print(f"    Throughput:          {results.total_accounts/duration:,.0f} accounts/sec")
    print(f"    Days Simulated:      {results.simulation_days}")

    # Summary
    print("\n" + "=" * 80)
    target_recovery = 0.25
    if results.recovery_rate >= target_recovery:
        print(f"  STATUS: PASSED - Recovery rate {results.recovery_rate*100:.2f}% >= {target_recovery*100:.0f}% target")
    else:
        print(f"  STATUS: BELOW TARGET - Recovery rate {results.recovery_rate*100:.2f}% < {target_recovery*100:.0f}% target")

    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    # Parse args
    num_accounts = 1000000
    max_balance = 500

    if len(sys.argv) > 1:
        try:
            num_accounts = int(sys.argv[1])
        except ValueError:
            pass

    if len(sys.argv) > 2:
        try:
            max_balance = int(sys.argv[2])
        except ValueError:
            pass

    results = asyncio.run(run_bnpl_simulation(num_accounts, max_balance))
