# Deployment status and Render preparation

The project is **not ready to serve customer schools in production**. Tenant ownership, a platform administration API/UI, tenant-specific private object keys and separate SaaS checkout/webhook code are implemented, but real provider verification, recurring billing/refunds, a complete resource authorization audit, full UI verification, and Render staging migration remain outstanding.

The Docker image binds to Render's `PORT`. Configure `ENVIRONMENT=production`, `DATABASE_URL` (Render PostgreSQL URL), a long random `SECRET_KEY`, `ALLOWED_ORIGINS` with exact frontend origins, `OBJECT_STORAGE_BUCKET`, optional `OBJECT_STORAGE_ENDPOINT` and `OBJECT_STORAGE_REGION`, and AWS-compatible access keys. Set Razorpay credentials only when school fee payments are enabled. Keep these values in Render environment variables; do not commit them. `/health` checks process liveness; `/ready` checks database connectivity.

SaaS checkout additionally needs `SAAS_RAZORPAY_KEY_ID`, `SAAS_RAZORPAY_KEY_SECRET`, and `SAAS_RAZORPAY_WEBHOOK_SECRET`. Point the provider webhook at `/api/saas/webhooks/razorpay`. Schedule `python -m scripts.reconcile_subscriptions` at least daily. Configure provider test mode and verify captured, failed, repeated and invalid-signature deliveries before enabling billing.

The reviewed [render.yaml](../render.yaml) defines a Docker web service and daily reconciliation cron job with automatic deploys off. It intentionally does not run migrations or provision a new database. Fill all prompted environment variables and verify the existing database and bucket before importing the Blueprint. Render's [Blueprint specification](https://render.com/docs/blueprint-spec) defines `sync: false` prompts and Docker commands; [cron schedules use UTC](https://render.com/docs/cronjobs).

Apply Alembic migrations as a deliberate pre-deploy step after a tested backup and staging rehearsal. See [MIGRATIONS.md](MIGRATIONS.md). Existing data needs legacy schema verification and a baseline stamp. The supplied Render database has not been contacted or changed. Rotate the password shared in the request before production use.

Local Docker Compose persists its development SQLite database and uploads in volumes. In production, private uploads use `tenant/{tenant_id}/{category}/{generated_filename}` keys in the configured S3-compatible bucket. Existing local files require a separate verified copy to object storage before removing their persistent disk.
