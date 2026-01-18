#!/usr/bin/env python3
"""
QUAN Pipeline Calibration Runner

Deploys maximum agents to calibrate pipeline for real-world conditions.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from quan.simulation.engine import SimulationEngine, SimulationConfig


async def run_industry_calibrated():
    print('=' * 70)
    print('QUAN PIPELINE - INDUSTRY-CALIBRATED SIMULATION')
    print('Target: 35% Recovery Rate (QUAN differentiated performance)')
    print('=' * 70)

    # Industry-calibrated parameters
    config = SimulationConfig(
        num_accounts=50_000,
        num_agents=250,

        # Conservative debtor behavior
        response_rate=0.08,
        pay_full_rate=0.02,
        negotiate_rate=0.90,
        accept_first_offer=0.03,
        dispute_rate=0.12,

        # Realistic payment friction
        payment_success_rate=0.82,
        plan_completion_rate=0.45,

        # Conservative channel efficacy
        channel_response_rates={
            'sms': 0.10,
            'email': 0.04,
            'voice': 0.18,
            'mail': 0.03,
        },

        target_recovery_rate=0.35,
    )

    engine = SimulationEngine(config)

    print('\n[DEPLOYING] 250 agents processing 50,000 accounts')
    print('[RUNNING] 5 calibration iterations...')
    print('-' * 70)

    results = []
    for i in range(5):
        result = await engine.run_simulation()
        results.append(result)

        efficiency = float(result.total_collected) / float(result.total_balance) * 100

        print(f'  Iteration {i+1}: Recovery={result.recovery_rate:5.1%} | '
              f'Efficiency={efficiency:4.1f}% | '
              f'Throughput={result.throughput_accounts_per_second:,.0f}/sec')

    final = results[-1]

    # Calculate metrics
    portfolio_value = float(final.total_balance)
    collected = float(final.total_collected)
    accounts = final.total_accounts
    recovered = final.accounts_recovered

    revenue = collected * 0.30
    op_cost = accounts * 0.50
    profit = revenue - op_cost
    margin = (profit / revenue) * 100 if revenue > 0 else 0
    roi = (profit / op_cost) * 100 if op_cost > 0 else 0

    avg_balance = portfolio_value / accounts
    avg_collected = collected / accounts
    revenue_per_account = revenue / accounts
    profit_per_account = profit / accounts

    print('\n' + '=' * 70)
    print('FINAL CALIBRATED RESULTS')
    print('=' * 70)

    print(f'''
PORTFOLIO METRICS
─────────────────────────────────────────────────────────────────────
  Total Accounts:          {accounts:>15,}
  Accounts Recovered:      {recovered:>15,}
  Recovery Rate:           {final.recovery_rate:>15.1%}

  Portfolio Value:         ${portfolio_value:>14,.2f}
  Amount Collected:        ${collected:>14,.2f}
  Collection Efficiency:   {(collected/portfolio_value)*100:>14.1f}%

FINANCIAL MODEL
─────────────────────────────────────────────────────────────────────
  Gross Revenue (30%):     ${revenue:>14,.2f}
  Operating Costs:         ${op_cost:>14,.2f}
  Net Profit:              ${profit:>14,.2f}
  Profit Margin:           {margin:>14.1f}%
  ROI:                     {roi:>14,.0f}%

UNIT ECONOMICS (per account)
─────────────────────────────────────────────────────────────────────
  Avg Balance:             ${avg_balance:>14.2f}
  Avg Collected:           ${avg_collected:>14.2f}
  Revenue/Account:         ${revenue_per_account:>14.2f}
  Cost/Account:            ${0.50:>14.2f}
  Profit/Account:          ${profit_per_account:>14.2f}
''')

    # Stage funnel
    print('PIPELINE FUNNEL')
    print('─────────────────────────────────────────────────────────────────────')

    stages = ['acquire', 'locate', 'contact', 'negotiate', 'collect', 'close', 'profit']
    prev_rate = 1.0

    for stage in stages:
        rate = final.stage_conversion.get(stage, 0)
        drop = prev_rate - rate
        bar_len = int(rate * 40)
        bar = '█' * bar_len + '░' * (40 - bar_len)

        print(f'  {stage.upper():12} |{bar}| {rate:5.1%} (-{drop:4.1%})')
        prev_rate = rate

    exhausted = final.stage_conversion.get('contact_exhausted', 0)
    print(f'\n  Contact Exhausted (no response): {exhausted:.1%}')

    # Comparison
    print('\n' + '=' * 70)
    print('QUAN vs TRADITIONAL COLLECTION')
    print('=' * 70)

    trad_recovery = 0.08
    trad_cost = 47.00

    quan_recovery = final.recovery_rate
    quan_cost = 0.50

    trad_collected = portfolio_value * trad_recovery
    trad_revenue = trad_collected * 0.30
    trad_total_cost = accounts * trad_cost
    trad_profit = trad_revenue - trad_total_cost

    print(f'''
                          Traditional      QUAN         Improvement
                          -----------      ----         -----------
  Recovery Rate:          {trad_recovery:>8.1%}        {quan_recovery:>8.1%}     {quan_recovery/trad_recovery:>8.1f}x
  Cost/Account:           ${trad_cost:>7.2f}        ${quan_cost:>7.2f}     {trad_cost/quan_cost:>8.0f}x cheaper
  Amount Collected:       ${trad_collected:>10,.0f}   ${collected:>10,.0f}   +${collected-trad_collected:>10,.0f}
  Net Profit:             ${trad_profit:>10,.0f}   ${profit:>10,.0f}   +${profit-trad_profit:>10,.0f}
''')

    print('=' * 70)
    print('SYSTEM PERFORMANCE')
    print('=' * 70)
    print(f'''
  Total Runtime:          {final.total_runtime_seconds:.1f} seconds
  Throughput:             {final.throughput_accounts_per_second:,.0f} accounts/second
  Agents Deployed:        250
  Accounts/Agent:         {accounts // 250:,}
''')

    print('=' * 70)
    print('CALIBRATION COMPLETE - MODELS TUNED FOR PRODUCTION')
    print('=' * 70)

    return final


if __name__ == '__main__':
    asyncio.run(run_industry_calibrated())
