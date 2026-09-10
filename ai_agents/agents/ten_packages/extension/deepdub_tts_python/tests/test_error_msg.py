import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
from unittest.mock import patch, AsyncMock

from ten_runtime import ExtensionTester, TenEnvTester, Data
from ten_ai_base.struct import TTSTextInput
from deepdub_tts_python.deepdub_tts import DeepdubTTSException


def _install_client_mock(mock_class):
    mock_instance = mock_class.return_value
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.cancel = AsyncMock()
    mock_instance.send_text = AsyncMock()
    mock_instance.wait_ready = AsyncMock()
    mock_instance.send_cancel = AsyncMock()

    def ctor(config, ten_env, on_audio, on_finish, on_error):
        mock_instance.on_audio = on_audio
        mock_instance.on_finish = on_finish
        mock_instance.on_error = on_error
        return mock_instance

    mock_class.side_effect = ctor
    return mock_instance


# ================ empty params → FATAL error from on_init ================
class ExtensionTesterEmptyParams(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.error_received = False
        self.error_code = None
        self.error_message = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        if data.get_name() != "error":
            return
        json_str, _ = data.get_property_to_json(None)
        payload = json.loads(json_str)
        self.error_received = True
        self.error_code = payload.get("code")
        self.error_message = payload.get("message", "")
        ten_env.stop_test()


def test_empty_params_fatal_error():
    empty_params_config = {
        "params": {
            "api_key": "",
            "url": "",
            "voice_prompt_id": "",
        }
    }
    tester = ExtensionTesterEmptyParams()
    tester.set_test_mode_single(
        "deepdub_tts_python", json.dumps(empty_params_config)
    )
    tester.run()

    assert tester.error_received, "Expected error event"
    assert (
        tester.error_code == -1000
    ), f"Expected FATAL_ERROR (-1000), got {tester.error_code}"
    assert tester.error_message


# ================ vendor error during synthesis → NON_FATAL ================
class ExtensionTesterVendorError(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.error_received = False
        self.error_code = None
        self.vendor_info = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        tts_input = TTSTextInput(
            request_id="rid-err",
            text="trigger vendor error",
            text_input_end=True,
        )
        d = Data.create("tts_text_input")
        d.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(d)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        if data.get_name() != "error":
            return
        json_str, _ = data.get_property_to_json(None)
        payload = json.loads(json_str)
        self.error_received = True
        self.error_code = payload.get("code")
        self.vendor_info = payload.get("vendor_info", {})
        ten_env.stop_test()


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_vendor_error_propagated(MockClient):
    import asyncio

    mock_instance = _install_client_mock(MockClient)

    async def fire_error(text: str):
        await mock_instance.on_error(
            DeepdubTTSException("vendor blew up", code=503)
        )

    async def mock_send_text(text: str):
        asyncio.create_task(fire_error(text))

    mock_instance.send_text.side_effect = mock_send_text

    config = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
        }
    }
    tester = ExtensionTesterVendorError()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(config))
    tester.run()

    assert tester.error_received
    assert (
        tester.error_code == 1000
    ), f"Expected NON_FATAL_ERROR (1000), got {tester.error_code}"
    assert tester.vendor_info is not None
    assert tester.vendor_info.get("vendor") == "deepdub"
    assert tester.vendor_info.get("code") == "503"
    assert "vendor blew up" in tester.vendor_info.get("message", "")
