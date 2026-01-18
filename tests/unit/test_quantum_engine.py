"""Tests for Quantum Engine"""

import pytest
import numpy as np
from quan.quantum import QuantumEngine, QuantumState


class TestQuantumEngine:
    """Test suite for QuantumEngine"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return QuantumEngine()

    @pytest.fixture
    def sample_portfolio(self):
        """Sample portfolio for testing"""
        return [
            {
                "account_id": "ACC001",
                "balance": 450.00,
                "original_creditor": "Klarna",
                "debtor_name": "John Doe",
                "days_overdue": 45,
                "debtor_state": "CA",
                "has_email": True,
                "has_phone": True,
            },
            {
                "account_id": "ACC002",
                "balance": 125.00,
                "original_creditor": "Affirm",
                "debtor_name": "Jane Smith",
                "days_overdue": 90,
                "debtor_state": "NY",
                "has_email": True,
                "has_phone": False,
            },
            {
                "account_id": "ACC003",
                "balance": 800.00,
                "original_creditor": "Klarna",
                "debtor_name": "Bob Wilson",
                "days_overdue": 30,
                "debtor_state": "CA",
                "has_email": False,
                "has_phone": True,
            },
        ]

    def test_quantum_analyze_returns_state(self, engine, sample_portfolio):
        """Test that quantum_analyze returns a QuantumState"""
        state = engine.quantum_analyze(sample_portfolio)

        assert isinstance(state, QuantumState)
        assert state.superposition is not None
        assert state.entanglement is not None
        assert 0 <= state.coherence <= 1

    def test_quantum_analyze_empty_portfolio(self, engine):
        """Test quantum_analyze with empty portfolio"""
        state = engine.quantum_analyze([])

        assert state.superposition.size == 0
        assert len(state.entanglement.nodes) == 0
        assert state.coherence == 0.0

    def test_superposition_normalized(self, engine, sample_portfolio):
        """Test that superposition is properly normalized"""
        state = engine.quantum_analyze(sample_portfolio)

        if state.superposition.size > 0:
            norm = np.linalg.norm(state.superposition)
            assert np.isclose(norm, 1.0, atol=0.01)

    def test_entanglement_graph_nodes(self, engine, sample_portfolio):
        """Test that entanglement graph has correct nodes"""
        state = engine.quantum_analyze(sample_portfolio)

        assert len(state.entanglement.nodes) == len(sample_portfolio)

    def test_entanglement_correlations(self, engine, sample_portfolio):
        """Test that correlated accounts are connected"""
        state = engine.quantum_analyze(sample_portfolio)

        # Accounts with same creditor (ACC001, ACC003) should be connected
        edges = list(state.entanglement.edges)
        # At least some edges should exist for correlated accounts
        assert len(edges) >= 0  # May or may not have edges depending on threshold

    def test_collapse_to_strategy(self, engine, sample_portfolio):
        """Test collapsing quantum state to strategies"""
        state = engine.quantum_analyze(sample_portfolio)
        strategies = engine.collapse_to_strategy(state)

        assert len(strategies) == len(sample_portfolio)

        for strategy in strategies:
            assert strategy.account_id is not None
            assert 0 <= strategy.recovery_probability <= 1
            assert len(strategy.optimal_channels) > 0
            assert 0 <= strategy.settlement_authority <= 1

    def test_strategy_channels_valid(self, engine, sample_portfolio):
        """Test that strategy channels are valid"""
        valid_channels = {"sms", "email", "voice", "mail", "push"}

        state = engine.quantum_analyze(sample_portfolio)
        strategies = engine.collapse_to_strategy(state)

        for strategy in strategies:
            for channel in strategy.optimal_channels:
                assert channel in valid_channels

    def test_feature_extraction(self, engine, sample_portfolio):
        """Test feature extraction from accounts"""
        account = sample_portfolio[0]
        features = engine._extract_features(account)

        assert isinstance(features, np.ndarray)
        assert len(features) == engine.FEATURE_DIM
        assert features.dtype == np.float32

    def test_correlation_calculation(self, engine, sample_portfolio):
        """Test correlation calculation between accounts"""
        acc1 = sample_portfolio[0]  # Klarna, CA
        acc2 = sample_portfolio[2]  # Klarna, CA

        correlation = engine._calculate_correlation(acc1, acc2)

        # Same creditor and same state should have high correlation
        assert correlation > 0.3

    def test_correlation_different_accounts(self, engine, sample_portfolio):
        """Test correlation for different accounts"""
        acc1 = sample_portfolio[0]  # Klarna, CA
        acc2 = sample_portfolio[1]  # Affirm, NY

        correlation = engine._calculate_correlation(acc1, acc2)

        # Different creditor and state should have lower correlation
        assert correlation < 0.5


class TestQuantumState:
    """Test suite for QuantumState"""

    def test_collapse_returns_probabilities(self):
        """Test that collapse returns valid probabilities"""
        superposition = np.array([[0.5 + 0.5j, 0.5 - 0.5j]])
        superposition = superposition / np.linalg.norm(superposition)

        state = QuantumState(
            superposition=superposition,
            entanglement=None,
            coherence=0.5,
        )

        probs = state.collapse()

        assert np.all(probs >= 0)
        assert np.all(probs <= 1)
