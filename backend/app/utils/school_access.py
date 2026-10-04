"""Same-school resource membership checks shared by academic routes."""

from backend.app.models.user import User
from backend.app.models.subject import Subject
from fastapi import HTTPException
from sqlalchemy.orm import Session


def teacher_class_ids(user: User) -> set[int]:
    teacher = user.teacher_profile if user.role == "TEACHER" else None
    if not teacher:
        return set()
    return {subject.class_id for subject in teacher.subjects if subject.class_id} | {
        section.class_id for section in teacher.sections if section.class_id
    }


def teacher_subject_ids(user: User) -> set[int]:
    teacher = user.teacher_profile if user.role == "TEACHER" else None
    return {subject.id for subject in teacher.subjects} if teacher else set()


def parent_child_ids(user: User) -> set[int]:
    parent = user.parent_profile if user.role == "PARENT" else None
    return {child.id for child in parent.students} if parent else set()


def parent_class_ids(user: User) -> set[int]:
    parent = user.parent_profile if user.role == "PARENT" else None
    return {child.class_id for child in parent.students if child.class_id} if parent else set()


def teacher_for_subject(db: Session, user: User, class_id: int, subject_id: int) -> int:
    """Validate the class/subject pair before a staff member creates class content."""
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.class_id == class_id).first()
    if not subject:
        raise HTTPException(status_code=400, detail="Subject does not belong to this class")
    if user.role == "TEACHER":
        teacher = user.teacher_profile
        if not teacher or subject.teacher_id != teacher.id:
            raise HTTPException(status_code=403, detail="Subject is not assigned to this teacher")
        return teacher.id
    if subject.teacher_id is None:
        raise HTTPException(status_code=400, detail="Assign a teacher to the subject first")
    return subject.teacher_id
