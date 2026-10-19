# StepFun ASR Python Extension

StepFun StepAudio 2.5 streaming ASR integration for TEN Framework.

## Configuration

The extension connects to `wss://api.stepfun.com/v1/realtime/asr/stream` with
Bearer authentication. The default model is `stepaudio-2.5-asr-stream`.
StepFun accepts signed 16-bit little-endian mono PCM at 16 kHz.

Set the key in the agent environment:

```bash
STEPFUN_API_KEY=your_stepfun_api_key
```

Example graph node:

```json
{
  "type": "extension",
  "name": "stt",
  "addon": "stepfun_asr_python",
  "extension_group": "stt",
  "property": {
    "params": {
      "api_key": "${env:STEPFUN_API_KEY}",
      "language": "en"
    }
  }
}
```

Supported parameters are exposed in `manifest.json`. `server_vad` enables
StepFun server-side VAD; otherwise the extension commits audio on TEN's
`asr_finalize` input. `full_rerun_on_commit` and
`enable_timestamp_align` are passed through to StepFun.

The extension retains up to 10 MB of unconfirmed PCM so a transient WebSocket
disconnect can replay audio after reconnect. Replayed transcript words are
deduplicated when StepFun supplies word timestamps.
