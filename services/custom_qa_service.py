"""
Custom Q&A matching service.
Checks incoming questions against admin-defined Q&A entries using
embedding similarity for fuzzy matching. Returns instant answers
when a match is found, completely bypassing the RAG pipeline.

Matching strategy (in order):
  1. Exact string match (instant)
  2. Substring match (instant)
  3. Keyword overlap match (fast)
  4. Embedding similarity vs patterns (semantic)
  5. Embedding similarity vs answer content (semantic fallback)
"""

from typing import Any, Dict, List, Optional, Set

import numpy as np
from sqlalchemy.orm import Session

from core.config import get_settings
from core.logger import get_logger, TimedOperation
from db.repositories.custom_qa_repo import CustomQARepository
from ingestion.embedder import embedding_model

logger = get_logger(__name__)
settings = get_settings()

# Common stop words to ignore during keyword matching
_STOP_WORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "about",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "it", "its", "my", "me", "i", "you", "your", "we", "our",
    "they", "them", "their", "how", "when", "where", "why", "if", "or",
    "and", "but", "not", "no", "so", "up", "out", "just", "than", "then",
    "also", "very", "much", "more", "most", "some", "any", "all",
    "tell", "give", "please", "explain", "describe",
}


class CustomQAService:
    """
    Matches incoming questions against custom Q&A entries.
    Uses a multi-strategy matching approach for maximum recall:
      - Pattern matching (exact, substring, keyword)
      - Embedding similarity against BOTH patterns AND answer content
    """

    def __init__(self, db: Session):
        self.repo = CustomQARepository(db)
        self.threshold = settings.CUSTOM_QA_SIMILARITY_THRESHOLD

    def find_match(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Check if a question matches any custom Q&A entry.
        Returns the answer dict if matched, None otherwise.
        """
        if not question or not question.strip():
            return None

        question_clean = question.strip()
        question_lower = question_clean.lower()

        try:
            entries = self.repo.get_all_active()
            if not entries:
                return None

            # ── Phase 1: Exact match ──────────────────────────
            for entry in entries:
                patterns = entry.question_patterns or []
                for pattern in patterns:
                    pattern_lower = pattern.strip().lower()
                    if not pattern_lower:
                        continue
                    if question_lower == pattern_lower:
                        logger.info(
                            "custom_qa_exact_match",
                            qa_id=entry.id,
                            pattern=pattern[:50]
                        )
                        return self._make_result(entry, "exact")

            # ── Phase 2: Substring match ──────────────────────
            for entry in entries:
                patterns = entry.question_patterns or []
                for pattern in patterns:
                    pattern_lower = pattern.strip().lower()
                    if not pattern_lower or len(pattern_lower) < 5:
                        continue
                    if (
                        pattern_lower in question_lower
                        or question_lower in pattern_lower
                    ):
                        logger.info(
                            "custom_qa_substring_match",
                            qa_id=entry.id,
                            pattern=pattern[:50]
                        )
                        return self._make_result(entry, "substring")

            # ── Phase 3: Keyword overlap match ────────────────
            question_keywords = self._extract_keywords(question_lower)
            if question_keywords:
                best_overlap_entry = None
                best_overlap_ratio = 0.0

                for entry in entries:
                    patterns = entry.question_patterns or []
                    for pattern in patterns:
                        pattern_keywords = self._extract_keywords(
                            pattern.strip().lower()
                        )
                        if not pattern_keywords:
                            continue

                        # Compute Jaccard-like overlap
                        intersection = question_keywords & pattern_keywords
                        union = question_keywords | pattern_keywords
                        if not union:
                            continue
                        overlap = len(intersection) / len(union)

                        # Also check: what fraction of pattern keywords
                        # appear in the question (recall)
                        recall = (
                            len(intersection) / len(pattern_keywords)
                            if pattern_keywords else 0
                        )

                        # Combined score — weighted toward recall
                        combined = 0.4 * overlap + 0.6 * recall

                        if combined > best_overlap_ratio:
                            best_overlap_ratio = combined
                            best_overlap_entry = entry

                if best_overlap_entry and best_overlap_ratio >= 0.6:
                    logger.info(
                        "custom_qa_keyword_match",
                        qa_id=best_overlap_entry.id,
                        overlap=round(best_overlap_ratio, 4)
                    )
                    return self._make_result(
                        best_overlap_entry, "keyword",
                        score=round(best_overlap_ratio, 4)
                    )

            # ── Phase 4: Embedding similarity vs patterns ─────
            with TimedOperation(logger, "custom_qa_embedding_match"):
                question_embedding = embedding_model.embed_text(question_clean)
                best_match = None
                best_score = 0.0

                for entry in entries:
                    # Check against each pattern
                    patterns = entry.question_patterns or []
                    for pattern in patterns:
                        if not pattern or not pattern.strip():
                            continue
                        pattern_embedding = embedding_model.embed_text(
                            pattern.strip()
                        )
                        score = self._cosine_similarity(
                            question_embedding, pattern_embedding
                        )
                        if score > best_score:
                            best_score = score
                            best_match = entry

                if best_match and best_score >= self.threshold:
                    logger.info(
                        "custom_qa_embedding_pattern_match",
                        qa_id=best_match.id,
                        score=round(best_score, 4),
                        threshold=self.threshold
                    )
                    return self._make_result(
                        best_match, "embedding_pattern",
                        score=round(best_score, 4)
                    )

                # ── Phase 5: Embedding similarity vs answer ───
                # If question didn't match patterns, check if it's
                # semantically similar to the answer content itself.
                # Example: Pattern="What is my name?" Answer="Your name is John"
                # Query: "How will people address me?" → similar to the answer
                answer_best_match = None
                answer_best_score = 0.0
                # Use a slightly lower threshold for answer matching
                answer_threshold = max(self.threshold - 0.10, 0.45)

                for entry in entries:
                    answer_text = entry.answer or ""
                    if not answer_text.strip():
                        continue

                    # Embed a combined context: patterns + answer
                    # This gives the model more semantic signal
                    patterns = entry.question_patterns or []
                    combined_text = " ".join(
                        [p.strip() for p in patterns if p.strip()]
                        + [answer_text.strip()[:200]]
                    )
                    combined_embedding = embedding_model.embed_text(
                        combined_text
                    )
                    score = self._cosine_similarity(
                        question_embedding, combined_embedding
                    )

                    if score > answer_best_score:
                        answer_best_score = score
                        answer_best_match = entry

                if answer_best_match and answer_best_score >= answer_threshold:
                    logger.info(
                        "custom_qa_embedding_answer_match",
                        qa_id=answer_best_match.id,
                        score=round(answer_best_score, 4),
                        threshold=answer_threshold
                    )
                    return self._make_result(
                        answer_best_match, "embedding_answer",
                        score=round(answer_best_score, 4)
                    )

            return None

        except Exception as e:
            logger.warning("custom_qa_match_error", error=str(e))
            return None

    @staticmethod
    def _make_result(
        entry,
        match_type: str,
        score: Optional[float] = None
    ) -> Dict[str, Any]:
        """Build a standard match result dict."""
        result = {
            "id": entry.id,
            "answer": entry.answer,
            "category": entry.category,
            "match_type": match_type
        }
        if score is not None:
            result["score"] = score
        return result

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """
        Extract meaningful keywords from text, stripping stop words.
        Returns a set of lowercase keyword stems.
        """
        words = set()
        for word in text.split():
            # Strip punctuation
            clean = word.strip(".,!?;:'\"()-[]{}/@#$%^&*")
            if clean and len(clean) >= 2 and clean not in _STOP_WORDS:
                words.add(clean)
        return words

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        try:
            a = np.array(vec_a, dtype=np.float32)
            b = np.array(vec_b, dtype=np.float32)
            dot = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(dot / (norm_a * norm_b))
        except Exception:
            return 0.0
