# Blaze STT Extension for TEN Framework

Blaze Speech-to-Text (STT) extension for [TEN Framework](https://github.com/TEN-framework/ten-framework).

## Installation

```bash
pip install -r requirements.txt
```

Or install dependencies directly:

```bash
pip install httpx pydantic
```

## Configuration

### Environment Variables

```bash
export BLAZE_API_KEY="your-api-key-here"
export BLAZE_STT_API_KEY="$BLAZE_API_KEY"
export BLAZE_STT_API_URL="https://api.blaze.vn"
```

### Property.json (TEN Framework)

```json
{
    "dump": false,
    "dump_path": "./",
    "params": {
        "api_url": "${env:BLAZE_STT_API_URL|https://api.blaze.vn}",
        "api_key": "${env:BLAZE_STT_API_KEY}",
        "language": "vi",
        "sample_rate": 16000,
        "timeout": 3600
    }
}
```

### Voice assistant graphs

In `agents/examples/voice-assistant`:

| Graph name | STT | TTS |
| ---------- | --- | --- |
| `voice_assistant_blaze_full` | Blaze | Blaze |

**Note:** Blaze STT is batch HTTP (`/v1/stt/execute`). The TEN extension buffers
PCM and submits a WAV on finalize (turn-based), not true streaming ASR.

### Live smoke test

```bash
python ai_agents/scripts/smoke_blaze.py
python ai_agents/scripts/smoke_blaze.py --skip-tts --audio /path/to/sample.wav
```

## Usage

### As TEN Framework Extension

```python
from blaze_stt_python import BlazeSTTExtension

# Initialize extension (can accept dict config from TEN framework)
stt = BlazeSTTExtension(config={
    "api_url": "http://localhost:8000",
    "api_key": "your-api-key",
    "language": "vi",
})

# Process audio using TEN framework interface
result = stt.process({
    "audio_data": audio_bytes,
    "audio_content_type": "audio/wav",
    "language": "vi",
})

print(result["transcription"])

# Get extension metadata
metadata = stt.get_metadata()
print(metadata)
```

### As Direct Extension

```python
from blaze_stt_python import BlazeSTTExtension, BlazeSTTConfig

# Initialize extension
config = BlazeSTTConfig(
    api_url="http://localhost:8000",
    api_key="your-api-key",
    default_language="vi",
)
stt = BlazeSTTExtension(config=config)

# Transcribe audio
result = stt.transcribe(
    audio_data=audio_bytes,
    audio_content_type="audio/wav",
    language="vi",
)

print(result["transcription"])
```

## API Reference

### BlazeSTTExtension

**TEN Framework Interface Methods:**
- `process(input_data)` - Process audio and return transcription (TEN framework interface)
- `get_metadata()` - Get extension metadata (TEN framework interface)

**Direct Methods:**

- `transcribe(audio_data, audio_file, audio_content_type, language)` - Transcribe audio data (bytes) or file (UploadFile)
- `get_job_status(job_id)` - Get transcription job status

## Supported Formats

- `audio/wav` - WAV format
- `audio/mpeg` - MP3 format
- `audio/webm` - WebM format
- `audio/ogg` - OGG format

## License

This extension is provided as-is for use with the TEN Framework and Blaze services.
