#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from websockets.frames import Close

from ..extension import SonioxASRExtension
from ..websocket import SonioxWebsocketClient, SonioxWebsocketEvents


def _connection_closed_ok(code: int = 1000, reason: str = "OK"):
    return ConnectionClosedOK(Close(code, reason), None)


def _connection_closed_error(code: int = 1006, reason: str = "abnormal"):
    return ConnectionClosedError(Close(code, reason), None)


def test_is_normal_websocket_close_ok():
    assert (
        SonioxASRExtension._is_normal_websocket_close(_connection_closed_ok())
        is True
    )
    assert (
        SonioxWebsocketClient.is_normal_close(_connection_closed_ok()) is True
    )


def test_is_normal_websocket_close_rejects_abnormal():
    assert (
        SonioxASRExtension._is_normal_websocket_close(
            _connection_closed_error()
        )
        is False
    )


def test_is_normal_websocket_close_rejects_going_away_1001():
    """1001 is ConnectionClosedOK in websockets but must not be silent."""
    going_away = _connection_closed_ok(1001, "going away")
    assert isinstance(going_away, ConnectionClosedOK)
    assert SonioxWebsocketClient.is_normal_close(going_away) is False
    assert SonioxASRExtension._is_normal_websocket_close(going_away) is False


@pytest.mark.asyncio
async def test_handle_exception_skips_error_on_normal_close():
    ext = SonioxASRExtension("test")
    ext.ten_env = MagicMock()
    ext.send_asr_error = AsyncMock()

    await ext._handle_exception(_connection_closed_ok())

    ext.send_asr_error.assert_not_awaited()
    ext.ten_env.log_info.assert_called()


@pytest.mark.asyncio
async def test_handle_exception_reports_abnormal_close_as_error():
    ext = SonioxASRExtension("test")
    ext.ten_env = MagicMock()
    ext.send_asr_error = AsyncMock()

    await ext._handle_exception(_connection_closed_error())

    ext.send_asr_error.assert_awaited_once()
    vendor_info = ext.send_asr_error.await_args.args[1]
    assert vendor_info.code == "-1"


@pytest.mark.asyncio
async def test_handle_exception_reports_going_away_1001_as_error():
    ext = SonioxASRExtension("test")
    ext.ten_env = MagicMock()
    ext.send_asr_error = AsyncMock()

    await ext._handle_exception(_connection_closed_ok(1001, "going away"))

    ext.send_asr_error.assert_awaited_once()
    error = ext.send_asr_error.await_args.args[0]
    assert "going away" in error.message or "1001" in str(
        ext.send_asr_error.await_args
    )


@pytest.mark.asyncio
async def test_websocket_normal_close_emits_close_not_exception():
    """Code 1000 must fire CLOSE once and never EXCEPTION."""
    client = SonioxWebsocketClient(
        "wss://example.invalid/ws",
        json.dumps({"api_key": "x"}),
    )
    events: list[tuple] = []

    async def on_exception(e):
        events.append(("exception", e))

    async def on_close(code, message):
        events.append(("close", code, message))

    client.on(SonioxWebsocketEvents.EXCEPTION, on_exception)
    client.on(SonioxWebsocketEvents.CLOSE, on_close)

    e = _connection_closed_ok()
    if client.state != client.State.STOPPING and not client.is_normal_close(e):
        await client._call(SonioxWebsocketEvents.EXCEPTION, e)
    close_code, close_message = client._extract_close_info(e)
    if client.state != client.State.STOPPING:
        await client._call(
            SonioxWebsocketEvents.CLOSE, close_code, close_message
        )

    assert events == [("close", 1000, "OK")]


@pytest.mark.asyncio
async def test_connect_going_away_1001_emits_exception_and_close():
    """Actual connect()/recv path: 1001 must emit EXCEPTION then CLOSE."""
    client = SonioxWebsocketClient(
        "wss://example.invalid/ws",
        json.dumps({"api_key": "x"}),
    )
    events: list[tuple] = []
    going_away = _connection_closed_ok(1001, "going away")

    async def on_exception(e):
        events.append(("exception", e))

    async def on_open(_ts):
        events.append(("open",))

    async def on_close(code, message):
        events.append(("close", code, message))

    client.on(SonioxWebsocketEvents.EXCEPTION, on_exception)
    client.on(SonioxWebsocketEvents.OPEN, on_open)
    client.on(SonioxWebsocketEvents.CLOSE, on_close)

    class FakeWs:
        async def send(self, _message):
            return None

        async def recv(self):
            raise going_away

    class FakeConnectCM:
        async def __aenter__(self):
            return FakeWs()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch(
        "soniox_asr_python.websocket.websockets.connect",
        return_value=FakeConnectCM(),
    ):
        await client.connect()

    assert len(events) == 3
    assert events[0] == ("open",)
    assert events[1][0] == "exception"
    assert isinstance(events[1][1], ConnectionClosedOK)
    assert events[1][1].code == 1001
    assert events[2] == ("close", 1001, "going away")


@pytest.mark.asyncio
async def test_connect_normal_close_1000_emits_close_not_exception():
    """Actual connect()/recv path: 1000 must emit CLOSE only."""
    client = SonioxWebsocketClient(
        "wss://example.invalid/ws",
        json.dumps({"api_key": "x"}),
    )
    events: list[tuple] = []
    normal = _connection_closed_ok(1000, "OK")

    async def on_exception(e):
        events.append(("exception", e))

    async def on_open(_ts):
        events.append(("open",))

    async def on_close(code, message):
        events.append(("close", code, message))

    client.on(SonioxWebsocketEvents.EXCEPTION, on_exception)
    client.on(SonioxWebsocketEvents.OPEN, on_open)
    client.on(SonioxWebsocketEvents.CLOSE, on_close)

    class FakeWs:
        async def send(self, _message):
            return None

        async def recv(self):
            raise normal

    class FakeConnectCM:
        async def __aenter__(self):
            return FakeWs()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch(
        "soniox_asr_python.websocket.websockets.connect",
        return_value=FakeConnectCM(),
    ):
        await client.connect()

    assert events[0] == ("open",)
    assert "exception" not in [e[0] for e in events]
    assert events[-1] == ("close", 1000, "OK")


def test_normal_close_reconnect_does_not_send_error(patch_soniox_ws):
    from .conftest import create_fake_websocket_mocks, inject_websocket_mocks
    from ten_runtime import (
        AsyncExtensionTester,
        AsyncTenEnvTester,
        AudioFrame,
        Data,
        TenError,
        TenErrorCode,
    )
    from typing_extensions import override

    class NormalCloseTester(AsyncExtensionTester):
        def __init__(self):
            super().__init__()
            self.errors: list[dict] = []
            self.saw_disconnect = False
            self.sender_task: asyncio.Task[None] | None = None
            self.stopped = False

        async def audio_sender(self, ten_env: AsyncTenEnvTester):
            while not self.stopped:
                chunk = b"\x01\x02" * 160
                audio_frame = AudioFrame.create("pcm_frame")
                audio_frame.set_property_from_json(
                    "metadata", json.dumps({"session_id": "normal_close"})
                )
                audio_frame.alloc_buf(len(chunk))
                buf = audio_frame.lock_buf()
                buf[:] = chunk
                audio_frame.unlock_buf(buf)
                await ten_env.send_audio_frame(audio_frame)
                await asyncio.sleep(0.05)

        @override
        async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
            self.sender_task = asyncio.create_task(
                self.audio_sender(ten_env_tester)
            )

        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            name = data.get_name()
            payload = json.loads(data.get_property_to_json()[0])
            if name == "error":
                self.errors.append(payload)
            if (
                name == "connection_status_changed"
                and payload.get("current") == "disconnected"
            ):
                self.saw_disconnect = True
                self.stopped = True
                if self.sender_task:
                    self.sender_task.cancel()
                if self.errors:
                    ten_env_tester.stop_test(
                        TenError.create(
                            error_code=TenErrorCode.ErrorCodeGeneric,
                            error_message=(
                                f"unexpected error on normal close: {self.errors}"
                            ),
                        )
                    )
                else:
                    ten_env_tester.stop_test()

    tester = NormalCloseTester()

    async def custom_connect():
        await patch_soniox_ws.websocket_client.trigger_open()
        await asyncio.sleep(0.15)
        # Simulate server normal close (1000 OK) without EXCEPTION.
        await patch_soniox_ws.websocket_client.trigger_close(1000, "OK")

    mocks = create_fake_websocket_mocks(
        patch_soniox_ws, on_connect=custom_connect
    )
    inject_websocket_mocks(patch_soniox_ws, mocks)

    property_json = {
        "params": {
            "api_key": "fake_key",
            "url": "wss://fake.soniox.com/transcribe-websocket",
            "sample_rate": 16000,
            "dump": False,
            "dump_path": ".",
        }
    }
    tester.set_test_mode_single("soniox_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"normal close test failed: {err.error_message()}"
    assert tester.saw_disconnect


def test_going_away_1001_reports_non_fatal_error(patch_soniox_ws):
    from .conftest import create_fake_websocket_mocks, inject_websocket_mocks
    from ten_runtime import (
        AsyncExtensionTester,
        AsyncTenEnvTester,
        AudioFrame,
        Data,
        TenError,
        TenErrorCode,
    )
    from typing_extensions import override

    class GoingAwayTester(AsyncExtensionTester):
        def __init__(self):
            super().__init__()
            self.errors: list[dict] = []
            self.saw_disconnect = False
            self.sender_task: asyncio.Task[None] | None = None
            self.stopped = False

        async def audio_sender(self, ten_env: AsyncTenEnvTester):
            while not self.stopped:
                chunk = b"\x01\x02" * 160
                audio_frame = AudioFrame.create("pcm_frame")
                audio_frame.set_property_from_json(
                    "metadata", json.dumps({"session_id": "going_away"})
                )
                audio_frame.alloc_buf(len(chunk))
                buf = audio_frame.lock_buf()
                buf[:] = chunk
                audio_frame.unlock_buf(buf)
                await ten_env.send_audio_frame(audio_frame)
                await asyncio.sleep(0.05)

        @override
        async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
            self.sender_task = asyncio.create_task(
                self.audio_sender(ten_env_tester)
            )

        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            name = data.get_name()
            payload = json.loads(data.get_property_to_json()[0])
            if name == "error":
                self.errors.append(payload)
            if (
                name == "connection_status_changed"
                and payload.get("current") == "disconnected"
            ):
                self.saw_disconnect = True
                self.stopped = True
                if self.sender_task:
                    self.sender_task.cancel()
                if not self.errors:
                    ten_env_tester.stop_test(
                        TenError.create(
                            error_code=TenErrorCode.ErrorCodeGeneric,
                            error_message=(
                                "expected NON_FATAL error on 1001 going away"
                            ),
                        )
                    )
                else:
                    ten_env_tester.stop_test()

    tester = GoingAwayTester()

    async def custom_connect():
        await patch_soniox_ws.websocket_client.trigger_open()
        await asyncio.sleep(0.15)
        await patch_soniox_ws.websocket_client.trigger_exception(
            _connection_closed_ok(1001, "going away")
        )
        await patch_soniox_ws.websocket_client.trigger_close(1001, "going away")

    mocks = create_fake_websocket_mocks(
        patch_soniox_ws, on_connect=custom_connect
    )
    inject_websocket_mocks(patch_soniox_ws, mocks)

    property_json = {
        "params": {
            "api_key": "fake_key",
            "url": "wss://fake.soniox.com/transcribe-websocket",
            "sample_rate": 16000,
            "dump": False,
            "dump_path": ".",
        }
    }
    tester.set_test_mode_single("soniox_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"going away test failed: {err.error_message()}"
    assert tester.saw_disconnect
    assert tester.errors, "expected ASR error for 1001 going away"
