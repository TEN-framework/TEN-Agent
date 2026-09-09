import sys
from pathlib import Path

# Add project root to sys.path to allow running tests from this directory
# The project root is 6 levels up from the parent directory of this file.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json
from unittest.mock import patch, AsyncMock, MagicMock

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Data,
)
from ten_ai_base.struct import TTSTextInput


class ExtensionTesterError(ExtensionTester):
    def __init__(self, send_request: bool = False):
        super().__init__()
        self.send_request = send_request
        self.error_received = False
        self.error_code = None
        self.error_message = None
        self.vendor_info = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        if self.send_request:
            tts_input = TTSTextInput(
                request_id="test-request-error",
                text="This text will trigger the error path.",
                text_input_end=True,
            )
            data = Data.create("tts_text_input")
            data.set_property_from_json(None, tts_input.model_dump_json())
            ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name == "error":
            self.error_received = True
            json_str, _ = data.get_property_to_json(None)
            error_data = json.loads(json_str)
            self.error_code = error_data.get("code")
            self.error_message = error_data.get("message", "")
            self.vendor_info = error_data.get("vendor_info", {})
            ten_env.log_info(
                f"Received error: code={self.error_code}, "
                f"message={self.error_message}"
            )
            ten_env.stop_test()


def test_empty_params_fatal_error():
    """Empty api_key must raise FATAL ERROR with code -1000."""
    empty_params_config = {"params": {"api_key": ""}}

    tester = ExtensionTesterError()
    tester.set_test_mode_single(
        "speko_tts_python", json.dumps(empty_params_config)
    )
    tester.run()

    assert tester.error_received, "Expected to receive error message"
    assert (
        tester.error_code == -1000
    ), f"Expected error code -1000 (FATAL_ERROR), got {tester.error_code}"
    assert tester.error_message, "Error message should not be empty"


class _MockStreamResponse:
    """Minimal httpx streaming response stand-in."""

    def __init__(self, status_code: int, body: bytes, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    async def aread(self) -> bytes:
        return self._body

    async def aiter_bytes(self, chunk_size: int = 4096):
        yield self._body


class _MockStreamContext:
    def __init__(self, response: _MockStreamResponse):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


@patch("ten_packages.extension.speko_tts_python.speko_tts.AsyncClient")
def test_invalid_api_key_error(MockAsyncClient):
    """A router 401 must surface as FATAL with vendor 'speko'."""
    router_401_body = json.dumps(
        {
            "error": {
                "code": "invalid_api_key",
                "message": "The API key is not valid.",
            }
        }
    ).encode("utf-8")

    mock_client = MockAsyncClient.return_value
    mock_client.stream = MagicMock(
        return_value=_MockStreamContext(
            _MockStreamResponse(401, router_401_body)
        )
    )
    mock_client.aclose = AsyncMock()

    invalid_key_config = {
        "params": {
            "api_key": "fake_invalid_key_for_testing",
        },
    }

    tester = ExtensionTesterError(send_request=True)
    tester.set_test_mode_single(
        "speko_tts_python", json.dumps(invalid_key_config)
    )
    tester.run()

    assert tester.error_received, "Expected to receive error message"
    assert (
        tester.error_code == -1000
    ), f"Expected error code -1000 (FATAL_ERROR), got {tester.error_code}"
    assert (
        "invalid_api_key" in tester.error_message
    ), f"Error message should carry the router body: {tester.error_message}"
    assert (
        tester.vendor_info.get("vendor") == "speko"
    ), f"Expected vendor 'speko', got {tester.vendor_info}"


@patch("ten_packages.extension.speko_tts_python.speko_tts.AsyncClient")
def test_upstream_error_is_non_fatal(MockAsyncClient):
    """A router 502 (all upstreams failed) must be NON_FATAL (1000)."""
    router_502_body = json.dumps(
        {
            "error": {
                "code": "all_upstreams_failed",
                "message": "Every candidate provider failed.",
            }
        }
    ).encode("utf-8")

    mock_client = MockAsyncClient.return_value
    mock_client.stream = MagicMock(
        return_value=_MockStreamContext(
            _MockStreamResponse(502, router_502_body)
        )
    )
    mock_client.aclose = AsyncMock()

    config = {
        "params": {
            "api_key": "fake_valid_looking_key",
        },
    }

    tester = ExtensionTesterError(send_request=True)
    tester.set_test_mode_single("speko_tts_python", json.dumps(config))
    tester.run()

    assert tester.error_received, "Expected to receive error message"
    assert (
        tester.error_code == 1000
    ), f"Expected error code 1000 (NON_FATAL_ERROR), got {tester.error_code}"
    assert (
        "all_upstreams_failed" in tester.error_message
    ), f"Error message should carry the router body: {tester.error_message}"
