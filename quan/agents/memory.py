# quan/agents/memory.py
"""
QuannexAgentState + QuannexMemoryManager

Structured Pydantic v2 state for the hierarchical agent system.
Auto-compresses observations at 70% of token budget using summarization.
Persists to filesystem (quan_agent_memory.json) for crash recovery.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from quan.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Token estimation helper
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Fast approximate token count (~4 chars per token for English)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Pydantic v2 state models
# ---------------------------------------------------------------------------

class MLScoreCache(BaseModel):
    """Cached ML scoring results to avoid redundant inference calls."""

    account_id: str = ""
    recovery_probability: float = 0.0
    settlement_threshold: float = 0.0
    optimal_channels: list[str] = Field(default_factory=list)
    segment_id: int | None = None
    confidence: float = 0.0
    scored_at: str = ""  # ISO timestamp


class ComplianceNote(BaseModel):
    """Immutable compliance record for audit trail."""

    timestamp: str  # ISO
    rule: str  # e.g. "fdcpa", "tcpa", "reg_f"
    check: str  # what was checked
    passed: bool
    detail: str = ""


class Observation(BaseModel):
    """A single agent observation / reasoning step."""

    timestamp: str
    source: str  # "supervisor", "planner", "outreach", "verifier", etc.
    content: str
    token_cost: int = 0


class QuannexAgentState(BaseModel):
    """
    Central state shared across the agent hierarchy.

    Design goals:
    - Keep token footprint predictable via bounded lists + summary.
    - All fields JSON-serializable for filesystem persistence.
    - Immutable compliance_notes (append-only in practice).
    """

    # --- Identity ---
    session_id: str = ""
    account_id: str = ""

    # --- Rolling summary (compressed from old observations) ---
    summary: str = ""

    # --- ML score cache (fast reflex layer) ---
    ml_cache: MLScoreCache = Field(default_factory=MLScoreCache)

    # --- Recent observations (bounded; oldest get summarized) ---
    observations: list[Observation] = Field(default_factory=list)

    # --- Compliance audit trail (append-only) ---
    compliance_notes: list[ComplianceNote] = Field(default_factory=list)

    # --- Current plan / next steps ---
    current_plan: list[str] = Field(default_factory=list)

    # --- Counters ---
    step_count: int = 0
    total_tokens_used: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = ""

    # --- Metadata bucket for specialist scratch data ---
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Memory manager
# ---------------------------------------------------------------------------

# Default budget: 120 000 tokens (~480K chars).  70% threshold = 84 000.
DEFAULT_TOKEN_BUDGET = 120_000
COMPRESS_THRESHOLD = 0.70  # trigger compression at 70% of budget


class QuannexMemoryManager:
    """
    Manages QuannexAgentState lifecycle:
    - append observations
    - auto-compress when nearing token budget
    - persist / restore from disk
    - provide XML-tagged context for LLM prompts
    """

    def __init__(
        self,
        state: QuannexAgentState | None = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        persist_path: str | Path = "quan_agent_memory.json",
    ):
        self.state = state or QuannexAgentState()
        self.token_budget = token_budget
        self.compress_at = int(token_budget * COMPRESS_THRESHOLD)
        self.persist_path = Path(persist_path)

    # ----- token accounting ------------------------------------------------

    def current_token_usage(self) -> int:
        """Estimate current token usage of the full state."""
        return estimate_tokens(self.state.model_dump_json())

    def budget_pct(self) -> float:
        """Return % of token budget consumed."""
        return self.current_token_usage() / self.token_budget

    # ----- mutation helpers ------------------------------------------------

    def add_observation(
        self,
        source: str,
        content: str,
    ) -> None:
        """Append an observation, then compress if needed."""
        ts = datetime.now(timezone.utc).isoformat()
        tok = estimate_tokens(content)
        obs = Observation(
            timestamp=ts,
            source=source,
            content=content,
            token_cost=tok,
        )
        self.state.observations.append(obs)
        self.state.total_tokens_used += tok
        self.state.updated_at = ts

        # Auto-compress if past threshold
        if self.current_token_usage() >= self.compress_at:
            self.compress()

    def add_compliance_note(
        self,
        rule: str,
        check: str,
        passed: bool,
        detail: str = "",
    ) -> None:
        """Append an immutable compliance note."""
        self.state.compliance_notes.append(
            ComplianceNote(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rule=rule,
                check=check,
                passed=passed,
                detail=detail,
            )
        )

    def update_ml_cache(
        self,
        account_id: str,
        recovery_probability: float,
        settlement_threshold: float,
        optimal_channels: list[str],
        confidence: float,
        segment_id: int | None = None,
    ) -> None:
        """Refresh the ML score cache from CollectionIntelligence."""
        self.state.ml_cache = MLScoreCache(
            account_id=account_id,
            recovery_probability=recovery_probability,
            settlement_threshold=settlement_threshold,
            optimal_channels=optimal_channels,
            confidence=confidence,
            segment_id=segment_id,
            scored_at=datetime.now(timezone.utc).isoformat(),
        )

    # ----- compression -----------------------------------------------------

    def compress(self, keep_recent: int = 5) -> None:
        """
        Summarize old observations into self.state.summary.

        Keeps the most recent `keep_recent` observations intact and folds
        everything older into a running summary.  This is a *local*
        compression (no LLM call) — fast and deterministic.  For deeper
        compression using an LLM, call compress_with_llm() instead.
        """
        obs = self.state.observations
        if len(obs) <= keep_recent:
            return

        to_fold = obs[:-keep_recent]
        kept = obs[-keep_recent:]

        # Build bullet summary of folded observations
        bullets = []
        for o in to_fold:
            # Truncate long content to first 200 chars
            short = o.content[:200].replace("\n", " ")
            bullets.append(f"- [{o.source}] {short}")
        folded_text = "\n".join(bullets)

        prior = self.state.summary
        self.state.summary = (
            f"{prior}\n\n[Compressed {len(to_fold)} observations at "
            f"{datetime.now(timezone.utc).isoformat()}]\n{folded_text}"
        ).strip()

        self.state.observations = kept

        logger.info(
            "Memory compressed",
            extra={
                "folded": len(to_fold),
                "kept": len(kept),
                "budget_pct": f"{self.budget_pct():.1%}",
            },
        )

    async def compress_with_llm(
        self,
        llm_callable,
        keep_recent: int = 5,
    ) -> None:
        """
        Use an LLM to produce a high-quality summary of old observations.

        `llm_callable` should be an async function accepting a prompt (str)
        and returning a summary (str).
        """
        obs = self.state.observations
        if len(obs) <= keep_recent:
            return

        to_fold = obs[:-keep_recent]
        kept = obs[-keep_recent:]

        fold_text = "\n".join(
            f"[{o.source} @ {o.timestamp}] {o.content}" for o in to_fold
        )
        prompt = (
            "Summarize the following agent observations into a concise "
            "paragraph.  Preserve key facts, decisions, compliance notes, "
            "and numeric results.  Drop conversational filler.\n\n"
            f"{fold_text}"
        )
        summary = await llm_callable(prompt)

        prior = self.state.summary
        self.state.summary = f"{prior}\n\n{summary}".strip()
        self.state.observations = kept

    # ----- context rendering -----------------------------------------------

    def render_context(self, max_chars: int | None = None) -> str:
        """
        Render the state as XML-tagged sections for an LLM prompt.

        XML tags let the model selectively attend to relevant sections and
        keep the prompt well-structured without wasting tokens on markdown.
        """
        parts: list[str] = []

        # Summary
        if self.state.summary:
            parts.append(
                f"<summary>\n{self.state.summary}\n</summary>"
            )

        # ML cache
        mc = self.state.ml_cache
        if mc.account_id:
            parts.append(
                "<ml_scores>\n"
                f"account_id={mc.account_id} "
                f"recovery_prob={mc.recovery_probability:.3f} "
                f"settlement_thresh={mc.settlement_threshold:.2f} "
                f"channels={','.join(mc.optimal_channels)} "
                f"confidence={mc.confidence:.3f} "
                f"scored_at={mc.scored_at}\n"
                "</ml_scores>"
            )

        # Recent observations
        if self.state.observations:
            obs_lines = "\n".join(
                f"[{o.source} @ {o.timestamp}] {o.content}"
                for o in self.state.observations
            )
            parts.append(
                f"<observations>\n{obs_lines}\n</observations>"
            )

        # Compliance notes (last 10)
        if self.state.compliance_notes:
            recent = self.state.compliance_notes[-10:]
            cn_lines = "\n".join(
                f"[{n.rule}] {n.check}: {'PASS' if n.passed else 'FAIL'} {n.detail}"
                for n in recent
            )
            parts.append(
                f"<compliance>\n{cn_lines}\n</compliance>"
            )

        # Plan
        if self.state.current_plan:
            plan_text = "\n".join(
                f"{i+1}. {s}" for i, s in enumerate(self.state.current_plan)
            )
            parts.append(f"<plan>\n{plan_text}\n</plan>")

        context = "\n\n".join(parts)

        if max_chars and len(context) > max_chars:
            context = context[:max_chars] + "\n[...truncated]"

        return context

    # ----- persistence -----------------------------------------------------

    def save(self) -> None:
        """Persist state to disk as JSON."""
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        self.persist_path.write_text(
            self.state.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.debug("State persisted", extra={"path": str(self.persist_path)})

    def load(self) -> bool:
        """Load state from disk.  Returns True if file existed."""
        if not self.persist_path.exists():
            return False
        try:
            raw = self.persist_path.read_text(encoding="utf-8")
            self.state = QuannexAgentState.model_validate_json(raw)
            logger.info(
                "State restored from disk",
                extra={
                    "session_id": self.state.session_id,
                    "steps": self.state.step_count,
                },
            )
            return True
        except Exception as exc:
            logger.warning(f"Failed to restore state: {exc}")
            return False
