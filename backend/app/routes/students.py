from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.parent import Parent
from backend.app.models.teacher import Teacher
from backend.app.schemas.student import StudentCreate, StudentUpdate, StudentResponse
from backend.app.services.student_service import student_service
from backend.app.services.attendance_service import attendance_service
from backend.app.services.fee_service import fee_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.pagination import paginate_query
from backend.app.utils.helpers import log_audit_action

from backend.app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/students", tags=["Students"])

def verify_student_access(student_id: int, current_user: User, db: Session) -> Student:
    student = student_service.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role in ["SCHOOL_ADMIN", "PRINCIPAL"]:
        return student

    if current_user.role == "STUDENT":
        if student.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Students can only access their own records")
        return student

    if current_user.role == "PARENT":
        parent = db.query(Parent).filter(Parent.user_id == current_user.id).first()
        if not parent or student.parent_id != parent.id:
            raise HTTPException(status_code=403, detail="Parents can only access their linked children")
        return student

    if current_user.role == "TEACHER":
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            # Check if teacher teaches this student's class or section
            teaches_subject = any(s.class_id == student.class_id for s in teacher.subjects)
            is_class_teacher = any(sec.id == student.section_id for sec in teacher.sections)
            if teaches_subject or is_class_teacher:
                return student
        raise HTTPException(status_code=403, detail="Teachers can only access students in their assigned classes")

    raise HTTPException(status_code=403, detail="Access denied")

@router.get("", response_model=dict)
def list_students(
    search: Optional[str] = None,
    class_id: Optional[int] = None,
    section_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL", "TEACHER"])),
    db: Session = Depends(get_db)
):
    query = db.query(Student).join(Student.user).options(
        joinedload(Student.user),
        joinedload(Student.class_obj),
        joinedload(Student.section),
        joinedload(Student.parent).joinedload(Parent.user)
    )

    # If teacher, restrict to teacher's classes unless admin/principal
    if current_user.role == "TEACHER":
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            teacher_class_ids = [s.class_id for s in teacher.subjects]
            for sec in teacher.sections:
                teacher_class_ids.append(sec.class_id)
            query = query.filter(Student.class_id.in_(list(set(teacher_class_ids))))
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.username.ilike(f"%{search}%")) |
            (Student.admission_number.ilike(f"%{search}%")) |
            (Student.roll_number.ilike(f"%{search}%"))
        )
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if section_id:
        query = query.filter(Student.section_id == section_id)

    query = query.order_by(Student.id.desc())
    paginated = paginate_query(query, page, page_size)

    items = []
    for s in paginated["items"]:
        items.append({
            "id": s.id,
            "user_id": s.user_id,
            "admission_number": s.admission_number,
            "roll_number": s.roll_number,
            "class_id": s.class_id,
            "section_id": s.section_id,
            "parent_id": s.parent_id,
            "date_of_birth": s.date_of_birth,
            "gender": s.gender,
            "blood_group": s.blood_group,
            "admission_date": s.admission_date,
            "address": s.address,
            "user": UserResponse.model_validate(s.user).model_dump() if s.user else None,
            "class_name": s.class_obj.name if s.class_obj else None,
            "section_name": s.section.name if s.section else None,
            "parent_name": s.parent.user.full_name if s.parent and s.parent.user else None,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        })
    paginated["items"] = items
    return paginated

@router.post("", response_model=StudentResponse)
def create_student(
    student_in: StudentCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    student = student_service.create_student(db, student_in)
    log_audit_action(db, "STUDENT_CREATE", "Student", str(student.id), f"Created student {student.admission_number}", current_user.id)
    s = student_service.get_student_by_id(db, student.id)
    return StudentResponse(
        id=s.id,
        user_id=s.user_id,
        admission_number=s.admission_number,
        roll_number=s.roll_number,
        class_id=s.class_id,
        section_id=s.section_id,
        parent_id=s.parent_id,
        date_of_birth=s.date_of_birth,
        gender=s.gender,
        blood_group=s.blood_group,
        admission_date=s.admission_date,
        address=s.address,
        user=UserResponse.model_validate(s.user) if s.user else None,
        class_name=s.class_obj.name if s.class_obj else None,
        section_name=s.section.name if s.section else None,
        parent_name=s.parent.user.full_name if s.parent and s.parent.user else None,
        created_at=s.created_at,
        updated_at=s.updated_at
    )

@router.get("/{student_id}")
def get_student(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    student = verify_student_access(student_id, current_user, db)
    return {
        "id": student.id,
        "user_id": student.user_id,
        "admission_number": student.admission_number,
        "roll_number": student.roll_number,
        "class_id": student.class_id,
        "section_id": student.section_id,
        "parent_id": student.parent_id,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "blood_group": student.blood_group,
        "admission_date": student.admission_date,
        "address": student.address,
        "user": UserResponse.model_validate(student.user).model_dump() if student.user else None,
        "class_name": student.class_obj.name if student.class_obj else None,
        "section_name": student.section.name if student.section else None,
        "parent_name": student.parent.user.full_name if student.parent and student.parent.user else None,
        "created_at": student.created_at,
        "updated_at": student.updated_at
    }

@router.put("/{student_id}")
def update_student(
    student_id: int,
    student_in: StudentUpdate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    student = student_service.update_student(db, student_id, student_in)
    log_audit_action(db, "STUDENT_UPDATE", "Student", str(student.id), f"Updated student {student.admission_number}", current_user.id)
    s = student_service.get_student_by_id(db, student.id)
    return {
        "id": s.id,
        "user_id": s.user_id,
        "admission_number": s.admission_number,
        "roll_number": s.roll_number,
        "class_id": s.class_id,
        "section_id": s.section_id,
        "parent_id": s.parent_id,
        "date_of_birth": s.date_of_birth,
        "gender": s.gender,
        "blood_group": s.blood_group,
        "admission_date": s.admission_date,
        "address": s.address,
        "user": UserResponse.model_validate(s.user).model_dump() if s.user else None,
        "class_name": s.class_obj.name if s.class_obj else None,
        "section_name": s.section.name if s.section else None,
        "parent_name": s.parent.user.full_name if s.parent and s.parent.user else None,
        "created_at": s.created_at,
        "updated_at": s.updated_at
    }

@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    student_service.delete_student(db, student_id)
    log_audit_action(db, "STUDENT_DELETE", "Student", str(student_id), "Deleted student record", current_user.id)
    return {"message": "Student deleted successfully"}

@router.get("/{student_id}/attendance")
def get_student_attendance(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    student = verify_student_access(student_id, current_user, db)
    stats = attendance_service.get_student_stats(db, student.id)
    records = student.attendances
    return {
        "stats": stats,
        "records": [
            {
                "id": a.id,
                "date": str(a.date),
                "status": a.status,
                "remarks": a.remarks,
                "recorded_by": a.recorder.full_name if a.recorder else None
            }
            for a in records
        ]
    }

@router.get("/{student_id}/fees")
def get_student_fees(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    student = verify_student_access(student_id, current_user, db)
    return fee_service.get_student_fee_summary(db, student.id)
