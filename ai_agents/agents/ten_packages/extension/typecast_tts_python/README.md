# Typecast TTS Extension

Typecast text-to-speech extension for TEN Framework.

The extension uses the official `typecast-python` SDK and Typecast's
`/v1/text-to-speech/stream` endpoint. Typecast streams WAV audio at 32 kHz,
16-bit, mono. The extension strips the initial WAV header and forwards PCM16
mono audio to TEN.

## Configuration

```json
{
  "params": {
    "api_key": "<typecast-api-key>",
    "url": "https://api.typecast.ai",
    "voice_id": "tc_60e5426de8b95f1d3000d7b5",
    "model": "ssfm-v30",
    "output": {
      "audio_format": "wav",
      "remove_silence_ms": 0
    }
  },
  "chunk_size": 8192
}
```

`output.audio_format` is forced to `wav` because TEN consumes PCM audio frames.
MP3 streaming would require an additional decoder and is intentionally not used.

### Silence removal

Set `params.output.remove_silence_ms` in this extension's `property.json`, or
under `property.params.output` on the `typecast_tts_python` node in your graph's
`property.json`. The example above opts in with `0`; this is not a required
setting or an automatically selected value.

The value is an integer from **0 to 1000 milliseconds** specifying how much
detected silence to **retain**, rather than how much to remove:

- `0`: remove detected silence for tighter speech playback.
- A positive value, for example `200`: retain that duration of detected silence
  when applying Typecast's silence processing, allowing more breathing room.
- Omitted (or `null` in the SDK configuration): disable this duration-based
  processing and preserve the service's unprocessed silence behavior. The
  extension's shipped default omits the setting.

Choose the value for the desired pacing; it does not need to stay at `0`.
The extension forwards the configured value on each synthesis call, without
switching it based on text or runtime conditions. Update the graph configuration
and restart the extension to apply a different setting.

Typecast performs the silence processing on the server. Changing the setting
can change the returned PCM length and pause timing; it does not change the
32 kHz PCM16 mono format or TEN's chunk size. Audio-end duration is calculated
from PCM actually emitted, so shorter returned audio produces a shorter media
duration. This setting does not guarantee lower time to first byte.

See the [Typecast Python SDK documentation](https://typecast.ai/docs/sdk/python).

## Validation

```bash
tman -y install --standalone
./tests/bin/start
```
