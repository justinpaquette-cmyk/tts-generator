"""Voice mappings and selection for TTS providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VoiceInfo:
    """Information about a voice."""
    name: str
    characteristic: str
    gender: str | None = None


# Google AI Studio voices (Gemini 2.5 TTS)
GOOGLE_VOICES: dict[str, VoiceInfo] = {
    "Zephyr": VoiceInfo("Zephyr", "Bright", "female"),
    "Puck": VoiceInfo("Puck", "Upbeat", "male"),
    "Charon": VoiceInfo("Charon", "Informative", "male"),
    "Kore": VoiceInfo("Kore", "Firm", "female"),
    "Fenrir": VoiceInfo("Fenrir", "Excitable", "male"),
    "Leda": VoiceInfo("Leda", "Youthful", "female"),
    "Orus": VoiceInfo("Orus", "Firm", "male"),
    "Aoede": VoiceInfo("Aoede", "Breezy", "female"),
    "Callirrhoe": VoiceInfo("Callirrhoe", "Easy-going", "female"),
    "Autonoe": VoiceInfo("Autonoe", "Bright", "female"),
    "Enceladus": VoiceInfo("Enceladus", "Breathy", "male"),
    "Iapetus": VoiceInfo("Iapetus", "Clear", "male"),
    "Umbriel": VoiceInfo("Umbriel", "Easy-going", "male"),
    "Algieba": VoiceInfo("Algieba", "Smooth", "male"),
    "Despina": VoiceInfo("Despina", "Smooth", "female"),
    "Erinome": VoiceInfo("Erinome", "Clear", "female"),
    "Algenib": VoiceInfo("Algenib", "Gravelly", "male"),
    "Rasalgethi": VoiceInfo("Rasalgethi", "Informative", "male"),
    "Laomedeia": VoiceInfo("Laomedeia", "Upbeat", "female"),
    "Achernar": VoiceInfo("Achernar", "Soft", "female"),
    "Alnilam": VoiceInfo("Alnilam", "Firm", "male"),
    "Schedar": VoiceInfo("Schedar", "Even", "male"),
    "Gacrux": VoiceInfo("Gacrux", "Mature", "female"),
    "Pulcherrima": VoiceInfo("Pulcherrima", "Forward", "female"),
    "Achird": VoiceInfo("Achird", "Friendly", "male"),
    "Zubenelgenubi": VoiceInfo("Zubenelgenubi", "Casual", "male"),
    "Vindemiatrix": VoiceInfo("Vindemiatrix", "Gentle", "female"),
    "Sadachbia": VoiceInfo("Sadachbia", "Lively", "male"),
    "Sadaltager": VoiceInfo("Sadaltager", "Knowledgeable", "male"),
    "Sulafat": VoiceInfo("Sulafat", "Warm", "female"),
}

# Default voice assignments for common speaker roles
DEFAULT_VOICE_ASSIGNMENTS = {
    "Provider": "Charon",  # Professional, informative
    "Doctor": "Charon",
    "Nurse": "Sulafat",  # Warm
    "Patient": "Achernar",  # Soft
    "Speaker A": "Kore",  # Firm, clear
    "Speaker B": "Puck",  # Upbeat
    "Speaker C": "Fenrir",  # Excitable
    "Speaker D": "Leda",  # Youthful
}

# Diverse voices for auto-assignment (mix of genders and characteristics)
AUTO_ASSIGN_VOICES = [
    "Kore",       # Female, Firm
    "Charon",     # Male, Informative
    "Sulafat",    # Female, Warm
    "Puck",       # Male, Upbeat
    "Aoede",      # Female, Breezy
    "Achird",     # Male, Friendly
    "Gacrux",     # Female, Mature
    "Iapetus",    # Male, Clear
    "Leda",       # Female, Youthful
    "Fenrir",     # Male, Excitable
]


class VoiceManager:
    """Manages voice assignments for speakers."""

    def __init__(self, provider: str = "google"):
        self.provider = provider
        self.assignments: dict[str, str] = {}
        self._used_voices: set[str] = set()

    def assign_voice(self, speaker: str, voice: str | None = None) -> str:
        """Assign a voice to a speaker.

        If voice is None, auto-assigns based on speaker name or next available.
        """
        if speaker in self.assignments:
            return self.assignments[speaker]

        if voice:
            self.assignments[speaker] = voice
            self._used_voices.add(voice)
            return voice

        # Check default assignments first
        if speaker in DEFAULT_VOICE_ASSIGNMENTS:
            default = DEFAULT_VOICE_ASSIGNMENTS[speaker]
            if default not in self._used_voices:
                self.assignments[speaker] = default
                self._used_voices.add(default)
                return default

        # Auto-assign from available voices
        for voice in AUTO_ASSIGN_VOICES:
            if voice not in self._used_voices:
                self.assignments[speaker] = voice
                self._used_voices.add(voice)
                return voice

        # Fallback: use first available Google voice
        for voice in GOOGLE_VOICES:
            if voice not in self._used_voices:
                self.assignments[speaker] = voice
                self._used_voices.add(voice)
                return voice

        # Last resort: reuse a voice
        fallback = AUTO_ASSIGN_VOICES[0]
        self.assignments[speaker] = fallback
        return fallback

    def get_voice(self, speaker: str) -> str:
        """Get the assigned voice for a speaker."""
        if speaker not in self.assignments:
            return self.assign_voice(speaker)
        return self.assignments[speaker]

    def set_manual_assignments(self, assignments: dict[str, str]):
        """Set manual voice assignments."""
        for speaker, voice in assignments.items():
            self.assignments[speaker] = voice
            self._used_voices.add(voice)

    def get_all_assignments(self) -> dict[str, str]:
        """Get all current voice assignments."""
        return self.assignments.copy()


def list_voices(provider: str = "google") -> list[VoiceInfo]:
    """List all available voices for a provider."""
    if provider == "google":
        return list(GOOGLE_VOICES.values())
    return []


def get_voice_info(voice_name: str, provider: str = "google") -> VoiceInfo | None:
    """Get information about a specific voice."""
    if provider == "google":
        return GOOGLE_VOICES.get(voice_name)
    return None
