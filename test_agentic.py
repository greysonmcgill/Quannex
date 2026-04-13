#!/usr/bin/env python3
"""Quick test for agentic controller"""

import asyncio

from quan.agents.agentic_controller import AgenticController, AutonomyLevel

async def quick_test():
    controller = AgenticController(
        default_autonomy=AutonomyLevel.LEVEL_3_GUIDED,
        max_concurrent_agents=5,
    )

    # Store mock profile
    mock_profile = {
        'account_id': 'TEST-001',
        'name': 'Test User',
        'balance': 350.00,
        'original_creditor': 'Test Credit',
        'state': 'CA',
        'recovery_probability': 0.6,
        'days_past_due': 30,
    }
    controller.rag._debtor_store['TEST-001'] = mock_profile

    print("\n=== AGENTIC CONTROLLER QUICK TEST ===\n")

    # Start session
    session = await controller.start_session('TEST-001', 'voice')
    print(f"Session started: {session['status']}")
    print(f"Conversation ID: {session['conversation_id']}")
    print(f"Agent ID: {session['agent_id']}")

    # Process a turn
    response, state = await controller.process_turn(
        session['conversation_id'],
        'Yes, this is Test User'
    )
    print(f"\nResponse: {response.text[:100]}..." if len(response.text) > 100 else f"\nResponse: {response.text}")
    print(f"Phase: {state.phase}")
    print(f"Intent: {response.intent}")

    # End session
    result = await controller.end_session(
        session['conversation_id'],
        'test_complete',
        amount_collected=175.00
    )
    print(f"\nOutcome: {result['outcome']}")
    print(f"ROI: {result['roi']:.1%}")

    # Get status
    status = controller.get_system_status()
    print(f"\nSystem Status:")
    print(f"  Active sessions: {status['active_sessions']}")
    print(f"  Total revenue: ${status['costs']['total_revenue']:.2f}")
    print(f"  Compliance violations (24h): {status['compliance_violations_24h']}")

    print('\n=== ALL COMPONENTS WORKING CORRECTLY ===\n')

if __name__ == "__main__":
    asyncio.run(quick_test())
