# Agora Mind bridge

`agora_mind_bridge_python` is the graph-local adapter for the FDB-v3 voice
path. It keeps the Agora Mind wire protocol in the existing
`agora_mind_extension_rust` extension and handles the two TEN message
translations needed by the agent:

- final `asr_result` data becomes `submit_user_input` with a pure-text
  `input_json` payload;
- a top-level `session_turn_completed` in `agora_mind_event` becomes one
  `tts_text_input` data message.

The bridge reserves ASR finals before submitting them, suppressing overlapping
duplicates even when a command times out after possible acceptance. It remembers
completed turns for the active Session so delayed completion replays produce no
extra TTS. It learns `session_id` from `create_session`, clears it on disconnect
or Workspace replacement, and ignores events from other or deleted Sessions.
On stop it attempts a bounded `delete_session` for any remaining active Session.
Late command results after a Session reset are rejected, so a disconnect or
shutdown cannot be undone by a pending `create_session` result.

Finals with a positive audio duration are identified by `start_ms`, `duration_ms`
and normalized text within this graph's single ASR timeline. TEN regenerates the
ASR result `id` after each final. The interval identity suppresses replays after a
turn completes and accepts the same words at a new interval. A text-only cache
would keep less state but drop legitimate repeated speech. Without a reliable
interval, the bridge retains consecutive-text suppression until turn completion.

Failed ASR submissions emit the standard TEN `error` data shape with module
`agora_mind_bridge`, code `1000`, a message, and Session/case metadata. A rejected
native command also preserves its `response_json` in metadata. The bridge does
not retry an input after an ambiguous timeout; the runner handles case failure
and its overall deadline.

## Configuration

| Property | Default | Description |
| --- | --- | --- |
| `agora_mind_extension` | `agora_mind` | Destination extension for Agora Mind commands |
| `tts_extension` | `tts` | Destination extension for TTS input |
| `example_id` | `${env:AGORA_MIND_FDB_EXAMPLE_ID\|}` | Case identifier carried in TTS metadata |
| `session_id` | `0` | Optional existing Session ID; `0` waits for `create_session` |
| `command_timeout_ms` | `30000` | Timeout for forwarded commands |

The bridge does not copy or resolve the FDB prompt. Callers send
`system_prompt_path` and the JSON-encoded action scope and merge policy through
the `create_session` command, which the bridge forwards unchanged.

## Graph wiring contract

The `fdb_v3` graph in `examples/websocket-example/tenapp/property.json` connects
these messages:

```text
stt.asr_result          -> bridge.asr_result
agora_mind.agora_mind_event -> bridge.agora_mind_event
bridge.error           -> websocket_server.error
```

The bridge sends its Agora Mind commands directly to the extension instance
named by `agora_mind_extension` (default: `agora_mind`). The graph therefore
installs the published `agora_mind_extension_rust` addon. It also sends
`tts_text_input` directly to `tts_extension`, so no additional route is needed
for either path. See the example's [FDB guide](../../../examples/websocket-example/FDB.md)
for WebSocket commands, case isolation and runtime-image setup.
