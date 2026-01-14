#!/bin/bash
# TTS Generator Setup Script

echo "=== TTS Generator Setup ==="
echo ""

# Navigate to project directory
cd "$(dirname "$0")/.." || exit 1
PROJECT_DIR=$(pwd)
echo "Project directory: $PROJECT_DIR"
echo ""

# Check Python version
echo "Checking Python..."
python3 --version
echo ""

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt
echo ""

# Check for API key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "WARNING: GOOGLE_API_KEY not set"
    echo ""
    echo "Get an API key at: https://aistudio.google.com/apikey"
    echo "Then run: export GOOGLE_API_KEY=\"your-api-key\""
else
    echo "GOOGLE_API_KEY is set"
fi
echo ""

# Test import
echo "Testing module import..."
python3 -c "from tts_generator.cli import main; print('Module loaded successfully')"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "Usage:"
echo "  python3 -m tts_generator.cli input.txt -o output.wav"
echo ""
echo "Quick test:"
echo "  python3 -m tts_generator.cli examples/short_test.txt -o test.wav"
