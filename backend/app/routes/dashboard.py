from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services.report_service import report_service
from backend.app.utils.permissions import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("")
def get_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    role = current_user.role
    if role == "SCHOOL_ADMIN":
        return report_service.get_admin_dashboard(db)
    elif role == "PRINCIPAL":
        return report_service.get_principal_dashboard(db)
    elif role == "TEACHER":
        if not current_user.teacher_profile:
            raise HTTPException(status_code=400, detail="Teacher profile not found")
        return report_service.get_teacher_dashboard(db, current_user.teacher_profile.id)
    elif role == "STUDENT":
        if not current_user.student_profile:
            raise HTTPException(status_code=400, detail="Student profile not found")
        return report_service.get_student_dashboard(db, current_user.student_profile.id)
    elif role == "PARENT":
        if not current_user.parent_profile:
            raise HTTPException(status_code=400, detail="Parent profile not found")
        return report_service.get_parent_dashboard(db, current_user.parent_profile.id)
    else:
        raise HTTPException(status_code=400, detail="Unknown role")
