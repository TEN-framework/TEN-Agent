# FDB graph validation — 2026-10-20

Tested TEN source commit: `9b041b378ef838fd28c7e0c72807a61e53ef7b89`.
Packaged graph regression test: `159312426` (`tests/test_fdb_runtime.py`).
Graph: `fdb_v3` in `tenapp/property.json`.
Canonical graph SHA-256 (sorted JSON, compact separators):
`06d9cd66ee212346e9e8df03c37d0d9333de60a1943a9025ea94b0334c2edcf7`.

## Results

| Check | Result |
| --- | --- |
| Graph, transport and bridge lifecycle tests | 32 passed |
| Existing bridge unit tests | 8 passed |
| Native TEN WebSocket command/event/PCM tests | 2 passed |
| Deepgram query and metadata regression tests | 6 passed |
| Existing ElevenLabs TTS extension suite | 9 passed, existing deprecation/mock warnings |
| API server `go test ./...` | Both packages compile; no test files |
| TEN graph/property and three manifest schema checks | Passed |
| Black on affected Python directories | Passed |
| Pylint on WebSocket and bridge extensions | 10.00/10 |
| Packaged graph regression tests | 6 passed in 38.95 seconds |
| Runtime image graph, manifest and bridge/transport source hashes | Match the current checkout |

The native runtime smoke starts the API and the actual five graph nodes in the
runtime image. Local WebSocket fixtures replace the three external services;
the real ASR extension, Rust Agora Mind addon, bridge and TTS extension run.
It verifies `/graphs`, `/start`, Workspace/Session creation, PCM input, repeated
ASR finals and completed turns, exactly one `session.user_input` and TTS request
per distinct audio interval, and 6400 bytes of expected output PCM per response
at 16 kHz/mono/16-bit. It checks
the successful `tts_audio_end` reason and exact 200 ms duration, Session deletion,
and `/stop`. Two cases reuse the same audio port and Agora Mind Session ID with
fresh workers; their case metadata remains isolated and `/list` confirms cleanup.
One- and two-turn cases use identical speech in separate intervals. Finals are
also replayed after the last answer, with TEN generating new result IDs; these
replays produce no extra input or audio. The Agent's final text is verified in
the raw Agora Mind events, independently of TTS transcript support.

Four additional tests inject a rejected input, a submission timeout, a
disconnected Agora Mind socket, and an accepted input with no completed turn.
Each test checks the failure event or runner deadline, suppresses duplicate
submissions and TTS, stops the failed worker, and then completes a normal case
using the same audio port. Quick regressions also verify that late Session
creation results cannot restore state after disconnect/stop, and stale input
failures do not affect a replacement Session.

The regression is now checked into the repository. Run it with the local image:

```sh
task test-fdb-runtime
```

The observed Agora Mind operations for a successful one-turn case, in order, were:

```text
workspace.create
session.create
session.user_input
session.delete
```

A two-turn case has two `session.user_input` operations before deletion. Quick
tests also accept distinct intervals while the previous turn is still pending
and preserve repeated turns when the ASR interval is unknown.

The existing voice-assistant graph matches the configuration before this work.
Official audio, external provider quality, fake tool execution and benchmark
scores require the Agora Mind runner and real provider credentials; they are
outside this synthetic test.

## Image and package versions

Build image:
`ghcr.io/ten-framework/ten_agent_build:0.7.14`

Build-image digest:
`sha256:ae28ec069644d5acda9a4182426662a368b993aca39413db77d0bf12d60f941a`

Local runtime image: `agora-mind/fdb-ten-agent:ten-0.7.14`

Local image ID:
`sha256:da85d31114699081ace76b5602b0c645b26fee774ddcfaa535b8cbe162b3c4a3`

The image is local and has no published registry digest. Compilation and release
completed using the common Dockerfile. After a Docker Hub timeout, the runtime
stage reused the completed builder and a cached Ubuntu 22.04 image. The final
bridge Python files, bridge manifest and graph configuration were copied into
the image after runtime tests verified the registration, TTS metadata, lifecycle,
failure reporting and ASR replay fixes. Their hashes match the current checkout.

| Package | Version |
| --- | --- |
| `ten_runtime`, `ten_runtime_python` | `0.11.73` |
| `ten_ai_base` | `0.7.62` |
| `agora_mind_extension_rust` | `0.1.0` |
| `agora_mind_bridge_python` | `0.1.0` |
| `websocket_server` | `0.0.2` |
| `deepgram_asr_python` | `0.5.4` |
| `elevenlabs_tts2_python` | `0.4.3` |

ASR and TTS graph settings are Nova-3 multilingual and
`eleven_multilingual_v2` / `pcm_16000`. The synthetic smoke uses deterministic
service replies and measures routing and lifecycle behavior.
