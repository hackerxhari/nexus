"""
End-to-end integration tests for the RAG query path.

These exercise the full query flow inside QueryEngine.query():
    cache check → embed → vector search → rerank → prompt build →
    LLM generate → cache store → return QueryResult

External services (Redis cache, embedding model, Qdrant vector store,
Ollama LLM, custom-Q&A DB lookup) are stubbed. The real query engine
orchestration code, RBAC enforcement, scoring filter, name-rerank, and
citation builder all run unmodified.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from retrieval.query_engine import QueryEngine, QueryResult


# ───────────────────────────────────────────────────────────────────
# Stand-in for retrieval.vector_store.SearchResult
# ───────────────────────────────────────────────────────────────────

class FakeSearchResult:
    """Duck-typed stand-in for SearchResult."""

    def __init__(
        self,
        result_id: str,
        text: str,
        score: float,
        source_file: str = "doc.pdf",
        doc_id: str = "doc-1",
        chunk_index: int = 0,
        allowed_roles: Optional[List[str]] = None,
        departments: Optional[List[str]] = None,
        hierarchy: int = 1,
        pages: Optional[List[int]] = None,
        topic_id: Optional[str] = None,
        topic_ancestors: Optional[List[str]] = None,
    ):
        self.id = result_id
        self.text = text
        self.score = score
        self.source_file = source_file
        self.doc_id = doc_id
        self.chunk_index = chunk_index
        self.allowed_roles = allowed_roles or ["employee"]
        self.departments = departments or []
        self.hierarchy = hierarchy
        self.pages = pages or []
        self.topic_id = topic_id
        self.topic_ancestors = topic_ancestors or []
        self.word_count = len(text.split())


# ───────────────────────────────────────────────────────────────────
# Stub services
# ───────────────────────────────────────────────────────────────────

class _StubEmbedder:
    def __init__(self):
        self.calls: List[str] = []

    def embed_text(self, text: str) -> List[float]:
        self.calls.append(text)
        return [0.01] * 384


class _StubVectorStore:
    """Records search calls and returns a configurable list of results."""

    def __init__(self, results: List[FakeSearchResult]):
        self.results = results
        self.searches: List[Dict[str, Any]] = []

    def search(
        self,
        query_vector,
        user_roles,
        limit,
        score_threshold,
        department_filter=None,
        topic_ancestor_id=None,
    ):
        self.searches.append({
            "user_roles": list(user_roles),
            "limit": limit,
            "score_threshold": score_threshold,
            "department_filter": department_filter,
            "topic_ancestor_id": topic_ancestor_id,
        })
        return list(self.results)


class _StubLLMResponse:
    def __init__(self, content: str):
        self.content = content


class _StubLLM:
    def __init__(self, content: str = "Stub answer."):
        self.content = content
        self.calls: List[Dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return _StubLLMResponse(self.content)


class _StubQueryCache:
    """In-memory query cache that records get/set."""

    def __init__(self, initial: Optional[Dict[str, Any]] = None):
        self.store: Dict[tuple, Dict[str, Any]] = {}
        if initial:
            # Insert at the canonical key the engine uses
            for key, value in initial.items():
                self.store[key] = value
        self.get_calls = 0
        self.set_calls = 0

    def get(self, question, topic_id=None, department=None):
        self.get_calls += 1
        return self.store.get((question.strip().lower(), topic_id, department))

    def set(self, question, topic_id, department, result, ttl=None):
        self.set_calls += 1
        self.store[(question.strip().lower(), topic_id, department)] = result
        return True


class _StubCacheService:
    def __init__(self, queries: _StubQueryCache):
        self.queries = queries


# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────

@pytest.fixture
def stub_embedder():
    return _StubEmbedder()


@pytest.fixture
def stub_llm():
    return _StubLLM("The leave policy is 20 days per year.")


@pytest.fixture
def stub_cache():
    return _StubCacheService(_StubQueryCache())


@pytest.fixture
def stub_results():
    return [
        FakeSearchResult(
            result_id="r1",
            text="The leave policy entitles every employee to 20 paid days per year.",
            score=0.91,
            source_file="hr_policy.pdf",
            doc_id="doc-hr",
            chunk_index=0,
            allowed_roles=["employee", "manager"],
            departments=[],
            hierarchy=1,
            pages=[3],
        ),
        FakeSearchResult(
            result_id="r2",
            text="Leave must be requested at least one week in advance.",
            score=0.84,
            source_file="hr_policy.pdf",
            doc_id="doc-hr",
            chunk_index=1,
            allowed_roles=["employee", "manager"],
            departments=[],
            hierarchy=1,
            pages=[4],
        ),
    ]


@pytest.fixture
def stub_vector_store(stub_results):
    return _StubVectorStore(stub_results)


@pytest.fixture
def patched_query_engine(stub_embedder, stub_vector_store, stub_llm, stub_cache):
    """
    Apply patches at the import locations used by retrieval.query_engine
    so that the real QueryEngine.query() orchestration runs against stubs.
    """
    with patch("retrieval.query_engine.embedding_model", stub_embedder), \
         patch("retrieval.query_engine.vector_store", stub_vector_store), \
         patch("retrieval.query_engine.cache_service", stub_cache), \
         patch(
             "retrieval.query_engine._get_llm_client",
             return_value=stub_llm,
         ), \
         patch("retrieval.query_engine._settings") as mock_settings:

        # Make settings deterministic for tests
        mock_settings.RETRIEVAL_TOP_K = 5
        mock_settings.RETRIEVAL_SCORE_THRESHOLD = 0.25
        mock_settings.SCORE_RELATIVE_THRESHOLD = 0.65
        mock_settings.MIN_SCORE_THRESHOLD = 0.30
        mock_settings.CONTEXT_CHAR_BUDGET = 9000
        mock_settings.TOPIC_FILTER_ENABLED = False
        mock_settings.QUERY_REWRITE_ENABLED = False
        mock_settings.CUSTOM_QA_ENABLED = False
        mock_settings.MULTI_HOP_ENABLED = False

        engine = QueryEngine(top_k=5, score_threshold=0.25)

        yield {
            "engine": engine,
            "embedder": stub_embedder,
            "vector_store": stub_vector_store,
            "llm": stub_llm,
            "cache": stub_cache,
            "settings": mock_settings,
        }


# ───────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────

class TestQueryEngineHappyPath:
    def test_full_pipeline_returns_grounded_answer(self, patched_query_engine):
        ctx = patched_query_engine

        result = ctx["engine"].query(
            question="What is the leave policy?",
            user_roles=["employee"],
            user_name="Alice",
        )

        assert isinstance(result, QueryResult)
        assert result.cache_hit is False
        assert result.answer == "The leave policy is 20 days per year."
        assert "hr_policy.pdf" in result.sources
        assert result.chunks_retrieved >= 1
        assert result.response_time_ms >= 0

        # All four pipeline stages executed
        assert ctx["embedder"].calls, "Embedder must be called"
        assert ctx["vector_store"].searches, "Vector store must be searched"
        assert ctx["llm"].calls, "LLM must be invoked"
        assert ctx["cache"].queries.get_calls >= 1
        assert ctx["cache"].queries.set_calls == 1

        # The LLM prompt must mention the context source line
        prompt = ctx["llm"].calls[0]["prompt"]
        assert "hr_policy.pdf" in prompt
        assert "leave policy" in prompt.lower()

        # Citations carry the page numbers from the retrieved chunks
        assert result.citations
        pages_seen = {p for c in result.citations for p in c["pages"]}
        assert pages_seen == {3, 4}

    def test_rbac_filter_passed_to_vector_store(self, patched_query_engine):
        ctx = patched_query_engine
        ctx["engine"].query(
            question="leave policy?",
            user_roles=["manager"],
            department_filter="hr",
        )
        last_search = ctx["vector_store"].searches[-1]
        assert last_search["user_roles"] == ["manager"]
        assert last_search["department_filter"] == "hr"


class TestQueryEngineCache:
    def test_cache_hit_short_circuits_pipeline(self, patched_query_engine):
        ctx = patched_query_engine
        cached_payload = {
            "answer": "Cached answer.",
            "sources": ["cached.pdf"],
            "citations": [{"file": "cached.pdf", "pages": [1]}],
            "chunks_retrieved": 2,
            "allowed_roles_union": ["employee"],
        }
        # Prime the cache at the canonical key
        ctx["cache"].queries.store[(
            "what is the leave policy?", None, None
        )] = cached_payload

        result = ctx["engine"].query(
            question="What is the leave policy?",
            user_roles=["employee"],
        )

        assert result.cache_hit is True
        assert result.answer == "Cached answer."
        assert result.sources == ["cached.pdf"]
        # No downstream work happened
        assert ctx["embedder"].calls == []
        assert ctx["vector_store"].searches == []
        assert ctx["llm"].calls == []

    def test_cache_role_mismatch_falls_through(self, patched_query_engine):
        ctx = patched_query_engine
        # Cache only allowed for admin; employee asks the same Q
        ctx["cache"].queries.store[(
            "what is the leave policy?", None, None
        )] = {
            "answer": "Admin-only answer.",
            "sources": ["secret.pdf"],
            "chunks_retrieved": 1,
            "allowed_roles_union": ["admin"],
        }

        result = ctx["engine"].query(
            question="What is the leave policy?",
            user_roles=["employee"],
        )

        # Falls through to full pipeline
        assert result.cache_hit is False
        assert result.answer == "The leave policy is 20 days per year."
        assert ctx["llm"].calls, "Should reach LLM despite stale cache"

    def test_bypass_cache_runs_full_pipeline(self, patched_query_engine):
        ctx = patched_query_engine
        # Even with cache primed, bypass forces a fresh run
        ctx["cache"].queries.store[(
            "what is the leave policy?", None, None
        )] = {
            "answer": "Cached.",
            "sources": ["x.pdf"],
            "chunks_retrieved": 1,
            "allowed_roles_union": [],
        }

        result = ctx["engine"].query(
            question="What is the leave policy?",
            user_roles=["employee"],
            bypass_cache=True,
        )

        assert result.cache_hit is False
        assert ctx["llm"].calls


class TestQueryEngineNoResults:
    def test_empty_search_returns_no_results_response(self, patched_query_engine):
        ctx = patched_query_engine
        ctx["vector_store"].results = []  # Force empty retrieval

        result = ctx["engine"].query(
            question="What is the leave policy?",
            user_roles=["employee"],
        )

        assert result.cache_hit is False
        assert result.sources == []
        assert result.chunks_retrieved == 0
        # No LLM call when retrieval is empty
        assert ctx["llm"].calls == []
        # A polite "no info" answer was returned
        assert isinstance(result.answer, str) and result.answer.strip()


class TestQueryEngineRBAC:
    def test_chunk_with_no_matching_role_is_dropped(self, patched_query_engine):
        ctx = patched_query_engine
        # Replace results with one that requires admin
        ctx["vector_store"].results = [
            FakeSearchResult(
                result_id="r1",
                text="Top-secret content.",
                score=0.95,
                source_file="secret.pdf",
                allowed_roles=["admin"],
                departments=[],
                hierarchy=1,
            ),
        ]

        result = ctx["engine"].query(
            question="What is in the secret file?",
            user_roles=["employee"],
        )

        # Search returned a result the user lacks role for — engine drops
        # it via _enforce_role_access and ends up returning no-results.
        assert result.sources == []
        assert ctx["llm"].calls == []


class TestQueryEngineValidation:
    def test_empty_question_raises(self, patched_query_engine):
        from core.exceptions import QueryFailedError
        engine = patched_query_engine["engine"]
        with pytest.raises(QueryFailedError):
            engine.query(question="   ", user_roles=["employee"])

    def test_empty_roles_raises(self, patched_query_engine):
        from core.exceptions import QueryFailedError
        engine = patched_query_engine["engine"]
        with pytest.raises(QueryFailedError):
            engine.query(question="hello?", user_roles=[])
