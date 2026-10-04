from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.message import Message
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import get_current_active_user, require_feature

router = APIRouter(prefix="/messages", tags=["Messaging"], dependencies=[Depends(require_feature("messaging"))])

class MessageCreate(BaseModel):
    receiver_id: int
    subject: str
    body: str

@router.post("")
def send_message(
    msg_in: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    receiver = db.query(User).filter(User.id == msg_in.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found")

    msg = Message(
        sender_id=current_user.id,
        receiver_id=msg_in.receiver_id,
        subject=msg_in.subject,
        body=msg_in.body,
        is_read=False
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Notify receiver
    notification_service.create_notification(
        db=db,
        user_id=receiver.id,
        title=f"New Message from {current_user.full_name}",
        message=f"{msg.subject}",
        notification_type="INFO"
    )

    return {"message": "Message sent successfully", "id": msg.id}

@router.get("/inbox")
def get_inbox(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    messages = db.query(Message).options(
        joinedload(Message.sender)
    ).filter(
        Message.receiver_id == current_user.id
    ).order_by(Message.sent_at.desc()).all()

    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": m.sender.full_name if m.sender else "Unknown",
            "sender_role": m.sender.role if m.sender else "",
            "subject": m.subject,
            "body": m.body,
            "is_read": m.is_read,
            "sent_at": m.sent_at
        }
        for m in messages
    ]

@router.get("/sent")
def get_sent_messages(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    messages = db.query(Message).options(
        joinedload(Message.receiver)
    ).filter(
        Message.sender_id == current_user.id
    ).order_by(Message.sent_at.desc()).all()

    return [
        {
            "id": m.id,
            "receiver_id": m.receiver_id,
            "receiver_name": m.receiver.full_name if m.receiver else "Unknown",
            "receiver_role": m.receiver.role if m.receiver else "",
            "subject": m.subject,
            "body": m.body,
            "is_read": m.is_read,
            "sent_at": m.sent_at
        }
        for m in messages
    ]

@router.patch("/{message_id}/read")
def mark_message_as_read(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(
        Message.id == message_id,
        Message.receiver_id == current_user.id
    ).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    db.commit()
    return {"message": "Message marked as read"}
