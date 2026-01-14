"""Google AI Studio TTS provider using Gemini 2.5."""

from __future__ import annotations

import base64
import os
import time
from functools import wraps

from google import genai
from google.genai import types

from .base import AudioSegment, TTSProvider


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """Decorator for retrying API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        print(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        print(f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


class GoogleTTSProvider(TTSProvider):
    """TTS provider using Google AI Studio (Gemini 2.5 TTS)."""

    MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_TIMEOUT = 60  # seconds

    def __init__(self, api_key: str | None = None, timeout: int | None = None):
        """Initialize the Google TTS provider.

        Args:
            api_key: Google API key. If None, uses GOOGLE_API_KEY env var.
            timeout: Request timeout in seconds. Defaults to 60.
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY environment "
                "variable or pass api_key parameter."
            )
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.client = genai.Client(api_key=self.api_key)
        self.debug = False  # Enable for verbose logging

    def _debug_log(self, message: str):
        """Print debug message if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def generate_single_speaker(
        self,
        text: str,
        voice: str,
        style_prompt: str | None = None
    ) -> AudioSegment:
        """Generate audio for a single speaker."""
        # Validate text length
        text_bytes = len(text.encode('utf-8'))
        if text_bytes > self.max_text_length():
            raise ValueError(
                f"Text too long ({text_bytes} bytes). Maximum is {self.max_text_length()} bytes. "
                "Consider using audiobook mode for long texts."
            )

        # Build TTS instruction with optional style
        if style_prompt:
            content = f"{style_prompt}\n\nTTS this: {text}"
        else:
            content = f"TTS this: {text}"

        response = self._call_api_with_retry(content, voice=voice)

        # Extract audio data from response
        audio_data = self._extract_audio(response)
        return AudioSegment(data=audio_data)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _call_api_with_retry(self, content: str, voice: str | None = None, speaker_configs: list | None = None):
        """Make API call with retry logic.

        Args:
            content: The text content to send
            voice: Single speaker voice name (for single speaker mode)
            speaker_configs: List of speaker configs (for multi-speaker mode)

        Returns:
            API response
        """
        text_bytes = len(content.encode('utf-8'))
        if speaker_configs:
            speakers = [sc.speaker for sc in speaker_configs]
            self._debug_log(f"API call: multi-speaker mode, speakers={speakers}, text={text_bytes} bytes")
        else:
            self._debug_log(f"API call: single-speaker mode, voice={voice}, text={text_bytes} bytes")

        if speaker_configs:
            # Multi-speaker mode
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=speaker_configs
                    )
                ),
            )
        else:
            # Single speaker mode
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            )

        return self.client.models.generate_content(
            model=self.MODEL,
            contents=content,
            config=config,
        )

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

        # Validate text length
        text_bytes = len(dialogue_text.encode('utf-8'))
        if text_bytes > self.max_text_length():
            raise ValueError(
                f"Dialogue too long ({text_bytes} bytes). Maximum is {self.max_text_length()} bytes. "
                "Consider using audiobook mode for long texts."
            )

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

        response = self._call_api_with_retry(content, speaker_configs=speaker_configs)

        audio_data = self._extract_audio(response)
        return AudioSegment(data=audio_data)

    def _extract_audio(self, response) -> bytes:
        """Extract audio bytes from API response.

        Validates response structure and provides helpful error messages.
        """
        # Validate response structure
        if not response:
            raise ValueError("Empty response from API")

        if not hasattr(response, 'candidates') or not response.candidates:
            raise ValueError(
                "Invalid API response: no candidates returned. "
                "This may indicate a rate limit or API error."
            )

        candidate = response.candidates[0]
        if not hasattr(candidate, 'content') or not candidate.content:
            raise ValueError(
                "Invalid API response: no content in candidate. "
                "The API may have returned an error."
            )

        if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
            raise ValueError(
                "Invalid API response: no parts in content. "
                "The model may not have generated audio."
            )

        # Extract audio data from parts
        for part in candidate.content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                data = part.inline_data.data
                # Data is already raw bytes (audio/L16;codec=pcm;rate=24000)
                if isinstance(data, bytes):
                    return data
                # Fallback: if string, try base64 decode
                return base64.b64decode(data)

        raise ValueError(
            "No audio data found in response. "
            "The model may have generated text instead of audio."
        )

    def max_speakers_per_call(self) -> int:
        """Google TTS supports max 2 speakers per call."""
        return 2

    def max_text_length(self) -> int:
        """Max text length is 4000 bytes."""
        return 4000
