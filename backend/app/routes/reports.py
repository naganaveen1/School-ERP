from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.attendance import Attendance
from backend.app.models.fee import Fee
from backend.app.models.payment import Payment
from backend.app.models.result import Result
from backend.app.models.student import Student
from backend.app.models.class_model import ClassModel
from backend.app.models.exam import Exam
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.school_access import teacher_class_ids, teacher_subject_ids

router = APIRouter(prefix="/reports", tags=["Reports"], dependencies=[Depends(require_feature("reports"))])

@router.get("/attendance")
def attendance_report(
    class_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL", "TEACHER"])),
    db: Session = Depends(get_db)
):
    query = db.query(Attendance)
    if current_user.role == "TEACHER":
        query = query.filter(Attendance.class_id.in_(teacher_class_ids(current_user)))
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    records = query.all()
    total = len(records)
    present = sum(1 for r in records if r.status.lower() == "present")
    absent = sum(1 for r in records if r.status.lower() == "absent")
    late = sum(1 for r in records if r.status.lower() == "late")
    percentage = round(((present + late) / total * 100), 2) if total > 0 else 0.0

    return {
        "total_records": total,
        "present": present,
        "absent": absent,
        "late": late,
        "percentage": percentage
    }

@router.get("/fees")
def fee_report(
    class_id: Optional[int] = None,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    fee_query = db.query(Fee)
    if class_id:
        fee_query = fee_query.filter(Fee.class_id == class_id)
    fees = fee_query.all()

    total_fees_expected = 0.0
    for fee in fees:
        if fee.class_id:
            num_students = db.query(Student).filter(Student.class_id == fee.class_id).count()
            total_fees_expected += fee.amount * num_students
        else:
            num_students = db.query(Student).count()
            total_fees_expected += fee.amount * num_students

    payment_query = db.query(
        func.sum(Payment.amount_paid), func.sum(Payment.discount_amount)
    ).filter(Payment.payment_status.in_(["PAID", "PARTIAL"]))
    if class_id:
        payment_query = payment_query.join(Student).filter(Student.class_id == class_id)
    total_collected, total_discounts = payment_query.one()
    total_collected = float(total_collected or 0)
    total_discounts = float(total_discounts or 0)

    return {
        "total_fees_expected": round(total_fees_expected, 2),
        "total_collected": round(total_collected, 2),
        "total_outstanding": round(max(0.0, total_fees_expected - total_collected - total_discounts), 2)
    }

@router.get("/academic")
def academic_performance_report(
    exam_id: Optional[int] = None,
    class_id: Optional[int] = None,
    current_user: User = Depends(require_roles(["SCHOOL_ADMIN", "PRINCIPAL", "TEACHER"])),
    db: Session = Depends(get_db)
):
    query = db.query(Result)
    if current_user.role == "TEACHER":
        query = query.filter(Result.subject_id.in_(teacher_subject_ids(current_user)))
    if exam_id:
        query = query.filter(Result.exam_id == exam_id)
    if class_id:
        query = query.join(Student).filter(Student.class_id == class_id)

    results = query.all()
    if not results:
        return {"total_results": 0, "average_percentage": 0.0, "grades_breakdown": {}}

    percentages = [(r.marks_obtained / r.max_marks * 100) for r in results if r.max_marks > 0]
    avg_pct = round(sum(percentages) / len(percentages), 2) if percentages else 0.0

    grades_count = {}
    for r in results:
        g = r.grade or "N/A"
        grades_count[g] = grades_count.get(g, 0) + 1

    return {
        "total_results": len(results),
        "average_percentage": avg_pct,
        "grades_breakdown": grades_count
    }
