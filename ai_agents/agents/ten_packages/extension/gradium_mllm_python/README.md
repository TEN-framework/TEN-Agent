# gradium_mllm_python

Real-time speech-to-speech (S2S) translation extension for TEN, using
[Gradium](https://gradium.ai/)'s Translation API. Implements the same
`AsyncMLLMBaseExtension` contract as `openai_mllm_python`, `azure_mllm_python`,
`gemini_mllm_python`, `glm_mllm_python`, and `stepfun_mllm_python`, so it can
be dropped into any graph node expecting an "mllm" addon.

## Status: protocol confirmed by Gradium, not yet run against a live endpoint

The full `/api/speech/s2s` protocol below was confirmed directly by Gradium
(Pratim, 2026-08-20), building on top of `gradium_asr_python` and
`gradium_tts_python`, which already talk to Gradium's real ASR/TTS websocket
APIs in this repo.

| | Value |
|---|---|
| Auth | header `x-api-key: <api_key>` |
| Host + path | `wss://<region>.api.gradium.ai/api/speech/s2s`, region `us` or `eu` |
| Handshake | client sends `{"type": "setup", ...}` (see below), waits for `{"type": "ready"}` before streaming audio |
| Setup payload | `model_name: "s2s-translate"`, `stt_model_name: "stt-translate"`, `tts_model_name: "default"`, `input_format`/`output_format: "pcm"` (24kHz in, 48kHz out), `voice_id`, and `json_config: {"target_language": ...}` -- **`target_language` nests inside `json_config`, it is not a top-level field** |
| Audio frames (both directions) | `{"type": "audio", "audio": "<base64 pcm16le>"}` |
| Text frames | `{"type": "text", "text": ..., "final": bool, ...}` -- **translated output only**, there is no separate source-language transcript event |
| End of turn | `{"type": "end_of_stream"}` |
| Errors | `{"type": "error", "message": ..., "code": ...}` |
| VAD | **not part of this protocol** -- only `ready`/`audio`/`text`/`end_of_stream`/`error` are ever sent |

Supported `target_language` values (confirmed): `en`, `fr`, `de`, `es`, `pt`.

`voice_id` must be a voice belonging to `target_language`, or Gradium will
reject/mis-synthesize -- `on_init` raises if it's unset rather than guessing.
Default is `YTpq7expH9539ERJ` ("Emma", English -- confirmed by Gradium,
2026-08-24), matching the default `target_language: "en"`. For other
languages, override both `voice_id` and `target_language` together (e.g. via
`GRADIUM_S2S_VOICE_ID` for the demo graph). Per Pratim, Gradium's voice
catalog is also queryable through their API -- not yet wired up here, so
picking a voice for a new language is still a manual lookup for now.

This has been run and passes end-to-end against a mocked Gradium client (see
Tests below), including a real shutdown-deadlock bug caught and fixed by
actually running it. It has **not** yet been run against Gradium's live
endpoint -- that's still the next step, on Ben's TEN dev server.

## Tests

`tests/` mirrors `gradium_tts_python`'s pattern: a real TEN runtime
(`tests/conftest.py`'s `FakeApp`) drives the actual extension lifecycle via
`AsyncExtensionTester`, with only `GradiumS2SClient` mocked (`tests/gradium_mocks.py`)
-- no live Gradium connection or real `voice_id` needed. Covers: session-ready
+ translated text/audio routing (`test_basic.py::test_session_ready_and_translated_output`),
server-side error propagation, connect failures, and missing
`api_key`/`voice_id` being reported cleanly instead of crashing the
extension. `tests/test_config.py` separately unit-tests `GradiumMLLMConfig`
(no TEN runtime needed) -- in particular the `json_config` nesting for
`target_language`, which was wrong in the initial scaffold.

Run from `ai_agents/` inside the dev container:
```bash
task test-extension EXTENSION=agents/ten_packages/extension/gradium_mllm_python
```

## Properties

Refer to `api` definition in [manifest.json](manifest.json) and default
values in [property.json](property.json).

| **Property** | **Type** | **Description** |
|---|---|---|
| `api_key` | `string` | Gradium API key (sent as the `x-api-key` header) |
| `region` | `string` | `us` or `eu` -- selects the websocket host |
| `base_url` | `string` | Optional explicit host override, skips region lookup |
| `path` | `string` | Websocket path (`/api/speech/s2s`) |
| `model_name` | `string` | Speech-to-speech model name (`s2s-translate`) |
| `stt_model_name` | `string` | ASR-leg model (`stt-translate`) |
| `tts_model_name` | `string` | TTS-leg model (`default`) |
| `voice_id` | `string` | Voice for the synthesized translated speech -- **required**, must belong to `target_language` |
| `target_language` | `string` | Language to translate into (`en`/`fr`/`de`/`es`/`pt` confirmed); sent nested in `json_config`, not top-level, on the wire |
| `input_format` | `string` | Input audio format (`pcm`) |
| `output_format` | `string` | Output audio format (`pcm`, `pcm_16000`, `pcm_24000`) |
| `input_sample_rate` | `int32` | Input PCM sample rate, Hz |
| `dump` / `dump_path` | `bool` / `string` | Audio dump for debugging (from the shared mllm interface) |

## Not implemented

Gradium's S2S translation is a continuous audio pipe, not a tool-calling
conversational LLM. `send_client_message_item`, `send_client_create_response`,
`send_client_register_tool`, and `send_client_function_call_output` are all
no-ops (logged at debug level) -- there's no known Gradium equivalent for
injecting messages/tools into a translation stream. Revisit if that turns
out to be wrong.

### Audio Frame In / Out

| **Name** | **Description** |
|---|---|
| `pcm_frame` | mic audio in / translated speech out |

### Data Out

`mllm_server_session_ready`, `mllm_server_output_transcript`, `error` (from
the shared `mllm-interface.json` contract).
