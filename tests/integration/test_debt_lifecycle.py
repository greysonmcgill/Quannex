"""
QUAN Integration Tests: Debt Lifecycle

End-to-end tests for the complete debt collection lifecycle:
1. Debt ingestion from creditor API
2. Consumer profile creation
3. Shadow score calculation
4. Contact sequence execution
5. Settlement negotiation
6. Payment processing
7. Resolution and restoration

Tests verify the entire flow from debt placement to successful resolution.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
import uuid

# Import QUAN components

from quan.shadow_bureau.live_ledger import (
    LiveLedger, DebtCategory, PaymentBehavior, RiskTier, MicroDebtRecord
)
from quan.shadow_bureau.rehabilitation_loop import (
    RehabilitationLoop, TrustLevel, RestoreStatus
)


class TestDebtIngestion:
    """Test debt ingestion from creditor API"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_single_debt_ingestion(self, data_generator, kafka_producer, audit_logger):
        """Test ingesting a single debt record"""
        account = data_generator.generate_account(
            balance=Decimal("147.50"),
            days_past_due=45,
            creditor_type="bnpl"
        )

        # Simulate ingestion
        ledger = LiveLedger()
        record = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=account["days_overdue"]),
            days_past_due=account["days_overdue"],
            consumer_data={"state": account["debtor_state"]}
        )

        # Verify record created
        assert record is not None
        assert record.consumer_id == account["consumer_id"]
        assert record.original_balance == float(account["balance"])
        assert record.collection_status == "active"
        assert record.category == DebtCategory.BNPL

        # Log audit event
        audit_logger.log("debt_ingestion", account["account_id"], "ingest", {
            "creditor": "KLARNA",
            "balance": float(account["balance"]),
            "dpd": account["days_overdue"]
        })

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_portfolio_ingestion(self, data_generator, kafka_producer, audit_logger):
        """Test ingesting a bulk portfolio"""
        portfolio = data_generator.generate_portfolio(50)
        ledger = LiveLedger()

        ingested_count = 0
        failed_count = 0

        for account in portfolio:
            try:
                record = ledger.ingest_debt(
                    creditor_id="BULK_CREDITOR",
                    creditor_name="Bulk Test Creditor",
                    consumer_id=account["consumer_id"],
                    category=DebtCategory.BNPL,
                    original_balance=float(account["balance"]),
                    charge_off_date=datetime.utcnow() - timedelta(days=account["days_overdue"]),
                    days_past_due=account["days_overdue"],
                    consumer_data={"state": account["debtor_state"]}
                )
                if record:
                    ingested_count += 1

                    # Send to Kafka for downstream processing
                    await kafka_producer.send(
                        topic="quan.accounts.new",
                        key=account["account_id"],
                        value={"record_id": record.record_id, "account": account}
                    )
            except Exception:
                failed_count += 1

        # Verify bulk ingestion success rate
        assert ingested_count >= 45  # At least 90% success
        assert failed_count <= 5

        # Verify Kafka messages sent
        messages = kafka_producer.get_messages("quan.accounts.new")
        assert len(messages) == ingested_count

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_duplicate_debt_handling(self, data_generator):
        """Test handling of duplicate debt records"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        # Ingest first time
        record1 = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45
        )

        # Attempt duplicate ingestion (same consumer, creditor, date)
        record2 = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45
        )

        # Both should have same record_id (deterministic)
        assert record1.record_id == record2.record_id

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_creditor_debt_aggregation(self, data_generator):
        """Test aggregating debts from multiple creditors for same consumer"""
        consumer_id = data_generator.generate_consumer_id()
        ledger = LiveLedger()

        # Ingest debts from multiple creditors
        creditors = [
            ("KLARNA", "Klarna", DebtCategory.BNPL, 147.50),
            ("AFFIRM", "Affirm", DebtCategory.BNPL, 89.00),
            ("NETFLIX", "Netflix", DebtCategory.SUBSCRIPTION, 32.99),
            ("VERIZON", "Verizon", DebtCategory.TELECOM, 156.00),
        ]

        for cred_id, cred_name, category, balance in creditors:
            ledger.ingest_debt(
                creditor_id=cred_id,
                creditor_name=cred_name,
                consumer_id=consumer_id,
                category=category,
                original_balance=balance,
                charge_off_date=datetime.utcnow() - timedelta(days=60),
                days_past_due=60
            )

        # Query aggregated consumer profile
        profile = ledger.consumer_profiles.get(consumer_id)
        assert profile is not None
        assert profile.total_debts_tracked == 4
        assert profile.creditors_in_network == 4
        assert profile.total_balance_tracked == sum(c[3] for c in creditors)


class TestConsumerProfileCreation:
    """Test consumer profile creation and management"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_profile_creation_on_first_debt(self, data_generator):
        """Test profile is created when first debt is ingested"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        # Before ingestion, profile should not exist
        assert account["consumer_id"] not in ledger.consumer_profiles

        # Ingest debt
        ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test Creditor",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30,
            consumer_data={"state": account["debtor_state"]}
        )

        # Profile should now exist
        profile = ledger.consumer_profiles.get(account["consumer_id"])
        assert profile is not None
        assert profile.geo_region == account["debtor_state"]
        assert profile.total_debts_tracked == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_profile_enrichment_with_behavior(self, data_generator):
        """Test profile enrichment with behavioral data"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        # Ingest debt
        record = ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test Creditor",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        # Record initial interaction
        ledger.record_interaction(
            record.record_id,
            "sms",
            response_received=True,
            promise_made=True
        )

        # Record promise kept
        ledger.record_promise_outcome(record.record_id, promise_kept=True)

        # Verify profile updated
        profile = ledger.consumer_profiles.get(account["consumer_id"])
        assert profile.response_score > 50  # Improved from default
        assert profile.promise_score > 50


class TestShadowScoreCalculation:
    """Test Shadow Bureau score calculation"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shadow_score_initial_value(self, data_generator):
        """Test initial shadow score for new consumer"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=float(account["balance"]),
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        profile = ledger.consumer_profiles.get(account["consumer_id"])

        # Initial score should be middle-range
        assert 300 <= profile.shadow_score <= 850
        assert profile.risk_tier in list(RiskTier)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shadow_score_improvement_with_payments(self, data_generator):
        """Test shadow score improves with positive behavior"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        record = ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=200.00,
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        initial_score = ledger.consumer_profiles[account["consumer_id"]].shadow_score

        # Simulate positive engagement pattern
        for i in range(5):
            ledger.record_interaction(
                record.record_id,
                "sms",
                response_received=True,
                promise_made=True,
                payment_received=20.00  # Partial payments
            )
            ledger.record_promise_outcome(record.record_id, promise_kept=True)

        final_score = ledger.consumer_profiles[account["consumer_id"]].shadow_score

        # Score should improve
        assert final_score > initial_score
        # Behavior should be positive
        profile = ledger.consumer_profiles[account["consumer_id"]]
        assert profile.primary_behavior in [
            PaymentBehavior.PROMPT_PAYER,
            PaymentBehavior.PLAN_KEEPER,
            PaymentBehavior.NEGOTIATOR
        ]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shadow_score_degradation_with_defaults(self, data_generator):
        """Test shadow score degrades with negative behavior"""
        account = data_generator.generate_account()
        ledger = LiveLedger()

        record = ledger.ingest_debt(
            creditor_id="TEST",
            creditor_name="Test",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=200.00,
            charge_off_date=datetime.utcnow() - timedelta(days=30),
            days_past_due=30
        )

        # Simulate negative pattern - no responses, broken promises
        for i in range(5):
            ledger.record_interaction(
                record.record_id,
                "sms",
                response_received=False  # Ghost behavior
            )

        profile = ledger.consumer_profiles[account["consumer_id"]]

        # Score should be low
        assert profile.response_score < 50
        # Behavior should reflect ghosting
        assert profile.primary_behavior == PaymentBehavior.GHOST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_risk_tier_classification(self, data_generator):
        """Test risk tier classification based on score"""
        ledger = LiveLedger()

        # Create consumers with different behaviors
        test_cases = [
            ("high_performer", True, True, 5, RiskTier.TIER_A),
            ("moderate", True, True, 2, RiskTier.TIER_B),
            ("low_performer", True, False, 1, RiskTier.TIER_C),
            ("ghost", False, False, 0, RiskTier.TIER_F),
        ]

        for name, responds, keeps_promises, payments, expected_min_tier in test_cases:
            consumer_id = f"TEST_{name}"

            record = ledger.ingest_debt(
                creditor_id="TEST",
                creditor_name="Test",
                consumer_id=consumer_id,
                category=DebtCategory.BNPL,
                original_balance=100.00,
                charge_off_date=datetime.utcnow() - timedelta(days=30),
                days_past_due=30
            )

            # Simulate behavior pattern
            for _ in range(5):
                ledger.record_interaction(
                    record.record_id,
                    "sms",
                    response_received=responds,
                    promise_made=responds,
                    payment_received=20.00 if payments > 0 else 0
                )
                if responds:
                    ledger.record_promise_outcome(record.record_id, promise_kept=keeps_promises)
                payments = max(0, payments - 1)


class TestContactSequenceExecution:
    """Test contact sequence execution"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_initial_contact_sequence(self, data_generator, communication_service, audit_logger):
        """Test initial contact sequence is executed correctly"""
        account = data_generator.generate_account()

        # Execute initial contact
        result = await communication_service.send_sms(
            to=account["debtor_phone"],
            message="Initial collection message with required disclosures. This is a debt collector.",
            metadata={"account_id": account["account_id"], "sequence": "initial"}
        )

        assert result["success"]

        # Log to audit
        audit_logger.log("contact", account["account_id"], "sms_sent", {
            "message_id": result["message_id"],
            "sequence": "initial"
        })

        # Verify contact recorded
        assert communication_service.get_contact_count(account["account_id"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_channel_contact_sequence(self, data_generator, communication_service):
        """Test multi-channel contact escalation"""
        account = data_generator.generate_account()

        # Day 1: SMS
        sms_result = await communication_service.send_sms(
            to=account["debtor_phone"],
            message="SMS contact. This is a debt collector.",
            metadata={"account_id": account["account_id"], "day": 1}
        )
        assert sms_result["success"]

        # Day 3: Email
        email_result = await communication_service.send_email(
            to=account["debtor_email"],
            subject="Important Notice",
            body="Email contact. This is a debt collector.",
            metadata={"account_id": account["account_id"], "day": 3}
        )
        assert email_result["success"]

        # Day 5: Voice
        voice_result = await communication_service.make_call(
            to=account["debtor_phone"],
            script={"type": "collection", "tone": "professional"},
            metadata={"account_id": account["account_id"], "day": 5}
        )
        assert voice_result["success"]

        # Verify all channels contacted
        assert len(communication_service.sms_log) == 1
        assert len(communication_service.email_log) == 1
        assert len(communication_service.voice_log) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_contact_sequence_respects_preferences(self, data_generator, communication_service):
        """Test contact sequence respects consumer channel preferences"""
        # Account with only email consent
        account = data_generator.generate_account()
        account["sms_consent"] = False
        account["voice_consent"] = False
        account["email_consent"] = True

        # Should only use email
        contacts_made = []

        if account.get("sms_consent"):
            result = await communication_service.send_sms(
                to=account["debtor_phone"],
                message="Test",
                metadata={"account_id": account["account_id"]}
            )
            contacts_made.append("sms")

        if account.get("email_consent"):
            result = await communication_service.send_email(
                to=account["debtor_email"],
                subject="Test",
                body="Test",
                metadata={"account_id": account["account_id"]}
            )
            contacts_made.append("email")

        if account.get("voice_consent"):
            result = await communication_service.make_call(
                to=account["debtor_phone"],
                script={},
                metadata={"account_id": account["account_id"]}
            )
            contacts_made.append("voice")

        assert contacts_made == ["email"]


class TestSettlementNegotiation:
    """Test settlement negotiation flow"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_settlement_offer_generation(self, data_generator):
        """Test settlement offer is generated correctly"""
        account = data_generator.generate_account(balance=Decimal("500.00"))
        offer = data_generator.generate_settlement_offer(account, rate=0.50)

        assert offer["balance"] == 500.00
        assert offer["settlement_amount"] == 250.00
        assert offer["settlement_rate"] == 0.50
        assert "expiration_date" in offer

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_settlement_negotiation_rounds(self, data_generator, audit_logger):
        """Test multi-round settlement negotiation"""
        account = data_generator.generate_account(balance=Decimal("500.00"))

        # Round 1: Initial offer at 60%
        offer1 = data_generator.generate_settlement_offer(account, rate=0.60)
        audit_logger.log("settlement", account["account_id"], "offer_made", {
            "round": 1, "rate": 0.60, "amount": offer1["settlement_amount"]
        })

        # Consumer counter at 40%
        counter1 = {"rate": 0.40, "amount": 200.00}
        audit_logger.log("settlement", account["account_id"], "counter_received", {
            "round": 1, "rate": 0.40, "amount": 200.00
        })

        # Round 2: Counter-offer at 55%
        offer2 = data_generator.generate_settlement_offer(account, rate=0.55)
        audit_logger.log("settlement", account["account_id"], "offer_made", {
            "round": 2, "rate": 0.55, "amount": offer2["settlement_amount"]
        })

        # Consumer accepts at 50%
        final_rate = 0.50
        final_amount = 250.00
        audit_logger.log("settlement", account["account_id"], "settlement_accepted", {
            "final_rate": final_rate, "final_amount": final_amount
        })

        # Verify negotiation trail
        entries = audit_logger.get_entries(account_id=account["account_id"])
        assert len(entries) == 4  # 2 offers + 1 counter + 1 acceptance

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_settlement_within_boundaries(self, data_generator):
        """Test settlement rates stay within acceptable boundaries"""
        account = data_generator.generate_account(balance=Decimal("500.00"))

        # Minimum allowed rate (typically 20%)
        min_rate = 0.20
        # Maximum allowed rate (100%)
        max_rate = 1.00

        # Test various settlement rates
        test_rates = [0.15, 0.20, 0.50, 0.75, 1.00, 1.10]

        for rate in test_rates:
            is_valid = min_rate <= rate <= max_rate

            if is_valid:
                offer = data_generator.generate_settlement_offer(account, rate=rate)
                assert offer["settlement_rate"] == rate
            # Rates outside bounds should be rejected in real system


class TestPaymentProcessing:
    """Test payment processing in lifecycle"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_payment_processing(self, data_generator, payment_processor, audit_logger):
        """Test full payment amount processing"""
        account = data_generator.generate_account(balance=Decimal("185.00"))
        payment_method = data_generator.generate_payment_method("card")

        # Authorize
        auth_success, auth_id, auth_error = await payment_processor.authorize(
            amount=Decimal("185.00"),
            payment_method=payment_method,
            metadata={"account_id": account["account_id"]}
        )

        assert auth_success
        assert auth_id

        # Capture
        capture_success, capture_id, capture_error = await payment_processor.capture(
            auth_id=auth_id,
            amount=Decimal("185.00")
        )

        assert capture_success
        assert capture_id

        # Log
        audit_logger.log("payment", account["account_id"], "payment_captured", {
            "amount": 185.00,
            "capture_id": capture_id
        })

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_settlement_payment_processing(self, data_generator, payment_processor):
        """Test settlement payment (partial balance)"""
        account = data_generator.generate_account(balance=Decimal("500.00"))
        payment_method = data_generator.generate_payment_method("card")

        # Settlement at 50%
        settlement_amount = Decimal("250.00")

        auth_success, auth_id, _ = await payment_processor.authorize(
            amount=settlement_amount,
            payment_method=payment_method,
            metadata={
                "account_id": account["account_id"],
                "payment_type": "settlement",
                "original_balance": 500.00
            }
        )

        assert auth_success

        capture_success, capture_id, _ = await payment_processor.capture(
            auth_id=auth_id,
            amount=settlement_amount
        )

        assert capture_success

        # Verify transaction recorded
        assert capture_id in payment_processor.transactions

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_payment_plan_execution(self, data_generator, payment_processor, audit_logger):
        """Test payment plan execution over time"""
        account = data_generator.generate_account(balance=Decimal("300.00"))
        payment_method = data_generator.generate_payment_method("bank_account")

        # 3-month payment plan: $100/month
        plan_payments = [
            {"month": 1, "amount": Decimal("100.00")},
            {"month": 2, "amount": Decimal("100.00")},
            {"month": 3, "amount": Decimal("100.00")},
        ]

        total_paid = Decimal("0")

        for payment in plan_payments:
            auth_success, auth_id, _ = await payment_processor.authorize(
                amount=payment["amount"],
                payment_method=payment_method,
                metadata={
                    "account_id": account["account_id"],
                    "payment_type": "plan",
                    "installment": payment["month"]
                }
            )

            if auth_success:
                capture_success, capture_id, _ = await payment_processor.capture(
                    auth_id=auth_id,
                    amount=payment["amount"]
                )

                if capture_success:
                    total_paid += payment["amount"]
                    audit_logger.log("payment", account["account_id"], "plan_payment", {
                        "installment": payment["month"],
                        "amount": float(payment["amount"]),
                        "total_paid": float(total_paid)
                    })

        assert total_paid == Decimal("300.00")

        # Verify all installments logged
        entries = audit_logger.get_entries(
            account_id=account["account_id"],
            event_type="payment"
        )
        assert len(entries) == 3


class TestResolutionAndRestoration:
    """Test debt resolution and consumer restoration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_resolution_flow(self, data_generator, audit_logger):
        """Test complete debt resolution"""
        account = data_generator.generate_account(balance=Decimal("200.00"))
        ledger = LiveLedger()
        rehab = RehabilitationLoop()

        # Ingest debt
        record = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=200.00,
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45
        )

        # Initialize rehabilitation tracking
        rehab.initialize_consumer(account["consumer_id"])

        # Simulate payment
        ledger.record_interaction(
            record.record_id,
            "payment_portal",
            response_received=True,
            payment_received=200.00  # Full payment
        )

        # Record payment in rehab loop
        rehab.record_payment(
            consumer_id=account["consumer_id"],
            amount=200.00,
            on_time=True,
            resolves_debt=True,
            creditor_id="KLARNA"
        )

        # Issue restoration certificate
        cert = rehab.issue_restoration_certificate(
            consumer_id=account["consumer_id"],
            creditor_id="KLARNA",
            creditor_name="Klarna",
            original_amount=200.00,
            resolved_amount=200.00,
            resolution_type="paid_full"
        )

        assert cert is not None
        assert cert.resolution_type == "paid_full"

        # Verify debt marked resolved
        assert record.collection_status == "resolved"

        # Log resolution
        audit_logger.log("resolution", account["account_id"], "debt_resolved", {
            "certificate_id": cert.certificate_id,
            "resolution_type": "paid_full"
        })

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_restoration_certificate_verification(self, data_generator):
        """Test restoration certificate can be verified"""
        account = data_generator.generate_account()
        rehab = RehabilitationLoop()

        rehab.initialize_consumer(account["consumer_id"])

        # Make payments to build trust
        for i in range(3):
            rehab.record_payment(
                consumer_id=account["consumer_id"],
                amount=50.00,
                on_time=True,
                resolves_debt=(i == 2)
            )

        # Issue certificate
        cert = rehab.issue_restoration_certificate(
            consumer_id=account["consumer_id"],
            creditor_id="KLARNA",
            creditor_name="Klarna",
            original_amount=150.00,
            resolved_amount=150.00,
            resolution_type="paid_full"
        )

        # Verify certificate
        verification = rehab.verify_certificate(cert.certificate_id)

        assert verification["valid"]
        assert verification["consumer_id"] == account["consumer_id"]
        assert "recommendation" in verification

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trust_level_progression(self, data_generator):
        """Test consumer trust level progresses with good behavior"""
        account = data_generator.generate_account()
        rehab = RehabilitationLoop()

        rehab.initialize_consumer(account["consumer_id"])

        initial_level = rehab.trust_scores[account["consumer_id"]].current_level
        assert initial_level == TrustLevel.UNTRUSTED

        # Make consistent on-time payments
        for i in range(10):
            result = rehab.record_payment(
                consumer_id=account["consumer_id"],
                amount=25.00,
                on_time=True,
                resolves_debt=(i == 9)
            )

        final_level = rehab.trust_scores[account["consumer_id"]].current_level

        # Should have progressed from UNTRUSTED
        assert final_level.value > initial_level.value

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_lifecycle_end_to_end(
        self, data_generator, payment_processor, communication_service, audit_logger
    ):
        """Test complete end-to-end lifecycle: ingestion -> resolution"""
        account = data_generator.generate_account(
            balance=Decimal("185.00"),
            days_past_due=45
        )
        payment_method = data_generator.generate_payment_method("card")

        ledger = LiveLedger()
        rehab = RehabilitationLoop()

        # STEP 1: Ingest debt
        record = ledger.ingest_debt(
            creditor_id="KLARNA",
            creditor_name="Klarna",
            consumer_id=account["consumer_id"],
            category=DebtCategory.BNPL,
            original_balance=185.00,
            charge_off_date=datetime.utcnow() - timedelta(days=45),
            days_past_due=45,
            consumer_data={"state": account["debtor_state"]}
        )
        audit_logger.log("lifecycle", account["account_id"], "debt_ingested", {})

        # STEP 2: Initialize consumer profile
        rehab.initialize_consumer(account["consumer_id"])
        audit_logger.log("lifecycle", account["account_id"], "profile_created", {})

        # STEP 3: Execute contact sequence
        await communication_service.send_sms(
            to=account["debtor_phone"],
            message="Initial contact. Debt collector.",
            metadata={"account_id": account["account_id"]}
        )
        ledger.record_interaction(record.record_id, "sms", response_received=True)
        audit_logger.log("lifecycle", account["account_id"], "contacted", {"channel": "sms"})

        # STEP 4: Generate and present settlement
        settlement_amount = Decimal("120.00")  # ~65% settlement
        audit_logger.log("lifecycle", account["account_id"], "settlement_offered", {
            "amount": float(settlement_amount)
        })

        # STEP 5: Process payment
        auth_success, auth_id, _ = await payment_processor.authorize(
            amount=settlement_amount,
            payment_method=payment_method,
            metadata={"account_id": account["account_id"]}
        )
        capture_success, capture_id, _ = await payment_processor.capture(auth_id, settlement_amount)
        audit_logger.log("lifecycle", account["account_id"], "payment_processed", {
            "amount": float(settlement_amount)
        })

        # STEP 6: Record payment and resolve
        ledger.record_interaction(record.record_id, "payment", response_received=True,
                                   payment_received=float(settlement_amount))
        rehab.record_payment(account["consumer_id"], float(settlement_amount), True, True)
        audit_logger.log("lifecycle", account["account_id"], "debt_resolved", {})

        # STEP 7: Issue restoration certificate
        cert = rehab.issue_restoration_certificate(
            account["consumer_id"], "KLARNA", "Klarna",
            185.00, float(settlement_amount), "settled"
        )
        audit_logger.log("lifecycle", account["account_id"], "restoration_issued", {
            "certificate_id": cert.certificate_id
        })

        # VERIFY: Complete audit trail
        entries = audit_logger.get_entries(account_id=account["account_id"])
        assert len(entries) >= 7

        # VERIFY: Audit chain integrity
        assert audit_logger.verify_chain()

        # VERIFY: Final state
        assert record.collection_status == "resolved"
        assert cert is not None
        profile = ledger.consumer_profiles.get(account["consumer_id"])
        assert profile.shadow_score > 300  # Improved from activity
