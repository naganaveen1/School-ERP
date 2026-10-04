"""Separate SaaS invoices, payments and idempotent provider events.

Revision ID: 5e201e7aa912
Revises: 4cdb7c7e12a0
"""

from alembic import op
import sqlalchemy as sa

revision = "5e201e7aa912"
down_revision = "4cdb7c7e12a0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("subscriptions", sa.Column("grace_ends_at", sa.DateTime()))
    op.create_table(
        "saas_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_order_id", sa.String(100), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime()),
    )
    op.create_index("ix_saas_invoices_tenant_id", "saas_invoices", ["tenant_id"])
    op.create_index("ix_saas_invoices_subscription_id", "saas_invoices", ["subscription_id"])
    op.create_index("ix_saas_invoices_status", "saas_invoices", ["status"])
    op.create_index("uq_saas_invoice_pending_tenant", "saas_invoices", ["tenant_id"], unique=True,
                    sqlite_where=sa.text("status = 'PENDING'"),
                    postgresql_where=sa.text("status = 'PENDING'"))
    op.create_table(
        "saas_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("saas_invoices.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("provider_payment_id", sa.String(100), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saas_payments_tenant_id", "saas_payments", ["tenant_id"])
    op.create_table(
        "saas_provider_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "event_id", name="uq_saas_provider_event"),
    )


def downgrade():
    op.drop_table("saas_provider_events")
    op.drop_table("saas_payments")
    op.drop_table("saas_invoices")
    op.drop_column("subscriptions", "grace_ends_at")
