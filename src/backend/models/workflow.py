"""Workflow model for main database."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.backend.core.database import MainBase


class Workflow(MainBase):
    """Workflow model."""

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    bitrix24_webhook_url = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Settings for Bitrix24 entity creation
    entity_type = Column(String, nullable=False, default="lead")  # "lead" or "deal"
    deal_category_id = Column(Integer, nullable=True)  # Funnel ID for deals
    deal_stage_id = Column(String, nullable=True)  # Stage ID for deals
    lead_status_id = Column(String, nullable=True, default="NEW")  # Status ID for leads
    
    # Webhook settings
    app_token = Column(String, nullable=True)  # Application token for webhook verification
    bitrix24_domain = Column(String, nullable=True, index=True)  # Bitrix24 portal domain for webhook routing
    
    # Public API settings
    api_token = Column(String, nullable=True, unique=True, index=True)  # Unique token for public API endpoint

    user = relationship("User", back_populates="workflows")
    accessible_users = relationship(
        "User",
        secondary="user_workflow_access",
        back_populates="accessible_workflows",
        lazy="dynamic",
    )
    field_mappings = relationship("WorkflowFieldMapping", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, name={self.name}, user_id={self.user_id}, entity_type={self.entity_type}, domain={self.bitrix24_domain})>"

