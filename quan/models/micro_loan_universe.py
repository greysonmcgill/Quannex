"""
Micro-Loan Universe Model

Comprehensive modeling of the full micro-loan marketplace including:
- All debt types (payday, BNPL, medical, utility, telecom, auto, student)
- Risk factors and mitigation
- Compliance requirements by debt type
- Market sizing and growth projections
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import math


class DebtType(Enum):
    """Types of micro-loans in the marketplace"""
    PAYDAY = "payday"
    PERSONAL_MICRO = "personal_micro"
    BNPL = "buy_now_pay_later"
    MEDICAL = "medical"
    UTILITY = "utility"
    TELECOM = "telecom"
    AUTO_MICRO = "auto_micro"
    STUDENT_MICRO = "student_micro"
    RETAIL_CREDIT = "retail_credit"
    SUBSCRIPTION = "subscription"


class RiskLevel(Enum):
    """Risk classification levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceRegime(Enum):
    """Applicable compliance regimes"""
    FDCPA = "fdcpa"
    TCPA = "tcpa"
    REG_F = "regulation_f"
    FCRA = "fcra"
    HIPAA = "hipaa"  # Medical debt
    STATE_SPECIFIC = "state_specific"
    CFPB = "cfpb"
    MLA = "military_lending_act"
    FCC = "fcc"  # Telecom regulations
    ED = "education_dept"  # Student loans
    TILA = "truth_in_lending"  # Retail credit


@dataclass
class DebtTypeProfile:
    """Profile for each debt type in the micro-loan universe"""
    debt_type: DebtType
    name: str
    description: str

    # Balance characteristics
    min_balance: Decimal
    max_balance: Decimal
    avg_balance: Decimal
    balance_skew: float  # Distribution skew (higher = more small debts)

    # Market sizing
    total_market_size_billions: float
    num_accounts_millions: float
    annual_growth_rate: float

    # Collection characteristics
    base_recovery_rate: float
    avg_days_to_collect: int
    payment_plan_likelihood: float
    settlement_acceptance_rate: float

    # Risk factors
    dispute_rate: float
    bankruptcy_rate: float
    fraud_rate: float
    litigation_risk: float

    # Compliance requirements
    compliance_regimes: List[ComplianceRegime]
    statute_of_limitations_years: int
    special_restrictions: List[str]

    # Debtor demographics
    avg_age: int
    income_distribution: Dict[str, float]  # low/medium/high percentages
    employment_rate: float


# Define the full micro-loan universe
MICRO_LOAN_UNIVERSE: Dict[DebtType, DebtTypeProfile] = {
    DebtType.PAYDAY: DebtTypeProfile(
        debt_type=DebtType.PAYDAY,
        name="Payday Loans",
        description="Short-term, high-interest loans typically due on next payday",
        min_balance=Decimal("50"),
        max_balance=Decimal("1500"),
        avg_balance=Decimal("375"),
        balance_skew=0.4,
        total_market_size_billions=12.0,
        num_accounts_millions=12.0,
        annual_growth_rate=0.03,
        base_recovery_rate=0.28,
        avg_days_to_collect=45,
        payment_plan_likelihood=0.65,
        settlement_acceptance_rate=0.45,
        dispute_rate=0.08,
        bankruptcy_rate=0.04,
        fraud_rate=0.02,
        litigation_risk=0.15,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.STATE_SPECIFIC, ComplianceRegime.MLA],
        statute_of_limitations_years=4,
        special_restrictions=["Rate caps in some states", "Rollover limits",
                            "Cooling-off periods required"],
        avg_age=35,
        income_distribution={"low": 0.55, "medium": 0.40, "high": 0.05},
        employment_rate=0.72
    ),

    DebtType.PERSONAL_MICRO: DebtTypeProfile(
        debt_type=DebtType.PERSONAL_MICRO,
        name="Personal Micro-Loans",
        description="Small personal loans from fintech lenders and credit unions",
        min_balance=Decimal("100"),
        max_balance=Decimal("5000"),
        avg_balance=Decimal("1200"),
        balance_skew=0.35,
        total_market_size_billions=45.0,
        num_accounts_millions=25.0,
        annual_growth_rate=0.12,
        base_recovery_rate=0.35,
        avg_days_to_collect=60,
        payment_plan_likelihood=0.70,
        settlement_acceptance_rate=0.40,
        dispute_rate=0.05,
        bankruptcy_rate=0.03,
        fraud_rate=0.015,
        litigation_risk=0.10,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.REG_F, ComplianceRegime.FCRA],
        statute_of_limitations_years=5,
        special_restrictions=["APR disclosure required", "Right to rescind"],
        avg_age=38,
        income_distribution={"low": 0.35, "medium": 0.50, "high": 0.15},
        employment_rate=0.78
    ),

    DebtType.BNPL: DebtTypeProfile(
        debt_type=DebtType.BNPL,
        name="Buy Now Pay Later",
        description="Point-of-sale installment loans (Affirm, Klarna, Afterpay)",
        min_balance=Decimal("25"),
        max_balance=Decimal("3000"),
        avg_balance=Decimal("250"),
        balance_skew=0.5,
        total_market_size_billions=25.0,
        num_accounts_millions=45.0,
        annual_growth_rate=0.25,
        base_recovery_rate=0.32,
        avg_days_to_collect=35,
        payment_plan_likelihood=0.55,
        settlement_acceptance_rate=0.50,
        dispute_rate=0.12,
        bankruptcy_rate=0.02,
        fraud_rate=0.03,
        litigation_risk=0.05,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.CFPB],
        statute_of_limitations_years=4,
        special_restrictions=["Merchant dispute resolution", "Return handling"],
        avg_age=32,
        income_distribution={"low": 0.30, "medium": 0.55, "high": 0.15},
        employment_rate=0.82
    ),

    DebtType.MEDICAL: DebtTypeProfile(
        debt_type=DebtType.MEDICAL,
        name="Medical Debt",
        description="Healthcare-related debts from providers and facilities",
        min_balance=Decimal("50"),
        max_balance=Decimal("15000"),
        avg_balance=Decimal("1800"),
        balance_skew=0.45,
        total_market_size_billions=140.0,
        num_accounts_millions=79.0,
        annual_growth_rate=0.05,
        base_recovery_rate=0.22,
        avg_days_to_collect=90,
        payment_plan_likelihood=0.75,
        settlement_acceptance_rate=0.55,
        dispute_rate=0.15,
        bankruptcy_rate=0.06,
        fraud_rate=0.01,
        litigation_risk=0.08,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.HIPAA, ComplianceRegime.CFPB],
        statute_of_limitations_years=6,
        special_restrictions=["HIPAA compliance required", "No credit reporting <$500",
                            "Insurance verification", "Charity care screening"],
        avg_age=45,
        income_distribution={"low": 0.40, "medium": 0.45, "high": 0.15},
        employment_rate=0.68
    ),

    DebtType.UTILITY: DebtTypeProfile(
        debt_type=DebtType.UTILITY,
        name="Utility Arrears",
        description="Electric, gas, water, and other utility debts",
        min_balance=Decimal("25"),
        max_balance=Decimal("2000"),
        avg_balance=Decimal("350"),
        balance_skew=0.4,
        total_market_size_billions=8.0,
        num_accounts_millions=15.0,
        annual_growth_rate=0.02,
        base_recovery_rate=0.38,
        avg_days_to_collect=40,
        payment_plan_likelihood=0.80,
        settlement_acceptance_rate=0.35,
        dispute_rate=0.10,
        bankruptcy_rate=0.03,
        fraud_rate=0.01,
        litigation_risk=0.12,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.STATE_SPECIFIC],
        statute_of_limitations_years=4,
        special_restrictions=["PUC regulations", "Shutoff moratoriums",
                            "LIHEAP coordination"],
        avg_age=42,
        income_distribution={"low": 0.50, "medium": 0.40, "high": 0.10},
        employment_rate=0.65
    ),

    DebtType.TELECOM: DebtTypeProfile(
        debt_type=DebtType.TELECOM,
        name="Telecom Debt",
        description="Mobile phone, internet, and cable service debts",
        min_balance=Decimal("50"),
        max_balance=Decimal("1500"),
        avg_balance=Decimal("320"),
        balance_skew=0.35,
        total_market_size_billions=15.0,
        num_accounts_millions=28.0,
        annual_growth_rate=0.04,
        base_recovery_rate=0.30,
        avg_days_to_collect=50,
        payment_plan_likelihood=0.60,
        settlement_acceptance_rate=0.45,
        dispute_rate=0.18,
        bankruptcy_rate=0.02,
        fraud_rate=0.04,
        litigation_risk=0.06,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.FCC],
        statute_of_limitations_years=4,
        special_restrictions=["Equipment return handling", "Contract disputes",
                            "Early termination fees"],
        avg_age=35,
        income_distribution={"low": 0.35, "medium": 0.50, "high": 0.15},
        employment_rate=0.75
    ),

    DebtType.AUTO_MICRO: DebtTypeProfile(
        debt_type=DebtType.AUTO_MICRO,
        name="Auto Micro-Loans",
        description="Small auto loans, title loans, and deficiency balances",
        min_balance=Decimal("500"),
        max_balance=Decimal("8000"),
        avg_balance=Decimal("2500"),
        balance_skew=0.3,
        total_market_size_billions=35.0,
        num_accounts_millions=12.0,
        annual_growth_rate=0.06,
        base_recovery_rate=0.25,
        avg_days_to_collect=75,
        payment_plan_likelihood=0.65,
        settlement_acceptance_rate=0.50,
        dispute_rate=0.08,
        bankruptcy_rate=0.05,
        fraud_rate=0.02,
        litigation_risk=0.18,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.STATE_SPECIFIC],
        statute_of_limitations_years=5,
        special_restrictions=["Repossession laws", "Deficiency balance rules",
                            "Title lien requirements"],
        avg_age=40,
        income_distribution={"low": 0.40, "medium": 0.45, "high": 0.15},
        employment_rate=0.70
    ),

    DebtType.STUDENT_MICRO: DebtTypeProfile(
        debt_type=DebtType.STUDENT_MICRO,
        name="Student Micro-Loans",
        description="Small private student loans and education financing",
        min_balance=Decimal("200"),
        max_balance=Decimal("10000"),
        avg_balance=Decimal("3500"),
        balance_skew=0.25,
        total_market_size_billions=20.0,
        num_accounts_millions=8.0,
        annual_growth_rate=0.08,
        base_recovery_rate=0.20,
        avg_days_to_collect=120,
        payment_plan_likelihood=0.85,
        settlement_acceptance_rate=0.35,
        dispute_rate=0.06,
        bankruptcy_rate=0.02,
        fraud_rate=0.01,
        litigation_risk=0.05,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.CFPB, ComplianceRegime.ED],
        statute_of_limitations_years=6,
        special_restrictions=["Income-driven repayment options",
                            "Hardship deferment", "School closure discharge"],
        avg_age=28,
        income_distribution={"low": 0.45, "medium": 0.45, "high": 0.10},
        employment_rate=0.72
    ),

    DebtType.RETAIL_CREDIT: DebtTypeProfile(
        debt_type=DebtType.RETAIL_CREDIT,
        name="Retail Credit",
        description="Store credit cards and retail financing",
        min_balance=Decimal("50"),
        max_balance=Decimal("3000"),
        avg_balance=Decimal("650"),
        balance_skew=0.4,
        total_market_size_billions=55.0,
        num_accounts_millions=40.0,
        annual_growth_rate=0.04,
        base_recovery_rate=0.33,
        avg_days_to_collect=55,
        payment_plan_likelihood=0.60,
        settlement_acceptance_rate=0.45,
        dispute_rate=0.10,
        bankruptcy_rate=0.03,
        fraud_rate=0.025,
        litigation_risk=0.08,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA,
                          ComplianceRegime.FCRA, ComplianceRegime.TILA],
        statute_of_limitations_years=5,
        special_restrictions=["Return merchandise handling",
                            "Promotional rate disputes"],
        avg_age=38,
        income_distribution={"low": 0.30, "medium": 0.55, "high": 0.15},
        employment_rate=0.78
    ),

    DebtType.SUBSCRIPTION: DebtTypeProfile(
        debt_type=DebtType.SUBSCRIPTION,
        name="Subscription Services",
        description="Streaming, gym, SaaS, and recurring service debts",
        min_balance=Decimal("20"),
        max_balance=Decimal("500"),
        avg_balance=Decimal("120"),
        balance_skew=0.5,
        total_market_size_billions=5.0,
        num_accounts_millions=18.0,
        annual_growth_rate=0.15,
        base_recovery_rate=0.40,
        avg_days_to_collect=30,
        payment_plan_likelihood=0.40,
        settlement_acceptance_rate=0.55,
        dispute_rate=0.20,
        bankruptcy_rate=0.01,
        fraud_rate=0.03,
        litigation_risk=0.02,
        compliance_regimes=[ComplianceRegime.FDCPA, ComplianceRegime.TCPA],
        statute_of_limitations_years=3,
        special_restrictions=["Auto-renewal disclosure", "Cancellation disputes",
                            "Trial conversion issues"],
        avg_age=30,
        income_distribution={"low": 0.25, "medium": 0.55, "high": 0.20},
        employment_rate=0.85
    ),
}


@dataclass
class RiskMitigation:
    """Risk mitigation strategies and controls"""
    risk_type: str
    description: str
    probability: float
    impact_severity: float  # 0-1 scale
    mitigation_strategy: str
    detection_method: str
    response_procedure: str
    cost_to_mitigate: Decimal


# Comprehensive risk catalog
RISK_CATALOG: List[RiskMitigation] = [
    # Compliance Risks
    RiskMitigation(
        risk_type="TCPA_VIOLATION",
        description="Calling consumer without proper consent or during restricted hours",
        probability=0.05,
        impact_severity=0.8,
        mitigation_strategy="Automated consent tracking, time-zone aware dialing",
        detection_method="Call log audit, consent database check",
        response_procedure="Immediate call suspension, compliance review",
        cost_to_mitigate=Decimal("0.02")
    ),
    RiskMitigation(
        risk_type="FDCPA_VIOLATION",
        description="Harassment, false statements, or unfair practices",
        probability=0.03,
        impact_severity=0.9,
        mitigation_strategy="Script compliance, call recording, agent training",
        detection_method="QA monitoring, complaint tracking",
        response_procedure="Agent coaching, script revision, legal review",
        cost_to_mitigate=Decimal("0.03")
    ),
    RiskMitigation(
        risk_type="HIPAA_BREACH",
        description="Improper disclosure of medical information",
        probability=0.01,
        impact_severity=0.95,
        mitigation_strategy="PHI encryption, access controls, training",
        detection_method="Access logging, data loss prevention",
        response_procedure="Breach notification, HHS reporting",
        cost_to_mitigate=Decimal("0.05")
    ),

    # Fraud Risks
    RiskMitigation(
        risk_type="IDENTITY_FRAUD",
        description="Debtor identity misrepresentation",
        probability=0.02,
        impact_severity=0.6,
        mitigation_strategy="Identity verification, fraud scoring",
        detection_method="SSN validation, address verification",
        response_procedure="Account flag, investigation, refund if needed",
        cost_to_mitigate=Decimal("0.15")
    ),
    RiskMitigation(
        risk_type="PAYMENT_FRAUD",
        description="Fraudulent payment methods or chargebacks",
        probability=0.03,
        impact_severity=0.5,
        mitigation_strategy="Payment verification, fraud detection ML",
        detection_method="Velocity checks, device fingerprinting",
        response_procedure="Payment hold, verification request",
        cost_to_mitigate=Decimal("0.10")
    ),

    # Legal Risks
    RiskMitigation(
        risk_type="BANKRUPTCY_FILING",
        description="Debtor files for bankruptcy protection",
        probability=0.04,
        impact_severity=0.7,
        mitigation_strategy="Bankruptcy monitoring, automatic stay compliance",
        detection_method="PACER monitoring, debtor notification",
        response_procedure="Immediate collection cease, proof of claim filing",
        cost_to_mitigate=Decimal("0.01")
    ),
    RiskMitigation(
        risk_type="LITIGATION",
        description="Debtor initiates lawsuit against collector",
        probability=0.01,
        impact_severity=0.85,
        mitigation_strategy="Documentation, compliance adherence",
        detection_method="Suit service, attorney letter",
        response_procedure="Legal escalation, settlement evaluation",
        cost_to_mitigate=Decimal("0.02")
    ),
    RiskMitigation(
        risk_type="SOL_EXPIRED",
        description="Statute of limitations has expired",
        probability=0.08,
        impact_severity=0.4,
        mitigation_strategy="SOL tracking, state-specific rules engine",
        detection_method="Date calculation, state lookup",
        response_procedure="Collection strategy adjustment, no legal action",
        cost_to_mitigate=Decimal("0.005")
    ),

    # Operational Risks
    RiskMitigation(
        risk_type="WRONG_PARTY",
        description="Contacting wrong person about debt",
        probability=0.12,
        impact_severity=0.5,
        mitigation_strategy="Identity verification protocols",
        detection_method="Mini-Miranda response, verification failure",
        response_procedure="Call termination, number removal",
        cost_to_mitigate=Decimal("0.01")
    ),
    RiskMitigation(
        risk_type="DECEASED_DEBTOR",
        description="Debtor is deceased",
        probability=0.02,
        impact_severity=0.3,
        mitigation_strategy="Death record monitoring",
        detection_method="SSA death index, family notification",
        response_procedure="Estate claim process, family communication",
        cost_to_mitigate=Decimal("0.01")
    ),
    RiskMitigation(
        risk_type="DISPUTED_DEBT",
        description="Debtor disputes validity of debt",
        probability=0.10,
        impact_severity=0.4,
        mitigation_strategy="Documentation, validation process",
        detection_method="Dispute notification",
        response_procedure="Collection pause, validation letter, investigation",
        cost_to_mitigate=Decimal("0.02")
    ),

    # Financial Risks
    RiskMitigation(
        risk_type="PAYMENT_REVERSAL",
        description="Payment reversed after collection (NSF, chargeback)",
        probability=0.08,
        impact_severity=0.5,
        mitigation_strategy="Payment verification, hold periods",
        detection_method="Bank notification, processor alert",
        response_procedure="Account reopen, re-collection attempt",
        cost_to_mitigate=Decimal("0.03")
    ),
    RiskMitigation(
        risk_type="HARDSHIP_GENUINE",
        description="Debtor in genuine financial hardship",
        probability=0.20,
        impact_severity=0.3,
        mitigation_strategy="Hardship programs, flexible terms",
        detection_method="Financial assessment, documentation",
        response_procedure="Reduced payment plan, settlement offer",
        cost_to_mitigate=Decimal("0.01")
    ),
]


@dataclass
class MarketSegment:
    """A segment of the micro-loan market"""
    segment_id: str
    name: str
    debt_types: List[DebtType]
    total_balance: Decimal
    num_accounts: int
    weighted_recovery_rate: float
    weighted_avg_balance: Decimal


class MicroLoanUniverseGenerator:
    """
    Generates realistic micro-loan portfolios based on market data.
    """

    def __init__(self, scale_factor: float = 1.0):
        """
        Initialize generator with scale factor.

        Args:
            scale_factor: Multiplier for portfolio size (1.0 = representative sample)
        """
        self.scale_factor = scale_factor
        self.universe = MICRO_LOAN_UNIVERSE
        self.risks = RISK_CATALOG

    def calculate_market_totals(self) -> Dict[str, Any]:
        """Calculate total addressable market"""
        total_market_billions = sum(
            p.total_market_size_billions for p in self.universe.values()
        )
        total_accounts_millions = sum(
            p.num_accounts_millions for p in self.universe.values()
        )
        weighted_recovery = sum(
            p.base_recovery_rate * p.total_market_size_billions
            for p in self.universe.values()
        ) / total_market_billions

        return {
            "total_market_size_billions": total_market_billions,
            "total_accounts_millions": total_accounts_millions,
            "weighted_avg_recovery_rate": weighted_recovery,
            "debt_type_breakdown": {
                dt.value: {
                    "market_size_b": p.total_market_size_billions,
                    "accounts_m": p.num_accounts_millions,
                    "recovery_rate": p.base_recovery_rate,
                    "avg_balance": float(p.avg_balance)
                }
                for dt, p in self.universe.items()
            }
        }

    def generate_portfolio_mix(
        self,
        target_accounts: int,
        debt_type_weights: Optional[Dict[DebtType, float]] = None
    ) -> Dict[DebtType, int]:
        """
        Generate portfolio mix based on market proportions.

        Args:
            target_accounts: Total accounts to generate
            debt_type_weights: Optional custom weights (default: market proportional)

        Returns:
            Dict of debt type -> account count
        """
        if debt_type_weights is None:
            # Use market proportions
            total_accounts = sum(
                p.num_accounts_millions for p in self.universe.values()
            )
            debt_type_weights = {
                dt: p.num_accounts_millions / total_accounts
                for dt, p in self.universe.items()
            }

        # Calculate account counts
        mix = {}
        remaining = target_accounts

        sorted_types = sorted(
            debt_type_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for i, (dt, weight) in enumerate(sorted_types):
            if i == len(sorted_types) - 1:
                # Last type gets remaining
                mix[dt] = remaining
            else:
                count = int(target_accounts * weight)
                mix[dt] = count
                remaining -= count

        return mix

    def generate_account(
        self,
        debt_type: DebtType,
        account_id: str
    ) -> Dict[str, Any]:
        """Generate a single account with realistic attributes"""
        profile = self.universe[debt_type]

        # Generate balance with skew
        raw = random.random() ** (1 + profile.balance_skew)
        balance = (
            profile.min_balance +
            Decimal(str(raw)) * (profile.max_balance - profile.min_balance)
        ).quantize(Decimal("0.01"))

        # Generate demographics based on profile
        age = int(random.gauss(profile.avg_age, 12))
        age = max(18, min(85, age))

        income_rand = random.random()
        if income_rand < profile.income_distribution.get("low", 0.33):
            income_bracket = "low"
        elif income_rand < (profile.income_distribution.get("low", 0.33) +
                          profile.income_distribution.get("medium", 0.34)):
            income_bracket = "medium"
        else:
            income_bracket = "high"

        employed = random.random() < profile.employment_rate

        # Calculate risk factors
        has_dispute = random.random() < profile.dispute_rate
        is_bankruptcy = random.random() < profile.bankruptcy_rate
        is_fraud_risk = random.random() < profile.fraud_rate
        litigation_risk = random.random() < profile.litigation_risk

        # Calculate collectability score
        base_score = profile.base_recovery_rate

        # Adjust for demographics
        if income_bracket == "high":
            base_score += 0.15
        elif income_bracket == "low":
            base_score -= 0.10

        if employed:
            base_score += 0.10
        else:
            base_score -= 0.15

        if age > 50:
            base_score += 0.05  # Older tends to be more responsible

        # Reduce for risk factors
        if has_dispute:
            base_score -= 0.20
        if is_bankruptcy:
            base_score = 0.05  # Nearly uncollectable
        if is_fraud_risk:
            base_score -= 0.15

        collectability = max(0.05, min(0.95, base_score + random.gauss(0, 0.1)))

        # Generate account age
        account_age_days = random.randint(30, 365 * 3)

        # Check statute of limitations
        sol_years = profile.statute_of_limitations_years
        sol_expired = account_age_days > (sol_years * 365)

        return {
            "account_id": account_id,
            "debt_type": debt_type.value,
            "balance": balance,
            "original_balance": balance * Decimal(str(random.uniform(1.0, 1.3))),

            # Demographics
            "age": age,
            "income_bracket": income_bracket,
            "employed": employed,

            # Risk factors
            "has_dispute": has_dispute,
            "is_bankruptcy": is_bankruptcy,
            "is_fraud_risk": is_fraud_risk,
            "litigation_risk_score": litigation_risk,
            "sol_expired": sol_expired,
            "account_age_days": account_age_days,

            # Collection attributes
            "collectability_score": collectability,
            "payment_plan_candidate": random.random() < profile.payment_plan_likelihood,
            "settlement_candidate": random.random() < profile.settlement_acceptance_rate,

            # Compliance
            "compliance_regimes": [r.value for r in profile.compliance_regimes],
            "special_restrictions": profile.special_restrictions,

            # Contact info (realistic quality)
            "phone_valid": random.random() < 0.82,
            "email_valid": random.random() < 0.68,
            "address_valid": random.random() < 0.88,

            # Tech readiness
            "mobile_device": random.random() < (0.95 if age < 50 else 0.70),
            "tech_savvy": max(0.1, min(0.95, 0.7 - (age - 30) * 0.01 + random.gauss(0, 0.15))),
        }

    def generate_full_portfolio(
        self,
        target_accounts: int,
        debt_type_weights: Optional[Dict[DebtType, float]] = None
    ) -> List[Dict[str, Any]]:
        """Generate a complete portfolio"""
        mix = self.generate_portfolio_mix(target_accounts, debt_type_weights)

        portfolio = []
        account_num = 0

        for debt_type, count in mix.items():
            for _ in range(count):
                account_id = f"ML-{debt_type.value[:3].upper()}-{account_num:07d}"
                account = self.generate_account(debt_type, account_id)
                portfolio.append(account)
                account_num += 1

        random.shuffle(portfolio)
        return portfolio

    def calculate_risk_adjusted_value(
        self,
        portfolio: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate risk-adjusted portfolio value"""
        total_balance = sum(Decimal(str(a["balance"])) for a in portfolio)
        total_accounts = len(portfolio)

        # Expected recovery by debt type
        recovery_by_type = {}
        for dt in DebtType:
            dt_accounts = [a for a in portfolio if a["debt_type"] == dt.value]
            if dt_accounts:
                dt_balance = sum(Decimal(str(a["balance"])) for a in dt_accounts)
                dt_collectability = sum(a["collectability_score"] for a in dt_accounts) / len(dt_accounts)
                recovery_by_type[dt.value] = {
                    "accounts": len(dt_accounts),
                    "balance": float(dt_balance),
                    "avg_collectability": dt_collectability,
                    "expected_recovery": float(dt_balance * Decimal(str(dt_collectability)))
                }

        # Risk-adjusted total
        total_expected = sum(r["expected_recovery"] for r in recovery_by_type.values())

        # Risk deductions
        bankruptcy_accounts = sum(1 for a in portfolio if a.get("is_bankruptcy"))
        disputed_accounts = sum(1 for a in portfolio if a.get("has_dispute"))
        sol_expired_accounts = sum(1 for a in portfolio if a.get("sol_expired"))
        fraud_risk_accounts = sum(1 for a in portfolio if a.get("is_fraud_risk"))

        return {
            "total_balance": float(total_balance),
            "total_accounts": total_accounts,
            "expected_recovery": total_expected,
            "expected_recovery_rate": total_expected / float(total_balance),
            "recovery_by_type": recovery_by_type,
            "risk_factors": {
                "bankruptcy": bankruptcy_accounts,
                "disputed": disputed_accounts,
                "sol_expired": sol_expired_accounts,
                "fraud_risk": fraud_risk_accounts,
                "total_high_risk": bankruptcy_accounts + disputed_accounts + sol_expired_accounts
            }
        }


def get_market_summary() -> str:
    """Get a summary of the micro-loan universe"""
    generator = MicroLoanUniverseGenerator()
    totals = generator.calculate_market_totals()

    lines = [
        "=" * 70,
        "  MICRO-LOAN UNIVERSE MARKET SUMMARY",
        "=" * 70,
        "",
        f"  Total Addressable Market: ${totals['total_market_size_billions']:.1f} Billion",
        f"  Total Accounts: {totals['total_accounts_millions']:.1f} Million",
        f"  Weighted Avg Recovery: {totals['weighted_avg_recovery_rate']*100:.1f}%",
        "",
        "  BREAKDOWN BY DEBT TYPE:",
        "  " + "-" * 66,
    ]

    for dt_name, data in sorted(
        totals['debt_type_breakdown'].items(),
        key=lambda x: x[1]['market_size_b'],
        reverse=True
    ):
        lines.append(
            f"  {dt_name:20s}  ${data['market_size_b']:6.1f}B  "
            f"{data['accounts_m']:5.1f}M accts  "
            f"Avg ${data['avg_balance']:,.0f}  "
            f"Rec {data['recovery_rate']*100:.0f}%"
        )

    lines.extend(["", "=" * 70])

    return "\n".join(lines)


if __name__ == "__main__":
    print(get_market_summary())

    # Generate sample portfolio
    generator = MicroLoanUniverseGenerator()
    portfolio = generator.generate_full_portfolio(10000)
    valuation = generator.calculate_risk_adjusted_value(portfolio)

    print(f"\nSample Portfolio (10,000 accounts):")
    print(f"  Total Balance: ${valuation['total_balance']:,.2f}")
    print(f"  Expected Recovery: ${valuation['expected_recovery']:,.2f}")
    print(f"  Expected Rate: {valuation['expected_recovery_rate']*100:.1f}%")
    print(f"  High-Risk Accounts: {valuation['risk_factors']['total_high_risk']}")
