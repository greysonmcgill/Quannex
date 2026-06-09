"""Add tokenization pool linkage to accounts table.

Revision ID: 20260609_0003
Revises: 20260530_0002
Create Date: 2026-06-09

Phase 2 of the closed-loop roadmap (docs/ZERO_BASED_ARCHITECTURE_REVIEW.md):
link accounts to RWA tokenization pools so the collections bridge can
aggregate Payment rows per pool and feed
``RWATokenizationPlatform.run_epoch(pool_id, collections, recoveries)``.

Design notes:

- ``pool_id`` is nullable (NULL = account not yet pooled), so no
  ``server_default`` is required; existing rows correctly read as un-pooled.
- No ``total_recovered`` rollup column is added: recoveries are derived from
  Payment rows at aggregation time by ``quan.finance.collections_bridge``,
  keeping payments the single source of truth.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260609_0003"
down_revision = "20260530_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the nullable pool linkage column and its lookup index."""
    op.add_column(
        "accounts",
        sa.Column("pool_id", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_accounts_pool_id", "accounts", ["pool_id"], unique=False)


def downgrade() -> None:
    """Remove the pool linkage index and column."""
    op.drop_index("ix_accounts_pool_id", table_name="accounts")
    op.drop_column("accounts", "pool_id")
