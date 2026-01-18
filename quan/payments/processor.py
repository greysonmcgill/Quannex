"""Secure payment processing with instant settlement"""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from quan.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PaymentResult:
    """Result of payment processing"""

    success: bool
    transaction_id: Optional[str] = None
    amount: Optional[Decimal] = None
    method: Optional[str] = None
    error: Optional[str] = None
    receipt_url: Optional[str] = None


@dataclass
class SettlementOffer:
    """Settlement offer for an account"""

    account_id: str
    original_balance: Decimal
    settlement_amount: Decimal
    savings: Decimal
    valid_until: datetime
    payment_options: List[Dict[str, Any]]

    @property
    def discount_percentage(self) -> float:
        if self.original_balance == 0:
            return 0
        return float((self.original_balance - self.settlement_amount) / self.original_balance * 100)


class PaymentProcessor:
    """Secure payment processing with instant settlement"""

    def __init__(self):
        self._stripe = None
        self.payment_validator = PaymentValidator()
        self.settlement_engine = SettlementEngine()

    def _get_stripe(self):
        """Lazy load Stripe"""
        if self._stripe is None and settings.stripe_secret_key:
            try:
                import stripe
                stripe.api_key = settings.stripe_secret_key
                self._stripe = stripe
            except ImportError:
                logger.warning("Stripe not installed")
        return self._stripe

    async def process_payment(
        self,
        account: Dict,
        payment_method: Dict,
        amount: Decimal,
    ) -> PaymentResult:
        """Process payment with full validation"""

        # Validate payment details
        validation = await self.payment_validator.validate(
            account,
            payment_method,
            amount,
        )

        if not validation["valid"]:
            return PaymentResult(
                success=False,
                error="; ".join(validation["errors"]),
            )

        try:
            method_type = payment_method.get("type")

            if method_type == "card":
                result = await self._process_card_payment(
                    account,
                    payment_method,
                    amount,
                )
            elif method_type == "ach":
                result = await self._process_ach_payment(
                    account,
                    payment_method,
                    amount,
                )
            elif method_type == "digital_wallet":
                result = await self._process_digital_wallet(
                    account,
                    payment_method,
                    amount,
                )
            else:
                return PaymentResult(
                    success=False,
                    error=f"Unsupported payment method: {method_type}",
                )

            # Record payment
            await self._record_payment(account, result)

            # Update account status
            await self._update_account_status(account, amount)

            # Generate receipt
            receipt = await self._generate_receipt(account, result)

            # Notify client
            await self._notify_client(account.get("client_id"), result)

            return PaymentResult(
                success=True,
                transaction_id=result.get("id"),
                amount=amount,
                method=method_type,
                receipt_url=receipt.get("url"),
            )

        except Exception as e:
            logger.error(f"Payment error for {account.get('account_id')}: {e}")
            return PaymentResult(
                success=False,
                error=str(e),
            )

    async def _process_card_payment(
        self,
        account: Dict,
        card: Dict,
        amount: Decimal,
    ) -> Dict:
        """Process credit/debit card payment"""

        stripe = self._get_stripe()
        if not stripe:
            raise Exception("Stripe not configured")

        # Create Stripe charge
        charge = stripe.Charge.create(
            amount=int(amount * 100),  # Convert to cents
            currency="usd",
            source=card.get("token"),
            description=f"Payment for account {account.get('account_id')}",
            metadata={
                "account_id": account.get("account_id"),
                "client_id": account.get("client_id"),
                "original_creditor": account.get("original_creditor"),
            },
        )

        return {
            "id": charge.id,
            "amount": amount,
            "method": "card",
            "status": charge.status,
        }

    async def _process_ach_payment(
        self,
        account: Dict,
        bank_account: Dict,
        amount: Decimal,
    ) -> Dict:
        """Process ACH bank transfer"""

        stripe = self._get_stripe()
        if not stripe:
            raise Exception("Stripe not configured")

        # ACH takes 3-5 days to clear
        # Would create a bank transfer here

        return {
            "id": f"ach_{account.get('account_id')}_{datetime.utcnow().timestamp()}",
            "amount": amount,
            "method": "ach",
            "status": "pending",
            "estimated_arrival": (datetime.utcnow() + timedelta(days=4)).isoformat(),
        }

    async def _process_digital_wallet(
        self,
        account: Dict,
        wallet: Dict,
        amount: Decimal,
    ) -> Dict:
        """Process digital wallet payment (Apple Pay, Google Pay)"""

        stripe = self._get_stripe()
        if not stripe:
            raise Exception("Stripe not configured")

        # Digital wallets are processed similarly to cards
        payment_intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency="usd",
            payment_method=wallet.get("payment_method_id"),
            confirm=True,
            metadata={
                "account_id": account.get("account_id"),
            },
        )

        return {
            "id": payment_intent.id,
            "amount": amount,
            "method": wallet.get("wallet_type", "digital_wallet"),
            "status": payment_intent.status,
        }

    async def _record_payment(self, account: Dict, result: Dict) -> None:
        """Record payment in database"""
        logger.info(
            f"Payment recorded: {account.get('account_id')} - "
            f"${result.get('amount')} via {result.get('method')}"
        )

    async def _update_account_status(
        self,
        account: Dict,
        amount: Decimal,
    ) -> None:
        """Update account after payment"""

        balance = Decimal(str(account.get("balance", 0)))
        new_balance = balance - amount

        account["balance"] = float(new_balance)
        account["last_payment_date"] = datetime.utcnow().isoformat()
        account["last_payment_amount"] = float(amount)

        if new_balance <= 0:
            account["status"] = "paid_in_full"
            logger.info(f"Account {account.get('account_id')} paid in full")

    async def _generate_receipt(
        self,
        account: Dict,
        result: Dict,
    ) -> Dict:
        """Generate payment receipt"""

        receipt = {
            "receipt_id": f"rcpt_{result.get('id')}",
            "account_id": account.get("account_id"),
            "amount": result.get("amount"),
            "date": datetime.utcnow().isoformat(),
            "method": result.get("method"),
            "url": f"https://pay.quanrecovery.com/receipt/{result.get('id')}",
        }

        return receipt

    async def _notify_client(
        self,
        client_id: str,
        result: Dict,
    ) -> None:
        """Notify client of payment"""
        # Would send webhook or notification to client
        logger.info(f"Notifying client {client_id} of payment: ${result.get('amount')}")

    async def create_payment_link(
        self,
        account: Dict,
        amount: Optional[Decimal] = None,
    ) -> str:
        """Create a payment link for account"""

        if amount is None:
            amount = Decimal(str(account.get("balance", 0)))

        # Would create Stripe payment link
        return f"https://pay.quanrecovery.com/{account.get('account_id')}?amount={amount}"


class SettlementEngine:
    """AI-powered settlement negotiation"""

    def __init__(self):
        self._ml_model = None
        self.authority_matrix = self._load_authority_matrix()

    def _load_authority_matrix(self) -> Dict[str, Dict]:
        """Load settlement authority rules"""
        return {
            "default": {
                "min_settlement": 0.20,  # 20% minimum
                "max_settlement": 0.80,  # 80% maximum
            },
            "high_probability": {
                "min_settlement": 0.60,
                "max_settlement": 0.90,
            },
            "low_probability": {
                "min_settlement": 0.15,
                "max_settlement": 0.50,
            },
            "aged": {
                "min_settlement": 0.10,
                "max_settlement": 0.40,
            },
        }

    async def calculate_settlement(
        self,
        account: Dict,
        offer: Optional[Decimal] = None,
    ) -> SettlementOffer:
        """Calculate optimal settlement offer"""

        balance = Decimal(str(account.get("balance", 0)))

        # Get AI recommendation
        features = self._extract_settlement_features(account)
        ai_recommendation = self._predict_optimal_settlement(features)

        # Apply business rules
        min_settlement = self._apply_authority_matrix(account, ai_recommendation)

        settlement_amount = max(balance * Decimal(str(min_settlement)), Decimal("1.00"))

        # If debtor made offer, evaluate it
        if offer is not None:
            if offer >= settlement_amount:
                settlement_amount = offer
            else:
                # Counter offer
                settlement_amount = settlement_amount * Decimal("1.1")

        # Generate payment options
        payment_options = self._generate_payment_options(settlement_amount)

        return SettlementOffer(
            account_id=account.get("account_id"),
            original_balance=balance,
            settlement_amount=settlement_amount,
            savings=balance - settlement_amount,
            valid_until=datetime.utcnow() + timedelta(days=7),
            payment_options=payment_options,
        )

    def _extract_settlement_features(self, account: Dict) -> List[float]:
        """Extract features for settlement prediction"""

        balance = account.get("balance", 0)
        days_overdue = account.get("days_overdue", 0)

        return [
            balance / 1000,
            days_overdue / 365,
            account.get("previous_payments", 0),
            account.get("contact_attempts", 0) / 10,
            1 if account.get("employed") else 0,
        ]

    def _predict_optimal_settlement(self, features: List[float]) -> float:
        """Predict optimal settlement ratio using ML"""

        # Simple heuristic (would be ML model in production)
        balance_factor = max(0.3, 1 - features[0] * 0.1)  # Lower for higher balances
        age_factor = max(0.2, 1 - features[1] * 0.3)  # Lower for older debts

        base = 0.5
        optimal = base * balance_factor * age_factor

        return max(0.15, min(0.85, optimal))

    def _apply_authority_matrix(
        self,
        account: Dict,
        ai_recommendation: float,
    ) -> float:
        """Apply business rules to AI recommendation"""

        days_overdue = account.get("days_overdue", 0)
        recovery_prob = account.get("recovery_probability", 0.5)

        # Select authority tier
        if days_overdue > 365:
            tier = "aged"
        elif recovery_prob > 0.6:
            tier = "high_probability"
        elif recovery_prob < 0.3:
            tier = "low_probability"
        else:
            tier = "default"

        rules = self.authority_matrix[tier]

        # Clamp to authority limits
        min_val = rules["min_settlement"]
        max_val = rules["max_settlement"]

        return max(min_val, min(max_val, ai_recommendation))

    def _generate_payment_options(
        self,
        settlement_amount: Decimal,
    ) -> List[Dict[str, Any]]:
        """Generate flexible payment options"""

        options = [
            {
                "type": "lump_sum",
                "amount": float(settlement_amount),
                "payments": 1,
                "discount": 0.10,  # Extra 10% off for lump sum
            },
            {
                "type": "two_payments",
                "amount": float(settlement_amount / 2),
                "payments": 2,
                "interval_days": 30,
                "discount": 0.05,
            },
            {
                "type": "payment_plan",
                "amount": float(settlement_amount / 3),
                "payments": 3,
                "interval_days": 30,
                "discount": 0.0,
            },
        ]

        # Add extended plan for larger amounts
        if settlement_amount > 500:
            options.append({
                "type": "extended_plan",
                "amount": float(settlement_amount / 6),
                "payments": 6,
                "interval_days": 30,
                "discount": -0.05,  # Small premium for longer plan
            })

        return options


class PaymentValidator:
    """Validate payment details"""

    async def validate(
        self,
        account: Dict,
        payment_method: Dict,
        amount: Decimal,
    ) -> Dict[str, Any]:
        """Validate payment request"""

        errors = []

        # Validate amount
        if amount <= 0:
            errors.append("Amount must be positive")

        balance = Decimal(str(account.get("balance", 0)))
        if amount > balance:
            errors.append("Amount exceeds balance")

        # Validate payment method
        method_type = payment_method.get("type")
        if method_type not in ["card", "ach", "digital_wallet"]:
            errors.append(f"Invalid payment method: {method_type}")

        if method_type == "card":
            if not payment_method.get("token"):
                errors.append("Card token required")

        if method_type == "ach":
            if not payment_method.get("routing_number"):
                errors.append("Routing number required")
            if not payment_method.get("account_number"):
                errors.append("Account number required")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }
