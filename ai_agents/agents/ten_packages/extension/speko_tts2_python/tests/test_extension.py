from unittest.mock import AsyncMock, MagicMock

import pytest
from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput

from speko_tts2_python.client import SpekoRouterError
from speko_tts2_python.config import SpekoTTS2Config
from speko_tts2_python.extension import SpekoTTS2Extension


def make_extension():
    extension = SpekoTTS2Extension("speko")
    extension.config = SpekoTTS2Config(api_key="test-key")
    extension.ten_env = MagicMock()
    for name in (
        "on_disconnected",
        "send_tts_audio_start",
        "send_tts_audio_end",
        "send_tts_error",
        "send_usage_metrics",
        "_flush_recorder",
    ):
        setattr(extension, name, AsyncMock())
    # Wrap the actual base method to verify it releases the request slot.
    extension.finish_request = AsyncMock(wraps=extension.finish_request)
    return extension


def text(value="hello", request_id="req", final=False):
    return TTSTextInput(text=value, request_id=request_id, text_input_end=final)


@pytest.mark.asyncio
async def test_intermediate_error_keeps_request_open_and_next_chunk_runs():
    extension = make_extension()
    extension._processing_request_id = "req"
    client = MagicMock()
    client.close = AsyncMock()

    async def fail_once(*_):
        extension.client = client
        raise SpekoRouterError("provider_error", "temporary", retryable=True)

    extension._stream_text = AsyncMock(side_effect=fail_once)
    await extension.request_tts(text())
    extension.finish_request.assert_not_awaited()
    extension.send_tts_audio_end.assert_not_awaited()
    assert extension._processing_request_id == "req"
    client.close.assert_awaited_once_with(drain=False)
    extension._stream_text.side_effect = None
    await extension.request_tts(text(" next", final=True))
    extension._stream_text.assert_awaited_with(" next", "req")
    extension.finish_request.assert_awaited_once()
    assert extension._processing_request_id is None


@pytest.mark.asyncio
async def test_close_error_emits_error_end_and_releases_next_request():
    extension = make_extension()
    await extension._begin_request(text())
    extension._processing_request_id = "req"
    client = MagicMock(usage={"characters": 5})
    client.close = AsyncMock(
        side_effect=SpekoRouterError(
            "provider_error", "settlement failed", retryable=True
        )
    )
    extension.client = client
    await extension._finalize_request(TTSAudioEndReason.REQUEST_END)
    extension.send_tts_audio_end.assert_awaited_once()
    assert (
        extension.send_tts_audio_end.await_args.kwargs["reason"]
        == TTSAudioEndReason.ERROR
    )
    assert extension.send_usage_metrics.await_args.kwargs["extra_metadata"][
        "router_usage"
    ] == {"characters": 5}
    extension._flush_recorder.assert_awaited_once_with("req")
    extension.finish_request.assert_awaited_once()
    assert extension._processing_request_id is None
    assert extension.client is None
    await extension._finalize_request(TTSAudioEndReason.REQUEST_END)
    extension.finish_request.assert_awaited_once()
    extension._stream_text = AsyncMock()
    await extension.request_tts(text("next", "next", True))
    assert extension.finish_request.await_count == 2


@pytest.mark.asyncio
async def test_final_chunk_error_finishes_once():
    extension = make_extension()
    extension._stream_text = AsyncMock(side_effect=OSError("closed"))
    await extension.request_tts(text(final=True))
    extension.finish_request.assert_awaited_once()
    assert (
        extension.finish_request.await_args.kwargs["reason"]
        == TTSAudioEndReason.ERROR
    )


@pytest.mark.asyncio
async def test_whitespace_and_output_metrics():
    extension = make_extension()
    client = MagicMock()

    async def stream(value):
        sent.append(value)
        if False:
            yield

    sent = []
    client.stream_text = stream
    extension._ensure_client = AsyncMock(return_value=client)
    extension.metrics_add_output_characters = MagicMock()
    extension.metrics_add_input_characters = MagicMock()
    for value in ("hello", " ", " world "):
        await extension.request_tts(text(value))
    assert sent == ["hello", " ", " world "]
    assert (
        sum(
            call.args[0]
            for call in extension.metrics_add_output_characters.call_args_list
        )
        == 13
    )
    extension.metrics_add_input_characters.assert_not_called()


@pytest.mark.asyncio
async def test_permanent_denial_does_not_reopen_client():
    extension = make_extension()
    extension._stream_text = AsyncMock(
        side_effect=SpekoRouterError("insufficient_credit", "no credit")
    )
    await extension.request_tts(text())
    await extension.request_tts(text("next", final=True))
    assert extension._stream_text.await_count == 1
    extension.finish_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_cleanup_even_if_client_fails():
    extension = make_extension()
    await extension._begin_request(text())
    client = MagicMock()
    client.cancel = AsyncMock(side_effect=OSError("closed"))
    extension.client = client
    await extension.cancel_tts()
    assert extension.client is None
    extension._flush_recorder.assert_awaited_once_with("req")
    assert (
        extension.send_tts_audio_end.await_args.kwargs["reason"]
        == TTSAudioEndReason.INTERRUPTED
    )
    extension.finish_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_recorder_failure_still_releases_request():
    extension = make_extension()
    await extension._begin_request(text())
    extension._processing_request_id = "req"
    extension._flush_recorder.side_effect = OSError("disk")
    with pytest.raises(OSError):
        await extension._finalize_request(TTSAudioEndReason.REQUEST_END)
    extension.finish_request.assert_awaited_once()
    assert extension._processing_request_id is None


def test_vendor_metadata():
    extension = make_extension()
    assert extension.vendor_metadata()["key"] == "test-key"
    assert extension.vendor_metadata()["api_key"] == "test-key"
    assert extension.vendor_metadata()["language"] == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["provider_error", "relay_error", "invalid_request"]
)
async def test_nonretryable_chunk_error_allows_new_text_without_replay(code):
    extension = make_extension()
    extension._stream_text = AsyncMock(
        side_effect=SpekoRouterError(code, "chunk failed", retryable=False)
    )
    await extension.request_tts(text(" "))
    extension.finish_request.assert_not_awaited()
    extension._stream_text.side_effect = None
    await extension.request_tts(text("valid next chunk", final=True))
    assert [
        call.args[0] for call in extension._stream_text.await_args_list
    ] == [" ", "valid next chunk"]
    extension.send_tts_error.assert_awaited_once()
    await extension.request_tts(text("new", "next", True))
    extension._stream_text.assert_awaited_with("new", "next")
    assert extension.finish_request.await_count == 2


@pytest.mark.asyncio
async def test_flush_during_close_emits_only_interruption():
    import asyncio

    extension = make_extension()
    await extension._begin_request(text())
    entered = asyncio.Event()

    async def close():
        entered.set()
        await asyncio.Future()

    client = MagicMock(usage={})
    client.close = AsyncMock(side_effect=close)
    client.cancel = AsyncMock()
    extension.client = client
    finalizing = asyncio.create_task(
        extension._finalize_request(TTSAudioEndReason.REQUEST_END)
    )
    await entered.wait()
    finalizing.cancel()
    await extension.cancel_tts()
    with pytest.raises(asyncio.CancelledError):
        await finalizing
    extension.send_tts_audio_end.assert_awaited_once()
    assert (
        extension.send_tts_audio_end.await_args.kwargs["reason"]
        == TTSAudioEndReason.INTERRUPTED
    )
    extension._flush_recorder.assert_awaited_once_with("req")
    extension.finish_request.assert_not_awaited()


def test_explicit_route_removes_merged_auto_objective():
    config = SpekoTTS2Config(
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
async def test_shutdown_joins_reentrant_cancel_without_duplicate_end():
    import asyncio

    extension = make_extension()
    await extension._begin_request(text())
    entered = asyncio.Event()

    async def cancel():
        entered.set()
        await asyncio.Future()

    client = MagicMock(cancel=AsyncMock(side_effect=cancel))
    extension.client = client
    cancelling = asyncio.create_task(extension.cancel_tts())
    await entered.wait()
    extension._stopped = True
    await extension.cancel_tts()
    cancelling.cancel()
    await cancelling
    client.cancel.assert_awaited_once()
    extension._flush_recorder.assert_awaited_once_with("req")
    extension.send_tts_audio_end.assert_not_awaited()


@pytest.mark.asyncio
async def test_old_close_does_not_clear_a_new_requests_client_or_usage():
    import asyncio

    extension = make_extension()
    extension.current_request_id = "old"
    entered, release = asyncio.Event(), asyncio.Event()

    async def close():
        entered.set()
        await release.wait()

    extension.client = MagicMock(
        close=AsyncMock(side_effect=close), usage={"characters": 1}
    )
    closing = asyncio.create_task(extension._close_client())
    await entered.wait()
    replacement = MagicMock()
    extension.client = replacement
    extension.current_request_id = "new"
    extension._router_usage = {"characters": 2}
    release.set()
    await closing
    assert extension.client is replacement
    assert extension._router_usage == {"characters": 2}
    extension.on_disconnected.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("late_error", [False, True])
async def test_base_flush_cancels_active_stream_and_allows_next_request(
    late_error,
):
    import asyncio
    from ten_ai_base.tts2 import RequestState

    extension = make_extension()
    extension._processing_request_id = "req"
    extension.request_states["req"] = RequestState.PROCESSING
    started = asyncio.Event()
    cancelled = asyncio.Event()
    client = MagicMock()
    client.cancel = AsyncMock()

    async def stream(*_):
        extension.client = client
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            if late_error:
                # A receive can complete concurrently with task cancellation.
                raise OSError("socket closed during flush") from None
            raise
        finally:
            cancelled.set()

    extension._stream_text = AsyncMock(side_effect=stream)
    request = asyncio.create_task(extension.request_tts(text()))
    await started.wait()
    await extension._flush_input_items()
    if late_error:
        await request
    else:
        with pytest.raises(asyncio.CancelledError):
            await request
    assert cancelled.is_set()
    assert extension.current_task is None
    assert extension._processing_request_id is None
    extension.send_tts_error.assert_not_awaited()
    extension.finish_request.assert_not_awaited()
    extension.send_tts_audio_end.assert_awaited_once()
    assert (
        extension.send_tts_audio_end.await_args.kwargs["reason"]
        == TTSAudioEndReason.INTERRUPTED
    )
    client.cancel.assert_awaited_once()

    extension._stream_text.side_effect = None
    await extension.request_tts(text("next", "next", True))
    extension.finish_request.assert_awaited_once()
