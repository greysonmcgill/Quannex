"""
QUAN Integration Tests: Payment Processing

Comprehensive payment flow testing:
1. ACH payment processing
2. Card payment handling
3. Payment plan execution
4. Failed payment retry
5. Reconciliation accuracy

Tests verify payment integrity and financial accuracy.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any
import uuid


# =============================================================================
# PAYMENT PROCESSING IMPLEMENTATION FOR TESTING
# =============================================================================

class PaymentStatus:
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    FAILED = "failed"
    REFUNDED = "refunded"


class FailureReason:
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    CARD_EXPIRED = "card_expired"
    INVALID_ACCOUNT = "invalid_account"
    NETWORK_ERROR = "network_error"
    FRAUD_SUSPECTED = "fraud_suspected"


class PaymentEngine:
    """Payment engine implementation for testing"""

    def __init__(self, processor):
        self.processor = processor
        self.transactions: Dict[str, Dict] = {}
        self.payment_plans: Dict[str, Dict] = {}
        self.reconciliation_records: List[Dict] = []
        self.retry_queue: List[Dict] = []

        # Configuration
        self.max_retries = 3
        self.retry_delays = [1, 4, 24]  # Hours between retries

    async def process_ach_payment(
        self,
        account_id: str,
        amount: Decimal,
        bank_token: Dict,
        metadata: Dict = None
    ) -> Dict:
        """Process ACH bank payment"""
        transaction_id = f"ach_{uuid.uuid4().hex[:12]}"

        # ACH-specific validation
        if amount > Decimal("25000"):
            return {
                "success": False,
                "error": "ACH amount exceeds daily limit",
                "transaction_id": transaction_id
            }

        # Authorize (ACH authorization is essentially immediate)
        auth_success, auth_id, auth_error = await self.processor.authorize(
            amount=amount,
            payment_method=bank_token,
            metadata={
                "account_id": account_id,
                "payment_type": "ach",
                **(metadata or {})
            }
        )

        if not auth_success:
            self._record_transaction(transaction_id, account_id, amount, PaymentStatus.FAILED, auth_error)
            return {"success": False, "error": auth_error, "transaction_id": transaction_id}

        # ACH capture (initiates bank transfer)
        capture_success, capture_id, capture_error = await self.processor.capture(
            auth_id=auth_id,
            amount=amount
        )

        if not capture_success:
            self._record_transaction(transaction_id, account_id, amount, PaymentStatus.FAILED, capture_error)
            return {"success": False, "error": capture_error, "transaction_id": transaction_id}

        self._record_transaction(
            transaction_id, account_id, amount, PaymentStatus.CAPTURED,
            processor_ref=capture_id, payment_type="ach"
        )

        return {
            "success": True,
            "transaction_id": transaction_id,
            "capture_id": capture_id,
            "amount": float(amount),
            "status": PaymentStatus.CAPTURED,
            "settlement_date": (datetime.utcnow() + timedelta(days=3)).isoformat()  # ACH settles in 3 days
        }

    async def process_card_payment(
        self,
        account_id: str,
        amount: Decimal,
        card_token: Dict,
        metadata: Dict = None
    ) -> Dict:
        """Process card payment"""
        transaction_id = f"card_{uuid.uuid4().hex[:12]}"

        # Card-specific validation
        if self._is_card_expired(card_token):
            return {
                "success": False,
                "error": "Card expired",
                "transaction_id": transaction_id
            }

        # Authorize
        auth_success, auth_id, auth_error = await self.processor.authorize(
            amount=amount,
            payment_method=card_token,
            metadata={
                "account_id": account_id,
                "payment_type": "card",
                **(metadata or {})
            }
        )

        if not auth_success:
            self._record_transaction(transaction_id, account_id, amount, PaymentStatus.FAILED, auth_error)
            return {"success": False, "error": auth_error, "transaction_id": transaction_id}

        # Capture
        capture_success, capture_id, capture_error = await self.processor.capture(
            auth_id=auth_id,
            amount=amount
        )

        if not capture_success:
            self._record_transaction(transaction_id, account_id, amount, PaymentStatus.FAILED, capture_error)
            return {"success": False, "error": capture_error, "transaction_id": transaction_id}

        self._record_transaction(
            transaction_id, account_id, amount, PaymentStatus.CAPTURED,
            processor_ref=capture_id, payment_type="card"
        )

        return {
            "success": True,
            "transaction_id": transaction_id,
            "capture_id": capture_id,
            "amount": float(amount),
            "status": PaymentStatus.CAPTURED,
            "settlement_date": (datetime.utcnow() + timedelta(days=1)).isoformat()  # Cards settle next day
        }

    async def create_payment_plan(
        self,
        account_id: str,
        total_amount: Decimal,
        installments: int,
        payment_method: Dict,
        start_date: datetime = None
    ) -> Dict:
        """Create a recurring payment plan"""
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"

        if installments < 2 or installments > 24:
            return {"success": False, "error": "Installments must be between 2 and 24"}

        installment_amount = (total_amount / installments).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # Adjust last payment for rounding
        last_payment = total_amount - (installment_amount * (installments - 1))

        start = start_date or datetime.utcnow()

        schedule = []
        for i in range(installments):
            payment_date = start + timedelta(days=30 * i)
            amount = last_payment if i == installments - 1 else installment_amount

            schedule.append({
                "installment": i + 1,
                "amount": float(amount),
                "due_date": payment_date.isoformat(),
                "status": "pending"
            })

        plan = {
            "plan_id": plan_id,
            "account_id": account_id,
            "total_amount": float(total_amount),
            "installments": installments,
            "installment_amount": float(installment_amount),
            "payment_method": payment_method,
            "schedule": schedule,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "completed_payments": 0,
            "total_paid": 0.0
        }

        self.payment_plans[plan_id] = plan

        return {"success": True, "plan": plan}

    async def execute_plan_payment(self, plan_id: str, installment_number: int = None) -> Dict:
        """Execute the next payment in a plan"""
        plan = self.payment_plans.get(plan_id)
        if not plan:
            return {"success": False, "error": "Payment plan not found"}

        if plan["status"] != "active":
            return {"success": False, "error": f"Plan is {plan['status']}"}

        # Find next pending payment
        next_payment = None
        for scheduled in plan["schedule"]:
            if scheduled["status"] == "pending":
                if installment_number is None or scheduled["installment"] == installment_number:
                    next_payment = scheduled
                    break

        if not next_payment:
            return {"success": False, "error": "No pending payments found"}

        # Process the payment
        result = await self.process_card_payment(
            account_id=plan["account_id"],
            amount=Decimal(str(next_payment["amount"])),
            card_token=plan["payment_method"],
            metadata={"plan_id": plan_id, "installment": next_payment["installment"]}
        )

        if result["success"]:
            next_payment["status"] = "paid"
            next_payment["paid_at"] = datetime.utcnow().isoformat()
            next_payment["transaction_id"] = result["transaction_id"]
            plan["completed_payments"] += 1
            plan["total_paid"] += next_payment["amount"]

            # Check if plan complete
            if plan["completed_payments"] == plan["installments"]:
                plan["status"] = "completed"
                plan["completed_at"] = datetime.utcnow().isoformat()
        else:
            next_payment["status"] = "failed"
            next_payment["failure_reason"] = result.get("error")

            # Add to retry queue
            self.retry_queue.append({
                "plan_id": plan_id,
                "installment": next_payment["installment"],
                "retry_count": 0,
                "next_retry": datetime.utcnow() + timedelta(hours=self.retry_delays[0])
            })

        return {
            "success": result["success"],
            "plan_id": plan_id,
            "installment": next_payment["installment"],
            "amount": next_payment["amount"],
            "transaction_id": result.get("transaction_id"),
            "plan_status": plan["status"],
            "error": result.get("error")
        }

    async def process_retry_queue(self) -> List[Dict]:
        """Process failed payments in retry queue"""
        results = []

        items_to_remove = []

        for item in self.retry_queue:
            if datetime.utcnow() < item["next_retry"]:
                continue

            plan = self.payment_plans.get(item["plan_id"])
            if not plan:
                items_to_remove.append(item)
                continue

            # Attempt retry
            result = await self.execute_plan_payment(item["plan_id"], item["installment"])

            if result["success"]:
                items_to_remove.append(item)
                results.append({"status": "success", **result})
            else:
                item["retry_count"] += 1

                if item["retry_count"] >= self.max_retries:
                    # Max retries reached
                    items_to_remove.append(item)
                    results.append({"status": "max_retries", "plan_id": item["plan_id"]})
                else:
                    # Schedule next retry
                    delay_hours = self.retry_delays[min(item["retry_count"], len(self.retry_delays) - 1)]
                    item["next_retry"] = datetime.utcnow() + timedelta(hours=delay_hours)
                    results.append({"status": "retry_scheduled", "next_retry": item["next_retry"].isoformat()})

        for item in items_to_remove:
            self.retry_queue.remove(item)

        return results

    async def process_refund(
        self,
        transaction_id: str,
        amount: Decimal = None,
        reason: str = None
    ) -> Dict:
        """Process a refund for a transaction"""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            return {"success": False, "error": "Transaction not found"}

        if transaction["status"] not in [PaymentStatus.CAPTURED, PaymentStatus.SETTLED]:
            return {"success": False, "error": f"Cannot refund {transaction['status']} transaction"}

        refund_amount = amount or Decimal(str(transaction["amount"]))

        if refund_amount > Decimal(str(transaction["amount"])):
            return {"success": False, "error": "Refund amount exceeds transaction amount"}

        success, refund_id, error = await self.processor.refund(
            transaction_id=transaction.get("processor_ref", transaction_id),
            amount=refund_amount
        )

        if success:
            transaction["status"] = PaymentStatus.REFUNDED
            transaction["refund_id"] = refund_id
            transaction["refund_amount"] = float(refund_amount)
            transaction["refund_reason"] = reason

            return {
                "success": True,
                "refund_id": refund_id,
                "amount": float(refund_amount),
                "transaction_id": transaction_id
            }

        return {"success": False, "error": error}

    async def reconcile_transactions(self, start_date: datetime, end_date: datetime) -> Dict:
        """Reconcile transactions for a date range"""
        transactions_in_range = [
            t for t in self.transactions.values()
            if start_date <= datetime.fromisoformat(t["created_at"]) <= end_date
        ]

        total_captured = Decimal("0")
        total_settled = Decimal("0")
        total_refunded = Decimal("0")
        total_failed = Decimal("0")

        by_status = {
            PaymentStatus.CAPTURED: [],
            PaymentStatus.SETTLED: [],
            PaymentStatus.REFUNDED: [],
            PaymentStatus.FAILED: []
        }

        for t in transactions_in_range:
            amount = Decimal(str(t["amount"]))
            status = t["status"]

            if status == PaymentStatus.CAPTURED:
                total_captured += amount
                by_status[PaymentStatus.CAPTURED].append(t)
            elif status == PaymentStatus.SETTLED:
                total_settled += amount
                by_status[PaymentStatus.SETTLED].append(t)
            elif status == PaymentStatus.REFUNDED:
                total_refunded += Decimal(str(t.get("refund_amount", t["amount"])))
                by_status[PaymentStatus.REFUNDED].append(t)
            elif status == PaymentStatus.FAILED:
                total_failed += amount
                by_status[PaymentStatus.FAILED].append(t)

        reconciliation = {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_transactions": len(transactions_in_range),
            "totals": {
                "captured": float(total_captured),
                "settled": float(total_settled),
                "refunded": float(total_refunded),
                "failed": float(total_failed),
                "net": float(total_captured + total_settled - total_refunded)
            },
            "counts": {
                status: len(txns) for status, txns in by_status.items()
            },
            "reconciled_at": datetime.utcnow().isoformat()
        }

        self.reconciliation_records.append(reconciliation)
        return reconciliation

    def _is_card_expired(self, card_token: Dict) -> bool:
        """Check if card is expired"""
        expiry_month = card_token.get("expiry_month")
        expiry_year = card_token.get("expiry_year")

        if not expiry_month or not expiry_year:
            return False

        now = datetime.utcnow()
        if expiry_year < now.year:
            return True
        if expiry_year == now.year and expiry_month < now.month:
            return True
        return False

    def _record_transaction(
        self,
        transaction_id: str,
        account_id: str,
        amount: Decimal,
        status: str,
        error: str = None,
        processor_ref: str = None,
        payment_type: str = None
    ):
        """Record a transaction"""
        self.transactions[transaction_id] = {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "amount": float(amount),
            "status": status,
            "error": error,
            "processor_ref": processor_ref,
            "payment_type": payment_type,
            "created_at": datetime.utcnow().isoformat()
        }


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestACHPaymentProcessing:
    """Test ACH bank payment processing"""

    @pytest.fixture
    def payment_engine(self, payment_processor):
        return PaymentEngine(payment_processor)

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_successful_ach_payment(self, payment_engine, data_generator):
        """Test successful ACH payment processing"""
        account = data_generator.generate_account()
        bank_account = data_generator.generate_payment_method("bank_account")

        result = await payment_engine.process_ach_payment(
            account_id=account["account_id"],
            amount=Decimal("185.00"),
            bank_token=bank_account
        )

        assert result["success"]
        assert result["transaction_id"].startswith("ach_")
        assert result["amount"] == 185.00
        assert result["status"] == PaymentStatus.CAPTURED
        assert "settlement_date" in result

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_ach_settlement_timing(self, payment_engine, data_generator):
        """Test ACH payments have correct settlement timing (3 days)"""
        account = data_generator.generate_account()
        bank_account = data_generator.generate_payment_method("bank_account")

        result = await payment_engine.process_ach_payment(
            account_id=account["account_id"],
            amount=Decimal("100.00"),
            bank_token=bank_account
        )

        settlement_date = datetime.fromisoformat(result["settlement_date"])
        expected_settlement = datetime.utcnow() + timedelta(days=3)

        # Within 1 day tolerance
        assert abs((settlement_date - expected_settlement).days) <= 1

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_ach_amount_limit(self, payment_engine, data_generator):
        """Test ACH daily amount limit is enforced"""
        account = data_generator.generate_account()
        bank_account = data_generator.generate_payment_method("bank_account")

        # Amount over limit
        result = await payment_engine.process_ach_payment(
            account_id=account["account_id"],
            amount=Decimal("30000.00"),  # Over $25K limit
            bank_token=bank_account
        )

        assert not result["success"]
        assert "limit" in result["error"].lower()

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_ach_failed_payment(self, payment_engine, data_generator, payment_processor):
        """Test ACH payment failure handling"""
        account = data_generator.generate_account()
        bank_account = data_generator.generate_payment_method("bank_account")

        # Set processor to fail
        payment_processor.set_failure(True, "Insufficient funds")

        result = await payment_engine.process_ach_payment(
            account_id=account["account_id"],
            amount=Decimal("500.00"),
            bank_token=bank_account
        )

        assert not result["success"]
        assert "Insufficient funds" in result["error"]

        # Verify transaction recorded as failed
        assert result["transaction_id"] in payment_engine.transactions
        assert payment_engine.transactions[result["transaction_id"]]["status"] == PaymentStatus.FAILED


class TestCardPaymentHandling:
    """Test card payment handling"""

    @pytest.fixture
    def payment_engine(self, payment_processor):
        return PaymentEngine(payment_processor)

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_successful_card_payment(self, payment_engine, data_generator):
        """Test successful card payment"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        result = await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("147.50"),
            card_token=card
        )

        assert result["success"]
        assert result["transaction_id"].startswith("card_")
        assert result["amount"] == 147.50

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_card_settlement_timing(self, payment_engine, data_generator):
        """Test card payments settle next business day"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        result = await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("100.00"),
            card_token=card
        )

        settlement_date = datetime.fromisoformat(result["settlement_date"])
        expected_settlement = datetime.utcnow() + timedelta(days=1)

        # Within 1 day tolerance
        assert abs((settlement_date - expected_settlement).days) <= 1

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_expired_card_rejected(self, payment_engine, data_generator):
        """Test expired card is rejected"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Set card as expired
        card["expiry_month"] = 1
        card["expiry_year"] = 2020

        result = await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("100.00"),
            card_token=card
        )

        assert not result["success"]
        assert "expired" in result["error"].lower()

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_card_decline_handling(self, payment_engine, data_generator, payment_processor):
        """Test card decline is handled gracefully"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        payment_processor.set_failure(True, "Card declined")

        result = await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("500.00"),
            card_token=card
        )

        assert not result["success"]
        assert "declined" in result["error"].lower()

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_multiple_payment_methods(self, payment_engine, data_generator):
        """Test processing payments with different card brands"""
        account = data_generator.generate_account()

        brands = ["visa", "mastercard", "amex"]
        results = []

        for brand in brands:
            card = data_generator.generate_payment_method("card")
            card["brand"] = brand

            result = await payment_engine.process_card_payment(
                account_id=account["account_id"],
                amount=Decimal("50.00"),
                card_token=card
            )
            results.append(result)

        # All should succeed
        assert all(r["success"] for r in results)


class TestPaymentPlanExecution:
    """Test payment plan creation and execution"""

    @pytest.fixture
    def payment_engine(self, payment_processor):
        return PaymentEngine(payment_processor)

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_create_payment_plan(self, payment_engine, data_generator):
        """Test creating a payment plan"""
        account = data_generator.generate_account(balance=Decimal("300.00"))
        card = data_generator.generate_payment_method("card")

        result = await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("300.00"),
            installments=3,
            payment_method=card
        )

        assert result["success"]
        plan = result["plan"]

        assert plan["total_amount"] == 300.00
        assert plan["installments"] == 3
        assert len(plan["schedule"]) == 3
        assert plan["status"] == "active"

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_payment_plan_amounts_accurate(self, payment_engine, data_generator):
        """Test payment plan amounts sum correctly"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        result = await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=3,
            payment_method=card
        )

        plan = result["plan"]
        total_scheduled = sum(p["amount"] for p in plan["schedule"])

        # Total should equal original amount
        assert abs(total_scheduled - 100.00) < 0.01

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_execute_payment_plan(self, payment_engine, data_generator):
        """Test executing payments in a plan"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Create plan
        create_result = await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("150.00"),
            installments=3,
            payment_method=card
        )

        plan_id = create_result["plan"]["plan_id"]

        # Execute all payments
        for i in range(3):
            result = await payment_engine.execute_plan_payment(plan_id)
            assert result["success"], f"Payment {i+1} failed"
            assert result["installment"] == i + 1

        # Check plan completed
        plan = payment_engine.payment_plans[plan_id]
        assert plan["status"] == "completed"
        assert plan["completed_payments"] == 3
        assert abs(plan["total_paid"] - 150.00) < 0.01

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_payment_plan_invalid_installments(self, payment_engine, data_generator):
        """Test invalid installment counts are rejected"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Too few
        result = await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=1,
            payment_method=card
        )
        assert not result["success"]

        # Too many
        result = await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=36,
            payment_method=card
        )
        assert not result["success"]


class TestFailedPaymentRetry:
    """Test failed payment retry logic"""

    @pytest.fixture
    def payment_engine(self, payment_processor):
        return PaymentEngine(payment_processor)

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_failed_payment_added_to_retry_queue(self, payment_engine, data_generator, payment_processor):
        """Test failed payments are added to retry queue"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Create plan
        await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=2,
            payment_method=card
        )
        plan_id = list(payment_engine.payment_plans.keys())[0]

        # Set processor to fail
        payment_processor.set_failure(True, "Card declined")

        # Execute (will fail)
        await payment_engine.execute_plan_payment(plan_id)

        # Check retry queue
        assert len(payment_engine.retry_queue) == 1
        assert payment_engine.retry_queue[0]["plan_id"] == plan_id
        assert payment_engine.retry_queue[0]["retry_count"] == 0

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_retry_succeeds_after_failure(self, payment_engine, data_generator, payment_processor):
        """Test retry succeeds when processor recovers"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=2,
            payment_method=card
        )
        plan_id = list(payment_engine.payment_plans.keys())[0]

        # Fail first payment
        payment_processor.set_failure(True, "Temporary error")
        await payment_engine.execute_plan_payment(plan_id)

        # Reset processor and manually set retry time to now
        payment_processor.reset()
        payment_engine.retry_queue[0]["next_retry"] = datetime.utcnow() - timedelta(seconds=1)

        # Process retry queue
        results = await payment_engine.process_retry_queue()

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert len(payment_engine.retry_queue) == 0

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_max_retries_enforced(self, payment_engine, data_generator, payment_processor):
        """Test payment stops retrying after max attempts"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        await payment_engine.create_payment_plan(
            account_id=account["account_id"],
            total_amount=Decimal("100.00"),
            installments=2,
            payment_method=card
        )
        plan_id = list(payment_engine.payment_plans.keys())[0]

        # Fail initial payment
        payment_processor.set_failure(True, "Persistent error")
        await payment_engine.execute_plan_payment(plan_id)

        # Simulate max retries
        for _ in range(payment_engine.max_retries):
            payment_engine.retry_queue[0]["next_retry"] = datetime.utcnow() - timedelta(seconds=1)
            payment_engine.retry_queue[0]["retry_count"] += 1

        # Final retry should remove from queue
        payment_engine.retry_queue[0]["next_retry"] = datetime.utcnow() - timedelta(seconds=1)
        results = await payment_engine.process_retry_queue()

        assert any(r.get("status") == "max_retries" for r in results)
        assert len(payment_engine.retry_queue) == 0


class TestReconciliationAccuracy:
    """Test reconciliation accuracy"""

    @pytest.fixture
    def payment_engine(self, payment_processor):
        return PaymentEngine(payment_processor)

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_basic_reconciliation(self, payment_engine, data_generator):
        """Test basic transaction reconciliation"""
        # Process several payments
        for i in range(5):
            account = data_generator.generate_account()
            card = data_generator.generate_payment_method("card")

            await payment_engine.process_card_payment(
                account_id=account["account_id"],
                amount=Decimal("100.00"),
                card_token=card
            )

        # Reconcile
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        reconciliation = await payment_engine.reconcile_transactions(start, end)

        assert reconciliation["total_transactions"] == 5
        assert reconciliation["totals"]["captured"] == 500.00
        assert reconciliation["counts"][PaymentStatus.CAPTURED] == 5

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_reconciliation_with_mixed_statuses(self, payment_engine, data_generator, payment_processor):
        """Test reconciliation with different payment statuses"""
        # 3 successful payments
        for _ in range(3):
            account = data_generator.generate_account()
            card = data_generator.generate_payment_method("card")
            await payment_engine.process_card_payment(
                account_id=account["account_id"],
                amount=Decimal("100.00"),
                card_token=card
            )

        # 2 failed payments
        payment_processor.set_failure(True, "Declined")
        for _ in range(2):
            account = data_generator.generate_account()
            card = data_generator.generate_payment_method("card")
            await payment_engine.process_card_payment(
                account_id=account["account_id"],
                amount=Decimal("50.00"),
                card_token=card
            )

        payment_processor.reset()

        # Reconcile
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        reconciliation = await payment_engine.reconcile_transactions(start, end)

        assert reconciliation["total_transactions"] == 5
        assert reconciliation["counts"][PaymentStatus.CAPTURED] == 3
        assert reconciliation["counts"][PaymentStatus.FAILED] == 2
        assert reconciliation["totals"]["captured"] == 300.00

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_reconciliation_with_refunds(self, payment_engine, data_generator):
        """Test reconciliation includes refunds"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Make payment
        result = await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("200.00"),
            card_token=card
        )

        # Refund half
        await payment_engine.process_refund(
            transaction_id=result["transaction_id"],
            amount=Decimal("100.00"),
            reason="Partial refund"
        )

        # Reconcile
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        reconciliation = await payment_engine.reconcile_transactions(start, end)

        assert reconciliation["totals"]["refunded"] == 100.00
        assert reconciliation["totals"]["net"] == -100.00  # Refunded transaction shows negative net

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_reconciliation_date_filtering(self, payment_engine, data_generator):
        """Test reconciliation filters by date correctly"""
        account = data_generator.generate_account()
        card = data_generator.generate_payment_method("card")

        # Make payment
        await payment_engine.process_card_payment(
            account_id=account["account_id"],
            amount=Decimal("100.00"),
            card_token=card
        )

        # Query different date range (yesterday)
        start = datetime.utcnow() - timedelta(days=2)
        end = datetime.utcnow() - timedelta(days=1)

        reconciliation = await payment_engine.reconcile_transactions(start, end)

        # Should find no transactions
        assert reconciliation["total_transactions"] == 0

    @pytest.mark.asyncio
    @pytest.mark.payments
    async def test_reconciliation_accuracy_large_volume(self, payment_engine, data_generator):
        """Test reconciliation accuracy with large volume"""
        expected_total = Decimal("0")

        # Process 100 payments
        for i in range(100):
            account = data_generator.generate_account()
            card = data_generator.generate_payment_method("card")
            amount = Decimal(str(50 + (i % 50)))  # Varying amounts

            result = await payment_engine.process_card_payment(
                account_id=account["account_id"],
                amount=amount,
                card_token=card
            )

            if result["success"]:
                expected_total += amount

        # Reconcile
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)

        reconciliation = await payment_engine.reconcile_transactions(start, end)

        # Verify totals match
        assert abs(Decimal(str(reconciliation["totals"]["captured"])) - expected_total) < Decimal("0.01")
