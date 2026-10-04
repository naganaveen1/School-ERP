from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.notification import NotificationCreate, NotificationResponse
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse])
def get_my_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return notification_service.get_user_notifications(db, current_user.id, unread_only)

@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    success = notification_service.mark_as_read(db, notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@router.post("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    count = notification_service.mark_all_as_read(db, current_user.id)
    return {"message": f"{count} notifications marked as read"}

@router.post("", response_model=NotificationResponse)
def create_notification(
    notif_in: NotificationCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    if not db.query(User.id).filter(User.id == notif_in.user_id).first():
        raise HTTPException(status_code=404, detail="Recipient not found")
    notif = notification_service.create_notification(
        db=db,
        user_id=notif_in.user_id,
        title=notif_in.title,
        message=notif_in.message,
        link=notif_in.link,
        notification_type=notif_in.notification_type or "INFO"
    )
    return notif
