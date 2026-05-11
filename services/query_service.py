"""
Query service for Nexus.
Orchestrates RAG queries with rate limiting and audit logging.
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from cache.cache_service import CacheService
from core.exceptions import RateLimitExceededError
from core.logger import get_logger
from db.repositories.audit_repo import AuditRepository
from retrieval.query_engine import query_engine

logger = get_logger(__name__)
cache = CacheService()


class QueryService:
    """
    Handles employee queries against the knowledge base.
    Enforces rate limits and logs every query for audit.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    # services/query_service.py

    def ask(
        self,
        question: str,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        user_name: Optional[str] = None,
        department_filter: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        bypass_cache: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_department: Optional[str] = None,
        user_hierarchy: int = 1
    ) -> Dict[str, Any]:
        """
        Process a question from an employee.
        Checks rate limit, runs RAG pipeline, logs audit trail.
        """
        start_time = time.perf_counter()

        # ── Rate Limit Check ──────────────────────────────────
        rate_status = cache.rate_limit.check_and_increment(user_id)

        # ── Run RAG Query ─────────────────────────────────────
        try:
            result = query_engine.query(
                question=question,
                user_roles=user_roles,
                user_name=user_name,
                department_filter=department_filter,
                bypass_cache=bypass_cache,
                conversation_history=conversation_history,
                user_department=user_department,
                user_hierarchy=user_hierarchy
            )

            # ── Audit Log — Success ───────────────────────────
            self.audit_repo.log_query(
                user_id=user_id,
                user_email=user_email,
                user_roles=user_roles,
                question=question,
                answer=result.answer,
                sources=result.sources,
                chunks_retrieved=result.chunks_retrieved,
                cache_hit=result.cache_hit,
                response_time_ms=result.response_time_ms,
                embedding_time_ms=result.embedding_time_ms,
                retrieval_time_ms=result.retrieval_time_ms,
                llm_time_ms=result.llm_time_ms,
                request_id=request_id,
                ip_address=ip_address,
                status="success"
            )

            return {
                "answer": result.answer,
                "sources": result.sources,
                "citations": result.citations,
                "chunks_retrieved": result.chunks_retrieved,
                "cache_hit": result.cache_hit,
                "performance": {
                    "response_time_ms": round(result.response_time_ms, 2),
                    "embedding_time_ms": round(result.embedding_time_ms, 2),
                    "retrieval_time_ms": round(result.retrieval_time_ms, 2),
                    "llm_time_ms": round(result.llm_time_ms, 2)
                },
                "rate_limit": {
                    "remaining": rate_status["remaining"],
                    "limit": rate_status["limit"],
                    "reset_in_seconds": rate_status["reset_in_seconds"]
                }
            }

        except RateLimitExceededError:
            # Audit log rate limit violations
            self.audit_repo.log_query(
                user_id=user_id,
                user_email=user_email,
                user_roles=user_roles,
                question=question,
                request_id=request_id,
                ip_address=ip_address,
                status="rate_limited",
                error_code="RATE_LIMIT_EXCEEDED"
            )
            raise

        except Exception as e:
            # Audit log failures
            self.audit_repo.log_query(
                user_id=user_id,
                user_email=user_email,
                user_roles=user_roles,
                question=question,
                request_id=request_id,
                ip_address=ip_address,
                status="error",
                error_code=type(e).__name__
            )
            logger.error(
                "query_service_error",
                user_id=user_id,
                error=str(e)
            )
            raise

    def get_history(
        self,
        user_id: str,
        requester_id: str,
        requester_roles: List[str],
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get query history.
        Users see their own history.
        Admins can see any user's history.
        """
        from core.security import RoleChecker

        is_admin = RoleChecker.has_any_role(
            requester_roles,
            ["admin"]
        )

        # Non-admins can only see their own history
        if not is_admin and requester_id != user_id:
            from core.exceptions import AuthorizationError
            raise AuthorizationError()

        logs = self.audit_repo.get_user_history(
            user_id=user_id,
            skip=skip,
            limit=limit
        )

        return [
            {
                "id": log.id,
                "question": log.question,
                "answer": log.answer,
                "sources": log.sources,
                "cache_hit": log.cache_hit,
                "response_time_ms": log.response_time_ms,
                "status": log.status,
                "asked_at": log.created_at.isoformat()
            }
            for log in logs
        ]

    def get_stats(
        self,
        requester_roles: List[str]
    ) -> Dict[str, Any]:
        """Admin-only usage statistics."""
        from core.security import RoleChecker
        RoleChecker.require_admin(requester_roles)

        return {
            "total_queries_today": self.audit_repo.count_today(),
            "cache_hit_rate_percent": self.audit_repo.get_cache_hit_rate(),
            "vector_store": query_engine.query_engine if hasattr(
                query_engine, "query_engine"
            ) else {}
        }