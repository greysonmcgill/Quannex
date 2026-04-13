"""Structured memory for the lightweight Quannex hierarchical agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from quan.logging_config import get_logger

logger = get_logger(__name__)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class QuannexObservation(BaseModel):
    """A compact fact captured during agent execution."""

    timestamp: datetime = Field(default_factory=utc_now)
    source: str
    kind: str = "note"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuannexComplianceNote(BaseModel):
    """Compliance finding or reminder retained in memory."""

    timestamp: datetime = Field(default_factory=utc_now)
    level: str = Field(default="info", pattern="^(info|warning|block)$")
    rule: str
    note: str
    account_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuannexMLCacheEntry(BaseModel):
    """Cached ML reflex score for an account."""

    account_id: str
    recovery_probability: float
    optimal_channels: list[str] = Field(default_factory=list)
    settlement_threshold: float = 1.0
    confidence: float = 0.0
    scored_at: datetime = Field(default_factory=utc_now)
    raw: dict[str, Any] = Field(default_factory=dict)


class QuannexActionAudit(BaseModel):
    """Auditable record of a decision or executed action."""

    timestamp: datetime = Field(default_factory=utc_now)
    actor: str = "supervisor"
    action: str
    status: str = Field(default="planned", pattern="^(planned|executed|blocked|error)$")
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)


class QuannexAgentState(BaseModel):
    """Persisted long-context state for a Quannex agent session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = "default"
    summary: str = "No prior summary."
    recent_observations: list[QuannexObservation] = Field(default_factory=list)
    ml_cache: dict[str, QuannexMLCacheEntry] = Field(default_factory=dict)
    compliance_notes: list[QuannexComplianceNote] = Field(default_factory=list)
    action_history: list[QuannexActionAudit] = Field(default_factory=list)
    token_budget: int = 1_000_000
    compression_threshold: float = 0.70
    updated_at: datetime = Field(default_factory=utc_now)
    last_compression_at: datetime | None = None


class MemoryEnvelope(BaseModel):
    """On-disk container for all sessions."""

    version: int = 1
    sessions: dict[str, QuannexAgentState] = Field(default_factory=dict)


class QuannexMemoryManager:
    """Filesystem-backed memory manager with proactive compression."""

    def __init__(
        self,
        path: str | Path = "quan_agent_memory.json",
        *,
        token_budget: int = 1_000_000,
        compression_threshold: float = 0.70,
        keep_recent_observations: int = 8,
        keep_recent_actions: int = 8,
        keep_recent_compliance_notes: int = 8,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.token_budget = token_budget
        self.compression_threshold = compression_threshold
        self.keep_recent_observations = keep_recent_observations
        self.keep_recent_actions = keep_recent_actions
        self.keep_recent_compliance_notes = keep_recent_compliance_notes
        self._lock = RLock()

    def load_state(self, session_id: str = "default") -> QuannexAgentState:
        """Load a persisted session or return a default state."""

        with self._lock:
            envelope = self._read_envelope()
            if session_id in envelope.sessions:
                state = envelope.sessions[session_id]
            else:
                state = QuannexAgentState(
                    session_id=session_id,
                    token_budget=self.token_budget,
                    compression_threshold=self.compression_threshold,
                )
                envelope.sessions[session_id] = state
                self._write_envelope(envelope)
            return state

    def save_state(self, state: QuannexAgentState) -> None:
        """Persist a session after compression."""

        with self._lock:
            state.updated_at = utc_now()
            state = self.compress_if_needed(state)
            envelope = self._read_envelope()
            envelope.sessions[state.session_id] = state
            self._write_envelope(envelope)

    def add_observation(
        self,
        state: QuannexAgentState,
        *,
        source: str,
        content: str,
        kind: str = "note",
        metadata: dict[str, Any] | None = None,
    ) -> QuannexAgentState:
        """Append a new observation to state."""

        state.recent_observations.append(
            QuannexObservation(
                source=source,
                kind=kind,
                content=content.strip(),
                metadata=metadata or {},
            )
        )
        state.updated_at = utc_now()
        return state

    def add_compliance_note(
        self,
        state: QuannexAgentState,
        *,
        level: str,
        rule: str,
        note: str,
        account_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> QuannexAgentState:
        """Append a compliance note to memory."""

        state.compliance_notes.append(
            QuannexComplianceNote(
                level=level,
                rule=rule,
                note=note.strip(),
                account_id=account_id,
                metadata=metadata or {},
            )
        )
        state.updated_at = utc_now()
        return state

    def cache_ml_score(
        self,
        state: QuannexAgentState,
        *,
        account_id: str,
        recovery_probability: float,
        optimal_channels: list[str],
        settlement_threshold: float,
        confidence: float = 0.0,
        raw: dict[str, Any] | None = None,
    ) -> QuannexAgentState:
        """Store the latest ML reflex score for an account."""

        state.ml_cache[account_id] = QuannexMLCacheEntry(
            account_id=account_id,
            recovery_probability=recovery_probability,
            optimal_channels=optimal_channels,
            settlement_threshold=settlement_threshold,
            confidence=confidence,
            raw=raw or {},
        )
        state.updated_at = utc_now()
        return state

    def add_action_audit(
        self,
        state: QuannexAgentState,
        *,
        action: str,
        status: str,
        reason: str,
        payload: dict[str, Any] | None = None,
        actor: str = "supervisor",
    ) -> QuannexAgentState:
        """Append an auditable action record."""

        state.action_history.append(
            QuannexActionAudit(
                actor=actor,
                action=action,
                status=status,
                reason=reason.strip(),
                payload=payload or {},
            )
        )
        state.updated_at = utc_now()
        return state

    def estimate_tokens(self, state: QuannexAgentState) -> int:
        """Estimate memory footprint in tokens using a compact heuristic."""

        compact = {
            "summary": state.summary,
            "observations": [
                f"{item.timestamp.isoformat()}|{item.source}|{item.kind}|{item.content}"
                for item in state.recent_observations
            ],
            "compliance": [
                f"{item.timestamp.isoformat()}|{item.level}|{item.rule}|{item.note}"
                for item in state.compliance_notes
            ],
            "actions": [
                f"{item.timestamp.isoformat()}|{item.action}|{item.status}|{item.reason}"
                for item in state.action_history
            ],
            "ml_cache": {
                key: {
                    "recovery_probability": value.recovery_probability,
                    "optimal_channels": value.optimal_channels,
                    "settlement_threshold": value.settlement_threshold,
                }
                for key, value in state.ml_cache.items()
            },
        }
        serialized = json.dumps(compact, separators=(",", ":"), default=str)
        return max(1, len(serialized) // 4)

    def compress_if_needed(self, state: QuannexAgentState) -> QuannexAgentState:
        """Summarize older memory once the session exceeds the threshold."""

        estimated_tokens = self.estimate_tokens(state)
        threshold = int(state.token_budget * state.compression_threshold)
        if estimated_tokens <= threshold:
            return state

        older_observations = state.recent_observations[:-self.keep_recent_observations]
        older_actions = state.action_history[:-self.keep_recent_actions]
        older_notes = state.compliance_notes[:-self.keep_recent_compliance_notes]

        summary_sections = [
            state.summary.strip(),
            self._summarize_observations(older_observations),
            self._summarize_actions(older_actions),
            self._summarize_compliance(older_notes),
        ]
        state.summary = " ".join(section for section in summary_sections if section).strip()
        state.summary = self._trim_text(state.summary, max_chars=8_000)
        state.recent_observations = state.recent_observations[-self.keep_recent_observations :]
        state.action_history = state.action_history[-self.keep_recent_actions :]
        state.compliance_notes = state.compliance_notes[-self.keep_recent_compliance_notes :]
        state.last_compression_at = utc_now()

        logger.info(
            "Compressed agent memory",
            extra={
                "session_id": state.session_id,
                "token_estimate_before": estimated_tokens,
                "token_budget": state.token_budget,
            },
        )
        return state

    def render_memory_xml(self, state: QuannexAgentState) -> str:
        """Render compact XML-tagged memory for the supervisor prompt."""

        observations = "\n".join(
            self._observation_to_xml(item) for item in state.recent_observations[-6:]
        ) or "<none />"
        compliance = "\n".join(
            self._compliance_to_xml(item) for item in state.compliance_notes[-5:]
        ) or "<none />"
        ml_cache = "\n".join(
            (
                f'<score account_id="{item.account_id}" '
                f'recovery_probability="{item.recovery_probability:.4f}" '
                f'settlement_threshold="{item.settlement_threshold:.4f}" '
                f'channels="{",".join(item.optimal_channels)}" />'
            )
            for item in list(state.ml_cache.values())[-5:]
        ) or "<none />"
        return (
            "<memory>\n"
            f"<summary>{self._escape_xml(state.summary)}</summary>\n"
            f"<recent_observations>\n{observations}\n</recent_observations>\n"
            f"<compliance_notes>\n{compliance}\n</compliance_notes>\n"
            f"<ml_cache>\n{ml_cache}\n</ml_cache>\n"
            "</memory>"
        )

    def _read_envelope(self) -> MemoryEnvelope:
        if not self.path.exists():
            return MemoryEnvelope()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return MemoryEnvelope.model_validate(data)
        except Exception as exc:
            logger.warning("Failed to read agent memory, starting fresh: %s", exc)
            return MemoryEnvelope()

    def _write_envelope(self, envelope: MemoryEnvelope) -> None:
        self.path.write_text(
            envelope.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _summarize_observations(self, items: Iterable[QuannexObservation]) -> str:
        values = list(items)
        if not values:
            return ""
        lines = [f"{item.source}:{item.kind}:{self._trim_text(item.content, 100)}" for item in values[-12:]]
        return f"Prior observations: {' | '.join(lines)}."

    def _summarize_actions(self, items: Iterable[QuannexActionAudit]) -> str:
        values = list(items)
        if not values:
            return ""
        lines = [f"{item.action}/{item.status}:{self._trim_text(item.reason, 100)}" for item in values[-12:]]
        return f"Prior actions: {' | '.join(lines)}."

    def _summarize_compliance(self, items: Iterable[QuannexComplianceNote]) -> str:
        values = list(items)
        if not values:
            return ""
        lines = [f"{item.level}:{item.rule}:{self._trim_text(item.note, 100)}" for item in values[-10:]]
        return f"Compliance history: {' | '.join(lines)}."

    def _observation_to_xml(self, item: QuannexObservation) -> str:
        return (
            f'<observation source="{self._escape_xml(item.source)}" '
            f'kind="{self._escape_xml(item.kind)}" '
            f'timestamp="{item.timestamp.isoformat()}">'
            f"{self._escape_xml(self._trim_text(item.content, 300))}"
            "</observation>"
        )

    def _compliance_to_xml(self, item: QuannexComplianceNote) -> str:
        account_id = item.account_id or ""
        return (
            f'<note level="{self._escape_xml(item.level)}" '
            f'rule="{self._escape_xml(item.rule)}" '
            f'account_id="{self._escape_xml(account_id)}" '
            f'timestamp="{item.timestamp.isoformat()}">'
            f"{self._escape_xml(self._trim_text(item.note, 240))}"
            "</note>"
        )

    def _trim_text(self, value: str, max_chars: int) -> str:
        text = value.strip()
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3].rstrip()}..."

    def _escape_xml(self, value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
