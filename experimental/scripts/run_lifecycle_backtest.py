#!/usr/bin/env python3
"""
QUAN Lifecycle Backtest Runner

Comprehensive end-to-end backtest with:
- Efficiency analysis and bottleneck detection
- Scale testing with capacity planning
- Scope validation with coverage reporting

Usage:
    python run_lifecycle_backtest.py [options]

Options:
    --accounts N     Number of accounts (default: 10000)
    --agents N       Number of agents (default: 50)
    --scale-test     Enable scale testing
    --efficiency     Enable efficiency analysis
    --scope          Enable scope validation
    --all            Enable all analysis modes
    --json           Output results as JSON
"""

import asyncio
import argparse
import json
from datetime import datetime
from dataclasses import asdict
from decimal import Decimal


from quan.backtest.lifecycle_orchestrator import (
    LifecycleOrchestrator,
    run_lifecycle_backtest,
)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, 'value'):  # Enums
            return obj.value
        return super().default(obj)


def print_banner():
    """Print application banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗    ██████╗  █████╗  ██████╗██╗  ██╗   ║
║  ██╔═══██╗██║   ██║██╔══██╗████╗  ██║    ██╔══██╗██╔══██╗██╔════╝██║ ██╔╝   ║
║  ██║   ██║██║   ██║███████║██╔██╗ ██║    ██████╔╝███████║██║     █████╔╝    ║
║  ██║▄▄ ██║██║   ██║██╔══██║██║╚██╗██║    ██╔══██╗██╔══██║██║     ██╔═██╗    ║
║  ╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║    ██████╔╝██║  ██║╚██████╗██║  ██╗   ║
║   ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝   ║
║                                                                              ║
║                 LIFECYCLE BACKTEST & PROCESS MAPPING                         ║
║                                                                              ║
║  End-to-end testing for Efficiency, Scale, and Scope                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


def print_process_map():
    """Print the process map visualization"""
    print("""
┌──────────────────────────────────────────────────────────────────────────────┐
│                        END-TO-END LIFECYCLE PROCESS MAP                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INGESTION PHASE                                                             │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐                                │
│  │ ACQUIRE │ -> │ VALIDATE │ -> │ REGISTER │                                │
│  │ (API)   │    │ (Rules)  │    │ (Bureau) │                                │
│  └─────────┘    └──────────┘    └──────────┘                                │
│       │                              │                                       │
│       v                              v                                       │
│  SCORING PHASE                                                               │
│  ┌────────┐    ┌────────┐    ┌───────┐    ┌─────────┐                       │
│  │ LOCATE │ -> │ ENRICH │ -> │ SCORE │ -> │ SEGMENT │                       │
│  │ (Skip) │    │ (Data) │    │  (ML) │    │ (Strat) │                       │
│  └────────┘    └────────┘    └───────┘    └─────────┘                       │
│       │                                        │                             │
│       v                                        v                             │
│  CONTACT PHASE                                                               │
│  ┌─────────┐    ┌────────┐    ┌───────────┐                                 │
│  │ CONTACT │ -> │ ENGAGE │ -> │ FOLLOW_UP │                                 │
│  │ (Multi) │    │ (Agent)│    │  (Re-eng) │                                 │
│  └─────────┘    └────────┘    └───────────┘                                 │
│       │              │                                                       │
│       v              v                                                       │
│  NEGOTIATION PHASE                                                           │
│  ┌───────────┐    ┌─────────┐    ┌─────────┐                                │
│  │ NEGOTIATE │ -> │ COUNTER │ -> │ APPROVE │                                │
│  │  (Game)   │    │ (Offer) │    │ (Valid) │                                │
│  └───────────┘    └─────────┘    └─────────┘                                │
│       │                               │                                      │
│       v                               v                                      │
│  COLLECTION PHASE                                                            │
│  ┌─────────┐    ┌────────┐    ┌───────────┐                                 │
│  │ COLLECT │ -> │ VERIFY │ -> │ RECONCILE │                                 │
│  │ (Pay)   │    │ (Fraud)│    │  (Acct)   │                                 │
│  └─────────┘    └────────┘    └───────────┘                                 │
│       │                               │                                      │
│       v                               v                                      │
│  RESOLUTION PHASE                                                            │
│  ┌───────┐    ┌─────────┐    ┌────────┐                                     │
│  │ CLOSE │ -> │ RESTORE │ -> │ REPORT │                                     │
│  │ (End) │    │ (Credit)│    │(Bureau)│                                     │
│  └───────┘    └─────────┘    └────────┘                                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
    """)


def print_results(result, json_output=False):
    """Print backtest results"""

    if json_output:
        # Convert to JSON-serializable dict
        output = {
            "run_id": result.run_id,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "duration_seconds": result.duration_seconds,
            "num_accounts": result.num_accounts,
            "num_agents": result.num_agents,
            "scale_level": result.scale_level.value,
            "total_balance": float(result.total_balance),
            "total_collected": float(result.total_collected),
            "recovery_rate": result.recovery_rate,
            "key_findings": result.key_findings,
            "recommendations": result.recommendations,
        }

        if result.efficiency_report:
            output["efficiency"] = {
                "grade": result.efficiency_report.overall_grade.value,
                "score": result.efficiency_report.overall_score,
                "throughput": result.efficiency_report.actual_throughput,
                "roi": result.efficiency_report.roi,
                "bottlenecks": result.efficiency_report.bottlenecks,
            }

        if result.scale_report:
            output["scale"] = {
                "max_throughput": result.scale_report.max_throughput,
                "accounts_per_agent": result.scale_report.accounts_per_agent,
                "linear_scalability": result.scale_report.linear_scalability,
                "time_for_1m_hours": result.scale_report.time_to_process_1m_accounts_hours,
            }

        if result.scope_report:
            output["scope"] = {
                "feature_coverage": result.scope_report.feature_coverage_pct,
                "component_coverage": result.scope_report.integration_coverage_pct,
                "lifecycle_coverage": result.scope_report.lifecycle_coverage_pct,
                "compliance_coverage": result.scope_report.compliance_coverage_pct,
            }

        print(json.dumps(output, indent=2, cls=DecimalEncoder))
        return

    # Human-readable output
    print("\n" + "═" * 80)
    print("  BACKTEST RESULTS")
    print("═" * 80)

    print(f"""
  Run ID:        {result.run_id}
  Duration:      {result.duration_seconds:.1f} seconds
  Accounts:      {result.num_accounts:,}
  Agents:        {result.num_agents}
  Scale Level:   {result.scale_level.value.upper()}
    """)

    print("─" * 80)
    print("  CORE METRICS")
    print("─" * 80)
    print(f"""
  Total Balance:    ${result.total_balance:>12,.2f}
  Total Collected:  ${result.total_collected:>12,.2f}
  Recovery Rate:    {result.recovery_rate:>12.1%}
    """)

    if result.efficiency_report:
        e = result.efficiency_report
        print("─" * 80)
        print("  EFFICIENCY ANALYSIS")
        print("─" * 80)
        print(f"""
  Overall Grade:        {e.overall_grade.value}
  Overall Score:        {e.overall_score:.1f}/100

  Throughput:
    Actual:             {e.actual_throughput:,.0f} accounts/sec
    Target:             {e.target_throughput:,.0f} accounts/sec
    Utilization:        {e.throughput_utilization:.1%}

  Latency:
    Actual:             {e.actual_latency_ms:.0f}ms
    Target:             {e.target_latency_ms:.0f}ms

  Cost Efficiency:
    Cost per $1:        ${e.cost_per_dollar_collected:.2f}
    ROI:                {e.roi:.1%}
        """)

        if e.bottlenecks:
            print("  Bottlenecks Identified:")
            for b in e.bottlenecks[:5]:
                print(f"    • {b}")

        if e.optimizations:
            print("\n  Optimization Opportunities:")
            for o in e.optimizations[:5]:
                print(f"    • {o}")

    if result.scale_report:
        s = result.scale_report
        print("\n" + "─" * 80)
        print("  SCALE ANALYSIS")
        print("─" * 80)
        print(f"""
  Max Throughput:           {s.max_throughput:,.0f} accounts/sec
  Accounts per Agent:       {s.accounts_per_agent:.0f}
  Linear Scalability:       {s.linear_scalability:.0%}
  Horizontal Scaling:       {s.horizontal_scaling_factor:.0%}

  Capacity Planning:
    Time for 1M accounts:   {s.time_to_process_1m_accounts_hours:.1f} hours
    Est. CPU Cores:         {s.estimated_cpu_cores}
    Est. Memory (GB):       {s.estimated_memory_gb:.1f}
        """)

        if s.scaling_recommendations:
            print("  Scaling Recommendations:")
            for r in s.scaling_recommendations:
                print(f"    • {r}")

    if result.scope_report:
        c = result.scope_report
        print("\n" + "─" * 80)
        print("  SCOPE COVERAGE")
        print("─" * 80)
        print(f"""
  Feature Coverage:        {c.feature_coverage_pct:.1f}%  ({c.features_tested}/{c.total_features})
  Component Coverage:      {c.integration_coverage_pct:.1f}%  ({c.components_integrated}/{c.total_components})
  Lifecycle Coverage:      {c.lifecycle_coverage_pct:.1f}%  ({c.phases_covered}/{c.total_phases})
  Compliance Coverage:     {c.compliance_coverage_pct:.1f}%  ({c.compliance_rules_validated}/{c.compliance_rules_total})
  Edge Case Coverage:      {c.edge_case_coverage_pct:.1f}%  ({c.edge_cases_tested}/{c.edge_cases_total})
        """)

        if c.coverage_gaps:
            print("  Coverage Gaps:")
            for g in c.coverage_gaps:
                print(f"    • {g}")

    print("\n" + "─" * 80)
    print("  KEY FINDINGS")
    print("─" * 80)
    for finding in result.key_findings:
        print(f"  • {finding}")

    print("\n" + "─" * 80)
    print("  RECOMMENDATIONS")
    print("─" * 80)
    for rec in result.recommendations[:10]:
        print(f"  • {rec}")

    print("\n" + "═" * 80)
    print("  BACKTEST COMPLETE")
    print("═" * 80 + "\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="QUAN Lifecycle Backtest Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--accounts", "-a",
        type=int,
        default=10_000,
        help="Number of accounts to simulate (default: 10000)"
    )
    parser.add_argument(
        "--agents", "-g",
        type=int,
        default=50,
        help="Number of concurrent agents (default: 50)"
    )
    parser.add_argument(
        "--scale-test", "-s",
        action="store_true",
        help="Enable scale testing analysis"
    )
    parser.add_argument(
        "--efficiency", "-e",
        action="store_true",
        help="Enable efficiency analysis"
    )
    parser.add_argument(
        "--scope", "-c",
        action="store_true",
        help="Enable scope validation"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enable all analysis modes"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress banner and process map"
    )

    args = parser.parse_args()

    # Default to all if no specific mode selected
    if not any([args.scale_test, args.efficiency, args.scope, args.all]):
        args.all = True

    if args.all:
        args.scale_test = True
        args.efficiency = True
        args.scope = True

    if not args.quiet and not args.json:
        print_banner()
        print_process_map()

    # Run backtest
    orchestrator = LifecycleOrchestrator()

    print(f"\nStarting backtest with {args.accounts:,} accounts and {args.agents} agents...\n")

    result = await orchestrator.run_comprehensive_backtest(
        num_accounts=args.accounts,
        num_agents=args.agents,
        scale_test=args.scale_test,
        efficiency_analysis=args.efficiency,
        scope_validation=args.scope,
    )

    print_results(result, json_output=args.json)

    return result


if __name__ == "__main__":
    asyncio.run(main())
