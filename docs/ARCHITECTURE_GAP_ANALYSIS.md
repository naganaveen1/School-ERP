# Architecture gap analysis

Updated 4 October 2026 for the current `new-version` checkout. The foundation report in `ENGINEERING_REPORT.md` records the original single-school baseline; the table below records the state after the SaaS continuation.

| Area | Implemented and verified locally | Remaining release gate |
| --- | --- | --- |
| Tenant data | `Tenant` and tenant IDs on school-owned tables; default-school migration, non-null keys, session query/write policy, cross-tenant FK checks. Two-school API tests and populated legacy SQLite/PostgreSQL rehearsals passed. | Complete the route-by-route same-school role/resource audit and expand ID substitution coverage across all modules. |
| Identity | Tenant slug login, tenant-bearing JWT, five school roles, three platform roles, platform/school route separation. | Rate limiting, password recovery, session revocation, and a production session strategy beyond localStorage. |
| Plans and subscriptions | Data-driven plans, feature/seat gates, trial and paid-period reconciliation, grace and expiry, billing-only admin access. | Explicitly review all state transitions and commercial upgrade/downgrade/proration policy. |
| SaaS billing | Separate invoice/payment/event tables and Razorpay checkout, provider verification, signed webhook, and idempotency with fake-provider tests. | Real provider sandbox payment/webhook, recurring charges, refunds/chargebacks, tax invoicing. |
| ERP payments | Existing school fees remain separate; order verification and duplicate-payment tests are present. | End-to-end provider sandbox reconciliation and a full financial workflow audit. |
| Private files | Tenant-specific keys, authorized download routes, optional S3-compatible production storage, bounded upload. | Real bucket integration, migration of legacy local uploads, malware scanning, lifecycle/backup policy. |
| Frontend | Shared design tokens, light/dark shell, role navigation, school branding, redesigned login, platform workspace, school settings and subscription screens. Platform workspace was checked at six widths. | Redesign and inspect the remaining ERP screens, tables, forms, empty/loading/error states, dark theme, keyboard and accessibility at all requested widths. |
| Operations | Alembic migrations, ready endpoint, local PostgreSQL rehearsal, Render Blueprint/cron configuration. | Customer-data staging migration, backup/restore test, real Render deployment and monitoring. The supplied Render database was not contacted. |

No customer school should be onboarded until the open authorization, payment, UI, and deployment gates are complete. The Render database password was supplied in chat and must be rotated before production use.
