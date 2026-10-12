---
name: ten-tts-extension-development
description: Build production-quality TEN Framework TTS extensions from a third-party HTTP API, SDK, or streaming protocol. Use when implementing or completing a TTS extension and the provider contract must be translated into TEN request, audio, error, flush, metrics, and reconnect behavior. Do not use for TTS code review only, non-TTS extensions, or documentation-only work.
---

# Build a TEN TTS extension from a provider contract

Use this skill when the input is a vendor API specification, SDK guide, WebSocket message schema, or a short description of how text and audio flow. Extract the provider’s actual lifecycle and implement an adapter that preserves the TEN TTS contract.

The requested deliverable is code, not a design essay. Generate only the extension package and its required artifacts. The required package contract is:

```text
<extension-name>/
├── addon.py
├── extension.py
├── config.py
├── <provider>_tts.py          # provider client/synthesizer
├── manifest.json
├── property.json
├── requirements.txt
└── tests/
    ├── bin/start
    ├── conftest.py
    ├── configs/
    └── test_*.py
```

`config.py` may be small but is required for a non-trivial provider. Generate only this extension package and its tests; do not modify graphs, examples, framework base classes, or unrelated files unless the user explicitly asks for that.

## Choose the transport model

Classify the provider by behavior, not by whether its documentation says “streaming”:

- **HTTP**: one request returns a finite response, optionally delivered in HTTP chunks. Requests are independent.
- **Single-request streaming**: one request is sent, audio is streamed back, and the next request must wait for the provider’s terminal event. A queue serializes requests.
- **Bidirectional streaming**: text can be sent continuously while audio is received, and one connection may carry several logical contexts or request IDs. Sending, receiving, and request completion are independent flows.

If an SDK hides the transport, inspect its methods and callbacks: determine whether it permits concurrent sends, how completion is signaled, whether callbacks contain a request/context ID, and how cancellation works.

Read the appropriate reference only when needed:

- [HTTP adapter](references/http.md)
- [Single-request stream adapter](references/single-stream.md)
- [Bidirectional stream adapter](references/bidirectional.md)
- [TEN contract and acceptance criteria](references/common.md)

## Implement the adapter boundary

Keep provider-specific code in a client/synthesizer layer. It should own authentication, request encoding, response parsing, provider terminal events, connection setup, cancellation, retry, and provider error normalization. The TEN extension should own request IDs, metadata, lifecycle events, PCM output, duration accounting, metrics, and flush coordination.

Use `AsyncTTS2HttpExtension` for HTTP. For WebSocket and SDK transports, use `AsyncTTS2BaseExtension` and implement `request_tts`, `vendor`, `synthesize_audio_sample_rate`, and a fast `cancel_tts` when provider work must be interrupted. Reuse base helpers for queueing, framing, metrics, and standardized errors.

For streaming transports, establish and start the provider connection during extension startup. The connection must reach a ready state before the first text input; input handling may wait for readiness but must not create the connection lazily. An abnormal disconnect must report state/error, discard invalid in-flight provider state as appropriate, and reconnect with bounded backoff.

## Preserve these invariants

Every implementation must satisfy [references/common.md](references/common.md). In particular:

- Emit `tts_audio_start` before the first PCM frame and exactly one `tts_audio_end` after the final frame.
- Keep `request_id` and metadata attached across queues and asynchronous callbacks.
- Calculate total audio duration from emitted PCM bytes and the actual format.
- On flush, stop producers, clear pending input, cancel active provider work, suppress late audio, and send `tts_flush_end` only after cleanup.
- Empty text completes quickly with no audio and no stuck request state.
- Classify authentication, provider, transport, cancellation, and configuration errors intentionally.
- Redact keys and authorization values from logs, errors, metadata, and test output.
- Record the TTFB start timestamp immediately before the provider send/SDK send call for the first text of a request ID. Do not record it when putting text into an internal queue, and do not include connection setup time. TTFB ends when the first audio frame for that request is received.
- Keep a PCM dump per request ID. Create the writer when a request ID first appears, write exactly the audio belonging to that ID, flush it before audio end, and close/remove stale writers on completion, interruption, error, and shutdown.
- After TEN flush, call provider cancellation, discard queued unsent text and unread/late audio, invalidate old callbacks, and establish a fresh ready connection before accepting new provider work.

## Build and verify

Derive configuration fields from the provider contract. Validate required values and ranges, normalize aliases, choose safe defaults, and make logging output redacted. Preserve provider response IDs and error codes as vendor metadata where useful.

Trace normal completion, incremental input, empty input, provider error, cancellation, connection loss, reconnect, and shutdown before writing code. For each asynchronous path, identify who owns the request state and who is allowed to emit its terminal event.

Add focused tests for basic audio and event order, empty and malformed text, flush races, invalid credentials, metrics/TTFB, duration, state transitions, dump output, and request isolation. Add transport-specific tests for serialized requests or interleaved contexts and reconnect replay. Prefer a deterministic mock provider over live credentials.

After generating code, run the self-check in [references/common.md](references/common.md) before running commands. Treat any failed check as an implementation defect to fix.

Before reporting completion, run formatting and linting for the generated extension, its standalone tests, and the TTS guarder. Fix failures in generated code rather than weakening checks. The extension is incomplete until all applicable checks pass or a concrete environment limitation is reported.

The developer must configure the provider’s real credentials in the environment and run the complete TTS guarder against the generated extension. Mock-only tests are useful for deterministic protocol cases, but they do not replace the guarder or prove completion.

When no real provider has been selected yet, use the provider-free validation stage described in [references/common.md](references/common.md). This stage validates generated structure and adapter behavior with a deterministic protocol mock, but the result must be reported as “implementation validated with mock; real-provider guarder pending.”
