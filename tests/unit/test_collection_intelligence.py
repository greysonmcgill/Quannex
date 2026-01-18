"""Tests for Collection Intelligence Engine"""

import pytest
import numpy as np
from quan.intelligence import CollectionIntelligence, PortfolioState, CollectionStrategy


class TestCollectionIntelligence:
    """Test suite for CollectionIntelligence"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return CollectionIntelligence()

    @pytest.fixture
    def sample_portfolio(self):
        """Sample portfolio for testing"""
        return [
            {
                "account_id": "ACC001",
                "balance": 450.00,
                "original_balance": 500.00,
                "original_creditor": "Klarna",
                "debtor_name": "John Doe",
                "age": 32,
                "payment_willingness": 0.6,
                "has_mobile": True,
                "email_valid": True,
                "employed": True,
            },
            {
                "account_id": "ACC002",
                "balance": 125.00,
                "original_balance": 150.00,
                "original_creditor": "Affirm",
                "debtor_name": "Jane Smith",
                "age": 28,
                "payment_willingness": 0.3,
                "has_mobile": True,
                "email_valid": False,
                "employed": True,
            },
            {
                "account_id": "ACC003",
                "balance": 800.00,
                "original_balance": 800.00,
                "original_creditor": "Klarna",
                "debtor_name": "Bob Wilson",
                "age": 45,
                "payment_willingness": 0.5,
                "has_mobile": False,
                "email_valid": True,
                "employed": False,
            },
        ]

    def test_generate_strategy(self, engine, sample_portfolio):
        """Test that generate_strategy returns a CollectionStrategy"""
        account = sample_portfolio[0]
        strategy = engine.generate_strategy(account)

        assert isinstance(strategy, CollectionStrategy)
        assert strategy.account_id == "ACC001"
        assert 0 <= strategy.recovery_probability <= 1
        assert len(strategy.optimal_channels) > 0

    def test_predict_recovery_probability(self, engine, sample_portfolio):
        """Test recovery probability prediction"""
        for account in sample_portfolio:
            prob = engine.predict_recovery_probability(account)
            assert 0.05 <= prob <= 0.95

    def test_segment_portfolio(self, engine, sample_portfolio):
        """Test portfolio segmentation"""
        segments = engine.segment_portfolio(sample_portfolio)

        assert isinstance(segments, dict)
        # All accounts should be in some segment
        all_accounts = set()
        for segment_accounts in segments.values():
            all_accounts.update(segment_accounts)

        account_ids = {acc["account_id"] for acc in sample_portfolio}
        assert all_accounts == account_ids

    def test_analyze_portfolio(self, engine, sample_portfolio):
        """Test comprehensive portfolio analysis"""
        analysis = engine.analyze_portfolio(sample_portfolio)

        assert "total_accounts" in analysis
        assert analysis["total_accounts"] == len(sample_portfolio)
        assert "expected_recovery" in analysis
        assert "expected_rate" in analysis
        assert 0 <= analysis["expected_rate"] <= 1

    def test_extract_features(self, engine, sample_portfolio):
        """Test feature extraction"""
        account = sample_portfolio[0]
        features = engine.extract_features(account)

        assert isinstance(features, np.ndarray)
        assert features.dtype == np.float32

    def test_similarity_calculation(self, engine, sample_portfolio):
        """Test similarity calculation between accounts"""
        acc1 = sample_portfolio[0]  # Klarna
        acc2 = sample_portfolio[2]  # Klarna

        similarity = engine._calculate_similarity(acc1, acc2)

        # Same creditor should have higher similarity
        assert similarity >= 0.3

    def test_strategy_channels_valid(self, engine, sample_portfolio):
        """Test that strategy channels are valid"""
        valid_channels = {"sms", "email", "voice", "mail", "push"}

        for account in sample_portfolio:
            strategy = engine.generate_strategy(account)
            for channel in strategy.optimal_channels:
                assert channel in valid_channels

    def test_contact_sequence_generated(self, engine, sample_portfolio):
        """Test that contact sequence is properly generated"""
        account = sample_portfolio[0]
        strategy = engine.generate_strategy(account)

        assert len(strategy.contact_sequence) > 0
        for step in strategy.contact_sequence:
            assert "day" in step
            assert "channel" in step
            assert "message_type" in step

    def test_empty_portfolio(self, engine):
        """Test handling of empty portfolio"""
        analysis = engine.analyze_portfolio([])
        assert "error" in analysis

        segments = engine.segment_portfolio([])
        assert segments == {}


class TestCollectionStrategy:
    """Test CollectionStrategy dataclass"""

    def test_strategy_fields(self):
        """Test strategy has required fields"""
        strategy = CollectionStrategy(
            account_id="ACC001",
            recovery_probability=0.65,
            optimal_channels=["sms", "email"],
            settlement_threshold=0.7,
            contact_sequence=[{"day": 1, "channel": "sms"}],
            confidence=0.75,
        )

        assert strategy.account_id == "ACC001"
        assert strategy.recovery_probability == 0.65
        assert strategy.settlement_threshold == 0.7
        assert strategy.confidence == 0.75


# Backward compatibility tests
class TestBackwardCompatibility:
    """Test backward compatibility aliases"""

    def test_quantum_engine_alias(self):
        """Test that QuantumEngine alias works"""
        from quan.quantum import QuantumEngine
        from quan.intelligence import CollectionIntelligence

        assert QuantumEngine is CollectionIntelligence

    def test_quantum_state_alias(self):
        """Test that QuantumState alias works"""
        from quan.quantum import QuantumState
        from quan.intelligence import PortfolioState

        assert QuantumState is PortfolioState
