# thunderphone_mllm_python

Run a [ThunderPhone](https://thunderphone.com) voice agent as the
speech-to-speech (multimodal LLM) model of a TEN graph. ThunderPhone handles
speech recognition, the language model, the voice, turn-taking, 47 languages
and tools; TEN handles the transport (Agora RTC, WebSocket, ...) and the rest
of the graph.

ThunderPhone's [Realtime WebSocket API](https://thunderphone.com/docs/api-reference/realtime)
speaks the OpenAI Realtime protocol, so this extension mirrors
`openai_mllm_python` and implements the same `mllm-interface.json`.

## Two ways to use it

**Saved agent.** Set `agent_id`. The agent's prompt, voice, engine, languages,
tools, greeting and silence handling are configured on ThunderPhone; the
graph only moves audio. Tools registered in the graph are ignored.

**Inline session.** Leave `agent_id` empty and set `prompt` (and optionally
`product`, `voice`, `language`). Tools registered in the graph
(`tool_register`) are sent to ThunderPhone with the first `session.update`,
which starts the call. ThunderPhone freezes instructions, tools and voice at
that point, so tools must be registered before audio starts (the extension
waits up to 500 ms after the session is created for late registrations).

Every WebSocket session is one call, visible in ThunderPhone's call history
and billed per minute. When the ThunderPhone agent hangs up (`call.ended`)
the extension does not reconnect, because a reconnect would start a new call.

## Properties

| Property | Type | Description |
|---|---|---|
| `api_key` | `string` | ThunderPhone secret key (`sk_live_...`). Default `${env:THUNDERPHONE_API_KEY}`. |
| `agent_id` | `string` | Id of a saved ThunderPhone agent. Leave empty for an inline session. |
| `product` | `string` | Engine for inline sessions: `spark`, `bolt` or `storm`. |
| `voice` | `string` | ThunderPhone voice name for inline sessions. |
| `language` | `string` | Primary language hint for inline sessions, e.g. `es`. |
| `prompt` | `string` | Instructions for inline sessions. Required without `agent_id`. |
| `from_number`, `to_number` | `string` | Numbers to record on the call when the graph fronts a phone line. |
| `live_transcripts` | `bool` | Stream caller transcript fragments mid-utterance (billed extra). |
| `sample_rate` | `int32` | PCM sample rate in both directions: `24000` (default) or `16000`. |
| `base_url`, `path` | `string` | Endpoint override. Defaults to `wss://api.thunderphone.com` + `/v1/realtime`. |

## Graph

Swap the `v2v` node of `examples/voice-assistant-realtime` for:

```json
{
  "type": "extension",
  "name": "v2v",
  "addon": "thunderphone_mllm_python",
  "property": {
    "api_key": "${env:THUNDERPHONE_API_KEY}",
    "agent_id": "${env:THUNDERPHONE_AGENT_ID|}",
    "product": "bolt",
    "language": "en",
    "prompt": "You are Acme Dental's receptionist. Be brief."
  }
}
```

The extension emits the standard MLLM server events
(`mllm_server_session_ready`, `mllm_server_input_transcript`,
`mllm_server_output_transcript`, `mllm_server_interrupted`,
`mllm_server_function_call`). Transcript metadata carries the ThunderPhone
`call_id`, usable with `GET /v1/calls/{call_id}` for the recording,
transcript and grade after the call.

## Notes

- Turn detection is server-side and always on.
- Injected assistant messages (`mllm_client_message_item` with role
  `assistant`) are not accepted by ThunderPhone; put the greeting in the
  prompt or on the saved agent, then trigger it with
  `mllm_client_create_response` (inline sessions only; a saved agent greets
  on its own).
- Audio is 16-bit mono PCM in both directions.

## Tests

```bash
task test-extension EXTENSION=agents/ten_packages/extension/thunderphone_mllm_python
```

`tests/test_realtime.py` needs no credentials. `tests/test_extension.py`
drives the addon through the TEN runtime; with `THUNDERPHONE_API_KEY` set it
opens a real (billed) session.
