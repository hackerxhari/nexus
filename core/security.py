"""
Security utilities for Nexus.
JWT creation/validation, password hashing, role checking.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from jose import JWTError, ExpiredSignatureError, jwt

from core.config import get_settings
from core.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    AuthorizationError
)
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"


class PasswordHandler:
    """Handles password hashing and verification using bcrypt."""

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """
        Hash a plain text password.
        Never store plain text passwords.
        """
        if not plain_password or len(plain_password) < 8:
            raise ValueError("Password must be at least 8 characters")

        salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        Returns False instead of raising on mismatch — never leak timing info.
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except Exception:
            return False


class TokenHandler:
    """
    Handles JWT creation and validation.
    Two-token system: short-lived access + long-lived refresh.
    """

    @staticmethod
    def create_access_token(
        user_id: str,
        email: str,
        roles: List[str],
        department: Optional[str] = None,
        hierarchy: int = 1
    ) -> Dict[str, Any]:
        """
        Create a short-lived access token.
        Returns token string and expiry info.
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        jti = str(uuid.uuid4())  # Unique token ID for blacklisting

        payload = {
            "sub": user_id,
            "email": email,
            "roles": roles,
            "department": department,
            "hierarchy": hierarchy,
            "type": TokenType.ACCESS,
            "jti": jti,
            "iat": now,
            "exp": expire
        }

        token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        logger.debug(
            "access_token_created",
            user_id=user_id,
            jti=jti,
            expires_at=expire.isoformat()
        )

        return {
            "token": token,
            "jti": jti,
            "expires_at": expire.isoformat(),
            "expires_in_seconds": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    def create_refresh_token(user_id: str) -> Dict[str, Any]:
        """
        Create a long-lived refresh token.
        Contains minimal claims — only used to issue new access tokens.
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        jti = str(uuid.uuid4())

        payload = {
            "sub": user_id,
            "type": TokenType.REFRESH,
            "jti": jti,
            "iat": now,
            "exp": expire
        }

        token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

        return {
            "token": token,
            "jti": jti,
            "expires_at": expire.isoformat()
        }

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.
        Raises specific exceptions for each failure mode.
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload

        except ExpiredSignatureError:
            logger.warning("token_expired", token_prefix=token[:20])
            raise TokenExpiredError()

        except JWTError as e:
            logger.warning("token_invalid", error=str(e))
            raise TokenInvalidError()

        except Exception as e:
            logger.error("token_decode_unexpected_error", error=str(e))
            raise TokenInvalidError()

    @staticmethod
    def extract_jti(token: str) -> Optional[str]:
        """
        Extract JTI without full validation.
        Used during logout to blacklist tokens even if nearly expired.
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            return payload.get("jti")
        except Exception:
            return None


class RoleChecker:
    """
    Validates user roles against required permissions.
    Used as a FastAPI dependency.
    """

    # Role hierarchy — higher index = more access
    ROLE_HIERARCHY = {
        "employee": 1,
        "manager": 2,
        "ceo": 3,
        "admin": 4
    }

    @classmethod
    def has_role(cls, user_roles: List[str], required_role: str) -> bool:
        """Check if user has a specific role or higher."""
        user_max_level = max(
            (cls.ROLE_HIERARCHY.get(r, 0) for r in user_roles),
            default=0
        )
        required_level = cls.ROLE_HIERARCHY.get(required_role, 999)
        return user_max_level >= required_level

    @classmethod
    def has_any_role(
        cls,
        user_roles: List[str],
        required_roles: List[str]
    ) -> bool:
        """Check if user has any of the required roles."""
        return any(r in user_roles for r in required_roles)

    @classmethod
    def require_roles(
        cls,
        user_roles: List[str],
        required_roles: List[str]
    ) -> None:
        """
        Raise AuthorizationError if user lacks required roles.
        Use this in service layer for role enforcement.
        """
        if not cls.has_any_role(user_roles, required_roles):
            logger.warning(
                "authorization_failed",
                user_roles=user_roles,
                required_roles=required_roles
            )
            raise AuthorizationError(required_roles=required_roles)

    @classmethod
    def require_admin(cls, user_roles: List[str]) -> None:
        """Shortcut for admin-only operations."""
        cls.require_roles(user_roles, ["admin"])