from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Result(TenantOwnedMixin, Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    marks_obtained = Column(Float, nullable=False)
    max_marks = Column(Float, default=100.0, nullable=False)
    grade = Column(String(10), nullable=True)  # A+, A, B, C, D, F
    remarks = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "subject_id", name="uq_exam_student_subject_result"),
    )

    exam = relationship("Exam", back_populates="results")
    student = relationship("Student", back_populates="results")
    subject = relationship("Subject", back_populates="results")
