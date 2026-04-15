#!/usr/bin/env python3
# test_quannex_agent.py
"""
Example usage & integration test for the Quannex hierarchical agent system.

Usage:
    # Run the offline (no-LLM) integration test:
    python test_quannex_agent.py

    # Run against a live LLM (requires ANTHROPIC_API_KEY or OPENAI_API_KEY):
    python test_quannex_agent.py --live

    # Run against the FastAPI server (requires server running on :8000):
    python test_quannex_agent.py --api
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Sample account fixture
# ---------------------------------------------------------------------------

SAMPLE_ACCOUNT: dict = {
    "account_id": "ACC-TEST-001",
    "debtor_name": "Jane Doe",
    "debtor_first_name": "Jane",
    "debtor_last_name": "Doe",
    "phone": "+15551234567",
    "phone_valid": True,
    "phone_type": "mobile",
    "email": "jane.doe@example.com",
    "email_valid": True,
    "has_mobile": True,
    "state": "CA",
    "debt_type": "buy_now_pay_later",
    "original_balance": 450.00,
    "current_balance": 385.00,
    "balance": 385.00,
    "days_past_due": 42,
    "payment_willingness": 0.45,
    "employed": True,
    "income_bracket": "medium",
    "age": 29,
    "contact_attempts": 2,
    "successful_contacts": 1,
    "response_rate": 0.5,
    "digital_preference": 0.8,
    # Compliance flags — all clear for test
    "do_not_call": False,
    "do_not_email": False,
    "do_not_mail": False,
    "bankruptcy_flag": False,
    "deceased_flag": False,
    "disputed": False,
    "attorney_represented": False,
    "statute_of_limitations_expired": False,
}


# ---------------------------------------------------------------------------
# 1. Offline test (no LLM, exercises ML scoring + memory + compression)
# ---------------------------------------------------------------------------

def test_offline():
    """Test memory, ML scoring, and compression without any LLM calls."""
    print("=" * 60)
    print("OFFLINE TEST — Memory + ML Scoring + Compression")
    print("=" * 60)

    from quan.agents.memory import QuannexMemoryManager, QuannexAgentState
    from quan.intelligence.engine import CollectionIntelligence

    # --- ML Scoring ---
    engine = CollectionIntelligence()
    strategy = engine.generate_strategy(SAMPLE_ACCOUNT)

    print(f"\nML Scoring Results:")
    print(f"  Account:              {strategy.account_id}")
    print(f"  Recovery Probability: {strategy.recovery_probability:.3f}")
    print(f"  Settlement Threshold: {strategy.settlement_threshold:.2f}")
    print(f"  Optimal Channels:     {strategy.optimal_channels}")
    print(f"  Confidence:           {strategy.confidence:.3f}")
    print(f"  Contact Sequence:     {len(strategy.contact_sequence)} steps")

    # --- Memory Manager ---
    state = QuannexAgentState(session_id="test-offline-001")
    memory = QuannexMemoryManager(
        state=state,
        token_budget=5000,  # Low budget to trigger compression
        persist_path="/tmp/test_quannex_agent_memory.json",
    )

    # Populate ML cache
    memory.update_ml_cache(
        account_id=strategy.account_id,
        recovery_probability=strategy.recovery_probability,
        settlement_threshold=strategy.settlement_threshold,
        optimal_channels=strategy.optimal_channels,
        confidence=strategy.confidence,
        segment_id=strategy.segment_id,
    )

    # Add observations to trigger compression
    for i in range(15):
        memory.add_observation(
            source="test",
            content=f"Observation {i}: scoring complete, channels evaluated, "
            f"compliance checks passed. Recovery={strategy.recovery_probability:.3f}. "
            f"Planning step {i} of collection sequence.",
        )

    print(f"\nMemory State:")
    print(f"  Observations:  {len(memory.state.observations)}")
    print(f"  Summary chars: {len(memory.state.summary)}")
    print(f"  Budget used:   {memory.budget_pct():.1%}")

    # --- XML Context Rendering ---
    context = memory.render_context()
    print(f"\nRendered Context ({len(context)} chars):")
    print(context[:500] + "\n..." if len(context) > 500 else context)

    # --- Persistence ---
    memory.save()
    memory2 = QuannexMemoryManager(
        persist_path="/tmp/test_quannex_agent_memory.json"
    )
    assert memory2.load(), "Failed to load persisted state"
    assert memory2.state.session_id == "test-offline-001"
    print(f"\nPersistence: OK (restored session {memory2.state.session_id})")

    # --- Compliance Note ---
    memory.add_compliance_note(
        rule="fdcpa",
        check="contact_hours",
        passed=True,
        detail="Contact at 10:15 AM PST — within allowed hours.",
    )
    assert len(memory.state.compliance_notes) == 1
    print(f"Compliance Notes: {len(memory.state.compliance_notes)}")

    print("\nOFFLINE TEST: PASSED")


# ---------------------------------------------------------------------------
# 2. Live LLM test (requires API key)
# ---------------------------------------------------------------------------

async def test_live():
    """Full supervisor step with a real LLM call."""
    print("=" * 60)
    print("LIVE TEST — Full Supervisor Step (LLM required)")
    print("=" * 60)

    from quan.agents.supervisor import QuannexSupervisor
    from quan.agents.outreach_specialist import OutreachSpecialist
    from quan.agents.llm_wrapper import LLMWrapper
    from quan.agents.memory import QuannexMemoryManager

    memory = QuannexMemoryManager(
        persist_path="/tmp/test_quannex_agent_live.json"
    )
    llm = LLMWrapper()
    supervisor = QuannexSupervisor(llm=llm, memory=memory)
    supervisor.register_specialist("outreach", OutreachSpecialist())

    # Step 1: Initial step (should score + plan)
    print("\n--- Step 1 ---")
    result = await supervisor.step(
        account=SAMPLE_ACCOUNT,
        goal="maximize recovery while maintaining compliance",
    )
    print(f"  Action:    {result.action}")
    print(f"  Reasoning: {result.reasoning[:200]}")
    print(f"  Next:      {result.next_steps}")
    print(f"  Tokens:    ~{result.token_estimate}")
    print(f"  Budget:    {memory.budget_pct():.1%}")

    # Step 2: Follow-up step
    print("\n--- Step 2 ---")
    result2 = await supervisor.step(
        account=SAMPLE_ACCOUNT,
        goal="plan outreach sequence for this BNPL account",
    )
    print(f"  Action:    {result2.action}")
    print(f"  Reasoning: {result2.reasoning[:200]}")
    print(f"  Next:      {result2.next_steps}")

    # Step 3: One more
    print("\n--- Step 3 ---")
    result3 = await supervisor.step(
        account=SAMPLE_ACCOUNT,
        goal="generate an initial SMS outreach draft",
    )
    print(f"  Action:    {result3.action}")
    print(f"  Reasoning: {result3.reasoning[:200]}")
    if "specialist_result" in result3.payload:
        sr = result3.payload["specialist_result"]
        print(f"  Specialist: {sr.get('action', 'n/a')}")
        if "message_text" in sr.get("payload", {}):
            print(f"  Message:   {sr['payload']['message_text'][:200]}")

    print(f"\n  Final state: {memory.state.step_count} steps, "
          f"{len(memory.state.observations)} observations, "
          f"{len(memory.state.compliance_notes)} compliance notes")
    print("\nLIVE TEST: COMPLETED")


# ---------------------------------------------------------------------------
# 3. API test (requires running server)
# ---------------------------------------------------------------------------

async def test_api():
    """Test against the running FastAPI server."""
    print("=" * 60)
    print("API TEST — POST /api/v1/agent/step")
    print("=" * 60)

    try:
        import httpx
    except ImportError:
        print("ERROR: pip install httpx  — required for API test")
        return

    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Health check
        health = await client.get(f"{base_url}/health")
        print(f"\nHealth: {health.json()}")

        # Step 1
        print("\n--- Step 1 ---")
        resp = await client.post(
            f"{base_url}/api/v1/agent/step",
            json={
                "account": SAMPLE_ACCOUNT,
                "goal": "maximize recovery while maintaining compliance",
            },
        )
        if resp.status_code != 200:
            print(f"ERROR: {resp.status_code} {resp.text}")
            return

        data = resp.json()
        session_id = data["session_id"]
        print(f"  Session:   {session_id}")
        print(f"  Step:      {data['step']}")
        print(f"  Action:    {data['action']}")
        print(f"  Reasoning: {data['reasoning'][:200]}")
        print(f"  Budget:    {data['budget_pct']:.1%}")

        # Step 2 — resume session
        print("\n--- Step 2 (resume) ---")
        resp2 = await client.post(
            f"{base_url}/api/v1/agent/step",
            json={
                "account": SAMPLE_ACCOUNT,
                "goal": "plan outreach sequence",
                "session_id": session_id,
            },
        )
        data2 = resp2.json()
        print(f"  Step:      {data2['step']}")
        print(f"  Action:    {data2['action']}")
        print(f"  Reasoning: {data2['reasoning'][:200]}")

        # Retrieve state
        print("\n--- State ---")
        state_resp = await client.get(
            f"{base_url}/api/v1/agent/state/{session_id}"
        )
        state = state_resp.json()
        print(f"  Steps:      {state['step_count']}")
        print(f"  Obs:        {len(state['observations'])}")
        print(f"  Compliance: {len(state['compliance_notes'])}")
        print(f"  Budget:     {state['budget_pct']:.1%}")

    print("\nAPI TEST: COMPLETED")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Test the Quannex hierarchical agent system."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live test with real LLM calls (requires API key).",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run API test against running server on localhost:8000.",
    )
    args = parser.parse_args()

    if args.api:
        asyncio.run(test_api())
    elif args.live:
        asyncio.run(test_live())
    else:
        test_offline()


if __name__ == "__main__":
    main()
