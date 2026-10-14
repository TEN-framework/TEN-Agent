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
import azure.cognitiveservices.speech as speechsdk

# We must import it, which means this test fixture will be automatically executed
from .mock import patch_azure_ws, trigger_vendor_live  # noqa: F401


class AzureAsrExtensionTester(AsyncExtensionTester):

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


# For the first three start_connection calls, a session_stopped event will be received after 1s.
# On the fourth start_connection call, a connected event will be received and no more session_stopped events will occur.
def test_reconnect(patch_azure_ws):
    start_connection_attempts = 0

    def fake_start_continuous_recognition():
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

        def triggerConnected():
            event = SimpleNamespace(session_id="123")
            patch_azure_ws.event_handlers["connected"](event)
            threading.Timer(0.2, triggerRecognized).start()

        def triggerWillFailAfterHandshake():
            threading.Timer(0.5, triggerCanceled).start()

        def triggerWillSuccessAfterHandshake():
            threading.Timer(0.2, triggerRecognized).start()

        def triggerSessionStopped():
            event = SimpleNamespace(session_id="123")
            patch_azure_ws.event_handlers["session_stopped"](event)

        def triggerCanceled():
            evt = SimpleNamespace(
                cancellation_details=SimpleNamespace(
                    code=123,
                    reason=speechsdk.CancellationReason.Error,
                    error_details="mock error details",
                )
            )
            patch_azure_ws.event_handlers["canceled"](evt)
            threading.Timer(0.1, triggerSessionStopped).start()

        nonlocal start_connection_attempts
        start_connection_attempts += 1

        def arm_attempt():
            trigger_vendor_live(patch_azure_ws.event_handlers)
            if start_connection_attempts <= 3:
                triggerWillFailAfterHandshake()
            else:
                triggerWillSuccessAfterHandshake()

        threading.Timer(0.05, arm_attempt).start()

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
    assert (
        err is None
    ), f"test_asr_result err code: {err.error_code()} message: {err.error_message()}"
