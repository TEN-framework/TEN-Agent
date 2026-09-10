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


class StateMachineExtensionTester(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.audio_start_events: list[str] = []
        self.audio_end_events: list[tuple[str, int]] = []
        self.request1_id = "state_req_1"
        self.request2_id = "state_req_2"
        self.test_completed = False

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        for rid, text in (
            (self.request1_id, "First request text"),
            (self.request2_id, "Second request text"),
        ):
            t = TTSTextInput(request_id=rid, text=text, text_input_end=True)
            d = Data.create("tts_text_input")
            d.set_property_from_json(None, t.model_dump_json())
            ten_env_tester.send_data(d)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data: Data) -> None:
        name = data.get_name()
        payload_str, _ = data.get_property_to_json("")
        if not payload_str:
            return
        payload = json.loads(payload_str)
        if name == "tts_audio_start":
            self.audio_start_events.append(payload.get("request_id", ""))
        elif name == "tts_audio_end":
            self.audio_end_events.append(
                (payload.get("request_id", ""), payload.get("reason", 0))
            )
            if len(self.audio_end_events) == 2:
                self.test_completed = True
                ten_env.stop_test()


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_sequential_requests_state_machine(MockClient):
    """Two requests sent back-to-back are processed in order; each one gets
    its own audio_start/audio_end pair with the matching request_id."""
    mock_instance = MockClient.return_value
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

    MockClient.side_effect = ctor

    first_done = asyncio.Event()

    async def stream_first():
        await mock_instance.on_audio(b"\x01\x02" * 16)
        await mock_instance.on_finish()
        first_done.set()

    async def stream_second():
        await first_done.wait()
        await mock_instance.on_audio(b"\x03\x04" * 16)
        await mock_instance.on_finish()

    async def mock_send_text(text: str):
        if "First" in text:
            asyncio.create_task(stream_first())
        else:
            asyncio.create_task(stream_second())

    mock_instance.send_text.side_effect = mock_send_text

    tester = StateMachineExtensionTester()
    config = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
        }
    }
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(config))
    tester.run()

    assert tester.test_completed
    assert len(tester.audio_start_events) == 2
    assert len(tester.audio_end_events) == 2
    # Both completed with success reason (== 1 in the TTSAudioEndReason enum).
    assert tester.audio_end_events[0][1] == 1
    assert tester.audio_end_events[1][1] == 1

    # Strict ordering: req1 starts and ends before req2 starts and ends.
    i1 = tester.audio_start_events.index(tester.request1_id)
    i2 = tester.audio_start_events.index(tester.request2_id)
    assert i1 < i2

    e1 = next(
        i
        for i, e in enumerate(tester.audio_end_events)
        if e[0] == tester.request1_id
    )
    e2 = next(
        i
        for i, e in enumerate(tester.audio_end_events)
        if e[0] == tester.request2_id
    )
    assert e1 < e2
