# OpenAI ASR Python Extension

A Python extension for OpenAI's Automatic Speech Recognition (ASR) service, providing real-time speech-to-text conversion capabilities with full async support using OpenAI's Realtime transcription API (GA).

## Features

- **Full Async Support**: Built with complete asynchronous architecture for high-performance speech recognition
- **Real-time Streaming**: Supports real-time audio streaming with low latency using OpenAI's WebSocket API
- **OpenAI Realtime API**: Uses OpenAI's GA Realtime transcription API via `session.update`
- **PCM16 Audio**: Accepts arbitrary input sample rates and resamples to 24 kHz PCM16 before sending
- **Audio Dumping**: Optional audio recording for debugging and analysis
- **Configurable Logging**: Adjustable log levels for debugging
- **Error Handling**: Comprehensive error handling with detailed logging
- **Multi-language Support**: Supports multiple languages through OpenAI's transcription models
- **Noise Reduction**: Optional noise reduction capabilities
- **Turn Detection**: Configurable turn detection for conversation analysis

## Configuration

The extension requires the following configuration parameters:

### Required Parameters

- `api_key`: OpenAI API key for authentication
- `params`: OpenAI ASR request parameters including audio format and transcription settings

### Optional Parameters

- `organization`: OpenAI organization ID (optional)
- `project`: OpenAI project ID (optional)
- `base_url`: Custom WebSocket base URL (optional)
- `dump`: Enable audio dumping (default: false)
- `dump_path`: Path for dumped audio files (default: "openai_asr_in.pcm")
- `log_level`: Logging level (default: "INFO")

### Example Configuration

```json
{
  "params": {
    "api_key": "your_openai_api_key",
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
      "model": "whisper-1",
      "prompt": "",
      "language": "en"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 500
    }
  },
  "dump": false,
  "log_level": "INFO"
}
```

Optional connection settings such as `organization`, `project`, and `base_url` belong under `params`.

## API

The extension implements the `AsyncASRBaseExtension` interface and provides the following key methods:

### Core Methods

- `on_init()`: Initialize the OpenAI ASR client and configuration
- `start_connection()`: Establish connection to OpenAI ASR service
- `stop_connection()`: Close connection to ASR service
- `send_audio()`: Send audio frames for recognition
- `finalize()`: Finalize the current recognition session

### Event Handlers

- `on_asr_start()`: Called when ASR session starts
- `on_asr_delta()`: Called when transcription delta is received
- `on_asr_completed()`: Called when transcription is completed
- `on_asr_committed()`: Called when audio buffer is committed
- `on_asr_server_error()`: Called when server error occurs
- `on_asr_client_error()`: Called when client error occurs

## Dependencies

- `typing_extensions`: For type hints
- `pydantic`: For configuration validation and data models
- `websockets`: For WebSocket communication
- `openai`: OpenAI Python client library
- `pytest`: For testing (development dependency)

## Development

### Building

The extension is built as part of the TEN Framework build system. No additional build steps are required.

### Testing

Run the unit tests using:

```bash
pytest tests/
```

The extension includes comprehensive tests for:
- Configuration validation
- Audio processing
- Error handling
- Connection management
- Transcription result handling

## Usage

1. **Installation**: The extension is automatically installed with the TEN Framework
2. **Configuration**: Set up your OpenAI API credentials and parameters
3. **Integration**: Use the extension through the TEN Framework ASR interface
4. **Monitoring**: Check logs for debugging and monitoring

## Error Handling

The extension provides detailed error information through:
- Module error codes
- OpenAI-specific error details
- Comprehensive logging
- Graceful degradation

## Performance

- **Low Latency**: Optimized for real-time processing using OpenAI's streaming API
- **High Throughput**: Efficient audio frame processing
- **Memory Efficient**: Minimal memory footprint
- **Connection Reuse**: Maintains persistent WebSocket connections

## Security

- **Credential Encryption**: Sensitive credentials are encrypted in configuration
- **Secure Communication**: Uses secure WebSocket connections to OpenAI
- **Input Validation**: Comprehensive input validation and sanitization

## OpenAI Models Supported

The extension supports various OpenAI transcription models:
- `whisper-1`: Standard Whisper model
- `gpt-4o-transcribe`: GPT-4o transcription model
- `gpt-4o-mini-transcribe`: GPT-4o mini transcription model

## Audio Format Support

- **PCM16** (recommended): The extension resamples incoming audio to 24 kHz PCM16 before sending to OpenAI. Set `input_audio_format` to `"pcm16"`.
- **G711 U-law / A-law**: Accepted in configuration for forward compatibility, but the extension currently always sends resampled PCM16 regardless of this setting.

## Troubleshooting

### Common Issues

1. **Connection Failures**: Check API key and network connectivity
2. **Audio Quality Issues**: Verify audio format and sample rate settings
3. **Performance Problems**: Adjust buffer settings and model selection
4. **Logging Issues**: Configure appropriate log levels

### Debug Mode

Enable debug mode by setting `dump: true` in configuration to record audio for analysis.

## License

This extension is part of the TEN Framework and is licensed under the Apache License, Version 2.0.
