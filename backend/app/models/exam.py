from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Exam(TenantOwnedMixin, Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Mid-Term Exam, Final Exam
    exam_type = Column(String(50), nullable=False)  # Midterm, Final, Unit Test, Quiz
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    academic_year = relationship("AcademicYear", back_populates="exams")
    class_obj = relationship("ClassModel")
    results = relationship("Result", back_populates="exam", cascade="all, delete-orphan")
