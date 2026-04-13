"""create layer1 backend tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260412_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("debt_mix", sa.JSON(), nullable=False),
        sa.Column("uploaded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portfolios_portfolio_id", "portfolios", ["portfolio_id"], unique=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("debtor_name", sa.String(length=255), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("original_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("original_creditor", sa.String(length=255), nullable=False),
        sa.Column("debt_type", sa.String(length=64), nullable=False),
        sa.Column("days_past_due", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scored"),
        sa.Column("recovery_probability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("optimal_channels", sa.JSON(), nullable=False),
        sa.Column("settlement_threshold", sa.Float(), nullable=False, server_default="1"),
        sa.Column("total_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_contact_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_accounts_account_id", "accounts", ["account_id"], unique=True)
    op.create_index("ix_accounts_debt_type", "accounts", ["debt_type"], unique=False)
    op.create_index("ix_accounts_days_past_due", "accounts", ["days_past_due"], unique=False)
    op.create_index("ix_accounts_state", "accounts", ["state"], unique=False)
    op.create_index("ix_accounts_status", "accounts", ["status"], unique=False)
    op.create_index(
        "ix_accounts_status_debt_type_state",
        "accounts",
        ["status", "debt_type", "state"],
        unique=False,
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="intake"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaigns_campaign_id", "campaigns", ["campaign_id"], unique=True)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("account_db_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payments_payment_id", "payments", ["payment_id"], unique=True)
    op.create_index("ix_payments_account_db_id", "payments", ["account_db_id"], unique=False)

    op.create_table(
        "contact_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("account_db_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("compliant", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("agent_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contact_attempts_attempt_id", "contact_attempts", ["attempt_id"], unique=True)
    op.create_index("ix_contact_attempts_account_db_id", "contact_attempts", ["account_db_id"], unique=False)
    op.create_index("ix_contact_attempts_channel", "contact_attempts", ["channel"], unique=False)

    op.create_table(
        "compliance_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("account_db_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_compliance_events_event_id", "compliance_events", ["event_id"], unique=True)
    op.create_index("ix_compliance_events_account_db_id", "compliance_events", ["account_db_id"], unique=False)
    op.create_index("ix_compliance_events_event_type", "compliance_events", ["event_type"], unique=False)
    op.create_index("ix_compliance_events_severity", "compliance_events", ["severity"], unique=False)
    op.create_index("ix_compliance_events_state", "compliance_events", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_compliance_events_state", table_name="compliance_events")
    op.drop_index("ix_compliance_events_severity", table_name="compliance_events")
    op.drop_index("ix_compliance_events_event_type", table_name="compliance_events")
    op.drop_index("ix_compliance_events_account_db_id", table_name="compliance_events")
    op.drop_index("ix_compliance_events_event_id", table_name="compliance_events")
    op.drop_table("compliance_events")

    op.drop_index("ix_contact_attempts_channel", table_name="contact_attempts")
    op.drop_index("ix_contact_attempts_account_db_id", table_name="contact_attempts")
    op.drop_index("ix_contact_attempts_attempt_id", table_name="contact_attempts")
    op.drop_table("contact_attempts")

    op.drop_index("ix_payments_account_db_id", table_name="payments")
    op.drop_index("ix_payments_payment_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_campaigns_campaign_id", table_name="campaigns")
    op.drop_table("campaigns")

    op.drop_index("ix_accounts_status_debt_type_state", table_name="accounts")
    op.drop_index("ix_accounts_status", table_name="accounts")
    op.drop_index("ix_accounts_state", table_name="accounts")
    op.drop_index("ix_accounts_days_past_due", table_name="accounts")
    op.drop_index("ix_accounts_debt_type", table_name="accounts")
    op.drop_index("ix_accounts_account_id", table_name="accounts")
    op.drop_table("accounts")

    op.drop_index("ix_portfolios_portfolio_id", table_name="portfolios")
    op.drop_table("portfolios")
