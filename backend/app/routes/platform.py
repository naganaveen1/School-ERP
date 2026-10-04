"""Platform administration. School ERP sessions cannot enter these endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Plan, PlatformAuditEvent, SaasPayment, Student, Subscription, Teacher, Tenant, User
from backend.app.utils.permissions import require_roles
from backend.app.utils.security import get_password_hash

router = APIRouter(prefix="/platform", tags=["Platform"])
reader = require_roles(["PLATFORM_SUPER_ADMIN", "PLATFORM_SUPPORT", "PLATFORM_BILLING"])
owner = require_roles(["PLATFORM_SUPER_ADMIN"])


class PlanInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    price: Decimal = Field(ge=0)
    billing_interval: str = Field(pattern="^(MONTHLY|YEARLY)$")
    trial_days: int = Field(default=14, ge=0, le=365)
    max_students: Optional[int] = Field(default=None, ge=1)
    max_teachers: Optional[int] = Field(default=None, ge=1)
    max_admins: Optional[int] = Field(default=None, ge=1)
    max_storage: Optional[int] = Field(default=None, ge=1)
    features: list[str] = Field(default_factory=list)
    is_active: bool = True


class SchoolInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    email: EmailStr
    admin_name: str = Field(min_length=2, max_length=100)
    admin_username: str = Field(min_length=2, max_length=50)
    admin_email: EmailStr
    admin_password: str = Field(min_length=12)
    plan_id: int


class SchoolPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    status: Optional[str] = Field(default=None, pattern="^(TRIAL|ACTIVE|SUSPENDED|EXPIRED|CANCELLED|ARCHIVED)$")
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    primary_color: Optional[str] = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    secondary_color: Optional[str] = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    logo_url: Optional[str] = None


class PlanChange(BaseModel):
    plan_id: int


class TrialExtension(BaseModel):
    days: int = Field(ge=1, le=365)


def _audit(db, actor, action, tenant_id=None, details=None):
    db.add(PlatformAuditEvent(actor_user_id=actor.id, tenant_id=tenant_id,
                              action=action, details=details or {}))


def _school(db, school_id):
    school = db.get(Tenant, school_id)
    if school is None:
        raise HTTPException(404, "School not found")
    return school


@router.get("/dashboard")
def dashboard(actor: User = Depends(reader), db: Session = Depends(get_db)):
    schools = dict(db.execute(select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)).all())
    # These are deliberately Core aggregates: platform identities do not have ERP ORM access.
    students = db.connection().execute(select(func.count(Student.__table__.c.id))).scalar_one()
    teachers = db.connection().execute(select(func.count(Teacher.__table__.c.id))).scalar_one()
    active_value = db.execute(select(func.coalesce(func.sum(Plan.price), 0)).join(
        Subscription, Subscription.plan_id == Plan.id).where(Subscription.status == "ACTIVE")).scalar_one()
    captured_revenue = db.connection().execute(select(func.coalesce(func.sum(SaasPayment.__table__.c.amount), 0))).scalar_one()
    new_schools = db.execute(select(func.count(Tenant.id)).where(
        Tenant.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30))).scalar_one()
    return {"total_schools": sum(schools.values()), "schools_by_status": schools,
            "total_students": students, "total_teachers": teachers,
            "active_plan_value": str(active_value), "captured_saas_revenue": str(captured_revenue),
            "new_schools_30d": new_schools}


@router.get("/schools")
def list_schools(actor: User = Depends(reader), db: Session = Depends(get_db)):
    return [{"id": school.id, "name": school.name, "slug": school.slug,
             "status": school.status, "email": school.email}
            for school in db.query(Tenant).order_by(Tenant.id.desc()).all()]


@router.get("/schools/{school_id}")
def get_school(school_id: int, actor: User = Depends(reader), db: Session = Depends(get_db)):
    school = _school(db, school_id)
    subscription = db.query(Subscription).filter(Subscription.tenant_id == school_id).first()
    student_count = db.connection().execute(select(func.count(Student.__table__.c.id)).where(Student.__table__.c.tenant_id == school_id)).scalar_one()
    teacher_count = db.connection().execute(select(func.count(Teacher.__table__.c.id)).where(Teacher.__table__.c.tenant_id == school_id)).scalar_one()
    return {"id": school.id, "name": school.name, "slug": school.slug, "status": school.status,
            "email": school.email, "phone": school.phone, "primary_color": school.primary_color,
            "secondary_color": school.secondary_color, "logo_url": school.logo_url,
            "usage": {"students": student_count, "teachers": teacher_count},
            "subscription": {"id": subscription.id, "plan_id": subscription.plan_id,
                             "status": subscription.status, "trial_end": subscription.trial_end}
            if subscription else None}


@router.post("/schools", status_code=201)
def create_school(data: SchoolInput, actor: User = Depends(owner), db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.slug == data.slug).first():
        raise HTTPException(409, "School slug already exists")
    plan = db.get(Plan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(404, "Active plan not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    school = Tenant(name=data.name, slug=data.slug, email=data.email, status="TRIAL")
    try:
        db.add(school)
        db.flush()
        # Scope the administrator write to the newly created school, in the same transaction.
        db.info.update(tenant_scope="tenant", tenant_id=school.id)
        admin = User(username=data.admin_username, email=data.admin_email,
                     full_name=data.admin_name, hashed_password=get_password_hash(data.admin_password),
                     role="SCHOOL_ADMIN", is_active=True)
        db.add(admin)
        db.flush()
        db.info.update(tenant_scope="platform", tenant_id=None)
        subscription = Subscription(tenant_id=school.id, plan_id=plan.id, status="TRIALING",
                                    trial_start=now, trial_end=now + timedelta(days=plan.trial_days))
        db.add(subscription)
        _audit(db, actor, "SCHOOL_CREATED", school.id, {"plan_id": plan.id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.info.update(tenant_scope="platform", tenant_id=None)
    return {"id": school.id, "slug": school.slug, "admin_user_id": admin.id,
            "subscription_id": subscription.id}


@router.patch("/schools/{school_id}")
def update_school(school_id: int, data: SchoolPatch, actor: User = Depends(owner), db: Session = Depends(get_db)):
    school = _school(db, school_id)
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(school, key, value)
    _audit(db, actor, "SCHOOL_UPDATED", school.id, {"fields": list(changes)})
    db.commit()
    return {"id": school.id, "status": school.status}


@router.get("/plans")
def list_plans(actor: User = Depends(reader), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "description": p.description, "price": str(p.price),
             "billing_interval": p.billing_interval, "trial_days": p.trial_days,
             "max_students": p.max_students, "max_teachers": p.max_teachers,
             "max_admins": p.max_admins, "max_storage": p.max_storage,
             "features": p.features, "is_active": p.is_active}
            for p in db.query(Plan).order_by(Plan.id).all()]


@router.post("/plans", status_code=201)
def create_plan(data: PlanInput, actor: User = Depends(owner), db: Session = Depends(get_db)):
    if db.query(Plan).filter(Plan.name == data.name).first():
        raise HTTPException(409, "Plan name already exists")
    plan = Plan(**data.model_dump())
    db.add(plan)
    db.flush()
    _audit(db, actor, "PLAN_CREATED", details={"plan_id": plan.id})
    db.commit()
    return {"id": plan.id}


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, data: PlanInput, actor: User = Depends(owner), db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    if db.query(Plan).filter(Plan.name == data.name, Plan.id != plan_id).first():
        raise HTTPException(409, "Plan name already exists")
    for key, value in data.model_dump().items():
        setattr(plan, key, value)
    _audit(db, actor, "PLAN_UPDATED", details={"plan_id": plan.id})
    db.commit()
    return {"id": plan.id}


@router.post("/schools/{school_id}/change-plan")
def change_school_plan(school_id: int, data: PlanChange, actor: User = Depends(owner),
                       db: Session = Depends(get_db)):
    _school(db, school_id)
    plan = db.get(Plan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(404, "Active plan not found")
    subscription = db.query(Subscription).filter(Subscription.tenant_id == school_id).first()
    if not subscription:
        raise HTTPException(404, "Subscription not found")
    previous = subscription.plan_id
    subscription.plan_id = plan.id
    _audit(db, actor, "SUBSCRIPTION_PLAN_CHANGED", school_id,
           {"previous_plan_id": previous, "plan_id": plan.id})
    db.commit()
    return {"id": subscription.id, "plan_id": plan.id, "status": subscription.status}


@router.post("/schools/{school_id}/extend-trial")
def extend_trial(school_id: int, data: TrialExtension, actor: User = Depends(owner),
                 db: Session = Depends(get_db)):
    _school(db, school_id)
    subscription = db.query(Subscription).filter(Subscription.tenant_id == school_id).first()
    if not subscription or subscription.status != "TRIALING":
        raise HTTPException(409, "School does not have a trial subscription")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subscription.trial_end = max(subscription.trial_end or now, now) + timedelta(days=data.days)
    _audit(db, actor, "TRIAL_EXTENDED", school_id, {"days": data.days})
    db.commit()
    return {"trial_end": subscription.trial_end}


@router.get("/subscriptions")
def list_subscriptions(actor: User = Depends(reader), db: Session = Depends(get_db)):
    return [{"id": s.id, "tenant_id": s.tenant_id, "plan_id": s.plan_id,
             "status": s.status, "trial_end": s.trial_end,
             "current_period_end": s.current_period_end}
            for s in db.query(Subscription).order_by(Subscription.id.desc()).all()]


@router.get("/audit")
def list_audit(actor: User = Depends(reader), db: Session = Depends(get_db)):
    return [{"id": e.id, "actor_user_id": e.actor_user_id, "tenant_id": e.tenant_id,
             "action": e.action, "details": e.details, "created_at": e.created_at}
            for e in db.query(PlatformAuditEvent).order_by(PlatformAuditEvent.id.desc()).limit(100).all()]
