"""
Payment Failure Recovery System

Intelligent recovery from payment failures with:
1. Root cause analysis
2. Automatic retry scheduling
3. Alternative payment method suggestions
4. Payday-aware rescheduling
5. Partial payment handling
6. Network routing optimization
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
from collections import defaultdict
import hashlib
import random


class FailureType(Enum):
    """Payment failure types"""
    INSUFFICIENT_FUNDS = "nsf"
    CARD_DECLINED = "declined"
    CARD_EXPIRED = "expired"
    INVALID_ACCOUNT = "invalid"
    BANK_REJECT = "bank_reject"
    NETWORK_ERROR = "network"
    FRAUD_BLOCK = "fraud"
    LIMIT_EXCEEDED = "limit"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Recovery actions"""
    RETRY_SAME = "retry_same"           # Retry same method
    RETRY_DIFFERENT_TIME = "retry_time"  # Retry at different time
    RETRY_PAYDAY = "retry_payday"        # Retry on payday
    REQUEST_UPDATE = "request_update"    # Request new payment info
    SPLIT_PAYMENT = "split"              # Split into smaller amounts
    ALTERNATIVE_METHOD = "alt_method"    # Suggest alternative
    ESCALATE = "escalate"                # Escalate to agent
    ABANDON = "abandon"                  # Mark as uncollectible via this method


class PaymentNetwork(Enum):
    """Payment networks/rails"""
    ACH = "ach"
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    DEBIT = "debit"
    PAYPAL = "paypal"
    VENMO = "venmo"
    CASHAPP = "cashapp"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


@dataclass
class PaymentFailure:
    """Record of a payment failure"""
    failure_id: str
    account_id: str
    consumer_id: str
    amount: float
    network: PaymentNetwork
    failure_type: FailureType
    failure_code: str
    failure_message: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    resolved: bool = False
    resolution_action: RecoveryAction | None = None


@dataclass
class RecoveryPlan:
    """Recovery plan for a failed payment"""
    plan_id: str
    failure_id: str
    account_id: str
    original_amount: float

    # Recovery strategy
    actions: list[dict[str, Any]] = field(default_factory=list)
    current_action_index: int = 0

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    next_action_at: datetime | None = None
    expires_at: datetime | None = None

    # Status
    status: str = "active"  # active, completed, abandoned
    total_recovered: float = 0.0


@dataclass
class ConsumerPaymentProfile:
    """Consumer's payment behavior profile"""
    consumer_id: str

    # Payment methods on file
    payment_methods: list[dict[str, Any]] = field(default_factory=list)
    preferred_method: str | None = None

    # Historical patterns
    total_payments: int = 0
    successful_payments: int = 0
    failed_payments: int = 0

    # Failure patterns
    failure_history: list[FailureType] = field(default_factory=list)
    common_failure_type: FailureType | None = None

    # Timing patterns
    successful_payment_days: list[int] = field(default_factory=list)  # Day of month
    successful_payment_hours: list[int] = field(default_factory=list)
    estimated_payday: int | None = None  # Day of month


class FailureAnalyzer:
    """
    Analyzes payment failures to determine root cause and optimal recovery
    """

    def __init__(self):
        self.failure_patterns: dict[str, list[FailureType]] = defaultdict(list)
        self.recovery_success: dict[tuple[FailureType, RecoveryAction], list[bool]] = defaultdict(list)

    def analyze(self, failure: PaymentFailure) -> dict[str, Any]:
        """Analyze failure and determine root cause"""
        analysis = {
            "failure_id": failure.failure_id,
            "failure_type": failure.failure_type,
            "root_cause": self._determine_root_cause(failure),
            "is_temporary": self._is_temporary(failure),
            "retry_likelihood": self._calculate_retry_success(failure),
            "recommended_actions": self._recommend_actions(failure),
            "optimal_retry_timing": self._calculate_optimal_timing(failure)
        }

        # Record pattern
        self.failure_patterns[failure.consumer_id].append(failure.failure_type)

        return analysis

    def _determine_root_cause(self, failure: PaymentFailure) -> str:
        """Determine root cause of failure"""
        root_causes = {
            FailureType.INSUFFICIENT_FUNDS: "Consumer lacks funds - likely timing issue",
            FailureType.CARD_DECLINED: "Card issuer declined - may be fraud protection or limit",
            FailureType.CARD_EXPIRED: "Payment method expired - needs update",
            FailureType.INVALID_ACCOUNT: "Account information incorrect or closed",
            FailureType.BANK_REJECT: "Bank rejected transaction - may need verification",
            FailureType.NETWORK_ERROR: "Network/processing issue - transient",
            FailureType.FRAUD_BLOCK: "Flagged as potential fraud - needs verification",
            FailureType.LIMIT_EXCEEDED: "Transaction limit exceeded - try smaller amount",
            FailureType.TIMEOUT: "Processing timeout - transient issue",
            FailureType.UNKNOWN: "Unknown failure - investigate"
        }
        return root_causes.get(failure.failure_type, "Unknown cause")

    def _is_temporary(self, failure: PaymentFailure) -> bool:
        """Determine if failure is temporary/recoverable"""
        temporary_types = {
            FailureType.INSUFFICIENT_FUNDS,
            FailureType.NETWORK_ERROR,
            FailureType.TIMEOUT,
            FailureType.LIMIT_EXCEEDED
        }
        return failure.failure_type in temporary_types

    def _calculate_retry_success(self, failure: PaymentFailure) -> float:
        """Calculate probability of successful retry"""
        base_rates = {
            FailureType.INSUFFICIENT_FUNDS: 0.45,  # Often succeeds on payday
            FailureType.CARD_DECLINED: 0.25,
            FailureType.CARD_EXPIRED: 0.05,  # Needs update
            FailureType.INVALID_ACCOUNT: 0.02,
            FailureType.BANK_REJECT: 0.15,
            FailureType.NETWORK_ERROR: 0.85,  # Usually transient
            FailureType.FRAUD_BLOCK: 0.10,
            FailureType.LIMIT_EXCEEDED: 0.60,  # Try smaller amount
            FailureType.TIMEOUT: 0.80,
            FailureType.UNKNOWN: 0.30
        }

        base_rate = base_rates.get(failure.failure_type, 0.30)

        # Adjust for retry count (diminishing returns)
        retry_factor = 0.8 ** failure.retry_count

        # Adjust for consumer history
        consumer_failures = self.failure_patterns.get(failure.consumer_id, [])
        if len(consumer_failures) > 5:
            # Chronic failure pattern
            retry_factor *= 0.7

        return base_rate * retry_factor

    def _recommend_actions(self, failure: PaymentFailure) -> list[RecoveryAction]:
        """Recommend recovery actions"""
        recommendations = {
            FailureType.INSUFFICIENT_FUNDS: [
                RecoveryAction.RETRY_PAYDAY,
                RecoveryAction.SPLIT_PAYMENT,
                RecoveryAction.RETRY_DIFFERENT_TIME
            ],
            FailureType.CARD_DECLINED: [
                RecoveryAction.RETRY_SAME,
                RecoveryAction.ALTERNATIVE_METHOD,
                RecoveryAction.REQUEST_UPDATE
            ],
            FailureType.CARD_EXPIRED: [
                RecoveryAction.REQUEST_UPDATE,
                RecoveryAction.ALTERNATIVE_METHOD
            ],
            FailureType.INVALID_ACCOUNT: [
                RecoveryAction.REQUEST_UPDATE,
                RecoveryAction.ESCALATE
            ],
            FailureType.BANK_REJECT: [
                RecoveryAction.RETRY_DIFFERENT_TIME,
                RecoveryAction.ALTERNATIVE_METHOD,
                RecoveryAction.ESCALATE
            ],
            FailureType.NETWORK_ERROR: [
                RecoveryAction.RETRY_SAME
            ],
            FailureType.FRAUD_BLOCK: [
                RecoveryAction.ESCALATE,
                RecoveryAction.ALTERNATIVE_METHOD
            ],
            FailureType.LIMIT_EXCEEDED: [
                RecoveryAction.SPLIT_PAYMENT,
                RecoveryAction.RETRY_DIFFERENT_TIME
            ],
            FailureType.TIMEOUT: [
                RecoveryAction.RETRY_SAME
            ],
            FailureType.UNKNOWN: [
                RecoveryAction.RETRY_SAME,
                RecoveryAction.ESCALATE
            ]
        }

        return recommendations.get(failure.failure_type, [RecoveryAction.ESCALATE])

    def _calculate_optimal_timing(self, failure: PaymentFailure) -> dict[str, Any]:
        """Calculate optimal retry timing"""
        now = datetime.now()

        if failure.failure_type == FailureType.INSUFFICIENT_FUNDS:
            # Try on likely payday
            day = now.day
            if day < 15:
                next_payday = now.replace(day=15)
            else:
                next_month = now.replace(day=1) + timedelta(days=32)
                next_payday = next_month.replace(day=1)

            return {
                "recommended_date": next_payday.isoformat(),
                "recommended_hour": 10,  # Morning after deposit clears
                "reason": "Waiting for likely payday",
                "confidence": 0.65
            }

        elif failure.failure_type in [FailureType.NETWORK_ERROR, FailureType.TIMEOUT]:
            # Retry soon
            return {
                "recommended_date": (now + timedelta(hours=2)).isoformat(),
                "recommended_hour": (now.hour + 2) % 24,
                "reason": "Transient error - retry soon",
                "confidence": 0.80
            }

        elif failure.failure_type == FailureType.LIMIT_EXCEEDED:
            # Try tomorrow (daily limit reset)
            return {
                "recommended_date": (now + timedelta(days=1)).isoformat(),
                "recommended_hour": 9,
                "reason": "Daily limit likely reset",
                "confidence": 0.55
            }

        else:
            # Default: wait 3 days
            return {
                "recommended_date": (now + timedelta(days=3)).isoformat(),
                "recommended_hour": 14,
                "reason": "Standard retry interval",
                "confidence": 0.35
            }

    def record_recovery_outcome(
        self,
        failure_type: FailureType,
        action: RecoveryAction,
        success: bool
    ) -> None:
        """Record outcome for learning"""
        key = (failure_type, action)
        self.recovery_success[key].append(success)

    def get_best_action(self, failure_type: FailureType) -> RecoveryAction:
        """Get best action based on historical success"""
        best_action = RecoveryAction.RETRY_SAME
        best_rate = 0.0

        for (ft, action), outcomes in self.recovery_success.items():
            if ft == failure_type and outcomes:
                success_rate = sum(outcomes) / len(outcomes)
                if success_rate > best_rate:
                    best_rate = success_rate
                    best_action = action

        return best_action


class PaydayDetector:
    """
    Detects consumer payday patterns for optimal retry scheduling
    """

    def __init__(self):
        self.payment_patterns: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

    def record_payment(
        self,
        consumer_id: str,
        payment_date: datetime,
        amount: float
    ) -> None:
        """Record successful payment for pattern detection"""
        self.payment_patterns[consumer_id].append((payment_date, amount))

        # Keep last 12 months
        cutoff = datetime.now() - timedelta(days=365)
        self.payment_patterns[consumer_id] = [
            (d, a) for d, a in self.payment_patterns[consumer_id]
            if d > cutoff
        ]

    def detect_payday(self, consumer_id: str) -> dict[str, Any]:
        """Detect likely payday pattern"""
        payments = self.payment_patterns.get(consumer_id, [])

        if len(payments) < 3:
            return {
                "detected": False,
                "confidence": 0.0,
                "pattern": "unknown"
            }

        # Analyze day of month
        days = [d.day for d, _ in payments]
        day_counts: dict[int, int] = defaultdict(int)
        for day in days:
            day_counts[day] += 1

        # Find most common day
        most_common_day = max(day_counts.items(), key=lambda x: x[1])

        # Check for patterns
        if most_common_day[1] >= len(payments) * 0.5:
            # Strong pattern
            if most_common_day[0] in [1, 2, 3]:
                pattern = "monthly_first"
            elif most_common_day[0] in [14, 15, 16]:
                pattern = "monthly_fifteenth"
            elif most_common_day[0] in [28, 29, 30, 31]:
                pattern = "monthly_last"
            else:
                pattern = "monthly_custom"

            return {
                "detected": True,
                "confidence": most_common_day[1] / len(payments),
                "pattern": pattern,
                "likely_day": most_common_day[0],
                "next_payday": self._calculate_next_payday(most_common_day[0])
            }

        # Check for biweekly
        # Group by week of year
        weeks = [d.isocalendar()[1] for d, _ in payments]
        week_diffs = [weeks[i+1] - weeks[i] for i in range(len(weeks)-1)]

        if week_diffs and sum(1 for d in week_diffs if d == 2) >= len(week_diffs) * 0.5:
            return {
                "detected": True,
                "confidence": 0.6,
                "pattern": "biweekly",
                "next_payday": self._calculate_next_biweekly(payments[-1][0])
            }

        return {
            "detected": False,
            "confidence": 0.3,
            "pattern": "irregular"
        }

    def _calculate_next_payday(self, day_of_month: int) -> datetime:
        """Calculate next occurrence of day of month"""
        now = datetime.now()

        if now.day < day_of_month:
            return now.replace(day=min(day_of_month, 28))
        else:
            next_month = now.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=min(day_of_month, 28))

    def _calculate_next_biweekly(self, last_payment: datetime) -> datetime:
        """Calculate next biweekly payday"""
        days_since = (datetime.now() - last_payment).days
        days_until = 14 - (days_since % 14)
        return datetime.now() + timedelta(days=days_until)


class PaymentRouter:
    """
    Routes payments through optimal networks based on success patterns
    """

    def __init__(self):
        self.network_success: dict[PaymentNetwork, list[bool]] = defaultdict(list)
        self.network_costs = {
            PaymentNetwork.ACH: 0.25,
            PaymentNetwork.VISA: 0.029,  # 2.9%
            PaymentNetwork.MASTERCARD: 0.029,
            PaymentNetwork.AMEX: 0.035,
            PaymentNetwork.DISCOVER: 0.028,
            PaymentNetwork.DEBIT: 0.015,
            PaymentNetwork.PAYPAL: 0.029,
            PaymentNetwork.VENMO: 0.019,
            PaymentNetwork.CASHAPP: 0.025,
            PaymentNetwork.APPLE_PAY: 0.029,
            PaymentNetwork.GOOGLE_PAY: 0.029
        }

    def get_optimal_network(
        self,
        amount: float,
        available_methods: list[PaymentNetwork]
    ) -> PaymentNetwork:
        """Get optimal payment network based on cost and success rate"""
        if not available_methods:
            return PaymentNetwork.ACH

        best_network = available_methods[0]
        best_score = 0.0

        for network in available_methods:
            success_rate = self._get_success_rate(network)
            cost = self._calculate_cost(network, amount)

            # Score = expected value minus cost
            expected_value = amount * success_rate
            score = expected_value - cost

            if score > best_score:
                best_score = score
                best_network = network

        return best_network

    def _get_success_rate(self, network: PaymentNetwork) -> float:
        """Get historical success rate for network"""
        outcomes = self.network_success.get(network, [])
        if not outcomes:
            # Default rates
            defaults = {
                PaymentNetwork.ACH: 0.85,
                PaymentNetwork.VISA: 0.92,
                PaymentNetwork.MASTERCARD: 0.91,
                PaymentNetwork.DEBIT: 0.95,
                PaymentNetwork.PAYPAL: 0.88,
            }
            return defaults.get(network, 0.85)

        return sum(outcomes) / len(outcomes)

    def _calculate_cost(self, network: PaymentNetwork, amount: float) -> float:
        """Calculate processing cost"""
        rate = self.network_costs.get(network, 0.03)

        if network == PaymentNetwork.ACH:
            return rate  # Flat fee
        else:
            return amount * rate  # Percentage

    def record_outcome(self, network: PaymentNetwork, success: bool) -> None:
        """Record payment outcome"""
        self.network_success[network].append(success)

        # Keep last 1000
        if len(self.network_success[network]) > 1000:
            self.network_success[network].pop(0)


class FailureRecoveryEngine:
    """
    Master engine for payment failure recovery

    Coordinates all recovery components for maximum payment capture
    """

    def __init__(self):
        self.analyzer = FailureAnalyzer()
        self.payday_detector = PaydayDetector()
        self.router = PaymentRouter()

        self.active_plans: dict[str, RecoveryPlan] = {}
        self.failure_history: list[PaymentFailure] = []
        self.recovery_metrics = {
            "total_failures": 0,
            "total_recovered": 0,
            "recovery_rate": 0.0,
            "avg_recovery_time_hours": 0.0
        }

    def handle_failure(self, failure: PaymentFailure) -> RecoveryPlan:
        """Handle a new payment failure"""
        self.failure_history.append(failure)
        self.recovery_metrics["total_failures"] += 1

        # Analyze failure
        analysis = self.analyzer.analyze(failure)

        # Detect payday pattern
        payday_info = self.payday_detector.detect_payday(failure.consumer_id)

        # Create recovery plan
        plan = self._create_recovery_plan(failure, analysis, payday_info)

        self.active_plans[plan.plan_id] = plan

        return plan

    def _create_recovery_plan(
        self,
        failure: PaymentFailure,
        analysis: dict[str, Any],
        payday_info: dict[str, Any]
    ) -> RecoveryPlan:
        """Create recovery plan based on analysis"""
        plan_id = hashlib.sha256(
            f"{failure.failure_id}{datetime.now()}".encode()
        ).hexdigest()[:16]

        actions = []

        # Build action sequence
        for i, rec_action in enumerate(analysis["recommended_actions"][:4]):
            timing = analysis["optimal_retry_timing"]

            if rec_action == RecoveryAction.RETRY_PAYDAY and payday_info.get("detected"):
                timing = {
                    "recommended_date": payday_info["next_payday"].isoformat(),
                    "recommended_hour": 10,
                    "reason": f"Detected payday pattern: {payday_info['pattern']}"
                }

            action = {
                "action": rec_action.value,
                "sequence": i,
                "timing": timing,
                "amount": failure.amount if rec_action != RecoveryAction.SPLIT_PAYMENT
                          else failure.amount / 2,
                "status": "pending"
            }
            actions.append(action)

        # Set expiration (30 days)
        expires_at = datetime.now() + timedelta(days=30)

        plan = RecoveryPlan(
            plan_id=plan_id,
            failure_id=failure.failure_id,
            account_id=failure.account_id,
            original_amount=failure.amount,
            actions=actions,
            expires_at=expires_at
        )

        if actions:
            first_timing = actions[0]["timing"]
            plan.next_action_at = datetime.fromisoformat(first_timing["recommended_date"])

        return plan

    def execute_recovery_action(self, plan_id: str) -> dict[str, Any]:
        """Execute next recovery action"""
        plan = self.active_plans.get(plan_id)
        if not plan or plan.status != "active":
            return {"success": False, "error": "Invalid or inactive plan"}

        if plan.current_action_index >= len(plan.actions):
            plan.status = "completed"
            return {"success": False, "error": "No more actions"}

        action = plan.actions[plan.current_action_index]

        # Simulate execution
        result = self._execute_action(plan, action)

        # Update action status
        action["status"] = "completed"
        action["result"] = result

        if result["success"]:
            plan.total_recovered += result.get("amount_recovered", 0)
            self.recovery_metrics["total_recovered"] += result.get("amount_recovered", 0)

            if plan.total_recovered >= plan.original_amount * 0.99:
                plan.status = "completed"

            # Record success
            self.analyzer.record_recovery_outcome(
                FailureType.INSUFFICIENT_FUNDS,  # Would use actual type
                RecoveryAction(action["action"]),
                True
            )
        else:
            # Move to next action
            plan.current_action_index += 1

            if plan.current_action_index < len(plan.actions):
                next_action = plan.actions[plan.current_action_index]
                plan.next_action_at = datetime.fromisoformat(
                    next_action["timing"]["recommended_date"]
                )

            self.analyzer.record_recovery_outcome(
                FailureType.INSUFFICIENT_FUNDS,
                RecoveryAction(action["action"]),
                False
            )

        # Update recovery rate
        if self.recovery_metrics["total_failures"] > 0:
            self.recovery_metrics["recovery_rate"] = (
                self.recovery_metrics["total_recovered"] /
                sum(f.amount for f in self.failure_history)
            )

        return result

    def _execute_action(
        self,
        plan: RecoveryPlan,
        action: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a single recovery action"""
        action_type = RecoveryAction(action["action"])

        if action_type in [RecoveryAction.RETRY_SAME, RecoveryAction.RETRY_DIFFERENT_TIME,
                          RecoveryAction.RETRY_PAYDAY]:
            # Simulate payment retry
            success = random.random() < 0.45  # 45% success rate
            return {
                "success": success,
                "action": action_type.value,
                "amount_recovered": action["amount"] if success else 0,
                "executed_at": datetime.now().isoformat()
            }

        elif action_type == RecoveryAction.SPLIT_PAYMENT:
            # Try smaller amount
            success = random.random() < 0.55  # Higher success with smaller amount
            return {
                "success": success,
                "action": action_type.value,
                "amount_recovered": action["amount"] if success else 0,
                "note": "Split payment attempted"
            }

        elif action_type == RecoveryAction.REQUEST_UPDATE:
            # Request payment method update
            return {
                "success": True,
                "action": action_type.value,
                "amount_recovered": 0,
                "note": "Update request sent"
            }

        elif action_type == RecoveryAction.ALTERNATIVE_METHOD:
            # Try alternative method
            success = random.random() < 0.35
            return {
                "success": success,
                "action": action_type.value,
                "amount_recovered": plan.original_amount if success else 0
            }

        else:
            return {
                "success": False,
                "action": action_type.value,
                "note": "Action requires manual intervention"
            }

    def get_pending_actions(self) -> list[dict[str, Any]]:
        """Get all pending recovery actions"""
        pending = []

        for plan_id, plan in self.active_plans.items():
            if plan.status != "active":
                continue

            if plan.next_action_at and plan.next_action_at <= datetime.now():
                pending.append({
                    "plan_id": plan_id,
                    "account_id": plan.account_id,
                    "amount": plan.original_amount,
                    "action": plan.actions[plan.current_action_index],
                    "scheduled_for": plan.next_action_at.isoformat()
                })

        return sorted(pending, key=lambda x: x["scheduled_for"])

    def get_metrics(self) -> dict[str, Any]:
        """Get recovery metrics"""
        active_plans = sum(1 for p in self.active_plans.values() if p.status == "active")
        completed_plans = sum(1 for p in self.active_plans.values() if p.status == "completed")

        return {
            **self.recovery_metrics,
            "active_plans": active_plans,
            "completed_plans": completed_plans,
            "total_plans": len(self.active_plans),
            "pending_actions": len(self.get_pending_actions())
        }


# Demonstration
if __name__ == "__main__":
    print("=== PAYMENT FAILURE RECOVERY DEMO ===\n")

    engine = FailureRecoveryEngine()

    # Simulate payment failure
    failure = PaymentFailure(
        failure_id="F001",
        account_id="A001",
        consumer_id="C001",
        amount=147.50,
        network=PaymentNetwork.ACH,
        failure_type=FailureType.INSUFFICIENT_FUNDS,
        failure_code="R01",
        failure_message="Insufficient funds in account"
    )

    print(f"Failure: {failure.failure_type.value}")
    print(f"Amount: ${failure.amount}")
    print()

    # Handle failure
    plan = engine.handle_failure(failure)

    print(f"Recovery Plan: {plan.plan_id}")
    print(f"Actions scheduled: {len(plan.actions)}")
    for i, action in enumerate(plan.actions):
        print(f"  {i+1}. {action['action']} - {action['timing']['reason']}")

    print()

    # Execute recovery actions
    for i in range(3):
        result = engine.execute_recovery_action(plan.plan_id)
        print(f"Action {i+1}: {result['action']} - {'Success' if result['success'] else 'Failed'}")
        if result.get("amount_recovered"):
            print(f"  Recovered: ${result['amount_recovered']}")

    print()

    # Get metrics
    metrics = engine.get_metrics()
    print("Recovery Metrics:")
    print(f"  Total Failures: {metrics['total_failures']}")
    print(f"  Total Recovered: ${metrics['total_recovered']:.2f}")
    print(f"  Recovery Rate: {metrics['recovery_rate']:.1%}")
    print(f"  Active Plans: {metrics['active_plans']}")
