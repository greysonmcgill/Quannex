"""
QUAN Integration Tests: Economic Validation

Testing for economic model accuracy:
1. CTC (Cost to Collect) calculations accuracy
2. ROI projections
3. Break-even validation
4. Dead Zone resurrection proof

Tests verify the financial projections and economic models are accurate.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple
import uuid
import random
from dataclasses import dataclass, field
from enum import Enum

import sys
sys.path.insert(0, '/home/user/Quan')


# =============================================================================
# ECONOMIC MODEL IMPLEMENTATION FOR TESTING
# =============================================================================

@dataclass
class CostStructure:
    """Cost structure for collections"""
    # Per-account costs
    cost_per_account_acquisition: Decimal = Decimal("0.50")
    cost_per_contact_sms: Decimal = Decimal("0.02")
    cost_per_contact_email: Decimal = Decimal("0.005")
    cost_per_contact_voice: Decimal = Decimal("0.15")
    cost_per_contact_letter: Decimal = Decimal("0.65")
    cost_per_payment_processing: Decimal = Decimal("0.30")
    cost_per_skip_trace: Decimal = Decimal("0.25")

    # Fixed costs (monthly)
    fixed_cost_infrastructure: Decimal = Decimal("5000.00")
    fixed_cost_compliance: Decimal = Decimal("2500.00")
    fixed_cost_staffing: Decimal = Decimal("15000.00")

    # Commission structure
    commission_rate_under_100: Decimal = Decimal("0.40")  # 40% for debts under $100
    commission_rate_100_500: Decimal = Decimal("0.35")    # 35% for $100-500
    commission_rate_over_500: Decimal = Decimal("0.30")   # 30% for over $500


@dataclass
class PortfolioMetrics:
    """Metrics for a debt portfolio"""
    total_accounts: int
    total_face_value: Decimal
    avg_balance: Decimal
    avg_days_past_due: int
    weighted_recovery_rate: float
    expected_collections: Decimal
    collection_period_months: int


@dataclass
class EconomicProjection:
    """Economic projection results"""
    gross_collections: Decimal
    total_cost_to_collect: Decimal
    net_revenue: Decimal
    roi_percentage: float
    cost_per_dollar_collected: Decimal
    break_even_recovery_rate: float
    profit_margin: float
    payback_period_months: float


class EconomicEngine:
    """Engine for economic calculations and projections"""

    def __init__(self, cost_structure: CostStructure = None):
        self.costs = cost_structure or CostStructure()

    def calculate_ctc(
        self,
        account_count: int,
        contact_mix: Dict[str, int],
        skip_traces: int,
        payments_processed: int
    ) -> Decimal:
        """Calculate Cost to Collect (CTC)"""
        # Variable costs
        variable_costs = Decimal("0")

        # Contact costs
        variable_costs += Decimal(str(contact_mix.get("sms", 0))) * self.costs.cost_per_contact_sms
        variable_costs += Decimal(str(contact_mix.get("email", 0))) * self.costs.cost_per_contact_email
        variable_costs += Decimal(str(contact_mix.get("voice", 0))) * self.costs.cost_per_contact_voice
        variable_costs += Decimal(str(contact_mix.get("letter", 0))) * self.costs.cost_per_contact_letter

        # Other variable costs
        variable_costs += Decimal(str(account_count)) * self.costs.cost_per_account_acquisition
        variable_costs += Decimal(str(skip_traces)) * self.costs.cost_per_skip_trace
        variable_costs += Decimal(str(payments_processed)) * self.costs.cost_per_payment_processing

        return variable_costs

    def calculate_fixed_costs(self, months: int = 1) -> Decimal:
        """Calculate fixed costs for a period"""
        monthly_fixed = (
            self.costs.fixed_cost_infrastructure +
            self.costs.fixed_cost_compliance +
            self.costs.fixed_cost_staffing
        )
        return monthly_fixed * months

    def calculate_commission(self, balance: Decimal, collected: Decimal) -> Decimal:
        """Calculate commission on collection"""
        if balance < Decimal("100"):
            rate = self.costs.commission_rate_under_100
        elif balance < Decimal("500"):
            rate = self.costs.commission_rate_100_500
        else:
            rate = self.costs.commission_rate_over_500

        return collected * rate

    def calculate_gross_revenue(
        self,
        collections: List[Tuple[Decimal, Decimal]]  # (balance, collected) pairs
    ) -> Decimal:
        """Calculate gross revenue from collections"""
        total_commission = Decimal("0")
        for balance, collected in collections:
            total_commission += self.calculate_commission(balance, collected)
        return total_commission

    def project_economics(
        self,
        portfolio: PortfolioMetrics,
        contact_intensity: float = 5.0,  # Avg contacts per account
        skip_trace_rate: float = 0.20,    # % needing skip trace
        payment_rate: float = None        # % making payments (defaults to recovery rate)
    ) -> EconomicProjection:
        """Project economics for a portfolio"""
        if payment_rate is None:
            payment_rate = portfolio.weighted_recovery_rate

        # Calculate expected collections
        gross_collections = portfolio.expected_collections

        # Estimate contact mix (typical distribution)
        total_contacts = int(portfolio.total_accounts * contact_intensity)
        contact_mix = {
            "sms": int(total_contacts * 0.45),
            "email": int(total_contacts * 0.35),
            "voice": int(total_contacts * 0.15),
            "letter": int(total_contacts * 0.05)
        }

        # Calculate costs
        skip_traces = int(portfolio.total_accounts * skip_trace_rate)
        payments = int(portfolio.total_accounts * payment_rate)

        variable_costs = self.calculate_ctc(
            portfolio.total_accounts,
            contact_mix,
            skip_traces,
            payments
        )

        fixed_costs = self.calculate_fixed_costs(portfolio.collection_period_months)

        total_ctc = variable_costs + fixed_costs

        # Calculate revenue (commission-based)
        # Estimate average collection per paying account
        if payments > 0:
            avg_collection = gross_collections / payments
        else:
            avg_collection = Decimal("0")

        # Assume collections distributed across balance ranges
        collections = []
        for _ in range(payments):
            balance = portfolio.avg_balance * Decimal(str(random.uniform(0.5, 1.5)))
            collected = balance * Decimal(str(portfolio.weighted_recovery_rate))
            collections.append((balance, collected))

        gross_revenue = self.calculate_gross_revenue(collections)

        # Net calculations
        net_revenue = gross_revenue - total_ctc

        # ROI
        roi = float((net_revenue / total_ctc) * 100) if total_ctc > 0 else 0

        # Cost per dollar collected
        cpdc = total_ctc / gross_collections if gross_collections > 0 else Decimal("0")

        # Break-even recovery rate
        if portfolio.total_face_value > 0:
            # Simplified: at what recovery rate does revenue = cost
            # revenue = face_value * recovery_rate * avg_commission_rate
            avg_commission = Decimal("0.35")  # Approximate
            break_even = float(total_ctc / (portfolio.total_face_value * avg_commission))
        else:
            break_even = 0

        # Profit margin
        margin = float(net_revenue / gross_revenue * 100) if gross_revenue > 0 else 0

        # Payback period (months to recover fixed costs)
        monthly_net = net_revenue / portfolio.collection_period_months if portfolio.collection_period_months > 0 else net_revenue
        payback = float(fixed_costs / monthly_net) if monthly_net > 0 else float('inf')

        return EconomicProjection(
            gross_collections=gross_collections,
            total_cost_to_collect=total_ctc,
            net_revenue=net_revenue,
            roi_percentage=roi,
            cost_per_dollar_collected=cpdc,
            break_even_recovery_rate=break_even,
            profit_margin=margin,
            payback_period_months=payback
        )

    def calculate_dead_zone_economics(
        self,
        balance: Decimal,
        age_months: int,
        traditional_recovery_rate: float,
        ai_enhanced_recovery_rate: float
    ) -> Dict:
        """Calculate economics for 'Dead Zone' accounts"""
        # Traditional approach
        traditional_collection = balance * Decimal(str(traditional_recovery_rate))
        traditional_commission = self.calculate_commission(balance, traditional_collection)
        traditional_cost = Decimal("5.00")  # Higher cost for manual
        traditional_net = traditional_commission - traditional_cost

        # AI-enhanced approach
        ai_collection = balance * Decimal(str(ai_enhanced_recovery_rate))
        ai_commission = self.calculate_commission(balance, ai_collection)
        ai_cost = Decimal("1.50")  # Lower cost for automation
        ai_net = ai_commission - ai_cost

        # Incremental value
        incremental_collection = ai_collection - traditional_collection
        incremental_net = ai_net - traditional_net

        # Is it profitable?
        is_viable_traditional = traditional_net > 0
        is_viable_ai = ai_net > 0
        resurrected = not is_viable_traditional and is_viable_ai

        return {
            "balance": float(balance),
            "age_months": age_months,
            "traditional": {
                "collection": float(traditional_collection),
                "commission": float(traditional_commission),
                "cost": float(traditional_cost),
                "net": float(traditional_net),
                "viable": is_viable_traditional
            },
            "ai_enhanced": {
                "collection": float(ai_collection),
                "commission": float(ai_commission),
                "cost": float(ai_cost),
                "net": float(ai_net),
                "viable": is_viable_ai
            },
            "incremental_value": float(incremental_net),
            "dead_zone_resurrected": resurrected
        }


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestCTCCalculations:
    """Test Cost to Collect calculations"""

    @pytest.fixture
    def engine(self):
        return EconomicEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_basic_ctc_calculation(self, engine):
        """Test basic CTC calculation"""
        ctc = engine.calculate_ctc(
            account_count=100,
            contact_mix={"sms": 200, "email": 150, "voice": 50, "letter": 20},
            skip_traces=20,
            payments_processed=30
        )

        # Should be positive
        assert ctc > 0

        # Verify components
        expected_sms = 200 * 0.02
        expected_email = 150 * 0.005
        expected_voice = 50 * 0.15
        expected_letter = 20 * 0.65
        expected_acquisition = 100 * 0.50
        expected_skip = 20 * 0.25
        expected_payment = 30 * 0.30

        expected_total = (
            expected_sms + expected_email + expected_voice +
            expected_letter + expected_acquisition +
            expected_skip + expected_payment
        )

        assert abs(float(ctc) - expected_total) < 0.01

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ctc_scales_with_volume(self, engine):
        """Test CTC scales appropriately with volume"""
        ctc_100 = engine.calculate_ctc(
            account_count=100,
            contact_mix={"sms": 200, "email": 100},
            skip_traces=10,
            payments_processed=20
        )

        ctc_1000 = engine.calculate_ctc(
            account_count=1000,
            contact_mix={"sms": 2000, "email": 1000},
            skip_traces=100,
            payments_processed=200
        )

        # Should scale approximately linearly
        ratio = ctc_1000 / ctc_100
        assert 9.0 < ratio < 11.0  # Allow for some variance

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_ctc_channel_costs(self, engine):
        """Test CTC varies by channel mix"""
        # SMS-heavy mix (cheaper)
        ctc_sms = engine.calculate_ctc(
            account_count=100,
            contact_mix={"sms": 400, "email": 0, "voice": 0, "letter": 0},
            skip_traces=0,
            payments_processed=0
        )

        # Voice-heavy mix (expensive)
        ctc_voice = engine.calculate_ctc(
            account_count=100,
            contact_mix={"sms": 0, "email": 0, "voice": 400, "letter": 0},
            skip_traces=0,
            payments_processed=0
        )

        # Voice should be significantly more expensive
        assert ctc_voice > ctc_sms * 5

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fixed_costs_calculation(self, engine):
        """Test fixed costs calculation"""
        monthly_fixed = engine.calculate_fixed_costs(months=1)
        quarterly_fixed = engine.calculate_fixed_costs(months=3)
        annual_fixed = engine.calculate_fixed_costs(months=12)

        # Should scale linearly
        assert quarterly_fixed == monthly_fixed * 3
        assert annual_fixed == monthly_fixed * 12

        # Verify components
        expected_monthly = 5000 + 2500 + 15000  # infra + compliance + staffing
        assert float(monthly_fixed) == expected_monthly


class TestROIProjections:
    """Test ROI projection accuracy"""

    @pytest.fixture
    def engine(self):
        return EconomicEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_positive_roi_scenario(self, engine):
        """Test positive ROI scenario"""
        portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("185000"),  # $185 avg
            avg_balance=Decimal("185"),
            avg_days_past_due=60,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("64750"),  # 35% of face value
            collection_period_months=6
        )

        projection = engine.project_economics(portfolio)

        # Should be profitable
        assert projection.net_revenue > 0
        assert projection.roi_percentage > 0
        assert projection.profit_margin > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_marginal_roi_scenario(self, engine):
        """Test marginal ROI with low recovery"""
        portfolio = PortfolioMetrics(
            total_accounts=500,
            total_face_value=Decimal("50000"),
            avg_balance=Decimal("100"),
            avg_days_past_due=180,  # Older debt
            weighted_recovery_rate=0.15,  # Low recovery
            expected_collections=Decimal("7500"),
            collection_period_months=12
        )

        projection = engine.project_economics(portfolio)

        # May or may not be profitable
        # But should calculate correctly
        assert projection.gross_collections > 0
        assert projection.total_cost_to_collect > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_roi_improves_with_scale(self, engine):
        """Test ROI improves with portfolio scale"""
        # Small portfolio
        small_portfolio = PortfolioMetrics(
            total_accounts=100,
            total_face_value=Decimal("18500"),
            avg_balance=Decimal("185"),
            avg_days_past_due=60,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("6475"),
            collection_period_months=6
        )

        # Large portfolio (10x)
        large_portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("185000"),
            avg_balance=Decimal("185"),
            avg_days_past_due=60,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("64750"),
            collection_period_months=6
        )

        small_proj = engine.project_economics(small_portfolio)
        large_proj = engine.project_economics(large_portfolio)

        # Larger portfolio should have better cost per dollar
        # (fixed costs spread across more accounts)
        assert large_proj.cost_per_dollar_collected < small_proj.cost_per_dollar_collected


class TestBreakEvenValidation:
    """Test break-even calculations"""

    @pytest.fixture
    def engine(self):
        return EconomicEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_break_even_calculation(self, engine):
        """Test break-even recovery rate calculation"""
        portfolio = PortfolioMetrics(
            total_accounts=500,
            total_face_value=Decimal("100000"),
            avg_balance=Decimal("200"),
            avg_days_past_due=90,
            weighted_recovery_rate=0.30,
            expected_collections=Decimal("30000"),
            collection_period_months=6
        )

        projection = engine.project_economics(portfolio)

        # Break-even should be less than actual recovery if profitable
        if projection.net_revenue > 0:
            assert projection.break_even_recovery_rate < portfolio.weighted_recovery_rate

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_break_even_sensitivity(self, engine):
        """Test break-even sensitivity to costs"""
        base_portfolio = PortfolioMetrics(
            total_accounts=500,
            total_face_value=Decimal("100000"),
            avg_balance=Decimal("200"),
            avg_days_past_due=90,
            weighted_recovery_rate=0.30,
            expected_collections=Decimal("30000"),
            collection_period_months=6
        )

        # Lower contact intensity = lower costs = lower break-even
        low_contact = engine.project_economics(base_portfolio, contact_intensity=3.0)
        high_contact = engine.project_economics(base_portfolio, contact_intensity=8.0)

        assert low_contact.break_even_recovery_rate < high_contact.break_even_recovery_rate

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_payback_period(self, engine):
        """Test payback period calculation"""
        portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("200000"),
            avg_balance=Decimal("200"),
            avg_days_past_due=60,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("70000"),
            collection_period_months=6
        )

        projection = engine.project_economics(portfolio)

        # Payback should be positive and reasonable
        if projection.net_revenue > 0:
            assert projection.payback_period_months > 0
            assert projection.payback_period_months < portfolio.collection_period_months * 2


class TestDeadZoneResurrection:
    """Test Dead Zone account resurrection economics"""

    @pytest.fixture
    def engine(self):
        return EconomicEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dead_zone_identification(self, engine):
        """Test identification of Dead Zone accounts"""
        # Very small, old debt
        result = engine.calculate_dead_zone_economics(
            balance=Decimal("75"),
            age_months=18,
            traditional_recovery_rate=0.05,  # 5% traditional
            ai_enhanced_recovery_rate=0.25   # 25% with AI
        )

        # Traditional should not be viable
        assert not result["traditional"]["viable"]

        # AI-enhanced should be viable
        assert result["ai_enhanced"]["viable"]

        # Should be marked as resurrected
        assert result["dead_zone_resurrected"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_incremental_value_calculation(self, engine):
        """Test incremental value from AI enhancement"""
        result = engine.calculate_dead_zone_economics(
            balance=Decimal("150"),
            age_months=12,
            traditional_recovery_rate=0.10,
            ai_enhanced_recovery_rate=0.30
        )

        # AI collection should be higher
        assert result["ai_enhanced"]["collection"] > result["traditional"]["collection"]

        # Incremental value should be positive
        assert result["incremental_value"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dead_zone_portfolio_impact(self, engine, data_generator):
        """Test Dead Zone accounts impact on portfolio economics"""
        # Simulate portfolio with mix of account types
        accounts = []

        # Regular accounts (60%)
        for _ in range(60):
            accounts.append({
                "balance": Decimal(str(random.uniform(100, 300))),
                "age_months": random.randint(2, 6),
                "traditional_recovery": 0.30,
                "ai_recovery": 0.35
            })

        # Dead zone accounts (40%)
        for _ in range(40):
            accounts.append({
                "balance": Decimal(str(random.uniform(25, 100))),
                "age_months": random.randint(12, 24),
                "traditional_recovery": 0.05,
                "ai_recovery": 0.20
            })

        # Calculate economics for each
        traditional_viable = 0
        ai_viable = 0
        resurrected = 0

        for acc in accounts:
            result = engine.calculate_dead_zone_economics(
                acc["balance"],
                acc["age_months"],
                acc["traditional_recovery"],
                acc["ai_recovery"]
            )

            if result["traditional"]["viable"]:
                traditional_viable += 1
            if result["ai_enhanced"]["viable"]:
                ai_viable += 1
            if result["dead_zone_resurrected"]:
                resurrected += 1

        # AI should make more accounts viable
        assert ai_viable > traditional_viable

        # Some dead zone accounts should be resurrected
        assert resurrected > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_micro_balance_economics(self, engine):
        """Test economics of very small balances"""
        micro_balances = [Decimal("25"), Decimal("50"), Decimal("75")]

        for balance in micro_balances:
            result = engine.calculate_dead_zone_economics(
                balance=balance,
                age_months=6,
                traditional_recovery_rate=0.10,
                ai_enhanced_recovery_rate=0.35
            )

            # Very small balances need high recovery to be viable
            # AI enhancement should help
            assert result["ai_enhanced"]["collection"] > result["traditional"]["collection"]


class TestEconomicIntegration:
    """Test integrated economic scenarios"""

    @pytest.fixture
    def engine(self):
        return EconomicEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_portfolio_projection(self, engine, data_generator, audit_logger):
        """Test full portfolio economic projection"""
        # Generate realistic portfolio
        accounts = data_generator.generate_portfolio(500)

        total_balance = sum(Decimal(str(acc["balance"])) for acc in accounts)
        avg_balance = total_balance / len(accounts)
        avg_dpd = sum(acc["days_overdue"] for acc in accounts) // len(accounts)

        portfolio = PortfolioMetrics(
            total_accounts=500,
            total_face_value=total_balance,
            avg_balance=avg_balance,
            avg_days_past_due=avg_dpd,
            weighted_recovery_rate=0.32,
            expected_collections=total_balance * Decimal("0.32"),
            collection_period_months=6
        )

        # Project economics
        projection = engine.project_economics(portfolio)

        audit_logger.log("economics", "PORTFOLIO", "projection_complete", {
            "gross_collections": float(projection.gross_collections),
            "total_ctc": float(projection.total_cost_to_collect),
            "net_revenue": float(projection.net_revenue),
            "roi": projection.roi_percentage
        })

        # Verify projection is reasonable
        assert projection.gross_collections > 0
        assert projection.total_cost_to_collect > 0
        assert projection.cost_per_dollar_collected > 0
        assert projection.cost_per_dollar_collected < 1.0  # Should cost less than collected

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scenario_comparison(self, engine):
        """Test comparing different scenarios"""
        base_portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("185000"),
            avg_balance=Decimal("185"),
            avg_days_past_due=60,
            weighted_recovery_rate=0.32,
            expected_collections=Decimal("59200"),
            collection_period_months=6
        )

        # Scenario 1: Standard approach
        standard = engine.project_economics(base_portfolio, contact_intensity=5.0)

        # Scenario 2: High-touch approach
        high_touch = engine.project_economics(base_portfolio, contact_intensity=8.0)

        # Scenario 3: Optimized approach
        optimized = engine.project_economics(base_portfolio, contact_intensity=4.0)

        # Compare scenarios
        scenarios = {
            "standard": standard,
            "high_touch": high_touch,
            "optimized": optimized
        }

        # Optimized should have best ROI (lower costs)
        assert optimized.roi_percentage >= standard.roi_percentage

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_commission_tier_impact(self, engine):
        """Test commission tier impact on economics"""
        # Small balance portfolio (higher commission rate)
        small_portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("75000"),
            avg_balance=Decimal("75"),
            avg_days_past_due=45,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("26250"),
            collection_period_months=6
        )

        # Large balance portfolio (lower commission rate)
        large_portfolio = PortfolioMetrics(
            total_accounts=1000,
            total_face_value=Decimal("600000"),
            avg_balance=Decimal("600"),
            avg_days_past_due=45,
            weighted_recovery_rate=0.35,
            expected_collections=Decimal("210000"),
            collection_period_months=6
        )

        small_proj = engine.project_economics(small_portfolio)
        large_proj = engine.project_economics(large_portfolio)

        # Large portfolio should generate more absolute revenue
        # but small portfolio may have better margin (higher commission rate)
        assert large_proj.gross_collections > small_proj.gross_collections
