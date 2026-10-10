from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.audit_log import AuditLog
from backend.app.utils.permissions import require_roles, get_current_tenant
from backend.app.models.tenant import Tenant
from backend.app.utils.helpers import log_audit_action
from backend.app.utils.pagination import paginate_query
from backend.app.services.report_service import report_service

router = APIRouter(prefix="/admin", tags=["Admin"])


class SchoolSettingsPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    legal_name: Optional[str] = Field(default=None, max_length=180)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=30)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    logo_url: Optional[str] = Field(default=None, pattern="^https://", max_length=500)
    favicon_url: Optional[str] = Field(default=None, pattern="^https://", max_length=500)
    primary_color: Optional[str] = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    secondary_color: Optional[str] = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    timezone: Optional[str] = Field(default=None, max_length=80)
    currency: Optional[str] = Field(default=None, pattern="^[A-Z]{3}$")


def _school_settings(school: Tenant):
    return {key: getattr(school, key) for key in (
        "id", "name", "slug", "legal_name", "email", "phone", "address", "city", "state",
        "country", "postal_code", "logo_url", "favicon_url", "primary_color",
        "secondary_color", "timezone", "currency", "status"
    )}


@router.get("/school-settings")
def get_school_settings(current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
                        school: Tenant = Depends(get_current_tenant)):
    return _school_settings(school)


@router.patch("/school-settings")
def update_school_settings(data: SchoolSettingsPatch,
                           current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
                           school: Tenant = Depends(get_current_tenant),
                           db: Session = Depends(get_db)):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "timezone" in changes:
        try:
            ZoneInfo(changes["timezone"])
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=400, detail="Unknown timezone") from exc
    for key, value in changes.items():
        setattr(school, key, value)
    db.commit()
    log_audit_action(db, "SCHOOL_SETTINGS_UPDATE", "Tenant", str(school.id),
                     f"Updated school settings: {', '.join(changes)}", current_user.id)
    return _school_settings(school)

@router.get("/overview")
def get_admin_overview(
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    return report_service.get_admin_dashboard(db)

@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = None,
    entity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity:
        query = query.filter(AuditLog.entity.ilike(f"%{entity}%"))
    query = query.order_by(AuditLog.timestamp.desc())

    paginated = paginate_query(query, page, page_size)
    items = []
    for log in paginated["items"]:
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else "System",
            "action": log.action,
            "entity": log.entity,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "timestamp": log.timestamp
        })
    paginated["items"] = items
    return paginated

@router.get("/settings")
def get_system_settings(
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"]))
):
    from backend.app.config import settings
    return {
        "project_name": settings.PROJECT_NAME,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES
    }
