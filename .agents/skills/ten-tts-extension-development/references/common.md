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

Generated packages should contain `__init__.py`, `addon.py`, `extension.py`, a provider client module, `config.py` when configuration is non-trivial, `manifest.json`, `property.json`, `requirements.txt`, and `tests/` with a runnable `tests/bin/start`. `__init__.py` must contain `from . import addon`; the Python addon loader imports the package itself, so a namespace package will not execute registration. The manifest must declare the TTS interface and runtime dependency. The property file must expose the provider configuration without embedding secrets.

## Input messages

`tts_text_input` contains a `request_id`, text, optional `text_input_end`, and metadata such as session and turn IDs. Multiple messages may belong to one request. `tts_flush` contains a flush ID and optional metadata and invalidates queued and active work.

## Output messages

- `tts_audio_start`: once per request, before audio.
- `pcm_frame`: signed PCM bytes with the configured sample rate, channels, and sample width.
- `tts_audio_end`: once per request after audio has started, after all emitted audio. Include `request_event_interval_ms`, total audio duration, and an explicit end reason. `request_event_interval_ms` is the monotonic elapsed time from emitting `tts_audio_start` to emitting `tts_audio_end`; it excludes queueing, connection setup, provider latency before audio, and TTFB. Use `0` when no audio start was emitted.
- `tts_flush_end`: after flush cleanup completes.
- `tts_text_result`: optional word/segment timing when the provider supplies trustworthy alignment.
- `error`: standardized TEN error with module, code, message, and optional vendor information.
- Metrics: at least TTFB when audio is produced, plus usage or request metrics when available.

## Audio rules

Provider chunks may split a sample. Buffer leftover bytes until a complete `sample_width * channels` unit exists. Count duration from bytes actually emitted: `bytes / (sample_width * channels * sample_rate)`. Do not infer duration from chunk count or wall-clock time. Measure `request_event_interval_ms` with a monotonic clock from the audio-start emission to the audio-end emission.

## Completion and flush

A successful request is complete only when the logical input is complete (`text_input_end`), the provider’s terminal event has arrived for the work belonging to that request, and no provider work remains for the same request ID. A provider END received after an earlier text chunk must not close a request that may receive more text. On successful completion, send `tts_audio_end()` and then call `finish_request()`; `send_tts_audio_end()` does not perform the base-class request transition by itself.

Terminal errors are not subject to the successful-completion gate. Report the error and, if `tts_audio_start` was emitted, send `tts_audio_end(reason=ERROR)` with the duration emitted so far; then call `finish_request()` regardless of `text_input_end`. If no audio started, call `finish_request()` without an audio end. A recoverable error must keep the request active so retry can continue. These rules prevent a failed request from continuing to own `_processing_request_id` and indefinitely buffering later request IDs. Flush remains owned by the base class as described below.

For a flush, the base class cancels the current task, clears input and buffered requests, and invokes `cancel_tts()`. The subclass should emit an interrupted audio end for an active request and must not call `finish_request()`. The base class performs the cleanup and emits `tts_flush_end`. No stale audio may follow flush completion.

## State, callbacks, and metrics

Connection state and request state are separate contracts. Report only these three values through the existing connection callbacks:

| State | Emit when |
|---|---|
| `connecting` | The connection attempt is about to be sent/started. |
| `connected` | The provider confirms the connection is ready for text. |
| `disconnected` | An established connection drops during normal operation or shutdown. |

`on_connecting()`, `on_connected()`, and `on_disconnected()` are the callback surface; the base status enum does not contain `reconnecting`, `processing`, `finalizing`, `interrupted`, `error`, or `closed`. Represent a retry as `disconnected` followed by `connecting`. Keep `reconnecting` as an internal flag/log if useful.

`AsyncTTS2BaseExtension` owns the request states `QUEUED`, `PROCESSING`, `FINALIZING`, and `COMPLETED`. It enters `PROCESSING` before calling `request_tts()` and enters `FINALIZING` when `text_input_end` is present, so those states are not transport status events and must not be emitted through connection callbacks. Record provider-send timestamps independently for TTFB. Request interruptions belong to the interrupted audio-end path, provider failures to the error path, and shutdown is normally reported as `disconnected` followed by internal cleanup. State callbacks must not expose credentials.

Provider callbacks must be normalized into one of: audio chunk, connection event, `ModuleError` with vendor name/code/message, or an internal completion/alignment event. Send TTFB only once per request ID, before its audio end; send error before error audio end when both are required.

## Provider-to-TEN mapping template

For every provider contract, write and implement a mapping table like this before coding:

| Provider signal | Required adapter action | TEN output/state |
|---|---|---|
| Connection attempt | Start/open transport | `connecting` |
| Connection ready/handshake success | Mark transport ready | `connected` |
| First text for request ID is sent | Record TTFB start immediately before send | Internal request state; no connection callback |
| Last text for request ID is sent | Mark input finalizing; base owns `FINALIZING` | Internal request state; no connection callback |
| First valid audio bytes | Start request output and compute TTFB | `tts_audio_start`, TTFB metric, `pcm_frame` |
| Audio bytes | Validate/alignment-buffer and emit | `pcm_frame` |
| Provider END for an incomplete logical request | Treat as intermediate; keep request open | No `tts_audio_end`; no `finish_request` |
| Provider completion with `text_input_end` and drained work | Flush dump, emit terminal end, complete base request | `tts_audio_end(reason=REQUEST_END)` then `finish_request()` |
| Terminal provider error | Normalize vendor code/message | `error`; if audio started, terminal error audio end then `finish_request`; otherwise `finish_request` directly |
| Recoverable provider error | Preserve the active request and retry according to policy | `error`; no terminal transition |
| Connection drop | Invalidate old callbacks and preserve only replayable input | `disconnected`, then `connecting` for retry |
| TEN flush | Base cancels, clears queued/buffered work; subclass cancels provider and interrupts active request | `tts_audio_end(reason=INTERRUPTED)` then `tts_flush_end`; no `finish_request` |
| Permanent shutdown | Stop tasks and close transport | `disconnected` through connection callback; internal closed state only |

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

Cover event ordering, empty/whitespace input, invalid/missing credentials, malformed and long text, exact duration, TTFB, enabled dump output, disabled dumping with no files, flush during synthesis, shutdown, and request isolation. Add reconnect tests whenever reconnect is implemented or promised. Add an appended-input scenario where multiple text chunks share one `request_id`, the provider emits an END after an intermediate chunk, and the extension still produces exactly one TEN audio lifecycle when the final input ends. Add a test where request A completes and buffered request B is then processed. Also test request A failing with an unrecoverable error before `text_input_end`; A must release the active request and buffered request B must complete. For HTTP, verify a minimal client that returns `{}` from `get_extra_metadata()` emits its first PCM frame and TTFB without raising `NotImplementedError`.

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

- The package contains the required files, including `__init__.py` with `from . import addon`, and a runnable `tests/bin/start`.
- Importing the generated package executes the addon registration; verify with a package-import test.
- The manifest declares the TTS interface and all runtime dependencies; the property file contains no secret.
- HTTP inherits `AsyncTTS2HttpExtension`; WebSocket and SDK implementations inherit `AsyncTTS2BaseExtension`.
- Every HTTP client implements `get_extra_metadata() -> dict` and returns `{}` when no extra metadata is available; the minimal client test reaches first PCM and TTFB.
- Streaming transports connect during startup and use only `connecting`, `connected`, and `disconnected` through connection callbacks; retries are `disconnected` -> `connecting`.
- Provider-send timing for TTFB is recorded immediately before the first actual send; connection time and queue time are excluded. Request-state transitions remain owned by the base class.
- An intermediate provider END does not produce a successful TEN end; normal completion requires `text_input_end` and drained provider work. A terminal error may finish directly from `PROCESSING`, while a recoverable error leaves the request active.
- When dumping is enabled, every request ID has an isolated PCM dump path, writer, byte count, and terminal cleanup; when `dump=false`, no dump file or writer is created.
- Config logs redact API keys, tokens, authorization headers, and nested secret fields.
- Top-level `url` and `headers` precedence over `params.url`, `params.base_url`, generated auth headers, and client defaults is tested.
- Flush cancels provider work, discards unsent text and unread/late audio, invalidates old callbacks, and prevents output after `tts_flush_end`.
- `tts_audio_end` reports monotonic start-to-end `request_event_interval_ms`, PCM duration, and reason for normal, interrupted, and error paths; use interval `0` when no audio started. Normal and terminal error streaming paths call `finish_request()`; flush relies on base cleanup.
- Same-request-ID appended input has one audio lifecycle, and a second request ID proceeds after the first completes.
- A request that fails terminally before final input releases its active slot, allowing a buffered second request ID to complete.
- Provider errors and callbacks preserve request correlation and vendor metadata without leaking secrets.
- Standalone tests, formatting, lint, and the real-key TTS guarder are all scheduled and their results will be reported.
