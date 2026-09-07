# Sarvam HTTP TTS Extension

This extension provides text-to-speech functionality using the Sarvam AI TTS API.

## Features

- Text-to-speech synthesis using Sarvam AI's HTTP API
- Supports multiple Indian languages (BCP-47 format)
- Multiple speaker voices supported by Sarvam's Bulbul models
- Configurable pace, with legacy pitch and loudness support for bulbul:v2
- Base64 WAV decoding and conversion to PCM
- Built-in retry mechanism for robust connections

## Configuration

The extension can be configured through your property.json:

```json
{
  "params": {
    "api_subscription_key": "your-sarvam-api-subscription-key",
    "target_language_code": "hi-IN",
    "speaker": "shubh",
    "pace": 1.0,
    "speech_sample_rate": 24000,
    "enable_preprocessing": false,
    "model": "bulbul:v3"
  }
}
```

### Configuration Options

**Top-level properties:**
- `dump` (optional): Enable audio dumping for debugging (default: false)
- `dump_path` (optional): Path for audio dumps (default: extension directory + "sarvam_tts_in.pcm")

**Parameters inside `params` object:**
- `api_subscription_key` (required): Your Sarvam API subscription key
- `target_language_code` (required): Language code in BCP-47 format (e.g., "hi-IN", "bn-IN", "en-IN")
- `speaker` (optional): Speaker voice to use (default: "shubh")
- `pitch` (optional): Pitch control for bulbul:v2 only, range -0.75 to 0.75
- `pace` (optional): Speech speed, range 0.5 to 2.0 (default: 1.0)
- `loudness` (optional): Audio loudness for bulbul:v2 only, range 0.3 to 3.0
- `speech_sample_rate` (optional): Sample rate in Hz - 8000, 16000, 22050, 24000 (default: 24000)
- `enable_preprocessing` (optional): Enable normalization of English words and numeric entities (default: false)
- `model` (optional): TTS model to use (default: "bulbul:v3")
- `output_audio_codec` (optional): Audio codec for output

## API Reference

Refer to the [Sarvam TTS API documentation](https://docs.sarvam.ai/api-reference/text-to-speech/convert) for detailed API information.

## Architecture

This extension follows the `AsyncTTS2HttpExtension` pattern:

- `extension.py`: Main extension class inheriting from `AsyncTTS2HttpExtension`
- `sarvam_tts.py`: Client implementation (`SarvamTTSClient`) with base64 WAV decoding
- `config.py`: Configuration model extending `AsyncTTS2HttpConfig`

The configuration uses a `params` dict to encapsulate all TTS-specific parameters, keeping the top level clean with only framework-related properties (`dump`, `dump_path`).

## Notes

- Each text should be no longer than 1500 characters
- Supports code-mixed text (English and Indic languages)
- For numbers larger than 4 digits, use commas (e.g., '10,000' instead of '10000') for proper pronunciation
