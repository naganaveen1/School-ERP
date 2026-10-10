from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declared_attr
from sqlalchemy.sql import func

from backend.app.database import Base


TENANT_STATUSES = ("TRIAL", "ACTIVE", "SUSPENDED", "EXPIRED", "CANCELLED", "ARCHIVED")


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('TRIAL','ACTIVE','SUSPENDED','EXPIRED','CANCELLED','ARCHIVED')",
            name="ck_tenants_status",
        ),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)
    legal_name = Column(String(180))
    email = Column(String(150))
    phone = Column(String(30))
    address = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100), nullable=False, default="India")
    postal_code = Column(String(20))
    logo_url = Column(String(500))
    favicon_url = Column(String(500))
    primary_color = Column(String(7), nullable=False, default="#0d675f")
    secondary_color = Column(String(7), nullable=False, default="#163530")
    timezone = Column(String(80), nullable=False, default="Asia/Kolkata")
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(20), nullable=False, default="TRIAL", index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantOwnedMixin:
    @declared_attr
    def tenant_id(cls):
        return Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
