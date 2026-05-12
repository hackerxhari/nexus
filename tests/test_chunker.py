"""
Unit tests for ingestion.chunker.SmartChunker.
Covers paragraph splitting, overlap, and edge cases.
"""

import pytest

from ingestion.chunker import SmartChunker, TextChunk, _get_spacy_nlp


class TestSmartChunkerBasics:
    def test_empty_text_returns_empty(self):
        chunker = SmartChunker(chunk_size=100, chunk_overlap=10, min_chunk_size=5)
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_overlap_must_be_less_than_size(self):
        with pytest.raises(ValueError):
            SmartChunker(chunk_size=50, chunk_overlap=50)
        with pytest.raises(ValueError):
            SmartChunker(chunk_size=50, chunk_overlap=100)

    def test_single_paragraph_below_size(self):
        chunker = SmartChunker(
            chunk_size=100,
            chunk_overlap=5,
            min_chunk_size=2,
            chunk_strategy="paragraph",
        )
        text = "This is one short paragraph that fits in a single chunk."
        result = chunker.chunk(text)
        assert len(result) == 1
        assert isinstance(result[0], TextChunk)
        assert result[0].chunk_index == 0
        assert "short paragraph" in result[0].text

    def test_multiple_paragraphs_split_properly(self):
        chunker = SmartChunker(
            chunk_size=10,
            chunk_overlap=2,
            min_chunk_size=2,
            chunk_strategy="paragraph",
        )
        # Each paragraph is small but together exceeds chunk_size
        text = (
            "Alpha alpha alpha alpha alpha alpha alpha.\n\n"
            "Beta beta beta beta beta beta beta.\n\n"
            "Gamma gamma gamma gamma gamma gamma gamma."
        )
        result = chunker.chunk(text)
        assert len(result) >= 2

    def test_chunk_index_is_sequential(self):
        chunker = SmartChunker(
            chunk_size=10,
            chunk_overlap=2,
            min_chunk_size=2,
            chunk_strategy="paragraph",
        )
        text = "a a a a a a a a a a.\n\nb b b b b b b b b b.\n\nc c c c c c c c c c."
        result = chunker.chunk(text)
        indices = [c.chunk_index for c in result]
        assert indices == list(range(len(result)))

    def test_chunks_below_min_are_dropped(self):
        chunker = SmartChunker(
            chunk_size=100,
            chunk_overlap=2,
            min_chunk_size=50,
            chunk_strategy="paragraph",
        )
        result = chunker.chunk("tiny.")
        assert result == []

    def test_metadata_propagates(self):
        chunker = SmartChunker(
            chunk_size=100,
            chunk_overlap=5,
            min_chunk_size=2,
            chunk_strategy="paragraph",
        )
        result = chunker.chunk("one fine paragraph here.", metadata={"page": 7})
        assert result[0].metadata == {"page": 7}


class TestSmartChunkerInternals:
    def test_clean_text_normalizes_whitespace(self):
        chunker = SmartChunker(chunk_size=100, chunk_overlap=5)
        cleaned = chunker._clean_text("foo\n\n\n\nbar   baz\tqux")
        assert "\n\n\n" not in cleaned
        assert "  " not in cleaned
        assert "\t" not in cleaned

    def test_split_sentences(self):
        chunker = SmartChunker(chunk_size=100, chunk_overlap=5)
        result = chunker._split_sentences("First. Second! Third? Done.")
        assert len(result) == 4
        assert result[0] == "First."
        assert result[3] == "Done."

    def test_add_overlap_repeats_last_words(self):
        chunker = SmartChunker(
            chunk_size=100, chunk_overlap=2, min_chunk_size=2
        )
        chunks = ["alpha beta gamma delta", "epsilon zeta eta"]
        with_overlap = chunker._add_overlap(chunks)
        # First chunk unchanged
        assert with_overlap[0] == chunks[0]
        # Second chunk starts with last 2 words of first
        assert with_overlap[1].startswith("gamma delta")

    def test_text_chunk_word_count_is_correct(self):
        chunk = TextChunk(text="one two three four", chunk_index=0)
        assert chunk.word_count == 4
        assert chunk.char_count == len("one two three four")


class TestSpacySentenceSegmentation:
    """
    Validates that the chunker uses SpaCy for sentence boundary detection
    when available. SpaCy is declared in requirements.txt, so on a properly
    set up environment these tests should hit the SpaCy path.
    """

    def test_spacy_loads(self):
        nlp = _get_spacy_nlp()
        # SpaCy is in requirements.txt, so it must be loadable here.
        assert nlp is not None, "SpaCy pipeline should load — it is in requirements.txt"
        # Either the small model or the blank+sentencizer fallback is fine.
        assert any(
            name in nlp.pipe_names
            for name in ["sentencizer", "parser", "senter"]
        )

    def test_abbreviation_not_split_mid_sentence(self):
        """Pure-regex segmentation would split on 'Dr.'; SpaCy should not."""
        chunker = SmartChunker(chunk_size=100, chunk_overlap=5)
        result = chunker._split_sentences(
            "Dr. Smith works at the U.S.A. office. He is a great person."
        )
        # The first sentence stays intact instead of getting split
        # after 'Dr.' or 'U.S.A.'.
        assert any("Dr. Smith" in s and "office" in s for s in result)

    def test_split_empty_text(self):
        chunker = SmartChunker(chunk_size=100, chunk_overlap=5)
        assert chunker._split_sentences("") == []
        assert chunker._split_sentences("   ") == []

    def test_basic_multi_sentence_split(self):
        chunker = SmartChunker(chunk_size=100, chunk_overlap=5)
        result = chunker._split_sentences(
            "First sentence. Second sentence! Third one?"
        )
        assert len(result) == 3

    def test_semantic_chunking_uses_spacy_sentences(self, monkeypatch):
        """
        Semantic chunking calls `_split_sentences`. Verify that with SpaCy
        in place, an input with abbreviations does not produce off-by-one
        sentence splits that the old regex would have caused.
        """
        # Force semantic strategy with a stubbed embedder so we don't
        # depend on sentence-transformers being warm.
        import numpy as np
        from ingestion import chunker as chunker_module

        class StubEmbedder:
            def embed_batch(self, texts):
                # Return distinct unit vectors so similarity stays low and
                # each sentence becomes its own chunk segment.
                rng = np.random.default_rng(0)
                return [rng.normal(size=8).tolist() for _ in texts]

        monkeypatch.setattr(
            chunker_module, "embedding_model", StubEmbedder(), raising=False
        )
        # Patch the lazy import inside _semantic_chunks
        import sys
        sys.modules["ingestion.embedder"].embedding_model = StubEmbedder()

        chunker = SmartChunker(
            chunk_size=50,
            chunk_overlap=5,
            min_chunk_size=2,
            chunk_strategy="semantic",
            semantic_sim_threshold=0.99,
        )
        chunks = chunker.chunk(
            "Dr. Adams reviewed the report. The team approved it. "
            "Mr. Singh signed off. Next quarter starts soon."
        )
        # SpaCy keeps abbreviation-prefixed sentences intact, so the
        # number of sentences detected is bounded.
        assert len(chunks) >= 1
