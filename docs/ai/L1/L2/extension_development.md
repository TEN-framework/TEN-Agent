# Extension Development

> **When to Read This:** Load this document when you are creating a new TTS, ASR, or LLM
> extension. It covers the exact files to create, base classes to inherit, abstract methods
> to implement, test configs to provide, and guarder tests your extension must pass.

## Quick Start: Copy an Existing Extension

The fastest way to create a new extension is to copy a similar one:

| Extension Type | Good Template to Copy           | Base Class                  |
| -------------- | ------------------------------- | --------------------------- |
| TTS (HTTP)     | `rime_http_tts`                 | `AsyncTTS2HttpExtension`    |
| TTS (WebSocket)| `deepgram_tts`                  | `AsyncTTS2BaseExtension`    |
| ASR (WebSocket)| `deepgram_asr_python`           | `AsyncASRBaseExtension`     |
| LLM            | `openai_llm2_python`            | `AsyncLLMBaseExtension`     |
| LLM Tool       | `bingsearch_tool_python`        | `AsyncLLMToolBaseExtension` |

```bash
cp -r agents/ten_packages/extension/deepgram_tts agents/ten_packages/extension/my_vendor_tts
# Then rename: addon decorator, class names, manifest.json name field
```

## Directory Structure

```
my_vendor_tts_python/
├── __init__.py              # Can be empty
├── addon.py                 # Registration (MUST match manifest.json name)
├── extension.py             # Main logic OR orchestration
├── my_vendor_tts.py         # Vendor client (websocket/http logic)
├── config.py                # Pydantic config model
├── manifest.json            # Metadata + API interface + property schema
├── property.json            # Defaults with ${env:VAR} syntax
├── requirements.txt         # Python deps
├── README.md                # Usage docs
└── tests/
    ├── bin/
    │   └── start            # Test entry script (sets PYTHONPATH, runs pytest)
    └── configs/
        ├── property_basic_audio_setting1.json # Sample rate test 1 (e.g. 16000)
        ├── property_basic_audio_setting2.json # Sample rate test 2 (e.g. 24000)
        ├── property_dump.json                # Audio dump test config
        ├── property_miss_required.json       # Missing API key test
        └── property_invalid.json             # Invalid API key test
```

Some extensions also include `property.json` as a default valid config.

## Step 1: addon.py

```python
from ten_runtime import Addon, register_addon_as_extension, TenEnv

@register_addon_as_extension("my_vendor_tts_python")
class MyVendorTTSAddon(Addon):
    def on_create_instance(self, ten: TenEnv, name: str, context) -> None:
        from .extension import MyVendorTTSExtension
        ten.on_create_instance_done(MyVendorTTSExtension(name), context)
```

The decorator name **must exactly match** `manifest.json` `name` field AND the `addon`
field in graph nodes.

## Step 2: config.py

```python
from pydantic import BaseModel, Field
from typing import Any
import copy
from ten_ai_base import utils

class MyVendorTTSConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.vendor.com"
    model: str = "default-model"
    sample_rate: int = 24000
    dump: bool = False
    dump_path: str = ""
    params: dict[str, Any] = Field(default_factory=dict)

    def update_params(self) -> None:
        params = self.params if isinstance(self.params, dict) else {}
        self.params = params
        for attr in ("api_key", "base_url", "model", "sample_rate"):
            if attr in params:
                setattr(self, attr, params.pop(attr))

    def validate(self) -> None:
        key = self.api_key or self.params.get("api_key", "")
        if not key:
            raise ValueError("API key is required")

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"
        config = copy.deepcopy(self)
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])
        return f"{config}"
```

## Step 3: manifest.json

```json
{
  "type": "extension",
  "name": "my_vendor_tts_python",
  "version": "0.1.0",
  "dependencies": [
    {"type": "system", "name": "ten_runtime_python", "version": "0.11"}
  ],
  "api": {
    "interface": [
      {"import_uri": "../../system/ten_ai_base/api/tts-interface.json"}
    ],
    "property": {
      "properties": {
        "dump": {"type": "bool"},
        "dump_path": {"type": "string"},
        "params": {
          "type": "object",
          "properties": {
            "api_key": {"type": "string"},
            "base_url": {"type": "string"},
            "model": {"type": "string"},
            "sample_rate": {"type": "int32"}
          }
        }
      }
    }
  }
}
```

Use `tts-interface.json` for TTS, `asr-interface.json` for ASR, `llm-interface.json` for LLM.

## Step 4: property.json

```json
{
  "params": {
    "api_key": "${env:MY_VENDOR_API_KEY}",
    "model": "default-model",
    "sample_rate": 24000
  }
}
```

## Step 5: extension.py — Implementing the Base Class

### TTS Extension (WebSocket Mode)

```python
from ten_ai_base.tts2 import AsyncTTS2BaseExtension

class MyVendorTTSExtension(AsyncTTS2BaseExtension):
    def vendor(self) -> str:
        return "my_vendor"

    async def on_init(self, ten_env) -> None:
        await super().on_init(ten_env)
        config_json, _ = await ten_env.get_property_to_json("")
        self.config = MyVendorTTSConfig(**json.loads(config_json))
        self.config.update_params()
        self.config.validate()

    async def on_start(self, ten_env) -> None:
        await super().on_start(ten_env)
        self.client = MyVendorTTSClient(self.config, ten_env)
        await self.client.start()

    async def on_stop(self, ten_env) -> None:
        await super().on_stop(ten_env)
        await self.client.stop()

    async def request_tts(self, t: TTSTextInput) -> None:
        async for data_msg, event_status in self.client.get(t.text):
            if event_status == EVENT_TTS_RESPONSE and data_msg:
                await self.send_tts_audio_data(data_msg)
            elif event_status == EVENT_TTS_END:
                if t.text_input_end:
                    await self._finalize_request(TTSAudioEndReason.REQUEST_END)
                break
            elif event_status == EVENT_TTS_ERROR:
                await self._finalize_request(TTSAudioEndReason.ERROR)
                break

    async def cancel_tts(self) -> None:
        await self.client.cancel()

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate

    def synthesize_audio_channels(self) -> int:
        return 1  # mono

    def synthesize_audio_sample_width(self) -> int:
        return 2  # 16-bit
```

**TTS2 state machine**: The base class manages request states automatically:
QUEUED -> PROCESSING -> FINALIZING -> COMPLETED. In real WebSocket extensions,
`request_tts()` usually consumes typed client events such as response/audio,
TTFB-metric, end, and error, then funnels completion through a single finalize path.
Avoid raw byte-generator designs that bypass request finalization and `finish_request()`.

**Typical output events** in this flow:
- `tts_audio_start` — emit once when audio begins
- `pcm_frame` — emit for each audio chunk via `send_tts_audio_data()`
- `tts_audio_end` — emit when the request completes through your finalize path
- `tts_error` — emit on failure through the same finalize/error path

### TTS Extension (HTTP Mode)

Simpler — for non-streaming HTTP APIs. In practice, subclasses usually implement
`create_config()` and `create_client()` and let `AsyncTTS2HttpExtension` handle
the request lifecycle:

```python
from ten_ai_base.tts2_http import (
    AsyncTTS2HttpExtension,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpClient,
)
from ten_runtime import AsyncTenEnv

class MyVendorTTSExtension(AsyncTTS2HttpExtension):
    async def create_config(
        self, config_json_str: str
    ) -> AsyncTTS2HttpConfig:
        return MyVendorTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        return MyVendorTTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        return "my_vendor"

    def synthesize_audio_sample_rate(self) -> int:
        return self.config.sample_rate
```

The extension class is thin — the real work lives in the **client**
(`AsyncTTS2HttpClient`). The base class drives the request lifecycle (queuing,
interleaving, `tts_audio_start`/`end`, flush) and calls your client's `get()`
once per request. You implement `get()` as an async generator that yields
`(audio_bytes | None, event_type)` tuples, where `event_type` is a
`TTS2HttpResponseEventType`:

| Event type          | Yield with                | Meaning                                       |
| ------------------- | ------------------------- | --------------------------------------------- |
| `RESPONSE`          | `(pcm16_bytes, RESPONSE)` | One audio chunk — must be PCM16 mono          |
| `END`               | `(None, END)`             | Request completed successfully                |
| `FLUSH`             | `(None, FLUSH)`           | Cancelled mid-stream (check your cancel flag) |
| `ERROR`             | `(msg_bytes, ERROR)`      | Non-fatal vendor/network error                |
| `INVALID_KEY_ERROR` | `(msg_bytes, INVALID_KEY_ERROR)` | Fatal auth/permission error (401/403)  |

```python
from ten_ai_base.tts2_http import AsyncTTS2HttpClient
from ten_ai_base.struct import TTS2HttpResponseEventType

class MyVendorTTSClient(AsyncTTS2HttpClient):
    async def get(self, text, request_id):
        if not text.strip():
            yield None, TTS2HttpResponseEventType.END   # empty text completes fast
            return
        self._is_cancelled = False
        async with self.client.stream("POST", self.url, json=payload) as resp:
            if resp.status_code != 200:
                err = (await resp.aread()).decode("utf-8", "replace")
                ev = (TTS2HttpResponseEventType.INVALID_KEY_ERROR
                      if resp.status_code in (401, 403)
                      else TTS2HttpResponseEventType.ERROR)
                yield err.encode(), ev
                return
            async for chunk in resp.aiter_bytes():
                if self._is_cancelled:
                    yield None, TTS2HttpResponseEventType.FLUSH
                    return
                yield chunk, TTS2HttpResponseEventType.RESPONSE  # PCM16 mono
            yield None, TTS2HttpResponseEventType.END

    async def cancel(self):            # set the flag get() polls between chunks
        self._is_cancelled = True

    async def clean(self):             # close the httpx client on teardown
        await self.client.aclose()

    def get_extra_metadata(self) -> dict:   # surfaced on TTFB metrics
        return {"model": self.config.params.get("model", "")}
```

**Auth and error classification**: extract `api_key` from `params` into an
`Authorization` header in the constructor; classify 401/403 (and vendor
`invalid_api_key` codes) as `INVALID_KEY_ERROR`, everything else as `ERROR`.
For a complete reference implementation see `mistral_tts_python` (streaming
httpx, error classification, audio conversion) or `rime_http_tts`.

### ASR Extension

```python
from ten_ai_base.asr import AsyncASRBaseExtension

class MyVendorASRExtension(AsyncASRBaseExtension):
    def vendor(self) -> str:
        return "my_vendor"

    async def start_connection(self) -> None:
        self.ws = await websockets.connect(self.url, headers=self.auth_headers)
        # Start a listener task for results
        asyncio.create_task(self._listen_for_results())

    async def stop_connection(self) -> None:
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send_audio(self, frame, session_id: str | None) -> bool:
        buf = frame.lock_buf()
        data = bytes(buf)
        frame.unlock_buf(buf)
        await self.ws.send(data)
        return True

    async def finalize(self, session_id: str | None) -> None:
        await self.ws.send(json.dumps({"type": "CloseStream"}))
        # Wait for final results before returning

    def is_connected(self) -> bool:
        return self.ws is not None and self.ws.open

    def input_audio_sample_rate(self) -> int:
        return 16000

    async def _listen_for_results(self):
        async for msg in self.ws:
            result = json.loads(msg)
            if result.get("is_final"):
                asr_result = ASRResult(text=result["transcript"], language="en-US", ...)
                await self.send_asr_result(asr_result)
```

**ASR output methods** you must call:
- `await self.send_asr_result(asr_result)` — for each transcription
- `await self.send_asr_error(error, vendor_info)` — on vendor errors
- `await self.send_asr_finalize_end()` — when finalize completes

**Buffer strategy**: Override `buffer_strategy()` to return `ASRBufferConfigModeKeep`
if you want audio buffered during disconnects (default discards).

#### Canonical `asr_result` payload

`session_id` lives inside `metadata`, never as a top-level field. Locked-interim
vs final is signalled at `metadata.asr_info.locked` (true = stable interim that
should not be reverted by a later partial; final = true = utterance ended).

```json
{
  "id": "uuid",
  "text": "hello world",
  "final": true,
  "start_ms": 120,
  "duration_ms": 340,
  "language": "en-US",
  "metadata": {
    "session_id": "session-123",
    "asr_info": {
      "vendor": "xai",
      "locked": false
    }
  }
}
```

#### Canonical error payload with `vendor_info`

```json
{
  "module": "tts",
  "code": -1000,
  "message": "Unauthorized",
  "vendor_info": {
    "vendor": "xai",
    "code": "401",
    "message": "Unauthorized"
  }
}
```

`code` is the framework-level severity (-1000 fatal, 1000 non-fatal). `vendor_info.code`
is the vendor-native status (HTTP code, vendor error code, etc.).

### LLM Extension

```python
from ten_ai_base.llm import AsyncLLMBaseExtension

class MyLLMExtension(AsyncLLMBaseExtension):
    async def on_call_chat_completion(self, ten_env, **kwargs):
        # Handle command-based chat requests
        pass

    async def on_data_chat_completion(self, ten_env, **kwargs):
        # Handle stream-based data input
        pass

    async def on_tools_update(self, ten_env, tool_metadata):
        async with self._available_tools_lock:
            self.available_tools = tool_metadata
```

---

## TTS Audio Pipeline: Data Types and Flow

Understanding the data types is critical for implementing TTS extensions correctly.

### Data Flow Through the Pipeline

```
User speaks → Agora RTC → pcm_frame → ASR → asr_result → main_control
  → text_data → LLM → text_data → main_control → tts_text_input → TTS
  → pcm_frame → Agora RTC → User hears
```

### tts_text_input (incoming to your extension)

```python
class TTSTextInput:
    request_id: str           # Unique request identifier
    text: str                 # Text chunk to synthesize
    text_input_end: bool      # True = last chunk for this request_id
    metadata: dict            # Context: {session_id, turn_id, ...}
```

- Multiple `tts_text_input` messages can share one `request_id` (the "append" pattern)
- `text_input_end=True` signals no more text is coming for this request
- The base class handles queuing and buffering — your `request_tts()` receives complete inputs

### tts_audio_start / tts_audio_end (outgoing from your extension)

These are sent automatically by the base class. You don't need to send them manually.

```json
// tts_audio_start
{"request_id": "req1", "metadata": {"session_id": "sess1", "turn_id": 1}}

// tts_audio_end
{
  "request_id": "req1",
  "request_event_interval_ms": 1500,
  "request_total_audio_duration_ms": 3200,
  "reason": 1,
  "metadata": {"session_id": "sess1", "turn_id": 1}
}
```

**Field semantics**:
- `request_event_interval_ms`: wall-clock between the first audio chunk arrival
  and the last audio chunk arrival for this `request_id` — the audio receive
  window. **Not** TTFB; TTFB is reported separately via the `metrics` channel.
- `request_total_audio_duration_ms`: total audio duration computed from the
  received byte count and the configured PCM format.

**Reason values**: `REQUEST_END` (1) = normal completion, `INTERRUPTED` (2) = flush/cancel,
`ERROR` (3) = failure.

### tts_flush / tts_flush_end

Flush is triggered when the user interrupts (speaks while TTS is playing).

```json
// tts_flush (incoming signal)
{"flush_id": "flush_abc123", "metadata": {"session_id": "sess1"}}

// tts_flush_end (your extension's response — sent automatically by base class)
{"flush_id": "flush_abc123", "metadata": {"session_id": "sess1"}}
```

**Critical**: `flush_id` and `metadata` must be echoed back exactly.

## Flush Handling in TTS Extensions

The base class (`AsyncTTS2BaseExtension`) handles most flush logic automatically.
Your extension only needs to implement `cancel_tts()`:

```python
async def cancel_tts(self) -> None:
    """Called when a flush signal arrives. Stop any in-progress synthesis."""
    if self.client:
        await self.client.cancel()
```

### What the Base Class Does on Flush

1. Acquires `_put_lock` to block new `tts_text_input` arrivals
2. Clears `_flush_complete_event` to prevent race conditions
3. Flushes the internal queue (discards all pending items)
4. Calls `cancel_tts()` on your extension (you stop the vendor API)
5. Sends `tts_audio_end` with `reason=INTERRUPTED` for the current request
6. Sends `tts_flush_end` with the echoed `flush_id` and `metadata`
7. Resets all request state (ready for next request)
8. Sets `_flush_complete_event` to re-enable queue processing

### Request Interleaving (How Buffering Works)

When multiple requests arrive with different `request_id`s:

1. First request is processed immediately (`_processing_request_id = "req1"`)
2. Messages for other request_ids are **buffered** in `_pending_messages`
3. When req1 completes, the next buffered request is released (FIFO order)
4. Each request maintains strict event ordering: `audio_start → frames → audio_end`

Your `request_tts()` doesn't need to handle interleaving — the base class does it.

## The Three property.json Files

There are three distinct `property.json` files with different roles:

### 1. Extension Defaults (`agents/ten_packages/extension/<name>/property.json`)

Default config for the extension. Loaded when no overrides are specified:

```json
{
  "params": {
    "api_key": "${env:MY_VENDOR_API_KEY}",
    "model": "default-model",
    "sample_rate": 24000
  }
}
```

### 2. App Graph Definition (`agents/examples/<name>/tenapp/property.json`)

Defines the complete agent — nodes, connections, per-instance overrides:

```json
{
  "ten": {
    "predefined_graphs": [{
      "name": "voice_assistant",
      "graph": {
        "nodes": [
          {"name": "tts", "addon": "my_vendor_tts_python",
           "property": {"params": {"model": "high-quality", "sample_rate": 24000}}}
        ],
        "connections": [...]
      }
    }]
  }
}
```

Properties here **override** extension defaults for this specific graph instance.

### 3. Test Configs (`agents/ten_packages/extension/<name>/tests/configs/*.json`)

Used by guarder tests. Each test loads a specific config file:

```json
{
  "dump": true,
  "dump_path": "./tests/dump_output/",
  "params": {"key": "${env:MY_VENDOR_API_KEY}", "sample_rate": 16000}
}
```

**Loading order**: Extension defaults → App graph overrides → Test config overrides.

---

## Step 6: Test Configuration Files

Your extension's `tests/configs/` directory needs these config files for the guarder tests to work:

### For TTS Extensions

| Config File                          | Purpose                                | Content                                |
| ------------------------------------ | -------------------------------------- | -------------------------------------- |
| `property_basic_audio_setting1.json` | Sample rate test 1                     | `sample_rate: 16000` + valid key       |
| `property_basic_audio_setting2.json` | Sample rate test 2                     | `sample_rate: 24000` + valid key       |
| `property_dump.json`                 | Audio dump test                        | `dump: true, dump_path: "./tests/dump_output/"` |
| `property_miss_required.json`        | Missing params error test              | Empty API key                          |
| `property_invalid.json`              | Invalid params error test              | Empty or invalid API key               |
| `property.json`                      | Optional default test config           | Valid API key, default model/settings  |

**Example `property.json`** (for elevenlabs):
```json
{
  "params": {
    "key": "${env:ELEVENLABS_TTS_KEY}",
    "model_id": "eleven_turbo_v2_5"
  }
}
```

**Example `property_basic_audio_setting1.json`**:
```json
{
  "dump": true,
  "dump_path": "./tests/keep_dump_output/",
  "params": {
    "sample_rate": 16000,
    "key": "${env:ELEVENLABS_TTS_KEY}"
  }
}
```

**Example `property_basic_audio_setting2.json`**:
```json
{
  "dump": true,
  "dump_path": "./tests/keep_dump_output/",
  "params": {
    "sample_rate": 24000,
    "key": "${env:ELEVENLABS_TTS_KEY}"
  }
}
```

**Example `property_miss_required.json`**:
```json
{
  "params": {"key": ""}
}
```

### For ASR Extensions

| Config File              | Purpose                    | Content                              |
| ------------------------ | -------------------------- | ------------------------------------ |
| `property_en.json`       | English transcription test | Valid key + `language: "en-US"`      |
| `property_zh.json`       | Chinese transcription test | Valid key + `language: "zh-CN"`      |
| `property_invalid.json`  | Error handling test        | `key: "invalid", region: "invalid"` |
| `property_dump.json`     | Audio dump test            | Valid key + `dump: true`             |

---

## Step 7: TTS Guarder Tests Your Extension Must Pass

Run with: `task tts-guarder-test EXTENSION=my_vendor_tts_python`

There are **15 core tests**. Some repositories may also include optional
vendor-specific checks such as subtitle alignment when the provider exposes
timing data.

### Must-Pass Tests

| Test                                    | What It Validates                                        |
| --------------------------------------- | -------------------------------------------------------- |
| `test_append_input`                     | Multiple text inputs appended with same request_id       |
| `test_append_input_stress`              | High volume of append operations                         |
| `test_append_input_without_text_input_end` | Missing text_input_end flags handled gracefully       |
| `test_append_interrupt`                 | New requests interrupting in-progress ones               |
| `test_basic_audio_setting`              | Different sample rates produce different audio           |
| `test_corner_input`                     | Special chars, emojis, very short/long text              |
| `test_dump`                             | Audio dump files created with valid PCM data             |
| `test_dump_each_request_id`             | Each request_id produces separate dump file              |
| `test_empty_text_request`               | Empty/whitespace text: audio_end within 500ms, no crash  |
| `test_flush`                            | Flush signal: receives flush_end, no data after 5s       |
| `test_interleaved_requests`             | 8 concurrent requests maintain separate audio streams    |
| `test_invalid_required_params`          | Invalid API key returns FATAL ERROR, no crash            |
| `test_invalid_text_handling`            | Malformed text handled without crash                     |
| `test_metrics`                          | TTFB metrics generated with valid timestamps             |
| `test_miss_required_params`             | Missing API key returns appropriate error                |

### Critical Pass Criteria

- **Event ordering**: `tts_audio_start` -> `pcm_frame`(s) -> `tts_audio_end` per request
- **Request isolation**: Interleaved requests must not mix audio streams
- **Error handling**: Invalid/missing configs must produce errors, never crashes
- **Empty text**: Must complete quickly (audio_end within 500ms), no audio generated
- **Flush**: After flush_end, no more data for 5 seconds
- **Dump files**: Valid PCM data, one file per request_id when enabled

## Step 8: ASR Guarder Tests Your Extension Must Pass

Run with: `task asr-guarder-test EXTENSION=my_vendor_asr_python`

There are **10 tests** (1 excluded by the default test runner):

| Test                        | What It Validates                                            |
| --------------------------- | ------------------------------------------------------------ |
| `test_connection_timing`    | Connects and transcribes English audio correctly             |
| `test_asr_result`           | Result structure: id, text, language, session_id fields      |
| `test_asr_finalize`         | Finalize signal produces final=True result + finalize_end    |
| `test_reconnection`         | Recovers gracefully after connection failure                 |
| `test_vendor_error`         | Invalid creds produce proper error with vendor info          |
| `test_multi_language`       | English (en-US) and Chinese (zh-CN) both transcribe correctly|
| `test_dump`                 | Audio dump files created correctly                           |
| `test_metrics`              | TTFW and TTLW metrics: positive, TTLW > TTFW                |
| `test_audio_timestamp`      | start_ms and duration_ms accuracy                            |
| `test_same_session_finalize_reconnect` | Audio sent after finalize still transcribes (fresh session if the vendor closes) |
| `test_connection_status`    | connection_status_changed events — **allowlist-gated** (see below) |
| `test_long_duration_stream` | **Excluded by default test runner** — 5+ min stream without timeout |

### Critical Pass Criteria

- **Result fields**: Every ASR result must have `id`, `text`, `language`, `session_id`
- **Finalize**: Must produce `final=True` result and `asr_finalize_end` response
- **Error format**: Errors must have `id`, `module`, `code`, `message` + vendor info
- **Metrics**: TTFW > 0, TTLW > TTFW, both in milliseconds
- **Audio format**: Accepts 16-bit PCM, 16kHz, mono, 320 bytes per frame

### Guarder Contract Gotchas (learned the hard way)

- **Timestamps** (`test_audio_timestamp`): every final needs `duration_ms > 0`,
  and consecutive finals must not overlap (`prev.start_ms + prev.duration_ms
  <= next.start_ms`). If the vendor returns no per-segment timing, synthesize
  contiguous timestamps from the audio timeline: start = end of the previous
  segment, end = total user audio sent when the final arrives.
- **Invalid credentials must be NON-fatal** (`test_reconnection`): the test
  feeds bad credentials and asserts every error in the window is non-fatal
  (retry expected). Classify only HTTP 401/403 as immediately fatal; vendors
  that reject bad keys another way (e.g. a websocket close code) must surface
  a non-fatal error and let the reconnect manager escalate to FATAL at the
  retry ceiling. Any fatal error inside the test window fails the test.
- **connection_status tests are allowlist-gated**: the guarder only asserts
  `connection_status_changed` sequences for extensions listed in
  `_EXTENSIONS_WITH_CONNECTION_STATUS` (in
  `integration_tests/asr_guarder/tests/test_connection_status.py`); other
  extensions skip these two tests — expect `N passed, 2 skipped`.
- **Capture the summary**: pipe guarder output to a log file
  (`task asr-guarder-test ... > /tmp/guarder.log 2>&1; echo $?`) — piping to
  `tail` reports the pipe's exit code, not pytest's, and the retry tracebacks
  from `test_reconnection` push the summary line out of a short tail.

---

## AudioFrame Creation Pattern

```python
from ten_runtime import AudioFrame, AudioFrameDataFmt

frame = AudioFrame.create("pcm_frame")
frame.set_sample_rate(16000)
frame.set_bytes_per_sample(2)        # 16-bit
frame.set_number_of_channels(1)      # Mono
frame.set_data_fmt(AudioFrameDataFmt.INTERLEAVE)
frame.set_samples_per_channel(len(pcm_data) // 2)
frame.alloc_buf(len(pcm_data))
buf = frame.lock_buf()
buf[:] = pcm_data
frame.unlock_buf(buf)
await ten_env.send_audio_frame(frame)
```

Set all properties **before** `alloc_buf()`.

## Params Dict Pattern

For HTTP/WebSocket vendor APIs:

1. Store all config including `api_key` in `params` dict
2. Extract `api_key` for auth headers in client constructor
3. Keep first-class convenience fields if needed (`model`, `sample_rate`, etc.)
4. Forward remaining vendor params to the HTTP body or WebSocket query string
5. Strip secrets only from the outbound request payload / query, not from the in-memory config
6. In `update_params()`: add vendor-required params, normalize keys

```python
# Client constructor
self.api_key = config.params.get("api_key", "")
self.headers = {"Authorization": f"Bearer {self.api_key}"}

# Request method / WS URL builder
vendor_params = {**self.config.params}
vendor_params.pop("api_key", None)
```

## Bidirectional Extension Pattern

For extensions that both receive from and send to the graph:

```python
class MyBridge(AsyncExtension):
    async def on_init(self, ten_env):
        self.ten_env = ten_env  # Store for callbacks

    async def on_audio_frame(self, ten_env, audio_frame):
        buf = audio_frame.lock_buf()
        self.external_system.send(bytes(buf))
        audio_frame.unlock_buf(buf)

    async def _external_callback(self, data):
        frame = AudioFrame.create("pcm_frame")
        # ... fill frame ...
        await self.ten_env.send_audio_frame(frame)
```

## Pre-Submission Checklist

- [ ] `addon.py` decorator name matches `manifest.json` `name` field
- [ ] All abstract methods implemented (vendor, request_tts/send_audio, etc.)
- [ ] Config validation raises ValueError for missing required params
- [ ] `to_str()` encrypts sensitive fields before logging
- [ ] `tests/configs/` has all required config files (see Step 6)
- [ ] Optional vendor-specific tests are documented explicitly when unsupported
- [ ] `task tts-guarder-test` or `task asr-guarder-test` passes
- [ ] `task format` passes (Black, line-length 80)
- [ ] `task lint-extension EXTENSION=my_vendor_tts_python` passes
- [ ] `requirements.txt` lists all Python dependencies
- [ ] `README.md` documents config properties and env vars
- [ ] No hardcoded API keys anywhere

## Language-Specific Notes

| Language   | Create Command                                                       |
| ---------- | -------------------------------------------------------------------- |
| Python     | `tman create extension name --template default_async_extension_python` |
| Go         | `tman create extension name --template default_extension_go`          |
| C++        | `tman create extension name --template default_extension_cpp`         |
| Node.js    | `tman create extension name --template default_extension_nodejs`      |

## Portal References (Full Guides)

- [Create a TTS Extension (89K)](https://github.com/TEN-framework/portal/blob/main/content/docs/ten_agent_examples/extension_dev/create_tts_extension.mdx) [EXTERNAL]
- [Create an ASR Extension (39K)](https://github.com/TEN-framework/portal/blob/main/content/docs/ten_agent_examples/extension_dev/create_asr_extension.mdx) [EXTERNAL]
- [Create a Hello World Extension](https://github.com/TEN-framework/portal/blob/main/content/docs/ten_agent_examples/extension_dev/create_hello_world_extension.mdx) [EXTERNAL]
- [How Interrupt (Flush) Works](https://github.com/TEN-framework/portal/blob/main/content/docs/ten_agent_examples/tutorials/how_does_interrupt_work.md) [EXTERNAL] — cancel/flush flow explained end-to-end

## See Also

- [Back to Conventions](../04_conventions.md)
- [Back to Workflows](../05_workflows.md)
- [Testing](testing.md) — Full guarder test details and debugging
