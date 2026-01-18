"""
Perpetual Payment Monitoring System

Manages ongoing payment plans, monitors for payments received,
handles retries, and maintains continuous collection loops.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import logging
import heapq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentPlanStatus(Enum):
    """Status of a payment plan"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class ScheduledPaymentStatus(Enum):
    """Status of a scheduled payment"""
    PENDING = "pending"
    DUE = "due"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class PaymentEventType(Enum):
    """Types of payment events"""
    PAYMENT_DUE = "payment_due"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    PLAN_COMPLETED = "plan_completed"
    PLAN_DEFAULTED = "plan_defaulted"
    REMINDER_SENT = "reminder_sent"
    RE_ENGAGEMENT_TRIGGERED = "re_engagement_triggered"


@dataclass
class ScheduledPayment:
    """A scheduled payment within a payment plan"""
    payment_id: str
    plan_id: str
    account_id: str
    amount: Decimal
    due_date: datetime
    status: ScheduledPaymentStatus = ScheduledPaymentStatus.PENDING

    # Attempt tracking
    attempts: int = 0
    max_attempts: int = 3
    last_attempt: Optional[datetime] = None
    next_retry: Optional[datetime] = None

    # Payment details
    method_token: Optional[str] = None
    transaction_id: Optional[str] = None
    paid_date: Optional[datetime] = None
    paid_amount: Optional[Decimal] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    notes: List[str] = field(default_factory=list)

    def __lt__(self, other):
        """For heap ordering by due date"""
        return self.due_date < other.due_date


@dataclass
class PaymentPlan:
    """A payment plan for an account"""
    plan_id: str
    account_id: str
    total_amount: Decimal
    payment_amount: Decimal
    frequency_days: int  # Days between payments
    start_date: datetime
    status: PaymentPlanStatus = PaymentPlanStatus.ACTIVE

    # Plan details
    payments: List[ScheduledPayment] = field(default_factory=list)
    num_payments: int = 0
    completed_payments: int = 0

    # Collection tracking
    total_collected: Decimal = Decimal("0")
    last_payment_date: Optional[datetime] = None
    consecutive_misses: int = 0
    max_consecutive_misses: int = 2

    # Saved payment method
    saved_method_token: Optional[str] = None
    auto_charge: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PaymentEvent:
    """An event in the payment lifecycle"""
    event_id: str
    event_type: PaymentEventType
    account_id: str
    plan_id: Optional[str]
    payment_id: Optional[str]
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)


class PerpetualPaymentMonitor:
    """
    Core monitoring system for perpetual payment collection.

    Features:
    1. Continuous monitoring loop
    2. Automatic payment processing
    3. Smart retry logic
    4. Re-engagement triggers
    5. Event-driven architecture
    """

    # Retry intervals (in hours)
    RETRY_INTERVALS = [4, 24, 72]  # 4 hours, 1 day, 3 days

    # Re-engagement triggers
    RE_ENGAGEMENT_THRESHOLD_DAYS = 7

    def __init__(self):
        self.plans: Dict[str, PaymentPlan] = {}
        self.payments: Dict[str, ScheduledPayment] = {}
        self.events: List[PaymentEvent] = []
        self.event_handlers: Dict[PaymentEventType, List[Callable]] = {}

        # Priority queue for due payments
        self.payment_queue: List[ScheduledPayment] = []

        # Running state
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_collected": Decimal("0"),
            "successful_payments": 0,
            "failed_payments": 0,
            "retries": 0,
            "re_engagements": 0
        }

    def create_payment_plan(
        self,
        account_id: str,
        total_amount: Decimal,
        payment_amount: Decimal,
        frequency_days: int = 14,
        start_date: Optional[datetime] = None,
        saved_method_token: Optional[str] = None,
        auto_charge: bool = True
    ) -> PaymentPlan:
        """
        Create a new payment plan with scheduled payments.

        Args:
            account_id: Account being collected
            total_amount: Total debt amount
            payment_amount: Amount per payment
            frequency_days: Days between payments
            start_date: First payment date (default: 7 days from now)
            saved_method_token: Token for saved payment method
            auto_charge: Whether to auto-charge on due date

        Returns:
            Created PaymentPlan
        """
        plan_id = str(uuid.uuid4())

        if start_date is None:
            start_date = datetime.now() + timedelta(days=7)

        # Calculate number of payments
        num_payments = int((total_amount / payment_amount).to_integral_value())
        remainder = total_amount - (payment_amount * num_payments)

        plan = PaymentPlan(
            plan_id=plan_id,
            account_id=account_id,
            total_amount=total_amount,
            payment_amount=payment_amount,
            frequency_days=frequency_days,
            start_date=start_date,
            num_payments=num_payments + (1 if remainder > 0 else 0),
            saved_method_token=saved_method_token,
            auto_charge=auto_charge
        )

        # Create scheduled payments
        current_date = start_date
        remaining = total_amount

        for i in range(plan.num_payments):
            amount = min(payment_amount, remaining)

            payment = ScheduledPayment(
                payment_id=str(uuid.uuid4()),
                plan_id=plan_id,
                account_id=account_id,
                amount=amount,
                due_date=current_date,
                method_token=saved_method_token
            )

            plan.payments.append(payment)
            self.payments[payment.payment_id] = payment

            # Add to priority queue
            heapq.heappush(self.payment_queue, payment)

            remaining -= amount
            current_date += timedelta(days=frequency_days)

        self.plans[plan_id] = plan

        # Emit plan created event
        self._emit_event(PaymentEventType.PAYMENT_DUE, account_id, plan_id, None, {
            "first_payment_date": start_date.isoformat(),
            "num_payments": plan.num_payments,
            "total_amount": str(total_amount)
        })

        logger.info(f"Created payment plan {plan_id} for account {account_id}: "
                   f"${total_amount} in {plan.num_payments} payments")

        return plan

    async def start_monitoring(self, check_interval_seconds: int = 60):
        """Start the perpetual monitoring loop"""
        self.running = True
        logger.info("Starting perpetual payment monitor...")

        while self.running:
            try:
                await self._check_due_payments()
                await self._check_retry_payments()
                await self._check_re_engagement()
                await asyncio.sleep(check_interval_seconds)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)

    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()

    async def _check_due_payments(self):
        """Check for and process due payments"""
        now = datetime.now()

        while self.payment_queue and self.payment_queue[0].due_date <= now:
            payment = heapq.heappop(self.payment_queue)

            # Skip if already processed
            if payment.status in [ScheduledPaymentStatus.COMPLETED,
                                  ScheduledPaymentStatus.SKIPPED]:
                continue

            # Get the plan
            plan = self.plans.get(payment.plan_id)
            if not plan or plan.status != PaymentPlanStatus.ACTIVE:
                continue

            # Mark as due and process
            payment.status = ScheduledPaymentStatus.DUE

            if plan.auto_charge and payment.method_token:
                await self._process_payment(payment, plan)
            else:
                # Send reminder for manual payment
                await self._send_payment_reminder(payment, plan)

    async def _process_payment(
        self,
        payment: ScheduledPayment,
        plan: PaymentPlan
    ):
        """Process a scheduled payment"""
        payment.status = ScheduledPaymentStatus.PROCESSING
        payment.attempts += 1
        payment.last_attempt = datetime.now()

        self.stats["total_processed"] += 1

        try:
            # Attempt to charge saved method
            result = await self._charge_payment_method(
                payment.method_token,
                payment.amount,
                payment.account_id
            )

            if result["success"]:
                # Payment successful
                payment.status = ScheduledPaymentStatus.COMPLETED
                payment.transaction_id = result.get("transaction_id")
                payment.paid_date = datetime.now()
                payment.paid_amount = payment.amount

                # Update plan
                plan.total_collected += payment.amount
                plan.completed_payments += 1
                plan.last_payment_date = datetime.now()
                plan.consecutive_misses = 0
                plan.updated_at = datetime.now()

                # Update stats
                self.stats["successful_payments"] += 1
                self.stats["total_collected"] += payment.amount

                # Check if plan is complete
                if plan.completed_payments >= plan.num_payments:
                    plan.status = PaymentPlanStatus.COMPLETED
                    self._emit_event(
                        PaymentEventType.PLAN_COMPLETED,
                        plan.account_id,
                        plan.plan_id,
                        payment.payment_id,
                        {"total_collected": str(plan.total_collected)}
                    )
                else:
                    self._emit_event(
                        PaymentEventType.PAYMENT_RECEIVED,
                        plan.account_id,
                        plan.plan_id,
                        payment.payment_id,
                        {"amount": str(payment.amount),
                         "remaining": str(plan.total_amount - plan.total_collected)}
                    )

                logger.info(f"Payment {payment.payment_id} successful: ${payment.amount}")

            else:
                # Payment failed
                await self._handle_payment_failure(payment, plan, result)

        except Exception as e:
            logger.error(f"Payment processing error: {e}")
            await self._handle_payment_failure(payment, plan, {"error": str(e)})

    async def _handle_payment_failure(
        self,
        payment: ScheduledPayment,
        plan: PaymentPlan,
        result: Dict[str, Any]
    ):
        """Handle a failed payment"""
        self.stats["failed_payments"] += 1

        error_code = result.get("error_code", "UNKNOWN")
        error_message = result.get("error", "Payment failed")

        payment.notes.append(f"Attempt {payment.attempts} failed: {error_code}")

        self._emit_event(
            PaymentEventType.PAYMENT_FAILED,
            plan.account_id,
            plan.plan_id,
            payment.payment_id,
            {"error_code": error_code, "error_message": error_message,
             "attempt": payment.attempts}
        )

        if payment.attempts < payment.max_attempts:
            # Schedule retry
            retry_hours = self.RETRY_INTERVALS[
                min(payment.attempts - 1, len(self.RETRY_INTERVALS) - 1)
            ]
            payment.status = ScheduledPaymentStatus.RETRYING
            payment.next_retry = datetime.now() + timedelta(hours=retry_hours)

            self.stats["retries"] += 1

            self._emit_event(
                PaymentEventType.RETRY_SCHEDULED,
                plan.account_id,
                plan.plan_id,
                payment.payment_id,
                {"retry_at": payment.next_retry.isoformat(),
                 "attempt": payment.attempts + 1}
            )

            logger.info(f"Payment {payment.payment_id} retry scheduled for "
                       f"{payment.next_retry}")
        else:
            # Max attempts reached
            payment.status = ScheduledPaymentStatus.FAILED
            plan.consecutive_misses += 1

            if plan.consecutive_misses >= plan.max_consecutive_misses:
                plan.status = PaymentPlanStatus.DEFAULTED
                self._emit_event(
                    PaymentEventType.PLAN_DEFAULTED,
                    plan.account_id,
                    plan.plan_id,
                    payment.payment_id,
                    {"consecutive_misses": plan.consecutive_misses,
                     "remaining_balance": str(plan.total_amount - plan.total_collected)}
                )
                logger.warning(f"Plan {plan.plan_id} defaulted after "
                              f"{plan.consecutive_misses} consecutive misses")

    async def _check_retry_payments(self):
        """Check for payments ready to retry"""
        now = datetime.now()

        for payment in self.payments.values():
            if (payment.status == ScheduledPaymentStatus.RETRYING and
                payment.next_retry and
                payment.next_retry <= now):

                plan = self.plans.get(payment.plan_id)
                if plan and plan.status == PaymentPlanStatus.ACTIVE:
                    logger.info(f"Retrying payment {payment.payment_id}")
                    await self._process_payment(payment, plan)

    async def _check_re_engagement(self):
        """Check for accounts needing re-engagement"""
        now = datetime.now()

        for plan in self.plans.values():
            if plan.status != PaymentPlanStatus.ACTIVE:
                continue

            # Check if overdue for engagement
            if plan.last_payment_date:
                days_since = (now - plan.last_payment_date).days
            else:
                days_since = (now - plan.created_at).days

            if days_since >= self.RE_ENGAGEMENT_THRESHOLD_DAYS:
                # Get next pending payment
                pending = [p for p in plan.payments
                          if p.status == ScheduledPaymentStatus.PENDING]

                if pending:
                    self.stats["re_engagements"] += 1

                    self._emit_event(
                        PaymentEventType.RE_ENGAGEMENT_TRIGGERED,
                        plan.account_id,
                        plan.plan_id,
                        pending[0].payment_id,
                        {"days_since_activity": days_since,
                         "remaining_balance": str(plan.total_amount - plan.total_collected)}
                    )

                    logger.info(f"Re-engagement triggered for plan {plan.plan_id}")

    async def _send_payment_reminder(
        self,
        payment: ScheduledPayment,
        plan: PaymentPlan
    ):
        """Send a reminder for manual payment"""
        self._emit_event(
            PaymentEventType.REMINDER_SENT,
            plan.account_id,
            plan.plan_id,
            payment.payment_id,
            {"amount": str(payment.amount), "due_date": payment.due_date.isoformat()}
        )
        logger.info(f"Payment reminder sent for {payment.payment_id}")

    async def _charge_payment_method(
        self,
        method_token: str,
        amount: Decimal,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Charge a saved payment method.

        In production, this would integrate with payment processor.
        """
        # Simulate payment processing
        await asyncio.sleep(0.1)

        import random

        # High success rate for saved methods
        if random.random() < 0.85:
            return {
                "success": True,
                "transaction_id": str(uuid.uuid4()),
                "amount": str(amount)
            }
        else:
            error_codes = [
                ("INSUFFICIENT_FUNDS", "Insufficient funds in account"),
                ("CARD_EXPIRED", "Payment card has expired"),
                ("BANK_DECLINE", "Bank declined the transaction"),
            ]
            error = random.choice(error_codes)
            return {
                "success": False,
                "error_code": error[0],
                "error": error[1]
            }

    def _emit_event(
        self,
        event_type: PaymentEventType,
        account_id: str,
        plan_id: Optional[str],
        payment_id: Optional[str],
        data: Dict[str, Any]
    ):
        """Emit a payment event"""
        event = PaymentEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            account_id=account_id,
            plan_id=plan_id,
            payment_id=payment_id,
            timestamp=datetime.now(),
            data=data
        )

        self.events.append(event)

        # Call registered handlers
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def on_event(
        self,
        event_type: PaymentEventType,
        handler: Callable[[PaymentEvent], None]
    ):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def record_manual_payment(
        self,
        payment_id: str,
        amount: Decimal,
        transaction_id: Optional[str] = None
    ) -> bool:
        """Record a manually received payment"""
        payment = self.payments.get(payment_id)
        if not payment:
            return False

        plan = self.plans.get(payment.plan_id)
        if not plan:
            return False

        payment.status = ScheduledPaymentStatus.COMPLETED
        payment.paid_date = datetime.now()
        payment.paid_amount = amount
        payment.transaction_id = transaction_id or str(uuid.uuid4())

        plan.total_collected += amount
        plan.completed_payments += 1
        plan.last_payment_date = datetime.now()
        plan.consecutive_misses = 0
        plan.updated_at = datetime.now()

        self.stats["successful_payments"] += 1
        self.stats["total_collected"] += amount

        # Check if plan is complete
        if plan.completed_payments >= plan.num_payments:
            plan.status = PaymentPlanStatus.COMPLETED
            self._emit_event(
                PaymentEventType.PLAN_COMPLETED,
                plan.account_id,
                plan.plan_id,
                payment_id,
                {"total_collected": str(plan.total_collected)}
            )
        else:
            self._emit_event(
                PaymentEventType.PAYMENT_RECEIVED,
                plan.account_id,
                plan.plan_id,
                payment_id,
                {"amount": str(amount)}
            )

        return True

    def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a payment plan"""
        plan = self.plans.get(plan_id)
        if not plan:
            return None

        pending = [p for p in plan.payments
                  if p.status == ScheduledPaymentStatus.PENDING]
        completed = [p for p in plan.payments
                    if p.status == ScheduledPaymentStatus.COMPLETED]
        failed = [p for p in plan.payments
                 if p.status == ScheduledPaymentStatus.FAILED]

        next_due = min(
            (p for p in plan.payments if p.status in
             [ScheduledPaymentStatus.PENDING, ScheduledPaymentStatus.DUE]),
            key=lambda p: p.due_date,
            default=None
        )

        return {
            "plan_id": plan.plan_id,
            "account_id": plan.account_id,
            "status": plan.status.value,
            "total_amount": str(plan.total_amount),
            "total_collected": str(plan.total_collected),
            "remaining": str(plan.total_amount - plan.total_collected),
            "progress_pct": float(plan.total_collected / plan.total_amount * 100),
            "payments": {
                "total": plan.num_payments,
                "completed": len(completed),
                "pending": len(pending),
                "failed": len(failed)
            },
            "next_payment": {
                "payment_id": next_due.payment_id,
                "amount": str(next_due.amount),
                "due_date": next_due.due_date.isoformat()
            } if next_due else None,
            "last_activity": (plan.last_payment_date or plan.created_at).isoformat()
        }

    def get_monitor_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        active_plans = sum(1 for p in self.plans.values()
                         if p.status == PaymentPlanStatus.ACTIVE)
        completed_plans = sum(1 for p in self.plans.values()
                            if p.status == PaymentPlanStatus.COMPLETED)
        defaulted_plans = sum(1 for p in self.plans.values()
                            if p.status == PaymentPlanStatus.DEFAULTED)

        success_rate = (
            self.stats["successful_payments"] / self.stats["total_processed"]
            if self.stats["total_processed"] > 0 else 0
        )

        return {
            "running": self.running,
            "plans": {
                "total": len(self.plans),
                "active": active_plans,
                "completed": completed_plans,
                "defaulted": defaulted_plans
            },
            "payments": {
                "total_processed": self.stats["total_processed"],
                "successful": self.stats["successful_payments"],
                "failed": self.stats["failed_payments"],
                "success_rate": success_rate
            },
            "collection": {
                "total_collected": str(self.stats["total_collected"]),
                "retries": self.stats["retries"],
                "re_engagements": self.stats["re_engagements"]
            },
            "events": len(self.events)
        }


class ContinuousCollectionLoop:
    """
    Implements a continuous collection loop that:
    1. Monitors for new accounts
    2. Creates optimal payment plans
    3. Processes payments perpetually
    4. Re-engages defaulted accounts
    """

    def __init__(self, monitor: PerpetualPaymentMonitor):
        self.monitor = monitor
        self.account_queue: List[Dict[str, Any]] = []
        self.processed_accounts: Dict[str, datetime] = {}
        self.running = False

        # Configuration
        self.min_payment_amount = Decimal("25")
        self.max_plan_length_months = 12
        self.re_engagement_cooldown_days = 30

    async def start(self, process_interval_seconds: int = 30):
        """Start the continuous collection loop"""
        self.running = True
        logger.info("Starting continuous collection loop...")

        # Start monitor in background
        monitor_task = asyncio.create_task(self.monitor.start_monitoring())

        while self.running:
            try:
                # Process new accounts
                await self._process_account_queue()

                # Re-engage defaulted plans
                await self._re_engage_defaulted()

                await asyncio.sleep(process_interval_seconds)

            except Exception as e:
                logger.error(f"Collection loop error: {e}")
                await asyncio.sleep(5)

        monitor_task.cancel()

    def stop(self):
        """Stop the collection loop"""
        self.running = False
        self.monitor.stop_monitoring()

    def add_account(self, account_data: Dict[str, Any]):
        """Add an account to the collection queue"""
        self.account_queue.append(account_data)
        logger.info(f"Account {account_data.get('account_id')} added to queue")

    async def _process_account_queue(self):
        """Process accounts in the queue"""
        while self.account_queue:
            account = self.account_queue.pop(0)
            await self._create_optimal_plan(account)

    async def _create_optimal_plan(self, account_data: Dict[str, Any]):
        """Create an optimal payment plan for an account"""
        account_id = account_data.get("account_id")
        total_amount = Decimal(str(account_data.get("balance", 0)))

        if total_amount <= 0:
            return

        # Calculate optimal payment amount
        # Target: 3-6 month plans for most accounts
        target_months = 4
        payment_amount = max(
            self.min_payment_amount,
            (total_amount / (target_months * 2)).quantize(Decimal("0.01"))
        )

        # Adjust for very small or large debts
        if total_amount < 100:
            payment_amount = total_amount  # Single payment
        elif total_amount > 5000:
            payment_amount = max(
                Decimal("100"),
                (total_amount / (self.max_plan_length_months * 2)).quantize(Decimal("0.01"))
            )

        # Create the plan
        plan = self.monitor.create_payment_plan(
            account_id=account_id,
            total_amount=total_amount,
            payment_amount=payment_amount,
            frequency_days=14,
            saved_method_token=account_data.get("payment_token"),
            auto_charge=account_data.get("auto_charge", True)
        )

        self.processed_accounts[account_id] = datetime.now()

        logger.info(f"Created plan for {account_id}: ${total_amount} in "
                   f"{plan.num_payments} payments of ${payment_amount}")

    async def _re_engage_defaulted(self):
        """Re-engage defaulted payment plans"""
        now = datetime.now()

        for plan in self.monitor.plans.values():
            if plan.status != PaymentPlanStatus.DEFAULTED:
                continue

            # Check cooldown
            last_processed = self.processed_accounts.get(plan.account_id)
            if last_processed:
                days_since = (now - last_processed).days
                if days_since < self.re_engagement_cooldown_days:
                    continue

            # Re-activate with modified terms
            remaining = plan.total_amount - plan.total_collected

            if remaining > 0:
                # Create new plan with lower payments
                new_payment = max(
                    self.min_payment_amount,
                    (plan.payment_amount * Decimal("0.75")).quantize(Decimal("0.01"))
                )

                new_plan = self.monitor.create_payment_plan(
                    account_id=plan.account_id,
                    total_amount=remaining,
                    payment_amount=new_payment,
                    frequency_days=14,
                    saved_method_token=plan.saved_method_token,
                    auto_charge=plan.auto_charge
                )

                self.processed_accounts[plan.account_id] = now

                logger.info(f"Re-engaged account {plan.account_id} with new plan: "
                           f"${remaining} in payments of ${new_payment}")


# Utility functions

def create_payment_plan_from_negotiation(
    monitor: PerpetualPaymentMonitor,
    negotiation_result: Dict[str, Any]
) -> Optional[PaymentPlan]:
    """
    Create a payment plan from negotiation result.

    Integrates with the negotiation pipeline stage.
    """
    account_id = negotiation_result.get("account_id")
    agreed_amount = Decimal(str(negotiation_result.get("agreed_amount", 0)))
    payment_amount = Decimal(str(negotiation_result.get("payment_amount", 0)))
    frequency = negotiation_result.get("frequency_days", 14)

    if not account_id or agreed_amount <= 0:
        return None

    # Use minimum payment if not specified
    if payment_amount <= 0:
        payment_amount = max(Decimal("25"), agreed_amount / 6)

    return monitor.create_payment_plan(
        account_id=account_id,
        total_amount=agreed_amount,
        payment_amount=payment_amount,
        frequency_days=frequency,
        saved_method_token=negotiation_result.get("payment_token"),
        auto_charge=negotiation_result.get("auto_charge", True)
    )


async def run_perpetual_monitor_demo():
    """Demo the perpetual payment monitor"""
    monitor = PerpetualPaymentMonitor()

    # Create test plans
    for i in range(5):
        monitor.create_payment_plan(
            account_id=f"ACC-{1000 + i}",
            total_amount=Decimal(str(500 + i * 100)),
            payment_amount=Decimal("50"),
            frequency_days=14,
            saved_method_token=f"tok_{uuid.uuid4().hex[:8]}",
            auto_charge=True
        )

    # Run for a short demo
    print("Starting perpetual monitor demo...")

    async def demo_run():
        for _ in range(5):
            await monitor._check_due_payments()
            await monitor._check_retry_payments()
            await asyncio.sleep(1)

    await demo_run()

    # Print stats
    stats = monitor.get_monitor_stats()
    print(f"\nMonitor Statistics:")
    print(f"  Plans: {stats['plans']}")
    print(f"  Payments: {stats['payments']}")
    print(f"  Collection: {stats['collection']}")

    return monitor


if __name__ == "__main__":
    asyncio.run(run_perpetual_monitor_demo())
