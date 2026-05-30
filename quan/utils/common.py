"""Shared utilities for the Quannex backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from quan.models.database import Account


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso(value: datetime | timedelta | None) -> str | None:
    """Convert a datetime or timedelta to ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return (utc_now() + value).isoformat()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return to_iso(utc_now())  # type: ignore


def get_account_or_404(db: Session, account_id: str) -> Account:
    """Fetch an account by its external account_id or raise 404."""
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def safe_ratio(numerator: Decimal | float | int, denominator: Decimal | float | int) -> float:
    """Return numerator/denominator, or 0.0 if denominator is zero."""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def compute_delta(
    current: float | Decimal,
    previous: float | Decimal,
    invert_direction: bool = False,
) -> dict[str, Any]:
    """Compute a change delta with direction indicator."""
    current_value = float(current)
    previous_value = float(previous)
    if previous_value == 0:
        if current_value == 0:
            return {"value": 0.0, "direction": "stable"}
        direction = "down" if invert_direction else "up"
        return {"value": 1.0, "direction": direction}

    change = (current_value - previous_value) / abs(previous_value)
    if invert_direction:
        direction = "down" if change < 0 else "up" if change > 0 else "stable"
    else:
        direction = "up" if change > 0 else "down" if change < 0 else "stable"
    return {"value": abs(change), "direction": direction}


CONTACT_COSTS: dict[str, Decimal] = {
    "sms": Decimal("0.02"),
    "email": Decimal("0.01"),
    "voice": Decimal("0.15"),
    "digital": Decimal("0.03"),
    "mail": Decimal("0.55"),
}

PIPELINE_STAGES = (
    "ingested",
    "enriched",
    "scored",
    "contacted",
    "negotiating",
    "payment_pending",
    "resolved",
)
