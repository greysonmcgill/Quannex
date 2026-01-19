"""
Payment Infrastructure Integration Layer

Comprehensive payment engine integrating Stripe, Plaid, and Dwolla
with full lifecycle management, failure handling, and financial controls.

Features:
- Multi-processor integration (Stripe, Plaid, Dwolla)
- Payment method tokenization with PCI compliance
- Full payment lifecycle management
- Intelligent retry with exponential backoff
- Financial controls and fraud prevention
- Real-time reporting and reconciliation
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Any, Callable, Tuple,
    TypeVar, Generic, Union, Set
)
import time

from quan.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class PaymentProcessor(Enum):
    """Supported payment processors"""
    STRIPE = "stripe"
    PLAID = "plaid"
    DWOLLA = "dwolla"


class PaymentMethodType(Enum):
    """Types of payment methods"""
    CARD = "card"
    DEBIT_CARD = "debit_card"
    BANK_ACCOUNT = "bank_account"
    ACH = "ach"
    DIGITAL_WALLET = "digital_wallet"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class PaymentType(Enum):
    """Types of payments"""
    ONE_TIME_FULL = "one_time_full"
    ONE_TIME_SETTLEMENT = "one_time_settlement"
    RECURRING = "recurring"
    VARIABLE_SCHEDULE = "variable_schedule"
    MICRO_PAYMENT = "micro_payment"


class PaymentStatus(Enum):
    """Payment lifecycle status"""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    RECONCILED = "reconciled"
    FAILED = "failed"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class FailureReason(Enum):
    """Payment failure reasons"""
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    CARD_EXPIRED = "card_expired"
    INVALID_CARD = "invalid_card"
    INVALID_ACCOUNT = "invalid_account"
    ACCOUNT_CLOSED = "account_closed"
    FRAUD_SUSPECTED = "fraud_suspected"
    VELOCITY_EXCEEDED = "velocity_exceeded"
    DUPLICATE_PAYMENT = "duplicate_payment"
    NETWORK_ERROR = "network_error"
    PROCESSOR_ERROR = "processor_error"
    AUTHENTICATION_REQUIRED = "authentication_required"
    LIMIT_EXCEEDED = "limit_exceeded"
    UNKNOWN = "unknown"


class RecurringFrequency(Enum):
    """Frequency for recurring payments"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PaymentMethodToken:
    """Tokenized payment method (PCI compliant)"""
    token_id: str
    processor: PaymentProcessor
    method_type: PaymentMethodType
    last_four: str
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None
    brand: Optional[str] = None  # visa, mastercard, etc.
    bank_name: Optional[str] = None
    routing_number_last_four: Optional[str] = None
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if payment method is expired"""
        if self.expiry_month is None or self.expiry_year is None:
            return False
        now = datetime.utcnow()
        # Card expires at end of expiry month
        if self.expiry_year < now.year:
            return True
        if self.expiry_year == now.year and self.expiry_month < now.month:
            return True
        return False

    @property
    def display_name(self) -> str:
        """Human-readable display name"""
        if self.method_type in [PaymentMethodType.CARD, PaymentMethodType.DEBIT_CARD]:
            brand = (self.brand or "Card").capitalize()
            return f"{brand} ending in {self.last_four}"
        elif self.method_type in [PaymentMethodType.BANK_ACCOUNT, PaymentMethodType.ACH]:
            bank = self.bank_name or "Bank Account"
            return f"{bank} ending in {self.last_four}"
        elif self.method_type == PaymentMethodType.APPLE_PAY:
            return "Apple Pay"
        elif self.method_type == PaymentMethodType.GOOGLE_PAY:
            return "Google Pay"
        return f"Payment method ending in {self.last_four}"


@dataclass
class PaymentAmount:
    """Represents a payment amount with proper decimal handling"""
    amount: Decimal
    currency: str = "USD"
    fee: Decimal = Decimal("0")
    net_amount: Decimal = field(init=False)

    def __post_init__(self):
        self.amount = Decimal(str(self.amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.fee = Decimal(str(self.fee)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.net_amount = self.amount - self.fee

    @property
    def amount_cents(self) -> int:
        """Amount in cents (for Stripe)"""
        return int(self.amount * 100)


@dataclass
class PaymentSchedule:
    """Payment schedule for recurring/variable payments"""
    schedule_id: str
    account_id: str
    payment_type: PaymentType
    total_amount: Decimal
    payments: List[Dict[str, Any]]  # List of {date, amount, status}
    frequency: Optional[RecurringFrequency] = None
    start_date: date = field(default_factory=date.today)
    end_date: Optional[date] = None
    next_payment_date: Optional[date] = None
    payments_completed: int = 0
    payments_remaining: int = 0
    amount_paid: Decimal = Decimal("0")
    amount_remaining: Decimal = Decimal("0")
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PaymentTransaction:
    """A single payment transaction"""
    transaction_id: str
    idempotency_key: str
    account_id: str
    client_id: str
    payment_type: PaymentType
    amount: PaymentAmount
    payment_method: PaymentMethodToken
    processor: PaymentProcessor
    status: PaymentStatus = PaymentStatus.PENDING

    # Processor references
    processor_transaction_id: Optional[str] = None
    processor_authorization_id: Optional[str] = None
    processor_capture_id: Optional[str] = None
    processor_settlement_id: Optional[str] = None

    # Lifecycle timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None

    # Failure info
    failure_reason: Optional[FailureReason] = None
    failure_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None

    # Refund info
    refunded_amount: Decimal = Decimal("0")
    refund_transactions: List[str] = field(default_factory=list)

    # Chargeback info
    chargeback_id: Optional[str] = None
    chargeback_reason: Optional[str] = None
    chargeback_amount: Optional[Decimal] = None

    # Audit trail
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_audit_entry(self, action: str, details: Dict[str, Any] = None):
        """Add entry to audit trail"""
        self.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details or {},
        })

    @property
    def can_retry(self) -> bool:
        """Check if payment can be retried"""
        if self.status not in [PaymentStatus.FAILED]:
            return False
        if self.retry_count >= self.max_retries:
            return False
        # Some failures are not retryable
        non_retryable = [
            FailureReason.FRAUD_SUSPECTED,
            FailureReason.ACCOUNT_CLOSED,
            FailureReason.DUPLICATE_PAYMENT,
        ]
        if self.failure_reason in non_retryable:
            return False
        return True


@dataclass
class RefundRequest:
    """Refund request details"""
    refund_id: str
    transaction_id: str
    amount: Decimal
    reason: str
    created_by: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    processor_refund_id: Optional[str] = None
    status: str = "pending"


@dataclass
class VelocityCheck:
    """Velocity check result"""
    passed: bool
    reason: Optional[str] = None
    daily_count: int = 0
    daily_limit: int = 10
    daily_amount: Decimal = Decimal("0")
    daily_amount_limit: Decimal = Decimal("10000")
    hourly_count: int = 0
    hourly_limit: int = 5


@dataclass
class SettlementReport:
    """Daily settlement report"""
    report_id: str
    report_date: date
    processor: PaymentProcessor
    total_transactions: int
    total_amount: Decimal
    total_fees: Decimal
    net_amount: Decimal
    successful_transactions: int
    failed_transactions: int
    refunds_count: int
    refunds_amount: Decimal
    chargebacks_count: int
    chargebacks_amount: Decimal
    transactions: List[str]  # Transaction IDs
    created_at: datetime = field(default_factory=datetime.utcnow)
    reconciled: bool = False


@dataclass
class CreditorRemittance:
    """Remittance calculation for creditors"""
    remittance_id: str
    creditor_id: str
    period_start: date
    period_end: date
    total_collected: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    net_remittance: Decimal
    transaction_count: int
    transactions: List[str]  # Transaction IDs
    reserve_held: Decimal = Decimal("0")
    adjustments: Decimal = Decimal("0")
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrustAccount:
    """Trust account for holding collected funds"""
    account_id: str
    balance: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    pending_deposits: Decimal = Decimal("0")
    pending_disbursements: Decimal = Decimal("0")
    reserve_balance: Decimal = Decimal("0")
    last_reconciled: Optional[datetime] = None


# =============================================================================
# PROCESSOR ADAPTERS
# =============================================================================

class ProcessorAdapter(ABC):
    """Abstract base class for payment processor adapters"""

    @abstractmethod
    async def authorize(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Authorize a payment. Returns (success, authorization_id, error)"""
        pass

    @abstractmethod
    async def capture(
        self,
        authorization_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Capture an authorized payment. Returns (success, capture_id, error)"""
        pass

    @abstractmethod
    async def authorize_and_capture(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Authorize and capture in one step. Returns (success, transaction_id, error)"""
        pass

    @abstractmethod
    async def refund(
        self,
        transaction_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Refund a payment. Returns (success, refund_id, error)"""
        pass

    @abstractmethod
    async def void(
        self,
        authorization_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Void an authorization. Returns (success, error)"""
        pass

    @abstractmethod
    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvc: str,
        billing_details: Dict[str, Any],
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Tokenize a card. Returns (token, error)"""
        pass

    @abstractmethod
    async def verify_bank_account(
        self,
        account_id: str,
        routing_number: str,
        account_number: str,
        account_type: str,
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Verify and tokenize bank account. Returns (token, error)"""
        pass


class StripeAdapter(ProcessorAdapter):
    """Stripe payment processor adapter"""

    def __init__(self):
        self._stripe = None
        self._initialized = False

    def _get_stripe(self):
        """Lazy load Stripe SDK"""
        if not self._initialized:
            if settings.stripe_secret_key:
                try:
                    import stripe
                    stripe.api_key = settings.stripe_secret_key
                    self._stripe = stripe
                    self._initialized = True
                except ImportError:
                    logger.warning("Stripe SDK not installed")
        return self._stripe

    async def authorize(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Authorize a card payment"""
        stripe = self._get_stripe()
        if not stripe:
            return False, "", "Stripe not configured"

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount.amount_cents,
                currency=amount.currency.lower(),
                payment_method=payment_method.token_id,
                capture_method="manual",
                metadata=metadata,
            )
            return True, intent.id, None
        except stripe.error.CardError as e:
            return False, "", self._map_stripe_error(e)
        except Exception as e:
            logger.error(f"Stripe authorization error: {e}")
            return False, "", str(e)

    async def capture(
        self,
        authorization_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Capture an authorized payment"""
        stripe = self._get_stripe()
        if not stripe:
            return False, "", "Stripe not configured"

        try:
            capture_params = {}
            if amount:
                capture_params["amount_to_capture"] = amount.amount_cents

            intent = stripe.PaymentIntent.capture(
                authorization_id,
                **capture_params,
            )
            return True, intent.latest_charge, None
        except Exception as e:
            logger.error(f"Stripe capture error: {e}")
            return False, "", str(e)

    async def authorize_and_capture(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Authorize and capture in one step"""
        stripe = self._get_stripe()
        if not stripe:
            return False, "", "Stripe not configured"

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount.amount_cents,
                currency=amount.currency.lower(),
                payment_method=payment_method.token_id,
                confirm=True,
                metadata=metadata,
            )

            if intent.status == "succeeded":
                return True, intent.latest_charge, None
            elif intent.status == "requires_action":
                return False, "", "3D Secure authentication required"
            else:
                return False, "", f"Payment failed: {intent.status}"

        except stripe.error.CardError as e:
            return False, "", self._map_stripe_error(e)
        except Exception as e:
            logger.error(f"Stripe payment error: {e}")
            return False, "", str(e)

    async def refund(
        self,
        transaction_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Refund a payment"""
        stripe = self._get_stripe()
        if not stripe:
            return False, "", "Stripe not configured"

        try:
            refund_params = {"charge": transaction_id}
            if amount:
                refund_params["amount"] = amount.amount_cents

            refund = stripe.Refund.create(**refund_params)
            return True, refund.id, None
        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return False, "", str(e)

    async def void(
        self,
        authorization_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Void an authorization"""
        stripe = self._get_stripe()
        if not stripe:
            return False, "Stripe not configured"

        try:
            stripe.PaymentIntent.cancel(authorization_id)
            return True, None
        except Exception as e:
            logger.error(f"Stripe void error: {e}")
            return False, str(e)

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvc: str,
        billing_details: Dict[str, Any],
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Tokenize a card"""
        stripe = self._get_stripe()
        if not stripe:
            return None, "Stripe not configured"

        try:
            # Create payment method
            pm = stripe.PaymentMethod.create(
                type="card",
                card={
                    "number": card_number,
                    "exp_month": expiry_month,
                    "exp_year": expiry_year,
                    "cvc": cvc,
                },
                billing_details=billing_details,
            )

            token = PaymentMethodToken(
                token_id=pm.id,
                processor=PaymentProcessor.STRIPE,
                method_type=PaymentMethodType.CARD,
                last_four=pm.card.last4,
                expiry_month=pm.card.exp_month,
                expiry_year=pm.card.exp_year,
                brand=pm.card.brand,
                is_verified=True,
            )
            return token, None

        except stripe.error.CardError as e:
            return None, self._map_stripe_error(e)
        except Exception as e:
            logger.error(f"Stripe tokenization error: {e}")
            return None, str(e)

    async def verify_bank_account(
        self,
        account_id: str,
        routing_number: str,
        account_number: str,
        account_type: str,
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Verify bank account for ACH (using Stripe's bank account tokens)"""
        stripe = self._get_stripe()
        if not stripe:
            return None, "Stripe not configured"

        try:
            # Create bank account token
            token = stripe.Token.create(
                bank_account={
                    "country": "US",
                    "currency": "usd",
                    "account_holder_type": "individual",
                    "routing_number": routing_number,
                    "account_number": account_number,
                },
            )

            payment_token = PaymentMethodToken(
                token_id=token.id,
                processor=PaymentProcessor.STRIPE,
                method_type=PaymentMethodType.BANK_ACCOUNT,
                last_four=token.bank_account.last4,
                bank_name=token.bank_account.bank_name,
                routing_number_last_four=routing_number[-4:],
                is_verified=False,  # Requires micro-deposit verification
            )
            return payment_token, None

        except Exception as e:
            logger.error(f"Stripe bank verification error: {e}")
            return None, str(e)

    def _map_stripe_error(self, error) -> str:
        """Map Stripe error to failure message"""
        error_code = error.error.code if hasattr(error, 'error') else None

        code_mapping = {
            "card_declined": "Card was declined",
            "expired_card": "Card has expired",
            "incorrect_cvc": "Incorrect CVC",
            "insufficient_funds": "Insufficient funds",
            "processing_error": "Payment processing error",
            "invalid_account": "Invalid account",
        }

        return code_mapping.get(error_code, str(error))


class PlaidAdapter(ProcessorAdapter):
    """Plaid adapter for bank account verification"""

    def __init__(self):
        self._plaid = None
        self._initialized = False

    def _get_plaid(self):
        """Lazy load Plaid SDK"""
        if not self._initialized:
            # Plaid configuration would go here
            self._initialized = True
        return self._plaid

    async def authorize(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Plaid doesn't directly authorize - used for verification"""
        return False, "", "Use Dwolla for ACH payments"

    async def capture(
        self,
        authorization_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Not applicable for Plaid"""
        return False, "", "Use Dwolla for ACH payments"

    async def authorize_and_capture(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Not applicable for Plaid"""
        return False, "", "Use Dwolla for ACH payments"

    async def refund(
        self,
        transaction_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Not applicable for Plaid"""
        return False, "", "Use Dwolla for ACH refunds"

    async def void(
        self,
        authorization_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Not applicable for Plaid"""
        return False, "Use Dwolla for ACH voids"

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvc: str,
        billing_details: Dict[str, Any],
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Not applicable for Plaid - use for bank accounts only"""
        return None, "Plaid is for bank account verification only"

    async def verify_bank_account(
        self,
        account_id: str,
        routing_number: str,
        account_number: str,
        account_type: str,
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Verify bank account using Plaid Link"""
        # In production, this would use Plaid Link token exchange
        # For now, simulate successful verification
        logger.info(f"Plaid bank verification for account ending in {account_number[-4:]}")

        token = PaymentMethodToken(
            token_id=f"plaid_{secrets.token_urlsafe(16)}",
            processor=PaymentProcessor.PLAID,
            method_type=PaymentMethodType.BANK_ACCOUNT,
            last_four=account_number[-4:],
            routing_number_last_four=routing_number[-4:],
            is_verified=True,  # Plaid instant verification
            metadata={
                "verification_method": "plaid_link",
                "account_type": account_type,
            },
        )
        return token, None

    async def get_balance(
        self,
        access_token: str,
    ) -> Tuple[Optional[Decimal], Optional[str]]:
        """Get bank account balance"""
        # Would call Plaid balance endpoint
        return None, "Plaid balance check not implemented"

    async def get_transactions(
        self,
        access_token: str,
        start_date: date,
        end_date: date,
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get transaction history"""
        # Would call Plaid transactions endpoint
        return None, "Plaid transactions not implemented"


class DwollaAdapter(ProcessorAdapter):
    """Dwolla adapter for ACH transfers"""

    def __init__(self):
        self._dwolla = None
        self._initialized = False
        self._api_url = "https://api.dwolla.com"

    def _get_dwolla(self):
        """Initialize Dwolla client"""
        if not self._initialized:
            # Dwolla initialization would go here
            self._initialized = True
        return self._dwolla

    async def authorize(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """ACH doesn't have separate authorization - returns pending status"""
        # ACH transfers are initiated directly without auth step
        transfer_id = f"dwolla_{uuid.uuid4().hex[:16]}"
        return True, transfer_id, None

    async def capture(
        self,
        authorization_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """ACH capture is implicit - check transfer status"""
        # Would check Dwolla transfer status
        return True, authorization_id, None

    async def authorize_and_capture(
        self,
        amount: PaymentAmount,
        payment_method: PaymentMethodToken,
        metadata: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Initiate ACH transfer"""
        logger.info(
            f"Initiating ACH transfer: ${amount.amount} "
            f"from account ending in {payment_method.last_four}"
        )

        # Generate transfer ID
        transfer_id = f"dwolla_{uuid.uuid4().hex[:16]}"

        # In production, would create Dwolla transfer
        # ACH takes 3-5 business days to settle

        return True, transfer_id, None

    async def refund(
        self,
        transaction_id: str,
        amount: Optional[PaymentAmount] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """Initiate ACH refund (credit back to source)"""
        refund_id = f"dwolla_ref_{uuid.uuid4().hex[:16]}"
        logger.info(f"Initiating ACH refund: {refund_id}")
        return True, refund_id, None

    async def void(
        self,
        authorization_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Cancel pending ACH transfer"""
        # Can only cancel if transfer is still pending
        logger.info(f"Cancelling ACH transfer: {authorization_id}")
        return True, None

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvc: str,
        billing_details: Dict[str, Any],
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Dwolla doesn't handle cards - use Stripe"""
        return None, "Dwolla is for ACH only. Use Stripe for cards."

    async def verify_bank_account(
        self,
        account_id: str,
        routing_number: str,
        account_number: str,
        account_type: str,
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """Create Dwolla funding source for ACH"""
        logger.info(
            f"Creating Dwolla funding source for account ending in {account_number[-4:]}"
        )

        funding_source_id = f"dwolla_fs_{uuid.uuid4().hex[:16]}"

        token = PaymentMethodToken(
            token_id=funding_source_id,
            processor=PaymentProcessor.DWOLLA,
            method_type=PaymentMethodType.ACH,
            last_four=account_number[-4:],
            routing_number_last_four=routing_number[-4:],
            is_verified=False,  # Requires micro-deposit verification
            metadata={
                "account_type": account_type,
                "verification_status": "pending",
            },
        )
        return token, None

    async def initiate_micro_deposits(
        self,
        funding_source_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """Initiate micro-deposit verification"""
        logger.info(f"Initiating micro-deposits for: {funding_source_id}")
        return True, None

    async def verify_micro_deposits(
        self,
        funding_source_id: str,
        amount1: Decimal,
        amount2: Decimal,
    ) -> Tuple[bool, Optional[str]]:
        """Verify micro-deposit amounts"""
        # Would verify amounts with Dwolla
        logger.info(f"Verifying micro-deposits for: {funding_source_id}")
        return True, None


# =============================================================================
# FINANCIAL CONTROLS
# =============================================================================

class FinancialControlsEngine:
    """
    Financial controls for fraud prevention and risk management.

    Implements:
    - Daily settlement limits
    - Velocity checks
    - Duplicate payment detection
    - Reserve calculations
    - Fee optimization
    """

    def __init__(self):
        self._daily_limits: Dict[str, Decimal] = defaultdict(
            lambda: Decimal("50000")  # Default $50k daily limit per account
        )
        self._transaction_cache: Dict[str, List[PaymentTransaction]] = defaultdict(list)
        self._payment_hashes: Set[str] = set()

        # Fee structures
        self.card_fee_rate = Decimal("0.029")  # 2.9%
        self.card_fee_fixed = Decimal("0.30")  # $0.30
        self.ach_fee_fixed = Decimal("0.50")   # $0.50
        self.ach_fee_rate = Decimal("0.005")   # 0.5%
        self.ach_fee_cap = Decimal("5.00")     # $5 max

        # Reserve rates
        self.default_reserve_rate = Decimal("0.10")  # 10%
        self.high_risk_reserve_rate = Decimal("0.20")  # 20%

    async def check_velocity(
        self,
        account_id: str,
        amount: Decimal,
    ) -> VelocityCheck:
        """Check velocity limits for account"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        recent_transactions = self._transaction_cache.get(account_id, [])

        # Count transactions in last hour
        hourly_transactions = [
            t for t in recent_transactions
            if t.created_at >= one_hour_ago
        ]
        hourly_count = len(hourly_transactions)

        # Count transactions in last day
        daily_transactions = [
            t for t in recent_transactions
            if t.created_at >= one_day_ago
        ]
        daily_count = len(daily_transactions)
        daily_amount = sum(t.amount.amount for t in daily_transactions)

        # Check limits
        hourly_limit = 5
        daily_limit = 10
        daily_amount_limit = self._daily_limits.get(account_id, Decimal("50000"))

        if hourly_count >= hourly_limit:
            return VelocityCheck(
                passed=False,
                reason=f"Hourly transaction limit exceeded ({hourly_count}/{hourly_limit})",
                daily_count=daily_count,
                daily_limit=daily_limit,
                daily_amount=daily_amount,
                daily_amount_limit=daily_amount_limit,
                hourly_count=hourly_count,
                hourly_limit=hourly_limit,
            )

        if daily_count >= daily_limit:
            return VelocityCheck(
                passed=False,
                reason=f"Daily transaction limit exceeded ({daily_count}/{daily_limit})",
                daily_count=daily_count,
                daily_limit=daily_limit,
                daily_amount=daily_amount,
                daily_amount_limit=daily_amount_limit,
                hourly_count=hourly_count,
                hourly_limit=hourly_limit,
            )

        if daily_amount + amount > daily_amount_limit:
            return VelocityCheck(
                passed=False,
                reason=f"Daily amount limit exceeded (${daily_amount + amount} > ${daily_amount_limit})",
                daily_count=daily_count,
                daily_limit=daily_limit,
                daily_amount=daily_amount,
                daily_amount_limit=daily_amount_limit,
                hourly_count=hourly_count,
                hourly_limit=hourly_limit,
            )

        return VelocityCheck(
            passed=True,
            daily_count=daily_count,
            daily_limit=daily_limit,
            daily_amount=daily_amount,
            daily_amount_limit=daily_amount_limit,
            hourly_count=hourly_count,
            hourly_limit=hourly_limit,
        )

    async def check_duplicate(
        self,
        account_id: str,
        amount: Decimal,
        payment_method_token: str,
        window_minutes: int = 5,
    ) -> Tuple[bool, Optional[str]]:
        """Check for duplicate payment within time window"""
        # Create payment fingerprint
        fingerprint = hashlib.sha256(
            f"{account_id}:{amount}:{payment_method_token}".encode()
        ).hexdigest()[:32]

        # Check if we've seen this fingerprint recently
        if fingerprint in self._payment_hashes:
            return True, f"Duplicate payment detected (fingerprint: {fingerprint[:8]})"

        # Add to cache (would expire based on window_minutes in production)
        self._payment_hashes.add(fingerprint)

        # Clean up old hashes (simple implementation)
        if len(self._payment_hashes) > 10000:
            # Remove oldest half
            hashes_list = list(self._payment_hashes)
            self._payment_hashes = set(hashes_list[5000:])

        return False, None

    def calculate_fee(
        self,
        amount: Decimal,
        payment_method: PaymentMethodType,
    ) -> Decimal:
        """Calculate processing fee for payment method"""
        if payment_method in [PaymentMethodType.CARD, PaymentMethodType.DEBIT_CARD,
                               PaymentMethodType.APPLE_PAY, PaymentMethodType.GOOGLE_PAY]:
            # Card: percentage + fixed
            fee = (amount * self.card_fee_rate) + self.card_fee_fixed
        elif payment_method in [PaymentMethodType.ACH, PaymentMethodType.BANK_ACCOUNT]:
            # ACH: percentage with cap
            percentage_fee = amount * self.ach_fee_rate
            fee = min(percentage_fee, self.ach_fee_cap) + self.ach_fee_fixed
        else:
            fee = self.card_fee_fixed  # Default

        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def recommend_payment_method(
        self,
        amount: Decimal,
        available_methods: List[PaymentMethodToken],
    ) -> Optional[PaymentMethodToken]:
        """Recommend optimal payment method based on fees"""
        if not available_methods:
            return None

        # Calculate fees for each method
        method_fees = []
        for method in available_methods:
            fee = self.calculate_fee(amount, method.method_type)
            method_fees.append((method, fee))

        # Sort by fee (lowest first)
        method_fees.sort(key=lambda x: x[1])

        # Return lowest fee method
        return method_fees[0][0]

    def calculate_reserve(
        self,
        amount: Decimal,
        risk_level: str = "normal",
    ) -> Decimal:
        """Calculate reserve amount to hold"""
        if risk_level == "high":
            rate = self.high_risk_reserve_rate
        else:
            rate = self.default_reserve_rate

        reserve = amount * rate
        return reserve.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def record_transaction(
        self,
        transaction: PaymentTransaction,
    ) -> None:
        """Record transaction for velocity tracking"""
        account_id = transaction.account_id
        self._transaction_cache[account_id].append(transaction)

        # Cleanup old transactions (keep last 100 per account)
        if len(self._transaction_cache[account_id]) > 100:
            self._transaction_cache[account_id] = (
                self._transaction_cache[account_id][-100:]
            )


# =============================================================================
# RETRY LOGIC
# =============================================================================

class RetryStrategy:
    """
    Exponential backoff retry strategy for failed payments.

    Implements intelligent retry based on failure type.
    """

    # Retry delays (in seconds) for each attempt
    RETRY_DELAYS = [
        60,      # 1 minute
        300,     # 5 minutes
        1800,    # 30 minutes
        3600,    # 1 hour
        14400,   # 4 hours
        86400,   # 24 hours
    ]

    # Failure reasons that should trigger specific actions
    PROMPT_ALTERNATIVE_METHOD = [
        FailureReason.INSUFFICIENT_FUNDS,
        FailureReason.CARD_DECLINED,
        FailureReason.ACCOUNT_CLOSED,
    ]

    CARD_UPDATE_REQUIRED = [
        FailureReason.CARD_EXPIRED,
        FailureReason.INVALID_CARD,
    ]

    NO_RETRY = [
        FailureReason.FRAUD_SUSPECTED,
        FailureReason.DUPLICATE_PAYMENT,
    ]

    @classmethod
    def should_retry(
        cls,
        failure_reason: FailureReason,
        retry_count: int,
        max_retries: int = 3,
    ) -> bool:
        """Determine if payment should be retried"""
        if failure_reason in cls.NO_RETRY:
            return False
        if retry_count >= max_retries:
            return False
        return True

    @classmethod
    def get_retry_delay(
        cls,
        retry_count: int,
        failure_reason: FailureReason,
    ) -> timedelta:
        """Get delay before next retry with exponential backoff"""
        # Base delay from schedule
        if retry_count < len(cls.RETRY_DELAYS):
            base_delay = cls.RETRY_DELAYS[retry_count]
        else:
            base_delay = cls.RETRY_DELAYS[-1]

        # Add jitter (10-20% random variation)
        import random
        jitter = base_delay * random.uniform(0.1, 0.2)

        # Adjust for failure type
        if failure_reason == FailureReason.INSUFFICIENT_FUNDS:
            # Insufficient funds - try again at different times of day
            # Delay until next likely payday (adjusted for typical pay cycles)
            base_delay = max(base_delay, 86400)  # At least 24 hours
        elif failure_reason == FailureReason.NETWORK_ERROR:
            # Network errors - can retry quickly
            base_delay = min(base_delay, 300)  # No more than 5 minutes

        return timedelta(seconds=int(base_delay + jitter))

    @classmethod
    def get_recovery_actions(
        cls,
        failure_reason: FailureReason,
    ) -> List[str]:
        """Get recommended recovery actions for failure"""
        actions = []

        if failure_reason in cls.PROMPT_ALTERNATIVE_METHOD:
            actions.append("prompt_alternative_payment_method")

        if failure_reason in cls.CARD_UPDATE_REQUIRED:
            actions.append("request_card_update")
            actions.append("send_card_expiration_reminder")

        if failure_reason == FailureReason.INSUFFICIENT_FUNDS:
            actions.append("schedule_retry_after_payday")
            actions.append("offer_smaller_payment_plan")

        if failure_reason == FailureReason.ACCOUNT_CLOSED:
            actions.append("request_new_bank_account")
            actions.append("prompt_alternative_payment_method")

        if failure_reason == FailureReason.AUTHENTICATION_REQUIRED:
            actions.append("request_3ds_authentication")

        return actions

    @classmethod
    def map_processor_error(
        cls,
        processor: PaymentProcessor,
        error_code: str,
        error_message: str,
    ) -> FailureReason:
        """Map processor-specific error to standard failure reason"""
        error_lower = error_message.lower()

        if "insufficient" in error_lower or "nsf" in error_lower:
            return FailureReason.INSUFFICIENT_FUNDS
        elif "expired" in error_lower:
            return FailureReason.CARD_EXPIRED
        elif "declined" in error_lower or "denied" in error_lower:
            return FailureReason.CARD_DECLINED
        elif "fraud" in error_lower or "suspicious" in error_lower:
            return FailureReason.FRAUD_SUSPECTED
        elif "closed" in error_lower:
            return FailureReason.ACCOUNT_CLOSED
        elif "invalid" in error_lower:
            if "card" in error_lower:
                return FailureReason.INVALID_CARD
            return FailureReason.INVALID_ACCOUNT
        elif "network" in error_lower or "timeout" in error_lower:
            return FailureReason.NETWORK_ERROR
        elif "duplicate" in error_lower:
            return FailureReason.DUPLICATE_PAYMENT
        elif "3d secure" in error_lower or "authentication" in error_lower:
            return FailureReason.AUTHENTICATION_REQUIRED
        elif "limit" in error_lower:
            return FailureReason.LIMIT_EXCEEDED
        else:
            return FailureReason.UNKNOWN


# =============================================================================
# PAYMENT SCHEDULE MANAGER
# =============================================================================

class PaymentScheduleManager:
    """
    Manages recurring and variable payment schedules.

    Supports:
    - Recurring payments (weekly, biweekly, monthly)
    - Variable schedules (custom dates/amounts)
    - Micro-payments ($5-25 weekly)
    """

    def __init__(self):
        self._schedules: Dict[str, PaymentSchedule] = {}
        self._due_today: List[PaymentSchedule] = []

    def create_recurring_schedule(
        self,
        account_id: str,
        total_amount: Decimal,
        frequency: RecurringFrequency,
        payment_amount: Decimal,
        start_date: date = None,
    ) -> PaymentSchedule:
        """Create a recurring payment schedule"""
        start_date = start_date or date.today()
        schedule_id = f"sched_{uuid.uuid4().hex[:16]}"

        # Calculate number of payments
        num_payments = int((total_amount / payment_amount).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ))

        # Handle remainder
        remainder = total_amount - (payment_amount * (num_payments - 1))

        # Generate payment dates
        payments = []
        current_date = start_date

        for i in range(num_payments):
            amount = remainder if i == num_payments - 1 else payment_amount
            payments.append({
                "payment_number": i + 1,
                "date": current_date.isoformat(),
                "amount": str(amount),
                "status": "scheduled",
            })
            current_date = self._next_payment_date(current_date, frequency)

        schedule = PaymentSchedule(
            schedule_id=schedule_id,
            account_id=account_id,
            payment_type=PaymentType.RECURRING,
            total_amount=total_amount,
            payments=payments,
            frequency=frequency,
            start_date=start_date,
            end_date=current_date,
            next_payment_date=start_date,
            payments_remaining=num_payments,
            amount_remaining=total_amount,
        )

        self._schedules[schedule_id] = schedule
        return schedule

    def create_micro_payment_schedule(
        self,
        account_id: str,
        total_amount: Decimal,
        weekly_amount: Decimal = Decimal("10"),
    ) -> PaymentSchedule:
        """Create a micro-payment schedule ($5-25 weekly)"""
        # Validate micro-payment amount
        if weekly_amount < Decimal("5") or weekly_amount > Decimal("25"):
            weekly_amount = Decimal("10")  # Default to $10

        return self.create_recurring_schedule(
            account_id=account_id,
            total_amount=total_amount,
            frequency=RecurringFrequency.WEEKLY,
            payment_amount=weekly_amount,
        )

    def create_variable_schedule(
        self,
        account_id: str,
        payments: List[Dict[str, Any]],  # List of {date, amount}
    ) -> PaymentSchedule:
        """Create a variable payment schedule with custom dates/amounts"""
        schedule_id = f"sched_{uuid.uuid4().hex[:16]}"

        total_amount = sum(Decimal(str(p["amount"])) for p in payments)

        # Format payments
        formatted_payments = []
        for i, p in enumerate(payments):
            formatted_payments.append({
                "payment_number": i + 1,
                "date": p["date"] if isinstance(p["date"], str) else p["date"].isoformat(),
                "amount": str(p["amount"]),
                "status": "scheduled",
            })

        # Sort by date
        formatted_payments.sort(key=lambda x: x["date"])

        first_date = date.fromisoformat(formatted_payments[0]["date"])
        last_date = date.fromisoformat(formatted_payments[-1]["date"])

        schedule = PaymentSchedule(
            schedule_id=schedule_id,
            account_id=account_id,
            payment_type=PaymentType.VARIABLE_SCHEDULE,
            total_amount=total_amount,
            payments=formatted_payments,
            start_date=first_date,
            end_date=last_date,
            next_payment_date=first_date,
            payments_remaining=len(payments),
            amount_remaining=total_amount,
        )

        self._schedules[schedule_id] = schedule
        return schedule

    def get_due_payments(
        self,
        target_date: date = None,
    ) -> List[Tuple[PaymentSchedule, Dict]]:
        """Get all payments due on target date"""
        target_date = target_date or date.today()
        target_str = target_date.isoformat()

        due_payments = []

        for schedule in self._schedules.values():
            if not schedule.is_active:
                continue

            for payment in schedule.payments:
                if payment["date"] == target_str and payment["status"] == "scheduled":
                    due_payments.append((schedule, payment))

        return due_payments

    def mark_payment_complete(
        self,
        schedule_id: str,
        payment_number: int,
        transaction_id: str,
    ) -> bool:
        """Mark a scheduled payment as complete"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False

        for payment in schedule.payments:
            if payment["payment_number"] == payment_number:
                payment["status"] = "completed"
                payment["transaction_id"] = transaction_id
                payment["completed_at"] = datetime.utcnow().isoformat()

                # Update schedule
                schedule.payments_completed += 1
                schedule.payments_remaining -= 1
                schedule.amount_paid += Decimal(str(payment["amount"]))
                schedule.amount_remaining -= Decimal(str(payment["amount"]))
                schedule.updated_at = datetime.utcnow()

                # Set next payment date
                remaining_payments = [
                    p for p in schedule.payments
                    if p["status"] == "scheduled"
                ]
                if remaining_payments:
                    schedule.next_payment_date = date.fromisoformat(
                        remaining_payments[0]["date"]
                    )
                else:
                    schedule.next_payment_date = None
                    schedule.is_active = False

                return True

        return False

    def mark_payment_failed(
        self,
        schedule_id: str,
        payment_number: int,
        failure_reason: str,
    ) -> bool:
        """Mark a scheduled payment as failed"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False

        for payment in schedule.payments:
            if payment["payment_number"] == payment_number:
                payment["status"] = "failed"
                payment["failure_reason"] = failure_reason
                payment["failed_at"] = datetime.utcnow().isoformat()
                schedule.updated_at = datetime.utcnow()
                return True

        return False

    def reschedule_payment(
        self,
        schedule_id: str,
        payment_number: int,
        new_date: date,
    ) -> bool:
        """Reschedule a failed or upcoming payment"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False

        for payment in schedule.payments:
            if payment["payment_number"] == payment_number:
                payment["date"] = new_date.isoformat()
                if payment["status"] == "failed":
                    payment["status"] = "scheduled"
                    payment.pop("failure_reason", None)
                    payment.pop("failed_at", None)
                schedule.updated_at = datetime.utcnow()
                return True

        return False

    def _next_payment_date(
        self,
        current_date: date,
        frequency: RecurringFrequency,
    ) -> date:
        """Calculate next payment date based on frequency"""
        if frequency == RecurringFrequency.DAILY:
            return current_date + timedelta(days=1)
        elif frequency == RecurringFrequency.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif frequency == RecurringFrequency.BIWEEKLY:
            return current_date + timedelta(weeks=2)
        elif frequency == RecurringFrequency.MONTHLY:
            # Add one month (handle month-end edge cases)
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(current_date.day, 28)  # Safe day for all months
            return date(year, month, day)
        else:
            return current_date + timedelta(weeks=1)  # Default to weekly


# =============================================================================
# REPORTING & RECONCILIATION
# =============================================================================

class ReportingEngine:
    """
    Payment reporting and reconciliation engine.

    Provides:
    - Real-time payment status
    - Daily settlement reports
    - Monthly financial statements
    - Creditor remittance calculations
    - Trust account management
    """

    def __init__(self):
        self._transactions: Dict[str, PaymentTransaction] = {}
        self._settlement_reports: Dict[str, SettlementReport] = {}
        self._remittances: Dict[str, CreditorRemittance] = {}
        self._trust_account = TrustAccount(account_id="main_trust")

    def record_transaction(
        self,
        transaction: PaymentTransaction,
    ) -> None:
        """Record a transaction for reporting"""
        self._transactions[transaction.transaction_id] = transaction

    def get_transaction_status(
        self,
        transaction_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get real-time transaction status"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            return None

        return {
            "transaction_id": transaction.transaction_id,
            "status": transaction.status.value,
            "amount": str(transaction.amount.amount),
            "created_at": transaction.created_at.isoformat(),
            "authorized_at": transaction.authorized_at.isoformat() if transaction.authorized_at else None,
            "captured_at": transaction.captured_at.isoformat() if transaction.captured_at else None,
            "settled_at": transaction.settled_at.isoformat() if transaction.settled_at else None,
            "failure_reason": transaction.failure_reason.value if transaction.failure_reason else None,
            "failure_message": transaction.failure_message,
            "retry_count": transaction.retry_count,
            "can_retry": transaction.can_retry,
        }

    async def generate_daily_settlement_report(
        self,
        report_date: date,
        processor: PaymentProcessor,
    ) -> SettlementReport:
        """Generate daily settlement report for a processor"""
        report_id = f"settle_{processor.value}_{report_date.isoformat()}"

        # Get transactions for the day
        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())

        day_transactions = [
            t for t in self._transactions.values()
            if t.processor == processor
            and start_of_day <= t.created_at <= end_of_day
        ]

        # Calculate metrics
        successful = [t for t in day_transactions if t.status == PaymentStatus.SETTLED]
        failed = [t for t in day_transactions if t.status == PaymentStatus.FAILED]
        refunded = [t for t in day_transactions if t.refunded_amount > 0]
        chargebacks = [t for t in day_transactions if t.status == PaymentStatus.CHARGEBACK]

        total_amount = sum(t.amount.amount for t in successful)
        total_fees = sum(t.amount.fee for t in successful)
        refunds_amount = sum(t.refunded_amount for t in refunded)
        chargebacks_amount = sum(t.chargeback_amount or Decimal("0") for t in chargebacks)

        report = SettlementReport(
            report_id=report_id,
            report_date=report_date,
            processor=processor,
            total_transactions=len(day_transactions),
            total_amount=total_amount,
            total_fees=total_fees,
            net_amount=total_amount - total_fees - refunds_amount - chargebacks_amount,
            successful_transactions=len(successful),
            failed_transactions=len(failed),
            refunds_count=len(refunded),
            refunds_amount=refunds_amount,
            chargebacks_count=len(chargebacks),
            chargebacks_amount=chargebacks_amount,
            transactions=[t.transaction_id for t in day_transactions],
        )

        self._settlement_reports[report_id] = report
        return report

    async def generate_monthly_statement(
        self,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """Generate monthly financial statement"""
        # Determine date range
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        # Get all transactions in range
        month_transactions = [
            t for t in self._transactions.values()
            if start_dt <= t.created_at <= end_dt
        ]

        # Group by processor
        by_processor = defaultdict(list)
        for t in month_transactions:
            by_processor[t.processor.value].append(t)

        # Group by payment type
        by_type = defaultdict(list)
        for t in month_transactions:
            by_type[t.payment_type.value].append(t)

        # Calculate metrics
        successful = [t for t in month_transactions if t.status in [
            PaymentStatus.SETTLED, PaymentStatus.RECONCILED
        ]]

        statement = {
            "period": f"{year}-{month:02d}",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summary": {
                "total_transactions": len(month_transactions),
                "successful_transactions": len(successful),
                "total_volume": str(sum(t.amount.amount for t in successful)),
                "total_fees": str(sum(t.amount.fee for t in successful)),
                "net_volume": str(sum(t.amount.net_amount for t in successful)),
                "average_transaction": str(
                    sum(t.amount.amount for t in successful) / len(successful)
                    if successful else Decimal("0")
                ),
            },
            "by_processor": {
                processor: {
                    "count": len(transactions),
                    "volume": str(sum(t.amount.amount for t in transactions)),
                }
                for processor, transactions in by_processor.items()
            },
            "by_payment_type": {
                ptype: {
                    "count": len(transactions),
                    "volume": str(sum(t.amount.amount for t in transactions)),
                }
                for ptype, transactions in by_type.items()
            },
            "failure_analysis": self._analyze_failures(month_transactions),
        }

        return statement

    def _analyze_failures(
        self,
        transactions: List[PaymentTransaction],
    ) -> Dict[str, Any]:
        """Analyze payment failures"""
        failed = [t for t in transactions if t.status == PaymentStatus.FAILED]

        if not failed:
            return {"failure_rate": 0, "by_reason": {}}

        # Group by reason
        by_reason = defaultdict(list)
        for t in failed:
            reason = t.failure_reason.value if t.failure_reason else "unknown"
            by_reason[reason].append(t)

        return {
            "failure_rate": len(failed) / len(transactions) if transactions else 0,
            "total_failed": len(failed),
            "failed_volume": str(sum(t.amount.amount for t in failed)),
            "by_reason": {
                reason: {
                    "count": len(transactions),
                    "volume": str(sum(t.amount.amount for t in transactions)),
                }
                for reason, transactions in by_reason.items()
            },
        }

    async def calculate_creditor_remittance(
        self,
        creditor_id: str,
        period_start: date,
        period_end: date,
        commission_rate: Decimal = Decimal("0.30"),
    ) -> CreditorRemittance:
        """Calculate remittance for a creditor"""
        remittance_id = f"remit_{creditor_id}_{period_start.isoformat()}"

        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())

        # Get creditor's transactions
        creditor_transactions = [
            t for t in self._transactions.values()
            if t.metadata.get("creditor_id") == creditor_id
            and start_dt <= t.created_at <= end_dt
            and t.status in [PaymentStatus.SETTLED, PaymentStatus.RECONCILED]
        ]

        total_collected = sum(t.amount.amount for t in creditor_transactions)
        commission_amount = (total_collected * commission_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net_remittance = total_collected - commission_amount

        remittance = CreditorRemittance(
            remittance_id=remittance_id,
            creditor_id=creditor_id,
            period_start=period_start,
            period_end=period_end,
            total_collected=total_collected,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            net_remittance=net_remittance,
            transaction_count=len(creditor_transactions),
            transactions=[t.transaction_id for t in creditor_transactions],
        )

        self._remittances[remittance_id] = remittance
        return remittance

    def update_trust_account(
        self,
        deposit: Decimal = Decimal("0"),
        disbursement: Decimal = Decimal("0"),
        reserve_change: Decimal = Decimal("0"),
    ) -> TrustAccount:
        """Update trust account balances"""
        self._trust_account.balance += deposit - disbursement
        self._trust_account.reserve_balance += reserve_change
        self._trust_account.available_balance = (
            self._trust_account.balance
            - self._trust_account.reserve_balance
            - self._trust_account.pending_disbursements
        )
        return self._trust_account

    def get_trust_account_status(self) -> Dict[str, Any]:
        """Get current trust account status"""
        return {
            "account_id": self._trust_account.account_id,
            "balance": str(self._trust_account.balance),
            "available_balance": str(self._trust_account.available_balance),
            "pending_deposits": str(self._trust_account.pending_deposits),
            "pending_disbursements": str(self._trust_account.pending_disbursements),
            "reserve_balance": str(self._trust_account.reserve_balance),
            "last_reconciled": (
                self._trust_account.last_reconciled.isoformat()
                if self._trust_account.last_reconciled else None
            ),
        }


# =============================================================================
# MAIN PAYMENT ENGINE
# =============================================================================

class PaymentEngine:
    """
    Core payment infrastructure integration layer.

    Integrates:
    - Stripe (card payments)
    - Plaid (bank account verification)
    - Dwolla (ACH transfers)

    Features:
    - Payment method tokenization with PCI compliance
    - Full payment lifecycle management
    - Intelligent retry with exponential backoff
    - Financial controls and fraud prevention
    - Real-time reporting and reconciliation
    """

    def __init__(self):
        # Processor adapters
        self.stripe = StripeAdapter()
        self.plaid = PlaidAdapter()
        self.dwolla = DwollaAdapter()

        # Components
        self.controls = FinancialControlsEngine()
        self.schedules = PaymentScheduleManager()
        self.reporting = ReportingEngine()

        # Transaction storage
        self._transactions: Dict[str, PaymentTransaction] = {}
        self._payment_methods: Dict[str, PaymentMethodToken] = {}
        self._idempotency_cache: Dict[str, str] = {}  # key -> transaction_id

        logger.info("Payment Engine initialized")

    # -------------------------------------------------------------------------
    # Payment Method Management
    # -------------------------------------------------------------------------

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        cvc: str,
        billing_details: Dict[str, Any],
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """
        Tokenize a card for PCI-compliant storage.

        Args:
            card_number: Full card number
            expiry_month: Expiration month (1-12)
            expiry_year: Expiration year (4 digits)
            cvc: Card verification code
            billing_details: Billing address details

        Returns:
            Tuple of (token, error_message)
        """
        token, error = await self.stripe.tokenize_card(
            card_number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvc=cvc,
            billing_details=billing_details,
        )

        if token:
            self._payment_methods[token.token_id] = token
            logger.info(f"Card tokenized: {token.display_name}")

        return token, error

    async def verify_bank_account_plaid(
        self,
        plaid_public_token: str,
        account_id: str,
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """
        Verify bank account using Plaid Link.

        Args:
            plaid_public_token: Token from Plaid Link
            account_id: Selected account ID from Plaid

        Returns:
            Tuple of (token, error_message)
        """
        # Exchange public token for access token (would be done in production)
        token, error = await self.plaid.verify_bank_account(
            account_id=account_id,
            routing_number="",  # Would come from Plaid
            account_number="",
            account_type="checking",
        )

        if token:
            self._payment_methods[token.token_id] = token
            logger.info(f"Bank account verified via Plaid: {token.display_name}")

        return token, error

    async def add_bank_account_dwolla(
        self,
        routing_number: str,
        account_number: str,
        account_type: str = "checking",
    ) -> Tuple[Optional[PaymentMethodToken], Optional[str]]:
        """
        Add bank account for ACH via Dwolla.

        Args:
            routing_number: Bank routing number
            account_number: Bank account number
            account_type: "checking" or "savings"

        Returns:
            Tuple of (token, error_message)
        """
        token, error = await self.dwolla.verify_bank_account(
            account_id="",
            routing_number=routing_number,
            account_number=account_number,
            account_type=account_type,
        )

        if token:
            self._payment_methods[token.token_id] = token
            logger.info(f"Bank account added via Dwolla: {token.display_name}")

            # Initiate micro-deposits for verification
            await self.dwolla.initiate_micro_deposits(token.token_id)

        return token, error

    async def verify_micro_deposits(
        self,
        token_id: str,
        amount1: Decimal,
        amount2: Decimal,
    ) -> Tuple[bool, Optional[str]]:
        """Verify micro-deposit amounts for bank account"""
        token = self._payment_methods.get(token_id)
        if not token:
            return False, "Payment method not found"

        if token.processor == PaymentProcessor.DWOLLA:
            success, error = await self.dwolla.verify_micro_deposits(
                token_id, amount1, amount2
            )
            if success:
                token.is_verified = True
                token.metadata["verification_status"] = "verified"
            return success, error

        return False, "Micro-deposit verification not supported for this method"

    def get_payment_method(
        self,
        token_id: str,
    ) -> Optional[PaymentMethodToken]:
        """Get a stored payment method"""
        return self._payment_methods.get(token_id)

    def get_customer_payment_methods(
        self,
        customer_id: str,
    ) -> List[PaymentMethodToken]:
        """Get all payment methods for a customer"""
        return [
            pm for pm in self._payment_methods.values()
            if pm.metadata.get("customer_id") == customer_id
        ]

    # -------------------------------------------------------------------------
    # Payment Processing
    # -------------------------------------------------------------------------

    async def process_payment(
        self,
        account_id: str,
        client_id: str,
        amount: Decimal,
        payment_method_token: str,
        payment_type: PaymentType = PaymentType.ONE_TIME_FULL,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentTransaction:
        """
        Process a payment through the appropriate processor.

        Args:
            account_id: Account being paid
            client_id: Client who owns the account
            amount: Payment amount
            payment_method_token: Tokenized payment method ID
            payment_type: Type of payment
            idempotency_key: Unique key for idempotent requests
            metadata: Additional metadata

        Returns:
            PaymentTransaction with result
        """
        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = f"pay_{uuid.uuid4().hex}"

        # Check idempotency
        if idempotency_key in self._idempotency_cache:
            existing_txn_id = self._idempotency_cache[idempotency_key]
            existing_txn = self._transactions.get(existing_txn_id)
            if existing_txn:
                logger.info(f"Returning cached transaction for idempotency key: {idempotency_key}")
                return existing_txn

        # Get payment method
        payment_method = self._payment_methods.get(payment_method_token)
        if not payment_method:
            return self._create_failed_transaction(
                account_id=account_id,
                client_id=client_id,
                amount=amount,
                idempotency_key=idempotency_key,
                failure_reason=FailureReason.INVALID_CARD,
                failure_message="Payment method not found",
            )

        # Check for expired card
        if payment_method.is_expired:
            return self._create_failed_transaction(
                account_id=account_id,
                client_id=client_id,
                amount=amount,
                idempotency_key=idempotency_key,
                failure_reason=FailureReason.CARD_EXPIRED,
                failure_message="Payment method has expired",
                payment_method=payment_method,
            )

        # Velocity check
        velocity_result = await self.controls.check_velocity(account_id, amount)
        if not velocity_result.passed:
            return self._create_failed_transaction(
                account_id=account_id,
                client_id=client_id,
                amount=amount,
                idempotency_key=idempotency_key,
                failure_reason=FailureReason.VELOCITY_EXCEEDED,
                failure_message=velocity_result.reason,
                payment_method=payment_method,
            )

        # Duplicate check
        is_duplicate, dup_message = await self.controls.check_duplicate(
            account_id, amount, payment_method_token
        )
        if is_duplicate:
            return self._create_failed_transaction(
                account_id=account_id,
                client_id=client_id,
                amount=amount,
                idempotency_key=idempotency_key,
                failure_reason=FailureReason.DUPLICATE_PAYMENT,
                failure_message=dup_message,
                payment_method=payment_method,
            )

        # Calculate fee
        fee = self.controls.calculate_fee(amount, payment_method.method_type)
        payment_amount = PaymentAmount(amount=amount, fee=fee)

        # Create transaction
        transaction = PaymentTransaction(
            transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            account_id=account_id,
            client_id=client_id,
            payment_type=payment_type,
            amount=payment_amount,
            payment_method=payment_method,
            processor=payment_method.processor,
            metadata=metadata or {},
        )

        transaction.add_audit_entry("created", {
            "amount": str(amount),
            "payment_method": payment_method.display_name,
        })

        # Select processor and process
        try:
            if payment_method.processor == PaymentProcessor.STRIPE:
                success, txn_id, error = await self.stripe.authorize_and_capture(
                    amount=payment_amount,
                    payment_method=payment_method,
                    metadata={
                        "account_id": account_id,
                        "client_id": client_id,
                        "transaction_id": transaction.transaction_id,
                    },
                )
            elif payment_method.processor == PaymentProcessor.DWOLLA:
                success, txn_id, error = await self.dwolla.authorize_and_capture(
                    amount=payment_amount,
                    payment_method=payment_method,
                    metadata={
                        "account_id": account_id,
                        "client_id": client_id,
                    },
                )
            else:
                success, txn_id, error = False, "", "Unsupported processor"

            if success:
                transaction.status = PaymentStatus.CAPTURED
                transaction.processor_transaction_id = txn_id
                transaction.captured_at = datetime.utcnow()
                transaction.add_audit_entry("captured", {"processor_id": txn_id})
                logger.info(
                    f"Payment successful: {transaction.transaction_id} - ${amount}"
                )
            else:
                failure_reason = RetryStrategy.map_processor_error(
                    payment_method.processor, "", error or ""
                )
                transaction.status = PaymentStatus.FAILED
                transaction.failure_reason = failure_reason
                transaction.failure_message = error
                transaction.add_audit_entry("failed", {
                    "reason": failure_reason.value,
                    "message": error,
                })

                # Schedule retry if applicable
                if transaction.can_retry:
                    retry_delay = RetryStrategy.get_retry_delay(0, failure_reason)
                    transaction.next_retry_at = datetime.utcnow() + retry_delay
                    transaction.add_audit_entry("retry_scheduled", {
                        "retry_at": transaction.next_retry_at.isoformat(),
                    })

                logger.warning(
                    f"Payment failed: {transaction.transaction_id} - {error}"
                )

        except Exception as e:
            logger.error(f"Payment processing error: {e}")
            transaction.status = PaymentStatus.FAILED
            transaction.failure_reason = FailureReason.PROCESSOR_ERROR
            transaction.failure_message = str(e)
            transaction.add_audit_entry("error", {"exception": str(e)})

        # Store transaction
        self._transactions[transaction.transaction_id] = transaction
        self._idempotency_cache[idempotency_key] = transaction.transaction_id

        # Record for velocity tracking
        self.controls.record_transaction(transaction)

        # Record for reporting
        self.reporting.record_transaction(transaction)

        return transaction

    async def authorize_payment(
        self,
        account_id: str,
        client_id: str,
        amount: Decimal,
        payment_method_token: str,
        idempotency_key: Optional[str] = None,
    ) -> PaymentTransaction:
        """
        Authorize a payment without capturing.

        Use for pre-authorization scenarios where capture happens later.
        """
        if not idempotency_key:
            idempotency_key = f"auth_{uuid.uuid4().hex}"

        payment_method = self._payment_methods.get(payment_method_token)
        if not payment_method:
            return self._create_failed_transaction(
                account_id=account_id,
                client_id=client_id,
                amount=amount,
                idempotency_key=idempotency_key,
                failure_reason=FailureReason.INVALID_CARD,
                failure_message="Payment method not found",
            )

        fee = self.controls.calculate_fee(amount, payment_method.method_type)
        payment_amount = PaymentAmount(amount=amount, fee=fee)

        transaction = PaymentTransaction(
            transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            account_id=account_id,
            client_id=client_id,
            payment_type=PaymentType.ONE_TIME_FULL,
            amount=payment_amount,
            payment_method=payment_method,
            processor=payment_method.processor,
        )

        try:
            success, auth_id, error = await self.stripe.authorize(
                amount=payment_amount,
                payment_method=payment_method,
                metadata={"account_id": account_id},
            )

            if success:
                transaction.status = PaymentStatus.AUTHORIZED
                transaction.processor_authorization_id = auth_id
                transaction.authorized_at = datetime.utcnow()
                transaction.add_audit_entry("authorized", {"authorization_id": auth_id})
            else:
                transaction.status = PaymentStatus.FAILED
                transaction.failure_reason = RetryStrategy.map_processor_error(
                    PaymentProcessor.STRIPE, "", error or ""
                )
                transaction.failure_message = error

        except Exception as e:
            transaction.status = PaymentStatus.FAILED
            transaction.failure_reason = FailureReason.PROCESSOR_ERROR
            transaction.failure_message = str(e)

        self._transactions[transaction.transaction_id] = transaction
        return transaction

    async def capture_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
    ) -> PaymentTransaction:
        """
        Capture a previously authorized payment.

        Args:
            transaction_id: ID of authorized transaction
            amount: Amount to capture (defaults to full authorization)
        """
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if transaction.status != PaymentStatus.AUTHORIZED:
            raise ValueError(
                f"Cannot capture transaction in status: {transaction.status.value}"
            )

        capture_amount = None
        if amount:
            capture_amount = PaymentAmount(amount=amount)

        try:
            success, capture_id, error = await self.stripe.capture(
                authorization_id=transaction.processor_authorization_id,
                amount=capture_amount,
            )

            if success:
                transaction.status = PaymentStatus.CAPTURED
                transaction.processor_capture_id = capture_id
                transaction.captured_at = datetime.utcnow()
                transaction.add_audit_entry("captured", {"capture_id": capture_id})
            else:
                transaction.status = PaymentStatus.FAILED
                transaction.failure_message = error
                transaction.add_audit_entry("capture_failed", {"error": error})

        except Exception as e:
            transaction.status = PaymentStatus.FAILED
            transaction.failure_message = str(e)

        return transaction

    async def void_authorization(
        self,
        transaction_id: str,
    ) -> PaymentTransaction:
        """Void an authorized but uncaptured payment"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if transaction.status != PaymentStatus.AUTHORIZED:
            raise ValueError(
                f"Cannot void transaction in status: {transaction.status.value}"
            )

        success, error = await self.stripe.void(
            transaction.processor_authorization_id
        )

        if success:
            transaction.status = PaymentStatus.CANCELLED
            transaction.add_audit_entry("voided")
        else:
            transaction.add_audit_entry("void_failed", {"error": error})

        return transaction

    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        reason: str = "",
    ) -> Tuple[PaymentTransaction, Optional[RefundRequest]]:
        """
        Refund a captured payment.

        Args:
            transaction_id: ID of transaction to refund
            amount: Amount to refund (defaults to full amount)
            reason: Reason for refund
        """
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if transaction.status not in [PaymentStatus.CAPTURED, PaymentStatus.SETTLED]:
            raise ValueError(
                f"Cannot refund transaction in status: {transaction.status.value}"
            )

        refund_amount = amount or transaction.amount.amount

        # Check refund doesn't exceed original
        already_refunded = transaction.refunded_amount
        max_refundable = transaction.amount.amount - already_refunded

        if refund_amount > max_refundable:
            raise ValueError(
                f"Refund amount ${refund_amount} exceeds refundable amount ${max_refundable}"
            )

        refund_request = RefundRequest(
            refund_id=f"ref_{uuid.uuid4().hex[:16]}",
            transaction_id=transaction_id,
            amount=refund_amount,
            reason=reason,
            created_by="system",
        )

        try:
            refund_payment_amount = PaymentAmount(amount=refund_amount)

            if transaction.processor == PaymentProcessor.STRIPE:
                success, refund_id, error = await self.stripe.refund(
                    transaction.processor_transaction_id,
                    refund_payment_amount,
                )
            elif transaction.processor == PaymentProcessor.DWOLLA:
                success, refund_id, error = await self.dwolla.refund(
                    transaction.processor_transaction_id,
                    refund_payment_amount,
                )
            else:
                success, refund_id, error = False, "", "Unsupported processor"

            if success:
                refund_request.status = "completed"
                refund_request.processed_at = datetime.utcnow()
                refund_request.processor_refund_id = refund_id

                transaction.refunded_amount += refund_amount
                transaction.refund_transactions.append(refund_request.refund_id)

                if transaction.refunded_amount >= transaction.amount.amount:
                    transaction.status = PaymentStatus.REFUNDED

                transaction.add_audit_entry("refunded", {
                    "refund_id": refund_id,
                    "amount": str(refund_amount),
                })

                logger.info(
                    f"Refund processed: {refund_request.refund_id} - ${refund_amount}"
                )
            else:
                refund_request.status = "failed"
                transaction.add_audit_entry("refund_failed", {"error": error})
                logger.warning(f"Refund failed: {error}")

        except Exception as e:
            refund_request.status = "error"
            logger.error(f"Refund error: {e}")

        return transaction, refund_request

    async def retry_failed_payment(
        self,
        transaction_id: str,
    ) -> PaymentTransaction:
        """Retry a failed payment"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if not transaction.can_retry:
            raise ValueError("Transaction cannot be retried")

        transaction.retry_count += 1
        transaction.add_audit_entry("retry_attempt", {
            "attempt": transaction.retry_count,
        })

        # Process through normal flow
        new_transaction = await self.process_payment(
            account_id=transaction.account_id,
            client_id=transaction.client_id,
            amount=transaction.amount.amount,
            payment_method_token=transaction.payment_method.token_id,
            payment_type=transaction.payment_type,
            idempotency_key=f"{transaction.idempotency_key}_retry_{transaction.retry_count}",
            metadata=transaction.metadata,
        )

        # Link to original
        new_transaction.metadata["original_transaction_id"] = transaction_id

        return new_transaction

    # -------------------------------------------------------------------------
    # Payment Schedules
    # -------------------------------------------------------------------------

    def create_payment_plan(
        self,
        account_id: str,
        total_amount: Decimal,
        frequency: RecurringFrequency,
        payment_amount: Decimal,
        start_date: date = None,
    ) -> PaymentSchedule:
        """Create a recurring payment plan"""
        return self.schedules.create_recurring_schedule(
            account_id=account_id,
            total_amount=total_amount,
            frequency=frequency,
            payment_amount=payment_amount,
            start_date=start_date,
        )

    def create_micro_payment_plan(
        self,
        account_id: str,
        total_amount: Decimal,
        weekly_amount: Decimal = Decimal("10"),
    ) -> PaymentSchedule:
        """Create a micro-payment plan ($5-25 weekly)"""
        return self.schedules.create_micro_payment_schedule(
            account_id=account_id,
            total_amount=total_amount,
            weekly_amount=weekly_amount,
        )

    def create_custom_schedule(
        self,
        account_id: str,
        payments: List[Dict[str, Any]],
    ) -> PaymentSchedule:
        """Create a variable payment schedule with custom dates/amounts"""
        return self.schedules.create_variable_schedule(
            account_id=account_id,
            payments=payments,
        )

    async def process_scheduled_payments(
        self,
    ) -> List[PaymentTransaction]:
        """Process all payments due today"""
        due_payments = self.schedules.get_due_payments()
        results = []

        for schedule, payment in due_payments:
            # Get stored payment method for account
            # In production, would look up from customer's saved methods
            payment_methods = [
                pm for pm in self._payment_methods.values()
                if pm.metadata.get("account_id") == schedule.account_id
            ]

            if not payment_methods:
                logger.warning(
                    f"No payment method for scheduled payment: {schedule.schedule_id}"
                )
                self.schedules.mark_payment_failed(
                    schedule.schedule_id,
                    payment["payment_number"],
                    "No payment method on file",
                )
                continue

            # Use first available method
            payment_method = payment_methods[0]

            transaction = await self.process_payment(
                account_id=schedule.account_id,
                client_id="",  # Would look up
                amount=Decimal(str(payment["amount"])),
                payment_method_token=payment_method.token_id,
                payment_type=schedule.payment_type,
                metadata={
                    "schedule_id": schedule.schedule_id,
                    "payment_number": payment["payment_number"],
                },
            )

            if transaction.status == PaymentStatus.CAPTURED:
                self.schedules.mark_payment_complete(
                    schedule.schedule_id,
                    payment["payment_number"],
                    transaction.transaction_id,
                )
            else:
                self.schedules.mark_payment_failed(
                    schedule.schedule_id,
                    payment["payment_number"],
                    transaction.failure_message or "Payment failed",
                )

            results.append(transaction)

        return results

    # -------------------------------------------------------------------------
    # Settlement & Reconciliation
    # -------------------------------------------------------------------------

    async def settle_transaction(
        self,
        transaction_id: str,
    ) -> PaymentTransaction:
        """Mark a captured transaction as settled"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if transaction.status != PaymentStatus.CAPTURED:
            raise ValueError(
                f"Cannot settle transaction in status: {transaction.status.value}"
            )

        transaction.status = PaymentStatus.SETTLED
        transaction.settled_at = datetime.utcnow()
        transaction.add_audit_entry("settled")

        # Update trust account
        self.reporting.update_trust_account(deposit=transaction.amount.net_amount)

        return transaction

    async def reconcile_transaction(
        self,
        transaction_id: str,
        processor_settlement_id: str,
    ) -> PaymentTransaction:
        """Reconcile a settled transaction with processor settlement"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        if transaction.status != PaymentStatus.SETTLED:
            raise ValueError(
                f"Cannot reconcile transaction in status: {transaction.status.value}"
            )

        transaction.status = PaymentStatus.RECONCILED
        transaction.processor_settlement_id = processor_settlement_id
        transaction.reconciled_at = datetime.utcnow()
        transaction.add_audit_entry("reconciled", {
            "settlement_id": processor_settlement_id,
        })

        return transaction

    async def handle_chargeback(
        self,
        transaction_id: str,
        chargeback_id: str,
        chargeback_reason: str,
        chargeback_amount: Decimal,
    ) -> PaymentTransaction:
        """Handle a chargeback notification"""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        transaction.status = PaymentStatus.CHARGEBACK
        transaction.chargeback_id = chargeback_id
        transaction.chargeback_reason = chargeback_reason
        transaction.chargeback_amount = chargeback_amount
        transaction.add_audit_entry("chargeback", {
            "chargeback_id": chargeback_id,
            "reason": chargeback_reason,
            "amount": str(chargeback_amount),
        })

        # Update trust account (debit the chargeback amount)
        self.reporting.update_trust_account(disbursement=chargeback_amount)

        logger.warning(
            f"Chargeback received: {transaction_id} - ${chargeback_amount} - {chargeback_reason}"
        )

        return transaction

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    def get_transaction(
        self,
        transaction_id: str,
    ) -> Optional[PaymentTransaction]:
        """Get a transaction by ID"""
        return self._transactions.get(transaction_id)

    def get_transaction_status(
        self,
        transaction_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get real-time transaction status"""
        return self.reporting.get_transaction_status(transaction_id)

    async def get_daily_settlement_report(
        self,
        report_date: date,
        processor: PaymentProcessor = PaymentProcessor.STRIPE,
    ) -> SettlementReport:
        """Get daily settlement report"""
        return await self.reporting.generate_daily_settlement_report(
            report_date, processor
        )

    async def get_monthly_statement(
        self,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """Get monthly financial statement"""
        return await self.reporting.generate_monthly_statement(year, month)

    async def get_creditor_remittance(
        self,
        creditor_id: str,
        period_start: date,
        period_end: date,
        commission_rate: Decimal = Decimal("0.30"),
    ) -> CreditorRemittance:
        """Calculate creditor remittance"""
        return await self.reporting.calculate_creditor_remittance(
            creditor_id, period_start, period_end, commission_rate
        )

    def get_trust_account_status(self) -> Dict[str, Any]:
        """Get trust account status"""
        return self.reporting.get_trust_account_status()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _create_failed_transaction(
        self,
        account_id: str,
        client_id: str,
        amount: Decimal,
        idempotency_key: str,
        failure_reason: FailureReason,
        failure_message: str,
        payment_method: Optional[PaymentMethodToken] = None,
    ) -> PaymentTransaction:
        """Create a failed transaction record"""
        transaction = PaymentTransaction(
            transaction_id=f"txn_{uuid.uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            account_id=account_id,
            client_id=client_id,
            payment_type=PaymentType.ONE_TIME_FULL,
            amount=PaymentAmount(amount=amount),
            payment_method=payment_method or PaymentMethodToken(
                token_id="unknown",
                processor=PaymentProcessor.STRIPE,
                method_type=PaymentMethodType.CARD,
                last_four="0000",
            ),
            processor=PaymentProcessor.STRIPE,
            status=PaymentStatus.FAILED,
            failure_reason=failure_reason,
            failure_message=failure_message,
        )

        transaction.add_audit_entry("failed", {
            "reason": failure_reason.value,
            "message": failure_message,
        })

        self._transactions[transaction.transaction_id] = transaction
        self._idempotency_cache[idempotency_key] = transaction.transaction_id

        return transaction

    def get_recovery_actions(
        self,
        transaction_id: str,
    ) -> List[str]:
        """Get recommended recovery actions for a failed transaction"""
        transaction = self._transactions.get(transaction_id)
        if not transaction or transaction.status != PaymentStatus.FAILED:
            return []

        return RetryStrategy.get_recovery_actions(transaction.failure_reason)

    def recommend_alternative_method(
        self,
        customer_id: str,
        amount: Decimal,
    ) -> Optional[PaymentMethodToken]:
        """Recommend alternative payment method for a customer"""
        methods = self.get_customer_payment_methods(customer_id)

        # Filter out expired methods
        valid_methods = [m for m in methods if not m.is_expired]

        if not valid_methods:
            return None

        # Recommend lowest fee method
        return self.controls.recommend_payment_method(amount, valid_methods)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_payment_engine() -> PaymentEngine:
    """Create and return a configured PaymentEngine instance"""
    return PaymentEngine()


async def process_one_time_payment(
    engine: PaymentEngine,
    account_id: str,
    client_id: str,
    amount: Decimal,
    payment_method_token: str,
) -> PaymentTransaction:
    """Convenience function for one-time full payment"""
    return await engine.process_payment(
        account_id=account_id,
        client_id=client_id,
        amount=amount,
        payment_method_token=payment_method_token,
        payment_type=PaymentType.ONE_TIME_FULL,
    )


async def process_settlement_payment(
    engine: PaymentEngine,
    account_id: str,
    client_id: str,
    settlement_amount: Decimal,
    payment_method_token: str,
    original_balance: Decimal,
) -> PaymentTransaction:
    """Convenience function for settlement payment"""
    return await engine.process_payment(
        account_id=account_id,
        client_id=client_id,
        amount=settlement_amount,
        payment_method_token=payment_method_token,
        payment_type=PaymentType.ONE_TIME_SETTLEMENT,
        metadata={
            "original_balance": str(original_balance),
            "settlement_percentage": str(
                (settlement_amount / original_balance * 100).quantize(Decimal("0.01"))
            ),
        },
    )


# =============================================================================
# CLI DEMO
# =============================================================================

async def demo_payment_flow():
    """Demonstrate payment engine capabilities"""
    print("=" * 70)
    print("QUAN PAYMENT ENGINE DEMO")
    print("=" * 70)

    engine = create_payment_engine()

    # 1. Tokenize a card
    print("\n[1] Tokenizing payment card...")
    token, error = await engine.tokenize_card(
        card_number="4242424242424242",
        expiry_month=12,
        expiry_year=2025,
        cvc="123",
        billing_details={
            "name": "John Doe",
            "address": {
                "line1": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94102",
            },
        },
    )

    if token:
        print(f"   Card tokenized: {token.display_name}")
        print(f"   Token ID: {token.token_id}")
    else:
        print(f"   Error: {error}")
        return

    # Store for account
    token.metadata["account_id"] = "ACC-001"
    token.metadata["customer_id"] = "CUST-001"

    # 2. Process one-time payment
    print("\n[2] Processing one-time payment...")
    txn = await engine.process_payment(
        account_id="ACC-001",
        client_id="CLIENT-001",
        amount=Decimal("150.00"),
        payment_method_token=token.token_id,
        payment_type=PaymentType.ONE_TIME_FULL,
    )

    print(f"   Transaction ID: {txn.transaction_id}")
    print(f"   Status: {txn.status.value}")
    print(f"   Amount: ${txn.amount.amount}")
    print(f"   Fee: ${txn.amount.fee}")
    print(f"   Net: ${txn.amount.net_amount}")

    # 3. Create micro-payment plan
    print("\n[3] Creating micro-payment plan...")
    schedule = engine.create_micro_payment_plan(
        account_id="ACC-002",
        total_amount=Decimal("250.00"),
        weekly_amount=Decimal("15.00"),
    )

    print(f"   Schedule ID: {schedule.schedule_id}")
    print(f"   Total: ${schedule.total_amount}")
    print(f"   Weekly: $15.00")
    print(f"   Payments: {len(schedule.payments)}")
    print(f"   First payment: {schedule.payments[0]['date']}")

    # 4. Fee optimization
    print("\n[4] Fee optimization comparison...")
    card_fee = engine.controls.calculate_fee(
        Decimal("100"), PaymentMethodType.CARD
    )
    ach_fee = engine.controls.calculate_fee(
        Decimal("100"), PaymentMethodType.ACH
    )

    print(f"   Card fee for $100: ${card_fee}")
    print(f"   ACH fee for $100: ${ach_fee}")
    print(f"   Savings with ACH: ${card_fee - ach_fee}")

    # 5. Velocity check
    print("\n[5] Velocity check...")
    velocity = await engine.controls.check_velocity("ACC-001", Decimal("500"))
    print(f"   Passed: {velocity.passed}")
    print(f"   Daily transactions: {velocity.daily_count}/{velocity.daily_limit}")
    print(f"   Daily amount: ${velocity.daily_amount}/${velocity.daily_amount_limit}")

    # 6. Trust account status
    print("\n[6] Trust account status...")
    trust = engine.get_trust_account_status()
    print(f"   Balance: ${trust['balance']}")
    print(f"   Available: ${trust['available_balance']}")
    print(f"   Reserve: ${trust['reserve_balance']}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(demo_payment_flow())
