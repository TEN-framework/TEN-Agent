import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import json
from typing import Any
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


class ExtensionTesterRobustness(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.first_request_error: dict[str, Any] | None = None
        self.second_request_successful = False
        self.ten_env: TenEnvTester | None = None

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        self.ten_env = ten_env_tester
        t1 = TTSTextInput(
            request_id="rid_fail",
            text="trigger a simulated drop",
            text_input_end=True,
        )
        d = Data.create("tts_text_input")
        d.set_property_from_json(None, t1.model_dump_json())
        ten_env_tester.send_data(d)
        ten_env_tester.on_start_done()

    def send_second_request(self):
        if self.ten_env is None:
            return
        t2 = TTSTextInput(
            request_id="rid_ok",
            text="this one succeeds after reconnect",
            text_input_end=True,
        )
        d = Data.create("tts_text_input")
        d.set_property_from_json(None, t2.model_dump_json())
        self.ten_env.send_data(d)

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        json_str, _ = data.get_property_to_json(None)
        if not json_str:
            return
        payload = json.loads(json_str)

        if name == "error" and payload.get("id") == "rid_fail":
            self.first_request_error = payload
            self.send_second_request()

        if payload.get("id") == "rid_ok" and name == "tts_audio_end":
            self.second_request_successful = True
            ten_env.stop_test()


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_recover_after_vendor_error(MockClient):
    """First request fails via on_error; subsequent request still succeeds."""
    mock_instance = _install_client_mock(MockClient)

    call_count = {"n": 0}

    async def stream_first_then_succeed(text: str):
        call_count["n"] += 1
        if call_count["n"] == 1:
            await mock_instance.on_error(
                DeepdubTTSException("Simulated vendor drop", code=503)
            )
        else:
            await mock_instance.on_audio(b"\x44\x55\x66" * 32)
            await mock_instance.on_finish()

    async def mock_send_text(text: str):
        asyncio.create_task(stream_first_then_succeed(text))

    mock_instance.send_text.side_effect = mock_send_text

    config = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
        }
    }
    tester = ExtensionTesterRobustness()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(config))
    tester.run()

    assert tester.first_request_error is not None
    assert (
        tester.first_request_error.get("code") == 1000
    ), f"Expected NON_FATAL_ERROR, got {tester.first_request_error.get('code')}"
    vendor_info = tester.first_request_error.get("vendor_info")
    assert vendor_info and vendor_info.get("vendor") == "deepdub"
    assert tester.second_request_successful
