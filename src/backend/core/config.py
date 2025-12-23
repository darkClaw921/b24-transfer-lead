"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    MAIN_DB_URL: str = "sqlite:///./main.db"
    WORKFLOWS_DIR: str = "./workflows"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    SESSION_COOKIE_NAME: str = "session_id"
    SESSION_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:3012"]

    # Frontend URL for public API endpoints
    FRONTEND_URL: str = "http://localhost:3012"

    # API Documentation
    ENABLE_DOCS: bool = False  # Отключить Swagger UI по умолчанию для безопасности

    # Admin user creation (used only in create_admin.py script)
    ADMIN_USERNAME: str | None = None
    ADMIN_PASSWORD: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

