"""Command-line interface for TTS Generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .parser import parse_file, get_unique_speakers
from .providers import GoogleTTSProvider
from .splicer import AudioSplicer
from .voices import VoiceManager, GOOGLE_VOICES


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


def run_standard_mode(args, lines, speakers, voice_manager, provider):
    """Run standard (non-audiobook) generation."""
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


def run_audiobook_mode(args, lines, speakers, voice_manager, provider):
    """Run audiobook mode with chunking and streaming."""
    from .chunker import TextChunker
    from .streaming import StreamingGenerator

    output_path = Path(args.output)

    # Chunk the text
    console.print("[cyan]Chunking text for audiobook mode...[/cyan]")
    chunker = TextChunker(
        max_bytes=3500,
        max_speakers_per_chunk=2,
        chapter_pause_ms=args.chapter_pause,
    )
    chunks = chunker.chunk(lines)
    stats = chunker.get_stats(chunks)

    console.print(f"[green]Created:[/green] {stats['chunks']} chunks")
    console.print(f"[dim]Estimated duration:[/dim] {stats['estimated_duration_min']:.1f} minutes")

    # Check for resume
    state_path = output_path.with_suffix('.state.json')
    if args.resume and state_path.exists():
        console.print("[yellow]Resuming from previous state...[/yellow]")
    elif state_path.exists() and not args.resume:
        console.print("[yellow]Warning:[/yellow] State file found. Use --resume to continue, or delete it to start fresh.")
        if output_path.exists():
            output_path.unlink()
        state_path.unlink()

    # Create streaming generator
    generator = StreamingGenerator(
        provider=provider,
        voice_manager=voice_manager,
        output_path=output_path,
        pause_ms=args.pause,
        chapter_pause_ms=args.chapter_pause,
    )

    # Generate with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating audiobook...", total=len(chunks))

        def update_progress(current, total, gen_stats):
            progress.update(task, completed=current)
            duration_sec = gen_stats.get("total_duration_ms", 0) / 1000
            progress.update(task, description=f"Chunk {current}/{total} | {duration_sec:.0f}s generated")

        generator.generate(
            chunks,
            progress_callback=update_progress,
            resume=args.resume,
        )

    console.print(f"[green]Success![/green] Audiobook saved to: {output_path}")
    console.print(f"[dim]Total duration:[/dim] {generator.stats['total_duration_ms'] / 1000 / 60:.1f} minutes")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert multi-speaker conversations to speech using Google AI Studio TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tts-generator input.txt -o output.wav
  tts-generator input.txt --voices "Speaker A:Kore,Provider:Charon"
  tts-generator --list-voices

Audiobook mode (for large files):
  tts-generator book.txt -o audiobook.wav --audiobook
  tts-generator book.txt -o audiobook.wav --audiobook --resume
        """,
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input file (text or JSON format)",
    )
    parser.add_argument(
        "-o", "--output",
        default="output.wav",
        help="Output audio file (default: output.wav)",
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

    # Audiobook mode options
    parser.add_argument(
        "--audiobook",
        action="store_true",
        help="Enable audiobook mode for large files (chunking + streaming)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted audiobook generation",
    )
    parser.add_argument(
        "--chapter-pause",
        type=int,
        default=2000,
        help="Pause duration at chapter breaks in ms (default: 2000)",
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
        voice_manager = VoiceManager(provider="google")

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
        provider = GoogleTTSProvider(api_key=args.api_key)
        console.print("[cyan]Provider:[/cyan] google")

        # Run appropriate mode
        if args.audiobook:
            run_audiobook_mode(args, lines, speakers, voice_manager, provider)
        else:
            run_standard_mode(args, lines, speakers, voice_manager, provider)

        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow] Use --resume to continue.")
        return 1
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
