# FunASR ASR Python Extension

A local (self-hosted) speech-to-text extension for TEN Framework, powered by
[FunASR](https://github.com/modelscope/FunASR) — an open-source speech toolkit
from Tongyi Lab with strong multilingual ASR (Chinese, Cantonese, English,
Japanese, Korean and more). The model runs locally on CPU or CUDA; **no API key
is required** and audio never leaves your machine.

It mirrors the existing `whisper_stt_python` extension, swapping faster-whisper
for a local FunASR model — a natural fit for Chinese / Asian-language agents.

## Features

- Local, self-hosted ASR — no cloud, no API key, no per-minute billing.
- Strong Chinese / multilingual recognition; default model **SenseVoice-Small**
  auto-detects the spoken language and emits inverse-text-normalized text.
- Swappable models via config (e.g. the flagship `FunAudioLLM/Fun-ASR-Nano-2512`
  on GPU, or `paraformer-zh` for Chinese with timestamps).
- CPU or CUDA via the `device` parameter.

## Configuration (`property.json` → `params`)

| Param | Default | Description |
|---|---|---|
| `model` | `iic/SenseVoiceSmall` | FunASR model id. Use `FunAudioLLM/Fun-ASR-Nano-2512` (flagship LLM-ASR) on GPU, or `paraformer-zh` for Chinese. |
| `device` | `cpu` | `cpu` or `cuda`. |
| `language` | `auto` | Language hint, or `auto` to detect. |
| `use_itn` | `true` | Apply inverse text normalization. |
| `sample_rate` | `16000` | Input PCM sample rate (16-bit mono). |

## Requirements

```
pip install funasr
```

The model is downloaded automatically on first run.
