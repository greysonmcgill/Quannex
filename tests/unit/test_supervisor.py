# tests/unit/test_supervisor.py
"""
QuannexSupervisor unit tests.

Uses MockLLMWrapper (no network, no API keys) plus the production
AgentSessionMemory backed by a tmp_path QuannexMemoryManager, so every
supervisor write is also exercised through the persistence envelope.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quan.agents.llm_wrapper import AgentOutput, LLMWrapper
from quan.agents.memory import AgentSessionMemory, QuannexMemoryManager
from quan.agents.mock_llm import ADVERSARIAL_RESPONSES, MockLLMWrapper
from quan.agents.supervisor import (
    BaseSpecialist,
    PlannerSpecialist,
    QuannexSupervisor,
    VerifierSpecialist,
)


# ---------------------------------------------------------------------------
# Test helpers / fixtures
# ---------------------------------------------------------------------------


class RecordingSpecialist(BaseSpecialist):
    """Specialist that records its invocation for assertions."""

    name = "recording"

    def __init__(self, action: str = "complete"):
        self.executed = False
        self.received_payload: dict[str, Any] | None = None
        self._action = action

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        self.executed = True
        self.received_payload = payload
        return AgentOutput(
            reasoning="Recording specialist executed.",
            action=self._action,
            payload={"handled_by": self.name},
            next_steps=["done"],
            token_estimate=10,
        )


@pytest.fixture
def clean_account() -> dict[str, Any]:
    """Full account dict with all compliance flags clear."""
    return {
        "account_id": "ACC-SUP-001",
        "debtor_name": "John Doe",
        "state": "CA",
        "balance": 250.00,
        "original_balance": 400.00,
        "original_creditor": "Acme BNPL",
        "days_past_due": 42,
        "status": "active",
        "recovery_probability": 0.5,
        "optimal_channels": ["sms", "email"],
        "settlement_threshold": 0.6,
        "total_paid": 0.0,
        "total_contact_attempts": 2,
        "last_contact_at": None,
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
def memory(tmp_path: Path) -> AgentSessionMemory:
    return AgentSessionMemory(
        persistence=QuannexMemoryManager(tmp_path / "supervisor_memory.json"),
        session_id="default",
    )


@pytest.fixture
def llm() -> MockLLMWrapper:
    return MockLLMWrapper()


@pytest.fixture
def supervisor(llm: MockLLMWrapper, memory: AgentSessionMemory) -> QuannexSupervisor:
    return QuannexSupervisor(llm=llm, memory=memory)


# ---------------------------------------------------------------------------
# Core step() behavior
# ---------------------------------------------------------------------------


class TestStepBasics:
    async def test_step_returns_agent_output(
        self, supervisor: QuannexSupervisor, clean_account: dict
    ):
        result = await supervisor.step(clean_account)

        assert isinstance(result, AgentOutput)
        assert isinstance(result.action, str) and result.action
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.payload, dict)
        assert isinstance(result.next_steps, list)

    async def test_step_consults_ml_fast_path(
        self,
        supervisor: QuannexSupervisor,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        """step() must score via CollectionIntelligence and cache the result."""
        await supervisor.step(clean_account)

        # Legacy view used by the supervisor decision loop.
        assert memory.state.ml_cache.account_id == "ACC-SUP-001"
        assert 0.0 <= memory.state.ml_cache.recovery_probability <= 1.0
        assert memory.state.ml_cache.optimal_channels

        # Real persisted cache in the underlying session state.
        assert "ACC-SUP-001" in memory.session.ml_cache
        entry = memory.session.ml_cache["ACC-SUP-001"]
        assert 0.0 <= entry.recovery_probability <= 1.0

        # ML scoring observation was recorded.
        contents = [o.content for o in memory.session.recent_observations]
        assert any("ML scored account ACC-SUP-001" in c for c in contents)

    async def test_step_ml_scores_persisted_to_disk(
        self,
        supervisor: QuannexSupervisor,
        memory: AgentSessionMemory,
        clean_account: dict,
        tmp_path: Path,
    ):
        await supervisor.step(clean_account)

        reloaded = QuannexMemoryManager(memory.persistence.path).load_state("default")
        assert "ACC-SUP-001" in reloaded.ml_cache

    async def test_step_increments_step_count_and_history(
        self,
        supervisor: QuannexSupervisor,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        await supervisor.step(clean_account)
        assert memory.state.step_count == 1
        obs_after_one = len(memory.session.recent_observations)
        assert obs_after_one >= 2  # ML score + decision observations

        await supervisor.step(clean_account)
        assert memory.state.step_count == 2
        assert len(memory.session.recent_observations) > obs_after_one

        sources = {o.source for o in memory.session.recent_observations}
        assert "supervisor" in sources

    async def test_ml_cache_prevents_rescoring_same_account(
        self,
        supervisor: QuannexSupervisor,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        await supervisor.step(clean_account)
        await supervisor.step(clean_account)

        contents = [o.content for o in memory.session.recent_observations]
        scoring_obs = [c for c in contents if c.startswith("ML scored account")]
        assert len(scoring_obs) == 1


# ---------------------------------------------------------------------------
# Specialist routing
# ---------------------------------------------------------------------------


class TestSpecialistRouting:
    async def test_register_specialist_adds_entry(
        self, supervisor: QuannexSupervisor
    ):
        custom = RecordingSpecialist()
        supervisor.register_specialist("negotiate", custom)
        assert supervisor.specialists["negotiate"] is custom

    async def test_supervisor_routes_to_registered_specialist(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        custom = RecordingSpecialist()
        supervisor.register_specialist("negotiate", custom)
        llm.queue_response(
            AgentOutput(
                reasoning="Delegate to the negotiation specialist.",
                action="negotiate",
                payload={"offer_pct": 0.65},
                next_steps=["await_response"],
                token_estimate=40,
            )
        )

        result = await supervisor.step(clean_account)

        assert custom.executed
        # Specialist receives the decision payload plus account and goal.
        assert custom.received_payload is not None
        assert custom.received_payload["offer_pct"] == 0.65
        assert custom.received_payload["account"] == clean_account
        assert "goal" in custom.received_payload
        # Specialist output is nested in the supervisor result.
        assert result.action == "negotiate"
        assert result.payload["specialist_result"]["payload"]["handled_by"] == "recording"
        assert result.next_steps == ["done"]

    async def test_plan_action_runs_planner_and_stores_plan(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        llm.queue_response(
            AgentOutput(
                reasoning="No plan exists yet.",
                action="plan",
                payload={},
                next_steps=[],
                token_estimate=30,
            )
        )

        result = await supervisor.step(clean_account)

        assert result.action == "plan"
        specialist_result = result.payload["specialist_result"]
        assert specialist_result["next_steps"]  # MockLLM planner returns 5 steps
        assert memory.state.current_plan == specialist_result["next_steps"]
        # Two LLM calls: supervisor decision + planner specialist.
        assert llm.call_count == 2

    async def test_score_action_reruns_ml_locally(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        llm.queue_response(
            AgentOutput(
                reasoning="ML scores are stale.",
                action="score",
                payload={},
                next_steps=["plan"],
                token_estimate=20,
            )
        )

        result = await supervisor.step(clean_account)

        assert result.action == "score"
        assert result.payload["account_id"] == "ACC-SUP-001"
        assert 0.0 <= result.payload["recovery_probability"] <= 1.0
        # Scoring is local — only the decision consumed an LLM call.
        assert llm.call_count == 1


# ---------------------------------------------------------------------------
# Adversarial / degraded LLM output
# ---------------------------------------------------------------------------


class TestAdversarialOutput:
    async def test_adversarial_draft_does_not_crash(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        """A non-routable adversarial action degrades to a plain decision."""
        llm.queue_response(ADVERSARIAL_RESPONSES["missing_mini_miranda"].model_copy(deep=True))

        result = await supervisor.step(clean_account)

        # "draft" matches no specialist; supervisor returns the decision as-is
        # instead of crashing.
        assert isinstance(result, AgentOutput)
        assert result.action == "draft"
        assert result.payload["mini_miranda_included"] is False

    async def test_unknown_and_empty_actions_degrade_gracefully(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        clean_account: dict,
    ):
        llm.queue_responses(
            [
                AgentOutput(
                    reasoning="Garbage action.",
                    action="   LAUNCH_MISSILES!!  ",
                    payload={},
                    next_steps=[],
                    token_estimate=1,
                ),
                AgentOutput(
                    reasoning="Empty action.",
                    action="",
                    payload={},
                    next_steps=[],
                    token_estimate=1,
                ),
            ]
        )

        first = await supervisor.step(clean_account)
        second = await supervisor.step(clean_account)

        assert isinstance(first, AgentOutput)
        assert isinstance(second, AgentOutput)
        # Neither routed anywhere nor mutated the plan.
        assert supervisor.memory.state.current_plan == []


# ---------------------------------------------------------------------------
# Verifier / compliance path
# ---------------------------------------------------------------------------


class TestVerifierPath:
    async def test_verifier_blocks_bankruptcy_account(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        clean_account["bankruptcy_flag"] = True
        llm.queue_response(
            AgentOutput(
                reasoning="Verify proposed SMS before sending.",
                action="verify",
                payload={"proposed_action": "send sms reminder"},
                next_steps=[],
                token_estimate=20,
            )
        )

        result = await supervisor.step(clean_account)

        # VerifierSpecialist surfaces bankruptcy_flag in its prompt and the
        # mock verifier blocks it.
        specialist_result = result.payload["specialist_result"]
        assert specialist_result["action"] == "block"
        assert specialist_result["payload"]["violation"] == "compliance_flag_active"

        # Supervisor logged a failed compliance note (passed=False → warning).
        notes = memory.session.compliance_notes
        assert notes
        assert notes[-1].rule == "fdcpa/tcpa"
        assert notes[-1].level == "warning"

    async def test_verifier_approves_clean_account(
        self,
        supervisor: QuannexSupervisor,
        llm: MockLLMWrapper,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        llm.queue_response(
            AgentOutput(
                reasoning="Verify proposed email before sending.",
                action="verify",
                payload={"proposed_action": "send payment reminder email"},
                next_steps=[],
                token_estimate=20,
            )
        )

        result = await supervisor.step(clean_account)

        specialist_result = result.payload["specialist_result"]
        assert specialist_result["action"] == "approve"

        notes = memory.session.compliance_notes
        assert notes
        assert notes[-1].level == "info"  # passed=True


# ---------------------------------------------------------------------------
# Memory compression path
# ---------------------------------------------------------------------------


class TestCompressionPath:
    async def test_step_triggers_compression_when_budget_high(
        self, tmp_path: Path, clean_account: dict
    ):
        memory = AgentSessionMemory(
            persistence=QuannexMemoryManager(
                tmp_path / "small_memory.json", token_budget=200
            ),
            session_id="default",
        )
        # Stuff memory well past 85% of the 200-token budget.
        for i in range(40):
            memory.add_observation(
                source="test",
                content=f"Observation {i}: " + "padding " * 15,
            )
        assert memory.budget_pct() > 0.85

        supervisor = QuannexSupervisor(llm=MockLLMWrapper(), memory=memory)
        result = await supervisor.step(clean_account)

        assert isinstance(result, AgentOutput)
        assert memory.session.last_compression_at is not None
        contents = [o.content for o in memory.session.recent_observations]
        assert any("Auto-compressed memory" in c for c in contents)

    async def test_step_below_budget_does_not_compress(
        self,
        supervisor: QuannexSupervisor,
        memory: AgentSessionMemory,
        clean_account: dict,
    ):
        await supervisor.step(clean_account)
        assert memory.session.last_compression_at is None
