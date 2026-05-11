"""
Custom Q&A repository — CRUD for admin-defined question-answer pairs.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from core.exceptions import RecordNotFoundError, DatabaseError
from core.logger import get_logger
from db.models import CustomQA

logger = get_logger(__name__)


class CustomQARepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        question_patterns: List[str],
        answer: str,
        category: Optional[str] = None,
        priority: int = 0,
        created_by: Optional[str] = None
    ) -> CustomQA:
        """Create a new custom Q&A entry."""
        try:
            entry = CustomQA(
                question_patterns=question_patterns,
                answer=answer,
                category=category,
                priority=priority,
                created_by=created_by
            )
            self.db.add(entry)
            self.db.flush()
            logger.info(
                "custom_qa_created",
                qa_id=entry.id,
                patterns_count=len(question_patterns),
                category=category
            )
            return entry
        except Exception as e:
            self.db.rollback()
            logger.error("custom_qa_create_failed", error=str(e))
            raise DatabaseError(f"Failed to create custom Q&A: {str(e)}")

    def get_by_id(self, qa_id: str) -> CustomQA:
        """Get a custom Q&A entry by ID. Raises if not found."""
        entry = self.db.query(CustomQA).filter(
            CustomQA.id == qa_id
        ).first()
        if not entry:
            raise RecordNotFoundError("CustomQA", qa_id)
        return entry

    def get_all_active(self) -> List[CustomQA]:
        """Get all active Q&A entries ordered by priority (highest first)."""
        return self.db.query(CustomQA).filter(
            CustomQA.is_active == True
        ).order_by(
            CustomQA.priority.desc(),
            CustomQA.created_at.desc()
        ).all()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        active_only: bool = False
    ) -> List[CustomQA]:
        """Get paginated Q&A entries with optional filters."""
        query = self.db.query(CustomQA)

        if active_only:
            query = query.filter(CustomQA.is_active == True)
        if category:
            query = query.filter(CustomQA.category == category)

        return query.order_by(
            CustomQA.priority.desc(),
            CustomQA.created_at.desc()
        ).offset(skip).limit(limit).all()

    def update(
        self,
        qa_id: str,
        question_patterns: Optional[List[str]] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> CustomQA:
        """Update an existing custom Q&A entry."""
        entry = self.get_by_id(qa_id)

        if question_patterns is not None:
            entry.question_patterns = question_patterns
        if answer is not None:
            entry.answer = answer
        if category is not None:
            entry.category = category
        if priority is not None:
            entry.priority = priority
        if is_active is not None:
            entry.is_active = is_active

        self.db.flush()
        logger.info("custom_qa_updated", qa_id=qa_id)
        return entry

    def delete(self, qa_id: str) -> None:
        """Delete a custom Q&A entry."""
        entry = self.get_by_id(qa_id)
        self.db.delete(entry)
        self.db.flush()
        logger.info("custom_qa_deleted", qa_id=qa_id)

    def count(self, active_only: bool = False) -> int:
        """Count Q&A entries."""
        query = self.db.query(CustomQA)
        if active_only:
            query = query.filter(CustomQA.is_active == True)
        return query.count()
