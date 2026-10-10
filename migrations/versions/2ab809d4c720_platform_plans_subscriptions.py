"""Platform plans, one subscription per school, and audit trail.

Revision ID: 2ab809d4c720
Revises: 83715953ee52
"""

from alembic import op
import sqlalchemy as sa

revision = "2ab809d4c720"
down_revision = "83715953ee52"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("billing_interval", sa.String(20), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("max_students", sa.Integer()),
        sa.Column("max_teachers", sa.Integer()),
        sa.Column("max_admins", sa.Integer()),
        sa.Column("max_storage", sa.Integer()),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("current_period_start", sa.DateTime()),
        sa.Column("current_period_end", sa.DateTime()),
        sa.Column("trial_start", sa.DateTime()),
        sa.Column("trial_end", sa.DateTime()),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.Column("provider", sa.String(30)),
        sa.Column("provider_customer_id", sa.String(100)),
        sa.Column("provider_subscription_id", sa.String(100), unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('TRIALING','ACTIVE','PAST_DUE','PAUSED','CANCELLED','EXPIRED')", name="ck_subscriptions_status"),
        sa.UniqueConstraint("tenant_id", name="uq_subscriptions_tenant"),
    )
    op.create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_table(
        "platform_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_audit_events_actor_user_id", "platform_audit_events", ["actor_user_id"])
    op.create_index("ix_platform_audit_events_tenant_id", "platform_audit_events", ["tenant_id"])
    op.create_index("ix_platform_audit_events_action", "platform_audit_events", ["action"])


def downgrade():
    op.drop_table("platform_audit_events")
    op.drop_table("subscriptions")
    op.drop_table("plans")
