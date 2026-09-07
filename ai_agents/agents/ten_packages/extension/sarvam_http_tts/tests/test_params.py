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
import asyncio
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

from sarvam_http_tts.config import SarvamTTSConfig
from sarvam_http_tts.sarvam_tts import SarvamTTSClient


def test_bulbul_v3_removes_unsupported_params():
    config = SarvamTTSConfig(
        params={
            "model": "bulbul:v3",
            "pitch": 0.0,
            "loudness": 1.0,
            "pace": 1.0,
        }
    )

    config.update_params()

    assert config.params == {"model": "bulbul:v3", "pace": 1.0}


def test_bulbul_v2_keeps_pitch_and_loudness():
    config = SarvamTTSConfig(
        params={
            "model": "bulbul:v2",
            "pitch": 0.2,
            "loudness": 1.5,
        }
    )

    config.update_params()

    assert config.params["pitch"] == 0.2
    assert config.params["loudness"] == 1.5


@patch("sarvam_http_tts.sarvam_tts.AsyncClient")
def test_bulbul_v3_request_omits_unsupported_params(MockAsyncClient):
    config = SarvamTTSConfig(
        params={
            "api_subscription_key": "test_api_key",
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "pitch": 0.0,
            "loudness": 1.0,
        }
    )
    config.update_params()

    response = MagicMock(status_code=200)
    response.json.return_value = {"audios": []}
    mock_http_client = MockAsyncClient.return_value
    mock_http_client.post = AsyncMock(return_value=response)

    client = SarvamTTSClient(config=config, ten_env=MagicMock())

    async def collect_events():
        return [event async for event in client.get("hello", "request-id")]

    asyncio.run(collect_events())

    payload = mock_http_client.post.await_args.kwargs["json"]
    assert payload["model"] == "bulbul:v3"
    assert payload["text"] == "hello"
    assert "api_subscription_key" not in payload
    assert "pitch" not in payload
    assert "loudness" not in payload


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


@patch("sarvam_http_tts.extension.SarvamTTSClient")
def test_params_passthrough(MockSarvamTTSClient):
    """
    Tests that custom parameters passed in the configuration are correctly
    forwarded to the SarvamTTS client constructor.
    """
    print("Starting test_params_passthrough with mock...")

    # --- Mock Configuration ---
    mock_instance = MockSarvamTTSClient.return_value
    mock_instance.clean = AsyncMock()  # Required for clean shutdown in on_flush

    # --- Test Setup ---
    # Define a configuration with custom parameters inside 'params'.
    # api_subscription_key stays in params and is only stripped when making HTTP request
    real_params = {
        "api_subscription_key": "test_api_key",
        "target_language_code": "hi-IN",
    }

    real_config = {
        "params": real_params,
    }

    passthrough_params = {
        "api_subscription_key": "test_api_key",
        "target_language_code": "hi-IN",
        "speaker": "shubh",
        "speech_sample_rate": 24000,
        "pace": 1.0,
        "enable_preprocessing": False,
        "model": "bulbul:v3",
    }

    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single("sarvam_http_tts", json.dumps(real_config))

    print("Running passthrough test...")
    tester.run()
    print("Passthrough test completed.")

    # --- Assertions ---
    # Check that the SarvamTTSClient client was instantiated exactly once.
    MockSarvamTTSClient.assert_called_once()

    # Get the arguments that the mock was called with.
    # The constructor is called with keyword arguments like config=...
    # so we inspect the keyword arguments dictionary.
    _, call_kwargs = MockSarvamTTSClient.call_args
    called_config = call_kwargs["config"]

    # Verify that the 'params' dictionary in the config object passed to the
    # client constructor is identical to the one we defined in our test config.
    print(f"called_config: {called_config.params}")
    assert (
        called_config.params == passthrough_params
    ), f"Expected params to be {passthrough_params}, but got {called_config.params}"

    print("✅ Params passthrough test passed successfully.")
    print(f"✅ Verified params: {called_config.params}")
