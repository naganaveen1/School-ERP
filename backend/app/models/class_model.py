from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class ClassModel(TenantOwnedMixin, Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)  # e.g., Grade 10, Class 10A
    grade_level = Column(Integer, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    department = relationship("Department", back_populates="classes")
    academic_year = relationship("AcademicYear", back_populates="classes")
    sections = relationship("Section", back_populates="class_obj", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="class_obj", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="class_obj")
    enrollments = relationship("Enrollment", back_populates="class_obj")
    fees = relationship("Fee", back_populates="class_obj")
    study_materials = relationship("StudyMaterial", back_populates="class_obj")
    assignments = relationship("Assignment", back_populates="class_obj")
    attendances = relationship("Attendance", back_populates="class_obj")
