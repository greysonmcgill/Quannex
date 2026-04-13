"""Initial schema - accounts, portfolios, campaigns, payments, contacts, compliance

Revision ID: 001
Revises:
Create Date: 2026-04-13

Creates the core database schema for QUAN Recovery platform.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Portfolios table
    op.create_table(
        'portfolios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('client_id', sa.String(36), nullable=True),
        sa.Column('total_accounts', sa.Integer, default=0),
        sa.Column('total_balance', sa.Numeric(15, 2), default=0),
        sa.Column('source_file', sa.String(500), nullable=True),
        sa.Column('upload_status', sa.String(50), default='pending'),
        sa.Column('valid_rows', sa.Integer, default=0),
        sa.Column('invalid_rows', sa.Integer, default=0),
        sa.Column('error_details', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_portfolios_client_id', 'portfolios', ['client_id'])
    op.create_index('ix_portfolios_created_at', 'portfolios', ['created_at'])

    # Accounts table
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('external_account_id', sa.String(100), nullable=True),
        sa.Column('portfolio_id', sa.String(36), sa.ForeignKey('portfolios.id'), nullable=True),

        # Debtor info
        sa.Column('debtor_name', sa.String(255), nullable=False),
        sa.Column('debtor_first_name', sa.String(100), nullable=True),
        sa.Column('debtor_last_name', sa.String(100), nullable=True),

        # Contact info
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('phone_valid', sa.Boolean, default=True),
        sa.Column('phone_type', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('email_valid', sa.Boolean, default=True),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        sa.Column('zip_code', sa.String(10), nullable=True),

        # Debt details
        sa.Column('original_creditor', sa.String(255), nullable=True),
        sa.Column('current_creditor', sa.String(255), nullable=True),
        sa.Column('debt_type', sa.String(50), default='other'),
        sa.Column('original_balance', sa.Numeric(12, 2), default=0),
        sa.Column('current_balance', sa.Numeric(12, 2), default=0),
        sa.Column('interest_rate', sa.Float, nullable=True),

        # Aging
        sa.Column('account_open_date', sa.DateTime, nullable=True),
        sa.Column('last_payment_date', sa.DateTime, nullable=True),
        sa.Column('charge_off_date', sa.DateTime, nullable=True),
        sa.Column('days_past_due', sa.Integer, default=0),

        # Status
        sa.Column('status', sa.String(50), default='new'),
        sa.Column('status_changed_at', sa.DateTime, server_default=sa.func.now()),

        # Intelligence scores
        sa.Column('recovery_probability', sa.Float, nullable=True),
        sa.Column('settlement_threshold', sa.Float, nullable=True),
        sa.Column('optimal_channels', sa.JSON, nullable=True),
        sa.Column('segment_id', sa.Integer, nullable=True),

        # Behavioral
        sa.Column('payment_willingness', sa.Float, nullable=True),
        sa.Column('has_mobile', sa.Boolean, default=False),
        sa.Column('employed', sa.Boolean, default=True),
        sa.Column('income_bracket', sa.String(20), nullable=True),
        sa.Column('age', sa.Integer, nullable=True),

        # Compliance flags
        sa.Column('do_not_call', sa.Boolean, default=False),
        sa.Column('do_not_email', sa.Boolean, default=False),
        sa.Column('do_not_mail', sa.Boolean, default=False),
        sa.Column('bankruptcy_flag', sa.Boolean, default=False),
        sa.Column('deceased_flag', sa.Boolean, default=False),
        sa.Column('disputed', sa.Boolean, default=False),
        sa.Column('attorney_represented', sa.Boolean, default=False),
        sa.Column('statute_of_limitations_expired', sa.Boolean, default=False),

        # Collection metrics
        sa.Column('total_payments', sa.Numeric(12, 2), default=0),
        sa.Column('contact_attempts', sa.Integer, default=0),
        sa.Column('successful_contacts', sa.Integer, default=0),
        sa.Column('last_contact_date', sa.DateTime, nullable=True),
        sa.Column('last_contact_channel', sa.String(20), nullable=True),

        # Settlement
        sa.Column('settlement_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('settlement_accepted_at', sa.DateTime, nullable=True),

        # Extra
        sa.Column('metadata', sa.JSON, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_accounts_status', 'accounts', ['status'])
    op.create_index('ix_accounts_debt_type', 'accounts', ['debt_type'])
    op.create_index('ix_accounts_state', 'accounts', ['state'])
    op.create_index('ix_accounts_portfolio_id', 'accounts', ['portfolio_id'])
    op.create_index('ix_accounts_created_at', 'accounts', ['created_at'])
    op.create_index('ix_accounts_external_id', 'accounts', ['external_account_id'])
    op.create_index('ix_accounts_recovery_probability', 'accounts', ['recovery_probability'])
    op.create_index('ix_accounts_current_balance', 'accounts', ['current_balance'])

    # Campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('portfolio_id', sa.String(36), sa.ForeignKey('portfolios.id'), nullable=True),
        sa.Column('strategy_type', sa.String(50), nullable=True),
        sa.Column('target_segment', sa.String(50), nullable=True),
        sa.Column('channels', sa.JSON, nullable=True),
        sa.Column('status', sa.String(50), default='created'),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('total_accounts', sa.Integer, default=0),
        sa.Column('accounts_contacted', sa.Integer, default=0),
        sa.Column('accounts_responded', sa.Integer, default=0),
        sa.Column('accounts_converted', sa.Integer, default=0),
        sa.Column('total_collected', sa.Numeric(12, 2), default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])
    op.create_index('ix_campaigns_portfolio_id', 'campaigns', ['portfolio_id'])

    # Contact Attempts table
    op.create_table(
        'contact_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id'), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('direction', sa.String(20), default='outbound'),
        sa.Column('contact_target', sa.String(255), nullable=True),
        sa.Column('outcome', sa.String(50), nullable=False),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('message_template', sa.String(100), nullable=True),
        sa.Column('message_content', sa.Text, nullable=True),
        sa.Column('agent_id', sa.String(36), nullable=True),
        sa.Column('response_received', sa.Boolean, default=False),
        sa.Column('response_content', sa.Text, nullable=True),
        sa.Column('cost', sa.Numeric(8, 4), default=0),
        sa.Column('consent_verified', sa.Boolean, default=True),
        sa.Column('within_contact_hours', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_contact_attempts_account_id', 'contact_attempts', ['account_id'])
    op.create_index('ix_contact_attempts_channel', 'contact_attempts', ['channel'])
    op.create_index('ix_contact_attempts_created_at', 'contact_attempts', ['created_at'])
    op.create_index('ix_contact_attempts_outcome', 'contact_attempts', ['outcome'])

    # Payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('is_settlement', sa.Boolean, default=False),
        sa.Column('is_payment_plan', sa.Boolean, default=False),
        sa.Column('payment_plan_installment', sa.Integer, nullable=True),
        sa.Column('transaction_id', sa.String(100), nullable=True),
        sa.Column('processor_reference', sa.String(100), nullable=True),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('failure_reason', sa.String(255), nullable=True),
        sa.Column('processing_fee', sa.Numeric(8, 2), default=0),
        sa.Column('net_amount', sa.Numeric(12, 2), default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_payments_account_id', 'payments', ['account_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])
    op.create_index('ix_payments_created_at', 'payments', ['created_at'])

    # Compliance Events table
    op.create_table(
        'compliance_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), default='info'),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('resolution', sa.Text, nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('regulation', sa.String(50), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        sa.Column('evidence', sa.JSON, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_compliance_events_account_id', 'compliance_events', ['account_id'])
    op.create_index('ix_compliance_events_event_type', 'compliance_events', ['event_type'])
    op.create_index('ix_compliance_events_severity', 'compliance_events', ['severity'])
    op.create_index('ix_compliance_events_created_at', 'compliance_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('compliance_events')
    op.drop_table('payments')
    op.drop_table('contact_attempts')
    op.drop_table('campaigns')
    op.drop_table('accounts')
    op.drop_table('portfolios')
