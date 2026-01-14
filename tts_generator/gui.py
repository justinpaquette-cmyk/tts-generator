"""Gradio web interface for TTS Generator."""

from __future__ import annotations

import atexit
import os
import tempfile
from pathlib import Path

import gradio as gr

from .parser import parse_text_file, get_unique_speakers
from .providers import GoogleTTSProvider
from .splicer import AudioSplicer
from .voices import VoiceManager, GOOGLE_VOICES, DEFAULT_VOICE_ASSIGNMENTS
from .chunker import TextChunker
from .streaming import StreamingGenerator


# Get list of voice names for dropdowns
VOICE_CHOICES = sorted(GOOGLE_VOICES.keys())

# Track temp files for cleanup
_temp_files: list[str] = []


def _cleanup_temp_files():
    """Clean up temporary audio files on exit."""
    for filepath in _temp_files:
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
        except Exception:
            pass  # Ignore cleanup errors


# Register cleanup on exit
atexit.register(_cleanup_temp_files)

SAMPLE_TEXT = """Provider: How are you feeling today?
Patient: Much better, thank you for asking.
Provider: That's great to hear. Any concerns?
Patient: Just a bit tired, but overall good."""


def get_default_voice(speaker):
    """Get default voice for a speaker."""
    if speaker in DEFAULT_VOICE_ASSIGNMENTS:
        return DEFAULT_VOICE_ASSIGNMENTS[speaker]
    return "Kore"


def detect_speakers(text):
    """Detect speakers and return updated dropdown configs."""
    if not text or not text.strip():
        return [
            gr.update(label="Speaker 1", value="Kore", visible=True),
            gr.update(label="Speaker 2", value="Charon", visible=True),
            gr.update(label="Speaker 3", value="Puck", visible=False),
            gr.update(label="Speaker 4", value="Fenrir", visible=False),
        ]

    lines = parse_text_file(text)
    speakers = get_unique_speakers(lines)

    updates = []
    for i in range(4):
        if i < len(speakers):
            speaker_name = speakers[i]
            default_voice = get_default_voice(speaker_name)
            updates.append(gr.update(
                label=speaker_name,
                value=default_voice,
                visible=True
            ))
        else:
            updates.append(gr.update(
                label=f"Speaker {i+1}",
                visible=False
            ))

    return updates


def generate_audio(text, voice1, voice2, voice3, voice4, pause_ms, audiobook_mode, chapter_pause_ms, progress=gr.Progress()):
    """Generate TTS audio from conversation text."""
    if not text or not text.strip():
        return None

    # Check API key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise gr.Error("GOOGLE_API_KEY not set. Set it before running.")

    # Parse text
    lines = parse_text_file(text)
    if not lines:
        raise gr.Error("No dialogue found. Use format: 'Speaker: dialogue text'")

    speakers = get_unique_speakers(lines)
    voice_list = [voice1, voice2, voice3, voice4]

    # Set up voice manager
    voice_manager = VoiceManager()
    for i, speaker in enumerate(speakers[:4]):
        voice_manager.set_manual_assignments({speaker: voice_list[i]})

    # Initialize provider
    provider = GoogleTTSProvider(api_key=api_key)

    # Create temp file for output
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    output_path = Path(temp_file.name)
    temp_file.close()

    # Track temp file for cleanup
    _temp_files.append(str(output_path))

    if audiobook_mode:
        # Audiobook mode: chunk and stream
        chunker = TextChunker(
            max_bytes=3500,
            max_speakers_per_chunk=2,
            chapter_pause_ms=int(chapter_pause_ms),
        )
        chunks = chunker.chunk(lines)

        if not chunks:
            raise gr.Error("No chunks generated from text")

        # Create streaming generator
        generator = StreamingGenerator(
            provider=provider,
            voice_manager=voice_manager,
            output_path=output_path,
            pause_ms=int(pause_ms),
            chapter_pause_ms=int(chapter_pause_ms),
        )

        # Generate with progress
        def update_progress(current, total, stats):
            progress(current / total, desc=f"Generating chunk {current}/{total}")

        generator.generate(chunks, progress_callback=update_progress)
    else:
        # Standard mode
        splicer = AudioSplicer(
            provider=provider,
            voice_manager=voice_manager,
            pause_ms=int(pause_ms),
        )
        audio = splicer.generate_conversation(lines)
        splicer.export(audio, output_path)

    return str(output_path)


def create_demo():
    """Create the Gradio interface."""
    with gr.Blocks(title="TTS Generator") as demo:
        gr.Markdown("# TTS Generator")
        gr.Markdown("Convert multi-speaker conversations to audio using Google AI Studio TTS.")

        with gr.Row():
            with gr.Column(scale=2):
                text_input = gr.Textbox(
                    label="Conversation",
                    placeholder="Speaker A: Hello\nProvider: Hi there!",
                    lines=10,
                    value=SAMPLE_TEXT,
                )
                detect_btn = gr.Button("Detect Speakers", variant="secondary", size="sm")

            with gr.Column(scale=1):
                gr.Markdown("### Voice Assignments")
                gr.Markdown("*Click 'Detect Speakers' to auto-fill*")
                voice1 = gr.Dropdown(choices=VOICE_CHOICES, value="Charon", label="Provider", visible=True)
                voice2 = gr.Dropdown(choices=VOICE_CHOICES, value="Achernar", label="Patient", visible=True)
                voice3 = gr.Dropdown(choices=VOICE_CHOICES, value="Puck", label="Speaker 3", visible=False)
                voice4 = gr.Dropdown(choices=VOICE_CHOICES, value="Fenrir", label="Speaker 4", visible=False)

                pause_slider = gr.Slider(
                    minimum=100,
                    maximum=1000,
                    value=300,
                    step=50,
                    label="Pause between speakers (ms)",
                )

                gr.Markdown("### Audiobook Mode")
                audiobook_checkbox = gr.Checkbox(
                    label="Enable audiobook mode (for large files)",
                    value=False,
                )
                chapter_pause_slider = gr.Slider(
                    minimum=500,
                    maximum=5000,
                    value=2000,
                    step=100,
                    label="Chapter pause (ms)",
                    visible=False,
                )

                # Show/hide chapter pause based on audiobook mode
                audiobook_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[audiobook_checkbox],
                    outputs=[chapter_pause_slider],
                )

        generate_btn = gr.Button("Generate Audio", variant="primary")
        audio_output = gr.Audio(label="Generated Audio", type="filepath")

        # Wire up detect button
        detect_btn.click(
            fn=detect_speakers,
            inputs=[text_input],
            outputs=[voice1, voice2, voice3, voice4],
        )

        # Wire up generate button
        generate_btn.click(
            fn=generate_audio,
            inputs=[text_input, voice1, voice2, voice3, voice4, pause_slider, audiobook_checkbox, chapter_pause_slider],
            outputs=[audio_output],
        )

    return demo


def main():
    """Launch the Gradio interface."""
    demo = create_demo()
    demo.launch(share=False)


if __name__ == "__main__":
    main()
