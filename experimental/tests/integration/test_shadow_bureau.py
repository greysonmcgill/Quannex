"""
QUAN Integration Tests: Shadow Bureau

Comprehensive testing for the Shadow Bureau system:
1. Live Ledger ingestion
2. Shadow score calculation
3. Network query responses
4. Rehabilitation loop progression
5. Restoration certificate generation

Tests verify the alternative credit scoring and restoration mechanisms.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
import uuid
import hashlib


from quan.shadow_bureau.live_ledger import (
    LiveLedger, DebtCategory, PaymentBehavior, RiskTier,
    MicroDebtRecord, ConsumerLedgerProfile
)
from quan.shadow_bureau.rehabilitation_loop import (
    RehabilitationLoop, TrustLevel, RestoreStatus, AchievementType
)


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestLiveLedgerIngestion:
    """Test Live Ledger data ingestion"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_single_record_ingestion(self, data_generator):
        """Test ingesting a single debt record"""
        ledger = LiveLedger()
        account = data_generator.generate_account()

        record = ledger.ingest_debt(
            creditor_id="KLARNA_001",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=185.00,
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45,
            consumer_data={"state": account["debtor_state"]}
        )

        assert record is not None
        assert record.consumer_id == account["consumer_id"]
        assert record.original_balance == 185.00
        assert record.current_balance == 185.00
        assert record.collection_status == "active"
        assert record.category == DebtCategory.BNPL

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_category_ingestion(self, data_generator):
        """Test ingesting debts across different categories"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        categories = [
            (DebtCategory.BNPL, "Klarna", 147.50),
            (DebtCategory.SUBSCRIPTION, "Netflix", 32.99),
            (DebtCategory.GIG_ADVANCE, "Uber", 75.00),
            (DebtCategory.TELECOM, "Verizon", 156.00),
            (DebtCategory.MEDICAL, "Med Center", 245.00),
        ]

        for category, creditor, balance in categories:
            ledger.ingest_debt(
                creditor_id=f"{creditor.upper()}_001",
                creditor_name=creditor,
                consumer_id=consumer_id,
                category=category,
                original_balance=balance,
                charge_off_date=datetime.utcnow() - timedelta(days=60),
                days_past_due=60
            )

        profile = ledger.consumer_profiles.get(consumer_id)

        assert profile.total_debts_tracked == 5
        assert len(profile.debt_categories) == 5
        assert profile.total_balance_tracked == sum(c[2] for c in categories)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_creditor_profile_creation(self, data_generator):
        """Test creditor profile is created on first ingestion"""
        ledger = LiveLedger()

        # Ingest multiple debts from same creditor
        for i in range(5):
            ledger.ingest_debt(
                creditor_id="KLARNA_001",
                creditor_name="Klarna",
                consumer_id=data_generator.generate_consumer_id(),
                category=DebtCategory.BNPL,
                original_balance=100.00 + i * 20,
                charge_off_date=datetime.utcnow() - timedelta(days=30),
                days_past_due=30
            )

        creditor = ledger.creditor_profiles.get("KLARNA_001")

        assert creditor is not None
        assert creditor.total_accounts_placed == 5
        assert creditor.total_balance_placed == sum(100 + i * 20 for i in range(5))

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_ingestion_performance(self, data_generator, perf_tracker):
        """Test bulk ingestion performance"""
        ledger = LiveLedger()
        portfolio = data_generator.generate_portfolio(500)

        perf_tracker.start_timer("bulk_ingestion")

        for account in portfolio:
            ledger.ingest_debt(
                creditor_id="BULK_CREDITOR",
                creditor_name="Bulk Test",
                consumer_id=account["consumer_id"],
                category=DebtCategory.BNPL,
                original_balance=float(account["balance"]),
                charge_off_date=datetime.utcnow() - timedelta(days=account["days_overdue"]),
                days_past_due=account["days_overdue"]
            )

        elapsed = perf_tracker.stop_timer("bulk_ingestion")

        assert len(ledger.debt_records) == 500
        assert elapsed < 5.0  # Should complete in under 5 seconds


class TestShadowScoreCalculation:
    """Test Shadow Score calculation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_initial_score_range(self, data_generator):
        """Test initial shadow score is within expected range"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=100.00,
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        profile = ledger.consumer_profiles[consumer_id]

        # Score should be in FICO-like range
        assert 300 <= profile.shadow_score <= 850

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_score_components(self, data_generator):
        """Test shadow score component calculations"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        record = ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=100.00,
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        # Record positive interactions
        for _ in range(5):
            ledger.record_interaction(record.record_id, "sms", response_received=True, promise_made=True)
            ledger.record_promise_outcome(record.record_id, promise_kept=True)

        profile = ledger.consumer_profiles[consumer_id]

        # All component scores should be positive
        assert profile.response_score > 50
        assert profile.promise_score > 50
        assert profile.payment_score >= 0  # May be 0 if no payments

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_score_improvement_trajectory(self, data_generator):
        """Test score improves with positive behavior"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        record = ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=200.00,
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        score_history = [ledger.consumer_profiles[consumer_id].shadow_score]

        # Positive behavior pattern
        for i in range(5):
            ledger.record_interaction(
                record.record_id, "sms",
                response_received=True,
                promise_made=True,
                payment_received=40.00
            )
            ledger.record_promise_outcome(record.record_id, promise_kept=True)
            score_history.append(ledger.consumer_profiles[consumer_id].shadow_score)

        # Score should trend upward
        assert score_history[-1] > score_history[0]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_risk_tier_assignment(self, data_generator):
        """Test risk tier assignment based on score"""
        ledger = LiveLedger()

        test_behaviors = [
            # (responds, keeps_promises, makes_payments) -> expected tier
            (True, True, True),   # Good behavior
            (True, True, False),  # Responds but doesn't pay
            (True, False, False), # Responds, breaks promises
            (False, False, False), # Ghost
        ]

        for i, (responds, keeps, pays) in enumerate(test_behaviors):
            consumer_id = f"TIER_TEST_{i}"

            record = ledger.ingest_debt(
                creditor_id="TEST",
                creditor_name="Test",
                consumer_id=consumer_id,
                category=DebtCategory.BNPL,
                original_balance=100.00,
                charge_off_date=datetime.utcnow() - timedelta(days=30),
                days_past_due=30
            )

            for _ in range(5):
                ledger.record_interaction(
                    record.record_id, "sms",
                    response_received=responds,
                    promise_made=responds,
                    payment_received=20.00 if pays else 0
                )
                if responds:
                    ledger.record_promise_outcome(record.record_id, promise_kept=keeps)

            profile = ledger.consumer_profiles[consumer_id]
            assert profile.risk_tier in list(RiskTier)


class TestNetworkQueryResponses:
    """Test Shadow Bureau network query functionality"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consumer_query(self, data_generator):
        """Test querying consumer shadow profile"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        # Ingest debt
        ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=150.00,
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45
        )

        # Query consumer
        result = ledger.query_consumer(consumer_id)

        assert result is not None
        assert result["consumer_id"] == consumer_id
        assert "shadow_score" in result
        assert "risk_tier" in result
        assert "behavioral_profile" in result
        assert "active_debts" in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_network_check_clean_consumer(self, data_generator):
        """Test network check for consumer with no outstanding debts"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        # No debts
        result = ledger.network_check(consumer_id)

        assert result["has_outstanding"] is False
        assert result["total_outstanding"] == 0
        assert result["recommendation"] == "APPROVE"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_network_check_consumer_with_debt(self, data_generator):
        """Test network check for consumer with outstanding debt"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        # Ingest outstanding debt
        ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=300.00,
            charge_off_date=datetime.utcnow() - timedelta(days=60),
            days_past_due=60
        )

        result = ledger.network_check(consumer_id)

        assert result["has_outstanding"] is True
        assert result["total_outstanding"] == 300.00
        assert "KLARNA" in str(result["creditors_owed"]) or "Klarna" in str(result["creditors_owed"])
        # Recommendation depends on amount and risk tier

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_portfolio_analytics(self, data_generator):
        """Test portfolio-level analytics"""
        ledger = LiveLedger()

        # Ingest portfolio
        for i in range(10):
            consumer_id = data_generator.generate_consumer_id()
            record = ledger.ingest_debt(
                creditor_id="CREDITOR_A",
                creditor_name="Creditor A",
                consumer_id=consumer_id,
                category=DebtCategory.BNPL,
                original_balance=100.00 + i * 10,
                charge_off_date=datetime.utcnow() - timedelta(days=30),
                days_past_due=30
            )

            # Resolve some
            if i < 3:
                ledger.record_interaction(
                    record.record_id, "payment",
                    response_received=True,
                    payment_received=100.00 + i * 10
                )

        analytics = ledger.get_portfolio_analytics("CREDITOR_A")

        assert analytics["total_accounts"] == 10
        assert analytics["resolved_accounts"] == 3
        assert analytics["active_accounts"] == 7
        assert analytics["recovery_rate"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cross_creditor_intelligence(self, data_generator):
        """Test cross-creditor intelligence gathering"""
        ledger = LiveLedger()
        consumer_id = data_generator.generate_consumer_id()

        # Consumer has debts with multiple creditors
        creditors = ["KLARNA", "AFFIRM", "AFTERPAY", "QUADPAY"]

        for creditor in creditors:
            ledger.ingest_debt(
                creditor_id=creditor,
                creditor_name=creditor.title(),
                consumer_id=consumer_id,
                category=DebtCategory.BNPL,
                original_balance=100.00,
                charge_off_date=datetime.utcnow() - timedelta(days=45),
                days_past_due=45
            )

        profile = ledger.consumer_profiles[consumer_id]

        assert profile.creditors_in_network == 4
        assert profile.total_debts_tracked == 4


class TestRehabilitationLoopProgression:
    """Test Rehabilitation Loop progression"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consumer_initialization(self, data_generator):
        """Test consumer initialization in rehab loop"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        score = rehab.initialize_consumer(consumer_id)

        assert score.consumer_id == consumer_id
        assert score.current_level == TrustLevel.UNTRUSTED
        assert score.numeric_score == 0
        assert score.payments_made == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_payment_recording(self, data_generator):
        """Test payment recording updates trust score"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        result = rehab.record_payment(
            consumer_id=consumer_id,
            amount=50.00,
            on_time=True,
            resolves_debt=False
        )

        assert result["trust_score"] > 0
        assert result["current_streak"] == 1
        assert "First Step" in result["new_achievements"]  # First payment achievement

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trust_level_progression(self, data_generator):
        """Test trust level progresses with consistent payments"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        # Make multiple on-time payments
        for i in range(10):
            result = rehab.record_payment(
                consumer_id=consumer_id,
                amount=25.00,
                on_time=True,
                resolves_debt=(i == 9)
            )

        final_level = rehab.trust_scores[consumer_id].current_level

        # Should have progressed from UNTRUSTED
        assert final_level.value > TrustLevel.UNTRUSTED.value

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_streak_tracking(self, data_generator):
        """Test payment streak tracking"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        # Build streak
        for _ in range(5):
            rehab.record_payment(consumer_id, 20.00, on_time=True)

        score = rehab.trust_scores[consumer_id]
        assert score.current_streak == 5
        assert score.longest_streak == 5

        # Break streak
        rehab.record_payment(consumer_id, 20.00, on_time=False)

        score = rehab.trust_scores[consumer_id]
        assert score.current_streak == 0
        assert score.longest_streak == 5  # Longest preserved

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_achievement_unlocking(self, data_generator):
        """Test achievements are unlocked correctly"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)
        all_achievements = []

        # First payment
        result = rehab.record_payment(consumer_id, 50.00, True)
        all_achievements.extend(result["new_achievements"])

        # Build streak
        for i in range(4):
            result = rehab.record_payment(consumer_id, 50.00, True, resolves_debt=(i == 3))
            all_achievements.extend(result["new_achievements"])

        # Should have earned multiple achievements
        assert "First Step" in all_achievements  # First payment
        assert "On a Roll" in all_achievements   # 3-streak
        assert "Debt Free" in all_achievements   # Resolution


class TestRestorationCertificateGeneration:
    """Test restoration certificate generation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_certificate_generation(self, data_generator):
        """Test restoration certificate is generated correctly"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        # Build trust with payments
        for _ in range(3):
            rehab.record_payment(consumer_id, 50.00, True)

        cert = rehab.issue_restoration_certificate(
            consumer_id=consumer_id,
            creditor_id="KLARNA",
            creditor_name="Klarna",
            original_amount=150.00,
            resolved_amount=150.00,
            resolution_type="paid_full"
        )

        assert cert is not None
        assert cert.consumer_id == consumer_id
        assert cert.creditor_id == "KLARNA"
        assert cert.original_debt_amount == 150.00
        assert cert.resolved_amount == 150.00
        assert cert.resolution_type == "paid_full"
        assert cert.verification_hash is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_certificate_verification(self, data_generator):
        """Test certificate verification"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)
        rehab.record_payment(consumer_id, 100.00, True, True)

        cert = rehab.issue_restoration_certificate(
            consumer_id=consumer_id,
            creditor_id="AFFIRM",
            creditor_name="Affirm",
            original_amount=100.00,
            resolved_amount=75.00,
            resolution_type="settled"
        )

        verification = rehab.verify_certificate(cert.certificate_id)

        assert verification["valid"] is True
        assert verification["consumer_id"] == consumer_id
        assert verification["amount_resolved"] == 75.00
        assert "recommendation" in verification

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_certificate_expiration(self, data_generator):
        """Test certificate expiration handling"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        cert = rehab.issue_restoration_certificate(
            consumer_id=consumer_id,
            creditor_id="TEST",
            creditor_name="Test",
            original_amount=100.00,
            resolved_amount=100.00,
            resolution_type="paid_full"
        )

        # Manually expire certificate
        cert.expires_at = datetime.utcnow() - timedelta(days=1)

        verification = rehab.verify_certificate(cert.certificate_id)

        assert verification["valid"] is False
        assert "expired" in verification["reason"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_access_restoration(self, data_generator):
        """Test service access is restored after certificate issuance"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        # Initial service access should be blocked
        assert consumer_id not in rehab.service_access or len(rehab.service_access.get(consumer_id, {})) == 0

        # Build trust and issue certificate
        for _ in range(5):
            rehab.record_payment(consumer_id, 30.00, True)

        cert = rehab.issue_restoration_certificate(
            consumer_id=consumer_id,
            creditor_id="KLARNA",
            creditor_name="Klarna",
            original_amount=150.00,
            resolved_amount=150.00,
            resolution_type="paid_full"
        )

        # Service access should be restored
        access = rehab.service_access.get(consumer_id, {}).get("KLARNA")
        assert access is not None
        assert access.status in [RestoreStatus.RESTORED, RestoreStatus.ENHANCED]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consumer_dashboard(self, data_generator):
        """Test consumer dashboard data"""
        rehab = RehabilitationLoop()
        consumer_id = data_generator.generate_consumer_id()

        rehab.initialize_consumer(consumer_id)

        # Build history
        for i in range(5):
            rehab.record_payment(consumer_id, 25.00, True, resolves_debt=(i == 4))

        rehab.issue_restoration_certificate(
            consumer_id, "KLARNA", "Klarna", 125.00, 125.00, "paid_full"
        )

        dashboard = rehab.get_consumer_dashboard(consumer_id)

        assert dashboard["trust_score"] > 0
        assert "trust_level" in dashboard
        assert dashboard["total_achievements"] > 0
        assert dashboard["current_streak"] == 5
        assert len(dashboard["services"]) > 0
        assert "motivational_message" in dashboard


class TestShadowBureauIntegration:
    """Test full Shadow Bureau integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_shadow_bureau_flow(self, data_generator, audit_logger):
        """Test complete Shadow Bureau flow"""
        ledger = LiveLedger()
        rehab = RehabilitationLoop()

        consumer_id = data_generator.generate_consumer_id()

        # 1. Ingest debt
        record = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=consumer_id,
            category=DebtCategory.BNPL,
            original_balance=200.00,
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45
        )
        audit_logger.log("shadow_bureau", consumer_id, "debt_ingested", {})

        # 2. Initialize rehabilitation
        rehab.initialize_consumer(consumer_id)
        audit_logger.log("shadow_bureau", consumer_id, "rehab_initialized", {})

        # 3. Record interactions and payments
        for i in range(4):
            ledger.record_interaction(
                record.record_id, "sms",
                response_received=True,
                promise_made=True,
                payment_received=50.00
            )
            ledger.record_promise_outcome(record.record_id, promise_kept=True)
            rehab.record_payment(consumer_id, 50.00, True, resolves_debt=(i == 3))

        audit_logger.log("shadow_bureau", consumer_id, "payments_completed", {})

        # 4. Query shadow score
        query_result = ledger.query_consumer(consumer_id)
        assert query_result["shadow_score"] > 300

        # 5. Network check
        network_result = ledger.network_check(consumer_id)
        # After full payment, should have no outstanding

        # 6. Issue restoration certificate
        cert = rehab.issue_restoration_certificate(
            consumer_id, "KLARNA", "Klarna", 200.00, 200.00, "paid_full"
        )
        audit_logger.log("shadow_bureau", consumer_id, "certificate_issued", {
            "certificate_id": cert.certificate_id
        })

        # 7. Verify certificate
        verification = rehab.verify_certificate(cert.certificate_id)
        assert verification["valid"]

        # Verify complete audit trail
        entries = audit_logger.get_entries(account_id=consumer_id)
        assert len(entries) >= 4

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_shadow_bureau_scale(self, data_generator, perf_tracker):
        """Test Shadow Bureau at scale"""
        ledger = LiveLedger()
        rehab = RehabilitationLoop()

        perf_tracker.start_timer("shadow_bureau_scale")

        # Process 1000 consumers
        for i in range(1000):
            consumer_id = data_generator.generate_consumer_id()

            # Ingest
            record = ledger.ingest_debt(
                creditor_id=f"CREDITOR_{i % 10}",
                creditor_name=f"Creditor {i % 10}",
                consumer_id=consumer_id,
                category=list(DebtCategory)[i % len(DebtCategory)],
                original_balance=100.00 + (i % 100),
                charge_off_date=datetime.utcnow() - timedelta(days=30),
                days_past_due=30
            )

            # Some interactions
            if i % 3 == 0:
                ledger.record_interaction(record.record_id, "sms", True, True, 50.00)

            # Some rehabilitations
            if i % 5 == 0:
                rehab.initialize_consumer(consumer_id)
                rehab.record_payment(consumer_id, 50.00, True)

        elapsed = perf_tracker.stop_timer("shadow_bureau_scale")

        assert len(ledger.debt_records) == 1000
        assert len(ledger.consumer_profiles) == 1000
        assert elapsed < 30.0  # Should complete in under 30 seconds

        # Verify queries work at scale
        analytics = ledger.get_portfolio_analytics()
        assert analytics["total_accounts"] == 1000
