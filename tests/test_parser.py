"""Tests for the parser module."""

import json
import tempfile
from pathlib import Path

import pytest

from tts_generator.parser import (
    DialogueLine,
    parse_text_file,
    parse_json_file,
    parse_file,
    get_unique_speakers,
)


class TestParseTextFile:
    """Tests for parse_text_file function."""

    def test_simple_dialogue(self):
        """Test parsing simple two-speaker dialogue."""
        content = """Speaker A: Hello there!
Speaker B: Hi, how are you?
Speaker A: I'm doing well."""

        lines = parse_text_file(content)

        assert len(lines) == 3
        assert lines[0].speaker == "Speaker A"
        assert lines[0].text == "Hello there!"
        assert lines[1].speaker == "Speaker B"
        assert lines[1].text == "Hi, how are you?"
        assert lines[2].speaker == "Speaker A"
        assert lines[2].text == "I'm doing well."

    def test_multiline_dialogue(self):
        """Test parsing dialogue that spans multiple lines."""
        content = """Speaker A: This is a long piece of dialogue
that continues on the next line
and even a third line.
Speaker B: Short response."""

        lines = parse_text_file(content)

        assert len(lines) == 2
        assert lines[0].speaker == "Speaker A"
        assert "continues on the next line" in lines[0].text
        assert "third line" in lines[0].text
        assert lines[1].text == "Short response."

    def test_empty_lines_ignored(self):
        """Test that empty lines are ignored."""
        content = """Speaker A: First line.

Speaker B: Second line.

"""
        lines = parse_text_file(content)

        assert len(lines) == 2

    def test_speaker_with_numbers(self):
        """Test speaker names with numbers."""
        content = """Speaker 1: Hello.
Speaker 2: Hi there."""

        lines = parse_text_file(content)

        assert len(lines) == 2
        assert lines[0].speaker == "Speaker 1"
        assert lines[1].speaker == "Speaker 2"

    def test_common_speaker_names(self):
        """Test common speaker names like Provider, Patient."""
        content = """Provider: How are you feeling?
Patient: Much better, thanks."""

        lines = parse_text_file(content)

        assert len(lines) == 2
        assert lines[0].speaker == "Provider"
        assert lines[1].speaker == "Patient"

    def test_empty_content(self):
        """Test parsing empty content."""
        lines = parse_text_file("")
        assert len(lines) == 0

    def test_no_valid_dialogue(self):
        """Test content with no valid dialogue format."""
        content = """Just some random text
without any speaker labels."""

        lines = parse_text_file(content)
        assert len(lines) == 0

    def test_colon_in_dialogue(self):
        """Test handling colons within dialogue text."""
        content = """Speaker A: The time is 10:30 AM."""

        lines = parse_text_file(content)

        assert len(lines) == 1
        assert lines[0].text == "The time is 10:30 AM."

    def test_url_not_treated_as_speaker(self):
        """Test that URLs are not treated as speaker labels."""
        content = """Speaker A: Check out https://example.com for more info."""

        lines = parse_text_file(content)

        assert len(lines) == 1
        assert "https://example.com" in lines[0].text

    def test_timestamp_not_treated_as_speaker(self):
        """Test that timestamps are not treated as speaker labels."""
        content = """Speaker A: The meeting is at
10:30 in the morning."""

        lines = parse_text_file(content)

        assert len(lines) == 1
        assert "10:30" in lines[0].text

    def test_speaker_name_must_start_with_letter(self):
        """Test that speaker names must start with a letter."""
        content = """Speaker A: Hello.
123Speaker: This should not match."""

        lines = parse_text_file(content)

        # Only first line should be parsed as dialogue
        assert len(lines) == 1
        assert lines[0].speaker == "Speaker A"


class TestParseJsonFile:
    """Tests for parse_json_file function."""

    def test_simple_json(self):
        """Test parsing simple JSON dialogue."""
        content = json.dumps([
            {"speaker": "Alice", "text": "Hello!"},
            {"speaker": "Bob", "text": "Hi there!"},
        ])

        lines = parse_json_file(content)

        assert len(lines) == 2
        assert lines[0].speaker == "Alice"
        assert lines[0].text == "Hello!"

    def test_empty_json_array(self):
        """Test parsing empty JSON array."""
        lines = parse_json_file("[]")
        assert len(lines) == 0

    def test_missing_fields(self):
        """Test JSON entries with missing fields are skipped."""
        content = json.dumps([
            {"speaker": "Alice", "text": "Hello!"},
            {"speaker": "Bob"},  # Missing text
            {"text": "No speaker"},  # Missing speaker
            {"speaker": "Carol", "text": "Valid"},
        ])

        lines = parse_json_file(content)

        assert len(lines) == 2
        assert lines[0].speaker == "Alice"
        assert lines[1].speaker == "Carol"

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed from speaker and text."""
        content = json.dumps([
            {"speaker": "  Alice  ", "text": "  Hello!  "},
        ])

        lines = parse_json_file(content)

        assert lines[0].speaker == "Alice"
        assert lines[0].text == "Hello!"


class TestParseFile:
    """Tests for parse_file function."""

    def test_text_file(self):
        """Test parsing a .txt file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Speaker A: Hello!")
            f.flush()

            lines = parse_file(f.name)

            assert len(lines) == 1
            assert lines[0].speaker == "Speaker A"

        Path(f.name).unlink()

    def test_json_file(self):
        """Test parsing a .json file."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump([{"speaker": "Alice", "text": "Hello!"}], f)
            f.flush()

            lines = parse_file(f.name)

            assert len(lines) == 1
            assert lines[0].speaker == "Alice"

        Path(f.name).unlink()


class TestGetUniqueSpeakers:
    """Tests for get_unique_speakers function."""

    def test_unique_speakers_in_order(self):
        """Test that speakers are returned in order of appearance."""
        lines = [
            DialogueLine("Alice", "First"),
            DialogueLine("Bob", "Second"),
            DialogueLine("Alice", "Third"),
            DialogueLine("Carol", "Fourth"),
        ]

        speakers = get_unique_speakers(lines)

        assert speakers == ["Alice", "Bob", "Carol"]

    def test_empty_lines(self):
        """Test with empty list of lines."""
        speakers = get_unique_speakers([])
        assert speakers == []

    def test_single_speaker(self):
        """Test with single speaker."""
        lines = [
            DialogueLine("Narrator", "Line 1"),
            DialogueLine("Narrator", "Line 2"),
        ]

        speakers = get_unique_speakers(lines)

        assert speakers == ["Narrator"]
