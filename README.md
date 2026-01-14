# TTS Generator

Multi-speaker text-to-speech tool using Google AI Studio (Gemini 2.5 TTS).

## Quick Start

```bash
# Clone and setup
git clone https://github.com/justinpaquette-cmyk/tts-generator.git
cd tts-generator
python3 -m pip install -r requirements.txt

# Set your API key (get one at https://aistudio.google.com/apikey)
export GOOGLE_API_KEY="your-google-api-key"

# Generate audio
python3 -m tts_generator.cli examples/sample_conversation.txt -o output.wav
```

Or use the helper scripts:
```bash
./scripts/setup.sh
./scripts/generate.sh examples/sample_conversation.txt output.wav
```

## Usage Examples

### Basic Usage
```bash
# Convert a conversation to audio
python3 -m tts_generator.cli input.txt -o output.wav

# Specify output file
python3 -m tts_generator.cli conversation.txt -o my_audio.wav
```

### Voice Options
```bash
# List all available voices
python3 -m tts_generator.cli --list-voices

# Show which voices are assigned to speakers
python3 -m tts_generator.cli input.txt -o output.wav --show-assignments

# Manually assign voices to speakers
python3 -m tts_generator.cli input.txt -o output.wav --voices "Provider:Sulafat,Speaker A:Achird"
```

### Style Control
```bash
# Add style/mood direction
python3 -m tts_generator.cli input.txt -o output.wav --style "conversational, warm tone"

# Adjust pause between speakers (default: 300ms)
python3 -m tts_generator.cli input.txt -o output.wav --pause 500
```

### Audiobook Mode (Large Files)
```bash
# Generate audiobook from large text file
python3 -m tts_generator.cli book.txt -o audiobook.wav --audiobook

# Resume interrupted generation
python3 -m tts_generator.cli book.txt -o audiobook.wav --audiobook --resume

# Custom chapter pause (default: 2000ms)
python3 -m tts_generator.cli book.txt -o audiobook.wav --audiobook --chapter-pause 3000
```

Audiobook mode:
- Chunks text to stay under API limits (4KB per request)
- Streams audio directly to disk (memory efficient)
- Saves progress after each chunk for resume capability
- Detects chapter markers for longer pauses

### Web GUI
```bash
# Launch the Gradio web interface
python3 -m tts_generator.gui
```

Features:
- Paste or type conversation text
- Auto-detect speakers with "Detect Speakers" button
- Assign voices to each speaker via dropdowns
- Audiobook mode toggle for large files
- Listen to generated audio in browser

### Using ElevenLabs (Alternative Provider)
```bash
export ELEVENLABS_API_KEY="your-elevenlabs-key"
python3 -m tts_generator.cli input.txt -o output.wav --provider elevenlabs
```

## Input Formats

### Text Format (input.txt)
```
Speaker A: Hello, how are you?
Provider: I'm doing well, thank you.
Speaker A: Great to hear!
```

### JSON Format (input.json)
```json
[
  {"speaker": "Speaker A", "text": "Hello, how are you?"},
  {"speaker": "Provider", "text": "I'm doing well, thank you."},
  {"speaker": "Speaker A", "text": "Great to hear!"}
]
```

## Available Voices

| Voice | Characteristic | Gender |
|-------|----------------|--------|
| Kore | Firm | Female |
| Charon | Informative | Male |
| Sulafat | Warm | Female |
| Puck | Upbeat | Male |
| Aoede | Breezy | Female |
| Achird | Friendly | Male |
| Gacrux | Mature | Female |
| Achernar | Soft | Female |
| Fenrir | Excitable | Male |
| Leda | Youthful | Female |

Run `python3 -m tts_generator.cli --list-voices` for the full list of 30 voices.

## Default Voice Assignments

The tool automatically assigns appropriate voices:
- **Provider/Doctor**: Charon (Informative, Male)
- **Speaker A**: Kore (Firm, Female)
- **Speaker B**: Puck (Upbeat, Male)
- **Speaker C**: Fenrir (Excitable, Male)
- **Patient**: Achernar (Soft, Female)
- **Nurse**: Sulafat (Warm, Female)

## Notes

- Supports unlimited speakers (automatically handles Google's 2-speaker-per-call limit via audio splicing)
- Output is 24kHz mono WAV
- For MP3 output, install ffmpeg: `brew install ffmpeg`
- Standard mode: best for short conversations (under ~10 minutes of audio)
- Audiobook mode: best for long texts (books, transcripts, etc.) - no practical limit
