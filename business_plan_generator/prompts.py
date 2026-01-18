"""
Interactive Business Plan Prompter

Guides users through creating comprehensive business plans with
intelligent prompts and suggestions.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import json

from business_plan_generator.models import (
    BusinessPlan, CompanyInfo, Problem, Solution, MarketAnalysis,
    MarketSegment, CompetitiveAnalysis, Competitor, BusinessModel,
    RevenueStream, FinancialProjections, YearProjection, GoToMarket,
    GoToMarketPhase, TeamInfo, TeamMember, OpenPosition, FundingRequirements,
    FundingRound, RiskAnalysis, Risk, ExitStrategy, ExitScenario, Appendix,
    BusinessStage, Industry, RevenueModel,
)


@dataclass
class PromptResult:
    """Result from a prompt"""
    value: Any
    skipped: bool = False
    error: Optional[str] = None


class InteractivePrompter:
    """
    Interactive system for building business plans through guided prompts.

    Provides intelligent defaults, suggestions, and validation.
    """

    def __init__(self, input_func: Callable = None, print_func: Callable = None):
        self.input_func = input_func or input
        self.print_func = print_func or print
        self.plan = BusinessPlan()

    def print(self, *args, **kwargs):
        """Print wrapper"""
        self.print_func(*args, **kwargs)

    def input(self, prompt: str) -> str:
        """Input wrapper"""
        return self.input_func(prompt)

    def build_plan(self) -> BusinessPlan:
        """
        Main entry point - guides user through entire business plan.
        """
        self._print_header("BUSINESS PLAN BUILDER")
        self.print("Let's build your business plan step by step.\n")
        self.print("Press Enter to use default/suggested values.")
        self.print("Type 'skip' to skip optional sections.")
        self.print("Type 'back' to go to previous section.")
        self.print("-" * 60)

        sections = [
            ("Company Information", self._prompt_company),
            ("Problem Statement", self._prompt_problem),
            ("Solution", self._prompt_solution),
            ("Market Analysis", self._prompt_market),
            ("Competitive Analysis", self._prompt_competition),
            ("Business Model", self._prompt_business_model),
            ("Financial Projections", self._prompt_financials),
            ("Go-to-Market Strategy", self._prompt_gtm),
            ("Team", self._prompt_team),
            ("Funding Requirements", self._prompt_funding),
            ("Risk Analysis", self._prompt_risks),
            ("Exit Strategy", self._prompt_exit),
        ]

        section_idx = 0
        while section_idx < len(sections):
            name, func = sections[section_idx]

            self._print_section_header(f"SECTION {section_idx + 1}: {name}")

            try:
                result = func()

                if result == "back" and section_idx > 0:
                    section_idx -= 1
                    continue

                section_idx += 1

            except KeyboardInterrupt:
                self.print("\n\nPlan building interrupted. Progress saved.")
                break

        # Generate executive summary
        self._generate_executive_summary()

        self._print_header("BUSINESS PLAN COMPLETE")
        self._print_completion_status()

        return self.plan

    # =========================================================================
    # SECTION 1: Company Information
    # =========================================================================

    def _prompt_company(self) -> Optional[str]:
        """Prompt for company information"""

        name = self._prompt_required("Company Name")
        if name == "back":
            return "back"

        tagline = self._prompt_with_suggestion(
            "Tagline/Slogan",
            f"AI-Powered {self._guess_industry_term(name)}"
        )

        # Industry selection
        self.print("\nSelect your industry:")
        for i, ind in enumerate(Industry, 1):
            self.print(f"  {i}. {ind.value}")

        industry_idx = self._prompt_number("Industry", 1, len(Industry), 1)
        industry = list(Industry)[industry_idx - 1]

        # Stage selection
        self.print("\nSelect your business stage:")
        for i, stage in enumerate(BusinessStage, 1):
            self.print(f"  {i}. {stage.value.replace('_', ' ').title()}")

        stage_idx = self._prompt_number("Stage", 1, len(BusinessStage), 1)
        stage = list(BusinessStage)[stage_idx - 1]

        description = self._prompt_multiline(
            "Company Description (2-3 sentences)",
            f"{name} is revolutionizing the {industry.value.lower()} industry..."
        )

        # Founder info
        self._print_subsection("Founder Information")

        founder_name = self._prompt_with_default("Founder Name", "")
        founder_title = self._prompt_with_default("Title", "Founder & CEO")
        founder_email = self._prompt_with_default("Email", f"{founder_name.lower().split()[0] if founder_name else 'contact'}@{name.lower().replace(' ', '')}.com")

        # Brand colors
        self._print_subsection("Brand Colors (hex codes)")
        primary_color = self._prompt_with_default("Primary Color", "#6B46FF")
        secondary_color = self._prompt_with_default("Secondary Color", "#00D4FF")

        self.plan.company = CompanyInfo(
            name=name,
            tagline=tagline,
            description=description,
            industry=industry,
            stage=stage,
            founder_name=founder_name,
            founder_title=founder_title,
            founder_email=founder_email,
            primary_color=primary_color,
            secondary_color=secondary_color,
        )

        return None

    # =========================================================================
    # SECTION 2: Problem Statement
    # =========================================================================

    def _prompt_problem(self) -> Optional[str]:
        """Prompt for problem statement"""

        headline = self._prompt_required(
            "Problem Headline (one sentence)"
        )
        if headline == "back":
            return "back"

        description = self._prompt_multiline(
            "Problem Description",
            "Describe the problem your target customers face..."
        )

        self.print("\nList 3-5 pain points (press Enter twice when done):")
        pain_points = self._prompt_list("Pain Point")

        self.print("\nList current solutions/workarounds:")
        current_solutions = self._prompt_list("Current Solution")

        why_inadequate = self._prompt_multiline(
            "Why are current solutions inadequate?",
            ""
        )

        market_impact = self._prompt_with_suggestion(
            "Market Impact (quantify the problem)",
            "$X billion lost annually due to this problem"
        )

        self.plan.problem = Problem(
            headline=headline,
            description=description,
            pain_points=pain_points,
            current_solutions=current_solutions,
            why_inadequate=why_inadequate,
            market_impact=market_impact,
        )

        return None

    # =========================================================================
    # SECTION 3: Solution
    # =========================================================================

    def _prompt_solution(self) -> Optional[str]:
        """Prompt for solution"""

        headline = self._prompt_required(
            "Solution Headline"
        )
        if headline == "back":
            return "back"

        description = self._prompt_multiline(
            "Solution Description",
            f"How {self.plan.company.name if self.plan.company else 'your product'} solves the problem..."
        )

        self.print("\nList key features (3-6):")
        features = self._prompt_list("Feature")

        self.print("\nList key differentiators (what makes you unique):")
        differentiators = self._prompt_list("Differentiator")

        self.print("\nList core technologies used:")
        technology = self._prompt_list("Technology")

        how_it_works = self._prompt_multiline(
            "How It Works (step by step)",
            "1. User does X\n2. System processes Y\n3. Result is Z"
        )

        self.plan.solution = Solution(
            headline=headline,
            description=description,
            key_features=features,
            differentiators=differentiators,
            technology=technology,
            how_it_works=how_it_works,
        )

        return None

    # =========================================================================
    # SECTION 4: Market Analysis
    # =========================================================================

    def _prompt_market(self) -> Optional[str]:
        """Prompt for market analysis"""

        self._print_subsection("Market Sizing")

        tam = self._prompt_number(
            "Total Addressable Market (TAM) in $B",
            0.1, 10000, 10.0, decimal=True
        )
        if tam == "back":
            return "back"

        tam_desc = self._prompt_with_default(
            "TAM Description",
            "Total global market for [your solution category]"
        )

        sam = self._prompt_number(
            "Serviceable Addressable Market (SAM) in $B",
            0.1, tam, tam * 0.3, decimal=True
        )

        sam_desc = self._prompt_with_default(
            "SAM Description",
            "Market segment we can realistically serve"
        )

        som = self._prompt_number(
            "Serviceable Obtainable Market (SOM) in $B",
            0.01, sam, sam * 0.1, decimal=True
        )

        som_desc = self._prompt_with_default(
            "SOM Description",
            "Market share we expect to capture in 5 years"
        )

        # Market segments
        self._print_subsection("Market Segments")
        self.print("Define 3-5 market segments:")

        segments = []
        for i in range(5):
            self.print(f"\n  Segment {i + 1}:")
            seg_name = self._prompt_with_default(f"  Name", "")
            if not seg_name:
                break

            seg_size = self._prompt_number("  Size ($B)", 0.1, 1000, 1.0, decimal=True)
            seg_growth = self._prompt_number("  Annual Growth (%)", 0, 100, 15, decimal=True)
            seg_desc = self._prompt_with_default("  Description", "")

            segments.append(MarketSegment(
                name=seg_name,
                size_billions=seg_size,
                growth_rate=seg_growth,
                description=seg_desc,
            ))

        # Growth drivers
        self.print("\nList market growth drivers:")
        growth_drivers = self._prompt_list("Growth Driver")

        # Key statistics
        self._print_subsection("Key Market Statistics")
        self.print("Add key statistics (e.g., 'Klarna Credit Losses': '€1.07B')")

        statistics = {}
        while True:
            stat_name = self._prompt_with_default("Statistic Name (or Enter to finish)", "")
            if not stat_name:
                break
            stat_value = self._prompt_with_default("Value", "")
            statistics[stat_name] = stat_value

        self.plan.market = MarketAnalysis(
            tam=tam,
            sam=sam,
            som=som,
            tam_description=tam_desc,
            sam_description=sam_desc,
            som_description=som_desc,
            segments=segments,
            growth_drivers=growth_drivers,
            key_statistics=statistics,
        )

        return None

    # =========================================================================
    # SECTION 5: Competitive Analysis
    # =========================================================================

    def _prompt_competition(self) -> Optional[str]:
        """Prompt for competitive analysis"""

        skip = self._prompt_skip("competitive analysis")
        if skip == "back":
            return "back"
        if skip:
            return None

        # Direct competitors
        self._print_subsection("Direct Competitors")
        self.print("List your main direct competitors:")

        direct = []
        for i in range(5):
            self.print(f"\n  Competitor {i + 1}:")
            comp_name = self._prompt_with_default("  Name", "")
            if not comp_name:
                break

            comp_desc = self._prompt_with_default("  Description", "")
            comp_position = self._prompt_with_default(
                "  Market Position (Leader/Challenger/Niche)",
                "Challenger"
            )
            comp_why_win = self._prompt_with_default("  Why we win against them", "")

            direct.append(Competitor(
                name=comp_name,
                description=comp_desc,
                strengths=[],
                weaknesses=[],
                market_position=comp_position,
                why_we_win=comp_why_win,
            ))

        # Competitive advantages
        self.print("\nList your competitive advantages:")
        advantages = self._prompt_list("Advantage")

        # Moats
        self.print("\nList your defensible moats:")
        moats = self._prompt_list("Moat")

        positioning = self._prompt_multiline(
            "Positioning Statement",
            f"For [target customer], {self.plan.company.name if self.plan.company else 'we'} is the only [category] that [key benefit]."
        )

        self.plan.competition = CompetitiveAnalysis(
            direct_competitors=direct,
            competitive_advantages=advantages,
            moats=moats,
            positioning_statement=positioning,
        )

        return None

    # =========================================================================
    # SECTION 6: Business Model
    # =========================================================================

    def _prompt_business_model(self) -> Optional[str]:
        """Prompt for business model"""

        # Revenue model selection
        self.print("Select your primary revenue model:")
        for i, model in enumerate(RevenueModel, 1):
            self.print(f"  {i}. {model.value}")

        model_idx = self._prompt_number("Revenue Model", 1, len(RevenueModel), 1)
        if model_idx == "back":
            return "back"

        revenue_model = list(RevenueModel)[model_idx - 1]

        # Revenue streams
        self._print_subsection("Revenue Streams")
        self.print("Define your revenue streams:")

        streams = []
        remaining_pct = 100

        for i in range(5):
            self.print(f"\n  Stream {i + 1} (remaining: {remaining_pct}%):")
            stream_name = self._prompt_with_default("  Name", "")
            if not stream_name:
                break

            stream_desc = self._prompt_with_default("  Description", "")
            stream_pct = self._prompt_number(
                "  % of Revenue (Year 5)",
                0, remaining_pct, min(50, remaining_pct)
            )
            stream_pricing = self._prompt_with_default("  Pricing", "")

            streams.append(RevenueStream(
                name=stream_name,
                description=stream_desc,
                model=revenue_model,
                percentage_of_total=stream_pct,
                pricing=stream_pricing,
            ))

            remaining_pct -= stream_pct
            if remaining_pct <= 0:
                break

        # Unit economics
        self._print_subsection("Unit Economics")

        unit_economics = {}

        if revenue_model == RevenueModel.SAAS_SUBSCRIPTION:
            unit_economics["cac"] = self._prompt_number("Customer Acquisition Cost ($)", 0, 100000, 500)
            unit_economics["ltv"] = self._prompt_number("Customer Lifetime Value ($)", 0, 1000000, 5000)
            unit_economics["arpu"] = self._prompt_number("Avg Revenue Per User/Month ($)", 0, 10000, 100)
            unit_economics["churn"] = self._prompt_number("Monthly Churn (%)", 0, 50, 3, decimal=True)
        else:
            unit_economics["revenue_per_unit"] = self._prompt_number("Revenue per Unit/Transaction ($)", 0, 100000, 100)
            unit_economics["cost_per_unit"] = self._prompt_number("Cost per Unit/Transaction ($)", 0, 10000, 10)
            unit_economics["margin"] = self._prompt_number("Gross Margin (%)", 0, 100, 70, decimal=True)

        gross_margin = self._prompt_number("Target Gross Margin (%)", 0, 100, 80, decimal=True)

        pricing_strategy = self._prompt_multiline(
            "Pricing Strategy",
            "Describe your pricing approach..."
        )

        self.plan.business_model = BusinessModel(
            revenue_model=revenue_model,
            revenue_streams=streams,
            unit_economics=unit_economics,
            gross_margin=gross_margin / 100,
            pricing_strategy=pricing_strategy,
        )

        return None

    # =========================================================================
    # SECTION 7: Financial Projections
    # =========================================================================

    def _prompt_financials(self) -> Optional[str]:
        """Prompt for financial projections"""

        self._print_subsection("5-Year Financial Projections")

        projections = []

        # Year 1
        self.print("\n  Year 1:")
        y1_revenue = self._prompt_number("  Revenue ($K)", 0, 100000, 500)
        if y1_revenue == "back":
            return "back"

        y1_employees = self._prompt_number("  Employees", 1, 100, 3)
        y1_customers = self._prompt_number("  Customers", 0, 10000, 10)

        projections.append(YearProjection(
            year=1,
            revenue=Decimal(str(y1_revenue * 1000)),
            gross_profit=Decimal(str(y1_revenue * 1000 * 0.8)),
            operating_expenses=Decimal(str(y1_revenue * 1000 * 0.9)),
            ebitda=Decimal(str(y1_revenue * 1000 * -0.1)),
            employees=y1_employees,
            customers=y1_customers,
        ))

        # Years 2-5 with growth rates
        self.print("\n  Enter annual growth rates for Years 2-5:")
        prev_revenue = y1_revenue
        prev_employees = y1_employees
        prev_customers = y1_customers

        for year in range(2, 6):
            self.print(f"\n  Year {year}:")

            growth = self._prompt_number(f"  Revenue Growth (%)", 0, 1000, 100 + (6 - year) * 20)
            revenue = prev_revenue * (1 + growth / 100)

            margin = self._prompt_number(f"  EBITDA Margin (%)", -100, 100, min(70, year * 15 - 10))

            employee_growth = self._prompt_number(f"  Employee Growth (%)", 0, 500, 50)
            employees = int(prev_employees * (1 + employee_growth / 100))

            customer_growth = self._prompt_number(f"  Customer Growth (%)", 0, 1000, growth)
            customers = int(prev_customers * (1 + customer_growth / 100))

            gross_margin = 0.80  # From business model

            projections.append(YearProjection(
                year=year,
                revenue=Decimal(str(int(revenue * 1000))),
                gross_profit=Decimal(str(int(revenue * 1000 * gross_margin))),
                operating_expenses=Decimal(str(int(revenue * 1000 * (gross_margin - margin / 100)))),
                ebitda=Decimal(str(int(revenue * 1000 * margin / 100))),
                employees=employees,
                customers=customers,
            ))

            prev_revenue = revenue
            prev_employees = employees
            prev_customers = customers

        # Assumptions
        self.print("\nList key financial assumptions:")
        assumptions = self._prompt_list("Assumption")

        self.plan.financials = FinancialProjections(
            projections=projections,
            assumptions=assumptions,
        )

        return None

    # =========================================================================
    # SECTION 8: Go-to-Market
    # =========================================================================

    def _prompt_gtm(self) -> Optional[str]:
        """Prompt for go-to-market strategy"""

        skip = self._prompt_skip("go-to-market strategy")
        if skip == "back":
            return "back"
        if skip:
            return None

        phases = []

        # Phase 1
        self._print_subsection("GTM Phase 1")
        p1_name = self._prompt_with_default("Phase Name", "Initial Launch")
        p1_timeline = self._prompt_with_default("Timeline", "Months 1-6")

        self.print("  Target customers:")
        p1_customers = self._prompt_list("  Customer")

        self.print("  Strategies:")
        p1_strategies = self._prompt_list("  Strategy")

        self.print("  Key milestones:")
        p1_milestones = self._prompt_list("  Milestone")

        phases.append(GoToMarketPhase(
            name=p1_name,
            timeline=p1_timeline,
            target_customers=p1_customers,
            strategies=p1_strategies,
            milestones=p1_milestones,
        ))

        # Phase 2
        add_phase = self._prompt_yes_no("Add another GTM phase?", True)
        if add_phase:
            self._print_subsection("GTM Phase 2")
            p2_name = self._prompt_with_default("Phase Name", "Scale")
            p2_timeline = self._prompt_with_default("Timeline", "Months 7-12")

            self.print("  Target customers:")
            p2_customers = self._prompt_list("  Customer")

            self.print("  Strategies:")
            p2_strategies = self._prompt_list("  Strategy")

            phases.append(GoToMarketPhase(
                name=p2_name,
                timeline=p2_timeline,
                target_customers=p2_customers,
                strategies=p2_strategies,
                milestones=[],
            ))

        # Value propositions
        self.print("\nKey value propositions:")
        value_props = self._prompt_list("Value Prop")

        self.plan.gtm = GoToMarket(
            phases=phases,
            key_value_propositions=value_props,
        )

        return None

    # =========================================================================
    # SECTION 9: Team
    # =========================================================================

    def _prompt_team(self) -> Optional[str]:
        """Prompt for team information"""

        founders = []
        advisors = []
        positions = []

        # Founders
        self._print_subsection("Founders")

        # Pre-fill from company info
        if self.plan.company and self.plan.company.founder_name:
            self.print(f"  Adding founder from company info: {self.plan.company.founder_name}")

            bio = self._prompt_multiline(
                f"  Bio for {self.plan.company.founder_name}",
                "Entrepreneur with background in..."
            )
            if bio == "back":
                return "back"

            founders.append(TeamMember(
                name=self.plan.company.founder_name,
                title=self.plan.company.founder_title,
                bio=bio,
            ))

        # Additional founders
        while True:
            add = self._prompt_yes_no("Add another founder/co-founder?", False)
            if not add:
                break

            name = self._prompt_with_default("  Name", "")
            if not name:
                break

            title = self._prompt_with_default("  Title", "Co-Founder")
            bio = self._prompt_multiline("  Bio", "")

            founders.append(TeamMember(name=name, title=title, bio=bio))

        # Key hires needed
        self._print_subsection("Key Hires Needed")
        self.print("List critical positions to fill:")

        for i in range(5):
            title = self._prompt_with_default(f"  Position {i + 1} Title", "")
            if not title:
                break

            desc = self._prompt_with_default("  Description", "")
            priority = self._prompt_with_default("  Priority (Critical/High/Medium)", "High")
            timeline = self._prompt_with_default("  Target Hire Date", "Q1")

            positions.append(OpenPosition(
                title=title,
                description=desc,
                priority=priority,
                timeline=timeline,
            ))

        self.plan.team = TeamInfo(
            founders=founders,
            advisors=advisors,
            open_positions=positions,
        )

        return None

    # =========================================================================
    # SECTION 10: Funding
    # =========================================================================

    def _prompt_funding(self) -> Optional[str]:
        """Prompt for funding requirements"""

        self._print_subsection("Current Funding Round")

        round_name = self._prompt_with_default(
            "Round Name",
            self._suggest_round_name()
        )
        if round_name == "back":
            return "back"

        amount = self._prompt_number("Amount Raising ($K)", 100, 500000, 2000)

        self.print("Use of funds:")
        use_of_funds = self._prompt_list("Use")

        self.print("Milestones this round will achieve:")
        milestones = self._prompt_list("Milestone")

        current_round = FundingRound(
            round_name=round_name,
            amount=Decimal(str(amount * 1000)),
            timing="Now",
            use_of_funds=use_of_funds,
            milestones=milestones,
        )

        # Future rounds
        future_rounds = []
        if self._prompt_yes_no("Define future funding rounds?", True):
            round_defaults = [
                ("Series A", 15000, "Month 12"),
                ("Series B", 50000, "Month 24"),
            ]

            for name, default_amt, timing in round_defaults:
                add = self._prompt_yes_no(f"Add {name}?", True)
                if not add:
                    break

                amt = self._prompt_number(f"  {name} Amount ($K)", 1000, 1000000, default_amt)

                future_rounds.append(FundingRound(
                    round_name=name,
                    amount=Decimal(str(amt * 1000)),
                    timing=timing,
                    use_of_funds=[],
                    milestones=[],
                ))

        self.plan.funding = FundingRequirements(
            current_round=current_round,
            future_rounds=future_rounds,
        )

        return None

    # =========================================================================
    # SECTION 11: Risks
    # =========================================================================

    def _prompt_risks(self) -> Optional[str]:
        """Prompt for risk analysis"""

        skip = self._prompt_skip("risk analysis")
        if skip == "back":
            return "back"
        if skip:
            return None

        risks = []
        categories = ["Market", "Technology", "Regulatory", "Competition", "Execution"]

        self.print("Define key risks and mitigations:")

        for category in categories:
            self.print(f"\n  {category} Risk:")

            desc = self._prompt_with_default("  Description", "")
            if not desc:
                continue

            probability = self._prompt_with_default("  Probability (Low/Medium/High)", "Medium")
            impact = self._prompt_with_default("  Impact (Low/Medium/High)", "Medium")
            mitigation = self._prompt_with_default("  Mitigation Strategy", "")

            risks.append(Risk(
                category=category,
                description=desc,
                probability=probability,
                impact=impact,
                mitigation=mitigation,
            ))

        self.plan.risks = RiskAnalysis(risks=risks)

        return None

    # =========================================================================
    # SECTION 12: Exit Strategy
    # =========================================================================

    def _prompt_exit(self) -> Optional[str]:
        """Prompt for exit strategy"""

        skip = self._prompt_skip("exit strategy")
        if skip == "back":
            return "back"
        if skip:
            return None

        scenarios = []

        # Strategic acquisition
        self._print_subsection("Strategic Acquisition")

        acq_prob = self._prompt_number("Probability (%)", 0, 100, 60)
        acq_timeline = self._prompt_with_default("Timeline", "Years 5-7")

        self.print("  Potential acquirers:")
        acquirers = self._prompt_list("  Acquirer")

        valuation = self._prompt_with_default("Valuation Range", "$500M - $2B")

        scenarios.append(ExitScenario(
            type="Strategic Acquisition",
            probability=acq_prob / 100,
            timeline=acq_timeline,
            potential_acquirers=acquirers,
            valuation_range=valuation,
            rationale="Strategic value to acquirer",
        ))

        # IPO
        if self._prompt_yes_no("Include IPO scenario?", False):
            ipo_prob = self._prompt_number("IPO Probability (%)", 0, 100, 15)
            ipo_timeline = self._prompt_with_default("Timeline", "Years 7-10")
            ipo_valuation = self._prompt_with_default("Valuation Range", "$1B - $5B")

            scenarios.append(ExitScenario(
                type="IPO",
                probability=ipo_prob / 100,
                timeline=ipo_timeline,
                potential_acquirers=[],
                valuation_range=ipo_valuation,
                rationale="Scale and market position warrant public offering",
            ))

        self.plan.exit_strategy = ExitStrategy(scenarios=scenarios)

        return None

    # =========================================================================
    # Executive Summary Generation
    # =========================================================================

    def _generate_executive_summary(self):
        """Auto-generate executive summary from plan data"""

        if not self.plan.company:
            return

        company = self.plan.company
        problem = self.plan.problem
        solution = self.plan.solution
        market = self.plan.market
        financials = self.plan.financials
        funding = self.plan.funding

        summary_parts = []

        # Company intro
        summary_parts.append(
            f"{company.name} is revolutionizing the {company.industry.value.lower()} "
            f"industry. {company.tagline}."
        )

        # Problem/Solution
        if problem and solution:
            summary_parts.append(
                f"\n\n**The Problem:** {problem.headline}\n\n"
                f"**Our Solution:** {solution.headline}"
            )

        # Market
        if market:
            summary_parts.append(
                f"\n\n**Market Opportunity:** ${market.tam}B TAM with "
                f"${market.sam}B serviceable market."
            )

        # Financials
        if financials and financials.projections:
            y5 = financials.projections[-1]
            summary_parts.append(
                f"\n\n**Financial Projections:** Targeting ${float(y5.revenue)/1000000:.0f}M "
                f"revenue by Year 5."
            )

        # Funding
        if funding:
            summary_parts.append(
                f"\n\n**Funding:** Raising ${float(funding.current_round.amount)/1000:.0f}K "
                f"in {funding.current_round.round_name} round."
            )

        self.plan.executive_summary = "".join(summary_parts)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _print_header(self, text: str):
        """Print major header"""
        self.print("\n" + "=" * 60)
        self.print(f"  {text}")
        self.print("=" * 60 + "\n")

    def _print_section_header(self, text: str):
        """Print section header"""
        self.print("\n" + "-" * 60)
        self.print(f"  {text}")
        self.print("-" * 60)

    def _print_subsection(self, text: str):
        """Print subsection header"""
        self.print(f"\n  [{text}]")

    def _prompt_required(self, prompt: str) -> str:
        """Prompt for required value"""
        while True:
            value = self.input(f"  {prompt}: ").strip()
            if value.lower() == "back":
                return "back"
            if value:
                return value
            self.print("    (This field is required)")

    def _prompt_with_default(self, prompt: str, default: str) -> str:
        """Prompt with default value"""
        if default:
            value = self.input(f"  {prompt} [{default}]: ").strip()
        else:
            value = self.input(f"  {prompt}: ").strip()

        return value if value else default

    def _prompt_with_suggestion(self, prompt: str, suggestion: str) -> str:
        """Prompt with suggestion"""
        self.print(f"    Suggestion: {suggestion}")
        value = self.input(f"  {prompt}: ").strip()
        return value if value else suggestion

    def _prompt_multiline(self, prompt: str, default: str) -> str:
        """Prompt for multiline input"""
        self.print(f"  {prompt}")
        if default:
            self.print(f"    Default: {default[:50]}...")
        self.print("    (Enter empty line to finish, or press Enter for default)")

        lines = []
        while True:
            line = self.input("    > ").strip()
            if not line:
                break
            if line.lower() == "back":
                return "back"
            lines.append(line)

        return "\n".join(lines) if lines else default

    def _prompt_list(self, item_name: str) -> List[str]:
        """Prompt for list of items"""
        items = []
        i = 1
        while True:
            item = self.input(f"    {i}. {item_name}: ").strip()
            if not item:
                break
            items.append(item)
            i += 1
        return items

    def _prompt_number(
        self,
        prompt: str,
        min_val: float,
        max_val: float,
        default: float,
        decimal: bool = False,
    ) -> float:
        """Prompt for number with validation"""
        while True:
            value = self.input(f"  {prompt} [{default}]: ").strip()

            if value.lower() == "back":
                return "back"

            if not value:
                return default

            try:
                num = float(value) if decimal else int(value)
                if min_val <= num <= max_val:
                    return num
                self.print(f"    (Please enter a value between {min_val} and {max_val})")
            except ValueError:
                self.print("    (Please enter a valid number)")

    def _prompt_yes_no(self, prompt: str, default: bool) -> bool:
        """Prompt for yes/no"""
        default_str = "Y/n" if default else "y/N"
        value = self.input(f"  {prompt} [{default_str}]: ").strip().lower()

        if not value:
            return default
        return value in ("y", "yes", "true", "1")

    def _prompt_skip(self, section: str) -> Optional[bool]:
        """Ask if user wants to skip optional section"""
        value = self.input(f"  Include {section}? [Y/n/back]: ").strip().lower()

        if value == "back":
            return "back"
        if value in ("n", "no", "skip"):
            return True
        return False

    def _guess_industry_term(self, name: str) -> str:
        """Guess industry term from company name"""
        name_lower = name.lower()

        if any(w in name_lower for w in ["pay", "fin", "money", "credit"]):
            return "Financial Solutions"
        if any(w in name_lower for w in ["health", "med", "care"]):
            return "Healthcare Solutions"
        if any(w in name_lower for w in ["ai", "ml", "data"]):
            return "Intelligence Platform"

        return "Innovation Platform"

    def _suggest_round_name(self) -> str:
        """Suggest funding round based on stage"""
        if not self.plan.company:
            return "Seed"

        stage = self.plan.company.stage

        stage_rounds = {
            BusinessStage.IDEA: "Pre-Seed",
            BusinessStage.PRE_SEED: "Pre-Seed",
            BusinessStage.SEED: "Seed",
            BusinessStage.SERIES_A: "Series A",
            BusinessStage.SERIES_B: "Series B",
            BusinessStage.GROWTH: "Growth",
        }

        return stage_rounds.get(stage, "Seed")

    def _print_completion_status(self):
        """Print completion status"""
        status = self.plan.get_completion_status()

        self.print("\nSection Completion:")
        for section, complete in status.items():
            icon = "✓" if complete else "○"
            self.print(f"  {icon} {section.replace('_', ' ').title()}")

        total = sum(status.values())
        self.print(f"\n  {total}/{len(status)} sections complete")
