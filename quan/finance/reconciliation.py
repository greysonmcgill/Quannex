"""
QUAN Financial Reconciliation Pipeline

Production-grade financial plumbing for debt collection operations:
- Payment reconciliation and matching
- Settlement accounting and write-offs
- Trust accounting (FDCPA-compliant)
- Creditor remittance and fee management
- Portfolio accounting and valuations
- Bank/processor reconciliation
- SOX-compliant audit trails
- Comprehensive reporting suite

Author: QUAN Recovery Platform
"""

import asyncio
import hashlib
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple, Set, Callable, Union
from collections import defaultdict
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND CONFIGURATION
# =============================================================================

# Regulatory thresholds
IRS_1099C_THRESHOLD = Decimal("600")
FDCPA_MAX_FEE_PERCENT = Decimal("0.50")
MIN_TRUST_BALANCE = Decimal("0.00")

# Aging buckets (days)
AGING_BUCKETS = [0, 30, 60, 90, 120, 180, 365]
AGING_BUCKET_LABELS = ["Current", "1-30", "31-60", "61-90", "91-120", "121-180", "181-365", "365+"]

# Reserve rates by aging bucket
DEFAULT_RESERVE_RATES = {
    "Current": Decimal("0.02"),
    "1-30": Decimal("0.05"),
    "31-60": Decimal("0.10"),
    "61-90": Decimal("0.20"),
    "91-120": Decimal("0.35"),
    "121-180": Decimal("0.50"),
    "181-365": Decimal("0.70"),
    "365+": Decimal("0.90"),
}

# Fee structures
class FeeStructure(Enum):
    CONTINGENCY = "contingency"
    FLAT_FEE = "flat_fee"
    TIERED = "tiered"
    HYBRID = "hybrid"
    FIRST_PARTY = "first_party"


class PaymentStatus(Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"
    REVERSED = "reversed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"
    APPLIED = "applied"


class TransactionType(Enum):
    PAYMENT = "payment"
    ADJUSTMENT = "adjustment"
    WRITE_OFF = "write_off"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    TRANSFER = "transfer"
    REVERSAL = "reversal"
    SETTLEMENT = "settlement"


class ReconciliationStatus(Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    PARTIAL = "partial"
    EXCEPTION = "exception"
    RESOLVED = "resolved"
    PENDING_REVIEW = "pending_review"


class AuditEventType(Enum):
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_APPLIED = "payment_applied"
    PAYMENT_REVERSED = "payment_reversed"
    SETTLEMENT_CREATED = "settlement_created"
    SETTLEMENT_COMPLETED = "settlement_completed"
    WRITE_OFF_APPROVED = "write_off_approved"
    REFUND_ISSUED = "refund_issued"
    FEE_CALCULATED = "fee_calculated"
    REMITTANCE_GENERATED = "remittance_generated"
    TRUST_DEPOSIT = "trust_deposit"
    TRUST_WITHDRAWAL = "trust_withdrawal"
    RECONCILIATION_RUN = "reconciliation_run"
    EXCEPTION_FLAGGED = "exception_flagged"
    EXCEPTION_RESOLVED = "exception_resolved"
    VALUATION_UPDATE = "valuation_update"
    RESERVE_ADJUSTMENT = "reserve_adjustment"


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class Payment:
    """Individual payment transaction"""
    payment_id: str
    account_id: str
    amount: Decimal
    payment_date: datetime
    payment_method: str  # card, ach, check, wire, digital_wallet
    status: PaymentStatus = PaymentStatus.PENDING

    # Source tracking
    processor_reference: Optional[str] = None
    bank_reference: Optional[str] = None
    confirmation_number: Optional[str] = None

    # Application details
    principal_applied: Decimal = Decimal("0")
    interest_applied: Decimal = Decimal("0")
    fees_applied: Decimal = Decimal("0")

    # Settlement context
    is_settlement_payment: bool = False
    settlement_id: Optional[str] = None
    payment_plan_id: Optional[str] = None
    payment_sequence: int = 1

    # Metadata
    payer_name: Optional[str] = None
    payer_last_four: Optional[str] = None
    memo: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "account_id": self.account_id,
            "amount": str(self.amount),
            "payment_date": self.payment_date.isoformat(),
            "status": self.status.value,
            "payment_method": self.payment_method,
        }


@dataclass
class PaymentPlan:
    """Multi-payment plan tracking"""
    plan_id: str
    account_id: str
    settlement_id: Optional[str]

    # Plan terms
    total_amount: Decimal
    down_payment: Decimal
    monthly_amount: Decimal
    num_payments: int
    start_date: date

    # Status tracking
    payments_made: int = 0
    amount_paid: Decimal = Decimal("0")
    next_due_date: Optional[date] = None
    is_active: bool = True
    is_completed: bool = False
    is_defaulted: bool = False

    # Payment history
    payment_ids: List[str] = field(default_factory=list)
    missed_payments: int = 0
    last_payment_date: Optional[date] = None

    @property
    def remaining_balance(self) -> Decimal:
        return self.total_amount - self.amount_paid

    @property
    def completion_percentage(self) -> float:
        if self.total_amount == 0:
            return 100.0
        return float(self.amount_paid / self.total_amount * 100)


@dataclass
class Settlement:
    """Settlement agreement tracking"""
    settlement_id: str
    account_id: str
    client_id: str

    # Amounts
    original_balance: Decimal
    settlement_amount: Decimal
    discount_amount: Decimal

    # Terms
    settlement_type: str  # lump_sum, payment_plan
    payment_plan_id: Optional[str] = None
    expiration_date: Optional[date] = None

    # Status
    is_approved: bool = False
    is_completed: bool = False
    is_expired: bool = False
    amount_collected: Decimal = Decimal("0")

    # Compliance
    requires_1099c: bool = False
    form_1099c_issued: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def discount_percentage(self) -> float:
        if self.original_balance == 0:
            return 0.0
        return float(self.discount_amount / self.original_balance * 100)

    @property
    def remaining_to_collect(self) -> Decimal:
        return self.settlement_amount - self.amount_collected


@dataclass
class Account:
    """Account for reconciliation purposes"""
    account_id: str
    client_id: str
    debtor_id: str

    # Balances
    original_balance: Decimal
    current_balance: Decimal
    principal_balance: Decimal
    interest_balance: Decimal = Decimal("0")
    fees_balance: Decimal = Decimal("0")

    # Status
    status: str = "active"  # active, settled, paid_in_full, written_off, disputed
    days_past_due: int = 0
    placement_date: date = field(default_factory=date.today)

    # Payment tracking
    total_payments: Decimal = Decimal("0")
    payment_count: int = 0
    last_payment_date: Optional[date] = None
    last_payment_amount: Decimal = Decimal("0")

    # Settlement tracking
    active_settlement_id: Optional[str] = None
    active_plan_id: Optional[str] = None

    # Client/creditor info
    creditor_name: str = ""
    debt_type: str = "consumer"


@dataclass
class TrustAccount:
    """Segregated trust account for FDCPA compliance"""
    trust_id: str
    client_id: str
    account_name: str

    # Balances
    balance: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    pending_deposits: Decimal = Decimal("0")
    pending_withdrawals: Decimal = Decimal("0")

    # Regulatory
    minimum_balance: Decimal = Decimal("0")
    reserve_requirement: Decimal = Decimal("0")
    is_compliant: bool = True

    # Interest (where applicable)
    interest_bearing: bool = False
    interest_rate: Decimal = Decimal("0")
    accrued_interest: Decimal = Decimal("0")

    # Audit
    last_reconciled: Optional[datetime] = None
    last_audit_date: Optional[date] = None


@dataclass
class RemittanceReport:
    """Creditor remittance report"""
    report_id: str
    client_id: str
    report_date: date
    period_start: date
    period_end: date

    # Summary amounts
    gross_collections: Decimal = Decimal("0")
    agency_fees: Decimal = Decimal("0")
    net_remittance: Decimal = Decimal("0")

    # Breakdowns
    payment_count: int = 0
    settlement_count: int = 0
    refund_count: int = 0

    # Details
    line_items: List[Dict[str, Any]] = field(default_factory=list)

    # Status
    is_finalized: bool = False
    remitted_date: Optional[date] = None
    remittance_reference: Optional[str] = None


@dataclass
class AuditEntry:
    """SOX-compliant audit trail entry"""
    audit_id: str
    event_type: AuditEventType
    timestamp: datetime

    # Context
    entity_type: str  # payment, account, settlement, trust, etc.
    entity_id: str

    # Actor
    user_id: Optional[str] = None
    system_id: str = "QUAN"
    ip_address: Optional[str] = None

    # Change tracking
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None

    # Details
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Integrity
    checksum: str = ""

    def calculate_checksum(self) -> str:
        """Calculate integrity checksum"""
        data = f"{self.audit_id}{self.event_type.value}{self.timestamp.isoformat()}{self.entity_id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class ReconciliationException:
    """Reconciliation exception for review"""
    exception_id: str
    exception_type: str
    severity: str  # low, medium, high, critical

    # Context
    source_system: str
    source_reference: str
    target_system: Optional[str] = None
    target_reference: Optional[str] = None

    # Amounts
    expected_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    variance: Optional[Decimal] = None

    # Status
    status: ReconciliationStatus = ReconciliationStatus.EXCEPTION
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    # Details
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# PAYMENT RECONCILIATION
# =============================================================================

class PaymentReconciliationEngine:
    """
    Core payment reconciliation engine.
    Matches incoming payments to accounts and handles complex scenarios.
    """

    def __init__(self):
        self.payments: Dict[str, Payment] = {}
        self.accounts: Dict[str, Account] = {}
        self.payment_plans: Dict[str, PaymentPlan] = {}
        self.settlements: Dict[str, Settlement] = {}
        self.unmatched_payments: List[Payment] = []
        self.audit_log = AuditTrail()

    async def receive_payment(
        self,
        amount: Decimal,
        account_id: Optional[str] = None,
        payment_method: str = "ach",
        processor_reference: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Payment:
        """Receive and process an incoming payment"""

        payment_id = f"PMT-{uuid.uuid4().hex[:12].upper()}"

        payment = Payment(
            payment_id=payment_id,
            account_id=account_id or "UNMATCHED",
            amount=amount,
            payment_date=datetime.utcnow(),
            payment_method=payment_method,
            processor_reference=processor_reference,
            status=PaymentStatus.PENDING,
        )

        if metadata:
            payment.payer_name = metadata.get("payer_name")
            payment.payer_last_four = metadata.get("last_four")
            payment.memo = metadata.get("memo")

        self.payments[payment_id] = payment

        # Log receipt
        await self.audit_log.log(
            AuditEventType.PAYMENT_RECEIVED,
            "payment",
            payment_id,
            new_state=payment.to_dict(),
            description=f"Payment received: ${amount} via {payment_method}",
        )

        # Attempt auto-matching if no account specified
        if account_id is None:
            matched = await self._attempt_auto_match(payment)
            if not matched:
                self.unmatched_payments.append(payment)
                logger.warning(f"Payment {payment_id} could not be auto-matched")
        else:
            # Apply to specified account
            await self.apply_payment(payment)

        return payment

    async def _attempt_auto_match(self, payment: Payment) -> bool:
        """Attempt to automatically match payment to an account"""

        # Strategy 1: Match by processor reference
        if payment.processor_reference:
            for account in self.accounts.values():
                if account.account_id in payment.processor_reference:
                    payment.account_id = account.account_id
                    await self.apply_payment(payment)
                    return True

        # Strategy 2: Match by exact amount on payment plan
        for plan in self.payment_plans.values():
            if plan.is_active and (
                payment.amount == plan.monthly_amount or
                payment.amount == plan.down_payment
            ):
                payment.account_id = plan.account_id
                payment.payment_plan_id = plan.plan_id
                await self.apply_payment(payment)
                return True

        # Strategy 3: Match by memo field
        if payment.memo:
            for account in self.accounts.values():
                if account.account_id.lower() in payment.memo.lower():
                    payment.account_id = account.account_id
                    await self.apply_payment(payment)
                    return True

        return False

    async def apply_payment(self, payment: Payment) -> Dict[str, Any]:
        """Apply payment to account with proper allocation"""

        account = self.accounts.get(payment.account_id)
        if not account:
            raise ValueError(f"Account {payment.account_id} not found")

        result = {
            "payment_id": payment.payment_id,
            "account_id": payment.account_id,
            "amount": payment.amount,
            "allocation": {},
            "status": "applied",
        }

        remaining = payment.amount

        # Check for overpayment
        if payment.amount > account.current_balance:
            result["overpayment"] = payment.amount - account.current_balance
            result["status"] = "overpayment"
            remaining = account.current_balance

        # Allocate to fees first
        if account.fees_balance > 0 and remaining > 0:
            fees_paid = min(remaining, account.fees_balance)
            payment.fees_applied = fees_paid
            account.fees_balance -= fees_paid
            remaining -= fees_paid
            result["allocation"]["fees"] = str(fees_paid)

        # Then interest
        if account.interest_balance > 0 and remaining > 0:
            interest_paid = min(remaining, account.interest_balance)
            payment.interest_applied = interest_paid
            account.interest_balance -= interest_paid
            remaining -= interest_paid
            result["allocation"]["interest"] = str(interest_paid)

        # Finally principal
        if account.principal_balance > 0 and remaining > 0:
            principal_paid = min(remaining, account.principal_balance)
            payment.principal_applied = principal_paid
            account.principal_balance -= principal_paid
            remaining -= principal_paid
            result["allocation"]["principal"] = str(principal_paid)

        # Update account totals
        applied_amount = payment.amount - remaining
        account.current_balance -= applied_amount
        account.total_payments += applied_amount
        account.payment_count += 1
        account.last_payment_date = payment.payment_date.date()
        account.last_payment_amount = applied_amount

        # Update payment status
        payment.status = PaymentStatus.APPLIED
        payment.updated_at = datetime.utcnow()

        # Check if paid in full
        if account.current_balance <= 0:
            account.status = "paid_in_full"
            result["account_status"] = "paid_in_full"

        # Update payment plan if applicable
        if payment.payment_plan_id:
            await self._update_payment_plan(payment)

        # Update settlement if applicable
        if payment.settlement_id or account.active_settlement_id:
            settlement_id = payment.settlement_id or account.active_settlement_id
            await self._update_settlement(settlement_id, applied_amount)

        # Log application
        await self.audit_log.log(
            AuditEventType.PAYMENT_APPLIED,
            "payment",
            payment.payment_id,
            new_state=result,
            description=f"Payment applied to account {account.account_id}",
        )

        return result

    async def process_partial_payment(
        self,
        payment: Payment,
        allocation: Dict[str, Decimal],
    ) -> Dict[str, Any]:
        """Process a partial payment with custom allocation"""

        account = self.accounts.get(payment.account_id)
        if not account:
            raise ValueError(f"Account {payment.account_id} not found")

        total_allocated = sum(allocation.values())
        if total_allocated > payment.amount:
            raise ValueError("Allocation exceeds payment amount")

        result = {
            "payment_id": payment.payment_id,
            "allocated": {},
            "remaining": payment.amount - total_allocated,
        }

        if "principal" in allocation:
            payment.principal_applied = allocation["principal"]
            account.principal_balance -= allocation["principal"]
            result["allocated"]["principal"] = str(allocation["principal"])

        if "interest" in allocation:
            payment.interest_applied = allocation["interest"]
            account.interest_balance -= allocation["interest"]
            result["allocated"]["interest"] = str(allocation["interest"])

        if "fees" in allocation:
            payment.fees_applied = allocation["fees"]
            account.fees_balance -= allocation["fees"]
            result["allocated"]["fees"] = str(allocation["fees"])

        # Update totals
        account.current_balance = (
            account.principal_balance +
            account.interest_balance +
            account.fees_balance
        )
        account.total_payments += total_allocated

        payment.status = PaymentStatus.APPLIED

        return result

    async def _update_payment_plan(self, payment: Payment) -> None:
        """Update payment plan after payment received"""

        plan = self.payment_plans.get(payment.payment_plan_id)
        if not plan:
            return

        plan.payments_made += 1
        plan.amount_paid += payment.amount
        plan.payment_ids.append(payment.payment_id)
        plan.last_payment_date = payment.payment_date.date()

        # Calculate next due date
        if plan.payments_made < plan.num_payments:
            plan.next_due_date = plan.start_date + timedelta(days=30 * plan.payments_made)
        else:
            plan.is_completed = True
            plan.is_active = False
            plan.next_due_date = None

    async def _update_settlement(
        self,
        settlement_id: str,
        amount: Decimal,
    ) -> None:
        """Update settlement after payment received"""

        settlement = self.settlements.get(settlement_id)
        if not settlement:
            return

        settlement.amount_collected += amount

        if settlement.amount_collected >= settlement.settlement_amount:
            settlement.is_completed = True
            settlement.completed_at = datetime.utcnow()

            # Check 1099-C requirement
            if settlement.discount_amount >= IRS_1099C_THRESHOLD:
                settlement.requires_1099c = True

            await self.audit_log.log(
                AuditEventType.SETTLEMENT_COMPLETED,
                "settlement",
                settlement_id,
                description=f"Settlement completed: ${settlement.amount_collected} collected",
            )

    async def process_overpayment(
        self,
        payment: Payment,
        action: str = "refund",
    ) -> Dict[str, Any]:
        """Handle overpayment scenarios"""

        account = self.accounts.get(payment.account_id)
        if not account:
            raise ValueError(f"Account {payment.account_id} not found")

        overpayment = payment.amount - account.current_balance

        if overpayment <= 0:
            return {"status": "no_overpayment"}

        result = {
            "overpayment_amount": str(overpayment),
            "action": action,
        }

        if action == "refund":
            # Create refund
            refund_id = f"REF-{uuid.uuid4().hex[:12].upper()}"
            result["refund_id"] = refund_id
            result["status"] = "refund_pending"

            await self.audit_log.log(
                AuditEventType.REFUND_ISSUED,
                "payment",
                payment.payment_id,
                description=f"Refund issued for overpayment: ${overpayment}",
                metadata={"refund_id": refund_id},
            )

        elif action == "apply_to_other":
            # Find other accounts for same debtor
            debtor_id = account.debtor_id
            for other_account in self.accounts.values():
                if (other_account.debtor_id == debtor_id and
                    other_account.account_id != account.account_id and
                    other_account.current_balance > 0):

                    result["applied_to"] = other_account.account_id
                    result["amount_applied"] = str(min(overpayment, other_account.current_balance))
                    break

        elif action == "credit":
            # Hold as credit on account
            result["credit_balance"] = str(overpayment)
            result["status"] = "credit_applied"

        return result

    async def reverse_payment(
        self,
        payment_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Reverse a payment (NSF, chargeback, etc.)"""

        payment = self.payments.get(payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        if payment.status == PaymentStatus.REVERSED:
            raise ValueError("Payment already reversed")

        account = self.accounts.get(payment.account_id)
        if not account:
            raise ValueError(f"Account {payment.account_id} not found")

        # Store previous state
        previous_state = {
            "account_balance": str(account.current_balance),
            "payment_status": payment.status.value,
        }

        # Reverse allocations
        account.principal_balance += payment.principal_applied
        account.interest_balance += payment.interest_applied
        account.fees_balance += payment.fees_applied
        account.current_balance += (
            payment.principal_applied +
            payment.interest_applied +
            payment.fees_applied
        )
        account.total_payments -= payment.amount
        account.payment_count -= 1

        # Update account status if needed
        if account.status == "paid_in_full" and account.current_balance > 0:
            account.status = "active"

        # Update payment
        payment.status = PaymentStatus.REVERSED
        payment.updated_at = datetime.utcnow()

        # Reverse payment plan if applicable
        if payment.payment_plan_id:
            plan = self.payment_plans.get(payment.payment_plan_id)
            if plan:
                plan.payments_made -= 1
                plan.amount_paid -= payment.amount
                if payment.payment_id in plan.payment_ids:
                    plan.payment_ids.remove(payment.payment_id)
                plan.is_completed = False
                plan.is_active = True

        # Reverse settlement if applicable
        settlement_id = payment.settlement_id or account.active_settlement_id
        if settlement_id:
            settlement = self.settlements.get(settlement_id)
            if settlement:
                settlement.amount_collected -= payment.amount
                settlement.is_completed = False
                settlement.completed_at = None

        # Log reversal
        await self.audit_log.log(
            AuditEventType.PAYMENT_REVERSED,
            "payment",
            payment_id,
            previous_state=previous_state,
            new_state={"account_balance": str(account.current_balance)},
            description=f"Payment reversed: {reason}",
        )

        return {
            "payment_id": payment_id,
            "status": "reversed",
            "reason": reason,
            "new_account_balance": str(account.current_balance),
        }


# =============================================================================
# SETTLEMENT ACCOUNTING
# =============================================================================

class SettlementAccountingEngine:
    """
    Settlement accounting and write-off management.
    Handles discounts, recovery rates, and tax compliance.
    """

    def __init__(self, audit_log: 'AuditTrail'):
        self.settlements: Dict[str, Settlement] = {}
        self.write_offs: Dict[str, Dict[str, Any]] = {}
        self.audit_log = audit_log

        # Fee structures by client
        self.client_fee_structures: Dict[str, Dict[str, Any]] = {}

    async def create_settlement(
        self,
        account: Account,
        settlement_amount: Decimal,
        settlement_type: str = "lump_sum",
        payment_plan_terms: Optional[Dict[str, Any]] = None,
        expiration_days: int = 14,
    ) -> Settlement:
        """Create a new settlement agreement"""

        settlement_id = f"STL-{uuid.uuid4().hex[:12].upper()}"
        discount_amount = account.current_balance - settlement_amount

        settlement = Settlement(
            settlement_id=settlement_id,
            account_id=account.account_id,
            client_id=account.client_id,
            original_balance=account.current_balance,
            settlement_amount=settlement_amount,
            discount_amount=discount_amount,
            settlement_type=settlement_type,
            expiration_date=date.today() + timedelta(days=expiration_days),
        )

        # Check 1099-C threshold
        if discount_amount >= IRS_1099C_THRESHOLD:
            settlement.requires_1099c = True

        self.settlements[settlement_id] = settlement

        # Log creation
        await self.audit_log.log(
            AuditEventType.SETTLEMENT_CREATED,
            "settlement",
            settlement_id,
            new_state={
                "original_balance": str(account.current_balance),
                "settlement_amount": str(settlement_amount),
                "discount_percentage": f"{settlement.discount_percentage:.1f}%",
            },
            description=f"Settlement created: ${settlement_amount} ({settlement.discount_percentage:.1f}% discount)",
        )

        return settlement

    def calculate_recovery_rate(
        self,
        settlements: List[Settlement],
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Calculate recovery rate metrics"""

        period_settlements = [
            s for s in settlements
            if s.is_completed and s.completed_at and
            period_start <= s.completed_at.date() <= period_end
        ]

        if not period_settlements:
            return {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "settlement_count": 0,
                "recovery_rate": 0.0,
            }

        total_original = sum(s.original_balance for s in period_settlements)
        total_collected = sum(s.amount_collected for s in period_settlements)
        total_discount = sum(s.discount_amount for s in period_settlements)

        recovery_rate = float(total_collected / total_original) if total_original else 0

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "settlement_count": len(period_settlements),
            "total_original_balance": str(total_original),
            "total_collected": str(total_collected),
            "total_discount": str(total_discount),
            "recovery_rate": round(recovery_rate * 100, 2),
            "average_discount": round(
                float(total_discount / len(period_settlements)), 2
            ) if period_settlements else 0,
        }

    async def process_write_off(
        self,
        account: Account,
        reason: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Process account write-off"""

        write_off_id = f"WO-{uuid.uuid4().hex[:12].upper()}"

        write_off = {
            "write_off_id": write_off_id,
            "account_id": account.account_id,
            "client_id": account.client_id,
            "amount": str(account.current_balance),
            "reason": reason,
            "approved_by": approved_by,
            "approved_at": datetime.utcnow().isoformat(),
            "requires_1099c": account.current_balance >= IRS_1099C_THRESHOLD,
        }

        self.write_offs[write_off_id] = write_off

        # Update account
        previous_balance = account.current_balance
        account.current_balance = Decimal("0")
        account.status = "written_off"

        # Log write-off
        await self.audit_log.log(
            AuditEventType.WRITE_OFF_APPROVED,
            "account",
            account.account_id,
            previous_state={"balance": str(previous_balance)},
            new_state=write_off,
            description=f"Write-off approved: ${previous_balance} - {reason}",
        )

        return write_off

    def calculate_contingency_fee(
        self,
        collection_amount: Decimal,
        client_id: str,
        debt_age_days: int,
    ) -> Dict[str, Decimal]:
        """Calculate contingency fee based on client terms"""

        fee_structure = self.client_fee_structures.get(client_id, {
            "type": FeeStructure.CONTINGENCY,
            "base_rate": Decimal("0.25"),
            "tiered_rates": [
                {"min_days": 0, "max_days": 90, "rate": Decimal("0.20")},
                {"min_days": 91, "max_days": 180, "rate": Decimal("0.25")},
                {"min_days": 181, "max_days": 365, "rate": Decimal("0.30")},
                {"min_days": 366, "max_days": 99999, "rate": Decimal("0.35")},
            ],
        })

        # Find applicable rate
        rate = fee_structure.get("base_rate", Decimal("0.25"))

        for tier in fee_structure.get("tiered_rates", []):
            if tier["min_days"] <= debt_age_days <= tier["max_days"]:
                rate = tier["rate"]
                break

        # Cap at regulatory maximum
        rate = min(rate, FDCPA_MAX_FEE_PERCENT)

        agency_fee = (collection_amount * rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net_to_client = collection_amount - agency_fee

        return {
            "gross_collection": collection_amount,
            "fee_rate": rate,
            "agency_fee": agency_fee,
            "net_to_client": net_to_client,
        }


# =============================================================================
# TRUST ACCOUNTING
# =============================================================================

class TrustAccountingEngine:
    """
    FDCPA-compliant trust account management.
    Handles segregated client funds with full audit trail.
    """

    def __init__(self, audit_log: 'AuditTrail'):
        self.trust_accounts: Dict[str, TrustAccount] = {}
        self.transactions: List[Dict[str, Any]] = []
        self.audit_log = audit_log

    def create_trust_account(
        self,
        client_id: str,
        account_name: str,
        minimum_balance: Decimal = Decimal("0"),
        interest_bearing: bool = False,
        interest_rate: Decimal = Decimal("0"),
    ) -> TrustAccount:
        """Create a segregated trust account for a client"""

        trust_id = f"TRUST-{uuid.uuid4().hex[:8].upper()}"

        trust_account = TrustAccount(
            trust_id=trust_id,
            client_id=client_id,
            account_name=account_name,
            minimum_balance=minimum_balance,
            interest_bearing=interest_bearing,
            interest_rate=interest_rate,
        )

        self.trust_accounts[trust_id] = trust_account
        logger.info(f"Trust account created: {trust_id} for client {client_id}")

        return trust_account

    async def deposit(
        self,
        trust_id: str,
        amount: Decimal,
        source: str,
        reference: str,
    ) -> Dict[str, Any]:
        """Deposit funds into trust account"""

        trust = self.trust_accounts.get(trust_id)
        if not trust:
            raise ValueError(f"Trust account {trust_id} not found")

        transaction_id = f"TD-{uuid.uuid4().hex[:12].upper()}"

        previous_balance = trust.balance
        trust.balance += amount
        trust.available_balance += amount

        transaction = {
            "transaction_id": transaction_id,
            "trust_id": trust_id,
            "type": "deposit",
            "amount": str(amount),
            "source": source,
            "reference": reference,
            "previous_balance": str(previous_balance),
            "new_balance": str(trust.balance),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.transactions.append(transaction)

        # Log deposit
        await self.audit_log.log(
            AuditEventType.TRUST_DEPOSIT,
            "trust",
            trust_id,
            previous_state={"balance": str(previous_balance)},
            new_state={"balance": str(trust.balance)},
            description=f"Trust deposit: ${amount} from {source}",
            metadata={"reference": reference},
        )

        # Check compliance
        await self._check_compliance(trust)

        return transaction

    async def withdraw(
        self,
        trust_id: str,
        amount: Decimal,
        purpose: str,
        destination: str,
        reference: str,
    ) -> Dict[str, Any]:
        """Withdraw funds from trust account"""

        trust = self.trust_accounts.get(trust_id)
        if not trust:
            raise ValueError(f"Trust account {trust_id} not found")

        # Check available balance
        if amount > trust.available_balance:
            raise ValueError(
                f"Insufficient funds: requested ${amount}, available ${trust.available_balance}"
            )

        # Check minimum balance requirement
        if trust.balance - amount < trust.minimum_balance:
            raise ValueError(
                f"Withdrawal would breach minimum balance requirement: ${trust.minimum_balance}"
            )

        transaction_id = f"TW-{uuid.uuid4().hex[:12].upper()}"

        previous_balance = trust.balance
        trust.balance -= amount
        trust.available_balance -= amount

        transaction = {
            "transaction_id": transaction_id,
            "trust_id": trust_id,
            "type": "withdrawal",
            "amount": str(amount),
            "purpose": purpose,
            "destination": destination,
            "reference": reference,
            "previous_balance": str(previous_balance),
            "new_balance": str(trust.balance),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.transactions.append(transaction)

        # Log withdrawal
        await self.audit_log.log(
            AuditEventType.TRUST_WITHDRAWAL,
            "trust",
            trust_id,
            previous_state={"balance": str(previous_balance)},
            new_state={"balance": str(trust.balance)},
            description=f"Trust withdrawal: ${amount} for {purpose}",
            metadata={"destination": destination, "reference": reference},
        )

        return transaction

    async def calculate_interest(
        self,
        trust_id: str,
        period_days: int = 30,
    ) -> Decimal:
        """Calculate and accrue interest on trust account"""

        trust = self.trust_accounts.get(trust_id)
        if not trust or not trust.interest_bearing:
            return Decimal("0")

        # Simple interest calculation
        daily_rate = trust.interest_rate / Decimal("365")
        interest = (trust.balance * daily_rate * period_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        trust.accrued_interest += interest

        return interest

    async def _check_compliance(self, trust: TrustAccount) -> bool:
        """Check trust account regulatory compliance"""

        is_compliant = True
        issues = []

        # Check minimum balance
        if trust.balance < trust.minimum_balance:
            is_compliant = False
            issues.append(f"Balance ${trust.balance} below minimum ${trust.minimum_balance}")

        # Check reserve requirement
        if trust.reserve_requirement > 0 and trust.balance < trust.reserve_requirement:
            is_compliant = False
            issues.append(f"Balance below reserve requirement ${trust.reserve_requirement}")

        trust.is_compliant = is_compliant

        if not is_compliant:
            logger.warning(f"Trust {trust.trust_id} compliance issues: {issues}")

        return is_compliant

    def get_trust_statement(
        self,
        trust_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Generate trust account statement"""

        trust = self.trust_accounts.get(trust_id)
        if not trust:
            raise ValueError(f"Trust account {trust_id} not found")

        # Filter transactions
        period_transactions = [
            t for t in self.transactions
            if t["trust_id"] == trust_id and
            start_date <= datetime.fromisoformat(t["timestamp"]).date() <= end_date
        ]

        deposits = sum(
            Decimal(t["amount"]) for t in period_transactions
            if t["type"] == "deposit"
        )
        withdrawals = sum(
            Decimal(t["amount"]) for t in period_transactions
            if t["type"] == "withdrawal"
        )

        return {
            "trust_id": trust_id,
            "client_id": trust.client_id,
            "account_name": trust.account_name,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "opening_balance": str(trust.balance - deposits + withdrawals),
            "total_deposits": str(deposits),
            "total_withdrawals": str(withdrawals),
            "closing_balance": str(trust.balance),
            "transaction_count": len(period_transactions),
            "transactions": period_transactions,
            "interest_accrued": str(trust.accrued_interest),
            "is_compliant": trust.is_compliant,
        }


# =============================================================================
# CREDITOR REMITTANCE
# =============================================================================

class CreditorRemittanceEngine:
    """
    Generate remittance reports and process creditor payments.
    Supports multiple fee structures and batch processing.
    """

    def __init__(
        self,
        settlement_engine: SettlementAccountingEngine,
        trust_engine: TrustAccountingEngine,
        audit_log: 'AuditTrail',
    ):
        self.settlement_engine = settlement_engine
        self.trust_engine = trust_engine
        self.audit_log = audit_log
        self.remittance_reports: Dict[str, RemittanceReport] = {}
        self.invoices: Dict[str, Dict[str, Any]] = {}

    async def generate_remittance_report(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        payments: List[Payment],
        accounts: Dict[str, Account],
    ) -> RemittanceReport:
        """Generate detailed remittance report for client"""

        report_id = f"REM-{uuid.uuid4().hex[:12].upper()}"

        report = RemittanceReport(
            report_id=report_id,
            client_id=client_id,
            report_date=date.today(),
            period_start=period_start,
            period_end=period_end,
        )

        # Filter payments for this client
        client_accounts = {
            acc_id: acc for acc_id, acc in accounts.items()
            if acc.client_id == client_id
        }
        client_account_ids = set(client_accounts.keys())

        client_payments = [
            p for p in payments
            if p.account_id in client_account_ids and
            p.status == PaymentStatus.APPLIED and
            period_start <= p.payment_date.date() <= period_end
        ]

        # Build line items
        for payment in client_payments:
            account = client_accounts.get(payment.account_id)
            if not account:
                continue

            # Calculate fees
            fee_calc = self.settlement_engine.calculate_contingency_fee(
                payment.amount,
                client_id,
                account.days_past_due,
            )

            line_item = {
                "payment_id": payment.payment_id,
                "account_id": payment.account_id,
                "payment_date": payment.payment_date.isoformat(),
                "gross_amount": str(payment.amount),
                "agency_fee": str(fee_calc["agency_fee"]),
                "net_amount": str(fee_calc["net_to_client"]),
                "fee_rate": str(fee_calc["fee_rate"]),
                "is_settlement": payment.is_settlement_payment,
            }

            report.line_items.append(line_item)
            report.gross_collections += payment.amount
            report.agency_fees += fee_calc["agency_fee"]
            report.net_remittance += fee_calc["net_to_client"]
            report.payment_count += 1

            if payment.is_settlement_payment:
                report.settlement_count += 1

        self.remittance_reports[report_id] = report

        # Log generation
        await self.audit_log.log(
            AuditEventType.REMITTANCE_GENERATED,
            "remittance",
            report_id,
            new_state={
                "client_id": client_id,
                "period": f"{period_start} to {period_end}",
                "gross_collections": str(report.gross_collections),
                "net_remittance": str(report.net_remittance),
            },
            description=f"Remittance report generated: ${report.net_remittance} net",
        )

        return report

    def calculate_net_amounts(
        self,
        report: RemittanceReport,
    ) -> Dict[str, Decimal]:
        """Calculate final net amounts including adjustments"""

        net_amounts = {
            "gross_collections": report.gross_collections,
            "agency_fees": report.agency_fees,
            "adjustments": Decimal("0"),
            "refunds": Decimal("0"),
            "net_remittance": report.net_remittance,
        }

        # Apply any pending adjustments
        # (In production, would pull from adjustment records)

        return net_amounts

    async def generate_invoice(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        report: RemittanceReport,
    ) -> Dict[str, Any]:
        """Generate invoice for agency fees"""

        invoice_id = f"INV-{uuid.uuid4().hex[:12].upper()}"

        invoice = {
            "invoice_id": invoice_id,
            "client_id": client_id,
            "invoice_date": date.today().isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "remittance_report_id": report.report_id,
            "line_items": [
                {
                    "description": "Collection Services",
                    "quantity": report.payment_count,
                    "unit_price": str(report.agency_fees / report.payment_count) if report.payment_count else "0",
                    "amount": str(report.agency_fees),
                },
            ],
            "subtotal": str(report.agency_fees),
            "tax": "0.00",
            "total": str(report.agency_fees),
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "status": "pending",
        }

        self.invoices[invoice_id] = invoice

        return invoice

    async def process_batch_remittance(
        self,
        reports: List[RemittanceReport],
    ) -> Dict[str, Any]:
        """Process batch remittance for multiple clients"""

        batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        batch_results = []

        total_gross = Decimal("0")
        total_fees = Decimal("0")
        total_net = Decimal("0")

        for report in reports:
            if report.is_finalized:
                continue

            # Mark as finalized
            report.is_finalized = True
            report.remitted_date = date.today()
            report.remittance_reference = f"{batch_id}-{report.client_id}"

            batch_results.append({
                "report_id": report.report_id,
                "client_id": report.client_id,
                "net_remittance": str(report.net_remittance),
                "reference": report.remittance_reference,
            })

            total_gross += report.gross_collections
            total_fees += report.agency_fees
            total_net += report.net_remittance

        return {
            "batch_id": batch_id,
            "processed_date": date.today().isoformat(),
            "report_count": len(batch_results),
            "total_gross": str(total_gross),
            "total_fees": str(total_fees),
            "total_net": str(total_net),
            "results": batch_results,
        }


# =============================================================================
# PORTFOLIO ACCOUNTING
# =============================================================================

class PortfolioAccountingEngine:
    """
    Portfolio valuation and accounting.
    Supports GAAP/IFRS compliance with mark-to-market and impairment testing.
    """

    def __init__(self, audit_log: 'AuditTrail'):
        self.portfolios: Dict[str, Dict[str, Any]] = {}
        self.valuations: List[Dict[str, Any]] = []
        self.audit_log = audit_log
        self.reserve_rates = DEFAULT_RESERVE_RATES.copy()

    def get_aging_bucket(self, days_past_due: int) -> str:
        """Determine aging bucket for an account"""

        if days_past_due <= 0:
            return "Current"
        elif days_past_due <= 30:
            return "1-30"
        elif days_past_due <= 60:
            return "31-60"
        elif days_past_due <= 90:
            return "61-90"
        elif days_past_due <= 120:
            return "91-120"
        elif days_past_due <= 180:
            return "121-180"
        elif days_past_due <= 365:
            return "181-365"
        else:
            return "365+"

    def calculate_aging_analysis(
        self,
        accounts: List[Account],
    ) -> Dict[str, Any]:
        """Calculate portfolio aging analysis"""

        buckets = {label: {"count": 0, "balance": Decimal("0")} for label in AGING_BUCKET_LABELS}

        for account in accounts:
            if account.status in ["written_off", "paid_in_full"]:
                continue

            bucket = self.get_aging_bucket(account.days_past_due)
            buckets[bucket]["count"] += 1
            buckets[bucket]["balance"] += account.current_balance

        total_balance = sum(b["balance"] for b in buckets.values())

        # Calculate percentages
        analysis = {
            "as_of_date": date.today().isoformat(),
            "total_balance": str(total_balance),
            "total_accounts": sum(b["count"] for b in buckets.values()),
            "buckets": {},
        }

        for label, data in buckets.items():
            pct = float(data["balance"] / total_balance * 100) if total_balance else 0
            analysis["buckets"][label] = {
                "count": data["count"],
                "balance": str(data["balance"]),
                "percentage": round(pct, 2),
            }

        return analysis

    def calculate_reserves(
        self,
        accounts: List[Account],
        custom_rates: Optional[Dict[str, Decimal]] = None,
    ) -> Dict[str, Any]:
        """Calculate required reserves using aging-based methodology"""

        rates = custom_rates or self.reserve_rates

        reserve_by_bucket = {label: Decimal("0") for label in AGING_BUCKET_LABELS}
        balance_by_bucket = {label: Decimal("0") for label in AGING_BUCKET_LABELS}

        for account in accounts:
            if account.status in ["written_off", "paid_in_full"]:
                continue

            bucket = self.get_aging_bucket(account.days_past_due)
            balance_by_bucket[bucket] += account.current_balance
            reserve_by_bucket[bucket] += (
                account.current_balance * rates.get(bucket, Decimal("0.50"))
            )

        total_balance = sum(balance_by_bucket.values())
        total_reserve = sum(reserve_by_bucket.values())

        return {
            "as_of_date": date.today().isoformat(),
            "total_balance": str(total_balance),
            "total_reserve": str(total_reserve.quantize(Decimal("0.01"))),
            "reserve_rate": round(
                float(total_reserve / total_balance * 100) if total_balance else 0, 2
            ),
            "by_bucket": {
                label: {
                    "balance": str(balance_by_bucket[label]),
                    "reserve_rate": str(rates.get(label, Decimal("0"))),
                    "reserve": str(reserve_by_bucket[label].quantize(Decimal("0.01"))),
                }
                for label in AGING_BUCKET_LABELS
            },
        }

    async def mark_to_market_valuation(
        self,
        portfolio_id: str,
        accounts: List[Account],
        market_discount_rate: Decimal = Decimal("0.15"),
    ) -> Dict[str, Any]:
        """Calculate mark-to-market portfolio valuation"""

        valuation_id = f"VAL-{uuid.uuid4().hex[:12].upper()}"

        # Calculate gross carrying value
        gross_value = sum(
            acc.current_balance for acc in accounts
            if acc.status not in ["written_off", "paid_in_full"]
        )

        # Calculate expected collections based on aging
        expected_collections = Decimal("0")
        for account in accounts:
            if account.status in ["written_off", "paid_in_full"]:
                continue

            bucket = self.get_aging_bucket(account.days_past_due)
            recovery_rate = Decimal("1") - self.reserve_rates.get(bucket, Decimal("0.50"))
            expected_collections += account.current_balance * recovery_rate

        # Apply market discount
        fair_value = expected_collections * (Decimal("1") - market_discount_rate)

        # Calculate impairment
        impairment = gross_value - fair_value

        valuation = {
            "valuation_id": valuation_id,
            "portfolio_id": portfolio_id,
            "valuation_date": datetime.utcnow().isoformat(),
            "account_count": len([a for a in accounts if a.status not in ["written_off", "paid_in_full"]]),
            "gross_carrying_value": str(gross_value),
            "expected_collections": str(expected_collections),
            "market_discount_rate": str(market_discount_rate),
            "fair_value": str(fair_value.quantize(Decimal("0.01"))),
            "impairment": str(impairment.quantize(Decimal("0.01"))),
            "impairment_rate": round(
                float(impairment / gross_value * 100) if gross_value else 0, 2
            ),
        }

        self.valuations.append(valuation)

        # Log valuation
        await self.audit_log.log(
            AuditEventType.VALUATION_UPDATE,
            "portfolio",
            portfolio_id,
            new_state=valuation,
            description=f"MTM valuation: Fair value ${fair_value.quantize(Decimal('0.01'))}",
        )

        return valuation

    async def impairment_test(
        self,
        portfolio_id: str,
        accounts: List[Account],
        carrying_value: Decimal,
    ) -> Dict[str, Any]:
        """Perform GAAP/IFRS impairment test"""

        # Calculate recoverable amount (higher of fair value less costs to sell, and value in use)
        aging_analysis = self.calculate_aging_analysis(accounts)
        reserves = self.calculate_reserves(accounts)

        # Value in use: expected collections
        expected_collections = Decimal(aging_analysis["total_balance"]) - Decimal(reserves["total_reserve"])

        # Fair value less costs to sell (assume 5% selling costs)
        selling_costs_rate = Decimal("0.05")
        fair_value_less_costs = expected_collections * (Decimal("1") - selling_costs_rate)

        recoverable_amount = max(expected_collections, fair_value_less_costs)

        # Impairment = carrying value - recoverable amount (if positive)
        impairment_loss = max(Decimal("0"), carrying_value - recoverable_amount)

        is_impaired = impairment_loss > 0

        result = {
            "portfolio_id": portfolio_id,
            "test_date": date.today().isoformat(),
            "carrying_value": str(carrying_value),
            "expected_collections": str(expected_collections),
            "fair_value_less_costs": str(fair_value_less_costs.quantize(Decimal("0.01"))),
            "recoverable_amount": str(recoverable_amount.quantize(Decimal("0.01"))),
            "is_impaired": is_impaired,
            "impairment_loss": str(impairment_loss.quantize(Decimal("0.01"))),
            "new_carrying_value": str((carrying_value - impairment_loss).quantize(Decimal("0.01"))),
        }

        if is_impaired:
            await self.audit_log.log(
                AuditEventType.RESERVE_ADJUSTMENT,
                "portfolio",
                portfolio_id,
                new_state=result,
                description=f"Impairment recognized: ${impairment_loss.quantize(Decimal('0.01'))}",
            )

        return result


# =============================================================================
# RECONCILIATION ENGINE
# =============================================================================

class ReconciliationEngine:
    """
    Cross-system reconciliation engine.
    Matches bank statements, payment processors, and internal records.
    """

    def __init__(self, audit_log: 'AuditTrail'):
        self.audit_log = audit_log
        self.exceptions: Dict[str, ReconciliationException] = {}
        self.reconciliation_runs: List[Dict[str, Any]] = []

        # Auto-resolution rules
        self.auto_resolution_rules: List[Dict[str, Any]] = [
            {
                "rule_id": "TIMING_1DAY",
                "description": "Match within 1 day timing difference",
                "condition": lambda e: e.exception_type == "timing" and abs((e.expected_amount or 0) - (e.actual_amount or 0)) < Decimal("0.01"),
                "resolution": "Timing difference - auto-matched",
            },
            {
                "rule_id": "ROUNDING_PENNY",
                "description": "Match with penny rounding difference",
                "condition": lambda e: abs(e.variance or 0) <= Decimal("0.01"),
                "resolution": "Rounding difference - auto-resolved",
            },
            {
                "rule_id": "FEE_ADJUSTMENT",
                "description": "Processor fee adjustment",
                "condition": lambda e: e.exception_type == "fee_variance" and (e.variance or 0) < Decimal("5.00"),
                "resolution": "Processor fee variance - auto-adjusted",
            },
        ]

    async def reconcile_bank_statement(
        self,
        statement_date: date,
        bank_transactions: List[Dict[str, Any]],
        internal_payments: List[Payment],
    ) -> Dict[str, Any]:
        """Reconcile bank statement against internal records"""

        recon_id = f"RECON-{uuid.uuid4().hex[:12].upper()}"

        matched = []
        unmatched_bank = []
        unmatched_internal = []
        exceptions = []

        # Index internal payments by reference and amount
        internal_by_ref = {}
        internal_by_amount = defaultdict(list)

        for payment in internal_payments:
            if payment.bank_reference:
                internal_by_ref[payment.bank_reference] = payment
            internal_by_amount[payment.amount].append(payment)

        # Track matched internal payments
        matched_payment_ids = set()

        # Match bank transactions
        for bank_txn in bank_transactions:
            bank_ref = bank_txn.get("reference")
            bank_amount = Decimal(str(bank_txn.get("amount", 0)))
            bank_date = bank_txn.get("date")

            match_found = False

            # Try exact reference match
            if bank_ref and bank_ref in internal_by_ref:
                payment = internal_by_ref[bank_ref]
                if payment.payment_id not in matched_payment_ids:
                    if payment.amount == bank_amount:
                        matched.append({
                            "bank_reference": bank_ref,
                            "payment_id": payment.payment_id,
                            "amount": str(bank_amount),
                            "match_type": "exact_reference",
                        })
                        matched_payment_ids.add(payment.payment_id)
                        match_found = True
                    else:
                        # Amount mismatch
                        exception = ReconciliationException(
                            exception_id=f"EXC-{uuid.uuid4().hex[:8].upper()}",
                            exception_type="amount_mismatch",
                            severity="medium",
                            source_system="bank",
                            source_reference=bank_ref,
                            target_system="internal",
                            target_reference=payment.payment_id,
                            expected_amount=payment.amount,
                            actual_amount=bank_amount,
                            variance=bank_amount - payment.amount,
                            description=f"Amount mismatch: expected ${payment.amount}, got ${bank_amount}",
                        )
                        exceptions.append(exception)
                        self.exceptions[exception.exception_id] = exception
                        match_found = True

            # Try amount match
            if not match_found and bank_amount in internal_by_amount:
                for payment in internal_by_amount[bank_amount]:
                    if payment.payment_id not in matched_payment_ids:
                        matched.append({
                            "bank_reference": bank_ref,
                            "payment_id": payment.payment_id,
                            "amount": str(bank_amount),
                            "match_type": "amount_match",
                        })
                        matched_payment_ids.add(payment.payment_id)
                        match_found = True
                        break

            if not match_found:
                unmatched_bank.append(bank_txn)

        # Find unmatched internal payments
        for payment in internal_payments:
            if payment.payment_id not in matched_payment_ids:
                unmatched_internal.append({
                    "payment_id": payment.payment_id,
                    "amount": str(payment.amount),
                    "date": payment.payment_date.isoformat(),
                })

        # Apply auto-resolution rules
        auto_resolved = await self._apply_auto_resolution(exceptions)

        result = {
            "reconciliation_id": recon_id,
            "statement_date": statement_date.isoformat(),
            "run_timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_bank_transactions": len(bank_transactions),
                "total_internal_payments": len(internal_payments),
                "matched": len(matched),
                "unmatched_bank": len(unmatched_bank),
                "unmatched_internal": len(unmatched_internal),
                "exceptions": len(exceptions),
                "auto_resolved": auto_resolved,
            },
            "matched_items": matched,
            "unmatched_bank": unmatched_bank,
            "unmatched_internal": unmatched_internal,
            "exceptions": [
                {
                    "exception_id": e.exception_id,
                    "type": e.exception_type,
                    "severity": e.severity,
                    "variance": str(e.variance) if e.variance else None,
                    "status": e.status.value,
                }
                for e in exceptions
            ],
        }

        self.reconciliation_runs.append(result)

        # Log reconciliation
        await self.audit_log.log(
            AuditEventType.RECONCILIATION_RUN,
            "reconciliation",
            recon_id,
            new_state=result["summary"],
            description=f"Bank reconciliation: {len(matched)} matched, {len(exceptions)} exceptions",
        )

        return result

    async def reconcile_processor(
        self,
        processor_name: str,
        processor_transactions: List[Dict[str, Any]],
        internal_payments: List[Payment],
    ) -> Dict[str, Any]:
        """Reconcile payment processor against internal records"""

        recon_id = f"PROC-{uuid.uuid4().hex[:12].upper()}"

        matched = []
        unmatched = []
        fee_variances = []

        # Index by processor reference
        internal_by_ref = {
            p.processor_reference: p
            for p in internal_payments
            if p.processor_reference
        }

        for proc_txn in processor_transactions:
            proc_ref = proc_txn.get("transaction_id")
            proc_amount = Decimal(str(proc_txn.get("amount", 0)))
            proc_fee = Decimal(str(proc_txn.get("fee", 0)))
            proc_net = Decimal(str(proc_txn.get("net_amount", 0)))

            if proc_ref in internal_by_ref:
                payment = internal_by_ref[proc_ref]

                matched.append({
                    "processor_reference": proc_ref,
                    "payment_id": payment.payment_id,
                    "gross_amount": str(proc_amount),
                    "processor_fee": str(proc_fee),
                    "net_amount": str(proc_net),
                })

                # Check for fee variance
                expected_net = payment.amount - proc_fee
                if abs(expected_net - proc_net) > Decimal("0.01"):
                    fee_variances.append({
                        "payment_id": payment.payment_id,
                        "expected_net": str(expected_net),
                        "actual_net": str(proc_net),
                        "variance": str(proc_net - expected_net),
                    })
            else:
                unmatched.append(proc_txn)

        return {
            "reconciliation_id": recon_id,
            "processor": processor_name,
            "run_timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_processor_transactions": len(processor_transactions),
                "matched": len(matched),
                "unmatched": len(unmatched),
                "fee_variances": len(fee_variances),
            },
            "matched_items": matched,
            "unmatched": unmatched,
            "fee_variances": fee_variances,
        }

    async def _apply_auto_resolution(
        self,
        exceptions: List[ReconciliationException],
    ) -> int:
        """Apply auto-resolution rules to exceptions"""

        resolved_count = 0

        for exception in exceptions:
            if exception.status != ReconciliationStatus.EXCEPTION:
                continue

            for rule in self.auto_resolution_rules:
                try:
                    if rule["condition"](exception):
                        exception.status = ReconciliationStatus.RESOLVED
                        exception.resolution = rule["resolution"]
                        exception.resolved_at = datetime.utcnow()
                        exception.resolved_by = f"AUTO:{rule['rule_id']}"
                        resolved_count += 1

                        await self.audit_log.log(
                            AuditEventType.EXCEPTION_RESOLVED,
                            "exception",
                            exception.exception_id,
                            description=f"Auto-resolved: {rule['resolution']}",
                        )
                        break
                except Exception:
                    continue

        return resolved_count

    async def resolve_exception(
        self,
        exception_id: str,
        resolution: str,
        resolved_by: str,
    ) -> ReconciliationException:
        """Manually resolve a reconciliation exception"""

        exception = self.exceptions.get(exception_id)
        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        exception.status = ReconciliationStatus.RESOLVED
        exception.resolution = resolution
        exception.resolved_by = resolved_by
        exception.resolved_at = datetime.utcnow()

        await self.audit_log.log(
            AuditEventType.EXCEPTION_RESOLVED,
            "exception",
            exception_id,
            description=f"Manually resolved by {resolved_by}: {resolution}",
        )

        return exception


# =============================================================================
# AUDIT TRAIL
# =============================================================================

class AuditTrail:
    """
    SOX-compliant audit trail with immutable logging.
    Supports regulatory audits and dispute documentation.
    """

    def __init__(self):
        self.entries: List[AuditEntry] = []
        self._entry_index: Dict[str, AuditEntry] = {}
        self._chain_hash: str = "GENESIS"

    async def log(
        self,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        user_id: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log an audit event"""

        audit_id = f"AUD-{uuid.uuid4().hex[:16].upper()}"

        entry = AuditEntry(
            audit_id=audit_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            previous_state=previous_state,
            new_state=new_state,
            description=description,
            metadata=metadata or {},
        )

        # Calculate checksum including chain hash for immutability
        chain_data = f"{self._chain_hash}{entry.audit_id}{entry.timestamp.isoformat()}"
        entry.checksum = hashlib.sha256(chain_data.encode()).hexdigest()[:16]
        self._chain_hash = entry.checksum

        self.entries.append(entry)
        self._entry_index[audit_id] = entry

        logger.info(f"Audit: {event_type.value} - {entity_type}/{entity_id} - {description}")

        return entry

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
    ) -> List[AuditEntry]:
        """Get complete audit history for an entity"""

        return [
            e for e in self.entries
            if e.entity_type == entity_type and e.entity_id == entity_id
        ]

    def get_entries_by_type(
        self,
        event_type: AuditEventType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditEntry]:
        """Get audit entries by event type and date range"""

        entries = [e for e in self.entries if e.event_type == event_type]

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return entries

    def generate_audit_report(
        self,
        start_date: date,
        end_date: date,
        entity_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate audit report for regulatory compliance"""

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        entries = [
            e for e in self.entries
            if start_dt <= e.timestamp <= end_dt
        ]

        if entity_type:
            entries = [e for e in entries if e.entity_type == entity_type]

        # Count by event type
        by_type = defaultdict(int)
        for entry in entries:
            by_type[entry.event_type.value] += 1

        # Count by entity type
        by_entity = defaultdict(int)
        for entry in entries:
            by_entity[entry.entity_type] += 1

        return {
            "report_date": date.today().isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_entries": len(entries),
            "by_event_type": dict(by_type),
            "by_entity_type": dict(by_entity),
            "chain_integrity": self.verify_chain_integrity(),
            "entries": [
                {
                    "audit_id": e.audit_id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "description": e.description,
                    "checksum": e.checksum,
                }
                for e in entries[:100]  # Limit to first 100 for report
            ],
        }

    def verify_chain_integrity(self) -> bool:
        """Verify audit trail has not been tampered with"""

        if not self.entries:
            return True

        chain_hash = "GENESIS"

        for entry in self.entries:
            expected = hashlib.sha256(
                f"{chain_hash}{entry.audit_id}{entry.timestamp.isoformat()}".encode()
            ).hexdigest()[:16]

            if entry.checksum != expected:
                logger.error(f"Chain integrity violation at {entry.audit_id}")
                return False

            chain_hash = entry.checksum

        return True

    def export_for_dispute(
        self,
        account_id: str,
    ) -> Dict[str, Any]:
        """Export audit trail for dispute documentation"""

        # Get all entries related to this account
        account_entries = [
            e for e in self.entries
            if e.entity_id == account_id or
            (e.metadata and e.metadata.get("account_id") == account_id)
        ]

        return {
            "account_id": account_id,
            "export_date": datetime.utcnow().isoformat(),
            "entry_count": len(account_entries),
            "chain_verified": self.verify_chain_integrity(),
            "timeline": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event": e.event_type.value,
                    "description": e.description,
                    "previous_state": e.previous_state,
                    "new_state": e.new_state,
                    "checksum": e.checksum,
                }
                for e in sorted(account_entries, key=lambda x: x.timestamp)
            ],
        }


# =============================================================================
# REPORTING ENGINE
# =============================================================================

class FinancialReportingEngine:
    """
    Comprehensive financial reporting suite.
    Generates daily, weekly, monthly, quarterly, and annual reports.
    """

    def __init__(
        self,
        payment_engine: PaymentReconciliationEngine,
        settlement_engine: SettlementAccountingEngine,
        portfolio_engine: PortfolioAccountingEngine,
        trust_engine: TrustAccountingEngine,
    ):
        self.payment_engine = payment_engine
        self.settlement_engine = settlement_engine
        self.portfolio_engine = portfolio_engine
        self.trust_engine = trust_engine

    def generate_daily_cash_position(
        self,
        report_date: date,
        payments: List[Payment],
        trust_accounts: List[TrustAccount],
    ) -> Dict[str, Any]:
        """Generate daily cash position report"""

        # Filter today's payments
        today_payments = [
            p for p in payments
            if p.payment_date.date() == report_date and p.status == PaymentStatus.APPLIED
        ]

        today_collections = sum(p.amount for p in today_payments)

        # Pending payments (ACH in transit)
        pending_payments = [
            p for p in payments
            if p.status == PaymentStatus.PENDING
        ]
        pending_amount = sum(p.amount for p in pending_payments)

        # Trust balances
        trust_total = sum(t.balance for t in trust_accounts)
        trust_available = sum(t.available_balance for t in trust_accounts)

        return {
            "report_type": "daily_cash_position",
            "report_date": report_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "collections": {
                "today_count": len(today_payments),
                "today_amount": str(today_collections),
                "by_method": self._group_by_method(today_payments),
            },
            "pending": {
                "count": len(pending_payments),
                "amount": str(pending_amount),
            },
            "trust_accounts": {
                "total_balance": str(trust_total),
                "available_balance": str(trust_available),
                "account_count": len(trust_accounts),
            },
            "cash_available": str(trust_available + today_collections),
        }

    def generate_weekly_collection_summary(
        self,
        week_ending: date,
        payments: List[Payment],
        accounts: List[Account],
    ) -> Dict[str, Any]:
        """Generate weekly collection summary"""

        week_start = week_ending - timedelta(days=6)

        week_payments = [
            p for p in payments
            if week_start <= p.payment_date.date() <= week_ending and
            p.status == PaymentStatus.APPLIED
        ]

        total_collected = sum(p.amount for p in week_payments)
        settlement_collected = sum(
            p.amount for p in week_payments if p.is_settlement_payment
        )

        # Compare to prior week
        prior_week_start = week_start - timedelta(days=7)
        prior_week_end = week_ending - timedelta(days=7)

        prior_payments = [
            p for p in payments
            if prior_week_start <= p.payment_date.date() <= prior_week_end and
            p.status == PaymentStatus.APPLIED
        ]
        prior_collected = sum(p.amount for p in prior_payments)

        wow_change = (
            float((total_collected - prior_collected) / prior_collected * 100)
            if prior_collected else 0
        )

        # Daily breakdown
        daily_breakdown = {}
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_payments = [
                p for p in week_payments if p.payment_date.date() == day
            ]
            daily_breakdown[day.isoformat()] = {
                "count": len(day_payments),
                "amount": str(sum(p.amount for p in day_payments)),
            }

        return {
            "report_type": "weekly_collection_summary",
            "week_ending": week_ending.isoformat(),
            "week_start": week_start.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_collected": str(total_collected),
                "payment_count": len(week_payments),
                "average_payment": str(
                    (total_collected / len(week_payments)).quantize(Decimal("0.01"))
                    if week_payments else Decimal("0")
                ),
                "settlement_collected": str(settlement_collected),
                "regular_collected": str(total_collected - settlement_collected),
            },
            "comparison": {
                "prior_week_collected": str(prior_collected),
                "wow_change_percent": round(wow_change, 2),
            },
            "daily_breakdown": daily_breakdown,
            "by_payment_method": self._group_by_method(week_payments),
        }

    def generate_monthly_client_report(
        self,
        client_id: str,
        report_month: date,
        payments: List[Payment],
        accounts: List[Account],
        settlements: List[Settlement],
    ) -> Dict[str, Any]:
        """Generate monthly client report"""

        # Filter for client
        client_accounts = [a for a in accounts if a.client_id == client_id]
        client_account_ids = {a.account_id for a in client_accounts}

        client_payments = [
            p for p in payments
            if p.account_id in client_account_ids and
            p.payment_date.year == report_month.year and
            p.payment_date.month == report_month.month and
            p.status == PaymentStatus.APPLIED
        ]

        client_settlements = [
            s for s in settlements
            if s.client_id == client_id and
            s.is_completed and s.completed_at and
            s.completed_at.year == report_month.year and
            s.completed_at.month == report_month.month
        ]

        # Calculate metrics
        total_collected = sum(p.amount for p in client_payments)
        total_placed = sum(a.original_balance for a in client_accounts)
        total_outstanding = sum(
            a.current_balance for a in client_accounts
            if a.status not in ["written_off", "paid_in_full"]
        )

        # Settlement metrics
        settlement_original = sum(s.original_balance for s in client_settlements)
        settlement_collected = sum(s.amount_collected for s in client_settlements)
        settlement_discount = sum(s.discount_amount for s in client_settlements)

        return {
            "report_type": "monthly_client_report",
            "client_id": client_id,
            "report_month": report_month.strftime("%Y-%m"),
            "generated_at": datetime.utcnow().isoformat(),
            "portfolio_summary": {
                "total_accounts": len(client_accounts),
                "active_accounts": len([a for a in client_accounts if a.status == "active"]),
                "total_placed": str(total_placed),
                "total_outstanding": str(total_outstanding),
                "collection_rate": round(
                    float(total_collected / total_placed * 100) if total_placed else 0, 2
                ),
            },
            "collection_summary": {
                "total_collected": str(total_collected),
                "payment_count": len(client_payments),
                "average_payment": str(
                    (total_collected / len(client_payments)).quantize(Decimal("0.01"))
                    if client_payments else Decimal("0")
                ),
            },
            "settlement_summary": {
                "settlement_count": len(client_settlements),
                "original_balance": str(settlement_original),
                "amount_collected": str(settlement_collected),
                "total_discount": str(settlement_discount),
                "average_discount_rate": round(
                    float(settlement_discount / settlement_original * 100)
                    if settlement_original else 0, 2
                ),
            },
            "aging_analysis": self.portfolio_engine.calculate_aging_analysis(client_accounts),
        }

    def generate_quarterly_portfolio_analytics(
        self,
        quarter_end: date,
        accounts: List[Account],
        payments: List[Payment],
        settlements: List[Settlement],
    ) -> Dict[str, Any]:
        """Generate quarterly portfolio analytics"""

        # Calculate quarter bounds
        quarter_month = ((quarter_end.month - 1) // 3) * 3 + 1
        quarter_start = date(quarter_end.year, quarter_month, 1)

        # Filter for quarter
        quarter_payments = [
            p for p in payments
            if quarter_start <= p.payment_date.date() <= quarter_end and
            p.status == PaymentStatus.APPLIED
        ]

        quarter_settlements = [
            s for s in settlements
            if s.is_completed and s.completed_at and
            quarter_start <= s.completed_at.date() <= quarter_end
        ]

        # Calculate KPIs
        total_collected = sum(p.amount for p in quarter_payments)
        total_balance = sum(
            a.current_balance for a in accounts
            if a.status not in ["written_off", "paid_in_full"]
        )

        # Recovery rate
        recovery_metrics = self.settlement_engine.calculate_recovery_rate(
            settlements, quarter_start, quarter_end
        )

        # Reserve analysis
        reserves = self.portfolio_engine.calculate_reserves(accounts)

        return {
            "report_type": "quarterly_portfolio_analytics",
            "quarter": f"Q{(quarter_end.month - 1) // 3 + 1} {quarter_end.year}",
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": quarter_end.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "portfolio_metrics": {
                "total_accounts": len(accounts),
                "active_accounts": len([a for a in accounts if a.status == "active"]),
                "total_outstanding": str(total_balance),
                "average_balance": str(
                    (total_balance / len(accounts)).quantize(Decimal("0.01"))
                    if accounts else Decimal("0")
                ),
            },
            "collection_metrics": {
                "total_collected": str(total_collected),
                "payment_count": len(quarter_payments),
                "settlement_count": len(quarter_settlements),
            },
            "recovery_metrics": recovery_metrics,
            "reserve_analysis": reserves,
            "aging_analysis": self.portfolio_engine.calculate_aging_analysis(accounts),
        }

    def generate_annual_compliance_report(
        self,
        report_year: int,
        audit_trail: AuditTrail,
        trust_accounts: List[TrustAccount],
        settlements: List[Settlement],
    ) -> Dict[str, Any]:
        """Generate annual compliance report"""

        year_start = date(report_year, 1, 1)
        year_end = date(report_year, 12, 31)

        # Audit trail analysis
        audit_report = audit_trail.generate_audit_report(year_start, year_end)

        # 1099-C tracking
        form_1099c_required = [
            s for s in settlements
            if s.requires_1099c and s.is_completed and
            s.completed_at and s.completed_at.year == report_year
        ]
        form_1099c_issued = [s for s in form_1099c_required if s.form_1099c_issued]

        # Trust compliance
        trust_compliance = {
            "total_accounts": len(trust_accounts),
            "compliant_accounts": len([t for t in trust_accounts if t.is_compliant]),
            "non_compliant_accounts": len([t for t in trust_accounts if not t.is_compliant]),
        }

        return {
            "report_type": "annual_compliance_report",
            "report_year": report_year,
            "generated_at": datetime.utcnow().isoformat(),
            "audit_summary": {
                "total_audit_entries": audit_report["total_entries"],
                "by_event_type": audit_report["by_event_type"],
                "chain_integrity_verified": audit_report["chain_integrity"],
            },
            "form_1099c_compliance": {
                "total_required": len(form_1099c_required),
                "total_issued": len(form_1099c_issued),
                "pending_issuance": len(form_1099c_required) - len(form_1099c_issued),
                "total_forgiveness_amount": str(
                    sum(s.discount_amount for s in form_1099c_required)
                ),
            },
            "trust_account_compliance": trust_compliance,
            "regulatory_summary": {
                "fdcpa_compliant": trust_compliance["non_compliant_accounts"] == 0,
                "sox_compliant": audit_report["chain_integrity"],
                "irs_compliant": len(form_1099c_required) == len(form_1099c_issued),
            },
        }

    def _group_by_method(self, payments: List[Payment]) -> Dict[str, Dict[str, Any]]:
        """Group payments by payment method"""

        by_method = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})

        for payment in payments:
            by_method[payment.payment_method]["count"] += 1
            by_method[payment.payment_method]["amount"] += payment.amount

        return {
            method: {
                "count": data["count"],
                "amount": str(data["amount"]),
            }
            for method, data in by_method.items()
        }


# =============================================================================
# INTEGRATED RECONCILIATION PIPELINE
# =============================================================================

class FinancialReconciliationPipeline:
    """
    Integrated financial reconciliation pipeline.
    Orchestrates all components for end-to-end financial operations.
    """

    def __init__(self):
        # Initialize core components
        self.audit_log = AuditTrail()

        self.payment_engine = PaymentReconciliationEngine()
        self.payment_engine.audit_log = self.audit_log

        self.settlement_engine = SettlementAccountingEngine(self.audit_log)
        self.trust_engine = TrustAccountingEngine(self.audit_log)
        self.portfolio_engine = PortfolioAccountingEngine(self.audit_log)
        self.reconciliation_engine = ReconciliationEngine(self.audit_log)

        self.remittance_engine = CreditorRemittanceEngine(
            self.settlement_engine,
            self.trust_engine,
            self.audit_log,
        )

        self.reporting_engine = FinancialReportingEngine(
            self.payment_engine,
            self.settlement_engine,
            self.portfolio_engine,
            self.trust_engine,
        )

        logger.info("Financial Reconciliation Pipeline initialized")

    def register_account(self, account: Account) -> None:
        """Register an account in the system"""
        self.payment_engine.accounts[account.account_id] = account

    def register_settlement(self, settlement: Settlement) -> None:
        """Register a settlement in the system"""
        self.payment_engine.settlements[settlement.settlement_id] = settlement
        self.settlement_engine.settlements[settlement.settlement_id] = settlement

    def register_payment_plan(self, plan: PaymentPlan) -> None:
        """Register a payment plan in the system"""
        self.payment_engine.payment_plans[plan.plan_id] = plan

    async def process_incoming_payment(
        self,
        amount: Decimal,
        account_id: Optional[str] = None,
        payment_method: str = "ach",
        **kwargs,
    ) -> Payment:
        """Process an incoming payment through the pipeline"""
        return await self.payment_engine.receive_payment(
            amount=amount,
            account_id=account_id,
            payment_method=payment_method,
            **kwargs,
        )

    async def run_daily_reconciliation(
        self,
        bank_transactions: List[Dict[str, Any]],
        processor_transactions: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Run daily reconciliation cycle"""

        results = {
            "reconciliation_date": date.today().isoformat(),
            "bank_reconciliation": None,
            "processor_reconciliations": {},
        }

        # Get all payments
        payments = list(self.payment_engine.payments.values())

        # Bank reconciliation
        bank_result = await self.reconciliation_engine.reconcile_bank_statement(
            statement_date=date.today(),
            bank_transactions=bank_transactions,
            internal_payments=payments,
        )
        results["bank_reconciliation"] = bank_result

        # Processor reconciliations
        for processor_name, transactions in processor_transactions.items():
            proc_result = await self.reconciliation_engine.reconcile_processor(
                processor_name=processor_name,
                processor_transactions=transactions,
                internal_payments=payments,
            )
            results["processor_reconciliations"][processor_name] = proc_result

        return results

    async def generate_client_remittance(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
    ) -> RemittanceReport:
        """Generate remittance report for a client"""

        payments = list(self.payment_engine.payments.values())
        accounts = self.payment_engine.accounts

        return await self.remittance_engine.generate_remittance_report(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            payments=payments,
            accounts=accounts,
        )

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Get current portfolio status"""

        accounts = list(self.payment_engine.accounts.values())

        return {
            "as_of": datetime.utcnow().isoformat(),
            "account_count": len(accounts),
            "aging_analysis": self.portfolio_engine.calculate_aging_analysis(accounts),
            "reserves": self.portfolio_engine.calculate_reserves(accounts),
        }

    def get_audit_report(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Get audit report for period"""
        return self.audit_log.generate_audit_report(start_date, end_date)


# =============================================================================
# DEMONSTRATION
# =============================================================================

async def run_demo():
    """Demonstrate the financial reconciliation pipeline"""

    print("=" * 80)
    print("QUAN FINANCIAL RECONCILIATION PIPELINE - DEMONSTRATION")
    print("=" * 80)

    # Initialize pipeline
    pipeline = FinancialReconciliationPipeline()

    # Create sample accounts
    print("\n[1] REGISTERING SAMPLE ACCOUNTS")
    print("-" * 40)

    accounts = [
        Account(
            account_id="ACC-001",
            client_id="CLIENT-A",
            debtor_id="DBT-001",
            original_balance=Decimal("1500.00"),
            current_balance=Decimal("1500.00"),
            principal_balance=Decimal("1400.00"),
            interest_balance=Decimal("75.00"),
            fees_balance=Decimal("25.00"),
            days_past_due=45,
            creditor_name="First National Bank",
        ),
        Account(
            account_id="ACC-002",
            client_id="CLIENT-A",
            debtor_id="DBT-002",
            original_balance=Decimal("850.00"),
            current_balance=Decimal("850.00"),
            principal_balance=Decimal("850.00"),
            days_past_due=120,
            creditor_name="First National Bank",
        ),
        Account(
            account_id="ACC-003",
            client_id="CLIENT-B",
            debtor_id="DBT-003",
            original_balance=Decimal("2200.00"),
            current_balance=Decimal("2200.00"),
            principal_balance=Decimal("2000.00"),
            interest_balance=Decimal("150.00"),
            fees_balance=Decimal("50.00"),
            days_past_due=200,
            creditor_name="Regional Credit Union",
        ),
    ]

    for account in accounts:
        pipeline.register_account(account)
        print(f"  Registered: {account.account_id} - ${account.current_balance} ({account.days_past_due} DPD)")

    # Create settlement
    print("\n[2] CREATING SETTLEMENT AGREEMENT")
    print("-" * 40)

    settlement = await pipeline.settlement_engine.create_settlement(
        account=accounts[2],
        settlement_amount=Decimal("1320.00"),
        settlement_type="payment_plan",
        expiration_days=30,
    )
    pipeline.register_settlement(settlement)
    accounts[2].active_settlement_id = settlement.settlement_id

    print(f"  Settlement ID: {settlement.settlement_id}")
    print(f"  Original Balance: ${settlement.original_balance}")
    print(f"  Settlement Amount: ${settlement.settlement_amount}")
    print(f"  Discount: ${settlement.discount_amount} ({settlement.discount_percentage:.1f}%)")
    print(f"  Requires 1099-C: {settlement.requires_1099c}")

    # Create payment plan
    print("\n[3] CREATING PAYMENT PLAN")
    print("-" * 40)

    plan = PaymentPlan(
        plan_id="PLAN-001",
        account_id="ACC-003",
        settlement_id=settlement.settlement_id,
        total_amount=Decimal("1320.00"),
        down_payment=Decimal("320.00"),
        monthly_amount=Decimal("200.00"),
        num_payments=6,
        start_date=date.today(),
        next_due_date=date.today(),
    )
    pipeline.register_payment_plan(plan)
    accounts[2].active_plan_id = plan.plan_id

    print(f"  Plan ID: {plan.plan_id}")
    print(f"  Down Payment: ${plan.down_payment}")
    print(f"  Monthly Amount: ${plan.monthly_amount}")
    print(f"  Number of Payments: {plan.num_payments}")

    # Process payments
    print("\n[4] PROCESSING PAYMENTS")
    print("-" * 40)

    # Regular payment
    payment1 = await pipeline.process_incoming_payment(
        amount=Decimal("250.00"),
        account_id="ACC-001",
        payment_method="card",
        processor_reference="STRIPE-12345",
        metadata={"payer_name": "John Smith", "last_four": "4242"},
    )
    print(f"  Payment 1: ${payment1.amount} to {payment1.account_id} via {payment1.payment_method}")
    print(f"    Status: {payment1.status.value}")
    print(f"    Account Balance: ${accounts[0].current_balance}")

    # Settlement down payment
    payment2 = await pipeline.process_incoming_payment(
        amount=Decimal("320.00"),
        account_id="ACC-003",
        payment_method="ach",
        processor_reference="ACH-67890",
    )
    payment2.is_settlement_payment = True
    payment2.settlement_id = settlement.settlement_id
    payment2.payment_plan_id = plan.plan_id
    print(f"\n  Payment 2 (Settlement Down Payment): ${payment2.amount} to {payment2.account_id}")
    print(f"    Settlement Progress: ${settlement.amount_collected} / ${settlement.settlement_amount}")

    # Unmatched payment (will try auto-match)
    payment3 = await pipeline.process_incoming_payment(
        amount=Decimal("100.00"),
        payment_method="check",
        metadata={"memo": "ACC-002 payment"},
    )
    print(f"\n  Payment 3 (Auto-matched): ${payment3.amount}")
    print(f"    Matched to: {payment3.account_id}")

    # Create trust account
    print("\n[5] TRUST ACCOUNTING")
    print("-" * 40)

    trust = pipeline.trust_engine.create_trust_account(
        client_id="CLIENT-A",
        account_name="First National Bank Trust",
        minimum_balance=Decimal("100.00"),
    )
    print(f"  Trust Account: {trust.trust_id}")
    print(f"  Client: {trust.client_id}")

    # Deposit to trust
    deposit = await pipeline.trust_engine.deposit(
        trust_id=trust.trust_id,
        amount=Decimal("670.00"),
        source="collections",
        reference="Daily sweep",
    )
    print(f"  Deposit: ${deposit['amount']} - Balance: ${trust.balance}")

    # Withdrawal for remittance
    withdrawal = await pipeline.trust_engine.withdraw(
        trust_id=trust.trust_id,
        amount=Decimal("500.00"),
        purpose="client_remittance",
        destination="CLIENT-A ACH",
        reference="Weekly remittance",
    )
    print(f"  Withdrawal: ${withdrawal['amount']} - Balance: ${trust.balance}")

    # Bank reconciliation
    print("\n[6] BANK RECONCILIATION")
    print("-" * 40)

    bank_transactions = [
        {"reference": "STRIPE-12345", "amount": "250.00", "date": date.today().isoformat()},
        {"reference": "ACH-67890", "amount": "320.00", "date": date.today().isoformat()},
        {"reference": "CHECK-99999", "amount": "100.00", "date": date.today().isoformat()},
        {"reference": "UNKNOWN-111", "amount": "75.00", "date": date.today().isoformat()},
    ]

    recon_result = await pipeline.reconciliation_engine.reconcile_bank_statement(
        statement_date=date.today(),
        bank_transactions=bank_transactions,
        internal_payments=list(pipeline.payment_engine.payments.values()),
    )

    print(f"  Reconciliation ID: {recon_result['reconciliation_id']}")
    print(f"  Matched: {recon_result['summary']['matched']}")
    print(f"  Unmatched Bank: {recon_result['summary']['unmatched_bank']}")
    print(f"  Exceptions: {recon_result['summary']['exceptions']}")

    # Generate remittance report
    print("\n[7] CREDITOR REMITTANCE")
    print("-" * 40)

    remittance = await pipeline.generate_client_remittance(
        client_id="CLIENT-A",
        period_start=date.today() - timedelta(days=7),
        period_end=date.today(),
    )

    print(f"  Report ID: {remittance.report_id}")
    print(f"  Client: {remittance.client_id}")
    print(f"  Gross Collections: ${remittance.gross_collections}")
    print(f"  Agency Fees: ${remittance.agency_fees}")
    print(f"  Net Remittance: ${remittance.net_remittance}")

    # Portfolio analysis
    print("\n[8] PORTFOLIO ANALYSIS")
    print("-" * 40)

    aging = pipeline.portfolio_engine.calculate_aging_analysis(accounts)
    print(f"  Total Balance: ${aging['total_balance']}")
    print(f"  Total Accounts: {aging['total_accounts']}")
    print("  Aging Buckets:")
    for bucket, data in aging['buckets'].items():
        if data['count'] > 0:
            print(f"    {bucket}: {data['count']} accounts, ${data['balance']} ({data['percentage']}%)")

    reserves = pipeline.portfolio_engine.calculate_reserves(accounts)
    print(f"\n  Total Reserve: ${reserves['total_reserve']}")
    print(f"  Reserve Rate: {reserves['reserve_rate']}%")

    # Mark-to-market valuation
    print("\n[9] PORTFOLIO VALUATION")
    print("-" * 40)

    valuation = await pipeline.portfolio_engine.mark_to_market_valuation(
        portfolio_id="PORTFOLIO-001",
        accounts=accounts,
        market_discount_rate=Decimal("0.15"),
    )

    print(f"  Gross Carrying Value: ${valuation['gross_carrying_value']}")
    print(f"  Expected Collections: ${valuation['expected_collections']}")
    print(f"  Fair Value: ${valuation['fair_value']}")
    print(f"  Impairment: ${valuation['impairment']} ({valuation['impairment_rate']}%)")

    # Daily cash position report
    print("\n[10] DAILY CASH POSITION REPORT")
    print("-" * 40)

    cash_report = pipeline.reporting_engine.generate_daily_cash_position(
        report_date=date.today(),
        payments=list(pipeline.payment_engine.payments.values()),
        trust_accounts=[trust],
    )

    print(f"  Today's Collections: ${cash_report['collections']['today_amount']}")
    print(f"  Payment Count: {cash_report['collections']['today_count']}")
    print(f"  Trust Balance: ${cash_report['trust_accounts']['total_balance']}")
    print(f"  Cash Available: ${cash_report['cash_available']}")

    # Audit trail verification
    print("\n[11] AUDIT TRAIL VERIFICATION")
    print("-" * 40)

    audit_report = pipeline.get_audit_report(
        start_date=date.today() - timedelta(days=1),
        end_date=date.today(),
    )

    print(f"  Total Audit Entries: {audit_report['total_entries']}")
    print(f"  Chain Integrity: {'VERIFIED' if audit_report['chain_integrity'] else 'FAILED'}")
    print("  Events by Type:")
    for event_type, count in audit_report['by_event_type'].items():
        print(f"    {event_type}: {count}")

    # Payment reversal demonstration
    print("\n[12] PAYMENT REVERSAL (NSF)")
    print("-" * 40)

    print(f"  Account balance before reversal: ${accounts[1].current_balance}")

    reversal_result = await pipeline.payment_engine.reverse_payment(
        payment_id=payment3.payment_id,
        reason="NSF - Insufficient funds",
    )

    print(f"  Reversed Payment: {reversal_result['payment_id']}")
    print(f"  Reason: {reversal_result['reason']}")
    print(f"  New Account Balance: {reversal_result['new_account_balance']}")

    # Final summary
    print("\n" + "=" * 80)
    print("PIPELINE DEMONSTRATION COMPLETE")
    print("=" * 80)

    status = pipeline.get_portfolio_status()
    print(f"\nFinal Portfolio Status:")
    print(f"  Total Accounts: {status['account_count']}")
    print(f"  Total Outstanding: ${status['aging_analysis']['total_balance']}")
    print(f"  Total Reserves: ${status['reserves']['total_reserve']}")

    # Verify audit chain one more time
    print(f"\nAudit Chain Integrity: {'VERIFIED' if pipeline.audit_log.verify_chain_integrity() else 'COMPROMISED'}")
    print(f"Total Audit Entries: {len(pipeline.audit_log.entries)}")

    return pipeline


if __name__ == "__main__":
    asyncio.run(run_demo())
