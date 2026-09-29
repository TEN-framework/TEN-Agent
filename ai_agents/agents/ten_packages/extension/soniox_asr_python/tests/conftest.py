#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
import threading
from types import SimpleNamespace
from typing import Callable, Any, Awaitable
from unittest.mock import AsyncMock, MagicMock, patch
from typing_extensions import override

import pytest
from ten_runtime import App, TenEnv


class FakeApp(App):
    def __init__(self):
        super().__init__()
        self.event: threading.Event | None = None

    # In the case of a fake app, we use `on_init` to allow the blocked testing
    # fixture to continue execution, rather than using `on_configure`. The
    # reason is that in the TEN runtime C core, the relationship between the
    # addon manager and the (fake) app is bound after `on_configure_done` is
    # called. So we only need to let the testing fixture continue execution
    # after this action in the TEN runtime C core, and at the upper layer
    # timing, the earliest point is within the `on_init()` function of the upper
    # TEN app. Therefore, we release the testing fixture lock within the user
    # layer's `on_init()` of the TEN app.
    @override
    def on_init(self, ten_env: TenEnv) -> None:
        assert self.event
        self.event.set()

        ten_env.on_init_done()

    @override
    def on_configure(self, ten_env: TenEnv) -> None:
        ten_env.init_property_from_json(
            json.dumps(
                {
                    "ten": {
                        "log": {
                            "handlers": [
                                {
                                    "matchers": [{"level": "debug"}],
                                    "formatter": {
                                        "type": "plain",
                                        "colored": True,
                                    },
                                    "emitter": {
                                        "type": "console",
                                        "config": {"stream": "stdout"},
                                    },
                                }
                            ]
                        }
                    }
                }
            ),
        )

        ten_env.on_configure_done()


class FakeAppCtx:
    def __init__(self, event: threading.Event):
        self.fake_app: FakeApp | None = None
        self.event = event


def run_fake_app(fake_app_ctx: FakeAppCtx):
    app = FakeApp()
    app.event = fake_app_ctx.event
    fake_app_ctx.fake_app = app
    app.run(False)


@pytest.fixture(scope="session", autouse=True)
def global_setup_and_teardown():
    event = threading.Event()
    fake_app_ctx = FakeAppCtx(event)

    fake_app_thread = threading.Thread(
        target=run_fake_app, args=(fake_app_ctx,)
    )
    fake_app_thread.start()

    event.wait()

    assert fake_app_ctx.fake_app is not None

    # Yield control to the test; after the test execution is complete, continue
    # with the teardown process.
    yield

    # Teardown part.
    fake_app_ctx.fake_app.close()
    fake_app_thread.join()


def create_fake_websocket_mocks(
    patch_soniox_ws,
    on_connect: Callable[[], Awaitable[None]] | None = None,
    on_send_audio: Callable[[bytes], Awaitable[None]] | None = None,
    on_finalize: Callable[[int | None], Awaitable[None]] | None = None,
    on_stop: Callable[[], Awaitable[None]] | None = None,
) -> dict[str, Callable]:
    """
    Factory function to create standard websocket mock behaviors.

    Args:
        patch_soniox_ws: The patch_soniox_ws fixture
        on_connect: Optional custom connect behavior
        on_send_audio: Optional custom send_audio behavior
        on_finalize: Optional custom finalize behavior
        on_stop: Optional custom stop behavior

    Returns:
        Dictionary with 'fake_connect', 'fake_send_audio', 'fake_finalize', 'fake_stop' keys
    """

    async def default_fake_connect():
        import time

        connection_start_timestamp = int(time.time() * 1000)
        await patch_soniox_ws.websocket_client.trigger_open(
            connection_start_timestamp
        )
        await asyncio.sleep(0.1)

    async def default_fake_send_audio(_audio_data: bytes):
        await asyncio.sleep(0)

    async def default_fake_finalize(
        trailing_silence_ms: int | None = None,
        before_send_callback: Callable[[], Awaitable[None]] | None = None,
    ):
        if before_send_callback:
            await before_send_callback()
        await asyncio.sleep(0)

    async def default_fake_stop():
        await asyncio.sleep(0)

    return {
        "fake_connect": on_connect or default_fake_connect,
        "fake_send_audio": on_send_audio or default_fake_send_audio,
        "fake_finalize": on_finalize or default_fake_finalize,
        "fake_stop": on_stop or default_fake_stop,
    }


def inject_websocket_mocks(patch_soniox_ws, mocks: dict[str, Callable]) -> None:
    """
    Inject mock behaviors into the websocket client.

    Args:
        patch_soniox_ws: The patch_soniox_ws fixture
        mocks: Dictionary with mock functions from create_fake_websocket_mocks
    """
    patch_soniox_ws.websocket_client.connect.side_effect = mocks["fake_connect"]
    patch_soniox_ws.websocket_client.send_audio.side_effect = mocks[
        "fake_send_audio"
    ]
    patch_soniox_ws.websocket_client.finalize.side_effect = mocks[
        "fake_finalize"
    ]
    patch_soniox_ws.websocket_client.stop.side_effect = mocks["fake_stop"]


@pytest.fixture(scope="function")
def patch_soniox_ws():
    # Use relative import from tests directory perspective
    patch_target = "soniox_asr_python.extension.SonioxWebsocketClient"

    with patch(patch_target) as MockWebsocketClient:
        websocket_client_instance = MagicMock()

        # Store callbacks registered via on() method
        websocket_client_instance._callbacks = {}

        def mock_on(event, callback):
            # Handle both enum values and string values
            event_key = event.value if hasattr(event, "value") else event
            websocket_client_instance._callbacks[event_key] = callback

        websocket_client_instance.on = mock_on

        # Mock async methods with AsyncMock
        websocket_client_instance.connect = AsyncMock()
        websocket_client_instance.send_audio = AsyncMock()
        websocket_client_instance.finalize = AsyncMock()
        websocket_client_instance.stop = AsyncMock()

        # Add helper methods that can be called by tests to trigger events
        async def trigger_open(connection_start_timestamp: int = 0):
            if "open" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["open"](
                    connection_start_timestamp
                )

        async def trigger_close(code: int = 0, message: str = "closed"):
            if "close" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["close"](
                    code, message
                )

        async def trigger_transcript(
            tokens, final_audio_proc_ms, total_audio_proc_ms
        ):
            if "transcript" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["transcript"](
                    tokens, final_audio_proc_ms, total_audio_proc_ms
                )

        async def trigger_error(
            error_code,
            error_message,
            request_id=None,
            error_type=None,
        ):
            if "error" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["error"](
                    error_code,
                    error_message,
                    request_id,
                    error_type,
                )

        async def trigger_exception(exception):
            if "exception" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["exception"](
                    exception
                )

        async def trigger_finished(final_audio_proc_ms, total_audio_proc_ms):
            if "finished" in websocket_client_instance._callbacks:
                await websocket_client_instance._callbacks["finished"](
                    final_audio_proc_ms, total_audio_proc_ms
                )

        websocket_client_instance.trigger_open = trigger_open
        websocket_client_instance.trigger_close = trigger_close
        websocket_client_instance.trigger_transcript = trigger_transcript
        websocket_client_instance.trigger_error = trigger_error
        websocket_client_instance.trigger_exception = trigger_exception
        websocket_client_instance.trigger_finished = trigger_finished

        MockWebsocketClient.return_value = websocket_client_instance

        fixture_obj = SimpleNamespace(
            websocket_client=websocket_client_instance,
        )

        yield fixture_obj
