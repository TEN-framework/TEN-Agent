import sys
from pathlib import Path

# Add project root to sys.path to allow running tests from this directory
# The project root is 6 levels up from the parent directory of this file.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from pathlib import Path
import json
from unittest.mock import patch

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Data,
)
from ten_ai_base.struct import TTSTextInput


# ================ test empty params ================
class ExtensionTesterEmptyParams(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.error_received = False
        self.error_code = None
        self.error_message = None
        self.error_module = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        """Called when test starts"""
        ten_env_tester.log_info("Test started")
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        ten_env.log_info(f"on_data name: {name}")

        if name == "error":
            self.error_received = True
            json_str, _ = data.get_property_to_json(None)
            error_data = json.loads(json_str)

            self.error_code = error_data.get("code")
            self.error_message = error_data.get("message", "")
            self.error_module = error_data.get("module", "")

            ten_env.log_info(
                f"Received error: code={self.error_code}, message={self.error_message}, module={self.error_module}"
            )

            # Stop test immediately
            ten_env.log_info("Error received, stopping test immediately")
            ten_env.stop_test()


def test_empty_params_fatal_error():
    """Test that empty params raises FATAL ERROR with code -1000"""

    print("Starting test_empty_params_fatal_error...")

    # Empty params configuration
    empty_params_config = {"params": {"api_key": ""}}

    tester = ExtensionTesterEmptyParams()
    tester.set_test_mode_single(
        "gandr_tts", json.dumps(empty_params_config)
    )

    print("Running test...")
    tester.run()
    print("Test completed.")

    # Verify FATAL ERROR was received
    assert tester.error_received, "Expected to receive error message"
    assert (
        tester.error_code == -1000
    ), f"Expected error code -1000 (FATAL_ERROR), got {tester.error_code}"
    assert tester.error_message is not None, "Error message should not be None"
    assert len(tester.error_message) > 0, "Error message should not be empty"

    print(
        f"✅ Empty params test passed: code={tester.error_code}, message={tester.error_message}"
    )
    print("Test verification completed successfully.")


# ================ test invalid api key ================
class ExtensionTesterInvalidApiKey(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.error_received = False
        self.error_code = None
        self.error_message = None
        self.error_module = None
        self.vendor_info = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        """Called when test starts, sends a TTS request to trigger the logic."""
        ten_env_tester.log_info(
            "Invalid API key test started, sending TTS request"
        )

        tts_input = TTSTextInput(
            request_id="test-request-invalid-key",
            text="This text will trigger API key validation.",
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)

        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        ten_env.log_info(f"on_data name: {name}")

        if name == "error":
            self.error_received = True
            json_str, _ = data.get_property_to_json(None)
            error_data = json.loads(json_str)

            self.error_code = error_data.get("code")
            self.error_message = error_data.get("message", "")
            self.error_module = error_data.get("module", "")
            self.vendor_info = error_data.get("vendor_info", {})

            ten_env.log_info(
                f"Received error: code={self.error_code}, message={self.error_message}"
            )
            ten_env.log_info("Error received, stopping test immediately")
            ten_env.stop_test()


from unittest.mock import AsyncMock


@patch("gandr_tts.gandr_tts.AsyncClient")
def test_invalid_api_key_error(MockAsyncClient):
    """Test that an invalid API key is handled correctly with a mock."""
    print("Starting test_invalid_api_key_error with mock...")

    # Mock API key error by raising exception in create() method
    mock_client = MockAsyncClient.return_value
    mock_client.stream.side_effect = Exception(
        "Client error '401 Unauthorized' for url 'https://tts.gandr.ai/v1/audio/speech'"
    )
    # Make aclose an AsyncMock so it can be awaited in clean()
    mock_client.aclose = AsyncMock()

    # Config with invalid API key
    invalid_key_config = {
        "params": {
            "api_key": "invalid_api_key_test",
        },
    }

    tester = ExtensionTesterInvalidApiKey()
    tester.set_test_mode_single("gandr_tts", json.dumps(invalid_key_config))

    print("Running test with mock...")
    tester.run()
    print("Test with mock completed.")

    # Verify FATAL ERROR was received for incorrect API key
    assert tester.error_received, "Expected to receive error message"
    assert (
        tester.error_code == -1000
    ), f"Expected error code -1000 (FATAL_ERROR), got {tester.error_code}"
    assert tester.error_message is not None, "Error message should not be None"
    assert (
        "401 Unauthorized" in tester.error_message
    ), "Error message should mention 401 Unauthorized"

    # Verify vendor_info
    vendor_info = tester.vendor_info
    assert vendor_info is not None, "Expected vendor_info to be present"
    assert (
        vendor_info.get("vendor") == "gandr"
    ), f"Expected vendor 'gandr', got {vendor_info.get('vendor')}"

    print(
        f"✅ Incorrect API key test passed: code={tester.error_code}, message={tester.error_message}"
    )
