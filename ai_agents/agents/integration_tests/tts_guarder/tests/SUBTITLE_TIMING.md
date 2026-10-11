# Subtitle timing checks

As of: 2026-10-11

Run with `--enable_subtitle_alignment=True`. The test observes two sequential
requests through public TEN messages and audio frames. Each request has its own
PCM origin, metadata, and terminal subtitle result.

The generic checks verify:

- Every audio timestamp follows the first frame plus cumulative PCM samples,
  within one millisecond. Comparing only adjacent rounded frame durations can
  miss cumulative drift.
- Subtitle words and positive result ranges stay within the actual PCM sample
  span. A word may start after leading silence; it need not equal the first
  audio timestamp. Empty terminal markers do not represent spoken text and are
  excluded from timing-range checks.
- Request identity, metadata, sequence order, and terminal results remain valid.

For `minimax_tts_websocket_duplex`, the registry creates a fresh timing hook
only within this test. It temporarily replaces the client module's
`websockets` dependency binding with a proxy. Matching endpoint connections
receive a dedicated connection type through the public `create_connection`
parameter; the original connect object retains its await, context-manager,
and reconnect semantics. The shared WebSocket library and its global
`ClientConnection.send/recv` methods are not modified.

The hook records only the actual `task_start` audio setting, original subtitle
payloads, and cumulative audio byte positions at sentence boundaries. Audio
chunks are counted from their hex length; their content is not retained or
decoded. The public TEN test input resets capture for each sequential request.
The capture callbacks do not track connection ownership, task submission,
flush ACKs, or reconnection lifecycle, and do not calculate word times.

The same vendor object implements `reference(request_id)` in
`timing_hooks/minimax_duplex.py`. After capture, this method merges duplicate
word indexes, handles space markers, and converts sentence offsets plus original
word times into request-relative references. Capture and calculation use separate
functions in that vendor module; no separate calculator package or reference
source wrapper is required. The common checker compares those references with
TEN output. Request completion continues
to be observed through public TEN audio/text end events. Nonzero first-word
offsets must be retained. Capture and calculation errors fail the timing check
without changing the extension's wire path.

The dependency binding is restored when the runner exits, including failure
paths. Only MiniMax Duplex is registered. Other vendors do not import or
install its hook, and other Guarder cases do not inject any hook. This module
consolidation preserves the existing checks and enable/skip behavior. Tests
sharing one extension module must run sequentially; parallel vendor runs require separate
processes and installed app directories.

To support another vendor, add one module implementing `install`,
`begin_request`, and `reference`, then register its class in `HOOK_FACTORIES`.
Its reference method returns the common `RequestTimingReference`; protocol
capture and interpretation stay together in that vendor module. The alignment
test also needs the vendor in its supported list and a prepared subtitle config.

| Observation point | Information read |
| --- | --- |
| TEN tester `on_data` | Public TTS results, audio start/end, request metadata |
| TEN tester `on_audio_frame` | Public timestamps, samples, format, metadata |
| Public WebSocket `send`/`recv` | Untouched provider format, PCM, word times, boundaries |
| TEN tester `run` result | Success or the externally returned rejection diagnostic |

No observation uses production extension private members or methods. The
Guarder naturally runs its own validators to judge received public messages.
The hook is test-process dependency injection at a transport boundary, rather
than a strict test using only TEN input/output ports.

These checks protect timestamp conversion and the PCM timeline. They do not
perform phonetic forced alignment or prove that a provider's word annotations
match every acoustic onset. Other supported providers receive the generic
checks; the raw protocol observer currently applies only to MiniMax Duplex.
