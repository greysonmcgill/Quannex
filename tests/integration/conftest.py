"""
QUAN Integration Test Configuration and Shared Fixtures

Provides common fixtures, mock services, and test utilities for
end-to-end integration testing of the QUAN debt collection system.
"""

import pytest
import asyncio
import uuid
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import random
import string


# =============================================================================
# TEST CONSTANTS
# =============================================================================

TEST_CLIENT_ID = "test_client_001"
TEST_CREDITOR_ID = "KLARNA_TEST"
TEST_CREDITOR_NAME = "Klarna Test"
DEFAULT_TEST_BALANCE = Decimal("185.00")
DEFAULT_TEST_DPD = 45


# =============================================================================
# MOCK SERVICES
# =============================================================================

class MockKafkaProducer:
    """Mock Kafka producer for testing"""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.topics: Dict[str, List[Dict]] = {}

    async def send(self, topic: str, value: Dict, key: str = None):
        message = {"topic": topic, "key": key, "value": value, "timestamp": datetime.utcnow()}
        self.messages.append(message)
        if topic not in self.topics:
            self.topics[topic] = []
        self.topics[topic].append(message)
        return {"status": "sent", "offset": len(self.messages)}

    def get_messages(self, topic: str = None) -> List[Dict]:
        if topic:
            return self.topics.get(topic, [])
        return self.messages

    def clear(self):
        self.messages.clear()
        self.topics.clear()


class MockPaymentProcessor:
    """Mock payment processor for testing"""

    def __init__(self):
        self.transactions: Dict[str, Dict] = {}
        self.should_fail = False
        self.failure_reason = None
        self.auth_codes: Dict[str, str] = {}

    async def authorize(self, amount: Decimal, payment_method: Dict, metadata: Dict) -> tuple:
        if self.should_fail:
            return False, "", self.failure_reason or "Transaction declined"

        auth_id = f"auth_{uuid.uuid4().hex[:12]}"
        self.auth_codes[auth_id] = {"amount": amount, "status": "authorized", "metadata": metadata}
        return True, auth_id, None

    async def capture(self, auth_id: str, amount: Decimal = None) -> tuple:
        if auth_id not in self.auth_codes:
            return False, "", "Authorization not found"

        if self.should_fail:
            return False, "", self.failure_reason or "Capture failed"

        capture_id = f"cap_{uuid.uuid4().hex[:12]}"
        self.transactions[capture_id] = {
            "auth_id": auth_id,
            "amount": amount or self.auth_codes[auth_id]["amount"],
            "status": "captured",
            "timestamp": datetime.utcnow()
        }
        return True, capture_id, None

    async def refund(self, transaction_id: str, amount: Decimal = None) -> tuple:
        if transaction_id not in self.transactions:
            return False, "", "Transaction not found"

        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        return True, refund_id, None

    def set_failure(self, should_fail: bool, reason: str = None):
        self.should_fail = should_fail
        self.failure_reason = reason

    def reset(self):
        self.transactions.clear()
        self.auth_codes.clear()
        self.should_fail = False
        self.failure_reason = None


class MockCommunicationService:
    """Mock communication service for testing"""

    def __init__(self):
        self.sent_messages: List[Dict] = []
        self.sms_log: List[Dict] = []
        self.email_log: List[Dict] = []
        self.voice_log: List[Dict] = []
        self.should_fail = False

    async def send_sms(self, to: str, message: str, metadata: Dict = None) -> Dict:
        if self.should_fail:
            return {"success": False, "error": "SMS delivery failed"}

        msg_id = f"sms_{uuid.uuid4().hex[:10]}"
        record = {
            "id": msg_id,
            "to": to,
            "message": message,
            "timestamp": datetime.utcnow(),
            "metadata": metadata
        }
        self.sms_log.append(record)
        self.sent_messages.append({"channel": "sms", **record})
        return {"success": True, "message_id": msg_id}

    async def send_email(self, to: str, subject: str, body: str, metadata: Dict = None) -> Dict:
        if self.should_fail:
            return {"success": False, "error": "Email delivery failed"}

        msg_id = f"email_{uuid.uuid4().hex[:10]}"
        record = {
            "id": msg_id,
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": datetime.utcnow(),
            "metadata": metadata
        }
        self.email_log.append(record)
        self.sent_messages.append({"channel": "email", **record})
        return {"success": True, "message_id": msg_id}

    async def make_call(self, to: str, script: Dict, metadata: Dict = None) -> Dict:
        if self.should_fail:
            return {"success": False, "error": "Call failed"}

        call_id = f"call_{uuid.uuid4().hex[:10]}"
        record = {
            "id": call_id,
            "to": to,
            "script": script,
            "timestamp": datetime.utcnow(),
            "duration_seconds": random.randint(30, 300),
            "metadata": metadata
        }
        self.voice_log.append(record)
        self.sent_messages.append({"channel": "voice", **record})
        return {"success": True, "call_id": call_id, "duration": record["duration_seconds"]}

    def get_contact_count(self, account_id: str = None) -> int:
        if account_id:
            return sum(1 for m in self.sent_messages if m.get("metadata", {}).get("account_id") == account_id)
        return len(self.sent_messages)

    def reset(self):
        self.sent_messages.clear()
        self.sms_log.clear()
        self.email_log.clear()
        self.voice_log.clear()
        self.should_fail = False


class MockAuditLogger:
    """Mock audit logger for compliance tracking"""

    def __init__(self):
        self.entries: List[Dict] = []
        self.chain_hashes: List[str] = []

    def log(self, event_type: str, account_id: str, action: str, details: Dict = None) -> str:
        entry_id = str(uuid.uuid4())

        # Build hash chain
        prev_hash = self.chain_hashes[-1] if self.chain_hashes else "genesis"
        entry_data = f"{entry_id}{event_type}{account_id}{action}{prev_hash}"
        entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()

        entry = {
            "entry_id": entry_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "account_id": account_id,
            "action": action,
            "details": details or {},
            "hash": entry_hash,
            "prev_hash": prev_hash
        }

        self.entries.append(entry)
        self.chain_hashes.append(entry_hash)
        return entry_id

    def verify_chain(self) -> bool:
        """Verify integrity of audit chain"""
        if not self.entries:
            return True

        for i, entry in enumerate(self.entries):
            expected_prev = self.chain_hashes[i - 1] if i > 0 else "genesis"
            if entry["prev_hash"] != expected_prev:
                return False
        return True

    def get_entries(self, account_id: str = None, event_type: str = None) -> List[Dict]:
        entries = self.entries
        if account_id:
            entries = [e for e in entries if e["account_id"] == account_id]
        if event_type:
            entries = [e for e in entries if e["event_type"] == event_type]
        return entries

    def reset(self):
        self.entries.clear()
        self.chain_hashes.clear()


# =============================================================================
# DATA GENERATORS
# =============================================================================

class TestDataGenerator:
    """Generate test data for integration tests"""

    STATE_CODES = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]
    CREDITOR_TYPES = ["bnpl", "medical", "subscription", "fintech", "telecom", "utility"]
    FIRST_NAMES = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "James", "Jessica"]
    LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]

    @classmethod
    def generate_consumer_id(cls) -> str:
        return f"C{uuid.uuid4().hex[:8].upper()}"

    @classmethod
    def generate_account_id(cls) -> str:
        return f"ACC{uuid.uuid4().hex[:10].upper()}"

    @classmethod
    def generate_phone(cls) -> str:
        return f"+1555{random.randint(1000000, 9999999)}"

    @classmethod
    def generate_email(cls, name: str = None) -> str:
        if not name:
            name = random.choice(cls.FIRST_NAMES).lower()
        domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "icloud.com"])
        return f"{name}{random.randint(100, 999)}@{domain}"

    @classmethod
    def generate_account(
        cls,
        account_id: str = None,
        balance: Decimal = None,
        days_past_due: int = None,
        state: str = None,
        creditor_type: str = None,
        with_contact_info: bool = True
    ) -> Dict[str, Any]:
        """Generate a complete test account"""

        first_name = random.choice(cls.FIRST_NAMES)
        last_name = random.choice(cls.LAST_NAMES)

        account = {
            "account_id": account_id or cls.generate_account_id(),
            "consumer_id": cls.generate_consumer_id(),
            "balance": float(balance or Decimal(str(random.uniform(50, 500)))),
            "original_balance": float((balance or Decimal("200")) * Decimal("1.1")),
            "original_creditor": f"Test Creditor {random.randint(1, 100)}",
            "creditor_type": creditor_type or random.choice(cls.CREDITOR_TYPES),
            "debtor_name": f"{first_name} {last_name}",
            "debtor_first_name": first_name,
            "debtor_last_name": last_name,
            "debtor_state": state or random.choice(cls.STATE_CODES),
            "days_overdue": days_past_due or random.randint(30, 180),
            "charge_off_date": (datetime.utcnow() - timedelta(days=random.randint(30, 365))).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }

        if with_contact_info:
            account.update({
                "debtor_phone": cls.generate_phone(),
                "debtor_email": cls.generate_email(first_name),
                "sms_consent": random.random() > 0.2,
                "email_consent": random.random() > 0.1,
                "voice_consent": random.random() > 0.3,
                "debtor_address": {
                    "street": f"{random.randint(100, 9999)} Test Street",
                    "city": "Test City",
                    "state": account["debtor_state"],
                    "zip": f"{random.randint(10000, 99999)}"
                }
            })

        return account

    @classmethod
    def generate_portfolio(cls, count: int, **kwargs) -> List[Dict]:
        """Generate a portfolio of test accounts"""
        return [cls.generate_account(**kwargs) for _ in range(count)]

    @classmethod
    def generate_payment_method(cls, method_type: str = "card") -> Dict:
        """Generate test payment method"""
        if method_type == "card":
            return {
                "type": "card",
                "token_id": f"tok_{uuid.uuid4().hex[:16]}",
                "last_four": f"{random.randint(1000, 9999)}",
                "brand": random.choice(["visa", "mastercard", "amex"]),
                "expiry_month": random.randint(1, 12),
                "expiry_year": datetime.utcnow().year + random.randint(1, 5)
            }
        else:  # bank_account / ACH
            return {
                "type": "bank_account",
                "token_id": f"ba_{uuid.uuid4().hex[:16]}",
                "last_four": f"{random.randint(1000, 9999)}",
                "bank_name": random.choice(["Chase", "Bank of America", "Wells Fargo", "Citi"]),
                "routing_last_four": f"{random.randint(1000, 9999)}"
            }

    @classmethod
    def generate_settlement_offer(cls, account: Dict, rate: float = 0.5) -> Dict:
        """Generate a settlement offer for an account"""
        balance = Decimal(str(account["balance"]))
        settlement_amount = balance * Decimal(str(rate))

        return {
            "offer_id": f"OFF_{uuid.uuid4().hex[:10]}",
            "account_id": account["account_id"],
            "balance": float(balance),
            "settlement_amount": float(settlement_amount),
            "settlement_rate": rate,
            "payment_type": "lump_sum",
            "expiration_date": (datetime.utcnow() + timedelta(days=14)).isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def kafka_producer():
    """Mock Kafka producer"""
    producer = MockKafkaProducer()
    yield producer
    producer.clear()


@pytest.fixture
def payment_processor():
    """Mock payment processor"""
    processor = MockPaymentProcessor()
    yield processor
    processor.reset()


@pytest.fixture
def communication_service():
    """Mock communication service"""
    service = MockCommunicationService()
    yield service
    service.reset()


@pytest.fixture
def audit_logger():
    """Mock audit logger"""
    logger = MockAuditLogger()
    yield logger
    logger.reset()


@pytest.fixture
def data_generator():
    """Test data generator"""
    return TestDataGenerator


@pytest.fixture
def test_account(data_generator):
    """Generate a single test account"""
    return data_generator.generate_account(
        balance=DEFAULT_TEST_BALANCE,
        days_past_due=DEFAULT_TEST_DPD,
        state="CA"
    )


@pytest.fixture
def test_portfolio(data_generator):
    """Generate a small test portfolio"""
    return data_generator.generate_portfolio(10)


@pytest.fixture
def large_portfolio(data_generator):
    """Generate a larger test portfolio for stress testing"""
    return data_generator.generate_portfolio(100)


@pytest.fixture
def test_payment_method(data_generator):
    """Generate test payment method"""
    return data_generator.generate_payment_method("card")


@pytest.fixture
def test_bank_account(data_generator):
    """Generate test bank account payment method"""
    return data_generator.generate_payment_method("bank_account")


# =============================================================================
# TEST UTILITIES
# =============================================================================

class TestAssertions:
    """Custom assertions for integration tests"""

    @staticmethod
    def assert_compliance_valid(result: Dict):
        """Assert compliance check passed"""
        assert result.get("compliant", result.get("valid", False)), \
            f"Compliance check failed: {result.get('reason', result.get('violations', 'Unknown'))}"

    @staticmethod
    def assert_payment_success(result: Dict):
        """Assert payment was successful"""
        assert result.get("success", False), \
            f"Payment failed: {result.get('error', 'Unknown error')}"

    @staticmethod
    def assert_in_range(value: float, min_val: float, max_val: float, name: str = "Value"):
        """Assert value is within expected range"""
        assert min_val <= value <= max_val, \
            f"{name} {value} not in expected range [{min_val}, {max_val}]"

    @staticmethod
    def assert_audit_complete(audit_logger: MockAuditLogger, account_id: str, expected_events: List[str]):
        """Assert all expected audit events exist"""
        entries = audit_logger.get_entries(account_id=account_id)
        event_types = [e["event_type"] for e in entries]
        for event in expected_events:
            assert event in event_types, f"Missing audit event: {event}"


@pytest.fixture
def assertions():
    """Custom test assertions"""
    return TestAssertions


# =============================================================================
# PERFORMANCE TRACKING
# =============================================================================

class PerformanceTracker:
    """Track performance metrics during tests"""

    def __init__(self):
        self.timings: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
        self.start_times: Dict[str, datetime] = {}

    def start_timer(self, name: str):
        self.start_times[name] = datetime.utcnow()

    def stop_timer(self, name: str) -> float:
        if name not in self.start_times:
            return 0.0
        elapsed = (datetime.utcnow() - self.start_times[name]).total_seconds()
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(elapsed)
        del self.start_times[name]
        return elapsed

    def increment(self, name: str, amount: int = 1):
        self.counters[name] = self.counters.get(name, 0) + amount

    def get_average(self, name: str) -> float:
        if name not in self.timings or not self.timings[name]:
            return 0.0
        return sum(self.timings[name]) / len(self.timings[name])

    def get_percentile(self, name: str, percentile: float) -> float:
        if name not in self.timings or not self.timings[name]:
            return 0.0
        sorted_times = sorted(self.timings[name])
        idx = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def get_report(self) -> Dict:
        return {
            "timings": {
                name: {
                    "count": len(times),
                    "total": sum(times),
                    "avg": sum(times) / len(times) if times else 0,
                    "min": min(times) if times else 0,
                    "max": max(times) if times else 0,
                    "p50": self.get_percentile(name, 50),
                    "p95": self.get_percentile(name, 95),
                    "p99": self.get_percentile(name, 99)
                }
                for name, times in self.timings.items()
            },
            "counters": self.counters
        }

    def reset(self):
        self.timings.clear()
        self.counters.clear()
        self.start_times.clear()


@pytest.fixture
def perf_tracker():
    """Performance tracker for tests"""
    tracker = PerformanceTracker()
    yield tracker
    tracker.reset()


# =============================================================================
# TEST MARKERS
# =============================================================================

# Custom markers for test categorization
pytest_plugins = []

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "stress: marks tests as stress tests")
    config.addinivalue_line("markers", "compliance: marks tests as compliance-related")
    config.addinivalue_line("markers", "payments: marks tests as payment-related")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
