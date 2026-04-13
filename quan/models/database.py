"""
SQLAlchemy Database Models for QUAN Recovery Platform

Core entities for debt collection operations:
- Account: Individual debt accounts
- Portfolio: Batches of accounts from creditors
- Campaign: Collection campaigns
- Payment: Payment records
- ContactAttempt: Contact history
- ComplianceEvent: Compliance audit trail
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Numeric,
    Index,
    Enum,
    JSON,
    event,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class AccountStatus(str, PyEnum):
    """Account pipeline stages"""
    NEW = "new"
    INGESTED = "ingested"
    ENRICHED = "enriched"
    SCORED = "scored"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_PLAN = "payment_plan"
    SETTLED = "settled"
    PAID_IN_FULL = "paid_in_full"
    DISPUTED = "disputed"
    UNCOLLECTABLE = "uncollectable"
    CLOSED = "closed"


class DebtType(str, PyEnum):
    """Types of debt"""
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
    OTHER = "other"


class ContactChannel(str, PyEnum):
    """Communication channels"""
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    MAIL = "mail"
    DIGITAL = "digital"
    PUSH = "push"


class ContactOutcome(str, PyEnum):
    """Contact attempt outcomes"""
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    CONNECTED = "connected"
    LEFT_MESSAGE = "left_message"
    NO_ANSWER = "no_answer"
    WRONG_NUMBER = "wrong_number"
    BOUNCED = "bounced"
    BLOCKED = "blocked"
    UNSUBSCRIBED = "unsubscribed"


class PaymentMethod(str, PyEnum):
    """Payment methods"""
    CARD = "card"
    ACH = "ach"
    CHECK = "check"
    MONEY_ORDER = "money_order"
    WIRE = "wire"
    EXTERNAL = "external"


class PaymentStatus(str, PyEnum):
    """Payment statuses"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
    REFUNDED = "refunded"


class ComplianceEventType(str, PyEnum):
    """Types of compliance events"""
    CONTACT_ATTEMPT = "contact_attempt"
    CONSENT_OBTAINED = "consent_obtained"
    CONSENT_REVOKED = "consent_revoked"
    DISPUTE_RECEIVED = "dispute_received"
    DISPUTE_RESOLVED = "dispute_resolved"
    VALIDATION_SENT = "validation_sent"
    CEASE_DESIST = "cease_desist"
    BANKRUPTCY_NOTICE = "bankruptcy_notice"
    DECEASED_NOTICE = "deceased_notice"
    ATTORNEY_NOTICE = "attorney_notice"
    TCPA_VIOLATION = "tcpa_violation"
    FDCPA_VIOLATION = "fdcpa_violation"
    STATE_VIOLATION = "state_violation"


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class Portfolio(Base):
    """
    A batch of accounts uploaded by a creditor/client.
    Represents a single upload or purchase of debt portfolio.
    """
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Portfolio metrics (calculated)
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    total_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0)

    # Upload info
    source_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    upload_status: Mapped[str] = mapped_column(String(50), default="pending")
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="portfolio")
    campaigns: Mapped[List["Campaign"]] = relationship("Campaign", back_populates="portfolio")

    __table_args__ = (
        Index("ix_portfolios_client_id", "client_id"),
        Index("ix_portfolios_created_at", "created_at"),
    )


class Account(Base):
    """
    Individual debt account representing a single debtor obligation.
    Core entity for all collection operations.
    """
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    external_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("portfolios.id"), nullable=True)

    # Debtor information
    debtor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    debtor_first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    debtor_last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Contact information
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    phone_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # mobile, landline, voip
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Debt details
    original_creditor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_creditor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    debt_type: Mapped[str] = mapped_column(String(50), default=DebtType.OTHER.value)
    original_balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    current_balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    interest_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Aging
    account_open_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    charge_off_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    days_past_due: Mapped[int] = mapped_column(Integer, default=0)

    # Status and workflow
    status: Mapped[str] = mapped_column(String(50), default=AccountStatus.NEW.value)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Intelligence scores (from quan/intelligence)
    recovery_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    settlement_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    optimal_channels: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Behavioral attributes
    payment_willingness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    has_mobile: Mapped[bool] = mapped_column(Boolean, default=False)
    employed: Mapped[bool] = mapped_column(Boolean, default=True)
    income_bracket: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Compliance flags
    do_not_call: Mapped[bool] = mapped_column(Boolean, default=False)
    do_not_email: Mapped[bool] = mapped_column(Boolean, default=False)
    do_not_mail: Mapped[bool] = mapped_column(Boolean, default=False)
    bankruptcy_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    deceased_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    attorney_represented: Mapped[bool] = mapped_column(Boolean, default=False)
    statute_of_limitations_expired: Mapped[bool] = mapped_column(Boolean, default=False)

    # Collection metrics
    total_payments: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    contact_attempts_count: Mapped[int] = mapped_column("contact_attempts", Integer, default=0)
    successful_contacts: Mapped[int] = mapped_column(Integer, default=0)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_contact_channel: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Settlement
    settlement_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    settlement_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Extra data
    extra_metadata: Mapped[Optional[str]] = mapped_column("metadata", JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    portfolio: Mapped[Optional["Portfolio"]] = relationship("Portfolio", back_populates="accounts")
    contact_history: Mapped[List["ContactAttempt"]] = relationship("ContactAttempt", back_populates="account", order_by="desc(ContactAttempt.created_at)")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="account", order_by="desc(Payment.created_at)")
    compliance_events: Mapped[List["ComplianceEvent"]] = relationship("ComplianceEvent", back_populates="account", order_by="desc(ComplianceEvent.created_at)")

    __table_args__ = (
        Index("ix_accounts_status", "status"),
        Index("ix_accounts_debt_type", "debt_type"),
        Index("ix_accounts_state", "state"),
        Index("ix_accounts_portfolio_id", "portfolio_id"),
        Index("ix_accounts_created_at", "created_at"),
        Index("ix_accounts_external_id", "external_account_id"),
        Index("ix_accounts_recovery_probability", "recovery_probability"),
        Index("ix_accounts_current_balance", "current_balance"),
    )


class Campaign(Base):
    """
    Collection campaign targeting a set of accounts.
    Tracks campaign performance and execution.
    """
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    portfolio_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("portfolios.id"), nullable=True)

    # Campaign configuration
    strategy_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    channels: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # List of channels

    # Status
    status: Mapped[str] = mapped_column(String(50), default="created")  # created, running, paused, completed
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metrics
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    accounts_contacted: Mapped[int] = mapped_column(Integer, default=0)
    accounts_responded: Mapped[int] = mapped_column(Integer, default=0)
    accounts_converted: Mapped[int] = mapped_column(Integer, default=0)
    total_collected: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    portfolio: Mapped[Optional["Portfolio"]] = relationship("Portfolio", back_populates="campaigns")

    __table_args__ = (
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_portfolio_id", "portfolio_id"),
    )


class ContactAttempt(Base):
    """
    Record of each contact attempt with a debtor.
    Essential for compliance tracking.
    """
    __tablename__ = "contact_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    campaign_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("campaigns.id"), nullable=True)

    # Contact details
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="outbound")  # outbound, inbound
    contact_target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # phone/email used

    # Outcome
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # for calls

    # Content
    message_template: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Agent info (for calls)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Response tracking
    response_received: Mapped[bool] = mapped_column(Boolean, default=False)
    response_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Cost tracking
    cost: Mapped[float] = mapped_column(Numeric(8, 4), default=0)

    # Compliance
    consent_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    within_contact_hours: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="contact_history")

    __table_args__ = (
        Index("ix_contact_attempts_account_id", "account_id"),
        Index("ix_contact_attempts_channel", "channel"),
        Index("ix_contact_attempts_created_at", "created_at"),
        Index("ix_contact_attempts_outcome", "outcome"),
    )


class Payment(Base):
    """
    Payment record for an account.
    Tracks all monetary transactions.
    """
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)

    # Payment details
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=PaymentStatus.PENDING.value)

    # Payment type
    is_settlement: Mapped[bool] = mapped_column(Boolean, default=False)
    is_payment_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_plan_installment: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # External references
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processor_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Processing details
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Fees and net
    processing_fee: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_account_id", "account_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
    )


class ComplianceEvent(Base):
    """
    Compliance event for audit trail.
    Tracks all compliance-relevant actions.
    """
    __tablename__ = "compliance_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info, warning, critical

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Regulation reference
    regulation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # fdcpa, tcpa, reg_f, etc.
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    # Evidence
    evidence: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)

    # Actor
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # system, agent_id, etc.

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    account: Mapped[Optional["Account"]] = relationship("Account", back_populates="compliance_events")

    __table_args__ = (
        Index("ix_compliance_events_account_id", "account_id"),
        Index("ix_compliance_events_event_type", "event_type"),
        Index("ix_compliance_events_severity", "severity"),
        Index("ix_compliance_events_created_at", "created_at"),
    )


# Event listeners for updating aggregates
@event.listens_for(Account, "after_insert")
def update_portfolio_on_account_insert(mapper, connection, target):
    """Update portfolio totals when account is inserted"""
    if target.portfolio_id:
        connection.execute(
            Portfolio.__table__.update()
            .where(Portfolio.id == target.portfolio_id)
            .values(
                total_accounts=Portfolio.total_accounts + 1,
                total_balance=Portfolio.total_balance + float(target.current_balance or 0)
            )
        )


@event.listens_for(Payment, "after_update")
def update_account_on_payment(mapper, connection, target):
    """Update account totals when payment status changes"""
    if target.status == PaymentStatus.COMPLETED.value:
        # Update total_payments on account
        connection.execute(
            Account.__table__.update()
            .where(Account.id == target.account_id)
            .values(
                total_payments=Account.total_payments + float(target.amount),
                current_balance=Account.current_balance - float(target.amount)
            )
        )
