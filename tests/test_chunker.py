"""
Unit tests for ingestion.chunker.SmartChunker.
Covers paragraph splitting, overlap, and edge cases.
"""

import pytest

from ingestion.chunker import SmartChunker, TextChunk


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
