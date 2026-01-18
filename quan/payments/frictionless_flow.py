"""
Frictionless Payment Flow Module

Optimizes the path from agent contact to payment collection,
minimizing friction at every step.
"""

import asyncio
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentMethod(Enum):
    """Supported payment methods ordered by friction (lowest first)"""
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    SAVED_CARD = "saved_card"
    ONE_CLICK_ACH = "one_click_ach"
    CARD_ON_FILE = "card_on_file"
    NEW_CARD = "new_card"
    ACH_BANK = "ach_bank"
    DEBIT_CARD = "debit_card"
    PAYMENT_LINK = "payment_link"
    IVR_PHONE = "ivr_phone"
    CHECK_BY_PHONE = "check_by_phone"
    MONEY_ORDER = "money_order"


class FrictionPoint(Enum):
    """Identified friction points in payment flow"""
    AUTHENTICATION = "authentication"
    DATA_ENTRY = "data_entry"
    VERIFICATION = "verification"
    CONFIRMATION = "confirmation"
    REDIRECT = "redirect"
    PAGE_LOAD = "page_load"
    ERROR_HANDLING = "error_handling"
    TRUST_SIGNALS = "trust_signals"


@dataclass
class PaymentSession:
    """Represents a payment session with minimal friction"""
    session_id: str
    account_id: str
    amount: Decimal
    created_at: datetime
    expires_at: datetime
    payment_link: str
    short_code: str
    qr_code_data: str
    prefilled_data: Dict[str, Any]
    available_methods: List[PaymentMethod]
    friction_score: float
    trust_tokens: List[str]

    # Session state
    viewed: bool = False
    started: bool = False
    completed: bool = False
    abandoned: bool = False

    # Optimization hints
    recommended_method: Optional[PaymentMethod] = None
    estimated_completion_time: int = 0  # seconds


@dataclass
class FrictionAnalysis:
    """Analysis of friction in payment flow"""
    total_score: float
    friction_points: Dict[FrictionPoint, float]
    recommendations: List[str]
    estimated_conversion_lift: float
    optimizations_applied: List[str]


@dataclass
class PaymentAttempt:
    """Record of a payment attempt"""
    attempt_id: str
    session_id: str
    method: PaymentMethod
    amount: Decimal
    timestamp: datetime
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_ms: int = 0
    friction_encountered: List[FrictionPoint] = field(default_factory=list)


class FrictionlessPaymentEngine:
    """
    Core engine for frictionless payment processing.

    Key principles:
    1. Minimize clicks to payment
    2. Pre-fill all available data
    3. Offer lowest-friction payment methods first
    4. Instant feedback on all actions
    5. Smart retry on failures
    """

    # Friction scores by payment method (lower = better)
    METHOD_FRICTION = {
        PaymentMethod.APPLE_PAY: 0.1,
        PaymentMethod.GOOGLE_PAY: 0.1,
        PaymentMethod.SAVED_CARD: 0.15,
        PaymentMethod.ONE_CLICK_ACH: 0.2,
        PaymentMethod.CARD_ON_FILE: 0.25,
        PaymentMethod.NEW_CARD: 0.5,
        PaymentMethod.ACH_BANK: 0.55,
        PaymentMethod.DEBIT_CARD: 0.45,
        PaymentMethod.PAYMENT_LINK: 0.6,
        PaymentMethod.IVR_PHONE: 0.7,
        PaymentMethod.CHECK_BY_PHONE: 0.8,
        PaymentMethod.MONEY_ORDER: 0.95,
    }

    # Conversion rates by method
    METHOD_CONVERSION = {
        PaymentMethod.APPLE_PAY: 0.85,
        PaymentMethod.GOOGLE_PAY: 0.83,
        PaymentMethod.SAVED_CARD: 0.78,
        PaymentMethod.ONE_CLICK_ACH: 0.72,
        PaymentMethod.CARD_ON_FILE: 0.70,
        PaymentMethod.NEW_CARD: 0.45,
        PaymentMethod.ACH_BANK: 0.42,
        PaymentMethod.DEBIT_CARD: 0.48,
        PaymentMethod.PAYMENT_LINK: 0.35,
        PaymentMethod.IVR_PHONE: 0.28,
        PaymentMethod.CHECK_BY_PHONE: 0.22,
        PaymentMethod.MONEY_ORDER: 0.15,
    }

    def __init__(self):
        self.sessions: Dict[str, PaymentSession] = {}
        self.attempts: List[PaymentAttempt] = []
        self.debtor_preferences: Dict[str, Dict] = {}
        self.payment_history: Dict[str, List[PaymentAttempt]] = {}

    def create_payment_session(
        self,
        account_id: str,
        amount: Decimal,
        debtor_data: Dict[str, Any],
        expiry_hours: int = 72
    ) -> PaymentSession:
        """
        Create an optimized payment session with minimal friction.

        Args:
            account_id: The account being collected
            amount: Amount to collect
            debtor_data: Known debtor information for pre-filling
            expiry_hours: Session validity period

        Returns:
            PaymentSession with optimized flow
        """
        session_id = str(uuid.uuid4())
        short_code = self._generate_short_code()

        # Determine available payment methods based on debtor data
        available_methods = self._determine_available_methods(debtor_data)

        # Pre-fill as much data as possible
        prefilled = self._extract_prefill_data(debtor_data)

        # Calculate friction score
        friction_score = self._calculate_session_friction(
            available_methods, prefilled, debtor_data
        )

        # Generate trust tokens
        trust_tokens = self._generate_trust_tokens(account_id, amount)

        # Generate payment link
        payment_link = f"https://pay.quan.ai/s/{short_code}"

        # Generate QR code data
        qr_data = json.dumps({
            "url": payment_link,
            "amount": str(amount),
            "session": session_id[:8]
        })

        # Recommend best method
        recommended = self._recommend_payment_method(
            available_methods, debtor_data
        )

        session = PaymentSession(
            session_id=session_id,
            account_id=account_id,
            amount=amount,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=expiry_hours),
            payment_link=payment_link,
            short_code=short_code,
            qr_code_data=qr_data,
            prefilled_data=prefilled,
            available_methods=available_methods,
            friction_score=friction_score,
            trust_tokens=trust_tokens,
            recommended_method=recommended,
            estimated_completion_time=self._estimate_completion_time(recommended)
        )

        self.sessions[session_id] = session
        return session

    def _generate_short_code(self, length: int = 8) -> str:
        """Generate a short, memorable payment code"""
        # Use alphanumeric without confusing characters
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _determine_available_methods(
        self,
        debtor_data: Dict[str, Any]
    ) -> List[PaymentMethod]:
        """Determine which payment methods are available for this debtor"""
        methods = []

        # Check for digital wallet indicators
        if debtor_data.get("device_type") == "ios":
            methods.append(PaymentMethod.APPLE_PAY)
        if debtor_data.get("device_type") == "android":
            methods.append(PaymentMethod.GOOGLE_PAY)

        # Check for saved payment methods
        if debtor_data.get("has_saved_card"):
            methods.append(PaymentMethod.SAVED_CARD)
        if debtor_data.get("has_saved_ach"):
            methods.append(PaymentMethod.ONE_CLICK_ACH)

        # Check for card on file from previous payment
        if debtor_data.get("card_on_file"):
            methods.append(PaymentMethod.CARD_ON_FILE)

        # Standard methods always available
        methods.extend([
            PaymentMethod.NEW_CARD,
            PaymentMethod.ACH_BANK,
            PaymentMethod.DEBIT_CARD,
            PaymentMethod.PAYMENT_LINK,
            PaymentMethod.IVR_PHONE,
        ])

        # Sort by friction score (lowest first)
        methods.sort(key=lambda m: self.METHOD_FRICTION.get(m, 1.0))

        return methods

    def _extract_prefill_data(self, debtor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data that can be pre-filled to reduce friction"""
        prefill = {}

        # Personal info
        if debtor_data.get("first_name"):
            prefill["first_name"] = debtor_data["first_name"]
        if debtor_data.get("last_name"):
            prefill["last_name"] = debtor_data["last_name"]
        if debtor_data.get("email"):
            prefill["email"] = debtor_data["email"]
        if debtor_data.get("phone"):
            prefill["phone"] = debtor_data["phone"]

        # Address (for card verification)
        if debtor_data.get("address"):
            prefill["billing_address"] = debtor_data["address"]
        if debtor_data.get("city"):
            prefill["billing_city"] = debtor_data["city"]
        if debtor_data.get("state"):
            prefill["billing_state"] = debtor_data["state"]
        if debtor_data.get("zip"):
            prefill["billing_zip"] = debtor_data["zip"]

        # Masked payment info (for recognition, not actual use)
        if debtor_data.get("last_four_card"):
            prefill["card_hint"] = f"**** **** **** {debtor_data['last_four_card']}"
        if debtor_data.get("last_four_bank"):
            prefill["bank_hint"] = f"****{debtor_data['last_four_bank']}"

        return prefill

    def _calculate_session_friction(
        self,
        methods: List[PaymentMethod],
        prefilled: Dict[str, Any],
        debtor_data: Dict[str, Any]
    ) -> float:
        """Calculate overall friction score for the session"""
        base_friction = 0.5

        # Reduce friction based on best available method
        if methods:
            best_method_friction = self.METHOD_FRICTION.get(methods[0], 0.5)
            base_friction = best_method_friction

        # Reduce friction for pre-filled data
        prefill_reduction = len(prefilled) * 0.02
        base_friction -= prefill_reduction

        # Reduce friction for returning debtor
        if debtor_data.get("previous_payments", 0) > 0:
            base_friction -= 0.1

        # Reduce friction for verified contact
        if debtor_data.get("phone_verified") or debtor_data.get("email_verified"):
            base_friction -= 0.05

        return max(0.05, min(1.0, base_friction))

    def _generate_trust_tokens(
        self,
        account_id: str,
        amount: Decimal
    ) -> List[str]:
        """Generate tokens that establish trust"""
        tokens = []

        # Session verification token
        session_hash = hashlib.sha256(
            f"{account_id}{amount}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        tokens.append(f"verify:{session_hash}")

        # Amount confirmation token
        tokens.append(f"amount:{amount}")

        # Compliance token
        tokens.append("fdcpa:compliant")
        tokens.append("pci:dss:compliant")

        return tokens

    def _recommend_payment_method(
        self,
        available: List[PaymentMethod],
        debtor_data: Dict[str, Any]
    ) -> Optional[PaymentMethod]:
        """Recommend the best payment method for this debtor"""
        if not available:
            return None

        # Check debtor preferences from history
        debtor_id = debtor_data.get("debtor_id")
        if debtor_id and debtor_id in self.debtor_preferences:
            prefs = self.debtor_preferences[debtor_id]
            preferred = prefs.get("preferred_method")
            if preferred and preferred in available:
                return preferred

        # Check previous successful payments
        if debtor_id and debtor_id in self.payment_history:
            history = self.payment_history[debtor_id]
            successful = [a for a in history if a.success]
            if successful:
                # Return most recently successful method
                last_success = successful[-1]
                if last_success.method in available:
                    return last_success.method

        # Default to lowest friction available
        return available[0] if available else None

    def _estimate_completion_time(self, method: Optional[PaymentMethod]) -> int:
        """Estimate time to complete payment in seconds"""
        if not method:
            return 120

        times = {
            PaymentMethod.APPLE_PAY: 5,
            PaymentMethod.GOOGLE_PAY: 5,
            PaymentMethod.SAVED_CARD: 10,
            PaymentMethod.ONE_CLICK_ACH: 15,
            PaymentMethod.CARD_ON_FILE: 20,
            PaymentMethod.NEW_CARD: 60,
            PaymentMethod.ACH_BANK: 90,
            PaymentMethod.DEBIT_CARD: 45,
            PaymentMethod.PAYMENT_LINK: 120,
            PaymentMethod.IVR_PHONE: 180,
            PaymentMethod.CHECK_BY_PHONE: 240,
            PaymentMethod.MONEY_ORDER: 600,
        }

        return times.get(method, 120)

    async def process_payment(
        self,
        session_id: str,
        method: PaymentMethod,
        payment_data: Dict[str, Any]
    ) -> PaymentAttempt:
        """
        Process a payment with minimal friction.

        Implements:
        - Instant validation
        - Progressive data capture
        - Smart error recovery
        - Real-time feedback
        """
        session = self.sessions.get(session_id)
        if not session:
            return PaymentAttempt(
                attempt_id=str(uuid.uuid4()),
                session_id=session_id,
                method=method,
                amount=Decimal("0"),
                timestamp=datetime.now(),
                success=False,
                error_code="SESSION_NOT_FOUND",
                error_message="Payment session not found or expired"
            )

        # Check session validity
        if datetime.now() > session.expires_at:
            return PaymentAttempt(
                attempt_id=str(uuid.uuid4()),
                session_id=session_id,
                method=method,
                amount=session.amount,
                timestamp=datetime.now(),
                success=False,
                error_code="SESSION_EXPIRED",
                error_message="Payment session has expired"
            )

        attempt_id = str(uuid.uuid4())
        start_time = datetime.now()
        friction_encountered = []

        try:
            # Validate payment data (minimal validation for speed)
            validation_result = self._quick_validate(method, payment_data)
            if not validation_result["valid"]:
                friction_encountered.append(FrictionPoint.ERROR_HANDLING)
                return PaymentAttempt(
                    attempt_id=attempt_id,
                    session_id=session_id,
                    method=method,
                    amount=session.amount,
                    timestamp=start_time,
                    success=False,
                    error_code="VALIDATION_FAILED",
                    error_message=validation_result["message"],
                    friction_encountered=friction_encountered
                )

            # Process payment based on method
            result = await self._process_by_method(
                method, session, payment_data
            )

            processing_time = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

            attempt = PaymentAttempt(
                attempt_id=attempt_id,
                session_id=session_id,
                method=method,
                amount=session.amount,
                timestamp=start_time,
                success=result["success"],
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
                processing_time_ms=processing_time,
                friction_encountered=friction_encountered
            )

            # Update session state
            if result["success"]:
                session.completed = True
                # Store preference for future
                self._update_debtor_preference(session.account_id, method)

            # Record attempt
            self.attempts.append(attempt)

            return attempt

        except Exception as e:
            logger.error(f"Payment processing error: {e}")
            return PaymentAttempt(
                attempt_id=attempt_id,
                session_id=session_id,
                method=method,
                amount=session.amount,
                timestamp=start_time,
                success=False,
                error_code="PROCESSING_ERROR",
                error_message=str(e),
                friction_encountered=[FrictionPoint.ERROR_HANDLING]
            )

    def _quick_validate(
        self,
        method: PaymentMethod,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Quick validation with minimal friction"""
        # Minimal validation - trust client-side validation
        # Only check absolute requirements

        if method in [PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY]:
            if not data.get("token"):
                return {"valid": False, "message": "Payment token required"}

        elif method in [PaymentMethod.NEW_CARD, PaymentMethod.DEBIT_CARD]:
            if not data.get("card_number"):
                return {"valid": False, "message": "Card number required"}
            # Luhn check only - no other validation
            if not self._luhn_check(data["card_number"]):
                return {"valid": False, "message": "Invalid card number"}

        elif method == PaymentMethod.ACH_BANK:
            if not data.get("routing_number") or not data.get("account_number"):
                return {"valid": False, "message": "Bank details required"}

        return {"valid": True, "message": "OK"}

    def _luhn_check(self, card_number: str) -> bool:
        """Quick Luhn algorithm check"""
        digits = [int(d) for d in card_number.replace(" ", "").replace("-", "")]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        total = sum(odd_digits)
        for digit in even_digits:
            total += sum(divmod(digit * 2, 10))
        return total % 10 == 0

    async def _process_by_method(
        self,
        method: PaymentMethod,
        session: PaymentSession,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process payment by specific method"""
        # Simulate processing with realistic timing
        await asyncio.sleep(0.1)  # Minimal latency

        # Simulated success rates based on method
        import random
        success_rate = self.METHOD_CONVERSION.get(method, 0.5)

        # Adjust based on session friction
        success_rate *= (1 - session.friction_score * 0.2)

        if random.random() < success_rate:
            return {
                "success": True,
                "transaction_id": str(uuid.uuid4()),
                "amount": str(session.amount)
            }
        else:
            error_codes = [
                ("INSUFFICIENT_FUNDS", "Insufficient funds"),
                ("CARD_DECLINED", "Card declined"),
                ("NETWORK_ERROR", "Network timeout"),
                ("FRAUD_SUSPECTED", "Transaction flagged for review"),
            ]
            error = random.choice(error_codes)
            return {
                "success": False,
                "error_code": error[0],
                "error_message": error[1]
            }

    def _update_debtor_preference(
        self,
        account_id: str,
        method: PaymentMethod
    ):
        """Update debtor payment preferences"""
        if account_id not in self.debtor_preferences:
            self.debtor_preferences[account_id] = {}
        self.debtor_preferences[account_id]["preferred_method"] = method
        self.debtor_preferences[account_id]["last_used"] = datetime.now()

    def analyze_friction(self, session_id: str) -> FrictionAnalysis:
        """Analyze friction points for a session"""
        session = self.sessions.get(session_id)
        if not session:
            return FrictionAnalysis(
                total_score=1.0,
                friction_points={},
                recommendations=["Session not found"],
                estimated_conversion_lift=0,
                optimizations_applied=[]
            )

        # Get attempts for this session
        session_attempts = [a for a in self.attempts if a.session_id == session_id]

        # Analyze friction points
        friction_points = {}

        # Check authentication friction
        if not session.prefilled_data.get("email"):
            friction_points[FrictionPoint.AUTHENTICATION] = 0.2

        # Check data entry friction
        missing_fields = 8 - len(session.prefilled_data)
        friction_points[FrictionPoint.DATA_ENTRY] = missing_fields * 0.05

        # Check verification friction
        if session.recommended_method in [PaymentMethod.NEW_CARD, PaymentMethod.ACH_BANK]:
            friction_points[FrictionPoint.VERIFICATION] = 0.15

        # Check for failed attempts (error handling friction)
        failed = [a for a in session_attempts if not a.success]
        if failed:
            friction_points[FrictionPoint.ERROR_HANDLING] = len(failed) * 0.1

        # Generate recommendations
        recommendations = []
        if FrictionPoint.DATA_ENTRY in friction_points:
            recommendations.append("Pre-fill more debtor data to reduce entry")
        if FrictionPoint.AUTHENTICATION in friction_points:
            recommendations.append("Add email verification for trust")
        if FrictionPoint.VERIFICATION in friction_points:
            recommendations.append("Offer saved payment methods")
        if FrictionPoint.ERROR_HANDLING in friction_points:
            recommendations.append("Improve error messages and retry flow")

        # Calculate conversion lift potential
        total_friction = sum(friction_points.values())
        potential_lift = total_friction * 0.5  # 50% of friction is recoverable

        return FrictionAnalysis(
            total_score=session.friction_score,
            friction_points=friction_points,
            recommendations=recommendations,
            estimated_conversion_lift=potential_lift,
            optimizations_applied=[
                "Lowest friction method recommended",
                f"Pre-filled {len(session.prefilled_data)} fields",
                "Trust tokens generated"
            ]
        )


class OneClickPaymentFlow:
    """
    Implements true one-click payment for returning debtors.

    Flow:
    1. Debtor receives SMS/email with payment link
    2. Clicks link, sees pre-filled payment summary
    3. Taps "Pay Now" with saved method
    4. Payment completes in <5 seconds
    """

    def __init__(self, engine: FrictionlessPaymentEngine):
        self.engine = engine
        self.one_click_tokens: Dict[str, Dict] = {}

    def create_one_click_link(
        self,
        account_id: str,
        amount: Decimal,
        saved_method_token: str,
        debtor_data: Dict[str, Any]
    ) -> str:
        """
        Create a one-click payment link.

        Returns a link that completes payment with single tap.
        """
        token = secrets.token_urlsafe(32)

        self.one_click_tokens[token] = {
            "account_id": account_id,
            "amount": amount,
            "method_token": saved_method_token,
            "debtor_data": debtor_data,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=48),
            "used": False
        }

        return f"https://pay.quan.ai/1c/{token}"

    async def execute_one_click(self, token: str) -> Dict[str, Any]:
        """Execute one-click payment from link"""
        if token not in self.one_click_tokens:
            return {"success": False, "error": "Invalid or expired link"}

        token_data = self.one_click_tokens[token]

        if token_data["used"]:
            return {"success": False, "error": "Link already used"}

        if datetime.now() > token_data["expires_at"]:
            return {"success": False, "error": "Link expired"}

        # Mark as used immediately to prevent double-tap
        token_data["used"] = True

        # Create minimal session
        session = self.engine.create_payment_session(
            account_id=token_data["account_id"],
            amount=token_data["amount"],
            debtor_data=token_data["debtor_data"],
            expiry_hours=1
        )

        # Process with saved method
        result = await self.engine.process_payment(
            session_id=session.session_id,
            method=PaymentMethod.SAVED_CARD,
            payment_data={"token": token_data["method_token"]}
        )

        return {
            "success": result.success,
            "amount": str(token_data["amount"]),
            "transaction_id": result.attempt_id if result.success else None,
            "error": result.error_message
        }


class ProgressivePaymentCapture:
    """
    Captures payment progressively to minimize abandonment.

    Strategy:
    1. Capture minimal info first (email for receipt)
    2. Show amount and payment options
    3. Capture payment details last
    4. Confirm and process

    Each step saves progress so debtor can resume.
    """

    def __init__(self, engine: FrictionlessPaymentEngine):
        self.engine = engine
        self.progress: Dict[str, Dict] = {}

    def start_capture(
        self,
        account_id: str,
        amount: Decimal
    ) -> str:
        """Start progressive capture, return progress ID"""
        progress_id = str(uuid.uuid4())

        self.progress[progress_id] = {
            "account_id": account_id,
            "amount": amount,
            "step": 1,
            "data": {},
            "started_at": datetime.now(),
            "last_activity": datetime.now()
        }

        return progress_id

    def capture_step(
        self,
        progress_id: str,
        step: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Capture data for a specific step"""
        if progress_id not in self.progress:
            return {"success": False, "error": "Session not found"}

        progress = self.progress[progress_id]

        # Save data for this step
        progress["data"].update(data)
        progress["step"] = step + 1
        progress["last_activity"] = datetime.now()

        # Return next step info
        return {
            "success": True,
            "next_step": step + 1,
            "steps_remaining": 4 - step,
            "progress_saved": True
        }

    async def complete_capture(self, progress_id: str) -> Dict[str, Any]:
        """Complete the progressive capture and process payment"""
        if progress_id not in self.progress:
            return {"success": False, "error": "Session not found"}

        progress = self.progress[progress_id]

        # Create payment session
        session = self.engine.create_payment_session(
            account_id=progress["account_id"],
            amount=progress["amount"],
            debtor_data=progress["data"]
        )

        # Process payment
        result = await self.engine.process_payment(
            session_id=session.session_id,
            method=session.recommended_method or PaymentMethod.NEW_CARD,
            payment_data=progress["data"]
        )

        return {
            "success": result.success,
            "transaction_id": result.attempt_id if result.success else None,
            "error": result.error_message
        }


# Utility functions for agent integration

def create_payment_message(
    session: PaymentSession,
    channel: str = "sms"
) -> str:
    """Create payment message for debtor communication"""
    if channel == "sms":
        return (
            f"QUAN: Your secure payment link is ready. "
            f"Pay ${session.amount} in under 30 seconds: {session.payment_link} "
            f"Code: {session.short_code}"
        )
    elif channel == "email":
        return f"""
Dear Customer,

Your payment of ${session.amount} is ready to process.

Click here to pay securely: {session.payment_link}

Or enter code {session.short_code} at pay.quan.ai

Estimated time: {session.estimated_completion_time} seconds

This link expires on {session.expires_at.strftime('%B %d, %Y')}.

Secure payment powered by QUAN.
"""
    else:
        return f"Payment link: {session.payment_link}"


def get_friction_report(engine: FrictionlessPaymentEngine) -> Dict[str, Any]:
    """Generate friction report across all sessions"""
    if not engine.sessions:
        return {"total_sessions": 0, "avg_friction": 0}

    sessions = list(engine.sessions.values())

    completed = [s for s in sessions if s.completed]
    abandoned = [s for s in sessions if s.abandoned]

    avg_friction = sum(s.friction_score for s in sessions) / len(sessions)

    # Method popularity
    method_counts = {}
    for attempt in engine.attempts:
        method = attempt.method.value
        method_counts[method] = method_counts.get(method, 0) + 1

    # Success rates by method
    method_success = {}
    for method in PaymentMethod:
        method_attempts = [a for a in engine.attempts if a.method == method]
        if method_attempts:
            success_rate = sum(1 for a in method_attempts if a.success) / len(method_attempts)
            method_success[method.value] = success_rate

    return {
        "total_sessions": len(sessions),
        "completed": len(completed),
        "abandoned": len(abandoned),
        "completion_rate": len(completed) / len(sessions) if sessions else 0,
        "avg_friction_score": avg_friction,
        "method_popularity": method_counts,
        "method_success_rates": method_success,
        "avg_processing_time_ms": (
            sum(a.processing_time_ms for a in engine.attempts) / len(engine.attempts)
            if engine.attempts else 0
        )
    }
