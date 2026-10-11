#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the root directory of this source tree.
#
"""Observe MiniMax wire facts and calculate request-relative word times."""

import json
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from threading import RLock

from .base import ReferenceWord, RequestTimingReference
from .transport import ObservedWebSockets

DEFAULT_URL = "wss://api.minimax.cn/ws/v1/t2a_v2_bidi"
CLIENT_MODULE = (
    "ten_packages.extension.minimax_tts_websocket_duplex.minimax_tts"
)


@dataclass(frozen=True)
class _CapturedSubtitle:
    sentence_start_bytes: int
    payload: dict


@dataclass(frozen=True)
class _CapturedTiming:
    audio_setting: dict
    pcm_bytes: int
    subtitles: tuple[_CapturedSubtitle, ...]
    error: str | None = None


class MiniMaxTimingHook:
    """Capture facts and provide references for sequential TEN requests."""

    def __init__(self):
        self.audio_setting = {}
        self.request_id = None
        self.pcm_bytes = 0
        self.sentence_start_bytes = 0
        self.subtitles = []
        self.error = None
        self.lock = RLock()

    def install(self, monkeypatch, config):
        module = import_module(CLIENT_MODULE)
        dependency = ObservedWebSockets(
            module.websockets, config.get("url") or DEFAULT_URL, self
        )
        monkeypatch.setattr(module, "websockets", dependency)

    def begin_request(self, request_id):
        with self.lock:
            self.request_id = request_id
            self.pcm_bytes = 0
            self.sentence_start_bytes = 0
            self.subtitles = []

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
        event = message.get("event")
        if event == "sentence_start":
            self.sentence_start_bytes = self.pcm_bytes
        elif event == "task_continued":
            data = message.get("data") or {}
            self.pcm_bytes += len(data.get("audio") or "") // 2
            subtitle = data.get("subtitle")
            if subtitle and subtitle.get("timestamped_words"):
                self.subtitles.append(
                    _CapturedSubtitle(
                        self.sentence_start_bytes, deepcopy(subtitle)
                    )
                )

    def reference(self, request_id):
        return _build_reference(self._capture(request_id))

    def _capture(self, request_id):
        with self.lock:
            error = self.error
            if request_id != self.request_id:
                error = "MiniMax capture belongs to another request"
            return _CapturedTiming(
                deepcopy(self.audio_setting),
                self.pcm_bytes,
                tuple(deepcopy(self.subtitles)),
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


def _build_reference(capture):
    setting = capture.audio_setting
    sample_rate = setting.get("sample_rate", 0)
    channels = setting.get("channels", setting.get("channel", 1))
    error = capture.error
    captions = []
    try:
        if setting.get("format", "pcm") != "pcm":
            error = "MiniMax timing reference requires PCM audio"
        elif sample_rate > 0 and channels > 0 and not error:
            for subtitle in capture.subtitles:
                sentence_ms = Fraction(
                    subtitle.sentence_start_bytes * 1000,
                    2 * channels * sample_rate,
                )
                captions.append(
                    tuple(
                        ReferenceWord(
                            " " if item["word"] == "[SPACE]" else item["word"],
                            sentence_ms + Fraction(str(item["time_begin"])),
                            sentence_ms + Fraction(str(item["time_end"])),
                        )
                        for item in _merge_words(subtitle.payload)
                    )
                )
    except (
        ArithmeticError,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        error = "MiniMax reference calculation failed: " + type(exc).__name__
    return RequestTimingReference(
        "MiniMax",
        sample_rate,
        channels,
        capture.pcm_bytes,
        tuple(captions),
        error,
    )
