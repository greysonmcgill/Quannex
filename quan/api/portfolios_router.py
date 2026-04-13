"""
Portfolio Ingestion API Router

Handles CSV file uploads for portfolio ingestion.
Validates data, stores valid accounts, and auto-scores using intelligence engine.
"""

import csv
import io
import re
from datetime import datetime
from typing import List, Optional
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from quan.database import get_db
from quan.models.database import (
    Account,
    Portfolio,
    AccountStatus,
    DebtType,
)
from quan.intelligence import CollectionIntelligence


router = APIRouter(prefix="/api/v1/portfolios", tags=["Portfolios"])


# Request/Response Models
class AccountRow(BaseModel):
    """Validated account row from CSV"""
    account_id: str
    debtor_name: str
    balance: float
    original_creditor: Optional[str] = None
    debt_type: str = "other"
    days_past_due: int = 0
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    @field_validator('balance')
    @classmethod
    def balance_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('Balance must be non-negative')
        return v

    @field_validator('state')
    @classmethod
    def state_must_be_valid(cls, v):
        if v and len(v) != 2:
            raise ValueError('State must be 2-letter code')
        return v.upper() if v else None

    @field_validator('debt_type')
    @classmethod
    def debt_type_must_be_valid(cls, v):
        valid_types = [dt.value for dt in DebtType]
        if v.lower() not in valid_types:
            return "other"
        return v.lower()


class ValidationError(BaseModel):
    """Error details for a single row"""
    row: int
    field: str
    error: str
    value: Optional[str] = None


class UploadSummary(BaseModel):
    """Summary of upload results"""
    portfolio_id: str
    portfolio_name: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    total_balance: float
    accounts_by_status: dict
    accounts_by_debt_type: dict
    errors: List[ValidationError]


class PortfolioResponse(BaseModel):
    """Portfolio details response"""
    id: str
    name: str
    client_id: Optional[str]
    total_accounts: int
    total_balance: float
    upload_status: str
    valid_rows: int
    invalid_rows: int
    created_at: str


class PortfolioListResponse(BaseModel):
    """List of portfolios response"""
    portfolios: List[PortfolioResponse]
    total: int
    page: int
    page_size: int


# Helper functions
def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone format (accepts various formats)"""
    if not phone:
        return True
    # Remove common formatting
    cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
    # Should be 10-11 digits
    return bool(re.match(r'^\+?1?\d{10}$', cleaned))


def clean_phone(phone: str) -> Optional[str]:
    """Clean phone number to standard format"""
    if not phone:
        return None
    cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
    cleaned = re.sub(r'^\+?1', '', cleaned)
    if len(cleaned) == 10:
        return f"{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
    return None


def parse_csv_row(row: dict, row_num: int) -> tuple[Optional[AccountRow], List[ValidationError]]:
    """Parse and validate a CSV row"""
    errors = []

    # Required fields
    account_id = row.get('account_id', '').strip()
    if not account_id:
        errors.append(ValidationError(row=row_num, field='account_id', error='Missing required field'))

    debtor_name = row.get('debtor_name', '').strip()
    if not debtor_name:
        errors.append(ValidationError(row=row_num, field='debtor_name', error='Missing required field'))

    # Balance
    balance_str = row.get('balance', '0').strip()
    try:
        balance = float(balance_str.replace('$', '').replace(',', ''))
        if balance < 0:
            errors.append(ValidationError(row=row_num, field='balance', error='Must be non-negative', value=balance_str))
    except (ValueError, InvalidOperation):
        errors.append(ValidationError(row=row_num, field='balance', error='Invalid number format', value=balance_str))
        balance = 0

    # Days past due
    dpd_str = row.get('days_past_due', '0').strip()
    try:
        days_past_due = int(dpd_str) if dpd_str else 0
        if days_past_due < 0:
            days_past_due = 0
    except ValueError:
        errors.append(ValidationError(row=row_num, field='days_past_due', error='Invalid number', value=dpd_str))
        days_past_due = 0

    # State
    state = row.get('state', '').strip().upper()
    if state and len(state) != 2:
        errors.append(ValidationError(row=row_num, field='state', error='Must be 2-letter code', value=state))
        state = None

    # Phone
    phone = row.get('phone', '').strip()
    if phone and not validate_phone(phone):
        errors.append(ValidationError(row=row_num, field='phone', error='Invalid phone format', value=phone))
        phone = None
    else:
        phone = clean_phone(phone)

    # Email
    email = row.get('email', '').strip()
    if email and not validate_email(email):
        errors.append(ValidationError(row=row_num, field='email', error='Invalid email format', value=email))
        email = None

    # Debt type
    debt_type = row.get('debt_type', 'other').strip().lower()
    valid_debt_types = [dt.value for dt in DebtType]
    if debt_type not in valid_debt_types:
        debt_type = 'other'

    if errors and any(e.field in ['account_id', 'debtor_name'] for e in errors):
        return None, errors

    return AccountRow(
        account_id=account_id,
        debtor_name=debtor_name,
        balance=balance,
        original_creditor=row.get('original_creditor', '').strip() or None,
        debt_type=debt_type,
        days_past_due=days_past_due,
        state=state,
        phone=phone,
        email=email,
    ), errors


# Endpoints
@router.post("/upload", response_model=UploadSummary)
async def upload_portfolio(
    file: UploadFile = File(...),
    portfolio_name: Optional[str] = Query(None, description="Name for the portfolio"),
    client_id: Optional[str] = Query(None, description="Client ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a CSV file to create a new portfolio.

    Expected CSV columns:
    - account_id (required): Unique identifier
    - debtor_name (required): Full name of debtor
    - balance (required): Current balance owed
    - original_creditor: Original creditor name
    - debt_type: Type of debt (payday, bnpl, medical, etc.)
    - days_past_due: Days since last payment
    - state: 2-letter state code
    - phone: Phone number
    - email: Email address

    Returns summary of imported accounts and any validation errors.
    """

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Read file content
    try:
        content = await file.read()
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = content.decode('latin-1')
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to decode file. Please use UTF-8 encoding.")

    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Create portfolio
    name = portfolio_name or f"Import - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    portfolio = Portfolio(
        name=name,
        client_id=client_id,
        source_file=file.filename,
        upload_status="processing",
    )
    db.add(portfolio)
    await db.flush()

    # Initialize intelligence engine
    intelligence = CollectionIntelligence()

    # Process rows
    valid_accounts = []
    all_errors = []
    total_balance = 0

    for i, row in enumerate(rows, start=2):  # Start at 2 (1 = header)
        parsed, errors = parse_csv_row(row, i)
        all_errors.extend(errors)

        if parsed:
            # Create account
            account_dict = {
                'account_id': parsed.account_id,
                'balance': parsed.balance,
                'payment_willingness': 0.5,  # Default
                'has_mobile': parsed.phone is not None,
                'email_valid': parsed.email is not None,
                'employed': True,  # Default assumption
            }

            # Get AI scoring
            strategy = intelligence.generate_strategy(account_dict)

            # Determine initial status
            if parsed.days_past_due < 30:
                status = AccountStatus.NEW.value
            elif parsed.days_past_due < 60:
                status = AccountStatus.INGESTED.value
            else:
                status = AccountStatus.SCORED.value

            account = Account(
                external_account_id=parsed.account_id,
                portfolio_id=portfolio.id,
                debtor_name=parsed.debtor_name,
                original_creditor=parsed.original_creditor,
                current_creditor="QUAN Recovery",
                debt_type=parsed.debt_type,
                current_balance=parsed.balance,
                original_balance=parsed.balance,
                days_past_due=parsed.days_past_due,
                state=parsed.state,
                phone=parsed.phone,
                phone_valid=parsed.phone is not None,
                email=parsed.email,
                email_valid=parsed.email is not None,
                status=status,
                recovery_probability=strategy.recovery_probability,
                settlement_threshold=strategy.settlement_threshold,
                optimal_channels=strategy.optimal_channels,
                has_mobile=parsed.phone is not None,
            )
            valid_accounts.append(account)
            total_balance += parsed.balance

    # Save accounts
    if valid_accounts:
        db.add_all(valid_accounts)

    # Update portfolio
    portfolio.total_accounts = len(valid_accounts)
    portfolio.total_balance = total_balance
    portfolio.valid_rows = len(valid_accounts)
    portfolio.invalid_rows = len(rows) - len(valid_accounts)
    portfolio.upload_status = "completed" if valid_accounts else "failed"
    portfolio.error_details = [e.model_dump() for e in all_errors[:100]] if all_errors else None

    await db.commit()

    # Calculate summary stats
    status_counts = {}
    debt_type_counts = {}
    for acc in valid_accounts:
        status_counts[acc.status] = status_counts.get(acc.status, 0) + 1
        debt_type_counts[acc.debt_type] = debt_type_counts.get(acc.debt_type, 0) + 1

    return UploadSummary(
        portfolio_id=portfolio.id,
        portfolio_name=portfolio.name,
        total_rows=len(rows),
        valid_rows=len(valid_accounts),
        invalid_rows=len(rows) - len(valid_accounts),
        total_balance=total_balance,
        accounts_by_status=status_counts,
        accounts_by_debt_type=debt_type_counts,
        errors=all_errors[:50],  # Limit errors in response
    )


@router.get("", response_model=PortfolioListResponse)
async def list_portfolios(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all portfolios with pagination"""

    # Count total
    total_result = await db.execute(select(func.count(Portfolio.id)))
    total = total_result.scalar() or 0

    # Get portfolios
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Portfolio)
        .order_by(Portfolio.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    portfolios = result.scalars().all()

    return PortfolioListResponse(
        portfolios=[
            PortfolioResponse(
                id=p.id,
                name=p.name,
                client_id=p.client_id,
                total_accounts=p.total_accounts,
                total_balance=float(p.total_balance),
                upload_status=p.upload_status,
                valid_rows=p.valid_rows,
                invalid_rows=p.invalid_rows,
                created_at=p.created_at.isoformat(),
            )
            for p in portfolios
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio details by ID"""

    result = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        client_id=portfolio.client_id,
        total_accounts=portfolio.total_accounts,
        total_balance=float(portfolio.total_balance),
        upload_status=portfolio.upload_status,
        valid_rows=portfolio.valid_rows,
        invalid_rows=portfolio.invalid_rows,
        created_at=portfolio.created_at.isoformat(),
    )


@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a portfolio and all its accounts"""

    result = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    portfolio = result.scalar_one_or_none()

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    # Delete accounts first (cascade would work too)
    await db.execute(
        Account.__table__.delete().where(Account.portfolio_id == portfolio_id)
    )

    await db.delete(portfolio)
    await db.commit()

    return {"message": "Portfolio deleted", "portfolio_id": portfolio_id}
