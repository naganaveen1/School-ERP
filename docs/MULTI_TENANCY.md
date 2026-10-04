# Tenant ownership design

## Data classification

Platform data: tenant registry, platform accounts (users with no tenant), plans, subscriptions, SaaS invoices/payments, provider events, and platform audit events. `Role` remains a global role definition. These records are managed only through platform endpoints.

School data: school users and profiles, departments, academic years, classes, sections, subjects, enrollments, timetable, attendance, leave, assignments, submissions, materials, exams, results, school fees and payments, notices, notifications, events, messages, complaints, documents, and ERP audit logs. These records carry a non-null `tenant_id`, except `User` whose null tenant denotes a platform identity.

## Context and isolation

The school user's database record establishes the tenant context after bearer authentication. Browser-supplied tenant IDs are ignored. A SQLAlchemy session policy applies tenant predicates to ORM reads and writes. New records receive the current tenant ID; explicit conflicting tenant IDs or foreign keys to another tenant are rejected before commit. Platform identities cannot read school tables through regular school sessions. Route-specific role and resource ownership rules remain additional requirements.

The static frontend can use `/school/{slug}` as an entry URL, which resolves to a branded login page. API authorization comes from the logged-in user's tenant, regardless of URL. Custom domains can later resolve to the same slug. The login slug narrows identity lookup and cannot grant access to a tenant by itself.

## Migration

The migration creates a default tenant for legacy single-school records, fills tenant keys, converts `ADMIN` to `SCHOOL_ADMIN`, then enforces non-null keys and indexes. It passed a synthetic legacy data rehearsal on local PostgreSQL and a copied legacy SQLite database. Two-school API tests cover login, student/fee reads, cross-school writes and platform creation. A full route-by-route resource authorization audit remains open; do not onboard customer schools yet.
