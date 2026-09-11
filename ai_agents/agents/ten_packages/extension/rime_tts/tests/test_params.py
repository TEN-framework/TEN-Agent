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
import json
from typing import Any
from unittest.mock import patch, AsyncMock, MagicMock
import tempfile
import os
import asyncio
import filecmp
import shutil
import threading

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Cmd,
    CmdResult,
    StatusCode,
    Data,
)
from ten_ai_base.struct import TTSTextInput, TTSFlush
from ten_ai_base.message import ModuleVendorException, ModuleErrorVendorInfo


def test_vendor_metadata_omits_empty_values():
    from rime_tts.config import RimeTTSConfig
    from rime_tts.extension import RimeTTSExtension

    extension = RimeTTSExtension("tts")
    config = RimeTTSConfig(params={"modelId": "", "lang": ""})
    config.update_params()
    extension.config = config

    metadata = extension.vendor_metadata()

    assert "key" not in metadata
    assert "model" not in metadata
    assert "lang" not in metadata
    assert "api_key" not in metadata
    assert all(metadata.values())


def test_vendor_metadata_uses_lang_parameter_name():
    from rime_tts.config import RimeTTSConfig
    from rime_tts.extension import RimeTTSExtension

    extension = RimeTTSExtension("tts")
    config = RimeTTSConfig(params={"lang": "eng"})
    config.update_params()
    extension.config = config

    metadata = extension.vendor_metadata()

    assert metadata["lang"] == "eng"
    assert "language" not in metadata


# ================ test params passthrough ================
class ExtensionTesterForPassthrough(ExtensionTester):
    """A simple tester that just starts and stops, to allow checking constructor calls."""

    def check_hello(self, ten_env: TenEnvTester, result: CmdResult | None):
        if result is None:
            ten_env.stop_test()
            return
        statusCode = result.get_status_code()
        print("receive hello_world, status:" + str(statusCode))

        if statusCode == StatusCode.OK:
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


@patch("rime_tts.extension.RimeTTSClient")
def test_params_passthrough(MockRimeTTSClient):
    """
    Tests that custom parameters passed in the configuration are correctly
    forwarded to the RimeTTSClient constructor.
    """
    print("Starting test_params_passthrough with mock...")

    # --- Mock Configuration ---
    mock_instance = MockRimeTTSClient.return_value
    mock_instance.send_text = AsyncMock()
    mock_instance.close = AsyncMock()

    # Mock the client constructor to properly handle the response_msgs queue
    def mock_client_init(config, ten_env, vendor, response_msgs, *_):
        # Store the real queue passed by the extension
        mock_instance.response_msgs = response_msgs
        return mock_instance

    MockRimeTTSClient.side_effect = mock_client_init

    # --- Test Setup ---
    # Define a configuration with custom parameters inside 'params'.
    # These are the parameters we expect to be "passed through".
    real_params = {
        "api_key": "a_test_api_key",
        "speaker": "cove",
        "modelId": "mistv2",
        "lang": "eng",
        "samplingRate": 24000,
    }

    real_config = {
        "params": real_params,
    }

    passthrough_params = {
        "speaker": "cove",
        "modelId": "mistv2",
        "lang": "eng",
        "samplingRate": 24000,
        "audioFormat": "pcm",
        "segment": "immediate",
        "speedAlpha": 1.0,
    }

    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single("rime_tts", json.dumps(real_config))

    print("Running passthrough test...")
    tester.run()
    print("Passthrough test completed.")

    # --- Assertions ---
    # Check that the RimeTTSClient client was instantiated exactly once.
    MockRimeTTSClient.assert_called_once()

    # Get the arguments that the mock was called with.
    # The constructor is called with keyword arguments like config=...
    # so we inspect the keyword arguments dictionary.
    call_args, _ = MockRimeTTSClient.call_args
    called_config = call_args[0]

    # Verify that the 'params' dictionary in the config object passed to the
    # client constructor is identical to the one we defined in our test config.
    print(f"called_config: {called_config.params}")
    assert (
        called_config.params == passthrough_params
    ), f"Expected params to be {passthrough_params}, but got {called_config.params}"

    print("✅ Params passthrough test passed successfully.")
    print(f"✅ Verified params: {called_config.params}")
