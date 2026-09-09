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

# We must import it so the test fixture is automatically executed.
from .mock import patch_speko_ws  # noqa: F401


class SpekoAsrExtensionTester(AsyncExtensionTester):

    def __init__(self, expected_code: int):
        super().__init__()
        self.expected_code = expected_code

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
            data_json, _ = data.get_property_to_json()
            data_dict = json.loads(data_json)
            ten_env_tester.log_info(
                f"tester recv error, data_dict: {data_dict}"
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                data_dict["code"] == self.expected_code,
                f"unexpected module error code: {data_dict}",
            )

            vendor_info = data_dict.get("vendor_info", {})
            self.stop_test_if_checking_failed(
                ten_env_tester,
                vendor_info.get("vendor") == "speko",
                f"vendor is not speko: {data_dict}",
            )
            self.stop_test_if_checking_failed(
                ten_env_tester,
                bool(vendor_info.get("code")),
                f"vendor_info.code is empty: {data_dict}",
            )

            ten_env_tester.stop_test()


def _run_with_router_error(
    patch_speko_ws, router_code: str, expected_module_code: int
):
    def trigger_error_message():
        frame = {
            "type": "error",
            "code": router_code,
            "message": f"router says {router_code}",
        }
        msg = patch_speko_ws.MockWebSocketMessage(
            msg_type=patch_speko_ws.WSMsgType.TEXT,
            data=json.dumps(frame),
        )
        patch_speko_ws.add_message(msg)

    def delayed_message_sender():
        import time

        time.sleep(2)
        trigger_error_message()

    sender_thread = threading.Thread(target=delayed_message_sender, daemon=True)
    sender_thread.start()

    property_json = {
        "params": {
            "api_key": "fake_api_key",
            "sample_rate": 16000,
        }
    }

    tester = SpekoAsrExtensionTester(expected_code=expected_module_code)
    tester.set_test_mode_single("speko_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"vendor error test err: {err}"


def test_vendor_error_upstream_is_non_fatal(patch_speko_ws):
    _run_with_router_error(patch_speko_ws, "UPSTREAM", 1000)


def test_vendor_error_unsupported_language_is_fatal(patch_speko_ws):
    _run_with_router_error(patch_speko_ws, "UNSUPPORTED_LANGUAGE", -1000)
