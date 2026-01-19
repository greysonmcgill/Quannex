"""
QUAN Recovery - Comprehensive Risk Management Engine

Enterprise-grade risk management system for debt portfolio operations.
Covers portfolio risk, operational risk, counterparty risk, model risk,
liquidity risk, and risk limits/controls.

Author: QUAN Recovery Platform
Version: 1.0.0
"""

import asyncio
import math
import random
import statistics
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMERATIONS AND CONSTANTS
# =============================================================================

class RiskLevel(Enum):
    """Risk severity levels"""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Categories of risk"""
    PORTFOLIO = "portfolio"
    OPERATIONAL = "operational"
    COUNTERPARTY = "counterparty"
    MODEL = "model"
    LIQUIDITY = "liquidity"
    COMPLIANCE = "compliance"
    MARKET = "market"


class VaRMethod(Enum):
    """Value at Risk calculation methods"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


class DebtType(Enum):
    """Types of debt"""
    CREDIT_CARD = "credit_card"
    MEDICAL = "medical"
    STUDENT_LOAN = "student_loan"
    AUTO_LOAN = "auto_loan"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    UTILITY = "utility"
    TELECOM = "telecom"
    RETAIL = "retail"
    OTHER = "other"


class StressScenario(Enum):
    """Predefined stress test scenarios"""
    RECESSION = "recession"
    UNEMPLOYMENT_SPIKE = "unemployment_spike"
    INTEREST_RATE_SHOCK = "interest_rate_shock"
    REGULATORY_CHANGE = "regulatory_change"
    PANDEMIC = "pandemic"
    REGIONAL_CRISIS = "regional_crisis"
    CREDITOR_DEFAULT = "creditor_default"
    SYSTEM_OUTAGE = "system_outage"


# State-specific regulatory risk factors
STATE_REGULATORY_RISK = {
    "CA": 0.85,  # High regulation
    "NY": 0.80,
    "MA": 0.75,
    "IL": 0.70,
    "TX": 0.40,  # Lower regulation
    "FL": 0.45,
    "NC": 0.50,
    "OH": 0.55,
    "PA": 0.60,
    "GA": 0.50,
    # Default for unlisted states
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Position:
    """A position in the debt portfolio"""
    position_id: str
    account_id: str
    creditor_id: str
    debt_type: DebtType
    original_balance: Decimal
    current_balance: Decimal
    purchase_price: Decimal
    state: str
    vintage_date: datetime
    last_payment_date: Optional[datetime] = None
    recovery_probability: float = 0.30
    expected_recovery: Decimal = Decimal("0")
    days_since_last_activity: int = 0
    litigation_flag: bool = False
    bankruptcy_flag: bool = False
    disputed_flag: bool = False
    contact_attempts: int = 0


@dataclass
class VaRResult:
    """Value at Risk calculation result"""
    method: VaRMethod
    confidence_level: float
    time_horizon_days: int
    var_amount: Decimal
    var_percentage: float
    expected_shortfall: Decimal  # CVaR
    expected_shortfall_percentage: float
    calculation_date: datetime
    portfolio_value: Decimal
    scenarios_used: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConcentrationRisk:
    """Concentration risk metrics"""
    dimension: str  # creditor, geography, debt_type
    concentration_ratio: float  # Top N concentration
    herfindahl_index: float  # HHI
    top_exposures: List[Tuple[str, Decimal, float]]  # (name, amount, percentage)
    risk_level: RiskLevel
    recommendations: List[str]


@dataclass
class VintageAnalysis:
    """Vintage cohort analysis"""
    vintage_period: str  # e.g., "2024-Q1"
    accounts_count: int
    total_balance: Decimal
    recovery_rate: float
    roll_rates: Dict[str, float]  # Delinquency progression
    loss_rate: float
    avg_days_to_recovery: float
    benchmark_comparison: float  # vs historical average


@dataclass
class ComplianceViolationRisk:
    """Compliance violation probability assessment"""
    account_id: str
    overall_risk_score: float
    tcpa_risk: float
    fdcpa_risk: float
    state_specific_risk: float
    litigation_probability: float
    risk_factors: List[str]
    recommended_actions: List[str]


@dataclass
class CounterpartyRiskAssessment:
    """Counterparty risk assessment"""
    counterparty_id: str
    counterparty_type: str  # creditor, payment_processor, servicer
    default_probability: float
    credit_rating: str
    exposure_amount: Decimal
    expected_loss: Decimal
    settlement_timing_risk: float
    reliability_score: float
    risk_level: RiskLevel


@dataclass
class ModelPerformanceMetrics:
    """Model performance tracking"""
    model_id: str
    model_name: str
    prediction_accuracy: float
    auc_roc: float
    precision: float
    recall: float
    f1_score: float
    calibration_error: float
    confidence_interval: Tuple[float, float]
    drift_score: float
    last_retrain_date: datetime
    samples_since_retrain: int


@dataclass
class BacktestResult:
    """Backtesting result for predictions"""
    test_period_start: datetime
    test_period_end: datetime
    predictions_made: int
    correct_predictions: int
    accuracy: float
    mean_absolute_error: float
    root_mean_squared_error: float
    actual_vs_predicted_ratio: float
    confidence_intervals_coverage: float


@dataclass
class ABTestResult:
    """A/B test significance tracking"""
    test_id: str
    test_name: str
    variant_a_name: str
    variant_b_name: str
    variant_a_samples: int
    variant_b_samples: int
    variant_a_conversion: float
    variant_b_conversion: float
    relative_lift: float
    p_value: float
    confidence_level: float
    is_significant: bool
    recommended_winner: Optional[str]
    minimum_detectable_effect: float


@dataclass
class LiquidityPosition:
    """Liquidity position assessment"""
    assessment_date: datetime
    available_cash: Decimal
    expected_inflows_30d: Decimal
    expected_outflows_30d: Decimal
    net_position_30d: Decimal
    settlement_obligations: Decimal
    reserve_requirement: Decimal
    current_reserve: Decimal
    reserve_coverage_ratio: float
    liquidity_ratio: float
    days_cash_on_hand: int
    risk_level: RiskLevel


@dataclass
class RiskLimit:
    """Risk limit definition"""
    limit_id: str
    limit_name: str
    category: RiskCategory
    metric_name: str
    soft_limit: float
    hard_limit: float
    current_value: float
    utilization: float
    breach_status: str  # "normal", "warning", "breach"
    last_updated: datetime
    auto_action: Optional[str] = None


@dataclass
class DeRiskingAction:
    """De-risking action trigger"""
    action_id: str
    trigger_condition: str
    action_type: str
    severity: RiskLevel
    positions_affected: List[str]
    estimated_impact: Decimal
    execution_status: str
    triggered_at: datetime
    executed_at: Optional[datetime] = None


@dataclass
class RiskDashboardMetrics:
    """Risk dashboard real-time metrics"""
    timestamp: datetime
    portfolio_var_1d: Decimal
    portfolio_cvar_1d: Decimal
    total_exposure: Decimal
    concentration_score: float
    compliance_risk_score: float
    operational_risk_score: float
    counterparty_risk_score: float
    model_risk_score: float
    liquidity_ratio: float
    overall_risk_score: float
    overall_risk_level: RiskLevel
    active_breaches: int
    pending_actions: int


@dataclass
class StressTestResult:
    """Stress test scenario result"""
    scenario: StressScenario
    scenario_name: str
    base_portfolio_value: Decimal
    stressed_portfolio_value: Decimal
    loss_amount: Decimal
    loss_percentage: float
    recovery_rate_impact: float
    accounts_at_risk: int
    capital_adequacy_post_stress: float
    actions_recommended: List[str]


# =============================================================================
# VALUE AT RISK CALCULATOR
# =============================================================================

class VaRCalculator:
    """
    Value at Risk calculator supporting multiple methodologies.

    Implements:
    - Historical VaR
    - Parametric (Variance-Covariance) VaR
    - Monte Carlo VaR
    """

    def __init__(
        self,
        historical_returns: Optional[List[float]] = None,
        mean_return: float = 0.0,
        volatility: float = 0.10,
    ):
        self.historical_returns = historical_returns or []
        self.mean_return = mean_return
        self.volatility = volatility

    def calculate_var(
        self,
        portfolio_value: Decimal,
        confidence_level: float = 0.95,
        time_horizon_days: int = 1,
        method: VaRMethod = VaRMethod.HISTORICAL,
        simulations: int = 10000,
    ) -> VaRResult:
        """
        Calculate Value at Risk using specified method.

        Args:
            portfolio_value: Current portfolio value
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            time_horizon_days: Time horizon in days
            method: VaR calculation method
            simulations: Number of Monte Carlo simulations

        Returns:
            VaRResult with VaR and Expected Shortfall
        """

        if method == VaRMethod.HISTORICAL:
            return self._historical_var(
                portfolio_value, confidence_level, time_horizon_days
            )
        elif method == VaRMethod.PARAMETRIC:
            return self._parametric_var(
                portfolio_value, confidence_level, time_horizon_days
            )
        elif method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(
                portfolio_value, confidence_level, time_horizon_days, simulations
            )
        else:
            raise ValueError(f"Unknown VaR method: {method}")

    def _historical_var(
        self,
        portfolio_value: Decimal,
        confidence_level: float,
        time_horizon_days: int,
    ) -> VaRResult:
        """Calculate VaR using historical simulation"""

        if not self.historical_returns:
            # Generate synthetic returns if no historical data
            self.historical_returns = self._generate_synthetic_returns(1000)

        # Scale returns to time horizon
        scaled_returns = [
            r * math.sqrt(time_horizon_days) for r in self.historical_returns
        ]

        # Sort returns (losses are negative)
        sorted_returns = sorted(scaled_returns)

        # Find VaR percentile
        var_index = int((1 - confidence_level) * len(sorted_returns))
        var_return = sorted_returns[var_index]

        # Calculate VaR amount
        var_amount = Decimal(str(abs(var_return))) * portfolio_value
        var_percentage = abs(var_return)

        # Calculate Expected Shortfall (average of losses beyond VaR)
        tail_returns = sorted_returns[:var_index + 1]
        es_return = statistics.mean(tail_returns) if tail_returns else var_return
        es_amount = Decimal(str(abs(es_return))) * portfolio_value
        es_percentage = abs(es_return)

        return VaRResult(
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence_level,
            time_horizon_days=time_horizon_days,
            var_amount=var_amount,
            var_percentage=var_percentage,
            expected_shortfall=es_amount,
            expected_shortfall_percentage=es_percentage,
            calculation_date=datetime.now(),
            portfolio_value=portfolio_value,
            scenarios_used=len(self.historical_returns),
            details={
                "min_return": min(sorted_returns),
                "max_return": max(sorted_returns),
                "mean_return": statistics.mean(sorted_returns),
                "std_return": statistics.stdev(sorted_returns) if len(sorted_returns) > 1 else 0,
            }
        )

    def _parametric_var(
        self,
        portfolio_value: Decimal,
        confidence_level: float,
        time_horizon_days: int,
    ) -> VaRResult:
        """Calculate VaR using parametric (variance-covariance) method"""

        # Z-score for confidence level
        z_scores = {
            0.90: 1.282,
            0.95: 1.645,
            0.99: 2.326,
            0.995: 2.576,
            0.999: 3.090,
        }
        z_score = z_scores.get(confidence_level, 1.645)

        # Scale volatility to time horizon
        scaled_volatility = self.volatility * math.sqrt(time_horizon_days)

        # VaR = Z * sigma * portfolio_value
        var_percentage = z_score * scaled_volatility
        var_amount = Decimal(str(var_percentage)) * portfolio_value

        # Expected Shortfall for normal distribution
        # ES = sigma * phi(z) / (1 - alpha) where phi is the PDF
        pdf_at_z = math.exp(-0.5 * z_score ** 2) / math.sqrt(2 * math.pi)
        es_percentage = scaled_volatility * pdf_at_z / (1 - confidence_level)
        es_amount = Decimal(str(es_percentage)) * portfolio_value

        return VaRResult(
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence_level,
            time_horizon_days=time_horizon_days,
            var_amount=var_amount,
            var_percentage=var_percentage,
            expected_shortfall=es_amount,
            expected_shortfall_percentage=es_percentage,
            calculation_date=datetime.now(),
            portfolio_value=portfolio_value,
            details={
                "z_score": z_score,
                "volatility": self.volatility,
                "scaled_volatility": scaled_volatility,
                "mean_return": self.mean_return,
            }
        )

    def _monte_carlo_var(
        self,
        portfolio_value: Decimal,
        confidence_level: float,
        time_horizon_days: int,
        simulations: int,
    ) -> VaRResult:
        """Calculate VaR using Monte Carlo simulation"""

        # Generate simulated returns
        simulated_values = []

        for _ in range(simulations):
            # Simulate path using geometric Brownian motion
            daily_return = random.gauss(
                self.mean_return / 252,  # Daily mean
                self.volatility / math.sqrt(252)  # Daily volatility
            )

            # Compound over time horizon
            total_return = 1.0
            for _ in range(time_horizon_days):
                daily_r = random.gauss(
                    self.mean_return / 252,
                    self.volatility / math.sqrt(252)
                )
                total_return *= (1 + daily_r)

            simulated_values.append(total_return - 1)  # Return

        # Sort returns
        sorted_returns = sorted(simulated_values)

        # Find VaR percentile
        var_index = int((1 - confidence_level) * simulations)
        var_return = sorted_returns[var_index]

        var_amount = Decimal(str(abs(var_return))) * portfolio_value
        var_percentage = abs(var_return)

        # Expected Shortfall
        tail_returns = sorted_returns[:var_index + 1]
        es_return = statistics.mean(tail_returns) if tail_returns else var_return
        es_amount = Decimal(str(abs(es_return))) * portfolio_value
        es_percentage = abs(es_return)

        return VaRResult(
            method=VaRMethod.MONTE_CARLO,
            confidence_level=confidence_level,
            time_horizon_days=time_horizon_days,
            var_amount=var_amount,
            var_percentage=var_percentage,
            expected_shortfall=es_amount,
            expected_shortfall_percentage=es_percentage,
            calculation_date=datetime.now(),
            portfolio_value=portfolio_value,
            scenarios_used=simulations,
            details={
                "simulations": simulations,
                "min_simulated_return": min(sorted_returns),
                "max_simulated_return": max(sorted_returns),
                "mean_simulated_return": statistics.mean(sorted_returns),
                "std_simulated_return": statistics.stdev(sorted_returns),
            }
        )

    def _generate_synthetic_returns(self, n: int) -> List[float]:
        """Generate synthetic returns for testing"""
        returns = []
        for _ in range(n):
            # Mix of normal returns and occasional large losses
            if random.random() < 0.05:  # 5% chance of stress event
                r = random.gauss(-0.05, 0.03)  # Large negative
            else:
                r = random.gauss(0.001, 0.015)  # Normal daily return
            returns.append(r)
        return returns

    def update_historical_returns(self, new_returns: List[float]):
        """Update historical returns with new data"""
        self.historical_returns.extend(new_returns)
        # Keep last 1000 observations
        if len(self.historical_returns) > 1000:
            self.historical_returns = self.historical_returns[-1000:]


# =============================================================================
# PORTFOLIO RISK MANAGER
# =============================================================================

class PortfolioRiskManager:
    """
    Portfolio-level risk management.

    Handles:
    - Value at Risk calculations
    - Expected Shortfall / Conditional VaR
    - Concentration risk analysis
    - Vintage analysis and cohort tracking
    """

    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.var_calculator = VaRCalculator()
        self.vintage_cohorts: Dict[str, List[str]] = defaultdict(list)
        self._historical_recoveries: List[float] = []

    def add_position(self, position: Position):
        """Add a position to the portfolio"""
        self.positions[position.position_id] = position

        # Track vintage
        vintage_key = position.vintage_date.strftime("%Y-Q%q").replace(
            "%q", str((position.vintage_date.month - 1) // 3 + 1)
        )
        self.vintage_cohorts[vintage_key].append(position.position_id)

    def get_portfolio_value(self) -> Decimal:
        """Get total portfolio value (expected recovery)"""
        return sum(
            p.current_balance * Decimal(str(p.recovery_probability))
            for p in self.positions.values()
        )

    def get_total_exposure(self) -> Decimal:
        """Get total exposure (current balance)"""
        return sum(p.current_balance for p in self.positions.values())

    def calculate_portfolio_var(
        self,
        confidence_level: float = 0.95,
        time_horizon_days: int = 1,
        method: VaRMethod = VaRMethod.MONTE_CARLO,
    ) -> VaRResult:
        """Calculate portfolio-level VaR"""

        portfolio_value = self.get_portfolio_value()

        # Update volatility based on position characteristics
        if self.positions:
            # Calculate portfolio volatility from position risks
            total_value = float(portfolio_value)
            weighted_vol = 0.0

            for pos in self.positions.values():
                pos_value = float(pos.current_balance * Decimal(str(pos.recovery_probability)))
                weight = pos_value / total_value if total_value > 0 else 0

                # Base volatility adjusted for risk factors
                base_vol = 0.15  # 15% base volatility
                if pos.bankruptcy_flag:
                    base_vol *= 1.5
                if pos.disputed_flag:
                    base_vol *= 1.3
                if pos.litigation_flag:
                    base_vol *= 1.2

                weighted_vol += weight * base_vol

            self.var_calculator.volatility = weighted_vol

        return self.var_calculator.calculate_var(
            portfolio_value,
            confidence_level,
            time_horizon_days,
            method,
        )

    def analyze_concentration_risk(
        self,
        dimension: str = "creditor",
        top_n: int = 10,
    ) -> ConcentrationRisk:
        """
        Analyze concentration risk by specified dimension.

        Args:
            dimension: "creditor", "state", "debt_type"
            top_n: Number of top exposures to report
        """

        # Group positions by dimension
        groups: Dict[str, Decimal] = defaultdict(Decimal)

        for pos in self.positions.values():
            if dimension == "creditor":
                key = pos.creditor_id
            elif dimension == "state":
                key = pos.state
            elif dimension == "debt_type":
                key = pos.debt_type.value
            else:
                key = "unknown"

            groups[key] += pos.current_balance

        total_exposure = sum(groups.values())

        if total_exposure == 0:
            return ConcentrationRisk(
                dimension=dimension,
                concentration_ratio=0.0,
                herfindahl_index=0.0,
                top_exposures=[],
                risk_level=RiskLevel.MINIMAL,
                recommendations=["Portfolio is empty"]
            )

        # Calculate concentration metrics
        shares = [(k, v, float(v / total_exposure)) for k, v in groups.items()]
        shares.sort(key=lambda x: x[1], reverse=True)

        # Top N concentration ratio
        top_n_exposure = sum(s[1] for s in shares[:top_n])
        concentration_ratio = float(top_n_exposure / total_exposure)

        # Herfindahl-Hirschman Index
        hhi = sum(s[2] ** 2 for s in shares)

        # Determine risk level
        if hhi > 0.25:
            risk_level = RiskLevel.CRITICAL
        elif hhi > 0.15:
            risk_level = RiskLevel.HIGH
        elif hhi > 0.10:
            risk_level = RiskLevel.MODERATE
        elif hhi > 0.05:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL

        # Generate recommendations
        recommendations = []
        if concentration_ratio > 0.5:
            recommendations.append(
                f"Top {top_n} {dimension}s represent {concentration_ratio:.0%} of exposure. "
                f"Consider diversification."
            )
        if hhi > 0.15:
            recommendations.append(
                f"HHI of {hhi:.3f} indicates high concentration. "
                f"Limit new positions in top {dimension}s."
            )

        return ConcentrationRisk(
            dimension=dimension,
            concentration_ratio=concentration_ratio,
            herfindahl_index=hhi,
            top_exposures=shares[:top_n],
            risk_level=risk_level,
            recommendations=recommendations,
        )

    def analyze_vintage(self, vintage_period: str) -> Optional[VintageAnalysis]:
        """
        Analyze performance of a vintage cohort.

        Args:
            vintage_period: Period string like "2024-Q1"
        """

        position_ids = self.vintage_cohorts.get(vintage_period, [])

        if not position_ids:
            return None

        positions = [self.positions[pid] for pid in position_ids if pid in self.positions]

        if not positions:
            return None

        # Calculate metrics
        total_balance = sum(p.current_balance for p in positions)
        total_original = sum(p.original_balance for p in positions)

        # Recovery rate (simplified - would use actual collections in production)
        avg_recovery_prob = statistics.mean(p.recovery_probability for p in positions)

        # Roll rates (delinquency progression)
        roll_rates = {
            "current_to_30dpd": 0.08,
            "30dpd_to_60dpd": 0.25,
            "60dpd_to_90dpd": 0.35,
            "90dpd_to_chargeoff": 0.45,
        }

        # Loss rate
        loss_rate = float((total_original - total_balance) / total_original) if total_original > 0 else 0

        # Average days to recovery
        recovery_days = []
        for p in positions:
            if p.last_payment_date:
                days = (p.last_payment_date - p.vintage_date).days
                recovery_days.append(days)

        avg_days_to_recovery = statistics.mean(recovery_days) if recovery_days else 180.0

        # Benchmark comparison (vs historical average of 30%)
        benchmark_recovery = 0.30
        benchmark_comparison = avg_recovery_prob / benchmark_recovery

        return VintageAnalysis(
            vintage_period=vintage_period,
            accounts_count=len(positions),
            total_balance=total_balance,
            recovery_rate=avg_recovery_prob,
            roll_rates=roll_rates,
            loss_rate=loss_rate,
            avg_days_to_recovery=avg_days_to_recovery,
            benchmark_comparison=benchmark_comparison,
        )

    def get_all_vintages(self) -> Dict[str, VintageAnalysis]:
        """Get analysis for all vintages"""
        results = {}
        for vintage_period in self.vintage_cohorts:
            analysis = self.analyze_vintage(vintage_period)
            if analysis:
                results[vintage_period] = analysis
        return results


# =============================================================================
# OPERATIONAL RISK MANAGER
# =============================================================================

class OperationalRiskManager:
    """
    Operational risk management.

    Handles:
    - Compliance violation probability scoring
    - Contact frequency limits enforcement
    - State-specific regulatory risk flags
    - Litigation risk assessment
    """

    # Contact limits by regulation
    MAX_CALLS_PER_WEEK = 7  # FDCPA Reg F
    MAX_CALLS_PER_DAY = 1
    MAX_SMS_PER_DAY = 3
    MAX_EMAILS_PER_WEEK = 14

    def __init__(self):
        self.contact_history: Dict[str, List[Dict]] = defaultdict(list)
        self.compliance_violations: Dict[str, List[Dict]] = defaultdict(list)
        self.litigation_history: Dict[str, List[Dict]] = defaultdict(list)

    def assess_compliance_risk(
        self,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> ComplianceViolationRisk:
        """
        Assess compliance violation probability for an account.

        Factors:
        - Contact frequency violations
        - TCPA consent issues
        - FDCPA violations
        - State-specific regulations
        """

        risk_factors = []

        # TCPA Risk Assessment
        tcpa_risk = self._calculate_tcpa_risk(account_id, account_data)
        if tcpa_risk > 0.3:
            risk_factors.append(f"TCPA risk elevated: {tcpa_risk:.0%}")

        # FDCPA Risk Assessment
        fdcpa_risk = self._calculate_fdcpa_risk(account_id, account_data)
        if fdcpa_risk > 0.3:
            risk_factors.append(f"FDCPA risk elevated: {fdcpa_risk:.0%}")

        # State-specific Risk
        state = account_data.get("state", "NY")
        state_risk = STATE_REGULATORY_RISK.get(state, 0.55)
        if state_risk > 0.6:
            risk_factors.append(f"High-regulation state: {state}")

        # Litigation Risk
        litigation_prob = self._calculate_litigation_risk(account_id, account_data)
        if litigation_prob > 0.1:
            risk_factors.append(f"Litigation risk: {litigation_prob:.0%}")

        # Overall risk score
        overall_risk = (
            tcpa_risk * 0.30 +
            fdcpa_risk * 0.30 +
            state_risk * 0.20 +
            litigation_prob * 0.20
        )

        # Generate recommendations
        recommendations = self._generate_compliance_recommendations(
            tcpa_risk, fdcpa_risk, state_risk, litigation_prob, account_data
        )

        return ComplianceViolationRisk(
            account_id=account_id,
            overall_risk_score=overall_risk,
            tcpa_risk=tcpa_risk,
            fdcpa_risk=fdcpa_risk,
            state_specific_risk=state_risk,
            litigation_probability=litigation_prob,
            risk_factors=risk_factors,
            recommended_actions=recommendations,
        )

    def _calculate_tcpa_risk(
        self,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> float:
        """Calculate TCPA violation risk"""

        risk = 0.0

        # Check SMS consent
        if not account_data.get("sms_consent"):
            risk += 0.3

        # Check calling hours compliance history
        contacts = self.contact_history.get(account_id, [])
        after_hours_contacts = sum(
            1 for c in contacts
            if c.get("after_hours", False)
        )
        if after_hours_contacts > 0:
            risk += min(0.4, after_hours_contacts * 0.1)

        # Check DNC status
        if account_data.get("on_dnc_list"):
            risk += 0.5

        return min(1.0, risk)

    def _calculate_fdcpa_risk(
        self,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> float:
        """Calculate FDCPA violation risk"""

        risk = 0.0

        # Check contact frequency
        contacts = self.contact_history.get(account_id, [])
        now = datetime.now()

        # Calls this week
        week_ago = now - timedelta(days=7)
        calls_this_week = sum(
            1 for c in contacts
            if c.get("type") == "call" and c.get("timestamp", now) > week_ago
        )

        if calls_this_week > self.MAX_CALLS_PER_WEEK:
            risk += 0.5
        elif calls_this_week > self.MAX_CALLS_PER_WEEK - 2:
            risk += 0.2

        # Check for cease communication request
        if account_data.get("cease_requested"):
            risk += 0.8

        # Check validation period
        if account_data.get("in_validation_period"):
            risk += 0.4

        # Check if disputed
        if account_data.get("disputed"):
            risk += 0.3

        return min(1.0, risk)

    def _calculate_litigation_risk(
        self,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> float:
        """Calculate litigation risk probability"""

        risk = 0.0

        # Prior litigation
        if account_data.get("prior_litigation"):
            risk += 0.4

        # Consumer has attorney
        if account_data.get("has_attorney"):
            risk += 0.5

        # High balance (more likely to litigate)
        balance = float(account_data.get("balance", 0))
        if balance > 5000:
            risk += 0.2
        elif balance > 10000:
            risk += 0.3

        # State propensity for consumer litigation
        state = account_data.get("state", "NY")
        litigation_states = {"CA": 0.2, "NY": 0.15, "FL": 0.15, "TX": 0.1}
        risk += litigation_states.get(state, 0.05)

        # Previous complaints
        complaints = account_data.get("complaint_count", 0)
        risk += min(0.3, complaints * 0.1)

        return min(1.0, risk)

    def _generate_compliance_recommendations(
        self,
        tcpa_risk: float,
        fdcpa_risk: float,
        state_risk: float,
        litigation_risk: float,
        account_data: Dict[str, Any],
    ) -> List[str]:
        """Generate compliance recommendations"""

        recommendations = []

        if tcpa_risk > 0.5:
            recommendations.append("HIGH TCPA RISK: Verify consent before any calls/SMS")
            recommendations.append("Consider mail-only communication strategy")

        if fdcpa_risk > 0.5:
            recommendations.append("HIGH FDCPA RISK: Review contact frequency immediately")
            recommendations.append("Ensure mini-Miranda is included in all communications")

        if state_risk > 0.7:
            state = account_data.get("state", "Unknown")
            recommendations.append(f"HIGH-REGULATION STATE ({state}): Apply stricter protocols")
            recommendations.append("Review state-specific collection requirements")

        if litigation_risk > 0.3:
            recommendations.append("LITIGATION RISK: Flag for legal review before action")
            recommendations.append("Document all communications meticulously")

        if not recommendations:
            recommendations.append("Standard compliance protocols apply")

        return recommendations

    def check_contact_limits(
        self,
        account_id: str,
        contact_type: str,
    ) -> Tuple[bool, str]:
        """
        Check if contact is within limits.

        Returns:
            Tuple of (is_allowed, reason)
        """

        contacts = self.contact_history.get(account_id, [])
        now = datetime.now()

        if contact_type == "call":
            # Check daily limit
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            calls_today = sum(
                1 for c in contacts
                if c.get("type") == "call" and c.get("timestamp", now) >= today_start
            )

            if calls_today >= self.MAX_CALLS_PER_DAY:
                return False, f"Daily call limit reached ({calls_today}/{self.MAX_CALLS_PER_DAY})"

            # Check weekly limit
            week_ago = now - timedelta(days=7)
            calls_week = sum(
                1 for c in contacts
                if c.get("type") == "call" and c.get("timestamp", now) > week_ago
            )

            if calls_week >= self.MAX_CALLS_PER_WEEK:
                return False, f"Weekly call limit reached ({calls_week}/{self.MAX_CALLS_PER_WEEK})"

        elif contact_type == "sms":
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            sms_today = sum(
                1 for c in contacts
                if c.get("type") == "sms" and c.get("timestamp", now) >= today_start
            )

            if sms_today >= self.MAX_SMS_PER_DAY:
                return False, f"Daily SMS limit reached ({sms_today}/{self.MAX_SMS_PER_DAY})"

        return True, "Contact within limits"

    def record_contact(
        self,
        account_id: str,
        contact_type: str,
        timestamp: Optional[datetime] = None,
        after_hours: bool = False,
    ):
        """Record a contact attempt"""

        if timestamp is None:
            timestamp = datetime.now()

        self.contact_history[account_id].append({
            "type": contact_type,
            "timestamp": timestamp,
            "after_hours": after_hours,
        })

    def get_state_regulatory_flags(self, state: str) -> Dict[str, Any]:
        """Get state-specific regulatory requirements"""

        # State-specific requirements (simplified)
        requirements = {
            "CA": {
                "license_required": True,
                "bond_required": True,
                "bond_amount": 25000,
                "additional_disclosures": True,
                "cease_desist_period_days": 30,
                "interest_restrictions": True,
                "fee_restrictions": True,
            },
            "NY": {
                "license_required": True,
                "bond_required": True,
                "bond_amount": 10000,
                "additional_disclosures": True,
                "cease_desist_period_days": 30,
                "interest_restrictions": True,
                "fee_restrictions": False,
            },
            "TX": {
                "license_required": False,
                "bond_required": True,
                "bond_amount": 10000,
                "additional_disclosures": False,
                "cease_desist_period_days": 0,
                "interest_restrictions": False,
                "fee_restrictions": False,
            },
        }

        default = {
            "license_required": True,
            "bond_required": False,
            "bond_amount": 0,
            "additional_disclosures": False,
            "cease_desist_period_days": 0,
            "interest_restrictions": False,
            "fee_restrictions": False,
        }

        return requirements.get(state, default)


# =============================================================================
# COUNTERPARTY RISK MANAGER
# =============================================================================

class CounterpartyRiskManager:
    """
    Counterparty risk management.

    Handles:
    - Creditor default probability
    - Settlement timing risk
    - Payment processor reliability scoring
    """

    def __init__(self):
        self.counterparties: Dict[str, Dict[str, Any]] = {}
        self.settlement_history: Dict[str, List[Dict]] = defaultdict(list)
        self.payment_processor_metrics: Dict[str, Dict] = {}

    def add_counterparty(
        self,
        counterparty_id: str,
        counterparty_type: str,
        credit_rating: str = "BBB",
        financial_data: Optional[Dict] = None,
    ):
        """Add a counterparty for monitoring"""

        self.counterparties[counterparty_id] = {
            "type": counterparty_type,
            "credit_rating": credit_rating,
            "financial_data": financial_data or {},
            "added_date": datetime.now(),
        }

    def assess_counterparty_risk(
        self,
        counterparty_id: str,
        exposure_amount: Decimal,
    ) -> CounterpartyRiskAssessment:
        """Assess risk for a counterparty"""

        counterparty = self.counterparties.get(counterparty_id, {})
        counterparty_type = counterparty.get("type", "unknown")
        credit_rating = counterparty.get("credit_rating", "NR")

        # Calculate default probability based on credit rating
        default_probs = {
            "AAA": 0.001,
            "AA": 0.002,
            "A": 0.005,
            "BBB": 0.015,
            "BB": 0.05,
            "B": 0.10,
            "CCC": 0.25,
            "CC": 0.50,
            "C": 0.75,
            "D": 1.0,
            "NR": 0.10,  # Not rated - assume moderate risk
        }

        default_probability = default_probs.get(credit_rating, 0.10)

        # Calculate expected loss
        loss_given_default = Decimal("0.60")  # Assume 60% LGD
        expected_loss = exposure_amount * Decimal(str(default_probability)) * loss_given_default

        # Settlement timing risk
        settlement_timing_risk = self._calculate_settlement_timing_risk(counterparty_id)

        # Reliability score (for payment processors)
        reliability_score = self._calculate_reliability_score(counterparty_id)

        # Determine risk level
        if default_probability > 0.20:
            risk_level = RiskLevel.CRITICAL
        elif default_probability > 0.10:
            risk_level = RiskLevel.HIGH
        elif default_probability > 0.05:
            risk_level = RiskLevel.MODERATE
        elif default_probability > 0.01:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL

        return CounterpartyRiskAssessment(
            counterparty_id=counterparty_id,
            counterparty_type=counterparty_type,
            default_probability=default_probability,
            credit_rating=credit_rating,
            exposure_amount=exposure_amount,
            expected_loss=expected_loss,
            settlement_timing_risk=settlement_timing_risk,
            reliability_score=reliability_score,
            risk_level=risk_level,
        )

    def _calculate_settlement_timing_risk(self, counterparty_id: str) -> float:
        """Calculate settlement timing risk based on history"""

        settlements = self.settlement_history.get(counterparty_id, [])

        if not settlements:
            return 0.1  # Default low risk for new counterparties

        # Calculate delay statistics
        delays = []
        for s in settlements:
            expected = s.get("expected_date")
            actual = s.get("actual_date")
            if expected and actual:
                delay = (actual - expected).days
                delays.append(delay)

        if not delays:
            return 0.1

        avg_delay = statistics.mean(delays)
        max_delay = max(delays)

        # Risk score based on delays
        risk = 0.0

        if avg_delay > 5:
            risk += 0.3
        elif avg_delay > 2:
            risk += 0.1

        if max_delay > 14:
            risk += 0.4
        elif max_delay > 7:
            risk += 0.2

        # Recent trend
        recent_delays = delays[-5:]
        if recent_delays and statistics.mean(recent_delays) > avg_delay:
            risk += 0.1  # Worsening trend

        return min(1.0, risk)

    def _calculate_reliability_score(self, counterparty_id: str) -> float:
        """Calculate reliability score for payment processors"""

        metrics = self.payment_processor_metrics.get(counterparty_id, {})

        uptime = metrics.get("uptime_pct", 99.9)
        success_rate = metrics.get("transaction_success_rate", 99.0)
        avg_response_time = metrics.get("avg_response_ms", 200)

        # Score from 0-1
        uptime_score = min(1.0, uptime / 100)
        success_score = min(1.0, success_rate / 100)
        latency_score = max(0, 1 - (avg_response_time - 100) / 1000)

        reliability = (uptime_score * 0.4 + success_score * 0.4 + latency_score * 0.2)

        return reliability

    def record_settlement(
        self,
        counterparty_id: str,
        amount: Decimal,
        expected_date: datetime,
        actual_date: Optional[datetime] = None,
    ):
        """Record a settlement for tracking"""

        self.settlement_history[counterparty_id].append({
            "amount": amount,
            "expected_date": expected_date,
            "actual_date": actual_date or datetime.now(),
        })

    def update_processor_metrics(
        self,
        processor_id: str,
        uptime_pct: float,
        success_rate: float,
        avg_response_ms: float,
    ):
        """Update payment processor metrics"""

        self.payment_processor_metrics[processor_id] = {
            "uptime_pct": uptime_pct,
            "transaction_success_rate": success_rate,
            "avg_response_ms": avg_response_ms,
            "updated_at": datetime.now(),
        }


# =============================================================================
# MODEL RISK MANAGER
# =============================================================================

class ModelRiskManager:
    """
    Model risk management.

    Handles:
    - Recovery prediction confidence intervals
    - Model drift detection
    - Backtesting framework
    - A/B test significance tracking
    """

    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        self.predictions: Dict[str, List[Dict]] = defaultdict(list)
        self.actuals: Dict[str, List[Dict]] = defaultdict(list)
        self.ab_tests: Dict[str, Dict] = {}
        self.drift_baselines: Dict[str, Dict] = {}

    def register_model(
        self,
        model_id: str,
        model_name: str,
        model_type: str,
        features: List[str],
        training_date: datetime,
    ):
        """Register a model for monitoring"""

        self.models[model_id] = {
            "name": model_name,
            "type": model_type,
            "features": features,
            "training_date": training_date,
            "predictions_count": 0,
        }

    def record_prediction(
        self,
        model_id: str,
        prediction_id: str,
        prediction_value: float,
        confidence_lower: float,
        confidence_upper: float,
        features: Dict[str, Any],
    ):
        """Record a model prediction"""

        self.predictions[model_id].append({
            "prediction_id": prediction_id,
            "value": prediction_value,
            "confidence_lower": confidence_lower,
            "confidence_upper": confidence_upper,
            "features": features,
            "timestamp": datetime.now(),
        })

        if model_id in self.models:
            self.models[model_id]["predictions_count"] += 1

    def record_actual(
        self,
        model_id: str,
        prediction_id: str,
        actual_value: float,
    ):
        """Record actual outcome for a prediction"""

        self.actuals[model_id].append({
            "prediction_id": prediction_id,
            "actual_value": actual_value,
            "timestamp": datetime.now(),
        })

    def calculate_model_metrics(self, model_id: str) -> Optional[ModelPerformanceMetrics]:
        """Calculate performance metrics for a model"""

        if model_id not in self.models:
            return None

        model_info = self.models[model_id]
        predictions = self.predictions.get(model_id, [])
        actuals = self.actuals.get(model_id, [])

        if not predictions or not actuals:
            return None

        # Match predictions with actuals
        actual_map = {a["prediction_id"]: a["actual_value"] for a in actuals}

        matched_data = []
        for pred in predictions:
            if pred["prediction_id"] in actual_map:
                matched_data.append({
                    "predicted": pred["value"],
                    "actual": actual_map[pred["prediction_id"]],
                    "conf_lower": pred["confidence_lower"],
                    "conf_upper": pred["confidence_upper"],
                })

        if not matched_data:
            return None

        # Calculate metrics
        predicted = [d["predicted"] for d in matched_data]
        actual = [d["actual"] for d in matched_data]

        # Accuracy (for binary classification, threshold at 0.5)
        binary_pred = [1 if p >= 0.5 else 0 for p in predicted]
        binary_actual = [1 if a >= 0.5 else 0 for a in actual]
        accuracy = sum(1 for p, a in zip(binary_pred, binary_actual) if p == a) / len(matched_data)

        # MAE and RMSE
        errors = [abs(p - a) for p, a in zip(predicted, actual)]
        mae = statistics.mean(errors)
        rmse = math.sqrt(statistics.mean([e ** 2 for e in errors]))

        # Calibration error
        calibration_errors = []
        for d in matched_data:
            in_interval = d["conf_lower"] <= d["actual"] <= d["conf_upper"]
            calibration_errors.append(0 if in_interval else 1)
        calibration_error = statistics.mean(calibration_errors)

        # Confidence interval coverage
        ci_coverage = 1 - calibration_error

        # Calculate drift score
        drift_score = self._calculate_drift(model_id)

        # Simplified precision/recall/F1 for binary case
        tp = sum(1 for p, a in zip(binary_pred, binary_actual) if p == 1 and a == 1)
        fp = sum(1 for p, a in zip(binary_pred, binary_actual) if p == 1 and a == 0)
        fn = sum(1 for p, a in zip(binary_pred, binary_actual) if p == 0 and a == 1)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # AUC-ROC approximation (simplified)
        auc_roc = (accuracy + precision + recall) / 3  # Rough approximation

        return ModelPerformanceMetrics(
            model_id=model_id,
            model_name=model_info["name"],
            prediction_accuracy=accuracy,
            auc_roc=auc_roc,
            precision=precision,
            recall=recall,
            f1_score=f1,
            calibration_error=calibration_error,
            confidence_interval=(ci_coverage - 0.05, ci_coverage + 0.05),
            drift_score=drift_score,
            last_retrain_date=model_info["training_date"],
            samples_since_retrain=model_info["predictions_count"],
        )

    def _calculate_drift(self, model_id: str) -> float:
        """Calculate model drift score"""

        predictions = self.predictions.get(model_id, [])

        if len(predictions) < 100:
            return 0.0  # Not enough data

        # Get baseline (first 50 predictions)
        if model_id not in self.drift_baselines:
            baseline_preds = [p["value"] for p in predictions[:50]]
            self.drift_baselines[model_id] = {
                "mean": statistics.mean(baseline_preds),
                "std": statistics.stdev(baseline_preds) if len(baseline_preds) > 1 else 0.1,
            }

        baseline = self.drift_baselines[model_id]

        # Compare recent predictions to baseline
        recent_preds = [p["value"] for p in predictions[-50:]]
        recent_mean = statistics.mean(recent_preds)
        recent_std = statistics.stdev(recent_preds) if len(recent_preds) > 1 else 0.1

        # KL divergence approximation
        mean_shift = abs(recent_mean - baseline["mean"]) / max(baseline["std"], 0.01)
        std_ratio = recent_std / max(baseline["std"], 0.01)

        drift_score = min(1.0, mean_shift * 0.5 + abs(1 - std_ratio) * 0.5)

        return drift_score

    def run_backtest(
        self,
        model_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[BacktestResult]:
        """Run backtesting for a model"""

        predictions = self.predictions.get(model_id, [])
        actuals = self.actuals.get(model_id, [])

        # Filter by date range
        filtered_preds = [
            p for p in predictions
            if start_date <= p["timestamp"] <= end_date
        ]

        actual_map = {a["prediction_id"]: a["actual_value"] for a in actuals}

        matched_data = []
        for pred in filtered_preds:
            if pred["prediction_id"] in actual_map:
                matched_data.append({
                    "predicted": pred["value"],
                    "actual": actual_map[pred["prediction_id"]],
                    "conf_lower": pred["confidence_lower"],
                    "conf_upper": pred["confidence_upper"],
                })

        if not matched_data:
            return None

        predicted = [d["predicted"] for d in matched_data]
        actual = [d["actual"] for d in matched_data]

        # Binary accuracy
        binary_pred = [1 if p >= 0.5 else 0 for p in predicted]
        binary_actual = [1 if a >= 0.5 else 0 for a in actual]
        correct = sum(1 for p, a in zip(binary_pred, binary_actual) if p == a)
        accuracy = correct / len(matched_data)

        # Error metrics
        errors = [abs(p - a) for p, a in zip(predicted, actual)]
        mae = statistics.mean(errors)
        rmse = math.sqrt(statistics.mean([e ** 2 for e in errors]))

        # Actual vs predicted ratio
        avg_predicted = statistics.mean(predicted)
        avg_actual = statistics.mean(actual)
        ratio = avg_actual / avg_predicted if avg_predicted > 0 else 1.0

        # CI coverage
        ci_hits = sum(
            1 for d in matched_data
            if d["conf_lower"] <= d["actual"] <= d["conf_upper"]
        )
        ci_coverage = ci_hits / len(matched_data)

        return BacktestResult(
            test_period_start=start_date,
            test_period_end=end_date,
            predictions_made=len(matched_data),
            correct_predictions=correct,
            accuracy=accuracy,
            mean_absolute_error=mae,
            root_mean_squared_error=rmse,
            actual_vs_predicted_ratio=ratio,
            confidence_intervals_coverage=ci_coverage,
        )

    def register_ab_test(
        self,
        test_id: str,
        test_name: str,
        variant_a_name: str,
        variant_b_name: str,
        minimum_detectable_effect: float = 0.05,
    ):
        """Register an A/B test"""

        self.ab_tests[test_id] = {
            "name": test_name,
            "variant_a_name": variant_a_name,
            "variant_b_name": variant_b_name,
            "mde": minimum_detectable_effect,
            "variant_a_data": [],
            "variant_b_data": [],
        }

    def record_ab_result(
        self,
        test_id: str,
        variant: str,  # "a" or "b"
        converted: bool,
    ):
        """Record an A/B test result"""

        if test_id not in self.ab_tests:
            return

        key = f"variant_{variant}_data"
        if key in self.ab_tests[test_id]:
            self.ab_tests[test_id][key].append(1 if converted else 0)

    def analyze_ab_test(self, test_id: str) -> Optional[ABTestResult]:
        """Analyze A/B test significance"""

        if test_id not in self.ab_tests:
            return None

        test = self.ab_tests[test_id]

        data_a = test["variant_a_data"]
        data_b = test["variant_b_data"]

        if len(data_a) < 30 or len(data_b) < 30:
            return None  # Not enough samples

        n_a = len(data_a)
        n_b = len(data_b)

        conv_a = statistics.mean(data_a)
        conv_b = statistics.mean(data_b)

        # Calculate standard error and z-score
        se_a = math.sqrt(conv_a * (1 - conv_a) / n_a) if conv_a > 0 else 0.01
        se_b = math.sqrt(conv_b * (1 - conv_b) / n_b) if conv_b > 0 else 0.01
        se_diff = math.sqrt(se_a ** 2 + se_b ** 2)

        diff = conv_b - conv_a
        z_score = diff / se_diff if se_diff > 0 else 0

        # P-value (two-tailed)
        # Using approximation for standard normal CDF
        p_value = 2 * (1 - self._normal_cdf(abs(z_score)))

        # Relative lift
        relative_lift = (conv_b - conv_a) / conv_a if conv_a > 0 else 0

        # Significance (95% confidence)
        is_significant = p_value < 0.05
        confidence_level = 1 - p_value

        # Determine winner
        recommended_winner = None
        if is_significant:
            if conv_b > conv_a:
                recommended_winner = test["variant_b_name"]
            else:
                recommended_winner = test["variant_a_name"]

        return ABTestResult(
            test_id=test_id,
            test_name=test["name"],
            variant_a_name=test["variant_a_name"],
            variant_b_name=test["variant_b_name"],
            variant_a_samples=n_a,
            variant_b_samples=n_b,
            variant_a_conversion=conv_a,
            variant_b_conversion=conv_b,
            relative_lift=relative_lift,
            p_value=p_value,
            confidence_level=confidence_level,
            is_significant=is_significant,
            recommended_winner=recommended_winner,
            minimum_detectable_effect=test["mde"],
        )

    def _normal_cdf(self, x: float) -> float:
        """Approximation of standard normal CDF"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# =============================================================================
# LIQUIDITY RISK MANAGER
# =============================================================================

class LiquidityRiskManager:
    """
    Liquidity risk management.

    Handles:
    - Cash flow timing mismatches
    - Settlement delay buffers
    - Reserve requirements calculation
    """

    def __init__(
        self,
        initial_cash: Decimal = Decimal("0"),
        reserve_ratio: float = 0.10,
    ):
        self.current_cash = initial_cash
        self.reserve_ratio = reserve_ratio
        self.expected_inflows: List[Dict] = []
        self.expected_outflows: List[Dict] = []
        self.settlement_obligations: List[Dict] = []

    def record_expected_inflow(
        self,
        amount: Decimal,
        expected_date: datetime,
        source: str,
        probability: float = 0.90,
    ):
        """Record an expected cash inflow"""

        self.expected_inflows.append({
            "amount": amount,
            "date": expected_date,
            "source": source,
            "probability": probability,
        })

    def record_expected_outflow(
        self,
        amount: Decimal,
        expected_date: datetime,
        destination: str,
        is_mandatory: bool = True,
    ):
        """Record an expected cash outflow"""

        self.expected_outflows.append({
            "amount": amount,
            "date": expected_date,
            "destination": destination,
            "is_mandatory": is_mandatory,
        })

    def add_settlement_obligation(
        self,
        creditor_id: str,
        amount: Decimal,
        due_date: datetime,
    ):
        """Add a settlement obligation"""

        self.settlement_obligations.append({
            "creditor_id": creditor_id,
            "amount": amount,
            "due_date": due_date,
        })

    def assess_liquidity_position(
        self,
        horizon_days: int = 30,
    ) -> LiquidityPosition:
        """Assess current liquidity position"""

        now = datetime.now()
        horizon_end = now + timedelta(days=horizon_days)

        # Calculate expected inflows
        inflows_in_period = sum(
            float(i["amount"]) * i["probability"]
            for i in self.expected_inflows
            if now <= i["date"] <= horizon_end
        )

        # Calculate expected outflows
        outflows_in_period = sum(
            float(o["amount"])
            for o in self.expected_outflows
            if now <= o["date"] <= horizon_end
        )

        # Settlement obligations
        settlement_total = sum(
            float(s["amount"])
            for s in self.settlement_obligations
            if now <= s["due_date"] <= horizon_end
        )

        # Net position
        net_position = Decimal(str(inflows_in_period - outflows_in_period))

        # Reserve requirements
        total_obligations = Decimal(str(outflows_in_period + settlement_total))
        reserve_requirement = total_obligations * Decimal(str(self.reserve_ratio))

        # Current reserve
        current_reserve = self.current_cash * Decimal(str(self.reserve_ratio))

        # Ratios
        reserve_coverage = float(current_reserve / reserve_requirement) if reserve_requirement > 0 else 1.0

        available_after_reserves = self.current_cash - reserve_requirement
        liquidity_ratio = float(available_after_reserves / total_obligations) if total_obligations > 0 else 1.0

        # Days cash on hand
        daily_outflow = outflows_in_period / horizon_days if horizon_days > 0 else 1
        days_cash = int(float(self.current_cash) / daily_outflow) if daily_outflow > 0 else 999

        # Risk level
        if liquidity_ratio < 0.5 or reserve_coverage < 0.8:
            risk_level = RiskLevel.CRITICAL
        elif liquidity_ratio < 0.75 or reserve_coverage < 1.0:
            risk_level = RiskLevel.HIGH
        elif liquidity_ratio < 1.0 or reserve_coverage < 1.2:
            risk_level = RiskLevel.MODERATE
        elif liquidity_ratio < 1.5:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL

        return LiquidityPosition(
            assessment_date=now,
            available_cash=self.current_cash,
            expected_inflows_30d=Decimal(str(inflows_in_period)),
            expected_outflows_30d=Decimal(str(outflows_in_period)),
            net_position_30d=net_position,
            settlement_obligations=Decimal(str(settlement_total)),
            reserve_requirement=reserve_requirement,
            current_reserve=current_reserve,
            reserve_coverage_ratio=reserve_coverage,
            liquidity_ratio=liquidity_ratio,
            days_cash_on_hand=days_cash,
            risk_level=risk_level,
        )

    def calculate_settlement_buffer(
        self,
        expected_settlement: Decimal,
        delay_probability: float = 0.10,
        max_delay_days: int = 14,
    ) -> Decimal:
        """Calculate required buffer for settlement delays"""

        # Buffer = expected settlement * delay probability * max delay impact
        buffer = expected_settlement * Decimal(str(delay_probability)) * Decimal("1.5")

        return buffer.quantize(Decimal("0.01"))

    def project_cash_flow(
        self,
        days_forward: int = 90,
    ) -> List[Dict[str, Any]]:
        """Project cash flows forward"""

        projections = []
        now = datetime.now()
        running_balance = self.current_cash

        for day in range(days_forward):
            date = now + timedelta(days=day)

            # Inflows for this day
            day_inflows = sum(
                float(i["amount"]) * i["probability"]
                for i in self.expected_inflows
                if i["date"].date() == date.date()
            )

            # Outflows for this day
            day_outflows = sum(
                float(o["amount"])
                for o in self.expected_outflows
                if o["date"].date() == date.date()
            )

            # Settlements due
            day_settlements = sum(
                float(s["amount"])
                for s in self.settlement_obligations
                if s["due_date"].date() == date.date()
            )

            running_balance += Decimal(str(day_inflows - day_outflows - day_settlements))

            projections.append({
                "date": date,
                "inflows": day_inflows,
                "outflows": day_outflows + day_settlements,
                "net": day_inflows - day_outflows - day_settlements,
                "ending_balance": running_balance,
            })

        return projections

    def update_cash_position(self, new_balance: Decimal):
        """Update current cash position"""
        self.current_cash = new_balance


# =============================================================================
# RISK LIMITS CONTROLLER
# =============================================================================

class RiskLimitsController:
    """
    Risk limits and controls management.

    Handles:
    - Position limits by category
    - Automatic de-risking triggers
    - Risk-adjusted return optimization
    """

    def __init__(self):
        self.limits: Dict[str, RiskLimit] = {}
        self.breach_history: List[Dict] = []
        self.de_risking_actions: List[DeRiskingAction] = []
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def set_limit(
        self,
        limit_id: str,
        limit_name: str,
        category: RiskCategory,
        metric_name: str,
        soft_limit: float,
        hard_limit: float,
        auto_action: Optional[str] = None,
    ):
        """Set a risk limit"""

        self.limits[limit_id] = RiskLimit(
            limit_id=limit_id,
            limit_name=limit_name,
            category=category,
            metric_name=metric_name,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            current_value=0.0,
            utilization=0.0,
            breach_status="normal",
            last_updated=datetime.now(),
            auto_action=auto_action,
        )

    def update_limit_value(
        self,
        limit_id: str,
        current_value: float,
    ) -> Optional[RiskLimit]:
        """Update current value for a limit and check for breaches"""

        if limit_id not in self.limits:
            return None

        limit = self.limits[limit_id]
        limit.current_value = current_value
        limit.utilization = current_value / limit.hard_limit if limit.hard_limit > 0 else 0
        limit.last_updated = datetime.now()

        # Check breach status
        old_status = limit.breach_status

        if current_value >= limit.hard_limit:
            limit.breach_status = "breach"
        elif current_value >= limit.soft_limit:
            limit.breach_status = "warning"
        else:
            limit.breach_status = "normal"

        # Record breach if status changed
        if limit.breach_status != old_status and limit.breach_status != "normal":
            self.breach_history.append({
                "limit_id": limit_id,
                "breach_type": limit.breach_status,
                "value": current_value,
                "limit": limit.hard_limit if limit.breach_status == "breach" else limit.soft_limit,
                "timestamp": datetime.now(),
            })

            # Trigger callbacks
            for callback in self.callbacks.get(limit.breach_status, []):
                callback(limit)

            # Execute auto action if configured
            if limit.breach_status == "breach" and limit.auto_action:
                self._execute_auto_action(limit)

        return limit

    def _execute_auto_action(self, limit: RiskLimit):
        """Execute automatic de-risking action"""

        action = DeRiskingAction(
            action_id=str(uuid.uuid4()),
            trigger_condition=f"{limit.limit_name} breach: {limit.current_value:.2f} > {limit.hard_limit:.2f}",
            action_type=limit.auto_action,
            severity=RiskLevel.HIGH if limit.current_value > limit.hard_limit * 1.1 else RiskLevel.MODERATE,
            positions_affected=[],
            estimated_impact=Decimal("0"),
            execution_status="pending",
            triggered_at=datetime.now(),
        )

        self.de_risking_actions.append(action)
        logger.warning(f"De-risking action triggered: {action.action_type} for {limit.limit_name}")

    def register_callback(
        self,
        breach_type: str,
        callback: Callable[[RiskLimit], None],
    ):
        """Register a callback for limit breaches"""
        self.callbacks[breach_type].append(callback)

    def get_all_limits(self) -> List[RiskLimit]:
        """Get all configured limits"""
        return list(self.limits.values())

    def get_active_breaches(self) -> List[RiskLimit]:
        """Get all limits currently in breach"""
        return [l for l in self.limits.values() if l.breach_status in ["warning", "breach"]]

    def calculate_risk_adjusted_return(
        self,
        expected_return: Decimal,
        risk_score: float,
        capital_at_risk: Decimal,
    ) -> Dict[str, float]:
        """Calculate risk-adjusted return metrics"""

        # Sharpe-like ratio (simplified)
        risk_free_rate = 0.02  # 2% risk-free rate
        excess_return = float(expected_return / capital_at_risk) - risk_free_rate if capital_at_risk > 0 else 0
        sharpe_ratio = excess_return / risk_score if risk_score > 0 else 0

        # Return on Risk-Adjusted Capital (RORAC)
        risk_adjusted_capital = capital_at_risk * Decimal(str(max(1.0, risk_score * 2)))
        rorac = float(expected_return / risk_adjusted_capital) if risk_adjusted_capital > 0 else 0

        # Risk-Adjusted Return on Capital (RAROC)
        expected_loss = capital_at_risk * Decimal(str(risk_score * 0.5))
        raroc = float((expected_return - expected_loss) / capital_at_risk) if capital_at_risk > 0 else 0

        return {
            "sharpe_ratio": sharpe_ratio,
            "rorac": rorac,
            "raroc": raroc,
            "excess_return": excess_return,
            "risk_premium": risk_score * 0.1,  # Risk premium
        }

    def get_pending_actions(self) -> List[DeRiskingAction]:
        """Get pending de-risking actions"""
        return [a for a in self.de_risking_actions if a.execution_status == "pending"]

    def mark_action_executed(self, action_id: str):
        """Mark a de-risking action as executed"""
        for action in self.de_risking_actions:
            if action.action_id == action_id:
                action.execution_status = "executed"
                action.executed_at = datetime.now()
                break


# =============================================================================
# STRESS TEST ENGINE
# =============================================================================

class StressTestEngine:
    """
    Stress testing engine for scenario analysis.
    """

    # Scenario parameters
    SCENARIO_PARAMS = {
        StressScenario.RECESSION: {
            "recovery_rate_shock": -0.20,  # 20% decrease
            "default_rate_shock": 0.15,     # 15% increase
            "collection_cost_shock": 0.10,  # 10% increase
            "duration_months": 18,
        },
        StressScenario.UNEMPLOYMENT_SPIKE: {
            "recovery_rate_shock": -0.25,
            "default_rate_shock": 0.20,
            "collection_cost_shock": 0.05,
            "duration_months": 12,
        },
        StressScenario.INTEREST_RATE_SHOCK: {
            "recovery_rate_shock": -0.10,
            "default_rate_shock": 0.08,
            "collection_cost_shock": 0.03,
            "duration_months": 6,
        },
        StressScenario.REGULATORY_CHANGE: {
            "recovery_rate_shock": -0.15,
            "default_rate_shock": 0.05,
            "collection_cost_shock": 0.25,  # Compliance costs
            "duration_months": 24,
        },
        StressScenario.PANDEMIC: {
            "recovery_rate_shock": -0.30,
            "default_rate_shock": 0.25,
            "collection_cost_shock": 0.15,
            "duration_months": 24,
        },
        StressScenario.REGIONAL_CRISIS: {
            "recovery_rate_shock": -0.15,
            "default_rate_shock": 0.12,
            "collection_cost_shock": 0.08,
            "duration_months": 12,
        },
        StressScenario.CREDITOR_DEFAULT: {
            "recovery_rate_shock": -0.05,
            "default_rate_shock": 0.02,
            "collection_cost_shock": 0.20,  # Restructuring costs
            "duration_months": 6,
        },
        StressScenario.SYSTEM_OUTAGE: {
            "recovery_rate_shock": -0.02,
            "default_rate_shock": 0.01,
            "collection_cost_shock": 0.50,  # Emergency costs
            "duration_months": 1,
        },
    }

    def __init__(self, portfolio_manager: PortfolioRiskManager):
        self.portfolio_manager = portfolio_manager

    def run_stress_test(
        self,
        scenario: StressScenario,
        custom_params: Optional[Dict[str, float]] = None,
    ) -> StressTestResult:
        """Run a stress test scenario"""

        params = self.SCENARIO_PARAMS.get(scenario, {}).copy()
        if custom_params:
            params.update(custom_params)

        # Get base portfolio metrics
        base_value = self.portfolio_manager.get_portfolio_value()
        total_exposure = self.portfolio_manager.get_total_exposure()

        # Apply shocks
        recovery_shock = params.get("recovery_rate_shock", 0)

        # Calculate stressed portfolio value
        stressed_recovery_rates = []
        accounts_at_risk = 0

        for pos in self.portfolio_manager.positions.values():
            stressed_rate = max(0, pos.recovery_probability * (1 + recovery_shock))
            stressed_recovery_rates.append(stressed_rate)

            if stressed_rate < pos.recovery_probability * 0.7:
                accounts_at_risk += 1

        avg_stressed_rate = statistics.mean(stressed_recovery_rates) if stressed_recovery_rates else 0.30
        stressed_value = total_exposure * Decimal(str(avg_stressed_rate))

        # Loss calculation
        loss_amount = base_value - stressed_value
        loss_percentage = float(loss_amount / base_value) if base_value > 0 else 0

        # Capital adequacy post-stress
        # Assume 15% capital buffer requirement
        capital_buffer = float(base_value) * 0.15
        remaining_buffer = capital_buffer - float(loss_amount)
        capital_adequacy = remaining_buffer / capital_buffer if capital_buffer > 0 else 0

        # Recovery rate impact
        base_recovery = statistics.mean(
            p.recovery_probability for p in self.portfolio_manager.positions.values()
        ) if self.portfolio_manager.positions else 0.30
        recovery_impact = avg_stressed_rate - base_recovery

        # Generate recommendations
        actions = self._generate_stress_recommendations(
            scenario, loss_percentage, capital_adequacy, accounts_at_risk
        )

        return StressTestResult(
            scenario=scenario,
            scenario_name=scenario.value.replace("_", " ").title(),
            base_portfolio_value=base_value,
            stressed_portfolio_value=stressed_value,
            loss_amount=loss_amount,
            loss_percentage=loss_percentage,
            recovery_rate_impact=recovery_impact,
            accounts_at_risk=accounts_at_risk,
            capital_adequacy_post_stress=capital_adequacy,
            actions_recommended=actions,
        )

    def _generate_stress_recommendations(
        self,
        scenario: StressScenario,
        loss_pct: float,
        capital_adequacy: float,
        accounts_at_risk: int,
    ) -> List[str]:
        """Generate recommendations based on stress test results"""

        recommendations = []

        if loss_pct > 0.20:
            recommendations.append("CRITICAL: Potential loss exceeds 20%. Implement immediate de-risking.")

        if capital_adequacy < 0.5:
            recommendations.append("WARNING: Post-stress capital adequacy below 50%. Increase capital buffers.")

        if accounts_at_risk > 100:
            recommendations.append(f"Review {accounts_at_risk} accounts with elevated risk exposure.")

        # Scenario-specific recommendations
        if scenario == StressScenario.RECESSION:
            recommendations.append("Focus on accounts with stable income sources.")
            recommendations.append("Increase settlement offers to accelerate collections.")
        elif scenario == StressScenario.UNEMPLOYMENT_SPIKE:
            recommendations.append("Implement hardship programs proactively.")
            recommendations.append("Reduce aggressive collection tactics.")
        elif scenario == StressScenario.REGULATORY_CHANGE:
            recommendations.append("Conduct compliance audit immediately.")
            recommendations.append("Review all communication templates.")
        elif scenario == StressScenario.PANDEMIC:
            recommendations.append("Shift to digital-first communication.")
            recommendations.append("Extend payment plan options.")

        return recommendations

    def run_all_scenarios(self) -> Dict[StressScenario, StressTestResult]:
        """Run all predefined stress scenarios"""

        results = {}
        for scenario in StressScenario:
            results[scenario] = self.run_stress_test(scenario)

        return results


# =============================================================================
# RISK DASHBOARD
# =============================================================================

class RiskDashboard:
    """
    Real-time risk dashboard metrics aggregator.
    """

    def __init__(
        self,
        portfolio_manager: PortfolioRiskManager,
        operational_manager: OperationalRiskManager,
        counterparty_manager: CounterpartyRiskManager,
        model_manager: ModelRiskManager,
        liquidity_manager: LiquidityRiskManager,
        limits_controller: RiskLimitsController,
    ):
        self.portfolio = portfolio_manager
        self.operational = operational_manager
        self.counterparty = counterparty_manager
        self.model = model_manager
        self.liquidity = liquidity_manager
        self.limits = limits_controller

        self.metrics_history: List[RiskDashboardMetrics] = []

    def get_current_metrics(self) -> RiskDashboardMetrics:
        """Get current aggregated risk metrics"""

        now = datetime.now()

        # Portfolio metrics
        var_result = self.portfolio.calculate_portfolio_var(
            confidence_level=0.95,
            time_horizon_days=1,
            method=VaRMethod.PARAMETRIC,
        )

        total_exposure = self.portfolio.get_total_exposure()

        # Concentration
        concentration = self.portfolio.analyze_concentration_risk("creditor")
        concentration_score = concentration.herfindahl_index * 10  # Scale to 0-1

        # Compliance risk (average across sampled accounts)
        compliance_scores = []
        sample_accounts = list(self.portfolio.positions.keys())[:100]
        for account_id in sample_accounts:
            pos = self.portfolio.positions.get(account_id)
            if pos:
                risk = self.operational.assess_compliance_risk(
                    account_id,
                    {"state": pos.state, "balance": float(pos.current_balance)}
                )
                compliance_scores.append(risk.overall_risk_score)

        compliance_risk_score = statistics.mean(compliance_scores) if compliance_scores else 0.1

        # Operational risk (based on contact limit utilization)
        operational_risk_score = min(1.0, len(self.operational.contact_history) / 10000)

        # Counterparty risk
        counterparty_risks = []
        for cp_id in self.counterparty.counterparties:
            assessment = self.counterparty.assess_counterparty_risk(cp_id, Decimal("100000"))
            counterparty_risks.append(assessment.default_probability)

        counterparty_risk_score = statistics.mean(counterparty_risks) if counterparty_risks else 0.05

        # Model risk (drift-based)
        model_drifts = []
        for model_id in self.model.models:
            metrics = self.model.calculate_model_metrics(model_id)
            if metrics:
                model_drifts.append(metrics.drift_score)

        model_risk_score = statistics.mean(model_drifts) if model_drifts else 0.0

        # Liquidity
        liquidity_position = self.liquidity.assess_liquidity_position()

        # Active breaches
        active_breaches = len(self.limits.get_active_breaches())
        pending_actions = len(self.limits.get_pending_actions())

        # Overall risk score (weighted average)
        overall_risk = (
            concentration_score * 0.15 +
            compliance_risk_score * 0.25 +
            operational_risk_score * 0.15 +
            counterparty_risk_score * 0.15 +
            model_risk_score * 0.10 +
            (1 - liquidity_position.liquidity_ratio) * 0.20
        )

        # Risk level
        if overall_risk > 0.7 or active_breaches > 3:
            risk_level = RiskLevel.CRITICAL
        elif overall_risk > 0.5 or active_breaches > 1:
            risk_level = RiskLevel.HIGH
        elif overall_risk > 0.3:
            risk_level = RiskLevel.MODERATE
        elif overall_risk > 0.15:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL

        metrics = RiskDashboardMetrics(
            timestamp=now,
            portfolio_var_1d=var_result.var_amount,
            portfolio_cvar_1d=var_result.expected_shortfall,
            total_exposure=total_exposure,
            concentration_score=concentration_score,
            compliance_risk_score=compliance_risk_score,
            operational_risk_score=operational_risk_score,
            counterparty_risk_score=counterparty_risk_score,
            model_risk_score=model_risk_score,
            liquidity_ratio=liquidity_position.liquidity_ratio,
            overall_risk_score=overall_risk,
            overall_risk_level=risk_level,
            active_breaches=active_breaches,
            pending_actions=pending_actions,
        )

        self.metrics_history.append(metrics)

        return metrics

    def get_metrics_history(
        self,
        hours_back: int = 24,
    ) -> List[RiskDashboardMetrics]:
        """Get historical metrics"""

        cutoff = datetime.now() - timedelta(hours=hours_back)
        return [m for m in self.metrics_history if m.timestamp >= cutoff]

    def generate_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report"""

        current = self.get_current_metrics()

        # Portfolio analysis
        var_historical = self.portfolio.calculate_portfolio_var(
            method=VaRMethod.HISTORICAL
        )
        var_parametric = self.portfolio.calculate_portfolio_var(
            method=VaRMethod.PARAMETRIC
        )
        var_monte_carlo = self.portfolio.calculate_portfolio_var(
            method=VaRMethod.MONTE_CARLO
        )

        # Concentration by multiple dimensions
        conc_creditor = self.portfolio.analyze_concentration_risk("creditor")
        conc_state = self.portfolio.analyze_concentration_risk("state")
        conc_debt_type = self.portfolio.analyze_concentration_risk("debt_type")

        # Liquidity
        liquidity = self.liquidity.assess_liquidity_position()
        cash_projection = self.liquidity.project_cash_flow(30)

        # Limits status
        all_limits = self.limits.get_all_limits()

        return {
            "report_date": datetime.now().isoformat(),
            "summary": {
                "overall_risk_level": current.overall_risk_level.value,
                "overall_risk_score": current.overall_risk_score,
                "total_exposure": float(current.total_exposure),
                "active_breaches": current.active_breaches,
            },
            "portfolio_risk": {
                "var_1d_95_historical": float(var_historical.var_amount),
                "var_1d_95_parametric": float(var_parametric.var_amount),
                "var_1d_95_monte_carlo": float(var_monte_carlo.var_amount),
                "cvar_1d_95": float(var_parametric.expected_shortfall),
            },
            "concentration_risk": {
                "by_creditor": {
                    "hhi": conc_creditor.herfindahl_index,
                    "risk_level": conc_creditor.risk_level.value,
                    "top_3_exposure_pct": sum(e[2] for e in conc_creditor.top_exposures[:3]),
                },
                "by_state": {
                    "hhi": conc_state.herfindahl_index,
                    "risk_level": conc_state.risk_level.value,
                },
                "by_debt_type": {
                    "hhi": conc_debt_type.herfindahl_index,
                    "risk_level": conc_debt_type.risk_level.value,
                },
            },
            "liquidity_risk": {
                "current_cash": float(liquidity.available_cash),
                "liquidity_ratio": liquidity.liquidity_ratio,
                "days_cash_on_hand": liquidity.days_cash_on_hand,
                "risk_level": liquidity.risk_level.value,
            },
            "operational_risk": {
                "compliance_score": current.compliance_risk_score,
                "operational_score": current.operational_risk_score,
            },
            "counterparty_risk": {
                "score": current.counterparty_risk_score,
            },
            "model_risk": {
                "drift_score": current.model_risk_score,
            },
            "limits_status": [
                {
                    "name": l.limit_name,
                    "utilization": l.utilization,
                    "status": l.breach_status,
                }
                for l in all_limits
            ],
        }


# =============================================================================
# MAIN RISK ENGINE
# =============================================================================

class RiskEngine:
    """
    Main risk management engine orchestrating all risk components.

    This is the primary interface for risk management operations.
    """

    def __init__(self):
        # Initialize all managers
        self.portfolio = PortfolioRiskManager()
        self.operational = OperationalRiskManager()
        self.counterparty = CounterpartyRiskManager()
        self.model = ModelRiskManager()
        self.liquidity = LiquidityRiskManager()
        self.limits = RiskLimitsController()

        # Stress testing
        self.stress_test = StressTestEngine(self.portfolio)

        # Dashboard
        self.dashboard = RiskDashboard(
            self.portfolio,
            self.operational,
            self.counterparty,
            self.model,
            self.liquidity,
            self.limits,
        )

        # Initialize default limits
        self._setup_default_limits()

    def _setup_default_limits(self):
        """Set up default risk limits"""

        # Portfolio limits
        self.limits.set_limit(
            "portfolio_var_1d",
            "Portfolio 1-Day VaR",
            RiskCategory.PORTFOLIO,
            "var_1d_95",
            soft_limit=0.05,  # 5% soft limit
            hard_limit=0.10,  # 10% hard limit
            auto_action="reduce_exposure",
        )

        self.limits.set_limit(
            "concentration_hhi",
            "Concentration HHI",
            RiskCategory.PORTFOLIO,
            "herfindahl_index",
            soft_limit=0.15,
            hard_limit=0.25,
            auto_action="diversify_portfolio",
        )

        # Operational limits
        self.limits.set_limit(
            "compliance_risk",
            "Compliance Risk Score",
            RiskCategory.COMPLIANCE,
            "compliance_score",
            soft_limit=0.30,
            hard_limit=0.50,
            auto_action="compliance_review",
        )

        # Liquidity limits
        self.limits.set_limit(
            "liquidity_ratio",
            "Liquidity Ratio",
            RiskCategory.LIQUIDITY,
            "liquidity_ratio",
            soft_limit=1.0,  # Below 1.0 is warning
            hard_limit=0.75,  # Below 0.75 is breach
        )

        # Model limits
        self.limits.set_limit(
            "model_drift",
            "Model Drift Score",
            RiskCategory.MODEL,
            "drift_score",
            soft_limit=0.15,
            hard_limit=0.30,
            auto_action="retrain_model",
        )

    async def assess_account_risk(
        self,
        account_id: str,
        account_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Comprehensive risk assessment for a single account.

        Returns combined risk metrics from all dimensions.
        """

        # Compliance risk
        compliance_risk = self.operational.assess_compliance_risk(account_id, account_data)

        # Check contact limits
        can_call, call_reason = self.operational.check_contact_limits(account_id, "call")
        can_sms, sms_reason = self.operational.check_contact_limits(account_id, "sms")

        # State regulatory flags
        state = account_data.get("state", "NY")
        state_flags = self.operational.get_state_regulatory_flags(state)

        return {
            "account_id": account_id,
            "compliance": {
                "overall_score": compliance_risk.overall_risk_score,
                "tcpa_risk": compliance_risk.tcpa_risk,
                "fdcpa_risk": compliance_risk.fdcpa_risk,
                "state_risk": compliance_risk.state_specific_risk,
                "litigation_probability": compliance_risk.litigation_probability,
                "risk_factors": compliance_risk.risk_factors,
                "recommendations": compliance_risk.recommended_actions,
            },
            "contact_permissions": {
                "can_call": can_call,
                "call_reason": call_reason,
                "can_sms": can_sms,
                "sms_reason": sms_reason,
            },
            "state_requirements": state_flags,
        }

    async def assess_portfolio_risk(self) -> Dict[str, Any]:
        """
        Comprehensive portfolio risk assessment.
        """

        # VaR calculations
        var_95_1d = self.portfolio.calculate_portfolio_var(
            confidence_level=0.95,
            time_horizon_days=1,
        )

        var_99_10d = self.portfolio.calculate_portfolio_var(
            confidence_level=0.99,
            time_horizon_days=10,
        )

        # Concentration analysis
        conc_creditor = self.portfolio.analyze_concentration_risk("creditor")
        conc_state = self.portfolio.analyze_concentration_risk("state")
        conc_debt = self.portfolio.analyze_concentration_risk("debt_type")

        # Vintage analysis
        vintages = self.portfolio.get_all_vintages()

        return {
            "summary": {
                "total_exposure": float(self.portfolio.get_total_exposure()),
                "expected_value": float(self.portfolio.get_portfolio_value()),
                "positions_count": len(self.portfolio.positions),
            },
            "var_metrics": {
                "var_95_1d": {
                    "amount": float(var_95_1d.var_amount),
                    "percentage": var_95_1d.var_percentage,
                },
                "cvar_95_1d": {
                    "amount": float(var_95_1d.expected_shortfall),
                    "percentage": var_95_1d.expected_shortfall_percentage,
                },
                "var_99_10d": {
                    "amount": float(var_99_10d.var_amount),
                    "percentage": var_99_10d.var_percentage,
                },
            },
            "concentration": {
                "by_creditor": {
                    "hhi": conc_creditor.herfindahl_index,
                    "top_5_ratio": conc_creditor.concentration_ratio,
                    "risk_level": conc_creditor.risk_level.value,
                },
                "by_state": {
                    "hhi": conc_state.herfindahl_index,
                    "risk_level": conc_state.risk_level.value,
                },
                "by_debt_type": {
                    "hhi": conc_debt.herfindahl_index,
                    "risk_level": conc_debt.risk_level.value,
                },
            },
            "vintages": {
                period: {
                    "accounts": v.accounts_count,
                    "balance": float(v.total_balance),
                    "recovery_rate": v.recovery_rate,
                    "benchmark_comparison": v.benchmark_comparison,
                }
                for period, v in vintages.items()
            },
        }

    async def run_stress_tests(
        self,
        scenarios: Optional[List[StressScenario]] = None,
    ) -> Dict[str, StressTestResult]:
        """
        Run stress tests for specified scenarios.
        """

        if scenarios is None:
            return self.stress_test.run_all_scenarios()

        results = {}
        for scenario in scenarios:
            results[scenario.value] = self.stress_test.run_stress_test(scenario)

        return results

    def get_risk_dashboard(self) -> RiskDashboardMetrics:
        """Get current risk dashboard metrics"""
        return self.dashboard.get_current_metrics()

    def generate_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report"""
        return self.dashboard.generate_risk_report()

    def update_limits(self) -> List[RiskLimit]:
        """Update all risk limits with current values"""

        # Update portfolio VaR limit
        var = self.portfolio.calculate_portfolio_var()
        self.limits.update_limit_value(
            "portfolio_var_1d",
            var.var_percentage,
        )

        # Update concentration limit
        conc = self.portfolio.analyze_concentration_risk("creditor")
        self.limits.update_limit_value(
            "concentration_hhi",
            conc.herfindahl_index,
        )

        # Update liquidity limit
        liq = self.liquidity.assess_liquidity_position()
        # Invert because lower ratio is worse
        self.limits.update_limit_value(
            "liquidity_ratio",
            1 - liq.liquidity_ratio,  # Invert so higher = worse
        )

        return self.limits.get_all_limits()


# =============================================================================
# DEMONSTRATION AND TESTING
# =============================================================================

async def demo():
    """Demonstrate risk engine capabilities"""

    print("=" * 80)
    print("  QUAN RECOVERY - RISK MANAGEMENT ENGINE DEMONSTRATION")
    print("=" * 80)

    # Initialize risk engine
    engine = RiskEngine()

    # Add sample positions
    print("\n[1] Adding sample portfolio positions...")

    creditors = ["CRED-001", "CRED-002", "CRED-003", "CRED-004", "CRED-005"]
    states = ["CA", "NY", "TX", "FL", "IL", "OH", "PA", "GA"]
    debt_types = list(DebtType)

    for i in range(500):
        pos = Position(
            position_id=f"POS-{i:04d}",
            account_id=f"ACC-{i:04d}",
            creditor_id=random.choice(creditors),
            debt_type=random.choice(debt_types),
            original_balance=Decimal(str(random.uniform(100, 5000))),
            current_balance=Decimal(str(random.uniform(50, 4000))),
            purchase_price=Decimal(str(random.uniform(10, 500))),
            state=random.choice(states),
            vintage_date=datetime.now() - timedelta(days=random.randint(30, 720)),
            recovery_probability=random.uniform(0.15, 0.45),
            litigation_flag=random.random() < 0.05,
            bankruptcy_flag=random.random() < 0.02,
            disputed_flag=random.random() < 0.08,
        )
        pos.expected_recovery = pos.current_balance * Decimal(str(pos.recovery_probability))
        engine.portfolio.add_position(pos)

    print(f"   Added {len(engine.portfolio.positions)} positions")

    # Portfolio Risk Assessment
    print("\n[2] Portfolio Risk Assessment")
    print("-" * 40)

    portfolio_risk = await engine.assess_portfolio_risk()

    print(f"   Total Exposure: ${portfolio_risk['summary']['total_exposure']:,.2f}")
    print(f"   Expected Value: ${portfolio_risk['summary']['expected_value']:,.2f}")
    print(f"   Positions: {portfolio_risk['summary']['positions_count']}")

    print(f"\n   VaR (95%, 1-day): ${portfolio_risk['var_metrics']['var_95_1d']['amount']:,.2f} "
          f"({portfolio_risk['var_metrics']['var_95_1d']['percentage']:.2%})")
    print(f"   CVaR (95%, 1-day): ${portfolio_risk['var_metrics']['cvar_95_1d']['amount']:,.2f}")
    print(f"   VaR (99%, 10-day): ${portfolio_risk['var_metrics']['var_99_10d']['amount']:,.2f}")

    print(f"\n   Concentration by Creditor:")
    print(f"     HHI: {portfolio_risk['concentration']['by_creditor']['hhi']:.4f}")
    print(f"     Risk Level: {portfolio_risk['concentration']['by_creditor']['risk_level']}")

    # VaR Methods Comparison
    print("\n[3] VaR Calculation Methods Comparison")
    print("-" * 40)

    portfolio_value = engine.portfolio.get_portfolio_value()

    for method in VaRMethod:
        var_result = engine.portfolio.calculate_portfolio_var(
            confidence_level=0.95,
            time_horizon_days=1,
            method=method,
        )
        print(f"   {method.value.replace('_', ' ').title():15} VaR: ${var_result.var_amount:>12,.2f} "
              f"({var_result.var_percentage:.2%})")

    # Stress Testing
    print("\n[4] Stress Test Results")
    print("-" * 40)

    stress_results = await engine.run_stress_tests([
        StressScenario.RECESSION,
        StressScenario.UNEMPLOYMENT_SPIKE,
        StressScenario.PANDEMIC,
    ])

    for scenario_name, result in stress_results.items():
        print(f"\n   Scenario: {result.scenario_name}")
        print(f"     Base Value:    ${result.base_portfolio_value:>12,.2f}")
        print(f"     Stressed Value:${result.stressed_portfolio_value:>12,.2f}")
        print(f"     Loss:          ${result.loss_amount:>12,.2f} ({result.loss_percentage:.1%})")
        print(f"     Capital Adequacy: {result.capital_adequacy_post_stress:.1%}")
        print(f"     Accounts at Risk: {result.accounts_at_risk}")

    # Account-Level Risk
    print("\n[5] Sample Account Risk Assessment")
    print("-" * 40)

    sample_account_data = {
        "state": "CA",
        "balance": 1500.0,
        "sms_consent": False,
        "cease_requested": False,
        "in_validation_period": False,
        "disputed": True,
        "has_attorney": False,
        "prior_litigation": False,
    }

    account_risk = await engine.assess_account_risk("ACC-0001", sample_account_data)

    print(f"   Account: ACC-0001")
    print(f"   Overall Compliance Risk: {account_risk['compliance']['overall_score']:.2%}")
    print(f"   TCPA Risk: {account_risk['compliance']['tcpa_risk']:.2%}")
    print(f"   FDCPA Risk: {account_risk['compliance']['fdcpa_risk']:.2%}")
    print(f"   Litigation Probability: {account_risk['compliance']['litigation_probability']:.2%}")
    print(f"   Can Call: {account_risk['contact_permissions']['can_call']}")
    print(f"   Can SMS: {account_risk['contact_permissions']['can_sms']}")

    if account_risk['compliance']['recommendations']:
        print(f"   Recommendations:")
        for rec in account_risk['compliance']['recommendations'][:3]:
            print(f"     - {rec}")

    # Liquidity Assessment
    print("\n[6] Liquidity Risk Assessment")
    print("-" * 40)

    # Add some cash and obligations
    engine.liquidity.update_cash_position(Decimal("500000"))

    for i in range(20):
        engine.liquidity.record_expected_inflow(
            amount=Decimal(str(random.uniform(10000, 50000))),
            expected_date=datetime.now() + timedelta(days=random.randint(1, 30)),
            source=f"Collections-{i}",
            probability=0.85,
        )
        engine.liquidity.record_expected_outflow(
            amount=Decimal(str(random.uniform(5000, 20000))),
            expected_date=datetime.now() + timedelta(days=random.randint(1, 30)),
            destination=f"Operations-{i}",
        )

    liquidity = engine.liquidity.assess_liquidity_position()

    print(f"   Available Cash: ${liquidity.available_cash:,.2f}")
    print(f"   Expected Inflows (30d): ${liquidity.expected_inflows_30d:,.2f}")
    print(f"   Expected Outflows (30d): ${liquidity.expected_outflows_30d:,.2f}")
    print(f"   Net Position: ${liquidity.net_position_30d:,.2f}")
    print(f"   Liquidity Ratio: {liquidity.liquidity_ratio:.2f}")
    print(f"   Days Cash on Hand: {liquidity.days_cash_on_hand}")
    print(f"   Risk Level: {liquidity.risk_level.value}")

    # Risk Dashboard
    print("\n[7] Risk Dashboard Summary")
    print("-" * 40)

    dashboard = engine.get_risk_dashboard()

    print(f"   Overall Risk Score: {dashboard.overall_risk_score:.2%}")
    print(f"   Overall Risk Level: {dashboard.overall_risk_level.value.upper()}")
    print(f"   Portfolio VaR (1d): ${dashboard.portfolio_var_1d:,.2f}")
    print(f"   Portfolio CVaR (1d): ${dashboard.portfolio_cvar_1d:,.2f}")
    print(f"   Concentration Score: {dashboard.concentration_score:.4f}")
    print(f"   Compliance Risk: {dashboard.compliance_risk_score:.2%}")
    print(f"   Operational Risk: {dashboard.operational_risk_score:.2%}")
    print(f"   Counterparty Risk: {dashboard.counterparty_risk_score:.2%}")
    print(f"   Model Risk: {dashboard.model_risk_score:.2%}")
    print(f"   Liquidity Ratio: {dashboard.liquidity_ratio:.2f}")
    print(f"   Active Breaches: {dashboard.active_breaches}")
    print(f"   Pending Actions: {dashboard.pending_actions}")

    # Risk Limits
    print("\n[8] Risk Limits Status")
    print("-" * 40)

    engine.update_limits()
    limits = engine.limits.get_all_limits()

    print(f"   {'Limit Name':<25} {'Current':>10} {'Soft':>10} {'Hard':>10} {'Status':>12}")
    print(f"   {'-'*67}")

    for limit in limits:
        print(f"   {limit.limit_name:<25} {limit.current_value:>10.2%} "
              f"{limit.soft_limit:>10.2%} {limit.hard_limit:>10.2%} "
              f"{limit.breach_status:>12}")

    # Model Risk
    print("\n[9] Model Risk Monitoring")
    print("-" * 40)

    # Register a model
    engine.model.register_model(
        "recovery-pred-v1",
        "Recovery Probability Model",
        "gradient_boosting",
        ["balance", "age", "state", "debt_type"],
        datetime.now() - timedelta(days=30),
    )

    # Simulate predictions
    for i in range(200):
        pred_value = random.uniform(0.2, 0.5)
        actual_value = pred_value + random.gauss(0, 0.1)

        engine.model.record_prediction(
            "recovery-pred-v1",
            f"pred-{i}",
            pred_value,
            pred_value - 0.1,
            pred_value + 0.1,
            {"balance": random.uniform(100, 5000)},
        )
        engine.model.record_actual(
            "recovery-pred-v1",
            f"pred-{i}",
            max(0, min(1, actual_value)),
        )

    metrics = engine.model.calculate_model_metrics("recovery-pred-v1")

    if metrics:
        print(f"   Model: {metrics.model_name}")
        print(f"   Accuracy: {metrics.prediction_accuracy:.2%}")
        print(f"   AUC-ROC: {metrics.auc_roc:.4f}")
        print(f"   Precision: {metrics.precision:.4f}")
        print(f"   Recall: {metrics.recall:.4f}")
        print(f"   F1 Score: {metrics.f1_score:.4f}")
        print(f"   Calibration Error: {metrics.calibration_error:.4f}")
        print(f"   Drift Score: {metrics.drift_score:.4f}")
        print(f"   Samples Since Retrain: {metrics.samples_since_retrain}")

    # A/B Test
    print("\n[10] A/B Test Significance")
    print("-" * 40)

    engine.model.register_ab_test(
        "settlement-offer-test",
        "Settlement Offer Strategy Test",
        "Standard Offer",
        "Enhanced Offer",
        minimum_detectable_effect=0.05,
    )

    # Simulate test results
    for _ in range(500):
        engine.model.record_ab_result("settlement-offer-test", "a", random.random() < 0.25)
        engine.model.record_ab_result("settlement-offer-test", "b", random.random() < 0.30)

    ab_result = engine.model.analyze_ab_test("settlement-offer-test")

    if ab_result:
        print(f"   Test: {ab_result.test_name}")
        print(f"   Variant A ({ab_result.variant_a_name}): {ab_result.variant_a_conversion:.2%} "
              f"(n={ab_result.variant_a_samples})")
        print(f"   Variant B ({ab_result.variant_b_name}): {ab_result.variant_b_conversion:.2%} "
              f"(n={ab_result.variant_b_samples})")
        print(f"   Relative Lift: {ab_result.relative_lift:.2%}")
        print(f"   P-Value: {ab_result.p_value:.4f}")
        print(f"   Significant: {'YES' if ab_result.is_significant else 'NO'}")
        if ab_result.recommended_winner:
            print(f"   Recommended Winner: {ab_result.recommended_winner}")

    print("\n" + "=" * 80)
    print("  RISK ENGINE DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo())
