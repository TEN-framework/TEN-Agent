#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Observe MiniMax wire facts and calculate request-relative word times."""

import json
from copy import deepcopy
from fractions import Fraction
from importlib import import_module
from threading import RLock

from .base import ReferenceWord, RequestTimingReference
from .transport import ObservedWebSockets

DEFAULT_URL = "wss://api.minimaxi.com/ws/v1/t2a_v2"
CLIENT_MODULE = "ten_packages.extension.minimax_tts_websocket.minimax_tts"


class MiniMaxTimingHook:
    """Capture provider audio bytes and subtitle timestamps for one request."""

    def __init__(self):
        self.audio_setting = {}
        self.request_id = None
        self.pcm_bytes = 0
        self.subtitles = []
        self.error = None
        self.lock = RLock()

    def install(self, monkeypatch, config):
        module = import_module(CLIENT_MODULE)
        params = config.get("params") or {}
        url = config.get("url") or params.get("url") or DEFAULT_URL
        dependency = ObservedWebSockets(module.websockets, url, self)
        monkeypatch.setattr(module, "websockets", dependency)

    def begin_request(self, request_id):
        with self.lock:
            self.request_id = request_id
            self.pcm_bytes = 0
            self.subtitles = []
            self.error = None

    def observe_send(self, payload):
        self._observe(payload, outgoing=True)

    def observe_receive(self, payload):
        self._observe(payload, outgoing=False)

    def _observe(self, payload, outgoing):
        with self.lock:
            try:
                message = json.loads(payload)
                if outgoing:
                    if message.get("event") == "task_start":
                        self.audio_setting = deepcopy(
                            message.get("audio_setting", {})
                        )
                elif self.request_id is not None:
                    self._capture_response(message)
            # Capture failures must not change the production wire path.
            except Exception as error:  # noqa: BLE001
                self.error = "MiniMax capture failed: " + type(error).__name__

    def _capture_response(self, message):
        data = message.get("data") or {}
        audio = data.get("audio")
        if audio:
            # MiniMax sends audio as hexadecimal PCM16.
            self.pcm_bytes += len(audio) // 2
        subtitle = data.get("subtitle")
        if subtitle and subtitle.get("timestamped_words"):
            self.subtitles.append(deepcopy(subtitle))

    def reference(self, request_id):
        with self.lock:
            error = self.error
            if request_id != self.request_id:
                error = "MiniMax capture belongs to another request"
            setting = deepcopy(self.audio_setting)
            pcm_bytes = self.pcm_bytes
            subtitles = tuple(deepcopy(self.subtitles))

        sample_rate = setting.get("sample_rate", 0)
        channels = setting.get("channels", setting.get("channel", 1))
        captions = []
        try:
            if setting.get("format", "pcm") != "pcm":
                error = "MiniMax timing reference requires PCM audio"
            elif sample_rate <= 0 or channels <= 0:
                error = "MiniMax audio format was not observed"
            elif not error:
                for subtitle in subtitles:
                    captions.append(
                        tuple(
                            ReferenceWord(
                                " " if item["word"] == "[SPACE]" else item["word"],
                                Fraction(str(item["time_begin"])),
                                Fraction(str(item["time_end"])),
                            )
                            for item in _merge_words(subtitle)
                        )
                    )
        except (
            ArithmeticError,
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            error = "MiniMax reference calculation failed: " + type(
                exc
            ).__name__
        return RequestTimingReference(
            "MiniMax",
            sample_rate,
            channels,
            pcm_bytes,
            tuple(captions),
            error,
        )


def _merge_words(subtitle):
    words = []
    for item in subtitle["timestamped_words"]:
        if (
            words
            and item.get("word_begin") is not None
            and item.get("word_end") is not None
            and (item["word_begin"], item["word_end"])
            == (words[-1].get("word_begin"), words[-1].get("word_end"))
        ):
            words[-1]["time_end"] = item["time_end"]
        else:
            words.append(dict(item))
    return words
