"""ElevenLabs TTS provider."""

from __future__ import annotations

import os
from io import BytesIO

from elevenlabs import ElevenLabs

from .base import AudioSegment, TTSProvider


# Default ElevenLabs voice IDs (these are example IDs, users should configure their own)
ELEVENLABS_VOICE_MAP = {
    # Map Google voice names to ElevenLabs default voices
    "Kore": "21m00Tcm4TlvDq8ikWAM",      # Rachel
    "Charon": "29vD33N1CtxCmqQRPOHJ",    # Drew
    "Sulafat": "EXAVITQu4vr4xnSDxMaL",   # Bella
    "Puck": "ErXwobaYiN019PkySvjV",      # Antoni
    "Aoede": "MF3mGyEYCl7XYWbV9V6O",     # Elli
    "Achird": "TxGEqnHWrfWFTfGW9XjX",    # Josh
    "Gacrux": "pNInz6obpgDQGcFmaJgB",    # Adam
    "Iapetus": "yoZ06aMxZJJ28mfd3POQ",   # Sam
}


class ElevenLabsProvider(TTSProvider):
    """TTS provider using ElevenLabs API."""

    def __init__(self, api_key: str | None = None):
        """Initialize the ElevenLabs provider.

        Args:
            api_key: ElevenLabs API key. If None, uses ELEVENLABS_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY environment "
                "variable or pass api_key parameter."
            )
        self.client = ElevenLabs(api_key=self.api_key)

    def _get_voice_id(self, voice_name: str) -> str:
        """Map voice name to ElevenLabs voice ID."""
        # First check our mapping
        if voice_name in ELEVENLABS_VOICE_MAP:
            return ELEVENLABS_VOICE_MAP[voice_name]
        # Assume it's already a voice ID
        return voice_name

    def generate_single_speaker(
        self,
        text: str,
        voice: str,
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for a single speaker."""
        voice_id = self._get_voice_id(voice)

        # ElevenLabs doesn't use style prompts the same way, but we can prepend
        # the style instruction to influence the output
        content = text
        if style_prompt:
            content = f"[{style_prompt}] {text}"

        audio_generator = self.client.text_to_speech.convert(
            voice_id=voice_id,
            text=content,
            model_id="eleven_multilingual_v2",
        )

        # Collect all chunks from the generator
        audio_data = b"".join(audio_generator)

        return AudioSegment(
            data=audio_data,
            sample_rate=44100,  # ElevenLabs default
            channels=1,
            sample_width=2,
        )

    def generate_multi_speaker(
        self,
        dialogue: list[tuple[str, str, str]],  # [(speaker, voice, text), ...]
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for multiple speakers.

        ElevenLabs generates one speaker at a time, so we concatenate segments.
        For proper multi-speaker, use the audio splicer which handles this better.
        """
        if len(dialogue) == 0:
            raise ValueError("Dialogue list cannot be empty")

        all_audio = BytesIO()

        for speaker, voice, text in dialogue:
            segment = self.generate_single_speaker(text, voice, style_prompt)
            all_audio.write(segment.data)

        return AudioSegment(
            data=all_audio.getvalue(),
            sample_rate=44100,
            channels=1,
            sample_width=2,
        )

    def max_speakers_per_call(self) -> int:
        """ElevenLabs generates one speaker at a time."""
        return 1

    def max_text_length(self) -> int:
        """ElevenLabs has a limit around 5000 characters."""
        return 5000
