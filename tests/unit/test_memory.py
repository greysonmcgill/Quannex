# tests/unit/test_memory.py
"""
QuannexMemoryManager unit tests.

Covers default-state creation, JSON round-trip persistence (including
datetime serialization), observation/compliance/ML-cache mutation helpers,
token estimation, proactive compression, XML rendering, and isolation
between sessions stored in the same envelope file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from quan.agents.memory import (
    QuannexAgentState,
    QuannexMemoryManager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_path(tmp_path: Path) -> Path:
    """Path for the on-disk memory envelope (file does not exist yet)."""
    return tmp_path / "agent_memory.json"


@pytest.fixture
def manager(memory_path: Path) -> QuannexMemoryManager:
    """Memory manager backed by a temp file with default settings."""
    return QuannexMemoryManager(memory_path)


@pytest.fixture
def small_manager(memory_path: Path) -> QuannexMemoryManager:
    """Manager with a tiny budget so compression triggers easily."""
    return QuannexMemoryManager(
        memory_path,
        token_budget=100,
        compression_threshold=0.70,
        keep_recent_observations=4,
        keep_recent_actions=3,
        keep_recent_compliance_notes=2,
    )


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------


class TestLoadAndSave:
    def test_load_state_creates_default_when_file_missing(
        self, manager: QuannexMemoryManager, memory_path: Path
    ):
        """Missing file should yield a fresh default state and create the file."""
        assert not memory_path.exists()

        state = manager.load_state("session-a")

        assert isinstance(state, QuannexAgentState)
        assert state.session_id == "session-a"
        assert state.summary == "No prior summary."
        assert state.recent_observations == []
        assert state.ml_cache == {}
        assert state.compliance_notes == []
        assert state.action_history == []
        assert memory_path.exists()

    def test_load_state_inherits_manager_budget_settings(self, memory_path: Path):
        """New states should pick up the manager's budget configuration."""
        manager = QuannexMemoryManager(
            memory_path, token_budget=5000, compression_threshold=0.5
        )
        state = manager.load_state()

        assert state.token_budget == 5000
        assert state.compression_threshold == 0.5

    def test_save_and_reload_roundtrips_observations(
        self, manager: QuannexMemoryManager, memory_path: Path
    ):
        """Observations (incl. datetimes) must survive a save/reload cycle."""
        state = manager.load_state("rt")
        manager.add_observation(
            state,
            source="supervisor",
            content="ML scored account ACC-1",
            kind="score",
            metadata={"account_id": "ACC-1"},
        )
        manager.save_state(state)

        # Fresh manager instance simulates process restart.
        reloaded = QuannexMemoryManager(memory_path).load_state("rt")

        assert len(reloaded.recent_observations) == 1
        obs = reloaded.recent_observations[0]
        assert obs.source == "supervisor"
        assert obs.kind == "score"
        assert obs.content == "ML scored account ACC-1"
        assert obs.metadata == {"account_id": "ACC-1"}
        # Datetime must come back as a timezone-aware datetime, not a string.
        assert isinstance(obs.timestamp, datetime)
        assert obs.timestamp.tzinfo is not None

    def test_save_and_reload_roundtrips_ml_cache(
        self, manager: QuannexMemoryManager, memory_path: Path
    ):
        state = manager.load_state("rt-ml")
        manager.cache_ml_score(
            state,
            account_id="ACC-9",
            recovery_probability=0.42,
            optimal_channels=["sms", "email"],
            settlement_threshold=0.65,
            confidence=0.8,
            raw={"segment_id": 3},
        )
        manager.save_state(state)

        reloaded = QuannexMemoryManager(memory_path).load_state("rt-ml")

        assert "ACC-9" in reloaded.ml_cache
        entry = reloaded.ml_cache["ACC-9"]
        assert entry.recovery_probability == pytest.approx(0.42)
        assert entry.optimal_channels == ["sms", "email"]
        assert entry.settlement_threshold == pytest.approx(0.65)
        assert entry.confidence == pytest.approx(0.8)
        assert entry.raw == {"segment_id": 3}
        assert isinstance(entry.scored_at, datetime)

    def test_save_and_reload_roundtrips_compliance_notes(
        self, manager: QuannexMemoryManager, memory_path: Path
    ):
        state = manager.load_state("rt-cn")
        manager.add_compliance_note(
            state,
            level="warning",
            rule="fdcpa",
            note="Missing Mini-Miranda in draft.",
            account_id="ACC-2",
        )
        manager.save_state(state)

        reloaded = QuannexMemoryManager(memory_path).load_state("rt-cn")

        assert len(reloaded.compliance_notes) == 1
        note = reloaded.compliance_notes[0]
        assert note.level == "warning"
        assert note.rule == "fdcpa"
        assert note.account_id == "ACC-2"
        assert isinstance(note.timestamp, datetime)


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------


class TestMutationHelpers:
    def test_add_observation_appends_in_order(self, manager: QuannexMemoryManager):
        state = manager.load_state()
        manager.add_observation(state, source="a", content="first")
        manager.add_observation(state, source="b", content="  second  ")

        assert [o.content for o in state.recent_observations] == ["first", "second"]
        assert [o.source for o in state.recent_observations] == ["a", "b"]

    def test_observation_cap_enforced_via_compression(
        self, small_manager: QuannexMemoryManager
    ):
        """Once over budget, save_state trims to keep_recent_observations."""
        state = small_manager.load_state()
        for i in range(30):
            small_manager.add_observation(
                state,
                source="supervisor",
                content=f"Observation {i}: " + "details " * 10,
            )
        small_manager.save_state(state)

        assert len(state.recent_observations) == 4  # keep_recent_observations
        # Most recent observations are the ones retained.
        assert state.recent_observations[-1].content.startswith("Observation 29")

    def test_add_compliance_note_persists_fields(self, manager: QuannexMemoryManager):
        state = manager.load_state()
        manager.add_compliance_note(
            state,
            level="block",
            rule="bankruptcy",
            note="Automatic stay active.",
            account_id="ACC-3",
        )

        note = state.compliance_notes[-1]
        assert note.level == "block"
        assert note.rule == "bankruptcy"
        assert note.account_id == "ACC-3"
        assert note.note == "Automatic stay active."

    def test_add_compliance_note_rejects_invalid_level(
        self, manager: QuannexMemoryManager
    ):
        state = manager.load_state()
        with pytest.raises(Exception):
            manager.add_compliance_note(
                state, level="catastrophic", rule="fdcpa", note="bad level"
            )

    def test_cache_ml_score_stores_per_account(self, manager: QuannexMemoryManager):
        state = manager.load_state()
        manager.cache_ml_score(
            state,
            account_id="A1",
            recovery_probability=0.3,
            optimal_channels=["sms"],
            settlement_threshold=0.7,
        )
        manager.cache_ml_score(
            state,
            account_id="A2",
            recovery_probability=0.6,
            optimal_channels=["email"],
            settlement_threshold=0.5,
        )

        assert set(state.ml_cache) == {"A1", "A2"}
        assert state.ml_cache["A1"].recovery_probability == pytest.approx(0.3)
        assert state.ml_cache["A2"].recovery_probability == pytest.approx(0.6)

    def test_cache_ml_score_overwrites_existing_account(
        self, manager: QuannexMemoryManager
    ):
        state = manager.load_state()
        manager.cache_ml_score(
            state,
            account_id="A1",
            recovery_probability=0.3,
            optimal_channels=["sms"],
            settlement_threshold=0.7,
        )
        manager.cache_ml_score(
            state,
            account_id="A1",
            recovery_probability=0.9,
            optimal_channels=["voice"],
            settlement_threshold=0.4,
        )

        assert len(state.ml_cache) == 1
        entry = state.ml_cache["A1"]
        assert entry.recovery_probability == pytest.approx(0.9)
        assert entry.optimal_channels == ["voice"]
        assert entry.settlement_threshold == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Token estimation + compression
# ---------------------------------------------------------------------------


class TestTokenEstimationAndCompression:
    def test_estimate_tokens_returns_positive_int(self, manager: QuannexMemoryManager):
        state = manager.load_state()
        tokens = manager.estimate_tokens(state)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_tokens_grows_with_content(self, manager: QuannexMemoryManager):
        state = manager.load_state()
        before = manager.estimate_tokens(state)
        for i in range(10):
            manager.add_observation(
                state, source="test", content=f"Observation {i}: " + "x" * 200
            )
        after = manager.estimate_tokens(state)
        assert after > before

    def test_compress_if_needed_noop_below_threshold(
        self, manager: QuannexMemoryManager
    ):
        state = manager.load_state()
        manager.add_observation(state, source="test", content="tiny")
        result = manager.compress_if_needed(state)

        assert result.last_compression_at is None
        assert len(result.recent_observations) == 1

    def test_compress_triggers_above_threshold_and_trims(
        self, small_manager: QuannexMemoryManager
    ):
        state = small_manager.load_state()
        for i in range(25):
            small_manager.add_observation(
                state, source="test", content=f"Observation {i}: " + "fact " * 20
            )
            small_manager.add_action_audit(
                state,
                action="plan",
                status="executed",
                reason=f"Executed plan step {i}",
            )

        assert small_manager.estimate_tokens(state) > int(
            state.token_budget * state.compression_threshold
        )

        result = small_manager.compress_if_needed(state)

        assert result.last_compression_at is not None
        assert len(result.recent_observations) == 4  # keep_recent_observations
        assert len(result.action_history) == 3  # keep_recent_actions
        # Older content is folded into the rolling summary.
        assert "Prior observations" in result.summary
        assert "Prior actions" in result.summary


# ---------------------------------------------------------------------------
# XML rendering
# ---------------------------------------------------------------------------


class TestRenderMemoryXml:
    def test_render_memory_xml_contains_key_sections(
        self, manager: QuannexMemoryManager
    ):
        state = manager.load_state()
        manager.add_observation(state, source="supervisor", content="scored ACC-1")
        manager.add_compliance_note(
            state, level="info", rule="fdcpa", note="Contact hours OK."
        )
        manager.cache_ml_score(
            state,
            account_id="ACC-1",
            recovery_probability=0.5,
            optimal_channels=["sms"],
            settlement_threshold=0.6,
        )

        xml = manager.render_memory_xml(state)

        assert isinstance(xml, str)
        assert xml.startswith("<memory>")
        assert xml.endswith("</memory>")
        for section in (
            "<summary>",
            "<recent_observations>",
            "<compliance_notes>",
            "<ml_cache>",
        ):
            assert section in xml
        assert "scored ACC-1" in xml
        assert 'account_id="ACC-1"' in xml

    def test_render_memory_xml_escapes_special_characters(
        self, manager: QuannexMemoryManager
    ):
        state = manager.load_state()
        manager.add_observation(
            state, source="test", content="balance < $100 & debtor said \"no\""
        )
        xml = manager.render_memory_xml(state)

        assert "&lt;" in xml
        assert "&amp;" in xml
        assert "< $100 &" not in xml


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------


class TestSessionIsolation:
    def test_sessions_do_not_leak_state(
        self, manager: QuannexMemoryManager, memory_path: Path
    ):
        state_a = manager.load_state("session-a")
        manager.add_observation(state_a, source="a", content="only in A")
        manager.cache_ml_score(
            state_a,
            account_id="ACC-A",
            recovery_probability=0.1,
            optimal_channels=["sms"],
            settlement_threshold=0.9,
        )
        manager.save_state(state_a)

        state_b = manager.load_state("session-b")
        assert state_b.recent_observations == []
        assert state_b.ml_cache == {}

        manager.add_observation(state_b, source="b", content="only in B")
        manager.save_state(state_b)

        # Reload both from disk; each retains only its own data.
        fresh = QuannexMemoryManager(memory_path)
        reloaded_a = fresh.load_state("session-a")
        reloaded_b = fresh.load_state("session-b")

        assert [o.content for o in reloaded_a.recent_observations] == ["only in A"]
        assert [o.content for o in reloaded_b.recent_observations] == ["only in B"]
        assert "ACC-A" in reloaded_a.ml_cache
        assert reloaded_b.ml_cache == {}
        assert reloaded_a.session_id == "session-a"
        assert reloaded_b.session_id == "session-b"
