"""
Account Management API Router

Provides CRUD operations for accounts, including:
- List accounts with filtering and pagination
- Get account details with contact history
- Update account status
- Log contact attempts
- Record payments
"""

from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from quan.database import get_db
from quan.models.database import (
    Account,
    AccountStatus,
    DebtType,
    ContactAttempt,
    ContactChannel,
    ContactOutcome,
    Payment,
    PaymentStatus,
    PaymentMethod,
    ComplianceEvent,
)


router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


# Request/Response Models
class AccountListItem(BaseModel):
    """Account summary for list view"""
    id: str
    external_account_id: Optional[str]
    debtor_name: str
    current_balance: float
    original_balance: float
    debt_type: str
    status: str
    state: Optional[str]
    days_past_due: int
    recovery_probability: Optional[float]
    contact_attempts: int
    last_contact_date: Optional[str]
    created_at: str


class AccountListResponse(BaseModel):
    """Paginated list of accounts"""
    accounts: List[AccountListItem]
    total: int
    page: int
    page_size: int
    total_balance: float


class ContactAttemptResponse(BaseModel):
    """Contact attempt details"""
    id: str
    channel: str
    direction: str
    outcome: str
    duration_seconds: Optional[int]
    response_received: bool
    cost: float
    created_at: str


class PaymentResponse(BaseModel):
    """Payment details"""
    id: str
    amount: float
    payment_method: str
    status: str
    is_settlement: bool
    is_payment_plan: bool
    processed_at: Optional[str]
    created_at: str


class ComplianceEventResponse(BaseModel):
    """Compliance event details"""
    id: str
    event_type: str
    severity: str
    description: str
    resolution: Optional[str]
    regulation: Optional[str]
    created_at: str


class AccountDetailResponse(BaseModel):
    """Full account details with history"""
    id: str
    external_account_id: Optional[str]
    portfolio_id: Optional[str]

    # Debtor info
    debtor_name: str
    debtor_first_name: Optional[str]
    debtor_last_name: Optional[str]

    # Contact info
    phone: Optional[str]
    phone_valid: bool
    email: Optional[str]
    email_valid: bool
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]

    # Debt details
    original_creditor: Optional[str]
    current_creditor: Optional[str]
    debt_type: str
    original_balance: float
    current_balance: float
    days_past_due: int

    # Status
    status: str
    status_changed_at: str

    # Intelligence
    recovery_probability: Optional[float]
    settlement_threshold: Optional[float]
    optimal_channels: Optional[List[str]]

    # Compliance flags
    do_not_call: bool
    do_not_email: bool
    bankruptcy_flag: bool
    disputed: bool

    # Metrics
    total_payments: float
    contact_attempts: int
    successful_contacts: int
    last_contact_date: Optional[str]

    # History
    contact_history: List[ContactAttemptResponse]
    payment_history: List[PaymentResponse]
    compliance_events: List[ComplianceEventResponse]

    # Timestamps
    created_at: str
    updated_at: str


class StatusUpdateRequest(BaseModel):
    """Request to update account status"""
    status: str
    notes: Optional[str] = None


class ContactAttemptRequest(BaseModel):
    """Request to log a contact attempt"""
    channel: str
    direction: str = "outbound"
    outcome: str
    contact_target: Optional[str] = None
    duration_seconds: Optional[int] = None
    message_content: Optional[str] = None
    response_content: Optional[str] = None
    cost: float = 0


class PaymentRequest(BaseModel):
    """Request to record a payment"""
    amount: float = Field(..., gt=0)
    payment_method: str
    is_settlement: bool = False
    is_payment_plan: bool = False
    payment_plan_installment: Optional[int] = None
    transaction_id: Optional[str] = None


# Endpoints
@router.get("", response_model=AccountListResponse)
async def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    debt_type: Optional[str] = Query(None, description="Filter by debt type"),
    state: Optional[str] = Query(None, description="Filter by state"),
    min_balance: Optional[float] = Query(None, description="Minimum balance"),
    max_balance: Optional[float] = Query(None, description="Maximum balance"),
    search: Optional[str] = Query(None, description="Search by name or account ID"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: AsyncSession = Depends(get_db),
):
    """
    List accounts with pagination and filtering.

    Filters:
    - status: Filter by pipeline status
    - debt_type: Filter by type of debt
    - state: Filter by US state
    - min_balance/max_balance: Filter by balance range
    - search: Search by debtor name or external account ID
    """

    # Build query
    query = select(Account)
    count_query = select(func.count(Account.id))
    balance_query = select(func.sum(Account.current_balance))

    # Apply filters
    filters = []

    if status:
        filters.append(Account.status == status)

    if debt_type:
        filters.append(Account.debt_type == debt_type)

    if state:
        filters.append(Account.state == state.upper())

    if min_balance is not None:
        filters.append(Account.current_balance >= min_balance)

    if max_balance is not None:
        filters.append(Account.current_balance <= max_balance)

    if search:
        search_filter = or_(
            Account.debtor_name.ilike(f"%{search}%"),
            Account.external_account_id.ilike(f"%{search}%"),
        )
        filters.append(search_filter)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
        balance_query = balance_query.where(and_(*filters))

    # Get total count and balance
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    balance_result = await db.execute(balance_query)
    total_balance = float(balance_result.scalar() or 0)

    # Apply sorting
    sort_column = getattr(Account, sort_by, Account.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    accounts = result.scalars().all()

    return AccountListResponse(
        accounts=[
            AccountListItem(
                id=a.id,
                external_account_id=a.external_account_id,
                debtor_name=a.debtor_name,
                current_balance=float(a.current_balance),
                original_balance=float(a.original_balance),
                debt_type=a.debt_type,
                status=a.status,
                state=a.state,
                days_past_due=a.days_past_due,
                recovery_probability=a.recovery_probability,
                contact_attempts=a.contact_attempts,
                last_contact_date=a.last_contact_date.isoformat() if a.last_contact_date else None,
                created_at=a.created_at.isoformat(),
            )
            for a in accounts
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_balance=total_balance,
    )


@router.get("/stats")
async def get_account_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate statistics for accounts"""

    # Total counts
    total_result = await db.execute(select(func.count(Account.id)))
    total_accounts = total_result.scalar() or 0

    # Total balance
    balance_result = await db.execute(select(func.sum(Account.current_balance)))
    total_balance = float(balance_result.scalar() or 0)

    # By status
    status_result = await db.execute(
        select(Account.status, func.count(Account.id))
        .group_by(Account.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # By debt type
    type_result = await db.execute(
        select(Account.debt_type, func.count(Account.id))
        .group_by(Account.debt_type)
    )
    by_debt_type = {row[0]: row[1] for row in type_result.all()}

    # By state (top 10)
    state_result = await db.execute(
        select(Account.state, func.count(Account.id))
        .where(Account.state.isnot(None))
        .group_by(Account.state)
        .order_by(func.count(Account.id).desc())
        .limit(10)
    )
    by_state = {row[0]: row[1] for row in state_result.all()}

    # Average metrics
    avg_result = await db.execute(
        select(
            func.avg(Account.current_balance),
            func.avg(Account.recovery_probability),
            func.avg(Account.days_past_due),
        )
    )
    avg_row = avg_result.one()

    return {
        "total_accounts": total_accounts,
        "total_balance": total_balance,
        "avg_balance": float(avg_row[0]) if avg_row[0] else 0,
        "avg_recovery_probability": float(avg_row[1]) if avg_row[1] else 0,
        "avg_days_past_due": int(avg_row[2]) if avg_row[2] else 0,
        "by_status": by_status,
        "by_debt_type": by_debt_type,
        "by_state": by_state,
    }


@router.get("/{account_id}", response_model=AccountDetailResponse)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full account details with contact and payment history"""

    result = await db.execute(
        select(Account)
        .options(
            selectinload(Account.contact_attempts),
            selectinload(Account.payments),
            selectinload(Account.compliance_events),
        )
        .where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return AccountDetailResponse(
        id=account.id,
        external_account_id=account.external_account_id,
        portfolio_id=account.portfolio_id,

        # Debtor info
        debtor_name=account.debtor_name,
        debtor_first_name=account.debtor_first_name,
        debtor_last_name=account.debtor_last_name,

        # Contact info
        phone=account.phone,
        phone_valid=account.phone_valid,
        email=account.email,
        email_valid=account.email_valid,
        address_line1=account.address_line1,
        address_line2=account.address_line2,
        city=account.city,
        state=account.state,
        zip_code=account.zip_code,

        # Debt details
        original_creditor=account.original_creditor,
        current_creditor=account.current_creditor,
        debt_type=account.debt_type,
        original_balance=float(account.original_balance),
        current_balance=float(account.current_balance),
        days_past_due=account.days_past_due,

        # Status
        status=account.status,
        status_changed_at=account.status_changed_at.isoformat(),

        # Intelligence
        recovery_probability=account.recovery_probability,
        settlement_threshold=account.settlement_threshold,
        optimal_channels=account.optimal_channels,

        # Compliance flags
        do_not_call=account.do_not_call,
        do_not_email=account.do_not_email,
        bankruptcy_flag=account.bankruptcy_flag,
        disputed=account.disputed,

        # Metrics
        total_payments=float(account.total_payments),
        contact_attempts=account.contact_attempts,
        successful_contacts=account.successful_contacts,
        last_contact_date=account.last_contact_date.isoformat() if account.last_contact_date else None,

        # History
        contact_history=[
            ContactAttemptResponse(
                id=c.id,
                channel=c.channel,
                direction=c.direction,
                outcome=c.outcome,
                duration_seconds=c.duration_seconds,
                response_received=c.response_received,
                cost=float(c.cost),
                created_at=c.created_at.isoformat(),
            )
            for c in (account.contact_attempts or [])[:20]
        ],
        payment_history=[
            PaymentResponse(
                id=p.id,
                amount=float(p.amount),
                payment_method=p.payment_method,
                status=p.status,
                is_settlement=p.is_settlement,
                is_payment_plan=p.is_payment_plan,
                processed_at=p.processed_at.isoformat() if p.processed_at else None,
                created_at=p.created_at.isoformat(),
            )
            for p in (account.payments or [])[:20]
        ],
        compliance_events=[
            ComplianceEventResponse(
                id=e.id,
                event_type=e.event_type,
                severity=e.severity,
                description=e.description,
                resolution=e.resolution,
                regulation=e.regulation,
                created_at=e.created_at.isoformat(),
            )
            for e in (account.compliance_events or [])[:20]
        ],

        # Timestamps
        created_at=account.created_at.isoformat(),
        updated_at=account.updated_at.isoformat(),
    )


@router.put("/{account_id}/status")
async def update_account_status(
    account_id: str,
    request: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update account status through pipeline stages"""

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Validate status
    valid_statuses = [s.value for s in AccountStatus]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    old_status = account.status
    account.status = request.status
    account.status_changed_at = datetime.now()

    # Log compliance event for status change
    event = ComplianceEvent(
        account_id=account.id,
        event_type="status_change",
        severity="info",
        description=f"Status changed from {old_status} to {request.status}",
        created_by="api",
    )
    db.add(event)

    await db.commit()

    return {
        "account_id": account_id,
        "old_status": old_status,
        "new_status": account.status,
        "updated_at": account.status_changed_at.isoformat(),
    }


@router.post("/{account_id}/contact")
async def log_contact_attempt(
    account_id: str,
    request: ContactAttemptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Log a contact attempt for an account"""

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Validate channel
    valid_channels = [c.value for c in ContactChannel]
    if request.channel not in valid_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel. Must be one of: {', '.join(valid_channels)}"
        )

    # Validate outcome
    valid_outcomes = [o.value for o in ContactOutcome]
    if request.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome. Must be one of: {', '.join(valid_outcomes)}"
        )

    # Create contact attempt
    contact = ContactAttempt(
        account_id=account_id,
        channel=request.channel,
        direction=request.direction,
        outcome=request.outcome,
        contact_target=request.contact_target,
        duration_seconds=request.duration_seconds,
        message_content=request.message_content,
        response_received=request.outcome in ['replied', 'connected'],
        response_content=request.response_content,
        cost=request.cost,
    )
    db.add(contact)

    # Update account stats
    account.contact_attempts += 1
    account.last_contact_date = datetime.now()
    account.last_contact_channel = request.channel

    if request.outcome in ['replied', 'connected']:
        account.successful_contacts += 1

    # If not contacted yet, update status
    if account.status in [AccountStatus.NEW.value, AccountStatus.INGESTED.value, AccountStatus.SCORED.value]:
        account.status = AccountStatus.CONTACTED.value
        account.status_changed_at = datetime.now()

    await db.commit()

    return {
        "contact_id": contact.id,
        "account_id": account_id,
        "channel": contact.channel,
        "outcome": contact.outcome,
        "created_at": contact.created_at.isoformat(),
    }


@router.post("/{account_id}/payment")
async def record_payment(
    account_id: str,
    request: PaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a payment for an account"""

    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Validate payment method
    valid_methods = [m.value for m in PaymentMethod]
    if request.payment_method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment method. Must be one of: {', '.join(valid_methods)}"
        )

    # Validate amount
    if request.amount > float(account.current_balance):
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({request.amount}) exceeds current balance ({float(account.current_balance)})"
        )

    # Create payment
    processing_fee = request.amount * 0.029  # ~3% fee
    payment = Payment(
        account_id=account_id,
        amount=request.amount,
        payment_method=request.payment_method,
        status=PaymentStatus.COMPLETED.value,
        is_settlement=request.is_settlement,
        is_payment_plan=request.is_payment_plan,
        payment_plan_installment=request.payment_plan_installment,
        transaction_id=request.transaction_id,
        processed_at=datetime.now(),
        processing_fee=processing_fee,
        net_amount=request.amount - processing_fee,
    )
    db.add(payment)

    # Update account
    account.total_payments = float(account.total_payments) + request.amount
    account.current_balance = float(account.current_balance) - request.amount

    # Update status based on payment
    if account.current_balance <= 0:
        if request.is_settlement:
            account.status = AccountStatus.SETTLED.value
            account.settlement_amount = request.amount
            account.settlement_accepted_at = datetime.now()
        else:
            account.status = AccountStatus.PAID_IN_FULL.value
    elif request.is_payment_plan:
        account.status = AccountStatus.PAYMENT_PLAN.value
    else:
        account.status = AccountStatus.PAYMENT_PENDING.value

    account.status_changed_at = datetime.now()

    await db.commit()

    return {
        "payment_id": payment.id,
        "account_id": account_id,
        "amount": payment.amount,
        "new_balance": float(account.current_balance),
        "status": account.status,
        "processed_at": payment.processed_at.isoformat(),
    }
