from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.complaint import Complaint
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/complaints", tags=["Complaints"])

class ComplaintCreate(BaseModel):
    title: str
    description: str

class ComplaintResolve(BaseModel):
    status: str  # IN_REVIEW, RESOLVED, REJECTED
    resolution: str

@router.post("")
def submit_complaint(
    c_in: ComplaintCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    complaint = Complaint(
        user_id=current_user.id,
        title=c_in.title,
        description=c_in.description,
        status="PENDING"
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    log_audit_action(db, "COMPLAINT_SUBMIT", "Complaint", str(complaint.id), f"Complaint submitted: {c_in.title}", current_user.id)
    return {"message": "Complaint submitted successfully", "id": complaint.id, "status": complaint.status}

@router.get("/my")
def get_my_complaints(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    complaints = db.query(Complaint).filter(Complaint.user_id == current_user.id).order_by(Complaint.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "status": c.status,
            "resolution": c.resolution,
            "created_at": c.created_at,
            "updated_at": c.updated_at
        }
        for c in complaints
    ]

@router.get("")
def list_all_complaints(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    query = db.query(Complaint).options(joinedload(Complaint.user))
    if status_filter:
        query = query.filter(Complaint.status == status_filter.upper())
    complaints = query.order_by(Complaint.created_at.desc()).all()

    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "user_name": c.user.full_name if c.user else "Unknown",
            "user_role": c.user.role if c.user else "",
            "title": c.title,
            "description": c.description,
            "status": c.status,
            "resolution": c.resolution,
            "created_at": c.created_at,
            "updated_at": c.updated_at
        }
        for c in complaints
    ]

@router.patch("/{complaint_id}/resolve")
def resolve_complaint(
    complaint_id: int,
    res_in: ComplaintResolve,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.status = res_in.status.upper()
    complaint.resolution = res_in.resolution
    complaint.resolved_by = current_user.id
    db.commit()

    notification_service.create_notification(
        db=db,
        user_id=complaint.user_id,
        title=f"Complaint Status: {complaint.status.capitalize()}",
        message=f"Regarding '{complaint.title}': {complaint.resolution}",
        notification_type="INFO"
    )

    log_audit_action(db, "COMPLAINT_RESOLVE", "Complaint", str(complaint.id), f"Resolved status: {complaint.status}", current_user.id)
    return {"message": "Complaint updated successfully", "status": complaint.status}
