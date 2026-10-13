#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Tests for the Fish Audio protocol-level flush_mode config."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ormsgpack
import pytest
from pydantic import ValidationError

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import FishAudioTTSClient

_POLL_INTERVAL = 0.001


class RecordingWebSocket:
    """Fake Fish Audio socket that records the events the client sends.

    A ``finish`` message is produced only after the client sends ``stop``, so
    the observed event sequence stays deterministic without races.
    """

    def __init__(self) -> None:
        self.response = SimpleNamespace(headers={})
        self.sent: list[dict] = []
        self.close_calls = 0
        self._incoming: list[dict] = []
        self._closed = asyncio.Event()

    async def send(self, message: bytes) -> None:
        payload = ormsgpack.unpackb(message)
        self.sent.append(payload)
        if payload.get("event") == "stop":
            self._incoming.append({"event": "finish", "reason": "stop"})

    async def recv(self) -> bytes:
        while True:
            if self._closed.is_set():
                raise ConnectionError("socket closed")
            if self._incoming:
                return ormsgpack.packb(self._incoming.pop(0))
            await asyncio.sleep(_POLL_INTERVAL)

    async def close(self) -> None:
        self.close_calls += 1
        self._closed.set()

    @property
    def events(self) -> list[str]:
        return [payload.get("event") for payload in self.sent]


class FakeConnect:
    def __init__(self, websocket) -> None:
        self.websocket = websocket

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, *_args) -> None:
        await self.websocket.close()


def _config(**params) -> FishAudioTTSConfig:
    config = FishAudioTTSConfig(api_key="test-key")
    config.params.update(params)
    config.update_params()
    return config


def _sent_events(config: FishAudioTTSConfig, calls) -> list[str]:
    """Feed ``calls`` through client.get() and return the sent event names."""

    async def run() -> list[str]:
        websocket = RecordingWebSocket()
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(websocket),
        ):
            client = FishAudioTTSClient(config, MagicMock())
            for text, text_input_end in calls:
                async for _event in client.get(
                    text,
                    request_id="req",
                    text_input_end=text_input_end,
                ):
                    pass
            await client.clean()
            return websocket.events

    return asyncio.run(run())


# ================ first_chunk mode ================
def test_first_chunk_flushes_only_the_first_chunk() -> None:
    events = _sent_events(
        _config(),
        [("Hello", False), (" more", False), (" end", True)],
    )
    assert events == ["start", "text", "flush", "text", "text", "stop"]


def test_first_chunk_skips_flush_on_final_chunk() -> None:
    events = _sent_events(_config(), [("Hello", True)])
    assert events == ["start", "text", "stop"]


def test_blank_text_never_flushes() -> None:
    events = _sent_events(_config(), [("   ", False)])
    assert events == ["start", "text"]


def test_blank_final_text_never_flushes() -> None:
    events = _sent_events(_config(), [(" \t ", True)])
    assert events == ["start", "text", "stop"]


# ================ off mode ================
def test_off_mode_never_flushes() -> None:
    events = _sent_events(
        _config(flush_mode="off"),
        [("Hello.", False), (" world", True)],
    )
    assert events == ["start", "text", "text", "stop"]


def test_off_mode_flush_mode_from_top_level_config() -> None:
    config = FishAudioTTSConfig(api_key="test-key", flush_mode="off")
    events = _sent_events(config, [("Hello.", False)])
    assert events == ["start", "text"]


# ================ every_sentence mode ================
@pytest.mark.parametrize(
    "text",
    [
        "Done.",
        "Really?",
        "Wow!",
        "你好。",
        "你好？",
        "你好！",
        "Trailing space! ",
    ],
)
def test_every_sentence_flushes_on_sentence_end(text: str) -> None:
    events = _sent_events(
        _config(flush_mode="every_sentence"),
        [(text, False)],
    )
    assert events == ["start", "text", "flush"]


@pytest.mark.parametrize(
    "text",
    [
        "No terminator",
        "Ends with comma,",
        "semicolon;",
        "",
        "   ",
    ],
)
def test_every_sentence_skips_non_sentence_end(text: str) -> None:
    events = _sent_events(
        _config(flush_mode="every_sentence"),
        [(text, False)],
    )
    assert events == ["start", "text"]


def test_every_sentence_flushes_each_sentence() -> None:
    events = _sent_events(
        _config(flush_mode="every_sentence"),
        [("One.", False), (" Two?", False), (" Three", True)],
    )
    assert events == ["start", "text", "flush", "text", "flush", "text", "stop"]


def test_every_sentence_skips_flush_on_final_chunk() -> None:
    """The final chunk is followed by stop, so it never flushes."""
    events = _sent_events(
        _config(flush_mode="every_sentence"),
        [("Done.", True)],
    )
    assert events == ["start", "text", "stop"]


# ================ config handling ================
def test_flush_mode_defaults_to_first_chunk() -> None:
    assert FishAudioTTSConfig().flush_mode == "first_chunk"


def test_update_params_extracts_flush_mode_from_params() -> None:
    config = _config(flush_mode="every_sentence")
    assert config.flush_mode == "every_sentence"
    assert "flush_mode" not in config.params


def test_update_params_rejects_invalid_flush_mode() -> None:
    config = FishAudioTTSConfig(api_key="test-key")
    config.params["flush_mode"] = "sometimes"

    with pytest.raises(ValueError) as excinfo:
        config.update_params()

    message = str(excinfo.value)
    for allowed in ("off", "first_chunk", "every_sentence"):
        assert allowed in message
    assert "flush_mode" not in config.params


def test_model_validation_accepts_known_flush_mode() -> None:
    config = FishAudioTTSConfig(flush_mode="every_sentence")
    assert config.flush_mode == "every_sentence"


def test_model_validation_rejects_unknown_flush_mode() -> None:
    with pytest.raises(ValidationError):
        FishAudioTTSConfig(flush_mode="sometimes")


def test_flush_mode_is_not_forwarded_to_vendor_request() -> None:
    config = _config(flush_mode="every_sentence")
    client = FishAudioTTSClient(config, MagicMock())
    request = client._build_request()
    assert "flush_mode" not in request
