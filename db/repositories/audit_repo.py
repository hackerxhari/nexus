"""
Audit log repository.
Write-heavy, read-rarely. Every query gets logged here.
"""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from core.exceptions import DatabaseError
from core.logger import get_logger
from db.models import AuditLog

logger = get_logger(__name__)


class AuditRepository:

    def __init__(self, db: Session):
        self.db = db

    def log_query(
        self,
        user_id: Optional[str],
        user_email: str,
        user_roles: List[str],
        question: str,
        answer: Optional[str] = None,
        sources: Optional[List[str]] = None,
        chunks_retrieved: Optional[int] = None,
        cache_hit: bool = False,
        response_time_ms: Optional[float] = None,
        embedding_time_ms: Optional[float] = None,
        retrieval_time_ms: Optional[float] = None,
        llm_time_ms: Optional[float] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        status: str = "success",
        error_code: Optional[str] = None
    ) -> AuditLog:
        """
        Log a query attempt.
        Never raises — audit logging failure must not block the user response.
        """
        try:
            question_hash = hashlib.sha256(
                question.strip().lower().encode()
            ).hexdigest()

            log = AuditLog(
                user_id=user_id,
                user_email=user_email,
                user_roles=user_roles,
                question=question,
                question_hash=question_hash,
                answer=answer,
                sources=sources or [],
                chunks_retrieved=chunks_retrieved,
                cache_hit=cache_hit,
                response_time_ms=response_time_ms,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=llm_time_ms,
                request_id=request_id,
                ip_address=ip_address,
                status=status,
                error_code=error_code
            )

            self.db.add(log)
            self.db.flush()
            return log

        except Exception as e:
            # Never let audit logging crash the app
            logger.error("audit_log_failed", error=str(e))
            return None

    def get_user_history(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[AuditLog]:
        """Get query history for a specific user."""
        return self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            AuditLog.created_at.desc()
        ).offset(skip).limit(limit).all()

    def get_recent(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[AuditLog]:
        """Get recent audit logs. Admin only."""
        query = self.db.query(AuditLog)
        if status:
            query = query.filter(AuditLog.status == status)
        return query.order_by(
            AuditLog.created_at.desc()
        ).offset(skip).limit(limit).all()

    def get_recent_by_department(
        self,
        department: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[AuditLog]:
        from db.models import User
        query = self.db.query(AuditLog).join(User, AuditLog.user_id == User.id).filter(User.department == department)
        if status:
            query = query.filter(AuditLog.status == status)
        return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    def count_today(self, user_id: Optional[str] = None) -> int:
        """Count queries made today."""
        today = datetime.now(timezone.utc).date()
        query = self.db.query(AuditLog).filter(
            AuditLog.created_at >= today
        )
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        return query.count()

    def get_cache_hit_rate(self) -> float:
        """Calculate overall cache hit rate. Returns 0.0 on error."""
        try:
            total = self.db.query(AuditLog).count()
            if total == 0:
                return 0.0
            hits = self.db.query(AuditLog).filter(
                AuditLog.cache_hit == True
            ).count()
            return round((hits / total) * 100, 2)
        except Exception:
            return 0.0