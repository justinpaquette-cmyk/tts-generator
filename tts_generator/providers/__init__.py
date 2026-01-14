"""TTS Provider implementations."""

from .base import TTSProvider, AudioSegment
from .google_tts import GoogleTTSProvider

__all__ = ["TTSProvider", "AudioSegment", "GoogleTTSProvider"]

# Optional ElevenLabs import (has dependency issues with some Python versions)
try:
    from .elevenlabs import ElevenLabsProvider
    __all__.append("ElevenLabsProvider")
except ImportError:
    ElevenLabsProvider = None
