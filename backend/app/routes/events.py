from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.event import Event
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.helpers import log_audit_action

router = APIRouter(prefix="/events", tags=["Events"])

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    target_audience: Optional[str] = "ALL"

@router.get("")
def list_events(
    target_audience: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Event).options(joinedload(Event.creator))
    if current_user.role not in ["SCHOOL_ADMIN", "PRINCIPAL"]:
        query = query.filter(
            (Event.target_audience == "ALL") | (Event.target_audience == current_user.role)
        )
    elif target_audience:
        query = query.filter(Event.target_audience == target_audience)

    events = query.order_by(Event.start_time.asc()).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "location": e.location,
            "target_audience": e.target_audience,
            "creator_name": e.creator.full_name if e.creator else None,
            "created_at": e.created_at
        }
        for e in events
    ]

@router.post("")
def create_event(
    event_in: EventCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    ev = Event(
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        location=event_in.location,
        target_audience=event_in.target_audience or "ALL",
        created_by=current_user.id
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    notification_service.notify_role(
        db=db,
        role=ev.target_audience,
        title=f"Upcoming Event: {ev.title}",
        message=f"Event scheduled from {ev.start_time.strftime('%Y-%m-%d %H:%M')}",
        notification_type="INFO"
    )

    log_audit_action(db, "EVENT_CREATE", "Event", str(ev.id), f"Created event {ev.title}", current_user.id)
    return {"message": "Event created successfully", "id": ev.id}

@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(ev)
    db.commit()
    log_audit_action(db, "EVENT_DELETE", "Event", str(event_id), "Deleted event", current_user.id)
    return {"message": "Event deleted successfully"}
