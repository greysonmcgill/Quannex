"""
SQLAlchemy ORM for the Quannex collections OS core domain.

Canonical pilot-focused schema — aligns with the Layer 1 Alembic migration
(``20260412_0001_layer1_backend_tables``), the FastAPI routers under
``quan.api``, the ``quan.analytics.live_dashboard`` aggregator, the Next.js
dashboard type contracts, and the seed script.

Core entities:

- :class:`Portfolio`       a single creditor/servicer upload
- :class:`Account`         one debtor obligation
- :class:`Campaign`        optional grouping for reporting
- :class:`ContactAttempt`  one outreach instance
- :class:`Payment`         one monetary transaction
- :class:`ComplianceEvent` one audit-relevant fact

Naming rules (applied everywhere — ORM, schemas, API, dashboard):

- Internal primary keys are ``id`` (integer, autoincrement).
- External business IDs are ``<entity>_id`` (string / UUID), always unique.
- Money columns use ``Numeric(12, 2)``; amounts carried as ``Decimal``.
- Timestamps use ``DateTime(timezone=True)`` and follow the ``*_at`` suffix.
- Foreign keys from child rows to the Account PK are ``account_db_id``,
  distinguishing them from the external, creditor-facing ``Account.account_id``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Enumerations (string-valued, stable on the wire)
# ---------------------------------------------------------------------------


class AccountStatus(str, PyEnum):
    """Pipeline stages an account can hold in the collections workflow."""

    INGESTED = "ingested"
    ENRICHED = "enriched"
    SCORED = "scored"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    PAYMENT_PENDING = "payment_pending"
    RESOLVED = "resolved"


class DebtType(str, PyEnum):
    """Supported small-balance debt categories for pilot operators."""

    BNPL = "bnpl"
    MEDICAL = "medical"
    TELECOM = "telecom"
    SUBSCRIPTION = "subscription"
    UTILITY = "utility"
    CREDIT_CARD = "credit_card"
    BANK = "bank"
    PERSONAL_LOAN = "personal_loan"
    AUTO = "auto"
    RENT = "rent"
    OTHER = "other"


class ContactChannel(str, PyEnum):
    """Outbound contact channels we log."""

    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    DIGITAL = "digital"
    MAIL = "mail"


class PaymentMethod(str, PyEnum):
    """Payment instruments the platform records."""

    CARD = "card"
    ACH = "ach"
    CASH = "cash"
    CHECK = "check"
    DIGITAL_WALLET = "digital_wallet"
    OTHER = "other"


class PaymentStatus(str, PyEnum):
    """Payment lifecycle states."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Core tables
# ---------------------------------------------------------------------------


class Portfolio(Base):
    """A single creditor/servicer portfolio upload."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    debt_mix: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    uploaded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    accounts: Mapped[List["Account"]] = relationship(
        "Account", back_populates="portfolio", cascade="save-update"
    )
    campaigns: Mapped[List["Campaign"]] = relationship(
        "Campaign", back_populates="portfolio", cascade="save-update"
    )

    __table_args__ = (Index("ix_portfolios_portfolio_id", "portfolio_id", unique=True),)


class Account(Base):
    """One debtor obligation — the central working object."""

    __tablename__ = "accounts"

    # Identity
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    portfolio_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("portfolios.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Debtor / contactability
    debtor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)

    # Debt details
    original_creditor: Mapped[str] = mapped_column(String(255), nullable=False)
    debt_type: Mapped[str] = mapped_column(String(64), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    days_past_due: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Workflow state
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AccountStatus.SCORED.value
    )

    # Intelligence-assigned scoring attributes (populated at ingest)
    recovery_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    optimal_channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    settlement_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Operational rollups
    total_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total_contact_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Compliance flags (block or restrict contact)
    do_not_call: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    do_not_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    do_not_mail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bankruptcy_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deceased_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disputed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attorney_represented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    statute_of_limitations_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    portfolio: Mapped[Optional["Portfolio"]] = relationship(
        "Portfolio", back_populates="accounts"
    )
    contact_attempts: Mapped[List["ContactAttempt"]] = relationship(
        "ContactAttempt",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(ContactAttempt.attempted_at)",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(Payment.recorded_at)",
    )
    compliance_events: Mapped[List["ComplianceEvent"]] = relationship(
        "ComplianceEvent",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(ComplianceEvent.occurred_at)",
    )

    __table_args__ = (
        Index("ix_accounts_account_id", "account_id", unique=True),
        Index("ix_accounts_debt_type", "debt_type"),
        Index("ix_accounts_days_past_due", "days_past_due"),
        Index("ix_accounts_state", "state"),
        Index("ix_accounts_status", "status"),
        Index(
            "ix_accounts_status_debt_type_state",
            "status",
            "debt_type",
            "state",
        ),
    )


class Campaign(Base):
    """Optional grouping of accounts for reporting and workflow batching."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    portfolio_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("portfolios.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="intake")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    portfolio: Mapped[Optional["Portfolio"]] = relationship(
        "Portfolio", back_populates="campaigns"
    )

    __table_args__ = (Index("ix_campaigns_campaign_id", "campaign_id", unique=True),)


class ContactAttempt(Base):
    """A single outreach instance against an account."""

    __tablename__ = "contact_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    account_db_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    account: Mapped["Account"] = relationship("Account", back_populates="contact_attempts")

    __table_args__ = (
        Index("ix_contact_attempts_attempt_id", "attempt_id", unique=True),
        Index("ix_contact_attempts_account_db_id", "account_db_id"),
        Index("ix_contact_attempts_channel", "channel"),
    )


class Payment(Base):
    """A monetary transaction recorded against an account."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    account_db_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PaymentStatus.COMPLETED.value
    )
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    account: Mapped["Account"] = relationship("Account", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_payment_id", "payment_id", unique=True),
        Index("ix_payments_account_db_id", "account_db_id"),
    )


class ComplianceEvent(Base):
    """An audit-relevant fact. Used to evidence FDCPA / TCPA / state compliance."""

    __tablename__ = "compliance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    account_db_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    account: Mapped[Optional["Account"]] = relationship(
        "Account", back_populates="compliance_events"
    )

    __table_args__ = (
        Index("ix_compliance_events_event_id", "event_id", unique=True),
        Index("ix_compliance_events_account_db_id", "account_db_id"),
        Index("ix_compliance_events_event_type", "event_type"),
        Index("ix_compliance_events_severity", "severity"),
        Index("ix_compliance_events_state", "state"),
    )


__all__ = [
    "Base",
    "AccountStatus",
    "DebtType",
    "ContactChannel",
    "PaymentMethod",
    "PaymentStatus",
    "Portfolio",
    "Account",
    "Campaign",
    "ContactAttempt",
    "Payment",
    "ComplianceEvent",
]
