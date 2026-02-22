#!/usr/bin/env python3
"""
Collections Test Runner

Runs collections simulation on 10,000 accounts across all debt types.
"""

import asyncio
import sys
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, '/home/user/Quan')

from quan.models.micro_loan_universe import DebtType, MicroLoanUniverseGenerator, MICRO_LOAN_UNIVERSE
from quan.simulation.full_scale_simulation import ScaleConfig, FullScaleSimulator


async def run_collections_test(num_accounts: int = 10000):
    """Run collections test on specified number of accounts"""

    print("=" * 80)
    print("  QUAN RECOVERY - COLLECTIONS TEST")
    print(f"  Testing with {num_accounts:,} accounts across all debt types")
    print("=" * 80)
    print(f"\n  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # List available debt types
    print(f"\n  DEBT TYPES INCLUDED:")
    for dt in DebtType:
        profile = MICRO_LOAN_UNIVERSE.get(dt)
        if profile:
            print(f"    - {profile.name} ({dt.value}): "
                  f"avg balance ${profile.avg_balance:,.2f}, "
                  f"base recovery {profile.base_recovery_rate*100:.0f}%")

    # Configure simulation for 10,000 accounts
    # Scale agents proportionally (1 agent per 100 accounts)
    num_agents = max(10, num_accounts // 100)

    config = ScaleConfig(
        num_agents=num_agents,
        total_accounts=num_accounts,
        simulation_days=90,  # 3 months
        max_contact_attempts=8,
        max_payment_retries=3,
        re_engagement_threshold_days=14,
        max_re_engagement_campaigns=3,
        cost_per_contact=Decimal("0.10"),
        cost_per_payment_attempt=Decimal("0.20"),
        cost_per_re_engagement=Decimal("0.40"),
        cost_per_agent_day=Decimal("150"),
    )

    print(f"\n  SIMULATION CONFIGURATION:")
    print(f"    Accounts:           {config.total_accounts:,}")
    print(f"    Agents:             {config.num_agents}")
    print(f"    Duration:           {config.simulation_days} days")
    print(f"    Max contacts:       {config.max_contact_attempts}")
    print(f"    Re-engagement max:  {config.max_re_engagement_campaigns}")

    print(f"\n  Running simulation...")
    print("  " + "-" * 76)

    # Run simulation
    simulator = FullScaleSimulator(config)
    results = await simulator.run_simulation()

    # Print results
    print("\n" + "=" * 80)
    print("  TEST RESULTS")
    print("=" * 80)

    print(f"\n  PORTFOLIO SUMMARY:")
    print(f"    Total Accounts:      {results.total_accounts:,}")
    print(f"    Total Balance:       ${results.total_balance:,.2f}")
    print(f"    Avg Balance:         ${float(results.total_balance)/results.total_accounts:,.2f}")

    print(f"\n  COLLECTION PERFORMANCE:")
    print(f"    Total Collected:     ${results.total_collected:,.2f}")
    print(f"    Recovery Rate:       {results.recovery_rate*100:.1f}%")
    print(f"    Accounts Closed:     {results.accounts_collected:,} ({results.accounts_collected/results.total_accounts*100:.1f}%)")
    print(f"    Partial Payments:    {results.accounts_partial:,} ({results.accounts_partial/results.total_accounts*100:.1f}%)")
    print(f"    Uncollected:         {results.accounts_uncollected:,} ({results.accounts_uncollected/results.total_accounts*100:.1f}%)")

    print(f"\n  ACTIVITY METRICS:")
    print(f"    Total Contacts:      {results.total_contacts:,}")
    print(f"    Re-engagements:      {results.total_re_engagements:,}")
    print(f"    Contacts/Account:    {results.total_contacts/results.total_accounts:.1f}")
    print(f"    Simulation Days:     {results.simulation_days}")

    print(f"\n  FINANCIAL PERFORMANCE:")
    print(f"    Total Cost:          ${results.total_cost:,.2f}")
    print(f"    Cost per $1:         ${results.cost_per_dollar:.3f}")
    print(f"    Profit Margin:       {results.profit_margin*100:.1f}%")
    print(f"    ROI:                 {results.roi*100:.0f}%")

    print(f"\n  AGENT EFFICIENCY:")
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

    print("  " + "-" * 76)

    # Summary status
    print(f"\n  TEST STATUS: ", end="")
    if results.recovery_rate >= 0.25:
        print("PASSED - Recovery rate meets threshold (>=25%)")
    else:
        print(f"BELOW TARGET - Recovery rate {results.recovery_rate*100:.1f}% < 25%")

    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return results


if __name__ == "__main__":
    # Parse command line args for custom account count
    num_accounts = 10000
    if len(sys.argv) > 1:
        try:
            num_accounts = int(sys.argv[1])
        except ValueError:
            print(f"Invalid account count: {sys.argv[1]}, using default 10000")

    results = asyncio.run(run_collections_test(num_accounts))
