"""Razorpay orders and captured payments for School -> platform subscriptions.

This module never writes the school fee or payment tables.
"""

import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import Plan, PlatformAuditEvent, SaasInvoice, SaasPayment, Subscription, Tenant
from backend.app.services.subscription_service import transition


def _client():
    if not settings.SAAS_RAZORPAY_KEY_ID or not settings.SAAS_RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Subscription payments are not configured")
    import razorpay
    return razorpay.Client(auth=(settings.SAAS_RAZORPAY_KEY_ID, settings.SAAS_RAZORPAY_KEY_SECRET))


def _paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _period_end(start: datetime, interval: str) -> datetime:
    year = start.year + (1 if interval == "YEARLY" else 0)
    month = start.month
    if interval == "MONTHLY":
        month += 1
        if month == 13:
            year += 1
            month = 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def start_checkout(db: Session, tenant_id: int, plan_id: int):
    subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).with_for_update().first()
    plan = db.get(Plan, plan_id)
    if not subscription or not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Subscription or active plan not found")
    if plan.price <= 0:
        raise HTTPException(status_code=400, detail="This plan has no payable checkout")
    pending = db.query(SaasInvoice).filter(SaasInvoice.tenant_id == tenant_id,
                                           SaasInvoice.status == "PENDING").first()
    if pending:
        if pending.plan_id != plan_id:
            raise HTTPException(status_code=409, detail="Complete or resolve the pending checkout first")
        return {"order_id": pending.provider_order_id, "invoice_id": pending.id,
                "amount": _paise(pending.amount), "currency": pending.currency,
                "key_id": settings.SAAS_RAZORPAY_KEY_ID}
    amount = _paise(plan.price)
    try:
        order = _client().order.create({"amount": amount, "currency": "INR",
                                        "receipt": f"saas-{tenant_id}-{int(datetime.now(timezone.utc).timestamp())}"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Payment provider order creation failed") from exc
    if order.get("amount") != amount or order.get("currency") != "INR" or not order.get("id"):
        raise HTTPException(status_code=502, detail="Payment provider returned an invalid order")
    invoice = SaasInvoice(tenant_id=tenant_id, subscription_id=subscription.id, plan_id=plan.id,
                          provider_order_id=order["id"], amount=plan.price, currency="INR", status="PENDING")
    db.add(invoice)
    db.commit()
    return {"order_id": order["id"], "invoice_id": invoice.id, "amount": amount,
            "currency": "INR", "key_id": settings.SAAS_RAZORPAY_KEY_ID}


def finalize_payment(db: Session, invoice: SaasInvoice, payment_id: str, client=None):
    invoice = db.query(SaasInvoice).filter(SaasInvoice.id == invoice.id).with_for_update().one()
    existing = db.query(SaasPayment).filter(SaasPayment.invoice_id == invoice.id).first()
    if existing:
        if existing.provider_payment_id != payment_id:
            raise HTTPException(status_code=409, detail="Invoice already paid with a different payment")
        return {"invoice_id": invoice.id, "payment_id": existing.id, "status": "PAID"}
    if invoice.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invoice is no longer payable")
    if db.query(SaasPayment).filter(SaasPayment.provider_payment_id == payment_id).first():
        raise HTTPException(status_code=409, detail="Payment is already assigned to another invoice")
    provider = client or _client()
    try:
        order = provider.order.fetch(invoice.provider_order_id)
        payment = provider.payment.fetch(payment_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Payment provider lookup failed") from exc
    expected = _paise(invoice.amount)
    if (order.get("id") != invoice.provider_order_id or order.get("amount") != expected or
        order.get("currency") != "INR" or payment.get("order_id") != invoice.provider_order_id or
        payment.get("status") != "captured" or payment.get("amount") != expected or
        payment.get("currency") != "INR"):
        raise HTTPException(status_code=409, detail="Payment details did not match the invoice")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subscription = db.query(Subscription).filter(Subscription.id == invoice.subscription_id).with_for_update().one()
    if subscription.tenant_id != invoice.tenant_id:
        raise HTTPException(status_code=409, detail="Subscription mismatch")
    plan = db.get(Plan, invoice.plan_id)
    if not plan:
        raise HTTPException(status_code=409, detail="Plan unavailable")
    start = (subscription.current_period_end if subscription.status == "ACTIVE" and
             subscription.plan_id == plan.id and subscription.current_period_end and
             subscription.current_period_end > now else now)
    if subscription.status != "ACTIVE":
        transition(subscription, "ACTIVE")
    subscription.plan_id = plan.id
    subscription.current_period_start = start
    subscription.current_period_end = _period_end(start, plan.billing_interval)
    subscription.grace_ends_at = None
    subscription.cancelled_at = None
    tenant = db.get(Tenant, invoice.tenant_id)
    tenant.status = "ACTIVE"
    invoice.status = "PAID"
    invoice.paid_at = now
    record = SaasPayment(tenant_id=invoice.tenant_id, invoice_id=invoice.id,
                         provider_payment_id=payment_id, amount=invoice.amount,
                         currency="INR", status="CAPTURED")
    db.add(record)
    db.add(PlatformAuditEvent(tenant_id=invoice.tenant_id, action="SAAS_PAYMENT_CAPTURED",
                              details={"invoice_id": invoice.id, "plan_id": plan.id}))
    db.commit()
    return {"invoice_id": invoice.id, "payment_id": record.id, "status": "PAID"}


def mark_failed(db: Session, invoice: SaasInvoice):
    invoice = db.query(SaasInvoice).filter(SaasInvoice.id == invoice.id).with_for_update().one()
    if invoice.status != "PENDING":
        return
    # One failed attempt does not close a Razorpay order. It may be retried or
    # later captured, so keep the invoice pending until a captured payment.
    subscription = db.query(Subscription).filter(Subscription.id == invoice.subscription_id).with_for_update().one()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if subscription.status == "ACTIVE" and subscription.current_period_end and subscription.current_period_end <= now:
        transition(subscription, "PAST_DUE")
        subscription.grace_ends_at = now + timedelta(days=7)
    db.add(PlatformAuditEvent(tenant_id=invoice.tenant_id, action="SAAS_PAYMENT_FAILED",
                              details={"invoice_id": invoice.id}))
    db.commit()
