# Security status

The application uses bearer tokens, server-owned tenant context, role checks, resource checks for several sensitive paths, bounded private uploads, and provider payment verification. Production requires PostgreSQL, a random JWT secret, exact CORS origins, and a private S3-compatible bucket. New file keys include the server-derived tenant ID; downloads resolve a scoped database record and resource ownership before reading the object. SaaS and school fee Razorpay credentials are separate.

The supplied database password was shared in chat. Rotate it before production use; it was not committed. No production customer database or Render service was modified in this work.

Outstanding production security work includes a full same-school authorization audit, token storage hardening (the static frontend still uses `localStorage`), rate limiting and account lockout, malware/content scanning for uploads, S3 migration of old local files, webhook/provider test-mode verification, and an operational backup/restore drill. Do not treat the current test pass as a production security sign-off.
