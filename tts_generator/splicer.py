"""Audio splicer for combining multi-speaker audio segments."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from pydub import AudioSegment as PydubSegment

from .parser import DialogueLine
from .providers.base import AudioSegment, TTSProvider
from .voices import VoiceManager


def group_dialogue_by_speaker_pairs(
    lines: list[DialogueLine],
    max_speakers: int = 2
) -> list[list[DialogueLine]]:
    """Group dialogue lines into segments with at most max_speakers unique speakers.

    This is necessary because Google TTS only supports 2 speakers per API call.
    We create segments that can be processed independently and then spliced together.
    """
    if not lines:
        return []

    groups = []
    current_group = []
    current_speakers = set()

    for line in lines:
        # Check if adding this speaker would exceed the limit
        if line.speaker not in current_speakers and len(current_speakers) >= max_speakers:
            # Start a new group
            if current_group:
                groups.append(current_group)
            current_group = [line]
            current_speakers = {line.speaker}
        else:
            current_group.append(line)
            current_speakers.add(line.speaker)

    # Add the last group
    if current_group:
        groups.append(current_group)

    return groups


def convert_raw_to_pydub(audio: AudioSegment) -> PydubSegment:
    """Convert raw audio data to pydub AudioSegment."""
    return PydubSegment(
        data=audio.data,
        sample_width=audio.sample_width,
        frame_rate=audio.sample_rate,
        channels=audio.channels,
    )


class AudioSplicer:
    """Handles generation and splicing of multi-speaker audio."""

    def __init__(
        self,
        provider: TTSProvider,
        voice_manager: VoiceManager,
        pause_ms: int = 300,
    ):
        """Initialize the audio splicer.

        Args:
            provider: The TTS provider to use.
            voice_manager: Voice manager with speaker-voice assignments.
            pause_ms: Pause duration between speaker changes in milliseconds.
        """
        self.provider = provider
        self.voice_manager = voice_manager
        self.pause_ms = pause_ms

    def generate_conversation(
        self,
        lines: list[DialogueLine],
        style_prompt: str | None = None,
        progress_callback: callable | None = None,
    ) -> PydubSegment:
        """Generate audio for an entire conversation, handling speaker limits.

        Args:
            lines: List of DialogueLine objects.
            style_prompt: Optional style direction for TTS.
            progress_callback: Optional callback(current, total) for progress updates.

        Returns:
            PydubSegment containing the complete audio.
        """
        if not lines:
            raise ValueError("No dialogue lines provided")

        # Assign voices to all speakers first
        for line in lines:
            self.voice_manager.assign_voice(line.speaker)

        # Group dialogue by speaker limits
        max_speakers = self.provider.max_speakers_per_call()
        groups = group_dialogue_by_speaker_pairs(lines, max_speakers)

        # Generate audio for each group
        audio_segments = []
        total_groups = len(groups)

        for i, group in enumerate(groups):
            if progress_callback:
                progress_callback(i + 1, total_groups)

            # Build dialogue tuples for the provider
            dialogue = [
                (line.speaker, self.voice_manager.get_voice(line.speaker), line.text)
                for line in group
            ]

            # Generate audio
            if len(set(line.speaker for line in group)) == 1:
                # Single speaker in this group
                speaker, voice, text = dialogue[0]
                # Combine all text for single speaker
                combined_text = " ".join(d[2] for d in dialogue)
                raw_audio = self.provider.generate_single_speaker(
                    combined_text, voice, style_prompt
                )
            else:
                # Multiple speakers
                raw_audio = self.provider.generate_multi_speaker(
                    dialogue, style_prompt
                )

            audio_segments.append(convert_raw_to_pydub(raw_audio))

        # Splice all segments together with pauses
        return self._splice_segments(audio_segments)

    def _splice_segments(self, segments: list[PydubSegment]) -> PydubSegment:
        """Splice audio segments together with pauses between them."""
        if not segments:
            raise ValueError("No segments to splice")

        if len(segments) == 1:
            return segments[0]

        # Create silence for pauses
        # Use the first segment's properties for the silence
        first = segments[0]
        silence = PydubSegment.silent(
            duration=self.pause_ms,
            frame_rate=first.frame_rate,
        )

        # Concatenate with pauses
        result = segments[0]
        for segment in segments[1:]:
            result = result + silence + segment

        return result

    def export(
        self,
        audio: PydubSegment,
        output_path: str | Path,
        format: str | None = None,
    ) -> Path:
        """Export audio to a file.

        Args:
            audio: The audio to export.
            output_path: Output file path.
            format: Output format (mp3, wav, etc.). Auto-detected from extension if None.

        Returns:
            Path to the exported file.
        """
        path = Path(output_path)

        if format is None:
            format = path.suffix.lstrip('.').lower()
            if not format:
                format = 'mp3'

        audio.export(str(path), format=format)
        return path
