from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Subject(TenantOwnedMixin, Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)  # Mathematics, Physics
    code = Column(String(20), nullable=False, index=True)   # MATH101
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    class_obj = relationship("ClassModel", back_populates="subjects")
    teacher = relationship("Teacher", back_populates="subjects")
    assignments = relationship("Assignment", back_populates="subject")
    study_materials = relationship("StudyMaterial", back_populates="subject")
    timetable_entries = relationship("Timetable", back_populates="subject")
    results = relationship("Result", back_populates="subject")
