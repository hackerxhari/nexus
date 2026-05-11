"""
Custom Q&A admin routes for Project Nexus.
Admin-only CRUD for custom question-answer pairs.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies import (
    get_request_id,
    CurrentUser,
    require_roles
)
from api.schemas.response import APIResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from db.repositories.custom_qa_repo import CustomQARepository

router = APIRouter(prefix="/custom-qa", tags=["Custom Q&A"])


# ── Request Schemas ───────────────────────────────────────────

class CreateCustomQARequest(BaseModel):
    question_patterns: List[str] = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=5000)
    category: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=100)


class UpdateCustomQARequest(BaseModel):
    question_patterns: Optional[List[str]] = None
    answer: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None


# ── Routes ────────────────────────────────────────────────────

@router.post("/", response_model=APIResponse)
async def create_custom_qa(
    body: CreateCustomQARequest,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Create a new custom Q&A entry. Admin only."""
    try:
        repo = CustomQARepository(db)
        entry = repo.create(
            question_patterns=body.question_patterns,
            answer=body.answer,
            category=body.category,
            priority=body.priority,
            created_by=current_user.id
        )
        return APIResponse.ok({
            "id": entry.id,
            "question_patterns": entry.question_patterns,
            "answer": entry.answer,
            "category": entry.category,
            "priority": entry.priority,
            "is_active": entry.is_active,
            "created_at": entry.created_at.isoformat() if entry.created_at else None
        }, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.get("/", response_model=APIResponse)
async def list_custom_qa(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    active_only: bool = False,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """List all custom Q&A entries. Admin only."""
    repo = CustomQARepository(db)
    entries = repo.get_all(
        skip=skip,
        limit=limit,
        category=category,
        active_only=active_only
    )
    return APIResponse.ok([{
        "id": e.id,
        "question_patterns": e.question_patterns,
        "answer": e.answer,
        "category": e.category,
        "priority": e.priority,
        "is_active": e.is_active,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None
    } for e in entries], request_id)


@router.put("/{qa_id}", response_model=APIResponse)
async def update_custom_qa(
    qa_id: str,
    body: UpdateCustomQARequest,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Update a custom Q&A entry. Admin only."""
    try:
        repo = CustomQARepository(db)
        entry = repo.update(
            qa_id=qa_id,
            question_patterns=body.question_patterns,
            answer=body.answer,
            category=body.category,
            priority=body.priority,
            is_active=body.is_active
        )
        return APIResponse.ok({
            "id": entry.id,
            "question_patterns": entry.question_patterns,
            "answer": entry.answer,
            "category": entry.category,
            "priority": entry.priority,
            "is_active": entry.is_active,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
        }, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.delete("/{qa_id}", response_model=APIResponse)
async def delete_custom_qa(
    qa_id: str,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Delete a custom Q&A entry. Admin only."""
    try:
        repo = CustomQARepository(db)
        repo.delete(qa_id)
        return APIResponse.ok(
            {"message": "Custom Q&A entry deleted"},
            request_id
        )

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.patch("/{qa_id}/toggle", response_model=APIResponse)
async def toggle_custom_qa(
    qa_id: str,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Toggle active/inactive status. Admin only."""
    try:
        repo = CustomQARepository(db)
        entry = repo.get_by_id(qa_id)
        entry = repo.update(qa_id=qa_id, is_active=not entry.is_active)
        return APIResponse.ok({
            "id": entry.id,
            "is_active": entry.is_active
        }, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)
