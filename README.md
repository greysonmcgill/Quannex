# QUAN Recovery

AI-Powered Micro-Debt Collection Platform

## Overview

QUAN Recovery is an intelligent debt collection platform that uses AI/ML to optimize recovery strategies for micro-debts (under $1,000). The platform handles portfolio ingestion, account management, contact orchestration, payment processing, and compliance monitoring.

## Quick Start

The easiest way to get started is using the development script:

```bash
# Install dependencies and start everything
make install
make dev-seed
```

This will:
1. Install Python and Node.js dependencies
2. Initialize SQLite database
3. Seed 1,000 realistic test accounts
4. Start API server on http://localhost:8000
5. Start dashboard on http://localhost:3000

## Manual Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/quan-recovery.git
cd quan-recovery

# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd dashboard && npm install && cd ..
```

### Database Setup

By default, QUAN uses SQLite for local development (no external dependencies).

```bash
# Initialize database (creates tables)
python -c "from quan.database import init_db_sync; init_db_sync()"

# Or run migrations
alembic upgrade head

# Seed with test data (1,000 accounts)
python scripts/seed_data.py --count 1000

# Reset and reseed
python scripts/seed_data.py --reset --count 1000
```

For production, set `DATABASE_URL` to use PostgreSQL:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/quan"
```

### Running the Application

**Start both API and Dashboard:**
```bash
./scripts/dev.sh
```

**Or start separately:**
```bash
# Terminal 1 - API Server
python -m uvicorn quan.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Dashboard
cd dashboard && npm run dev
```

**Or use Docker:**
```bash
docker-compose -f docker-compose.dev.yaml up
```

### Accessing the Application

- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Features

### Portfolio Ingestion
Upload CSV files containing debt accounts. The system validates data, auto-scores accounts using AI, and stores them in the database.

**Dashboard**: Navigate to `/upload` to upload a CSV file.

**API**: `POST /api/v1/portfolios/upload`

CSV format:
```csv
account_id,debtor_name,balance,original_creditor,debt_type,days_past_due,state,phone,email
ACC-001,John Smith,456.78,QuickCash,payday,45,CA,555-123-4567,john@email.com
```

### Account Management
View, search, filter, and manage individual accounts.

**Dashboard**: Navigate to `/accounts` for account list, click an account for details.

**API Endpoints**:
- `GET /api/v1/accounts` - List accounts with filtering
- `GET /api/v1/accounts/{id}` - Get account details
- `PUT /api/v1/accounts/{id}/status` - Update account status
- `POST /api/v1/accounts/{id}/contact` - Log contact attempt
- `POST /api/v1/accounts/{id}/payment` - Record payment

### Dashboard Analytics
Real-time dashboard showing:
- Executive KPIs (revenue, recovery rate, ROI)
- Operations metrics (pipeline stages, channel performance)
- Compliance monitoring (violations, audit readiness)
- Tokenization portfolio (for securitization)

**Dashboard**: Navigate to `/` for overview, or specific sections.

**API**: `GET /api/v1/dashboard/` returns all dashboard data.

### AI Intelligence
Each account is automatically scored on ingestion:
- **Recovery Probability**: Likelihood of successful collection
- **Optimal Channels**: Best communication channels (SMS, email, mail)
- **Settlement Threshold**: Recommended settlement percentage

## Project Structure

```
quan/
├── api/                    # FastAPI routers
│   ├── accounts_router.py  # Account CRUD endpoints
│   ├── portfolios_router.py # Portfolio upload
│   ├── dashboard_router.py # Dashboard endpoints
│   └── dashboard_service.py # Database-backed metrics
├── models/
│   ├── database.py         # SQLAlchemy models
│   └── micro_loan_universe.py # Debt type profiles
├── intelligence/
│   └── engine.py           # AI scoring engine
├── database.py             # Database connection
├── main.py                 # FastAPI application
└── config.py               # Settings

dashboard/                  # Next.js frontend
├── src/
│   ├── app/
│   │   ├── accounts/       # Account list & detail pages
│   │   ├── upload/         # Portfolio upload page
│   │   └── ...             # Other dashboard pages
│   ├── components/         # React components
│   └── lib/
│       └── api.ts          # API client

scripts/
├── dev.sh                  # Development launcher
└── seed_data.py            # Database seeding

alembic/                    # Database migrations
```

## API Reference

### Dashboard Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/dashboard/ | Full dashboard data |
| GET | /api/v1/dashboard/executive | Executive KPIs |
| GET | /api/v1/dashboard/operations | Operations metrics |
| GET | /api/v1/dashboard/compliance | Compliance status |
| GET | /api/v1/dashboard/summary | Summary statistics |

### Account Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/accounts | List accounts (paginated) |
| GET | /api/v1/accounts/stats | Aggregate statistics |
| GET | /api/v1/accounts/{id} | Account details |
| PUT | /api/v1/accounts/{id}/status | Update status |
| POST | /api/v1/accounts/{id}/contact | Log contact |
| POST | /api/v1/accounts/{id}/payment | Record payment |

### Portfolio Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/portfolios/upload | Upload CSV |
| GET | /api/v1/portfolios | List portfolios |
| GET | /api/v1/portfolios/{id} | Portfolio details |
| DELETE | /api/v1/portfolios/{id} | Delete portfolio |

## Development

### Running Tests
```bash
pytest tests/ -v
```

### Linting
```bash
ruff check quan/
mypy quan/ --ignore-missing-imports
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///quan.db | Database connection string |
| ENVIRONMENT | development | Environment name |
| DEBUG | false | Enable debug mode |
| SQL_DEBUG | false | Log SQL queries |
| NEXT_PUBLIC_API_URL | http://localhost:8000 | API URL for frontend |

## Production Deployment

For production, use PostgreSQL and proper infrastructure:

```bash
# Set production database
export DATABASE_URL="postgresql+asyncpg://user:pass@db.example.com:5432/quan"

# Run migrations
alembic upgrade head

# Start with gunicorn
gunicorn quan.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

See `docker-compose.yaml` for full production setup with PostgreSQL, Redis, Kafka, and monitoring.

## License

Proprietary - All Rights Reserved
