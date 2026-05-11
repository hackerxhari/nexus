"""
Authentication routes for Project Nexus.
Login, logout, token refresh.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.dependencies import (
    get_current_user,
    get_request_id,
    get_client_ip,
    CurrentUser
)
from api.schemas.request import LoginRequest, RefreshTokenRequest
from api.schemas.response import APIResponse, LoginResponse, TokenResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=APIResponse[LoginResponse])
async def login(
    body: LoginRequest,
    request: Request,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Authenticate and receive token pair."""
    try:
        auth_service = AuthService(db)
        result = auth_service.login(
            email=body.email,
            password=body.password,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(
            e.error_code.value,
            e.message,
            request_id
        )


@router.post("/logout", response_model=APIResponse)
async def logout(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Logout and invalidate tokens."""
    try:
        auth_service = AuthService(db)
        refresh_token = request.headers.get("X-Refresh-Token")
        auth_service.logout(
            access_token_jti=current_user.jti,
            refresh_token=refresh_token,
            user_id=current_user.id
        )
        return APIResponse.ok(
            {"message": "Logged out successfully"},
            request_id
        )

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.post("/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(
    body: RefreshTokenRequest,
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Get new access token using refresh token."""
    try:
        auth_service = AuthService(db)
        result = auth_service.refresh_access_token(body.refresh_token)
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.get("/me", response_model=APIResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id)
):
    """Get current user info."""
    return APIResponse.ok({
        "id": current_user.id,
        "email": current_user.email,
        "roles": current_user.roles,
        "department": current_user.department
    }, request_id)