# oruk_realtime_asr_python

Streaming speech-to-text for TEN using **Oruk's realtime API**. It streams audio
over an authenticated WebSocket and surfaces interim transcript deltas and a
final transcript per turn, plus optional **phrase-emotion estimates** (vocal
expression descriptors that arrive independently of the transcript).

> Phrase-emotion estimates describe how speech sounds. They are not verified
> assessments of a person's internal state.

For a fully local, key-free option, use `oruk_asr_python` (Orukeet on CPU).

## Audio

Mono **PCM16 at 16 kHz** (`pcm_frame`).

## Credentials

The Oruk API key is read from `params.api_key` / `params.key` (typically wired
from `${env:ORUK_API_KEY}`) and sent only in the WebSocket upgrade's
`Authorization` header — never in the URL.

## Configuration (`property.json` → `params`)

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `key` / `api_key` | string | — | Oruk API key (required). |
| `url` | string | `wss://speech-api.oruk.ai/v1/realtime?model=oruk-realtime` | Must be `wss`. |
| `sample_rate` | int | `16000` | Must be 16000. |
| `language` | string | `"auto"` | Oruk locale or `"auto"`. |
| `phrase_emotions` | bool | `true` | Emit phrase-emotion estimates. |
| `diarize` | bool | `false` | Speaker separation. |
| `result_language_default` | string | derived | Locale stamped on results when the server omits one. |

## Turn model

The Oruk realtime socket commits **one turn per connection**: the extension
streams PCM, emits interim results, and on finalize sends a commit to receive
the final transcript, phrase-emotion estimates, and usage before the server
closes. It then reconnects for the next turn. Audio that arrives during a
reconnect is buffered (keep strategy) so the next utterance is not lost.

Phrase-emotion estimates and usage are reported via the vendor-metrics channel;
estimates available before the final transcript are also attached to the final
result's `metadata.asr_info.phrases`.

## Lifecycle and validation

Invalid configuration prevents connection attempts. Finalize completion is
bounded, and timestamps preserve the audio timeline across turns and reconnects.
The realtime extension ignores callbacks from replaced sockets, closes each
turn's transport, and uses one recovery task with at most five attempts and
exponential backoff. Stop cancels and awaits recovery.

Run these commands from `ai_agents/` in the supported Linux development image
(`ghcr.io/ten-framework/ten_agent_build:0.7.14`):

```bash
task test-extension EXTENSION=agents/ten_packages/extension/oruk_realtime_asr_python
task asr-guarder-test EXTENSION=oruk_realtime_asr_python CONFIG_DIR=tests/configs
```

Run guarders sequentially. In fresh standalone containers, install the extension
requirements and the installed TEN system packages' `requirements.txt` first;
`tman install --standalone` installs TEN packages, not their Python dependencies.
The guarder install handles its own dependencies.

Offline lifecycle fault-injection tests for both extensions are in
`oruk_realtime_asr_python/tests/unit/test_lifecycle.py`. They exercise the actual
extension and transport methods with a stubbed TEN boundary. The native ASR
guarder separately exercises the real runtime and provider. Long-duration cases
are opt-in and are not included in the default guarder command.

When the recognizer does not report a detected language, results use `und`
(undetermined), or the caller's `result_language_default`. A caller-supplied
locale is metadata, not a detected-language or accuracy result.
