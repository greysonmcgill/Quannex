# Quannex Refocus Changelog

**Date:** 2026-04-15

This changelog summarizes the refactor that narrows Quannex to a pilot-ready
collections operating system for small-balance debt. See
`docs/CORE_PRODUCT_REFOCUS_PLAN.md` for the accompanying plan.

## Removed

- **Tokenization dashboard surface** — server builders, REST endpoints, Next.js
  route, sidebar link, TypeScript interfaces, empty-state factories, and helper
  components.
  - `build_tokenization_snapshot()` (from `quan/analytics/live_dashboard.py`)
  - `GET /api/v1/dashboard/tokenization`, `/pools`, `/investors` (from `quan/api/dashboard_router.py`)
  - `dashboard/src/app/tokenization/page.tsx`
  - `dashboard/src/components/dashboard/pool-table.tsx`, `tranche-chart.tsx`
  - `TokenizationData`, `PortfolioSummary`, `Pool`, `TrancheData`,
    `InvestorMetrics`, `SecondaryMarket`, `Trade`, `createEmptyTokenizationData()` (from `dashboard/src/lib/api.ts`)
- **Speculative top-level API endpoints that bypassed persistence**:
  `POST /api/v1/analyze`, `POST /api/v1/campaigns`, `GET /api/v1/campaigns/{id}`,
  `POST /api/v1/settlements`, `POST /api/v1/payments`,
  `GET /api/v1/business-plan/download`.
- **Kafka lifespan bootstrap** in `quan/main.py`.
- **Conflicting initial Alembic migration** `20260413_0001_001_initial_schema.py`
  (it defined a second, incompatible schema and collided with the Layer 1 head).
- **Duplicate routers and services**:
  - `quan/api/portfolios_router.py` — async duplicate of `portfolio_router.py`
    using the wrong schema; never wired.
  - `quan/api/dashboard_service.py` — duplicate of `quan/analytics/live_dashboard.py`
    using the pre-drift ORM names.
- **Dead API surface**: `quan/api/gateway.py` (~2,700 lines of alternate FastAPI
  app with Shadow Bureau, Tokenization, Plans, Webhooks, etc.) — never imported
  by the runtime. Moved to `experimental/api_gateway_legacy.py`.
- **Legacy navigation** ("Tokenization") and branding refresh (Quannex /
  "Collections OS" in the sidebar footer).

## Isolated (moved out of default path, not destroyed)

- `experimental/scripts/`:
  `run_advanced_calibration.py`, `run_bnpl_1m_simulation.py`,
  `run_calibration.py`, `run_collections_test.py`, `run_full_scale.py`,
  `run_lifecycle_backtest.py`, `run_perpetual_simulation.py`, `run_sub1k.py`,
  `test_agentic.py`, `test_quannex_agent.py`,
  `build_business_plan.py`, `generate_business_plan.py`,
  `generate_thesis_pdf.py`.
- `experimental/business_plan_generator/`, `mlflow-artifacts/`,
  `model-registry/`, `output/`.
- `experimental/PERFORMANCE_REVIEW.md`, `experimental/QUAN_Systemic_Thesis.pdf`.
- `experimental/tests/` — legacy integration/unit tests that exercised the
  Shadow Bureau, tokenization, stress / economics suites. Not run by the
  default `pytest` invocation.
- In-tree Python packages that remain under `quan/` but are not on the
  product path (documented in `experimental/README.md`):
  `quan/shadow_bureau/`, `quan/quantum/`, `quan/finance/`, `quan/simulation/`,
  `quan/backtest/`, `quan/semantic/`, `quan/mlops/`, `quan/agents/`,
  `quan/orchestration/`, `quan/optimization/`, `quan/integration/`,
  `quan/reporting/`, `quan/risk/`.

## Standardized

- **Canonical ORM** in `quan/models/database.py` matches the Layer 1 Alembic
  migration (`20260412_0001_layer1_backend_tables.py`), the routers, the
  analytics aggregator, and the Next.js dashboard types. Canonical fields:
  - `Account.balance`, `Account.original_balance`, `Account.total_paid`,
    `Account.total_contact_attempts`, `Account.last_contact_at`,
    `Account.last_payment_at`, `Account.account_id`.
  - `ContactAttempt.attempt_id`, `ContactAttempt.account_db_id`,
    `ContactAttempt.compliant`, `ContactAttempt.attempted_at`.
  - `Payment.payment_id`, `Payment.account_db_id`, `Payment.method`,
    `Payment.recorded_at`.
  - `ComplianceEvent.event_id`, `ComplianceEvent.account_db_id`,
    `ComplianceEvent.message`, `ComplianceEvent.resolved`,
    `ComplianceEvent.occurred_at`, `ComplianceEvent.metadata_json`.
  - `Portfolio.portfolio_id`, `Portfolio.source_filename`, `Portfolio.debt_mix`,
    `Portfolio.uploaded_count`, `Portfolio.valid_count`,
    `Portfolio.rejected_count`.
- **Resolved relationship/column name collision** on `Account`: the integer
  counter is `total_contact_attempts`; the ORM relationship is
  `contact_attempts` (and no longer shadows a column of the same name).
- **Single Alembic head**: `20260412_0001_layer1_backend_tables` is now the
  only initial migration; `alembic upgrade head` applies one schema cleanly
  on SQLite and PostgreSQL.
- **Health & readiness are honest**:
  - `GET /livez` — simple liveness.
  - `GET /readyz` — runs `SELECT 1` against the database. No more hardcoded
    `True` for "database", "kafka", "redis".
  - `GET /health`, `GET /ready` — kept as aliases for backwards compatibility.
- **CORS / config**: `Settings.allowed_origins` is explicit, and `secret_key`
  fails loudly outside of development environments if not set.
- **Dashboard TypeScript types** deduplicated: the second set of
  `AccountDetail`, `AccountListItem`, `PortfolioResponse`, etc. that carried
  the pre-drift names has been removed in favour of the single canonical
  definitions.

## Dependencies

Dropped from runtime `pyproject.toml`:

- `torch`, `transformers`, `apache-beam`,
- `google-cloud-bigquery`, `google-cloud-texttospeech`,
- `confluent-kafka`, `ray`, `prefect`, `celery`,
- `twilio`, `sendgrid`,
- `asyncpg`, `opentelemetry-api`, `opentelemetry-sdk`,
- `redis` (moved to an optional `[cache]` extra),
- `prometheus-client` (moved to an optional `[metrics]` extra),
- `stripe` (moved to an optional `[payments]` extra),
- `psycopg2-binary` (introduced as `[postgres]` optional extra; Postgres
  deployments install it explicitly).

Kept in runtime:

- `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`,
  `python-multipart`, `email-validator`,
- `sqlalchemy`, `alembic`,
- `numpy`, `pandas`, `scikit-learn`, `networkx`,
- `httpx`, `tenacity`, `cryptography`, `python-json-logger`.

`pytest-xdist` and `pre-commit` were removed from the dev extras (not used by
the default test invocation); keep adding them back per developer if wanted.

## Infrastructure

- `docker-compose.yaml` trimmed to `api` + `postgres` + `dashboard`. Kafka,
  Zookeeper, Redis, Prometheus, and Grafana are no longer started by default.
- `docker-compose.dev.yaml` still boots the API on SQLite for developers.
- Dockerfile healthcheck now hits `/livez` instead of `/health`.

## Tests

- `tests/integration/test_api.py` rewritten to assert the canonical pilot
  surface: 18 tests covering health, portfolio upload, accounts CRUD, contact
  logging, payment recording, compliance event emission, and dashboard
  payloads.
- `tests/integration/conftest.py` trimmed from a multi-hundred-line mock
  factory down to a small fixture module that binds an isolated SQLite
  database for the session.
- Stale tests referencing Shadow Bureau, tokenization, economics, multi-agent,
  stress, payment-processor wiring, debt lifecycle, and the quantum alias
  were moved under `experimental/tests/` and are no longer collected by the
  default `pytest` run.
- `tests/unit/test_collection_intelligence.py` retained — it tests the engine
  used by `portfolio_router`.

## What remains for later phases

- Authentication / tenant isolation at the API boundary.
- Real Stripe wiring for payment capture (interface-only today).
- Consolidating the Layer 1 migration into purpose-specific migrations once
  the schema evolves past pilot.
- Feature flags or lightweight extension points for re-activating specific
  experimental modules (Shadow Bureau, MLOps, simulation) if a pilot requires
  them.
- End-to-end dashboard smoke tests (Playwright / Cypress) against the live
  FastAPI + Next.js pair.
