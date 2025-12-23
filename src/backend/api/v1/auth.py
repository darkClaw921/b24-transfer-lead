"""Authentication endpoints."""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.api.v1.dependencies import get_current_user
from src.backend.core.database import get_main_db
from src.backend.core.config import settings
from src.backend.models.user import User
from src.backend.services.auth import AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""

    username: str
    role: str
    message: str


class UserResponse(BaseModel):
    """User response model."""

    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_main_db),
):
    """Login endpoint."""
    user = AuthService.authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = AuthService.create_session(user.id, user.username, user.role)

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
    )

    return LoginResponse(
        username=user.username,
        role=user.role,
        message="Login successful",
    )


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
):
    """Logout endpoint."""
    if session_id:
        AuthService.delete_session(session_id)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )

    return {"message": "Logout successful"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
    )

