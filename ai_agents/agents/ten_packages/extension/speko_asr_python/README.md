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
| `params.language` | `en-US` | Language tag for routing/transcription |
| `params.routing` | auto, balanced | Speko routing selection |
| `params.options` | `{}` | Diarization, keywords, noise reduction, or namespaced provider options |
| `params.buffer_duration_ms` | `5000` | Audio retained while disconnected; `0` discards |

The transport is raw signed 16-bit little-endian PCM. A TEN `asr_finalize`
message sends Speko `input.commit`. Each finalize is serialized and acknowledged
with its own `finalize_id` and metadata, including disconnected and timeout paths.
Silent or already-finalized input completes without waiting for another transcript.
Empty vendor transcripts are not emitted as user turns.

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

Transient disconnects have one background recovery loop with delays of 0.5, 1,
2, 4, and 4 seconds. A successful handshake resets this retry budget. Exhaustion,
invalid configuration, authentication/credit failures, and unavailable explicit
routes stop further attempts until the cause is corrected and the extension is
restarted. Failed sends are not replayed; disconnected input uses the bounded
buffer. Stop cancels pending recovery and finalization.

Finalization waits for an in-progress handshake and previously accepted audio
to drain through the base consumer before committing. Later ingress waits until
that finalize completes, preserving audio order and the request's metadata.

Segment and word timestamps are mapped onto TEN's user-audio timeline, retaining
position across connection replacement and excluding protocol silence. The raw
input dump records each ingress frame once, including buffered input.

Run standalone tests before guarders using the same image as CI:

```bash
task test-extension EXTENSION=agents/ten_packages/extension/speko_asr_python
task check
task lint
```

The standalone suite inspects emitted TEN JSON for results, finalize context,
metrics, status transitions, and redaction. Endpoint logs omit URL userinfo,
query parameters, and fragments. The single `key` vendor metadata field is
masked by TEN's reporting layer.
