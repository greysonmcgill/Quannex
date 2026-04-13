"""
QUAN Recovery - Centralized Enums

This module contains all shared enums used across the QUAN platform.
Import enums from here instead of defining them locally to ensure consistency.

Usage:
    from quan.enums import PaymentStatus, ContactChannel, DebtStatus
"""

from enum import Enum, auto


# =============================================================================
# PAYMENT ENUMS
# =============================================================================

class PaymentStatus(Enum):
    """
    Payment lifecycle status.

    Consolidated from:
    - quan/finance/reconciliation.py
    - quan/payments/payment_engine.py
    """
    # Initial states
    PENDING = "pending"
    AUTHORIZED = "authorized"

    # Processing states
    CAPTURED = "captured"
    CLEARED = "cleared"
    SETTLED = "settled"
    RECONCILED = "reconciled"
    APPLIED = "applied"

    # Terminal states - Success
    COMPLETED = "completed"

    # Terminal states - Failure
    FAILED = "failed"
    DECLINED = "declined"
    CANCELLED = "cancelled"

    # Dispute/Reversal states
    REVERSED = "reversed"
    DISPUTED = "disputed"
    CHARGEBACK = "chargeback"
    REFUNDED = "refunded"


class PaymentMethod(Enum):
    """Payment method types"""
    CARD = "card"
    ACH = "ach"
    DEBIT = "debit"
    WALLET = "wallet"
    CHECK = "check"
    CASH = "cash"


class FailureReason(Enum):
    """Payment failure reasons"""
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    CARD_EXPIRED = "card_expired"
    INVALID_CARD = "invalid_card"
    INVALID_ACCOUNT = "invalid_account"
    FRAUD_SUSPECTED = "fraud_suspected"
    BANK_DECLINED = "bank_declined"
    LIMIT_EXCEEDED = "limit_exceeded"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class TransactionType(Enum):
    """Financial transaction types"""
    PAYMENT = "payment"
    ADJUSTMENT = "adjustment"
    WRITE_OFF = "write_off"
    REFUND = "refund"
    FEE = "fee"
    CREDIT = "credit"
    DEBIT = "debit"


# =============================================================================
# CONTACT/COMMUNICATION ENUMS
# =============================================================================

class ContactChannel(Enum):
    """
    Communication channels for debt collection.

    Consolidated from:
    - quan/compliance/compliance_orchestrator.py (most comprehensive)
    - quan/orchestration/re_engagement.py
    - quan/simulation/consumer_simulator.py
    """
    # Phone channels
    PHONE_LIVE = "phone_live"
    PHONE_AUTO = "phone_auto"
    VOICE = "voice"
    VOICEMAIL = "voicemail"

    # Digital channels
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    PORTAL = "portal"

    # Physical channels
    LETTER = "letter"
    MAIL = "mail"
    IN_PERSON = "in_person"


class ContactResult(Enum):
    """Result of a contact attempt"""
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    BUSY = "busy"
    DISCONNECTED = "disconnected"
    WRONG_NUMBER = "wrong_number"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"


# =============================================================================
# ACCOUNT/DEBT STATUS ENUMS
# =============================================================================

class DebtStatus(Enum):
    """
    Status of debt account in the system.

    From: quan/orchestration/pipeline.py
    """
    PENDING = "pending"
    ACTIVE = "active"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    PAYMENT_PLAN = "payment_plan"
    SETTLING = "settling"
    COLLECTED = "collected"
    DISPUTED = "disputed"
    UNCOLLECTIBLE = "uncollectible"
    CLOSED = "closed"
    RESTORED = "restored"


class AccountStatus(Enum):
    """
    Account status in the collection lifecycle.

    Consolidated from:
    - quan/pipeline.py
    - quan/orchestration/master_orchestrator.py
    """
    # Initial states
    NEW = "new"
    SCORED = "scored"
    LOCATED = "located"

    # Active states
    ACTIVE = "active"
    IN_CONTACT = "in_contact"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"

    # Payment states
    PAYMENT_PENDING = "payment_pending"
    PAYING = "paying"
    PARTIAL = "partial"

    # Terminal states - Success
    PAID_IN_FULL = "paid_in_full"
    SETTLED = "settled"
    COLLECTED = "collected"

    # Terminal states - Failure/Hold
    UNCOLLECTABLE = "uncollectable"
    WRITTEN_OFF = "written_off"
    DISPUTE = "dispute"
    PAUSED = "paused"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Metro2AccountStatus(Enum):
    """
    Metro 2 Account Status Codes (Field 17) for credit bureau reporting.

    From: quan/reporting/metro2_bridge.py
    Note: These are industry-standard codes, not internal statuses.
    """
    CURRENT = "11"
    LATE_30 = "71"
    LATE_60 = "78"
    LATE_90 = "80"
    LATE_120 = "82"
    LATE_150 = "83"
    LATE_180 = "84"
    COLLECTION = "93"
    CHARGED_OFF = "97"
    PAID_COLLECTION = "62"
    SETTLED = "65"
    PAID_FULL = "13"
    PAID_CHARGE_OFF = "64"
    DISPUTED = "DA"


# =============================================================================
# ACTION/WORKFLOW ENUMS
# =============================================================================

class ActionType(Enum):
    """
    Types of collection actions.

    Consolidated from:
    - quan/compliance/risk_mitigation.py
    - quan/orchestration/master_orchestrator.py
    """
    # Contact actions
    CONTACT_SMS = "contact_sms"
    CONTACT_EMAIL = "contact_email"
    CONTACT_PUSH = "contact_push"
    CONTACT_VOICE = "contact_voice"
    CONTACT_MAIL = "contact_mail"
    PHONE_CALL = "phone_call"
    VOICEMAIL = "voicemail"

    # Negotiation actions
    NEGOTIATE_FULL = "negotiate_full"
    NEGOTIATE_SETTLEMENT = "negotiate_settlement"
    NEGOTIATE_PLAN = "negotiate_plan"
    SETTLEMENT_OFFER = "settlement_offer"
    PAYMENT_REQUEST = "payment_request"

    # Lifecycle actions
    ESCALATE = "escalate"
    PAUSE = "pause"
    RE_ENGAGE = "re_engage"
    WRITE_OFF = "write_off"
    CLOSE = "close"
    LEGAL_ACTION = "legal_action"


class Priority(Enum):
    """Priority levels for accounts and actions"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class PipelineStage(Enum):
    """Stages in the collection pipeline"""
    INGESTION = "ingestion"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    SEGMENTATION = "segmentation"
    STRATEGY = "strategy"
    CONTACT = "contact"
    NEGOTIATION = "negotiation"
    PAYMENT = "payment"
    SETTLEMENT = "settlement"
    RESOLUTION = "resolution"


class EventType(Enum):
    """Types of events in the system"""
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    CONTACT_ATTEMPTED = "contact_attempted"
    CONTACT_SUCCESSFUL = "contact_successful"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    SETTLEMENT_OFFERED = "settlement_offered"
    SETTLEMENT_ACCEPTED = "settlement_accepted"
    DISPUTE_RAISED = "dispute_raised"
    COMPLIANCE_VIOLATION = "compliance_violation"


# =============================================================================
# COMPLIANCE ENUMS
# =============================================================================

class ComplianceStatus(Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    EXEMPTED = "exempted"
    BLOCKED = "blocked"


class ViolationType(Enum):
    """Types of compliance violations"""
    FDCPA = "fdcpa"
    TCPA = "tcpa"
    REG_F = "reg_f"
    STATE_LAW = "state_law"
    SCRA = "scra"
    CONTACT_FREQUENCY = "contact_frequency"
    CONTACT_TIME = "contact_time"
    CONSENT = "consent"


# =============================================================================
# RISK ENUMS
# =============================================================================

class RiskLevel(Enum):
    """Risk level classifications"""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Categories of risk assessment"""
    CREDIT = "credit"
    FRAUD = "fraud"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    COUNTERPARTY = "counterparty"
    LIQUIDITY = "liquidity"
    MODEL = "model"


# =============================================================================
# TOKENIZATION ENUMS
# =============================================================================

class AssetClass(Enum):
    """Asset classes for tokenization"""
    CONSUMER_DEBT = "consumer_debt"
    MEDICAL_DEBT = "medical_debt"
    STUDENT_DEBT = "student_debt"
    AUTO_DEBT = "auto_debt"
    BNPL = "bnpl"
    UTILITY = "utility"
    TELECOM = "telecom"


class TrancheType(Enum):
    """Tranche types for securitization"""
    SENIOR = "senior"
    MEZZANINE = "mezzanine"
    JUNIOR = "junior"
    EQUITY = "equity"


class RiskRating(Enum):
    """Risk ratings for tokenized assets"""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    DEFAULT = "D"


# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================

# For modules that import specific enum values directly
__all__ = [
    # Payment
    "PaymentStatus",
    "PaymentMethod",
    "FailureReason",
    "TransactionType",
    # Contact
    "ContactChannel",
    "ContactResult",
    # Account/Debt
    "DebtStatus",
    "AccountStatus",
    "Metro2AccountStatus",
    # Action/Workflow
    "ActionType",
    "Priority",
    "PipelineStage",
    "EventType",
    # Compliance
    "ComplianceStatus",
    "ViolationType",
    # Risk
    "RiskLevel",
    "RiskCategory",
    # Tokenization
    "AssetClass",
    "TrancheType",
    "RiskRating",
]
