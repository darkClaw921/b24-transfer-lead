"""Database service for managing workflow databases."""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.backend.core.config import settings
from src.backend.models.lead import Base as LeadBase


class DatabaseService:
    """Service for managing workflow databases."""

    def __init__(self):
        """Initialize database service."""
        self.workflows_dir = Path(settings.WORKFLOWS_DIR)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def get_workflow_db_path(self, workflow_id: int) -> Path:
        """Get path to workflow database file."""
        workflow_dir = self.workflows_dir / str(workflow_id)
        workflow_dir.mkdir(parents=True, exist_ok=True)
        return workflow_dir / "database.db"

    def get_workflow_engine(self, workflow_id: int):
        """Get SQLAlchemy engine for workflow database."""
        db_path = self.get_workflow_db_path(workflow_id)
        db_url = f"sqlite:///{db_path}"
        return create_engine(db_url, connect_args={"check_same_thread": False})

    def init_workflow_db(self, workflow_id: int):
        """Initialize workflow database tables."""
        engine = self.get_workflow_engine(workflow_id)
        # Create tables for both Lead and LeadField models (they share the same Base)
        LeadBase.metadata.create_all(bind=engine)

    def get_workflow_session(self, workflow_id: int) -> Generator[Session, None, None]:
        """Get database session for workflow."""
        engine = self.get_workflow_engine(workflow_id)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def delete_workflow_db(self, workflow_id: int):
        """Delete workflow database."""
        db_path = self.get_workflow_db_path(workflow_id)
        if db_path.exists():
            os.remove(db_path)
        workflow_dir = db_path.parent
        if workflow_dir.exists() and not any(workflow_dir.iterdir()):
            workflow_dir.rmdir()


# Global instance
database_service = DatabaseService()

