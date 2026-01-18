"""Tests for Payment Processor"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from quan.payments import PaymentProcessor, SettlementEngine


class TestPaymentProcessor:
    """Test suite for PaymentProcessor"""

    @pytest.fixture
    def processor(self):
        """Create payment processor instance"""
        return PaymentProcessor()

    @pytest.fixture
    def account(self):
        """Sample account for testing"""
        return {
            "account_id": "ACC001",
            "balance": 450.00,
            "client_id": "CLIENT001",
            "original_creditor": "Klarna",
        }

    @pytest.fixture
    def card_payment(self):
        """Card payment method"""
        return {
            "type": "card",
            "token": "tok_visa_test",
        }

    @pytest.fixture
    def ach_payment(self):
        """ACH payment method"""
        return {
            "type": "ach",
            "routing_number": "110000000",
            "account_number": "000123456789",
        }

    @pytest.mark.asyncio
    async def test_validate_valid_payment(self, processor, account, card_payment):
        """Test validation of valid payment"""
        result = await processor.payment_validator.validate(
            account,
            card_payment,
            Decimal("100.00"),
        )

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_amount_exceeds_balance(self, processor, account, card_payment):
        """Test validation when amount exceeds balance"""
        result = await processor.payment_validator.validate(
            account,
            card_payment,
            Decimal("500.00"),  # More than balance
        )

        assert result["valid"] is False
        assert any("exceed" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_negative_amount(self, processor, account, card_payment):
        """Test validation with negative amount"""
        result = await processor.payment_validator.validate(
            account,
            card_payment,
            Decimal("-50.00"),
        )

        assert result["valid"] is False
        assert any("positive" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_invalid_method(self, processor, account):
        """Test validation with invalid payment method"""
        invalid_method = {"type": "bitcoin"}

        result = await processor.payment_validator.validate(
            account,
            invalid_method,
            Decimal("100.00"),
        )

        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_validate_card_missing_token(self, processor, account):
        """Test validation when card token is missing"""
        card_no_token = {"type": "card"}

        result = await processor.payment_validator.validate(
            account,
            card_no_token,
            Decimal("100.00"),
        )

        assert result["valid"] is False
        assert any("token" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_ach_missing_routing(self, processor, account):
        """Test validation when ACH routing number is missing"""
        ach_no_routing = {
            "type": "ach",
            "account_number": "000123456789",
        }

        result = await processor.payment_validator.validate(
            account,
            ach_no_routing,
            Decimal("100.00"),
        )

        assert result["valid"] is False
        assert any("routing" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_create_payment_link(self, processor, account):
        """Test creating payment link"""
        link = await processor.create_payment_link(account)

        assert "quanrecovery.com" in link
        assert account["account_id"] in link


class TestSettlementEngine:
    """Test suite for SettlementEngine"""

    @pytest.fixture
    def engine(self):
        """Create settlement engine instance"""
        return SettlementEngine()

    @pytest.fixture
    def standard_account(self):
        """Standard account for testing"""
        return {
            "account_id": "ACC001",
            "balance": 500.00,
            "days_overdue": 60,
            "recovery_probability": 0.5,
        }

    @pytest.fixture
    def aged_account(self):
        """Aged account for testing"""
        return {
            "account_id": "ACC002",
            "balance": 300.00,
            "days_overdue": 400,  # Over 1 year
            "recovery_probability": 0.2,
        }

    @pytest.fixture
    def high_prob_account(self):
        """High probability account"""
        return {
            "account_id": "ACC003",
            "balance": 200.00,
            "days_overdue": 30,
            "recovery_probability": 0.7,
        }

    @pytest.mark.asyncio
    async def test_calculate_settlement_standard(self, engine, standard_account):
        """Test settlement calculation for standard account"""
        offer = await engine.calculate_settlement(standard_account)

        assert offer.account_id == standard_account["account_id"]
        assert offer.original_balance == Decimal("500.00")
        assert offer.settlement_amount < offer.original_balance
        assert offer.savings > 0
        assert offer.valid_until > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_settlement_aged_account_deeper_discount(self, engine, aged_account):
        """Test that aged accounts get deeper discounts"""
        offer = await engine.calculate_settlement(aged_account)

        discount = offer.discount_percentage

        # Aged accounts should get at least 50% discount
        assert discount >= 50

    @pytest.mark.asyncio
    async def test_settlement_high_prob_smaller_discount(self, engine, high_prob_account):
        """Test that high probability accounts get smaller discounts"""
        offer = await engine.calculate_settlement(high_prob_account)

        discount = offer.discount_percentage

        # High probability accounts should get smaller discount
        assert discount < 50

    @pytest.mark.asyncio
    async def test_settlement_with_debtor_offer_accepted(self, engine, standard_account):
        """Test settlement when debtor makes acceptable offer"""
        # Calculate what minimum we'd accept
        base_offer = await engine.calculate_settlement(standard_account)

        # Debtor offers more than minimum
        debtor_offer = base_offer.settlement_amount + Decimal("50")

        offer = await engine.calculate_settlement(
            standard_account,
            debtor_offer,
        )

        # Should accept debtor's higher offer
        assert offer.settlement_amount == debtor_offer

    @pytest.mark.asyncio
    async def test_settlement_payment_options(self, engine, standard_account):
        """Test that settlement includes payment options"""
        offer = await engine.calculate_settlement(standard_account)

        assert len(offer.payment_options) >= 3

        # Should have lump sum option
        lump_sum = next(
            (o for o in offer.payment_options if o["type"] == "lump_sum"),
            None,
        )
        assert lump_sum is not None
        assert lump_sum["payments"] == 1
        assert lump_sum["discount"] > 0  # Lump sum should have extra discount

    @pytest.mark.asyncio
    async def test_settlement_validity_period(self, engine, standard_account):
        """Test that settlement has 7-day validity"""
        offer = await engine.calculate_settlement(standard_account)

        validity = offer.valid_until - datetime.utcnow()

        # Should be valid for approximately 7 days
        assert timedelta(days=6) < validity < timedelta(days=8)


class TestAuthorityMatrix:
    """Test authority matrix rules"""

    @pytest.fixture
    def engine(self):
        return SettlementEngine()

    def test_authority_matrix_loaded(self, engine):
        """Test that authority matrix is loaded"""
        assert "default" in engine.authority_matrix
        assert "aged" in engine.authority_matrix
        assert "high_probability" in engine.authority_matrix
        assert "low_probability" in engine.authority_matrix

    def test_authority_matrix_ranges(self, engine):
        """Test authority matrix has valid ranges"""
        for tier, rules in engine.authority_matrix.items():
            assert 0 <= rules["min_settlement"] <= 1
            assert 0 <= rules["max_settlement"] <= 1
            assert rules["min_settlement"] <= rules["max_settlement"]
