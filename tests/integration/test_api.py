"""End-to-end integration tests for the canonical Quannex pilot API.

Covers the full operator flow:

1. health / readiness endpoints,
2. CSV portfolio upload,
3. account listing, detail, status transition,
4. contact logging and payment recording,
5. dashboard surfaces reflect the new activity,
6. compliance events are emitted.

Runs against a fresh SQLite file so the suite is isolated from the developer's
local database.
"""

from __future__ import annotations

import pytest

# The ``client`` fixture is provided by ``tests/integration/conftest.py`` and
# is bound to an isolated SQLite database for the whole test session.


# ---------------------------------------------------------------------------
# Meta / health
# ---------------------------------------------------------------------------


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Quannex Recovery"
    assert payload["status"] == "operational"


def test_livez(client) -> None:
    response = client.get("/livez")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_alias(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readyz_runs_real_database_check(client) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["checks"]["database"] == "ok"


def test_ready_alias_runs_real_check(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["database"] == "ok"


# ---------------------------------------------------------------------------
# Portfolio upload → accounts
# ---------------------------------------------------------------------------


CSV_PAYLOAD = (
    "account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email\n"
    "ACC-INT-001,Jane Doe,250.50,Klarna,bnpl,45,CA,+15551234567,jane@example.com\n"
    "ACC-INT-002,John Roe,175.00,Afterpay,bnpl,30,TX,,john@example.com\n"
    "ACC-INT-003,Taylor Park,500.00,Verizon,telecom,60,NY,+15559876543,\n"
)


def test_portfolio_upload_imports_accounts(client) -> None:
    response = client.post(
        "/api/v1/portfolios/upload",
        files={"file": ("pilot.csv", CSV_PAYLOAD.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["received_rows"] == 3
    assert body["imported_rows"] == 3
    assert body["rejected_rows"] == 0
    assert set(body["debt_mix"].keys()) == {"bnpl", "telecom"}
    assert len(body["accounts"]) == 3


def test_portfolio_upload_rejects_bad_csv(client) -> None:
    bad_csv = (
        "account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email\n"
        "ACC-BAD-01,X,-50,Klarna,mystery,45,ZZ,notaphone,notanemail\n"
    )
    response = client.post(
        "/api/v1/portfolios/upload",
        files={"file": ("bad.csv", bad_csv.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["imported_rows"] == 0
    assert body["rejected_rows"] == 1
    assert body["row_errors"][0]["errors"]


# ---------------------------------------------------------------------------
# Account surface
# ---------------------------------------------------------------------------


def test_accounts_list_returns_uploaded_accounts(client) -> None:
    response = client.get("/api/v1/accounts")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert any(item["account_id"] == "ACC-INT-001" for item in body["items"])


def test_accounts_list_filter_by_debt_type(client) -> None:
    response = client.get("/api/v1/accounts", params={"debt_type": "telecom"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(item["debt_type"] == "telecom" for item in body["items"])


def test_account_detail_uses_canonical_fields(client) -> None:
    response = client.get("/api/v1/accounts/ACC-INT-001")
    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == "ACC-INT-001"
    # Canonical pilot field names — no current_balance / total_payments drift.
    for key in (
        "balance",
        "original_balance",
        "total_paid",
        "total_contact_attempts",
        "last_contact_at",
        "last_payment_at",
        "contact_history",
        "payments",
        "compliance_events",
    ):
        assert key in body


def test_update_account_status_emits_compliance_event(client) -> None:
    response = client.put(
        "/api/v1/accounts/ACC-INT-001/status",
        json={"status": "negotiating", "notes": "Debtor reached via SMS"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "negotiating"

    detail = client.get("/api/v1/accounts/ACC-INT-001").json()
    assert any(
        event["event_type"] == "status_change" for event in detail["compliance_events"]
    )


def test_log_contact_attempt_updates_rollups(client) -> None:
    response = client.post(
        "/api/v1/accounts/ACC-INT-002/contact",
        json={
            "channel": "sms",
            "outcome": "no_answer",
            "compliant": True,
            "agent_name": "pilot-runner",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == "sms"
    assert body["compliant"] is True

    detail = client.get("/api/v1/accounts/ACC-INT-002").json()
    assert detail["total_contact_attempts"] >= 1
    assert detail["last_contact_at"] is not None
    assert detail["status"] == "contacted"


def test_record_payment_reduces_balance_and_marks_resolved(client) -> None:
    original = client.get("/api/v1/accounts/ACC-INT-003").json()
    full_balance = float(original["balance"])

    response = client.post(
        "/api/v1/accounts/ACC-INT-003/payment",
        json={
            "amount": full_balance,
            "method": "card",
            "status": "completed",
            "reference": "test-full-pay",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["balance"] == pytest.approx(0.0, abs=0.01)

    detail = client.get("/api/v1/accounts/ACC-INT-003").json()
    assert detail["status"] == "resolved"
    assert detail["total_paid"] == pytest.approx(full_balance, abs=0.01)
    assert detail["payments"], "payment history should include the recorded payment"


def test_non_compliant_contact_emits_compliance_event(client) -> None:
    response = client.post(
        "/api/v1/accounts/ACC-INT-001/contact",
        json={
            "channel": "voice",
            "outcome": "left_message_outside_hours",
            "compliant": False,
            "notes": "Outside contact window",
        },
    )
    assert response.status_code == 201

    detail = client.get("/api/v1/accounts/ACC-INT-001").json()
    assert any(
        event["event_type"] == "contact_policy" for event in detail["compliance_events"]
    )


# ---------------------------------------------------------------------------
# Dashboard surface
# ---------------------------------------------------------------------------


def test_dashboard_full_payload_has_no_tokenization(client) -> None:
    response = client.get("/api/v1/dashboard/")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "generated_at",
        "executive",
        "operations",
        "compliance",
        "system_health",
        "alerts",
    }


def test_dashboard_operations_pipeline_reflects_activity(client) -> None:
    response = client.get("/api/v1/dashboard/operations")
    assert response.status_code == 200
    pipeline = response.json()["pipeline"]
    # "resolved" should have at least one account after the payment above.
    assert pipeline["resolved"]["count"] >= 1


def test_dashboard_compliance_counts_events(client) -> None:
    response = client.get("/api/v1/dashboard/compliance")
    assert response.status_code == 200
    body = response.json()
    assert body["violations"]["total_30d"] >= 1


def test_dashboard_summary_returns_flat_kpis(client) -> None:
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    # Legacy "tokenization" key must not leak back in.
    assert "tokenization" not in body
    assert {"executive", "operations", "compliance", "alert_count"}.issubset(body)
