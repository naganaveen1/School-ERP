from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.parent import Parent
from backend.app.models.student import Student
from backend.app.schemas.parent import ParentCreate, ParentUpdate, ParentResponse
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.services.auth_service import auth_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.pagination import paginate_query
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/parents", tags=["Parents"])

@router.get("", response_model=dict)
def list_parents(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    query = db.query(Parent).join(Parent.user).options(
        joinedload(Parent.user),
        joinedload(Parent.students).joinedload(Student.user)
    )

    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.username.ilike(f"%{search}%"))
        )

    query = query.order_by(Parent.id.desc())
    paginated = paginate_query(query, page, page_size)

    items = []
    for p in paginated["items"]:
        items.append({
            "id": p.id,
            "user_id": p.user_id,
            "occupation": p.occupation,
            "relation_type": p.relation_type,
            "address": p.address,
            "emergency_contact": p.emergency_contact,
            "user": UserResponse.model_validate(p.user).model_dump() if p.user else None,
            "children_count": len(p.students),
            "students": [
                {"id": s.id, "name": s.user.full_name if s.user else "", "admission_number": s.admission_number}
                for s in p.students
            ],
            "created_at": p.created_at,
            "updated_at": p.updated_at
        })
    paginated["items"] = items
    return paginated

@router.post("", response_model=ParentResponse)
def create_parent(
    parent_in: ParentCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    user_create = UserCreate(
        username=parent_in.username,
        email=parent_in.email,
        password=parent_in.password,
        full_name=parent_in.full_name,
        role="PARENT",
        phone=parent_in.phone,
        is_active=True
    )
    user = auth_service.create_user(db, user_create)

    parent = Parent(
        user_id=user.id,
        occupation=parent_in.occupation,
        relation_type=parent_in.relation_type or "Guardian",
        address=parent_in.address,
        emergency_contact=parent_in.emergency_contact
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    log_audit_action(db, "PARENT_CREATE", "Parent", str(parent.id), f"Created parent {user.username}", current_user.id)
    return parent

@router.get("/{parent_id}")
def get_parent(
    parent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"] and (
        current_user.role != "PARENT" or not current_user.parent_profile
        or current_user.parent_profile.id != parent_id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    parent = db.query(Parent).options(
        joinedload(Parent.user),
        joinedload(Parent.students).joinedload(Student.user),
        joinedload(Parent.students).joinedload(Student.class_obj),
        joinedload(Parent.students).joinedload(Student.section)
    ).filter(Parent.id == parent_id).first()

    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    return {
        "id": parent.id,
        "user_id": parent.user_id,
        "occupation": parent.occupation,
        "relation_type": parent.relation_type,
        "address": parent.address,
        "emergency_contact": parent.emergency_contact,
        "user": UserResponse.model_validate(parent.user).model_dump() if parent.user else None,
        "students": [
            {
                "id": s.id,
                "name": s.user.full_name if s.user else "",
                "admission_number": s.admission_number,
                "roll_number": s.roll_number,
                "class_name": s.class_obj.name if s.class_obj else "",
                "section_name": s.section.name if s.section else ""
            }
            for s in parent.students
        ],
        "created_at": parent.created_at,
        "updated_at": parent.updated_at
    }

@router.put("/{parent_id}")
def update_parent(
    parent_id: int,
    parent_in: ParentUpdate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    user = parent.user
    if parent_in.full_name is not None:
        user.full_name = parent_in.full_name
    if parent_in.email is not None:
        user.email = parent_in.email
    if parent_in.phone is not None:
        user.phone = parent_in.phone
    if parent_in.occupation is not None:
        parent.occupation = parent_in.occupation
    if parent_in.relation_type is not None:
        parent.relation_type = parent_in.relation_type
    if parent_in.address is not None:
        parent.address = parent_in.address
    if parent_in.emergency_contact is not None:
        parent.emergency_contact = parent_in.emergency_contact

    db.commit()
    db.refresh(parent)
    log_audit_action(db, "PARENT_UPDATE", "Parent", str(parent.id), f"Updated parent {user.username}", current_user.id)
    return parent

@router.delete("/{parent_id}")
def delete_parent(
    parent_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    user = parent.user
    db.delete(parent)
    if user:
        db.delete(user)
    db.commit()
    log_audit_action(db, "PARENT_DELETE", "Parent", str(parent_id), "Deleted parent record", current_user.id)
    return {"message": "Parent deleted successfully"}

@router.post("/{parent_id}/link-student/{student_id}")
def link_student_to_parent(
    parent_id: int,
    student_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.parent_id = parent.id
    db.commit()
    log_audit_action(db, "PARENT_LINK_STUDENT", "Parent", str(parent.id), f"Linked student {student.id} to parent {parent.id}", current_user.id)
    return {"message": f"Successfully linked student {student.admission_number} to parent {parent.user.full_name}"}
