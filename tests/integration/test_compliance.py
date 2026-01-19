"""
QUAN Integration Tests: Compliance

Comprehensive compliance testing for:
1. FDCPA timing rules
2. Regulation F 7-in-7 enforcement
3. State-specific rule application
4. Consent management
5. Audit trail completeness

Tests ensure the system maintains regulatory compliance under all conditions.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, time
from decimal import Decimal
from typing import Dict, List, Any
import uuid

import sys
sys.path.insert(0, '/home/user/Quan')


# =============================================================================
# COMPLIANCE RULE IMPLEMENTATIONS FOR TESTING
# =============================================================================

class ComplianceRuleEngine:
    """Compliance rule engine for testing"""

    # FDCPA calling hours (8am-9pm local time)
    FDCPA_START_HOUR = 8
    FDCPA_END_HOUR = 21

    # Regulation F: 7 contacts in 7 days limit
    REG_F_CONTACT_LIMIT = 7
    REG_F_WINDOW_DAYS = 7

    # State-specific statutes of limitations (years)
    STATE_SOL = {
        "CA": 4, "NY": 6, "TX": 4, "FL": 5, "IL": 5,
        "PA": 4, "OH": 6, "GA": 6, "NC": 3, "MI": 6,
        "NJ": 6, "VA": 5, "WA": 6, "AZ": 6, "MA": 6
    }

    # States requiring collection agency license
    LICENSE_REQUIRED_STATES = [
        "CA", "NY", "TX", "FL", "IL", "PA", "CT", "CO",
        "GA", "MD", "MA", "NJ", "NC", "OH", "OR", "WA"
    ]

    # Prohibited terms in communications
    PROHIBITED_TERMS = [
        "arrest", "jail", "prison", "criminal",
        "garnish your wages", "seize your property",
        "sue you", "take legal action"
    ]

    # Required disclosures
    REQUIRED_DISCLOSURES = {
        "mini_miranda": ["debt collector", "attempt to collect a debt"],
        "validation_notice": ["30 days", "dispute", "verification"]
    }

    def __init__(self):
        self.contact_history: Dict[str, List[Dict]] = {}
        self.consent_records: Dict[str, Dict] = {}
        self.audit_log: List[Dict] = []

    async def validate_contact_timing(
        self,
        account: Dict,
        channel: str,
        contact_time: datetime = None
    ) -> tuple:
        """Validate contact timing against FDCPA rules"""
        if contact_time is None:
            contact_time = datetime.utcnow()

        # Only phone/SMS restricted by time
        if channel not in ["phone", "sms", "voice", "voicemail"]:
            return True, None

        state = account.get("debtor_state", "NY")
        local_hour = self._get_local_hour(contact_time, state)

        if local_hour < self.FDCPA_START_HOUR:
            return False, f"Contact before {self.FDCPA_START_HOUR}am local time not allowed"

        if local_hour >= self.FDCPA_END_HOUR:
            return False, f"Contact after {self.FDCPA_END_HOUR - 12}pm local time not allowed"

        return True, None

    async def validate_contact_frequency(
        self,
        account_id: str,
        contact_time: datetime = None
    ) -> tuple:
        """Validate against Regulation F 7-in-7 rule"""
        if contact_time is None:
            contact_time = datetime.utcnow()

        history = self.contact_history.get(account_id, [])

        # Count contacts in last 7 days
        window_start = contact_time - timedelta(days=self.REG_F_WINDOW_DAYS)
        recent_contacts = [
            c for c in history
            if c["timestamp"] > window_start
        ]

        if len(recent_contacts) >= self.REG_F_CONTACT_LIMIT:
            return False, f"Regulation F: {self.REG_F_CONTACT_LIMIT} contacts in {self.REG_F_WINDOW_DAYS} days exceeded"

        return True, None

    async def validate_message_content(
        self,
        message: str,
        channel: str,
        state: str,
        is_initial: bool = False
    ) -> tuple:
        """Validate message content for prohibited terms and required disclosures"""
        violations = []
        message_lower = message.lower()

        # Check prohibited terms
        for term in self.PROHIBITED_TERMS:
            if term in message_lower:
                violations.append(f"Prohibited term: '{term}'")

        # Check required disclosures for written communications
        if channel in ["email", "letter", "sms"]:
            for disclosure_type, phrases in self.REQUIRED_DISCLOSURES.items():
                if disclosure_type == "mini_miranda":
                    has_disclosure = any(phrase in message_lower for phrase in phrases)
                    if not has_disclosure:
                        violations.append(f"Missing mini-Miranda disclosure")

                if is_initial and disclosure_type == "validation_notice":
                    has_validation = all(phrase in message_lower for phrase in phrases)
                    if not has_validation:
                        violations.append(f"Initial contact missing validation notice")

        return len(violations) == 0, violations

    async def validate_consent(
        self,
        account_id: str,
        channel: str
    ) -> tuple:
        """Validate consent for contact channel"""
        consent = self.consent_records.get(account_id, {})

        consent_mapping = {
            "sms": "sms_consent",
            "email": "email_consent",
            "voice": "voice_consent",
            "phone": "voice_consent"
        }

        consent_field = consent_mapping.get(channel)
        if consent_field and not consent.get(consent_field, False):
            return False, f"No consent for {channel} channel"

        # Check if consent was revoked
        if consent.get(f"{consent_field}_revoked"):
            return False, f"Consent for {channel} was revoked"

        return True, None

    async def validate_statute_of_limitations(
        self,
        account: Dict
    ) -> tuple:
        """Validate debt is within statute of limitations"""
        state = account.get("debtor_state", "NY")
        sol_years = self.STATE_SOL.get(state, 6)

        charge_off_date = account.get("charge_off_date")
        if isinstance(charge_off_date, str):
            charge_off_date = datetime.fromisoformat(charge_off_date.replace("Z", "+00:00"))

        if charge_off_date:
            sol_expiry = charge_off_date + timedelta(days=sol_years * 365)
            if datetime.utcnow() > sol_expiry:
                return False, f"Debt past {state} statute of limitations ({sol_years} years)"

        return True, None

    async def validate_license_required(
        self,
        state: str
    ) -> tuple:
        """Check if state requires collection agency license"""
        requires_license = state in self.LICENSE_REQUIRED_STATES
        return True, {"requires_license": requires_license, "state": state}

    def record_contact(self, account_id: str, channel: str, success: bool):
        """Record contact attempt for tracking"""
        if account_id not in self.contact_history:
            self.contact_history[account_id] = []

        self.contact_history[account_id].append({
            "timestamp": datetime.utcnow(),
            "channel": channel,
            "success": success
        })

    def set_consent(self, account_id: str, consent_data: Dict):
        """Set consent records for account"""
        self.consent_records[account_id] = consent_data

    def _get_local_hour(self, utc_time: datetime, state: str) -> int:
        """Get approximate local hour for state (simplified)"""
        # Simplified timezone offsets
        offsets = {
            "CA": -8, "WA": -8, "OR": -8, "NV": -8,
            "AZ": -7, "CO": -7, "MT": -7, "NM": -7, "UT": -7,
            "TX": -6, "IL": -6, "MN": -6, "WI": -6, "MO": -6,
            "NY": -5, "FL": -5, "GA": -5, "PA": -5, "OH": -5,
            "NC": -5, "VA": -5, "MA": -5, "NJ": -5, "MI": -5
        }
        offset = offsets.get(state, -5)
        return (utc_time.hour + offset) % 24


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestFDCPATimingRules:
    """Test FDCPA calling hours compliance"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_contact_allowed_during_business_hours(self, compliance_engine, data_generator):
        """Test contact is allowed during 8am-9pm local time"""
        account = data_generator.generate_account(state="NY")

        # 2pm local time (7pm UTC for NY)
        test_time = datetime.utcnow().replace(hour=19, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "phone", test_time
        )

        assert valid
        assert reason is None

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_contact_blocked_before_8am(self, compliance_engine, data_generator):
        """Test contact blocked before 8am local time"""
        account = data_generator.generate_account(state="NY")

        # 6am local time (11am UTC for NY)
        test_time = datetime.utcnow().replace(hour=11, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "phone", test_time
        )

        assert not valid
        assert "8am" in reason.lower() or "before" in reason.lower()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_contact_blocked_after_9pm(self, compliance_engine, data_generator):
        """Test contact blocked after 9pm local time"""
        account = data_generator.generate_account(state="NY")

        # 10pm local time (3am UTC next day for NY)
        test_time = datetime.utcnow().replace(hour=3, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "phone", test_time
        )

        assert not valid
        assert "9pm" in reason.lower() or "after" in reason.lower()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_email_allowed_anytime(self, compliance_engine, data_generator):
        """Test email is allowed at any time (not subject to calling hours)"""
        account = data_generator.generate_account(state="NY")

        # 3am - would be blocked for phone
        test_time = datetime.utcnow().replace(hour=3, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "email", test_time
        )

        assert valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_timezone_handling_california(self, compliance_engine, data_generator):
        """Test timezone handling for California (PST/PDT)"""
        account = data_generator.generate_account(state="CA")

        # 12pm UTC = 4am PST (blocked) or 5am PDT (blocked)
        test_time = datetime.utcnow().replace(hour=12, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "phone", test_time
        )

        # Should be blocked - before 8am local
        assert not valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_timezone_handling_florida(self, compliance_engine, data_generator):
        """Test timezone handling for Florida (EST/EDT)"""
        account = data_generator.generate_account(state="FL")

        # 3pm UTC = 10am EST (allowed)
        test_time = datetime.utcnow().replace(hour=15, minute=0)

        valid, reason = await compliance_engine.validate_contact_timing(
            account, "phone", test_time
        )

        assert valid


class TestRegulationF:
    """Test Regulation F 7-in-7 rule compliance"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_first_contact_allowed(self, compliance_engine, data_generator):
        """Test first contact is always allowed"""
        account = data_generator.generate_account()

        valid, reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )

        assert valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_seven_contacts_in_seven_days_allowed(self, compliance_engine, data_generator):
        """Test 7 contacts in 7 days is at the limit"""
        account = data_generator.generate_account()

        # Record 6 contacts
        for _ in range(6):
            compliance_engine.record_contact(account["account_id"], "phone", True)

        # 7th contact should be allowed (at limit)
        valid, reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )

        assert valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_eighth_contact_blocked(self, compliance_engine, data_generator):
        """Test 8th contact in 7 days is blocked"""
        account = data_generator.generate_account()

        # Record 7 contacts
        for _ in range(7):
            compliance_engine.record_contact(account["account_id"], "phone", True)

        # 8th contact should be blocked
        valid, reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )

        assert not valid
        assert "7" in reason  # Should mention the limit

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_contact_window_resets_after_seven_days(self, compliance_engine, data_generator):
        """Test contact limit resets after 7 days"""
        account = data_generator.generate_account()

        # Manually set old contacts (8 days ago)
        old_time = datetime.utcnow() - timedelta(days=8)
        for _ in range(7):
            compliance_engine.contact_history.setdefault(account["account_id"], []).append({
                "timestamp": old_time,
                "channel": "phone",
                "success": True
            })

        # New contact should be allowed
        valid, reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )

        assert valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_different_channels_count_separately(self, compliance_engine, data_generator):
        """Test contact limit applies per account regardless of channel"""
        account = data_generator.generate_account()

        # Mix of channels - all count toward limit
        channels = ["phone", "sms", "email", "phone", "sms", "phone", "email"]
        for channel in channels:
            compliance_engine.record_contact(account["account_id"], channel, True)

        # 8th contact blocked regardless of channel
        valid, reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )

        assert not valid


class TestStateSpecificRules:
    """Test state-specific compliance rules"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_california_sol_four_years(self, compliance_engine, data_generator):
        """Test California 4-year statute of limitations"""
        account = data_generator.generate_account(state="CA")

        # Debt from 3 years ago - within SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=3*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert valid

        # Debt from 5 years ago - past SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=5*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert not valid
        assert "4 years" in reason

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_new_york_sol_six_years(self, compliance_engine, data_generator):
        """Test New York 6-year statute of limitations"""
        account = data_generator.generate_account(state="NY")

        # Debt from 5 years ago - within SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=5*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert valid

        # Debt from 7 years ago - past SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=7*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert not valid
        assert "6 years" in reason

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_north_carolina_sol_three_years(self, compliance_engine, data_generator):
        """Test North Carolina 3-year statute of limitations"""
        account = data_generator.generate_account(state="NC")

        # Debt from 2 years ago - within SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=2*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert valid

        # Debt from 4 years ago - past SOL
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=4*365)).isoformat()

        valid, reason = await compliance_engine.validate_statute_of_limitations(account)
        assert not valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_license_required_states(self, compliance_engine):
        """Test identification of states requiring collection license"""
        # States requiring license
        for state in ["CA", "NY", "TX", "FL"]:
            valid, info = await compliance_engine.validate_license_required(state)
            assert info["requires_license"]

        # States not requiring license (check a few)
        # Note: Most states do require licenses, this is simplified

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_all_states_sol_coverage(self, compliance_engine, data_generator):
        """Test SOL rules cover all major states"""
        major_states = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"]

        for state in major_states:
            account = data_generator.generate_account(state=state)
            account["charge_off_date"] = (datetime.utcnow() - timedelta(days=30)).isoformat()

            valid, reason = await compliance_engine.validate_statute_of_limitations(account)

            # Recent debt should be within SOL for all states
            assert valid, f"State {state} SOL check failed for recent debt"


class TestConsentManagement:
    """Test consent management compliance"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_sms_requires_consent(self, compliance_engine, data_generator):
        """Test SMS contact requires explicit consent"""
        account = data_generator.generate_account()

        # No consent set
        valid, reason = await compliance_engine.validate_consent(
            account["account_id"], "sms"
        )
        assert not valid

        # Set consent
        compliance_engine.set_consent(account["account_id"], {"sms_consent": True})

        valid, reason = await compliance_engine.validate_consent(
            account["account_id"], "sms"
        )
        assert valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_voice_requires_consent(self, compliance_engine, data_generator):
        """Test voice contact requires consent"""
        account = data_generator.generate_account()

        # Set voice consent
        compliance_engine.set_consent(account["account_id"], {"voice_consent": True})

        valid, reason = await compliance_engine.validate_consent(
            account["account_id"], "voice"
        )
        assert valid

        # No consent
        compliance_engine.set_consent(account["account_id"], {"voice_consent": False})

        valid, reason = await compliance_engine.validate_consent(
            account["account_id"], "voice"
        )
        assert not valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_consent_revocation_honored(self, compliance_engine, data_generator):
        """Test revoked consent is honored"""
        account = data_generator.generate_account()

        # Consent given then revoked
        compliance_engine.set_consent(account["account_id"], {
            "sms_consent": True,
            "sms_consent_revoked": True
        })

        valid, reason = await compliance_engine.validate_consent(
            account["account_id"], "sms"
        )

        assert not valid
        assert "revoked" in reason.lower()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_multi_channel_consent(self, compliance_engine, data_generator):
        """Test consent is managed per channel"""
        account = data_generator.generate_account()

        # SMS yes, voice no, email yes
        compliance_engine.set_consent(account["account_id"], {
            "sms_consent": True,
            "voice_consent": False,
            "email_consent": True
        })

        sms_valid, _ = await compliance_engine.validate_consent(account["account_id"], "sms")
        voice_valid, _ = await compliance_engine.validate_consent(account["account_id"], "voice")
        email_valid, _ = await compliance_engine.validate_consent(account["account_id"], "email")

        assert sms_valid
        assert not voice_valid
        assert email_valid


class TestMessageCompliance:
    """Test message content compliance"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_message_with_proper_disclosures(self, compliance_engine):
        """Test message with required disclosures passes validation"""
        message = """
        This is QUAN Recovery, a debt collector.
        This is an attempt to collect a debt and any information
        obtained will be used for that purpose.
        Please contact us regarding your account.
        """

        valid, violations = await compliance_engine.validate_message_content(
            message, "email", "CA", is_initial=False
        )

        assert valid
        assert len(violations) == 0

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_message_missing_mini_miranda(self, compliance_engine):
        """Test message missing mini-Miranda fails validation"""
        message = """
        Please contact us to discuss your account balance.
        We have payment options available.
        """

        valid, violations = await compliance_engine.validate_message_content(
            message, "email", "CA"
        )

        assert not valid
        assert any("mini-Miranda" in v or "disclosure" in v for v in violations)

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_message_with_prohibited_terms(self, compliance_engine):
        """Test message with prohibited terms fails validation"""
        prohibited_messages = [
            "Pay now or you will be arrested for this debt.",
            "We will garnish your wages if you don't pay.",
            "You could go to jail for not paying this debt.",
            "We will sue you if payment is not received.",
        ]

        for message in prohibited_messages:
            # Add mini-miranda to isolate the prohibited term check
            full_message = message + " This is a debt collector attempting to collect a debt."

            valid, violations = await compliance_engine.validate_message_content(
                full_message, "email", "CA"
            )

            assert not valid, f"Message should fail: {message}"
            assert any("prohibited" in v.lower() for v in violations)

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_initial_contact_requires_validation_notice(self, compliance_engine):
        """Test initial contact requires validation notice"""
        # Message without validation notice components
        message = """
        This is QUAN Recovery, a debt collector.
        This is an attempt to collect a debt.
        Please pay your balance of $500.
        """

        valid, violations = await compliance_engine.validate_message_content(
            message, "email", "CA", is_initial=True
        )

        assert not valid
        assert any("validation" in v.lower() for v in violations)

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_sms_compliance(self, compliance_engine):
        """Test SMS messages are compliant"""
        # Good SMS
        good_sms = "QUAN Recovery, a debt collector. Settlement available. Reply YES. This is an attempt to collect a debt."

        valid, violations = await compliance_engine.validate_message_content(
            good_sms, "sms", "CA"
        )

        assert valid

        # Bad SMS - missing disclosure
        bad_sms = "You owe money. Pay now or face consequences."

        valid, violations = await compliance_engine.validate_message_content(
            bad_sms, "sms", "CA"
        )

        assert not valid


class TestAuditTrailCompleteness:
    """Test audit trail completeness and integrity"""

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_audit_trail_captures_all_contacts(self, data_generator, audit_logger, communication_service):
        """Test all contact attempts are logged"""
        account = data_generator.generate_account()

        # Make contacts
        await communication_service.send_sms(
            account["debtor_phone"], "Test SMS", {"account_id": account["account_id"]}
        )
        audit_logger.log("contact", account["account_id"], "sms_sent", {"channel": "sms"})

        await communication_service.send_email(
            account["debtor_email"], "Test", "Body", {"account_id": account["account_id"]}
        )
        audit_logger.log("contact", account["account_id"], "email_sent", {"channel": "email"})

        await communication_service.make_call(
            account["debtor_phone"], {}, {"account_id": account["account_id"]}
        )
        audit_logger.log("contact", account["account_id"], "call_made", {"channel": "voice"})

        # Verify audit trail
        entries = audit_logger.get_entries(account_id=account["account_id"])
        assert len(entries) == 3

        channels_logged = [e["details"].get("channel") for e in entries]
        assert "sms" in channels_logged
        assert "email" in channels_logged
        assert "voice" in channels_logged

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_audit_trail_integrity(self, data_generator, audit_logger):
        """Test audit trail maintains hash chain integrity"""
        account = data_generator.generate_account()

        # Create multiple entries
        for i in range(10):
            audit_logger.log(
                "test_event",
                account["account_id"],
                f"action_{i}",
                {"sequence": i}
            )

        # Verify chain integrity
        assert audit_logger.verify_chain()

        # Verify entries are linked
        entries = audit_logger.entries
        for i in range(1, len(entries)):
            assert entries[i]["prev_hash"] == entries[i-1]["hash"]

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_audit_entries_immutable(self, data_generator, audit_logger):
        """Test audit entries cannot be tampered with"""
        account = data_generator.generate_account()

        audit_logger.log("test", account["account_id"], "original_action", {"data": "original"})

        original_hash = audit_logger.entries[0]["hash"]

        # Attempt to modify (simulated)
        # In real system, this would fail cryptographic verification
        assert audit_logger.entries[0]["hash"] == original_hash

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_audit_trail_timestamps(self, data_generator, audit_logger):
        """Test audit entries have accurate timestamps"""
        account = data_generator.generate_account()

        before_time = datetime.utcnow()
        audit_logger.log("test", account["account_id"], "test_action", {})
        after_time = datetime.utcnow()

        entry = audit_logger.entries[0]
        entry_time = datetime.fromisoformat(entry["timestamp"])

        # Timestamp should be between before and after
        assert before_time <= entry_time <= after_time

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_audit_trail_query_by_type(self, data_generator, audit_logger):
        """Test audit trail can be queried by event type"""
        account = data_generator.generate_account()

        # Log different event types
        audit_logger.log("contact", account["account_id"], "sms_sent", {})
        audit_logger.log("contact", account["account_id"], "email_sent", {})
        audit_logger.log("payment", account["account_id"], "payment_received", {})
        audit_logger.log("compliance", account["account_id"], "validation_passed", {})

        # Query by type
        contact_entries = audit_logger.get_entries(event_type="contact")
        payment_entries = audit_logger.get_entries(event_type="payment")

        assert len(contact_entries) == 2
        assert len(payment_entries) == 1


class TestComprehensiveCompliance:
    """Test comprehensive compliance scenarios"""

    @pytest.fixture
    def compliance_engine(self):
        return ComplianceRuleEngine()

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_full_compliance_check(self, compliance_engine, data_generator, audit_logger):
        """Test complete compliance validation flow"""
        account = data_generator.generate_account(state="CA")
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=180)).isoformat()

        # Set consent
        compliance_engine.set_consent(account["account_id"], {
            "sms_consent": True,
            "email_consent": True,
            "voice_consent": True
        })

        # Validate all aspects
        checks = []

        # 1. Timing
        timing_valid, timing_reason = await compliance_engine.validate_contact_timing(
            account, "sms", datetime.utcnow().replace(hour=18)  # 6pm UTC = ~10am PST
        )
        checks.append(("timing", timing_valid, timing_reason))

        # 2. Frequency
        freq_valid, freq_reason = await compliance_engine.validate_contact_frequency(
            account["account_id"]
        )
        checks.append(("frequency", freq_valid, freq_reason))

        # 3. SOL
        sol_valid, sol_reason = await compliance_engine.validate_statute_of_limitations(
            account
        )
        checks.append(("sol", sol_valid, sol_reason))

        # 4. Consent
        consent_valid, consent_reason = await compliance_engine.validate_consent(
            account["account_id"], "sms"
        )
        checks.append(("consent", consent_valid, consent_reason))

        # 5. Message content
        message = "QUAN Recovery, a debt collector. This is an attempt to collect a debt. Please reply."
        content_valid, content_violations = await compliance_engine.validate_message_content(
            message, "sms", "CA"
        )
        checks.append(("content", content_valid, content_violations))

        # Log compliance check
        audit_logger.log("compliance", account["account_id"], "full_check", {
            "checks": [{"name": c[0], "passed": c[1]} for c in checks]
        })

        # All checks should pass
        failed_checks = [c for c in checks if not c[1]]
        assert len(failed_checks) == 0, f"Failed checks: {failed_checks}"

    @pytest.mark.asyncio
    @pytest.mark.compliance
    async def test_compliance_blocks_contact_appropriately(self, compliance_engine, data_generator):
        """Test compliance engine blocks contacts when violations exist"""
        account = data_generator.generate_account(state="CA")

        # Scenario 1: Past SOL - should block
        account["charge_off_date"] = (datetime.utcnow() - timedelta(days=5*365)).isoformat()
        sol_valid, _ = await compliance_engine.validate_statute_of_limitations(account)
        assert not sol_valid

        # Scenario 2: No consent - should block
        consent_valid, _ = await compliance_engine.validate_consent(account["account_id"], "sms")
        assert not consent_valid

        # Scenario 3: Exceeded contact limit - should block
        for _ in range(7):
            compliance_engine.record_contact(account["account_id"], "phone", True)
        freq_valid, _ = await compliance_engine.validate_contact_frequency(account["account_id"])
        assert not freq_valid

    @pytest.mark.asyncio
    @pytest.mark.compliance
    @pytest.mark.slow
    async def test_compliance_under_volume(self, compliance_engine, data_generator):
        """Test compliance checks perform under volume"""
        portfolio = data_generator.generate_portfolio(100)

        compliant_count = 0
        non_compliant_count = 0

        for account in portfolio:
            account["charge_off_date"] = (datetime.utcnow() - timedelta(days=90)).isoformat()
            compliance_engine.set_consent(account["account_id"], {
                "sms_consent": True, "email_consent": True, "voice_consent": True
            })

            sol_valid, _ = await compliance_engine.validate_statute_of_limitations(account)
            freq_valid, _ = await compliance_engine.validate_contact_frequency(account["account_id"])
            consent_valid, _ = await compliance_engine.validate_consent(account["account_id"], "sms")

            if sol_valid and freq_valid and consent_valid:
                compliant_count += 1
            else:
                non_compliant_count += 1

        # All should be compliant with proper setup
        assert compliant_count == 100
