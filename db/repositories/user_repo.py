"""
User repository — all database operations for User model.
Services never write raw queries — they call these methods.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    DatabaseError
)
from core.logger import get_logger
from core.security import PasswordHandler
from db.models import User

logger = get_logger(__name__)


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        email: str,
        full_name: str,
        plain_password: str,
        roles: List[str],
        department: Optional[str] = None,
        hierarchy: int = 1
    ) -> User:
        """
        Create a new user.
        Raises DuplicateRecordError if email already exists.
        """
        try:
            hashed = PasswordHandler.hash_password(plain_password)

            user = User(
                email=email.lower().strip(),
                full_name=full_name.strip(),
                hashed_password=hashed,
                roles=roles,
                department=department,
                hierarchy=hierarchy
            )

            self.db.add(user)
            self.db.flush()  # Get ID without committing

            logger.info(
                "user_created",
                user_id=user.id,
                email=user.email,
                roles=roles
            )
            return user

        except IntegrityError:
            self.db.rollback()
            raise DuplicateRecordError("User", "email", email)

        except Exception as e:
            self.db.rollback()
            logger.error("user_create_failed", email=email, error=str(e))
            raise DatabaseError(f"Failed to create user: {str(e)}")

    def get_by_id(self, user_id: str) -> User:
        """Get user by ID. Raises RecordNotFoundError if not found."""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()

        if not user:
            raise RecordNotFoundError("User", user_id)
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        Returns None if not found — used for login checks.
        """
        return self.db.query(User).filter(
            User.email == email.lower().strip()
        ).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        department: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> List[User]:
        """Get paginated list of users with optional filters."""
        query = self.db.query(User)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if department:
            query = query.filter(User.department == department)

        return query.offset(skip).limit(limit).all()

    def update_roles(
        self,
        user_id: str,
        roles: List[str]
    ) -> User:
        """Update user roles. Admin operation."""
        user = self.get_by_id(user_id)
        old_roles = user.roles
        user.roles = roles
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(
            "user_roles_updated",
            user_id=user_id,
            old_roles=old_roles,
            new_roles=roles
        )
        return user

    def update_last_login(self, user_id: str) -> None:
        """Update last login timestamp."""
        self.db.query(User).filter(User.id == user_id).update(
            {"last_login_at": datetime.now(timezone.utc)}
        )

    def deactivate(self, user_id: str) -> User:
        """Deactivate a user account."""
        user = self.get_by_id(user_id)
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info("user_deactivated", user_id=user_id)
        return user

    def count(self, is_active: Optional[bool] = None) -> int:
        """Count users with optional active filter."""
        query = self.db.query(User)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        return query.count()

    def delete(self, user_id: str) -> None:
        """Permanently delete a user account."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise RecordNotFoundError("User", user_id)
            
        self.db.delete(user)
        self.db.flush()
        logger.info("user_deleted", user_id=user_id)