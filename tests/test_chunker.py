"""Tests for the chunker module."""

import pytest

from tts_generator.parser import DialogueLine
from tts_generator.chunker import (
    Chunk,
    TextChunker,
    is_chapter_marker,
    CHAPTER_PATTERNS,
)


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        """Test creating a chunk."""
        lines = [DialogueLine("Alice", "Hello")]
        chunk = Chunk(index=0, lines=lines, speakers=["Alice"])

        assert chunk.index == 0
        assert len(chunk.lines) == 1
        assert chunk.speakers == ["Alice"]
        assert chunk.is_chapter_start is False
        assert chunk.chapter_title is None

    def test_chunk_text_size(self):
        """Test text_size property."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "World"),
        ]
        chunk = Chunk(index=0, lines=lines, speakers=["Alice", "Bob"])

        # "Hello" + "World" = 10 bytes
        assert chunk.text_size == 10

    def test_chunk_to_text(self):
        """Test to_text method."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "Hi there"),
        ]
        chunk = Chunk(index=0, lines=lines, speakers=["Alice", "Bob"])

        text = chunk.to_text()

        assert "Alice: Hello" in text
        assert "Bob: Hi there" in text


class TestIsChapterMarker:
    """Tests for is_chapter_marker function."""

    def test_chapter_with_number(self):
        """Test chapter markers with numbers."""
        is_chapter, title = is_chapter_marker("Chapter 1")
        assert is_chapter is True
        assert title == "Chapter 1"

    def test_chapter_with_roman_numerals(self):
        """Test chapter markers with roman numerals."""
        is_chapter, title = is_chapter_marker("Chapter IV")
        assert is_chapter is True

    def test_part_marker(self):
        """Test part markers."""
        is_chapter, title = is_chapter_marker("Part 2")
        assert is_chapter is True

    def test_section_marker(self):
        """Test section markers."""
        is_chapter, title = is_chapter_marker("Section 3")
        assert is_chapter is True

    def test_markdown_header(self):
        """Test markdown headers."""
        is_chapter, title = is_chapter_marker("# Introduction")
        assert is_chapter is True

        is_chapter, title = is_chapter_marker("## Chapter One")
        assert is_chapter is True

    def test_divider(self):
        """Test divider markers."""
        is_chapter, _ = is_chapter_marker("---")
        assert is_chapter is True

        is_chapter, _ = is_chapter_marker("***")
        assert is_chapter is True

    def test_regular_text_not_chapter(self):
        """Test that regular text is not detected as chapter."""
        is_chapter, _ = is_chapter_marker("Hello, how are you?")
        assert is_chapter is False

    def test_case_insensitive(self):
        """Test that chapter detection is case insensitive."""
        is_chapter, _ = is_chapter_marker("CHAPTER 1")
        assert is_chapter is True

        is_chapter, _ = is_chapter_marker("chapter 1")
        assert is_chapter is True


class TestTextChunker:
    """Tests for TextChunker class."""

    def test_empty_input(self):
        """Test chunking empty input."""
        chunker = TextChunker()
        chunks = chunker.chunk([])
        assert chunks == []

    def test_single_chunk(self):
        """Test small input that fits in one chunk."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "Hi"),
        ]
        chunker = TextChunker(max_bytes=1000)
        chunks = chunker.chunk(lines)

        assert len(chunks) == 1
        assert len(chunks[0].lines) == 2

    def test_split_by_size(self):
        """Test splitting when size limit is exceeded."""
        lines = [
            DialogueLine("Alice", "A" * 100),
            DialogueLine("Alice", "B" * 100),
            DialogueLine("Alice", "C" * 100),
        ]
        # Small max_bytes to force splitting
        chunker = TextChunker(max_bytes=150)
        chunks = chunker.chunk(lines)

        assert len(chunks) > 1

    def test_split_by_speakers(self):
        """Test splitting when speaker limit is exceeded."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "Hi"),
            DialogueLine("Carol", "Hey"),  # Third speaker should trigger split
        ]
        chunker = TextChunker(max_bytes=10000, max_speakers_per_chunk=2)
        chunks = chunker.chunk(lines)

        assert len(chunks) == 2
        # First chunk should have 2 speakers
        assert len(chunks[0].speakers) <= 2

    def test_chapter_starts_new_chunk(self):
        """Test that chapter markers start new chunks."""
        lines = [
            DialogueLine("Narrator", "Once upon a time..."),
            DialogueLine("Narrator", "Chapter 2"),
            DialogueLine("Narrator", "The story continues..."),
        ]
        chunker = TextChunker(max_bytes=10000)
        chunks = chunker.chunk(lines)

        assert len(chunks) == 2
        # Second chunk should be marked as chapter start
        assert chunks[1].is_chapter_start is True

    def test_chunk_indices_sequential(self):
        """Test that chunk indices are sequential."""
        lines = [
            DialogueLine("Alice", "A" * 100),
            DialogueLine("Bob", "B" * 100),
            DialogueLine("Carol", "C" * 100),
        ]
        chunker = TextChunker(max_bytes=150, max_speakers_per_chunk=2)
        chunks = chunker.chunk(lines)

        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_estimate_duration(self):
        """Test duration estimation."""
        lines = [
            DialogueLine("Alice", "word " * 150),  # 150 words
        ]
        chunker = TextChunker()
        chunks = chunker.chunk(lines)

        # At 150 words per minute, 150 words = 60 seconds
        duration = chunker.estimate_duration(chunks, words_per_minute=150)
        assert 55 <= duration <= 65  # Allow some tolerance

    def test_get_stats(self):
        """Test get_stats method."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "Hi there"),
            DialogueLine("Alice", "How are you?"),
        ]
        chunker = TextChunker()
        chunks = chunker.chunk(lines)
        stats = chunker.get_stats(chunks)

        assert stats["chunks"] == 1
        assert stats["lines"] == 3
        assert stats["speakers"] == 2
        assert "Alice" in stats["speaker_names"]
        assert "Bob" in stats["speaker_names"]

    def test_get_stats_empty(self):
        """Test get_stats with empty chunks."""
        chunker = TextChunker()
        stats = chunker.get_stats([])

        assert stats["chunks"] == 0
        assert stats["lines"] == 0

    def test_speakers_preserved_in_chunk(self):
        """Test that speaker info is preserved in chunks."""
        lines = [
            DialogueLine("Alice", "Hello"),
            DialogueLine("Bob", "Hi"),
        ]
        chunker = TextChunker()
        chunks = chunker.chunk(lines)

        assert "Alice" in chunks[0].speakers
        assert "Bob" in chunks[0].speakers
