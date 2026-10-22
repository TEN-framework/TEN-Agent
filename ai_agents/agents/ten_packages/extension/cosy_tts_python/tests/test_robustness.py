import asyncio
import json
import threading

import pytest
from pytest_ten import TenTestContext, ten_test
from ten_ai_base.struct import TTSFlush, TTSTextInput
from ten_runtime import Data

from .. import cosy_tts
from ..cosy_tts import (
    AsyncIteratorCallback,
    ProviderError,
    SharedPool,
)
from .test_connection_reuse import (
    PROPERTY_JSON,
    SERVER_PORT,
    FakeDashScopeServer,
)


@pytest.fixture
def robustness_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def test_flush_while_pool_startup_is_pending(
    monkeypatch: pytest.MonkeyPatch,
    robustness_server: FakeDashScopeServer,
) -> None:
    startup_started = threading.Event()
    release_startup = threading.Event()
    original_register = SharedPool.register.__func__

    def delayed_register(cls, config):
        startup_started.set()
        assert release_startup.wait(2.0)
        return original_register(cls, config)

    monkeypatch.setattr(
        SharedPool,
        "register",
        classmethod(delayed_register),
    )

    @ten_test(
        "cosy_tts_python",
        property_json_str=PROPERTY_JSON,
        timeout=4.0,
    )
    async def scenario(ctx: TenTestContext) -> None:
        assert await asyncio.to_thread(startup_started.wait, 1.0)
        first = TTSTextInput(
            request_id="startup-flush",
            text="must not be sent",
            text_input_end=False,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json("", first.model_dump_json())
        await ctx.send_data(data)
        # Let the base input queue enter request_tts() and block on startup.
        await asyncio.sleep(0.1)

        flush = Data.create("tts_flush")
        flush.set_property_from_json(
            "",
            TTSFlush(flush_id="startup-flush").model_dump_json(),
        )
        await ctx.send_data(flush)
        interrupted = await ctx.expect_data("tts_audio_end", timeout=0.5)
        payload, error = interrupted.get_property_to_json("")
        assert error is None
        assert json.loads(payload)["reason"] == 2
        await ctx.expect_data("tts_flush_end", timeout=0.5)

        release_startup.set()
        await ctx.assert_no_data("tts_audio_start", timeout=0.2)
        await ctx.assert_no_audio_frame(timeout=0.2)

        next_request = TTSTextInput(
            request_id="after-startup-flush",
            text="next request",
            text_input_end=True,
        )
        next_data = Data.create("tts_text_input")
        next_data.set_property_from_json("", next_request.model_dump_json())
        await ctx.send_data(next_data)

        await ctx.expect_audio_frame(timeout=1.0)
        end = await ctx.expect_data("tts_audio_end", timeout=0.5)
        payload, error = end.get_property_to_json("")
        assert error is None
        assert json.loads(payload)["request_id"] == "after-startup-flush"

    scenario()
    assert robustness_server.task_parameters


def test_transient_pool_start_failure_recovers_on_next_request(
    monkeypatch: pytest.MonkeyPatch,
    robustness_server: FakeDashScopeServer,
) -> None:
    original_register = SharedPool.register.__func__
    calls = 0

    def fail_then_recover(cls, config):
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise TimeoutError("websocket handshake timed out")
        return original_register(cls, config)

    monkeypatch.setattr(
        SharedPool,
        "register",
        classmethod(fail_then_recover),
    )
    monkeypatch.setattr(
        cosy_tts,
        "TTS_STARTUP_RETRY_DELAYS_SECONDS",
        (0.0, 0.0),
    )

    @ten_test(
        "cosy_tts_python",
        property_json_str=PROPERTY_JSON,
        timeout=3.0,
    )
    async def scenario(ctx: TenTestContext) -> None:
        failed = TTSTextInput(
            request_id="startup-failure",
            text="first attempt",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json("", failed.model_dump_json())
        await ctx.send_data(data)

        end = await ctx.expect_data("tts_audio_end", timeout=0.5)
        payload, error = end.get_property_to_json("")
        assert error is None
        assert json.loads(payload)["reason"] == 3
        error_data = await ctx.expect_data("error", timeout=0.5)
        error_payload, error = error_data.get_property_to_json("")
        assert error is None
        assert (
            json.loads(error_payload)["vendor_info"]["code"] == "TimeoutError"
        )

        recovered = TTSTextInput(
            request_id="startup-recovered",
            text="second attempt",
            text_input_end=True,
        )
        recovered_data = Data.create("tts_text_input")
        recovered_data.set_property_from_json(
            "",
            recovered.model_dump_json(),
        )
        await ctx.send_data(recovered_data)

        await ctx.expect_audio_frame(timeout=1.0)
        end = await ctx.expect_data("tts_audio_end", timeout=0.5)
        payload, error = end.get_property_to_json("")
        assert error is None
        assert json.loads(payload)["request_id"] == "startup-recovered"

    scenario()
    assert calls == 4


@pytest.mark.asyncio
async def test_stale_callback_is_dropped_after_cancel() -> None:
    queue: asyncio.Queue = asyncio.Queue()
    callback = AsyncIteratorCallback(
        ten_env=None,  # type: ignore[arg-type]
        queue=queue,
        loop=asyncio.get_running_loop(),
        request_id="stale-request",
        sample_rate=16000,
        words_enabled=False,
    )
    callback.bind_task("stale-task")
    callback.cancel()

    callback.on_data(b"\x01\x00" * 10)
    callback.on_error(
        json.dumps(
            {
                "header": {
                    "task_id": "stale-task",
                    "error_code": "late-error",
                    "error_message": "late",
                }
            }
        )
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_socket_close_releases_completion_waiter() -> None:
    completion_event = threading.Event()
    callback = AsyncIteratorCallback(
        ten_env=None,  # type: ignore[arg-type]
        queue=asyncio.Queue(),
        loop=asyncio.get_running_loop(),
        request_id="closed-request",
        sample_rate=16000,
        words_enabled=False,
    )
    callback.bind_task("closed-task")
    callback.bind_completion_event(completion_event)

    callback.on_close()

    assert completion_event.is_set()
    assert callback.error == ProviderError(
        code="ConnectionClosed",
        message="connection closed before task-finished",
        task_id="closed-task",
    )


@pytest.mark.asyncio
async def test_cancelled_callback_disables_old_transport_callbacks() -> None:
    callback = AsyncIteratorCallback(
        ten_env=None,  # type: ignore[arg-type]
        queue=asyncio.Queue(),
        loop=asyncio.get_running_loop(),
        request_id="old-request",
        sample_rate=16000,
        words_enabled=False,
    )
    callback.cancel()

    assert callback.cancelled is True
    callback.on_complete()
    callback.on_close()
    assert callback.error is None
