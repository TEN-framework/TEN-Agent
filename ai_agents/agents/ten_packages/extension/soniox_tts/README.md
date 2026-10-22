# Soniox TTS

Soniox real-time Text-to-Speech extension for TEN Framework.

The extension uses the Soniox WebSocket API at
`wss://tts-rt.soniox.com/tts-websocket`. It sends streamed text and emits raw
signed 16-bit little-endian mono PCM frames through the TEN TTS interface.

## Configuration

Set `SONIOX_API_KEY` in the agent environment. The default configuration uses
the `tts-rt-v2` model, the `en` language, the `Adrian` voice, and 24 kHz PCM.

The supported `sample_rate` values are 8000, 16000, 24000, 44100, and 48000.
`audio_format` must be `pcm_s16le` so the output matches the TEN PCM frame
contract. `speed` accepts values from 0.7 to 1.3.

Optional settings include `language`, `voice`, `model`, `speed`,
`reduce_silence`, `return_timestamps`, `client_reference_id`, `dump`, and
`dump_path`.

## Development

Run the standalone tests with:

```bash
./tests/bin/start
```

Run the extension checks from `ai_agents` with:

```bash
task test-extension EXTENSION=agents/ten_packages/extension/soniox_tts
task tts-guarder-test EXTENSION=soniox_tts
```
