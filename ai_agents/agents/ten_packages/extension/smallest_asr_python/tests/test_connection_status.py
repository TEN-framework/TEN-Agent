import json
import threading
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    TenError,
    TenErrorCode,
)

# We must import it, which means this test fixture will be automatically executed
from .mock import patch_smallest_ws  # noqa: F401


class SmallestAsrConnectionStatusTester(AsyncExtensionTester):
    """Collects every `connection_status_changed` transition observed."""

    def __init__(self):
        super().__init__()
        self.transitions: list[dict] = []

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
        if data.get_name() != "connection_status_changed":
            return
        data_json, _ = data.get_property_to_json()
        self.transitions.append(json.loads(data_json))


# The handshake succeeds, so `on_connected()` must fire immediately after
# `ws_connect()` returns — the base class only emits CONNECTING before
# `start_connection()` runs, so without this the reported status would stay
# stuck on "connecting" even though the socket is already usable.
def test_connection_status_reports_connected_after_handshake(
    patch_smallest_ws,
):
    def trigger_transcript_message():
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

    class ConnectedTester(SmallestAsrConnectionStatusTester):
        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            await super().on_data(ten_env_tester, data)
            if any(t.get("current") == "connected" for t in self.transitions):
                ten_env_tester.stop_test()

    def delayed_message_sender():
        import time

        time.sleep(0.5)
        trigger_transcript_message()

    threading.Thread(target=delayed_message_sender, daemon=True).start()

    property_json = {
        "params": {"api_key": "fake_api_key", "sample_rate": 16000}
    }

    tester = ConnectedTester()
    tester.set_test_mode_single(
        "smallest_asr_python", json.dumps(property_json)
    )
    err = tester.run()
    assert err is None, (
        f"test_connection_status_reports_connected_after_handshake err "
        f"code: {err.error_code()} message: {err.error_message()}"
    )
    assert any(
        t.get("current") == "connected" for t in tester.transitions
    ), f"never observed a 'connected' transition: {tester.transitions}"


# aiohttp consumes CLOSE/CLOSING/CLOSED frames in __anext__ and ends iteration
# via StopAsyncIteration. The extension must report "disconnected" and
# reconnect after that normal loop exit rather than waiting for a close frame
# that aiohttp never yields to the loop body.
def test_connection_status_reports_disconnected_on_iterator_exit(
    patch_smallest_ws,
):
    connect_attempts = 0
    transcript_message = {
        "type": "transcription",
        "transcript": "hello world",
        "is_final": True,
        "language": "en",
    }

    def push_after(delay, msg_type, data=None):
        def _run():
            import time

            time.sleep(delay)
            patch_smallest_ws.add_message(
                patch_smallest_ws.MockWebSocketMessage(
                    msg_type=msg_type, data=data
                )
            )

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
                push_after(0.3, patch_smallest_ws.WSMsgType.CLOSED, 1006)
            else:
                push_after(
                    0.3,
                    patch_smallest_ws.WSMsgType.TEXT,
                    json.dumps(transcript_message),
                )
            return ws

        async def close(self) -> None:
            self.closed = True

    class DisconnectThenReconnectTester(SmallestAsrConnectionStatusTester):
        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            await super().on_data(ten_env_tester, data)
            if data.get_name() == "asr_result":
                ten_env_tester.stop_test()

    with patch(
        "ten_packages.extension.smallest_asr_python.extension.aiohttp.ClientSession",
        MockSessionMidClose,
    ):
        property_json = {
            "params": {"api_key": "fake_api_key", "sample_rate": 16000}
        }

        tester = DisconnectThenReconnectTester()
        tester.set_test_mode_single(
            "smallest_asr_python", json.dumps(property_json)
        )
        err = tester.run()
        assert err is None, (
            "test_connection_status_reports_disconnected_on_iterator_exit "
            "err "
            f"code: {err.error_code()} message: {err.error_message()}"
        )

        statuses = [t.get("current") for t in tester.transitions]
        assert (
            "connected" in statuses
        ), f"never observed a 'connected' transition: {tester.transitions}"
        assert "disconnected" in statuses, (
            "never observed a 'disconnected' transition after iterator exit: "
            f"{tester.transitions}"
        )
        assert connect_attempts >= 2, "iterator exit did not trigger reconnect"
        assert statuses.count("connected") >= 2, (
            "never observed the reconnect's 'connected' transition: "
            f"{statuses}"
        )
        first_connected = statuses.index("connected")
        disconnected = statuses.index("disconnected")
        reconnected = statuses.index("connected", first_connected + 1)
        assert first_connected < disconnected < reconnected, (
            "expected connected -> disconnected -> connected transitions: "
            f"{statuses}"
        )
        disconnected_transition = next(
            transition
            for transition in tester.transitions
            if transition.get("current") == "disconnected"
        )
        assert "close code: 1006" in disconnected_transition.get(
            "message", ""
        ), f"close code was not reported: {disconnected_transition}"
