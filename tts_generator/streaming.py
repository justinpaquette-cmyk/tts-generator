"""Streaming audio generation for large files."""

from __future__ import annotations

import json
import time
import wave
from datetime import datetime
from pathlib import Path

from pydub import AudioSegment as PydubSegment

from .chunker import Chunk
from .providers.base import TTSProvider
from .splicer import convert_raw_to_pydub
from .voices import VoiceManager


# Target audio format for consistency (matches Google TTS output)
TARGET_SAMPLE_RATE = 24000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit


def normalize_audio(audio: PydubSegment) -> PydubSegment:
    """Normalize audio to target format for consistent concatenation.

    Ensures all audio chunks have the same sample rate, channels, and
    sample width to prevent audio corruption at boundaries.
    """
    # Convert to target format if needed
    if audio.frame_rate != TARGET_SAMPLE_RATE:
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
    if audio.channels != TARGET_CHANNELS:
        audio = audio.set_channels(TARGET_CHANNELS)
    if audio.sample_width != TARGET_SAMPLE_WIDTH:
        audio = audio.set_sample_width(TARGET_SAMPLE_WIDTH)
    return audio


def crossfade_segments(seg1: PydubSegment, seg2: PydubSegment, crossfade_ms: int = 25) -> PydubSegment:
    """Join two audio segments with a crossfade to prevent clicking artifacts.

    Args:
        seg1: First audio segment
        seg2: Second audio segment
        crossfade_ms: Duration of crossfade in milliseconds (default: 25ms)

    Returns:
        Combined audio segment with smooth transition
    """
    if crossfade_ms <= 0:
        return seg1 + seg2

    # Ensure crossfade doesn't exceed segment lengths
    crossfade_ms = min(crossfade_ms, len(seg1), len(seg2))

    if crossfade_ms < 5:
        # Too short for meaningful crossfade
        return seg1 + seg2

    return seg1.append(seg2, crossfade=crossfade_ms)


class StreamingGenerator:
    """Generates audio chunk-by-chunk, streaming to disk."""

    def __init__(
        self,
        provider: TTSProvider,
        voice_manager: VoiceManager,
        output_path: str | Path,
        pause_ms: int = 300,
        chapter_pause_ms: int = 2000,
        state_save_interval: int = 5,
        crossfade_ms: int = 25,
    ):
        """Initialize streaming generator.

        Args:
            provider: TTS provider to use
            voice_manager: Voice manager with speaker assignments
            output_path: Path for output audio file
            pause_ms: Pause between regular chunks (ms)
            chapter_pause_ms: Pause at chapter breaks (ms)
            state_save_interval: Save state every N chunks (default: 5)
            crossfade_ms: Crossfade duration at chunk boundaries (default: 25ms)
        """
        self.provider = provider
        self.voice_manager = voice_manager
        self.output_path = Path(output_path)
        self.pause_ms = pause_ms
        self.chapter_pause_ms = chapter_pause_ms
        self.state_save_interval = state_save_interval
        self.crossfade_ms = crossfade_ms

        # State file for resume capability
        self.state_path = self.output_path.with_suffix('.state.json')

        # Track audio parameters for consistency checking
        self._audio_params = None

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

                # Normalize audio to ensure consistent format
                audio = normalize_audio(audio)

                # Add pause between chunks (with crossfade for smooth transitions)
                if i > 0:
                    pause_duration = self.chapter_pause_ms if chunk.is_chapter_start else self.pause_ms
                    silence = PydubSegment.silent(
                        duration=pause_duration,
                        frame_rate=TARGET_SAMPLE_RATE,
                    )
                    # Prepend silence, then we'll crossfade when appending
                    audio = silence + audio

                # Append to output file with crossfade
                self._append_audio(audio, use_crossfade=(i > 0))

                # Update stats
                self.stats["chunks_completed"] = i + 1
                self.stats["total_duration_ms"] += len(audio)

                # Save state periodically (every N chunks, or on last chunk)
                is_last_chunk = (i + 1) == len(chunks)
                should_save = (i + 1) % self.state_save_interval == 0 or is_last_chunk
                if should_save:
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

    def _append_audio(self, audio: PydubSegment, use_crossfade: bool = False):
        """Append audio segment to output file with optional crossfade.

        For the first chunk, creates a new WAV file. For subsequent chunks,
        loads the existing audio, applies crossfade at the boundary, and
        re-exports. This ensures proper audio alignment and prevents
        artifacts at chunk boundaries.

        Args:
            audio: The audio segment to append
            use_crossfade: Whether to apply crossfade at the boundary
        """
        if not self.output_path.exists():
            # First chunk - create new file with proper WAV header
            # Store the audio parameters for consistency checking
            self._audio_params = {
                'frame_rate': audio.frame_rate,
                'channels': audio.channels,
                'sample_width': audio.sample_width,
            }
            audio.export(str(self.output_path), format="wav")
        else:
            # Load existing audio
            existing = PydubSegment.from_wav(str(self.output_path))

            # Verify format consistency (should be guaranteed by normalize_audio,
            # but check anyway for safety)
            if (existing.frame_rate != audio.frame_rate or
                existing.channels != audio.channels or
                existing.sample_width != audio.sample_width):
                # Normalize the new audio to match existing
                audio = audio.set_frame_rate(existing.frame_rate)
                audio = audio.set_channels(existing.channels)
                audio = audio.set_sample_width(existing.sample_width)

            # Combine with crossfade for smooth transition
            if use_crossfade and self.crossfade_ms > 0:
                combined = crossfade_segments(existing, audio, self.crossfade_ms)
            else:
                combined = existing + audio

            # Export combined audio
            combined.export(str(self.output_path), format="wav")

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
