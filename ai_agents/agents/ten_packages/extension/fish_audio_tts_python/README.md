# fish_audio_tts_python

<!-- brief introduction for the extension -->

## Features

<!-- main features introduction -->

- Direct WebSocket streaming TTS through Fish Audio's timestamped endpoint.
- WebSocket observability with a W3C `traceparent` header.
- Logs the Fish Audio handshake response headers, including
  `x-fishaudio-datacenter` and the generated trace ID.

## API

Refer to `api` definition in [manifest.json] and default values in [property.json](property.json).

<!-- Additional API.md can be referred to if extra introduction needed -->

## Development

### Build

<!-- build dependencies and steps -->

### Unit test

<!-- how to do unit test for the extension -->

## Misc

<!-- others if applicable -->

### Observability

Each TTS request connects to
`wss://api.fish.audio/v1/tts/live/with-timestamp`, sends MessagePack
`start`, `text`, and `stop` events, and forwards the binary `audio` payloads.
The timestamp and alignment fields are currently ignored. Each request sends
a new W3C `traceparent` value on the WebSocket upgrade request. The response
headers and trace ID are written to the extension logs after the handshake, so
the `x-fishaudio-datacenter` value can be shared with Fish Audio support for
latency analysis.

### raise OSError('PortAudio library not found')
apt-get update && apt-get install -y portaudio19-dev python3-pyaudio
