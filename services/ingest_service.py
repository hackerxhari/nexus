"""
Ingestion service for Nexus.
Handles document upload validation, ingestion orchestration,
and document management operations.
"""

import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from cache.cache_service import CacheService
from core.config import get_settings
from core.exceptions import (
    AuthorizationError,
    FileTooLargeError,
    RecordNotFoundError,
    UnsupportedFileTypeError
)
from core.logger import get_logger
from core.security import RoleChecker
from db.repositories.doc_repo import DocumentRepository
from ingestion.pipeline import pipeline
from services.topic_service import TopicService

logger = get_logger(__name__)
settings = get_settings()
cache = CacheService()


class IngestService:
    """
    Handles document ingestion business logic.
    Validates permissions, manages files, orchestrates pipeline.
    """

    def __init__(self, db: Session):
        self.db = db
        self.doc_repo = DocumentRepository(db)

    def upload_document(
        self,
        file_content: bytes,
        filename: str,
        allowed_roles: List[str],
        uploaded_by: str,
        uploader_roles: List[str],
        departments: List[str] = None,
        hierarchy: int = 1,
        document_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate, save, and ingest an uploaded document.
        Only admins can upload documents.
        """
        # No strict role check here; allowed users are determined by global route protections.

        # Validate filename
        if not filename or "." not in filename:
            raise UnsupportedFileTypeError(
                filename, "unknown",
                settings.allowed_extensions
            )

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in settings.allowed_extensions:
            raise UnsupportedFileTypeError(
                filename, ext,
                settings.allowed_extensions
            )

        # Validate file size
        file_size = len(file_content)
        if file_size > settings.max_file_size_bytes:
            size_mb = file_size / (1024 * 1024)
            raise FileTooLargeError(
                filename,
                size_mb,
                settings.MAX_FILE_SIZE_MB
            )

        # Validate roles being assigned are legitimate
        valid_roles = list(RoleChecker.ROLE_HIERARCHY.keys())
        invalid_roles = [r for r in allowed_roles if r not in valid_roles]
        if invalid_roles:
            from core.exceptions import ValidationError
            raise ValidationError(
                f"Invalid roles: {invalid_roles}",
                fields={"allowed_roles": f"Must be one of {valid_roles}"}
            )

        # Save file with unique name to prevent collisions
        safe_filename = f"{uuid.uuid4()}_{self._sanitize_filename(filename)}"
        save_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        with open(save_path, "wb") as f:
            f.write(file_content)

        logger.info(
            "document_saved",
            original_filename=filename,
            saved_as=safe_filename,
            size_bytes=file_size,
            allowed_roles=allowed_roles
        )

        # Run ingestion pipeline
        try:
            result = pipeline.ingest(
                filepath=save_path,
                allowed_roles=allowed_roles,
                uploaded_by=uploaded_by,
                departments=departments,
                hierarchy=hierarchy,
                original_filename=document_name or filename
            )
            return result

        except Exception:
            # Clean up saved file on ingestion failure
            if os.path.exists(save_path):
                os.remove(save_path)
            raise

    def get_documents(
        self,
        requester_roles: List[str],
        skip: int = 0,
        limit: int = 50,
        department: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of documents.
        Admins see all. Others see only docs matching their roles.
        """
        is_admin = RoleChecker.has_any_role(
            requester_roles,
            ["admin", "superadmin"]
        )

        docs = self.doc_repo.get_all(
            skip=skip,
            limit=limit,
            department=department,
            status=status
        )

        result = []
        for doc in docs:
            # Non-admins only see docs accessible to their roles
            if not is_admin:
                doc_roles = doc.allowed_roles or []
                if not any(r in doc_roles for r in requester_roles):
                    continue

            result.append({
                "id": doc.id,
                "filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size_bytes": doc.file_size_bytes,
                "departments": getattr(doc, 'departments', []) or [],
                "hierarchy": getattr(doc, 'hierarchy', 1) or 1,
                "allowed_roles": doc.allowed_roles or [],
                "status": doc.status,
                "total_chunks": getattr(doc, 'total_chunks', 0) or 0,
                "uploaded_at": doc.created_at.isoformat(),
                "ingestion_time_seconds": getattr(doc, 'ingestion_time_seconds', None)
            })

        return result

    def delete_document(
        self,
        doc_id: str,
        requester_roles: List[str]
    ) -> None:
        """
        Delete a document from DB and Qdrant.
        Admin only operation.
        """
        RoleChecker.require_admin(requester_roles)

        try:
            doc = self.doc_repo.get_by_id(doc_id)
        except RecordNotFoundError:
            # Fallback: allow deletion by filename if UI sends filename
            try:
                doc = self.doc_repo.get_by_filename(doc_id)
            except RecordNotFoundError:
                doc = self.doc_repo.get_by_original_filename(doc_id)

        # Delete from Qdrant
        pipeline.delete_document(doc.id, doc.filename)

        # Invalidate related cache entries
        cache.queries.invalidate_by_source(doc.original_filename)

        # Delete from DB
        self.doc_repo.delete(doc.id)

        topic_service = TopicService(self.db)
        topic_service.delete_by_doc_id(doc.id)

        logger.info(
            "document_deleted",
            doc_id=doc.id,
            filename=doc.filename
        )

    def clear_all_documents(
        self,
        requester_roles: List[str],
        delete_files: bool = False
    ) -> Dict[str, Any]:
        """
        Delete all documents and vectors. Admin-only operation.
        Optionally delete uploaded files from disk.
        """
        RoleChecker.require_admin(requester_roles)

        # Clear Qdrant collection
        pipeline.clear_all_documents()

        # Clear query cache
        cache.queries.clear_all()

        # Delete all document metadata
        deleted_docs = self.doc_repo.delete_all()
        remaining_docs = self.doc_repo.count()

        topic_service = TopicService(self.db)
        topic_service.clear_all()

        deleted_files = 0
        if delete_files:
            upload_dir = settings.UPLOAD_DIR
            if os.path.exists(upload_dir):
                for name in os.listdir(upload_dir):
                    path = os.path.join(upload_dir, name)
                    if os.path.isfile(path):
                        os.remove(path)
                        deleted_files += 1

        logger.info(
            "documents_cleared_all",
            deleted_docs=deleted_docs,
            deleted_files=deleted_files
        )

        return {
            "deleted_documents": deleted_docs,
            "remaining_documents": remaining_docs,
            "deleted_files": deleted_files,
            "vector_store_cleared": True
        }

    def prune_missing_documents(
        self,
        requester_roles: List[str]
    ) -> Dict[str, Any]:
        """
        Remove documents whose uploaded files no longer exist on disk.
        Admin-only operation.
        """
        RoleChecker.require_admin(requester_roles)

        docs = self.doc_repo.get_all_unbounded()
        topic_service = TopicService(self.db)
        pruned = 0
        failed = 0

        for doc in docs:
            path = os.path.join(settings.UPLOAD_DIR, doc.filename)
            if os.path.exists(path):
                continue

            try:
                pipeline.delete_document(doc.id, doc.filename)
                cache.queries.invalidate_by_source(doc.original_filename)
                self.doc_repo.delete(doc.id)
                topic_service.delete_by_doc_id(doc.id)
                pruned += 1
            except Exception as e:
                failed += 1
                logger.warning(
                    "prune_missing_failed",
                    doc_id=doc.id,
                    filename=doc.filename,
                    error=str(e)
                )

        remaining_docs = self.doc_repo.count()

        logger.info(
            "prune_missing_completed",
            pruned_documents=pruned,
            failed_documents=failed
        )

        return {
            "pruned_documents": pruned,
            "failed_documents": failed,
            "remaining_documents": remaining_docs
        }

    def _sanitize_filename(self, filename: str) -> str:
        """Remove dangerous characters from filename."""
        import re
        filename = os.path.basename(filename)
        filename = re.sub(r"[^\w\s\-\.]", "", filename)
        filename = re.sub(r"\s+", "_", filename)
        return filename[:100]  # Max 100 chars