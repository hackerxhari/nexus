"""
Authentication service for Nexus.
Handles login, logout, token refresh, and user registration.
Business logic only — no HTTP concerns here.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from cache.cache_service import CacheService
from core.exceptions import (
    AuthenticationError,
    AccountDisabledError,
    RecordNotFoundError,
    DuplicateRecordError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError
)
from core.logger import get_logger
from core.security import PasswordHandler, TokenHandler, RoleChecker
from db.models import RefreshToken
from db.repositories.user_repo import UserRepository

logger = get_logger(__name__)
cache = CacheService()


class AuthService:
    """
    Handles all authentication operations.
    Single responsibility — auth only, nothing else.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate user and issue token pair.
        Returns access token, refresh token, and user info.
        Raises AuthenticationError on any failure.
        Never reveal whether email or password was wrong — same error both ways.
        """
        # Get user — return same error whether email wrong or password wrong
        user = self.user_repo.get_by_email(email)
        if not user:
            logger.warning("login_failed_unknown_email", email=email)
            raise AuthenticationError("Invalid email or password")

        # Check account status before password verification
        if not user.is_active:
            logger.warning("login_failed_disabled_account", user_id=user.id)
            raise AccountDisabledError()

        # Verify password
        if not PasswordHandler.verify_password(password, user.hashed_password):
            logger.warning("login_failed_wrong_password", user_id=user.id)
            raise AuthenticationError("Invalid email or password")

        # Issue tokens
        access_token_data = TokenHandler.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=user.roles,
            department=user.department,
            hierarchy=user.hierarchy
        )

        refresh_token_data = TokenHandler.create_refresh_token(
            user_id=user.id
        )

        # Store refresh token in DB
        refresh_record = RefreshToken(
            jti=refresh_token_data["jti"],
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.fromisoformat(
                refresh_token_data["expires_at"]
            )
        )
        self.db.add(refresh_record)

        # Update last login
        self.user_repo.update_last_login(user.id)

        logger.info(
            "login_success",
            user_id=user.id,
            email=user.email,
            roles=user.roles,
            ip_address=ip_address
        )

        return {
            "access_token": access_token_data["token"],
            "refresh_token": refresh_token_data["token"],
            "token_type": "bearer",
            "expires_in": access_token_data["expires_in_seconds"],
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "roles": user.roles,
                "department": user.department,
                "is_active": user.is_active
            }
        }

    def logout(
        self,
        access_token_jti: str,
        refresh_token: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Logout user by blacklisting their tokens.
        Both access and refresh tokens are invalidated immediately.
        """
        # Blacklist access token
        access_expiry = 60 * 15  # 15 minutes — match ACCESS_TOKEN_EXPIRE_MINUTES
        cache.blacklist.blacklist(access_token_jti, access_expiry)

        # Revoke refresh token in DB
        if refresh_token:
            refresh_jti = TokenHandler.extract_jti(refresh_token)
            if refresh_jti:
                self._revoke_refresh_token(refresh_jti, "logout")
                # Also blacklist in Redis
                refresh_expiry = 60 * 60 * 24 * 7  # 7 days
                cache.blacklist.blacklist(refresh_jti, refresh_expiry)

        logger.info(
            "logout_success",
            user_id=user_id,
            access_jti=access_token_jti
        )

    def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Issue new access token using a valid refresh token.
        Validates refresh token is not expired or revoked.
        """
        # Decode refresh token
        try:
            payload = TokenHandler.decode_token(refresh_token)
        except TokenExpiredError:
            raise AuthenticationError("Refresh token has expired. Please login again.")
        except (TokenInvalidError, TokenRevokedError):
            raise AuthenticationError("Invalid refresh token.")

        # Verify it's actually a refresh token
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type.")

        jti = payload.get("jti")
        user_id = payload.get("sub")

        # Check Redis blacklist
        if cache.blacklist.is_blacklisted(jti):
            raise TokenRevokedError()

        # Check DB for revocation
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.jti == jti
        ).first()

        if not db_token or db_token.is_revoked:
            raise TokenRevokedError()

        # Get fresh user data — roles may have changed since token issued
        user = self.user_repo.get_by_id(user_id)
        if not user.is_active:
            raise AccountDisabledError()

        # Issue new access token with current roles
        access_token_data = TokenHandler.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=user.roles,
            department=user.department,
            hierarchy=user.hierarchy
        )

        logger.info(
            "token_refreshed",
            user_id=user_id,
            new_jti=access_token_data["jti"]
        )

        return {
            "access_token": access_token_data["token"],
            "token_type": "bearer",
            "expires_in": access_token_data["expires_in_seconds"]
        }

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an access token and return its payload.
        Used by auth middleware on every request.
        """
        payload = TokenHandler.decode_token(token)

        # Check token type
        if payload.get("type") != "access":
            raise TokenInvalidError()

        jti = payload.get("jti")

        # Check blacklist
        if cache.blacklist.is_blacklisted(jti):
            raise TokenRevokedError()

        return payload

    def _revoke_refresh_token(
        self,
        jti: str,
        reason: str = "manual"
    ) -> None:
        """Mark refresh token as revoked in DB."""
        token = self.db.query(RefreshToken).filter(
            RefreshToken.jti == jti
        ).first()

        if token:
            token.is_revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            token.revoked_reason = reason