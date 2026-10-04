from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.subject import Subject
from backend.app.schemas.class_schema import SubjectCreate, SubjectResponse
from backend.app.utils.permissions import require_roles, get_current_active_user

router = APIRouter(prefix="/subjects", tags=["Subjects"])

@router.get("", response_model=List[SubjectResponse])
def get_subjects(
    class_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Subject).options(
        joinedload(Subject.class_obj),
        joinedload(Subject.teacher)
    )
    if class_id:
        query = query.filter(Subject.class_id == class_id)
    if teacher_id:
        query = query.filter(Subject.teacher_id == teacher_id)

    subjects = query.order_by(Subject.name.asc()).all()
    return [
        SubjectResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            class_id=s.class_id,
            teacher_id=s.teacher_id,
            class_name=s.class_obj.name if s.class_obj else None,
            teacher_name=s.teacher.user.full_name if s.teacher and s.teacher.user else None,
            created_at=s.created_at
        )
        for s in subjects
    ]

@router.post("", response_model=SubjectResponse)
def create_subject(
    subj_in: SubjectCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    subj = Subject(
        name=subj_in.name,
        code=subj_in.code.upper(),
        class_id=subj_in.class_id,
        teacher_id=subj_in.teacher_id
    )
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return SubjectResponse(
        id=subj.id,
        name=subj.name,
        code=subj.code,
        class_id=subj.class_id,
        teacher_id=subj.teacher_id,
        created_at=subj.created_at
    )

@router.put("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    subj_in: SubjectCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")

    subj.name = subj_in.name
    subj.code = subj_in.code.upper()
    subj.class_id = subj_in.class_id
    subj.teacher_id = subj_in.teacher_id
    db.commit()
    db.refresh(subj)
    return SubjectResponse(
        id=subj.id,
        name=subj.name,
        code=subj.code,
        class_id=subj.class_id,
        teacher_id=subj.teacher_id,
        created_at=subj.created_at
    )

@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(subj)
    db.commit()
    return {"message": "Subject deleted successfully"}
