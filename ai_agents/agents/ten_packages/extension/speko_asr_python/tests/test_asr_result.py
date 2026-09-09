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


class SpekoAsrExtensionTester(AsyncExtensionTester):

    def __init__(self):
        super().__init__()
        self.sender_task: asyncio.Task[None] | None = None
        self.stopped = False
        self.received_partial = False

    async def audio_sender(self, ten_env: AsyncTenEnvTester):
        while not self.stopped:
            chunk = b"\x01\x02" * 160  # 320 bytes (16-bit * 160 samples)
            audio_frame = AudioFrame.create("pcm_frame")
            metadata = {"session_id": "123"}
            audio_frame.set_property_from_json("metadata", json.dumps(metadata))
            audio_frame.alloc_buf(len(chunk))
            buf = audio_frame.lock_buf()
            buf[:] = chunk
            audio_frame.unlock_buf(buf)
            await ten_env.send_audio_frame(audio_frame)
            await asyncio.sleep(0.1)

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender_task = asyncio.create_task(
            self.audio_sender(ten_env_tester)
        )

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
        if data_name != "asr_result":
            return

        data_json, _ = data.get_property_to_json()
        data_dict = json.loads(data_json)

        ten_env_tester.log_info(f"tester on_data, data_dict: {data_dict}")

        for field in (
            "id",
            "text",
            "final",
            "start_ms",
            "duration_ms",
            "language",
            "metadata",
        ):
            self.stop_test_if_checking_failed(
                ten_env_tester,
                field in data_dict,
                f"{field} is not in data_dict: {data_dict}",
            )

        session_id = data_dict.get("metadata", {}).get("session_id", "")
        self.stop_test_if_checking_failed(
            ten_env_tester,
            session_id == "123",
            f"session_id is not 123: {session_id}",
        )

        self.stop_test_if_checking_failed(
            ten_env_tester,
            data_dict["language"] == "en-US",
            f"language is not en-US: {data_dict}",
        )

        if not data_dict["final"]:
            self.received_partial = True
            return

        self.stop_test_if_checking_failed(
            ten_env_tester,
            self.received_partial,
            "final arrived before any partial transcript",
        )
        self.stop_test_if_checking_failed(
            ten_env_tester,
            data_dict["text"] == "hello world",
            f"unexpected final text: {data_dict}",
        )
        ten_env_tester.stop_test()

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.stopped = True
        if self.sender_task:
            _ = self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


def test_asr_result(patch_speko_ws):
    def trigger_transcript_messages():
        """Push router frames: ready, a partial, then a final."""
        for frame in (
            {"type": "ready", "provider": "MockProvider"},
            {
                "type": "transcript",
                "text": "hello",
                "isFinal": False,
                "confidence": 1.0,
                "words": None,
            },
            {
                "type": "transcript",
                "text": "hello world",
                "isFinal": True,
                "confidence": 1.0,
                "words": None,
            },
        ):
            msg = patch_speko_ws.MockWebSocketMessage(
                msg_type=patch_speko_ws.WSMsgType.TEXT,
                data=json.dumps(frame),
            )
            patch_speko_ws.add_message(msg)

    def delayed_message_sender():
        import time

        time.sleep(2)  # Wait for connection
        trigger_transcript_messages()

    sender_thread = threading.Thread(target=delayed_message_sender, daemon=True)
    sender_thread.start()

    property_json = {
        "params": {
            "api_key": "fake_api_key",
            "language": "en",
            "sample_rate": 16000,
        }
    }

    tester = SpekoAsrExtensionTester()
    tester.set_test_mode_single("speko_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"test_asr_result err: {err}"


def test_config_frame_is_first_and_camel_case(patch_speko_ws):
    """The router rejects unknown fields and expects the config frame
    first — pin the wire contract."""

    def trigger_final():
        frame = {
            "type": "transcript",
            "text": "done",
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

        time.sleep(2)
        trigger_final()

    sender_thread = threading.Thread(target=delayed_message_sender, daemon=True)
    sender_thread.start()

    class WireTester(SpekoAsrExtensionTester):
        @override
        async def on_data(
            self, ten_env_tester: AsyncTenEnvTester, data: Data
        ) -> None:
            if data.get_name() != "asr_result":
                return
            ws = patch_speko_ws.ws
            self.stop_test_if_checking_failed(
                ten_env_tester,
                len(ws.sent_messages) >= 1,
                "no text frame was sent before transcripts arrived",
            )
            first = json.loads(ws.sent_messages[0])
            self.stop_test_if_checking_failed(
                ten_env_tester,
                first.get("type") == "config",
                f"first frame is not a config frame: {first}",
            )
            for field in ("language", "interimResults", "sampleRate"):
                self.stop_test_if_checking_failed(
                    ten_env_tester,
                    field in first,
                    f"{field} missing from config frame: {first}",
                )
            self.stop_test_if_checking_failed(
                ten_env_tester,
                len(ws.sent_bytes) > 0,
                "no binary PCM frames were sent",
            )
            # Bare PCM: no RIFF header on the first binary frame.
            self.stop_test_if_checking_failed(
                ten_env_tester,
                not bytes(ws.sent_bytes[0]).startswith(b"RIFF"),
                "first binary frame carries a WAV header",
            )
            ten_env_tester.stop_test()

    property_json = {
        "params": {
            "api_key": "fake_api_key",
            "language": "en",
            "sample_rate": 16000,
        }
    }

    tester = WireTester()
    tester.set_test_mode_single("speko_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"test_config_frame err: {err}"
