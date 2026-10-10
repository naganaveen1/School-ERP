"""Subscription lifecycle rules shared by authentication and billing."""

from datetime import datetime, timezone

from backend.app.models.saas import Subscription


ALLOWED_TRANSITIONS = {
    "TRIALING": {"ACTIVE", "EXPIRED", "CANCELLED"},
    "ACTIVE": {"PAST_DUE", "PAUSED", "CANCELLED", "EXPIRED"},
    "PAST_DUE": {"ACTIVE", "PAUSED", "EXPIRED", "CANCELLED"},
    "PAUSED": {"ACTIVE", "CANCELLED", "EXPIRED"},
    "CANCELLED": {"ACTIVE"},
    "EXPIRED": {"ACTIVE"},
}


def can_access_school(subscription: Subscription) -> bool:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if subscription.status == "TRIALING":
        return subscription.trial_end is not None and subscription.trial_end > now
    if subscription.status == "ACTIVE":
        return subscription.current_period_end is None or subscription.current_period_end > now
    if subscription.status == "PAST_DUE":
        return subscription.grace_ends_at is not None and subscription.grace_ends_at > now
    return False


def transition(subscription: Subscription, new_status: str):
    if new_status not in ALLOWED_TRANSITIONS.get(subscription.status, set()):
        raise ValueError(f"Invalid subscription transition: {subscription.status} -> {new_status}")
    subscription.status = new_status
