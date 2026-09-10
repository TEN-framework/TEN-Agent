# Deepdub TTS (Streaming) — Python

TEN extension wrapping Deepdub's text-streaming WebSocket API.

- One persistent WebSocket per extension instance, opened and configured during `on_init` (pre-warmed before the first sentence arrives).
- Each `tts_text_input` fragment is forwarded as a `stream-text` frame, so audio synthesis starts before the LLM has finished producing the full reply.
- The vendor's `isFinished` boundary is used to emit `tts_audio_end` and release the request lock, naturally serialising back-to-back TEN requests on a single connection.

## Required configuration

Provide via `property.json` `params` or environment variables:

| Property          | Env var                        | Notes                                       |
| ----------------- | ------------------------------ | ------------------------------------------- |
| `api_key`         | `DEEPDUB_API_KEY`              | Account API key.                            |
| `url`             | `DEEPDUB_WS_STREAMING_URL`     | Text-streaming WS endpoint URL.             |
| `voice_prompt_id` | `DEEPDUB_VOICE_PROMPT_ID`      | Voice prompt to use for the session.        |
| `model`           | `DEEPDUB_MODEL`                | Defaults to `dd-etts-3.2`.                  |
| `locale`          | `DEEPDUB_LOCALE`               | Defaults to `en-US`.                        |

## Audio output

Defaults to raw PCM (`s16le`) at 48 kHz, mono — fed directly to the framework's audio pipeline without header parsing.

## Constraints

- The streaming WS binds a single voice/locale/model to a connection (set via `stream-config`). Changing voice mid-session would require a reconnect. v1 assumes a single voice per agent session.
- `cancel_tts` (TEN flush) drops the in-flight stream and reconnects.
