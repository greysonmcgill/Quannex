"""Integration tests for the recovery (agent-assisted collections) router.

Covers:

1. compliance pre-checks (compliant and non-compliant messages),
2. 404 handling for unknown accounts,
3. outreach channel validation (pattern matches ContactChannel enum),
4. dry-run outreach drafting (no contact attempt recorded),
5. compliance event history.

The outreach endpoint normally drives an LLM through ``LLMWrapper``.  Tests
monkeypatch ``quan.agents.supervisor.LLMWrapper`` with the deterministic
``MockLLMWrapper`` so the suite runs without network access or API keys.

The ``client`` fixture is provided by ``tests/integration/conftest.py`` and
is bound to an isolated SQLite database for the whole test session.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CSV_PAYLOAD = (
    "account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email\n"
    "ACC-REC-001,Alice Rivera,320.00,Klarna,bnpl,40,CA,+15551112222,alice@example.com\n"
    "ACC-REC-002,Bob Chen,150.75,Verizon,telecom,25,TX,+15553334444,bob@example.com\n"
)

MINI_MIRANDA_MESSAGE = (
    "Hello Alice, this is a reminder about your account balance of $320.00. "
    "This is an attempt to collect a debt and any information obtained will "
    "be used for that purpose. This communication is from a debt collector. "
    "Please contact us to discuss flexible payment options."
)

THREATENING_MESSAGE = (
    "Pay immediately or you will be arrested and the police will be notified."
)


@pytest.fixture(scope="module", autouse=True)
def recovery_accounts(client) -> None:
    """Upload a small portfolio so recovery endpoints have accounts to act on."""

    response = client.post(
        "/api/v1/portfolios/upload",
        files={"file": ("recovery.csv", CSV_PAYLOAD.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["imported_rows"] == 2


@pytest.fixture()
def mock_llm(monkeypatch):
    """Replace the real LLM wrapper with the deterministic mock.

    The recovery router lazily imports ``QuannexSupervisor``, whose
    constructor instantiates ``LLMWrapper()`` from the supervisor module's
    namespace — patching that name routes all agent calls to the mock.

    A compliant outreach draft is queued explicitly: the mock's contextual
    default matches the word "compliance" in the outreach system prompt and
    would otherwise return a verifier-style payload without message text.
    """

    from quan.agents import supervisor as supervisor_module
    from quan.agents.llm_wrapper import AgentOutput
    from quan.agents.mock_llm import MockLLMWrapper

    draft = AgentOutput(
        reasoning="Generated compliant email draft with Mini-Miranda.",
        action="draft",
        payload={
            "channel": "email",
            "message_text": MINI_MIRANDA_MESSAGE,
            "subject": "Important Notice About Your Account",
        },
        next_steps=["verify", "send_if_approved"],
        token_estimate=100,
    )

    monkeypatch.setattr(
        supervisor_module,
        "LLMWrapper",
        lambda *args, **kwargs: MockLLMWrapper(responses=[draft]),
    )


# ---------------------------------------------------------------------------
# Compliance pre-check
# ---------------------------------------------------------------------------


def test_compliance_check_passes_for_compliant_message(client) -> None:
    response = client.post(
        "/api/v1/recovery/ACC-REC-001/compliance-check",
        json={
            "action_type": "outreach",
            "channel": "email",
            "message_text": MINI_MIRANDA_MESSAGE,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is True
    assert body["violations"] == []
    assert body["rule_summary"]


def test_compliance_check_fails_for_threatening_message(client) -> None:
    response = client.post(
        "/api/v1/recovery/ACC-REC-001/compliance-check",
        json={
            "action_type": "outreach",
            "channel": "sms",
            "message_text": THREATENING_MESSAGE,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is False
    assert body["violations"], "threatening message must produce violations"
    violation_types = {v["type"] for v in body["violations"]}
    # Missing Mini-Miranda plus criminal-threat language.
    assert violation_types, violation_types


def test_compliance_check_unknown_account_returns_404(client) -> None:
    response = client.post(
        "/api/v1/recovery/ACC-DOES-NOT-EXIST/compliance-check",
        json={
            "action_type": "outreach",
            "channel": "email",
            "message_text": MINI_MIRANDA_MESSAGE,
        },
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


def test_outreach_rejects_unsupported_push_channel(client) -> None:
    response = client.post(
        "/api/v1/recovery/ACC-REC-001/outreach",
        json={"channel": "push", "dry_run": True},
    )
    # "push" is not a ContactChannel — the request schema pattern rejects it.
    assert response.status_code == 422


def test_outreach_dry_run_drafts_without_recording_contact(client, mock_llm) -> None:
    before = client.get("/api/v1/accounts/ACC-REC-002").json()
    attempts_before = before["total_contact_attempts"]

    response = client.post(
        "/api/v1/recovery/ACC-REC-002/outreach",
        json={"channel": "email", "goal": "initial_notice", "dry_run": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["account_id"] == "ACC-REC-002"
    assert body["channel"] == "email"
    assert body["compliance_passed"] is True
    assert body["status"] in {"drafted", "approved"}
    assert body["message_text"], "dry run should still draft a message"
    assert body["contact_attempt_id"] is None

    # Dry run must not record a contact attempt.
    after = client.get("/api/v1/accounts/ACC-REC-002").json()
    assert after["total_contact_attempts"] == attempts_before


# ---------------------------------------------------------------------------
# Compliance history
# ---------------------------------------------------------------------------


def test_compliance_history_returns_events_list(client) -> None:
    response = client.get("/api/v1/recovery/ACC-REC-001/compliance-history")
    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == "ACC-REC-001"
    assert isinstance(body["events"], list)
    assert body["total_events"] == len(body["events"])
