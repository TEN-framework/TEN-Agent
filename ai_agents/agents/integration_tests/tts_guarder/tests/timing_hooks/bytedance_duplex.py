"""Capture ByteDance duplex provider word times at the conversion boundary."""

from fractions import Fraction
from importlib import import_module

from .base import ReferenceWord, RequestTimingReference

EXTENSION_MODULE = "ten_packages.extension.bytedance_tts_duplex.extension"


class ByteDanceDuplexTimingHook:
    def __init__(self):
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.origin = None
        self.groups = []
        self.error = None

    def install(self, monkeypatch, config):
        module = import_module(EXTENSION_MODULE)
        original = module.BytedanceTTSDuplexExtension._handle_transcription
        hook = self

        async def _handle_transcription(
            extension, transcription_data, is_final
        ):
            if not is_final:
                hook._capture(extension, transcription_data)
            return await original(extension, transcription_data, is_final)

        monkeypatch.setattr(
            module.BytedanceTTSDuplexExtension,
            "_handle_transcription",
            _handle_transcription,
        )
        params = config.get("params") or {}
        audio_params = params.get("audio_params") or {}
        self.sample_rate = int(
            audio_params.get("sample_rate")
            or config.get("sample_rate")
            or 24000
        )
        self.channels = 1

    def _capture(self, extension, transcription_data):
        try:
            if (
                getattr(extension, "current_request_id", None)
                != self.request_id
            ):
                return
            if not isinstance(transcription_data, dict):
                return
            raw_words = transcription_data.get("words") or []
            if not raw_words:
                return
            sentence_start = int(extension.current_sentence_start_ms)
            if self.origin is None:
                self.origin = sentence_start
            base = sentence_start - self.origin
            first_start_ms = int(
                float(raw_words[0].get("startTime", 0.0)) * 1000
            )
            words = []
            for item in raw_words:
                start_sec = float(item.get("startTime", 0.0))
                end_sec = float(item.get("endTime", 0.0))
                start_ms = base + int(start_sec * 1000) - first_start_ms
                duration_ms = int((end_sec - start_sec) * 1000)
                words.append(
                    ReferenceWord(
                        str(item.get("word", "")),
                        Fraction(start_ms),
                        Fraction(start_ms + duration_ms),
                    )
                )
            self.groups.append(tuple(words))
        except (AttributeError, TypeError, ValueError) as error:
            self.error = (
                "ByteDance duplex capture failed: " + type(error).__name__
            )

    def begin_request(self, request_id):
        self.request_id = request_id
        self.origin = None
        self.groups = []
        self.error = None

    def reference(self, request_id):
        error = self.error
        if request_id != self.request_id:
            error = "ByteDance duplex capture belongs to another request"
        return RequestTimingReference(
            "ByteDance",
            self.sample_rate,
            self.channels,
            -1,
            tuple(self.groups),
            error,
        )
