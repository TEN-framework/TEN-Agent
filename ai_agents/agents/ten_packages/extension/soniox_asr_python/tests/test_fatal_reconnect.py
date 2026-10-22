#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.asr import AsyncASRBaseExtension
from ten_ai_base.message import ModuleErrorCode

from ..config import FinalizeReconnectMode, SonioxASRConfig
from ..extension import SonioxASRExtension
from ..reconnect_manager import ReconnectManager


def make_extension() -> SonioxASRExtension:
    ext = SonioxASRExtension("test")
    ext.ten_env = MagicMock()
    ext.ten_env.send_data = AsyncMock()
    ext.config = SonioxASRConfig(params={"api_key": "fake_key"})
    ext.send_asr_error = AsyncMock()
    ext.on_disconnected = AsyncMock()
    return ext


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,message",
    [
        (400, "Invalid parameter"),
        (401, "Unauthorized"),
        (402, "Payment required"),
    ],
)
async def test_fatal_error_prevents_close_reconnect(code, message):
    ext = make_extension()
    ext.connected = True
    ext._needs_reconnect = True
    ext._handle_reconnect = AsyncMock()

    await ext._handle_error(code, message)
    # A later transient error must not clear the fatal latch.
    await ext._handle_error(-1, "Connection closed")
    await ext._handle_close(1006, "abnormal closure")

    assert ext._fatal_error
    assert not ext._needs_reconnect
    assert not ext.connected
    ext._handle_reconnect.assert_not_awaited()
    ext.on_disconnected.assert_awaited_once()
    error, vendor_info = ext.send_asr_error.await_args_list[0].args
    assert error.code == int(ModuleErrorCode.FATAL_ERROR.value)
    assert vendor_info.code == str(code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,message",
    [
        (400, "No audio received"),
        (400, "Audio is too long"),
        (500, "Internal server error"),
        (-1, "Connection exception"),
    ],
)
async def test_non_fatal_error_preserves_close_reconnect(code, message):
    ext = make_extension()
    ext._handle_reconnect = AsyncMock()

    await ext._handle_error(code, message)
    await ext._handle_close()

    assert not ext._fatal_error
    ext._handle_reconnect.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(FinalizeReconnectMode))
async def test_fatal_error_completes_finalize_without_reconnect(mode):
    ext = make_extension()
    ext.config.finalize_reconnect_mode = mode
    ext._pending_close_finalize = True
    ext._finalize_end = AsyncMock()
    ext.start_connection = AsyncMock()

    await ext._handle_error(401, "Unauthorized")
    await ext._handle_close()

    ext._finalize_end.assert_awaited_once_with("disconnect")
    ext.start_connection.assert_not_awaited()
    assert not ext._pending_close_finalize
    assert not ext._needs_reconnect


@pytest.mark.asyncio
async def test_fatal_error_prevents_audio_triggered_reconnect():
    ext = make_extension()
    ext._needs_reconnect = True
    ext.start_connection = AsyncMock()

    await ext._handle_error(401, "Unauthorized")
    with patch.object(
        AsyncASRBaseExtension, "on_audio_frame", new_callable=AsyncMock
    ) as on_audio_frame:
        frame = MagicMock()
        await ext.on_audio_frame(ext.ten_env, frame)
        on_audio_frame.assert_awaited_once_with(ext.ten_env, frame)

    ext.start_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_fatal_error_during_backoff_prevents_connection():
    ext = make_extension()
    ext.reconnect_manager = ReconnectManager()
    ext._start_websocket = AsyncMock()

    async def fatal_during_sleep(_delay):
        await ext._handle_error(401, "Unauthorized")

    with patch(
        "soniox_asr_python.reconnect_manager.asyncio.sleep",
        side_effect=fatal_during_sleep,
    ):
        await ext._handle_reconnect()

    ext._start_websocket.assert_not_awaited()
    ext.on_disconnected.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_api_key_latches_fatal_error():
    ext = make_extension()
    ext.config.params = {}
    ext._start_websocket = AsyncMock()
    ext.reconnect_manager = MagicMock()
    ext.reconnect_manager.handle_reconnect = AsyncMock()

    await ext.start_connection()
    await ext._handle_reconnect()
    await ext.start_connection()

    assert ext._fatal_error
    ext.send_asr_error.assert_awaited_once()
    ext._start_websocket.assert_not_awaited()
    ext.reconnect_manager.handle_reconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_consecutive_connection_failures_keep_reconnecting():
    ext = make_extension()
    ext.reconnect_manager = ReconnectManager(base_delay=0, max_delay=0)
    tasks = []
    disconnected = asyncio.Event()

    async def on_disconnected(**_kwargs):
        if len(tasks) == 3:
            disconnected.set()

    ext.on_disconnected.side_effect = on_disconnected

    class FailedConnection:
        async def __aenter__(self):
            tasks.append(asyncio.current_task())
            if len(tasks) == 3:
                ext.stopped = True
            raise ConnectionError("Handshake failed")

        async def __aexit__(self, *_args):
            return False

    with patch(
        "soniox_asr_python.websocket.websockets.connect",
        side_effect=lambda _url, **_kwargs: FailedConnection(),
    ):
        try:
            await ext.start_connection()
            await asyncio.wait_for(disconnected.wait(), timeout=1)
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    assert len(tasks) == 3
    assert ext.reconnect_manager.attempts == 2
    assert not ext._suppress_close_status
    assert not ext._fatal_error


@pytest.mark.asyncio
@pytest.mark.parametrize("emits_close", [False, True])
async def test_close_suppression_does_not_leak_to_next_connection(emits_close):
    ext = make_extension()
    ext.websocket = MagicMock()
    ext.websocket.stop = AsyncMock()
    if emits_close:
        ext.websocket.stop.side_effect = ext._handle_close

    await ext._stop_websocket(suppress_status=True)

    assert not ext._suppress_close_status
    ext._handle_reconnect = AsyncMock()
    await ext._handle_close()
    ext._handle_reconnect.assert_awaited_once()
