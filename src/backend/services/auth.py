"""Authentication service."""
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.backend.core.config import settings
from src.backend.models.user import User, UserRole

# In-memory session storage (in production, use Redis or database)
sessions: dict[str, dict] = {}


class AuthService:
    """Service for authentication and authorization."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash.

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            True if password matches
        """
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    @staticmethod
    def create_session(user_id: int, username: str, role: str) -> str:
        """Create a new session.

        Args:
            user_id: User ID
            username: Username
            role: User role

        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        expire_time = datetime.utcnow() + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)

        sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "expires_at": expire_time,
        }

        return session_id

    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        """Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if invalid/expired
        """
        if session_id not in sessions:
            return None

        session = sessions[session_id]
        if datetime.utcnow() > session["expires_at"]:
            del sessions[session_id]
            return None

        return session

    @staticmethod
    def delete_session(session_id: str):
        """Delete session.

        Args:
            session_id: Session ID
        """
        if session_id in sessions:
            del sessions[session_id]

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user by username and password.

        Args:
            db: Database session
            username: Username
            password: Password

        Returns:
            User object if authenticated, None otherwise
        """
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None

        if not AuthService.verify_password(password, user.password_hash):
            return None

        return user

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        password: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Create a new user.

        Args:
            db: Database session
            username: Username
            password: Plain text password
            role: User role

        Returns:
            Created user object

        Raises:
            ValueError: If user already exists
        """
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise ValueError(f"User {username} already exists")

        password_hash = AuthService.hash_password(password)
        user = User(username=username, password_hash=password_hash, role=role.value)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def is_admin(role: str) -> bool:
        """Check if role is admin.

        Args:
            role: User role

        Returns:
            True if admin
        """
        return role == UserRole.ADMIN.value

