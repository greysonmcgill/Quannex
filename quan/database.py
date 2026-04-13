"""Database engine and session helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from quan.config import settings
from quan.models.database import Base


def _normalize_database_url(raw_url: str) -> str:
    """Normalize DATABASE_URL values for local SQLite development."""

    if not raw_url:
        raw_url = "sqlite:///./quan.db"

    if raw_url.startswith("sqlite:///"):
        db_path = raw_url.replace("sqlite:///", "", 1)
        if db_path and db_path not in {":memory:", ""}:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    return raw_url


DATABASE_URL = _normalize_database_url(settings.database_url)
CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=CONNECT_ARGS,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_database() -> None:
    """Create tables for environments that do not run Alembic."""

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
