#!/usr/bin/env python3
"""
QUAN Recovery - Deployment Cost Calculator

Calculate estimated costs for real-world deployment based on scale.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional
import json


@dataclass
class LicensingCosts:
    """State licensing costs"""

    # State -> (License Fee, Bond Required, Annual Renewal)
    STATE_REQUIREMENTS = {
        "CA": (300, 25000, 150),
        "TX": (500, 10000, 250),
        "NY": (1000, 5000, 500),
        "FL": (300, 50000, 150),
        "IL": (100, 0, 50),
        "PA": (300, 5000, 150),
        "OH": (500, 0, 250),
        "GA": (250, 0, 125),
        "NC": (500, 15000, 250),
        "NJ": (300, 5000, 150),
        "MI": (250, 5000, 125),
        "VA": (200, 5000, 100),
        "WA": (400, 10000, 200),
        "AZ": (200, 10000, 100),
        "MA": (500, 25000, 250),
        "TN": (200, 0, 100),
        "MO": (200, 0, 100),
        "MD": (300, 5000, 150),
        "WI": (200, 0, 100),
        "MN": (300, 10000, 150),
    }

    def calculate(self, states: List[str]) -> Dict[str, float]:
        """Calculate licensing costs for given states"""
        total_fees = 0
        total_bonds = 0
        annual_renewals = 0

        for state in states:
            if state in self.STATE_REQUIREMENTS:
                fee, bond, renewal = self.STATE_REQUIREMENTS[state]
                total_fees += fee
                total_bonds += bond
                annual_renewals += renewal

        # Bond cost is typically 1-5% of bond amount
        bond_premium = total_bonds * 0.03  # 3% average

        return {
            "license_fees": total_fees,
            "bond_face_value": total_bonds,
            "bond_premium_annual": bond_premium,
            "annual_renewals": annual_renewals,
            "year_1_total": total_fees + bond_premium,
            "ongoing_annual": annual_renewals + bond_premium,
        }


@dataclass
class InfrastructureCosts:
    """Cloud infrastructure costs"""

    def calculate(self, accounts_per_month: int) -> Dict[str, float]:
        """Calculate infrastructure costs based on scale"""

        # Base costs
        base_compute = 400  # 3x t3.xlarge
        base_database = 300  # RDS
        base_cache = 150  # Redis
        base_storage = 50  # S3
        base_networking = 150  # VPC, NAT, etc.
        base_monitoring = 100  # CloudWatch, etc.

        # Scale factors
        if accounts_per_month <= 10000:
            scale_factor = 1.0
        elif accounts_per_month <= 50000:
            scale_factor = 2.0
        elif accounts_per_month <= 100000:
            scale_factor = 3.5
        elif accounts_per_month <= 500000:
            scale_factor = 8.0
        elif accounts_per_month <= 1000000:
            scale_factor = 15.0
        else:
            scale_factor = 25.0 + (accounts_per_month - 1000000) / 200000

        compute = base_compute * scale_factor
        database = base_database * scale_factor
        cache = base_cache * scale_factor
        storage = base_storage * max(1, accounts_per_month / 10000)
        networking = base_networking * min(scale_factor, 5)
        monitoring = base_monitoring * min(scale_factor, 3)

        return {
            "compute": compute,
            "database": database,
            "cache": cache,
            "storage": storage,
            "networking": networking,
            "monitoring": monitoring,
            "monthly_total": compute + database + cache + storage + networking + monitoring,
            "annual_total": (compute + database + cache + storage + networking + monitoring) * 12,
        }


@dataclass
class CommunicationCosts:
    """SMS, Email, Voice costs"""

    # Per-unit costs
    SMS_COST = 0.0075  # Twilio
    EMAIL_COST = 0.001  # SendGrid
    VOICE_IVR_COST = 0.015  # Per minute
    VOICE_AGENT_COST = 2.50  # Per call (outsourced)

    def calculate(
        self,
        accounts_per_month: int,
        avg_sms_per_account: float = 4.0,
        avg_emails_per_account: float = 3.0,
        avg_voice_minutes_per_account: float = 0.5,
    ) -> Dict[str, float]:
        """Calculate communication costs"""

        sms_count = accounts_per_month * avg_sms_per_account
        email_count = accounts_per_month * avg_emails_per_account
        voice_minutes = accounts_per_month * avg_voice_minutes_per_account

        sms_cost = sms_count * self.SMS_COST
        email_cost = email_count * self.EMAIL_COST
        voice_cost = voice_minutes * self.VOICE_IVR_COST

        # Twilio monthly platform fee
        platform_fee = 150 if accounts_per_month > 10000 else 50

        return {
            "sms_volume": sms_count,
            "sms_cost": sms_cost,
            "email_volume": email_count,
            "email_cost": email_cost,
            "voice_minutes": voice_minutes,
            "voice_cost": voice_cost,
            "platform_fees": platform_fee,
            "monthly_total": sms_cost + email_cost + voice_cost + platform_fee,
        }


@dataclass
class PaymentProcessingCosts:
    """Payment processing costs"""

    CARD_RATE = 0.029  # 2.9%
    CARD_TXN_FEE = 0.30  # $0.30 per transaction
    ACH_RATE = 0.008  # 0.8%
    ACH_TXN_FEE = 0.25  # $0.25 per transaction

    def calculate(
        self,
        monthly_collected: float,
        avg_payment_amount: float = 150,
        card_percentage: float = 0.60,
    ) -> Dict[str, float]:
        """Calculate payment processing costs"""

        total_payments = monthly_collected / avg_payment_amount
        card_payments = total_payments * card_percentage
        ach_payments = total_payments * (1 - card_percentage)

        card_collected = monthly_collected * card_percentage
        ach_collected = monthly_collected * (1 - card_percentage)

        card_fees = (card_collected * self.CARD_RATE) + (card_payments * self.CARD_TXN_FEE)
        ach_fees = (ach_collected * self.ACH_RATE) + (ach_payments * self.ACH_TXN_FEE)

        return {
            "card_transactions": card_payments,
            "card_fees": card_fees,
            "ach_transactions": ach_payments,
            "ach_fees": ach_fees,
            "monthly_total": card_fees + ach_fees,
            "effective_rate": (card_fees + ach_fees) / monthly_collected if monthly_collected > 0 else 0,
        }


@dataclass
class DataProviderCosts:
    """Skip tracing and data costs"""

    SKIP_TRACE_COST = 0.75  # Average per lookup
    IDENTITY_VERIFY_COST = 0.15
    PHONE_VALIDATE_COST = 0.01

    def calculate(
        self,
        accounts_per_month: int,
        skip_trace_rate: float = 0.30,  # % needing skip trace
    ) -> Dict[str, float]:
        """Calculate data provider costs"""

        skip_traces = accounts_per_month * skip_trace_rate
        verifications = accounts_per_month * 0.10  # 10% need ID verify
        phone_validations = accounts_per_month * 2  # 2 numbers per account avg

        skip_cost = skip_traces * self.SKIP_TRACE_COST
        verify_cost = verifications * self.IDENTITY_VERIFY_COST
        phone_cost = phone_validations * self.PHONE_VALIDATE_COST

        # Monthly minimums
        minimum_commitment = 500  # Typical minimum

        return {
            "skip_traces": skip_traces,
            "skip_cost": skip_cost,
            "verifications": verifications,
            "verify_cost": verify_cost,
            "phone_validations": phone_validations,
            "phone_cost": phone_cost,
            "monthly_total": max(minimum_commitment, skip_cost + verify_cost + phone_cost),
        }


@dataclass
class ComplianceCosts:
    """Compliance and regulatory costs"""

    def calculate(self, accounts_per_month: int) -> Dict[str, float]:
        """Calculate compliance costs"""

        # TCPA/DNC scrubbing
        dnc_cost = max(200, accounts_per_month * 0.005)

        # Call recording storage
        recording_cost = accounts_per_month * 0.02  # ~2 cents per account

        # Compliance software
        if accounts_per_month < 50000:
            software_cost = 500
        elif accounts_per_month < 200000:
            software_cost = 1500
        else:
            software_cost = 3000

        # Audit reserve (quarterly audits)
        audit_reserve = 500  # Monthly reserve for quarterly audits

        return {
            "dnc_scrubbing": dnc_cost,
            "call_recording": recording_cost,
            "compliance_software": software_cost,
            "audit_reserve": audit_reserve,
            "monthly_total": dnc_cost + recording_cost + software_cost + audit_reserve,
        }


@dataclass
class InsuranceCosts:
    """Insurance costs"""

    def calculate(self, annual_revenue: float) -> Dict[str, float]:
        """Calculate insurance costs"""

        # E&O scales with revenue
        if annual_revenue < 1000000:
            eo_premium = 3000
        elif annual_revenue < 5000000:
            eo_premium = 8000
        else:
            eo_premium = 15000 + (annual_revenue - 5000000) * 0.001

        # Cyber liability
        cyber_premium = max(5000, annual_revenue * 0.002)

        # General liability
        gl_premium = 1500

        # D&O
        do_premium = 3000

        return {
            "eo_annual": eo_premium,
            "cyber_annual": cyber_premium,
            "general_liability_annual": gl_premium,
            "do_annual": do_premium,
            "annual_total": eo_premium + cyber_premium + gl_premium + do_premium,
            "monthly_total": (eo_premium + cyber_premium + gl_premium + do_premium) / 12,
        }


@dataclass
class SaaSCosts:
    """SaaS tool subscriptions"""

    def calculate(self, team_size: int) -> Dict[str, float]:
        """Calculate SaaS subscription costs"""

        # Per-seat tools
        slack = 12.50 * team_size
        google_workspace = 12 * team_size
        github = 21 * team_size
        linear = 8 * team_size
        one_password = 8 * team_size

        # Flat-rate tools
        zendesk = 150
        datadog = 300
        vanta = 833  # $10K/year

        return {
            "slack": slack,
            "google_workspace": google_workspace,
            "github": github,
            "linear": linear,
            "one_password": one_password,
            "zendesk": zendesk,
            "datadog": datadog,
            "vanta": vanta,
            "monthly_total": slack + google_workspace + github + linear + one_password + zendesk + datadog + vanta,
        }


class DeploymentCostCalculator:
    """Main cost calculator"""

    def __init__(self):
        self.licensing = LicensingCosts()
        self.infrastructure = InfrastructureCosts()
        self.communications = CommunicationCosts()
        self.payments = PaymentProcessingCosts()
        self.data = DataProviderCosts()
        self.compliance = ComplianceCosts()
        self.insurance = InsuranceCosts()
        self.saas = SaaSCosts()

    def calculate_full_deployment(
        self,
        states: List[str],
        accounts_per_month: int,
        avg_balance: float = 400,
        recovery_rate: float = 0.47,
        commission_rate: float = 0.30,
        team_size: int = 5,
    ) -> Dict[str, any]:
        """Calculate complete deployment costs"""

        # Revenue projections
        total_balance = accounts_per_month * avg_balance
        collected = total_balance * recovery_rate
        monthly_revenue = collected * commission_rate
        annual_revenue = monthly_revenue * 12

        # Calculate all cost categories
        licensing = self.licensing.calculate(states)
        infrastructure = self.infrastructure.calculate(accounts_per_month)
        communications = self.communications.calculate(accounts_per_month)
        payment_processing = self.payments.calculate(collected)
        data_providers = self.data.calculate(accounts_per_month)
        compliance = self.compliance.calculate(accounts_per_month)
        insurance = self.insurance.calculate(annual_revenue)
        saas = self.saas.calculate(team_size)

        # Totals
        monthly_operating = (
            infrastructure["monthly_total"] +
            communications["monthly_total"] +
            payment_processing["monthly_total"] +
            data_providers["monthly_total"] +
            compliance["monthly_total"] +
            insurance["monthly_total"] +
            saas["monthly_total"]
        )

        year_1_startup = licensing["year_1_total"] + 20000  # + legal

        return {
            "inputs": {
                "states": states,
                "accounts_per_month": accounts_per_month,
                "avg_balance": avg_balance,
                "recovery_rate": recovery_rate,
                "commission_rate": commission_rate,
                "team_size": team_size,
            },
            "revenue": {
                "total_balance_monthly": total_balance,
                "collected_monthly": collected,
                "revenue_monthly": monthly_revenue,
                "revenue_annual": annual_revenue,
            },
            "costs": {
                "licensing": licensing,
                "infrastructure": infrastructure,
                "communications": communications,
                "payment_processing": payment_processing,
                "data_providers": data_providers,
                "compliance": compliance,
                "insurance": insurance,
                "saas": saas,
            },
            "totals": {
                "monthly_operating_cost": monthly_operating,
                "annual_operating_cost": monthly_operating * 12,
                "year_1_startup_cost": year_1_startup,
                "cost_per_account": monthly_operating / accounts_per_month if accounts_per_month > 0 else 0,
                "cost_per_dollar_collected": monthly_operating / collected if collected > 0 else 0,
            },
            "profitability": {
                "monthly_gross_profit": monthly_revenue - monthly_operating,
                "gross_margin": (monthly_revenue - monthly_operating) / monthly_revenue if monthly_revenue > 0 else 0,
                "annual_gross_profit": (monthly_revenue - monthly_operating) * 12,
                "breakeven_accounts": monthly_operating / (avg_balance * recovery_rate * commission_rate) if recovery_rate > 0 else 0,
            },
        }


def print_report(results: Dict):
    """Print formatted cost report"""

    print("\n" + "=" * 70)
    print("  QUAN RECOVERY - DEPLOYMENT COST ANALYSIS")
    print("=" * 70)

    inputs = results["inputs"]
    print(f"\nConfiguration:")
    print(f"  States Licensed: {len(inputs['states'])} ({', '.join(inputs['states'][:5])}...)")
    print(f"  Accounts/Month: {inputs['accounts_per_month']:,}")
    print(f"  Avg Balance: ${inputs['avg_balance']:.2f}")
    print(f"  Recovery Rate: {inputs['recovery_rate']:.1%}")
    print(f"  Commission: {inputs['commission_rate']:.1%}")
    print(f"  Team Size: {inputs['team_size']}")

    rev = results["revenue"]
    print(f"\nRevenue Projection:")
    print(f"  Monthly Balance Under Management: ${rev['total_balance_monthly']:,.0f}")
    print(f"  Monthly Collected: ${rev['collected_monthly']:,.0f}")
    print(f"  Monthly Revenue: ${rev['revenue_monthly']:,.0f}")
    print(f"  Annual Revenue: ${rev['revenue_annual']:,.0f}")

    costs = results["costs"]
    print(f"\nMonthly Operating Costs:")
    print(f"  Infrastructure (AWS): ${costs['infrastructure']['monthly_total']:,.0f}")
    print(f"  Communications (SMS/Email): ${costs['communications']['monthly_total']:,.0f}")
    print(f"  Payment Processing: ${costs['payment_processing']['monthly_total']:,.0f}")
    print(f"  Data Providers: ${costs['data_providers']['monthly_total']:,.0f}")
    print(f"  Compliance: ${costs['compliance']['monthly_total']:,.0f}")
    print(f"  Insurance: ${costs['insurance']['monthly_total']:,.0f}")
    print(f"  SaaS Tools: ${costs['saas']['monthly_total']:,.0f}")

    totals = results["totals"]
    print(f"\nCost Summary:")
    print(f"  Year 1 Startup Costs: ${totals['year_1_startup_cost']:,.0f}")
    print(f"  Monthly Operating: ${totals['monthly_operating_cost']:,.0f}")
    print(f"  Annual Operating: ${totals['annual_operating_cost']:,.0f}")
    print(f"  Cost per Account: ${totals['cost_per_account']:.2f}")
    print(f"  Cost per Dollar Collected: ${totals['cost_per_dollar_collected']:.3f}")

    profit = results["profitability"]
    print(f"\nProfitability:")
    print(f"  Monthly Gross Profit: ${profit['monthly_gross_profit']:,.0f}")
    print(f"  Gross Margin: {profit['gross_margin']:.1%}")
    print(f"  Annual Gross Profit: ${profit['annual_gross_profit']:,.0f}")
    print(f"  Breakeven Accounts/Month: {profit['breakeven_accounts']:,.0f}")

    print("\n" + "=" * 70)


def main():
    """Run cost calculator with sample scenarios"""

    calculator = DeploymentCostCalculator()

    # Priority states for BNPL debtor coverage
    priority_states = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "NJ"]

    # Scenario 1: Seed Stage
    print("\n### SCENARIO 1: SEED STAGE ###")
    seed = calculator.calculate_full_deployment(
        states=priority_states[:5],
        accounts_per_month=10000,
        team_size=3,
    )
    print_report(seed)

    # Scenario 2: Series A
    print("\n### SCENARIO 2: SERIES A STAGE ###")
    series_a = calculator.calculate_full_deployment(
        states=priority_states,
        accounts_per_month=100000,
        team_size=15,
    )
    print_report(series_a)

    # Scenario 3: Growth Stage
    print("\n### SCENARIO 3: GROWTH STAGE ###")
    growth = calculator.calculate_full_deployment(
        states=priority_states + ["MI", "VA", "WA", "AZ", "MA"],
        accounts_per_month=500000,
        team_size=45,
    )
    print_report(growth)

    # Export to JSON
    all_scenarios = {
        "seed": seed,
        "series_a": series_a,
        "growth": growth,
    }

    with open("/home/user/Quan/docs/cost_analysis.json", "w") as f:
        json.dump(all_scenarios, f, indent=2, default=str)

    print("\n\nCost analysis exported to: /home/user/Quan/docs/cost_analysis.json")


if __name__ == "__main__":
    main()
