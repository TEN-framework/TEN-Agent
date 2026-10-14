"""Capture the duplex provider's own word times at the transport boundary.

Only server messages are read: sentence boundaries, the provider's word
fields, and the number of audio bytes it delivered. Sentence positions are
accumulated from those counts instead of the extension's own accounting,
so the reference does not depend on the conversion it verifies.

The provider sends turn-relative times, and the extension aligns the first
word of each sentence with the start of that sentence's audio. The
reference mirrors that alignment, so a lost or shifted first-word offset is
not detected for this vendor; see SUBTITLE_TIMING.md.
"""

import json
from fractions import Fraction
from importlib import import_module

from .base import ReferenceWord, RequestTimingReference

CLIENT_MODULE = "ten_packages.extension.bytedance_tts_duplex.bytedance_tts"


class ByteDanceDuplexTimingHook:
    """Observe one request's provider messages before they are converted."""

    def __init__(self):
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.pcm_bytes = 0
        self.groups = []
        self.error = None
        self.active = False
        self.events = {}
        self.base_ms = 0
        self.sentence_start_ms = 0
        self.accumulated_ms = 0

    def install(self, monkeypatch, config):
        module = import_module(CLIENT_MODULE)
        original = module.BytedanceV3Synthesizer._handle_server_response
        hook = self

        async def _handle_server_response(synthesizer, message):
            hook._capture(message)
            return await original(synthesizer, message)

        monkeypatch.setattr(
            module.BytedanceV3Synthesizer,
            "_handle_server_response",
            _handle_server_response,
        )
        params = config.get("params") or {}
        audio_params = params.get("audio_params") or {}
        self.sample_rate = int(
            audio_params.get("sample_rate")
            or config.get("sample_rate")
            or 24000
        )
        self.channels = 1
        self.events = {
            "chunk": module.EVENT_TTSResponse,
            "sentence_start": module.EVENT_TTSSentenceStart,
            "sentence_end": module.EVENT_TTSSentenceEnd,
        }

    def _capture(self, message):
        try:
            if not self.active or self.sample_rate <= 0:
                return
            event = getattr(message, "event", None)
            if event == self.events["chunk"]:
                payload = getattr(message, "payload", None) or b""
                self.pcm_bytes += len(payload)
                # The extension accumulates one truncated duration per
                # audio chunk, so the reference counts the same way.
                self.accumulated_ms += self._bytes_to_ms(len(payload))
            elif event == self.events["sentence_start"]:
                self.sentence_start_ms = self.base_ms
                self.accumulated_ms = 0
            elif event == self.events["sentence_end"]:
                self.base_ms = self.sentence_start_ms + self.accumulated_ms
                self._capture_words(getattr(message, "payload_json", None))
        except (
            AttributeError,
            TypeError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self.error = (
                "ByteDance duplex capture failed: " + type(error).__name__
            )

    def _bytes_to_ms(self, byte_length: int) -> int:
        bytes_per_second = self.sample_rate * self.channels * 2
        return int(byte_length / bytes_per_second * 1000)

    def _capture_words(self, payload_json):
        if not payload_json:
            return
        data = (
            json.loads(payload_json)
            if isinstance(payload_json, str)
            else payload_json
        )
        raw_words = data.get("words") or []
        if not raw_words:
            return
        # The provider sends turn-relative times and the extension aligns the
        # first word of a sentence with the start of that sentence's audio.
        first_start_ms = int(float(raw_words[0].get("startTime", 0.0)) * 1000)
        words = []
        for item in raw_words:
            start_sec = float(item.get("startTime", 0.0))
            end_sec = float(item.get("endTime", 0.0))
            start_ms = (
                self.sentence_start_ms + int(start_sec * 1000) - first_start_ms
            )
            duration_ms = int((end_sec - start_sec) * 1000)
            words.append(
                ReferenceWord(
                    str(item.get("word", "")),
                    Fraction(start_ms),
                    Fraction(start_ms + duration_ms),
                )
            )
        self.groups.append(tuple(words))

    def begin_request(self, request_id):
        self.request_id = request_id
        self.pcm_bytes = 0
        self.groups = []
        self.error = None
        self.base_ms = 0
        self.sentence_start_ms = 0
        self.accumulated_ms = 0
        self.active = True

    def reference(self, request_id):
        self.active = False
        error = self.error
        if request_id != self.request_id:
            error = "ByteDance duplex capture belongs to another request"
        if self.pcm_bytes == 0 or not self.groups:
            error = error or "ByteDance duplex reference has no provider data"
        return RequestTimingReference(
            "ByteDance",
            self.sample_rate,
            self.channels,
            self.pcm_bytes,
            tuple(self.groups),
            error,
        )
