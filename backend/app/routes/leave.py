from datetime import date
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.leave import Leave
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/leave", tags=["Leave Management"])

class LeaveApplyRequest(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str

class LeaveReviewRequest(BaseModel):
    status: str  # APPROVED, REJECTED
    remarks: Optional[str] = None

@router.post("")
def apply_leave(
    leave_in: LeaveApplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    leave = Leave(
        user_id=current_user.id,
        applicant_role=current_user.role,
        leave_type=leave_in.leave_type,
        start_date=leave_in.start_date,
        end_date=leave_in.end_date,
        reason=leave_in.reason,
        status="PENDING"
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)

    log_audit_action(db, "LEAVE_APPLY", "Leave", str(leave.id), f"Leave application by {current_user.username}", current_user.id)

    return {
        "message": "Leave application submitted successfully",
        "id": leave.id,
        "status": leave.status
    }

@router.get("/my")
def get_my_leaves(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    leaves = db.query(Leave).filter(Leave.user_id == current_user.id).order_by(Leave.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "leave_type": l.leave_type,
            "start_date": str(l.start_date),
            "end_date": str(l.end_date),
            "reason": l.reason,
            "status": l.status,
            "remarks": l.remarks,
            "created_at": l.created_at
        }
        for l in leaves
    ]

@router.get("")
def list_all_leaves(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    query = db.query(Leave).options(joinedload(Leave.user))
    if status_filter:
        query = query.filter(Leave.status == status_filter.upper())
    leaves = query.order_by(Leave.created_at.desc()).all()

    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "applicant_name": l.user.full_name if l.user else "",
            "applicant_role": l.applicant_role,
            "leave_type": l.leave_type,
            "start_date": str(l.start_date),
            "end_date": str(l.end_date),
            "reason": l.reason,
            "status": l.status,
            "remarks": l.remarks,
            "created_at": l.created_at
        }
        for l in leaves
    ]

@router.patch("/{leave_id}/review")
def review_leave(
    leave_id: int,
    review_in: LeaveReviewRequest,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    status_val = review_in.status.upper()
    if status_val not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED")

    leave.status = status_val
    leave.remarks = review_in.remarks
    leave.reviewed_by = current_user.id
    db.commit()

    # Notify applicant
    notification_service.create_notification(
        db=db,
        user_id=leave.user_id,
        title=f"Leave Request {status_val.capitalize()}",
        message=f"Your leave request for {leave.start_date} to {leave.end_date} was {status_val.lower()}.",
        link=None,
        notification_type="SUCCESS" if status_val == "APPROVED" else "WARNING"
    )

    log_audit_action(db, f"LEAVE_{status_val}", "Leave", str(leave.id), f"Leave {status_val} with remarks: {review_in.remarks}", current_user.id)

    return {"message": f"Leave request {status_val.lower()} successfully", "status": status_val}
