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
# See the LICENSE file in the root directory for more information.
#
import asyncio
import json
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput, TTSWord
from ten_runtime import (
    Data,
    ExtensionTester,
    TenEnvTester,
)

from cartesia_tts.config import CartesiaTTSConfig
from cartesia_tts.extension import CartesiaTTSExtension


def _new_extension() -> CartesiaTTSExtension:
    extension = CartesiaTTSExtension("cartesia_tts")
    extension.ten_env = MagicMock()
    return extension


def test_terminal_subtitle_releases_sequence_state():
    """The counter survives audio end but is released by the terminal result."""

    async def _run():
        extension = _new_extension()
        extension.current_request_id = "req-1"
        extension.send_tts_text_result = AsyncMock()
        extension.client = MagicMock()
        extension.client.get_words = AsyncMock(
            side_effect=[
                (
                    [TTSWord(word="hello", start_ms=0, duration_ms=100)],
                    "req-1",
                    "hello",
                    False,
                ),
                ([], "req-1", "", True),
                ([], "", "", False),
            ]
        )

        await extension._process_transcription()

        results = [
            call.args[0]
            for call in extension.send_tts_text_result.call_args_list
        ]
        assert [result.text_result_end for result in results] == [False, True]
        assert [result.metadata["turn_seq_id"] for result in results] == [0, 1]
        assert [result.metadata["turn_status"] for result in results] == [0, 1]
        # The terminal subtitle released the counter.
        assert "req-1" not in extension.request_seq_id_map

    asyncio.run(_run())


def test_next_request_releases_previous_sequence_state():
    """A failed or interrupted request cannot keep its counter forever."""

    async def _run():
        extension = _new_extension()
        extension.config = CartesiaTTSConfig(api_key="test")
        extension.config.update_params()
        extension.config_update_lock = asyncio.Lock()
        extension.current_request_id = "req-1"
        extension.last_audio_end_request_id = "req-1"
        extension.request_seq_id_map = {"req-old": 4, "req-1": 7}
        extension.client = MagicMock()
        extension.client.set_current_request_id = AsyncMock()
        extension.client.text_to_speech = AsyncMock()
        extension.total_audio_bytes = 0
        extension.has_valid_text = False

        await extension.request_tts(
            TTSTextInput(request_id="req-2", text="hello", text_input_end=False)
        )

        # The new request allocates its counter with its first subtitle;
        # the older requests must not stay behind.
        assert extension.request_seq_id_map == {}

    asyncio.run(_run())


def test_interrupted_request_releases_sequence_state():
    """Interrupted requests never receive a terminal subtitle."""

    async def _run():
        extension = _new_extension()
        extension.current_request_id = "req-1"
        extension.request_seq_id_map["req-1"] = 3
        extension.send_tts_audio_end = AsyncMock()
        extension.send_usage_metrics = AsyncMock()
        extension.finish_request = AsyncMock()

        await extension._handle_completed_request(TTSAudioEndReason.INTERRUPTED)

        assert "req-1" not in extension.request_seq_id_map

    asyncio.run(_run())


class FakeClock:
    """Replace the extension's wall clock so elapsed time is exact."""

    def __init__(self, start: float = 1000.0):
        self.current = start

    def time(self) -> float:
        return self.current

    def monotonic(self) -> float:
        return self.current

    def advance(self, ms: float) -> None:
        self.current += ms / 1000.0


class ExtensionTesterAccounting(ExtensionTester):
    def __init__(self, clock: FakeClock):
        super().__init__()
        self.clock = clock
        self.audio_end_events: list[dict] = []
        self.text_results: list[dict] = []
        self.received_audio_bytes = 0
        self.first_frame_seen = False
        self.test_finished = threading.Event()

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        tts_input = TTSTextInput(
            request_id="accounting_request",
            text="hello accounting",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        if not self.first_frame_seen:
            self.first_frame_seen = True
            # The request started when the extension handled this frame.
            self.clock.advance(250)
        buf = audio_frame.lock_buf()
        try:
            self.received_audio_bytes += len(buf)
        finally:
            audio_frame.unlock_buf(buf)

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name not in ("tts_audio_end", "tts_text_result"):
            return
        json_str, _ = data.get_property_to_json(None)
        payload = json.loads(json_str)
        if name == "tts_audio_end":
            self.audio_end_events.append(payload)
            if not self.test_finished.is_set():
                self.test_finished.set()
                # Give a duplicate end event a chance to show up.
                threading.Timer(0.3, ten_env.stop_test).start()
        else:
            self.text_results.append(payload)


def test_audio_end_reports_emitted_bytes_and_elapsed_time():
    """tts_audio_end carries the emitted PCM duration and the event interval."""
    clock = FakeClock()
    sample_rate = 16000
    chunk = b"\x11\x22" * 800  # 1600 bytes == 50ms of mono 16-bit PCM

    mock_instance = MagicMock()
    pcm_queue = asyncio.Queue()
    words_queue = asyncio.Queue()

    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.cancel = AsyncMock()
    mock_instance.set_current_request_id = AsyncMock()

    async def mock_text_to_speech(t):
        request_id = t.request_id

        async def _stream():
            await pcm_queue.put((chunk, request_id, 0))
            await asyncio.sleep(0.02)
            await pcm_queue.put((chunk, request_id, 50))
            await words_queue.put(
                (
                    [TTSWord(word="hello", start_ms=0, duration_ms=100)],
                    request_id,
                    "hello",
                    False,
                )
            )
            await pcm_queue.put((None, request_id, 0))
            await words_queue.put(([], request_id, "", True))

        asyncio.create_task(_stream())

    mock_instance.text_to_speech = AsyncMock(side_effect=mock_text_to_speech)
    mock_instance.get_audio = AsyncMock(side_effect=pcm_queue.get)
    mock_instance.get_words = AsyncMock(side_effect=words_queue.get)

    config = {"params": {"api_key": "test_api_key"}}
    tester = ExtensionTesterAccounting(clock)

    with patch(
        "cartesia_tts.extension.CartesiaTTSClient", return_value=mock_instance
    ):
        with patch("cartesia_tts.extension.time", clock):
            tester.set_test_mode_single("cartesia_tts", json.dumps(config))
            tester.run()

    assert tester.first_frame_seen, "Did not receive any audio frame."
    assert tester.received_audio_bytes == 2 * len(chunk)

    assert (
        len(tester.audio_end_events) == 1
    ), "Expected exactly one tts_audio_end."
    payload = tester.audio_end_events[0]
    assert payload["request_id"] == "accounting_request"
    assert payload["request_total_audio_duration_ms"] == (
        tester.received_audio_bytes * 1000 // (sample_rate * 2)
    )
    # The interval is the elapsed time between the first audio frame and the
    # end event, not the audio duration.
    assert payload["request_event_interval_ms"] == 250

    terminal = [
        result for result in tester.text_results if result["text_result_end"]
    ]
    assert len(terminal) == 1
    assert terminal[0]["metadata"]["turn_status"] == 1
