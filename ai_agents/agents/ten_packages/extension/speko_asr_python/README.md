# Speko Router ASR extension

Streams TEN PCM audio to the Speko Router and emits the standard TEN
`asr_result`, `asr_finalize_end`, `metrics`, `error`, and connection-status
messages.

## Configuration

Set `SPEKO_API_KEY`, then use the extension defaults or override `params` in
your graph.

| Property | Default | Description |
| --- | --- | --- |
| `params.base_url` | `https://router.speko.dev` | Speko Router origin |
| `params.sample_rate` | `16000` | PCM input sample rate |
| `params.channels` | `1` | PCM input channel count |
| `params.language` | `en-US` | Optional routing/transcription hint |
| `params.routing` | auto, balanced | Speko routing selection |
| `params.options` | `{}` | Diarization, keywords, noise reduction, or namespaced provider options |
| `params.buffer_duration_ms` | `5000` | Audio retained while disconnected; `0` discards |

The transport is raw signed 16-bit little-endian PCM. A TEN `asr_finalize`
message sends Speko `input.commit` and `asr_finalize_end` is emitted after the
corresponding final transcript.

```json
{
  "type": "extension",
  "name": "asr",
  "addon": "speko_asr_python",
  "extension_group": "asr",
  "property": {
    "params": {
      "api_key": "${env:SPEKO_API_KEY}",
      "routing": {"mode": "auto", "objective": "latency"},
      "language": "en-US"
    }
  }
}
```

For an explicit route, set `routing` to
`{"mode":"explicit","provider":"deepgram","model":"nova-3"}`.


## Testing

From the extension directory, with TEN runtime/base packages installed and
available on `PYTHONPATH`, run the client, extension lifecycle, and package
contract regressions:

```bash
./tests/bin/start
```

From `ai_agents/`, set `SPEKO_API_KEY` and run the live guarder:

```bash
task asr-guarder-test EXTENSION=speko_asr_python
```

Run ASR and TTS guarders sequentially. The guarder uses `tests/configs` and
contacts the hosted Router; it requires a funded key and an available route.
For reproducible provider checks, copy the configs to a temporary directory,
set `params.routing` to an explicit supported provider/model, then invoke the
installed guarder’s `tests/bin/start` with `--extension_name speko_asr_python`
and `--config_dir /absolute/path/to/configs`. Keep invalid-key configs invalid.
Client/lifecycle unit tests use mocked transport and do not require credentials.

Transient disconnects reconnect on subsequent audio ingress; failed sends are
not replayed. Finalize acknowledges already-finalized input without waiting
for a duplicate transcript. Fallback timestamps retain session position while
resetting per-turn audio accounting. Permanent admission denials require correcting
the cause and restarting the extension.
