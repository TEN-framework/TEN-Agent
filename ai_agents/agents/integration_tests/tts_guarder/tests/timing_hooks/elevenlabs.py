"""Capture ElevenLabs alignment messages for the common timing checker."""

import base64
import json
from fractions import Fraction
from importlib import import_module
from threading import RLock

from .base import ReferenceWord, RequestTimingReference
from .transport import ObservedWebSockets

CLIENT_MODULE = "ten_packages.extension.elevenlabs_multiple_context_tts_python.elevenlabs_tts"


class ElevenLabsTimingHook:
    def __init__(self):
        self.lock = RLock()
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.pcm_bytes = 0
        self.groups = []
        self.origin = None
        self.error = None

    def install(self, monkeypatch, config):
        module = import_module(CLIENT_MODULE)
        url = config.get("url") or "wss://api.elevenlabs.io"
        output = config.get("output_format") or {}
        params = config.get("params") or {}
        self.sample_rate = int(
            output.get(
                "sample_rate",
                params.get("sample_rate", config.get("sample_rate", 0)),
            )
        )
        self.channels = int(output.get("channels", 1))
        monkeypatch.setattr(
            module,
            "websockets",
            ObservedWebSockets(module.websockets, url, self, match_path=False),
        )

    def begin_request(self, request_id):
        with self.lock:
            self.request_id = request_id
            self.pcm_bytes = 0
            self.groups = []
            self.error = None

    def observe_send(self, payload):
        return None

    def observe_receive(self, payload):
        try:
            data = json.loads(payload)
            if data.get("contextId") != self.request_id:
                return
            audio = data.get("audio")
            if audio:
                self.pcm_bytes += len(base64.b64decode(audio))
            alignment = data.get("alignment")
            if alignment and alignment.get("chars"):
                chars = alignment["chars"]
                starts = alignment.get("charStartTimesMs", [])
                durations = alignment.get("charDurationsMs", [])
                while chars and chars[-1].isspace():
                    chars = chars[:-1]
                    starts = starts[:-1]
                    durations = durations[:-1]
                while chars and chars[-1].isspace():
                    chars = chars[:-1]
                    starts = starts[:-1]
                    durations = durations[:-1]
                if not starts or len(starts) != len(chars):
                    return
                if self.origin is None:
                    self.origin = starts[0]
                origin = self.origin
                chars_words = []
                for char, start, duration in zip(chars, starts, durations):
                    if char in "\n\r":
                        continue
                    chars_words.append((char, start, duration))
                words = []
                current = []
                for char, start, duration in chars_words:
                    if current and (
                        char.isspace()
                        or current[-1][0].isspace()
                        or not char.isalnum()
                        or not current[-1][0].isalnum()
                    ):
                        words.append(_reference_word(current, origin))
                        current = []
                    current.append((char, start, duration))
                if current:
                    words.append(_reference_word(current, origin))
                self.groups.append(tuple(words))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self.error = "ElevenLabs capture failed: " + type(error).__name__

    def reference(self, request_id):
        with self.lock:
            error = self.error
            if request_id != self.request_id:
                error = "ElevenLabs capture belongs to another request"
            return RequestTimingReference(
                "ElevenLabs",
                self.sample_rate,
                self.channels,
                -1,
                tuple(self.groups),
                error,
            )


def _reference_word(chars, origin):
    text = "".join(item[0] for item in chars)
    start = chars[0][1] - origin
    end = chars[-1][1] - origin + chars[-1][2]
    return ReferenceWord(text, Fraction(start), Fraction(end))
