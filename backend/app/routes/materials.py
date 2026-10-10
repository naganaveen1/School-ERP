from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.teacher import Teacher
from backend.app.models.study_material import StudyMaterial
from backend.app.schemas.assignment import StudyMaterialResponse
from backend.app.services.file_service import file_service
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.helpers import log_audit_action
from backend.app.utils.school_access import teacher_for_subject

router = APIRouter(prefix="/materials", tags=["Study Materials"], dependencies=[Depends(require_feature("assignments"))])

@router.get("", response_model=List[StudyMaterialResponse])
def list_materials(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(StudyMaterial).options(
        joinedload(StudyMaterial.class_obj),
        joinedload(StudyMaterial.subject),
        joinedload(StudyMaterial.teacher).joinedload(Teacher.user)
    )

    if current_user.role == "STUDENT":
        student = current_user.student_profile
        if not student or student.class_id is None:
            return []
        query = query.filter(StudyMaterial.class_id == student.class_id)
    elif current_user.role == "PARENT":
        children = current_user.parent_profile.students if current_user.parent_profile else []
        if not children:
            return []
        query = query.filter(StudyMaterial.class_id.in_([child.class_id for child in children if child.class_id]))
    elif current_user.role == "TEACHER":
        teacher = current_user.teacher_profile
        if not teacher:
            return []
        query = query.filter(StudyMaterial.teacher_id == teacher.id)
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        return []
    if class_id:
        query = query.filter(StudyMaterial.class_id == class_id)

    if subject_id:
        query = query.filter(StudyMaterial.subject_id == subject_id)

    materials = query.order_by(StudyMaterial.upload_date.desc()).all()

    return [
        StudyMaterialResponse(
            id=m.id,
            title=m.title,
            description=m.description,
            class_id=m.class_id,
            subject_id=m.subject_id,
            teacher_id=m.teacher_id,
            file_path=m.file_path,
            file_type=m.file_type,
            file_size=m.file_size,
            upload_date=m.upload_date,
            class_name=m.class_obj.name if m.class_obj else None,
            subject_name=m.subject.name if m.subject else None,
            teacher_name=m.teacher.user.full_name if m.teacher and m.teacher.user else None
        )
        for m in materials
    ]

@router.post("", response_model=StudyMaterialResponse)
def upload_study_material(
    title: str = Form(...),
    class_id: int = Form(...),
    subject_id: int = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    teacher_id = teacher_for_subject(db, current_user, class_id, subject_id)

    stored_path = file_service.save_upload_file(file, "study-materials", current_user.tenant_id)
    file_type = Path(file.filename).suffix.lstrip(".")

    material = StudyMaterial(
        title=title,
        description=description,
        class_id=class_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        file_path=stored_path,
        file_type=file_type
    )
    db.add(material)
    try:
        db.commit()
    except Exception:
        file_service.delete_file(stored_path)
        raise
    db.refresh(material)

    log_audit_action(db, "STUDY_MATERIAL_UPLOAD", "StudyMaterial", str(material.id), f"Uploaded {title}", current_user.id)

    return StudyMaterialResponse(
        id=material.id,
        title=material.title,
        description=material.description,
        class_id=material.class_id,
        subject_id=material.subject_id,
        teacher_id=material.teacher_id,
        file_path=material.file_path,
        file_type=material.file_type,
        file_size=material.file_size,
        upload_date=material.upload_date
    )

@router.delete("/{material_id}")
def delete_study_material(
    material_id: int,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    m = db.query(StudyMaterial).filter(StudyMaterial.id == material_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")

    if current_user.role == "TEACHER" and (not current_user.teacher_profile or m.teacher_id != current_user.teacher_profile.id):
        raise HTTPException(status_code=403, detail="Cannot delete material uploaded by another teacher")

    file_service.delete_file(m.file_path)
    db.delete(m)
    db.commit()
    log_audit_action(db, "STUDY_MATERIAL_DELETE", "StudyMaterial", str(material_id), "Deleted material", current_user.id)
    return {"message": "Study material deleted successfully"}
