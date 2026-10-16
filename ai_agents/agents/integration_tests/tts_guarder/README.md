# TTS Guarder Test Guide

As of: 2026-10-11

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

`test_subtitle_alignment.py` supports `cartesia_tts`, `cosy_tts_python` and
`minimax_tts_websocket_duplex`. It validates two sequential requests against
the cumulative PCM clock. MiniMax also compares TEN word timestamps with
untouched provider messages. See [the timing checks](tests/SUBTITLE_TIMING.md)
for the validation rules and their limits.

See [adding a TTS extension](tests/SUBTITLE_TIMING.md#adding-a-tts-extension)
for extension setup, the vendor object interface, registry entries, and
verification steps.

Only `minimax_tts_websocket_duplex` installs a vendor timing hook. The hook
applies to the alignment test's matching connections and restores the client
dependency afterward. Unregistered vendors receive no hook, and other Guarder
cases retain their behavior. Cartesia uses the strengthened generic alignment
checks without a vendor hook.
