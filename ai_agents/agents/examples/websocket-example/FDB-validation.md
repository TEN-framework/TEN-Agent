# FDB graph validation — 2026-10-20

Tested TEN source commit: `e0620432cbc97ab49a0525ba4f1a0e3ccfa90220`.
Graph: `fdb_v3` in `tenapp/property.json`.
Canonical graph SHA-256 (sorted JSON, compact separators):
`f49df39aad9d439d7af64ea874a3e49010ae89605a2ee32b6991f9507c28dd5e`.

## Results

| Check | Result |
| --- | --- |
| Graph, transport and bridge lifecycle tests | 22 passed |
| Existing bridge unit tests | 8 passed |
| Native TEN WebSocket command/event/PCM tests | 2 passed |
| Deepgram query and metadata regression tests | 6 passed |
| Existing ElevenLabs TTS extension suite | 9 passed, existing deprecation/mock warnings |
| API server `go test ./...` | Both packages compile; no test files |
| TEN graph/property and three manifest schema checks | Passed |
| Black on affected Python directories | Passed |
| Pylint on WebSocket and bridge extensions | 10.00/10 |
| Runtime image and synthetic full graph smoke | Passed |

The native runtime smoke starts the API and the actual five graph nodes in the
runtime image. Local WebSocket fixtures replace the three external services;
the real ASR extension, Rust Agora Mind addon, bridge and TTS extension run.
It verifies `/graphs`, `/start`, Workspace/Session creation, PCM input, ASR final,
one `session.user_input`, a completed turn, exactly 6400 bytes of expected output
PCM at 16 kHz, `tts_audio_end`, Session deletion, and `/stop`.

The observed Agora Mind operations, in order, were:

```text
workspace.create
session.create
session.user_input
session.delete
```

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
`sha256:0e571007cf6519d7bac2e0a2793b8786716e23c4fa4515a0a55bb6a0fc845fae`

The image is local and has no published registry digest. Compilation and release
completed using the common Dockerfile. After a Docker Hub timeout, the runtime
stage reused the completed builder and a cached Ubuntu 22.04 image. The final
bridge Python files were copied into the image after the runtime smoke exposed
and verified fixes for addon registration and the TTS metadata Session ID type.

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
