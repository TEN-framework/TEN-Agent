#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import os
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.asr import AsyncASRBaseExtension

extension_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, extension_dir)

package = types.ModuleType("bytedance_llm_based_asr")
package.__path__ = [extension_dir]
sys.modules["bytedance_llm_based_asr"] = package

from bytedance_llm_based_asr import config as config_module

sys.modules["bytedance_llm_based_asr.config"] = config_module

from bytedance_llm_based_asr import extension as extension_module

sys.modules["bytedance_llm_based_asr.extension"] = extension_module

from bytedance_llm_based_asr.config import BytedanceASRLLMConfig
from bytedance_llm_based_asr.extension import BytedanceASRLLMExtension


def _minimal_config() -> BytedanceASRLLMConfig:
    return BytedanceASRLLMConfig.model_validate(
        {
            "params": {
                "audio": {"rate": 16000},
                "request": {"model_name": "bigmodel"},
            }
        }
    )


class _BlockingClient:
    def __init__(self) -> None:
        self.connected = True
        self.audio_send_started = asyncio.Event()
        self.allow_audio_send = asyncio.Event()
        self.finalize_started = asyncio.Event()
        self.allow_finalize = asyncio.Event()

    async def send_audio(self, _audio_data: bytes) -> None:
        self.audio_send_started.set()
        await self.allow_audio_send.wait()
        if not self.connected:
            raise RuntimeError("Not connected to ASR service")

    async def finalize(self) -> None:
        self.finalize_started.set()
        await self.allow_finalize.wait()
        if not self.connected:
            raise RuntimeError("Not connected to ASR service")


def _new_extension(client: object) -> BytedanceASRLLMExtension:
    extension = BytedanceASRLLMExtension("test_extension")
    extension.ten_env = MagicMock()
    extension.config = _minimal_config()
    extension.connected = True
    extension.client = client
    extension.send_asr_error = AsyncMock()
    return extension


def _frame(payload: bytes = b"\x00\x01") -> MagicMock:
    frame = MagicMock()
    frame.lock_buf.return_value = payload
    frame.get_buf.return_value = payload
    frame.get_property_to_json.return_value = ("", None)
    return frame


def _install_restart_mocks(
    extension: BytedanceASRLLMExtension,
    old_client: Any,
) -> tuple[AsyncMock, AsyncMock]:
    async def stop_connection() -> None:
        old_client.connected = False
        extension.connected = False
        extension.client = None

    async def start_connection() -> None:
        new_client = MagicMock()
        new_client.connected = True
        extension.client = new_client
        extension.connected = True

    stop_mock = AsyncMock(side_effect=stop_connection)
    start_mock = AsyncMock(side_effect=start_connection)
    extension.stop_connection = stop_mock
    extension.start_connection = start_mock
    return stop_mock, start_mock


@pytest.mark.asyncio
async def test_update_configs_waits_for_in_flight_audio():
    client = _BlockingClient()
    extension = _new_extension(client)
    stop_mock, _ = _install_restart_mocks(extension, client)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await client.audio_send_started.wait()

    update_task = asyncio.create_task(
        extension._run_update_configs(
            {
                "params": {
                    "request": {
                        "corpus": {"context": "updated dialog context"},
                    }
                }
            }
        )
    )
    await asyncio.sleep(0)

    assert extension.is_connected() is False
    assert extension._send_lock.locked()
    stop_mock.assert_not_awaited()
    client.allow_audio_send.set()
    update_result, audio_result = await asyncio.gather(update_task, audio_task)

    assert update_result == (True, "")
    assert audio_result is True
    stop_mock.assert_awaited_once()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_dump_outside_send_lock_does_not_block_reconnect():
    """Slow dump must not hold _send_lock; replace can proceed during dump."""
    old_client = MagicMock()
    old_client.connected = True
    old_client.send_audio = AsyncMock()
    extension = _new_extension(old_client)

    dump_started = asyncio.Event()
    allow_dump = asyncio.Event()
    stop_started = asyncio.Event()
    allow_stop = asyncio.Event()
    audio_dumper = MagicMock()

    async def push_bytes(_audio_data: bytes) -> None:
        dump_started.set()
        await allow_dump.wait()

    async def stop_connection() -> None:
        stop_started.set()
        old_client.connected = False
        extension.connected = False
        await allow_stop.wait()
        extension.client = None

    async def start_connection() -> None:
        new_client = MagicMock()
        new_client.connected = True
        new_client.send_audio = AsyncMock()
        extension.client = new_client
        extension.connected = True

    audio_dumper.push_bytes = AsyncMock(side_effect=push_bytes)
    extension.audio_dumper = audio_dumper
    extension.stop_connection = AsyncMock(side_effect=stop_connection)
    extension.start_connection = AsyncMock(side_effect=start_connection)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await dump_started.wait()
    assert not extension._send_lock.locked()

    update_task = asyncio.create_task(
        extension._run_update_configs(
            {"params": {"request": {"enable_nonstream": False}}}
        )
    )
    await stop_started.wait()
    assert not allow_dump.is_set()

    allow_dump.set()
    await asyncio.sleep(0)
    allow_stop.set()
    update_result, audio_result = await asyncio.gather(update_task, audio_task)

    assert update_result == (True, "")
    # In-flight frame may soft-fail during the gate or land on the new client.
    assert audio_result in (True, False)
    old_client.send_audio.assert_not_awaited()
    extension.stop_connection.assert_awaited_once()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_audio_during_swap_returns_false_without_touching_old_client():
    """While connection is being replaced, send_audio soft-fails; base buffers."""
    old_client = MagicMock()
    old_client.connected = True
    old_client.send_audio = AsyncMock()
    extension = _new_extension(old_client)

    switch_started = asyncio.Event()
    allow_switch = asyncio.Event()
    new_client = MagicMock()
    new_client.connected = True
    new_client.send_audio = AsyncMock()

    async def stop_connection() -> None:
        old_client.connected = False
        extension.connected = False
        switch_started.set()
        await allow_switch.wait()
        extension.client = None

    async def start_connection() -> None:
        extension.client = new_client
        extension.connected = True

    extension.stop_connection = AsyncMock(side_effect=stop_connection)
    extension.start_connection = AsyncMock(side_effect=start_connection)

    update_task = asyncio.create_task(
        extension._run_update_configs(
            {"params": {"request": {"enable_nonstream": False}}}
        )
    )
    await switch_started.wait()

    audio_result = await extension.send_audio(_frame(), "session-1")

    assert audio_result is False
    old_client.send_audio.assert_not_awaited()
    extension.start_connection.assert_not_awaited()

    allow_switch.set()
    update_result = await update_task

    assert update_result == (True, "")
    extension.start_connection.assert_awaited_once()
    new_client.send_audio.assert_not_awaited()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_audio_frame_buffers_during_connection_swap():
    """Base Keep buffer must receive frames while is_connected is gated off."""
    client = MagicMock()
    client.connected = True
    extension = _new_extension(client)
    extension._connection_swap_depth = 1

    frame = _frame(b"\x02\x03")
    await extension._handle_audio_frame(extension.ten_env, frame)

    assert extension.buffered_frames.qsize() == 1
    assert extension.buffered_frames_size == 2
    client.send_audio = AsyncMock()
    # Direct send also soft-fails while gated.
    assert await extension.send_audio(frame, "session-1") is False


@pytest.mark.asyncio
async def test_send_audio_skips_when_disconnected_without_reconnecting():
    client = MagicMock()
    client.connected = False
    extension = _new_extension(client)
    extension.connected = False
    extension.start_connection = AsyncMock()

    result = await extension.send_audio(_frame(), "session-1")

    assert result is False
    extension.start_connection.assert_not_awaited()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_audio_propagates_external_cancellation():
    """A real CancelledError must not be swallowed as a soft failure."""
    client = _BlockingClient()
    extension = _new_extension(client)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await client.audio_send_started.wait()

    audio_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await audio_task

    client.allow_audio_send.set()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_configs_waits_for_in_flight_finalize():
    client = _BlockingClient()
    extension = _new_extension(client)
    stop_mock, _ = _install_restart_mocks(extension, client)

    finalize_task = asyncio.create_task(extension.finalize("session-1"))
    await client.finalize_started.wait()

    update_task = asyncio.create_task(
        extension._run_update_configs(
            {
                "params": {
                    "request": {
                        "corpus": {"context": "updated dialog context"},
                    }
                }
            }
        )
    )
    await asyncio.sleep(0)

    assert extension.is_connected() is False
    assert extension._send_lock.locked()
    stop_mock.assert_not_awaited()
    client.allow_finalize.set()
    update_result, _ = await asyncio.gather(update_task, finalize_task)

    assert update_result == (True, "")
    stop_mock.assert_awaited_once()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_automatic_reconnect_waits_for_in_flight_audio():
    client = _BlockingClient()
    extension = _new_extension(client)
    extension.min_retry_delay = 0
    stop_mock, _ = _install_restart_mocks(extension, client)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await client.audio_send_started.wait()

    reconnect_task = asyncio.create_task(extension._handle_reconnect())
    await asyncio.sleep(0)

    stop_mock.assert_not_awaited()
    client.allow_audio_send.set()
    await asyncio.gather(audio_task, reconnect_task)

    stop_mock.assert_awaited_once()
    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconnect_waits_for_in_flight_update_configs_replace():
    """update_configs and reconnect must not overlap start_connection / leak clients."""
    old_client = MagicMock()
    old_client.connected = True
    extension = _new_extension(old_client)
    extension.min_retry_delay = 0

    start_entered = asyncio.Event()
    allow_start = asyncio.Event()
    live_clients: list[MagicMock] = []
    max_concurrent_live = 0

    async def stop_connection() -> None:
        client = extension.client
        if client is not None:
            client.connected = False
            if client in live_clients:
                live_clients.remove(client)
        extension.connected = False
        extension.client = None

    async def start_connection() -> None:
        nonlocal max_concurrent_live
        new_client = MagicMock()
        new_client.connected = True
        live_clients.append(new_client)
        max_concurrent_live = max(max_concurrent_live, len(live_clients))
        extension.client = new_client
        extension.connected = True
        start_entered.set()
        await allow_start.wait()

    extension.stop_connection = AsyncMock(side_effect=stop_connection)
    extension.start_connection = AsyncMock(side_effect=start_connection)

    update_task = asyncio.create_task(
        extension._run_update_configs(
            {"params": {"request": {"enable_nonstream": False}}}
        )
    )
    await start_entered.wait()

    reconnect_task = asyncio.create_task(extension._handle_reconnect())
    await asyncio.sleep(0)

    # Reconnect is blocked on _swap_lock; only the update swap's client is live.
    assert len(live_clients) == 1
    assert extension.start_connection.await_count == 1
    assert extension._swap_lock.locked()

    allow_start.set()
    update_result, _ = await asyncio.gather(update_task, reconnect_task)

    assert update_result == (True, "")
    assert max_concurrent_live == 1
    assert len(live_clients) == 1
    assert extension.client is live_clients[0]
    # Serialized: update's start, then reconnect's stop+start.
    assert extension.start_connection.await_count == 2
    assert extension.stop_connection.await_count == 2


@pytest.mark.asyncio
async def test_reconnect_does_not_run_after_stop_while_waiting_for_send_lock():
    client = MagicMock()
    client.connected = False
    extension = _new_extension(client)
    extension.connected = False
    extension.min_retry_delay = 0
    extension.stop_connection = AsyncMock()
    extension.start_connection = AsyncMock()

    async with extension._send_lock:
        reconnect_task = asyncio.create_task(extension._handle_reconnect())
        await asyncio.sleep(0)
        extension.stopped = True

    await reconnect_task

    extension.stop_connection.assert_not_awaited()
    extension.start_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_error_reconnect_does_not_deadlock():
    client = MagicMock()
    client.connected = True
    client.finalize = AsyncMock(side_effect=RuntimeError("finalize failed"))
    extension = _new_extension(client)
    extension.min_retry_delay = 0
    stop_mock, start_mock = _install_restart_mocks(extension, client)

    await asyncio.wait_for(extension.finalize("session-1"), timeout=1.0)

    stop_mock.assert_awaited_once()
    start_mock.assert_awaited_once()
    extension.send_asr_error.assert_awaited()


@pytest.mark.asyncio
async def test_on_deinit_waits_for_in_flight_audio():
    client = _BlockingClient()
    extension = _new_extension(client)

    async def stop_connection() -> None:
        client.connected = False
        extension.connected = False
        extension.client = None

    extension.stop_connection = AsyncMock(side_effect=stop_connection)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await client.audio_send_started.wait()

    with patch.object(
        AsyncASRBaseExtension, "on_deinit", new_callable=AsyncMock
    ):
        deinit_task = asyncio.create_task(
            extension.on_deinit(extension.ten_env)
        )
        await asyncio.sleep(0)

        extension.stop_connection.assert_not_awaited()
        client.allow_audio_send.set()
        await asyncio.gather(audio_task, deinit_task)

    assert audio_task.result() is True
    extension.stop_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_audio_resumes_on_new_connection_after_replace():
    old_client = _BlockingClient()
    extension = _new_extension(old_client)
    extension.min_retry_delay = 0

    new_client = MagicMock()
    new_client.connected = True
    new_client.send_audio = AsyncMock()

    async def stop_connection() -> None:
        old_client.connected = False
        extension.connected = False
        extension.client = None

    async def start_connection() -> None:
        extension.client = new_client
        extension.connected = True

    extension.stop_connection = AsyncMock(side_effect=stop_connection)
    extension.start_connection = AsyncMock(side_effect=start_connection)

    audio_task = asyncio.create_task(
        extension.send_audio(_frame(), "session-1")
    )
    await old_client.audio_send_started.wait()

    reconnect_task = asyncio.create_task(extension._handle_reconnect())
    await asyncio.sleep(0)
    old_client.allow_audio_send.set()
    await asyncio.gather(audio_task, reconnect_task)

    result = await asyncio.wait_for(
        extension.send_audio(_frame(), "session-2"),
        timeout=1.0,
    )

    assert result is True
    new_client.send_audio.assert_awaited_once_with(b"\x00\x01")
    extension.send_asr_error.assert_not_awaited()
