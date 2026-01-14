# Agent Instructions: TTS Generator

## Overview
This tool converts multi-speaker conversation transcripts into audio using Google AI Studio TTS.

## Prerequisites
- Python 3.9+
- Google API key with Gemini API access (get one at https://aistudio.google.com/apikey)

## Quick Start Commands

```bash
# Step 1: Navigate to project
cd tts-generator

# Step 2: Install dependencies (if not already installed)
python3 -m pip install -r requirements.txt

# Step 3: Set API key
export GOOGLE_API_KEY="your-google-api-key"

# Step 4: Run TTS generation
python3 -m tts_generator.cli examples/sample_conversation.txt -o output.wav
```

## How to Use

### Generate Audio from Text File
```bash
python3 -m tts_generator.cli <input_file> -o <output_file.wav>
```

### Input File Format
Create a text file with this format:
```
Speaker Name: Dialogue text here.
Other Speaker: Their response.
```

Example:
```
Provider: How are you feeling today?
Patient: Much better, thank you.
Provider: That's great to hear.
```

### Command Options

| Option | Description | Example |
|--------|-------------|---------|
| `-o, --output` | Output file path | `-o output.wav` |
| `--voices` | Manual voice assignment | `--voices "Provider:Charon,Patient:Achernar"` |
| `--show-assignments` | Display voice assignments | `--show-assignments` |
| `--style` | Style/mood direction | `--style "calm, professional"` |
| `--pause` | Pause between speakers (ms) | `--pause 400` |
| `--list-voices` | Show available voices | `--list-voices` |
| `--provider` | TTS provider (google/elevenlabs) | `--provider google` |

## Workflow for Agent

1. **Receive conversation transcript** from user
2. **Save transcript** to a `.txt` file in the examples folder
3. **Run the TTS command**:
   ```bash
   python3 -m tts_generator.cli examples/<filename>.txt -o <output_name>.wav --show-assignments
   ```
4. **Verify output** by checking file exists and size
5. **Report results** to user including duration and voice assignments

## Example Agent Workflow

```bash
# Save user's conversation to file
cat > examples/user_conversation.txt << 'EOF'
Doctor: Good morning, how can I help you today?
Patient: I've been having headaches for the past week.
Doctor: I see. Let me ask you a few questions about that.
EOF

# Generate audio
python3 -m tts_generator.cli examples/user_conversation.txt -o user_audio.wav --show-assignments

# Check output
ls -la user_audio.wav
```

## Troubleshooting

### "API key required" error
```bash
export GOOGLE_API_KEY="your-key-here"
```

### "Module not found" error
```bash
python3 -m pip install -r requirements.txt
```

### Warnings about ffmpeg
These are safe to ignore for WAV output. For MP3, install ffmpeg:
```bash
brew install ffmpeg
```

## File Locations

- **Input examples**: `examples/`
- **Main module**: `tts_generator/`
- **Helper scripts**: `scripts/`

## Multi-Speaker Handling

The tool automatically handles conversations with 3+ speakers by:
1. Grouping dialogue into 2-speaker segments
2. Generating audio for each segment
3. Splicing segments together with pauses

No special configuration needed - just include all speakers in your input file.
