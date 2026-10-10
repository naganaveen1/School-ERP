from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Department(TenantOwnedMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_departments_tenant_name"),
        UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    teachers = relationship("Teacher", back_populates="department")
    classes = relationship("ClassModel", back_populates="department")
