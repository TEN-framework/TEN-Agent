# kotoba_tts_python

TEN framework TTS extension for [Kotoba](https://kotoba.tech) text-to-speech,
served on [fal](https://fal.ai) as the public app `Kotoba-Technologies/kotoba-tts`.

The extension implements `AsyncTTS2BaseExtension` (WebSocket path) on top of
the official [`kotoba-sdk`](https://pypi.org/project/kotoba-sdk/) client.
Audio is delivered as 16-bit mono PCM at the configured sample rate.

## Configuration

Set the fal API key in the environment the TEN app runs in:

```bash
export KOTOBA_TTS_KEY=<your fal key>
```

`property.json` / graph node `params`:

| key | default | description |
|---|---|---|
| `key` | `${env:KOTOBA_TTS_KEY}` | fal API key (`api_key` is accepted as an alias) |
| `base_url` | `wss://fal.run/Kotoba-Technologies/kotoba-tts/v2/tts/ws` | WebSocket endpoint; a self-hosted URL uses `Bearer` auth automatically |
| `language` | `ja` | language served by the endpoint (the public app serves Japanese) |
| `speaker_id` | `male-01` | `male-01` or `female-01` |
| `sample_rate` | `16000` | `8000`, `16000` or `24000` |
| `request_timeout_seconds` | `30` | longest wait for the first audio chunk of a sentence, and between chunks |
| `segment_soft_limit_chars` | `120` | buffered text longer than this is cut at a comma; twice this is cut unconditionally |

Top-level `dump` / `dump_path` write one `kotoba_tts_dump_<request_id>.pcm`
per request for debugging.

## How it works

The service synthesizes one complete text per response, while TEN streams
LLM output as deltas. The extension buffers deltas per `request_id` and sends
a request as soon as a sentence is complete (`。！？!?.` or a newline), then
the remainder on `text_input_end`.

One WebSocket is reused across requests; it reconnects after the service's
idle timeout or any connection drop, and retries a sentence once when the
connection fails before any audio for it arrived. Connection state is
reported through `connection_status_changed` (`connecting`, `connected`,
`disconnected`).

Flush cancels the in-flight response (`response.cancel`), drops buffered text
and reports `tts_audio_end` with reason `INTERRUPTED`. Empty or
punctuation-only input ends immediately without contacting the service.

Errors: a rejected key or an unsupported language / sample rate is reported
as `FATAL_ERROR`; worker and transport failures are `NON_FATAL_ERROR`, and
the next request starts on a fresh connection.

## Tests

Extension-local tests run against an in-process fake of the Kotoba service
and need the TEN runtime. Inside the `ten_agent_build` container:

```bash
cd ten_packages/extension/kotoba_tts_python
tman -y install --standalone
pip install -r requirements.txt -r .ten/app/ten_packages/system/ten_ai_base/requirements.txt pytest
tests/bin/start
```

The TEN TTS guarder suite runs from a `ten-framework` checkout that
contains this extension (`scripts/sync-to-ten-fork.sh`). Against the live
service:

```bash
export KOTOBA_TTS_KEY=<your fal key>
task tts-guarder-test EXTENSION=kotoba_tts_python
```

Against the fake service, which needs no key (`tests/configs_fake/` points
at port 8765):

```bash
python3 ten_packages/extension/kotoba_tts_python/tests/run_fake_server.py 8765 &
export KOTOBA_TTS_KEY=fake-key
task tts-guarder-test EXTENSION=kotoba_tts_python CONFIG_DIR=tests/configs_fake
```

Guarder skips: `test_subtitle_alignment` is skipped because the service
exposes no word timestamps. `test_connection_status` runs for this
extension (listed in the guarder's WebSocket allowlist).
