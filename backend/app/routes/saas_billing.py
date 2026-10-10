"""School-to-platform subscription billing, separate from school fees."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import Plan, PlatformAuditEvent, SaasInvoice, SaasProviderEvent, Subscription, Tenant, User
from backend.app.services.saas_billing_service import _client, finalize_payment, mark_failed, start_checkout
from backend.app.services.subscription_service import transition
from backend.app.utils.permissions import get_token_from_request
from backend.app.utils.security import decode_access_token

router = APIRouter(prefix="/saas", tags=["SaaS Billing"])


class CheckoutInput(BaseModel):
    plan_id: int


class VerifyInput(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def billing_admin(token: str = Depends(get_token_from_request), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token) if token else None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user = db.query(User).filter(User.id == user_id).first()
    if (not user or not user.is_active or user.role != "SCHOOL_ADMIN" or
        user.tenant_id is None or payload.get("tid") != user.tenant_id):
        raise HTTPException(status_code=403, detail="School administrator required")
    school = db.get(Tenant, user.tenant_id)
    if not school or school.status == "ARCHIVED":
        raise HTTPException(status_code=403, detail="School account unavailable")
    db.info.update(tenant_scope="tenant", tenant_id=user.tenant_id)
    return user


@router.get("/plans")
def payable_plans(admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    return [{"id": plan.id, "name": plan.name, "description": plan.description,
             "price": str(plan.price), "billing_interval": plan.billing_interval,
             "features": plan.features, "max_students": plan.max_students,
             "max_teachers": plan.max_teachers}
            for plan in db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price).all()]


@router.get("/subscription")
def school_subscription(admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.tenant_id == admin.tenant_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    plan = db.get(Plan, sub.plan_id)
    return {"id": sub.id, "plan_id": sub.plan_id, "plan_name": plan.name if plan else None,
            "status": sub.status,
            "trial_end": sub.trial_end, "current_period_end": sub.current_period_end,
            "grace_ends_at": sub.grace_ends_at}


@router.get("/invoices")
def school_invoices(admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    return [{"id": invoice.id, "plan_id": invoice.plan_id, "amount": str(invoice.amount),
             "currency": invoice.currency, "status": invoice.status,
             "created_at": invoice.created_at, "paid_at": invoice.paid_at}
            for invoice in db.query(SaasInvoice).filter(SaasInvoice.tenant_id == admin.tenant_id)
            .order_by(SaasInvoice.id.desc()).limit(100).all()]


@router.post("/checkout")
def create_checkout(data: CheckoutInput, admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    return start_checkout(db, admin.tenant_id, data.plan_id)


@router.post("/verify")
def verify_checkout(data: VerifyInput, admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    invoice = db.query(SaasInvoice).filter(SaasInvoice.tenant_id == admin.tenant_id,
                                           SaasInvoice.provider_order_id == data.razorpay_order_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    provider = _client()
    try:
        provider.utility.verify_payment_signature({
            "razorpay_order_id": data.razorpay_order_id,
            "razorpay_payment_id": data.razorpay_payment_id,
            "razorpay_signature": data.razorpay_signature,
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid payment signature") from exc
    return finalize_payment(db, invoice, data.razorpay_payment_id, provider)


@router.post("/cancel")
def cancel_subscription(admin: User = Depends(billing_admin), db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.tenant_id == admin.tenant_id).with_for_update().first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    try:
        transition(subscription, "CANCELLED")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    subscription.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(PlatformAuditEvent(actor_user_id=admin.id, tenant_id=admin.tenant_id,
                              action="SUBSCRIPTION_CANCELLED", details={}))
    db.commit()
    return {"status": subscription.status}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.SAAS_RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Subscription webhook is not configured")
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Webhook too large")
    supplied = request.headers.get("x-razorpay-signature", "")
    expected = hmac.new(settings.SAAS_RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    event_id = request.headers.get("x-razorpay-event-id")
    if not event_id or len(event_id) > 100:
        raise HTTPException(status_code=400, detail="Missing provider event ID")
    if db.query(SaasProviderEvent).filter(SaasProviderEvent.provider == "RAZORPAY",
                                           SaasProviderEvent.event_id == event_id).first():
        return {"status": "duplicate"}
    try:
        event = json.loads(body)
        event_type = event["event"]
        payment = event["payload"]["payment"]["entity"]
        if not isinstance(payment, dict) or not isinstance(payment.get("id"), str) or not isinstance(payment.get("order_id"), str):
            raise ValueError("Invalid payment")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed webhook") from exc
    invoice = db.query(SaasInvoice).filter(SaasInvoice.provider_order_id == payment.get("order_id")).first()
    outcome = "IGNORED"
    if invoice and event_type == "payment.captured":
        finalize_payment(db, invoice, payment["id"])
        outcome = "PROCESSED"
    elif invoice and event_type == "payment.failed":
        mark_failed(db, invoice)
        outcome = "PROCESSED"
    db.add(SaasProviderEvent(provider="RAZORPAY", event_id=event_id,
                             event_type=event_type, status=outcome))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    return {"status": outcome.lower()}
