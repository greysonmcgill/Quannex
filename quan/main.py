"""Quannex Recovery — FastAPI application entry point.

This is the pilot surface of the collections OS. It exposes four routers:

- ``/api/v1/portfolios`` — portfolio CSV ingestion and listing.
- ``/api/v1/accounts``   — account listing, detail, status, contact, payment.
- ``/api/v1/dashboard``  — operator, executive, and compliance reporting.
- ``/api/v1/recovery``   — agent-assisted actions with compliance guard.

The recovery router is Phase 1 of the autonomous collection system. It wires
the QuannexSupervisor agent to the API with a deterministic ComplianceGuard
kill-switch that blocks non-compliant actions before execution.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from quan.api import accounts_router, dashboard_router, portfolio_router, recovery_router
from quan.config import settings
from quan.database import SessionLocal
from quan.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks for the FastAPI app.

    Intentionally minimal: the pilot does not bootstrap Kafka, Redis, or any
    other optional infrastructure at startup. Optional integrations are wired
    on demand at the call site.
    """

    logger.info(
        "Starting Quannex Recovery API",
        extra={"environment": settings.environment, "debug": settings.debug},
    )
    yield
    logger.info("Shutting down Quannex Recovery API")


app = FastAPI(
    title="Quannex Recovery API",
    description="Collections operating system for small-balance debt portfolios.",
    version="0.1.0",
    lifespan=lifespan,
)


# -- CORS --------------------------------------------------------------------
_dev_modes = {"development", "dev", "local"}
_allow_all = settings.debug or settings.environment.lower() in _dev_modes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Request logging ---------------------------------------------------------
@app.middleware("http")
async def _access_log(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "http_request",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
        },
    )
    return response


# -- Routers -----------------------------------------------------------------
app.include_router(portfolio_router)
app.include_router(accounts_router)
app.include_router(dashboard_router)
app.include_router(recovery_router)


# -- Root / meta -------------------------------------------------------------
@app.get("/", tags=["Meta"])
def root() -> dict[str, str]:
    """Simple service descriptor."""

    return {
        "service": "Quannex Recovery",
        "version": app.version,
        "status": "operational",
    }


# -- Liveness / readiness ----------------------------------------------------
@app.get("/livez", tags=["Meta"])
def livez() -> dict[str, str]:
    """Liveness probe. The process is up and serving HTTP."""

    return {"status": "alive"}


@app.get("/health", tags=["Meta"])
def health() -> dict[str, str]:
    """Backwards-compatible alias for /livez."""

    return {"status": "alive"}


@app.get("/readyz", tags=["Meta"])
def readyz() -> dict[str, object]:
    """Readiness probe. Honest: reports a real database check."""

    checks: dict[str, str] = {}
    ready = True

    # Database: try a real round-trip.
    db_session = SessionLocal()
    try:
        db_session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:  # pragma: no cover - depends on env
        logger.warning("readiness_database_failed", extra={"error": str(exc)})
        checks["database"] = "error"
        ready = False
    finally:
        db_session.close()

    return {"ready": ready, "checks": checks}


@app.get("/ready", tags=["Meta"])
def ready() -> dict[str, object]:
    """Alias for /readyz, retained for dashboards and legacy deployments."""

    return readyz()
