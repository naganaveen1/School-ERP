"""Add school ownership and backfill the existing single-school ERP.

Revision ID: 83715953ee52
Revises: 598ecbb48c43
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "83715953ee52"
down_revision: Union[str, Sequence[str], None] = "598ecbb48c43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHOOL_TABLES = (
    "academic_years", "assignments", "attendances", "audit_logs", "classes",
    "complaints", "departments", "documents", "enrollments", "events", "exams",
    "fees", "leaves", "messages", "notices", "notifications", "parents",
    "payments", "principals", "results", "sections", "students",
    "study_materials", "subjects", "submissions", "teachers", "timetables",
)
ALL_OWNED = ("users",) + SCHOOL_TABLES

GLOBAL_UNIQUE_INDEXES = {
    "academic_years": ("name",),
    "departments": ("name", "code"),
    "principals": ("employee_id",),
    "students": ("admission_number",),
    "teachers": ("employee_id",),
    "users": ("username", "email"),
}
COMPOSITE_UNIQUES = {
    "academic_years": ("name",),
    "departments": ("name", "code"),
    "principals": ("employee_id",),
    "students": ("admission_number",),
    "teachers": ("employee_id",),
    "users": ("username", "email"),
}


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("legal_name", sa.String(180)),
        sa.Column("email", sa.String(150)),
        sa.Column("phone", sa.String(30)),
        sa.Column("address", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("favicon_url", sa.String(500)),
        sa.Column("primary_color", sa.String(7), nullable=False),
        sa.Column("secondary_color", sa.String(7), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('TRIAL','ACTIVE','SUSPENDED','EXPIRED','CANCELLED','ARCHIVED')",
            name="ck_tenants_status",
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.execute(
        "INSERT INTO tenants (name, slug, country, primary_color, secondary_color, timezone, currency, status) "
        "VALUES ('Existing School', 'legacy-school', 'India', '#0d675f', '#163530', 'Asia/Kolkata', 'INR', 'ACTIVE')"
    )

    # Add nullable columns first, then fill every existing row before enforcing NOT NULL.
    for table in ALL_OWNED:
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
        op.execute(sa.text(
            f"UPDATE {table} SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-school') "
            "WHERE tenant_id IS NULL"
        ))
        if not context.is_offline_mode():
            remaining = op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id IS NULL")).scalar_one()
            if remaining:
                raise RuntimeError(f"Could not backfill {table}.tenant_id")

    op.execute("UPDATE users SET role = 'SCHOOL_ADMIN' WHERE role = 'ADMIN'")
    op.execute("UPDATE roles SET name = 'SCHOOL_ADMIN' WHERE name = 'ADMIN'")

    for table in ALL_OWNED:
        with op.batch_alter_table(table) as batch:
            if table != "users":
                batch.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
            else:
                batch.alter_column("role", existing_type=sa.String(20), type_=sa.String(30), nullable=False)
            batch.create_foreign_key(f"fk_{table}_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    for table, columns in GLOBAL_UNIQUE_INDEXES.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.create_index(f"ix_{table}_{column}", table, [column], unique=False)

    for table, columns in COMPOSITE_UNIQUES.items():
        for column in columns:
            suffix = "admission" if table == "students" else "employee" if table in ("teachers", "principals") else column
            with op.batch_alter_table(table) as batch:
                batch.create_unique_constraint(f"uq_{table}_tenant_{suffix}", ["tenant_id", column])

    for column in ("username", "email"):
        op.create_index(
            f"uq_users_platform_{column}", "users", [column], unique=True,
            sqlite_where=sa.text("tenant_id IS NULL"),
            postgresql_where=sa.text("tenant_id IS NULL"),
        )


def downgrade() -> None:
    raise RuntimeError("Tenant ownership migration cannot be safely downgraded; restore the verified backup")
