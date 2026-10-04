from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class AcademicYear(TenantOwnedMixin, Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_academic_years_tenant_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)  # e.g., 2025-2026
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    classes = relationship("ClassModel", back_populates="academic_year")
    enrollments = relationship("Enrollment", back_populates="academic_year")
    exams = relationship("Exam", back_populates="academic_year")
    fees = relationship("Fee", back_populates="academic_year")
