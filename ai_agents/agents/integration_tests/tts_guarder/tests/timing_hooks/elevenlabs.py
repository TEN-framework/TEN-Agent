"""Capture ElevenLabs alignment messages for the common timing checker.

The extension selects one of two protocols from the model: the TTS modules
report request-relative character times, while the text-to-dialogue (TTD)
client restarts alignment at zero in every chunk. Each chunk is anchored where
its audio starts, so a provider whose spans do not exactly match the audio
cannot accumulate drift. The hook follows the same protocol and reads only the
provider's own alignment payload.
"""

import base64
import json
from fractions import Fraction
from importlib import import_module
from threading import RLock

from .base import ReferenceWord, RequestTimingReference
from .transport import ObservedWebSockets

TTS_CLIENT_MODULE = (
    "ten_packages.extension.elevenlabs_multiple_context_tts_python.elevenlabs_tts"
)
TTD_CLIENT_MODULE = (
    "ten_packages.extension.elevenlabs_multiple_context_tts_python.elevenlabs_ttd"
)
CONFIG_MODULE = "ten_packages.extension.elevenlabs_multiple_context_tts_python.config"


class ElevenLabsTimingHook:
    def __init__(self):
        self.lock = RLock()
        self.request_id = None
        self.sample_rate = 0
        self.channels = 1
        self.pcm_bytes = 0
        self.groups = []
        self.origin = None
        self.ttd = False
        self.error = None

    def install(self, monkeypatch, config):
        url = config.get("url") or "wss://api.elevenlabs.io"
        output = config.get("output_format") or {}
        params = config.get("params") or {}
        model_id = str(params.get("model_id") or config.get("model_id") or "")
        config_module = import_module(CONFIG_MODULE)
        self.ttd = config_module.uses_ttd_protocol(model_id)
        module = import_module(
            TTD_CLIENT_MODULE if self.ttd else TTS_CLIENT_MODULE
        )
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
            # Alignment times are relative to each generation request, so the
            # origin must not carry over from the previous request.
            self.origin = None
            self.error = None

    def observe_send(self, payload):
        return None

    def observe_receive(self, payload):
        try:
            data = json.loads(payload)
            context_id = data.get(
                "context_id" if self.ttd else "contextId",
                data.get("contextId"),
            )
            if context_id != self.request_id:
                return
            audio = data.get("audio")
            # The chunk's audio starts where the previous messages ended.
            pcm_before = self.pcm_bytes
            if audio:
                self.pcm_bytes += len(base64.b64decode(audio))
            alignment = data.get("alignment")
            if not alignment:
                return
            chars = alignment.get("chars", alignment.get("characters", []))
            starts = alignment.get(
                "charStartTimesMs", alignment.get("char_start_times_ms", [])
            )
            durations = alignment.get(
                "charDurationsMs", alignment.get("char_durations_ms", [])
            )
            if not starts or len(starts) != len(chars):
                return
            chars_words = [
                (char, start, duration)
                for char, start, duration in zip(chars, starts, durations)
                if char not in "\n\r"
            ]
            if not chars_words:
                return
            offset = self._segment_offset(starts, pcm_before)
            words = []
            current = []
            for char, start, duration in chars_words:
                if current and (
                    char.isspace()
                    or current[-1][0].isspace()
                    or not char.isalnum()
                    or not current[-1][0].isalnum()
                ):
                    words.append(_reference_word(current, offset))
                    current = []
                current.append((char, start, duration))
            if current:
                words.append(_reference_word(current, offset))
            self.groups.append(tuple(words))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self.error = "ElevenLabs capture failed: " + type(error).__name__

    def _segment_offset(self, starts, pcm_before):
        if self.ttd:
            # TTD character times are zero-based within each chunk, whose
            # audio starts after pcm_before bytes.
            bytes_per_ms = self.sample_rate * self.channels * 2 / 1000
            if bytes_per_ms <= 0:
                return 0.0
            return -(pcm_before / bytes_per_ms)
        if self.origin is None:
            self.origin = starts[0]
        return self.origin

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
