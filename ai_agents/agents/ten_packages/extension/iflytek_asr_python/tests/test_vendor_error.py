import asyncio

from iflytek_asr_python.protocol import IFlytekProtocolError
from iflytek_asr_python.reconnect_manager import ReconnectLimitReachedError

from .helpers import create_extension, data_as_dict


def test_vendor_errors_include_classification_code_and_message() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()

        await extension.on_error(
            IFlytekProtocolError("vendor-429", "temporarily overloaded")
        )
        await extension._send_framework_error(
            ReconnectLimitReachedError("maximum reconnection attempts reached"),
            fatal=True,
        )

        errors = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "error"
        ]
        assert [error["code"] for error in errors] == [1000, -1000]
        assert errors[0]["vendor_info"] == {
            "vendor": "iflytek",
            "code": "vendor-429",
            "message": "temporarily overloaded",
        }
        assert errors[1]["vendor_info"]["vendor"] == "iflytek"
        assert errors[1]["vendor_info"]["code"] == "reconnect_exhausted"
        assert errors[1]["vendor_info"]["message"]

    asyncio.run(run())
