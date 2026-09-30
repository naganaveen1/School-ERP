from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base

class Fee(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    fee_type = Column(String(50), default="Tuition")  # Tuition, Exam, Transport, Library, Other
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False)
    installment_name = Column(String(50), default="Annual", nullable=False)  # e.g., Semester 1, Installment 1, Annual
    installment_number = Column(Integer, default=1, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    class_obj = relationship("ClassModel", back_populates="fees")
    academic_year = relationship("AcademicYear", back_populates="fees")
    payments = relationship("Payment", back_populates="fee", cascade="all, delete-orphan")
