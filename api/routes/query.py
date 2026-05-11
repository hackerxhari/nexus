"""
Query routes for Project Nexus.
Employee-facing endpoints for asking questions.
"""

from fastapi import APIRouter, Depends, Request, Query as QueryParam
from sqlalchemy.orm import Session

from api.dependencies import (
    get_current_user,
    get_request_id,
    get_client_ip,
    CurrentUser
)
from api.schemas.request import QueryRequest
from api.schemas.response import APIResponse, QueryResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from db.repositories.doc_repo import DocumentRepository
from services.query_service import QueryService

router = APIRouter(prefix="/query", tags=["Query"])

# api/routes/query.py

from core.security import RoleChecker
from retrieval.query_engine import query_engine
from retrieval.vector_store import vector_store

@router.post("/debug/retrieve", response_model=APIResponse)
async def debug_retrieve(
    body: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id)
):
    RoleChecker.require_admin(current_user.roles)

    results = query_engine.retrieve_chunks(
        question=body.question,
        user_roles=current_user.roles,
        department_filter=body.department_filter
    )

    payload = {
        "question": body.question,
        "count": len(results),
        "chunks": [
            {
                "source": r.source_file,
                "score": r.score,
                "preview": " ".join(r.text.split())[:240]
            }
            for r in results
        ]
    }
    return APIResponse.ok(payload, request_id)


@router.get("/debug/contains", response_model=APIResponse)
async def debug_contains(
    q: str = QueryParam(..., min_length=2),
    doc_id: str | None = QueryParam(default=None),
    filename: str | None = QueryParam(default=None),
    limit: int = QueryParam(default=200, ge=1, le=2000),
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Admin debug: check whether a phrase exists in stored chunks."""
    RoleChecker.require_admin(current_user.roles)

    doc_repo = DocumentRepository(db)
    doc = None
    if doc_id:
        try:
            doc = doc_repo.get_by_id(doc_id)
        except Exception:
            doc = None
    if doc is None and filename:
        try:
            doc = doc_repo.get_by_filename(filename)
        except Exception:
            try:
                doc = doc_repo.get_by_original_filename(filename)
            except Exception:
                doc = None

    if doc is None:
        return APIResponse.fail(
            "RECORD_NOT_FOUND",
            "Document not found",
            request_id,
            {"doc_id": doc_id, "filename": filename}
        )

    query_text = q.strip().lower()
    chunks = vector_store.get_chunks_by_doc_id(doc.id, limit=limit)

    matches = []
    for c in chunks:
        if query_text in (c.text or "").lower():
            matches.append({
                "chunk_index": c.chunk_index,
                "source": c.source_file,
                "preview": " ".join(c.text.split())[:240]
            })

    payload = {
        "doc_id": doc.id,
        "filename": doc.original_filename,
        "searched": q,
        "total_chunks": len(chunks),
        "match_count": len(matches),
        "matches": matches[:25]
    }

    return APIResponse.ok(payload, request_id)

@router.post("/ask", response_model=APIResponse[QueryResponse])
async def ask(
    body: QueryRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """
    Ask a question against the knowledge base.
    Results are filtered by your role automatically.
    """
    try:
        query_service = QueryService(db)
        # api/routes/query.py

        result = query_service.ask(
            question=body.question,
            user_id=current_user.id,
            user_email=current_user.email,
            user_roles=current_user.roles,
            user_name=current_user.full_name,
            department_filter=body.department_filter,
            request_id=request_id,
            ip_address=get_client_ip(request),
            bypass_cache=body.bypass_cache,
            conversation_history=[
                {"role": t.role, "content": t.content}
                for t in body.conversation_history
            ] if body.conversation_history else None,
            user_department=current_user.department,
            user_hierarchy=current_user.hierarchy
        )
        return APIResponse.ok(result, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(
            e.error_code.value,
            e.message,
            request_id,
            e.details
        )


@router.get("/history", response_model=APIResponse)
async def get_history(
    skip: int = 0,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    """Get your query history."""
    try:
        query_service = QueryService(db)
        history = query_service.get_history(
            user_id=current_user.id,
            requester_id=current_user.id,
            requester_roles=current_user.roles,
            skip=skip,
            limit=limit
        )
        return APIResponse.ok(history, request_id)

    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)