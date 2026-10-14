# TTS Guarder Test Guide

As of: 2026-10-13

This document describes how to run Guarder Test for TTS

## Environment Variables

Before running the test, you need to set the following environment variables:

```bash
# TTS Vendor Services API Key
export VENDOR_TTS_API_KEY=your_api_key_here
#for example:
export ELEVENLABS_TTS_API_KEY=your_elevenlabs_api_key

```

Or create a `.env` file in the project root:

```bash
# .env file
ELEVENLABS_TTS_API_KEY=your_elevenlabs_api_key
```

## Test Text

prepare mutiple text for testing different scenario

## Running the Test

```bash
# Run the test
bash tests/bin/start tests/test_elevenlabs_tts_basic.py::test_short_text --extension_name=elevenlbas_tts_python
```

## Subtitle Alignment Test

The subtitle alignment test is disabled by default in TTS guarder.

```bash
# Default guarder run: subtitle alignment test is skipped
task tts-guarder-test EXTENSION=cartesia_tts

# Explicitly enable subtitle alignment test
task tts-guarder-test EXTENSION=cartesia_tts -- --enable_subtitle_alignment=True
```

`test_subtitle_alignment.py` supports `cartesia_tts`,
`minimax_tts_websocket_duplex`, `elevenlabs_multiple_context_tts_python`,
`bytedance_tts`, `bytedance_tts_duplex`, `minimax_tts_websocket`, and
`soul_tts_python`. It validates two sequential requests against the cumulative
PCM clock. Vendors with a registered hook also compare TEN word timestamps with
untouched provider messages. See
[the timing checks](tests/SUBTITLE_TIMING.md) for the validation rules and their
limits.

See [adding a TTS extension](tests/SUBTITLE_TIMING.md#adding-a-tts-extension)
for extension setup, the vendor object interface, registry entries, and
verification steps.

Only `minimax_tts_websocket_duplex`, `cartesia_tts`,
`elevenlabs_multiple_context_tts_python`, `bytedance_tts`, and
`bytedance_tts_duplex` install a vendor timing hook. A hook applies to the
alignment test's matching connections and restores the client dependency
afterward. Unregistered vendors receive no hook, and other Guarder cases retain
their behavior. `minimax_tts_websocket` and `soul_tts_python` use the
strengthened generic alignment checks without a vendor hook.
