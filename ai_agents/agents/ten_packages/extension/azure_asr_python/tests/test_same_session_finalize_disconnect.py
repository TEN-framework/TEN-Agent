import asyncio
import json
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

from .mock import patch_azure_ws, trigger_vendor_live  # noqa: F401


class SameSessionFinalizeDisconnectTester(AsyncExtensionTester):
    """Two speak/finalize cycles with finalize_mode=disconnect in one session."""

    def __init__(self):
        super().__init__()
        self.final_texts: list[str] = []

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        for cycle in (1, 2):
            for _ in range(5):
                chunk = b"\x01\x02" * 160
                audio_frame = AudioFrame.create("pcm_frame")
                metadata = {"session_id": "123"}
                audio_frame.set_property_from_json(
                    "metadata", json.dumps(metadata)
                )
                audio_frame.alloc_buf(len(chunk))
                buf = audio_frame.lock_buf()
                buf[:] = chunk
                audio_frame.unlock_buf(buf)
                await ten_env_tester.send_audio_frame(audio_frame)
                await asyncio.sleep(0.05)

            finalize_data = Data.create("asr_finalize")
            finalize_data.set_property_from_json(
                None,
                json.dumps(
                    {
                        "finalize_id": str(cycle),
                        "metadata": {"session_id": "123"},
                    }
                ),
            )
            await ten_env_tester.send_data(finalize_data)
            await asyncio.sleep(2.0)

    def stop_test_if_checking_failed(
        self,
        ten_env_tester: AsyncTenEnvTester,
        success: bool,
        error_message: str,
    ) -> None:
        if not success:
            ten_env_tester.stop_test(
                TenError.create(TenErrorCode.ErrorCodeGeneric, error_message)
            )

    @override
    async def on_data(
        self, ten_env_tester: AsyncTenEnvTester, data: Data
    ) -> None:
        data_name = data.get_name()
        if data_name != "asr_result":
            return

        data_json, _ = data.get_property_to_json()
        data_dict = json.loads(data_json)
        if not data_dict.get("final"):
            return

        text = data_dict.get("text", "")
        self.final_texts.append(text)
        if len(self.final_texts) >= 2:
            self.stop_test_if_checking_failed(
                ten_env_tester,
                self.final_texts[0] != "" and self.final_texts[1] != "",
                f"expected two non-empty finals, got: {self.final_texts}",
            )
            ten_env_tester.stop_test()


def test_same_session_finalize_disconnect_two_cycles(patch_azure_ws):
    start_calls = 0
    result_index = 0
    lock = threading.Lock()
    timers_active = {"value": True}

    def emit_recognized(text: str) -> None:
        evt = SimpleNamespace(
            result=SimpleNamespace(
                text=text,
                offset=0,
                duration=5000000,
                no_match_details=None,
                json=json.dumps(
                    {
                        "DisplayText": text,
                        "Offset": 0,
                        "Duration": 5000000,
                    }
                ),
            )
        )
        patch_azure_ws.event_handlers["recognized"](evt)

    def fake_start_continuous_recognition():
        nonlocal start_calls, result_index
        with lock:
            start_calls += 1
            result_index += 1
            text = f"cycle-{result_index}"

        def arm_attempt() -> None:
            if not timers_active["value"]:
                return
            trigger_vendor_live(patch_azure_ws.event_handlers, session_id="123")
            threading.Timer(0.2, lambda: emit_recognized(text)).start()

        threading.Timer(0.05, arm_attempt).start()
        return None

    def fake_stop_continuous_recognition():
        def emit_session_stopped() -> None:
            if not timers_active["value"]:
                return
            stopped = SimpleNamespace(session_id="123")
            handler = patch_azure_ws.event_handlers.get("session_stopped")
            if handler is None:
                return
            try:
                handler(stopped)
            except RuntimeError:
                return

        threading.Timer(0.05, emit_session_stopped).start()
        return None

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
            "finalize_mode": "disconnect",
        }
    }

    tester = SameSessionFinalizeDisconnectTester()
    tester.set_test_mode_single("azure_asr_python", json.dumps(property_json))
    try:
        err = tester.run()
    finally:
        timers_active["value"] = False

    assert err is None, (
        f"test_same_session_finalize_disconnect_two_cycles failed: "
        f"{err.error_code() if err else None} {err.error_message() if err else ''}"
    )
    assert (
        start_calls >= 2
    ), f"expected reopen after first finalize, starts={start_calls}"
