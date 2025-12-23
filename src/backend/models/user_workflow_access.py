"""User-Workflow access model for many-to-many relationship."""
from sqlalchemy import Column, ForeignKey, Integer, Table

from src.backend.core.database import MainBase

# Association table for many-to-many relationship between User and Workflow
user_workflow_access = Table(
    "user_workflow_access",
    MainBase.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, index=True),
    Column("workflow_id", Integer, ForeignKey("workflows.id"), primary_key=True, index=True),
)

