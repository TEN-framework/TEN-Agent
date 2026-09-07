import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from ten_ai_base.asr import AsyncASRBaseExtension

from ..extension import SmallestASRExtension


def make_extension() -> SmallestASRExtension:
    extension = SmallestASRExtension("smallest_asr_python")
    extension.ten_env = MagicMock()
    extension.send_asr_error = AsyncMock()  # type: ignore[method-assign]
    extension.on_disconnected = AsyncMock()  # type: ignore[method-assign]
    return extension


def test_schedule_reconnect_is_single_flight():
    async def run_test() -> None:
        extension = make_extension()
        reconnect_calls = 0
        release = asyncio.Event()

        async def reconnect() -> None:
            nonlocal reconnect_calls
            reconnect_calls += 1
            await release.wait()

        extension._handle_reconnect = reconnect  # type: ignore[method-assign]

        extension._schedule_reconnect()
        extension._schedule_reconnect()
        await asyncio.sleep(0)

        assert reconnect_calls == 1

        release.set()
        await extension._cancel_reconnect_task()

    asyncio.run(run_test())


def test_disconnect_during_reconnect_unwind_schedules_follow_up():
    async def run_test() -> None:
        extension = make_extension()
        reconnect_calls = 0
        second_reconnect = asyncio.Event()

        async def reconnect() -> None:
            nonlocal reconnect_calls
            reconnect_calls += 1
            if reconnect_calls == 1:
                # Model a successful handshake followed by an immediate close
                # before this reconnect task's done callback has run.
                extension.connected = True
                extension.connected = False
                extension._schedule_reconnect()
            else:
                extension.connected = True
                second_reconnect.set()

        extension._handle_reconnect = reconnect  # type: ignore[method-assign]

        extension._schedule_reconnect()
        await asyncio.wait_for(second_reconnect.wait(), timeout=1.0)

        assert reconnect_calls == 2
        await extension._cancel_reconnect_task()

    asyncio.run(run_test())


def test_on_stop_cancels_reconnect_during_backoff():
    async def run_test() -> None:
        extension = make_extension()
        reconnect_started = asyncio.Event()
        reconnect_cancelled = asyncio.Event()

        async def reconnect() -> None:
            reconnect_started.set()
            try:
                await asyncio.Future()
            finally:
                reconnect_cancelled.set()

        async def base_on_stop(
            self: AsyncASRBaseExtension, ten_env: MagicMock
        ) -> None:
            self.stopped = True

        extension._handle_reconnect = reconnect  # type: ignore[method-assign]
        extension._schedule_reconnect()
        await reconnect_started.wait()

        with patch.object(AsyncASRBaseExtension, "on_stop", base_on_stop):
            await extension.on_stop(extension.ten_env)

        assert reconnect_cancelled.is_set()
        assert extension._reconnect_task is None

    asyncio.run(run_test())


def test_stale_message_loop_does_not_reconnect_replacement_socket():
    async def run_test() -> None:
        extension = make_extension()
        extension.connected = True
        iterator_started = asyncio.Event()
        finish_iteration = asyncio.Event()

        class PausingWebSocket:
            closed = False
            close_code = 1006

            def __aiter__(self):
                return self

            async def __anext__(self):
                iterator_started.set()
                await finish_iteration.wait()
                raise StopAsyncIteration

        stale_ws = PausingWebSocket()
        replacement_ws = SimpleNamespace(closed=False, close_code=None)
        extension.ws = stale_ws  # type: ignore[assignment]
        extension._schedule_reconnect = MagicMock()  # type: ignore[method-assign]

        message_task = asyncio.create_task(extension._process_messages())
        await iterator_started.wait()
        extension.ws = replacement_ws  # type: ignore[assignment]
        finish_iteration.set()
        await message_task

        assert extension.connected is True
        extension.send_asr_error.assert_not_awaited()  # type: ignore[attr-defined]
        extension.on_disconnected.assert_not_awaited()  # type: ignore[attr-defined]
        extension._schedule_reconnect.assert_not_called()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_message_error_marks_connection_disconnected():
    async def run_test() -> None:
        extension = make_extension()
        extension.connected = True

        class ErrorWebSocket:
            closed = False
            close_code = None
            yielded = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.yielded:
                    raise StopAsyncIteration
                self.yielded = True
                return SimpleNamespace(type=aiohttp.WSMsgType.ERROR)

            def exception(self):
                return RuntimeError("vendor socket failed")

        ws = ErrorWebSocket()
        extension.ws = ws  # type: ignore[assignment]
        extension._schedule_reconnect = MagicMock()  # type: ignore[method-assign]

        await extension._process_messages()

        assert extension.connected is False
        extension.send_asr_error.assert_awaited_once()  # type: ignore[attr-defined]
        extension.on_disconnected.assert_awaited_once()  # type: ignore[attr-defined]
        extension._schedule_reconnect.assert_called_once()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_same_socket_disconnect_is_reported_once():
    async def run_test() -> None:
        extension = make_extension()
        extension.connected = True
        ws = SimpleNamespace(closed=False, close_code=1006)
        extension.ws = ws  # type: ignore[assignment]
        extension._schedule_reconnect = MagicMock()  # type: ignore[method-assign]

        await extension._handle_unexpected_disconnect("first failure", ws)  # type: ignore[arg-type]
        await extension._handle_unexpected_disconnect("second failure", ws)  # type: ignore[arg-type]

        assert extension.connected is False
        extension.send_asr_error.assert_awaited_once()  # type: ignore[attr-defined]
        extension.on_disconnected.assert_awaited_once()  # type: ignore[attr-defined]
        extension._schedule_reconnect.assert_called_once()  # type: ignore[attr-defined]

    asyncio.run(run_test())
