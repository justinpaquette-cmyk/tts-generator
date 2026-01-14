"""Base class for TTS providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AudioSegment:
    """A segment of generated audio."""
    data: bytes
    sample_rate: int = 24000
    channels: int = 1
    sample_width: int = 2  # 16-bit


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def generate_single_speaker(
        self,
        text: str,
        voice: str,
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for a single speaker.

        Args:
            text: The text to convert to speech.
            voice: The voice name to use.
            style_prompt: Optional style/emotion direction.

        Returns:
            AudioSegment with the generated audio data.
        """
        pass

    @abstractmethod
    def generate_multi_speaker(
        self,
        dialogue: list[tuple[str, str, str]],  # [(speaker, voice, text), ...]
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for multiple speakers.

        Args:
            dialogue: List of (speaker_name, voice_name, text) tuples.
            style_prompt: Optional style/emotion direction.

        Returns:
            AudioSegment with the generated audio data.
        """
        pass

    @abstractmethod
    def max_speakers_per_call(self) -> int:
        """Return the maximum number of speakers per API call."""
        pass

    @abstractmethod
    def max_text_length(self) -> int:
        """Return the maximum text length per call in bytes."""
        pass
