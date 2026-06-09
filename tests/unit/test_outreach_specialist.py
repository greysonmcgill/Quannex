# tests/unit/test_outreach_specialist.py
"""
OutreachSpecialist unit tests.

Uses MockLLMWrapper (no network) and the production ephemeral
AgentSessionMemory.  Verifies per-channel prompt construction, Mini-Miranda
inclusion, settlement-offer handling, preflight flag blocking, postflight
validation, and that generated drafts pass the deterministic ComplianceGuard
for a clean account.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from quan.agents.compliance_guard import ComplianceGuard
from quan.agents.llm_wrapper import AgentOutput
from quan.agents.memory import AgentSessionMemory
from quan.agents.mock_llm import ADVERSARIAL_RESPONSES, MockLLMWrapper
from quan.agents.outreach_specialist import (
    CHANNEL_LIMITS,
    MINI_MIRANDA,
    OutreachSpecialist,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_account() -> dict[str, Any]:
    """Account with no compliance flags set."""
    return {
        "account_id": "ACC-OUT-001",
        "debtor_name": "John Doe",
        "debtor_first_name": "John",
        "state": "CA",
        "balance": 385.00,
        "current_balance": 385.00,
        "original_balance": 450.00,
        "days_past_due": 42,
        "total_contact_attempts": 2,
        "days_since_first_contact": 3,
        "do_not_call": False,
        "do_not_email": False,
        "do_not_mail": False,
        "bankruptcy_flag": False,
        "deceased_flag": False,
        "disputed": False,
        "attorney_represented": False,
        "statute_of_limitations_expired": False,
    }


@pytest.fixture
def specialist() -> OutreachSpecialist:
    return OutreachSpecialist()


@pytest.fixture
def memory() -> AgentSessionMemory:
    mem = AgentSessionMemory()
    mem.update_ml_cache(
        account_id="ACC-OUT-001",
        recovery_probability=0.42,
        settlement_threshold=0.7,
        optimal_channels=["email", "sms"],
    )
    return mem


@pytest.fixture
def llm() -> MockLLMWrapper:
    return MockLLMWrapper()


# ---------------------------------------------------------------------------
# Message generation per channel
# ---------------------------------------------------------------------------


class TestChannelGeneration:
    async def test_email_draft_generated(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "email"},
            llm=llm,
        )

        assert result.action == "draft"
        assert result.payload["channel"] == "email"
        assert result.payload["message_text"]
        # Specialist embedded the channel + correct char limit in the prompt.
        prompt = llm.call_history[-1]["user_message"]
        assert "<channel>email</channel>" in prompt
        assert f"<char_limit>{CHANNEL_LIMITS['email']}</char_limit>" in prompt
        assert "<balance>$385.00</balance>" in prompt

    async def test_sms_channel_draft(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "sms"},
            llm=llm,
        )

        assert result.action == "draft"
        assert result.payload["channel"] == "sms"
        prompt = llm.call_history[-1]["user_message"]
        assert "<channel>sms</channel>" in prompt
        assert f"<char_limit>{CHANNEL_LIMITS['sms']}</char_limit>" in prompt

    async def test_mail_channel_uses_mail_char_limit(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "mail"},
            llm=llm,
        )

        prompt = llm.call_history[-1]["user_message"]
        assert "<channel>mail</channel>" in prompt
        assert f"<char_limit>{CHANNEL_LIMITS['mail']}</char_limit>" in prompt


# ---------------------------------------------------------------------------
# Mini-Miranda
# ---------------------------------------------------------------------------


class TestMiniMiranda:
    async def test_mini_miranda_required_in_system_prompt(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "email"},
            llm=llm,
        )

        system = llm.call_history[-1]["system"]
        assert MINI_MIRANDA in system

    async def test_generated_draft_contains_mini_miranda(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "email"},
            llm=llm,
        )

        text = result.payload["message_text"].lower()
        assert "attempt to collect" in text
        assert "debt collector" in text
        # Postflight found no issues, so no compliance warnings were attached.
        assert "compliance_warnings" not in result.payload
        # The postflight audit note recorded a passing check.
        assert memory.compliance_notes[-1]["passed"] is True

    async def test_draft_missing_mini_miranda_is_flagged(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        """Adversarial LLM output without the disclosure gets warning-flagged."""
        llm.queue_response(
            ADVERSARIAL_RESPONSES["missing_mini_miranda"].model_copy(deep=True)
        )

        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "sms"},
            llm=llm,
        )

        warnings = result.payload["compliance_warnings"]
        assert any("debt collector" in w for w in warnings)
        assert any("attempt to collect" in w for w in warnings)
        # The draft is routed back through the verifier, not sent directly.
        assert result.next_steps[0] == "verify"
        failed = [n for n in memory.compliance_notes if not n["passed"]]
        assert failed and failed[0]["check"] == "outreach_postflight"


# ---------------------------------------------------------------------------
# Settlement offer handling
# ---------------------------------------------------------------------------


class TestOfferPercentage:
    async def test_offer_pct_renders_settlement_line(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        await specialist.execute(
            memory=memory,
            payload={
                "account": clean_account,
                "channel": "email",
                "goal": "settlement_offer",
                "offer_pct": 0.70,
            },
            llm=llm,
        )

        prompt = llm.call_history[-1]["user_message"]
        # 70% of $385.00 = $269.50
        assert "We can offer a settlement of $269.50" in prompt
        assert "(70% of $385.00)" in prompt
        assert "<message_goal>settlement_offer</message_goal>" in prompt

    async def test_no_settlement_line_without_offer_pct(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": "email"},
            llm=llm,
        )

        prompt = llm.call_history[-1]["user_message"]
        assert "<settlement_info></settlement_info>" in prompt
        assert "We can offer a settlement" not in prompt


# ---------------------------------------------------------------------------
# Preflight compliance blocking
# ---------------------------------------------------------------------------


class TestPreflightBlocking:
    @pytest.mark.parametrize(
        ("flag", "channel", "expected_fragment"),
        [
            ("bankruptcy_flag", "email", "Bankruptcy"),
            ("deceased_flag", "sms", "deceased"),
            ("attorney_represented", "email", "Attorney"),
            ("do_not_email", "email", "Do-not-email"),
        ],
    )
    async def test_flagged_accounts_blocked_before_llm(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
        flag: str,
        channel: str,
        expected_fragment: str,
    ):
        clean_account[flag] = True

        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": channel},
            llm=llm,
        )

        assert result.action == "block"
        assert expected_fragment in result.payload["block_reason"]
        # Blocked before any LLM tokens were spent.
        assert llm.call_count == 0
        assert memory.compliance_notes[-1]["passed"] is False


# ---------------------------------------------------------------------------
# End-to-end: drafts must pass the deterministic ComplianceGuard
# ---------------------------------------------------------------------------


class TestComplianceGuardIntegration:
    @pytest.mark.parametrize("channel", ["email", "sms"])
    async def test_generated_draft_passes_compliance_guard(
        self,
        specialist: OutreachSpecialist,
        memory: AgentSessionMemory,
        llm: MockLLMWrapper,
        clean_account: dict,
        channel: str,
    ):
        result = await specialist.execute(
            memory=memory,
            payload={"account": clean_account, "channel": channel},
            llm=llm,
        )

        guard = ComplianceGuard(strict_mode=True)
        contact_time = datetime(2026, 6, 9, 14, 0, tzinfo=timezone.utc)  # 2 PM
        guard_result = guard.check_outreach(
            result.payload["message_text"],
            channel,
            clean_account,
            contact_time=contact_time,
        )

        assert guard_result.passed, (
            f"Draft failed guard: {[v.description for v in guard_result.violations]}"
        )
