import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedOK, InvalidStatus
from websockets.frames import Close
from websockets.http11 import Response

from stepfun_asr_python.config import StepFunASRConfig
from stepfun_asr_python.extension import StepFunASRExtension
from stepfun_asr_python.recognition import (
    StepFunASRRecognition,
    StepFunASRRecognitionCallback,
    TranscriptSegment,
)
from stepfun_asr_python.reconnect_manager import ReconnectManager


def _config(**overrides):
    params = {
        "api_key": "test-key",
        "url": "wss://example.test/asr",
        "model": "stepaudio-2.5-asr-stream",
        "language": "en",
        "sample_rate": 16000,
        "bits": 16,
        "channels": 1,
        "reconnect_max_attempts": 3,
        "reconnect_base_delay": 0,
        "finalize_timeout": 0.05,
    }
    params.update(overrides)
    return StepFunASRConfig.model_validate({"params": params})


def _extension() -> StepFunASRExtension:
    ext = StepFunASRExtension("stepfun_asr_python")
    ext.ten_env = MagicMock()
    ext.ten_env.send_data = AsyncMock()
    ext.ten_env.log_info = MagicMock()
    ext.ten_env.log_warn = MagicMock()
    ext.ten_env.log_error = MagicMock()
    ext.ten_env.log_debug = MagicMock()
    ext.config = _config()
    ext.reconnect_manager = ReconnectManager(max_attempts=3, base_delay=0)
    ext.send_asr_error = AsyncMock()
    ext.send_asr_result = AsyncMock()
    ext.send_asr_finalize_end = AsyncMock()
    ext.on_connected = AsyncMock()
    ext.on_disconnected = AsyncMock()
    ext.send_connect_delay_metrics = AsyncMock()
    return ext


class CapturingCallback(StepFunASRRecognitionCallback):
    def __init__(self):
        self.errors = []
        self.closed = 0

    async def on_error(self, message, error_type="", error_code=""):
        self.errors.append((message, error_type, error_code))

    async def on_close(self):
        self.closed += 1


class FakeWebSocket:
    def __init__(self, *, fail_send: Exception | None = None):
        self.open = True
        self.sent = []
        self._fail_send = fail_send

    async def send(self, raw):
        if self._fail_send is not None:
            raise self._fail_send
        self.sent.append(json.loads(raw))

    async def close(self):
        self.open = False


@pytest.mark.asyncio
async def test_finalize_includes_buffered_audio_boundary():
    ext = _extension()
    recognition = StepFunASRRecognition(
        ext.config, SimpleNamespace(), CapturingCallback()
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    frame = MagicMock()
    frame.get_buf.return_value = b"\x01\x02" * 160
    frame.lock_buf.return_value = memoryview(b"\x01\x02" * 160)
    frame.unlock_buf = MagicMock()
    frame.get_property_to_json.return_value = ("", None)
    ext.buffered_frames.put_nowait(frame)
    ext.buffered_frames_size = len(frame.get_buf())

    await ext._handle_finalize(
        "final-1",
        asyncio.get_running_loop().time(),
        {"session_id": "sess-a"},
    )

    assert recognition._pending[0].finalize_id == "final-1"
    assert recognition._pending[0].end == 320
    assert ext.buffered_frames.qsize() == 0


@pytest.mark.asyncio
async def test_fatal_state_still_completes_finalize():
    ext = _extension()
    ext._fatal = True
    ext.audio_frames_queue = asyncio.Queue()
    ext._input_task = None

    consumer = asyncio.create_task(ext._audio_frame_consumer())
    await ext.audio_frames_queue.put(
        ("final-fatal", asyncio.get_running_loop().time(), {"session_id": "s1"})
    )
    for _ in range(20):
        if "final-fatal" in ext._completed_finalizes:
            break
        await asyncio.sleep(0.01)
    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)

    ext.send_asr_finalize_end.assert_awaited()
    assert "final-fatal" in ext._completed_finalizes


@pytest.mark.asyncio
async def test_late_final_keeps_originating_session_metadata():
    ext = _extension()
    ext.metadata = {"session_id": "session-b"}
    ext.session_id = "session-b"
    ext.last_finalize_time = 99.0
    ext.finalize_id = "final-b"
    ext.first_audio_time = None
    ext.ttfw_sent = True

    emitted = []

    async def capture_result(result):
        # Reproduce the base helper's shallow metadata merge so the test
        # asserts against the JSON shape callers actually observe.
        payload = json.loads(result.model_dump_json())
        if ext.metadata is not None:
            metadata = dict(payload.get("metadata") or {})
            metadata.update(ext.metadata)
            payload["metadata"] = metadata
        emitted.append(payload)

    ext.send_asr_result = capture_result

    segment = TranscriptSegment(
        0,
        320,
        finalize_id="final-a",
        finalize_time=1.0,
        metadata={"session_id": "session-a"},
        session_id="session-a",
        timed_out=True,
    )
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "transcript": "hello",
            "item_id": "item-a",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        },
        segment,
    )

    assert emitted[0]["metadata"]["session_id"] == "session-a"
    assert emitted[0]["metadata"]["asr_info"]["finalize_id"] == "final-a"
    # Current turn TTLW context must remain intact.
    assert ext.last_finalize_time == 99.0
    assert ext.finalize_id == "final-b"
    assert ext.session_id == "session-b"
    ext.send_asr_finalize_end.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_failure_still_transfers_journal_ownership():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    recognition.websocket = FakeWebSocket(
        fail_send=RuntimeError("send failed")
    )
    recognition._started = True
    recognition._generation = 1

    audio = b"\x01\x02" * 160
    # Even when the live send fails, the frame is owned by the journal so
    # callers (flush) must not re-queue it into buffered_frames.
    assert await recognition.send_audio(audio) is True
    assert recognition._tail == len(audio)
    assert callback.closed == 1
    assert callback.errors


@pytest.mark.asyncio
async def test_send_path_connection_closed_ok_skips_asr_error():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    recognition.websocket = FakeWebSocket(
        fail_send=ConnectionClosedOK(Close(1000, "bye"), Close(1000, "bye"), True)
    )
    recognition._started = True
    recognition._generation = 1

    assert await recognition.send_audio(b"\x01\x02" * 160) is True
    assert callback.errors == []
    assert callback.closed == 1


@pytest.mark.asyncio
async def test_connect_failure_reports_disconnected_and_retries_via_public_hook():
    ext = _extension()
    ext.recognition = MagicMock()
    ext.recognition.start = AsyncMock(side_effect=ConnectionError("refused"))
    ext._schedule_reconnect = MagicMock()
    ext.reconnect_manager.base_delay = 0

    await ext.start_connection()

    ext.send_asr_error.assert_awaited()
    error = ext.send_asr_error.await_args.args[0]
    assert error.code != 0
    ext.on_disconnected.assert_awaited()
    assert ext.reconnect_manager.attempts == 1
    ext._schedule_reconnect.assert_called_once()


@pytest.mark.asyncio
async def test_auth_handshake_failure_is_fatal_without_retry():
    ext = _extension()
    ext.recognition = MagicMock()
    response = Response(401, "Unauthorized", Headers(), b"")
    ext.recognition.start = AsyncMock(side_effect=InvalidStatus(response))
    ext._schedule_reconnect = MagicMock()

    await ext.start_connection()

    assert ext._fatal is True
    vendor = ext.send_asr_error.await_args.args[1]
    assert vendor.code == "401"
    ext._schedule_reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_completed_item_bookkeeping_is_bounded():
    recognition = StepFunASRRecognition(
        _config(), SimpleNamespace(), CapturingCallback()
    )
    recognition._MAX_COMPLETED_ITEMS = 3
    for idx in range(5):
        recognition._remember_completed_item(f"item-{idx}")
    assert list(recognition._completed_items) == [
        "item-2",
        "item-3",
        "item-4",
    ]
    assert "item-0" not in recognition._completed_item_set


@pytest.mark.asyncio
async def test_on_data_routes_finalize_through_super():
    ext = _extension()
    ext.finalize = AsyncMock()
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-1", None)
    data.get_property_to_json.return_value = (
        json.dumps({"session_id": "sess-1"}),
        None,
    )

    # Bypass base connection checks by stubbing the wrapped path pieces used
    # inside AsyncASRBaseExtension.on_data.
    ext._safe_is_connected = MagicMock(return_value=True)
    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    assert ext.metadata["session_id"] == "sess-1"
    assert ext.finalize_id == "final-1"
    ext.finalize.assert_awaited_once()
