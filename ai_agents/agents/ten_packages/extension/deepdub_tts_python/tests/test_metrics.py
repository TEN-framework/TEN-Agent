import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import json
from unittest.mock import patch, AsyncMock

from ten_runtime import ExtensionTester, TenEnvTester, Data
from ten_ai_base.struct import TTSTextInput


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


class ExtensionTesterMetrics(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.ttfb_received = False
        self.ttfb_value = -1
        self.audio_frame_received = False
        self.audio_end_received = False

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        tts_input = TTSTextInput(
            request_id="metrics_rid",
            text="hello, this is a metrics test.",
            text_input_end=True,
        )
        d = Data.create("tts_text_input")
        d.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(d)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name == "metrics":
            json_str, _ = data.get_property_to_json(None)
            metrics_data = json.loads(json_str)
            nested = metrics_data.get("metrics", {})
            if "ttfb" in nested:
                self.ttfb_received = True
                self.ttfb_value = nested.get("ttfb", -1)
        elif name == "tts_audio_end":
            self.audio_end_received = True
            if self.ttfb_received:
                ten_env.stop_test()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        if not self.audio_frame_received:
            self.audio_frame_received = True


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_ttfb_metric_is_sent(MockClient):
    mock_instance = _install_client_mock(MockClient)

    async def stream_with_delay(text: str):
        await asyncio.sleep(0.2)
        await mock_instance.on_audio(b"\x11\x22\x33" * 32)
        await mock_instance.on_finish()

    async def mock_send_text(text: str):
        asyncio.create_task(stream_with_delay(text))

    mock_instance.send_text.side_effect = mock_send_text

    config = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
        }
    }
    tester = ExtensionTesterMetrics()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(config))
    tester.run()

    assert tester.audio_frame_received
    assert tester.audio_end_received
    assert tester.ttfb_received
    assert (
        180 <= tester.ttfb_value <= 500
    ), f"TTFB out of expected band: {tester.ttfb_value}ms"
