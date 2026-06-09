# quan/agents/supervisor.py
"""
QuannexSupervisor — hierarchical agent orchestrator.

Architecture:
    Supervisor.step(account_data, goal)
        1. Fast reflex: call CollectionIntelligence (ML scoring) — ~0 LLM tokens
        2. Build XML-tagged context from AgentSessionMemory
        3. LLM call → AgentOutput (structured JSON)
        4. Route action to specialist (outreach, verify, simulate, etc.)
        5. Log compliance, persist state, return result

The supervisor never generates outreach text itself; it delegates to
specialists, keeping each agent focused and auditable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from quan.agents.llm_wrapper import AgentOutput, LLMWrapper
from quan.agents.memory import AgentSessionMemory
from quan.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Specialist protocol
# ---------------------------------------------------------------------------

class BaseSpecialist:
    """
    Interface every specialist must implement.

    Specialists receive the full memory manager (read-only access
    recommended) and an action payload, then return an AgentOutput.
    """

    name: str = "base"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Built-in lightweight specialists
# ---------------------------------------------------------------------------

class PlannerSpecialist(BaseSpecialist):
    """Creates a multi-step collection plan based on ML scores + context."""

    name = "planner"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        context = memory.render_context(max_chars=8000)
        system = (
            "You are the Planner specialist in a fintech debt-collection "
            "agent system. Given the current state, produce a numbered "
            "collection plan (3-7 steps). Each step should name the "
            "responsible specialist and expected outcome. Stay FDCPA/TCPA "
            "compliant. Be concise."
        )
        user_msg = (
            f"<context>\n{context}\n</context>\n\n"
            f"<goal>{payload.get('goal', 'maximize recovery')}</goal>\n\n"
            "Produce your plan."
        )
        return await llm.call(system=system, user_message=user_msg)


class VerifierSpecialist(BaseSpecialist):
    """Checks a proposed action for FDCPA / TCPA / Reg F compliance."""

    name = "verifier"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        proposed = payload.get("proposed_action", "")
        account = payload.get("account", {})

        # Build compliance context
        compliance_flags = []
        for flag in (
            "do_not_call", "do_not_email", "do_not_mail",
            "bankruptcy_flag", "deceased_flag", "disputed",
            "attorney_represented", "statute_of_limitations_expired",
        ):
            if account.get(flag):
                compliance_flags.append(flag)

        context = memory.render_context(max_chars=4000)
        system = (
            "You are the Compliance Verifier in a fintech debt-collection "
            "agent system.  Evaluate the proposed action for FDCPA, TCPA, "
            "and Reg F compliance.  If it passes, action='approve'. If it "
            "fails, action='block' with reasoning explaining the violation."
        )
        user_msg = (
            f"<context>\n{context}\n</context>\n\n"
            f"<proposed_action>{proposed}</proposed_action>\n"
            f"<compliance_flags>{', '.join(compliance_flags) or 'none'}</compliance_flags>\n"
            f"<account_state>{account.get('state', 'unknown')}</account_state>\n"
            f"<contact_attempts>{account.get('contact_attempts', 0)}</contact_attempts>\n\n"
            "Evaluate compliance."
        )
        return await llm.call(system=system, user_message=user_msg)


class SimulatorSpecialist(BaseSpecialist):
    """
    Runs a lightweight what-if simulation using the ML engine.

    For heavier simulations, this could shell out to scripts like
    run_bnpl_1m_simulation.py via subprocess — but we keep it in-process
    for the common case to avoid token waste.
    """

    name = "simulator"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        context = memory.render_context(max_chars=4000)
        system = (
            "You are the Simulator/Optimizer in a fintech agent system. "
            "Given ML scores and account context, evaluate settlement "
            "scenarios and channel sequencing options.  Return the "
            "recommended scenario as action='recommend' with payload "
            "containing settlement_pct, channel_sequence, and "
            "expected_recovery."
        )
        user_msg = (
            f"<context>\n{context}\n</context>\n\n"
            f"<scenario>{payload.get('scenario', 'default')}</scenario>\n\n"
            "Run simulation and recommend."
        )
        return await llm.call(system=system, user_message=user_msg)


class MemoryManagerSpecialist(BaseSpecialist):
    """Triggers LLM-powered deep compression of agent memory."""

    name = "memory_manager"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        before_pct = memory.budget_pct()
        await memory.compress_with_llm(
            llm_callable=lambda prompt: llm.call_raw(
                system="Summarize concisely, preserving key facts and numbers.",
                user_message=prompt,
            ),
            keep_recent=payload.get("keep_recent", 5),
        )
        after_pct = memory.budget_pct()
        memory.save()

        return AgentOutput(
            reasoning=(
                f"Compressed memory from {before_pct:.1%} to {after_pct:.1%} "
                "of token budget."
            ),
            action="complete",
            payload={"before_pct": before_pct, "after_pct": after_pct},
            next_steps=["continue_plan"],
            token_estimate=200,
        )


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

SUPERVISOR_SYSTEM = """\
You are the Quannex Supervisor — the top-level orchestrator of a hierarchical \
AI debt-collection system.  You coordinate specialists to maximize recovery \
while maintaining strict FDCPA/TCPA/Reg F compliance.

Available specialists you can delegate to (via the "action" field):
- "plan"       → Planner: create/revise multi-step collection plan
- "outreach"   → Outreach: generate personalized, compliant debtor messages
- "verify"     → Verifier: compliance-check a proposed action before execution
- "simulate"   → Simulator: run what-if scenarios for settlement/channel mix
- "compress"   → MemoryManager: compress agent memory to reclaim token budget
- "score"      → (handled locally) re-run ML scoring via CollectionIntelligence
- "complete"   → signal that the current goal is achieved
- "escalate"   → flag for human review

Decision framework:
1. If ML scores are stale (>5 min or missing), action="score".
2. If no plan exists, action="plan".
3. Before any outreach, action="verify" first.
4. If token budget >85%, action="compress".
5. Otherwise, advance the plan by delegating to the next specialist.

Be concise.  Respond ONLY with the required JSON."""


class QuannexSupervisor:
    """
    Main entry point for the hierarchical agent system.

    Integrates:
    - CollectionIntelligence (ML fast path)
    - LLMWrapper (reasoning layer)
    - AgentSessionMemory (working state, optional persistence)
    - Specialist agents (planner, outreach, verifier, simulator, memory)
    """

    def __init__(
        self,
        llm: LLMWrapper | None = None,
        memory: AgentSessionMemory | None = None,
        specialists: dict[str, BaseSpecialist] | None = None,
    ):
        self.llm = llm or LLMWrapper()
        self.memory = memory or AgentSessionMemory()
        self.specialists: dict[str, BaseSpecialist] = specialists or {
            "plan": PlannerSpecialist(),
            "verify": VerifierSpecialist(),
            "simulate": SimulatorSpecialist(),
            "compress": MemoryManagerSpecialist(),
        }

    def register_specialist(self, action: str, specialist: BaseSpecialist) -> None:
        """Register or replace a specialist for a given action key."""
        self.specialists[action] = specialist
        logger.info(f"Registered specialist: {action} → {specialist.name}")

    # ----- ML fast path ----------------------------------------------------

    def _run_ml_scoring(self, account: dict[str, Any]) -> dict[str, Any]:
        """
        Call CollectionIntelligence synchronously (fast, no LLM tokens).

        Returns the strategy dict and updates the ML cache in memory.
        """
        from quan.intelligence.engine import CollectionIntelligence

        engine = CollectionIntelligence()
        strategy = engine.generate_strategy(account)

        # Update memory cache
        self.memory.update_ml_cache(
            account_id=strategy.account_id,
            recovery_probability=strategy.recovery_probability,
            settlement_threshold=strategy.settlement_threshold,
            optimal_channels=strategy.optimal_channels,
            confidence=strategy.confidence,
            segment_id=strategy.segment_id,
        )

        return {
            "account_id": strategy.account_id,
            "recovery_probability": strategy.recovery_probability,
            "settlement_threshold": strategy.settlement_threshold,
            "optimal_channels": strategy.optimal_channels,
            "confidence": strategy.confidence,
            "contact_sequence": strategy.contact_sequence,
        }

    # ----- main step -------------------------------------------------------

    async def step(
        self,
        account: dict[str, Any],
        goal: str = "maximize recovery while maintaining compliance",
    ) -> AgentOutput:
        """
        Execute one supervisor reasoning step.

        This is the primary API.  Call it repeatedly to advance through
        the collection workflow for a single account.

        Returns:
            AgentOutput with the action taken and any specialist results
            nested in payload["specialist_result"].
        """
        state = self.memory.state
        state.step_count += 1
        state.account_id = account.get("account_id", state.account_id)

        if not state.session_id:
            state.session_id = str(uuid.uuid4())

        # 1) ML fast path — always refresh if cache is empty or stale
        ml_cache = state.ml_cache
        needs_scoring = (
            not ml_cache.account_id
            or ml_cache.account_id != account.get("account_id")
        )
        if needs_scoring:
            scores = self._run_ml_scoring(account)
            self.memory.add_observation(
                source="supervisor",
                content=(
                    f"ML scored account {scores['account_id']}: "
                    f"recovery_prob={scores['recovery_probability']:.3f}, "
                    f"settlement={scores['settlement_threshold']:.2f}, "
                    f"channels={scores['optimal_channels']}"
                ),
            )

        # 2) Check token budget — auto-compress if high
        if self.memory.budget_pct() > 0.85:
            self.memory.compress(keep_recent=5)
            self.memory.add_observation(
                source="supervisor",
                content="Auto-compressed memory (local) — budget was >85%.",
            )

        # 3) Build context + call LLM
        context = self.memory.render_context()
        user_msg = (
            f"<context>\n{context}\n</context>\n\n"
            f"<goal>{goal}</goal>\n"
            f"<step>{state.step_count}</step>\n"
            f"<budget_pct>{self.memory.budget_pct():.1%}</budget_pct>\n\n"
            "Decide the next action."
        )

        decision = await self.llm.call(
            system=SUPERVISOR_SYSTEM, user_message=user_msg
        )

        self.memory.add_observation(
            source="supervisor",
            content=(
                f"Step {state.step_count} decision: action={decision.action}, "
                f"reasoning={decision.reasoning[:200]}"
            ),
        )

        # 4) Route to specialist
        result = decision
        action = decision.action.lower().strip()

        if action == "score":
            # Re-run ML scoring
            scores = self._run_ml_scoring(account)
            result = AgentOutput(
                reasoning="Re-scored account via ML engine.",
                action="score",
                payload=scores,
                next_steps=decision.next_steps,
                token_estimate=50,
            )

        elif action in self.specialists:
            specialist = self.specialists[action]
            payload = {**decision.payload, "account": account, "goal": goal}
            specialist_result = await specialist.execute(
                memory=self.memory, payload=payload, llm=self.llm
            )
            self.memory.add_observation(
                source=specialist.name,
                content=(
                    f"Specialist result: action={specialist_result.action}, "
                    f"reasoning={specialist_result.reasoning[:200]}"
                ),
            )

            # If specialist was planner, store the plan
            if action == "plan" and specialist_result.next_steps:
                state.current_plan = specialist_result.next_steps

            # If specialist was verifier, log compliance
            if action == "verify":
                passed = specialist_result.action == "approve"
                self.memory.add_compliance_note(
                    rule="fdcpa/tcpa",
                    check=f"verify:{decision.payload.get('proposed_action', '')}",
                    passed=passed,
                    detail=specialist_result.reasoning[:300],
                )

            # Nest specialist output
            result = AgentOutput(
                reasoning=decision.reasoning,
                action=decision.action,
                payload={
                    **decision.payload,
                    "specialist_result": specialist_result.model_dump(),
                },
                next_steps=specialist_result.next_steps or decision.next_steps,
                token_estimate=(
                    decision.token_estimate + specialist_result.token_estimate
                ),
            )

        # 5) Persist state
        self.memory.save()

        logger.info(
            "Supervisor step complete",
            extra={
                "step": state.step_count,
                "action": result.action,
                "budget_pct": f"{self.memory.budget_pct():.1%}",
            },
        )

        return result
