# Subtitle timing checks

As of: 2026-10-13

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
word indexes, handles space markers, and converts sentence offsets plus
original word times into request-relative references. Capture and calculation
use separate functions in that vendor module; no separate calculator package
or reference source wrapper is required. The common checker compares those
references with TEN output. Request completion continues to be observed through
public TEN audio/text end events. Nonzero first-word
offsets must be retained. Capture and calculation errors fail the timing check
without changing the extension's wire path.

The dependency binding is restored when the runner exits, including failure
paths. Only the vendors listed in [registry.py](timing_hooks/registry.py) are
registered: a vendor without a registry entry installs no observer, and other
Guarder cases do not inject any hook. This module consolidation preserves the
existing checks and enable/skip behavior. Tests sharing one extension module
must run sequentially; parallel vendor runs require separate processes and
installed app directories.

See [adding a TTS extension](#adding-a-tts-extension) below for setup,
registration, and verification steps.

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
match every acoustic onset. Providers without a registry entry receive the
generic checks only. The registered observers differ per vendor because each one
hooks the client's actual transport entry point: MiniMax Duplex and ElevenLabs
wrap the client module's `websockets` binding through
[ObservedWebSockets](timing_hooks/transport.py), Cartesia wraps
`aiohttp.ClientSession`, and ByteDance wraps the session's response handler.
The ByteDance session hook also reads the provider's frontend word messages
before the session converts them, and counts the audio bytes it delivered.
The ByteDance duplex hook wraps the client's server-response handler, where
sentence boundaries, provider word fields, and audio chunks are still in
provider form.

## Adding a TTS extension

Choose the coverage level before adding support:

| Coverage | What it verifies | Required changes |
| --- | --- | --- |
| Generic checks only | PCM timestamps, subtitle bounds, request metadata, and completion | Supported-extension list and subtitle configuration |
| Generic checks plus a vendor hook | Generic checks and preservation of original provider word times, including first-word offsets | Also add one vendor module and a registry entry |

Unregistered extensions install no vendor observer. Generic bounds checks alone
cannot prove that the first-word offset was converted correctly: shifted words
can still lie within the audio span. `minimax_tts_websocket_duplex`,
`cartesia_tts`, `elevenlabs_multiple_context_tts_python`, and `bytedance_tts`
have a registered hook today; `minimax_tts_websocket` and `soul_tts_python`
receive generic checks only. Other extensions skip this case until they are
added to the supported list and have a subtitle configuration.

### 1. Prepare the extension and configuration

- Ensure the extension loads through the TEN standalone runner and emits
  subtitles with word timestamps.
- Prepare a valid model, voice, and credentials using the extension's own
  documentation. Supply credentials through environment variables.
- Add `property_subtitle_alignment.json` under the extension's `tests/configs/`
  directory, enabling provider word timestamps. Configuration fields depend
  on the provider protocol.
- Add the extension name to `SUPPORTED_TTS_EXTENSIONS` in
  [test_subtitle_alignment.py](test_subtitle_alignment.py).

The case sends two sequential requests with `request_id`, `session_id`, and
`turn_id`. It observes subtitles, audio frames, and `tts_audio_start/end` through
public TEN callbacks, and waits for both the terminal subtitle and audio-end
event. The extension must support these public outputs.

The normal `task tts-guarder-test` installs the target from
`ai_agents/agents/ten_packages/extension/<extension_name>/`. For an extension
from another repository, first prepare its source, configuration, and a runnable
Guarder app, and record the source revision. Registering a hook does not install
the production extension. This Framework checkout does not contain
`minimax_tts_websocket_duplex`; the recorded MiniMax runs used a separately
prepared Engine extension.

### 2. Implement capture and calculation in one vendor module

For raw word-time comparison, add a file under `timing_hooks/`, for example
`acme_tts_duplex.py`. Keep both capture and reference calculation in this file;
no separate calculator package is needed. See
[minimax_duplex.py](timing_hooks/minimax_duplex.py) for the existing structure.

The vendor object implements these methods:

| Method | Called when | Responsibility |
| --- | --- | --- |
| `install(monkeypatch, config)` | Before the TEN tester starts | Inject only the target client's transport dependency using the supplied scoped monkeypatch |
| `begin_request(request_id)` | Before each TEN input | Set the current request identity and reset accumulated audio positions and captured subtitles |
| `reference(request_id)` | After the request's audio and subtitles complete | Return a common `RequestTimingReference` and verify that the capture belongs to this request |

Capture callbacks record only facts needed for conversion: effective audio
settings, original word timestamps, and sentence audio positions. When word
times are relative to a sentence, count all preceding audio packets, including
packets without subtitles. Connection-level audio settings may arrive before
the first request; retain still-effective settings when resetting a request.

Build the reference from the provider's own fields. Reading the already
converted TEN words, or the extension's own sentence bookkeeping, makes the
comparison move with the conversion it verifies and accept a wrong one.
Sentence positions come from the audio bytes the provider delivered, counted
at its own sentence boundaries, and a request's origin is reset before each
request.

`reference()` interprets protocol units, sentence boundaries, duplicate word
markers, and space markers, then returns the structures in
[base.py](timing_hooks/base.py):

| Field | Meaning |
| --- | --- |
| `vendor` | Provider name for diagnostics |
| `sample_rate`, `channels` | Effective audio sample rate and channel count |
| `pcm_bytes` | Total PCM16 bytes for this request |
| `captions` | Tuples of `ReferenceWord`, grouped in subtitle-result order |
| `ReferenceWord.word` | Word text corresponding to the public TEN subtitle |
| `ReferenceWord.start_ms/end_ms` | Times relative to this request's audio origin, using `Fraction` to preserve fractions |
| `error` | Capture or calculation diagnostic, or `None` on success |

The common comparison expects reference PCM16 at the same sample rate and
channel count as TEN output. If the provider returns compressed audio, another
sample format, or another sample rate, define how the reference maps to TEN
output before enabling the hook. Transport byte counts cannot be used directly
as PCM16 byte counts.

For example, a first-word provider offset of `42.667ms` and a TEN first-frame
PTS of `1000ms` produce an expected word PTS of `1042ms`, not `1000ms`.
If the preceding sentence contains 3200 bytes of mono PCM16 at 16kHz, it lasts
100ms. A subsequent sentence's first-word offset of `42.667ms` becomes
`142.667ms` relative to the request, producing `1142ms` on that TEN timeline.
Retain the original offset and accumulate audio duration before rounding.
The second request starts from its own first frame.

### 3. Scope transport observation

- Observe raw provider transport messages and public TEN outputs; do not read
  production extension private state.
- Replace only the target client module's dependency binding, without changing
  shared transport-library methods.
- Resolve the target endpoint using the client's effective configuration
  precedence, including top-level and `params` aliases.
- Preserve wire messages and connection behavior. Report capture errors through
  the reference result without changing the production send/receive path.
- Use the registry's monkeypatch context so success and failure both restore
  the original dependency.

WebSocket vendors can reuse
[ObservedWebSockets](timing_hooks/transport.py). The connection library must
support `create_connection`; matching endpoints receive a dedicated connection
type. The vendor object also supplies `observe_send(payload)` and
`observe_receive(payload)` for its capture callbacks. Choose the injection
point based on the extension's actual connection entry point rather than
copying MiniMax's module binding name.

For other transports, implement equivalent local injection in the vendor file.
Run cases sharing one extension sequentially. Parallel runs use separate
processes and installed app directories.

### 4. Register the vendor object

Add an entry to `HOOK_FACTORIES` in [registry.py](timing_hooks/registry.py):

```python
"acme_tts_duplex": (".acme_tts_duplex", "AcmeTimingHook"),
```

The key must exactly match the extension name passed to Guarder. The registry
imports the selected module on demand, creates a fresh object, installs it,
and passes it directly to the common case. No common-checker change or separate
calculator registration is needed. For generic-only coverage, omit the registry
entry to retain the path without a hook.

### 5. Run and verify

From `ai_agents/`, run the subtitle case and confirm that it executes. A skip
does not establish passing coverage:

```bash
task tts-guarder-test EXTENSION=acme_tts_duplex CONFIG_DIR=tests/configs -- \
  --enable_subtitle_alignment=True -k subtitle_alignment -s -vv
```

Then run the extension's full Guarder suite:

```bash
task tts-guarder-test EXTENSION=acme_tts_duplex CONFIG_DIR=tests/configs -- \
  --enable_subtitle_alignment=True -s -vv
```

A disabled flag, an unsupported extension name, or a missing subtitle
configuration skips the case. Once a hook is registered, missing or invalid raw
reference data must fail the check rather than fall back to generic-only checks.

Verify that:

- Both requests reset their reference identity and accumulated audio positions.
- Nonzero first-word offsets are retained and incorrect offsets are rejected,
  except where a vendor section documents that the extension aligns a
  sentence's first word with its audio start.
- Success and failure restore injected dependencies.
- Unregistered extensions receive no injection.

Construct or observe these scenarios through public TEN and transport boundaries,
without accessing extension private fields. Record Guarder and production
extension revisions, commands, pass/fail/skip counts, and any validation-harness
adaptations. Redact credentials from logs and configuration before sharing them.

### Current limitations

These checks validate timestamp conversion; they do not perform acoustic forced
alignment or prove that provider annotations match actual speech onsets.
For `bytedance_tts_duplex` the provider sends turn-relative times and the
extension aligns each sentence's first word with the start of that sentence's
audio, so about 100ms of provider lead-in silence per sentence is normalized
away and the ByteDance duplex reference mirrors that alignment instead of
rejecting it. The remaining word offsets within a sentence are still compared
against the provider's own fields and independently counted audio bytes.
Review findings for actual buffer-length validation, nonterminal subtitles with
empty `words`, and MiniMax `params.url` matching remain unresolved. These
instructions do not imply that those gaps have been fixed. New vendors should
implement their effective configuration precedence rather than copy MiniMax's
current URL-selection logic.
