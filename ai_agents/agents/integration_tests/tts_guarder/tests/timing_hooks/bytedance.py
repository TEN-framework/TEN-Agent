"""Capture parsed ByteDance timing data at the vendor session boundary."""

from fractions import Fraction
from importlib import import_module
from .base import ReferenceWord, RequestTimingReference

SESSION_MODULE = "ten_packages.extension.bytedance_tts.session"


class ByteDanceTimingHook:
    def __init__(self):
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.pcm_bytes = 0
        self.groups = []
        self.origin = None
        self.error = None

    def install(self, monkeypatch, config):
        module = import_module(SESSION_MODULE)
        original = module.Session.on_response
        hook = self

        def on_response(session, response):
            result = original(session, response)
            try:
                session_request_id = getattr(
                    session, "original_request_id", None
                ) or getattr(session.tts_input, "request_id", None)
                if session_request_id != hook.request_id:
                    return result
                audio, _ = result
                if audio and audio.frame:
                    hook.pcm_bytes += len(audio.frame)
                    if hook.origin is None:
                        hook.origin = audio.timestamp
                if audio and audio.text_result and audio.text_result.words:
                    hook.groups.append(
                        tuple(
                            ReferenceWord(
                                word.word,
                                Fraction(word.start_ms - hook.origin),
                                Fraction(
                                    word.start_ms
                                    + word.duration_ms
                                    - hook.origin
                                ),
                            )
                            for word in audio.text_result.words
                        )
                    )
            except Exception as error:  # noqa: BLE001
                hook.error = "ByteDance capture failed: " + type(error).__name__
            return result

        monkeypatch.setattr(module.Session, "on_response", on_response)
        params = config.get("params") or {}
        self.sample_rate = int(
            params.get("rate") or config.get("rate") or 24000
        )

    def begin_request(self, request_id):
        self.request_id = request_id
        self.pcm_bytes = 0
        self.groups = []
        self.origin = None
        self.error = None

    def reference(self, request_id):
        error = self.error
        if request_id != self.request_id:
            error = "ByteDance capture belongs to another request"
        return RequestTimingReference(
            "ByteDance",
            self.sample_rate,
            self.channels,
            -1,
            tuple(self.groups),
            error,
        )
