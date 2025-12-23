"""User model for main database."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from src.backend.core.database import MainBase


class UserRole(str, Enum):
    """User role enum."""

    ADMIN = "admin"
    USER = "user"


class User(MainBase):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default=UserRole.USER.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflows = relationship("Workflow", back_populates="user")  # Workflows created by user
    accessible_workflows = relationship(
        "Workflow",
        secondary="user_workflow_access",
        back_populates="accessible_users",
        lazy="dynamic",
    )  # Workflows user has access to

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

