"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.backend.core.config import settings

# Common Base for main database models
MainBase = declarative_base()

# Main database engine (for users and workflows)
main_engine = create_engine(
    settings.MAIN_DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.MAIN_DB_URL else {},
)

MainSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=main_engine)


def init_main_db():
    """Initialize main database tables."""
    MainBase.metadata.create_all(bind=main_engine)


def get_main_db():
    """Get main database session."""
    db = MainSessionLocal()
    try:
        yield db
    finally:
        db.close()
