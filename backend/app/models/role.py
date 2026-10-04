import enum
from sqlalchemy import Column, Integer, String
from backend.app.database import Base

class RoleEnum(str, enum.Enum):
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    PRINCIPAL = "PRINCIPAL"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"
    PLATFORM_SUPER_ADMIN = "PLATFORM_SUPER_ADMIN"
    PLATFORM_SUPPORT = "PLATFORM_SUPPORT"
    PLATFORM_BILLING = "PLATFORM_BILLING"

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
