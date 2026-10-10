from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.teacher import Teacher
from backend.app.models.department import Department
from backend.app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherResponse
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.services.auth_service import auth_service
from backend.app.services.entitlement_service import entitlement_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.pagination import paginate_query
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/teachers", tags=["Teachers"])

@router.get("", response_model=dict)
def list_teachers(
    search: Optional[str] = None,
    department_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL", "TEACHER"])),
    db: Session = Depends(get_db)
):
    query = db.query(Teacher).join(Teacher.user).options(
        joinedload(Teacher.user),
        joinedload(Teacher.department)
    )
    if current_user.role == "TEACHER":
        query = query.filter(Teacher.user_id == current_user.id)

    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (Teacher.employee_id.ilike(f"%{search}%"))
        )
    if department_id:
        query = query.filter(Teacher.department_id == department_id)

    query = query.order_by(Teacher.id.desc())
    paginated = paginate_query(query, page, page_size)

    items = []
    for t in paginated["items"]:
        items.append({
            "id": t.id,
            "user_id": t.user_id,
            "employee_id": t.employee_id,
            "department_id": t.department_id,
            "qualification": t.qualification,
            "designation": t.designation,
            "joining_date": t.joining_date,
            "phone": t.phone,
            "address": t.address,
            "user": UserResponse.model_validate(t.user).model_dump() if t.user else None,
            "department_name": t.department.name if t.department else None,
            "created_at": t.created_at,
            "updated_at": t.updated_at
        })
    paginated["items"] = items
    return paginated

@router.post("", response_model=TeacherResponse)
def create_teacher(
    teacher_in: TeacherCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    entitlement_service.check_usage(db, "teachers")
    if db.query(Teacher).filter(Teacher.employee_id == teacher_in.employee_id).first():
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    # Create user account
    user_create = UserCreate(
        username=teacher_in.username,
        email=teacher_in.email,
        password=teacher_in.password,
        full_name=teacher_in.full_name,
        role="TEACHER",
        phone=teacher_in.phone,
        is_active=True
    )
    user = auth_service.create_user(db, user_create)

    teacher = Teacher(
        user_id=user.id,
        employee_id=teacher_in.employee_id,
        department_id=teacher_in.department_id,
        qualification=teacher_in.qualification,
        designation=teacher_in.designation or "Teacher",
        joining_date=teacher_in.joining_date,
        phone=teacher_in.phone,
        address=teacher_in.address
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    log_audit_action(db, "TEACHER_CREATE", "Teacher", str(teacher.id), f"Created teacher {teacher.employee_id}", current_user.id)

    return TeacherResponse(
        id=teacher.id,
        user_id=teacher.user_id,
        employee_id=teacher.employee_id,
        department_id=teacher.department_id,
        qualification=teacher.qualification,
        designation=teacher.designation,
        joining_date=teacher.joining_date,
        phone=teacher.phone,
        address=teacher.address,
        user=teacher.user,
        department_name=teacher.department.name if teacher.department else None,
        created_at=teacher.created_at,
        updated_at=teacher.updated_at
    )

@router.get("/{teacher_id}")
def get_teacher(
    teacher_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL", "TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = db.query(Teacher).options(
        joinedload(Teacher.user),
        joinedload(Teacher.department),
        joinedload(Teacher.subjects),
        joinedload(Teacher.sections)
    ).filter(Teacher.id == teacher_id).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    if current_user.role == "TEACHER" and teacher.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    subjects_list = [
        {"id": s.id, "name": s.name, "code": s.code, "class_name": s.class_obj.name if s.class_obj else ""}
        for s in teacher.subjects
    ]
    sections_list = [
        {"id": sec.id, "name": sec.name, "class_name": sec.class_obj.name if sec.class_obj else ""}
        for sec in teacher.sections
    ]

    return {
        "id": teacher.id,
        "user_id": teacher.user_id,
        "employee_id": teacher.employee_id,
        "department_id": teacher.department_id,
        "qualification": teacher.qualification,
        "designation": teacher.designation,
        "joining_date": teacher.joining_date,
        "phone": teacher.phone,
        "address": teacher.address,
        "user": UserResponse.model_validate(teacher.user).model_dump() if teacher.user else None,
        "department_name": teacher.department.name if teacher.department else None,
        "subjects": subjects_list,
        "class_teacher_sections": sections_list,
        "created_at": teacher.created_at,
        "updated_at": teacher.updated_at
    }

@router.put("/{teacher_id}")
def update_teacher(
    teacher_id: int,
    teacher_in: TeacherUpdate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    user = teacher.user
    if teacher_in.full_name is not None:
        user.full_name = teacher_in.full_name
    if teacher_in.email is not None:
        user.email = teacher_in.email
    if teacher_in.phone is not None:
        user.phone = teacher_in.phone
        teacher.phone = teacher_in.phone
    if teacher_in.department_id is not None:
        teacher.department_id = teacher_in.department_id
    if teacher_in.qualification is not None:
        teacher.qualification = teacher_in.qualification
    if teacher_in.designation is not None:
        teacher.designation = teacher_in.designation
    if teacher_in.address is not None:
        teacher.address = teacher_in.address

    db.commit()
    db.refresh(teacher)
    log_audit_action(db, "TEACHER_UPDATE", "Teacher", str(teacher.id), f"Updated teacher {teacher.employee_id}", current_user.id)
    return teacher

@router.delete("/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    user = teacher.user
    db.delete(teacher)
    if user:
        db.delete(user)
    db.commit()
    log_audit_action(db, "TEACHER_DELETE", "Teacher", str(teacher_id), "Deleted teacher record", current_user.id)
    return {"message": "Teacher deleted successfully"}
