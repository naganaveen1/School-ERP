from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.attendance import Attendance
from backend.app.models.student import Student
from backend.app.schemas.attendance import (
    AttendanceBulkCreate, AttendanceCreate, AttendanceUpdate,
    AttendanceResponse, AttendanceStats
)
from backend.app.services.attendance_service import attendance_service
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.helpers import log_audit_action
from backend.app.utils.school_access import parent_child_ids, teacher_class_ids
from backend.app.routes.students import verify_student_access

router = APIRouter(prefix="/attendance", tags=["Attendance"], dependencies=[Depends(require_feature("attendance"))])

@router.post("", response_model=List[AttendanceResponse])
def mark_attendance(
    bulk_in: AttendanceBulkCreate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "TEACHER", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    if current_user.role == "TEACHER" and bulk_in.class_id not in teacher_class_ids(current_user):
        raise HTTPException(status_code=403, detail="Class is not assigned to this teacher")
    student_ids = {item.student_id for item in bulk_in.records}
    matched = db.query(Student.id).filter(Student.id.in_(student_ids),
                                          Student.class_id == bulk_in.class_id,
                                          Student.section_id == bulk_in.section_id).count()
    if matched != len(student_ids) or len(student_ids) != len(bulk_in.records):
        raise HTTPException(status_code=400, detail="Attendance students must belong to the selected class and section")
    saved = attendance_service.mark_attendance(
        db=db,
        class_id=bulk_in.class_id,
        section_id=bulk_in.section_id,
        att_date=bulk_in.date,
        records=bulk_in.records,
        recorded_by=current_user.id
    )

    log_audit_action(
        db, "ATTENDANCE_RECORDED", "Attendance",
        f"class_{bulk_in.class_id}_sec_{bulk_in.section_id}",
        f"Marked attendance for {len(saved)} students on {bulk_in.date}",
        current_user.id
    )

    # Return enriched responses
    responses = []
    for a in saved:
        student = db.query(Student).filter(Student.id == a.student_id).first()
        responses.append(AttendanceResponse(
            id=a.id,
            student_id=a.student_id,
            class_id=a.class_id,
            section_id=a.section_id,
            date=a.date,
            status=a.status,
            remarks=a.remarks,
            recorded_by=a.recorded_by,
            student_name=student.user.full_name if student and student.user else None,
            admission_number=student.admission_number if student else None,
            roll_number=student.roll_number if student else None,
            created_at=a.created_at
        ))
    return responses

@router.get("", response_model=List[AttendanceResponse])
def get_attendance(
    att_date: Optional[date] = None,
    class_id: Optional[int] = None,
    section_id: Optional[int] = None,
    student_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Attendance).options(
        joinedload(Attendance.student).joinedload(Student.user),
        joinedload(Attendance.class_obj),
        joinedload(Attendance.section)
    )

    if current_user.role == "STUDENT":
        if not current_user.student_profile:
            return []
        query = query.filter(Attendance.student_id == current_user.student_profile.id)
    elif current_user.role == "PARENT":
        query = query.filter(Attendance.student_id.in_(parent_child_ids(current_user)))
    elif current_user.role == "TEACHER":
        query = query.filter(Attendance.class_id.in_(teacher_class_ids(current_user)))
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        return []

    if att_date:
        query = query.filter(Attendance.date == att_date)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if section_id:
        query = query.filter(Attendance.section_id == section_id)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)

    records = query.order_by(Attendance.date.desc()).all()
    return [
        AttendanceResponse(
            id=a.id,
            student_id=a.student_id,
            class_id=a.class_id,
            section_id=a.section_id,
            date=a.date,
            status=a.status,
            remarks=a.remarks,
            recorded_by=a.recorded_by,
            student_name=a.student.user.full_name if a.student and a.student.user else None,
            admission_number=a.student.admission_number if a.student else None,
            roll_number=a.student.roll_number if a.student else None,
            class_name=a.class_obj.name if a.class_obj else None,
            section_name=a.section.name if a.section else None,
            created_at=a.created_at
        )
        for a in records
    ]

@router.get("/student/{student_id}", response_model=dict)
def get_student_attendance(
    student_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    verify_student_access(student_id, current_user, db)
    stats = attendance_service.get_student_stats(db, student_id, start_date, end_date)
    query = db.query(Attendance).filter(Attendance.student_id == student_id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    records = query.order_by(Attendance.date.desc()).all()

    return {
        "stats": stats,
        "records": [
            {
                "id": r.id,
                "date": str(r.date),
                "status": r.status,
                "remarks": r.remarks
            }
            for r in records
        ]
    }

@router.get("/class-summary")
def get_class_attendance_summary(
    class_id: int,
    section_id: Optional[int] = None,
    att_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "TEACHER":
        if class_id not in teacher_class_ids(current_user):
            raise HTTPException(status_code=403, detail="Class is not assigned to this teacher")
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        raise HTTPException(status_code=403, detail="School staff access required")
    if not att_date:
        att_date = date.today()

    query = db.query(Attendance).filter(
        Attendance.class_id == class_id,
        Attendance.date == att_date
    )
    if section_id:
        query = query.filter(Attendance.section_id == section_id)

    records = query.all()
    total = len(records)
    present = sum(1 for r in records if r.status.lower() == "present")
    absent = sum(1 for r in records if r.status.lower() == "absent")
    late = sum(1 for r in records if r.status.lower() == "late")
    percentage = round(((present + late) / total * 100), 2) if total > 0 else 0.0

    return {
        "date": str(att_date),
        "class_id": class_id,
        "section_id": section_id,
        "total": total,
        "present": present,
        "absent": absent,
        "late": late,
        "percentage": percentage
    }

@router.put("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance_record(
    attendance_id: int,
    att_in: AttendanceUpdate,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "TEACHER", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    att = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if current_user.role == "TEACHER" and att.class_id not in teacher_class_ids(current_user):
        raise HTTPException(status_code=403, detail="Class is not assigned to this teacher")

    att.status = att_in.status
    if att_in.remarks is not None:
        att.remarks = att_in.remarks
    db.commit()
    db.refresh(att)

    log_audit_action(db, "ATTENDANCE_UPDATE", "Attendance", str(att.id), f"Changed status to {att.status}", current_user.id)

    return AttendanceResponse(
        id=att.id,
        student_id=att.student_id,
        class_id=att.class_id,
        section_id=att.section_id,
        date=att.date,
        status=att.status,
        remarks=att.remarks,
        recorded_by=att.recorded_by,
        student_name=att.student.user.full_name if att.student and att.student.user else None,
        created_at=att.created_at
    )
