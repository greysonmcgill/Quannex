"""Shared pytest fixtures for Quannex integration tests.

Key responsibility: point the app at an ephemeral SQLite database **before**
any ``quan.*`` module is imported, so that every router, service, and ORM
table binds to the test database for the duration of the test session.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

# --- Isolate the database. Must run before any quan.* import. ---------------
_TMP_DB = tempfile.NamedTemporaryFile(suffix="-quannex-tests.db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="session", autouse=True)
def _initialize_database() -> Iterator[None]:
    """Create all ORM tables once per test session and clean up after."""

    from quan.database import init_database

    init_database()
    yield
    Path(_TMP_DB.name).unlink(missing_ok=True)


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient bound to the isolated database."""

    from fastapi.testclient import TestClient
    from quan.main import app

    with TestClient(app) as test_client:
        yield test_client


def pytest_configure(config):
    """Register custom markers used by integration tests."""

    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
