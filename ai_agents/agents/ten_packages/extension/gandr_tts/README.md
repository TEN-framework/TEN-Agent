# gandr_tts

TEN extension for Gandr text to speech (https://gandr.ai). It streams raw PCM audio from Gandr's OpenAI compatible speech endpoint over a plain HTTP POST.

## Features

- Streams audio from `POST https://tts.gandr.ai/v1/audio/speech` with an OpenAI compatible request body (`model`, `input`, `voice`, `response_format`)
- Output is PCM, s16le, mono, 24000 Hz (fixed by the service)
- Six voices: gandr-mia, gandr-ava, gandr-jenny, gandr-dane, gandr-leo, gandr-lewis
- 23 languages, every render watermarked
- First audio byte in 146 ms over the open internet, 116 ms p50 first audio, server side warm

API keys are available at https://gandr.ai. The free tier is 50,000 tokens; paid is $10 a month for one million tokens.

## API

Refer to `api` definition in [manifest.json](manifest.json) and default values in [property.json](property.json).

Properties (under `params`):

- `api_key` (string, required): Gandr API key, defaults to the `GANDR_TTS_API_KEY` environment variable
- `voice` (string): one of the six voices above, default `gandr-mia`
- `model` (string): default `tts-1`
- `endpoint` (string): override the request URL, default `https://tts.gandr.ai/v1/audio/speech`

`response_format` is always set to `pcm` by the extension, and the synthesized sample rate reported to the TEN pipeline is a fixed 24000 Hz.

## Development

### Build

No build step. Python only; dependencies are listed in `requirements.txt` (httpx, pydantic).

### Unit test

See `tests/`. All vendor calls are mocked, so no API key is needed. Run via `tests/bin/start` inside the extension test environment.

## Misc

Gandr also exposes mp3 and wav response formats on the same endpoint; this extension always requests pcm because the TEN audio pipeline consumes raw frames.
