"""Unit tests for quan.finance.collections_bridge.

Unit-level analogue of the integration-suite database isolation: an
in-memory SQLite engine with tables created straight from
``Base.metadata.create_all`` — no FastAPI, no app wiring, no network.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quan.finance.collections_bridge import CollectionsBridge, EpochCollections
from quan.models.database import Account, Base, Payment, Portfolio

# --- Fixed epoch window used throughout (half-open: [start, end)) -----------
PERIOD_START = datetime(2026, 6, 1, 0, 0, 0)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0)
IN_WINDOW = datetime(2026, 6, 15, 12, 0, 0)

POOL = "POOL-BNPL-2026Q2"
OTHER_POOL = "POOL-MEDICAL-2026Q2"


@pytest.fixture()
def session():
    """Fresh in-memory SQLite database per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def bridge(session):
    return CollectionsBridge(session)


def make_account(session, account_id: str, pool_id: str | None) -> Account:
    portfolio = session.query(Portfolio).first()
    if portfolio is None:
        portfolio = Portfolio(portfolio_id=str(uuid.uuid4()), name="Test Portfolio")
        session.add(portfolio)
        session.flush()
    account = Account(
        account_id=account_id,
        portfolio_id=portfolio.id,
        debtor_name=f"Debtor {account_id}",
        state="TX",
        original_creditor="Acme Lending",
        debt_type="bnpl",
        balance=Decimal("500.00"),
        original_balance=Decimal("500.00"),
        pool_id=pool_id,
    )
    session.add(account)
    session.flush()
    return account


def make_payment(
    session,
    account: Account,
    amount: str,
    *,
    method: str = "card",
    status: str = "completed",
    notes: str | None = None,
    recorded_at: datetime = IN_WINDOW,
) -> Payment:
    payment = Payment(
        payment_id=str(uuid.uuid4()),
        account_db_id=account.id,
        amount=Decimal(amount),
        method=method,
        status=status,
        notes=notes,
        recorded_at=recorded_at,
    )
    session.add(payment)
    session.flush()
    return payment


class StubPlatform:
    """Duck-typed stand-in for RWATokenizationPlatform.run_epoch."""

    def __init__(self, result: dict | None = None):
        self.calls: list[dict] = []
        self.result = result if result is not None else {"epoch": 1, "nav": "1.00"}

    def run_epoch(self, pool_id, collections, recoveries):
        self.calls.append(
            {"pool_id": pool_id, "collections": collections, "recoveries": recoveries}
        )
        return self.result


# ---------------------------------------------------------------- aggregation


def test_aggregate_sums_completed_payments_for_pool(session, bridge):
    acct = make_account(session, "ACC-001", POOL)
    make_payment(session, acct, "100.00")
    make_payment(session, acct, "50.25")
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("150.25")
    assert result.recoveries == Decimal("0.00")
    assert result.payment_count == 2
    assert result.account_count == 1
    assert result.pool_id == POOL


def test_payments_outside_window_excluded(session, bridge):
    acct = make_account(session, "ACC-002", POOL)
    make_payment(session, acct, "100.00")  # in window
    make_payment(session, acct, "40.00", recorded_at=PERIOD_START - timedelta(seconds=1))
    make_payment(session, acct, "60.00", recorded_at=PERIOD_END)  # half-open: excluded
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("100.00")
    assert result.payment_count == 1


def test_window_start_is_inclusive(session, bridge):
    acct = make_account(session, "ACC-003", POOL)
    make_payment(session, acct, "75.00", recorded_at=PERIOD_START)
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("75.00")


def test_other_pools_and_unpooled_accounts_excluded(session, bridge):
    in_pool = make_account(session, "ACC-004", POOL)
    other_pool = make_account(session, "ACC-005", OTHER_POOL)
    unpooled = make_account(session, "ACC-006", None)
    make_payment(session, in_pool, "10.00")
    make_payment(session, other_pool, "999.00")
    make_payment(session, unpooled, "888.00")
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("10.00")
    assert result.payment_count == 1
    assert result.account_count == 1


def test_pending_and_failed_payments_excluded(session, bridge):
    acct = make_account(session, "ACC-007", POOL)
    make_payment(session, acct, "20.00", status="completed")
    make_payment(session, acct, "30.00", status="pending")
    make_payment(session, acct, "40.00", status="failed")
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("20.00")
    assert result.payment_count == 1


def test_recoveries_split_by_method_and_notes_rule(session, bridge):
    """method == 'settlement' OR notes mentioning 'settlement' -> recoveries."""
    acct = make_account(session, "ACC-008", POOL)
    make_payment(session, acct, "100.00", method="card")  # collection
    make_payment(session, acct, "60.00", method="settlement")  # recovery (method)
    make_payment(  # recovery (notes, case-insensitive)
        session, acct, "40.00", method="ach", notes="Lump-sum SETTLEMENT at 60%"
    )
    make_payment(  # plain notes stay a collection
        session, acct, "25.00", method="ach", notes="regular installment"
    )
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert result.collections == Decimal("125.00")
    assert result.recoveries == Decimal("100.00")
    assert result.payment_count == 4
    assert result.account_count == 1


def test_empty_pool_returns_zeros_without_crashing(session, bridge):
    result = bridge.aggregate_period("POOL-EMPTY", PERIOD_START, PERIOD_END)

    assert isinstance(result, EpochCollections)
    assert result.collections == Decimal("0.00")
    assert result.recoveries == Decimal("0.00")
    assert result.payment_count == 0
    assert result.account_count == 0


def test_decimal_precision_preserved_exactly(session, bridge):
    """Many one-cent payments must sum exactly — no float laundering."""
    acct = make_account(session, "ACC-009", POOL)
    for _ in range(100):
        make_payment(session, acct, "0.01")
    make_payment(session, acct, "0.10")
    session.commit()

    result = bridge.aggregate_period(POOL, PERIOD_START, PERIOD_END)

    assert isinstance(result.collections, Decimal)
    assert result.collections == Decimal("1.10")
    assert result.payment_count == 101


# ----------------------------------------------------------- pool assignment


def test_assign_accounts_to_pool_updates_and_returns_count(session, bridge):
    a1 = make_account(session, "ACC-010", None)
    a2 = make_account(session, "ACC-011", None)
    untouched = make_account(session, "ACC-012", None)
    session.commit()

    count = bridge.assign_accounts_to_pool(["ACC-010", "ACC-011"], POOL)

    assert count == 2
    session.refresh(a1), session.refresh(a2), session.refresh(untouched)
    assert a1.pool_id == POOL
    assert a2.pool_id == POOL
    assert untouched.pool_id is None


def test_assign_accounts_ignores_unknown_ids(session, bridge):
    a1 = make_account(session, "ACC-013", None)
    session.commit()

    count = bridge.assign_accounts_to_pool(["ACC-013", "ACC-NOPE", "ACC-NADA"], POOL)

    assert count == 1
    session.refresh(a1)
    assert a1.pool_id == POOL
    assert bridge.assign_accounts_to_pool([], POOL) == 0


# ------------------------------------------------------------ run_pool_epoch


def test_run_pool_epoch_passes_aggregated_decimals_to_platform(session, bridge):
    acct = make_account(session, "ACC-014", POOL)
    make_payment(session, acct, "200.00", method="card")
    make_payment(session, acct, "75.50", method="settlement")
    session.commit()
    platform = StubPlatform()

    bridge.run_pool_epoch(platform, POOL, PERIOD_START, PERIOD_END)

    assert len(platform.calls) == 1
    call = platform.calls[0]
    assert call["pool_id"] == POOL
    assert call["collections"] == Decimal("200.00")
    assert call["recoveries"] == Decimal("75.50")
    assert isinstance(call["collections"], Decimal)
    assert isinstance(call["recoveries"], Decimal)


def test_run_pool_epoch_merges_result_with_source(session, bridge):
    acct = make_account(session, "ACC-015", POOL)
    make_payment(session, acct, "300.00")
    session.commit()
    platform = StubPlatform(result={"epoch": 7, "nav": "1.0234", "yields": []})

    merged = bridge.run_pool_epoch(platform, POOL, PERIOD_START, PERIOD_END)

    assert merged["epoch"] == 7
    assert merged["nav"] == "1.0234"
    source = merged["source"]
    assert source["pool_id"] == POOL
    assert source["collections"] == Decimal("300.00")
    assert source["recoveries"] == Decimal("0.00")
    assert source["payment_count"] == 1
    assert source["account_count"] == 1
    assert source["period_start"] == PERIOD_START
    assert source["period_end"] == PERIOD_END
