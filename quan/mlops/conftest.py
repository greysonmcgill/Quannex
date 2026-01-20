"""
Pytest configuration and shared fixtures for QUAN ML tests

This conftest.py provides:
- Shared fixtures for all ML test modules
- Custom pytest hooks for CI integration
- Test collection and reporting customization
"""

import asyncio
import gc
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest

# Import test harness components
from quan.mlops.test_harness import (
    TestAccount,
    MockExternalService,
    MockPaymentGateway,
    MockSkipTraceService,
    MockCommunicationService,
    create_mock_context,
)

# Import QUAN modules
from quan.ml.prediction_engine import (
    FeatureStore,
    MLPredictionEngine,
    EnsemblePredictor,
    GradientBoostModel,
    NeuralNetModel,
    BayesianModel,
    PredictionTarget,
)
from quan.intelligence.engine import CollectionIntelligence


# =============================================================================
# SESSION-SCOPED FIXTURES (Created once per test session)
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def ml_engine():
    """Session-scoped ML prediction engine"""
    return MLPredictionEngine()


@pytest.fixture(scope="session")
def intelligence_engine():
    """Session-scoped collection intelligence engine"""
    return CollectionIntelligence()


# =============================================================================
# MODULE-SCOPED FIXTURES (Created once per test module)
# =============================================================================

@pytest.fixture(scope="module")
def trained_gradient_boost():
    """Pre-trained gradient boost model for testing"""
    model = GradientBoostModel(PredictionTarget.PAYMENT_PROBABILITY)

    # Create training data
    store = FeatureStore()
    training_data = []
    for i in range(50):
        account = TestAccount(
            account_id=f"TRAIN{i:03d}",
            balance=100 + i * 20,
            days_past_due=30 + i,
            shadow_score=500 + i * 5,
            payment_willingness=0.3 + (i % 5) * 0.15,
        )
        features = store.compute_features(account.to_dict())
        label = 1.0 if account.payment_willingness > 0.5 else 0.0
        training_data.append((features, label))

    model.train(training_data)
    return model


@pytest.fixture(scope="module")
def trained_ensemble():
    """Pre-trained ensemble predictor for testing"""
    predictor = EnsemblePredictor(PredictionTarget.PAYMENT_PROBABILITY)

    store = FeatureStore()
    training_data = []
    for i in range(50):
        account = TestAccount(
            account_id=f"TRAIN{i:03d}",
            balance=100 + i * 20,
            days_past_due=30 + i,
            shadow_score=500 + i * 5,
            payment_willingness=0.3 + (i % 5) * 0.15,
        )
        features = store.compute_features(account.to_dict())
        label = 1.0 if account.payment_willingness > 0.5 else 0.0
        training_data.append((features, label))

    predictor.train(training_data)
    return predictor


# =============================================================================
# FUNCTION-SCOPED FIXTURES (Created fresh for each test)
# =============================================================================

@pytest.fixture
def sample_account() -> TestAccount:
    """Standard test account"""
    return TestAccount(
        account_id="TEST001",
        balance=250.00,
        days_past_due=45,
        shadow_score=620,
        total_contacts=3,
        successful_contacts=1,
        response_rate=0.33,
        promise_kept_rate=0.5,
    )


@pytest.fixture
def sample_accounts() -> List[TestAccount]:
    """Multiple test accounts"""
    return [
        TestAccount(
            account_id="ACC001",
            balance=147.50,
            days_past_due=67,
            shadow_score=580,
            payment_willingness=0.6,
            has_mobile=True,
            email_valid=True,
        ),
        TestAccount(
            account_id="ACC002",
            balance=425.00,
            days_past_due=120,
            shadow_score=510,
            payment_willingness=0.3,
            has_mobile=True,
            email_valid=False,
        ),
        TestAccount(
            account_id="ACC003",
            balance=89.99,
            days_past_due=30,
            shadow_score=680,
            payment_willingness=0.7,
            has_mobile=False,
            email_valid=True,
        ),
        TestAccount(
            account_id="ACC004",
            balance=1250.00,
            days_past_due=200,
            shadow_score=450,
            payment_willingness=0.2,
            employed=False,
        ),
        TestAccount(
            account_id="ACC005",
            balance=55.00,
            days_past_due=15,
            shadow_score=720,
            payment_willingness=0.8,
        ),
    ]


@pytest.fixture
def large_portfolio() -> List[TestAccount]:
    """Large portfolio for stress testing"""
    accounts = []
    for i in range(100):
        accounts.append(TestAccount(
            account_id=f"LARGE{i:04d}",
            balance=50 + np.random.exponential(500),
            days_past_due=int(np.random.exponential(90)),
            shadow_score=int(300 + np.random.beta(5, 2) * 550),
            payment_willingness=np.random.beta(2, 3),
            has_mobile=np.random.random() > 0.2,
            email_valid=np.random.random() > 0.3,
            employed=np.random.random() > 0.15,
        ))
    return accounts


@pytest.fixture
def feature_store() -> FeatureStore:
    """Fresh feature store"""
    return FeatureStore()


@pytest.fixture
def prediction_engine() -> MLPredictionEngine:
    """Fresh ML prediction engine"""
    return MLPredictionEngine()


@pytest.fixture
def collection_intelligence() -> CollectionIntelligence:
    """Fresh collection intelligence engine"""
    return CollectionIntelligence()


@pytest.fixture
def ensemble_predictor() -> EnsemblePredictor:
    """Fresh ensemble predictor"""
    return EnsemblePredictor(PredictionTarget.PAYMENT_PROBABILITY)


@pytest.fixture
def gradient_boost_model() -> GradientBoostModel:
    """Fresh gradient boost model"""
    return GradientBoostModel(PredictionTarget.PAYMENT_PROBABILITY)


@pytest.fixture
def neural_net_model() -> NeuralNetModel:
    """Fresh neural network model"""
    return NeuralNetModel(PredictionTarget.PAYMENT_PROBABILITY)


@pytest.fixture
def bayesian_model() -> BayesianModel:
    """Fresh Bayesian model"""
    return BayesianModel(PredictionTarget.PAYMENT_PROBABILITY)


@pytest.fixture
def training_data(sample_accounts, feature_store) -> List[Tuple[Dict[str, float], float]]:
    """Training data from sample accounts"""
    data = []
    for acc in sample_accounts:
        features = feature_store.compute_features(acc.to_dict())
        label = 1.0 if acc.payment_willingness > 0.5 else 0.0
        data.append((features, label))
    return data


@pytest.fixture
def expanded_training_data(large_portfolio, feature_store) -> List[Tuple[Dict[str, float], float]]:
    """Larger training dataset"""
    data = []
    for acc in large_portfolio:
        features = feature_store.compute_features(acc.to_dict())
        label = 1.0 if acc.payment_willingness > 0.5 else 0.0
        data.append((features, label))
    return data


# =============================================================================
# MOCK SERVICE FIXTURES
# =============================================================================

@pytest.fixture
def mock_payment_gateway():
    """Mock payment gateway"""
    return MockPaymentGateway()


@pytest.fixture
def mock_skip_trace():
    """Mock skip trace service"""
    return MockSkipTraceService()


@pytest.fixture
def mock_communications():
    """Mock communication service"""
    return MockCommunicationService()


@pytest.fixture
def mock_context():
    """Complete mock context"""
    return create_mock_context()


@pytest.fixture
def failing_payment_gateway():
    """Payment gateway that fails 50% of time"""
    return MockPaymentGateway(failure_rate=0.5)


@pytest.fixture
def slow_service():
    """Slow external service for timeout testing"""
    return MockExternalService(response_delay=0.5)


# =============================================================================
# TEMPORARY FILE FIXTURES
# =============================================================================

@pytest.fixture
def temp_model_path():
    """Temporary path for model serialization tests"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_directory():
    """Temporary directory for test artifacts"""
    import tempfile
    import shutil

    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


# =============================================================================
# PERFORMANCE TRACKING FIXTURES
# =============================================================================

@dataclass
class PerformanceTracker:
    """Track test performance metrics"""
    test_name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    memory_before: int = 0
    memory_after: int = 0

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def memory_delta_kb(self) -> float:
        return (self.memory_after - self.memory_before) / 1024


@pytest.fixture
def performance_tracker(request):
    """Fixture to track test performance"""
    import tracemalloc

    tracker = PerformanceTracker(test_name=request.node.name)

    tracemalloc.start()
    current, peak = tracemalloc.get_traced_memory()
    tracker.memory_before = current
    tracker.start_time = time.perf_counter()

    yield tracker

    tracker.end_time = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracker.memory_after = current
    tracemalloc.stop()

    # Report if test was slow or memory-heavy
    if tracker.duration_ms > 100:
        print(f"\n  [SLOW] {tracker.test_name}: {tracker.duration_ms:.2f}ms")
    if tracker.memory_delta_kb > 1024:
        print(f"\n  [MEMORY] {tracker.test_name}: {tracker.memory_delta_kb:.2f}KB")


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    gc.collect()


# =============================================================================
# PYTEST HOOKS
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "memory: marks tests that check memory usage"
    )
    config.addinivalue_line(
        "markers", "thread_safety: marks thread safety tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers", "property: marks property-based tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify collected tests for CI optimization"""
    for item in items:
        # Mark slow tests
        if "Performance" in item.nodeid or "Memory" in item.nodeid:
            item.add_marker(pytest.mark.slow)

        # Mark memory tests
        if "Memory" in item.nodeid:
            item.add_marker(pytest.mark.memory)

        # Mark thread safety tests
        if "ThreadSafety" in item.nodeid:
            item.add_marker(pytest.mark.thread_safety)

        # Mark integration tests
        if "Integration" in item.nodeid or "Pipeline" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Mark property-based tests
        if "PropertyBased" in item.nodeid:
            item.add_marker(pytest.mark.property)


def pytest_report_header(config):
    """Add custom header to pytest report"""
    return [
        "QUAN ML Test Suite",
        f"Python: {sys.version}",
        f"NumPy: {np.__version__}",
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Custom terminal summary"""
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    total = passed + failed

    if total > 0:
        terminalreporter.write_sep("=", "QUAN ML Test Summary")
        terminalreporter.write_line(f"Pass Rate: {passed/total:.1%}")
        terminalreporter.write_line(f"Coverage Target: 80%")

        if passed / total >= 0.80:
            terminalreporter.write_line("Status: MEETS COVERAGE TARGET", green=True)
        else:
            terminalreporter.write_line("Status: BELOW COVERAGE TARGET", red=True)
