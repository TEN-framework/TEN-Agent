# Changelog

All notable changes to the iFLYTEK ASR Python Extension are documented here.

## 0.2.1 - 2026-09-02

- Align the packaged extension with the reviewed conversational agent
  integration, including the reconnect-limit error naming used by vendor
  error classification.
- Preserve `ReconnectLimitReached` as a legacy alias for 0.2.x callers.
- Modernize the protocol `Mapping` import to use `collections.abc`.

## 0.2.0 - 2026-08-20

- Standardize vendor and connection settings under `property.params` so TEN
  graphs can configure iFLYTEK consistently with other ASR extensions.
- Require all vendor and connection settings under `property.params`; only
  `dump` and `dump_path` remain extension-level properties.

## 0.1.0 - 2026-08-04

- Implement iFLYTEK WebSocket request and response mapping.
- Add interim and final results, word timing, speaker metadata, hotwords,
  resource IDs, and voiceprints.
- Add bounded exponential reconnection, keep buffering, finalize completion
  with timeout protection, categorized errors, connection status, metrics,
  and optional PCM dumps.
- Harden protocol validation, error redaction, dependency constraints, and
  connection lifecycle concurrency.
- Verify the extension with offline tests and the TEN ASR Guarder against a
  real iFLYTEK service.
