# QUAN Recovery

AI-powered micro-debt collection platform with a real SQLite-backed operational layer for local development.

## What Layer 1 Includes

- SQLAlchemy models for portfolios, accounts, campaigns, payments, contact attempts, and compliance events
- Alembic migrations for the operational backend
- CSV portfolio upload with row validation and account auto-scoring
- Real dashboard APIs backed by database queries instead of mock payloads
- Account listing, detail, status updates, contact logging, and payment recording
- Seed script that generates 1,000 realistic accounts across multiple debt types
- Next.js dashboard pages for upload, accounts, and account detail

## Quick Start

### Option 1: Native local dev

```bash
python3 -m pip install -e ".[dev]"
cd dashboard && npm install && cd ..
alembic upgrade head
python3 scripts/seed_data.py --reset
make dev
```

This starts:

- FastAPI backend on `http://localhost:8000`
- Next.js dashboard on `http://localhost:3000`

### Option 2: Docker for the API only

```bash
docker compose -f docker-compose.dev.yaml up --build
```

This runs the API with SQLite persisted at `./data/quan.db`.

## Core Commands

```bash
make migrate   # Run Alembic migrations
make seed      # Reset and seed 1,000 test accounts
make api       # Start only the FastAPI backend
make frontend  # Start only the dashboard
make dev       # Start backend + frontend together
```

## CSV Upload Format

Upload portfolios to `POST /api/v1/portfolios/upload` with these columns:

```text
account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email
```

Supported `debt_type` values:

- `bnpl`
- `medical`
- `telecom`
- `subscription`
- `utility`
- `credit_card`
- `bank`
- `personal_loan`
- `auto`
- `rent`

## Operational APIs

- `POST /api/v1/portfolios/upload`
- `GET /api/v1/accounts`
- `GET /api/v1/accounts/{account_id}`
- `PUT /api/v1/accounts/{account_id}/status`
- `POST /api/v1/accounts/{account_id}/contact`
- `POST /api/v1/accounts/{account_id}/payment`
- `GET /api/v1/dashboard/`
- `GET /api/v1/dashboard/executive`
- `GET /api/v1/dashboard/operations`
- `GET /api/v1/dashboard/compliance`

## Notes

- Local development defaults to SQLite via `DATABASE_URL=sqlite:///./quan.db`
- Production can switch to PostgreSQL by overriding `DATABASE_URL`
- The legacy simulation and research modules remain in place; the new operational backend is additive
