#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from unittest.mock import patch
import json

from ten_runtime import (
    Cmd,
    CmdResult,
    ExtensionTester,
    StatusCode,
    TenEnvTester,
    TenError,
)
from .mock_client import MockClientStream


# ================ test params passthrough ================
class ExtensionTesterForPassthrough(ExtensionTester):
    """A simple tester that just starts and stops, to allow checking constructor calls."""

    def check_hello(self, ten_env: TenEnvTester, result: CmdResult | None):
        if result is None:
            ten_env.stop_test(TenError(1, "CmdResult is None"))
            return
        statusCode = result.get_status_code()
        print("receive hello_world, status:" + str(statusCode))

        if statusCode == StatusCode.OK:
            # TODO: move stop_test() to where the test passes
            ten_env.stop_test()

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")

        print("send hello_world")
        ten_env_tester.send_cmd(
            new_cmd,
            lambda ten_env, result, _: self.check_hello(ten_env, result),
        )

        print("tester on_start_done")
        ten_env_tester.on_start_done()


@patch("cosy_tts_python.extension.CosyTTSClient")
def test_params_passthrough(MockCosyTTSClient):
    """
    Tests that custom parameters passed in the configuration are correctly
    forwarded to the CosyTTSClient client constructor.
    """
    print("Starting test_params_passthrough with mock...")

    # --- Mock Setup ---
    mock_instance = MockCosyTTSClient.return_value
    MockClientStream().configure(mock_instance)

    # --- Test Setup ---
    # Define a configuration with custom, arbitrary parameters inside 'params'.
    # These are the parameters we expect to be "passed through".
    passthrough_params = {
        "api_key": "a_valid_key",
        "model": "cosyvoice-v1",
        "sample_rate": 16000,
        "voice": "longxiaochun",
        "url": "wss://example.com/api-ws/v1/inference",
        "instruction": "speak happily",
        "future_protocol_parameter": "future-value",
    }
    passthrough_config = {
        "url": "wss://top-level.example.com/api-ws/v1/inference",
        "headers": {"X-Custom-Header": "custom-value"},
        "params": passthrough_params,
    }

    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single(
        "cosy_tts_python", json.dumps(passthrough_config)
    )

    print("Running passthrough test...")
    tester.run()
    print("Passthrough test completed.")

    # --- Assertions ---
    # Check that the CosyTTSClient client was instantiated exactly once.
    MockCosyTTSClient.assert_called_once()

    # Get the arguments that the mock was called with.
    # The constructor signature is (self, config, ten_env, vendor),
    # so we inspect the 'config' object at index 1 of the call arguments.
    call_args, call_kwargs = MockCosyTTSClient.call_args
    called_config = call_args[0]

    # Extension-owned and dedicated SDK arguments are extracted from params.
    # Everything left is forwarded to DashScope unchanged.
    assert called_config.params == {
        "instruction": "speak happily",
        "future_protocol_parameter": "future-value",
    }

    print("✅ Params passthrough test passed successfully.")
    print(f"✅ Verified params: {called_config.params}")
    assert called_config.url == passthrough_config["url"]
    assert called_config.headers == passthrough_config["headers"]
    assert called_config.provider_params() == {
        "instruction": "speak happily",
        "future_protocol_parameter": "future-value",
    }
