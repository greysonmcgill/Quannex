"""
Sub-$1K Micro-Debt Collection Simulation

QUAN's targeted sweet spot: accounts under $1,000
- Too small for large agencies to prioritize
- High volume, low balance = perfect for AI automation
- Frictionless digital payments maximize conversion
"""

import asyncio
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import sys

sys.path.insert(0, '/home/user/Quan')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class MicroDebtType(Enum):
    """Micro-debt types under $1,000"""
    PAYDAY = "payday"                    # $50-500
    BNPL = "buy_now_pay_later"          # $25-500
    SUBSCRIPTION = "subscription"        # $20-300
    UTILITY = "utility"                  # $25-500
    TELECOM = "telecom"                  # $50-500
    MEDICAL_SMALL = "medical_small"      # $50-1000
    RETAIL_SMALL = "retail_small"        # $50-800
    PERSONAL_MICRO = "personal_micro"    # $100-1000


@dataclass
class MicroDebtProfile:
    """Profile for sub-$1K debt types"""
    debt_type: MicroDebtType
    name: str
    min_balance: Decimal
    max_balance: Decimal
    avg_balance: Decimal

    # Market sizing (accounts in millions, balance in billions)
    accounts_millions: float
    total_balance_billions: float

    # Collection characteristics
    base_recovery_rate: float
    digital_payment_rate: float  # % who pay via digital methods
    one_click_conversion: float  # Conversion rate for one-click pay
    avg_days_to_collect: int

    # Debtor profile
    avg_age: int
    mobile_rate: float  # % with mobile device
    digital_native_rate: float  # % comfortable with digital payments


# Sub-$1K Market Universe
SUB_1K_UNIVERSE: Dict[MicroDebtType, MicroDebtProfile] = {
    MicroDebtType.PAYDAY: MicroDebtProfile(
        debt_type=MicroDebtType.PAYDAY,
        name="Payday Loans",
        min_balance=Decimal("50"),
        max_balance=Decimal("500"),
        avg_balance=Decimal("275"),
        accounts_millions=8.5,
        total_balance_billions=2.3,
        base_recovery_rate=0.32,
        digital_payment_rate=0.65,
        one_click_conversion=0.45,
        avg_days_to_collect=28,
        avg_age=34,
        mobile_rate=0.92,
        digital_native_rate=0.70
    ),

    MicroDebtType.BNPL: MicroDebtProfile(
        debt_type=MicroDebtType.BNPL,
        name="Buy Now Pay Later",
        min_balance=Decimal("25"),
        max_balance=Decimal("500"),
        avg_balance=Decimal("185"),
        accounts_millions=32.0,
        total_balance_billions=5.9,
        base_recovery_rate=0.38,
        digital_payment_rate=0.85,
        one_click_conversion=0.55,
        avg_days_to_collect=21,
        avg_age=29,
        mobile_rate=0.96,
        digital_native_rate=0.88
    ),

    MicroDebtType.SUBSCRIPTION: MicroDebtProfile(
        debt_type=MicroDebtType.SUBSCRIPTION,
        name="Subscription Services",
        min_balance=Decimal("20"),
        max_balance=Decimal("300"),
        avg_balance=Decimal("95"),
        accounts_millions=15.0,
        total_balance_billions=1.4,
        base_recovery_rate=0.45,
        digital_payment_rate=0.90,
        one_click_conversion=0.60,
        avg_days_to_collect=18,
        avg_age=28,
        mobile_rate=0.95,
        digital_native_rate=0.92
    ),

    MicroDebtType.UTILITY: MicroDebtProfile(
        debt_type=MicroDebtType.UTILITY,
        name="Utility Arrears",
        min_balance=Decimal("25"),
        max_balance=Decimal("500"),
        avg_balance=Decimal("225"),
        accounts_millions=12.0,
        total_balance_billions=2.7,
        base_recovery_rate=0.42,
        digital_payment_rate=0.55,
        one_click_conversion=0.40,
        avg_days_to_collect=32,
        avg_age=42,
        mobile_rate=0.85,
        digital_native_rate=0.58
    ),

    MicroDebtType.TELECOM: MicroDebtProfile(
        debt_type=MicroDebtType.TELECOM,
        name="Telecom Debt",
        min_balance=Decimal("50"),
        max_balance=Decimal("500"),
        avg_balance=Decimal("220"),
        accounts_millions=22.0,
        total_balance_billions=4.8,
        base_recovery_rate=0.35,
        digital_payment_rate=0.75,
        one_click_conversion=0.48,
        avg_days_to_collect=35,
        avg_age=35,
        mobile_rate=0.94,
        digital_native_rate=0.72
    ),

    MicroDebtType.MEDICAL_SMALL: MicroDebtProfile(
        debt_type=MicroDebtType.MEDICAL_SMALL,
        name="Small Medical Debt",
        min_balance=Decimal("50"),
        max_balance=Decimal("1000"),
        avg_balance=Decimal("385"),
        accounts_millions=45.0,
        total_balance_billions=17.3,
        base_recovery_rate=0.28,
        digital_payment_rate=0.50,
        one_click_conversion=0.35,
        avg_days_to_collect=45,
        avg_age=45,
        mobile_rate=0.82,
        digital_native_rate=0.52
    ),

    MicroDebtType.RETAIL_SMALL: MicroDebtProfile(
        debt_type=MicroDebtType.RETAIL_SMALL,
        name="Small Retail Credit",
        min_balance=Decimal("50"),
        max_balance=Decimal("800"),
        avg_balance=Decimal("295"),
        accounts_millions=28.0,
        total_balance_billions=8.3,
        base_recovery_rate=0.38,
        digital_payment_rate=0.70,
        one_click_conversion=0.50,
        avg_days_to_collect=38,
        avg_age=38,
        mobile_rate=0.88,
        digital_native_rate=0.65
    ),

    MicroDebtType.PERSONAL_MICRO: MicroDebtProfile(
        debt_type=MicroDebtType.PERSONAL_MICRO,
        name="Personal Micro-Loans",
        min_balance=Decimal("100"),
        max_balance=Decimal("1000"),
        avg_balance=Decimal("450"),
        accounts_millions=18.0,
        total_balance_billions=8.1,
        base_recovery_rate=0.40,
        digital_payment_rate=0.72,
        one_click_conversion=0.52,
        avg_days_to_collect=42,
        avg_age=36,
        mobile_rate=0.90,
        digital_native_rate=0.68
    ),
}


def get_sub_1k_market_summary() -> Dict[str, Any]:
    """Calculate sub-$1K market totals"""
    total_accounts = sum(p.accounts_millions for p in SUB_1K_UNIVERSE.values())
    total_balance = sum(p.total_balance_billions for p in SUB_1K_UNIVERSE.values())

    weighted_recovery = sum(
        p.base_recovery_rate * p.total_balance_billions
        for p in SUB_1K_UNIVERSE.values()
    ) / total_balance

    weighted_digital = sum(
        p.digital_payment_rate * p.accounts_millions
        for p in SUB_1K_UNIVERSE.values()
    ) / total_accounts

    weighted_avg_balance = total_balance * 1e9 / (total_accounts * 1e6)

    return {
        "total_accounts_millions": total_accounts,
        "total_balance_billions": total_balance,
        "weighted_avg_balance": weighted_avg_balance,
        "weighted_recovery_rate": weighted_recovery,
        "weighted_digital_rate": weighted_digital,
        "by_type": {
            dt.value: {
                "accounts_m": p.accounts_millions,
                "balance_b": p.total_balance_billions,
                "avg_balance": float(p.avg_balance),
                "recovery": p.base_recovery_rate,
                "digital_rate": p.digital_payment_rate
            }
            for dt, p in SUB_1K_UNIVERSE.items()
        }
    }


@dataclass
class Sub1KAccount:
    """A sub-$1K micro-debt account"""
    account_id: str
    debt_type: MicroDebtType
    balance: Decimal
    original_balance: Decimal

    # Debtor characteristics
    age: int
    has_mobile: bool
    is_digital_native: bool
    payment_willingness: float

    # State tracking
    status: str = "active"
    payments_made: int = 0
    total_paid: Decimal = Decimal("0")
    contact_attempts: int = 0
    last_contact_day: int = -999
    last_payment_day: int = -999
    re_engagement_attempts: int = 0

    # Digital payment readiness
    has_saved_payment: bool = False
    preferred_method: str = "new_card"


@dataclass
class Sub1KConfig:
    """Configuration for sub-$1K focused simulation"""
    num_agents: int = 500
    total_accounts: int = 100000
    simulation_days: int = 90

    # Balance constraints
    max_balance: Decimal = Decimal("1000")
    target_avg_balance: Decimal = Decimal("275")

    # Collection parameters
    max_contact_attempts: int = 8
    max_re_engagement_campaigns: int = 3
    re_engagement_threshold_days: int = 10

    # Cost parameters (optimized for micro-debt)
    cost_per_sms: Decimal = Decimal("0.02")
    cost_per_email: Decimal = Decimal("0.005")
    cost_per_digital_payment: Decimal = Decimal("0.15")
    cost_per_agent_day: Decimal = Decimal("120")


@dataclass
class Sub1KResults:
    """Results from sub-$1K simulation"""
    total_accounts: int = 0
    total_balance: Decimal = Decimal("0")
    avg_balance: Decimal = Decimal("0")

    accounts_collected: int = 0
    accounts_partial: int = 0
    accounts_uncollected: int = 0

    total_collected: Decimal = Decimal("0")
    recovery_rate: float = 0.0

    total_contacts: int = 0
    digital_payments: int = 0
    one_click_payments: int = 0

    total_cost: Decimal = Decimal("0")
    cost_per_dollar: float = 0.0
    profit_margin: float = 0.0
    roi: float = 0.0

    # By debt type
    by_type: Dict[str, Dict] = field(default_factory=dict)

    # Performance indicators
    avg_days_to_collect: float = 0.0
    digital_payment_rate: float = 0.0
    one_click_rate: float = 0.0


class Sub1KSimulator:
    """
    Simulator specifically for sub-$1K micro-debt collection.

    Optimized for:
    - High volume, low balance accounts
    - Digital-first payment capture
    - Frictionless one-click payments
    - SMS/email over phone calls
    """

    def __init__(self, config: Sub1KConfig):
        self.config = config
        self.accounts: List[Sub1KAccount] = []
        self.results = Sub1KResults()
        self.current_day = 0
        self.daily_rates: List[float] = []

        # Type tracking
        self.type_metrics: Dict[str, Dict] = {}

    def generate_portfolio(self):
        """Generate sub-$1K account portfolio"""
        logger.info(f"Generating {self.config.total_accounts:,} sub-$1K accounts...")

        # Calculate account distribution by type
        market = get_sub_1k_market_summary()
        total_market_accounts = market["total_accounts_millions"]

        type_counts = {}
        remaining = self.config.total_accounts

        sorted_types = sorted(
            SUB_1K_UNIVERSE.items(),
            key=lambda x: x[1].accounts_millions,
            reverse=True
        )

        for i, (dt, profile) in enumerate(sorted_types):
            if i == len(sorted_types) - 1:
                type_counts[dt] = remaining
            else:
                count = int(
                    self.config.total_accounts *
                    (profile.accounts_millions / total_market_accounts)
                )
                type_counts[dt] = count
                remaining -= count

        # Generate accounts
        account_num = 0
        for dt, count in type_counts.items():
            profile = SUB_1K_UNIVERSE[dt]

            # Initialize type metrics
            self.type_metrics[dt.value] = {
                "accounts": count,
                "balance": Decimal("0"),
                "collected": Decimal("0"),
                "contacts": 0,
                "payments": 0,
                "digital_payments": 0,
                "collection_days": []
            }

            for _ in range(count):
                # Generate balance within type's range, capped at $1K
                raw = random.random() ** 0.6  # Skew toward lower balances
                balance = (
                    profile.min_balance +
                    Decimal(str(raw)) * (
                        min(profile.max_balance, self.config.max_balance) -
                        profile.min_balance
                    )
                ).quantize(Decimal("0.01"))

                # Generate debtor characteristics
                age = max(18, min(75, int(random.gauss(profile.avg_age, 10))))
                has_mobile = random.random() < profile.mobile_rate
                is_digital = random.random() < profile.digital_native_rate

                # Payment willingness based on characteristics
                willingness = profile.base_recovery_rate
                if is_digital:
                    willingness += 0.15
                if age < 35:
                    willingness += 0.10
                elif age > 55:
                    willingness -= 0.10
                willingness = max(0.1, min(0.85, willingness + random.gauss(0, 0.1)))

                account = Sub1KAccount(
                    account_id=f"MIC-{dt.value[:3].upper()}-{account_num:07d}",
                    debt_type=dt,
                    balance=balance,
                    original_balance=balance,
                    age=age,
                    has_mobile=has_mobile,
                    is_digital_native=is_digital,
                    payment_willingness=willingness
                )

                self.accounts.append(account)
                self.type_metrics[dt.value]["balance"] += balance
                account_num += 1

        self.results.total_accounts = len(self.accounts)
        self.results.total_balance = sum(a.balance for a in self.accounts)
        self.results.avg_balance = self.results.total_balance / len(self.accounts)

        logger.info(f"Generated {len(self.accounts):,} accounts")
        logger.info(f"Total balance: ${self.results.total_balance:,.2f}")
        logger.info(f"Average balance: ${self.results.avg_balance:.2f}")

    def simulate_collection(
        self,
        account: Sub1KAccount,
        day: int
    ) -> Tuple[bool, Decimal, bool]:
        """
        Simulate collection attempt on sub-$1K account.

        Returns: (success, amount_collected, was_digital)

        Industry-calibrated probabilities:
        - Sub-$1K segment has ~25-35% base recovery (higher than larger debts)
        - Digital channels boost conversion by 15-20%
        - Multiple contacts needed to convert
        """
        profile = SUB_1K_UNIVERSE[account.debt_type]

        # Base probability: start with profile's base rate
        # This accounts for the inherent collectability of the debt type
        base_prob = profile.base_recovery_rate * 0.3  # Per-contact probability

        # Willingness multiplier
        willingness_mult = 0.5 + (account.payment_willingness * 0.5)
        prob = base_prob * willingness_mult

        # Digital native bonus (10% lift)
        if account.is_digital_native:
            prob *= 1.10

        # Mobile device bonus (can receive SMS, use mobile pay)
        if account.has_mobile:
            prob *= 1.05

        # Saved payment method = one-click potential (significant boost)
        if account.has_saved_payment:
            prob *= 1.25

        # Contact attempt impact - builds over time then decays
        if account.contact_attempts == 0:
            prob *= 0.7  # First contact has lower conversion
        elif account.contact_attempts <= 3:
            prob *= 1.0  # Peak effectiveness
        else:
            # Decay after multiple attempts
            decay = 0.88 if account.is_digital_native else 0.82
            excess_attempts = account.contact_attempts - 3
            prob *= (decay ** excess_attempts)

        # Re-engagement bonus (time gap refreshes interest)
        if account.re_engagement_attempts > 0:
            prob *= 1.12

        # Cap at realistic maximum
        prob = min(0.45, prob)

        success = random.random() < prob
        amount = Decimal("0")
        was_digital = False

        if success:
            # Determine payment amount
            balance = account.balance

            # Most sub-$1K accounts pay in full
            if random.random() < 0.85:
                amount = balance
            else:
                # Partial payment
                amount = (balance * Decimal(str(random.uniform(0.4, 0.8)))).quantize(Decimal("0.01"))

            # Determine if digital payment
            digital_prob = profile.digital_payment_rate
            if account.is_digital_native:
                digital_prob += 0.15
            if account.has_mobile:
                digital_prob += 0.10

            was_digital = random.random() < min(0.95, digital_prob)

            # Update account
            account.balance -= amount
            account.total_paid += amount
            account.payments_made += 1
            account.last_payment_day = day

            # Save payment method for future (70% chance)
            if was_digital and random.random() < 0.70:
                account.has_saved_payment = True

            if account.balance <= 0:
                account.status = "collected"
            else:
                account.status = "partial"

            # Track collection time
            collection_days = day - (account.last_contact_day if account.last_contact_day > 0 else 0)
            self.type_metrics[account.debt_type.value]["collection_days"].append(collection_days)

        # Update tracking
        account.contact_attempts += 1
        account.last_contact_day = day

        return success, amount, was_digital

    async def run_day(self, day: int):
        """Run a single simulation day"""
        self.current_day = day
        daily_collected = Decimal("0")
        daily_contacts = 0
        daily_digital = 0
        daily_one_click = 0

        for account in self.accounts:
            if account.status == "collected":
                continue

            days_since_contact = day - account.last_contact_day

            # Skip if recently contacted
            if days_since_contact < 2:  # Faster cadence for micro-debt
                continue

            should_contact = False

            # Fresh or active accounts
            if account.contact_attempts < self.config.max_contact_attempts:
                should_contact = True

            # Re-engagement for dormant
            elif (days_since_contact > self.config.re_engagement_threshold_days and
                  account.re_engagement_attempts < self.config.max_re_engagement_campaigns):
                should_contact = True
                account.re_engagement_attempts += 1

            if should_contact:
                success, amount, was_digital = self.simulate_collection(account, day)

                daily_contacts += 1
                self.type_metrics[account.debt_type.value]["contacts"] += 1

                if success:
                    daily_collected += amount
                    self.type_metrics[account.debt_type.value]["collected"] += amount
                    self.type_metrics[account.debt_type.value]["payments"] += 1

                    if was_digital:
                        daily_digital += 1
                        self.type_metrics[account.debt_type.value]["digital_payments"] += 1

                        # Check if was one-click (has saved method)
                        if account.has_saved_payment:
                            daily_one_click += 1

        # Update results
        self.results.total_collected += daily_collected
        self.results.total_contacts += daily_contacts
        self.results.digital_payments += daily_digital
        self.results.one_click_payments += daily_one_click

        if self.results.total_balance > 0:
            rate = float(self.results.total_collected / self.results.total_balance)
            self.daily_rates.append(rate)

    def check_convergence(self) -> bool:
        """Check if simulation has converged"""
        if len(self.daily_rates) < 45:
            return False

        recent = self.daily_rates[-10:]
        std = statistics.stdev(recent)
        return std < 0.001

    def calculate_final_metrics(self):
        """Calculate final metrics"""
        collected = sum(1 for a in self.accounts if a.status == "collected")
        partial = sum(1 for a in self.accounts if a.status == "partial")

        self.results.accounts_collected = collected
        self.results.accounts_partial = partial
        self.results.accounts_uncollected = len(self.accounts) - collected - partial

        if self.results.total_balance > 0:
            self.results.recovery_rate = float(
                self.results.total_collected / self.results.total_balance
            )

        # Calculate costs (digital-optimized)
        # SMS/email costs much less than phone calls
        sms_contacts = int(self.results.total_contacts * 0.6)
        email_contacts = int(self.results.total_contacts * 0.35)

        self.results.total_cost = (
            self.config.cost_per_sms * sms_contacts +
            self.config.cost_per_email * email_contacts +
            self.config.cost_per_digital_payment * self.results.digital_payments +
            self.config.cost_per_agent_day * self.config.num_agents * self.current_day
        )

        if self.results.total_collected > 0:
            self.results.cost_per_dollar = float(
                self.results.total_cost / self.results.total_collected
            )
            net = self.results.total_collected - self.results.total_cost
            self.results.profit_margin = float(net / self.results.total_collected)
            self.results.roi = float(net / self.results.total_cost)

        # Performance metrics
        if self.results.digital_payments > 0:
            total_payments = sum(
                m["payments"] for m in self.type_metrics.values()
            )
            self.results.digital_payment_rate = (
                self.results.digital_payments / total_payments if total_payments > 0 else 0
            )
            self.results.one_click_rate = (
                self.results.one_click_payments / self.results.digital_payments
            )

        # Average days to collect
        all_days = []
        for m in self.type_metrics.values():
            all_days.extend(m.get("collection_days", []))
        if all_days:
            self.results.avg_days_to_collect = statistics.mean(all_days)

        # By type results
        for dt_name, metrics in self.type_metrics.items():
            if metrics["balance"] > 0:
                self.results.by_type[dt_name] = {
                    "accounts": metrics["accounts"],
                    "balance": float(metrics["balance"]),
                    "collected": float(metrics["collected"]),
                    "recovery_rate": float(metrics["collected"] / metrics["balance"]),
                    "contacts": metrics["contacts"],
                    "payments": metrics["payments"],
                    "digital_rate": (
                        metrics["digital_payments"] / metrics["payments"]
                        if metrics["payments"] > 0 else 0
                    )
                }

    async def run(self) -> Sub1KResults:
        """Run the full simulation"""
        self.generate_portfolio()

        logger.info(f"\nRunning {self.config.simulation_days}-day simulation...")
        logger.info(f"Agents: {self.config.num_agents}")
        logger.info(f"Target: Sub-$1K accounts only (avg ${self.results.avg_balance:.2f})")

        for day in range(self.config.simulation_days):
            await self.run_day(day)

            if day > 0 and day % 15 == 0:
                rate = self.daily_rates[-1] * 100 if self.daily_rates else 0
                logger.info(f"  Day {day}: Recovery {rate:.1f}%, "
                           f"Collected ${self.results.total_collected:,.2f}")

            if day > 45 and self.check_convergence():
                logger.info(f"  Converged at day {day}")
                break

        self.calculate_final_metrics()
        return self.results


def print_sub1k_market():
    """Print sub-$1K market summary"""
    market = get_sub_1k_market_summary()

    print("\n" + "=" * 75)
    print("  SUB-$1K MICRO-DEBT MARKET - QUAN SWEET SPOT")
    print("=" * 75)
    print(f"\n  Total Addressable Market:")
    print(f"    Accounts:        {market['total_accounts_millions']:.1f} Million")
    print(f"    Balance:         ${market['total_balance_billions']:.1f} Billion")
    print(f"    Avg Balance:     ${market['weighted_avg_balance']:.0f}")
    print(f"    Avg Recovery:    {market['weighted_recovery_rate']*100:.1f}%")
    print(f"    Digital Rate:    {market['weighted_digital_rate']*100:.1f}%")

    print(f"\n  WHY LARGE AGENCIES IGNORE THIS SEGMENT:")
    print(f"    - Average balance ${market['weighted_avg_balance']:.0f} < $1,000 threshold")
    print(f"    - Phone-based collection uneconomical at this scale")
    print(f"    - High volume requires automation they lack")

    print(f"\n  WHY QUAN WINS HERE:")
    print(f"    - AI handles unlimited volume at near-zero marginal cost")
    print(f"    - Digital-first: {market['weighted_digital_rate']*100:.0f}% pay digitally")
    print(f"    - Frictionless mobile payments = higher conversion")
    print(f"    - SMS/email at $0.02 vs phone at $0.50+")

    print(f"\n  BREAKDOWN BY DEBT TYPE:")
    print("  " + "-" * 71)
    print(f"  {'Type':<20} {'Accounts':>10} {'Balance':>10} {'Avg Bal':>10} {'Recovery':>10} {'Digital':>10}")
    print("  " + "-" * 71)

    for dt_name, data in sorted(
        market['by_type'].items(),
        key=lambda x: x[1]['accounts_m'],
        reverse=True
    ):
        print(f"  {dt_name:<20} {data['accounts_m']:>9.1f}M "
              f"${data['balance_b']:>8.1f}B ${data['avg_balance']:>9.0f} "
              f"{data['recovery']*100:>9.0f}% {data['digital_rate']*100:>9.0f}%")

    print("  " + "-" * 71)
    print()


async def run_sub1k_simulation():
    """Run sub-$1K focused simulation"""
    print_sub1k_market()

    config = Sub1KConfig(
        num_agents=500,
        total_accounts=100000,
        simulation_days=90,
        max_balance=Decimal("1000"),
        max_contact_attempts=8,
        max_re_engagement_campaigns=3,
        re_engagement_threshold_days=10,
        cost_per_sms=Decimal("0.02"),
        cost_per_email=Decimal("0.005"),
        cost_per_digital_payment=Decimal("0.15"),
        cost_per_agent_day=Decimal("120")
    )

    simulator = Sub1KSimulator(config)
    results = await simulator.run()

    print("\n" + "=" * 75)
    print("  SUB-$1K SIMULATION RESULTS")
    print("=" * 75)

    print(f"\n  PORTFOLIO (Sub-$1K Only):")
    print(f"    Total Accounts:     {results.total_accounts:,}")
    print(f"    Total Balance:      ${results.total_balance:,.2f}")
    print(f"    Average Balance:    ${results.avg_balance:.2f}")

    print(f"\n  RECOVERY:")
    print(f"    Collected:          ${results.total_collected:,.2f}")
    print(f"    Recovery Rate:      {results.recovery_rate*100:.1f}%")
    print(f"    Accounts Closed:    {results.accounts_collected:,} ({results.accounts_collected/results.total_accounts*100:.1f}%)")
    print(f"    Partial:            {results.accounts_partial:,}")
    print(f"    Uncollected:        {results.accounts_uncollected:,}")

    print(f"\n  DIGITAL PERFORMANCE:")
    print(f"    Total Contacts:     {results.total_contacts:,}")
    print(f"    Digital Payments:   {results.digital_payments:,} ({results.digital_payment_rate*100:.1f}%)")
    print(f"    One-Click Payments: {results.one_click_payments:,} ({results.one_click_rate*100:.1f}% of digital)")
    print(f"    Avg Days to Collect: {results.avg_days_to_collect:.1f}")

    print(f"\n  ECONOMICS:")
    print(f"    Total Cost:         ${results.total_cost:,.2f}")
    print(f"    Cost per $1:        ${results.cost_per_dollar:.3f}")
    print(f"    Profit Margin:      {results.profit_margin*100:.1f}%")
    print(f"    ROI:                {results.roi*100:.0f}%")

    print(f"\n  RESULTS BY DEBT TYPE:")
    print("  " + "-" * 71)
    print(f"  {'Type':<20} {'Accounts':>10} {'Balance':>12} {'Collected':>12} {'Rate':>8} {'Digital':>8}")
    print("  " + "-" * 71)

    for dt_name, data in sorted(
        results.by_type.items(),
        key=lambda x: x[1]['collected'],
        reverse=True
    ):
        print(f"  {dt_name:<20} {data['accounts']:>10,} "
              f"${data['balance']:>11,.0f} ${data['collected']:>11,.0f} "
              f"{data['recovery_rate']*100:>7.1f}% {data['digital_rate']*100:>7.1f}%")

    print("  " + "-" * 71)

    # Competitive advantage summary
    print(f"\n  COMPETITIVE ADVANTAGE vs LARGE AGENCIES:")
    print(f"    Cost per $1 collected:  QUAN ${results.cost_per_dollar:.3f} vs Industry $0.25-0.35")
    print(f"    Digital payment rate:   QUAN {results.digital_payment_rate*100:.0f}% vs Industry 30-40%")
    print(f"    Days to collect:        QUAN {results.avg_days_to_collect:.0f} vs Industry 60-90")
    print(f"    Profit margin:          QUAN {results.profit_margin*100:.0f}% vs Industry 15-25%")

    print("\n" + "=" * 75)

    return results


if __name__ == "__main__":
    asyncio.run(run_sub1k_simulation())
