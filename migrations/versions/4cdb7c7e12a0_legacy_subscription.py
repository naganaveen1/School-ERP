"""Grandfather migrated schools into an explicit unmetered plan.

Revision ID: 4cdb7c7e12a0
Revises: 2ab809d4c720
"""

from alembic import op
import sqlalchemy as sa

revision = "4cdb7c7e12a0"
down_revision = "2ab809d4c720"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO plans (name, description, price, billing_interval, trial_days,
                           features, is_active)
        SELECT 'Legacy', 'Existing school entitlement', 0, 'MONTHLY', 0,
               '["attendance","assignments","exams","finance","messaging","reports","documents","advanced_reports"]', false
        WHERE NOT EXISTS (SELECT 1 FROM plans WHERE name = 'Legacy')
    """)
    op.execute("""
        INSERT INTO subscriptions (tenant_id, plan_id, status)
        SELECT t.id, p.id, 'ACTIVE'
        FROM tenants t CROSS JOIN plans p
        WHERE t.slug = 'legacy-school' AND p.name = 'Legacy'
          AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.tenant_id = t.id)
    """)


def downgrade():
    raise RuntimeError("Legacy entitlements cannot be safely downgraded; restore a verified backup")
