"""normalize legacy constraints

Revision ID: 598ecbb48c43
Revises: 54cd203053ec
Create Date: 2026-10-04 21:59:33.608889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '598ecbb48c43'
down_revision: Union[str, Sequence[str], None] = '54cd203053ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill legacy nulls before enforcing current model constraints."""
    op.execute("UPDATE fees SET installment_name = 'Annual' WHERE installment_name IS NULL")
    op.execute("UPDATE fees SET installment_number = 1 WHERE installment_number IS NULL")
    op.execute("UPDATE payments SET discount_amount = 0 WHERE discount_amount IS NULL")
    op.execute("UPDATE payments SET reconciliation_status = 'UNRECONCILED' WHERE reconciliation_status IS NULL")
    with op.batch_alter_table('fees') as batch_op:
        batch_op.alter_column('installment_name', existing_type=sa.String(50), nullable=False)
        batch_op.alter_column('installment_number', existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table('payments') as batch_op:
        batch_op.alter_column('discount_amount', existing_type=sa.Float(), nullable=False)
        batch_op.alter_column('reconciliation_status', existing_type=sa.String(20), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('payments') as batch_op:
        batch_op.alter_column('discount_amount', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('reconciliation_status', existing_type=sa.String(20), nullable=True)
    with op.batch_alter_table('fees') as batch_op:
        batch_op.alter_column('installment_name', existing_type=sa.String(50), nullable=True)
        batch_op.alter_column('installment_number', existing_type=sa.Integer(), nullable=True)
