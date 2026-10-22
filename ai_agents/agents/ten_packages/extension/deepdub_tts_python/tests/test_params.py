import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from unittest.mock import patch, AsyncMock

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Cmd,
    CmdResult,
    StatusCode,
    TenError,
)


class ExtensionTesterForPassthrough(ExtensionTester):
    """Trivial tester that just allows the extension to initialise so we can
    assert how the underlying client was constructed."""

    def check_hello(self, ten_env: TenEnvTester, result: CmdResult | None):
        if result is None:
            ten_env.stop_test(TenError(1, "CmdResult is None"))
            return
        if result.get_status_code() == StatusCode.OK:
            ten_env.stop_test()

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")
        ten_env_tester.send_cmd(
            new_cmd,
            lambda ten_env, result, _: self.check_hello(ten_env, result),
        )
        ten_env_tester.on_start_done()


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_params_passthrough(MockClient):
    """Config values land on the DeepdubTTSConfig passed to the client ctor."""
    mock_instance = MockClient.return_value
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()

    real_config = {
        "params": {
            "api_key": "the_key",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v-prompt-id",
            "model": "dd-etts-3.2",
            "locale": "es-ES",
            "sample_rate": 24000,
            "channels": 1,
            "format": "s16le",
            "temperature": 0.7,
            "tempo": 1.1,
            "prompt_boost": True,
        }
    }
    tester = ExtensionTesterForPassthrough()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(real_config))
    tester.run()

    MockClient.assert_called_once()
    _, kwargs = MockClient.call_args
    cfg = kwargs.get("config") or MockClient.call_args.args[0]

    assert cfg.api_key == "the_key"
    assert cfg.url == "wss://example.invalid/ws"
    assert cfg.voice_prompt_id == "v-prompt-id"
    assert cfg.model == "dd-etts-3.2"
    assert cfg.locale == "es-ES"
    assert cfg.sample_rate == 24000
    assert cfg.format == "s16le"
    assert cfg.temperature == 0.7
    assert cfg.tempo == 1.1
    assert cfg.prompt_boost is True


def test_missing_required_params_rejected():
    """Empty required fields → on_init raises before client is constructed."""
    bad = {"params": {"api_key": "", "url": "", "voice_prompt_id": ""}}
    received_error = {"flag": False}

    class T(ExtensionTester):
        def on_start(self, ten_env_tester):
            ten_env_tester.on_start_done()

        def on_data(self, ten_env, data):
            if data.get_name() == "error":
                received_error["flag"] = True
                ten_env.stop_test()

    tester = T()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(bad))
    tester.run()
    assert received_error["flag"], "Expected error event for missing params"


def test_invalid_sample_rate_rejected():
    bad = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
            "sample_rate": 12345,
        }
    }
    received_error = {"flag": False}

    class T(ExtensionTester):
        def on_start(self, ten_env_tester):
            ten_env_tester.on_start_done()

        def on_data(self, ten_env, data):
            if data.get_name() == "error":
                received_error["flag"] = True
                ten_env.stop_test()

    tester = T()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(bad))
    tester.run()
    assert received_error["flag"], "Expected error for bad sample_rate"
