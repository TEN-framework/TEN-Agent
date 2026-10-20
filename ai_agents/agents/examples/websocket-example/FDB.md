# FDB-v3 graph

Select `fdb_v3` through the API's `/start` endpoint. It connects:

```text
WebSocket PCM -> Deepgram ASR -> Agora Mind bridge -> Agora Mind
                                      ^                 |
                                      | completed turn  |
                                      +-----------------+
                                      |
                                      v
                              ElevenLabs TTS -> WebSocket PCM
```

Agora Mind owns the model, FDB actions and prompt. The external Rust runner owns
WAV conversion, case scheduling, collection and evaluation. This graph uses the
existing Rust TEN addon for Agora Mind's WebSocket protocol and the Python bridge
for the ASR/TTS message conversion.

## Install and start

`tenapp/manifest.json` pins the published Linux x64
`agora_mind_extension_rust` package to `0.1.0`. `task install` installs it together
with the local bridge. The addon requires TEN runtime `0.11.71`; use the
`ten_agent_build:0.7.14` build image and `tman` 0.11.71 or newer.

Configure these variables in `ai_agents/.env` or the runtime container:

- `DEEPGRAM_API_KEY`
- `ELEVENLABS_TTS_KEY`
- `AGORA_MIND_ENDPOINT`: the Agora Mind server's WebSocket URL, reachable from
  the TEN worker/container. The two servers are separate processes.

Configure `AGORA_MIND_RESOURCES_ROOT` on the **Agora Mind server** to resolve
`prompts/fdb_v3.md`. The prompt stays in Agora Mind's resources directory.
The graph uses Deepgram Nova-3 multilingual recognition and ElevenLabs
`eleven_multilingual_v2`; provider settings can be overridden through `/start`.

Start the example with `task run`, then start one worker per case:

```json
{
  "request_id": "case-1-start",
  "channel_name": "fdb-case-1",
  "graph_name": "fdb_v3",
  "timeout": 120,
  "properties": {
    "websocket_server": {"port": 8765},
    "bridge": {"example_id": "case-1"}
  }
}
```

Send this body to `POST http://localhost:8080/start`. Set the same case ID in
`AGORA_MIND_FDB_EXAMPLE_ID` on the Agora Mind server so its tool logs correlate
with TEN's TTS metadata. `AGORA_MIND_FDB_EXAMPLE_ID` is also an optional default
for the bridge when `/start` does not override `example_id`.

Connect the runner to `ws://localhost:8765` (publish this port when using Docker).
The graph listens on `0.0.0.0` for container access and accepts one client.

## Session control

Before sending audio, send these commands on the TEN WebSocket in order and wait
for each successful `cmd_result`. Results carry the original `request_id`, a TEN
`status` (`0` means success), and `data.response_json`, a JSON-encoded Agora Mind
response. A timeout or routing error has a nonzero status and `data.error`.

```json
{"type":"cmd","name":"create_workspace","request_id":"case-1-workspace","data":{"profile":"benchmark.fdb_v3"}}
```

```json
{
  "type": "cmd",
  "name": "create_session",
  "request_id": "case-1-session",
  "data": {
    "model": "custom",
    "system_prompt_path": "prompts/fdb_v3.md",
    "model_action_scope_json": "{\"type\":\"only\",\"actions\":[\"search_flights\",\"book_flight\",\"update_identity_doc\",\"get_card_benefits\",\"get_exchange_rate\",\"modify_autopay\",\"search_apartments\",\"calculate_commute\",\"update_search_filter\",\"track_order\",\"search_products\",\"add_to_cart\"]}",
    "input_merge_policy_json": "{\"batch\":\"disabled\",\"history_tail\":\"disabled\"}",
    "input_format": "pure_text",
    "trigger_mode": "normal"
  }
}
```

The bridge learns the session ID from `session.created`. Action scope and merge
policy are strings at the TEN command boundary; the Rust addon converts them
into Agora Mind protocol objects. The graph routes these commands to the bridge:
`create_workspace`, `create_session`, `flush_session`, `set_session_debug`, and
`delete_session`. Session-specific commands require `data.session_id`.

## Audio and collection

Input messages are `{"audio":"<base64 PCM>","metadata":{"example_id":"case-1"}}`.
Input must be 16 kHz, mono, signed 16-bit little-endian PCM. The Rust runner must
convert 48 kHz WAV and pace the PCM before injection. TEN does not accept a WAV
container in the audio field.

Output audio uses `{"type":"audio","audio":"<base64 PCM>","metadata":{...}}`.
Use the output metadata's `sample_rate`, `channels`, and `bytes_per_sample` when
saving WAV. This graph requests 16 kHz PCM from TTS.

The graph also exposes the following through
`{"type":"data","name":"<event>","data":{...}}`:

- `asr_result`: input transcripts, including interim/final markers;
- `agora_mind_event`: raw Agora Mind envelopes in `data.event_json`, including
  final turn text, connection state and failures;
- `tts_text_result`: synthesized text;
- `tts_audio_start`, `tts_audio_end`, `tts_flush_end`: output lifecycle;
- `error`, `metrics`: provider failures and timing.

The bridge addresses TTS directly, so its TTS input has no additional graph
route. This keeps each final response on a single synthesis path. Wait for
`tts_audio_end` matching the output request ID, including all preceding audio
messages, before writing `output.wav`. Check its reason for completion/errors.
A turn with no final text produces no TTS request; use the Agora Mind completion
event and a bounded runner deadline in that case.

At case end, send `delete_session` with the session ID and wait for its result,
then close the socket and `POST /stop` with the worker's `channel_name`. Stop the
worker on failure as well. Start a fresh worker, Workspace and Session for the
next case, and run cases sequentially.

## Runtime image

From the repository root:

```sh
docker build -f ai_agents/Dockerfile \
  --build-arg USE_AGENT=agents/examples/websocket-example \
  -t agora-mind/fdb-ten-agent:ten-0.7.14 ai_agents
```

The image contains TEN speech processing and the two bridge addons. Supply
runtime environment variables and publish ports `8080` and `8765`; provide a
container-reachable `AGORA_MIND_ENDPOINT`. The API starts workers on demand via
`/start`. Record the TEN commit, build-image digest, final-image digest, addon
version, graph name, and provider versions with benchmark results.

## Quick tests

```sh
cd ai_agents/agents/examples/websocket-example
python3 -m pip install -r tests/requirements.txt
task test-fdb
```

These tests need no API keys, native TEN runtime, FDB corpus, or external server.
They check the graph, package dependencies, command and event routes, duplicate
suppression, PCM metadata, and a real local WebSocket connection. ASR, TTS and
the native Rust addon are replaced at their TEN boundaries in the graph flow
test. A real audio benchmark additionally requires provider credentials and
the Agora Mind server/runner.
