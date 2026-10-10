from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.student import Student
from backend.app.models.timetable import Timetable
from backend.app.models.assignment import Assignment
from backend.app.models.result import Result
from backend.app.models.exam import Exam
from backend.app.models.study_material import StudyMaterial
from backend.app.models.teacher import Teacher
from backend.app.services.attendance_service import attendance_service
from backend.app.services.fee_service import fee_service
from backend.app.utils.permissions import require_roles, require_feature
from backend.app.utils.helpers import calculate_percentage

router = APIRouter(prefix="/student", tags=["Student Portal"])

def get_current_student(current_user: User, db: Session) -> Student:
    if not current_user.student_profile:
        raise HTTPException(status_code=400, detail="Student profile not found")
    return current_user.student_profile

class StudentProfileUpdateRequest(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None

@router.get("/profile")
def get_student_profile(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    return {
        "id": student.id,
        "admission_number": student.admission_number,
        "roll_number": student.roll_number,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": student.user.phone or current_user.phone,
        "gender": student.gender,
        "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
        "blood_group": student.blood_group,
        "admission_date": str(student.admission_date) if student.admission_date else None,
        "address": student.address,
        "class_name": student.class_obj.name if student.class_obj else "Not assigned",
        "section_name": student.section.name if student.section else "Not assigned",
        "parent_name": student.parent.user.full_name if student.parent and student.parent.user else None,
        "emergency_contact": student.parent.emergency_contact if student.parent else None
    }

@router.put("/profile")
def update_student_profile(
    profile_in: StudentProfileUpdateRequest,
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    if profile_in.phone is not None:
        current_user.phone = profile_in.phone
    if profile_in.address is not None:
        student.address = profile_in.address
    db.commit()
    return {"message": "Profile updated successfully"}

@router.get("/timetable")
def get_student_timetable(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    if not student.class_id or not student.section_id:
        return []

    query = db.query(Timetable).options(
        joinedload(Timetable.subject),
        joinedload(Timetable.teacher).joinedload(Teacher.user)
    ).filter(Timetable.class_id == student.class_id,
             Timetable.section_id == student.section_id)

    entries = query.order_by(Timetable.day_of_week, Timetable.start_time).all()
    return [
        {
            "id": e.id,
            "day_of_week": e.day_of_week,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "room_number": e.room_number,
            "subject_name": e.subject.name if e.subject else "",
            "teacher_name": e.teacher.user.full_name if e.teacher and e.teacher.user else ""
        }
        for e in entries
    ]

@router.get("/attendance", dependencies=[Depends(require_feature("attendance"))])
def get_my_attendance(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    stats = attendance_service.get_student_stats(db, student.id)
    records = student.attendances
    return {
        "stats": stats,
        "records": [
            {
                "id": a.id,
                "date": str(a.date),
                "status": a.status,
                "remarks": a.remarks
            }
            for a in records
        ]
    }

@router.get("/assignments", dependencies=[Depends(require_feature("assignments"))])
def get_my_assignments(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    if not student.class_id:
        return []

    assignments = db.query(Assignment).options(
        joinedload(Assignment.subject),
        joinedload(Assignment.teacher).joinedload(Teacher.user),
        joinedload(Assignment.submissions)
    ).filter(
        Assignment.class_id == student.class_id,
        (Assignment.section_id.is_(None)) | (Assignment.section_id == student.section_id),
    ).order_by(Assignment.due_date.desc()).all()

    items = []
    for a in assignments:
        sub = next((s for s in a.submissions if s.student_id == student.id), None)
        items.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "due_date": str(a.due_date),
            "max_marks": a.max_marks,
            "subject_name": a.subject.name if a.subject else "",
            "teacher_name": a.teacher.user.full_name if a.teacher and a.teacher.user else "",
            "attachment_path": a.attachment_path,
            "submission": {
                "id": sub.id,
                "submission_date": str(sub.submission_date),
                "status": sub.status,
                "marks_obtained": sub.marks_obtained,
                "feedback": sub.feedback,
                "file_path": sub.file_path
            } if sub else None
        })
    return items

@router.get("/results", dependencies=[Depends(require_feature("exams"))])
def get_my_results(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    results = db.query(Result).join(Exam).options(
        joinedload(Result.exam),
        joinedload(Result.subject)
    ).filter(
        Result.student_id == student.id,
        Exam.is_published == True
    ).order_by(Result.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "exam_name": r.exam.name if r.exam else "",
            "subject_name": r.subject.name if r.subject else "",
            "marks_obtained": r.marks_obtained,
            "max_marks": r.max_marks,
            "percentage": calculate_percentage(r.marks_obtained, r.max_marks),
            "grade": r.grade,
            "remarks": r.remarks
        }
        for r in results
    ]

@router.get("/fees", dependencies=[Depends(require_feature("finance"))])
def get_my_fees(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    return fee_service.get_student_fee_summary(db, student.id)

@router.get("/study-materials", dependencies=[Depends(require_feature("assignments"))])
def get_my_study_materials(
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    student = get_current_student(current_user, db)
    if not student.class_id:
        return []

    materials = db.query(StudyMaterial).options(
        joinedload(StudyMaterial.subject),
        joinedload(StudyMaterial.teacher)
    ).filter(StudyMaterial.class_id == student.class_id).order_by(StudyMaterial.upload_date.desc()).all()

    return [
        {
            "id": m.id,
            "title": m.title,
            "description": m.description,
            "subject_name": m.subject.name if m.subject else "",
            "teacher_name": m.teacher.user.full_name if m.teacher and m.teacher.user else "",
            "file_path": m.file_path,
            "file_type": m.file_type,
            "upload_date": str(m.upload_date)
        }
        for m in materials
    ]
