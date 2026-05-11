"""
RAG Query Engine — the heart of Nexus.
Orchestrates: embed -> search -> rerank -> generate -> cache -> audit.
This is where a question becomes an answer.

Includes multi-hop retrieval for cross-document entity resolution:
when Roll No appears in one file (with name) and another file (with marks),
the engine automatically links them by doing a second search pass.
"""

import re
import time
from typing import Dict, Any, List, Optional, Set

from cache.cache_service import CacheService
from core.config import get_settings
from core.exceptions import QueryFailedError, AuthorizationError
from core.logger import get_logger, TimedOperation
from db.base import get_db_session
from ingestion.embedder import embedding_model
from llm.prompt_builder import PromptBuilder
from retrieval.vector_store import vector_store, SearchResult
from services.topic_service import TopicService

logger = get_logger(__name__)
cache_service = CacheService()
_settings = get_settings()


def _get_llm_client():
    """Return the configured LLM client (airllm or ollama)."""
    if _settings.LLM_PROVIDER == "airllm":
        try:
            from llm.airllm_client import airllm_client
            return airllm_client
        except ModuleNotFoundError as e:
            logger.warning(
                "airllm_unavailable_fallback_ollama",
                error=str(e)
            )
            from llm.ollama_client import ollama_client
            return ollama_client
    else:
        from llm.ollama_client import ollama_client
        return ollama_client


_UUID_PREFIX_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_',
    re.IGNORECASE
)


def _clean_source_name(name: str) -> str:
    """Strip UUID prefix from stored filenames for display."""
    return _UUID_PREFIX_RE.sub('', name)


def _extract_name_query(question: str) -> str:
    """Heuristic to extract a name-like phrase from a question."""
    lowered = question.strip().lower()
    for prefix in [
        "who is",
        "who's",
        "tell me about",
        "give me description about",
        "describe",
        "about",
    ]:
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):].strip()
            break
    return lowered


def _rerank_results_by_name_query(
    question: str,
    results: List[SearchResult]
) -> List[SearchResult]:
    name_query = _extract_name_query(question)
    if len(name_query) < 3:
        return results

    parts = [p for p in name_query.split() if len(p) >= 2]
    if not parts:
        return results

    def boosted_score(result: SearchResult) -> float:
        text_lower = result.text.lower()
        match_all = all(part in text_lower for part in parts)
        match_any = any(part in text_lower for part in parts)
        bonus = 0.2 if match_all else 0.05 if match_any else 0.0
        return result.score + bonus

    return sorted(results, key=boosted_score, reverse=True)


def _preview(text: str, limit: int = 240) -> str:
    clean = " ".join(text.split())
    return clean[:limit]


# ── Cross-document identifier extraction ──────────────────────

# Patterns to detect key identifiers in chunk text
_IDENTIFIER_PATTERNS = [
    # Roll No: 101, Roll Number: 101, RollNo: 101
    re.compile(
        r'(?:roll\s*(?:no|number|num)\.?\s*[:\-]?\s*)(\S+)',
        re.IGNORECASE
    ),
    # ID: ABC123, Employee ID: 42, Emp ID: 42
    re.compile(
        r'(?:(?:employee|emp|student|staff)?\s*id\s*[:\-]?\s*)(\S+)',
        re.IGNORECASE
    ),
    # Reg No: 2024CS01
    re.compile(
        r'(?:reg(?:istration)?\s*(?:no|number|num)\.?\s*[:\-]?\s*)(\S+)',
        re.IGNORECASE
    ),
]


def _extract_cross_doc_identifiers(
    results: List[SearchResult],
    question: str
) -> List[str]:
    """
    Extract key identifiers from retrieved chunks that could be used
    to find related data in OTHER documents.

    Example:
      Chunk from file A: "Roll No: 101 | Name: John"
      → extracts "Roll No 101" so we can search for marks in file B

    Returns a list of search queries for the second hop.
    """
    seen_identifiers: Set[str] = set()
    hop_queries: List[str] = []
    source_files = set()

    for r in results:
        source_files.add(r.source_file)
        text = r.text

        for pattern in _IDENTIFIER_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                identifier_value = match.group(1).strip().rstrip('|,;.')
                if (
                    identifier_value
                    and len(identifier_value) >= 1
                    and identifier_value not in seen_identifiers
                ):
                    seen_identifiers.add(identifier_value)

    # Build search queries from identifiers
    for ident in seen_identifiers:
        # Search for this identifier to find related info in other docs
        hop_queries.append(ident)

    if hop_queries:
        logger.debug(
            "cross_doc_identifiers_found",
            count=len(hop_queries),
            identifiers=list(seen_identifiers)[:10],
            source_count=len(source_files)
        )

    return hop_queries


def _multi_hop_retrieval(
    initial_results: List[SearchResult],
    question: str,
    user_roles: List[str],
    score_threshold: float,
    department_filter: Optional[str] = None,
    max_extra_chunks: int = 5
) -> List[SearchResult]:
    """
    Perform a second retrieval pass using identifiers extracted from
    the initial results. This enables cross-document entity resolution.

    Example flow:
      Query: "What are John's marks?"
      Initial results: ["Roll No: 101 | Name: John" from file A]
      Hop query: "101" → finds ["Roll No: 101 | Marks: 95" from file B]
      Merged: Both chunks given to LLM → it can answer correctly.
    """
    hop_queries = _extract_cross_doc_identifiers(initial_results, question)
    if not hop_queries:
        return initial_results

    # Track which chunks we already have
    existing_ids = {r.id for r in initial_results}
    new_chunks: List[SearchResult] = []

    for query_text in hop_queries[:3]:  # Limit to 3 hop queries
        try:
            hop_vector = embedding_model.embed_text(query_text)
            hop_results = vector_store.search(
                query_vector=hop_vector,
                user_roles=user_roles,
                limit=3,
                score_threshold=score_threshold,
                department_filter=department_filter,
                topic_ancestor_id=None
            )

            for r in hop_results:
                if r.id not in existing_ids:
                    existing_ids.add(r.id)
                    new_chunks.append(r)

        except Exception as e:
            logger.debug(
                "multi_hop_search_failed",
                query=query_text,
                error=str(e)
            )
            continue

    if new_chunks:
        logger.info(
            "multi_hop_retrieval_success",
            initial_count=len(initial_results),
            new_chunks=len(new_chunks),
            total=len(initial_results) + len(new_chunks)
        )

    # Merge: initial results first, then hop results (lower priority)
    merged = initial_results + new_chunks[:max_extra_chunks]
    return merged


def _filter_results_by_score(results: List[SearchResult]) -> List[SearchResult]:
    if not results:
        return results
    max_score = max(r.score for r in results)
    floor = max(
        _settings.MIN_SCORE_THRESHOLD,
        max_score * _settings.SCORE_RELATIVE_THRESHOLD
    )
    return [r for r in results if r.score >= floor]


def _exact_match_results(
    question: str,
    results: List[SearchResult]
) -> List[SearchResult]:
    q = question.strip().lower()
    if len(q) < 3:
        return []
    matches = [r for r in results if q in r.text.lower()]
    if matches:
        return matches
    name_query = _extract_name_query(question)
    if name_query and name_query != q:
        n = name_query.lower()
        matches = [r for r in results if n in r.text.lower()]
    return matches


def _enforce_role_access(
    results: List[SearchResult],
    user_roles: List[str],
    user_department: Optional[str] = None,
    user_hierarchy: int = 1
) -> List[SearchResult]:
    """
    Filter out chunks the user doesn't have access to.
    Enforces department and hierarchy based on user's role level.
    """
    from core.security import RoleChecker
    is_global = any(r in user_roles for r in ["admin", "ceo"])

    filtered = []
    for r in results:
        allowed = r.allowed_roles or []
        if not allowed or any(role in allowed for role in user_roles):
            if is_global:
                filtered.append(r)
            else:
                doc_depts = getattr(r, 'departments', [])
                usr_dept = user_department or ""
                doc_hier = getattr(r, 'hierarchy', 1)
                
                # Document is accessible if user's department is in the document's allowed departments
                # or if the document has no specific department restriction (empty list)
                dept_match = (usr_dept in doc_depts) if doc_depts else True
                
                if dept_match and doc_hier <= user_hierarchy:
                    filtered.append(r)
                    
    if len(filtered) < len(results):
        logger.debug(
            "rbac_filtered_chunks",
            total=len(results),
            kept=len(filtered),
            removed=len(results) - len(filtered)
        )
    return filtered


def _rewrite_question(question: str) -> str:
    if not _settings.QUERY_REWRITE_ENABLED:
        return question

    try:
        llm_client = _get_llm_client()
        prompt = PromptBuilder.build_query_focus_prompt(question)
        response = llm_client.generate(prompt=prompt, temperature=0.0)
        focused = response.content.strip().splitlines()[0].strip()
        if 3 <= len(focused) <= 200:
            return focused
    except Exception:
        pass

    return question


def _cache_roles_ok(cached: Dict[str, Any], user_roles: List[str]) -> bool:
    """
    Check if user has at least ONE role in the cached result's role union.
    Previously used all() which was too restrictive — a user only needs
    at least one matching role to access the cached result.
    """
    allowed_union = cached.get("allowed_roles_union")
    if not allowed_union:
        return True  # No role restriction in cached result
    return any(role in allowed_union for role in user_roles)


def _multiple_name_matches_note(
    question: str,
    results: List[SearchResult]
) -> Optional[str]:
    name_query = _extract_name_query(question)
    if len(name_query) < 3:
        return None

    parts = [p for p in name_query.split() if len(p) >= 2]
    if not parts:
        return None

    matching_sources = set()
    for r in results:
        text_lower = r.text.lower()
        if all(part in text_lower for part in parts):
            matching_sources.add(_clean_source_name(r.source_file))

    if len(matching_sources) >= 2:
        return (
            f"I found multiple matches for \"{name_query}\" in the documents. "
            "Please add a last name, email, role, or department to narrow it down."
        )

    return None


class QueryResult:
    """Structured query result returned to the service layer."""

    def __init__(
        self,
        answer: str,
        sources: List[str],
        chunks_retrieved: int,
        cache_hit: bool,
        response_time_ms: float,
        embedding_time_ms: float,
        retrieval_time_ms: float,
        llm_time_ms: float,
        retrieved_chunks: Optional[List[SearchResult]] = None
    ):
        self.answer = answer
        self.sources = sources
        self.chunks_retrieved = chunks_retrieved
        self.cache_hit = cache_hit
        self.response_time_ms = response_time_ms
        self.embedding_time_ms = embedding_time_ms
        self.retrieval_time_ms = retrieval_time_ms
        self.llm_time_ms = llm_time_ms
        self.retrieved_chunks = retrieved_chunks or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "chunks_retrieved": self.chunks_retrieved,
            "cache_hit": self.cache_hit,
            "response_time_ms": round(self.response_time_ms, 2),
            "embedding_time_ms": round(self.embedding_time_ms, 2),
            "retrieval_time_ms": round(self.retrieval_time_ms, 2),
            "llm_time_ms": round(self.llm_time_ms, 2)
        }


class QueryEngine:
    """
    Full RAG pipeline with caching and RBAC.

    Flow:
        1. Check Redis cache (instant return on hit)
        2. Embed question locally
        3. Search Qdrant with role filter (RBAC enforced here)
        4. Build prompt from retrieved chunks
        5. Generate answer via Ollama
        6. Cache result in Redis
        7. Return QueryResult
    """

    def __init__(
        self,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None
    ):
        self.top_k = top_k or _settings.RETRIEVAL_TOP_K
        self.score_threshold = score_threshold or _settings.RETRIEVAL_SCORE_THRESHOLD

    def retrieve_chunks(
        self,
        question: str,
        user_roles: List[str],
        department_filter: Optional[str] = None
    ) -> List[SearchResult]:
        if not question or not question.strip():
            raise QueryFailedError("Question cannot be empty")
        if not user_roles:
            raise QueryFailedError("User roles cannot be empty")

        question = question.strip()

        search_question = _rewrite_question(question)
        topic_id = None
        if _settings.TOPIC_FILTER_ENABLED:
            with get_db_session() as db:
                topic_service = TopicService(db)
                topic_id = topic_service.resolve_query_topic(search_question)
        query_vector = embedding_model.embed_text(search_question)

        search_limit = max(self.top_k * 2, self.top_k)
        results = vector_store.search(
            query_vector=query_vector,
            user_roles=user_roles,
            limit=search_limit,
            score_threshold=self.score_threshold,
            department_filter=department_filter,
            topic_ancestor_id=topic_id if _settings.TOPIC_FILTER_ENABLED else None
        )

        results = _rerank_results_by_name_query(question, results)
        return results[:self.top_k]

    def query(
        self,
        question: str,
        user_roles: List[str],
        user_name: Optional[str] = None,
        department_filter: Optional[str] = None,
        bypass_cache: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_department: Optional[str] = None,
        user_hierarchy: int = 1
    ) -> QueryResult:
        """
        Main query method.
        Returns QueryResult with answer, sources, and performance metrics.
        """
        total_start = time.perf_counter()
        embedding_time_ms = 0.0
        retrieval_time_ms = 0.0
        llm_time_ms = 0.0

        # Validate inputs
        if not question or not question.strip():
            raise QueryFailedError("Question cannot be empty")
        if not user_roles:
            raise QueryFailedError("User roles cannot be empty")

        question = question.strip()
        search_question = _rewrite_question(question)

        # -- Step 0: Check Custom Q&A (instant response) --------
        if _settings.CUSTOM_QA_ENABLED:
            try:
                from services.custom_qa_service import CustomQAService
                with get_db_session() as db:
                    custom_qa = CustomQAService(db)
                    match = custom_qa.find_match(question)
                    if match:
                        total_time = (time.perf_counter() - total_start) * 1000
                        logger.info(
                            "query_custom_qa_hit",
                            question_preview=question[:80],
                            qa_id=match["id"],
                            response_time_ms=round(total_time, 2)
                        )
                        return QueryResult(
                            answer=match["answer"],
                            sources=["Custom Q&A"],
                            chunks_retrieved=0,
                            cache_hit=False,
                            response_time_ms=total_time,
                            embedding_time_ms=0,
                            retrieval_time_ms=0,
                            llm_time_ms=0
                        )
            except Exception as e:
                logger.warning("custom_qa_check_failed", error=str(e))

        topic_id = None
        if _settings.TOPIC_FILTER_ENABLED:
            with get_db_session() as db:
                topic_service = TopicService(db)
                topic_id = topic_service.resolve_query_topic(search_question)

        logger.info(
            "query_started",
            question_preview=question[:80],
            user_roles=user_roles,
            user_name=user_name
        )

        # -- Step 1: Cache Check ------------------------------------
        if not bypass_cache:
            cached = cache_service.queries.get(
                question,
                topic_id=topic_id,
                department=department_filter
            )
            if cached and _cache_roles_ok(cached, user_roles):
                total_time = (time.perf_counter() - total_start) * 1000
                logger.info(
                    "query_cache_hit",
                    response_time_ms=round(total_time, 2)
                )
                return QueryResult(
                    answer=cached["answer"],
                    sources=cached["sources"],
                    chunks_retrieved=cached.get("chunks_retrieved", 0),
                    cache_hit=True,
                    response_time_ms=total_time,
                    embedding_time_ms=0,
                    retrieval_time_ms=0,
                    llm_time_ms=0
                )

        # -- Step 2: Embed Question ---------------------------------
        embed_start = time.perf_counter()
        try:
            query_vector = embedding_model.embed_text(search_question)
        except Exception as e:
            raise QueryFailedError(f"Embedding failed: {str(e)}")
        embedding_time_ms = (time.perf_counter() - embed_start) * 1000

        # -- Step 3: Search Qdrant with RBAC ------------------------
        retrieval_start = time.perf_counter()
        search_limit = max(self.top_k * 2, self.top_k)
        results = vector_store.search(
            query_vector=query_vector,
            user_roles=user_roles,
            limit=search_limit,
            score_threshold=self.score_threshold,
            department_filter=department_filter,
            topic_ancestor_id=topic_id if _settings.TOPIC_FILTER_ENABLED else None
        )
        retrieval_time_ms = (time.perf_counter() - retrieval_start) * 1000

        # -- Step 3b: Keep top-k chunks across documents ------------
        # Allow multiple documents to contribute context to avoid
        # dropping relevant header/name chunks from other resumes.

        # -- Step 4: Handle No Results ------------------------------
        if not results:
            total_time = (time.perf_counter() - total_start) * 1000
            no_result_answer = PromptBuilder.build_no_results_response(question)

            logger.info(
                "query_no_results",
                question_preview=question[:80],
                user_roles=user_roles,
                response_time_ms=round(total_time, 2)
            )

            return QueryResult(
                answer=no_result_answer,
                sources=[],
                chunks_retrieved=0,
                cache_hit=False,
                response_time_ms=total_time,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=0
            )

        # -- Step 4b: Prefer chunks containing the name query -------
        results = _rerank_results_by_name_query(question, results)
        results = _filter_results_by_score(results)
        if not results:
            total_time = (time.perf_counter() - total_start) * 1000
            no_result_answer = PromptBuilder.build_no_results_response(question)
            return QueryResult(
                answer=no_result_answer,
                sources=[],
                chunks_retrieved=0,
                cache_hit=False,
                response_time_ms=total_time,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=0
            )

        results = results[:self.top_k]

        results = _enforce_role_access(results, user_roles, user_department, user_hierarchy)
        if not results:
            total_time = (time.perf_counter() - total_start) * 1000
            no_result_answer = PromptBuilder.build_no_results_response(question)
            return QueryResult(
                answer=no_result_answer,
                sources=[],
                chunks_retrieved=0,
                cache_hit=False,
                response_time_ms=total_time,
                embedding_time_ms=embedding_time_ms,
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=0
            )

        # -- Step 4c: Multi-hop cross-document retrieval --------
        # If chunks reference identifiers (roll no, IDs), search
        # for related data in other documents.
        if _settings.MULTI_HOP_ENABLED:
            results = _multi_hop_retrieval(
                initial_results=results,
                question=question,
                user_roles=user_roles,
                score_threshold=self.score_threshold,
                department_filter=department_filter
            )
            # Re-apply RBAC to any new chunks from multi-hop
            results = _enforce_role_access(results, user_roles, user_department, user_hierarchy)

        exact_matches = _exact_match_results(search_question, results)
        if exact_matches:
            exact_sources = []
            for r in exact_matches:
                name = _clean_source_name(r.source_file)
                if name not in exact_sources:
                    exact_sources.append(name)

            if len(exact_sources) > 1:
                total_time = (time.perf_counter() - total_start) * 1000
                answer = PromptBuilder.build_disambiguation_response(
                    _extract_name_query(question),
                    exact_sources
                )
                return QueryResult(
                    answer=answer,
                    sources=exact_sources,
                    chunks_retrieved=len(exact_matches),
                    cache_hit=False,
                    response_time_ms=total_time,
                    embedding_time_ms=embedding_time_ms,
                    retrieval_time_ms=retrieval_time_ms,
                    llm_time_ms=0.0
                )

            results = exact_matches

        name_query = _extract_name_query(question)
        if name_query and len(name_query) >= 3:
            all_sources = []
            for r in results:
                name = _clean_source_name(r.source_file)
                if name not in all_sources:
                    all_sources.append(name)

            if len(all_sources) > 1:
                total_time = (time.perf_counter() - total_start) * 1000
                answer = PromptBuilder.build_disambiguation_response(
                    name_query,
                    all_sources
                )
                return QueryResult(
                    answer=answer,
                    sources=all_sources,
                    chunks_retrieved=len(results),
                    cache_hit=False,
                    response_time_ms=total_time,
                    embedding_time_ms=embedding_time_ms,
                    retrieval_time_ms=retrieval_time_ms,
                    llm_time_ms=0.0
                )

        logger.info(
            "query_retrieval_debug",
            top_k=len(results),
            samples=[
                {
                    "source": _clean_source_name(r.source_file),
                    "score": round(r.score, 4),
                    "preview": _preview(r.text)
                }
                for r in results[:5]
            ]
        )

        # -- Step 5: Build Prompt -----------------------------------
        # Trim context chunks to fit within the model's context window.
        # Reserve tokens for system prompt, question framing, and generation.
        available_chars = _settings.CONTEXT_CHAR_BUDGET
        context_chunks = []
        context_sources = []
        total_chars = 0
        for r in results:
            if total_chars + len(r.text) > available_chars:
                remaining = available_chars - total_chars
                if remaining > 200:
                    context_chunks.append(r.text[:remaining])
                    context_sources.append(r.source_file)
                break
            context_chunks.append(r.text)
            context_sources.append(r.source_file)
            total_chars += len(r.text)

        # Deduplicate sources from chunks actually used and clean display names
        used_sources = []
        for s in context_sources:
            clean = _clean_source_name(s)
            if clean not in used_sources:
                used_sources.append(clean)

        prompt = PromptBuilder.build_rag_prompt(
            question=question,
            context_chunks=context_chunks,
            sources=context_sources,
            user_name=user_name,
            conversation_history=conversation_history
        )

        disambiguation_note = _multiple_name_matches_note(
            question,
            results
        )

        # -- Step 6: Generate Answer -------------------------------
        llm_start = time.perf_counter()
        llm_client = _get_llm_client()
        llm_response = llm_client.generate(prompt=prompt)
        llm_time_ms = (time.perf_counter() - llm_start) * 1000

        answer = llm_response.content
        if disambiguation_note:
            answer = f"{disambiguation_note}\n\n{answer}"

        total_time = (time.perf_counter() - total_start) * 1000

        # -- Step 7: Cache Result ----------------------------------
        allowed_roles_union = sorted({
            role
            for r in results
            for role in (r.allowed_roles or [])
        })

        cache_payload = {
            "answer": answer,
            "sources": used_sources,
            "chunks_retrieved": len(context_chunks),
            "allowed_roles_union": allowed_roles_union
        }
        cache_service.queries.set(
            question,
            topic_id=topic_id,
            department=department_filter,
            result=cache_payload
        )

        result = QueryResult(
            answer=answer,
            sources=used_sources,
            chunks_retrieved=len(context_chunks),
            cache_hit=False,
            response_time_ms=total_time,
            embedding_time_ms=embedding_time_ms,
            retrieval_time_ms=retrieval_time_ms,
            llm_time_ms=llm_time_ms,
            retrieved_chunks=results
        )

        logger.info(
            "query_completed",
            question_preview=question[:80],
            chunks_retrieved=len(context_chunks),
            sources=used_sources,
            cache_hit=False,
            response_time_ms=round(total_time, 2),
            embedding_time_ms=round(embedding_time_ms, 2),
            retrieval_time_ms=round(retrieval_time_ms, 2),
            llm_time_ms=round(llm_time_ms, 2)
        )

        return result


# Module level singleton — uses config values for top_k and score_threshold
query_engine = QueryEngine()