"""Input parser for conversation files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DialogueLine:
    """A single line of dialogue."""
    speaker: str
    text: str


def parse_text_file(content: str) -> list[DialogueLine]:
    """Parse text format: 'Speaker: dialogue' per line.

    Handles multi-line dialogue by continuing until the next speaker line.
    """
    lines = []
    current_speaker = None
    current_text = []

    # Pattern to match speaker labels like "Speaker A:", "Provider:", etc.
    speaker_pattern = re.compile(r'^([A-Za-z0-9 ]+):\s*(.*)$')

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = speaker_pattern.match(line)
        if match:
            # Save previous dialogue if exists
            if current_speaker and current_text:
                lines.append(DialogueLine(
                    speaker=current_speaker,
                    text=' '.join(current_text)
                ))

            current_speaker = match.group(1).strip()
            dialogue = match.group(2).strip()
            current_text = [dialogue] if dialogue else []
        elif current_speaker:
            # Continuation of previous speaker's dialogue
            current_text.append(line)

    # Don't forget the last dialogue
    if current_speaker and current_text:
        lines.append(DialogueLine(
            speaker=current_speaker,
            text=' '.join(current_text)
        ))

    return lines


def parse_json_file(content: str) -> list[DialogueLine]:
    """Parse JSON format: [{speaker: "...", text: "..."}, ...]"""
    data = json.loads(content)

    lines = []
    for item in data:
        speaker = item.get('speaker', '').strip()
        text = item.get('text', '').strip()
        if speaker and text:
            lines.append(DialogueLine(speaker=speaker, text=text))

    return lines


def parse_file(file_path: str | Path) -> list[DialogueLine]:
    """Parse input file, auto-detecting format from extension."""
    path = Path(file_path)
    content = path.read_text(encoding='utf-8')

    if path.suffix.lower() == '.json':
        return parse_json_file(content)
    else:
        # Default to text format
        return parse_text_file(content)


def get_unique_speakers(lines: list[DialogueLine]) -> list[str]:
    """Get list of unique speakers in order of appearance."""
    seen = set()
    speakers = []
    for line in lines:
        if line.speaker not in seen:
            seen.add(line.speaker)
            speakers.append(line.speaker)
    return speakers
