# Database model and migration status

`tenants` owns school identity and branding. School ERP tables have non-null `tenant_id`; `users.tenant_id` is nullable only for platform identities. Composite uniqueness allows matching usernames, emails and school identifiers in different schools. `plans`, `subscriptions`, `saas_invoices`, `saas_payments`, `saas_provider_events` and `platform_audit_events` are platform-managed, even where they reference a school.

Alembic revisions create the legacy schema, normalize old constraints, backfill a default tenant and school ownership, create platform plan/subscription tables, grant an explicit Legacy subscription, and create separate SaaS billing tables. The tenant migration and Legacy entitlement revision intentionally lack a destructive downgrade. Use a verified backup to reverse them.

The full chain and model comparison passed on a disposable local PostgreSQL server. A synthetic populated legacy PostgreSQL schema and a copied legacy SQLite database retained their records through tenant migration. The supplied Render database was not inspected or migrated; verify its schema, back it up, and rehearse on a customer-data staging copy before applying migrations there. See [migration procedure](MIGRATIONS.md).
