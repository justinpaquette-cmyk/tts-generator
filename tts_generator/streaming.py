"""Streaming audio generation for large files."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment as PydubSegment

from .chunker import Chunk
from .providers.base import TTSProvider
from .splicer import convert_raw_to_pydub
from .voices import VoiceManager


class StreamingGenerator:
    """Generates audio chunk-by-chunk, streaming to disk."""

    def __init__(
        self,
        provider: TTSProvider,
        voice_manager: VoiceManager,
        output_path: str | Path,
        pause_ms: int = 300,
        chapter_pause_ms: int = 2000,
    ):
        """Initialize streaming generator.

        Args:
            provider: TTS provider to use
            voice_manager: Voice manager with speaker assignments
            output_path: Path for output audio file
            pause_ms: Pause between regular chunks (ms)
            chapter_pause_ms: Pause at chapter breaks (ms)
        """
        self.provider = provider
        self.voice_manager = voice_manager
        self.output_path = Path(output_path)
        self.pause_ms = pause_ms
        self.chapter_pause_ms = chapter_pause_ms

        # State file for resume capability
        self.state_path = self.output_path.with_suffix('.state.json')

        # Track generation stats
        self.stats = {
            "chunks_completed": 0,
            "total_duration_ms": 0,
            "start_time": None,
            "errors": [],
        }

    def generate(
        self,
        chunks: list[Chunk],
        progress_callback: callable | None = None,
        resume: bool = False,
    ) -> Path:
        """Generate audio from chunks, streaming to disk.

        Args:
            chunks: List of text chunks to generate
            progress_callback: Optional callback(current, total, stats) for progress
            resume: Whether to resume from saved state

        Returns:
            Path to generated audio file
        """
        if not chunks:
            raise ValueError("No chunks provided")

        # Load or initialize state
        start_idx = 0
        if resume and self.state_path.exists():
            state = self._load_state()
            start_idx = state.get("completed_chunks", 0)
            print(f"Resuming from chunk {start_idx + 1}/{len(chunks)}")
        else:
            # Start fresh - remove any existing output
            if self.output_path.exists():
                self.output_path.unlink()

        self.stats["start_time"] = time.time()

        # Process each chunk
        for i, chunk in enumerate(chunks[start_idx:], start=start_idx):
            try:
                # Generate audio for this chunk
                audio = self._generate_chunk(chunk)

                # Add pause between chunks
                if i > 0:
                    pause_duration = self.chapter_pause_ms if chunk.is_chapter_start else self.pause_ms
                    silence = PydubSegment.silent(duration=pause_duration, frame_rate=24000)
                    audio = silence + audio

                # Append to output file
                self._append_audio(audio)

                # Update stats
                self.stats["chunks_completed"] = i + 1
                self.stats["total_duration_ms"] += len(audio)

                # Save state for resume
                self._save_state(i + 1, len(chunks))

                # Progress callback
                if progress_callback:
                    progress_callback(i + 1, len(chunks), self.stats.copy())

            except Exception as e:
                self.stats["errors"].append({
                    "chunk": i,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
                # Save state so we can resume
                self._save_state(i, len(chunks))
                raise

        # Clean up state file on completion
        self._cleanup_state()

        return self.output_path

    def _generate_chunk(self, chunk: Chunk) -> PydubSegment:
        """Generate audio for a single chunk."""
        # Build dialogue tuples
        dialogue = [
            (line.speaker, self.voice_manager.get_voice(line.speaker), line.text)
            for line in chunk.lines
        ]

        # Generate based on number of speakers
        unique_speakers = set(line.speaker for line in chunk.lines)

        if len(unique_speakers) == 1:
            # Single speaker - combine all text
            speaker, voice, _ = dialogue[0]
            combined_text = " ".join(d[2] for d in dialogue)
            raw_audio = self.provider.generate_single_speaker(combined_text, voice)
        else:
            # Multiple speakers
            raw_audio = self.provider.generate_multi_speaker(dialogue)

        return convert_raw_to_pydub(raw_audio)

    def _append_audio(self, audio: PydubSegment):
        """Append audio segment to output file."""
        if self.output_path.exists():
            # Load existing and append
            existing = PydubSegment.from_wav(str(self.output_path))
            combined = existing + audio
            combined.export(str(self.output_path), format="wav")
        else:
            # First chunk - just export
            audio.export(str(self.output_path), format="wav")

    def _save_state(self, completed: int, total: int):
        """Save generation state for resume capability."""
        state = {
            "output_path": str(self.output_path),
            "completed_chunks": completed,
            "total_chunks": total,
            "voice_assignments": self.voice_manager.get_all_assignments(),
            "stats": self.stats,
            "updated_at": datetime.now().isoformat(),
        }

        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> dict:
        """Load saved state."""
        with open(self.state_path) as f:
            return json.load(f)

    def _cleanup_state(self):
        """Remove state file after successful completion."""
        if self.state_path.exists():
            self.state_path.unlink()

    def get_progress_string(self, current: int, total: int) -> str:
        """Get formatted progress string."""
        percent = (current / total) * 100
        elapsed = time.time() - (self.stats.get("start_time") or time.time())

        if current > 0:
            eta_seconds = (elapsed / current) * (total - current)
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            eta_str = f"{eta_min}:{eta_sec:02d}"
        else:
            eta_str = "calculating..."

        duration_ms = self.stats.get("total_duration_ms", 0)
        duration_min = int((duration_ms / 1000) // 60)
        duration_sec = int((duration_ms / 1000) % 60)

        return (
            f"[{current}/{total}] {percent:.1f}% | "
            f"Duration: {duration_min}:{duration_sec:02d} | "
            f"ETA: {eta_str}"
        )
