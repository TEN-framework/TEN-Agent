# Cekura Metrics Extension for TEN Framework

This extension collects metrics and transcripts from TEN agent components (ASR/STT, TTS, LLM, etc.) and POSTs them to [Cekura](https://cekura.ai) observability for evaluation and monitoring.

## Keys and secrets (what we sync to git)

**There are no real Cekura credentials in the tracked files.** In the repo you should only see:

| Location | What appears |
|----------|----------------|
| `property.json` examples | `"api_key": "${env:CEKURA_API_KEY|}"` and similar `${env:…}` placeholders (TEN optional default after `|`). |
| This README | Illustrative words like `your-api-key-here`, never live tokens. |
| Unit tests | Dummy values such as `"test-key"` (not a production key). |

Never commit literal API keys, Groq/OpenAI-style `sk-…` strings, or Agora/Cekura secrets into `property.json` or README. Use environment substitution only.

## Suggested pull-request split

| PR | Scope | Purpose |
|----|--------|---------|
| **1** | This extension + `manifest.json` / `property.json` wiring (as in `examples/voice-assistant`) + this README | Ship Cekura with **graph-only** integration and document **what works vs what does not** without changing `main_python`. |
| **2** (optional) | `main_python` (or your control extension) | Emit `transcript` / `llm_response` / `tool_call` data to `cekura_metrics` (e.g. via `helpers.py` and explicit `Loc` destinations) so Cekura sees **assistant** lines and **tools**, not only STT + module metrics. |

PR 1 is mergeable on its own; PR 2 is only if you need full transcript parity with the in-app conversation log.

---

## What works without changing `main_python`

When the graph wires the same channels as the stock `voice_assistant` example:

- **Session lifecycle**: Fan-out `on_user_joined` / `on_user_left` from `agora_rtc` → `cekura_metrics` starts a session on first join and flushes on last leave.
- **User speech (final)**: Fan-out `asr_result` from STT → `cekura_metrics` (in parallel with `main_control`).
- **Assistant speech**: Fan-out `text_data` from TTS → `cekura_metrics`. `ten_ai_base`'s TTS base classes emit `text_data` via `send_data` **without** `set_dests`, so the runtime routes it along graph edges. Any subscriber (including Cekura) can tap it. This carries the **spoken** assistant transcript (what TTS is producing audio for). See "Why this works — routing proof" below.
- **Latency**: `metrics` data from STT / TTS / LLM (`ten_ai_base` module metrics).

If `CEKURA_API_KEY` is unset or configuration is invalid, the extension **stays idle** (logs a warning) so the rest of the agent still runs.

---

## What does *not* work from graph wiring alone

Two specific traffic shapes stay invisible to `cekura_metrics` unless `main_python` (or another bridge) explicitly fans them out:

1. **The UI-bound, chunked transcript** that `main_python` posts to `message_collector`. It is sent with **`_send_data(..., dest="message_collector", ...)`** (a fixed `Loc` in `helper.py`). The runtime delivers it **only** to `message_collector`, bypassing graph fan-out. Whether you also want this shape in Cekura depends on whether TTS `text_data` is enough.
2. **LLM reasoning deltas and `tool_call` events**. `openai_llm2_python` (and other `AsyncLLM2BaseExtension` children) stream `chat_completion` **back through `return_result` (CmdResult)** to whoever called it — which is `main_python`. The `LLMResponseToolCall` / reasoning fragments surface there and never hit any `send_data` edge. To capture them in Cekura, `main_python` has to emit something Cekura subscribes to.

So the **optional PR 2** exists specifically for (1) if you want UI-parity transcripts and (2) for tool calls / reasoning.

### Can we add a “translator” in this extension instead of changing `main_python`?

**Partially — for `text_data` and `asr_result`, yes; for the `message_collector`-bound stream and tool calls, no.**

A handler in `cekura_metrics_python` only runs for **`Data` / `Cmd` that the runtime actually delivers to this extension**, which per `core/src/ten_runtime/extension/extension.c` (`ten_extension_determine_out_msgs`) means one of:

- the message was sent **without** `set_dests`, in which case the runtime consults graph connections (`ten_extension_determine_out_msg_dest_from_graph`) and dispatches to every subscriber, or
- the message was sent **with** an explicit `set_dests([Loc(...)])`, in which case the runtime ships it only to those extensions (`ten_extension_determine_out_msg_dest_from_msg`).

`main_python` → `message_collector` falls in the second bucket, so `cekura_metrics` is never in the delivery list. There is nothing to "translate" in-process.

Summary:

- **Yes**, this extension already translates formats it receives — `asr_result` → Cekura transcript rows, `text_data` → Cekura transcript rows, `metrics` → Cekura latency. That is normal `on_data` logic.
- **No**, it cannot turn `message_collector`-targeted traffic, nor `chat_completion` `CmdResult` streams, into Cekura rows without one of: a second `send_data` from `main_python` (or shared `helper.py`), a change to `message_collector2` to duplicate/forward, or a bridge extension placed on a path that already carries those messages.

### Why this works — routing proof

From `core/src/ten_runtime/extension/extension.c`:

- If `ten_msg_get_dest_cnt(msg) > 0` → route by explicit dests (`determine_out_msg_dest_from_msg`). No graph fan-out.
- Else → look up graph connections (`determine_out_msg_dest_from_graph`) and **clone to every subscriber**.

From `voice-assistant/tenapp/ten_packages/system/ten_ai_base/interface/ten_ai_base/tts.py` and `tts2.py`: the TTS base classes call `ten_env.send_data(data)` on a freshly `Data.create("text_data")` without ever calling `set_dests`. That puts the message in the "graph-routed" path, so a `data.source = [{ "extension": "tts" }]` subscription on `cekura_metrics` is sufficient to receive it in parallel with whoever else consumes it (e.g. `main_control`).

From `voice-assistant/tenapp/ten_packages/extension/main_python/helper.py` (`_send_data`): explicit `data.set_dests([Loc("", "", dest)])`. That is the second bucket and bypasses graph fan-out by design.

That is why the optional **second PR** exists for UI-parity transcripts and tool-call events — not for basic caller/assistant transcripts.

---

## For coding assistants (how to wire Cekura in)

Use this checklist when editing a TEN **example app** (paths are relative to `tenapp/`):

1. **Register the addon**  
   In `manifest.json` → `dependencies`, add:
   ```json
   { "path": "../../../ten_packages/extension/cekura_metrics_python" }
   ```
   (Adjust `../` depth if your app lives elsewhere.)

2. **Lock file**  
   Run `tman install` inside `tenapp/` so `manifest-lock.json` picks up the new package (or merge the lock entry from `examples/voice-assistant`).

3. **Graph node**  
   Under `ten.predefined_graphs[].graph.nodes`, add an extension node named e.g. `cekura_metrics` with `addon`: `cekura_metrics_python`, `extension_group`: `default`, and a `property` block (see [Configuration](#configuration)).

4. **Graph connections**  
   Under the same graph’s `connections`, append a block for `cekura_metrics`:
   - **`cmd`**: `on_user_joined`, `on_user_left` with `source` → `agora_rtc` (same command names `main_control` already uses).
   - **`data`**: `asr_result` with `source` → your STT extension (same name STT already sends to `main_control`).
   - **`data`**: `text_data` with `source` → your TTS extension (assistant transcript from `ten_ai_base` TTS base classes).
   - **`data`**: `metrics` with `source` → STT, TTS, and LLM extensions that emit `ten_ai_base` metrics.

5. **Environment**  
   Set `CEKURA_API_KEY` and either a numeric **`CEKURA_AGENT_ID`** in property JSON (`agent_id`) **or** `CEKURA_ASSISTANT_ID` (`assistant_id` string). Example app uses `${env:CEKURA_ASSISTANT_ID|}` plus `agent_id: 0` when only assistant id is needed.

6. **Python deps**  
   Ensure `aiohttp` is installed for this addon (see `requirements.txt`).

Do **not** commit real API keys; use `${env:...}` only.

---

## For humans (manual wiring)

You can achieve the same result as above in two ways:

1. **TMAN Designer** (if your TEN build includes it)  
   Open the designer, add the `cekura_metrics_python` extension node, set properties from the table below, then draw **data/cmd connections** equivalent to the JSON in the [Reference fragment](#reference-graph-fragment-voice_assistant-example). Export or save so `property.json` / graph state updates.

2. **Edit `property.json` by hand**  
   Merge the [Reference fragment](#reference-graph-fragment-voice_assistant-example) into your graph’s `nodes` and `connections`, and merge the manifest path as in step 1 for assistants.

If your UI only exposes a subset of fields, fall back to raw `property.json` for advanced links (multi-source `metrics`, duplicate RTC commands).

---

## Reference graph fragment (`voice_assistant` example)

**Node** (place with other extensions):

```json
{
  "type": "extension",
  "name": "cekura_metrics",
  "addon": "cekura_metrics_python",
  "extension_group": "default",
  "property": {
    "api_key": "${env:CEKURA_API_KEY|}",
    "agent_id": 0,
    "assistant_id": "${env:CEKURA_ASSISTANT_ID|}",
    "base_url": "https://api.cekura.ai",
    "auto_flush": true,
    "auto_flush_interval_ms": 5000,
    "metric_ids": "${env:CEKURA_METRIC_IDS|}",
    "collect_latency": true,
    "collect_transcripts": true,
    "collect_tool_calls": true
  }
}
```

Set **`agent_id`** to your Cekura numeric agent id when you are not using `assistant_id`.

**Connections** (append under the same graph’s `connections` array):

```json
{
  "extension": "cekura_metrics",
  "cmd": [
    {
      "names": ["on_user_joined", "on_user_left"],
      "source": [{ "extension": "agora_rtc" }]
    }
  ],
  "data": [
    {
      "name": "asr_result",
      "source": [{ "extension": "stt" }]
    },
    {
      "name": "text_data",
      "source": [{ "extension": "tts" }]
    },
    {
      "name": "metrics",
      "source": [
        { "extension": "stt" },
        { "extension": "tts" },
        { "extension": "llm" }
      ]
    }
  ]
}
```

Rename `stt` / `tts` / `llm` / `agora_rtc` if your graph uses different extension instance names.

---

## Installation

Copy this folder to your agent’s extensions tree (same level as other Python addons), or depend on it via `manifest.json` `path` as in the official examples layout:

`ai_agents/agents/ten_packages/extension/cekura_metrics_python`

Install Python dependency:

```bash
pip install aiohttp
```

---

## Configuration

### Property (`property.json` node `property` or root)

```json
{
  "api_key": "${env:CEKURA_API_KEY}",
  "agent_id": 123,
  "assistant_id": "",
  "base_url": "https://api.cekura.ai",
  "auto_flush": true,
  "auto_flush_interval_ms": 5000,
  "metric_ids": "1,2,3",
  "collect_latency": true,
  "collect_transcripts": true,
  "collect_tool_calls": true
}
```

### Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `api_key` | string | `""` | Cekura API key; if empty after env substitution, extension does nothing. |
| `agent_id` | int | `0` | Cekura agent id (required unless `assistant_id` is set). |
| `assistant_id` | string | `""` | External assistant id (min length enforced at API). |
| `base_url` | string | `https://api.cekura.ai` | API base URL. |
| `auto_flush` | bool | `true` | POST full snapshots on an interval while session is open. |
| `auto_flush_interval_ms` | int | `5000` | Interval for auto-flush. |
| `metric_ids` | string | `""` | Comma-separated Cekura metric ids to evaluate. |
| `collect_latency` | bool | `true` | Ingest `metrics` / latency payloads. |
| `collect_transcripts` | bool | `true` | Ingest transcript-style payloads where connected. |
| `collect_tool_calls` | bool | `true` | Ingest `tool_call` where connected. |

---

## Runtime behaviour (when extension is enabled)

1. Configure `api_key` and `agent_id` or `assistant_id`.
2. Wire the graph (see above) or send `session_start` / data from control code using `helpers.py`.
3. With **auto RTC** wiring, the first `on_user_joined` opens a session; last `on_user_left` ends and POSTs. With **`auto_flush`**, snapshots POST on a timer while the session is open.
4. Listen for **`metrics_sent`** after each HTTP POST.

---

## API

### Data inputs

#### `transcript`

```json
{
  "text": "Hello, how can I help you?",
  "role": "assistant",
  "is_final": true,
  "start_time": 1.5,
  "end_time": 3.2
}
```

#### `llm_response`

```json
{
  "text": "I can help you with that.",
  "latency_ms": 250.5,
  "tokens_in": 50,
  "tokens_out": 25,
  "model": "gpt-4o"
}
```

#### `tts_audio`

```json
{
  "text": "Hello there",
  "latency_ms": 150.0,
  "duration_ms": 1200.0,
  "vendor": "elevenlabs"
}
```

#### `asr_result`

JSON root from STT (`ten_ai_base`) or flat properties — see `extension.py`.

#### `metrics`

`ModuleMetrics` JSON root from STT/TTS/LLM.

#### `tool_call`

```json
{
  "name": "get_weather",
  "arguments": "{\"location\": \"NYC\"}",
  "result": "{\"temp\": 72}",
  "success": true,
  "latency_ms": 500.0
}
```

### Commands

- `session_start` / `session_end` / `flush` — see inline docstrings in `extension.py`.
- `on_user_joined` / `on_user_left` — optional RTC lifecycle from `agora_rtc`.

### Command output

- `metrics_sent` — `session_id`, `success`, optional `call_log_id`.

---

## Helpers (`helpers.py`)

Optional typed sends from other extensions. When using them, set destinations the same way as `main_python/helper.py` (`Loc`) if your runtime requires explicit routing; graph-only routing applies to producers that emit on connected channels.

---

## Cekura metrics catalogue

See [Cekura pre-defined metrics](https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics).

---

## Environment variables (full list)

| Variable | Required when Cekura is enabled? | Purpose |
|----------|----------------------------------|---------|
| `CEKURA_API_KEY` | **Yes** (to send anything) | Cekura API key (`X-CEKURA-API-KEY` on observe). If unset, the extension disables itself. |
| `CEKURA_ASSISTANT_ID` | **One of** this or numeric `agent_id` in JSON | External assistant id (e.g. `asst_…`). Used when `property.json` sets `"assistant_id": "${env:CEKURA_ASSISTANT_ID|}"` and `agent_id` is `0`. |
| `CEKURA_METRIC_IDS` | No | Comma-separated metric ids to evaluate on each observe call (e.g. `1,2,3`). |

**Not an env var:** you may instead set a numeric **`agent_id`** directly in the `cekura_metrics` node in `property.json` (no secret there — it is a public id in Cekura). You still need `CEKURA_API_KEY` for auth.

No other Cekura-specific env vars are required by this extension. (Your Agora / STT / LLM / TTS keys stay separate.)

---

## Copy-paste examples

### `.env` (Cekura only; combine with your existing TEN `.env`)

```bash
# Required to enable POSTs to Cekura
CEKURA_API_KEY=

# Pick ONE identity style:
# A) Assistant id from Cekura / provider (matches voice_assistant example property.json)
CEKURA_ASSISTANT_ID=

# B) If you prefer numeric agent id, leave CEKURA_ASSISTANT_ID unset and put agent_id in property.json (see below)

# Optional — limit which Cekura metrics run on each call
# CEKURA_METRIC_IDS=1,2,3
```

### `property.json` node — **assistant id via env** (matches `examples/voice-assistant`)

```json
{
  "type": "extension",
  "name": "cekura_metrics",
  "addon": "cekura_metrics_python",
  "extension_group": "default",
  "property": {
    "api_key": "${env:CEKURA_API_KEY|}",
    "agent_id": 0,
    "assistant_id": "${env:CEKURA_ASSISTANT_ID|}",
    "base_url": "https://api.cekura.ai",
    "auto_flush": true,
    "auto_flush_interval_ms": 5000,
    "metric_ids": "${env:CEKURA_METRIC_IDS|}",
    "collect_latency": true,
    "collect_transcripts": true,
    "collect_tool_calls": true
  }
}
```

### `property.json` node — **numeric agent id** (no `CEKURA_ASSISTANT_ID` needed)

Replace `12345` with your Cekura dashboard agent id (integer, not secret):

```json
{
  "type": "extension",
  "name": "cekura_metrics",
  "addon": "cekura_metrics_python",
  "extension_group": "default",
  "property": {
    "api_key": "${env:CEKURA_API_KEY|}",
    "agent_id": 12345,
    "assistant_id": "",
    "base_url": "https://api.cekura.ai",
    "auto_flush": true,
    "auto_flush_interval_ms": 5000,
    "metric_ids": "${env:CEKURA_METRIC_IDS|}",
    "collect_latency": true,
    "collect_transcripts": true,
    "collect_tool_calls": true
  }
}
```

### `manifest.json` dependency (path layout for `agents/examples/.../tenapp`)

```json
{
  "path": "../../../ten_packages/extension/cekura_metrics_python"
}
```

---

## License

MIT
