# ASR Plugin Design and Review Guide

> **Scope:** `ai_agents/agents/ten_packages/extension/*asr*`
>
> **Purpose:** This guide is the review baseline for new ASR integrations and
> changes to existing ASR lifecycle, connection, reconnection, finalize, result,
> metrics, or protocol behavior.
>
> **Last Reviewed:** 2026-09-16

## 1. Requirement Levels

This guide uses the following requirement levels:

| Level | Meaning |
| ----- | ------- |
| **MUST** | Blocks merge unless the framework contract is intentionally changed with a migration plan |
| **SHOULD** | Expected by default; deviations require a documented vendor limitation, alternative, and test evidence |
| **Conditional** | Required only when the plugin claims the capability, such as runtime config updates, word timestamps, or multilingual recognition |

Review must cover more than whether the plugin can produce text. A production
ASR plugin is a complete state machine:

```text
config -> connect -> send/buffer audio -> results -> finalize -> next turn
                         |                         |
                         +---- disconnect/reconnect+
```

Historical plugins may not satisfy every rule in this guide. They are useful
for understanding vendor differences, but they are not exemptions from new
`MUST` requirements. When modifying a legacy plugin, the changed state or
protocol path must no longer depend on known anti-patterns. Any legacy issue
that cannot be fixed in the same PR must be recorded explicitly in the review.

## 2. Sources of Truth

Read these files before reviewing an ASR change:

| File | Purpose |
| ---- | ------- |
| `ten_ai_base/interface/ten_ai_base/asr.py` | Base lifecycle, buffering, results, errors, metrics, and connection reporting |
| `ten_ai_base/interface/ten_ai_base/connection_status.py` | Valid connection-state transitions |
| `ten_ai_base/interface/ten_ai_base/timeline.py` | Vendor timeline to real user-audio timeline conversion |
| `ten_ai_base/api/asr-interface.json` | Input and output schemas |
| `integration_tests/asr_guarder/` | Framework-level acceptance behavior |

Choose a recent template with the same transport and session shape as the new
vendor. Do not copy a plugin only because its directory name looks similar.

| Scenario | Useful References |
| -------- | ----------------- |
| SDK callbacks arrive from non-asyncio threads | `azure_asr_python` |
| Long-lived WebSocket, connection reporting, and reconnect | `soniox_asr_python`, `smallest_asr_python` |
| Server closes after finalize and the next turn needs a new connection | `xai_asr_python` |
| `update_configs` races with audio sending | `bytedance_llm_based_asr` |
| Rich result metadata or two-pass results | `deepgram_asr_python`, `bytedance_llm_based_asr` |

## 3. Package Structure and Configuration

### 3.1 Package Structure

A new plugin **MUST** contain at least:

```text
<vendor>_asr_python/
├── __init__.py
├── addon.py
├── extension.py
├── config.py
├── manifest.json
├── property.json
├── requirements.txt
├── pyproject.toml
└── tests/
    ├── bin/start
    ├── configs/
    └── test_*.py
```

The following names **MUST** match exactly:

1. Extension directory name.
2. Name passed to `@register_addon_as_extension(...)`.
3. `name` in `manifest.json`.
4. `addon` in graph nodes.

`manifest.json` **MUST** import
`../../system/ten_ai_base/api/asr-interface.json`. Vendor-specific outputs may
be added, but they must not redefine or break standard `asr_result`, `error`,
`metrics`, `asr_finalize_end`, or `connection_status_changed` behavior.

### 3.2 Configuration Model

- **MUST** parse configuration with a Pydantic model and validate credentials,
  URL, language, sample rate, and enum values explicitly.
- **MUST** keep vendor pass-through options in `params` and framework-wide
  settings as first-class fields.
- **MUST** log the final effective configuration with the `config:` prefix
  after redaction.
- **MUST** report invalid configuration as one `FATAL_ERROR` and prevent later
  auto-connect attempts from using a fallback empty configuration.
- **MUST** inject credentials through `${env:VAR}` or
  `${env:VAR|default}`. Never commit plaintext credentials.
- **SHOULD** separate config normalization from vendor request construction so
  `update_params()` does not accidentally remove source `params`.

Keep an explicit initialization failure latch:

```python
self._init_failed = False

try:
    self.config = VendorASRConfig.model_validate_json(config_json)
    self.config.validate_config()
except Exception as exc:
    self._init_failed = True
    await self.send_asr_error(...)

async def start_connection(self) -> None:
    if self._init_failed:
        return
```

## 4. Base Lifecycle Contract

The plugin **MUST** inherit `AsyncASRBaseExtension` and implement:

```python
vendor()
start_connection()
stop_connection()
is_connected()
send_audio()
finalize()
input_audio_sample_rate()
```

### 4.1 Required `super()` Calls

| Lifecycle Method | Requirement | Base-Class Responsibility |
| ---------------- | ----------- | ------------------------- |
| `on_init` | **MUST** call | Stores `ten_env`, reads `auto_connect`, starts the audio consumer |
| `on_start` | **MUST** call when overridden | Reports features, starts metrics, performs auto-connect |
| `on_audio_frame` | **MUST** eventually call when overridden | Sends audio through the serialized base consumer |
| `on_data` | **MUST** call exactly once when overridden | Handles `asr_finalize` and `trigger_connect` |
| `on_stop` | **MUST** call when overridden | Sets the stop latch, disconnects, stops metrics |
| `on_deinit` | **MUST** call when overridden | Preserves the framework cleanup chain |

Do not register signal handlers in extension threads or use `atexit` as a
replacement for extension lifecycle cleanup.

### 4.2 Hidden `start_connection()` Behavior

The base class wraps subclass `start_connection()` methods through
`__init_subclass__` and emits `connecting` before the override runs.

- **MUST NOT** emit a duplicate `connecting` event manually.
- A semantically new connection attempt **MUST** call public
  `start_connection()`, not only a private helper such as
  `_start_websocket()`, or the connection state machine will miss the attempt.
- A return from `start_connection()` does not prove that the handshake
  succeeded. Call `await self.on_connected()` only after the vendor confirms
  the connection can accept audio.
- Connection creation or handshake failures **MUST** call
  `await self.on_disconnected(...)` so `connecting` is closed by a
  `disconnected` transition.

## 5. Connection State Machine

Valid transitions are:

```text
disconnected -> connecting -> connected
connected    -> disconnected
connected    -> connecting       # intentional connection replacement
disconnected -> connecting       # reconnect
```

### 5.1 Authoritative Connection State

- `is_connected()` **MUST** report whether the vendor connection can actually
  accept audio. A non-null client object is not sufficient.
- Base `connection_status` is for event reporting and observation; it is not
  proof that the transport is live.
- **MUST NOT** set connected immediately after `connect()` returns if a later
  vendor handshake callback establishes readiness.
- If the SDK performs internal transport recovery, the plugin **SHOULD** allow
  a bounded grace period before taking over reconnection. This prevents SDK
  recovery and extension recovery from running concurrently.

### 5.2 Callback Generations

An old connection can emit close or session-stopped callbacks after a new
connection is active. Plugins that recreate clients **MUST** use a generation,
epoch, or client identity check:

```python
self._connection_epoch += 1
epoch = self._connection_epoch

async def on_vendor_close(..., callback_epoch: int) -> None:
    if callback_epoch != self._connection_epoch:
        return
```

Without this guard, a late callback can close the new connection, report an
incorrect state, or start a second reconnect chain.

### 5.3 Expected and Unexpected Closure

The plugin **MUST** distinguish:

| Closure Cause | Required Behavior |
| ------------- | ----------------- |
| `on_stop` or deinit | Do not reconnect; release all resources |
| Vendor protocol closes on finalize | Complete finalize, then restore the next-turn path |
| `update_configs` replaces the connection | Suppress duplicate status and reconnect work from the old close callback |
| Network or service failure | Report non-fatal or fatal failure and apply the reconnect policy |

A vendor error callback and its later close callback must not each start an
independent reconnect chain.

## 6. Audio Sending and Buffering

### 6.1 Input Format

The default contract is signed PCM16 mono. The plugin **MUST** declare its real
input requirements through:

```python
input_audio_sample_rate()
input_audio_channels()       # defaults to 1
input_audio_sample_width()   # defaults to 2 bytes
```

If the vendor does not accept the graph input format, the plugin **MUST**
perform an explicit conversion. Changing only the declared values is invalid.

### 6.2 `send_audio()` Semantics

- Return `True` only after the frame has been successfully handed to the
  vendor send layer.
- Return `False` while disconnected, during a connection swap, or after a
  send failure.
- **MUST NOT** synchronously connect or recursively reconnect from
  `send_audio()`. Connection recovery belongs to a separate state machine.
- When using `lock_buf()`, **MUST** call `unlock_buf()` from `finally`.
- **MUST** prevent send, finalize, stop, and runtime config updates from
  operating on the same client concurrently.
- Audio dump, logging, and other slow I/O **SHOULD** remain outside the short
  client lock, while the client snapshot and live-state check remain inside it.

Recommended lock order:

```text
config/update lock -> connection swap lock -> send/finalize lock
```

Every path must use the same order. Error handling and reconnect code must not
hold the send lock while requesting the swap lock.

### 6.3 Buffering Strategy

The base behavior discards frames while disconnected. To preserve audio across
a disconnect, return:

```python
ASRBufferConfigModeKeep(byte_limit=...)
```

Review **MUST** verify:

1. The byte limit is bounded.
2. The overflow policy is acceptable and does not corrupt session boundaries.
3. `is_connected()` returns `False` during connection replacement so the base
   class buffers instead of sending to a client being destroyed.
4. Buffered frames are eventually flushed. If no new frame may arrive after
   connection recovery, flush explicitly from the open callback.
5. An explicit flush reads metadata from every frame so frames from an older
   session are not assigned to the current session.
6. An explicit flush updates `buffered_frames_size` and cannot send frames
   twice.

The base class normally flushes buffered frames when the next frame arrives
while connected. A successful connection with no later frame can therefore
leave data in the queue. Every new plugin must evaluate this boundary.

### 6.4 Audio Timeline

The plugin **MUST** maintain:

| Actual Behavior | Timeline Update |
| --------------- | --------------- |
| User audio successfully handed to the vendor | `add_user_audio(duration_ms)` |
| Silence injected for finalize or endpointing | `add_silence_audio(duration_ms)` |
| Vendor stream timestamps reset | Accumulate the old real duration, then call `reset()` |

Calculate duration from the actual format:

```python
duration_ms = (
    len(audio_bytes)
    / sample_rate
    / channels
    / sample_width
    * 1000
)
```

Vendor stream-relative `start_ms` values **SHOULD** be mapped through
`audio_timeline.get_audio_duration_before_time()`. Injected silence must not
advance the user timeline, and dropped audio or reconnect offsets must not make
timestamps move backward.

## 7. ASR Result Contract

### 7.1 Required Fields

Every `ASRResult` **MUST** contain:

```json
{
  "id": "managed-by-the-base-class",
  "text": "hello",
  "final": false,
  "start_ms": 0,
  "duration_ms": 120,
  "language": "en-US",
  "words": [],
  "metadata": {
    "session_id": "session-123",
    "asr_info": {
      "vendor": "vendor-name"
    }
  }
}
```

Rules:

- `session_id` **MUST** be at `metadata.session_id`, never at the top level.
- Vendor-specific fields **MUST** be under `metadata.asr_info`.
- `language` **MUST** use the normalized format promised by the plugin.
- `start_ms` and `duration_ms` **MUST** be non-negative milliseconds.
- Preserve vendor request or transcript IDs under `asr_info` if needed.
  `send_asr_result()` overwrites `ASRResult.id`.

### 7.2 Result IDs and Turns

The base class uses one UUID for interim and final results in the current turn,
then creates a new UUID after the final result.

- **MUST NOT** rely on an input `ASRResult.id` to preserve a vendor identifier.
- Partial, locked-interim, and final results in one turn **SHOULD** retain the
  same base-generated ID.
- **MUST NOT** emit duplicate final results for the same semantic result unless
  the protocol explicitly represents independent segments.

### 7.3 `final`, `locked`, and Word Stability

| State | `final` | `metadata.asr_info.locked` |
| ----- | ------- | ------------------------- |
| Revisable partial | `false` | `false` or omitted |
| Stable text before utterance end | `false` | `true` |
| Utterance ended | `true` | `false` or omitted |

When word-level results are available, `ASRWord.stable` **SHOULD** match the
segment stability.

### 7.4 Empty Text

- Empty interim results **SHOULD** usually be dropped.
- An empty final result is not a valid user turn.
- If the vendor uses an empty final event as a finalize acknowledgement, the
  plugin may consume it to send `asr_finalize_end`, but **SHOULD NOT** emit an
  empty `asr_result` downstream.
- For input containing speech, the same-session guarder requires a non-empty
  final result for every cycle.

### 7.5 Metadata Merge Trap

`send_asr_result()` shallow-merges the latest input metadata saved by the base
class into plugin-provided metadata.

- **MUST** deep-copy metadata before using `pop()` or otherwise modifying it.
  Never mutate `self.metadata`.
- **MUST** check whether `session_id` or `asr_info` is overwritten.
- **MUST** test the final emitted Data JSON, not only the pre-send
  `ASRResult` object.
- When input metadata contains custom fields, review must decide whether they
  remain at the metadata root or move under `asr_info`, consistent with the
  downstream contract.

## 8. Finalize Contract

`asr_finalize` is a request-response handshake, not merely a request to send
silence:

```text
asr_finalize(finalize_id, metadata)
    -> vendor drain / flush / close / silence
    -> final result, when present
    -> asr_finalize_end(same finalize_id, same session_id)
```

### 8.1 Required Behavior

- Every finalize request **MUST** eventually produce exactly one
  `asr_finalize_end`.
- `finalize_id` **MUST** be echoed without modification.
- `metadata.session_id` **MUST** match the corresponding finalize and session.
- Disconnected state, silent input, missing vendor final, timeout, or finalize
  send failure **MUST** still have a bounded completion path. Callers cannot
  wait forever.
- A final result caused by finalize **SHOULD** be emitted before
  `asr_finalize_end`.
- Concurrent finalize requests **MUST** be serialized or keep independent
  contexts. The base class has one mutable `finalize_id`, so concurrent
  requests otherwise overwrite each other.

### 8.2 Metadata Trap

The base class reads `finalize_id` from `asr_finalize`, but
`send_asr_finalize_end()` uses `self.metadata`, which normally comes from the
latest audio frame. If finalize metadata can differ from the latest frame,
the plugin **MUST** parse and save finalize metadata before calling
`super().on_data()`, or maintain a separate finalize context.

### 8.3 Common Finalize Modes

| Mode | Review Focus |
| ---- | ------------ |
| Vendor finalize API | Wait for final or acknowledgement, enforce a timeout, close the handshake on errors |
| Injected silence | Calculate bytes from the real audio format and call `add_silence_audio()` |
| Close connection | Mark the close as expected so unexpected-reconnect logic does not race it |
| Ignore finalize | Allow only when vendor endpointing reliably auto-finalizes; still handle finalize end |
| Single-utterance protocol | Reconnect cleanly after final so the same session can process the next turn |

If the vendor auto-finalizes before `asr_finalize` arrives, the plugin must
still handle the later finalize request. Old finalize state must not leak into
the next turn's TTLW, finalize ID, or reconnect behavior.

## 9. Reconnection and Concurrency

### 9.1 One Reconnect Owner

The plugin **MUST** have one reconnect entry point:

```text
vendor close/error -> classify -> reconnect manager -> replace connection
```

The following patterns cause reconnect storms and are prohibited:

- Connecting directly from `send_audio()` when disconnected.
- Enabling SDK auto-reconnect while the extension also recursively reconnects.
- Letting error, close, and session-stopped callbacks each reconnect.
- Recursively calling `_handle_reconnect()` without a task, lock, or stop
  condition.

### 9.2 Reconnect Policy

- Transient network failures **MUST** use `NON_FATAL_ERROR` and a backoff
  policy.
- `websockets.exceptions.ConnectionClosedOK` **MUST NOT** emit an ASR
  `error`, including normal code-1000 and code-1001 handshakes. Still report
  the disconnected connection state and apply the session reconnect policy;
  a normal transport close does not necessarily mean an intentional stop.
- `ConnectionClosedError` **MUST** remain a failure even when its received
  close code is `1000`: an incomplete close handshake is not a normal close.
  Classify by exception type, not by close code alone. This explicitly
  exempts `ConnectionClosedOK` from the transient-failure error requirement.
- Authentication, authorization, and invalid configuration **MUST** use
  `FATAL_ERROR` and must not retry indefinitely.
- A bounded retry strategy **MUST** escalate to fatal when its ceiling is
  reached.
- A successful handshake **MUST** reset the retry counter.
- `on_stop`, a fatal latch, or an expected close **MUST NOT** create a new
  reconnect task.
- Every background reconnect task **MUST** be cancelled and awaited, or
  otherwise safely completed, during stop/deinit.

### 9.3 Connection Replacement

Both runtime config updates and reconnect can execute stop followed by start.
The replacement **MUST** be atomic:

1. Acquire the swap lock.
2. Mark connection swapping so `is_connected()` returns `False`.
3. Wait for active send/finalize work to complete.
4. Close the old client.
5. Create the new client.
6. Let the new client's handshake callback call `on_connected()`.
7. Clear the swapping marker.

Do not hold the send lock across a slow network connection attempt. Doing so
can deadlock audio consumption, stop, and error handling.

### 9.4 SDK Thread Callbacks

If the vendor SDK invokes callbacks from another thread, the plugin **MUST**
transfer work to the asyncio event loop:

```python
loop.call_soon_threadsafe(
    asyncio.create_task,
    self._handle_vendor_event(event),
)
```

Do not await, manipulate asyncio locks or queues, or call TEN async APIs
directly from the SDK thread.

## 10. Error Model

Use only these framework-level severities:

| Scenario | `ModuleErrorCode` |
| -------- | ----------------- |
| Invalid or missing config, 401/403, unrecoverable protocol error | `FATAL_ERROR` (`-1000`) |
| Abnormal network disconnect, timeout, temporary server failure | `NON_FATAL_ERROR` (`1000`) |
| Completed normal WebSocket close (`ConnectionClosedOK`) | No ASR error; report disconnected state |
| Retry ceiling reached | `FATAL_ERROR` (`-1000`) |

Vendor-originated errors **MUST** include:

```json
{
  "vendor_info": {
    "vendor": "vendor-name",
    "code": "vendor-native-code-as-a-string",
    "message": "vendor-native-message"
  }
}
```

Review requirements:

- Framework `code` is severity, not the HTTP or vendor-native code.
- `vendor_info.code` **MUST** be converted to a string.
- An error event does not prove the connection is closed. Call
  `on_disconnected()` only when the transport is actually unusable.
- The same root cause **SHOULD NOT** emit duplicate fatal errors from config,
  connect, and close paths.
- Expected exceptions during stop **SHOULD** be suppressed and must not trigger
  reconnect.

## 11. Metrics and Vendor Metadata

### 11.1 Base-Managed Metrics

The base class manages:

| Metric | Trigger |
| ------ | ------- |
| `ttfw` | First result after the first successful audio send |
| `ttlw` | Final result after a finalize request |
| `actual_send` / `actual_send_delta` | Periodic reads from `AudioTimeline` |

The plugin is responsible for:

- Calling `send_connect_delay_metrics()` after a successful handshake.
- Calling `send_vendor_metrics()` for vendor-specific measurements.
- Not manually duplicating base-managed TTFW or TTLW.

`connect_delay` can be emitted before the first audio frame and is the only
normal ASR metric allowed to omit `session_id`. Other turn-related metrics
**MUST** carry the correct session metadata.

### 11.2 `vendor_metadata()`

`connection_status_changed.metadata.vendor_metadata` is built from
`vendor_metadata()`. The base class recursively redacts recognized sensitive
keys.

- **SHOULD** include useful model, region, mode, and endpoint information.
- Credential fields may be returned for base redaction, but their names must
  be recognized by the redactor.
- A signed URL cannot rely only on JSON-key redaction. If secrets are in query
  parameters, **MUST** redact the URL first or remove the secret parameters.
- `vendor_metadata()` **MUST** return `{}` before configuration is available.
- **MUST** test that sensitive values are masked in connection-status events.

## 12. Dumping, Logging, and Cleanup

### 12.1 Audio Dump

- `dump=true` **MUST** produce a readable PCM file.
- The ASR guarder verifies that at least one dump matches the original input
  audio bytes.
- Injected finalize silence, vendor responses, and protocol packets
  **SHOULD NOT** be appended to the raw-input PCM file. Use a separate file or
  rotate the dump at finalize if those artifacts are required.
- Dumper start and stop **MUST** be idempotent. Connection replacement must not
  leak file handles or start duplicate dump workers.

### 12.2 Logging

Use these conventions:

- `LOG_CATEGORY_KEY_POINT` for configuration, lifecycle, finalize, and key
  metrics.
- `LOG_CATEGORY_VENDOR` for vendor connection, response, and error details.
- `config:` for the redacted configuration log prefix.
- `vendor_status_changed:` for vendor connection state.
- `vendor_error:` for vendor errors.
- `vendor_result:` for vendor result diagnostics.

**MUST NOT** log plaintext keys, tokens, signed URLs, Authorization headers,
private keys, or complete sensitive responses.

### 12.3 Stop and Deinit

Recommended cleanup order:

1. Set stop and fatal latches so no new reconnect can start.
2. Cancel delayed reconnect, keepalive, listener, and recovery tasks.
3. Stop input and close the input stream.
4. Close the client, WebSocket, or SDK recognizer.
5. Await background task completion.
6. Stop dumpers and close files.
7. Clear client and task references.

`stop_connection()` **MUST** be idempotent and must tolerate partial
initialization without raising a secondary failure.

## 13. Test Requirements

### 13.1 Minimum Standalone Tests for a New Plugin

| Test | Required Coverage |
| ---- | ----------------- |
| `test_asr_result` | Required fields, session, language, final/partial, emitted JSON |
| `test_finalize` | Success, no result, disconnected, timeout, finalize ID and session echo |
| `test_connection_status` | connecting -> connected -> disconnected, payload, redaction |
| `test_reconnect` | Transient retry, no retry after fatal, counter reset after success |
| `test_reconnect_lifecycle` | Expected close, no reconnect during stop, stale callback ignored |
| `test_invalid_params` | One fatal error and no later connection attempt |
| `test_vendor_error` | Correct separation of framework severity and `vendor_info` |
| `test_dump` | Complete raw PCM without injected-silence contamination |
| `test_metrics` | Connect delay, TTFW/TTLW, session metadata |
| `test_vendor_metadata` | Model/region/URL reporting and credential redaction |
| `test_audio_timeline` | User audio, silence, and timestamp continuity across connections |

Add these tests when the capability is supported:

| Capability | Additional Test |
| ---------- | --------------- |
| `update_configs` | Update racing with send, finalize, and reconnect |
| Single-utterance protocol | Two audio/finalize cycles in the same session |
| Multi-threaded SDK callbacks | Event-loop transfer and harmless late callbacks after stop |
| Words | Word timestamp, duration, and stability |
| Locked interim | `final=false` with `asr_info.locked=true` |
| Multilingual | Normalized output for every advertised language |

### 13.2 Guarder

Before submission, run sequentially:

```bash
task test-extension \
  EXTENSION=agents/ten_packages/extension/<vendor>_asr_python

task asr-guarder-test \
  EXTENSION=<vendor>_asr_python \
  CONFIG_DIR=tests/configs
```

Do not run ASR and TTS guarders in parallel in the same container.

Provide at least:

```text
tests/configs/property_en.json
tests/configs/property_zh.json
tests/configs/property_invalid.json
tests/configs/property_dump.json
```

Key guarder acceptance areas:

1. Standard result fields and `metadata.session_id`.
2. Final result and `asr_finalize_end`.
3. Two recognition cycles in the same session.
4. Connection-status payload and valid transitions.
5. Invalid-credential error structure.
6. Continuous audio input during reconnect without a crash.
7. TTFW/TTLW and connect delay.
8. Timestamp accuracy.
9. Dump byte equality.
10. Multilingual and long-lived connection stability. Long-duration streaming
   may not be in the default test set and must be run explicitly when the
   change risk requires it.

## 14. Merge-Blocking Findings

Any of the following should block review:

- The plugin does not inherit `AsyncASRBaseExtension` or bypasses the standard
  interface.
- It marks connected before handshake or omits `on_connected()` or
  `on_disconnected()`.
- `send_audio()` reconnects directly.
- Finalize has no `asr_finalize_end` fallback for disconnect, silence, timeout,
  or error.
- An expected close is treated as an unexpected failure and starts duplicate
  reconnect work.
- A background task can reconnect or emit results after stop.
- A stale callback from an old client can modify new-client state.
- Audio is sent to an old client during connection replacement.
- Audio buffering is unbounded or crosses session ownership incorrectly.
- A `lock_buf()` error path does not unlock the frame.
- Vendor-relative timestamps are used without accounting for injected silence
  or reconnect offsets.
- `session_id` is top-level or vendor fields are outside
  `metadata.asr_info`.
- An empty final is treated as a valid user turn.
- A vendor-native code is used as the framework error severity.
- A vendor error omits `vendor_info`.
- Logs, vendor metadata, or URLs expose credentials.
- The raw input dump contains finalize silence and no longer matches input.
- Only the happy path is tested; finalize, reconnect, and stop races are
  missing.

## 15. PR Review Checklist

Copy this section into the PR:

```markdown
### ASR design review

- [ ] Package/addon/manifest/graph names match; manifest imports asr-interface.json
- [ ] Config is validated once and logged with `config:` after redaction
- [ ] Invalid config emits one fatal error and prevents connection attempts
- [ ] `start_connection()` reports connected only after vendor handshake
- [ ] All connect failures/closures close the base connection state
- [ ] Expected close, unexpected close, stop, and config swap are distinguished
- [ ] Reconnect has one owner, bounded backoff policy, stop/fatal cancellation
- [ ] Stale callbacks from old clients are ignored
- [ ] send/finalize/stop/config swap cannot race the same client
- [ ] Audio buffer policy is explicit, bounded, session-safe, and flushes after recovery
- [ ] AudioFrame buffers are always unlocked and send_audio return value is accurate
- [ ] AudioTimeline includes sent user audio and injected silence exactly once
- [ ] ASR result shape, language, timestamps, words, final/locked semantics are correct
- [ ] session_id is under metadata; vendor fields are under metadata.asr_info
- [ ] Finalize always echoes finalize_id/session_id exactly once, including failures/timeouts
- [ ] Same session works for at least two audio -> finalize cycles
- [ ] Framework error severity and vendor_info are separated correctly
- [ ] Connect delay, TTFW/TTLW, and vendor metrics have correct metadata
- [ ] vendor_metadata and all logs redact secrets and signed URLs
- [ ] Dump contains original PCM without protocol silence contamination
- [ ] Stop/deinit cancels and awaits background tasks; cleanup is idempotent
- [ ] Standalone tests pass
- [ ] ASR guarder passes
- [ ] `task format`, `task check`, and `task lint` pass
```
