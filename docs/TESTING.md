# Test and verification record

The backend suite currently covers existing ERP behavior, school isolation with overlapping usernames, cross-school reads/writes, platform onboarding and role separation, plan limits and feature gates, expiry/grace behavior, tenant-specific storage keys, and mocked SaaS checkout/signature/webhook idempotency.

On 4 October 2026, **43 tests passed** on disposable seeded SQLite and **43 tests passed** on disposable local PostgreSQL. Alembic upgraded fresh SQLite and PostgreSQL databases and `alembic check` found no model drift in the earlier migration rehearsal. A synthetic populated legacy PostgreSQL database and a copy of legacy SQLite retained rows and gained tenant IDs. The supplied Render database was not accessed.

The Razorpay tests use a fake provider and local HMAC calculation. No real provider sandbox payment, webhook delivery, refund, chargeback, Render deployment or customer-data staging migration has been verified. Browser inspection covered the platform workspace at 360, 390, 412, 768, 1024 and 1280 pixels without page-wide overflow, plus school settings and subscription at 360 pixels in dark mode. This does not cover every ERP screen or accessibility behavior.

Run the checks on a disposable seeded database:

```bash
pytest backend/tests -q
python -m compileall -q backend migrations scripts
alembic check
git diff --check
```

Production gates still open: full same-school resource authorization matrix, full screen/device/accessibility inspection, real provider sandbox tests, Render staging migration and backup restoration.
