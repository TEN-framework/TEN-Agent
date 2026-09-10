#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from typing import Any, Optional
from unittest.mock import patch
import json

from ten_ai_base.struct import TTSTextInput
from ten_runtime import (
    Data,
    ExtensionTester,
    TenEnvTester,
)
from ..cosy_tts import MESSAGE_TYPE_CMD_COMPLETE
from .mock_client import MockClientStream


# ================ test reconnect after connection drop(robustness) ================
class ExtensionTesterRobustness(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.first_request_error: Optional[dict[str, Any]] = None
        self.first_request_event_interval_ms: Optional[int] = None
        self.second_request_successful = False
        self.ten_env: Optional[TenEnvTester] = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        """Called when test starts, sends the first TTS request."""
        self.ten_env = ten_env_tester
        ten_env_tester.log_info(
            "Robustness test started, sending first TTS request."
        )

        # First request, expected to fail
        tts_input_1 = TTSTextInput(
            request_id="tts_request_to_fail",
            text="This request will trigger a simulated connection drop.",
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input_1.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def send_second_request(self):
        """Sends the second TTS request to verify reconnection."""
        if self.ten_env is None:
            print("Error: ten_env is not initialized.")
            return
        self.ten_env.log_info(
            "Sending second TTS request to verify reconnection."
        )
        tts_input_2 = TTSTextInput(
            request_id="tts_request_to_succeed",
            text="This request should succeed after reconnection.",
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input_2.model_dump_json())
        self.ten_env.send_data(data)

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        json_str, _ = data.get_property_to_json(None)
        if not json_str:
            # Not all events have a JSON payload (e.g., tts_audio_start)
            return
        payload = json.loads(json_str)

        if name == "error" and payload.get("id") == "tts_request_to_fail":
            ten_env.log_info(
                f"Received expected error for the first request: {payload}"
            )
            self.first_request_error = payload
            # After receiving the error for the first request, immediately send the second one.
            self.send_second_request()

        elif (
            name == "tts_audio_end"
            and payload.get("request_id") == "tts_request_to_fail"
        ):
            self.first_request_event_interval_ms = payload.get(
                "request_event_interval_ms"
            )

        elif (
            name == "tts_audio_end"
            and payload.get("request_id") == "tts_request_to_succeed"
        ):
            ten_env.log_info(
                "Received tts_audio_end for the second request. Test successful."
            )
            self.second_request_successful = True
            # We can now safely stop the test.
            ten_env.stop_test()


@patch("cosy_tts_python.extension.CosyTTSClient")
def test_reconnect_after_connection_drop(MockCosyTTSClient):
    """
    Tests that the extension can recover from a connection drop, report a
    NON_FATAL_ERROR, and then successfully reconnect and process a new request.
    """
    print("Starting test_reconnect_after_connection_drop with mock...")

    # --- Mock Configuration ---
    mock_instance = MockCosyTTSClient.return_value
    request_count = 0

    def events(_text: str, _request_id: str):
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return [
                (
                    MESSAGE_TYPE_CMD_COMPLETE,
                    ConnectionRefusedError(
                        "Simulated connection drop from test"
                    ),
                    0,
                )
            ]
        return [(MESSAGE_TYPE_CMD_COMPLETE, None, 0)]

    MockClientStream(events).configure(mock_instance)

    # --- Test Setup ---
    config = {
        "params": {
            "api_key": "a_valid_key",
        },
    }
    tester = ExtensionTesterRobustness()
    tester.set_test_mode_single("cosy_tts_python", json.dumps(config))

    print("Running robustness test...")
    tester.run()
    print("Robustness test completed.")

    # --- Assertions ---
    # 1. Verify that the first request resulted in a NON_FATAL_ERROR
    assert (
        tester.first_request_error is not None
    ), "Did not receive any error message."
    assert (
        tester.first_request_error.get("code") == 1000
    ), f"Expected error code 1000 (NON_FATAL_ERROR), got {tester.first_request_error.get('code')}"
    assert tester.first_request_event_interval_ms == 0, (
        "A request with no audio should report a zero event interval, got "
        f"{tester.first_request_event_interval_ms}ms"
    )

    # 2. Verify that vendor_info was included in the error
    vendor_info = tester.first_request_error.get("vendor_info")
    assert vendor_info is not None, "Error message did not contain vendor_info."
    assert (
        vendor_info.get("vendor") == "cosy"
    ), f"Expected vendor 'cosy', got {vendor_info.get('vendor')}"

    # 3. Verify that the client's start method was called twice (initial + reconnect)
    # This assertion is tricky because the reconnection logic might be inside the client.
    # A better assertion is to check if the second request succeeded.

    # 4. Verify that the second TTS request was successful
    assert (
        tester.second_request_successful
    ), "The second TTS request after the error did not succeed."

    print(
        "✅ Robustness test passed: Correctly handled simulated connection drop and recovered."
    )
