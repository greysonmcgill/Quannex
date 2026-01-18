#!/usr/bin/env python3
"""
QUAN Business Plan Generator

Interactive tool for creating comprehensive business plans.

Usage:
    python build_business_plan.py              # Full interactive mode
    python build_business_plan.py --demo       # Demo with QUAN Recovery data
    python build_business_plan.py --help       # Show help
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from business_plan_generator.models import (
    BusinessPlan, CompanyInfo, Problem, Solution, MarketAnalysis,
    MarketSegment, CompetitiveAnalysis, Competitor, BusinessModel,
    RevenueStream, FinancialProjections, YearProjection, GoToMarket,
    GoToMarketPhase, TeamInfo, TeamMember, OpenPosition, FundingRequirements,
    FundingRound, RiskAnalysis, Risk, ExitStrategy, ExitScenario,
    BusinessStage, Industry, RevenueModel,
)
from business_plan_generator.prompts import InteractivePrompter
from business_plan_generator.pdf_generator import PDFGenerator


def create_quan_demo_plan() -> BusinessPlan:
    """Create demo plan with QUAN Recovery data"""

    plan = BusinessPlan()

    # Company
    plan.company = CompanyInfo(
        name="QUAN Recovery",
        tagline="Quantum Intelligence for Micro-Debt Collection",
        description=(
            "QUAN Recovery is revolutionizing the debt collection industry by making "
            "sub-$1,000 debt collection profitable for the first time in history. "
            "Using quantum-inspired AI technology, we achieve 35% recovery rates on "
            "debt that traditional collectors abandon due to negative unit economics."
        ),
        industry=Industry.FINTECH,
        stage=BusinessStage.SEED,
        founder_name="Greyson McGill",
        founder_title="Founder & CEO",
        founder_email="greyson@quanrecovery.com",
        website="quanrecovery.com",
        primary_color="#6B46FF",
        secondary_color="#00D4FF",
    )

    # Problem
    plan.problem = Problem(
        headline="$400 billion in micro-debt is written off annually",
        description=(
            "Traditional debt collection costs $47 per account, making it impossible "
            "to profitably collect on balances under $1,000. BNPL providers, banks, "
            "and digital services hemorrhage billions in uncollected micro-debt."
        ),
        pain_points=[
            "Human collection costs ($47) exceed recovery value on small balances",
            "BNPL providers losing billions to uncollected micro-debt",
            "Only 12% of agencies accept accounts under $500",
            "Collection economics fundamentally broken for micro-debt",
        ],
        current_solutions=[
            "Write off the debt entirely",
            "Sell to debt buyers at pennies on the dollar",
            "Basic automated emails with poor results",
        ],
        why_inadequate=(
            "Current solutions either accept 100% loss or recover only 5-10% "
            "of micro-debt value. No one has solved the unit economics problem."
        ),
        market_impact="$400B written off annually",
    )

    # Solution
    plan.solution = Solution(
        headline="AI-powered collection that costs $0.50 per account",
        description=(
            "QUAN's AI platform reduces collection costs to $0.50 per account while "
            "achieving 35% recovery rates through automated omnichannel campaigns "
            "and behavioral intelligence. We transform worthless debt into profitable assets."
        ),
        key_features=[
            "Quantum-inspired portfolio analysis",
            "AI-powered omnichannel outreach (SMS, email, voice)",
            "Behavioral prediction with 89% accuracy",
            "Real-time compliance engine (FDCPA/TCPA)",
            "Dynamic settlement optimization",
            "Instant payment processing",
        ],
        differentiators=[
            "97% profit margins through complete automation",
            "Quantum intelligence analyzes portfolios holistically",
            "First-mover advantage in abandoned micro-debt market",
            "Compliance built-in from day 1",
        ],
        technology=[
            "Quantum-inspired machine learning",
            "Graph neural networks for behavioral analysis",
            "Transformer-based negotiation AI",
            "Distributed processing (Ray, Kafka)",
        ],
        how_it_works=(
            "1. ACQUIRE: Ingest portfolio, score accounts, rank by recovery potential\n"
            "2. LOCATE: Skip trace, verify contacts, determine best channel\n"
            "3. CONTACT: AI outreach with escalating frequency, channel rotation\n"
            "4. NEGOTIATE: Push for max recovery, counter settlements high\n"
            "5. COLLECT: Capture payment, process, retry failures\n"
            "6. CLOSE: Monitor plans, book revenue on completion"
        ),
    )

    # Market
    plan.market = MarketAnalysis(
        tam=100.0,
        sam=30.0,
        som=3.0,
        tam_description="Total micro-debt market ($100B+)",
        sam_description="US BNPL and digital banking micro-debt",
        som_description="Target capture in 5 years",
        segments=[
            MarketSegment("BNPL Defaults", 4.0, 40.0, "Klarna, Affirm, Afterpay charge-offs"),
            MarketSegment("Credit Card <$1K", 28.0, 5.0, "Small balance charge-offs from major banks"),
            MarketSegment("Overdrafts/NSF", 15.0, 3.0, "Uncollected overdraft and NSF fees"),
            MarketSegment("Digital Subscriptions", 36.0, 25.0, "Streaming, SaaS, subscription churn"),
        ],
        growth_drivers=[
            "BNPL market growing 40% annually",
            "AI costs dropped 90% in 24 months",
            "Regulation F legitimized digital collection",
            "150 million Americans with BNPL accounts",
        ],
        key_statistics={
            "Klarna Credit Losses": "€1.07B (2022)",
            "Affirm Charge-offs": "$434.8M (FY2023)",
            "JPMorgan Write-offs": "$5.2B (2023)",
            "Agencies accepting <$500": "Only 12%",
        },
    )

    # Competition
    plan.competition = CompetitiveAnalysis(
        direct_competitors=[
            Competitor(
                name="Traditional Agencies (Encore, PRA)",
                description="Large collection agencies focused on $1,000+ debt",
                strengths=["Scale", "Established relationships"],
                weaknesses=["High costs", "Can't do micro-debt profitably"],
                market_position="Market Leader",
                why_we_win="They can't compete in micro-debt economics",
            ),
            Competitor(
                name="BNPL In-House",
                description="Klarna, Affirm internal collection",
                strengths=["Data access", "Customer relationship"],
                weaknesses=["Not core competency", "Brand risk"],
                market_position="Challenger",
                why_we_win="We're specialists they can outsource to",
            ),
        ],
        competitive_advantages=[
            "97% margins vs industry losses",
            "Quantum analysis genuinely novel",
            "2-year head start in virgin market",
        ],
        moats=[
            "Economic moat: Profitable where others lose money",
            "Technical moat: Proprietary quantum-inspired AI",
            "Network effects: Every account improves the AI",
            "Regulatory moat: Compliance built-in",
        ],
        positioning_statement=(
            "For BNPL providers and digital banks losing billions to micro-debt, "
            "QUAN Recovery is the only AI-powered collection platform that makes "
            "sub-$1,000 debt profitable with 35% recovery rates at $0.50 per account."
        ),
    )

    # Business Model
    plan.business_model = BusinessModel(
        revenue_model=RevenueModel.CONTINGENCY,
        revenue_streams=[
            RevenueStream(
                name="Collection Fees",
                description="30% contingency on amounts collected",
                model=RevenueModel.CONTINGENCY,
                percentage_of_total=60.0,
                pricing="30% of collected amount",
            ),
            RevenueStream(
                name="Debt Purchase",
                description="Purchase and collect on portfolios",
                model=RevenueModel.CONTINGENCY,
                percentage_of_total=25.0,
                pricing="5-10 cents per dollar of face value",
            ),
            RevenueStream(
                name="SaaS Platform",
                description="Self-service platform for smaller clients",
                model=RevenueModel.SAAS_SUBSCRIPTION,
                percentage_of_total=10.0,
                pricing="$499-2,499/month",
            ),
            RevenueStream(
                name="Data Services",
                description="Anonymized insights and benchmarking",
                model=RevenueModel.LICENSING,
                percentage_of_total=5.0,
                pricing="Custom pricing",
            ),
        ],
        unit_economics={
            "avg_balance": 400,
            "recovery_rate": 0.35,
            "revenue_per_account": 42,
            "cost_per_account": 0.50,
            "profit_per_account": 41.50,
            "margin": 98.8,
            "roi": 8300,
        },
        gross_margin=0.97,
        pricing_strategy="30% contingency with volume discounts for large portfolios",
    )

    # Financials
    plan.financials = FinancialProjections(
        projections=[
            YearProjection(1, Decimal("625000"), Decimal("500000"), Decimal("350000"),
                          Decimal("150000"), employees=3, customers=10),
            YearProjection(2, Decimal("7000000"), Decimal("5600000"), Decimal("2800000"),
                          Decimal("2800000"), employees=15, customers=75),
            YearProjection(3, Decimal("42000000"), Decimal("35000000"), Decimal("14000000"),
                          Decimal("21000000"), employees=45, customers=300),
            YearProjection(4, Decimal("180000000"), Decimal("155000000"), Decimal("45000000"),
                          Decimal("110000000"), employees=120, customers=1000),
            YearProjection(5, Decimal("540000000"), Decimal("470000000"), Decimal("90000000"),
                          Decimal("380000000"), employees=250, customers=2500),
        ],
        assumptions=[
            "Recovery rates improve with AI learning and scale",
            "Gross margins remain 80%+ due to automation",
            "Customer acquisition cost decreases with brand recognition",
            "Technology investment front-loaded in early years",
            "International expansion begins Year 4",
        ],
    )

    # Go-to-Market
    plan.gtm = GoToMarket(
        phases=[
            GoToMarketPhase(
                name="BNPL Beachhead",
                timeline="Months 1-6",
                target_customers=["Sezzle", "Perpay", "Splitit", "Tier 2 BNPL providers"],
                strategies=[
                    "Risk-free pilots: 'We collect 35% or you pay nothing'",
                    "Build case studies from successful recoveries",
                    "Leverage success to approach Klarna, Affirm, Afterpay",
                ],
                milestones=["First 10 clients", "$100K MRR"],
            ),
            GoToMarketPhase(
                name="Digital Banks & Fintechs",
                timeline="Months 7-12",
                target_customers=["Chime", "Varo", "Current", "Neo-banks"],
                strategies=[
                    "Expand to overdraft and NSF fee recovery",
                    "Develop specialized subscription solutions",
                ],
                milestones=["50 clients", "$1M MRR"],
            ),
            GoToMarketPhase(
                name="Enterprise Expansion",
                timeline="Year 2+",
                target_customers=["Major banks", "Credit unions", "Telecom", "Healthcare"],
                strategies=[
                    "Enterprise sales team",
                    "Strategic partnerships",
                ],
                milestones=["1000 clients", "$10M ARR"],
            ),
        ],
        key_value_propositions=[
            "Turn your $0 write-offs into 35% recovery",
            "No upfront costs - pay only on success",
            "100% compliant with zero CFPB risk",
            "7-day average resolution time",
        ],
    )

    # Team
    plan.team = TeamInfo(
        founders=[
            TeamMember(
                name="Greyson McGill",
                title="Founder & CEO",
                bio=(
                    "Entrepreneur exploring opportunities at the intersection of AI and "
                    "financial infrastructure. Identified the micro-debt gap through "
                    "comprehensive market research and analysis of the $400B abandoned debt market."
                ),
            ),
        ],
        open_positions=[
            OpenPosition("Chief Technology Officer", "AI/ML expert from FAANG or leading fintech", "Critical", "Q1"),
            OpenPosition("VP Compliance", "Former CFPB or state regulator with FDCPA expertise", "Critical", "Q1"),
            OpenPosition("VP Sales", "Existing relationships with BNPL providers", "High", "Q2"),
            OpenPosition("VP Engineering", "Scaled systems to millions of transactions", "High", "Q2"),
        ],
    )

    # Funding
    plan.funding = FundingRequirements(
        current_round=FundingRound(
            round_name="Seed",
            amount=Decimal("2000000"),
            timing="Now",
            use_of_funds=[
                "MVP development and compliance infrastructure",
                "First 3 key hires (CTO, VP Compliance, VP Sales)",
                "Initial client acquisition and pilots",
                "18 months runway",
            ],
            milestones=[
                "$100K MRR",
                "10 active clients",
                "35% recovery rate validated",
            ],
        ),
        future_rounds=[
            FundingRound("Series A", Decimal("15000000"), "Month 9",
                        ["Scale operations", "Platform build-out"], ["$1M MRR", "50 clients"]),
            FundingRound("Series B", Decimal("50000000"), "Month 20",
                        ["Market expansion", "Bureau integration"], ["$10M ARR"]),
        ],
    )

    # Risks
    plan.risks = RiskAnalysis(
        risks=[
            Risk("Regulatory", "FDCPA/TCPA changes could impact operations",
                 "Medium", "High", "Compliance-first design, legal counsel, conservative approach"),
            Risk("Market", "Lower than projected recovery rates",
                 "Medium", "Medium", "Conservative projections, multiple revenue streams"),
            Risk("Competition", "BNPL providers build in-house",
                 "Low", "High", "Fast execution, exclusive contracts, superior results"),
            Risk("Technology", "AI model performance issues",
                 "Low", "Medium", "Redundant systems, extensive testing, gradual rollout"),
            Risk("Execution", "Unable to hire key talent",
                 "Medium", "Medium", "Competitive compensation, equity incentives, remote options"),
        ],
    )

    # Exit
    plan.exit_strategy = ExitStrategy(
        scenarios=[
            ExitScenario(
                type="Strategic Acquisition",
                probability=0.60,
                timeline="Years 5-7",
                potential_acquirers=["Experian", "TransUnion", "Visa", "Mastercard", "Klarna", "Affirm"],
                valuation_range="$1.5-2.5B",
                rationale="Strategic value of micro-debt data and infrastructure",
            ),
            ExitScenario(
                type="Private Equity",
                probability=0.25,
                timeline="Years 5-7",
                potential_acquirers=["Vista Equity", "Thoma Bravo"],
                valuation_range="$3-4.5B (8-12x EBITDA)",
                rationale="Platform play to consolidate collection agencies",
            ),
            ExitScenario(
                type="IPO",
                probability=0.10,
                timeline="Years 7-10",
                potential_acquirers=[],
                valuation_range="$5-10B",
                rationale="Scale and market position warrant public offering",
            ),
        ],
    )

    # Executive Summary
    plan.executive_summary = (
        "QUAN Recovery is revolutionizing the debt collection industry by making sub-$1,000 "
        "debt collection profitable for the first time in history. Using quantum-inspired AI "
        "technology, we achieve 35% recovery rates on debt that traditional collectors abandon "
        "due to negative unit economics.\n\n"
        "<b>The Problem:</b> $400 billion in micro-debt is written off annually because human "
        "collection costs ($47) exceed recovery value on small balances.\n\n"
        "<b>Our Solution:</b> QUAN's AI platform reduces collection costs to $0.50 per account "
        "while achieving 35% recovery rates through automated omnichannel campaigns.\n\n"
        "<b>Market Opportunity:</b> $100B+ TAM with massive growth from BNPL expansion.\n\n"
        "<b>Competitive Advantage:</b> 97% profit margins through complete automation and "
        "first-mover advantage in an abandoned market.\n\n"
        "<b>The Ask:</b> $2M Seed round to build MVP and acquire first 10 clients."
    )

    return plan


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Business Plan Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate demo plan with QUAN Recovery data",
    )

    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="Output directory (default: ./output)",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    if args.demo:
        print("\n" + "=" * 60)
        print("  BUSINESS PLAN GENERATOR - DEMO MODE")
        print("=" * 60)
        print("\nGenerating QUAN Recovery business plan...")

        plan = create_quan_demo_plan()

        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = output_dir / f"QUAN_Recovery_Business_Plan_{timestamp}.pdf"

        generator = PDFGenerator(plan)
        generator.generate(str(pdf_path))

        print(f"\n✓ PDF generated: {pdf_path}")
        print("\n" + "=" * 60)
        print("  DEMO COMPLETE")
        print("=" * 60 + "\n")

    else:
        print("\n" + "=" * 60)
        print("  BUSINESS PLAN GENERATOR")
        print("=" * 60)
        print("\nBuild a comprehensive business plan through guided prompts.\n")
        print("Press Enter to use default/suggested values.")
        print("Type 'skip' to skip optional sections.")
        print("Type 'back' to return to previous section.")
        print("-" * 60)

        # Interactive mode
        prompter = InteractivePrompter()
        plan = prompter.build_plan()

        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company_name = plan.company.name if plan.company else "Business_Plan"
        company_slug = company_name.replace(" ", "_")
        pdf_path = output_dir / f"{company_slug}_{timestamp}.pdf"

        generator = PDFGenerator(plan)
        generator.generate(str(pdf_path))

        print(f"\n✓ PDF generated: {pdf_path}")
        print("\n" + "=" * 60)
        print("  BUSINESS PLAN COMPLETE")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
