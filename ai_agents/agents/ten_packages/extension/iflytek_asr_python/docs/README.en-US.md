# iFLYTEK ASR Python Extension

This extension connects TEN Framework to the iFLYTEK realtime transcription service over WebSocket and emits standard TEN `ASRResult` messages.

## Features

- Sends Base64-encoded PCM audio with iFLYTEK first, continue, and last frame states
- Supports interim and final transcripts, word timing, speaker metadata, hotwords, and voiceprints
- Reports vendor errors using the TEN ASR error structure
- Retries unexpected disconnects with bounded exponential backoff
- Completes finalize exactly once with terminal-response and timeout handling
- Reports connecting, connected, disconnected, and reconnection status changes
- Provides categorized, sanitized logs, connect-delay metrics, a 10 MB keep buffer, and optional PCM dumps

## Configuration

Starting with version 0.2.0, vendor and connection settings must be nested under the `params` property; the 0.1.0 top-level fields are no longer accepted. `dump` and `dump_path` remain top-level properties. `url` and `biz_id` are required for service integration. The default property file reads them from `IFLYTEK_ASR_URL` and `IFLYTEK_BIZ_ID`. Optional fields include `app_id`, `sample_rate`, `language`, `engine`, `res_id_list`, `hotwords`, `hotword_weight`, and `voiceprints`.

Production controls include `finalize_timeout` (default `5` seconds), `reconnect_delay` (`0.5` seconds), `reconnect_max_delay` (`8` seconds), `reconnect_max_attempts` (`5`), and `buffer_max_bytes` (`10485760`). Set `dump` to `true` and `dump_path` to a directory or `.pcm` file to record successfully sent audio. Dump failures are non-fatal. Audio dumps may contain sensitive data and should be enabled only with appropriate retention and access controls.

Initial connection failures and intermediate reconnect failures are non-fatal and use bounded exponential backoff. Exhausting the configured attempts is fatal. A successful reconnect resets the retry counter.

The input must be mono 16-bit PCM at the configured sample rate. For multiple languages, separate language codes with `|`, for example `zh|en`.

See [TEN ASR Extension Development Guide](https://theten.ai/cn/docs/ten_agent_examples/extension_dev/create_asr_extension), `README.zh-CN.md`, and `PRODUCTION_READINESS.md` for the complete configuration and release checks.
