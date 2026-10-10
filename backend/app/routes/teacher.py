from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.teacher import Teacher
from backend.app.models.student import Student
from backend.app.models.class_model import ClassModel
from backend.app.models.subject import Subject
from backend.app.models.timetable import Timetable
from backend.app.models.submission import Submission
from backend.app.models.assignment import Assignment
from backend.app.utils.permissions import require_roles, require_feature

router = APIRouter(prefix="/teacher", tags=["Teacher Portal"])

def get_current_teacher(current_user: User, db: Session) -> Teacher:
    if not current_user.teacher_profile:
        raise HTTPException(status_code=400, detail="Teacher profile not found")
    return current_user.teacher_profile

@router.get("/profile")
def get_teacher_profile(
    current_user: User = Depends(require_roles(["TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = get_current_teacher(current_user, db)
    return {
        "id": teacher.id,
        "employee_id": teacher.employee_id,
        "qualification": teacher.qualification,
        "designation": teacher.designation,
        "joining_date": str(teacher.joining_date) if teacher.joining_date else None,
        "phone": teacher.phone or current_user.phone,
        "address": teacher.address,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "department_name": teacher.department.name if teacher.department else "General"
    }

@router.get("/classes")
def get_teacher_classes(
    current_user: User = Depends(require_roles(["TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = get_current_teacher(current_user, db)
    class_ids = set([s.class_id for s in teacher.subjects] + [sec.class_id for sec in teacher.sections])
    classes = db.query(ClassModel).filter(ClassModel.id.in_(list(class_ids))).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "grade_level": c.grade_level,
            "sections": [{"id": s.id, "name": s.name} for s in c.sections],
            "subjects": [{"id": subj.id, "name": subj.name, "code": subj.code} for subj in c.subjects if subj.teacher_id == teacher.id]
        }
        for c in classes
    ]

@router.get("/students")
def get_teacher_students(
    class_id: int = None,
    section_id: int = None,
    current_user: User = Depends(require_roles(["TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = get_current_teacher(current_user, db)
    allowed_class_ids = set([s.class_id for s in teacher.subjects] + [sec.class_id for sec in teacher.sections])

    query = db.query(Student).join(Student.user).filter(Student.class_id.in_(list(allowed_class_ids)))
    if class_id:
        query = query.filter(Student.class_id == class_id)
    if section_id:
        query = query.filter(Student.section_id == section_id)

    students = query.all()
    return [
        {
            "id": s.id,
            "admission_number": s.admission_number,
            "roll_number": s.roll_number,
            "full_name": s.user.full_name if s.user else "",
            "class_name": s.class_obj.name if s.class_obj else "",
            "section_name": s.section.name if s.section else ""
        }
        for s in students
    ]

@router.get("/timetable")
def get_teacher_timetable(
    current_user: User = Depends(require_roles(["TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = get_current_teacher(current_user, db)
    entries = db.query(Timetable).options(
        joinedload(Timetable.class_obj),
        joinedload(Timetable.section),
        joinedload(Timetable.subject)
    ).filter(Timetable.teacher_id == teacher.id).order_by(Timetable.day_of_week, Timetable.start_time).all()

    return [
        {
            "id": e.id,
            "day_of_week": e.day_of_week,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "room_number": e.room_number,
            "class_name": e.class_obj.name if e.class_obj else "",
            "section_name": e.section.name if e.section else "",
            "subject_name": e.subject.name if e.subject else ""
        }
        for e in entries
    ]

@router.get("/submissions", dependencies=[Depends(require_feature("assignments"))])
def get_teacher_submissions(
    current_user: User = Depends(require_roles(["TEACHER"])),
    db: Session = Depends(get_db)
):
    teacher = get_current_teacher(current_user, db)
    submissions = db.query(Submission).join(Assignment).options(
        joinedload(Submission.assignment),
        joinedload(Submission.student).joinedload(Student.user)
    ).filter(Assignment.teacher_id == teacher.id).order_by(Submission.submission_date.desc()).all()

    return [
        {
            "id": s.id,
            "assignment_id": s.assignment_id,
            "assignment_title": s.assignment.title if s.assignment else "",
            "student_name": s.student.user.full_name if s.student and s.student.user else "",
            "admission_number": s.student.admission_number if s.student else "",
            "file_path": s.file_path,
            "submission_date": str(s.submission_date),
            "marks_obtained": s.marks_obtained,
            "max_marks": s.assignment.max_marks if s.assignment else 100.0,
            "status": s.status,
            "feedback": s.feedback
        }
        for s in submissions
    ]
