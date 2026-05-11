"""
Document ingestion routes for Project Nexus.
Admin-only endpoints for uploading documents.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional

from api.dependencies import (
    get_current_user,
    get_request_id,
    CurrentUser,
    require_roles
)
from api.schemas.response import APIResponse, DocumentResponse, IngestionResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from services.ingest_service import IngestService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=APIResponse[IngestionResponse])
async def upload_document(
    file: UploadFile = File(...),
    allowed_roles: str = Form(...),
    departments: Optional[str] = Form(None),
    document_name: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """
    Upload and ingest a document.
    Admin only. Specify which roles can access this document.
    allowed_roles: comma-separated string e.g. "admin,hr,manager"
    """
    try:
        roles_list = [r.strip() for r in allowed_roles.split(",")]
        file_content = await file.read()

        dept_list = [d.strip() for d in departments.split(",") if d.strip()] if departments else []

        from core.security import RoleChecker
        hierarchy = max((RoleChecker.ROLE_HIERARCHY.get(r, 1) for r in roles_list), default=1)

        ingest_service = IngestService(db)
        result = ingest_service.upload_document(
            file_content=file_content,
            filename=file.filename,
            allowed_roles=roles_list,
            uploaded_by=current_user.id,
            uploader_roles=current_user.roles,
            departments=dept_list,
            hierarchy=hierarchy,
            document_name=document_name
        )
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(
            e.error_code.value,
            e.message,
            request_id,
            e.details
        )


@router.get("/", response_model=APIResponse[List[DocumentResponse]])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    department: Optional[str] = None,
    status: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """List documents accessible to the current user."""
    try:
        ingest_service = IngestService(db)
        docs = ingest_service.get_documents(
            requester_roles=current_user.roles,
            skip=skip,
            limit=limit,
            department=department,
            status=status
        )
        return APIResponse.ok(docs, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.delete("/clear-all", response_model=APIResponse)
async def clear_documents(
    delete_files: bool = False,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """
    Clear all documents and vectors. Admin only.
    Optionally delete uploaded files from disk.
    """
    try:
        ingest_service = IngestService(db)
        result = ingest_service.clear_all_documents(
            requester_roles=current_user.roles,
            delete_files=delete_files
        )
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(
    doc_id: str,
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Delete a document. Admin only."""
    try:
        ingest_service = IngestService(db)
        ingest_service.delete_document(doc_id, current_user.roles)
        return APIResponse.ok(
            {"message": "Document deleted successfully"},
            request_id
        )

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)


@router.post("/prune-missing", response_model=APIResponse)
async def prune_missing_documents(
    current_user: CurrentUser = Depends(require_roles("admin")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """
    Remove documents whose uploaded files no longer exist on disk.
    Admin only.
    """
    try:
        ingest_service = IngestService(db)
        result = ingest_service.prune_missing_documents(
            requester_roles=current_user.roles
        )
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)