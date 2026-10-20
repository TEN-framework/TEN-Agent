# Default Async Python Extension

<!-- Brief introduction for the extension -->

## Features

<!-- Main features introduction -->

- xxx features

## API

Refer to `api` definition in [manifest.json] and default values in [property.json].

<!-- Additional API.md can be referred to if extra introduction needed -->

## Development

### Build

<!-- Build dependencies and steps -->

### Unit test

<!-- How to do unit test for the extension -->

## Misc

<!-- Others if applicable -->

## Graph commands and events

Clients can send a TEN command through the graph's configured command routes:

```json
{"type":"cmd","name":"create_session","request_id":"case-1","data":{"model":"custom"}}
```

The response preserves `name` and `request_id`:

```json
{"type":"cmd_result","name":"create_session","request_id":"case-1","status":0,"data":{"response_json":"{\"type\":\"session.created\",\"session_id\":7}"}}
```

`status` is the TEN status code (`0` for success, `1` for error). Routing failures
and timeouts return an error status and `data.error`. `command_timeout_ms`
defaults to 30000. Commands use graph routes; the client cannot select a TEN
destination. Wait for a command result before sending audio that depends on it.

Data routed into this extension is forwarded as
`{"type":"data","name":"<TEN data name>","data":{...}}`, preserving the TEN
properties. This includes ASR transcripts, Agora Mind events, TTS text and audio
lifecycle events, metrics, and errors when connected in the graph. Audio messages
continue to use base64 PCM and include their actual sample format in `metadata`.

Decoded input audio must contain at least one complete sample frame: its byte
count must be a positive multiple of `channels * bytes_per_sample`. Invalid
lengths return `{"type":"error","error":"..."}` before allocating a TEN
AudioFrame or writing an audio dump. The same client can continue sending valid
audio after an error.
