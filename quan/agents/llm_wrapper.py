# quan/agents/llm_wrapper.py
"""
Async LLM wrapper with JSON-mode output and tool support.

Supports Anthropic (Claude) and OpenAI-compatible APIs.
Picks provider from the QUANNEX_LLM_PROVIDER env var
("anthropic" | "openai", default "anthropic").

All calls return a parsed dict — the wrapper enforces structured JSON
output via system prompts and optional response_format where supported.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

from quan.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Output schema every LLM call must conform to
# ---------------------------------------------------------------------------

class AgentOutput(BaseModel):
    """Canonical output schema for every agent / specialist response."""

    reasoning: str = Field(
        ..., description="Chain-of-thought explaining the decision."
    )
    action: str = Field(
        ...,
        description=(
            "Action to take: score, plan, outreach, verify, simulate, "
            "compress, delegate, complete, escalate."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific structured data.",
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of recommended follow-up actions.",
    )
    token_estimate: int = Field(
        default=0,
        description="Estimated tokens consumed by this response.",
    )


# ---------------------------------------------------------------------------
# Provider-agnostic async wrapper
# ---------------------------------------------------------------------------

_JSON_SYSTEM_SUFFIX = (
    "\n\nYou MUST reply with valid JSON matching this schema and nothing "
    "else — no markdown fences, no commentary outside the JSON object:\n"
    "{\n"
    '  "reasoning": "<str>",\n'
    '  "action": "<str>",\n'
    '  "payload": { ... },\n'
    '  "next_steps": ["<str>", ...],\n'
    '  "token_estimate": <int>\n'
    "}"
)


class LLMWrapper:
    """
    Thin async wrapper around Anthropic and OpenAI chat completion APIs.

    Usage::

        llm = LLMWrapper()                   # reads env vars
        result = await llm.call(
            system="You are a debt-collection AI supervisor.",
            user_message="<context>...</context>\\nDecide next action.",
        )
        # result is a validated AgentOutput instance

    For plain summarization calls (no JSON schema)::

        text = await llm.call_raw(
            system="Summarize concisely.",
            user_message=long_text,
        )
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ):
        self.provider = (
            provider or os.getenv("QUANNEX_LLM_PROVIDER", "anthropic")
        ).lower()
        self.max_tokens = max_tokens
        self.temperature = temperature

        if self.provider == "anthropic":
            self.model = model or os.getenv(
                "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"
            )
            self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        else:
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
            self._api_key = os.getenv("OPENAI_API_KEY", "")

        if not self._api_key:
            logger.warning(
                f"No API key set for provider={self.provider}. "
                "LLM calls will fail until key is configured."
            )

    # ----- structured call (returns AgentOutput) ----------------------------

    async def call(
        self,
        system: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentOutput:
        """
        Send a prompt and parse the response as AgentOutput.

        Appends JSON schema instructions to the system prompt so the
        model returns well-formed JSON regardless of provider.
        """
        full_system = system + _JSON_SYSTEM_SUFFIX
        raw = await self._dispatch(full_system, user_message, tools)
        return self._parse_output(raw)

    # ----- raw call (returns plain str) ------------------------------------

    async def call_raw(
        self,
        system: str,
        user_message: str,
    ) -> str:
        """Return the raw string response (for summarization, etc.)."""
        return await self._dispatch(system, user_message)

    # ----- internal dispatch -----------------------------------------------

    async def _dispatch(
        self,
        system: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        if self.provider == "anthropic":
            return await self._call_anthropic(system, user_message, tools)
        return await self._call_openai(system, user_message, tools)

    # ----- Anthropic (Claude) ----------------------------------------------

    async def _call_anthropic(
        self,
        system: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "pip install anthropic  — required for Anthropic provider"
            ) from exc

        client = AsyncAnthropic(api_key=self._api_key)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)

        # Extract text from content blocks
        text_parts: list[str] = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        return "\n".join(text_parts)

    # ----- OpenAI / compatible --------------------------------------------

    async def _call_openai(
        self,
        system: str,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "pip install openai  — required for OpenAI provider"
            ) from exc

        client = AsyncOpenAI(api_key=self._api_key)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    # ----- response parsing ------------------------------------------------

    @staticmethod
    def _parse_output(raw: str) -> AgentOutput:
        """Parse raw LLM text into an AgentOutput, with graceful fallback."""
        # Strip markdown fences if model included them despite instructions
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            return AgentOutput.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(
                f"LLM output failed JSON parse, wrapping as escalation: {exc}"
            )
            return AgentOutput(
                reasoning=f"Failed to parse LLM output: {str(exc)[:200]}",
                action="escalate",
                payload={"raw_output": raw[:2000]},
                next_steps=["retry_with_stricter_prompt"],
                token_estimate=len(raw) // 4,
            )
