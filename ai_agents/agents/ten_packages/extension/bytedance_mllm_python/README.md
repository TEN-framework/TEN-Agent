# ByteDance Realtime MLLM Extension

This extension connects TEN `AsyncMLLMBaseExtension` to Volcengine Doubao
end-to-end realtime speech model API.

It sends mono PCM16 16 kHz audio to Doubao and requests mono PCM16 24 kHz audio
back from the service.

## Configuration

Configure provider values under `params`:

```json
{
  "params": {
    "app_id": "${env:DOUBAO_REALTIME_APP_ID}",
    "access_key": "${env:DOUBAO_REALTIME_ACCESS_KEY}",
    "model": "1.2.1.1",
    "speaker": "zh_female_vv_jupiter_bigtts",
    "bot_name": "豆包",
    "prompt": "You are a concise voice assistant."
  }
}
```

Optional nested `asr`, `tts`, and `dialog` objects are merged into the
`StartSession` payload.
