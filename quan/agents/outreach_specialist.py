# quan/agents/outreach_specialist.py
"""
Outreach Specialist — generates personalized, FDCPA/TCPA-compliant
debtor communications.

This specialist NEVER sends messages itself; it produces draft content
that must pass through the Verifier before execution.  Each draft
includes the required Mini-Miranda disclosure and respects all
compliance flags on the account.
"""

from __future__ import annotations

from typing import Any

from quan.agents.llm_wrapper import AgentOutput, LLMWrapper
from quan.agents.memory import AgentSessionMemory
from quan.agents.supervisor import BaseSpecialist
from quan.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Required disclosures (FDCPA § 1692e(11))
# ---------------------------------------------------------------------------

MINI_MIRANDA = (
    "This is an attempt to collect a debt and any information obtained "
    "will be used for that purpose. This communication is from a debt "
    "collector."
)

# Channel-specific character budgets (keeps costs low)
CHANNEL_LIMITS: dict[str, int] = {
    "sms": 160,
    "email": 2000,
    "mail": 4000,
    "push": 120,
}


# ---------------------------------------------------------------------------
# Outreach system prompt
# ---------------------------------------------------------------------------

OUTREACH_SYSTEM = """\
You are the Outreach Specialist in a fintech micro-debt collection system.

Your job: produce a SINGLE personalized message for the specified channel.

HARD RULES — violating any of these is a compliance failure:
1. Always include the Mini-Miranda disclosure verbatim:
   "{mini_miranda}"
2. Never threaten actions the company will not take.
3. Never use dehumanizing or abusive language.
4. Never disclose the debt to third parties (message must be addressed
   to the debtor only).
5. Never contact before 8 AM or after 9 PM local time.
6. Respect all compliance flags: do_not_call, do_not_email, do_not_mail,
   bankruptcy_flag, deceased_flag, disputed, attorney_represented.
7. If the account is disputed, the message must acknowledge the dispute
   and include validation rights.
8. Keep the message within the channel character limit.

TONE: empathetic, professional, solution-oriented.  Emphasize
convenience (payment link, settlement options) over pressure.

Respond ONLY with the required JSON.
""".format(mini_miranda=MINI_MIRANDA)


# ---------------------------------------------------------------------------
# Specialist implementation
# ---------------------------------------------------------------------------

class OutreachSpecialist(BaseSpecialist):
    """
    Generates a single outreach draft per invocation.

    Input payload keys:
        channel   (str)  : "sms" | "email" | "mail" | "push"
        account   (dict) : full account dict
        goal      (str)  : e.g. "initial_notice", "reminder", "settlement_offer"
        offer_pct (float): optional settlement percentage (e.g. 0.70)
    """

    name = "outreach"

    async def execute(
        self,
        memory: AgentSessionMemory,
        payload: dict[str, Any],
        llm: LLMWrapper,
    ) -> AgentOutput:
        account = payload.get("account", {})
        channel = payload.get("channel", "email")
        goal = payload.get("goal", "initial_notice")
        offer_pct = payload.get("offer_pct")

        # --- Pre-flight compliance checks (fast, no LLM) ----------------
        block_reason = self._preflight_check(account, channel)
        if block_reason:
            memory.add_compliance_note(
                rule="fdcpa/tcpa",
                check=f"outreach_preflight:{channel}",
                passed=False,
                detail=block_reason,
            )
            return AgentOutput(
                reasoning=f"Blocked by preflight compliance: {block_reason}",
                action="block",
                payload={"block_reason": block_reason},
                next_steps=["log_compliance_event"],
                token_estimate=0,
            )

        # --- Build LLM prompt -------------------------------------------
        char_limit = CHANNEL_LIMITS.get(channel, 2000)
        mc = memory.state.ml_cache
        context = memory.render_context(max_chars=4000)

        debtor_first = (
            account.get("debtor_first_name")
            or account.get("debtor_name", "").split()[0]
            if account.get("debtor_name")
            else "Valued Customer"
        )
        balance = float(account.get("current_balance", 0))

        settlement_line = ""
        if offer_pct and balance > 0:
            offer_amt = balance * offer_pct
            settlement_line = (
                f"We can offer a settlement of ${offer_amt:,.2f} "
                f"({offer_pct:.0%} of ${balance:,.2f})."
            )

        user_msg = (
            f"<context>\n{context}\n</context>\n\n"
            f"<channel>{channel}</channel>\n"
            f"<char_limit>{char_limit}</char_limit>\n"
            f"<message_goal>{goal}</message_goal>\n"
            f"<debtor_first_name>{debtor_first}</debtor_first_name>\n"
            f"<balance>${balance:,.2f}</balance>\n"
            f"<recovery_probability>{mc.recovery_probability:.2f}</recovery_probability>\n"
            f"<settlement_info>{settlement_line}</settlement_info>\n"
            f"<disputed>{'yes' if account.get('disputed') else 'no'}</disputed>\n\n"
            "Generate the outreach message.  Put the full message text in "
            'payload["message_text"] and the subject line (if email) in '
            'payload["subject"].'
        )

        result = await llm.call(system=OUTREACH_SYSTEM, user_message=user_msg)

        # --- Post-flight validation -------------------------------------
        msg_text = result.payload.get("message_text", "")
        issues = self._postflight_check(msg_text, channel)
        if issues:
            memory.add_compliance_note(
                rule="fdcpa",
                check="outreach_postflight",
                passed=False,
                detail="; ".join(issues),
            )
            result.payload["compliance_warnings"] = issues
            # Don't block — let verifier make final call — but flag it
            result.next_steps = ["verify"] + result.next_steps

        memory.add_compliance_note(
            rule="fdcpa/tcpa",
            check=f"outreach_draft:{channel}:{goal}",
            passed=len(issues) == 0,
            detail=f"Generated {len(msg_text)} chars for {channel}",
        )

        return result

    # ---- compliance helpers -----------------------------------------------

    @staticmethod
    def _preflight_check(account: dict, channel: str) -> str | None:
        """Return a block reason string, or None if OK."""
        if account.get("deceased_flag"):
            return "Account flagged as deceased."
        if account.get("bankruptcy_flag"):
            return "Bankruptcy protection active."
        if account.get("attorney_represented"):
            return "Attorney representation — must contact attorney."
        if channel == "sms" and account.get("do_not_call"):
            return "Do-not-call flag set; cannot SMS."
        if channel == "email" and account.get("do_not_email"):
            return "Do-not-email flag set."
        if channel == "mail" and account.get("do_not_mail"):
            return "Do-not-mail flag set."
        return None

    @staticmethod
    def _postflight_check(text: str, channel: str) -> list[str]:
        """Validate generated message text.  Returns list of issues."""
        issues: list[str] = []
        lower = text.lower()

        # Mini-Miranda presence
        if "debt collector" not in lower:
            issues.append("Missing Mini-Miranda: 'debt collector' not found.")
        if "attempt to collect" not in lower and "attempting to collect" not in lower:
            issues.append("Missing Mini-Miranda: 'attempt to collect' not found.")

        # Prohibited language (FDCPA)
        prohibited = [
            "arrest", "jail", "prison", "criminal",
            "garnish your wages", "seize your",
        ]
        for term in prohibited:
            if term in lower:
                issues.append(f"Prohibited language detected: '{term}'.")

        # Character limit
        limit = CHANNEL_LIMITS.get(channel, 2000)
        if len(text) > limit:
            issues.append(
                f"Message exceeds {channel} limit: {len(text)}/{limit} chars."
            )

        return issues
