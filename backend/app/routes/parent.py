from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.parent import Parent
from backend.app.models.student import Student
from backend.app.models.assignment import Assignment
from backend.app.models.result import Result
from backend.app.models.exam import Exam
from backend.app.services.attendance_service import attendance_service
from backend.app.services.fee_service import fee_service
from backend.app.utils.permissions import require_roles, require_feature
from backend.app.utils.helpers import calculate_percentage

router = APIRouter(prefix="/parent", tags=["Parent Portal"])

def get_parent_and_child(parent_user: User, child_id: int, db: Session) -> Student:
    parent = parent_user.parent_profile
    if not parent:
        raise HTTPException(status_code=400, detail="Parent profile not found")

    student = db.query(Student).filter(
        Student.id == child_id,
        Student.parent_id == parent.id
    ).first()

    if not student:
        raise HTTPException(status_code=403, detail="Child not found or not linked to this parent account")
    return student

@router.get("/children")
def get_children(
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    parent = current_user.parent_profile
    if not parent:
        raise HTTPException(status_code=400, detail="Parent profile not found")

    students = db.query(Student).options(
        joinedload(Student.user),
        joinedload(Student.class_obj),
        joinedload(Student.section)
    ).filter(Student.parent_id == parent.id).all()

    return [
        {
            "id": s.id,
            "name": s.user.full_name if s.user else "",
            "admission_number": s.admission_number,
            "roll_number": s.roll_number,
            "class_name": s.class_obj.name if s.class_obj else "",
            "section_name": s.section.name if s.section else ""
        }
        for s in students
    ]

@router.get("/child/{child_id}/profile")
def get_child_profile(
    child_id: int,
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    student = get_parent_and_child(current_user, child_id, db)
    return {
        "id": student.id,
        "name": student.user.full_name if student.user else "",
        "admission_number": student.admission_number,
        "roll_number": student.roll_number,
        "class_name": student.class_obj.name if student.class_obj else "",
        "section_name": student.section.name if student.section else "",
        "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
        "gender": student.gender,
        "blood_group": student.blood_group,
        "address": student.address
    }

@router.get("/child/{child_id}/attendance", dependencies=[Depends(require_feature("attendance"))])
def get_child_attendance(
    child_id: int,
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    student = get_parent_and_child(current_user, child_id, db)
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

@router.get("/child/{child_id}/results", dependencies=[Depends(require_feature("exams"))])
def get_child_results(
    child_id: int,
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    student = get_parent_and_child(current_user, child_id, db)
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

@router.get("/child/{child_id}/fees", dependencies=[Depends(require_feature("finance"))])
def get_child_fees(
    child_id: int,
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    student = get_parent_and_child(current_user, child_id, db)
    return fee_service.get_student_fee_summary(db, student.id)

@router.get("/child/{child_id}/assignments", dependencies=[Depends(require_feature("assignments"))])
def get_child_assignments(
    child_id: int,
    current_user: User = Depends(require_roles(["PARENT"])),
    db: Session = Depends(get_db)
):
    student = get_parent_and_child(current_user, child_id, db)
    if not student.class_id:
        return []

    assignments = db.query(Assignment).options(
        joinedload(Assignment.subject),
        joinedload(Assignment.submissions)
    ).filter(
        Assignment.class_id == student.class_id,
        (Assignment.section_id.is_(None)) | (Assignment.section_id == student.section_id),
    ).all()

    items = []
    for a in assignments:
        sub = next((s for s in a.submissions if s.student_id == student.id), None)
        items.append({
            "id": a.id,
            "title": a.title,
            "subject_name": a.subject.name if a.subject else "",
            "due_date": str(a.due_date),
            "submitted": sub is not None,
            "submission_status": sub.status if sub else "pending",
            "marks_obtained": sub.marks_obtained if sub else None,
            "max_marks": a.max_marks
        })
    return items
