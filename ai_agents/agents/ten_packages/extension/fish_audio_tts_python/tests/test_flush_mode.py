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
from ten_ai_base.const import LOG_CATEGORY_VENDOR

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.fish_audio_tts import FishAudioTTSClient

_POLL_INTERVAL = 0.001


class RecordingWebSocket:
    """Fake Fish Audio socket that records the events the client sends.

    A ``finish`` message is produced only after the client sends ``stop``, so
    the observed event sequence stays deterministic without races.
    """

    def __init__(self, timeline: list[str] | None = None) -> None:
        self.response = SimpleNamespace(headers={})
        self.sent: list[dict] = []
        self.close_calls = 0
        self._incoming: list[dict] = []
        self._closed = asyncio.Event()
        self.timeline = timeline if timeline is not None else []

    async def send(self, message: bytes) -> None:
        payload = ormsgpack.unpackb(message)
        self.sent.append(payload)
        self.timeline.append(f"send:{payload.get('event')}")
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


def test_update_params_falls_back_on_invalid_flush_mode() -> None:
    """An invalid value must not abort init; it falls back to the default."""
    config = FishAudioTTSConfig(api_key="test-key")
    config.params["flush_mode"] = "sometimes"

    config.update_params()

    assert config.flush_mode == "first_chunk"
    assert config.flush_mode_warning is not None
    for allowed in ("off", "first_chunk", "every_sentence"):
        assert allowed in config.flush_mode_warning
    assert "flush_mode" not in config.params


def test_model_validation_accepts_known_flush_mode() -> None:
    config = FishAudioTTSConfig(flush_mode="every_sentence")
    assert config.flush_mode == "every_sentence"


def test_unknown_flush_mode_falls_back_without_raising() -> None:
    config = FishAudioTTSConfig(flush_mode="sometimes")

    config.update_params()

    assert config.flush_mode == "first_chunk"
    assert config.flush_mode_warning is not None


def test_flush_mode_is_not_forwarded_to_vendor_request() -> None:
    config = _config(flush_mode="every_sentence")
    client = FishAudioTTSClient(config, MagicMock())
    request = client._build_request()
    assert "flush_mode" not in request


def test_vendor_send_logs_omit_user_text() -> None:
    """Vendor diagnostics must not persist the utterance text."""

    async def run() -> list[str]:
        websocket = RecordingWebSocket()
        ten_env = MagicMock()
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(websocket),
        ):
            client = FishAudioTTSClient(_config(flush_mode="off"), ten_env)
            async for _event in client.get(
                "hello secret phrase",
                request_id="req",
                text_input_end=True,
            ):
                pass
            await client.clean()
        return [
            call.args[0]
            for call in ten_env.log_info.call_args_list
            if call.kwargs.get("category") == LOG_CATEGORY_VENDOR
        ]

    messages = asyncio.run(run())
    assert messages
    for message in messages:
        assert "secret" not in message


# ================ on_text_send contract ================
def test_client_invokes_on_text_send_before_each_text_payload() -> None:
    """The extension's TTFB anchor depends on this client contract.

    The mocked-client tests replace FishAudioTTSClient entirely, so no mock
    exercised this callback and their assertions silently lost coverage when
    the TTFB anchor moved to text-send time. Lock the real behaviour: the
    callback fires immediately before the text payload goes over the socket.
    """
    timeline: list[str] = []

    async def run() -> list[str]:
        websocket = RecordingWebSocket(timeline)
        with patch(
            "fish_audio_tts_python.fish_audio_tts.connect",
            return_value=FakeConnect(websocket),
        ):
            client = FishAudioTTSClient(
                _config(),
                MagicMock(),
                on_text_send=lambda: timeline.append("on_text_send"),
            )
            for text, text_input_end in (
                ("Hello", False),
                (" world", True),
            ):
                async for _event in client.get(
                    text,
                    request_id="req",
                    text_input_end=text_input_end,
                ):
                    pass
            await client.clean()
        return timeline

    recorded = asyncio.run(run())

    callback_indexes = [
        index for index, entry in enumerate(recorded) if entry == "on_text_send"
    ]
    text_send_indexes = [
        index for index, entry in enumerate(recorded) if entry == "send:text"
    ]

    assert len(callback_indexes) == 2, recorded
    assert len(text_send_indexes) == 2, recorded
    for callback_index, text_send_index in zip(
        callback_indexes, text_send_indexes
    ):
        assert callback_index < text_send_index, recorded
