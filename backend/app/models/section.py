from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Section(TenantOwnedMixin, Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)  # e.g., A, B, Rose
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    room_number = Column(String(50), nullable=True)
    class_teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    class_obj = relationship("ClassModel", back_populates="sections")
    class_teacher = relationship("Teacher", back_populates="sections")
    students = relationship("Student", back_populates="section")
    timetable_entries = relationship("Timetable", back_populates="section")
