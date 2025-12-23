"""Lead model for workflow database."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Lead(Base):
    """Lead model for workflow database."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=True, default="NEW")
    bitrix24_lead_id = Column(String, nullable=True, index=True)
    assigned_by_name = Column(String, nullable=True)  # Имя и фамилия ответственного из Bitrix24
    status_semantic_id = Column(String, nullable=True)  # Семантический ID статуса (S/F) для определения цвета
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    fields = relationship("LeadField", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, phone={self.phone}, name={self.name}, status={self.status})>"

