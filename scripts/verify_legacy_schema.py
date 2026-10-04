"""Check a legacy database before stamping the Alembic baseline.

Read-only. Run against a backup or staging copy before touching production.
"""

from sqlalchemy import inspect

from backend.app import models  # noqa: F401 - register metadata
from backend.app.database import Base, engine


ALLOWED_LEGACY_NULLABLE = {
    ("fees", "installment_name"),
    ("fees", "installment_number"),
    ("payments", "discount_amount"),
    ("payments", "reconciliation_status"),
}


def main() -> None:
    inspector = inspect(engine)
    expected_tables = set(Base.metadata.tables)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    errors = []
    if expected_tables != actual_tables:
        errors.append(f"Tables differ: missing={sorted(expected_tables - actual_tables)}, extra={sorted(actual_tables - expected_tables)}")

    for table_name in sorted(expected_tables & actual_tables):
        model_table = Base.metadata.tables[table_name]
        actual_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        expected_columns = set(model_table.columns.keys())
        if expected_columns != set(actual_columns):
            errors.append(f"{table_name}: column names differ")
            continue
        for column in model_table.columns:
            actual = actual_columns[column.name]
            if bool(actual["nullable"]) != bool(column.nullable):
                if (table_name, column.name) not in ALLOWED_LEGACY_NULLABLE or not actual["nullable"]:
                    errors.append(f"{table_name}.{column.name}: nullability differs")

        expected_fks = {
            (tuple(fk.parent.name for fk in constraint.elements),
             tuple(str(fk.target_fullname) for fk in constraint.elements))
            for constraint in model_table.foreign_key_constraints
        }
        actual_fks = {
            (tuple(fk["constrained_columns"]),
             tuple(f"{fk['referred_table']}.{name}" for name in fk["referred_columns"]))
            for fk in inspector.get_foreign_keys(table_name)
        }
        if expected_fks != actual_fks:
            errors.append(f"{table_name}: foreign keys differ")

    if errors:
        raise SystemExit("Legacy schema does not match the reviewed baseline:\n" + "\n".join(errors))
    print(f"Legacy schema verified: {len(expected_tables)} tables; no unexpected columns or foreign keys.")


if __name__ == "__main__":
    main()
