"""
Smart text chunker for Nexus.
Paragraph-aware chunking with overlap.
Preserves sentence boundaries — never cuts mid-sentence.
"""

import re

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TextChunk:
    """A single chunk of text ready for embedding."""
    text: str
    chunk_index: int
    word_count: int = 0
    char_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.word_count = len(self.text.split())
        self.char_count = len(self.text)


class SmartChunker:
    """
    Paragraph-aware text chunker.

    Strategy:
    1. Split on paragraph boundaries first
    2. If paragraph is too large, split on sentence boundaries
    3. Merge small paragraphs together up to chunk_size
    4. Add overlap between chunks to preserve context
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: int = 20,
        chunk_strategy: Optional[str] = None,
        semantic_sim_threshold: Optional[float] = None
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.min_chunk_size = min_chunk_size
        self.chunk_strategy = (
            chunk_strategy or settings.CHUNK_STRATEGY
        ).lower()
        self.semantic_sim_threshold = (
            semantic_sim_threshold
            if semantic_sim_threshold is not None
            else settings.SEMANTIC_SIM_THRESHOLD
        )

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    def chunk(
        self,
        text: str,
        metadata: Optional[dict] = None
    ) -> List[TextChunk]:
        """
        Main chunking method.
        Returns list of TextChunk objects ready for embedding.
        """
        if not text or not text.strip():
            logger.warning("chunker_empty_text")
            return []

        # Clean text
        text = self._clean_text(text)

        if self.chunk_strategy == "semantic":
            raw_chunks = self._semantic_chunks(text)
            chunks_with_overlap = raw_chunks
        else:
            # Split into paragraphs
            paragraphs = self._split_paragraphs(text)

            # Build chunks from paragraphs
            raw_chunks = self._build_chunks(paragraphs)

            # Add overlap
            chunks_with_overlap = self._add_overlap(raw_chunks)

        # Convert to TextChunk objects
        result = []
        for idx, chunk_text in enumerate(chunks_with_overlap):
            if len(chunk_text.split()) < self.min_chunk_size:
                continue  # Skip tiny chunks

            result.append(TextChunk(
                text=chunk_text.strip(),
                chunk_index=idx,
                metadata=metadata or {}
            ))

        logger.debug(
            "chunking_completed",
            input_words=len(text.split()),
            output_chunks=len(result),
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap
        )

        return result

    def _clean_text(self, text: str) -> str:
        """Clean text before chunking."""
        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\t", " ", text)
        return text.strip()

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs on double newlines."""
        paragraphs = re.split(r"\n\n+", text)
        result = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            words = para.split()
            if len(words) > self.chunk_size:
                # Paragraph too large — split into sentences
                sentences = self._split_sentences(para)
                result.extend(sentences)
            else:
                result.append(para)

        return result

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Split on sentence-ending punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _build_chunks(self, paragraphs: List[str]) -> List[str]:
        """
        Merge paragraphs into chunks respecting chunk_size.
        Never breaks a paragraph mid-way unless it exceeds chunk_size.
        """
        chunks = []
        current_words = []
        current_size = 0

        for para in paragraphs:
            para_words = para.split()
            para_size = len(para_words)

            if current_size + para_size > self.chunk_size and current_words:
                # Current chunk is full — save it
                chunks.append(" ".join(current_words))
                current_words = []
                current_size = 0

            current_words.extend(para_words)
            current_size += para_size

        # Don't forget the last chunk
        if current_words:
            chunks.append(" ".join(current_words))

        return chunks

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """
        Add overlap between consecutive chunks.
        Takes last N words of previous chunk and prepends to current.
        This ensures context isn't lost at chunk boundaries.
        """
        if len(chunks) <= 1:
            return chunks

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_words = chunks[i - 1].split()
            overlap_words = prev_words[-self.chunk_overlap:]
            overlap_text = " ".join(overlap_words)
            result.append(f"{overlap_text} {chunks[i]}")

        return result

    def _semantic_chunks(self, text: str) -> List[str]:
        """
        Semantic chunking using sentence embeddings.
        Starts a new chunk when semantic similarity drops.
        """
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            return sentences

        from ingestion.embedder import embedding_model

        vectors = embedding_model.embed_batch(sentences)

        chunks = []
        current_sentences = [sentences[0]]
        current_vector = np.array(vectors[0], dtype=np.float32)
        current_words = len(sentences[0].split())

        for i in range(1, len(sentences)):
            sent = sentences[i]
            sent_words = len(sent.split())
            sent_vector = np.array(vectors[i], dtype=np.float32)

            similarity = float(np.dot(current_vector, sent_vector))
            would_exceed = current_words + sent_words > self.chunk_size
            split_on_similarity = (
                similarity < self.semantic_sim_threshold
                and current_words >= self.min_chunk_size
            )

            if would_exceed or split_on_similarity:
                chunks.append(" ".join(current_sentences).strip())
                current_sentences = [sent]
                current_vector = sent_vector
                current_words = sent_words
                continue

            current_sentences.append(sent)
            current_words += sent_words
            current_vector = self._avg_norm(current_vector, sent_vector)

        if current_sentences:
            chunks.append(" ".join(current_sentences).strip())

        return chunks

    def _avg_norm(
        self,
        a: np.ndarray,
        b: np.ndarray
    ) -> np.ndarray:
        """Average two vectors and normalize."""
        avg = (a + b) / 2.0
        norm = np.linalg.norm(avg)
        if norm == 0:
            return avg
        return avg / norm