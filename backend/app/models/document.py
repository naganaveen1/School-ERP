from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.database import Base
from backend.app.models.tenant import TenantOwnedMixin

class Document(TenantOwnedMixin, Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    file_path = Column(String(255), nullable=False)
    document_type = Column(String(50), default="General")  # Certificate, ID Card, Academic, General, Report
    file_size = Column(Integer, nullable=True)  # in bytes
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="documents")
