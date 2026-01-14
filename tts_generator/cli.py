"""Command-line interface for TTS Generator."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .parser import parse_file, get_unique_speakers
from .providers import GoogleTTSProvider, ElevenLabsProvider
from .splicer import AudioSplicer
from .voices import VoiceManager, list_voices, GOOGLE_VOICES


console = Console()


def parse_voice_mapping(voice_str: str) -> dict[str, str]:
    """Parse voice mapping string like 'Speaker A:Kore,Provider:Charon'."""
    if not voice_str:
        return {}

    mapping = {}
    pairs = voice_str.split(',')
    for pair in pairs:
        if ':' in pair:
            speaker, voice = pair.split(':', 1)
            mapping[speaker.strip()] = voice.strip()
    return mapping


def list_available_voices():
    """Display available voices in a table."""
    table = Table(title="Available Google TTS Voices")
    table.add_column("Voice", style="cyan")
    table.add_column("Characteristic", style="green")
    table.add_column("Gender", style="magenta")

    for name, info in sorted(GOOGLE_VOICES.items()):
        table.add_row(name, info.characteristic, info.gender or "")

    console.print(table)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert multi-speaker conversations to speech using Google AI Studio TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tts-generator input.txt -o output.mp3
  tts-generator conversation.json -o output.wav --provider elevenlabs
  tts-generator input.txt --voices "Speaker A:Kore,Provider:Charon"
  tts-generator --list-voices
        """,
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file (text or JSON format)",
    )
    parser.add_argument(
        "-o", "--output",
        default="output.mp3",
        help="Output audio file (default: output.mp3)",
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["google", "elevenlabs"],
        default="google",
        help="TTS provider to use (default: google)",
    )
    parser.add_argument(
        "--voices",
        help="Voice mapping (e.g., 'Speaker A:Kore,Provider:Charon')",
    )
    parser.add_argument(
        "--pause",
        type=int,
        default=300,
        help="Pause duration between speakers in ms (default: 300)",
    )
    parser.add_argument(
        "--style",
        help="Style prompt for TTS (e.g., 'conversational, natural pace')",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices and exit",
    )
    parser.add_argument(
        "--api-key",
        help="API key (overrides environment variable)",
    )
    parser.add_argument(
        "--show-assignments",
        action="store_true",
        help="Show voice assignments before generating",
    )

    args = parser.parse_args()

    # Handle list-voices flag
    if args.list_voices:
        list_available_voices()
        return 0

    # Validate input file
    if not args.input:
        console.print("[red]Error:[/red] Input file required. Use --help for usage.")
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Error:[/red] Input file not found: {input_path}")
        return 1

    try:
        # Parse input file
        console.print(f"[cyan]Parsing:[/cyan] {input_path}")
        lines = parse_file(input_path)
        speakers = get_unique_speakers(lines)

        console.print(f"[green]Found:[/green] {len(lines)} dialogue lines, {len(speakers)} speakers")
        console.print(f"[dim]Speakers:[/dim] {', '.join(speakers)}")

        # Set up voice manager
        voice_manager = VoiceManager(provider=args.provider)

        # Apply manual voice assignments if provided
        if args.voices:
            manual_assignments = parse_voice_mapping(args.voices)
            voice_manager.set_manual_assignments(manual_assignments)
            console.print(f"[cyan]Manual voices:[/cyan] {manual_assignments}")

        # Assign voices to all speakers
        for speaker in speakers:
            voice_manager.assign_voice(speaker)

        if args.show_assignments:
            assignments = voice_manager.get_all_assignments()
            table = Table(title="Voice Assignments")
            table.add_column("Speaker", style="cyan")
            table.add_column("Voice", style="green")
            for speaker, voice in assignments.items():
                table.add_row(speaker, voice)
            console.print(table)

        # Initialize TTS provider
        if args.provider == "google":
            provider = GoogleTTSProvider(api_key=args.api_key)
        else:
            provider = ElevenLabsProvider(api_key=args.api_key)

        console.print(f"[cyan]Provider:[/cyan] {args.provider}")

        # Create splicer and generate audio
        splicer = AudioSplicer(
            provider=provider,
            voice_manager=voice_manager,
            pause_ms=args.pause,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating audio...", total=None)

            def update_progress(current, total):
                progress.update(task, description=f"Generating segment {current}/{total}...")

            audio = splicer.generate_conversation(
                lines,
                style_prompt=args.style,
                progress_callback=update_progress,
            )

        # Export
        output_path = Path(args.output)
        splicer.export(audio, output_path)

        console.print(f"[green]Success![/green] Audio saved to: {output_path}")
        console.print(f"[dim]Duration:[/dim] {len(audio) / 1000:.1f} seconds")

        return 0

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
