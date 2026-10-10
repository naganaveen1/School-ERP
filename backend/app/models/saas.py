"""Platform-owned plans, school subscriptions, and platform audit events."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.sql import func

from backend.app.database import Base


SUBSCRIPTION_STATUSES = ("TRIALING", "ACTIVE", "PAST_DUE", "PAUSED", "CANCELLED", "EXPIRED")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    billing_interval = Column(String(20), nullable=False, default="MONTHLY")
    trial_days = Column(Integer, nullable=False, default=14)
    max_students = Column(Integer)
    max_teachers = Column(Integer)
    max_admins = Column(Integer)
    max_storage = Column(Integer)  # Bytes
    features = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("status IN ('TRIALING','ACTIVE','PAST_DUE','PAUSED','CANCELLED','EXPIRED')", name="ck_subscriptions_status"),
        UniqueConstraint("tenant_id", name="uq_subscriptions_tenant"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="TRIALING", index=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    trial_start = Column(DateTime)
    trial_end = Column(DateTime)
    grace_ends_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    provider = Column(String(30))
    provider_customer_id = Column(String(100))
    provider_subscription_id = Column(String(100), unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAuditEvent(Base):
    __tablename__ = "platform_audit_events"

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="SET NULL"), index=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SaasInvoice(Base):
    __tablename__ = "saas_invoices"
    __table_args__ = (
        Index("uq_saas_invoice_pending_tenant", "tenant_id", unique=True,
              sqlite_where=text("status = 'PENDING'"), postgresql_where=text("status = 'PENDING'")),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    provider_order_id = Column(String(100), nullable=False, unique=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    paid_at = Column(DateTime)


class SaasPayment(Base):
    __tablename__ = "saas_payments"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("saas_invoices.id", ondelete="RESTRICT"), nullable=False, unique=True)
    provider_payment_id = Column(String(100), nullable=False, unique=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(20), nullable=False, default="CAPTURED")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SaasProviderEvent(Base):
    __tablename__ = "saas_provider_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_saas_provider_event"),)

    id = Column(Integer, primary_key=True)
    provider = Column(String(30), nullable=False)
    event_id = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="PROCESSED")
    received_at = Column(DateTime, nullable=False, server_default=func.now())
