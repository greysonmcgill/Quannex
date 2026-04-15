# Quannex Recovery

**Collections operating system for small-balance debt portfolios.**

Quannex is a pilot-ready collections platform for creditors, servicers, and
debt collectors working fragmented, small-balance receivables — BNPL,
micro-loans, utilities, telecom, subscriptions, small medical, rent tail.
It handles the operational loop end to end:

1. **Ingest** a portfolio from CSV with row-level validation.
2. **Prioritize** accounts with an intelligence engine (recovery probability,
   optimal channels, settlement threshold).
3. **Work** accounts through a named pipeline (`ingested → enriched → scored →
   contacted → negotiating → payment_pending → resolved`).
4. **Evidence compliance** on every touch (compliant flag, compliance events,
   state-aware reporting).
5. **Report** operationally (pipeline, channels, queues, throughput) and
   executively (revenue, recovery rate, cost per dollar collected).

## Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.x, Alembic.
- **Databases**: SQLite for local development, PostgreSQL for production.
- **Dashboard**: Next.js 14, TypeScript, Tailwind.
- **Intelligence**: NumPy / scikit-learn / NetworkX. No heavy ML stack.

## Quick start

### 1. Native local dev

```bash
python3 -m pip install -e ".[dev]"
cd dashboard && npm install && cd ..

alembic upgrade head
python3 scripts/seed_data.py --reset        # seeds ~1000 accounts by default

make api        # FastAPI on :8000
make frontend   # Next.js on :3000
make dev        # both
```

### 2. Docker (API on SQLite)

```bash
docker compose -f docker-compose.dev.yaml up --build
```

API binds to `http://localhost:8000` with data persisted at `./data/quan.db`.

### 3. Docker (production-ish: API + Postgres + dashboard)

```bash
docker compose up --build
```

Only the three services the pilot actually needs: `api`, `postgres`, and
`dashboard`. No Kafka, Redis, Prometheus, or Grafana in the default stack.
Install optional extras explicitly when you need them:

```bash
pip install -e ".[postgres,payments,cache,metrics]"
```

## Canonical API

All endpoints are live in `quan.main:app`.

### Meta
- `GET /` — service descriptor
- `GET /livez` — liveness probe (process up)
- `GET /readyz` — readiness probe (real DB `SELECT 1`)
- `GET /health`, `GET /ready` — legacy aliases

### Portfolios
- `POST /api/v1/portfolios/upload` — CSV portfolio import + auto-scoring

### Accounts
- `GET  /api/v1/accounts` — paginated list with filters (`status`, `debt_type`, `state`, `search`)
- `GET  /api/v1/accounts/{account_id}` — full account detail including contact history, payments, compliance events
- `PUT  /api/v1/accounts/{account_id}/status` — workflow transition
- `POST /api/v1/accounts/{account_id}/contact` — log a contact attempt (updates rollups; non-compliant attempts emit a compliance event)
- `POST /api/v1/accounts/{account_id}/payment` — record a payment (updates `balance`, `total_paid`, `last_payment_at`; resolves the account on full payment)

### Dashboard
- `GET /api/v1/dashboard/` — full executive + operations + compliance + health + alerts payload
- `GET /api/v1/dashboard/executive`
- `GET /api/v1/dashboard/operations`
- `GET /api/v1/dashboard/compliance`
- `GET /api/v1/dashboard/health`, `/alerts`
- `GET /api/v1/dashboard/pipeline`, `/channels`, `/queues`, `/violations`
- `GET /api/v1/dashboard/summary` — flat KPI cards payload
- `WS  /api/v1/dashboard/ws` — live heartbeat

## CSV upload format

```text
account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email
```

Supported `debt_type` values: `bnpl`, `medical`, `telecom`, `subscription`,
`utility`, `credit_card`, `bank`, `personal_loan`, `auto`, `rent`.

## Canonical domain model

| Entity           | Key columns                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| `Portfolio`      | `portfolio_id`, `name`, `source_filename`, `debt_mix`, `uploaded_count`, `valid_count`, `rejected_count` |
| `Account`        | `account_id`, `portfolio_id`, `debtor_name`, `balance`, `original_balance`, `debt_type`, `state`, `status`, `recovery_probability`, `optimal_channels`, `settlement_threshold`, `total_paid`, `total_contact_attempts`, `last_contact_at`, `last_payment_at` |
| `ContactAttempt` | `attempt_id`, `account_db_id`, `channel`, `outcome`, `compliant`, `cost`, `attempted_at`              |
| `Payment`        | `payment_id`, `account_db_id`, `amount`, `method`, `status`, `recorded_at`                            |
| `ComplianceEvent`| `event_id`, `account_db_id`, `event_type`, `severity`, `message`, `resolution`, `resolved`, `state`, `occurred_at` |
| `Campaign`       | `campaign_id`, `portfolio_id`, `name`, `status`, `stage`, `metadata_json`                             |

All field names are used consistently across the ORM, the Pydantic schemas,
the API responses, the dashboard TypeScript types, and the tests.

## Make targets

| Target           | What it does                             |
| ---------------- | ---------------------------------------- |
| `make dev`       | API + dashboard                          |
| `make api`       | FastAPI only                             |
| `make frontend`  | Next.js dashboard only                   |
| `make migrate`   | `alembic upgrade head`                   |
| `make seed`      | reset and seed 1,000 realistic accounts  |
| `make test`      | pytest with coverage                     |
| `make lint`      | ruff + mypy                              |
| `make install`   | install dev dependencies                 |

## Testing

```bash
pytest tests/
```

The integration suite (`tests/integration/test_api.py`) exercises the full
pilot flow: health probes, CSV upload, account list / detail / status
transition, contact logging, payment recording, compliance event emission,
and dashboard KPIs.

## Repository layout

```
quan/
├── main.py                    FastAPI app entry point
├── config.py                  pydantic-settings
├── database.py                engine + SessionLocal + init_database
├── logging_config.py          structured logging
├── models/database.py         canonical ORM (Portfolio, Account, ...)
├── api/                       routers (portfolio, accounts, dashboard)
├── analytics/                 live dashboard aggregations
└── intelligence/              scoring engine (CollectionIntelligence)

alembic/                       database migrations
dashboard/                     Next.js operator UI
scripts/                       seed + deploy scripts
tests/                         pytest suite
docs/                          product + refactor docs
experimental/                  research / non-core modules (see README)
```

## Further reading

- `docs/CORE_PRODUCT_REFOCUS_PLAN.md` — the active refocus plan.
- `docs/REFOCUS_CHANGELOG.md` — what was removed, standardized, and isolated.
- `experimental/README.md` — inventory of out-of-path research modules.

## License

Proprietary. All rights reserved.
