# Speechify TTS Python Extension

A Text-to-Speech extension for TEN Framework using the [Speechify](https://speechify.ai) API.

## Features

- Real-time text-to-speech synthesis via Speechify's `simba-3.2` streaming-native model
- HTTP chunked audio streaming (`POST /v1/audio/stream`) for low-latency playback
- Immediate cancellation support for flush/interrupt scenarios
- Configurable audio parameters (sample rate, language, loudness/text normalization)
- Audio dump functionality for debugging

## Architecture

Unlike ElevenLabs' persistent bidirectional websocket, Speechify's public API is a
one-shot HTTP request/response stream: each TTS request buffers incoming text deltas
until `text_input_end`, then issues a single `POST /v1/audio/stream` call whose
chunked response is forwarded to TEN as they arrive. The `speechify-api` Python SDK
(`AsyncSpeechify`) is used for all outbound calls, with `Speechify-Caller: ten-framework`
set on every request so usage is attributed to this integration.

## API

Refer to the `api` definition in [manifest.json](manifest.json) and default values in
[property.json](property.json).

## Development

### Build

Install dependencies:
```bash
pip install -r requirements.txt
```

### Unit test

Run tests using pytest:
```bash
pytest tests/
```

## Configuration

Configure the extension in `property.json`:

```json
{
  "params": {
    "base_url": "https://api.speechify.ai",
    "key": "your_speechify_api_key",
    "model": "simba-3.2",
    "voice_id": "geffen_32",
    "sample_rate": 24000
  }
}
```

`key` and `voice_id` are required. `base_url` defaults to the public Speechify API and
should not normally be overridden. `model` defaults to `simba-3.2`, the recommended
streaming-native Simba 3 model.

## Documentation

- [API Reference](manifest.json) - Complete API specification
- [Configuration](property.json) - Default configuration values
- [Speechify API docs](https://docs.speechify.ai)
