# oruk_asr_python

Local, on-device speech-to-text for TEN using **Orukeet** — Oruk's multilingual
ASR model (NVIDIA Parakeet TDT 0.6B v3 with fitted Gabor kernels, 25 languages
with automatic detection). It runs entirely on CPU through
[`onnx-asr`](https://pypi.org/project/onnx-asr/) with the Orukeet INT8 ONNX
export, so it needs **no API key and uploads no audio**.

This extension transcribes complete utterances. The framework's turn detection
(VAD / `asr_finalize`) marks the end of a turn; the buffered audio is then
transcribed and a single **final** result is emitted. It does not produce
interim text, word timestamps, or speaker labels. For streaming interim results
and phrase-emotion estimates, use `oruk_realtime_asr_python`.

## Audio

Mono **PCM16 at 16 kHz** (`pcm_frame`).

## Configuration (`property.json` → `params`)

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `sample_rate` | int | `16000` | Must be 16000. |
| `language` | string | `"auto"` | Orukeet auto-detects; must be `"auto"`. |
| `result_language_default` | string | `"und"` | Optional locale stamped on every result (e.g. `"en-US"`). |
| `cache_dir` | string | Hugging Face default | Where the model is cached. |
| `local_files_only` | bool | `false` | Require a cached model instead of downloading. |
| `model` | string | `"orukeet"` | Fixed to Orukeet. |

## Model download

On first connect, the pinned Orukeet INT8 ONNX export (~486 MB) is downloaded
from Hugging Face (`oruk/orukeet`) and verified by checksum, then loaded once.
Set `cache_dir` to control the cache location, or `local_files_only: true` to
require a pre-provisioned cache in offline deployments.

## Licensing

Orukeet code is MIT; the model weights and Gabor kernels are CC BY-SA 4.0. See
the model card at https://huggingface.co/oruk/orukeet.

## Lifecycle and validation

Invalid configuration prevents connection attempts. Each finalize request
marks its position in the audio queue, drains preceding frames, and snapshots
that turn before accepting subsequent audio. Overlapping finalize requests
retain their individual boundaries and metadata.

A connected utterance is limited to **10 MiB** of PCM16 (about 5.5 minutes).
Exceeding this limit emits one nonfatal `utterance_too_long` error and discards
the whole turn. Audio is ignored until the next finalize, which acknowledges
the discarded turn; the following turn can proceed normally.

Audio draining, model readiness, and recognition each have a **30-second**
deadline. A timeout emits a fatal error and disables the extension instance;
subsequent finalize requests acknowledge promptly without starting more work.
Stop and finalize do not wait indefinitely for native inference. Python cannot
interrupt an active ONNX call: its result is ignored and its model is released
when that call returns. Restart the extension after a fatal timeout.

Run these commands from `ai_agents/` in the supported Linux development image
(`ghcr.io/ten-framework/ten_agent_build:0.7.14`):

```bash
task test-extension EXTENSION=agents/ten_packages/extension/oruk_asr_python
task asr-guarder-test EXTENSION=oruk_asr_python CONFIG_DIR=tests/configs
```

Run guarders sequentially. In fresh standalone containers, install the extension
requirements and the installed TEN system packages' `requirements.txt` first;
`tman install --standalone` installs TEN packages, not their Python dependencies.
The guarder install handles its own dependencies.

Offline local lifecycle and native-work deadline fault-injection tests are in
`tests/test_lifecycle.py`. They import only this extension and run with its own
requirements, using a thin stubbed TEN boundary without downloading models or
contacting the provider. The native ASR guarder separately exercises the real
runtime and provider. Long-duration cases are opt-in and are not included in
the default guarder command.

When the recognizer does not report a detected language, results use `und`
(undetermined), or the caller's `result_language_default`. A caller-supplied
locale is metadata, not a detected-language or accuracy result.

The local model supports Spanish but not Chinese. The multilingual guarder
therefore uses the existing English and Spanish fixtures for this extension.
