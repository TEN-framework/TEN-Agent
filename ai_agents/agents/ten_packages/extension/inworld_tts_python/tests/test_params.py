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
from unittest.mock import AsyncMock, patch, MagicMock

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Cmd,
    CmdResult,
    StatusCode,
    TenError,
)


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


@patch("inworld_tts_python.extension.InworldTTSClient")
def test_params_passthrough(MockInworldTTSClient):
    """
    Tests that custom parameters passed in the configuration are correctly
    forwarded to the OpenaiTTS client constructor.
    """
    print("Starting test_params_passthrough with mock...")

    # --- Mock Configuration ---
    mock_instance = MockInworldTTSClient.return_value
    mock_instance.clean = AsyncMock()  # Required for clean shutdown in on_flush

    # --- Test Setup ---
    # Define a configuration with custom parameters inside 'params'.
    # api_key stays in params and is only stripped when making HTTP request
    real_params = {
        "api_key": "test_api_key",
        "voice": "Wendy",
        "model": "inworld-tts-1.5-max",
        "sample_rate": 24000,
        "temperature": 0.7,
    }

    real_config = {
        "params": real_params,
    }

    # update_params() fills the documented defaults; everything given in
    # the config must pass through untouched.
    passthrough_params = {
        "api_key": "test_api_key",
        "voice": "Wendy",
        "model": "inworld-tts-1.5-max",
        "sample_rate": 24000,
        "temperature": 0.7,
        "encoding": "LINEAR16",
        "speaking_rate": 1.0,
        "text_normalization": "ON",
    }

    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single("inworld_tts_python", json.dumps(real_config))

    print("Running passthrough test...")
    tester.run()
    print("Passthrough test completed.")

    # --- Assertions ---
    # Check that the InworldTTSClient client was instantiated exactly once.
    MockInworldTTSClient.assert_called_once()

    # Get the arguments that the mock was called with.
    # The constructor is called with keyword arguments like config=...
    # so we inspect the keyword arguments dictionary.
    _, call_kwargs = MockInworldTTSClient.call_args
    called_config = call_kwargs["config"]

    # Verify that the 'params' dictionary in the config object passed to the
    # client constructor is identical to the one we defined in our test config.
    print(f"called_config: {called_config.params}")
    assert (
        called_config.params == passthrough_params
    ), f"Expected params to be {passthrough_params}, but got {called_config.params}"

    print("✅ Params passthrough test passed successfully.")
    print(f"✅ Verified params: {called_config.params}")
