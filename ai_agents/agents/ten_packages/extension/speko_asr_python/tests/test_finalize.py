import asyncio
import json
import threading

from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)

# We must import it so the test fixture is automatically executed.
from .mock import patch_speko_ws  # noqa: F401


class SpekoAsrFinalizeTester(AsyncExtensionTester):

    def __init__(self, ws_fixture):
        super().__init__()
        self.ws_fixture = ws_fixture
        self.sender_task: asyncio.Task[None] | None = None
        self.stopped = False
        self.finalize_end_count = 0

    async def audio_sender(self, ten_env: AsyncTenEnvTester):
        while not self.stopped:
            chunk = b"\x01\x02" * 160
            audio_frame = AudioFrame.create("pcm_frame")
            metadata = {"session_id": "123"}
            audio_frame.set_property_from_json("metadata", json.dumps(metadata))
            audio_frame.alloc_buf(len(chunk))
            buf = audio_frame.lock_buf()
            buf[:] = chunk
            audio_frame.unlock_buf(buf)
            await ten_env.send_audio_frame(audio_frame)
            await asyncio.sleep(0.1)

    async def send_finalize_event(self, ten_env: AsyncTenEnvTester):
        finalize_data = Data.create("asr_finalize")
        data = {
            "finalize_id": "1",
            "metadata": {
                "session_id": "123",
            },
        }
        finalize_data.set_property_from_json(None, json.dumps(data))
        await ten_env.send_data(finalize_data)

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender_task = asyncio.create_task(
            self.audio_sender(ten_env_tester)
        )

        # Send a finalize event once the connection is up.
        await asyncio.sleep(1.5)
        await self.send_finalize_event(ten_env_tester)

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

    async def on_finalize_end(self, ten_env_tester: AsyncTenEnvTester) -> None:
        """Subclass hook: default behavior stops the test."""
        ten_env_tester.stop_test()

    @override
    async def on_data(
        self, ten_env_tester: AsyncTenEnvTester, data: Data
    ) -> None:
        data_name = data.get_name()
        if data_name == "asr_finalize_end":
            self.finalize_end_count += 1

            finalize_id, _ = data.get_property_string("finalize_id")
            self.stop_test_if_checking_failed(
                ten_env_tester,
                finalize_id == "1",
                f"finalize_id is not '1': {finalize_id}",
            )

            # The extension must have flushed the router with an end
            # frame (the router has no flush-in-place message).
            sent_types = [
                json.loads(m).get("type")
                for m in self.ws_fixture.ws.sent_messages
            ]
            self.stop_test_if_checking_failed(
                ten_env_tester,
                "end" in sent_types,
                f"no end frame was sent to the router: {sent_types}",
            )

            await self.on_finalize_end(ten_env_tester)

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.stopped = True
        if self.sender_task:
            _ = self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


PROPERTY_JSON = {
    "params": {
        "api_key": "fake_api_key",
        "sample_rate": 16000,
    }
}


def test_finalize(patch_speko_ws):
    def trigger_transcript_messages():
        """Simulate the router flushing a final after the end frame."""
        frame = {
            "type": "transcript",
            "text": "hello world",
            "isFinal": True,
            "confidence": 1.0,
            "words": None,
        }
        msg = patch_speko_ws.MockWebSocketMessage(
            msg_type=patch_speko_ws.WSMsgType.TEXT,
            data=json.dumps(frame),
        )
        patch_speko_ws.add_message(msg)

    def delayed_message_sender():
        import time

        time.sleep(2)  # After the finalize event lands
        trigger_transcript_messages()

    sender_thread = threading.Thread(target=delayed_message_sender, daemon=True)
    sender_thread.start()

    tester = SpekoAsrFinalizeTester(patch_speko_ws)
    tester.set_test_mode_single("speko_asr_python", json.dumps(PROPERTY_JSON))
    err = tester.run()
    assert err is None, f"test_finalize err: {err}"


def test_finalize_server_end_reconnects(patch_speko_ws):
    """The full turn flow: finalize -> tail final -> server end frame.

    The extension must complete the finalize handshake exactly once and
    open a FRESH socket (with a new config frame) for the next turn,
    because the router closes the session after an end frame.
    """

    def trigger_flush_then_end():
        for frame in (
            {
                "type": "transcript",
                "text": "hello world",
                "isFinal": True,
                "confidence": 1.0,
                "words": None,
            },
            {"type": "end"},
        ):
            msg = patch_speko_ws.MockWebSocketMessage(
                msg_type=patch_speko_ws.WSMsgType.TEXT,
                data=json.dumps(frame),
            )
            patch_speko_ws.add_message(msg)

    def delayed_message_sender():
        import time

        time.sleep(2)  # After the finalize event lands
        trigger_flush_then_end()

    sender_thread = threading.Thread(target=delayed_message_sender, daemon=True)
    sender_thread.start()

    class ReconnectTester(SpekoAsrFinalizeTester):
        @override
        async def on_finalize_end(
            self, ten_env_tester: AsyncTenEnvTester
        ) -> None:
            # Wait for the reconnect: a second socket must appear and
            # carry its own config frame. Reconnect backoff is 300ms.
            for _ in range(50):
                sockets = self.ws_fixture.sockets
                if len(sockets) >= 2 and sockets[1].sent_messages:
                    break
                await asyncio.sleep(0.1)

            sockets = self.ws_fixture.sockets
            self.stop_test_if_checking_failed(
                ten_env_tester,
                len(sockets) >= 2,
                f"no reconnect after server end: {len(sockets)} socket(s)",
            )
            self.stop_test_if_checking_failed(
                ten_env_tester,
                self.finalize_end_count == 1,
                f"finalize_end sent {self.finalize_end_count} times",
            )
            first = json.loads(sockets[1].sent_messages[0])
            self.stop_test_if_checking_failed(
                ten_env_tester,
                first.get("type") == "config",
                f"reconnected socket did not lead with config: {first}",
            )
            ten_env_tester.stop_test()

    tester = ReconnectTester(patch_speko_ws)
    tester.set_test_mode_single("speko_asr_python", json.dumps(PROPERTY_JSON))
    err = tester.run()
    assert err is None, f"test_finalize_server_end_reconnects err: {err}"
