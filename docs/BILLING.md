# Billing boundaries and current payment flow

School fees (`fees` and `payments`) record Parent → School money. SaaS invoices (`saas_invoices` and `saas_payments`) record School → Platform money. They use separate Razorpay credentials, routes, provider orders, audit records, and database tables.

For SaaS checkout, a school administrator selects an active paid plan. The server calculates the INR amount from `plans.price`, creates a Razorpay order, and stores one pending invoice per school. The school may retry the pending order. Verification checks the Razorpay signature and fetches both order and payment from the provider. It requires a captured payment with the exact order, amount and currency. A unique provider payment ID and one payment per invoice make repeated verification idempotent.

`POST /api/saas/webhooks/razorpay` verifies the raw-body HMAC with `SAAS_RAZORPAY_WEBHOOK_SECRET`, requires a unique provider event ID, and handles captured and failed payment events. A failed attempt leaves the order pending so it can be retried. Captured events recheck provider state before activating the subscription. Repeated event IDs do not create new payments or periods.

Configure `SAAS_RAZORPAY_KEY_ID`, `SAAS_RAZORPAY_KEY_SECRET`, and `SAAS_RAZORPAY_WEBHOOK_SECRET` separately from `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` for school fees. Tests mock the provider; no real Razorpay test transaction or live webhook has been verified. Refunds, chargebacks, tax invoices, recurring provider subscriptions and proration are not implemented. Do not use this flow for customer billing until those requirements and provider test-mode verification are complete.

The school-fee summary now excludes pending/void/refunded payments and subtracts discounts from outstanding balances. The legacy academic-year rollover still creates class-level arrears fees per student; it can multiply charges and must be redesigned around student-specific obligations before use.
