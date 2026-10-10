from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class StudyMaterial(TenantOwnedMixin, Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes
    upload_date = Column(DateTime, server_default=func.now(), nullable=False)

    class_obj = relationship("ClassModel", back_populates="study_materials")
    subject = relationship("Subject", back_populates="study_materials")
    teacher = relationship("Teacher", back_populates="study_materials")
