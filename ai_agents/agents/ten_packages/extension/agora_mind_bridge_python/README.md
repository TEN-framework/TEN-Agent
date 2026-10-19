# Agora Mind bridge

`agora_mind_bridge_python` is the graph-local adapter for the FDB-v3 voice
path. It keeps the Agora Mind wire protocol in the existing
`agora_mind_extension_rust` extension and handles the two TEN message
translations needed by the agent:

- final `asr_result` data becomes `submit_user_input` with a pure-text
  `input_json` payload;
- a top-level `session_turn_completed` in `agora_mind_event` becomes one
  `tts_text_input` data message.

The bridge suppresses consecutive duplicate ASR finals and duplicate turn
completion events. It learns `session_id` from the `create_session` command
result and clears it when the Agora Mind extension reports a disconnect.

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

The eventual FDB graph should connect these messages:

```text
stt.asr_result          -> bridge.asr_result
agora_mind.agora_mind_event -> bridge.agora_mind_event
bridge.tts_text_input   -> tts.tts_text_input
```

The bridge sends its Agora Mind commands directly to the extension instance
named by `agora_mind_extension` (default: `agora_mind`). The graph therefore
needs an `agora_mind_extension_rust` addon supplied by the TEN image build; the
bridge package does not vendor that Rust transport or assume a checkout path
outside the TEN build context.
