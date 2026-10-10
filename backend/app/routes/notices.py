from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.notice import Notice
from backend.app.schemas.notice import NoticeCreate, NoticeUpdate, NoticeResponse
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/notices", tags=["Notices"])

@router.get("", response_model=List[NoticeResponse])
def list_notices(
    target_role: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Notice).options(joinedload(Notice.publisher))

    # Normal users only see published notices targeting them or ALL
    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"]:
        query = query.filter(
            Notice.is_published == True,
            (Notice.target_role == "ALL") | (Notice.target_role == current_user.role)
        )
    elif target_role:
        query = query.filter(Notice.target_role == target_role)

    notices = query.order_by(Notice.publish_date.desc()).all()
    return [
        NoticeResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            target_role=n.target_role,
            published_by=n.published_by,
            is_published=n.is_published,
            publish_date=n.publish_date,
            expires_at=n.expires_at,
            publisher_name=n.publisher.full_name if n.publisher else None,
            created_at=n.created_at,
            updated_at=n.updated_at
        )
        for n in notices
    ]

@router.post("", response_model=NoticeResponse)
def create_notice(
    notice_in: NoticeCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    notice = Notice(
        title=notice_in.title,
        content=notice_in.content,
        target_role=notice_in.target_role,
        published_by=current_user.id,
        is_published=notice_in.is_published,
        expires_at=notice_in.expires_at
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    if notice.is_published:
        notification_service.notify_role(
            db=db,
            role=notice.target_role,
            title="New Announcement Notice",
            message=notice.title,
            link="/frontend/student/notices.html" if notice.target_role == "STUDENT" else None,
            notification_type="INFO"
        )

    log_audit_action(db, "NOTICE_CREATE", "Notice", str(notice.id), f"Created notice {notice.title}", current_user.id)

    return NoticeResponse(
        id=notice.id,
        title=notice.title,
        content=notice.content,
        target_role=notice.target_role,
        published_by=notice.published_by,
        is_published=notice.is_published,
        publish_date=notice.publish_date,
        expires_at=notice.expires_at,
        publisher_name=current_user.full_name,
        created_at=notice.created_at,
        updated_at=notice.updated_at
    )

@router.put("/{notice_id}", response_model=NoticeResponse)
def update_notice(
    notice_id: int,
    notice_in: NoticeUpdate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")

    if notice_in.title is not None:
        notice.title = notice_in.title
    if notice_in.content is not None:
        notice.content = notice_in.content
    if notice_in.target_role is not None:
        notice.target_role = notice_in.target_role
    if notice_in.is_published is not None:
        notice.is_published = notice_in.is_published
    if notice_in.expires_at is not None:
        notice.expires_at = notice_in.expires_at

    db.commit()
    db.refresh(notice)
    log_audit_action(db, "NOTICE_UPDATE", "Notice", str(notice.id), f"Updated notice {notice.title}", current_user.id)
    return notice

@router.delete("/{notice_id}")
def delete_notice(
    notice_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    db.delete(notice)
    db.commit()
    log_audit_action(db, "NOTICE_DELETE", "Notice", str(notice_id), "Deleted notice", current_user.id)
    return {"message": "Notice deleted successfully"}
