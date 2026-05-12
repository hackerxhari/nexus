"""
End-to-end integration tests for the ingestion pipeline.

These exercise the full path:
    ExtractorRegistry → SmartChunker → embedding_model → Qdrant upsert

External services (Qdrant, the embedding model, the SQL database, the
topic service) are stubbed so the test stays hermetic and fast, but the
real chunker, real extractor registry, and real pipeline orchestration
code all run.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ───────────────────────────────────────────────────────────────────
# Module-level pre-patching of QdrantClient.
#
# ingestion.pipeline instantiates a real QdrantClient at module load
# (via the `pipeline = IngestionPipeline()` singleton at the bottom),
# which would attempt a TCP connection. Patch the class before import.
# ───────────────────────────────────────────────────────────────────
def _build_fake_qdrant_class():
    fake_class = MagicMock(name="FakeQdrantClientClass")

    def factory(*args, **kwargs):
        inst = MagicMock(name="FakeQdrantClient")
        inst.get_collections.return_value.collections = []
        inst._upserts = []

        def record_upsert(collection_name, points, **kw):
            inst._upserts.append({
                "collection_name": collection_name,
                "points": list(points),
            })
            return MagicMock(status="ok")

        inst.upsert.side_effect = record_upsert
        return inst

    fake_class.side_effect = factory
    return fake_class


_FAKE_QDRANT_CLASS = _build_fake_qdrant_class()
_qdrant_patcher = patch("qdrant_client.QdrantClient", _FAKE_QDRANT_CLASS)
_qdrant_patcher.start()

# Safe to import now — module-level singleton uses the fake.
from ingestion.pipeline import (  # noqa: E402
    ExtractorRegistry,
    IngestionPipeline,
)
from ingestion.extractors.base import ExtractionResult  # noqa: E402


# ───────────────────────────────────────────────────────────────────
# Helpers / fakes
# ───────────────────────────────────────────────────────────────────

class _FakeDoc:
    def __init__(self, doc_id: str):
        self.id = doc_id


class _FakeDocRepo:
    """Stand-in for DocumentRepository — records calls without a DB."""

    def __init__(self, db):
        self.db = db
        self.created: List[Dict[str, Any]] = []
        self.processing: List[str] = []
        self.completed: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        doc_id = "doc-" + uuid.uuid4().hex[:8]
        self.created.append({"id": doc_id, **kwargs})
        return _FakeDoc(doc_id)

    def mark_processing(self, doc_id):
        self.processing.append(doc_id)

    def mark_completed(self, doc_id, total_chunks, ingestion_time_seconds):
        self.completed.append({
            "doc_id": doc_id,
            "total_chunks": total_chunks,
            "ingestion_time_seconds": ingestion_time_seconds,
        })

    def mark_failed(self, doc_id, reason):
        self.failed.append({"doc_id": doc_id, "reason": reason})


class _FakeEmbedder:
    """Deterministic stub embedding model. Returns 384-dim vectors."""

    def __init__(self):
        self.calls: List[List[str]] = []

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        return [[0.01 * (i + 1)] * 384 for i in range(len(texts))]

    def embed_text(self, text):
        return [0.01] * 384


class _FakeTopicService:
    def __init__(self, db):
        self.db = db

    def build_for_document(self, doc_id, original_filename, text):
        return {
            "doc_topic_id": "topic-" + doc_id,
            "topic_ancestors": ["root", "topic-" + doc_id],
        }


# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_embedder():
    return _FakeEmbedder()


@pytest.fixture
def patched_pipeline_deps(fake_embedder):
    """
    Patch DB session, DocumentRepository, TopicService and the embedding
    singleton used inside ingestion.pipeline. Yields a `(pipeline,
    captured)` tuple where `captured` exposes the fake repo and embedder
    for assertions.
    """
    captured: Dict[str, Any] = {}

    class _SessionCM:
        def __enter__(self):
            return MagicMock(name="FakeDBSession")

        def __exit__(self, exc_type, exc, tb):
            return False

    repo_holder: Dict[str, _FakeDocRepo] = {}

    def repo_factory(db):
        repo = repo_holder.get("repo")
        if repo is None:
            repo = _FakeDocRepo(db)
            repo_holder["repo"] = repo
        return repo

    with patch("ingestion.pipeline.get_db_session", return_value=_SessionCM()), \
         patch("ingestion.pipeline.DocumentRepository", side_effect=repo_factory), \
         patch("ingestion.pipeline.TopicService", _FakeTopicService), \
         patch("ingestion.pipeline.embedding_model", fake_embedder):

        # Construct a fresh pipeline — its __init__ wires up the fake
        # QdrantClient (already pre-patched at module load).
        pipeline = IngestionPipeline()
        captured["pipeline"] = pipeline
        captured["embedder"] = fake_embedder
        captured["repo_holder"] = repo_holder
        captured["qdrant"] = pipeline.qdrant
        yield captured


@pytest.fixture
def sample_txt_file():
    """Create a temporary .txt file with realistic multi-paragraph text."""
    content = (
        "Welcome to the company handbook.\n"
        "This document describes our key policies in detail.\n\n"
        "All employees are entitled to twenty paid leave days per year. "
        "Leave must be requested at least one week in advance. "
        "Approval is granted by the direct manager.\n\n"
        "Expense claims must be submitted within thirty days. "
        "Receipts are required for every claim over one hundred dollars. "
        "Reimbursement is processed in the next pay cycle.\n\n"
        "Confidential information must never leave company devices. "
        "Encryption is mandatory on all laptops and removable media. "
        "Violations may result in immediate termination.\n"
    )

    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


# ───────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────

class TestExtractorRegistry:
    """The registry is part of the pipeline's wiring — sanity check it."""

    def test_txt_extractor_handles_text_files(self, sample_txt_file):
        registry = ExtractorRegistry()
        extractor = registry.get(sample_txt_file)
        assert extractor is not None
        result = extractor.extract(sample_txt_file)
        assert isinstance(result, ExtractionResult)
        assert result.text and "company handbook" in result.text

    def test_unsupported_extension_raises(self):
        registry = ExtractorRegistry()
        from core.exceptions import UnsupportedFileTypeError
        with pytest.raises(UnsupportedFileTypeError):
            registry.get("file.unknownext")


class TestFullIngestionPipeline:
    """
    Drive the real pipeline end-to-end with a small text document.
    The flow runs: extract → chunk (real SmartChunker) → embed (fake) →
    Qdrant upsert (fake). DB and TopicService are stubbed.
    """

    def test_happy_path_ingestion(
        self, patched_pipeline_deps, sample_txt_file
    ):
        pipeline = patched_pipeline_deps["pipeline"]
        embedder = patched_pipeline_deps["embedder"]
        qdrant = patched_pipeline_deps["qdrant"]
        repo_holder = patched_pipeline_deps["repo_holder"]

        stats = pipeline.ingest(
            filepath=sample_txt_file,
            allowed_roles=["employee", "manager"],
            uploaded_by="alice@example.com",
            departments=["hr"],
            hierarchy=2,
        )

        # Stats shape is correct
        assert stats["status"] == "completed"
        assert stats["total_chunks"] >= 1
        assert stats["total_words"] > 0
        assert stats["filename"].endswith(".txt")
        assert "ingestion_time_seconds" in stats

        # Embedder was called once with a batch of chunk texts
        assert len(embedder.calls) == 1
        chunk_texts = embedder.calls[0]
        assert len(chunk_texts) == stats["total_chunks"]
        assert all(isinstance(t, str) and t.strip() for t in chunk_texts)

        # Qdrant received upsert(s) carrying chunk payloads
        assert qdrant.upsert.called, "Qdrant.upsert must be called"
        assert len(qdrant._upserts) >= 1
        all_points = []
        for batch in qdrant._upserts:
            all_points.extend(batch["points"])
        assert len(all_points) == stats["total_chunks"]

        # Verify payload integrity for the first point
        first = all_points[0]
        assert first.vector is not None
        assert len(first.vector) == 384
        payload = first.payload
        assert payload["source_file"].endswith(".txt")
        assert payload["allowed_roles"] == ["employee", "manager"]
        assert payload["departments"] == ["hr"]
        assert payload["hierarchy"] == 2
        assert payload["chunk_index"] == 0
        assert payload["topic_id"] is not None
        assert "topic_ancestors" in payload

        # DocumentRepository lifecycle: create → mark_processing → complete
        repo = repo_holder["repo"]
        assert len(repo.created) == 1
        assert repo.processing == [repo.created[0]["id"]]
        assert len(repo.completed) == 1
        assert repo.completed[0]["total_chunks"] == stats["total_chunks"]
        assert repo.failed == []

    def test_empty_document_raises_and_marks_failed(
        self, patched_pipeline_deps
    ):
        from core.exceptions import EmptyDocumentError

        pipeline = patched_pipeline_deps["pipeline"]
        repo_holder = patched_pipeline_deps["repo_holder"]

        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("   \n   \n")  # only whitespace

            # Empty text trips EmptyDocumentError; the extractor itself
            # raises ExtractionFailedError on a fully empty extraction.
            with pytest.raises(Exception) as excinfo:
                pipeline.ingest(
                    filepath=path,
                    allowed_roles=["employee"],
                    uploaded_by="alice@example.com",
                )
            # Confirm the doc was marked failed in DB
            repo = repo_holder["repo"]
            assert len(repo.failed) == 1
            # Exception should be an IngestionError (EmptyDocumentError is one)
            from core.exceptions import IngestionError
            assert isinstance(excinfo.value, IngestionError)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_unsupported_filetype_raises(self, patched_pipeline_deps):
        from core.exceptions import UnsupportedFileTypeError

        pipeline = patched_pipeline_deps["pipeline"]

        fd, path = tempfile.mkstemp(suffix=".xyz")
        os.close(fd)
        try:
            with open(path, "w") as fh:
                fh.write("dummy")
            with pytest.raises(UnsupportedFileTypeError):
                pipeline.ingest(
                    filepath=path,
                    allowed_roles=["employee"],
                    uploaded_by="x@y.com",
                )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_missing_file_raises_extraction_error(self, patched_pipeline_deps):
        from core.exceptions import ExtractionFailedError

        pipeline = patched_pipeline_deps["pipeline"]
        with pytest.raises(ExtractionFailedError):
            pipeline.ingest(
                filepath="h:/does/not/exist.txt",
                allowed_roles=["employee"],
                uploaded_by="x@y.com",
            )

    def test_chunk_count_matches_vectors_and_points(
        self, patched_pipeline_deps, sample_txt_file
    ):
        """The number of chunks must equal both the embeddings produced
        and the points upserted to Qdrant — guards against off-by-one
        drift between stages."""
        pipeline = patched_pipeline_deps["pipeline"]
        embedder = patched_pipeline_deps["embedder"]
        qdrant = patched_pipeline_deps["qdrant"]

        stats = pipeline.ingest(
            filepath=sample_txt_file,
            allowed_roles=["employee"],
            uploaded_by="bob@example.com",
        )

        n_chunks = stats["total_chunks"]
        assert n_chunks >= 1

        n_embeddings = sum(len(call) for call in embedder.calls)
        n_points = sum(len(b["points"]) for b in qdrant._upserts)

        assert n_chunks == n_embeddings == n_points
