from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.leave import Leave
from backend.app.models.complaint import Complaint
from backend.app.models.student import Student
from backend.app.models.teacher import Teacher
from backend.app.services.report_service import report_service
from backend.app.utils.permissions import require_roles

router = APIRouter(prefix="/principal", tags=["Principal"])

@router.get("/dashboard")
def get_principal_dashboard(
    current_user: User = Depends(require_roles(["PRINCIPAL", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    return report_service.get_principal_dashboard(db)

@router.get("/leave-requests")
def get_leave_requests(
    current_user: User = Depends(require_roles(["PRINCIPAL", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    leaves = db.query(Leave).order_by(Leave.created_at.desc()).all()
    return [
        {
            "id": l.id,
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

@router.get("/complaints")
def get_complaints(
    current_user: User = Depends(require_roles(["PRINCIPAL", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "user_name": c.user.full_name if c.user else "",
            "user_role": c.user.role if c.user else "",
            "title": c.title,
            "description": c.description,
            "status": c.status,
            "resolution": c.resolution,
            "created_at": c.created_at
        }
        for c in complaints
    ]
