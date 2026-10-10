# Database migrations

Alembic reads `DATABASE_URL` from the environment through `backend/app/config.py`. The checked-in `alembic.ini` URL is an inert local placeholder. Production startup no longer creates tables automatically; apply migrations as a separate release step before starting the web service.

## New, empty database

```bash
alembic upgrade head
alembic check
```

The first revision creates the existing ERP schema. The second normalizes four legacy nullable columns. The third creates the default `legacy-school` tenant, backfills school ownership and converts `ADMIN` to `SCHOOL_ADMIN`. Later revisions create platform plans and subscriptions, grant a Legacy subscription to the migrated school, and add separate SaaS invoice, payment and provider-event tables.

## Existing single-school database

Take and verify a restorable backup, rehearse on a staging copy, and compare row counts before and after. The supplied Render database has **not** been modified or inspected by this work.

```bash
python -m scripts.verify_legacy_schema
alembic stamp 54cd203053ec
alembic upgrade head
alembic check
```

`stamp` records that the preexisting tables correspond to the reviewed baseline; it does not create or change them. Run it only after the verifier succeeds against that exact database. Existing data is preserved by the tenant migration. If the verifier fails, investigate the schema and write a targeted migration rather than forcing the stamp.

## Rollback and production gate

Test restoration from backup before migration. SQLite batch DDL is not fully transactional, and the first revision's downgrade drops all ERP tables; never use a blind downgrade on a database with school data. The tenant migration intentionally has no destructive downgrade; restore a verified backup if reversal is needed. A fresh local PostgreSQL database was migrated, seeded, schema-checked and tested. A second local PostgreSQL database with synthetic legacy users, students, fees and audit records was upgraded with counts and tenant IDs preserved. The Render database and a real customer-data staging copy are still untested.
