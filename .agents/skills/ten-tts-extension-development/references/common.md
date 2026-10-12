# TEN TTS contract

## Extension surface

`AsyncTTS2BaseExtension` provides lifecycle hooks, the input queue, flush coordination, PCM framing, metrics, and standardized error output. A streaming subclass supplies:

```python
async def request_tts(self, text_input): ...
def vendor(self) -> str: ...
def synthesize_audio_sample_rate(self) -> int: ...
async def cancel_tts(self) -> None: ...
```

`AsyncTTS2HttpExtension` supplies the HTTP request pipeline. An HTTP subclass supplies configuration creation, client creation, vendor name, and output sample rate.

Generated packages should contain `extension.py`, a provider client module, `config.py` when configuration is non-trivial, `addon.py`, `manifest.json`, `property.json`, `requirements.txt`, and `tests/` with a runnable `tests/bin/start`. The manifest must declare the TTS interface and runtime dependency. The property file must expose the provider configuration without embedding secrets.

## Input messages

`tts_text_input` contains a `request_id`, text, optional `text_input_end`, and metadata such as session and turn IDs. Multiple messages may belong to one request. `tts_flush` contains a flush ID and optional metadata and invalidates queued and active work.

## Output messages

- `tts_audio_start`: once per request, before audio.
- `pcm_frame`: signed PCM bytes with the configured sample rate, channels, and sample width.
- `tts_audio_end`: once per request, after all audio. Include the event interval, total audio duration, and an explicit end reason.
- `tts_flush_end`: after flush cleanup completes.
- `tts_text_result`: optional word/segment timing when the provider supplies trustworthy alignment.
- `error`: standardized TEN error with module, code, message, and optional vendor information.
- Metrics: at least TTFB when audio is produced, plus usage or request metrics when available.

## Audio rules

Provider chunks may split a sample. Buffer leftover bytes until a complete `sample_width * channels` unit exists. Count duration from bytes actually emitted: `bytes / (sample_width * channels * sample_rate)`. Do not infer duration from chunk count or wall-clock time.

## Completion and flush

A request is complete only when the provider’s terminal event has arrived, or when the request is intentionally interrupted or fails. Flush must cancel or close provider work, clear pending input, invalidate late callbacks, finish any active request with an interrupted/error reason, then emit `tts_flush_end`. No stale audio may follow flush completion.

## State, callbacks, and metrics

Report state through the extension’s existing state/metric callbacks using exactly these states and triggers:

| State | Emit when |
|---|---|
| `connecting` | The connection attempt is about to be sent/started. |
| `connected` | The provider confirms the connection is ready for text. |
| `processing` | The first text chunk for a request ID is about to be sent to the provider. |
| `finalizing` | The final text chunk for a request ID has been sent to the provider. |
| `disconnected` | An established connection drops during normal operation, before recovery or retry. |
| `reconnecting` | A retry attempt starts after a disconnect or recoverable connection error. |
| `interrupted` | TEN flush is received and active provider work is being cancelled. |
| `error` | An internal error or provider error response is received. |
| `closed` | The extension/provider connection is permanently closed during shutdown or terminal teardown. |

Do not emit `processing` when text is merely placed into an internal queue: emit it immediately before the actual provider send for that request ID. Do not use `closed` for a transient disconnect. State callbacks must not expose credentials. Provider callbacks must be normalized into one of: audio chunk, request complete, connection event, or `ModuleError` with vendor name/code/message. Send TTFB only once per request ID, before its audio end; send error before error audio end when both are required.

## Provider-to-TEN mapping template

For every provider contract, write and implement a mapping table like this before coding:

| Provider signal | Required adapter action | TEN output/state |
|---|---|---|
| Connection attempt | Start/open transport | `connecting` |
| Connection ready/handshake success | Mark transport ready | `connected` |
| First text for request ID is sent | Record TTFB start immediately before send | `processing` |
| Last text for request ID is sent | Mark input finalizing | `finalizing` |
| First valid audio bytes | Start request output and compute TTFB | `tts_audio_start`, TTFB metric, `pcm_frame` |
| Audio bytes | Validate/alignment-buffer and emit | `pcm_frame` |
| Provider completion | Flush dump and close request | `tts_audio_end(reason=REQUEST_END)` |
| Provider error response | Normalize vendor code/message | `error`, state `error`, and terminal audio end when required |
| Connection drop | Invalidate old callbacks and preserve only replayable input | `disconnected`, then `reconnecting` |
| TEN flush | Cancel, discard queued/late data, invalidate session | `interrupted`, `tts_flush_end` |
| Permanent shutdown | Stop tasks and close transport | `closed` |

The provider’s field names may differ, but every row must have an explicit implementation path and test.

## Configuration precedence

Use explicit top-level fields for TEN-owned behavior (`url`, `headers`, audio format, dump, dump path, and provider credential fields that the extension documents). Keep provider-specific synthesis options in `params` and pass them through after removing only fields consumed to build the endpoint or authentication.

For endpoint selection, apply this deterministic order:

1. non-empty top-level `url`;
2. non-empty `params.url`;
3. `params.base_url` combined with the provider’s endpoint path;
4. the provider default URL.

Once selected, remove endpoint-only `url`/`base_url` keys from the provider request body. A top-level URL always wins over values nested in `params`; `base_url` is a fallback, never a second request destination.

For headers, start with provider-required defaults, derive an authorization header from a credential in `params` only when the corresponding explicit header is absent, then overlay top-level `headers`. Thus an explicit header wins over a generated header, and top-level headers win over SDK/client defaults for the same key. Do not send the same secret through both a header and request body unless the provider protocol explicitly requires it. Preserve unrelated `params` as provider payload/config passthrough.

## Acceptance tests

Cover event ordering, empty/whitespace input, invalid/missing credentials, malformed and long text, exact duration, TTFB, dump output, flush during synthesis, shutdown, and request isolation. Add reconnect tests whenever reconnect is implemented or promised.

Run the repository’s format and lint tasks from the agent workspace (`task format`, `task lint`, and the focused `task lint-extension EXTENSION=...`), the generated extension’s standalone test command, and the TTS guarder with the extension’s test configs. Include tests for config redaction, endpoint/header precedence, per-request dump filenames, state/error callbacks, pre-connected startup, reconnect after abnormal disconnect, and flush dropping unsent text and unread audio.

For HTTP, rely on `AsyncTTS2HttpExtension` for the common request cancellation, flush coordination, audio-end, and client lifecycle behavior. Implement only the HTTP client contract and verify the inherited behavior with tests; do not duplicate the base request pipeline. For WebSocket/SDK flush, cancel the provider operation and establish a fresh ready connection, because queued and unread data from the old session must be discarded.

The real-provider acceptance gate is mandatory: configure a valid provider key and run the full TTS guarder, including its audio, flush, error, metrics, dump, and request-isolation cases. A mock provider may supplement this suite but cannot substitute for it. If credentials, network access, or provider quota prevent the guarder from running, report the extension as not validated rather than marking it complete.

## Provider-free validation stage

Use this stage only when no real provider is available. Create a local deterministic mock at the protocol boundary, without changing the extension’s production path. The mock must exercise:

- connection startup and ready handshake;
- chunked PCM, including chunks that split a sample boundary;
- delayed first audio for TTFB;
- normal completion and empty input;
- provider error response;
- abnormal disconnect followed by reconnect;
- queued text that must be discarded by flush;
- unread/late audio that must be discarded by flush;
- multiple request IDs or contexts when the transport supports them;
- word alignment if the adapter claims to support it.

Run package/file checks, format, lint, extension-local tests, and these mock scenarios. Record the result as **mock validation only**. Do not run a fake provider through the real-key guarder and do not report the extension as production-complete until a real key and provider endpoint have passed the full guarder.

## Generated-code self-check

Before running tests, verify all of the following:

- The package contains the required files and a runnable `tests/bin/start`.
- The manifest declares the TTS interface and all runtime dependencies; the property file contains no secret.
- HTTP inherits `AsyncTTS2HttpExtension`; WebSocket and SDK implementations inherit `AsyncTTS2BaseExtension`.
- Streaming transports connect during startup and expose the nine state behaviors above with the specified triggers.
- `processing` timing is recorded immediately before the first actual provider send for a request ID; connection time and queue time are excluded from TTFB.
- `finalizing` is emitted after the last text send, and provider completion—not merely queue exhaustion—drives `tts_audio_end`.
- Every request ID has an isolated PCM dump path, writer, byte count, and terminal cleanup.
- Config logs redact API keys, tokens, authorization headers, and nested secret fields.
- Top-level `url` and `headers` precedence over `params.url`, `params.base_url`, generated auth headers, and client defaults is tested.
- Flush cancels provider work, discards unsent text and unread/late audio, invalidates old callbacks, and prevents output after `tts_flush_end`.
- `tts_audio_end` reports accurate interval, PCM duration, and reason for normal, empty, interrupted, and error paths.
- Provider errors and callbacks preserve request correlation and vendor metadata without leaking secrets.
- Standalone tests, formatting, lint, and the real-key TTS guarder are all scheduled and their results will be reported.
