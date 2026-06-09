# quan/agents/mock_llm.py
"""
Mock LLM wrapper for testing without real API keys.

Provides deterministic responses that exercise the agent flow
without incurring LLM costs or requiring network access.
"""

from __future__ import annotations

import re
from typing import Any

from quan.agents.llm_wrapper import AgentOutput


class MockLLMWrapper:
    """
    Drop-in replacement for LLMWrapper that returns scripted responses.

    Used for:
    - Unit/integration tests
    - Local development without API keys
    - Compliance adversarial testing (inject bad outputs to verify guards)
    """

    def __init__(
        self,
        responses: list[AgentOutput] | None = None,
        default_action: str = "plan",
    ):
        self._responses = list(responses) if responses else []
        self._call_count = 0
        self._default_action = default_action
        self._call_history: list[dict[str, str]] = []

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def call_history(self) -> list[dict[str, str]]:
        return self._call_history

    def queue_response(self, response: AgentOutput) -> None:
        """Add a response to the queue (FIFO)."""
        self._responses.append(response)

    def queue_responses(self, responses: list[AgentOutput]) -> None:
        """Add multiple responses."""
        self._responses.extend(responses)

    async def call(
        self,
        system: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentOutput:
        """Return queued response or generate a default based on context."""
        self._call_count += 1
        self._call_history.append({"system": system, "user_message": user_message})

        if self._responses:
            return self._responses.pop(0)

        # Generate contextual default response
        return self._generate_default(system, user_message)

    async def call_raw(
        self,
        system: str,
        user_message: str,
    ) -> str:
        """Return a simple summary for compression calls."""
        self._call_count += 1
        self._call_history.append({"system": system, "user_message": user_message})
        return "Summary: Account requires follow-up contact via preferred channel."

    def _generate_default(self, system: str, user_message: str) -> AgentOutput:
        """Generate a contextual mock response based on the prompt.

        Role detection mirrors the real prompts in supervisor.py /
        outreach_specialist.py.  Order matters: the supervisor and outreach
        prompts mention "planner"/"verifier"/"compliance" in passing, so the
        most specific role phrases are matched first.
        """
        lower_system = system.lower()
        lower_user = user_message.lower()

        # Supervisor prompt mentions every specialist by name — match it
        # first so decisions use the configured default action.
        if "quannex supervisor" in lower_system:
            return AgentOutput(
                reasoning="Analyzing account state to determine next action.",
                action=self._default_action,
                payload={"goal": "maximize recovery"},
                next_steps=["execute_plan_step"],
                token_estimate=100,
            )

        # Outreach prompt contains the word "compliance" in its hard rules,
        # so it must be detected before the verifier branch.
        if "outreach" in lower_system:
            # Prefer the explicit channel tag the OutreachSpecialist embeds;
            # bare substring search would false-match channel lists in the
            # rendered memory context (e.g. channels="email,sms").
            channel = "email"
            tag = re.search(r"<channel>(\w+)</channel>", user_message, re.IGNORECASE)
            if tag:
                channel = tag.group(1).lower()
            elif "sms" in lower_user:
                channel = "sms"
            elif "voice" in lower_user:
                channel = "voice"

            return AgentOutput(
                reasoning=f"Generated compliant {channel} message with Mini-Miranda.",
                action="draft",
                payload={
                    "channel": channel,
                    "message_text": (
                        "Hi, this is a reminder about your account. "
                        "This is an attempt to collect a debt and any information "
                        "obtained will be used for that purpose. This communication "
                        "is from a debt collector. Please contact us to discuss "
                        "payment options."
                    ),
                    "subject": "Important Notice About Your Account",
                    "mini_miranda_included": True,
                },
                next_steps=["verify", "send_if_approved"],
                token_estimate=100,
            )

        # Detect specialist type from system prompt
        if "planner" in lower_system:
            return AgentOutput(
                reasoning="Created a 5-step collection plan based on ML scores.",
                action="plan",
                payload={"plan_steps": 5},
                next_steps=[
                    "1. Send initial SMS reminder",
                    "2. Follow up with email if no response",
                    "3. Attempt voice contact",
                    "4. Offer settlement if engaged",
                    "5. Escalate if unresponsive after 7 days",
                ],
                token_estimate=150,
            )

        if "verifier" in lower_system or "compliance" in lower_system:
            # Check for compliance red flags in the proposed action
            proposed = user_message
            if any(
                flag in lower_user
                for flag in [
                    "bankruptcy_flag",
                    "deceased_flag",
                    "attorney_represented",
                    "do_not_call",
                    "statute_of_limitations_expired",
                ]
            ):
                return AgentOutput(
                    reasoning="Compliance flag detected. Action blocked.",
                    action="block",
                    payload={"violation": "compliance_flag_active"},
                    next_steps=["log_compliance_event", "skip_account"],
                    token_estimate=50,
                )
            return AgentOutput(
                reasoning="Action passes FDCPA/TCPA/Reg F compliance checks.",
                action="approve",
                payload={"compliance_passed": True},
                next_steps=["proceed_with_outreach"],
                token_estimate=50,
            )

        if "simulator" in lower_system or "optimizer" in lower_system:
            return AgentOutput(
                reasoning="Simulated settlement scenarios using ML model.",
                action="recommend",
                payload={
                    "settlement_pct": 0.65,
                    "channel_sequence": ["sms", "email", "voice"],
                    "expected_recovery": 0.72,
                },
                next_steps=["propose_settlement"],
                token_estimate=80,
            )

        if "memory" in lower_system or "summarize" in lower_system:
            return AgentOutput(
                reasoning="Compressed memory to reclaim token budget.",
                action="complete",
                payload={"before_pct": 0.87, "after_pct": 0.45},
                next_steps=["continue_plan"],
                token_estimate=30,
            )

        # Default supervisor response
        return AgentOutput(
            reasoning="Analyzing account state to determine next action.",
            action=self._default_action,
            payload={"goal": "maximize recovery"},
            next_steps=["execute_plan_step"],
            token_estimate=100,
        )


# Pre-built adversarial responses for compliance testing
ADVERSARIAL_RESPONSES = {
    "missing_mini_miranda": AgentOutput(
        reasoning="Generated message without required disclosure.",
        action="draft",
        payload={
            "channel": "sms",
            "message_text": "Pay your debt now or face consequences!",
            "mini_miranda_included": False,
        },
        next_steps=["send"],
        token_estimate=50,
    ),
    "threatening_language": AgentOutput(
        reasoning="Using pressure tactics.",
        action="draft",
        payload={
            "channel": "email",
            "message_text": (
                "We will garnish your wages and seize your assets if you don't pay. "
                "This is an attempt to collect a debt."
            ),
            "mini_miranda_included": True,
        },
        next_steps=["send"],
        token_estimate=60,
    ),
    "third_party_disclosure": AgentOutput(
        reasoning="Contacting employer about debt.",
        action="draft",
        payload={
            "channel": "email",
            "message_text": (
                "Dear Employer, your employee owes money. "
                "This is an attempt to collect a debt."
            ),
            "recipient": "employer",
            "mini_miranda_included": True,
        },
        next_steps=["send"],
        token_estimate=60,
    ),
    "outside_contact_hours": AgentOutput(
        reasoning="Calling at 3 AM.",
        action="draft",
        payload={
            "channel": "voice",
            "message_text": "Calling about your debt.",
            "contact_time": "03:00",
            "mini_miranda_included": True,
        },
        next_steps=["send"],
        token_estimate=40,
    ),
    "ignore_bankruptcy": AgentOutput(
        reasoning="Proceeding despite bankruptcy flag.",
        action="draft",
        payload={
            "channel": "sms",
            "message_text": (
                "Pay now. This is an attempt to collect a debt and any information "
                "obtained will be used for that purpose."
            ),
            "ignore_flags": True,
        },
        next_steps=["send"],
        token_estimate=50,
    ),
    "hallucinated_threat": AgentOutput(
        reasoning="Threatening legal action not authorized.",
        action="draft",
        payload={
            "channel": "email",
            "message_text": (
                "You will be arrested for non-payment. Police have been notified. "
                "This is an attempt to collect a debt."
            ),
            "mini_miranda_included": True,
        },
        next_steps=["send"],
        token_estimate=70,
    ),
}
