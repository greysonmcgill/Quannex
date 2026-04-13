"""
Database Connection and Session Management

Supports SQLite for local development and PostgreSQL for production.
Uses SQLAlchemy 2.0 async patterns.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from quan.models.database import Base


def get_database_url() -> str:
    """
    Get database URL from environment with SQLite as default.

    Supports:
    - SQLite (default for local dev): sqlite:///quan.db or sqlite+aiosqlite:///quan.db
    - PostgreSQL: postgresql+asyncpg://user:pass@host:port/db
    """
    url = os.getenv("DATABASE_URL", "")

    if not url:
        # Default to SQLite for local development
        db_path = os.getenv("SQLITE_DB_PATH", "quan.db")
        return f"sqlite:///{db_path}"

    # Handle PostgreSQL URL variations
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def get_async_database_url() -> str:
    """Get async-compatible database URL."""
    url = get_database_url()

    if url.startswith("sqlite://"):
        # Convert to aiosqlite for async
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    elif url.startswith("postgresql://"):
        # Convert to asyncpg for async
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+asyncpg://"):
        return url

    return url


def is_sqlite() -> bool:
    """Check if using SQLite database."""
    return "sqlite" in get_database_url()


# Sync engine and session (for Alembic and simple scripts)
_sync_engine: Optional[create_engine] = None
_sync_session_factory: Optional[sessionmaker] = None


def get_sync_engine():
    """Get or create synchronous engine."""
    global _sync_engine
    if _sync_engine is None:
        url = get_database_url()
        connect_args = {}

        if "sqlite" in url:
            connect_args["check_same_thread"] = False

        _sync_engine = create_engine(
            url,
            connect_args=connect_args,
            echo=os.getenv("SQL_DEBUG", "").lower() == "true",
        )
    return _sync_engine


def get_sync_session_factory():
    """Get or create synchronous session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _sync_session_factory


def get_sync_session() -> Session:
    """Get a new synchronous session."""
    return get_sync_session_factory()()


# Async engine and session (for FastAPI)
_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker] = None


def get_async_engine() -> AsyncEngine:
    """Get or create async engine."""
    global _async_engine
    if _async_engine is None:
        url = get_async_database_url()
        connect_args = {}
        poolclass = None

        if "sqlite" in url:
            connect_args["check_same_thread"] = False
            # SQLite needs special handling for async
            poolclass = StaticPool

        kwargs = {
            "echo": os.getenv("SQL_DEBUG", "").lower() == "true",
        }

        if "sqlite" in url:
            kwargs["connect_args"] = connect_args
            kwargs["poolclass"] = poolclass

        _async_engine = create_async_engine(url, **kwargs)
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI endpoints to get database session.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async_session = get_async_session_factory()
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting a database session outside of FastAPI.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(select(Account))
    """
    async_session = get_async_session_factory()
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database - create all tables.

    Call this on application startup.
    """
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync() -> None:
    """
    Initialize database synchronously - for scripts and Alembic.
    """
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)


async def close_db() -> None:
    """
    Close database connections.

    Call this on application shutdown.
    """
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


def close_db_sync() -> None:
    """Close synchronous database connections."""
    global _sync_engine, _sync_session_factory
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None


async def check_db_connection() -> bool:
    """Check if database connection is healthy."""
    try:
        async with get_db_context() as db:
            await db.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


def check_db_connection_sync() -> bool:
    """Check database connection synchronously."""
    try:
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


# Reset functions for testing
def reset_engines() -> None:
    """Reset all engine instances (for testing)."""
    global _sync_engine, _sync_session_factory, _async_engine, _async_session_factory
    close_db_sync()
    _sync_engine = None
    _sync_session_factory = None
    _async_engine = None
    _async_session_factory = None
