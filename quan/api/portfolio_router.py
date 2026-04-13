"""Portfolio ingestion endpoints."""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quan.database import get_db
from quan.models.database import Account, Portfolio
from quan.intelligence import CollectionIntelligence

router = APIRouter(prefix="/api/v1/portfolios", tags=["Portfolios"])

REQUIRED_COLUMNS = {
    "account_id",
    "debtor_name",
    "balance",
    "original_creditor",
    "debt_type",
    "days_past_due",
    "state",
    "phone",
    "email",
}
SUPPORTED_DEBT_TYPES = {
    "bnpl",
    "medical",
    "telecom",
    "subscription",
    "utility",
    "credit_card",
    "bank",
    "personal_loan",
    "auto",
    "rent",
}
PHONE_REGEX = re.compile(r"^\+?1?\d{10,15}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}


class RowError(BaseModel):
    row_number: int
    account_id: str | None = None
    errors: list[str]


class UploadedAccountSummary(BaseModel):
    account_id: str
    debtor_name: str
    debt_type: str
    balance: float
    recovery_probability: float
    optimal_channels: list[str]
    settlement_threshold: float


class PortfolioUploadResponse(BaseModel):
    portfolio_id: str
    portfolio_name: str
    filename: str
    received_rows: int
    imported_rows: int
    rejected_rows: int
    debt_mix: dict[str, int]
    row_errors: list[RowError]
    accounts: list[UploadedAccountSummary]


@dataclass
class ValidatedRow:
    account_id: str
    debtor_name: str
    balance: Decimal
    original_creditor: str
    debt_type: str
    days_past_due: int
    state: str
    phone: str | None
    email: str | None


@router.post("/upload", response_model=PortfolioUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_portfolio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PortfolioUploadResponse:
    """Upload a CSV portfolio, validate rows, store accounts, and score them."""

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    raw = file.file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV file is missing a header row.")

    headers = {header.strip() for header in reader.fieldnames}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(sorted(missing))}",
        )

    engine = CollectionIntelligence()
    row_errors: list[RowError] = []
    valid_rows: list[ValidatedRow] = []
    seen_ids: set[str] = set()

    for row_number, row in enumerate(reader, start=2):
        account_id = (row.get("account_id") or "").strip() or None
        errors = _validate_row(row, seen_ids, db)
        if errors:
            row_errors.append(RowError(row_number=row_number, account_id=account_id, errors=errors))
            continue

        seen_ids.add(account_id or "")
        valid_rows.append(
            ValidatedRow(
                account_id=account_id or "",
                debtor_name=row["debtor_name"].strip(),
                balance=Decimal(str(row["balance"]).strip()),
                original_creditor=row["original_creditor"].strip(),
                debt_type=row["debt_type"].strip().lower(),
                days_past_due=int(str(row["days_past_due"]).strip()),
                state=row["state"].strip().upper(),
                phone=_normalize_phone(row.get("phone")),
                email=_normalize_email(row.get("email")),
            )
        )

    portfolio = Portfolio(
        portfolio_id=str(uuid.uuid4()),
        name=_portfolio_name_from_filename(file.filename),
        source_filename=file.filename,
        debt_mix=dict(Counter(item.debt_type for item in valid_rows)),
        uploaded_count=len(valid_rows) + len(row_errors),
        valid_count=len(valid_rows),
        rejected_count=len(row_errors),
    )
    db.add(portfolio)
    db.flush()

    imported_accounts: list[UploadedAccountSummary] = []
    for row in valid_rows:
        strategy = engine.generate_strategy(_scoring_payload(row))
        account = Account(
            account_id=row.account_id,
            portfolio_id=portfolio.id,
            debtor_name=row.debtor_name,
            balance=row.balance,
            original_balance=row.balance,
            original_creditor=row.original_creditor,
            debt_type=row.debt_type,
            days_past_due=row.days_past_due,
            state=row.state,
            phone=row.phone,
            email=row.email,
            status="scored",
            recovery_probability=strategy.recovery_probability,
            optimal_channels=strategy.optimal_channels,
            settlement_threshold=strategy.settlement_threshold,
        )
        db.add(account)
        imported_accounts.append(
            UploadedAccountSummary(
                account_id=row.account_id,
                debtor_name=row.debtor_name,
                debt_type=row.debt_type,
                balance=float(row.balance),
                recovery_probability=strategy.recovery_probability,
                optimal_channels=strategy.optimal_channels,
                settlement_threshold=strategy.settlement_threshold,
            )
        )

    db.commit()

    return PortfolioUploadResponse(
        portfolio_id=portfolio.portfolio_id,
        portfolio_name=portfolio.name,
        filename=file.filename,
        received_rows=len(valid_rows) + len(row_errors),
        imported_rows=len(valid_rows),
        rejected_rows=len(row_errors),
        debt_mix=portfolio.debt_mix,
        row_errors=row_errors,
        accounts=imported_accounts[:25],
    )


def _validate_row(row: dict[str, Any], seen_ids: set[str], db: Session) -> list[str]:
    errors: list[str] = []

    account_id = (row.get("account_id") or "").strip()
    if not account_id:
        errors.append("account_id is required")
    elif account_id in seen_ids:
        errors.append("Duplicate account_id in upload")
    elif db.query(Account).filter(Account.account_id == account_id).first():
        errors.append("account_id already exists")

    debtor_name = (row.get("debtor_name") or "").strip()
    if len(debtor_name) < 2:
        errors.append("debtor_name must be at least 2 characters")

    try:
        balance = Decimal(str((row.get("balance") or "").strip()))
        if balance <= 0:
            errors.append("balance must be greater than 0")
    except Exception:
        errors.append("balance must be a valid decimal number")

    if not (row.get("original_creditor") or "").strip():
        errors.append("original_creditor is required")

    debt_type = (row.get("debt_type") or "").strip().lower()
    if debt_type not in SUPPORTED_DEBT_TYPES:
        errors.append(f"debt_type must be one of: {', '.join(sorted(SUPPORTED_DEBT_TYPES))}")

    try:
        days_past_due = int(str((row.get("days_past_due") or "").strip()))
        if days_past_due < 0:
            errors.append("days_past_due must be 0 or greater")
    except Exception:
        errors.append("days_past_due must be an integer")

    state = (row.get("state") or "").strip().upper()
    if state not in STATES:
        errors.append("state must be a valid US state or DC abbreviation")

    phone = _normalize_phone(row.get("phone"))
    if row.get("phone") and phone is None:
        errors.append("phone must be a valid US-format number")

    email = _normalize_email(row.get("email"))
    if row.get("email") and email is None:
        errors.append("email must be a valid email address")

    return errors


def _normalize_phone(phone: Any) -> str | None:
    value = str(phone or "").strip()
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        digits = f"1{digits}"
    normalized = f"+{digits}"
    if not PHONE_REGEX.match(normalized):
        return None
    return normalized


def _normalize_email(email: Any) -> str | None:
    value = str(email or "").strip().lower()
    if not value:
        return None
    return value if EMAIL_REGEX.match(value) else None


def _portfolio_name_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return cleaned.title() or "Uploaded Portfolio"


def _scoring_payload(row: ValidatedRow) -> dict[str, Any]:
    return {
        "account_id": row.account_id,
        "balance": float(row.balance),
        "original_balance": float(row.balance),
        "original_creditor": row.original_creditor,
        "debtor_name": row.debtor_name,
        "debt_type": row.debt_type,
        "days_overdue": row.days_past_due,
        "days_past_due": row.days_past_due,
        "has_mobile": bool(row.phone),
        "email_valid": bool(row.email),
        "payment_willingness": _payment_willingness(row.days_past_due, row.debt_type),
        "age": _age_hint(row.debt_type),
    }


def _payment_willingness(days_past_due: int, debt_type: str) -> float:
    base = {
        "bnpl": 0.58,
        "medical": 0.33,
        "telecom": 0.48,
        "subscription": 0.62,
        "utility": 0.45,
        "credit_card": 0.37,
        "bank": 0.34,
        "personal_loan": 0.29,
        "auto": 0.31,
        "rent": 0.41,
    }.get(debt_type, 0.4)
    penalty = min(days_past_due / 365, 0.35)
    return max(0.05, min(0.95, base - penalty))


def _age_hint(debt_type: str) -> int:
    return {
        "subscription": 29,
        "bnpl": 31,
        "telecom": 37,
        "utility": 42,
        "medical": 47,
    }.get(debt_type, 39)
