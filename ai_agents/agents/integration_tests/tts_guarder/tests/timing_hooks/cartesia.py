#
# This file is part of TEN Framework.
# Licensed under the Apache License, Version 2.0.
#
"""Capture Cartesia's public WebSocket timing data for subtitle checks."""

import base64
import json
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from threading import RLock

from .base import ReferenceWord, RequestTimingReference

CLIENT_MODULE = "ten_packages.extension.cartesia_tts.cartesia_tts"


@dataclass(frozen=True)
class _Capture:
    sample_rate: int
    channels: int
    pcm_bytes: int
    words: tuple[tuple[ReferenceWord, ...], ...]
    error: str | None = None


class CartesiaTimingHook:
    """Observe only the selected Cartesia client's WebSocket connection."""

    def __init__(self):
        self._lock = RLock()
        self._request_id = None
        self._sample_rate = 0
        self._channels = 1
        self._pcm_bytes = 0
        self._words = []
        self._error = None

    def install(self, monkeypatch, config):
        module = import_module(CLIENT_MODULE)
        original = module.aiohttp.ClientSession
        hook = self

        class SessionProxy:
            def __init__(self, *args, **kwargs):
                self._session = original(*args, **kwargs)

            async def ws_connect(self, url, *args, **kwargs):
                ws = await self._session.ws_connect(url, *args, **kwargs)
                return _WebSocketProxy(ws, hook)

            def __getattr__(self, name):
                return getattr(self._session, name)

        monkeypatch.setattr(module.aiohttp, "ClientSession", SessionProxy)

    def begin_request(self, request_id):
        with self._lock:
            self._request_id = request_id
            self._pcm_bytes = 0
            self._words = []
            self._error = None

    def observe_send(self, payload):
        try:
            message = json.loads(payload)
            if message.get("context_id") != self._request_id:
                return
            output = message.get("output_format") or {}
            with self._lock:
                self._sample_rate = int(output.get("sample_rate", 0))
                self._channels = int(output.get("channels", 1))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._error = "Cartesia capture failed: " + type(error).__name__

    def observe_receive(self, payload):
        try:
            message = json.loads(payload)
            if message.get("context_id") != self._request_id:
                return
            response_type = message.get("type")
            with self._lock:
                if response_type == "chunk":
                    self._pcm_bytes += len(
                        base64.b64decode(message.get("data", ""))
                    )
                elif response_type == "timestamps":
                    data = message.get("word_timestamps", message)
                    words = data.get("words", [])
                    starts = data.get("start", [])
                    ends = data.get("end", [])
                    if words:
                        self._words.append(
                            tuple(
                                ReferenceWord(
                                    word,
                                    Fraction(str(starts[index])) * 1000,
                                    Fraction(str(ends[index])) * 1000,
                                )
                                for index, word in enumerate(words)
                                if index < len(starts) and index < len(ends)
                            )
                        )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            self._error = "Cartesia capture failed: " + type(error).__name__

    def reference(self, request_id):
        with self._lock:
            error = self._error
            if request_id != self._request_id:
                error = "Cartesia capture belongs to another request"
            return RequestTimingReference(
                "Cartesia",
                self._sample_rate,
                self._channels,
                self._pcm_bytes,
                tuple(_add_spacing_groups(self._words)),
                error,
            )


def _add_spacing(words):
    """Mirror Cartesia's public subtitle spacing behavior."""
    result = []
    previous = None
    for word in words:
        if previous is not None and _needs_space(previous.word, word.word):
            result.append(ReferenceWord(" ", word.start_ms, word.start_ms))
        result.append(word)
        previous = word
    return tuple(result)


def _add_spacing_groups(groups):
    """Mirror spacing both within and between Cartesia timestamp groups."""
    result = []
    previous = None
    for group in groups:
        current = []
        for word in group:
            if previous is not None and _needs_space(previous.word, word.word):
                current.append(ReferenceWord(" ", word.start_ms, word.start_ms))
            current.append(word)
            previous = word
        result.append(tuple(current))
    return result


def _needs_space(previous, current):
    if (
        not previous
        or not current
        or previous[-1].isspace()
        or current[0].isspace()
    ):
        return False
    if previous[-1] in "([{<“‘「『【":
        return False
    if current[0] in ".,!?;:%)]}，。！？；：、％》」』】":
        return False
    return True


class _WebSocketProxy:
    def __init__(self, websocket, hook):
        self._websocket = websocket
        self._hook = hook

    async def send_json(self, payload, *args, **kwargs):
        self._hook.observe_send(json.dumps(payload))
        return await self._websocket.send_json(payload, *args, **kwargs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        message = await self._websocket.__anext__()
        if getattr(message, "data", None):
            self._hook.observe_receive(message.data)
        return message

    def __getattr__(self, name):
        return getattr(self._websocket, name)
