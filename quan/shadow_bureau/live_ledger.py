"""
Live Ledger - Real-Time Micro-Credit Behavioral Database

The Shadow Bureau's core data infrastructure. Unlike traditional bureaus
that update every 30-90 days, the Live Ledger operates in REAL-TIME.

This creates a proprietary data moat: We become the primary source of truth
for creditworthiness in the gig-economy, BNPL, and micro-credit space.

Key Innovation: Payment behavior on micro-debts is MORE predictive of
future default risk than traditional FICO scores for this demographic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
import hashlib
import json


class DebtCategory(Enum):
    """Micro-debt categorization"""
    BNPL = "bnpl"                    # Buy Now Pay Later (Klarna, Affirm, Afterpay)
    SUBSCRIPTION = "subscription"     # Streaming, SaaS, memberships
    GIG_ADVANCE = "gig_advance"       # Uber, DoorDash, Instacart advances
    OVERDRAFT = "overdraft"           # Bank overdraft/NSF
    UTILITY = "utility"               # Phone, internet, utilities
    MEDICAL = "medical"               # Small medical bills
    FINTECH_LOAN = "fintech_loan"     # Cash App, Venmo, PayPal credit
    TELECOM = "telecom"               # Phone contracts, equipment
    OTHER = "other"


class PaymentBehavior(Enum):
    """Behavioral classification based on payment patterns"""
    PROMPT_PAYER = auto()        # Pays within 7 days of contact
    NEGOTIATOR = auto()          # Settles for less, but pays
    PLAN_KEEPER = auto()         # Makes payment plan, keeps it
    PLAN_BREAKER = auto()        # Makes payment plan, breaks it
    GHOST = auto()               # Never responds
    HOSTILE_RESOLVER = auto()    # Complains but eventually pays
    CHRONIC_DEFAULTER = auto()   # Pattern of defaults across creditors


class RiskTier(Enum):
    """Real-time risk classification"""
    TIER_A = "A"   # High probability of payment (>70%)
    TIER_B = "B"   # Moderate probability (40-70%)
    TIER_C = "C"   # Low probability (20-40%)
    TIER_D = "D"   # Very low probability (5-20%)
    TIER_F = "F"   # Effectively uncollectible (<5%)


@dataclass
class MicroDebtRecord:
    """Individual debt record in the Live Ledger"""
    record_id: str
    consumer_id: str
    creditor_id: str
    creditor_name: str

    # Debt details
    category: DebtCategory
    original_balance: float
    current_balance: float
    charge_off_date: datetime
    days_past_due: int

    # Collection status
    collection_status: str  # active, resolved, disputed, uncollectible
    resolution_type: str | None = None  # paid_full, settled, payment_plan, written_off
    resolution_date: datetime | None = None
    resolution_amount: float | None = None

    # Behavioral data (THE MOAT)
    first_contact_date: datetime | None = None
    first_response_date: datetime | None = None
    response_latency_hours: float | None = None
    total_contacts: int = 0
    total_responses: int = 0
    promises_made: int = 0
    promises_kept: int = 0
    payment_behavior: PaymentBehavior | None = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConsumerLedgerProfile:
    """
    Aggregated consumer profile across all debts

    This is the "Shadow Credit Score" - a real-time behavioral
    assessment that traditional bureaus cannot provide.
    """
    consumer_id: str

    # Identity (hashed/anonymized for data licensing)
    identity_hash: str
    geo_region: str  # State/Metro for compliance

    # Aggregate debt metrics
    total_debts_tracked: int = 0
    total_balance_tracked: float = 0.0
    total_balance_resolved: float = 0.0
    total_balance_outstanding: float = 0.0

    # Behavioral scores (0-100)
    response_score: float = 50.0      # How likely to respond
    payment_score: float = 50.0       # How likely to pay
    promise_score: float = 50.0       # How reliable are promises
    velocity_score: float = 50.0      # How fast they resolve

    # Composite Shadow Score (0-850, mimics FICO range)
    shadow_score: int = 500

    # Risk classification
    risk_tier: RiskTier = RiskTier.TIER_C

    # Pattern detection
    primary_behavior: PaymentBehavior = PaymentBehavior.GHOST
    debt_categories: list[DebtCategory] = field(default_factory=list)

    # Network effects (cross-creditor intelligence)
    creditors_in_network: int = 0
    network_default_rate: float = 0.0

    # Timestamps
    first_seen: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    score_updated: datetime = field(default_factory=datetime.now)


@dataclass
class CreditorProfile:
    """Creditor/merchant profile for network intelligence"""
    creditor_id: str
    creditor_name: str
    industry: str
    category: DebtCategory

    # Portfolio metrics
    total_accounts_placed: int = 0
    total_balance_placed: float = 0.0
    total_recovered: float = 0.0
    recovery_rate: float = 0.0

    # Data quality metrics
    contact_accuracy_rate: float = 0.0  # How good is their consumer data
    avg_balance: float = 0.0
    avg_days_past_due: int = 0

    # Integration status
    api_integrated: bool = False
    real_time_placement: bool = False

    # Timestamps
    onboarded_at: datetime = field(default_factory=datetime.now)


class LiveLedger:
    """
    The Shadow Bureau's Core Database

    Key Differentiators:
    1. REAL-TIME updates (vs 30-90 day bureau lag)
    2. BEHAVIORAL data (not just payment history)
    3. MICRO-CREDIT focus (the blind spot of traditional bureaus)
    4. NETWORK EFFECTS (cross-creditor default intelligence)
    """

    def __init__(self):
        self.debt_records: dict[str, MicroDebtRecord] = {}
        self.consumer_profiles: dict[str, ConsumerLedgerProfile] = {}
        self.creditor_profiles: dict[str, CreditorProfile] = {}
        self._score_weights = {
            "response": 0.20,
            "payment": 0.35,
            "promise": 0.25,
            "velocity": 0.20
        }

    def ingest_debt(
        self,
        creditor_id: str,
        creditor_name: str,
        consumer_id: str,
        category: DebtCategory,
        original_balance: float,
        charge_off_date: datetime,
        days_past_due: int,
        consumer_data: dict[str, Any] | None = None
    ) -> MicroDebtRecord:
        """
        Ingest a new debt into the Live Ledger

        This is the entry point for the data flywheel
        """
        record_id = self._generate_record_id(creditor_id, consumer_id, charge_off_date)

        record = MicroDebtRecord(
            record_id=record_id,
            consumer_id=consumer_id,
            creditor_id=creditor_id,
            creditor_name=creditor_name,
            category=category,
            original_balance=original_balance,
            current_balance=original_balance,
            charge_off_date=charge_off_date,
            days_past_due=days_past_due,
            collection_status="active"
        )

        self.debt_records[record_id] = record

        # Update or create consumer profile
        self._update_consumer_profile(consumer_id, record, consumer_data)

        # Update creditor metrics
        self._update_creditor_profile(creditor_id, creditor_name, category, record)

        return record

    def record_interaction(
        self,
        record_id: str,
        interaction_type: str,
        response_received: bool,
        promise_made: bool = False,
        payment_received: float = 0.0
    ) -> None:
        """Record an interaction and update behavioral scores"""
        record = self.debt_records.get(record_id)
        if not record:
            return

        now = datetime.now()
        record.updated_at = now
        record.total_contacts += 1

        if response_received:
            record.total_responses += 1
            if record.first_response_date is None:
                record.first_response_date = now
                if record.first_contact_date:
                    delta = now - record.first_contact_date
                    record.response_latency_hours = delta.total_seconds() / 3600

        if promise_made:
            record.promises_made += 1

        if payment_received > 0:
            record.current_balance -= payment_received
            if record.current_balance <= 0:
                record.collection_status = "resolved"
                record.resolution_type = "paid_full" if payment_received >= record.original_balance else "settled"
                record.resolution_date = now
                record.resolution_amount = record.original_balance - record.current_balance

        # Update consumer behavioral scores
        self._recalculate_consumer_scores(record.consumer_id)

    def record_promise_outcome(
        self,
        record_id: str,
        promise_kept: bool
    ) -> None:
        """Record whether a payment promise was kept"""
        record = self.debt_records.get(record_id)
        if not record:
            return

        if promise_kept:
            record.promises_kept += 1

        # Recalculate scores
        self._recalculate_consumer_scores(record.consumer_id)

    def query_consumer(self, consumer_id: str) -> dict[str, Any] | None:
        """
        Query the Shadow Bureau for consumer intelligence

        This is the API that BNPL providers and micro-lenders
        can use to assess creditworthiness in real-time.
        """
        profile = self.consumer_profiles.get(consumer_id)
        if not profile:
            return None

        # Get all debt records for this consumer
        records = [r for r in self.debt_records.values() if r.consumer_id == consumer_id]

        active_debts = [r for r in records if r.collection_status == "active"]
        resolved_debts = [r for r in records if r.collection_status == "resolved"]

        return {
            "consumer_id": consumer_id,
            "shadow_score": profile.shadow_score,
            "risk_tier": profile.risk_tier.value,
            "behavioral_profile": profile.primary_behavior.name,

            # Real-time debt intelligence
            "active_debts": len(active_debts),
            "active_balance": sum(r.current_balance for r in active_debts),
            "resolved_debts": len(resolved_debts),
            "resolved_balance": sum(r.resolution_amount or 0 for r in resolved_debts),

            # Behavioral scores
            "response_score": profile.response_score,
            "payment_score": profile.payment_score,
            "promise_score": profile.promise_score,
            "velocity_score": profile.velocity_score,

            # Network intelligence
            "creditors_in_network": profile.creditors_in_network,
            "network_default_rate": profile.network_default_rate,

            # Timing
            "last_activity": profile.last_activity.isoformat(),
            "score_freshness": (datetime.now() - profile.score_updated).total_seconds()
        }

    def network_check(self, consumer_id: str) -> dict[str, Any]:
        """
        Check if consumer has outstanding debts in the network

        THE NETWORK EFFECT: Pay the platform, or get blocked everywhere.
        """
        records = [r for r in self.debt_records.values()
                   if r.consumer_id == consumer_id and r.collection_status == "active"]

        if not records:
            return {
                "consumer_id": consumer_id,
                "has_outstanding": False,
                "total_outstanding": 0.0,
                "creditors_owed": [],
                "recommendation": "APPROVE"
            }

        creditors = list(set(r.creditor_name for r in records))
        total = sum(r.current_balance for r in records)

        profile = self.consumer_profiles.get(consumer_id)
        risk = profile.risk_tier if profile else RiskTier.TIER_C

        recommendation = "APPROVE" if total < 50 and risk in [RiskTier.TIER_A, RiskTier.TIER_B] else "REVIEW"
        if total > 200 or risk in [RiskTier.TIER_D, RiskTier.TIER_F]:
            recommendation = "DECLINE"

        return {
            "consumer_id": consumer_id,
            "has_outstanding": True,
            "total_outstanding": total,
            "debt_count": len(records),
            "creditors_owed": creditors,
            "risk_tier": risk.value,
            "recommendation": recommendation
        }

    def get_portfolio_analytics(self, creditor_id: str | None = None) -> dict[str, Any]:
        """Get portfolio-level analytics for reporting"""
        if creditor_id:
            records = [r for r in self.debt_records.values() if r.creditor_id == creditor_id]
        else:
            records = list(self.debt_records.values())

        if not records:
            return {"status": "no_data"}

        active = [r for r in records if r.collection_status == "active"]
        resolved = [r for r in records if r.collection_status == "resolved"]

        total_placed = sum(r.original_balance for r in records)
        total_recovered = sum(r.resolution_amount or 0 for r in resolved)

        # Category breakdown
        by_category: dict[str, dict[str, float]] = {}
        for r in records:
            cat = r.category.value
            if cat not in by_category:
                by_category[cat] = {"count": 0, "balance": 0, "recovered": 0}
            by_category[cat]["count"] += 1
            by_category[cat]["balance"] += r.original_balance
            if r.resolution_amount:
                by_category[cat]["recovered"] += r.resolution_amount

        # Behavioral distribution
        behaviors: dict[str, int] = {}
        for profile in self.consumer_profiles.values():
            b = profile.primary_behavior.name
            behaviors[b] = behaviors.get(b, 0) + 1

        return {
            "total_accounts": len(records),
            "active_accounts": len(active),
            "resolved_accounts": len(resolved),
            "total_balance_placed": total_placed,
            "total_recovered": total_recovered,
            "recovery_rate": total_recovered / total_placed if total_placed > 0 else 0,
            "avg_balance": total_placed / len(records) if records else 0,
            "by_category": by_category,
            "behavioral_distribution": behaviors,
            "avg_shadow_score": sum(p.shadow_score for p in self.consumer_profiles.values()) / len(self.consumer_profiles) if self.consumer_profiles else 0
        }

    def _generate_record_id(
        self,
        creditor_id: str,
        consumer_id: str,
        charge_off_date: datetime
    ) -> str:
        """Generate unique record ID"""
        data = f"{creditor_id}:{consumer_id}:{charge_off_date.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _update_consumer_profile(
        self,
        consumer_id: str,
        record: MicroDebtRecord,
        consumer_data: dict[str, Any] | None
    ) -> None:
        """Update or create consumer profile"""
        if consumer_id not in self.consumer_profiles:
            identity_hash = hashlib.sha256(consumer_id.encode()).hexdigest()
            self.consumer_profiles[consumer_id] = ConsumerLedgerProfile(
                consumer_id=consumer_id,
                identity_hash=identity_hash,
                geo_region=consumer_data.get("state", "UNKNOWN") if consumer_data else "UNKNOWN"
            )

        profile = self.consumer_profiles[consumer_id]
        profile.total_debts_tracked += 1
        profile.total_balance_tracked += record.original_balance
        profile.total_balance_outstanding += record.current_balance
        profile.last_activity = datetime.now()

        if record.category not in profile.debt_categories:
            profile.debt_categories.append(record.category)

        # Count unique creditors
        creditor_ids = set(r.creditor_id for r in self.debt_records.values()
                          if r.consumer_id == consumer_id)
        profile.creditors_in_network = len(creditor_ids)

    def _update_creditor_profile(
        self,
        creditor_id: str,
        creditor_name: str,
        category: DebtCategory,
        record: MicroDebtRecord
    ) -> None:
        """Update creditor profile"""
        if creditor_id not in self.creditor_profiles:
            self.creditor_profiles[creditor_id] = CreditorProfile(
                creditor_id=creditor_id,
                creditor_name=creditor_name,
                industry=category.value,
                category=category
            )

        profile = self.creditor_profiles[creditor_id]
        profile.total_accounts_placed += 1
        profile.total_balance_placed += record.original_balance
        profile.avg_balance = profile.total_balance_placed / profile.total_accounts_placed

    def _recalculate_consumer_scores(self, consumer_id: str) -> None:
        """Recalculate all behavioral scores for a consumer"""
        profile = self.consumer_profiles.get(consumer_id)
        if not profile:
            return

        records = [r for r in self.debt_records.values() if r.consumer_id == consumer_id]
        if not records:
            return

        # Response score (0-100)
        total_contacts = sum(r.total_contacts for r in records)
        total_responses = sum(r.total_responses for r in records)
        profile.response_score = (total_responses / total_contacts * 100) if total_contacts > 0 else 50

        # Payment score (0-100)
        resolved = [r for r in records if r.collection_status == "resolved"]
        profile.payment_score = (len(resolved) / len(records) * 100) if records else 50

        # Promise score (0-100)
        total_promises = sum(r.promises_made for r in records)
        kept_promises = sum(r.promises_kept for r in records)
        profile.promise_score = (kept_promises / total_promises * 100) if total_promises > 0 else 50

        # Velocity score (based on response latency)
        latencies = [r.response_latency_hours for r in records if r.response_latency_hours is not None]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Convert to score (faster = higher score)
            profile.velocity_score = max(0, min(100, 100 - (avg_latency / 2)))
        else:
            profile.velocity_score = 50

        # Calculate Shadow Score (0-850)
        weighted_score = (
            profile.response_score * self._score_weights["response"] +
            profile.payment_score * self._score_weights["payment"] +
            profile.promise_score * self._score_weights["promise"] +
            profile.velocity_score * self._score_weights["velocity"]
        )
        profile.shadow_score = int(300 + (weighted_score * 5.5))  # Scale to 300-850

        # Determine risk tier
        if profile.shadow_score >= 750:
            profile.risk_tier = RiskTier.TIER_A
        elif profile.shadow_score >= 650:
            profile.risk_tier = RiskTier.TIER_B
        elif profile.shadow_score >= 550:
            profile.risk_tier = RiskTier.TIER_C
        elif profile.shadow_score >= 450:
            profile.risk_tier = RiskTier.TIER_D
        else:
            profile.risk_tier = RiskTier.TIER_F

        # Determine primary behavior
        if profile.payment_score > 70 and profile.velocity_score > 60:
            profile.primary_behavior = PaymentBehavior.PROMPT_PAYER
        elif profile.payment_score > 50:
            if profile.promise_score > 70:
                profile.primary_behavior = PaymentBehavior.PLAN_KEEPER
            else:
                profile.primary_behavior = PaymentBehavior.NEGOTIATOR
        elif profile.response_score < 20:
            profile.primary_behavior = PaymentBehavior.GHOST
        elif profile.promise_score < 30:
            profile.primary_behavior = PaymentBehavior.PLAN_BREAKER
        else:
            profile.primary_behavior = PaymentBehavior.CHRONIC_DEFAULTER

        profile.score_updated = datetime.now()


# Database Schema (SQL representation for production deployment)
LIVE_LEDGER_SCHEMA = """
-- ============================================================
-- LIVE LEDGER - SHADOW BUREAU DATABASE SCHEMA
-- Real-time micro-credit behavioral database
-- ============================================================

-- Consumers (anonymized for data licensing)
CREATE TABLE consumers (
    consumer_id VARCHAR(64) PRIMARY KEY,
    identity_hash VARCHAR(64) NOT NULL,
    geo_region VARCHAR(32),

    -- Aggregate metrics
    total_debts_tracked INTEGER DEFAULT 0,
    total_balance_tracked DECIMAL(12,2) DEFAULT 0,
    total_balance_resolved DECIMAL(12,2) DEFAULT 0,
    total_balance_outstanding DECIMAL(12,2) DEFAULT 0,

    -- Behavioral scores (0-100)
    response_score DECIMAL(5,2) DEFAULT 50,
    payment_score DECIMAL(5,2) DEFAULT 50,
    promise_score DECIMAL(5,2) DEFAULT 50,
    velocity_score DECIMAL(5,2) DEFAULT 50,

    -- Shadow Score (300-850)
    shadow_score INTEGER DEFAULT 500,
    risk_tier CHAR(1) DEFAULT 'C',
    primary_behavior VARCHAR(32),

    -- Network intelligence
    creditors_in_network INTEGER DEFAULT 0,
    network_default_rate DECIMAL(5,4) DEFAULT 0,

    -- Timestamps
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    score_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_shadow_score (shadow_score),
    INDEX idx_risk_tier (risk_tier),
    INDEX idx_last_activity (last_activity)
);

-- Debt Records
CREATE TABLE debt_records (
    record_id VARCHAR(64) PRIMARY KEY,
    consumer_id VARCHAR(64) NOT NULL,
    creditor_id VARCHAR(64) NOT NULL,

    -- Debt details
    category VARCHAR(32) NOT NULL,
    original_balance DECIMAL(10,2) NOT NULL,
    current_balance DECIMAL(10,2) NOT NULL,
    charge_off_date DATE NOT NULL,
    days_past_due INTEGER NOT NULL,

    -- Status
    collection_status VARCHAR(32) DEFAULT 'active',
    resolution_type VARCHAR(32),
    resolution_date TIMESTAMP,
    resolution_amount DECIMAL(10,2),

    -- Behavioral tracking
    first_contact_date TIMESTAMP,
    first_response_date TIMESTAMP,
    response_latency_hours DECIMAL(10,2),
    total_contacts INTEGER DEFAULT 0,
    total_responses INTEGER DEFAULT 0,
    promises_made INTEGER DEFAULT 0,
    promises_kept INTEGER DEFAULT 0,
    payment_behavior VARCHAR(32),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id),
    INDEX idx_consumer (consumer_id),
    INDEX idx_creditor (creditor_id),
    INDEX idx_status (collection_status),
    INDEX idx_category (category)
);

-- Creditors
CREATE TABLE creditors (
    creditor_id VARCHAR(64) PRIMARY KEY,
    creditor_name VARCHAR(255) NOT NULL,
    industry VARCHAR(64),
    category VARCHAR(32),

    -- Portfolio metrics
    total_accounts_placed INTEGER DEFAULT 0,
    total_balance_placed DECIMAL(14,2) DEFAULT 0,
    total_recovered DECIMAL(14,2) DEFAULT 0,
    recovery_rate DECIMAL(5,4) DEFAULT 0,

    -- Data quality
    contact_accuracy_rate DECIMAL(5,4) DEFAULT 0,
    avg_balance DECIMAL(10,2) DEFAULT 0,
    avg_days_past_due INTEGER DEFAULT 0,

    -- Integration
    api_integrated BOOLEAN DEFAULT FALSE,
    real_time_placement BOOLEAN DEFAULT FALSE,
    api_key_hash VARCHAR(64),

    -- Timestamps
    onboarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_category (category)
);

-- Interaction Audit Log (immutable)
CREATE TABLE interaction_log (
    interaction_id VARCHAR(64) PRIMARY KEY,
    record_id VARCHAR(64) NOT NULL,
    consumer_id VARCHAR(64) NOT NULL,

    -- Interaction details
    timestamp TIMESTAMP NOT NULL,
    channel VARCHAR(32) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    agent_persona VARCHAR(32),

    -- Content (encrypted in production)
    message_hash VARCHAR(64) NOT NULL,
    sentiment_detected VARCHAR(32),
    strategy_applied VARCHAR(64),
    outcome VARCHAR(32),

    -- Compliance
    compliance_checks JSON,
    regulatory_basis JSON,
    hash_chain VARCHAR(64) NOT NULL,

    FOREIGN KEY (record_id) REFERENCES debt_records(record_id),
    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_record (record_id),
    INDEX idx_hash_chain (hash_chain)
);

-- Network Queries (for data licensing API)
CREATE TABLE api_queries (
    query_id VARCHAR(64) PRIMARY KEY,
    creditor_id VARCHAR(64) NOT NULL,
    consumer_id VARCHAR(64) NOT NULL,
    query_type VARCHAR(32) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_data JSON,
    latency_ms INTEGER,

    FOREIGN KEY (creditor_id) REFERENCES creditors(creditor_id),
    INDEX idx_creditor (creditor_id),
    INDEX idx_timestamp (timestamp)
);

-- Materialized view for real-time scoring
CREATE MATERIALIZED VIEW consumer_risk_scores AS
SELECT
    c.consumer_id,
    c.shadow_score,
    c.risk_tier,
    c.primary_behavior,
    c.total_balance_outstanding,
    COUNT(d.record_id) as active_debt_count,
    SUM(d.current_balance) as active_balance,
    c.score_updated
FROM consumers c
LEFT JOIN debt_records d ON c.consumer_id = d.consumer_id
    AND d.collection_status = 'active'
GROUP BY c.consumer_id;

-- Refresh every 5 minutes for real-time queries
-- REFRESH MATERIALIZED VIEW consumer_risk_scores;
"""


# Demonstration
if __name__ == "__main__":
    ledger = LiveLedger()

    # Simulate debt ingestion
    print("=== LIVE LEDGER DEMO ===\n")

    # Ingest debts from multiple creditors
    debts = [
        ("KLARNA", "Klarna", "C001", DebtCategory.BNPL, 147.50, 45),
        ("AFFIRM", "Affirm", "C001", DebtCategory.BNPL, 89.00, 60),
        ("NETFLIX", "Netflix", "C001", DebtCategory.SUBSCRIPTION, 32.99, 90),
        ("UBER", "Uber", "C002", DebtCategory.GIG_ADVANCE, 75.00, 30),
        ("AFTERPAY", "Afterpay", "C002", DebtCategory.BNPL, 200.00, 45),
    ]

    for cred_id, cred_name, cons_id, cat, balance, dpd in debts:
        ledger.ingest_debt(
            creditor_id=cred_id,
            creditor_name=cred_name,
            consumer_id=cons_id,
            category=cat,
            original_balance=balance,
            charge_off_date=datetime.now() - timedelta(days=dpd),
            days_past_due=dpd
        )

    # Simulate interactions
    records = list(ledger.debt_records.values())
    for record in records[:3]:
        ledger.record_interaction(record.record_id, "sms", response_received=True, promise_made=True)
        ledger.record_promise_outcome(record.record_id, promise_kept=True)
        ledger.record_interaction(record.record_id, "sms", response_received=True, payment_received=record.original_balance * 0.6)

    # Query consumer
    print("Consumer C001 Shadow Bureau Query:")
    result = ledger.query_consumer("C001")
    if result:
        print(f"  Shadow Score: {result['shadow_score']}")
        print(f"  Risk Tier: {result['risk_tier']}")
        print(f"  Behavior: {result['behavioral_profile']}")
        print(f"  Active Debts: {result['active_debts']} (${result['active_balance']:.2f})")
        print(f"  Payment Score: {result['payment_score']:.1f}")

    # Network check
    print("\nNetwork Check for C002:")
    check = ledger.network_check("C002")
    print(f"  Outstanding: ${check['total_outstanding']:.2f}")
    print(f"  Creditors: {check['creditors_owed']}")
    print(f"  Recommendation: {check['recommendation']}")

    # Portfolio analytics
    print("\nPortfolio Analytics:")
    analytics = ledger.get_portfolio_analytics()
    print(f"  Total Accounts: {analytics['total_accounts']}")
    print(f"  Recovery Rate: {analytics['recovery_rate']:.1%}")
    print(f"  Avg Shadow Score: {analytics['avg_shadow_score']:.0f}")
