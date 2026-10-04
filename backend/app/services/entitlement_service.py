"""Central subscription feature and seat checks for school operations."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models import Plan, Student, Subscription, Teacher, User
from backend.app.services.subscription_service import can_access_school


class FeatureEntitlementService:
    def active_plan(self, db: Session) -> Plan:
        tenant_id = db.info.get("tenant_id")
        if db.info.get("tenant_scope") != "tenant" or tenant_id is None:
            raise HTTPException(status_code=403, detail="School context required")
        subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
        if not subscription or not can_access_school(subscription):
            raise HTTPException(status_code=403, detail={"code": "SUBSCRIPTION_INACTIVE"})
        plan = db.get(Plan, subscription.plan_id)
        if not plan:
            raise HTTPException(status_code=403, detail={"code": "PLAN_UNAVAILABLE"})
        return plan

    def has_feature(self, db: Session, feature: str) -> bool:
        return feature in (self.active_plan(db).features or [])

    def require_feature(self, db: Session, feature: str):
        if not self.has_feature(db, feature):
            raise HTTPException(status_code=403, detail={"code": "FEATURE_NOT_INCLUDED", "feature": feature})

    def check_usage(self, db: Session, resource: str):
        plan = self.active_plan(db)
        specs = {
            "students": (plan.max_students, Student),
            "teachers": (plan.max_teachers, Teacher),
            "admins": (plan.max_admins, User),
        }
        if resource not in specs:
            raise ValueError("Unsupported usage resource")
        maximum, model = specs[resource]
        if maximum is None:
            return
        query = db.query(model)
        if resource == "admins":
            query = query.filter(User.role == "SCHOOL_ADMIN")
        current = query.count()
        if current >= maximum:
            raise HTTPException(status_code=409, detail={"code": "USAGE_LIMIT_REACHED",
                                                        "resource": resource, "limit": maximum,
                                                        "current": current})


entitlement_service = FeatureEntitlementService()
