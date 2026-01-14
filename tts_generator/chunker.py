"""Text chunking for large audio generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import DialogueLine, get_unique_speakers


@dataclass
class Chunk:
    """A chunk of dialogue for generation."""
    index: int
    lines: list[DialogueLine]
    speakers: list[str] = field(default_factory=list)
    is_chapter_start: bool = False
    chapter_title: str | None = None

    @property
    def text_size(self) -> int:
        """Get approximate byte size of text content."""
        return sum(len(line.text.encode('utf-8')) for line in self.lines)

    def to_text(self) -> str:
        """Convert chunk to text format."""
        return "\n".join(f"{line.speaker}: {line.text}" for line in self.lines)


# Chapter detection patterns
CHAPTER_PATTERNS = [
    re.compile(r'^(chapter|part|section)\s+(\d+|[ivxlcdm]+)', re.IGNORECASE),
    re.compile(r'^(chapter|part|section)\s+\w+:', re.IGNORECASE),
    re.compile(r'^#{1,3}\s+'),  # Markdown headers
    re.compile(r'^[*\-=]{3,}$'),  # Dividers
]


def is_chapter_marker(text: str) -> tuple[bool, str | None]:
    """Check if text is a chapter marker and extract title."""
    text = text.strip()

    for pattern in CHAPTER_PATTERNS:
        if pattern.match(text):
            return True, text

    return False, None


class TextChunker:
    """Splits dialogue into chunks for streaming generation."""

    def __init__(
        self,
        max_bytes: int = 3500,
        max_speakers_per_chunk: int = 2,
        chapter_pause_ms: int = 2000,
    ):
        """Initialize chunker.

        Args:
            max_bytes: Maximum bytes per chunk (leave buffer under 4KB API limit)
            max_speakers_per_chunk: Max speakers per chunk (Google limit is 2)
            chapter_pause_ms: Pause duration at chapter breaks
        """
        self.max_bytes = max_bytes
        self.max_speakers = max_speakers_per_chunk
        self.chapter_pause_ms = chapter_pause_ms

    def chunk(self, lines: list[DialogueLine]) -> list[Chunk]:
        """Split dialogue lines into chunks.

        Strategy:
        1. Group by speaker pairs (max 2 per chunk for Google API)
        2. Split when text size exceeds max_bytes
        3. Start new chunk at chapter markers
        4. Preserve natural conversation flow
        """
        if not lines:
            return []

        chunks = []
        current_lines = []
        current_speakers = set()
        current_size = 0
        chunk_index = 0
        # Track chapter info for current chunk
        current_is_chapter_start = False
        current_chapter_title = None

        for line in lines:
            line_size = len(line.text.encode('utf-8')) + len(line.speaker.encode('utf-8')) + 2

            # Check for chapter marker
            is_chapter, chapter_title = is_chapter_marker(line.text)

            # Decide if we need to start a new chunk
            needs_new_chunk = False

            if is_chapter and current_lines:
                needs_new_chunk = True
            elif line.speaker not in current_speakers and len(current_speakers) >= self.max_speakers:
                needs_new_chunk = True
            elif current_size + line_size > self.max_bytes and current_lines:
                needs_new_chunk = True

            # Save current chunk if needed
            if needs_new_chunk:
                chunks.append(Chunk(
                    index=chunk_index,
                    lines=current_lines,
                    speakers=list(current_speakers),
                    is_chapter_start=current_is_chapter_start,
                    chapter_title=current_chapter_title,
                ))
                chunk_index += 1
                current_lines = []
                current_speakers = set()
                current_size = 0
                # Reset chapter tracking for new chunk
                current_is_chapter_start = False
                current_chapter_title = None

            # Add line to current chunk
            current_lines.append(line)
            current_speakers.add(line.speaker)
            current_size += line_size

            # Mark chapter start if this is first line of chunk and is a chapter marker
            if is_chapter and len(current_lines) == 1:
                current_is_chapter_start = True
                current_chapter_title = chapter_title

        # Don't forget the last chunk
        if current_lines:
            chunks.append(Chunk(
                index=chunk_index,
                lines=current_lines,
                speakers=list(current_speakers),
                is_chapter_start=current_is_chapter_start,
                chapter_title=current_chapter_title,
            ))

        return chunks

    def estimate_duration(self, chunks: list[Chunk], words_per_minute: int = 150) -> float:
        """Estimate total audio duration in seconds.

        Args:
            chunks: List of chunks
            words_per_minute: Average speaking rate

        Returns:
            Estimated duration in seconds
        """
        total_words = 0
        for chunk in chunks:
            for line in chunk.lines:
                total_words += len(line.text.split())

        return (total_words / words_per_minute) * 60

    def get_stats(self, chunks: list[Chunk]) -> dict:
        """Get statistics about the chunks."""
        if not chunks:
            return {"chunks": 0, "lines": 0, "speakers": 0, "estimated_duration": 0}

        all_speakers = set()
        total_lines = 0
        total_bytes = 0

        for chunk in chunks:
            total_lines += len(chunk.lines)
            total_bytes += chunk.text_size
            all_speakers.update(chunk.speakers)

        return {
            "chunks": len(chunks),
            "lines": total_lines,
            "speakers": len(all_speakers),
            "speaker_names": sorted(all_speakers),
            "total_bytes": total_bytes,
            "estimated_duration_sec": self.estimate_duration(chunks),
            "estimated_duration_min": self.estimate_duration(chunks) / 60,
        }
