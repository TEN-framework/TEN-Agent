from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    TenError,
    TenErrorCode,
)
import json

# We must import it, which means this test fixture will be automatically executed
from .mock import patch_azure_ws  # noqa: F401


class AzureAsrExtensionTester(AsyncExtensionTester):

    def __init__(self):
        super().__init__()

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
                "id" in data_dict,
                f"id is not in data_dict: {data_dict}",
            )

            self.stop_test_if_checking_failed(
                ten_env_tester,
                data_dict["code"] == -1000,
                f"code is not FATAL_ERROR: {data_dict}",
            )

            ten_env_tester.stop_test()


def test_invalid_params():
    property_json = {
        "params": {
            "key": "",
        }
    }

    tester = AzureAsrExtensionTester()
    tester.set_test_mode_single("azure_asr_python", json.dumps(property_json))
    err = tester.run()
    assert (
        err is None
    ), f"test_asr_result err code: {err.error_code()} message: {err.error_message()}"


def test_invalid_transport_reconnect_grace_sec_on_init():
    property_json = {
        "params": {
            "key": "fake_key",
            "region": "fake_region",
            "transport_reconnect_grace_sec": 0,
        }
    }

    tester = AzureAsrExtensionTester()
    tester.set_test_mode_single("azure_asr_python", json.dumps(property_json))
    err = tester.run()
    assert (
        err is None
    ), f"invalid grace init err code: {err.error_code()} message: {err.error_message()}"
