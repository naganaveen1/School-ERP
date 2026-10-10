"""Advance time-based subscription states. Schedule at least daily."""

from datetime import datetime, timedelta, timezone

from backend.app.database import SessionLocal
from backend.app.models import PlatformAuditEvent, Subscription, Tenant
from backend.app.services.subscription_service import transition


def reconcile(db, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    changed = 0
    for subscription in db.query(Subscription).filter(
        Subscription.status.in_(["TRIALING", "ACTIVE", "PAST_DUE"])
    ).with_for_update().all():
        previous = subscription.status
        if subscription.status == "TRIALING" and subscription.trial_end and subscription.trial_end <= now:
            transition(subscription, "EXPIRED")
        elif subscription.status == "ACTIVE" and subscription.current_period_end and subscription.current_period_end <= now:
            transition(subscription, "PAST_DUE")
            subscription.grace_ends_at = subscription.current_period_end + timedelta(days=7)
        if subscription.status == "PAST_DUE" and subscription.grace_ends_at and subscription.grace_ends_at <= now:
            transition(subscription, "EXPIRED")
        if subscription.status != previous:
            if subscription.status == "EXPIRED":
                school = db.get(Tenant, subscription.tenant_id)
                if school:
                    school.status = "EXPIRED"
            db.add(PlatformAuditEvent(tenant_id=subscription.tenant_id,
                                      action="SUBSCRIPTION_STATUS_CHANGED",
                                      details={"from": previous, "to": subscription.status}))
            changed += 1
    db.commit()
    return changed


if __name__ == "__main__":
    with SessionLocal() as session:
        print(f"Reconciled {reconcile(session)} subscriptions")
