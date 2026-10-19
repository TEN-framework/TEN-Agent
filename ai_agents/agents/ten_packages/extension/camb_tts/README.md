# camb_tts

Camb.ai TTS extension for TEN Framework using the MARS text-to-speech API.

## Features

- MARS model family (mars-flash, mars-pro, mars-instruct)
- 140+ languages supported
- Voice cloning capabilities
- Real-time HTTP streaming
- Model-specific sample rates (22.05kHz / 48kHz)

## API

Refer to `api` definition in [manifest.json](manifest.json) and default values in [property.json](property.json).

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| api_key | string | (required) | Camb.ai API key |
| voice_id | int32 | 147320 | Voice ID |
| language | string | "en-us" | Language code (BCP-47 format) |
| speech_model | string | "mars-flash" | Model selection |
| user_instructions | string | (optional) | Instructions for mars-instruct model |
| format | string | "pcm_s16le" | Output format |

### Available Models

| Model | Sample Rate | Description |
|-------|-------------|-------------|
| `mars-flash` | 22.05kHz | Fast inference (default) |
| `mars-pro` | 48kHz | High quality |
| `mars-instruct` | 22.05kHz | Supports user instructions |

## Development

### Setup

1. Get your API key from [Camb.ai](https://camb.ai)
2. Set environment variable:
   ```bash
   export CAMB_API_KEY=your_key_here
   ```

### Build

Follow the standard TEN Framework extension build process.

### Unit test

Run tests using the standard TEN Framework testing approach.

## Resources

- [Camb.ai API Documentation](https://camb.mintlify.app/)
- [Getting Started](https://camb.mintlify.app/getting-started)
- [API Reference](https://camb.mintlify.app/api-reference/endpoint/create-tts-stream)
