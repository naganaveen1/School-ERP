# School ERP

FastAPI, SQLAlchemy, Alembic, and a static HTML/JavaScript frontend for school administration, teaching, student and parent workflows. The repository now contains tenant ownership, a platform administration workspace, plan entitlements, separate SaaS checkout records, and tenant-specific private file keys. It is **still under development and must not yet be used to onboard customer schools**: real provider payment tests, recurring billing/refunds, a complete route authorization audit, and full screen/device QA are not finished.

## Current modules

- School roles: `SCHOOL_ADMIN`, `PRINCIPAL`, `TEACHER`, `STUDENT`, `PARENT`.
- Platform roles: `PLATFORM_SUPER_ADMIN`, `PLATFORM_SUPPORT`, `PLATFORM_BILLING`.
- School ERP: users and profiles, academics, attendance, assignments, exams, results, school fees, communications, documents, reports, and audit events.
- Platform: school registry, plan management, atomic school/administrator/trial creation, status updates, real school and usage counts, subscription management, and platform audit trail.
- SaaS billing: a separate School → Platform Razorpay order/verification/webhook path with idempotent invoice and payment records. Real provider transactions are not yet verified.
- Private uploads: local tenant paths in development; S3-compatible object storage required in production.

The school fee payment flow is separate from platform subscription records. Automatic recurring charging, refunds, chargebacks, tax invoices and proration are **not implemented**.

## Local setup

Use Python 3.10 or newer. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m backend.app.seed.seed_database
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The example environment uses a local SQLite database. For production, configure a PostgreSQL `DATABASE_URL`, a long random `SECRET_KEY`, an S3-compatible `OBJECT_STORAGE_BUCKET` and AWS-compatible credentials, and exact `ALLOWED_ORIGINS`. Production startup does not create database tables; run reviewed Alembic migrations before the web service starts.

To create the first platform owner after migrations, set `PLATFORM_ADMIN_USERNAME`, `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_NAME`, and a unique `PLATFORM_ADMIN_PASSWORD` of at least 16 characters, then run `python -m scripts.create_platform_admin`. No production owner or password is seeded automatically.

Visit `/school/{slug}` for a school login or `/frontend/login.html` for general sign-in. A school slug selects an account when usernames overlap; API access always derives the tenant from the authenticated user. Platform staff sign in without a school slug and use `/frontend/platform/dashboard.html`.

## Verification

```bash
pytest backend/tests -q
python -m compileall -q backend migrations scripts
alembic check
git diff --check
```

See [tenant design](docs/MULTI_TENANCY.md), [migration procedure](docs/MIGRATIONS.md), [deployment status](docs/DEPLOYMENT.md), and [engineering report](docs/ENGINEERING_REPORT.md). The supplied Render database has not been changed by this work.
