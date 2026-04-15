"""
Business Plan Data Models

Defines the structure for all business plan components.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class BusinessStage(Enum):
    """Stage of business development"""
    IDEA = "idea"
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    GROWTH = "growth"
    PROFITABLE = "profitable"


class Industry(Enum):
    """Industry categories"""
    FINTECH = "Financial Technology"
    HEALTHCARE = "Healthcare & Life Sciences"
    SAAS = "Software as a Service"
    ECOMMERCE = "E-Commerce & Retail"
    AI_ML = "Artificial Intelligence & Machine Learning"
    EDTECH = "Education Technology"
    CLEANTECH = "Clean Technology & Sustainability"
    PROPTECH = "Property Technology"
    INSURTECH = "Insurance Technology"
    MARKETPLACE = "Marketplace & Platform"
    CONSUMER = "Consumer Products & Services"
    ENTERPRISE = "Enterprise Software"
    OTHER = "Other"


class RevenueModel(Enum):
    """Revenue model types"""
    SAAS_SUBSCRIPTION = "SaaS Subscription"
    MARKETPLACE_FEE = "Marketplace/Transaction Fee"
    CONTINGENCY = "Contingency/Success Fee"
    LICENSING = "Licensing"
    FREEMIUM = "Freemium"
    ADVERTISING = "Advertising"
    HARDWARE_PLUS_SERVICE = "Hardware + Service"
    USAGE_BASED = "Usage-Based Pricing"
    HYBRID = "Hybrid Model"


@dataclass
class CompanyInfo:
    """Core company information"""
    name: str
    tagline: str
    description: str
    industry: Industry
    stage: BusinessStage
    founded_date: Optional[datetime] = None
    website: Optional[str] = None

    # Contact
    founder_name: str = ""
    founder_title: str = "Founder & CEO"
    founder_email: str = ""
    founder_linkedin: Optional[str] = None

    # Location
    headquarters: str = ""
    markets: List[str] = field(default_factory=list)

    # Brand
    primary_color: str = "#6B46FF"
    secondary_color: str = "#00D4FF"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "tagline": self.tagline,
            "description": self.description,
            "industry": self.industry.value,
            "stage": self.stage.value,
            "founder_name": self.founder_name,
            "founder_title": self.founder_title,
            "founder_email": self.founder_email,
        }


@dataclass
class Problem:
    """Problem statement"""
    headline: str
    description: str
    pain_points: List[str]
    current_solutions: List[str]
    why_inadequate: str
    market_impact: str  # e.g., "$400B written off annually"


@dataclass
class Solution:
    """Solution description"""
    headline: str
    description: str
    key_features: List[str]
    differentiators: List[str]
    technology: List[str]
    how_it_works: str


@dataclass
class MarketSegment:
    """Market segment data"""
    name: str
    size_billions: float
    growth_rate: float  # Annual %
    description: str


@dataclass
class MarketAnalysis:
    """Market opportunity analysis"""
    tam: float  # Total Addressable Market (billions)
    sam: float  # Serviceable Addressable Market
    som: float  # Serviceable Obtainable Market

    tam_description: str
    sam_description: str
    som_description: str

    segments: List[MarketSegment] = field(default_factory=list)

    growth_drivers: List[str] = field(default_factory=list)
    market_trends: List[str] = field(default_factory=list)

    # Validation
    data_sources: List[str] = field(default_factory=list)
    key_statistics: Dict[str, str] = field(default_factory=dict)


@dataclass
class Competitor:
    """Competitor information"""
    name: str
    description: str
    strengths: List[str]
    weaknesses: List[str]
    market_position: str  # e.g., "Market Leader", "Challenger", "Niche"
    why_we_win: str


@dataclass
class CompetitiveAnalysis:
    """Competitive landscape"""
    direct_competitors: List[Competitor] = field(default_factory=list)
    indirect_competitors: List[Competitor] = field(default_factory=list)

    competitive_advantages: List[str] = field(default_factory=list)
    moats: List[str] = field(default_factory=list)  # Defensible advantages

    positioning_statement: str = ""


@dataclass
class RevenueStream:
    """Individual revenue stream"""
    name: str
    description: str
    model: RevenueModel
    percentage_of_total: float  # Year 5 target
    pricing: str  # e.g., "$99/month", "30% of collections"


@dataclass
class BusinessModel:
    """Business model description"""
    revenue_model: RevenueModel
    revenue_streams: List[RevenueStream] = field(default_factory=list)

    unit_economics: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"cac": 500, "ltv": 5000, "ltv_cac_ratio": 10, "payback_months": 6}

    pricing_strategy: str = ""
    sales_cycle: str = ""  # e.g., "30 days average"

    gross_margin: float = 0.0  # Target gross margin


@dataclass
class YearProjection:
    """Single year financial projection"""
    year: int
    revenue: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    ebitda: Decimal

    # Operational metrics
    customers: int = 0
    employees: int = 0
    arr: Decimal = Decimal("0")  # Annual Recurring Revenue
    mrr: Decimal = Decimal("0")  # Monthly Recurring Revenue


@dataclass
class FinancialProjections:
    """5-year financial projections"""
    projections: List[YearProjection] = field(default_factory=list)

    # Key assumptions
    assumptions: List[str] = field(default_factory=list)

    # Metrics
    break_even_month: int = 0
    target_gross_margin: float = 0.80
    target_ebitda_margin: float = 0.30

    # Growth rates
    revenue_cagr: float = 0.0  # Compound Annual Growth Rate


@dataclass
class GoToMarketPhase:
    """GTM phase"""
    name: str
    timeline: str  # e.g., "Months 1-6"
    target_customers: List[str]
    strategies: List[str]
    milestones: List[str]


@dataclass
class GoToMarket:
    """Go-to-market strategy"""
    phases: List[GoToMarketPhase] = field(default_factory=list)

    customer_acquisition_channels: List[str] = field(default_factory=list)
    partnerships: List[str] = field(default_factory=list)

    sales_strategy: str = ""
    marketing_strategy: str = ""

    key_value_propositions: List[str] = field(default_factory=list)


@dataclass
class TeamMember:
    """Team member"""
    name: str
    title: str
    bio: str
    linkedin: Optional[str] = None
    background: List[str] = field(default_factory=list)  # Key achievements


@dataclass
class OpenPosition:
    """Position to hire"""
    title: str
    description: str
    priority: str  # "Critical", "High", "Medium"
    timeline: str  # e.g., "Q1 2025"


@dataclass
class TeamInfo:
    """Team information"""
    founders: List[TeamMember] = field(default_factory=list)
    key_hires: List[TeamMember] = field(default_factory=list)
    advisors: List[TeamMember] = field(default_factory=list)

    open_positions: List[OpenPosition] = field(default_factory=list)

    team_strengths: List[str] = field(default_factory=list)
    hiring_plan: str = ""


@dataclass
class FundingRound:
    """Funding round details"""
    round_name: str  # "Seed", "Series A", etc.
    amount: Decimal
    timing: str  # "Now", "Month 12", etc.
    use_of_funds: List[str]
    milestones: List[str]
    target_valuation: Optional[Decimal] = None


@dataclass
class FundingRequirements:
    """Funding requirements"""
    current_round: FundingRound
    future_rounds: List[FundingRound] = field(default_factory=list)

    total_capital_needed: Decimal = Decimal("0")
    runway_months: int = 18

    previous_funding: Decimal = Decimal("0")
    current_investors: List[str] = field(default_factory=list)


@dataclass
class Risk:
    """Risk item"""
    category: str  # "Market", "Technology", "Regulatory", "Competition", "Execution"
    description: str
    probability: str  # "Low", "Medium", "High"
    impact: str  # "Low", "Medium", "High"
    mitigation: str


@dataclass
class RiskAnalysis:
    """Risk analysis"""
    risks: List[Risk] = field(default_factory=list)


@dataclass
class ExitScenario:
    """Exit scenario"""
    type: str  # "Strategic Acquisition", "IPO", "PE Buyout"
    probability: float
    timeline: str  # e.g., "Years 5-7"
    potential_acquirers: List[str]
    valuation_range: str  # e.g., "$1-2B"
    rationale: str


@dataclass
class ExitStrategy:
    """Exit strategy"""
    scenarios: List[ExitScenario] = field(default_factory=list)
    comparable_exits: List[str] = field(default_factory=list)


@dataclass
class Appendix:
    """Appendix materials"""
    data_sources: List[str] = field(default_factory=list)
    market_research: List[str] = field(default_factory=list)
    technical_details: str = ""
    product_screenshots: List[str] = field(default_factory=list)


@dataclass
class BusinessPlan:
    """Complete business plan"""

    # Meta
    version: str = "1.0"
    created_date: datetime = field(default_factory=datetime.utcnow)
    confidential: bool = True

    # Core sections
    company: CompanyInfo = None
    problem: Problem = None
    solution: Solution = None
    market: MarketAnalysis = None
    competition: CompetitiveAnalysis = None
    business_model: BusinessModel = None
    financials: FinancialProjections = None
    gtm: GoToMarket = None
    team: TeamInfo = None
    funding: FundingRequirements = None
    risks: RiskAnalysis = None
    exit_strategy: ExitStrategy = None
    appendix: Appendix = None

    # Executive summary (auto-generated or custom)
    executive_summary: str = ""

    def is_complete(self) -> bool:
        """Check if all required sections are filled"""
        required = [
            self.company,
            self.problem,
            self.solution,
            self.market,
            self.business_model,
            self.financials,
            self.team,
            self.funding,
        ]
        return all(r is not None for r in required)

    def get_completion_status(self) -> Dict[str, bool]:
        """Get completion status of each section"""
        return {
            "company": self.company is not None,
            "problem": self.problem is not None,
            "solution": self.solution is not None,
            "market": self.market is not None,
            "competition": self.competition is not None,
            "business_model": self.business_model is not None,
            "financials": self.financials is not None,
            "gtm": self.gtm is not None,
            "team": self.team is not None,
            "funding": self.funding is not None,
            "risks": self.risks is not None,
            "exit_strategy": self.exit_strategy is not None,
        }
