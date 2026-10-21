"""Capture the duplex provider's own word times at the transport boundary.

Only server messages are read: sentence boundaries, the provider's word
fields, and the number of audio bytes it delivered. The provider's word times
are cumulative within the request, so the reference uses them directly rather
than duplicating the extension's sentence bookkeeping.
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
            audio_params.get("sample_rate") or config.get("sample_rate") or 24000
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
            elif event == self.events["sentence_end"]:
                self._capture_words(getattr(message, "payload_json", None))
        except (
            AttributeError,
            TypeError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self.error = "ByteDance duplex capture failed: " + type(error).__name__

    def _capture_words(self, payload_json):
        if not payload_json:
            return
        data = (
            json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        )
        raw_words = data.get("words") or []
        if not raw_words:
            return
        words = []
        for item in raw_words:
            start_sec = float(item.get("startTime", 0.0))
            end_sec = float(item.get("endTime", 0.0))
            start_ms = int(start_sec * 1000)
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
