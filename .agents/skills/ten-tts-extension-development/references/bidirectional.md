# Bidirectional and multiplexed streaming adapter

Use independent send and receive loops around a long-lived provider connection. The sender converts incremental TEN text inputs into provider messages. The receiver converts provider audio, alignment, completion, and error messages into queues consumed by TEN output handling.

Maintain explicit mappings for provider context ID, TEN request ID, pending input, active contexts, and terminal state. Never route audio using only a single global current request when the connection can carry multiple contexts. Ignore or quarantine late audio from completed or interrupted contexts.

Mark input as acknowledged before removing it from replay storage. On reconnect, replay only unacknowledged input after connection readiness; do not replay audio already delivered. Implement provider keepalive or idle-timeout handling, bounded transport retries, context close, and shutdown cancellation.

Flush must cancel every active context, invalidate receiver callbacks, clear pending sends, and prevent late audio. A successful provider context completion produces TEN `tts_audio_end()` and `finish_request()` only when that context’s logical input is complete and its audio work is drained; an intermediate per-chunk completion stays internal. A terminal error may release the context earlier according to the common error rules. For flush, emit the interrupted audio end and leave final cleanup to the base class. When alignment is available, validate timestamps and emit `tts_text_result` with the matching request metadata.

Test interleaved contexts, concurrent send/receive, reconnect with pending input, context close, keepalive, flush races, late messages, empty text, and error recovery.
