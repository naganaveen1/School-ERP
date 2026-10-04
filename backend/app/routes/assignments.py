from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.teacher import Teacher
from backend.app.models.student import Student
from backend.app.models.section import Section
from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission
from backend.app.schemas.assignment import (
    AssignmentCreate, AssignmentUpdate, AssignmentResponse,
    SubmissionGrade, SubmissionResponse
)
from backend.app.services.assignment_service import assignment_service
from backend.app.services.file_service import file_service
from backend.app.services.notification_service import notification_service
from backend.app.utils.permissions import require_roles, get_current_active_user, require_feature
from backend.app.utils.helpers import log_audit_action
from backend.app.utils.school_access import teacher_for_subject

router = APIRouter(prefix="/assignments", tags=["Assignments"], dependencies=[Depends(require_feature("assignments"))])


def _can_view_assignment(assignment: Assignment, user: User) -> bool:
    if user.role in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        return True
    if user.role == "TEACHER":
        return bool(user.teacher_profile and assignment.teacher_id == user.teacher_profile.id)
    if user.role == "STUDENT":
        student = user.student_profile
        return bool(student and student.class_id == assignment.class_id and
                    (assignment.section_id is None or assignment.section_id == student.section_id))
    if user.role == "PARENT":
        return bool(user.parent_profile and any(
            child.class_id == assignment.class_id and
            (assignment.section_id is None or assignment.section_id == child.section_id)
            for child in user.parent_profile.students
        ))
    return False

@router.get("", response_model=List[AssignmentResponse])
def list_assignments(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(Assignment).options(
        joinedload(Assignment.class_obj),
        joinedload(Assignment.section),
        joinedload(Assignment.subject),
        joinedload(Assignment.teacher).joinedload(Teacher.user),
        joinedload(Assignment.submissions)
    )

    if current_user.role == "STUDENT":
        student = current_user.student_profile
        if not student or student.class_id is None:
            return []
        query = query.filter(Assignment.class_id == student.class_id)
        query = query.filter((Assignment.section_id.is_(None)) | (Assignment.section_id == student.section_id))
    elif current_user.role == "TEACHER":
        teacher = current_user.teacher_profile
        if not teacher:
            return []
        query = query.filter(Assignment.teacher_id == teacher.id)
    elif current_user.role == "PARENT":
        children = current_user.parent_profile.students if current_user.parent_profile else []
        if not children:
            return []
        query = query.filter(Assignment.class_id.in_([child.class_id for child in children if child.class_id]))
    elif current_user.role not in {"SCHOOL_ADMIN", "PRINCIPAL"}:
        return []
    if class_id:
        query = query.filter(Assignment.class_id == class_id)

    if subject_id:
        query = query.filter(Assignment.subject_id == subject_id)
    if teacher_id:
        query = query.filter(Assignment.teacher_id == teacher_id)

    assignments = [a for a in query.order_by(Assignment.due_date.desc()).all()
                   if _can_view_assignment(a, current_user)]

    student_id = current_user.student_profile.id if current_user.role == "STUDENT" and current_user.student_profile else None

    responses = []
    for a in assignments:
        my_sub = None
        if student_id:
            sub = next((s for s in a.submissions if s.student_id == student_id), None)
            if sub:
                my_sub = {
                    "id": sub.id,
                    "submission_date": str(sub.submission_date),
                    "file_path": sub.file_path,
                    "status": sub.status,
                    "marks_obtained": sub.marks_obtained,
                    "feedback": sub.feedback
                }

        responses.append(AssignmentResponse(
            id=a.id,
            title=a.title,
            description=a.description,
            class_id=a.class_id,
            section_id=a.section_id,
            subject_id=a.subject_id,
            teacher_id=a.teacher_id,
            due_date=a.due_date,
            max_marks=a.max_marks,
            attachment_path=a.attachment_path,
            class_name=a.class_obj.name if a.class_obj else None,
            section_name=a.section.name if a.section else None,
            subject_name=a.subject.name if a.subject else None,
            teacher_name=a.teacher.user.full_name if a.teacher and a.teacher.user else None,
            submission_count=len(a.submissions),
            my_submission=my_sub,
            created_at=a.created_at,
            updated_at=a.updated_at
        ))
    return responses

@router.post("", response_model=AssignmentResponse)
def create_assignment(
    title: str = Form(...),
    class_id: int = Form(...),
    subject_id: int = Form(...),
    due_date: datetime = Form(...),
    description: Optional[str] = Form(None),
    section_id: Optional[int] = Form(None),
    max_marks: float = Form(100.0),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    teacher_id = teacher_for_subject(db, current_user, class_id, subject_id)
    if section_id and not db.query(Section.id).filter(Section.id == section_id,
                                                      Section.class_id == class_id).first():
        raise HTTPException(status_code=400, detail="Section does not belong to this class")

    attachment_path = None
    if file and file.filename:
        attachment_path = file_service.save_upload_file(file, "assignments", current_user.tenant_id)

    assignment_in = AssignmentCreate(
        title=title,
        description=description,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        due_date=due_date,
        max_marks=max_marks
    )
    try:
        assignment = assignment_service.create_assignment(db, teacher_id, assignment_in, attachment_path)
    except Exception:
        if attachment_path:
            file_service.delete_file(attachment_path)
        raise

    # Notify students in that class
    students = db.query(Student).filter(Student.class_id == class_id).all()
    for s in students:
        notification_service.create_notification(
            db=db,
            user_id=s.user_id,
            title="New Assignment Posted",
            message=f"New assignment '{title}' has been assigned. Due: {due_date.strftime('%Y-%m-%d %H:%M')}",
            link="/frontend/student/assignments.html",
            notification_type="ASSIGNMENT"
        )

    log_audit_action(db, "ASSIGNMENT_CREATE", "Assignment", str(assignment.id), f"Created assignment {title}", current_user.id)

    return AssignmentResponse(
        id=assignment.id,
        title=assignment.title,
        description=assignment.description,
        class_id=assignment.class_id,
        section_id=assignment.section_id,
        subject_id=assignment.subject_id,
        teacher_id=assignment.teacher_id,
        due_date=assignment.due_date,
        max_marks=assignment.max_marks,
        attachment_path=assignment.attachment_path,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at
    )

@router.get("/{assignment_id}")
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    a = db.query(Assignment).options(
        joinedload(Assignment.class_obj),
        joinedload(Assignment.section),
        joinedload(Assignment.subject),
        joinedload(Assignment.teacher).joinedload(Teacher.user),
        joinedload(Assignment.submissions)
    ).filter(Assignment.id == assignment_id).first()

    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _can_view_assignment(a, current_user):
        raise HTTPException(status_code=404, detail="Assignment not found")

    my_sub = None
    if current_user.role == "STUDENT" and current_user.student_profile:
        sub = next((s for s in a.submissions if s.student_id == current_user.student_profile.id), None)
        if sub:
            my_sub = {
                "id": sub.id,
                "submission_date": str(sub.submission_date),
                "file_path": sub.file_path,
                "status": sub.status,
                "marks_obtained": sub.marks_obtained,
                "feedback": sub.feedback
            }

    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "class_id": a.class_id,
        "section_id": a.section_id,
        "subject_id": a.subject_id,
        "teacher_id": a.teacher_id,
        "due_date": a.due_date,
        "max_marks": a.max_marks,
        "attachment_path": a.attachment_path,
        "class_name": a.class_obj.name if a.class_obj else None,
        "section_name": a.section.name if a.section else None,
        "subject_name": a.subject.name if a.subject else None,
        "teacher_name": a.teacher.user.full_name if a.teacher and a.teacher.user else None,
        "submission_count": len(a.submissions),
        "my_submission": my_sub,
        "created_at": a.created_at,
        "updated_at": a.updated_at
    }

@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if current_user.role == "TEACHER" and (not current_user.teacher_profile or a.teacher_id != current_user.teacher_profile.id):
        raise HTTPException(status_code=403, detail="Cannot delete assignment created by another teacher")

    if a.attachment_path:
        file_service.delete_file(a.attachment_path)

    db.delete(a)
    db.commit()
    log_audit_action(db, "ASSIGNMENT_DELETE", "Assignment", str(assignment_id), "Deleted assignment", current_user.id)
    return {"message": "Assignment deleted successfully"}

# Submissions
@router.post("/{assignment_id}/submit")
def submit_assignment(
    assignment_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(["STUDENT"])),
    db: Session = Depends(get_db)
):
    if not current_user.student_profile:
        raise HTTPException(status_code=400, detail="Student profile not found")

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment or not _can_view_assignment(assignment, current_user):
        raise HTTPException(status_code=404, detail="Assignment not found")

    file_path = file_service.save_upload_file(file, "assignments", current_user.tenant_id)
    try:
        submission = assignment_service.submit_assignment(
            db=db,
            assignment_id=assignment_id,
            student_id=current_user.student_profile.id,
            file_path=file_path
        )
    except Exception:
        file_service.delete_file(file_path)
        raise

    log_audit_action(db, "SUBMISSION_CREATE", "Submission", str(submission.id), f"Student {current_user.username} submitted assignment {assignment_id}", current_user.id)

    return {
        "message": "Assignment submitted successfully",
        "submission_id": submission.id,
        "status": submission.status,
        "submission_date": submission.submission_date
    }

@router.get("/{assignment_id}/submissions", response_model=List[SubmissionResponse])
def get_assignment_submissions(
    assignment_id: int,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN", "PRINCIPAL"])),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if current_user.role == "TEACHER" and not _can_view_assignment(assignment, current_user):
        raise HTTPException(status_code=404, detail="Assignment not found")

    submissions = db.query(Submission).options(
        joinedload(Submission.student).joinedload(Student.user)
    ).filter(Submission.assignment_id == assignment_id).all()

    return [
        SubmissionResponse(
            id=s.id,
            assignment_id=s.assignment_id,
            student_id=s.student_id,
            student_name=s.student.user.full_name if s.student and s.student.user else None,
            admission_number=s.student.admission_number if s.student else None,
            file_path=s.file_path,
            submission_date=s.submission_date,
            marks_obtained=s.marks_obtained,
            feedback=s.feedback,
            status=s.status,
            assignment_title=assignment.title,
            max_marks=assignment.max_marks,
            created_at=s.created_at
        )
        for s in submissions
    ]

@router.put("/submissions/{submission_id}/grade", response_model=SubmissionResponse)
def grade_submission(
    submission_id: int,
    grade_data: SubmissionGrade,
    current_user: User = Depends(require_roles(["TEACHER", "SCHOOL_ADMIN"])),
    db: Session = Depends(get_db)
):
    target = db.query(Submission).filter(Submission.id == submission_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role == "TEACHER" and not _can_view_assignment(target.assignment, current_user):
        raise HTTPException(status_code=404, detail="Submission not found")
    if grade_data.marks_obtained < 0 or grade_data.marks_obtained > target.assignment.max_marks:
        raise HTTPException(status_code=400, detail="Marks must be between zero and the assignment maximum")
    sub = assignment_service.grade_submission(
        db=db,
        submission_id=submission_id,
        marks_obtained=grade_data.marks_obtained,
        feedback=grade_data.feedback
    )

    # Notify student
    if sub.student and sub.student.user_id:
        notification_service.create_notification(
            db=db,
            user_id=sub.student.user_id,
            title="Assignment Graded",
            message=f"Your submission for assignment '{sub.assignment.title}' was graded: {sub.marks_obtained}/{sub.assignment.max_marks}",
            link=f"/frontend/student/assignments.html",
            notification_type="SUCCESS"
        )

    log_audit_action(db, "SUBMISSION_GRADE", "Submission", str(sub.id), f"Graded submission with {sub.marks_obtained}", current_user.id)

    return SubmissionResponse(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        student_name=sub.student.user.full_name if sub.student and sub.student.user else None,
        admission_number=sub.student.admission_number if sub.student else None,
        file_path=sub.file_path,
        submission_date=sub.submission_date,
        marks_obtained=sub.marks_obtained,
        feedback=sub.feedback,
        status=sub.status,
        assignment_title=sub.assignment.title if sub.assignment else None,
        max_marks=sub.assignment.max_marks if sub.assignment else None,
        created_at=sub.created_at
    )
