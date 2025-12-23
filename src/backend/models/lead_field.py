"""Lead field model for workflow database."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.backend.models.lead import Base


class LeadField(Base):
    """Lead field model for workflow database."""

    __tablename__ = "lead_fields"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False, index=True)  # Field name (matches field_name from mapping)
    field_value = Column(String, nullable=False)  # Field value
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    lead = relationship("Lead", back_populates="fields")

    def __repr__(self) -> str:
        return f"<LeadField(id={self.id}, lead_id={self.lead_id}, field_name={self.field_name}, field_value={self.field_value})>"

