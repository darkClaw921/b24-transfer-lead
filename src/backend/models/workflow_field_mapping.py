"""Workflow field mapping model for main database."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.backend.core.database import MainBase


class WorkflowFieldMapping(MainBase):
    """Workflow field mapping model."""

    __tablename__ = "workflow_field_mappings"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    field_name = Column(String, nullable=False)  # Field name in our system (e.g., "email", "company")
    display_name = Column(String, nullable=False)  # Human-readable name for display in UI (e.g., "Email", "Company")
    bitrix24_field_id = Column(String, nullable=False)  # Field ID in Bitrix24 (e.g., "EMAIL", "COMPANY_TITLE")
    bitrix24_field_name = Column(String, nullable=False)  # Human-readable field name from Bitrix24
    entity_type = Column(String, nullable=False)  # "lead" or "deal"
    update_on_event = Column(Boolean, nullable=False, default=False)  # Update this field when receiving webhook event from Bitrix24
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="field_mappings")

    def __repr__(self) -> str:
        return f"<WorkflowFieldMapping(id={self.id}, workflow_id={self.workflow_id}, field_name={self.field_name}, bitrix24_field_id={self.bitrix24_field_id})>"

