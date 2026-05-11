"""
Qdrant vector store abstraction for Nexus.
Nothing outside this file talks to Qdrant directly.
Swap Qdrant for any other vector DB by changing only this file.
"""

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams
)

from core.config import get_settings
from core.exceptions import (
    CollectionNotFoundError,
    QueryFailedError,
    RetrievalError
)
from core.logger import get_logger, TimedOperation

logger = get_logger(__name__)
settings = get_settings()


class SearchResult:
    """
    Normalized search result.
    Decouples the rest of the app from Qdrant's data structures.
    """

    def __init__(self, point):
        self.id = str(point.id)
        self.score = round(float(point.score), 4)
        self.text = point.payload.get("text", "")
        self.source_file = point.payload.get("source_file", "unknown")
        self.doc_id = point.payload.get("doc_id", "")
        self.chunk_index = point.payload.get("chunk_index", 0)
        self.departments = point.payload.get("departments", [])
        self.hierarchy = point.payload.get("hierarchy", 1)
        self.allowed_roles = point.payload.get("allowed_roles", [])
        self.word_count = point.payload.get("word_count", 0)
        self.topic_id = point.payload.get("topic_id")
        self.topic_ancestors = point.payload.get("topic_ancestors", [])
        self.payload = point.payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "text": self.text,
            "source_file": self.source_file,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "departments": self.departments
        }

    def __repr__(self) -> str:
        return (
            f"<SearchResult score={self.score} "
            f"source={self.source_file} chunk={self.chunk_index}>"
        )


class VectorStore:
    """
    Qdrant vector store wrapper.
    Singleton — one client instance shared across the app.
    """

    _instance: Optional["VectorStore"] = None
    _client: Optional[QdrantClient] = None

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """Connect to Qdrant and ensure collection exists."""
        try:
            self._client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=30
            )
            self._ensure_collection()
            logger.info(
                "qdrant_connected",
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                collection=settings.QDRANT_COLLECTION_NAME
            )
        except Exception as e:
            logger.error("qdrant_connection_failed", error=str(e))
            raise RetrievalError(f"Qdrant connection failed: {str(e)}")

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self.initialize()
        return self._client

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        existing = [
            c.name for c in
            self.client.get_collections().collections
        ]
        if settings.QDRANT_COLLECTION_NAME not in existing:
            self.client.create_collection(
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

    def search(
        self,
        query_vector: List[float],
        user_roles: List[str],
        limit: int = 5,
        score_threshold: float = 0.3,
        department_filter: Optional[str] = None,
        topic_ancestor_id: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Search for relevant chunks with mandatory RBAC filtering.
        user_roles determines which chunks are visible.
        A user will NEVER receive chunks their roles don't allow.
        """
        if not user_roles:
            logger.warning("search_called_with_empty_roles")
            return []

        try:
            # Build role filter — core RBAC enforcement
            must_conditions = [
                FieldCondition(
                    key="allowed_roles",
                    match=MatchAny(any=user_roles)
                )
            ]

            # Optional department filter
            if department_filter:
                must_conditions.append(
                    FieldCondition(
                        key="departments",
                        match=MatchAny(any=[department_filter])
                    )
                )

            if topic_ancestor_id:
                must_conditions.append(
                    FieldCondition(
                        key="topic_ancestors",
                        match=MatchAny(any=[topic_ancestor_id])
                    )
                )

            rbac_filter = Filter(must=must_conditions)
            from qdrant_client.models import QueryRequest
            with TimedOperation(
                logger,
                "qdrant_search",
                roles=user_roles,
                limit=limit
            ):
                points = self.client.query_points(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    query=query_vector,
                    query_filter=rbac_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True
                ).points

            results = [SearchResult(p) for p in points]

            logger.info(
                "qdrant_search_results",
                results_count=len(results),
                user_roles=user_roles,
                top_score=results[0].score if results else 0
            )

            return results

        except Exception as e:
            logger.error("qdrant_search_failed", error=str(e))
            raise QueryFailedError(str(e))

    def is_healthy(self) -> bool:
        """Check Qdrant connectivity. Never raises."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics for admin dashboard."""
        try:
            info = self.client.get_collection(
                settings.QDRANT_COLLECTION_NAME
            )
            return {
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": str(info.status)
            }
        except Exception as e:
            logger.error("collection_stats_failed", error=str(e))
            return {}

    def get_chunks_by_doc_id(
        self,
        doc_id: str,
        limit: int = 200
    ) -> List[SearchResult]:
        """Fetch chunks for a specific document ID (debug only)."""
        try:
            doc_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id)
                    )
                ]
            )

            with TimedOperation(
                logger,
                "qdrant_scroll",
                doc_id=doc_id,
                limit=limit
            ):
                points, _ = self.client.scroll(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    scroll_filter=doc_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )

            return [SearchResult(p) for p in points]

        except Exception as e:
            logger.error("qdrant_scroll_failed", doc_id=doc_id, error=str(e))
            return []


# Module level singleton
vector_store = VectorStore()