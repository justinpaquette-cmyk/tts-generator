#!/bin/bash
# Quick generation script
# Usage: ./scripts/generate.sh input.txt output.wav

cd "$(dirname "$0")/.." || exit 1

if [ -z "$1" ]; then
    echo "Usage: ./scripts/generate.sh <input_file> [output_file]"
    echo ""
    echo "Examples:"
    echo "  ./scripts/generate.sh examples/sample_conversation.txt"
    echo "  ./scripts/generate.sh my_script.txt my_audio.wav"
    exit 1
fi

INPUT="$1"
OUTPUT="${2:-output.wav}"

echo "Input:  $INPUT"
echo "Output: $OUTPUT"
echo ""

python3 -m tts_generator.cli "$INPUT" -o "$OUTPUT" --show-assignments
