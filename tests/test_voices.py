"""Tests for the voices module."""

import pytest

from tts_generator.voices import (
    VoiceInfo,
    VoiceManager,
    GOOGLE_VOICES,
    DEFAULT_VOICE_ASSIGNMENTS,
    AUTO_ASSIGN_VOICES,
    list_voices,
    get_voice_info,
)


class TestVoiceInfo:
    """Tests for VoiceInfo dataclass."""

    def test_voice_info_creation(self):
        """Test creating VoiceInfo."""
        voice = VoiceInfo("TestVoice", "Friendly", "male")

        assert voice.name == "TestVoice"
        assert voice.characteristic == "Friendly"
        assert voice.gender == "male"

    def test_voice_info_optional_gender(self):
        """Test VoiceInfo without gender."""
        voice = VoiceInfo("TestVoice", "Friendly")

        assert voice.gender is None


class TestGoogleVoices:
    """Tests for GOOGLE_VOICES constant."""

    def test_voices_not_empty(self):
        """Test that voices dictionary is not empty."""
        assert len(GOOGLE_VOICES) > 0

    def test_common_voices_exist(self):
        """Test that commonly used voices exist."""
        expected_voices = ["Charon", "Kore", "Puck", "Sulafat", "Achernar"]
        for voice_name in expected_voices:
            assert voice_name in GOOGLE_VOICES

    def test_voice_info_complete(self):
        """Test that all voices have complete info."""
        for name, info in GOOGLE_VOICES.items():
            assert info.name == name
            assert info.characteristic
            assert info.gender in ("male", "female", None)


class TestVoiceManager:
    """Tests for VoiceManager class."""

    def test_manual_assignment(self):
        """Test manually assigning voices."""
        manager = VoiceManager()
        manager.set_manual_assignments({"Alice": "Kore", "Bob": "Charon"})

        assert manager.get_voice("Alice") == "Kore"
        assert manager.get_voice("Bob") == "Charon"

    def test_auto_assignment_default_speakers(self):
        """Test auto-assignment for default speaker names."""
        manager = VoiceManager()

        # Provider should get Charon (from DEFAULT_VOICE_ASSIGNMENTS)
        voice = manager.assign_voice("Provider")
        assert voice == "Charon"

        # Patient should get Achernar
        voice = manager.assign_voice("Patient")
        assert voice == "Achernar"

    def test_auto_assignment_unique_voices(self):
        """Test that auto-assignment gives unique voices."""
        manager = VoiceManager()

        voices = []
        for i in range(5):
            voice = manager.assign_voice(f"Speaker{i}")
            voices.append(voice)

        # All voices should be unique
        assert len(set(voices)) == 5

    def test_get_voice_auto_assigns(self):
        """Test that get_voice auto-assigns if not already assigned."""
        manager = VoiceManager()

        voice = manager.get_voice("NewSpeaker")

        assert voice is not None
        assert voice in GOOGLE_VOICES

    def test_get_all_assignments(self):
        """Test getting all assignments."""
        manager = VoiceManager()
        manager.set_manual_assignments({"Alice": "Kore"})
        manager.assign_voice("Bob")

        assignments = manager.get_all_assignments()

        assert "Alice" in assignments
        assert "Bob" in assignments
        assert assignments["Alice"] == "Kore"

    def test_assignments_returns_copy(self):
        """Test that get_all_assignments returns a copy."""
        manager = VoiceManager()
        manager.set_manual_assignments({"Alice": "Kore"})

        assignments = manager.get_all_assignments()
        assignments["Alice"] = "Modified"

        # Original should be unchanged
        assert manager.get_voice("Alice") == "Kore"

    def test_reuse_voice_when_exhausted(self):
        """Test that voices are reused when all are exhausted."""
        manager = VoiceManager()

        # Assign more speakers than available voices
        voices = []
        for i in range(len(GOOGLE_VOICES) + 5):
            voice = manager.assign_voice(f"Speaker{i}")
            voices.append(voice)

        # Should have assigned all speakers (some voices reused)
        assert len(voices) == len(GOOGLE_VOICES) + 5

    def test_same_speaker_same_voice(self):
        """Test that the same speaker always gets the same voice."""
        manager = VoiceManager()

        voice1 = manager.assign_voice("Alice")
        voice2 = manager.assign_voice("Alice")
        voice3 = manager.get_voice("Alice")

        assert voice1 == voice2 == voice3


class TestListVoices:
    """Tests for list_voices function."""

    def test_list_google_voices(self):
        """Test listing Google voices."""
        voices = list_voices("google")

        assert len(voices) == len(GOOGLE_VOICES)
        assert all(isinstance(v, VoiceInfo) for v in voices)

    def test_list_unknown_provider(self):
        """Test listing voices for unknown provider."""
        voices = list_voices("unknown_provider")
        assert voices == []


class TestGetVoiceInfo:
    """Tests for get_voice_info function."""

    def test_get_existing_voice(self):
        """Test getting info for existing voice."""
        info = get_voice_info("Charon", "google")

        assert info is not None
        assert info.name == "Charon"
        assert info.characteristic == "Informative"

    def test_get_nonexistent_voice(self):
        """Test getting info for nonexistent voice."""
        info = get_voice_info("NonexistentVoice", "google")
        assert info is None

    def test_get_voice_unknown_provider(self):
        """Test getting voice from unknown provider."""
        info = get_voice_info("Charon", "unknown_provider")
        assert info is None
