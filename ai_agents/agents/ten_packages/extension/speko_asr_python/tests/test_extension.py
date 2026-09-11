from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from speko_asr_python.client import SpekoRouterError
from speko_asr_python.config import SpekoASRConfig
from speko_asr_python.extension import SpekoASRExtension


def make_extension():
    extension = SpekoASRExtension("speko")
    extension.config = SpekoASRConfig(api_key="test-key")
    extension.ten_env = MagicMock()
    for name in (
        "send_asr_result",
        "send_asr_error",
        "send_asr_finalize_end",
        "on_disconnected",
        "send_vendor_metrics",
    ):
        setattr(extension, name, AsyncMock())
    client = MagicMock(is_ready=True)
    client.send_audio = AsyncMock()
    client.commit = AsyncMock()
    client.close = AsyncMock()
    extension.client = client
    return extension, client


def frame():
    audio = MagicMock()
    audio.lock_buf.return_value = bytes(32000)
    audio.get_buf.return_value = bytes(32000)
    audio.get_property_to_json.return_value = (None, None)
    return audio


@pytest.mark.asyncio
async def test_multiple_turns_have_separate_duration_and_session_positions():
    extension, _ = make_extension()
    for _ in range(2):
        assert await extension.send_audio(frame(), "session")
        await extension._on_router_event(
            {"type": "transcript.final", "text": "hello"}
        )
        await extension.finalize("session")
    results = [
        call.args[0] for call in extension.send_asr_result.await_args_list
    ]
    assert [(result.start_ms, result.duration_ms) for result in results] == [
        (0, 1000),
        (1000, 1000),
    ]
    assert extension._total_audio_bytes == 0
    assert extension.send_asr_finalize_end.await_count == 2


@pytest.mark.asyncio
async def test_timeout_disconnects_and_completes_finalize_once():
    extension, client = make_extension()
    client.commit.side_effect = SpekoRouterError(
        "request_timeout", "timeout", retryable=True
    )
    await extension.finalize("session")
    client.close.assert_awaited_once()
    assert extension.client is None
    extension.send_asr_finalize_end.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_failure_recovers_for_next_frame_without_replay():
    extension, client = make_extension()
    client.send_audio.side_effect = OSError("closed")
    audio = frame()
    assert not await extension.send_audio(audio, "session")
    audio.unlock_buf.assert_called_once()
    client.send_audio.assert_awaited_once()
    assert extension.client is None
    replacement = MagicMock(is_ready=True, send_audio=AsyncMock())

    async def reconnect():
        extension.client = replacement

    extension.start_connection = AsyncMock(side_effect=reconnect)
    await extension.on_audio_frame(extension.ten_env, frame())
    await extension._reconnect_task
    await extension._handle_audio_frame(
        extension.ten_env, await extension.audio_frames_queue.get()
    )
    extension.start_connection.assert_awaited_once()
    replacement.send_audio.assert_awaited_once()


@pytest.mark.asyncio
async def test_permanent_denial_does_not_reconnect():
    extension, client = make_extension()
    client.send_audio.side_effect = SpekoRouterError(
        "insufficient_credit", "no credit"
    )
    assert not await extension.send_audio(frame(), "session")
    extension.start_connection = AsyncMock()
    assert not await extension.send_audio(frame(), "session")
    extension.start_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_terminal_usage_is_forwarded():
    extension, _ = make_extension()
    await extension._on_router_event(
        {"type": "session.closed", "usage": {"audio_seconds": 2}}
    )
    extension.send_vendor_metrics.assert_awaited_once_with(
        {"usage": {"audio_seconds": 2}}
    )


@pytest.mark.asyncio
async def test_deinit_stops_dumper_once_even_after_connection_failure():
    extension, client = make_extension()
    dumper = MagicMock(stop=AsyncMock())
    extension.audio_dumper = dumper
    client.close.side_effect = OSError("closed")
    with patch(
        "speko_asr_python.extension.AsyncASRBaseExtension.on_deinit",
        new_callable=AsyncMock,
    ):
        with pytest.raises(OSError):
            await extension.on_deinit(extension.ten_env)
        await extension.on_deinit(extension.ten_env)
    dumper.stop.assert_awaited_once()
    assert extension.audio_dumper is None


def test_metadata_contains_key_and_language():
    extension, _ = make_extension()
    assert extension.vendor_metadata()["key"] == "test-key"
    assert extension.vendor_metadata()["api_key"] == "test-key"
    assert extension.vendor_metadata()["language"]


@pytest.mark.asyncio
async def test_finalize_cancelled_by_shutdown_does_not_emit_after_stop():
    import asyncio

    extension, client = make_extension()
    entered = asyncio.Event()

    async def commit():
        entered.set()
        await asyncio.Future()

    client.commit.side_effect = commit
    task = asyncio.create_task(extension.finalize("session"))
    await entered.wait()
    extension.stopped = True
    task.cancel()
    await task
    extension.send_asr_finalize_end.assert_not_awaited()


@pytest.mark.asyncio
async def test_audio_ingress_does_not_wait_for_reconnection_and_stop_joins_it():
    import asyncio

    extension, _ = make_extension()
    extension.client = None
    entered = asyncio.Event()

    async def connect():
        entered.set()
        await asyncio.Future()

    extension._ensure_connection = AsyncMock(side_effect=connect)
    await asyncio.wait_for(
        extension.on_audio_frame(extension.ten_env, frame()), 0.1
    )
    await entered.wait()
    pending = extension._reconnect_task
    await extension.on_audio_frame(extension.ten_env, frame())
    assert extension._reconnect_task is pending
    await extension.stop_connection()
    assert pending.done()
    assert extension._reconnect_task is None


def test_explicit_route_removes_merged_auto_objective():
    config = SpekoASRConfig(
        api_key="test-key",
        params={
            "routing": {
                "mode": "explicit",
                "objective": "balanced",
                "provider": "deepgram",
                "model": "nova-3",
            }
        },
    )
    config.update_params()
    assert config.routing == {
        "mode": "explicit",
        "provider": "deepgram",
        "model": "nova-3",
    }


@pytest.mark.asyncio
async def test_connection_ready_requeues_early_audio_before_live_frames():
    extension, client = make_extension()
    extension.on_connected = AsyncMock()
    extension.send_connect_delay_metrics = AsyncMock()
    client.is_ready = False
    early = frame()
    await extension._handle_audio_frame(extension.ten_env, early)
    live = frame()
    extension.audio_frames_queue.put_nowait(live)
    client.is_ready = True
    await extension._on_router_event({"type": "session.ready", "route": {}})
    assert extension.buffered_frames.empty()
    assert extension.buffered_frames_size == 0
    assert extension.audio_frames_queue.get_nowait() is early
    assert extension.audio_frames_queue.get_nowait() is live


@pytest.mark.asyncio
async def test_audio_during_initial_connection_does_not_schedule_retry():
    extension, _ = make_extension()
    extension.client = None
    extension._connection_machine.try_connecting()
    await extension.on_audio_frame(extension.ten_env, frame())
    assert extension._reconnect_task is None
    assert extension.audio_frames_queue.qsize() == 1


@pytest.mark.asyncio
async def test_reconnect_waits_for_failed_session_cleanup():
    import asyncio

    extension, client = make_extension()
    entered, release = asyncio.Event(), asyncio.Event()

    async def close():
        entered.set()
        await release.wait()

    client.close.side_effect = close
    resetting = asyncio.create_task(
        extension._reset_connection(
            SpekoRouterError("relay_error", "broken", retryable=True)
        )
    )
    await entered.wait()

    async def reconnect():
        extension.client = MagicMock(is_ready=True)

    extension.start_connection = AsyncMock(side_effect=reconnect)
    await extension.on_audio_frame(extension.ten_env, frame())
    await asyncio.sleep(0)
    extension.start_connection.assert_not_awaited()
    release.set()
    await resetting
    await extension._reconnect_task
    extension.start_connection.assert_awaited_once()
