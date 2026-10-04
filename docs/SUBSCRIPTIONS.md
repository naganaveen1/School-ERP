# Subscription rules

Each school has one subscription and an assigned plan. Plans carry features and student, teacher and administrator limits. The migration grants the existing school an explicit inactive-for-sale Legacy plan with unmetered ERP features. New schools receive a `TRIALING` subscription during platform onboarding.

Authentication grants school ERP access for an unexpired trial, an active paid period, or a `PAST_DUE` period within its seven-day grace window. An expired school administrator may sign in to the subscription page, but ordinary ERP endpoints reject that token. Platform operators may extend a trial or change a plan; those actions are audited. Plan changes are immediate and do not calculate proration.

Captured SaaS payment moves a subscription to `ACTIVE`, sets a monthly or yearly period, and reactivates an expired school. A renewal on the same plan starts after the current paid period; a plan change starts a new period immediately. Cancellation is immediate and ends ERP access. `scripts/reconcile_subscriptions.py` advances expired trials and paid periods through `PAST_DUE` and `EXPIRED`; schedule it at least daily in deployment. Access checks also enforce timestamps if the job runs late.

Allowed status transitions are centralized in `backend/app/services/subscription_service.py`. Automatic recurring charging, invoice PDFs, tax handling, refunds, chargebacks and proration remain open.
