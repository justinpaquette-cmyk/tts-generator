"""Google AI Studio TTS provider using Gemini 2.5."""

from __future__ import annotations

import base64
import os

from google import genai
from google.genai import types

from .base import AudioSegment, TTSProvider


class GoogleTTSProvider(TTSProvider):
    """TTS provider using Google AI Studio (Gemini 2.5 TTS)."""

    MODEL = "gemini-2.5-flash-preview-tts"

    def __init__(self, api_key: str | None = None):
        """Initialize the Google TTS provider.

        Args:
            api_key: Google API key. If None, uses GOOGLE_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY environment "
                "variable or pass api_key parameter."
            )
        self.client = genai.Client(api_key=self.api_key)

    def generate_single_speaker(
        self,
        text: str,
        voice: str,
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for a single speaker."""
        # Build TTS instruction with optional style
        if style_prompt:
            content = f"{style_prompt}\n\nTTS this: {text}"
        else:
            content = f"TTS this: {text}"

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=content,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            )
        )

        # Extract audio data from response
        audio_data = self._extract_audio(response)
        return AudioSegment(data=audio_data)

    def generate_multi_speaker(
        self,
        dialogue: list[tuple[str, str, str]],  # [(speaker, voice, text), ...]
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for multiple speakers (max 2 per call)."""
        if len(dialogue) == 0:
            raise ValueError("Dialogue list cannot be empty")

        # Get unique speakers in this dialogue segment
        speakers = {}
        for speaker, voice, _ in dialogue:
            if speaker not in speakers:
                speakers[speaker] = voice

        if len(speakers) > 2:
            raise ValueError(
                f"Google TTS supports max 2 speakers per call, got {len(speakers)}. "
                "Use the audio splicer to handle more speakers."
            )

        # Build dialogue text
        lines = []
        for speaker, _, text in dialogue:
            lines.append(f"{speaker}: {text}")

        dialogue_text = "\n".join(lines)

        # Add TTS instruction and optional style
        if style_prompt:
            content = f"{style_prompt}\n\nTTS the following conversation:\n{dialogue_text}"
        else:
            content = f"TTS the following conversation:\n{dialogue_text}"

        # Build speaker voice configs
        speaker_configs = []
        for speaker, voice in speakers.items():
            speaker_configs.append(
                types.SpeakerVoiceConfig(
                    speaker=speaker,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                )
            )

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=content,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=speaker_configs
                    )
                ),
            )
        )

        audio_data = self._extract_audio(response)
        return AudioSegment(data=audio_data)

    def _extract_audio(self, response) -> bytes:
        """Extract audio bytes from API response."""
        # The response contains inline_data with raw PCM audio bytes
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                data = part.inline_data.data
                # Data is already raw bytes (audio/L16;codec=pcm;rate=24000)
                if isinstance(data, bytes):
                    return data
                # Fallback: if string, try base64 decode
                return base64.b64decode(data)

        raise ValueError("No audio data found in response")

    def max_speakers_per_call(self) -> int:
        """Google TTS supports max 2 speakers per call."""
        return 2

    def max_text_length(self) -> int:
        """Max text length is 4000 bytes."""
        return 4000
