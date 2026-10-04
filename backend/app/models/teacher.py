from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Teacher(TenantOwnedMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_teachers_tenant_employee"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    employee_id = Column(String(50), nullable=False, index=True)
    qualification = Column(String(100), nullable=True)
    designation = Column(String(100), default="Teacher")
    joining_date = Column(Date, nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="teacher_profile")
    department = relationship("Department", back_populates="teachers")
    subjects = relationship("Subject", back_populates="teacher")
    sections = relationship("Section", back_populates="class_teacher")
    assignments = relationship("Assignment", back_populates="teacher")
    study_materials = relationship("StudyMaterial", back_populates="teacher")
    timetable_entries = relationship("Timetable", back_populates="teacher")
