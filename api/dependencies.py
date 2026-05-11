"""
Shared FastAPI dependencies for Nexus.
Injected into routes via Depends().
"""

import uuid
from typing import Dict, Any, List

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from cache.cache_service import CacheService
from core.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    GreenBaseException
)
from core.logger import get_logger, set_request_context
from db.base import get_db
from services.auth_service import AuthService

logger = get_logger(__name__)
cache = CacheService()
bearer_scheme = HTTPBearer()


class CurrentUser:
    """Represents the authenticated user for the current request."""

    def __init__(self, payload: Dict[str, Any]):
        self.id: str = payload["sub"]
        self.email: str = payload["email"]
        self.roles: List[str] = payload.get("roles", [])
        self.department: str = payload.get("department")
        self.hierarchy: int = payload.get("hierarchy", 1)
        self.jti: str = payload.get("jti")

    @property
    def full_name(self) -> str:
        return self.email.split("@")[0].replace(".", " ").title()


def get_request_id(request: Request) -> str:
    """Extract or generate request ID for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_context(request_id=request_id)
    return request_id


def get_client_ip(request: Request) -> str:
    """Extract real client IP, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> CurrentUser:
    """
    Validate JWT and return current user.
    Injected into every protected route.
    """
    token = credentials.credentials

    try:
        auth_service = AuthService(db)
        payload = auth_service.validate_token(token)
        user = CurrentUser(payload)
        set_request_context(user_id=user.id)
        return user

    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Token has expired"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    except (TokenInvalidError, TokenRevokedError) as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_INVALID",
                "message": "Invalid or revoked token"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error("auth_dependency_error", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


def require_roles(*required_roles: str):
    """
    Role enforcement dependency factory.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles("admin"))])
    """
    async def _check(user: CurrentUser = Depends(get_current_user)):
        from core.security import RoleChecker
        if not RoleChecker.has_any_role(user.roles, list(required_roles)):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": "You don't have permission to access this resource"
                }
            )
        return user
    return _check