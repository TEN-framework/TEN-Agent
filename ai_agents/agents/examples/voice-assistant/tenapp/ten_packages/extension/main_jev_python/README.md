# Jev voice-assistant controller

`main_jev_python` is used only by the optional
`voice_assistant_jev_router` graph. It combines Deepgram's final English
utterance, asks the `typesafe_jev_python` extension to choose `fast` or
`deep`, and sends the chat request to `llm_fast` or `llm_deep`.

The two LLM nodes both use DeepSeek Flash. `fast` disables thinking; `deep`
enables it. A `fast` choice needs confidence of at least 0.80. A low-confidence
choice uses thinking, while a Jev error or timeout falls back to no thinking.

The route is sent to the message collector as a normal assistant transcript
before the answer. Reasoning is sent as the existing `reasoning` message type.
Neither the route nor the reasoning is sent to TTS. Route, reasoning, and
answer use separate stream IDs so the unchanged playground does not merge
their chat bubbles.

The shared `main_python` controller is not imported or modified by this
extension. Other graphs continue to use it unchanged.
