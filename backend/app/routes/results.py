from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.result import Result
from backend.app.models.exam import Exam
from backend.app.models.student import Student
from backend.app.models.subject import Subject
from backend.app.schemas.result import (
    ResultCreate, ResultBulkCreate, ResultUpdate, ResultResponse, StudentReportCard
)
from backend.app.services.exam_service import exam_service
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.helpers import log_audit_action, calculate_grade, calculate_percentage
from backend.app.utils.school_access import parent_child_ids, teacher_subject_ids
from backend.app.routes.students import verify_student_access

router = APIRouter(prefix="/results", tags=["Results"], dependencies=[Depends(require_feature("exams"))])


def _validate_result_context(db: Session, user: User, exam_id: int, subject_id: int, student_ids: list[int]):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not exam or not subject or exam.class_id != subject.class_id:
        raise HTTPException(status_code=400, detail="Exam and subject must belong to the same class")
    if user.role == "TEACHER" and subject_id not in teacher_subject_ids(user):
        raise HTTPException(status_code=403, detail="Subject is not assigned to this teacher")
    if len(student_ids) != len(set(student_ids)):
        raise HTTPException(status_code=400, detail="Duplicate student in results")
    matched = db.query(Student.id).filter(Student.id.in_(student_ids), Student.class_id == exam.class_id).count()
    if matched != len(student_ids):
        raise HTTPException(status_code=400, detail="Result students must belong to the exam class")

@router.post("/bulk", response_model=List[ResultResponse])
def record_bulk_results(
    bulk_in: ResultBulkCreate,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    _validate_result_context(db, current_user, bulk_in.exam_id, bulk_in.subject_id,
                             [item.student_id for item in bulk_in.records])
    if any(item.max_marks <= 0 or item.marks_obtained < 0 or item.marks_obtained > item.max_marks
           for item in bulk_in.records):
        raise HTTPException(status_code=400, detail="Marks must be between zero and the maximum")
    saved = exam_service.record_results_bulk(
        db=db,
        exam_id=bulk_in.exam_id,
        subject_id=bulk_in.subject_id,
        records=bulk_in.records
    )

    log_audit_action(
        db, "MARKS_RECORDED", "Result",
        f"exam_{bulk_in.exam_id}_subj_{bulk_in.subject_id}",
        f"Recorded marks for {len(saved)} students",
        current_user.id
    )

    return [
        ResultResponse(
            id=r.id,
            exam_id=r.exam_id,
            student_id=r.student_id,
            subject_id=r.subject_id,
            marks_obtained=r.marks_obtained,
            max_marks=r.max_marks,
            percentage=calculate_percentage(r.marks_obtained, r.max_marks),
            grade=r.grade,
            remarks=r.remarks,
            student_name=r.student.user.full_name if r.student and r.student.user else None,
            admission_number=r.student.admission_number if r.student else None,
            created_at=r.created_at
        )
        for r in saved
    ]

@router.post("", response_model=ResultResponse)
def record_result(
    res_in: ResultCreate,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    _validate_result_context(db, current_user, res_in.exam_id, res_in.subject_id, [res_in.student_id])
    if res_in.max_marks <= 0 or res_in.marks_obtained < 0 or res_in.marks_obtained > res_in.max_marks:
        raise HTTPException(status_code=400, detail="Marks must be between zero and the maximum")
    pct = calculate_percentage(res_in.marks_obtained, res_in.max_marks)
    grade = calculate_grade(pct)

    existing = db.query(Result).filter(
        Result.exam_id == res_in.exam_id,
        Result.student_id == res_in.student_id,
        Result.subject_id == res_in.subject_id
    ).first()

    if existing:
        existing.marks_obtained = res_in.marks_obtained
        existing.max_marks = res_in.max_marks
        existing.grade = grade
        existing.remarks = res_in.remarks
        res = existing
    else:
        res = Result(
            exam_id=res_in.exam_id,
            student_id=res_in.student_id,
            subject_id=res_in.subject_id,
            marks_obtained=res_in.marks_obtained,
            max_marks=res_in.max_marks,
            grade=grade,
            remarks=res_in.remarks
        )
        db.add(res)

    db.commit()
    db.refresh(res)

    log_audit_action(db, "MARKS_RECORD", "Result", str(res.id), f"Recorded mark {res.marks_obtained}", current_user.id)

    return ResultResponse(
        id=res.id,
        exam_id=res.exam_id,
        student_id=res.student_id,
        subject_id=res.subject_id,
        marks_obtained=res.marks_obtained,
        max_marks=res.max_marks,
        percentage=pct,
        grade=grade,
        remarks=res.remarks,
        created_at=res.created_at
    )

@router.get("", response_model=List[ResultResponse])
def get_results(
    exam_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    student_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Result).options(
        joinedload(Result.exam),
        joinedload(Result.subject),
        joinedload(Result.student).joinedload(Student.user)
    )

    if current_user.role == "STUDENT":
        if not current_user.student_profile:
            return []
        query = query.filter(Result.student_id == current_user.student_profile.id)
    elif current_user.role == "PARENT":
        query = query.filter(Result.student_id.in_(parent_child_ids(current_user)))
    elif current_user.role == "TEACHER":
        query = query.filter(Result.subject_id.in_(teacher_subject_ids(current_user)))
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        return []
    if student_id:
        query = query.filter(Result.student_id == student_id)

    if exam_id:
        query = query.filter(Result.exam_id == exam_id)
    if subject_id:
        query = query.filter(Result.subject_id == subject_id)

    # If student or parent, only show published exam results
    if current_user.role in ["STUDENT", "PARENT"]:
        query = query.join(Exam).filter(Exam.is_published == True)

    results = query.order_by(Result.id.desc()).all()

    return [
        ResultResponse(
            id=r.id,
            exam_id=r.exam_id,
            student_id=r.student_id,
            subject_id=r.subject_id,
            marks_obtained=r.marks_obtained,
            max_marks=r.max_marks,
            percentage=calculate_percentage(r.marks_obtained, r.max_marks),
            grade=r.grade,
            remarks=r.remarks,
            exam_name=r.exam.name if r.exam else None,
            student_name=r.student.user.full_name if r.student and r.student.user else None,
            admission_number=r.student.admission_number if r.student else None,
            roll_number=r.student.roll_number if r.student else None,
            subject_name=r.subject.name if r.subject else None,
            created_at=r.created_at
        )
        for r in results
    ]

@router.get("/report-card", response_model=StudentReportCard)
def get_report_card(
    exam_id: int,
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    student = verify_student_access(student_id, current_user, db)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam or exam.class_id != student.class_id:
        raise HTTPException(status_code=404, detail="Exam not found")
    if current_user.role in {"STUDENT", "PARENT"} and not exam.is_published:
        raise HTTPException(status_code=404, detail="Exam not found")

    return exam_service.get_student_report(db, exam_id, student_id)
