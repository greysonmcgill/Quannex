"""Add compliance flags to accounts table.

Revision ID: 20260530_0002
Revises: 20260412_0001_layer1_backend_tables
Create Date: 2026-05-30

These flags enable the compliance guard to block contact attempts
for accounts with specific legal/compliance status.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260530_0002"
down_revision = "20260412_0001_layer1_backend_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add compliance flag columns to accounts table."""
    op.add_column(
        "accounts",
        sa.Column("do_not_call", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("do_not_email", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("do_not_mail", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("bankruptcy_flag", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("deceased_flag", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("disputed", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column("attorney_represented", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "statute_of_limitations_expired", sa.Boolean(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    """Remove compliance flag columns from accounts table."""
    op.drop_column("accounts", "statute_of_limitations_expired")
    op.drop_column("accounts", "attorney_represented")
    op.drop_column("accounts", "disputed")
    op.drop_column("accounts", "deceased_flag")
    op.drop_column("accounts", "bankruptcy_flag")
    op.drop_column("accounts", "do_not_mail")
    op.drop_column("accounts", "do_not_email")
    op.drop_column("accounts", "do_not_call")
