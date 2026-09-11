from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.message import ModuleErrorCode
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close, CloseCode

from ..config import BytedanceASRLLMConfig
from ..extension import BytedanceASRLLMExtension
from .. import volcengine_asr_client as client_module
from ..volcengine_asr_client import ASRResponse, VolcengineASRClient


def _minimal_config() -> BytedanceASRLLMConfig:
    return BytedanceASRLLMConfig.model_validate(
        {
            "params": {
                "audio": {"rate": 16000},
                "request": {"model_name": "bigmodel"},
            }
        }
    )


class _FailingWebSocket:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("listen failed")


class _SingleMessageWebSocket:
    def __init__(self):
        self._sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        return b"response"


@pytest.mark.asyncio
async def test_server_error_response_preserves_result_callback():
    client = VolcengineASRClient(
        url="wss://example.test/asr",
        app_key="app_key",
        access_key="access_key",
        api_key="api_key",
        auth_method="api_key",
        config=_minimal_config(),
    )
    client.websocket = _SingleMessageWebSocket()
    client._first_response_received = True
    client.result_callback = AsyncMock()
    client.asr_error_callback = MagicMock(
        return_value=(45000081, "packet timeout")
    )
    client.set_on_disconnected_callback(AsyncMock())

    with patch.object(
        client_module.ResponseParser,
        "parse_response",
        return_value=ASRResponse(
            code=45000081,
            payload_msg={"error_message": "packet timeout"},
        ),
    ):
        await client._listen_for_responses()

    client.result_callback.assert_awaited_once()
    client.asr_error_callback.assert_called_once()
    error = client.asr_error_callback.call_args.args[0]
    assert error.code == 45000081
    assert str(error) == "packet timeout"


@pytest.mark.asyncio
async def test_server_error_response_handles_non_dict_payload():
    client = VolcengineASRClient(
        url="wss://example.test/asr",
        app_key="app_key",
        access_key="access_key",
        api_key="api_key",
        auth_method="api_key",
        config=_minimal_config(),
    )
    client.websocket = _SingleMessageWebSocket()
    client._first_response_received = True
    client.result_callback = AsyncMock()
    client.asr_error_callback = MagicMock(
        return_value=(45000081, "Server error response: code=45000081")
    )
    client.set_on_disconnected_callback(AsyncMock())

    with patch.object(
        client_module.ResponseParser,
        "parse_response",
        return_value=ASRResponse(code=45000081, payload_msg=["unexpected"]),
    ):
        await client._listen_for_responses()

    client.asr_error_callback.assert_called_once()
    error = client.asr_error_callback.call_args.args[0]
    assert error.code == 45000081
    assert str(error) == "Server error response: code=45000081"


@pytest.mark.asyncio
async def test_extension_result_callback_does_not_report_server_error():
    extension = BytedanceASRLLMExtension("test_extension")
    extension.ten_env = MagicMock()
    extension.send_asr_error = AsyncMock()

    await extension._on_asr_result(
        ASRResponse(
            code=45000081,
            payload_msg={"error_message": "packet timeout"},
        )
    )

    extension.send_asr_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_asr_error_callback_forwards_vendor_close_fields():
    client = VolcengineASRClient(
        url="wss://example.test/asr",
        app_key="app_key",
        access_key="access_key",
        api_key="api_key",
        auth_method="api_key",
        config=_minimal_config(),
    )
    client.websocket = _FailingWebSocket()
    client.asr_error_callback = MagicMock(
        return_value=(1000, "mapped non-fatal error")
    )

    disconnected = AsyncMock()
    client.set_on_disconnected_callback(disconnected)

    await client._listen_for_responses()

    client.asr_error_callback.assert_called_once()
    disconnected.assert_awaited_once_with(
        1000,
        "closed",
        "1000",
        "mapped non-fatal error",
    )


@pytest.mark.asyncio
async def test_extension_disconnected_forwards_vendor_close_fields():
    extension = BytedanceASRLLMExtension("test_extension")
    extension.ten_env = MagicMock()
    extension.on_disconnected = AsyncMock()

    await extension._on_disconnected(
        vendor_close_code=1000,
        vendor_close_message="mapped non-fatal error",
    )

    extension.on_disconnected.assert_awaited_once_with(
        code=1000,
        message="mapped non-fatal error",
        vendor_info=None,
    )


@pytest.mark.asyncio
async def test_extension_disconnected_accepts_int_vendor_code():
    extension = BytedanceASRLLMExtension("test_extension")
    extension.ten_env = MagicMock()
    extension.on_disconnected = AsyncMock()
    extension.vendor = MagicMock(return_value="bytedance_bigmodel")

    await extension._on_disconnected(
        vendor_close_code=1000,
        vendor_close_message="closed",
        vendor_code=45000081,
        vendor_message="Server error response: code=45000081",
    )

    extension.on_disconnected.assert_awaited_once()
    _, kwargs = extension.on_disconnected.await_args
    vendor_info = kwargs["vendor_info"]
    assert vendor_info is not None
    assert vendor_info.code == "45000081"
    assert vendor_info.message == "Server error response: code=45000081"
    assert vendor_info.vendor == "bytedance_bigmodel"


@pytest.mark.asyncio
async def test_connection_error_callback_forwards_vendor_close_fields():
    client = VolcengineASRClient(
        url="wss://example.test/asr",
        app_key="app_key",
        access_key="access_key",
        api_key="api_key",
        auth_method="api_key",
        config=_minimal_config(),
    )
    error = Exception("server rejected WebSocket connection: HTTP 401")
    client.connection_error_callback = MagicMock(
        return_value=(401, "server rejected WebSocket connection: HTTP 401")
    )
    client.disconnect = AsyncMock()

    with patch.object(
        client_module.websockets, "connect", new=AsyncMock(side_effect=error)
    ):
        with pytest.raises(Exception, match="HTTP 401"):
            await client.connect()

    client.connection_error_callback.assert_called_once_with(error)
    client.disconnect.assert_awaited_once_with(
        1000,
        "closed",
        "401",
        "server rejected WebSocket connection: HTTP 401",
    )


def test_extension_connection_error_returns_parsed_http_code():
    extension = BytedanceASRLLMExtension("test_extension")

    with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
        close_code, close_message = extension._on_connection_error(
            Exception("server rejected WebSocket connection: HTTP 401")
        )

    assert close_code == 401
    assert close_message == "server rejected WebSocket connection: HTTP 401"


def test_extension_reports_numeric_abnormal_closure_code():
    extension = BytedanceASRLLMExtension("test_extension")
    extension._on_asr_error = AsyncMock()
    error = ConnectionClosedError(
        Close(CloseCode.ABNORMAL_CLOSURE, ""), None, None
    )

    with patch("asyncio.create_task", side_effect=lambda coro: coro.close()):
        close_code, close_message = extension._on_asr_communication_error(error)

    assert close_code == 1006
    assert "1006" in close_message
    extension._on_asr_error.assert_called_once_with(1006, close_message)


@pytest.mark.asyncio
async def test_extension_omits_vendor_info_for_local_fallback_code():
    extension = BytedanceASRLLMExtension("test_extension")
    extension.ten_env = MagicMock()
    extension.stopped = True
    extension.send_asr_error = AsyncMock()

    await extension._on_asr_error(
        int(ModuleErrorCode.FATAL_ERROR.value),
        "local runtime failure",
    )

    extension.send_asr_error.assert_awaited_once()
    module_error, vendor_info = extension.send_asr_error.await_args.args
    assert module_error.code == int(ModuleErrorCode.NON_FATAL_ERROR.value)
    assert vendor_info is None
