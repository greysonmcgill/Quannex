"""
Collections → tokenization bridge (the deterministic epoch seam).

This module closes the two integration gaps called out in
``docs/ZERO_BASED_ARCHITECTURE_REVIEW.md`` ("Gap analysis — what actually has
to be built"):

- **G1 — payment aggregation (review gap #6, "Epoch scheduler"):** nothing
  previously summed recorded :class:`~quan.models.database.Payment` rows per
  pool per period and handed them to
  ``RWATokenizationPlatform.run_epoch(pool_id, collections, recoveries)``.
- **G2 — pool linkage (review gap #1, "One source of truth"):** accounts had
  no foreign reference to a tokenization pool. ``Account.pool_id`` (added in
  migration ``20260609_0003``) provides that linkage; this module maintains
  and consumes it.

Everything here is deterministic: no LLM, no network, pure
SQLAlchemy-session-in / Decimal-out. All money math uses :class:`~decimal.
Decimal` quantized to cents — never float.

Recoveries classification rule (documented design decision)
-----------------------------------------------------------

The waterfall distinguishes *collections* (regular debtor payments) from
*recoveries* (settlement proceeds). The ``payments`` table has no dedicated
flag for this, and the public API constrains ``Payment.method`` to the
instrument set ``card|ach|cash|check|digital_wallet|other`` — so an honest,
derivable rule is used instead of a new writer-less rollup column:

    A completed payment is a **recovery** when ``Payment.method ==
    "settlement"`` (rows written directly by finance jobs, where the method
    column is free-form ``String(32)``) OR when its free-text ``notes``
    contain the word ``"settlement"`` (case-insensitive — the only field the
    instrument-constrained API path can carry the distinction in). Everything
    else is a regular **collection**.

This keeps Payment rows the single source of truth; no ``total_recovered``
denormalized counter exists to drift out of sync.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from quan.models.database import Account, Payment, PaymentStatus

__all__ = ["EpochCollections", "CollectionsBridge"]

#: Quantum used for all cent-level money math.
_CENT = Decimal("0.01")

#: ``Payment.method`` value that marks a settlement written by finance jobs.
SETTLEMENT_METHOD = "settlement"

#: Case-insensitive token searched for in ``Payment.notes`` (API-path rows).
SETTLEMENT_NOTES_TOKEN = "settlement"


@dataclass
class EpochCollections:
    """Aggregated, waterfall-ready cash for one pool over one period.

    The period window is half-open: ``period_start <= recorded_at <
    period_end``, so consecutive epochs never double-count a payment.
    """

    pool_id: str
    period_start: datetime
    period_end: datetime
    collections: Decimal
    recoveries: Decimal
    payment_count: int
    account_count: int


def _is_recovery(method: str, notes: str | None) -> bool:
    """Apply the documented recoveries classification rule."""
    if method == SETTLEMENT_METHOD:
        return True
    return bool(notes) and SETTLEMENT_NOTES_TOKEN in notes.lower()


class CollectionsBridge:
    """Deterministic seam between recorded payments and the tokenization waterfall.

    Constructed with a plain SQLAlchemy :class:`~sqlalchemy.orm.Session`; owns
    no engine, no network client, and calls no model. The tokenization
    platform is duck-typed — anything exposing
    ``run_epoch(pool_id, collections, recoveries)`` works (tests pass stubs).
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ G1
    def aggregate_period(
        self, pool_id: str, period_start: datetime, period_end: datetime
    ) -> EpochCollections:
        """Sum completed payments for ``pool_id`` within the half-open window.

        Only ``Payment.status == "completed"`` rows on accounts whose
        ``Account.pool_id`` matches are counted. Amounts are summed in Python
        as :class:`~decimal.Decimal` quantized to cents (never float) so the
        result is exact regardless of backend numeric affinity (SQLite stores
        NUMERIC as float; SQL-side SUM would launder precision through float).
        Pilot-scale row counts make the per-row fetch a non-issue.
        """
        rows = self.session.execute(
            select(Payment.amount, Payment.method, Payment.notes, Payment.account_db_id)
            .join(Account, Payment.account_db_id == Account.id)
            .where(
                Account.pool_id == pool_id,
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.recorded_at >= period_start,
                Payment.recorded_at < period_end,
            )
        ).all()

        collections = Decimal("0.00")
        recoveries = Decimal("0.00")
        account_ids: set[int] = set()
        for amount, method, notes, account_db_id in rows:
            amount = Decimal(amount).quantize(_CENT)
            if _is_recovery(method, notes):
                recoveries += amount
            else:
                collections += amount
            account_ids.add(account_db_id)

        return EpochCollections(
            pool_id=pool_id,
            period_start=period_start,
            period_end=period_end,
            collections=collections,
            recoveries=recoveries,
            payment_count=len(rows),
            account_count=len(account_ids),
        )

    # ------------------------------------------------------------------ G2
    def assign_accounts_to_pool(self, account_ids: list[str], pool_id: str) -> int:
        """Set ``Account.pool_id`` for the given external account IDs.

        Unknown IDs are silently ignored. Returns the number of accounts
        actually updated and commits the change.
        """
        if not account_ids:
            return 0
        result = self.session.execute(
            update(Account)
            .where(Account.account_id.in_(account_ids))
            .values(pool_id=pool_id)
            .execution_options(synchronize_session="fetch")
        )
        self.session.commit()
        return int(result.rowcount or 0)

    # --------------------------------------------------------------- G1+G2
    def run_pool_epoch(
        self,
        platform,
        pool_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict:
        """Aggregate the period, then drive one waterfall epoch.

        ``platform`` is duck-typed: any object with
        ``run_epoch(pool_id, collections, recoveries)`` (e.g.
        ``quan.finance.tokenization.RWATokenizationPlatform`` or a test stub).
        Returns the platform's epoch result dict merged with a ``"source"``
        key carrying the :class:`EpochCollections` fields, so every
        distribution is traceable back to the exact payment aggregation that
        funded it.
        """
        source = self.aggregate_period(pool_id, period_start, period_end)
        epoch_result = platform.run_epoch(
            pool_id, collections=source.collections, recoveries=source.recoveries
        )
        return {**dict(epoch_result), "source": asdict(source)}
