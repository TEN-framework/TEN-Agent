"""Capture the ByteDance provider's own word times for the timing check.

Only the transport payload is read: the provider's word fields and the
number of audio bytes it delivered. Word positions are accumulated from
those counts, so the reference does not depend on the session's own
conversion of the same words that the check verifies.
"""

import json
from fractions import Fraction
from importlib import import_module

from .base import ReferenceWord, RequestTimingReference

SESSION_MODULE = "ten_packages.extension.bytedance_tts.session"


def _starts_with_english(word: str) -> bool:
    return bool(word) and word[0].isascii() and word[0].isalpha()


def _ends_with_english(word: str) -> bool:
    return bool(word) and word[-1].isascii() and word[-1].isalpha()


class ByteDanceTimingHook:
    """Observe one session's provider messages before they are converted."""

    def __init__(self):
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.pcm_bytes = 0
        self.groups = []
        self.error = None
        self.words = []
        self.offset_ms = 0
        self.unit_ms = 0.0

    def install(self, monkeypatch, config):
        module = import_module(SESSION_MODULE)
        original_response = module.Session.on_response
        original_frontend_msg = module.Session._on_frontend_msg
        hook = self

        def on_response(session, response):
            result = original_response(session, response)
            hook._observe_response(session, result)
            return result

        def _on_frontend_msg(session, msg):
            hook._observe_frontend_msg(session, msg)
            return original_frontend_msg(session, msg)

        monkeypatch.setattr(module.Session, "on_response", on_response)
        monkeypatch.setattr(
            module.Session, "_on_frontend_msg", _on_frontend_msg
        )
        params = config.get("params") or {}
        self.sample_rate = int(
            params.get("rate") or config.get("rate") or 24000
        )

    @staticmethod
    def _session_request_id(session):
        return getattr(session, "original_request_id", None) or getattr(
            session.tts_input, "request_id", None
        )

    def _observe_frontend_msg(self, session, msg):
        try:
            if self._session_request_id(session) != self.request_id:
                return
            message = json.loads(msg)
            frontend = message.get("frontend")
            if not frontend:
                return
            for word in json.loads(frontend).get("words") or []:
                self.words.append(word)
        except (
            AttributeError,
            TypeError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self.error = "ByteDance capture failed: " + type(error).__name__

    def _observe_response(self, session, result):
        try:
            if self._session_request_id(session) != self.request_id:
                return
            audio, _ = result
            if audio is None:
                return
            if audio.frame:
                self.pcm_bytes += len(audio.frame)
                self.unit_ms += len(audio.frame) / self._bytes_per_ms()
            if audio.text_result is not None:
                self._close_unit()
        except (AttributeError, TypeError, ValueError) as error:
            self.error = "ByteDance capture failed: " + type(error).__name__

    def _bytes_per_ms(self) -> float:
        return self.sample_rate * self.channels * 2 / 1000

    def _close_unit(self) -> None:
        """Build one subtitle reference from the provider's own word times."""
        if self.sample_rate <= 0:
            self.error = "ByteDance audio format was not observed"
            return
        if self.words:
            words = []
            previous_english = False
            for index, item in enumerate(self.words):
                text = str(item.get("word", ""))
                if (
                    index > 0
                    and previous_english
                    and _starts_with_english(text)
                ):
                    # The session separates two English words with a space.
                    text = " " + text
                start_ms = self.offset_ms + int(item.get("start_time", 0))
                end_ms = self.offset_ms + int(item.get("end_time", 0))
                words.append(
                    ReferenceWord(text, Fraction(start_ms), Fraction(end_ms))
                )
                previous_english = _ends_with_english(text)
            self.groups.append(tuple(words))
        self.offset_ms += int(self.unit_ms)
        self.unit_ms = 0.0
        self.words = []

    def begin_request(self, request_id):
        self.request_id = request_id
        self.pcm_bytes = 0
        self.groups = []
        self.words = []
        self.offset_ms = 0
        self.unit_ms = 0.0
        self.error = None

    def reference(self, request_id):
        error = self.error
        if request_id != self.request_id:
            error = "ByteDance capture belongs to another request"
        if self.pcm_bytes == 0 or not self.groups:
            error = error or "ByteDance reference contains no provider words"
        return RequestTimingReference(
            "ByteDance",
            self.sample_rate,
            self.channels,
            self.pcm_bytes,
            tuple(self.groups),
            error,
        )
