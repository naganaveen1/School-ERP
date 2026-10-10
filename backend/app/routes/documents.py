import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.document import Document
from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission
from backend.app.models.study_material import StudyMaterial
from backend.app.services.file_service import file_service
from backend.app.utils.permissions import require_roles, get_current_active_user, get_current_user, require_feature
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/documents", tags=["Documents"], dependencies=[Depends(require_feature("documents"))])

@router.post("")
def upload_document(
    title: str = Form(...),
    document_type: str = Form("General"),
    user_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    target_user_id = current_user.id
    if user_id and current_user.role in ["SCHOOL_ADMIN", "PRINCIPAL"]:
        if not db.query(User.id).filter(User.id == user_id).first():
            raise HTTPException(status_code=404, detail="User not found")
        target_user_id = user_id

    stored_path = file_service.save_upload_file(file, "documents", current_user.tenant_id)
    file_size = file_service.file_size(stored_path)

    doc = Document(
        user_id=target_user_id,
        title=title,
        file_path=stored_path,
        document_type=document_type,
        file_size=file_size
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_audit_action(db, "DOCUMENT_UPLOAD", "Document", str(doc.id), f"Uploaded document {title}", current_user.id)

    return {
        "message": "Document uploaded successfully",
        "id": doc.id,
        "title": doc.title,
        "file_path": doc.file_path,
        "document_type": doc.document_type
    }

@router.get("")
def list_documents(
    user_id: Optional[int] = None,
    document_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Document).options(joinedload(Document.user))

    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"]:
        query = query.filter(Document.user_id == current_user.id)
    elif user_id:
        query = query.filter(Document.user_id == user_id)

    if document_type:
        query = query.filter(Document.document_type == document_type)

    docs = query.order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "user_id": d.user_id,
            "user_name": d.user.full_name if d.user else "",
            "title": d.title,
            "file_path": d.file_path,
            "document_type": d.document_type,
            "file_size": d.file_size,
            "uploaded_at": d.uploaded_at
        }
        for d in docs
    ]

@router.get("/download/{document_id}")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"] and doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot access this document")

    return file_service.download_response(doc.file_path)

@router.get("/file/{file_subpath:path}")
def download_file(
    file_subpath: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Resolve the owning record before opening a path. Never serve arbitrary files
    # from the upload directory to anyone with a valid token.
    allowed = current_user.role in ("SCHOOL_ADMIN", "PRINCIPAL")
    doc = db.query(Document).filter(Document.file_path == file_subpath).first()
    if doc:
        allowed = allowed or doc.user_id == current_user.id
    else:
        submission = db.query(Submission).filter(Submission.file_path == file_subpath).first()
        if submission:
            allowed = allowed or (
                current_user.student_profile is not None
                and submission.student_id == current_user.student_profile.id
            ) or (
                current_user.teacher_profile is not None
                and submission.assignment.teacher_id == current_user.teacher_profile.id
            ) or (
                current_user.parent_profile is not None
                and any(s.id == submission.student_id for s in current_user.parent_profile.students)
            )
        else:
            assignment = db.query(Assignment).filter(Assignment.attachment_path == file_subpath).first()
            material = db.query(StudyMaterial).filter(StudyMaterial.file_path == file_subpath).first()
            resource = assignment or material
            if resource:
                allowed = allowed or (
                    current_user.teacher_profile is not None
                    and resource.teacher_id == current_user.teacher_profile.id
                ) or (
                    current_user.student_profile is not None
                    and resource.class_id == current_user.student_profile.class_id
                    and (not assignment or assignment.section_id is None
                         or assignment.section_id == current_user.student_profile.section_id)
                ) or (
                    current_user.parent_profile is not None
                    and any(s.class_id == resource.class_id and
                            (not assignment or assignment.section_id is None
                             or assignment.section_id == s.section_id)
                            for s in current_user.parent_profile.students)
                )
            else:
                raise HTTPException(status_code=404, detail="File not found")

    if not allowed:
        raise HTTPException(status_code=404, detail="File not found")
    return file_service.download_response(file_subpath)

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role != "SCHOOL_ADMIN" and doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete this document")

    file_service.delete_file(doc.file_path)
    db.delete(doc)
    db.commit()
    log_audit_action(db, "DOCUMENT_DELETE", "Document", str(document_id), "Deleted document", current_user.id)
    return {"message": "Document deleted successfully"}
