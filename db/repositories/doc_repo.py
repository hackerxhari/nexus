"""
Document repository — metadata for all ingested documents.
Actual vectors live in Qdrant. This tracks everything else.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.exceptions import RecordNotFoundError, DatabaseError
from core.logger import get_logger
from db.models import Document

logger = get_logger(__name__)


class DocumentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        allowed_roles: List[str],
        uploaded_by: str,
        departments: List[str] = None,
        hierarchy: int = 1
    ) -> Document:
        """Register a new document. Status starts as 'pending'."""
        try:
            doc = Document(
                filename=filename,
                original_filename=original_filename,
                file_type=file_type,
                file_size_bytes=file_size_bytes,
                allowed_roles=allowed_roles,
                uploaded_by=uploaded_by,
                departments=departments or [],
                hierarchy=hierarchy,
                status="pending"
            )

            self.db.add(doc)
            self.db.flush()

            logger.info(
                "document_registered",
                doc_id=doc.id,
                filename=filename,
                allowed_roles=allowed_roles
            )
            return doc

        except Exception as e:
            self.db.rollback()
            logger.error(
                "document_create_failed",
                filename=filename,
                error=str(e)
            )
            raise DatabaseError(f"Failed to register document: {str(e)}")

    def get_by_id(self, doc_id: str) -> Document:
        """Get document by ID. Raises if not found."""
        doc = self.db.query(Document).filter(
            Document.id == doc_id
        ).first()
        if not doc:
            raise RecordNotFoundError("Document", doc_id)
        return doc

    def get_by_filename(self, filename: str) -> Document:
        """Get document by stored filename. Raises if not found."""
        doc = self.db.query(Document).filter(
            Document.filename == filename
        ).first()
        if not doc:
            raise RecordNotFoundError("Document", filename)
        return doc

    def get_by_original_filename(self, original_filename: str) -> Document:
        """Get document by original filename. Raises if not found."""
        doc = self.db.query(Document).filter(
            Document.original_filename == original_filename
        ).first()
        if not doc:
            raise RecordNotFoundError("Document", original_filename)
        return doc

    def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        department: Optional[str] = None,
        status: Optional[str] = None,
        uploaded_by: Optional[str] = None
    ) -> List[Document]:
        """Get paginated documents with optional filters."""
        query = self.db.query(Document)

        if department:
            query = query.filter(Document.departments.like(f'%"{department}"%'))
        if status:
            query = query.filter(Document.status == status)
        if uploaded_by:
            query = query.filter(Document.uploaded_by == uploaded_by)

        return query.order_by(
            Document.created_at.desc()
        ).offset(skip).limit(limit).all()

    def get_all_unbounded(
        self,
        department: Optional[str] = None,
        status: Optional[str] = None,
        uploaded_by: Optional[str] = None
    ) -> List[Document]:
        """Get all documents without pagination."""
        query = self.db.query(Document)

        if department:
            query = query.filter(Document.departments.like(f'%"{department}"%'))
        if status:
            query = query.filter(Document.status == status)
        if uploaded_by:
            query = query.filter(Document.uploaded_by == uploaded_by)

        return query.order_by(Document.created_at.desc()).all()

    def mark_processing(self, doc_id: str) -> Document:
        """Mark document as currently being processed."""
        doc = self.get_by_id(doc_id)
        doc.status = "processing"
        doc.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return doc

    def mark_completed(
        self,
        doc_id: str,
        total_chunks: int,
        ingestion_time_seconds: float
    ) -> Document:
        """Mark document ingestion as complete with stats."""
        doc = self.get_by_id(doc_id)
        doc.status = "completed"
        doc.total_chunks = total_chunks
        doc.ingestion_time_seconds = ingestion_time_seconds
        doc.completed_at = datetime.now(timezone.utc)
        doc.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(
            "document_ingestion_completed",
            doc_id=doc_id,
            total_chunks=total_chunks,
            ingestion_time_seconds=ingestion_time_seconds
        )
        return doc

    def mark_failed(self, doc_id: str, error_message: str) -> Document:
        """Mark document ingestion as failed with error details."""
        doc = self.get_by_id(doc_id)
        doc.status = "failed"
        doc.error_message = error_message
        doc.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.error(
            "document_ingestion_failed",
            doc_id=doc_id,
            error=error_message
        )
        return doc

    def delete(self, doc_id: str) -> None:
        """Delete document metadata. Caller must also delete from Qdrant."""
        doc = self.get_by_id(doc_id)
        self.db.delete(doc)
        self.db.flush()

        logger.info("document_deleted", doc_id=doc_id)

    def delete_all(self) -> int:
        """Delete all document metadata rows. Returns count deleted."""
        count = self.db.query(Document).delete(synchronize_session=False)
        self.db.flush()
        logger.info("documents_deleted_all", count=count)
        return count

    def count(self, status: Optional[str] = None) -> int:
        """Count documents with optional status filter."""
        query = self.db.query(Document)
        if status:
            query = query.filter(Document.status == status)
        return query.count()