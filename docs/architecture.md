# Architecture

The existing FastAPI + SQLAlchemy backend and static HTML/JavaScript frontend remain in place. Alembic manages schema evolution. A tenant ownership migration adds school IDs to ERP records; request authentication installs a scoped ORM session policy. Platform models and routes are separate from school ERP models and routes. Plans and subscriptions determine feature access and seat limits. A distinct SaaS billing service handles School → Platform payments; the existing fee service handles Parent → School payments.

The frontend has a shared design-system stylesheet and school-role shell, a school-slug login entry, a platform dashboard, and a school subscription page. Production private files use S3-compatible storage with server-generated tenant keys. A scheduled subscription reconciliation command is available but must be configured in the hosting environment.

The implementation is not production complete. See [authorization status](AUTHORIZATION.md), [billing limits](BILLING.md), and [deployment status](DEPLOYMENT.md).
