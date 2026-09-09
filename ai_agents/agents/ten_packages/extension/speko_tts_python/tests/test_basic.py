import sys
from pathlib import Path

# Add project root to sys.path to allow running tests from this directory
# The project root is 6 levels up from the parent directory of this file.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock

from ten_runtime import (
    ExtensionTester,
    TenEnvTester,
    Data,
)
from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput, TTSFlush, TTS2HttpResponseEventType


class ExtensionTesterBasic(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.audio_start_received = False
        self.audio_end_received = False
        self.ttfb_metric_received = False
        self.received_audio_bytes = 0

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        ten_env_tester.log_info("Basic test started, sending TTS request.")

        tts_input = TTSTextInput(
            request_id="tts_request_1",
            text="hello word, hello agora",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name == "tts_audio_start":
            self.audio_start_received = True
        elif name == "metrics":
            json_str, _ = data.get_property_to_json(None)
            metrics_data = json.loads(json_str)
            if "ttfb" in metrics_data.get("metrics", {}):
                self.ttfb_metric_received = True
        elif name == "tts_audio_end":
            self.audio_end_received = True
            ten_env.stop_test()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        buf = audio_frame.lock_buf()
        try:
            self.received_audio_bytes += len(bytes(buf))
        finally:
            audio_frame.unlock_buf(buf)


async def mock_get_generator():
    """Yield a few PCM chunks, then END."""
    for _ in range(3):
        await asyncio.sleep(0.01)
        yield (
            b"\x01\x02" * 1024,
            TTS2HttpResponseEventType.RESPONSE,
        )
    yield (None, TTS2HttpResponseEventType.END)


@patch("ten_packages.extension.speko_tts_python.extension.SpekoTTSClient")
def test_basic_streaming(MockSpekoTTSClient):
    """Audio chunks stream through as pcm_frames with start/end events."""
    mock_instance = MagicMock()
    MockSpekoTTSClient.return_value = mock_instance

    def mock_get(text: str, request_id: str):
        return mock_get_generator()

    mock_instance.get = mock_get
    mock_instance.cancel = AsyncMock()
    mock_instance.clean = AsyncMock()
    mock_instance.get_extra_metadata = MagicMock(
        return_value={"route": "MockProvider/mock-model"}
    )

    config = {
        "params": {
            "api_key": "test_api_key",
            "language": "en",
        },
    }

    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("speko_tts_python", json.dumps(config))
    tester.run()

    assert tester.audio_start_received, "tts_audio_start was not received"
    assert tester.audio_end_received, "tts_audio_end was not received"
    assert tester.ttfb_metric_received, "ttfb metric was not received"
    assert (
        tester.received_audio_bytes == 3 * 2048
    ), f"unexpected audio byte count: {tester.received_audio_bytes}"


class ExtensionTesterFlush(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.first_audio_frame_received = False
        self.audio_end_received = False
        self.audio_end_reason = None
        self.flush_end_received = False

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        ten_env_tester.log_info("Flush test started, sending TTS request.")

        tts_input = TTSTextInput(
            request_id="tts_request_flush",
            text=(
                "a very long sentence designed to stream for a while so "
                "the flush lands mid-request"
            ),
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        # Flush once the request is demonstrably mid-stream.
        if not self.first_audio_frame_received:
            self.first_audio_frame_received = True
            flush = TTSFlush(flush_id="tts_request_flush")
            flush_data = Data.create("tts_flush")
            flush_data.set_property_from_json(None, flush.model_dump_json())
            ten_env.send_data(flush_data)

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name == "tts_audio_end":
            self.audio_end_received = True
            json_str, _ = data.get_property_to_json(None)
            payload = json.loads(json_str)
            self.audio_end_reason = payload.get("reason")
        elif name == "tts_flush_end":
            self.flush_end_received = True
            ten_env.stop_test()


@patch("ten_packages.extension.speko_tts_python.extension.SpekoTTSClient")
def test_flush_logic(MockSpekoTTSClient):
    """A tts_flush interrupts the stream and reports INTERRUPTED."""
    mock_instance = MagicMock()
    MockSpekoTTSClient.return_value = mock_instance

    cancelled = asyncio.Event()

    async def slow_generator():
        for _ in range(100):
            if cancelled.is_set():
                yield (None, TTS2HttpResponseEventType.FLUSH)
                return
            await asyncio.sleep(0.05)
            yield (
                b"\x01\x02" * 512,
                TTS2HttpResponseEventType.RESPONSE,
            )
        yield (None, TTS2HttpResponseEventType.END)

    def mock_get(text: str, request_id: str):
        return slow_generator()

    async def mock_cancel():
        cancelled.set()

    mock_instance.get = mock_get
    mock_instance.cancel = mock_cancel
    mock_instance.clean = AsyncMock()
    mock_instance.get_extra_metadata = MagicMock(return_value={})

    config = {
        "params": {
            "api_key": "test_api_key",
        },
    }

    tester = ExtensionTesterFlush()
    tester.set_test_mode_single("speko_tts_python", json.dumps(config))
    tester.run()

    assert tester.flush_end_received, "tts_flush_end was not received"
    assert tester.audio_end_received, "tts_audio_end was not received"
    assert (
        tester.audio_end_reason == TTSAudioEndReason.INTERRUPTED
    ), f"unexpected audio end reason: {tester.audio_end_reason}"
