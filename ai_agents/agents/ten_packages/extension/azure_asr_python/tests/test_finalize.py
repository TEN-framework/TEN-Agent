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
from .mock import patch_azure_ws, trigger_vendor_live  # noqa: F401


class AzureAsrExtensionTester(AsyncExtensionTester):

    def __init__(self):
        super().__init__()
        self.sender_task: asyncio.Task[None] | None = None
        self.stopped = False

    async def audio_sender(self, ten_env: AsyncTenEnvTester):
        while not self.stopped:
            chunk = b"\x01\x02" * 160  # 320 bytes (16-bit * 160 samples)
            if not chunk:
                break
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

        # send a finalize event after 1.5 seconds
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

    @override
    async def on_data(
        self, ten_env_tester: AsyncTenEnvTester, data: Data
    ) -> None:
        data_name = data.get_name()
        if data_name == "asr_result":
            # Check the data structure.

            data_json, _ = data.get_property_to_json()
            data_dict = json.loads(data_json)

            ten_env_tester.log_info(f"tester on_data, data_dict: {data_dict}")

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "id" in data_dict,
                f"id is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "text" in data_dict,
                f"text is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "final" in data_dict,
                f"final is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "start_ms" in data_dict,
                f"start_ms is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "duration_ms" in data_dict,
                f"duration_ms is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "language" in data_dict,
                f"language is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                "metadata" in data_dict,
                f"metadata is not in data_dict: {data_dict}",
            )

            session_id = data_dict.get("metadata", {}).get("session_id", "")
            self.stop_test_if_checking_failed(
                ten_env_tester,
                session_id == "123",
                f"session_id is not 123: {session_id}",
            )
        elif data_name == "asr_finalize_end":
            # Check if the finalize_id equals to the one in finalize data.
            finalize_id, _ = data.get_property_string("finalize_id")
            self.stop_test_if_checking_failed(
                ten_env_tester,
                finalize_id == "1",
                f"finalize_id is not '1': {finalize_id}",
            )

            # Check if the metadata equals to the one in finalize data.
            metadata_json, _ = data.get_property_to_json("metadata")
            metadata_dict = json.loads(metadata_json)
            self.stop_test_if_checking_failed(
                ten_env_tester,
                metadata_dict["session_id"] == "123",
                f"session_id is not 123 in asr_finalize_end: {metadata_dict}",
            )

            ten_env_tester.stop_test()

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        if self.sender_task:
            _ = self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


def test_asr_result(patch_azure_ws):
    def fake_start_continuous_recognition():
        def triggerSessionStarted():
            trigger_vendor_live(patch_azure_ws.event_handlers, session_id="123")

            threading.Timer(1.0, triggerRecognizing).start()
            threading.Timer(2.0, triggerRecognizing).start()
            threading.Timer(3.0, triggerRecognized).start()

        def triggerRecognizing():
            evt = SimpleNamespace(
                result=SimpleNamespace(
                    text="goodbye",
                    offset=0,
                    duration=1000000,
                    no_match_details=None,
                    json=json.dumps(
                        {
                            "DisplayText": "goodbye",
                            "Offset": 0,
                            "Duration": 1000000,
                        }
                    ),
                )
            )
            patch_azure_ws.event_handlers["recognizing"](evt)

        def triggerRecognized():
            evt = SimpleNamespace(
                result=SimpleNamespace(
                    text="goodbye world",
                    offset=0,
                    duration=5000000,
                    no_match_details=None,
                    json=json.dumps(
                        {
                            "DisplayText": "goodbye world",
                            "Offset": 0,
                            "Duration": 5000000,
                        }
                    ),
                )
            )
            patch_azure_ws.event_handlers["recognized"](evt)

        threading.Timer(0.2, triggerSessionStarted).start()
        return None

    def fake_stop_continuous_recognition():
        return None

    # Inject into recognizer
    patch_azure_ws.recognizer_instance.start_continuous_recognition.side_effect = (
        fake_start_continuous_recognition
    )

    patch_azure_ws.recognizer_instance.stop_continuous_recognition.side_effect = (
        fake_stop_continuous_recognition
    )

    property_json = {
        "params": {
            "key": "fake_key",
            "region": "fake_region",
        }
    }

    tester = AzureAsrExtensionTester()
    tester.set_test_mode_single("azure_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"test_asr_result err: {err}"
