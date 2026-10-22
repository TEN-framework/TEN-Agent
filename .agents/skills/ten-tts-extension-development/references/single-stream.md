# Single-request streaming adapter

Use a provider client with one input queue and one active vendor request. The sender takes the next TEN text input only after the previous request has emitted its provider terminal event. Map `text_input_end` to the provider’s end-of-input marker. A provider END for an earlier chunk is intermediate and must leave the TEN request open. Emit `tts_audio_end()` and call `finish_request()` only when the final text is sent and provider work for that request is drained.

The receiver should normalize provider audio, sentence/task completion, and provider errors into extension callbacks. Track the active request ID, first-audio timestamp, emitted byte count, and a cancellation generation. A callback is valid only if its generation and request ID are still current.

On cancellation, disable callbacks first, close or interrupt the stream, clear queued work, and unblock any queue wait. Emit an interrupted audio end for an active request and leave final cleanup to the base class. On reconnect, replay only input that was not acknowledged by the provider; never replay audio that was already emitted downstream. Use bounded backoff and a clear fatal retry ceiling.

Test serial request ordering, terminal-event handling, flush while receiving, connection loss, retry/replay, provider error followed by a buffered request, and duration accounting.
