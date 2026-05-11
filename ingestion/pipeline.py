"""
Ingestion pipeline orchestrator for Nexus.
Coordinates: extraction → chunking → embedding → storage.
This is the single entry point for all document ingestion.
"""

import os
import re
import time
import uuid
from typing import List, Optional

# Matches the page markers inserted by the PDF extractor.
# Kept in sync with ingestion.extractors.pdf.PAGE_MARKER_FORMAT.
_PAGE_MARKER_RE = re.compile(r"<<NEXUS_PAGE:(\d+)>>")

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams
)

from core.config import get_settings
from core.exceptions import (
    EmptyDocumentError,
    ExtractionFailedError,
    FileTooLargeError,
    IngestionError,
    UnsupportedFileTypeError
)
from core.logger import get_logger, TimedOperation
from db.base import get_db_session
from db.repositories.doc_repo import DocumentRepository
from ingestion.chunker import SmartChunker
from ingestion.embedder import embedding_model
from ingestion.extractors.docx import DOCXExtractor
from ingestion.extractors.excel import ExcelExtractor
from ingestion.extractors.image import ImageExtractor
from ingestion.extractors.pdf import PDFExtractor
from ingestion.extractors.pptx import PPTXExtractor
from ingestion.extractors.txt import TXTExtractor
from services.topic_service import TopicService

logger = get_logger(__name__)
settings = get_settings()


class ExtractorRegistry:
    """
    Maps file extensions to extractor instances.
    Adding a new file type = register it here.
    """

    def __init__(self):
        self._extractors = [
            PDFExtractor(),
            DOCXExtractor(),
            PPTXExtractor(),
            ExcelExtractor(),
            ImageExtractor(),
            TXTExtractor()
        ]

    def get(self, filepath: str):
        """Get the right extractor for a file. Raises if unsupported."""
        for extractor in self._extractors:
            if extractor.can_handle(filepath):
                return extractor

        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else "unknown"
        raise UnsupportedFileTypeError(
            os.path.basename(filepath),
            ext,
            settings.allowed_extensions
        )

    @property
    def supported_extensions(self) -> List[str]:
        exts = []
        for e in self._extractors:
            exts.extend(e.supported_extensions)
        return exts


class IngestionPipeline:
    """
    Full document ingestion pipeline.

    Flow:
        validate → extract → chunk → embed → store in Qdrant → update DB
    """

    def __init__(self):
        self.registry = ExtractorRegistry()
        self.chunker = SmartChunker()
        self.qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it doesn't exist."""
        existing = [
            c.name for c in
            self.qdrant.get_collections().collections
        ]

        if settings.QDRANT_COLLECTION_NAME not in existing:
            self.qdrant.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.QDRANT_VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
            logger.info(
                "qdrant_collection_created",
                collection=settings.QDRANT_COLLECTION_NAME
            )

    def ingest(
        self,
        filepath: str,
        allowed_roles: List[str],
        uploaded_by: str,
        departments: List[str] = None,
        hierarchy: int = 1,
        doc_id: Optional[str] = None,
        original_filename: Optional[str] = None
    ) -> dict:
        """
        Ingest a single document.
        Returns ingestion stats dict.
        Raises specific IngestionError subclasses on failure.
        """
        start_time = time.perf_counter()
        filename = os.path.basename(filepath)
        original_name = original_filename or filename

        logger.info(
            "ingestion_started",
            filename=filename,
            allowed_roles=allowed_roles,
            departments=departments,
            uploaded_by=uploaded_by
        )

        # ── Step 1: Validate ─────────────────────────────────
        self._validate_file(filepath)

        # ── Step 2: Register in DB ───────────────────────────
        with get_db_session() as db:
            doc_repo = DocumentRepository(db)
            doc = doc_repo.create(
                filename=filename,
                original_filename=original_name,
                file_type=filepath.rsplit(".", 1)[-1].lower(),
                file_size_bytes=os.path.getsize(filepath),
                allowed_roles=allowed_roles,
                uploaded_by=uploaded_by,
                departments=departments,
                hierarchy=hierarchy
            )
            doc_id = doc.id
            doc_repo.mark_processing(doc_id)

        try:
            # ── Step 3: Extract Text ──────────────────────────
            with TimedOperation(logger, "extraction", filename=filename):
                extractor = self.registry.get(filepath)
                result = extractor.extract(filepath)

            if result.is_empty:
                raise EmptyDocumentError(filename)

            # ── Step 3b: Topic Tree -----------------------------
            doc_topic_id = None
            topic_ancestors = []
            try:
                with get_db_session() as db:
                    topic_service = TopicService(db)
                    topic_info = topic_service.build_for_document(
                        doc_id=doc_id,
                        original_filename=original_name,
                        text=result.text
                    )
                    doc_topic_id = topic_info["doc_topic_id"]
                    topic_ancestors = topic_info["topic_ancestors"]
            except Exception as e:
                logger.warning("topic_tree_build_failed", error=str(e))

            # ── Step 4: Chunk ─────────────────────────────────
            with TimedOperation(logger, "chunking", filename=filename):
                chunks = self.chunker.chunk(
                    result.text,
                    metadata={
                        "source_file": filename,
                        "doc_id": doc_id
                    }
                )

            if not chunks:
                raise EmptyDocumentError(filename)

            # ── Step 4b: Tag chunks with page numbers ─────────
            # PDF extractor injects <<NEXUS_PAGE:N>> markers; carry
            # the current page across chunks so even chunks without a
            # marker get the correct page from the preceding chunk.
            chunk_pages: List[List[int]] = []
            current_page: Optional[int] = None
            for chunk in chunks:
                pages_in_chunk: List[int] = []
                for match in _PAGE_MARKER_RE.finditer(chunk.text):
                    page_num = int(match.group(1))
                    if not pages_in_chunk or pages_in_chunk[-1] != page_num:
                        pages_in_chunk.append(page_num)
                    current_page = page_num
                if not pages_in_chunk and current_page is not None:
                    pages_in_chunk = [current_page]
                # Strip markers from the chunk text before embedding
                chunk.text = _PAGE_MARKER_RE.sub("", chunk.text).strip()
                chunk_pages.append(pages_in_chunk)

            # ── Step 5: Embed ─────────────────────────────────
            with TimedOperation(
                logger,
                "embedding",
                filename=filename,
                chunks=len(chunks)
            ):
                chunk_texts = [c.text for c in chunks]
                vectors = embedding_model.embed_batch(chunk_texts)

            # ── Step 6: Store in Qdrant ───────────────────────
            with TimedOperation(
                logger,
                "qdrant_upsert",
                filename=filename,
                points=len(chunks)
            ):
                points = [
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vectors[i],
                        payload={
                            "text": chunks[i].text,
                            "source_file": filename,
                            "doc_id": doc_id,
                            "chunk_index": chunks[i].chunk_index,
                            "departments": departments,
                            "hierarchy": hierarchy,
                            "allowed_roles": allowed_roles,
                            "word_count": chunks[i].word_count,
                            "topic_id": doc_topic_id,
                            "topic_ancestors": topic_ancestors,
                            "pages": chunk_pages[i]
                        }
                    )
                    for i in range(len(chunks))
                ]

                # Upsert in batches of 100
                batch_size = 100
                for i in range(0, len(points), batch_size):
                    batch = points[i:i + batch_size]
                    self.qdrant.upsert(
                        collection_name=settings.QDRANT_COLLECTION_NAME,
                        points=batch
                    )

            # ── Step 7: Mark Complete in DB ───────────────────
            total_time = time.perf_counter() - start_time

            with get_db_session() as db:
                doc_repo = DocumentRepository(db)
                doc_repo.mark_completed(
                    doc_id=doc_id,
                    total_chunks=len(chunks),
                    ingestion_time_seconds=round(total_time, 2)
                )

            stats = {
                "doc_id": doc_id,
                "filename": filename,
                "status": "completed",
                "total_chunks": len(chunks),
                "total_pages": result.page_count,
                "total_words": result.word_count,
                "extraction_method": result.extraction_method,
                "ingestion_time_seconds": round(total_time, 2),
                "warnings": result.warnings
            }

            logger.info("ingestion_completed", **stats)
            return stats

        except (IngestionError, EmptyDocumentError) as e:
            # Mark failed in DB and re-raise
            with get_db_session() as db:
                doc_repo = DocumentRepository(db)
                doc_repo.mark_failed(doc_id, str(e))
            raise

        except Exception as e:
            with get_db_session() as db:
                doc_repo = DocumentRepository(db)
                doc_repo.mark_failed(doc_id, str(e))
            logger.error(
                "ingestion_unexpected_error",
                filename=filename,
                error=str(e)
            )
            raise IngestionError(
                f"Unexpected ingestion error: {str(e)}"
            )

    def _validate_file(self, filepath: str) -> None:
        """Validate file exists, size, and type before processing."""
        filename = os.path.basename(filepath)

        if not os.path.exists(filepath):
            raise ExtractionFailedError(filename, "File not found")

        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size > settings.max_file_size_bytes:
            size_mb = file_size / (1024 * 1024)
            raise FileTooLargeError(
                filename,
                size_mb,
                settings.MAX_FILE_SIZE_MB
            )

        # Check file type
        if "." not in filepath:
            raise UnsupportedFileTypeError(
                filename, "unknown",
                settings.allowed_extensions
            )

        ext = filepath.rsplit(".", 1)[-1].lower()
        if ext not in settings.allowed_extensions:
            raise UnsupportedFileTypeError(
                filename, ext,
                settings.allowed_extensions
            )

    def delete_document(self, doc_id: str, filename: str) -> None:
        """
        Remove a document from both Qdrant and the database.
        Called when admin deletes a document.
        """
        try:
            # Delete from Qdrant by filtering on doc_id payload
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            self.qdrant.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                )
            )

            logger.info(
                "document_deleted_from_qdrant",
                doc_id=doc_id,
                filename=filename
            )

        except Exception as e:
            logger.error(
                "qdrant_delete_failed",
                doc_id=doc_id,
                error=str(e)
            )
            raise IngestionError(f"Failed to delete from vector store: {str(e)}")

    def clear_all_documents(self) -> None:
        """
        Clear all vectors from the collection and recreate it.
        Used for admin-only bulk delete operations.
        """
        try:
            self.qdrant.delete_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME
            )
            self._ensure_collection()
            logger.info(
                "qdrant_collection_cleared",
                collection=settings.QDRANT_COLLECTION_NAME
            )
        except Exception as e:
            logger.error(
                "qdrant_collection_clear_failed",
                collection=settings.QDRANT_COLLECTION_NAME,
                error=str(e)
            )
            raise IngestionError(
                f"Failed to clear vector store: {str(e)}"
            )


# Module level singleton
pipeline = IngestionPipeline()