"""
Admin routes for Project Nexus.
User management, audit logs, system stats.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import (
    get_request_id,
    CurrentUser,
    require_roles,
    get_current_user
)
from api.schemas.request import CreateUserRequest, UpdateUserRolesRequest
from api.schemas.response import APIResponse, UserResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from db.repositories.audit_repo import AuditRepository
from db.repositories.user_repo import UserRepository
from db.repositories.dept_repo import DepartmentRepository
from retrieval.vector_store import vector_store
from cache.cache_service import CacheService
from db.base import check_db_health
from cache.redis_client import redis_client

router = APIRouter(prefix="/admin", tags=["Admin"])
cache = CacheService()


@router.post("/users", response_model=APIResponse[UserResponse])
async def create_user(
    body: CreateUserRequest,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Create a new user account. Admin creates anywhere, Manager creates in their department."""
    try:
        is_admin = "admin" in current_user.roles
        is_ceo = "ceo" in current_user.roles
        is_manager = "manager" in current_user.roles
        
        allowed_roles_to_create = []
        if is_admin:
            allowed_roles_to_create = ["ceo", "manager", "employee"]
        elif is_ceo:
            allowed_roles_to_create = ["manager", "employee"]
        elif is_manager:
            allowed_roles_to_create = ["employee"]
        else:
            return APIResponse.fail("AUTHORIZATION_ERROR", "Not authorized to create users", request_id)
            
        for r in body.roles:
            if r not in allowed_roles_to_create:
                return APIResponse.fail("AUTHORIZATION_ERROR", f"Not authorized to create user with role: {r}", request_id)

        is_global = is_admin or is_ceo
        
        if not is_global:
            if not current_user.department:
                return APIResponse.fail("AUTHORIZATION_ERROR", "You are not assigned to a department", request_id)
            if body.department != current_user.department:
                return APIResponse.fail("AUTHORIZATION_ERROR", f"You can only create users in your department ({current_user.department})", request_id)

        from core.security import RoleChecker
        hierarchy = max((RoleChecker.ROLE_HIERARCHY.get(r, 1) for r in body.roles), default=1)

        user_repo = UserRepository(db)
        user = user_repo.create(
            email=body.email,
            full_name=body.full_name,
            plain_password=body.password,
            roles=body.roles,
            department=body.department,
            hierarchy=hierarchy
        )
        return APIResponse.ok({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "roles": user.roles,
            "department": user.department,
            "hierarchy": user.hierarchy,
            "is_active": user.is_active
        }, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.get("/users", response_model=APIResponse)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """List users. Admin sees all, Manager sees their department."""
    is_global_admin = "admin" in current_user.roles or "ceo" in current_user.roles
    is_manager = "manager" in current_user.roles
    
    if not is_global_admin and not is_manager:
        return APIResponse.fail("AUTHORIZATION_ERROR", "Not authorized to view users", request_id)

    user_repo = UserRepository(db)
    if is_global_admin:
        users = user_repo.get_all(skip=skip, limit=limit)
    else:
        if not current_user.department:
            users = []
        else:
            users = user_repo.get_all(skip=skip, limit=limit, department=current_user.department)
        
    return APIResponse.ok([{
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "roles": u.roles,
        "department": u.department,
        "hierarchy": u.hierarchy,
        "is_active": u.is_active,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None
    } for u in users], request_id)


def _check_admin_or_manager_access(current_user: CurrentUser, target_user_id: str, db: Session) -> None:
    is_global_admin = "admin" in current_user.roles or "ceo" in current_user.roles
    if is_global_admin:
        # Prevent non-admins from managing admins
        user_repo = UserRepository(db)
        target_user = user_repo.get_by_id(target_user_id)
        if "admin" in target_user.roles and "admin" not in current_user.roles:
            raise ValueError("Cannot manage an Admin user")
        if target_user.hierarchy >= current_user.hierarchy and target_user.id != current_user.id:
            raise ValueError("Cannot manage user with equal or higher hierarchy")
        return
        
    is_manager = "manager" in current_user.roles
    if not is_manager:
        raise ValueError("Not authorized to manage this user")
        
    user_repo = UserRepository(db)
    target_user = user_repo.get_by_id(target_user_id)
    
    if target_user.department != current_user.department:
        raise ValueError(f"User is not in your department ({current_user.department})")
        
    if target_user.hierarchy >= current_user.hierarchy:
        raise ValueError("Cannot manage user with equal or higher hierarchy")


@router.patch("/users/{user_id}/roles", response_model=APIResponse)
async def update_user_roles(
    user_id: str,
    body: UpdateUserRolesRequest,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Update user roles. Admin or Manager."""
    try:
        _check_admin_or_manager_access(current_user, user_id, db)
        
        user_repo = UserRepository(db)
        user = user_repo.update_roles(user_id, body.roles)

        # Force re-login by revoking all their tokens
        cache.blacklist.revoke_all_user_tokens(user_id)

        return APIResponse.ok({
            "id": user.id,
            "email": user.email,
            "roles": user.roles
        }, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)
    except ValueError as e:
        return APIResponse.fail("AUTHORIZATION_ERROR", str(e), request_id)


@router.patch("/users/{user_id}/deactivate", response_model=APIResponse)
async def deactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Deactivate a user account. Admin or Manager."""
    try:
        _check_admin_or_manager_access(current_user, user_id, db)
        
        user_repo = UserRepository(db)
        user_repo.deactivate(user_id)
        cache.blacklist.revoke_all_user_tokens(user_id)
        return APIResponse.ok({"message": "User deactivated"}, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)
    except ValueError as e:
        return APIResponse.fail("AUTHORIZATION_ERROR", str(e), request_id)


@router.delete("/users/{user_id}", response_model=APIResponse)
async def delete_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Delete a user account permanently. Admin or Manager."""
    try:
        _check_admin_or_manager_access(current_user, user_id, db)
        
        user_repo = UserRepository(db)
        user_repo.delete(user_id)
        cache.blacklist.revoke_all_user_tokens(user_id)
        return APIResponse.ok({"message": "User deleted successfully"}, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)
    except ValueError as e:
        return APIResponse.fail("AUTHORIZATION_ERROR", str(e), request_id)


@router.get("/audit-logs", response_model=APIResponse)
async def get_audit_logs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Get audit logs. CEO/Admin see all, Manager sees dept, Employee sees self."""
    audit_repo = AuditRepository(db)
    
    is_global = any(r in current_user.roles for r in ["admin", "ceo"])
    is_manager = "manager" in current_user.roles
    
    if is_global:
        logs = audit_repo.get_recent(skip=skip, limit=limit, status=status)
    else:
        if is_manager and current_user.department:
            logs = audit_repo.get_recent_by_department(current_user.department, skip=skip, limit=limit, status=status)
        else:
            # Regular employee sees their own history
            logs = audit_repo.get_user_history(current_user.id, skip=skip, limit=limit)
            if status:
                logs = [l for l in logs if l.status == status]

    return APIResponse.ok([{
        "id": log.id,
        "user_email": log.user_email,
        "user_roles": log.user_roles,
        "question": log.question,
        "sources": log.sources,
        "cache_hit": log.cache_hit,
        "response_time_ms": log.response_time_ms,
        "status": log.status,
        "asked_at": log.created_at.isoformat()
    } for log in logs], request_id)


@router.get("/health", response_model=APIResponse)
async def health_check(
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id)
):
    """Detailed system health check. Admin only."""
    return APIResponse.ok({
        "database": check_db_health(),
        "redis": redis_client.is_healthy(),
        "qdrant": vector_store.is_healthy(),
        "vector_store_stats": vector_store.get_collection_stats()
    }, request_id)