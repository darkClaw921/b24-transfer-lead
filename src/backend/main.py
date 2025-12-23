"""Main FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.backend.api.v1 import auth, leads, public, users, webhook, workflows
from src.backend.core.config import settings
from src.backend.core.database import init_main_db
# Import models to ensure they are registered with SQLAlchemy
from src.backend.models import user_workflow_access  # noqa: F401
from src.backend.utils.migrate_db import (
    migrate_workflow_api_token,
    migrate_workflow_app_token,
    migrate_workflow_field_mapping,
    migrate_workflow_settings,
    migrate_workflows_table,
    migrate_user_workflow_access,
)

app = FastAPI(
    title="Bitrix24 Lead Transfer API",
    description="API for transferring leads to Bitrix24",
    version="0.1.0",
    docs_url="/docs" if settings.ENABLE_DOCS else None,  # Отключить Swagger UI если ENABLE_DOCS=False
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,  # Отключить ReDoc если ENABLE_DOCS=False
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,  # Отключить OpenAPI schema если ENABLE_DOCS=False
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_main_db()
    # Run migrations for workflows table
    migrate_workflows_table()
    migrate_workflow_settings()
    migrate_workflow_app_token()
    migrate_workflow_api_token()
    migrate_workflow_field_mapping()
    migrate_user_workflow_access()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(leads.router, prefix="/api/v1/workflows", tags=["leads"])
app.include_router(webhook.router, prefix="/api/v1/webhook", tags=["webhook"])
app.include_router(public.router, prefix="/api/v1/public", tags=["public"])

# Mount static files for frontend (in production)
# app.mount("/", StaticFiles(directory="src/frontend/dist", html=True), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7860)

