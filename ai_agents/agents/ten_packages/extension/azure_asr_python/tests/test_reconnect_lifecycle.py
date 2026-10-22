import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from ..config import AzureASRConfig
from ..extension import AzureASRExtension
from ..reconnect_manager import ReconnectManager


async def _mock_reconnect_handshake_ok(extension: AzureASRExtension) -> bool:
    extension._transport_connected = True
    extension.connected = True
    extension._transport_handshake_ready.set()
    return True


def make_extension(
    transport_reconnect_grace_sec: float = 10,
) -> AzureASRExtension:
    extension = AzureASRExtension("azure_asr_python")
    extension.ten_env = MagicMock()
    extension.config = AzureASRConfig(
        transport_reconnect_grace_sec=transport_reconnect_grace_sec
    )
    extension.reconnect_manager = MagicMock()
    extension.reconnect_manager.can_retry = MagicMock(return_value=True)
    extension.client = MagicMock()
    extension.on_disconnected = AsyncMock()  # type: ignore[method-assign]
    extension.on_connected = AsyncMock()  # type: ignore[method-assign]
    extension.send_connect_delay_metrics = AsyncMock()  # type: ignore[method-assign]
    extension.send_asr_error = AsyncMock()  # type: ignore[method-assign]
    extension.stop_connection = AsyncMock()  # type: ignore[method-assign]

    async def mock_reconnect() -> bool:
        return await _mock_reconnect_handshake_ok(extension)

    extension._handle_reconnect = AsyncMock(side_effect=mock_reconnect)  # type: ignore[method-assign]
    extension._recognizer_epoch = 1
    extension.stopped = False
    extension.connected = True
    extension._transport_connected = True
    return extension


def make_extension_with_real_stop(
    transport_reconnect_grace_sec: float = 10,
) -> AzureASRExtension:
    """Extension with real stop_connection; SDK/metrics dependencies mocked."""
    extension = AzureASRExtension("azure_asr_python")
    extension.ten_env = MagicMock()
    extension.config = AzureASRConfig(
        transport_reconnect_grace_sec=transport_reconnect_grace_sec
    )
    extension.reconnect_manager = ReconnectManager(
        max_attempts=5, logger=MagicMock()
    )
    extension.client = MagicMock()
    extension.client.stop_continuous_recognition = MagicMock()
    extension.send_vendor_metrics = AsyncMock()  # type: ignore[method-assign]
    extension.on_disconnected = AsyncMock()  # type: ignore[method-assign]
    extension.on_connected = AsyncMock()  # type: ignore[method-assign]
    extension.send_connect_delay_metrics = AsyncMock()  # type: ignore[method-assign]
    extension.send_asr_error = AsyncMock()  # type: ignore[method-assign]
    extension.stopped = False
    extension.connected = True
    extension._transport_connected = False
    extension._recognizer_epoch = 1
    return extension


def test_transport_recovery_runs_after_grace_when_sdk_does_not_reconnect():
    async def run_test() -> None:
        extension = make_extension(transport_reconnect_grace_sec=0.05)
        evt = SimpleNamespace(session_id="session-1")

        await extension._azure_event_handler_on_disconnected(evt, 1)
        assert extension.connected is True
        assert extension.is_connected() is False

        await asyncio.sleep(0.1)

        extension.stop_connection.assert_awaited_once()  # type: ignore[attr-defined]
        extension._handle_reconnect.assert_awaited_once()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_transport_recovery_task_can_be_cancelled_and_awaited():
    async def run_test() -> None:
        extension = make_extension(transport_reconnect_grace_sec=10)

        await extension._schedule_transport_recovery()
        task = extension._transport_recovery_task
        assert task is not None

        await extension._cancel_transport_recovery()

        assert task.done()
        extension._handle_reconnect.assert_not_awaited()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_transport_recovery_cancelled_when_sdk_reconnects():
    async def run_test() -> None:
        extension = make_extension(transport_reconnect_grace_sec=0.2)
        disconnect_evt = SimpleNamespace(session_id="session-1")
        connect_evt = SimpleNamespace(session_id="session-1")

        await extension._azure_event_handler_on_disconnected(disconnect_evt, 1)
        await extension._azure_event_handler_on_connected(connect_evt, 1)
        await asyncio.sleep(0.3)

        assert extension.is_connected() is True
        extension.stop_connection.assert_not_awaited()  # type: ignore[attr-defined]
        extension._handle_reconnect.assert_not_awaited()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_session_stopped_cancels_pending_transport_recovery():
    async def run_test() -> None:
        extension = make_extension(transport_reconnect_grace_sec=10)
        disconnect_evt = SimpleNamespace(session_id="session-1")
        stopped_evt = SimpleNamespace(session_id="session-1")

        await extension._azure_event_handler_on_disconnected(disconnect_evt, 1)
        assert extension._transport_recovery_task is not None

        await extension._azure_event_handler_on_session_stopped(stopped_evt, 1)

        extension._handle_reconnect.assert_awaited_once()  # type: ignore[attr-defined]
        assert extension._transport_recovery_task is None

    asyncio.run(run_test())


def test_transport_reconnect_grace_sec_from_params():
    config = AzureASRConfig()
    config.update({"transport_reconnect_grace_sec": 15})
    assert config.transport_reconnect_grace_sec == 15


def test_transport_reconnect_grace_sec_rejects_invalid_values():
    config = AzureASRConfig()

    for value in (0, -1, "invalid", float("nan"), float("inf")):
        try:
            config.update({"transport_reconnect_grace_sec": value})
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid grace value accepted: {value!r}")


def test_stale_session_stopped_is_ignored():
    async def run_test() -> None:
        extension = make_extension()
        extension._recognizer_epoch = 2
        evt = SimpleNamespace(session_id="old-session")

        await extension._azure_event_handler_on_session_stopped(evt, 1)

        extension._handle_reconnect.assert_not_awaited()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_stale_canceled_is_ignored():
    async def run_test() -> None:
        extension = make_extension()
        evt = SimpleNamespace(
            cancellation_details=SimpleNamespace(
                reason="error",
                code="authentication-failure",
                error_details="stale",
            )
        )

        await extension._azure_event_handler_on_canceled(evt, 0)

        extension.send_asr_error.assert_not_awaited()  # type: ignore[attr-defined]
        assert extension.stopped is False

    asyncio.run(run_test())


def test_expected_session_stop_schedules_finalize_reconnect():
    async def run_test() -> None:
        extension = make_extension()
        extension._expected_disconnect = True
        evt = SimpleNamespace(session_id="session-1")

        with patch.object(
            extension, "_schedule_finalize_reconnect"
        ) as schedule_finalize:
            await extension._azure_event_handler_on_session_stopped(evt, 1)

        schedule_finalize.assert_called_once()
        extension._handle_reconnect.assert_not_awaited()  # type: ignore[attr-defined]
        assert extension._expected_disconnect is False

    asyncio.run(run_test())


def test_reconnect_after_finalize_reopens_transport():
    async def run_test() -> None:
        extension = make_extension()
        extension._transport_connected = False
        extension.connected = False
        extension.start_connection = AsyncMock()  # type: ignore[method-assign]

        async def complete_handshake() -> bool:
            extension._transport_connected = True
            extension._transport_handshake_ready.set()
            return True

        extension._wait_for_transport_handshake = AsyncMock(  # type: ignore[method-assign]
            side_effect=complete_handshake
        )

        await extension._reconnect_after_finalize()

        extension.stop_connection.assert_awaited_once()  # type: ignore[attr-defined]
        extension.start_connection.assert_awaited_once()  # type: ignore[attr-defined]
        assert extension.is_connected() is True

    asyncio.run(run_test())


def test_handshake_timeout_returns_false_and_tears_down():
    async def run_test() -> None:
        extension = AzureASRExtension("azure_asr_python")
        extension.ten_env = MagicMock()
        extension.config = AzureASRConfig()
        extension.reconnect_manager = ReconnectManager(
            max_attempts=5, logger=MagicMock()
        )
        extension.on_disconnected = AsyncMock()  # type: ignore[method-assign]
        extension.on_connected = AsyncMock()  # type: ignore[method-assign]
        extension.send_connect_delay_metrics = AsyncMock()  # type: ignore[method-assign]
        extension.send_asr_error = AsyncMock()  # type: ignore[method-assign]
        extension.start_connection = AsyncMock()  # type: ignore[method-assign]
        extension.stop_connection = AsyncMock()  # type: ignore[method-assign]
        extension._handshake_timeout_sec = lambda: 0.05  # type: ignore[method-assign]
        extension._transport_connected = False
        extension._recognizer_epoch = 1

        ok = await extension._handle_reconnect()

        assert ok is False
        extension.start_connection.assert_awaited_once()  # type: ignore[attr-defined]
        extension.stop_connection.assert_awaited_once()  # type: ignore[attr-defined]
        extension.on_disconnected.assert_awaited_once()  # type: ignore[attr-defined]
        disconnect_kwargs = extension.on_disconnected.await_args.kwargs  # type: ignore[attr-defined]
        assert disconnect_kwargs["message"].startswith(
            "Azure transport handshake timed out"
        )

    asyncio.run(run_test())


def test_stale_connected_callback_aborted_after_metrics_await():
    async def run_test() -> None:
        extension = make_extension_with_real_stop()
        extension._recognizer_epoch = 5
        extension.connection_start_timestamp = 0
        evt = SimpleNamespace(session_id="session-5")

        metrics_started = asyncio.Event()
        metrics_release = asyncio.Event()

        async def slow_metrics(_ms: int) -> None:
            metrics_started.set()
            await metrics_release.wait()

        extension.send_connect_delay_metrics = slow_metrics  # type: ignore[method-assign]

        connected_task = asyncio.create_task(
            extension._azure_event_handler_on_connected(evt, 5)
        )
        await metrics_started.wait()
        await extension.stop_connection()
        metrics_release.set()
        await connected_task

        extension.on_connected.assert_not_awaited()  # type: ignore[attr-defined]
        assert extension._transport_connected is False
        assert extension._recognizer_epoch == 6

    asyncio.run(run_test())


def test_handshake_timeout_keeps_transport_recovery_scheduled():
    async def run_test() -> None:
        extension = make_extension(transport_reconnect_grace_sec=0.05)
        extension._transport_connected = False
        extension._handle_reconnect = AsyncMock(return_value=False)  # type: ignore[method-assign]

        schedule_calls = 0
        real_schedule = extension._schedule_transport_recovery

        async def schedule_spy() -> None:
            nonlocal schedule_calls
            schedule_calls += 1
            await real_schedule()

        extension._schedule_transport_recovery = schedule_spy  # type: ignore[method-assign]

        await extension._azure_event_handler_on_disconnected(
            SimpleNamespace(session_id="session-1"), 1
        )
        await asyncio.sleep(0.12)

        extension._handle_reconnect.assert_awaited()  # type: ignore[attr-defined]
        assert schedule_calls >= 2

    asyncio.run(run_test())


def test_session_stopped_does_not_reconnect_during_transport_recovery():
    async def run_test() -> None:
        extension = make_extension()
        extension._transport_recovery_in_flight = True
        evt = SimpleNamespace(session_id="session-1")

        await extension._azure_event_handler_on_session_stopped(evt, 1)

        extension._handle_reconnect.assert_not_awaited()  # type: ignore[attr-defined]
        assert extension.connected is False

    asyncio.run(run_test())


def test_stale_connected_callback_does_not_mark_transport_live():
    async def run_test() -> None:
        extension = make_extension()
        extension._recognizer_epoch = 2
        extension._transport_connected = False
        evt = SimpleNamespace(session_id="old-session")

        await extension._azure_event_handler_on_connected(evt, 1)

        assert extension._transport_connected is False
        extension.on_connected.assert_not_awaited()  # type: ignore[attr-defined]
        extension.reconnect_manager.mark_connection_successful.assert_not_called()  # type: ignore[attr-defined]

    asyncio.run(run_test())


def test_stop_connection_retires_recognizer_epoch():
    async def run_test() -> None:
        extension = make_extension_with_real_stop()
        extension._recognizer_epoch = 4

        await extension.stop_connection()

        assert extension._recognizer_epoch == 5
        assert extension._transport_connected is False
        assert extension._transport_connected_epoch == 0

    asyncio.run(run_test())


def test_handshake_wait_rejects_stale_transport_flag():
    async def run_test() -> None:
        extension = make_extension()
        extension._recognizer_epoch = 3
        extension._transport_connected = True
        extension._transport_connected_epoch = 1
        extension._handshake_timeout_sec = lambda: 0.05  # type: ignore[method-assign]

        ok = await extension._wait_for_transport_handshake(3)

        assert ok is False

    asyncio.run(run_test())


def test_late_old_connected_during_replacement_does_not_complete_handshake():
    async def run_test() -> None:
        extension = make_extension_with_real_stop()
        extension._recognizer_epoch = 1
        extension.connected = True

        await extension.stop_connection()
        assert extension._recognizer_epoch == 2

        extension._recognizer_epoch += 1
        new_epoch = extension._recognizer_epoch
        extension._reset_transport_handshake_state()

        stale_evt = SimpleNamespace(session_id="stale")
        await extension._azure_event_handler_on_connected(stale_evt, 1)

        assert extension._transport_handshake_complete(new_epoch) is False

        fresh_evt = SimpleNamespace(session_id="fresh")
        await extension._azure_event_handler_on_connected(fresh_evt, new_epoch)

        assert extension._transport_handshake_complete(new_epoch) is True

    asyncio.run(run_test())
