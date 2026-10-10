from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Enrollment(TenantOwnedMixin, Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    enrollment_date = Column(Date, nullable=False)
    status = Column(String(50), default="active")  # active, completed, transferred
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    student = relationship("Student", back_populates="enrollments")
    class_obj = relationship("ClassModel", back_populates="enrollments")
    academic_year = relationship("AcademicYear", back_populates="enrollments")
