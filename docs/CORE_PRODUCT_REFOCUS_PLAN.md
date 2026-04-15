# QUAN Recovery — Core Product Refocus Plan

**Date:** 2026-04-15
**Status:** Active refactor
**Target:** Pilot-ready collections operating system for small-balance debt.

---

## 1. Problem statement

The repository has drifted. The product narrative ("AI-powered micro-debt collection platform") is
sound, but the implementation has acquired speculative layers that blur the pilot story:

- Two parallel schemas (Layer 1 simplified vs. original "platform" ORM) live in the tree.
  The wired API references fields that do not exist on the wired ORM. The app is effectively
  broken when you run it end-to-end.
- Two `portfolio` routers (`portfolio_router.py`, `portfolios_router.py`) share the same URL
  prefix, one sync and one async.
- The dashboard carries a full "tokenization / tranches / investors / secondary market"
  surface that is not required for any pilot collections operator.
- Main runtime imports speculative modules (`quan.ingestion` with Kafka producer bootstrapping,
  root-level `/api/v1/analyze`, `/api/v1/campaigns`, `/api/v1/settlements`, `/api/v1/payments`
  endpoints that bypass persistence entirely).
- `/ready` returns hardcoded `True` for database / Kafka / Redis with comments saying "would
  check actual connection."
- `pyproject.toml` pulls in PyTorch, Transformers, Apache Beam, Kafka, Ray, Prefect, Twilio,
  SendGrid, Google Cloud, etc. — implying a platform the repo does not ship.
- Non-core runtime modules exist in `quan/`: `shadow_bureau/`, `quantum/`, `finance/tokenization.py`,
  simulation engines sized for 1M+ account stress tests.

## 2. Target product

Quannex is a **collections operating system** for small-balance, fragmented receivables
(BNPL, micro-loans, utilities, telecom, subscriptions, small medical, rent tail).

### Core jobs it does

1. **Ingest** a portfolio (CSV upload, validation, auto-scoring).
2. **Prioritize** accounts (recovery probability, debt type, days past due, state).
3. **Work** accounts (status transitions, contact attempts, payment recording).
4. **Enforce & evidence compliance** (compliant flag per attempt, compliance events,
   state-aware reporting).
5. **Report** operationally (pipeline, channels, queues, throughput) and executively
   (revenue, recovery rate, cost per dollar collected).

### Core entities (canonical domain model)

- `Portfolio` — a single upload / creditor batch.
- `Account` — one debtor obligation.
- `ContactAttempt` — one outreach instance.
- `Payment` — one monetary transaction.
- `ComplianceEvent` — one audit-relevant fact.
- `Campaign` — grouping for reporting (kept, optional for pilot).

### Canonical field naming (applied across ORM, schemas, routers, dashboard)

| Concept                     | Canonical field            |
| --------------------------- | -------------------------- |
| Internal DB PK              | `id` (int, autoincrement)  |
| External account identifier | `account_id` (string)      |
| External portfolio ID       | `portfolio_id` (UUID str)  |
| External attempt ID         | `attempt_id` (UUID str)    |
| External payment ID         | `payment_id` (UUID str)    |
| External event ID           | `event_id` (UUID str)      |
| Current balance             | `balance`                  |
| Original face value         | `original_balance`         |
| Lifetime payments           | `total_paid`               |
| Outreach count on account   | `total_contact_attempts`   |
| Latest outreach timestamp   | `last_contact_at`          |
| Latest payment timestamp    | `last_payment_at`          |
| FK from attempt/payment/event → account | `account_db_id` |
| Attempt timestamp           | `attempted_at`             |
| Payment timestamp           | `recorded_at`              |
| Event timestamp             | `occurred_at`              |

This matches the Layer 1 migration (`20260412_0001_layer1_backend_tables.py`) and the
Next.js frontend contracts. The older "platform" ORM (`current_balance`, `total_payments`,
`contact_attempts` counter-plus-relationship, `last_contact_date`) is removed.

## 3. Actions in this refactor

### A. Schema & ORM
- Rewrite `quan/models/database.py` to the canonical Layer 1 model.
- Delete the conflicting initial migration `20260413_0001_001_initial_schema.py`.
- Keep `20260412_0001_layer1_backend_tables.py` as the head.
- Fix the latent `contact_attempts` column/relationship shadow bug by renaming the
  relationship to `contact_attempt_history` and keeping the integer counter as
  `total_contact_attempts`.

### B. API surface
- Delete `quan/api/portfolios_router.py` (duplicate, wrong schema, async mismatch).
- Delete `quan/api/dashboard_service.py` (duplicate of `quan/analytics/live_dashboard.py`).
- Keep the canonical triad:
  - `quan/api/portfolio_router.py` → `/api/v1/portfolios` (upload, list, detail, delete).
  - `quan/api/accounts_router.py` → `/api/v1/accounts` (list, detail, status, contact, payment).
  - `quan/api/dashboard_router.py` → `/api/v1/dashboard` (overview, executive, operations, compliance, health, alerts, summary).
- Remove speculative top-level endpoints from `quan/main.py`:
  `/api/v1/analyze`, `/api/v1/campaigns`, `/api/v1/settlements`, `/api/v1/payments`,
  `/api/v1/business-plan/download`.
- Remove `/api/v1/dashboard/tokenization`, `/pools`, `/investors` endpoints.
- Drop `from quan.ingestion import ingestion_router` and `KafkaProducerClient` lifespan
  bootstrap from `main.py`.

### C. Health & readiness
- `/livez` — simple liveness.
- `/readyz` — real check (DB `SELECT 1`).
- `/health` — alias of `/livez` for backwards compatibility.
- `/ready` — alias of `/readyz`, but runs a real DB ping.

### D. Dashboard frontend
- Delete `dashboard/src/app/tokenization/page.tsx`.
- Remove `Tokenization` link from sidebar.
- Remove `TokenizationData` / `Pool` / `Tranche` / `Investor` / `SecondaryMarket` types
  from `dashboard/src/lib/api.ts`.
- Remove `tokenization` fields from dashboard overview page consumption.
- Keep executive page but strip speculative ROI / margin narrative where it appears.

### E. Dependencies
Drop from runtime `pyproject.toml`:
- `torch`, `transformers`, `apache-beam`,
- `google-cloud-bigquery`, `google-cloud-texttospeech`,
- `confluent-kafka`,
- `ray`, `prefect`, `celery`,
- `twilio`, `sendgrid`,
- `networkx`.

Keep (pilot-honest stack):
- `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `python-multipart`, `email-validator`,
- `sqlalchemy`, `alembic`, `psycopg2-binary` (prod), sqlite (stdlib),
- `numpy`, `pandas`, `scikit-learn` (used by `quan.intelligence`),
- `httpx`, `tenacity`, `cryptography`, `python-json-logger`,
- `prometheus-client` (light metrics, optional path),
- `stripe` (payment processor interface, honest),
- `redis` — **moved to optional `[cache]` extra**.

### F. Non-core modules
Kept in-tree but **not imported by the runtime** (already the case; we explicitly confirm):
- `quan/shadow_bureau/`, `quan/quantum/`, `quan/finance/tokenization.py`,
- `quan/simulation/`, `quan/backtest/`, `quan/semantic/`, `quan/orchestration/`,
- `quan/agents/`, `quan/mlops/` (large ML ops surface),
- root-level simulation scripts (`run_bnpl_1m_simulation.py`, `run_perpetual_simulation.py`,
  `run_full_scale.py`, `run_advanced_calibration.py`, `test_agentic.py`,
  `test_quannex_agent.py`, `build_business_plan.py`, `generate_business_plan.py`,
  `generate_thesis_pdf.py`).

They are moved into `experimental/` at the repo root so the main tree becomes obviously
pilot-focused, without destroying research. A stub `experimental/README.md` explains scope.

### G. Tests
- Rewrite `tests/integration/test_api.py` to use the canonical API surface (no
  `/api/v1/analyze`, no `/api/v1/settlements`; use portfolios/accounts/dashboard only).
- Drop assertions that depend on deleted endpoints.
- Keep existing unit tests (`tests/unit/*`) where they test the intelligence engine
  directly against the in-memory interface.
- Add a focused pilot-flow test: seed → list accounts → log contact → record payment →
  dashboard reflects activity.

### H. Scripts & Makefile
- `scripts/seed_data.py` is aligned with the canonical schema (already correct);
  leave in place.
- Trim `Makefile` to: `dev`, `api`, `frontend`, `migrate`, `seed`, `test`, `lint`,
  `install`. Remove `status` (redundant).
- Remove root-level simulation scripts from the main tree; move under `experimental/`.

### I. Config & security defaults
- `.env.example` already documents dev-safe defaults (SQLite). Keep.
- In `quan/config.py` ensure production defaults are not insecure: `DEBUG=false`,
  `ALLOWED_ORIGINS` explicit, no hardcoded secrets. (Verify and fix if needed.)

### J. Docs
- Rewrite `README.md` to reflect the collections-OS product scope, the canonical domain
  model, how to run locally, and the Layer 1 backend.
- Author `docs/REFOCUS_CHANGELOG.md` summarizing removed / isolated / standardized items.

## 4. Out of scope for this pass

- Agent orchestration (`quan/agents/*`, `quan/orchestration/*`) — left in tree, not wired.
- Real payment-processor integration (Stripe path stays interface-only).
- WebSocket broadcast hardening (the existing endpoint is preserved but not expanded).
- Feature-flag framework for experimental modules.
- Migration consolidation of the Layer 1 schema into multiple purpose-specific files.

## 5. Definition of done (this pass)

1. `uvicorn quan.main:app` imports cleanly with the slimmed runtime.
2. `alembic upgrade head` applies one consistent schema.
3. `python3 scripts/seed_data.py --reset` succeeds.
4. `pytest tests/` passes (updated suite).
5. Dashboard has no tokenization/investor surface in primary navigation.
6. README and `REFOCUS_CHANGELOG.md` explain what changed and what remains.
