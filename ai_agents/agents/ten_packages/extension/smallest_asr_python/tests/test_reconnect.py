import asyncio
import threading
from types import SimpleNamespace
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)
import json

# We must import it, which means this test fixture will be automatically executed
from .mock import patch_smallest_ws  # noqa: F401


class SmallestAsrExtensionTester(AsyncExtensionTester):

    def __init__(self):
        super().__init__()
        self.recv_error_count = 0

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        pass

    def stop_test_if_checking_failed(
        self,
        ten_env_tester: AsyncTenEnvTester,
        success: bool,
        error_message: str,
    ) -> None:
        if not success:
            err = TenError.create(
                error_code=TenErrorCode.ErrorCodeGeneric,
                error_message=error_message,
            )
            ten_env_tester.stop_test(err)

    @override
    async def on_data(
        self, ten_env_tester: AsyncTenEnvTester, data: Data
    ) -> None:
        data_name = data.get_name()
        if data_name == "error":
            self.recv_error_count += 1
        elif data_name == "asr_result":
            self.stop_test_if_checking_failed(
                ten_env_tester,
                self.recv_error_count == 3,
                f"recv_error_count is not 3: {self.recv_error_count}",
            )
            ten_env_tester.stop_test()


# For the first three start_connection calls, ws_connect will raise an exception.
# On the fourth start_connection call, a successful transcript will be received.
def test_reconnect(patch_smallest_ws):
    start_connection_attempts = 0

    def trigger_transcript_messages():
        """Add WebSocket messages to simulate successful Smallest AI Pulse API response."""
        transcript_message = {
            "type": "transcription",
            "transcript": "hello world",
            "is_final": True,
            "language": "en",
        }

        msg = patch_smallest_ws.MockWebSocketMessage(
            msg_type=patch_smallest_ws.WSMsgType.TEXT,
            data=json.dumps(transcript_message),
        )
        patch_smallest_ws.add_message(msg)

    # Create a new session class that tracks attempts
    from unittest.mock import patch

    class MockSessionWithTracking:
        def __init__(self, *args, **kwargs) -> None:
            self.closed: bool = False

        async def ws_connect(self, url, headers=None, timeout=None):
            nonlocal start_connection_attempts
            start_connection_attempts += 1

            if start_connection_attempts <= 3:
                # Fail the first 3 connection attempts by raising an exception
                raise Exception("WebSocket connection error")

            # On 4th attempt, allow connection to succeed
            # Reset closed state and exception for successful connection
            patch_smallest_ws.prepare_connection()

            # Schedule transcript message after a short delay
            def delayed_transcript():
                import time

                time.sleep(0.5)
                trigger_transcript_messages()

            sender_thread = threading.Thread(
                target=delayed_transcript, daemon=True
            )
            sender_thread.start()
            return patch_smallest_ws.ws

        async def close(self) -> None:
            self.closed = True

    # Patch the ClientSession for the duration of the test
    with patch(
        "ten_packages.extension.smallest_asr_python.extension.aiohttp.ClientSession",
        MockSessionWithTracking,
    ):
        property_json = {
            "params": {
                "api_key": "fake_api_key",
                "sample_rate": 16000,
            }
        }

        tester = SmallestAsrExtensionTester()
        tester.set_test_mode_single(
            "smallest_asr_python", json.dumps(property_json)
        )
        err = tester.run()
        assert (
            err is None
        ), f"test_reconnect err code: {err.error_code()} message: {err.error_message()}"


class SmallestAsrReconnectAfterCloseTester(AsyncExtensionTester):
    """Expects: one error (the mid-session close) then a transcript after the
    reconnect. Fails via a timeout if the transcript never arrives."""

    def __init__(self):
        super().__init__()
        self.recv_error_count = 0
        self.test_timeout_task: asyncio.Task | None = None

    async def _timeout(self, ten_env_tester: AsyncTenEnvTester) -> None:
        await asyncio.sleep(10.0)
        err = TenError.create(
            error_code=TenErrorCode.ErrorCodeGeneric,
            error_message=(
                "no asr_result after ws close; reconnect likely cancelled "
                f"itself (recv_error_count={self.recv_error_count})"
            ),
        )
        ten_env_tester.stop_test(err)

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.test_timeout_task = asyncio.create_task(
            self._timeout(ten_env_tester)
        )

    @override
    async def on_data(
        self, ten_env_tester: AsyncTenEnvTester, data: Data
    ) -> None:
        data_name = data.get_name()
        if data_name == "error":
            self.recv_error_count += 1
        elif data_name == "asr_result":
            # The reconnect (attempt 2) succeeded and delivered a transcript.
            # There must have been exactly one preceding close error.
            if self.recv_error_count < 1:
                err = TenError.create(
                    error_code=TenErrorCode.ErrorCodeGeneric,
                    error_message=(
                        "asr_result arrived without a preceding close error: "
                        f"{self.recv_error_count}"
                    ),
                )
                ten_env_tester.stop_test(err)
                return
            if self.test_timeout_task:
                self.test_timeout_task.cancel()
            ten_env_tester.stop_test()

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        if self.test_timeout_task:
            self.test_timeout_task.cancel()
            try:
                await self.test_timeout_task
            except asyncio.CancelledError:
                pass


# The first connection succeeds, then the vendor drops the socket mid-session
# (a CLOSED frame). The reconnect must succeed and deliver a transcript.
# Regression test for the self-cancellation bug: `_process_messages` runs
# inside `_message_task`, and awaiting the reconnect there let
# `stop_connection()` cancel that same task, so `start_connection()` never
# spawned a new message task and the post-drop transcript never arrived.
def test_reconnect_after_ws_close(patch_smallest_ws):
    connect_attempts = 0

    transcript_message = {
        "type": "transcription",
        "transcript": "hello world",
        "is_final": True,
        "language": "en",
    }

    def push(msg_type, data=None):
        patch_smallest_ws.add_message(
            patch_smallest_ws.MockWebSocketMessage(msg_type=msg_type, data=data)
        )

    def push_after(delay, msg_type, data=None):
        def _run():
            import time

            time.sleep(delay)
            push(msg_type, data)

        threading.Thread(target=_run, daemon=True).start()

    from unittest.mock import patch

    class MockSessionMidClose:
        def __init__(self, *args, **kwargs) -> None:
            self.closed: bool = False

        async def ws_connect(self, url, headers=None, timeout=None):
            nonlocal connect_attempts
            connect_attempts += 1

            ws = patch_smallest_ws.prepare_connection()

            if connect_attempts == 1:
                # Simulate the vendor dropping the socket mid-session.
                push_after(0.3, patch_smallest_ws.WSMsgType.CLOSED)
            else:
                # After reconnect, deliver a real transcript.
                push_after(
                    0.3,
                    patch_smallest_ws.WSMsgType.TEXT,
                    json.dumps(transcript_message),
                )
            return ws

        async def close(self) -> None:
            self.closed = True

    with patch(
        "ten_packages.extension.smallest_asr_python.extension.aiohttp.ClientSession",
        MockSessionMidClose,
    ):
        property_json = {
            "params": {
                "api_key": "fake_api_key",
                "sample_rate": 16000,
            }
        }

        tester = SmallestAsrReconnectAfterCloseTester()
        tester.set_test_mode_single(
            "smallest_asr_python", json.dumps(property_json)
        )
        err = tester.run()
        assert (
            err is None
        ), f"test_reconnect_after_ws_close err code: {err.error_code()} message: {err.error_message()}"
        assert (
            connect_attempts >= 2
        ), f"expected a reconnect (>=2 connects), got {connect_attempts}"
