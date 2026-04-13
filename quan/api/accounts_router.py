"""Account management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from quan.database import get_db
from quan.models.database import Account, ComplianceEvent, ContactAttempt, Payment

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])

VALID_STATUSES = {
    "ingested",
    "enriched",
    "scored",
    "contacted",
    "negotiating",
    "payment_pending",
    "resolved",
}
CONTACT_COSTS = {
    "sms": Decimal("0.02"),
    "email": Decimal("0.01"),
    "voice": Decimal("0.15"),
    "digital": Decimal("0.03"),
    "mail": Decimal("0.55"),
}


class ContactAttemptCreate(BaseModel):
    channel: str = Field(..., pattern="^(sms|email|voice|digital|mail)$")
    outcome: str = Field(..., min_length=2, max_length=64)
    notes: str | None = None
    compliant: bool = True
    agent_name: str | None = None


class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"))
    method: str = Field(..., pattern="^(card|ach|cash|check|digital_wallet|other)$")
    status: str = Field(default="completed", pattern="^(pending|completed|failed)$")
    reference: str | None = None
    notes: str | None = None


class AccountStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ingested|enriched|scored|contacted|negotiating|payment_pending|resolved)$")
    notes: str | None = None


def _account_summary(account: Account) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "debtor_name": account.debtor_name,
        "balance": float(account.balance),
        "original_balance": float(account.original_balance),
        "original_creditor": account.original_creditor,
        "debt_type": account.debt_type,
        "days_past_due": account.days_past_due,
        "state": account.state,
        "phone": account.phone,
        "email": account.email,
        "status": account.status,
        "recovery_probability": account.recovery_probability,
        "optimal_channels": account.optimal_channels,
        "settlement_threshold": account.settlement_threshold,
        "total_paid": float(account.total_paid),
        "total_contact_attempts": account.total_contact_attempts,
        "last_contact_at": _iso(account.last_contact_at),
        "last_payment_at": _iso(account.last_payment_at),
        "created_at": _iso(account.created_at),
        "updated_at": _iso(account.updated_at),
    }


@router.get("")
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str | None = Query(None),
    debt_type: str | None = Query(None),
    state: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List accounts with pagination and filters."""

    query = db.query(Account)
    if status:
        query = query.filter(Account.status == status)
    if debt_type:
        query = query.filter(Account.debt_type == debt_type)
    if state:
        query = query.filter(Account.state == state.upper())
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Account.account_id.ilike(like),
                Account.debtor_name.ilike(like),
                Account.original_creditor.ilike(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(Account.updated_at.desc(), Account.account_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "items": [_account_summary(account) for account in items],
    }


@router.get("/{account_id}")
def get_account_detail(account_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get full account detail with related history."""

    account = (
        db.query(Account)
        .options(
            joinedload(Account.contact_attempts),
            joinedload(Account.payments),
            joinedload(Account.compliance_events),
        )
        .filter(Account.account_id == account_id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        **_account_summary(account),
        "contact_history": [
            {
                "attempt_id": attempt.attempt_id,
                "channel": attempt.channel,
                "outcome": attempt.outcome,
                "compliant": attempt.compliant,
                "cost": float(attempt.cost),
                "agent_name": attempt.agent_name,
                "notes": attempt.notes,
                "attempted_at": _iso(attempt.attempted_at),
            }
            for attempt in account.contact_attempts
        ],
        "payments": [
            {
                "payment_id": payment.payment_id,
                "amount": float(payment.amount),
                "method": payment.method,
                "status": payment.status,
                "reference": payment.reference,
                "notes": payment.notes,
                "recorded_at": _iso(payment.recorded_at),
            }
            for payment in account.payments
        ],
        "compliance_events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "severity": event.severity,
                "message": event.message,
                "resolution": event.resolution,
                "resolved": event.resolved,
                "occurred_at": _iso(event.occurred_at),
            }
            for event in account.compliance_events
        ],
    }


@router.put("/{account_id}/status")
def update_account_status(
    account_id: str,
    payload: AccountStatusUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update the current pipeline status for an account."""

    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.status = payload.status
    account.updated_at = _now()
    if payload.notes:
        db.add(
            ComplianceEvent(
                event_id=str(uuid.uuid4()),
                account_db_id=account.id,
                event_type="status_change",
                severity="info",
                message=f"Account status changed to {payload.status}",
                resolution=payload.notes,
                state=account.state,
                resolved=True,
            )
        )
    db.commit()
    db.refresh(account)
    return _account_summary(account)


@router.post("/{account_id}/contact", status_code=201)
def log_contact_attempt(
    account_id: str,
    payload: ContactAttemptCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Log a contact attempt and update account rollups."""

    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    cost = CONTACT_COSTS[payload.channel]
    attempt = ContactAttempt(
        attempt_id=str(uuid.uuid4()),
        account_db_id=account.id,
        channel=payload.channel,
        outcome=payload.outcome,
        compliant=payload.compliant,
        cost=cost,
        agent_name=payload.agent_name,
        notes=payload.notes,
    )
    db.add(attempt)

    account.total_contact_attempts += 1
    account.last_contact_at = _now()
    if account.status in {"scored", "enriched", "ingested"}:
        account.status = "contacted"

    if not payload.compliant:
        db.add(
            ComplianceEvent(
                event_id=str(uuid.uuid4()),
                account_db_id=account.id,
                event_type="contact_policy",
                severity="warning",
                message=f"Non-compliant {payload.channel} contact logged: {payload.outcome}",
                resolution="Review agent notes",
                state=account.state,
                resolved=False,
            )
        )

    db.commit()
    db.refresh(attempt)
    db.refresh(account)

    return {
        "attempt_id": attempt.attempt_id,
        "account_id": account.account_id,
        "status": account.status,
        "channel": attempt.channel,
        "outcome": attempt.outcome,
        "compliant": attempt.compliant,
        "cost": float(attempt.cost),
        "attempted_at": _iso(attempt.attempted_at),
    }


@router.post("/{account_id}/payment", status_code=201)
def record_payment(
    account_id: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record a payment against an account."""

    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    payment = Payment(
        payment_id=str(uuid.uuid4()),
        account_db_id=account.id,
        amount=payload.amount,
        method=payload.method,
        status=payload.status,
        reference=payload.reference,
        notes=payload.notes,
    )
    db.add(payment)

    if payload.status == "completed":
        account.total_paid = (account.total_paid or Decimal("0.00")) + payload.amount
        account.balance = max(Decimal("0.00"), account.balance - payload.amount)
        account.last_payment_at = _now()
        account.status = "resolved" if account.balance <= Decimal("0.00") else "payment_pending"
    elif payload.status == "pending":
        account.status = "payment_pending"

    db.commit()
    db.refresh(payment)
    db.refresh(account)

    return {
        "payment_id": payment.payment_id,
        "account_id": account.account_id,
        "amount": float(payment.amount),
        "method": payment.method,
        "status": payment.status,
        "balance": float(account.balance),
        "recorded_at": _iso(payment.recorded_at),
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
