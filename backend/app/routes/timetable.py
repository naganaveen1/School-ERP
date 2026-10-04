from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, false, or_
from backend.app.database import get_db
from backend.app.models.timetable import Timetable
from backend.app.models.teacher import Teacher
from backend.app.schemas.class_schema import TimetableCreate, TimetableResponse
from backend.app.utils.permissions import require_roles, get_current_active_user
from backend.app.utils.school_access import teacher_class_ids

router = APIRouter(prefix="/timetable", tags=["Timetable"])

@router.get("", response_model=List[TimetableResponse])
def get_timetable(
    class_id: Optional[int] = None,
    section_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    day_of_week: Optional[str] = None,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Timetable).options(
        joinedload(Timetable.class_obj),
        joinedload(Timetable.section),
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher).joinedload(Teacher.user)
    )
    if current_user.role == "STUDENT":
        student = current_user.student_profile
        query = query.filter(
            Timetable.class_id == student.class_id,
            Timetable.section_id == student.section_id,
        ) if student else query.filter(false())
    elif current_user.role == "PARENT":
        parent = current_user.parent_profile
        clauses = [and_(Timetable.class_id == child.class_id,
                        Timetable.section_id == child.section_id)
                   for child in parent.students if child.class_id and child.section_id] if parent else []
        query = query.filter(or_(*clauses)) if clauses else query.filter(false())
    elif current_user.role == "TEACHER":
        query = query.filter(Timetable.class_id.in_(teacher_class_ids(current_user)))
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        query = query.filter(false())

    if class_id:
        query = query.filter(Timetable.class_id == class_id)
    if section_id:
        query = query.filter(Timetable.section_id == section_id)
    if teacher_id:
        query = query.filter(Timetable.teacher_id == teacher_id)
    if day_of_week:
        query = query.filter(Timetable.day_of_week.ilike(day_of_week))

    entries = query.order_by(Timetable.day_of_week, Timetable.start_time).all()
    return [
        TimetableResponse(
            id=e.id,
            class_id=e.class_id,
            section_id=e.section_id,
            subject_id=e.subject_id,
            teacher_id=e.teacher_id,
            day_of_week=e.day_of_week,
            start_time=e.start_time,
            end_time=e.end_time,
            room_number=e.room_number,
            class_name=e.class_obj.name if e.class_obj else None,
            section_name=e.section.name if e.section else None,
            subject_name=e.subject.name if e.subject else None,
            teacher_name=e.teacher.user.full_name if e.teacher and e.teacher.user else None,
            created_at=e.created_at
        )
        for e in entries
    ]

@router.post("", response_model=TimetableResponse)
def create_timetable_entry(
    entry_in: TimetableCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    entry = Timetable(
        class_id=entry_in.class_id,
        section_id=entry_in.section_id,
        subject_id=entry_in.subject_id,
        teacher_id=entry_in.teacher_id,
        day_of_week=entry_in.day_of_week,
        start_time=entry_in.start_time,
        end_time=entry_in.end_time,
        room_number=entry_in.room_number
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return TimetableResponse(
        id=entry.id,
        class_id=entry.class_id,
        section_id=entry.section_id,
        subject_id=entry.subject_id,
        teacher_id=entry.teacher_id,
        day_of_week=entry.day_of_week,
        start_time=entry.start_time,
        end_time=entry.end_time,
        room_number=entry.room_number,
        created_at=entry.created_at
    )

@router.put("/{entry_id}", response_model=TimetableResponse)
def update_timetable_entry(
    entry_id: int,
    entry_in: TimetableCreate,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    entry = db.query(Timetable).filter(Timetable.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    entry.class_id = entry_in.class_id
    entry.section_id = entry_in.section_id
    entry.subject_id = entry_in.subject_id
    entry.teacher_id = entry_in.teacher_id
    entry.day_of_week = entry_in.day_of_week
    entry.start_time = entry_in.start_time
    entry.end_time = entry_in.end_time
    entry.room_number = entry_in.room_number

    db.commit()
    db.refresh(entry)
    return TimetableResponse(
        id=entry.id,
        class_id=entry.class_id,
        section_id=entry.section_id,
        subject_id=entry.subject_id,
        teacher_id=entry.teacher_id,
        day_of_week=entry.day_of_week,
        start_time=entry.start_time,
        end_time=entry.end_time,
        room_number=entry.room_number,
        created_at=entry.created_at
    )

@router.delete("/{entry_id}")
def delete_timetable_entry(
    entry_id: int,
    current_user = Depends(require_roles(["SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    entry = db.query(Timetable).filter(Timetable.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Timetable entry deleted successfully"}
