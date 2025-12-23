"""User management endpoints (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.api.v1.dependencies import get_admin_user
from src.backend.core.database import get_main_db
from src.backend.models.user import User, UserRole
from src.backend.models.workflow import Workflow
from src.backend.models.user_workflow_access import user_workflow_access
from src.backend.services.auth import AuthService

router = APIRouter()


class CreateUserRequest(BaseModel):
    """Create user request model."""

    username: str
    password: str
    role: str = "user"
    workflow_ids: list[int] = []  # List of workflow IDs user should have access to


class UserResponse(BaseModel):
    """User response model."""

    id: int
    username: str
    role: str
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[UserResponse])
async def list_users(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_main_db),
):
    """List all users (admin only)."""
    users = db.query(User).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at.isoformat(),
        )
        for user in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_main_db),
):
    """Create a new user (admin only)."""
    try:
        role = UserRole(request.role) if request.role in ["admin", "user"] else UserRole.USER
        user = AuthService.create_user(db, request.username, request.password, role)
        
        # Grant access to specified workflows
        if request.workflow_ids:
            # Verify that all workflow IDs exist
            workflows = db.query(Workflow).filter(Workflow.id.in_(request.workflow_ids)).all()
            found_ids = {w.id for w in workflows}
            missing_ids = set(request.workflow_ids) - found_ids
            
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Workflows not found: {list(missing_ids)}",
                )
            
            # Add access relationships
            for workflow in workflows:
                if workflow not in user.accessible_workflows:
                    user.accessible_workflows.append(workflow)
            
            db.commit()
            db.refresh(user)
        
        return UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

