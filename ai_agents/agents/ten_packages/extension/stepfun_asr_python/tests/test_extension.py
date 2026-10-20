import asyncio
import json
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import ModuleMetricKey
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
        "server_vad": False,
    }
    params.update(overrides)
    return StepFunASRConfig.model_validate({"params": params})


def _extension(*, mock_result: bool = True) -> StepFunASRExtension:
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
    if mock_result:
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
        self.messages = []

    async def on_result(self, message, segment: TranscriptSegment):
        self.messages.append((message, segment))

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


class ExhaustingWebSocket(FakeWebSocket):
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def _real_output_extension() -> StepFunASRExtension:
    ext = _extension(mock_result=False)
    ext.send_asr_error = StepFunASRExtension.send_asr_error.__get__(ext)
    ext.send_asr_finalize_end = (
        StepFunASRExtension.send_asr_finalize_end.__get__(ext)
    )
    ext.on_connected = StepFunASRExtension.on_connected.__get__(ext)
    ext.on_disconnected = StepFunASRExtension.on_disconnected.__get__(ext)
    ext.send_connect_delay_metrics = (
        StepFunASRExtension.send_connect_delay_metrics.__get__(ext)
    )
    return ext


class FakeFrame:
    def __init__(self, payload: bytes, metadata: dict | None = None):
        self.payload = bytearray(payload)
        self._metadata = metadata

    def get_buf(self):
        return bytes(self.payload)

    def lock_buf(self):
        return self.payload

    def unlock_buf(self, _buf):
        return None

    def get_property_to_json(self, key):
        if key == "metadata" and self._metadata is not None:
            return json.dumps(self._metadata), None
        return "", None


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

    frame = FakeFrame(b"\x01\x02" * 160)
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
async def test_finalize_keeps_captured_session_after_buffer_absorption():
    ext = _extension()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    frame = FakeFrame(b"\x01\x02" * 160, {"session_id": "session-a"})
    ext.buffered_frames.put_nowait(frame)
    ext.buffered_frames_size = len(frame.get_buf())

    await ext._handle_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-b"},
    )

    segment = recognition._pending[0]
    assert segment.session_id == "session-b"
    assert segment.metadata["session_id"] == "session-b"


@pytest.mark.asyncio
async def test_empty_finalize_clears_its_ttlw_context():
    ext = _extension()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    received_at = asyncio.get_running_loop().time()
    await ext._handle_finalize(
        "empty-final",
        received_at,
        {"session_id": "session-a"},
    )

    assert ext.last_finalize_time is None
    ext.send_asr_finalize_end.assert_awaited_once()


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
async def test_late_final_keeps_originating_session_and_ttlw_via_real_helper():
    ext = _extension(mock_result=False)
    ext.metadata = {"session_id": "session-b"}
    ext.session_id = "session-b"
    ext.last_finalize_time = 99.0
    ext.finalize_id = "final-b"
    ext.first_audio_time = None
    ext.ttfw_sent = True
    ext._send_metrics_ttfw = AsyncMock()
    ext._send_metrics_ttlw = AsyncMock()

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

    sent = ext.ten_env.send_data.await_args.args[0]
    payload = json.loads(sent.get_property_to_json(None)[0])
    assert payload["metadata"]["session_id"] == "session-a"
    assert payload["metadata"]["asr_info"]["finalize_id"] == "final-a"
    ext._send_metrics_ttlw.assert_not_awaited()
    assert ext.last_finalize_time == 99.0
    assert ext.finalize_id == "final-b"
    assert ext.session_id == "session-b"
    ext.send_asr_finalize_end.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_final_leaves_ttlw_timestamp_cleared():
    ext = _extension(mock_result=False)
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"
    ext.last_finalize_time = 10.0
    ext.finalize_id = "final-a"
    ext.ttfw_sent = True
    ext._send_metrics_ttfw = AsyncMock()
    ext._send_metrics_ttlw = AsyncMock()

    segment = TranscriptSegment(
        0,
        320,
        finalize_id="final-a",
        finalize_time=10.0,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "transcript": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        },
        segment,
    )

    ext._send_metrics_ttlw.assert_awaited()
    assert ext.last_finalize_time is None


@pytest.mark.asyncio
async def test_send_failure_journals_but_reports_delivery_false():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    recognition.websocket = FakeWebSocket(fail_send=RuntimeError("send failed"))
    recognition._started = True
    recognition._generation = 1

    audio = b"\x01\x02" * 160
    assert await recognition.send_audio(audio) is False
    assert recognition._tail == len(audio)
    assert callback.closed == 1
    assert callback.errors


@pytest.mark.asyncio
async def test_flush_does_not_requeue_journaled_failed_delivery():
    ext = _extension()
    recognition = StepFunASRRecognition(
        ext.config, SimpleNamespace(), CapturingCallback()
    )
    recognition.websocket = FakeWebSocket(fail_send=RuntimeError("send failed"))
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    frame = FakeFrame(b"\x01\x02" * 160)
    ext.buffered_frames_size = 320
    assert await ext._consume_buffered_frame(frame) is True
    assert recognition._tail == 320
    assert ext.buffered_frames.qsize() == 0


@pytest.mark.asyncio
async def test_failed_first_delivery_does_not_set_first_audio_time():
    ext = _extension()
    recognition = StepFunASRRecognition(
        ext.config, SimpleNamespace(), CapturingCallback()
    )
    recognition.websocket = FakeWebSocket(fail_send=RuntimeError("send failed"))
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    delivered = await ext.send_audio(FakeFrame(b"\x01\x02" * 160), "sess")
    assert delivered is False
    assert ext.first_audio_time is None
    assert recognition._tail == 320


@pytest.mark.asyncio
async def test_send_path_connection_closed_ok_skips_asr_error():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    recognition.websocket = FakeWebSocket(
        fail_send=ConnectionClosedOK(
            Close(1000, "bye"), Close(1000, "bye"), True
        )
    )
    recognition._started = True
    recognition._generation = 1

    assert await recognition.send_audio(b"\x01\x02" * 160) is False
    assert callback.errors == []
    assert callback.closed == 1


@pytest.mark.asyncio
async def test_reconnect_loop_continues_after_scheduled_failure():
    ext = _extension()
    ext.recognition = MagicMock()
    attempts = {"n": 0}

    async def flaky_start():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError(f"refused-{attempts['n']}")
        ext.recognition.is_connected = MagicMock(return_value=True)

    ext.recognition.start = AsyncMock(side_effect=flaky_start)
    ext.recognition.is_connected = MagicMock(return_value=False)
    ext.reconnect_manager = ReconnectManager(max_attempts=5, base_delay=0)

    # First failure from outside schedules the recovery owner.
    await ext.start_connection()
    assert ext._recovery_task is not None
    await asyncio.wait_for(ext._recovery_task, timeout=2)

    assert attempts["n"] == 3
    assert ext._fatal is False
    assert ext.reconnect_manager.attempts == 0 or ext.is_connected()


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
async def test_server_vad_segment_keeps_originating_session_metadata():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), callback
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition.send_audio(
        b"\x03\x04" * 160,
        metadata={"session_id": "session-b"},
        session_id="session-b",
    )
    # Session boundary sealed span A before B's audio.
    assert recognition._pending[0].session_id == "session-a"
    assert recognition._pending[0].metadata["session_id"] == "session-a"
    assert recognition._current.session_id == "session-b"

    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-b",
            "audio_end_ms": 20,
        }
    )
    # Force end within sent range for the open B span.
    recognition._sent = recognition._tail
    sealed = recognition._pending[-1]
    assert sealed.session_id in {"session-a", "session-b"}

    ext = _extension(mock_result=False)
    ext.metadata = {"session_id": "session-b"}
    ext.session_id = "session-b"
    ext.ttfw_sent = True
    ext._send_metrics_ttfw = AsyncMock()
    ext._send_metrics_ttlw = AsyncMock()
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "transcript": "from-a",
            "words": [{"word": "from-a", "start": 0.0, "end": 0.1}],
        },
        recognition._pending[0],
    )
    sent = ext.ten_env.send_data.await_args.args[0]
    payload = json.loads(sent.get_property_to_json(None)[0])
    assert payload["metadata"]["session_id"] == "session-a"


@pytest.mark.asyncio
async def test_replay_final_for_published_span_survives_earlier_pending_final():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), callback
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "a"},
        session_id="a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a0",
            "audio_end_ms": 20,
        }
    )
    seg_a = recognition._pending[0]

    await recognition.send_audio(
        b"\x03\x04" * 160,
        metadata={"session_id": "b"},
        session_id="b",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-b0",
            "audio_end_ms": 40,
        }
    )
    seg_b = recognition._pending[1]
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b0",
            "transcript": "b",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        }
    )
    assert seg_b.published is True

    recognition._generation = 2
    recognition._items.clear()
    recognition._item_starts.clear()
    recognition._completed_item_set.clear()
    recognition._completed_items.clear()
    recognition._awaiting_ack.clear()
    seg_a.generation = 2
    seg_b.generation = 2
    recognition._items["item-a1"] = seg_a
    recognition._items["item-b1"] = seg_b

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a1",
            "transcript": "a",
            "words": [{"word": "a", "start": 0.0, "end": 0.1}],
        }
    )
    assert recognition._items.get("item-b1") is seg_b

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b1",
            "transcript": "b",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        }
    )
    assert callback.errors == []
    assert not any(
        code == "missing_commit_boundary" for _, _, code in callback.errors
    )


@pytest.mark.asyncio
async def test_replayed_vad_item_uses_retained_pending_segment():
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), callback
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-old",
            "audio_end_ms": 20,
        }
    )
    retained = recognition._pending[0]

    recognition._generation = 2
    recognition._items.clear()
    retained.generation = 2
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.delta",
            "item_id": "item-replayed",
            "text": "hello",
        }
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-replayed",
            "audio_end_ms": 20,
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-replayed",
            "transcript": "hello",
        }
    )

    assert callback.errors == []
    assert callback.messages[0][1] is retained
    assert callback.messages[-1][1] is retained
    assert retained.published is True


@pytest.mark.asyncio
async def test_delayed_vad_boundary_preserves_suffix_session_in_result():
    ext = _extension(mock_result=False)
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 320,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 10,
        }
    )
    await recognition.send_audio(
        b"\x03\x04" * 160,
        metadata={"session_id": "session-b"},
        session_id="session-b",
    )

    suffix = recognition._pending[1]
    assert suffix.metadata["session_id"] == "session-a"
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a-suffix",
            "transcript": "suffix",
            "words": [{"word": "suffix", "start": 0.0, "end": 0.1}],
        },
        suffix,
    )

    sent = ext.ten_env.send_data.await_args.args[0]
    payload = json.loads(sent.get_property_to_json(None)[0])
    assert payload["metadata"]["session_id"] == "session-a"


@pytest.mark.asyncio
async def test_finalize_waits_for_pending_vad_result():
    ext = _extension(mock_result=False)
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 20,
        }
    )
    await ext._handle_finalize(
        "final-a",
        asyncio.get_running_loop().time(),
        {"session_id": "session-a"},
    )

    assert ext.send_asr_finalize_end.await_count == 0
    assert recognition._pending[0].finalize_id == "final-a"

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a",
            "transcript": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        }
    )

    assert ext.send_asr_finalize_end.await_count == 1


@pytest.mark.asyncio
async def test_empty_finalize_does_not_claim_other_session_pending_vad():
    ext = _real_output_extension()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 20,
        }
    )
    assert recognition._pending[0].session_id == "session-a"
    assert recognition._current.start == recognition._tail

    await ext._handle_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-b"},
    )

    pending_a = recognition._pending[0]
    assert pending_a.finalize_id is None
    assert pending_a.session_id == "session-a"
    assert pending_a.metadata["session_id"] == "session-a"

    outputs = [
        json.loads(data.get_property_to_json(None)[0])
        for call in ext.ten_env.send_data.await_args_list
        for data in [call.args[0]]
        if data.get_name() in {"asr_result", "asr_finalize_end"}
    ]
    finalize_ends = [item for item in outputs if "finalize_id" in item]
    assert [item["finalize_id"] for item in finalize_ends] == ["final-b"]
    assert all(
        item.get("metadata", {}).get("session_id") != "session-a"
        or item.get("finalize_id") != "final-b"
        for item in outputs
    )


@pytest.mark.asyncio
async def test_finalize_binds_new_current_audio_not_older_vad_segment():
    ext = _real_output_extension()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 20,
        }
    )
    await recognition.send_audio(
        b"\x03\x04" * 160,
        metadata={"session_id": "session-b"},
        session_id="session-b",
    )
    await ext._handle_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-b"},
    )

    await recognition._handle_message(
        {
            "type": "input_audio_buffer.committed",
            "item_id": "item-b",
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a",
            "transcript": "from-a",
            "words": [{"word": "from-a", "start": 0.0, "end": 0.1}],
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b",
            "transcript": "from-b",
            "words": [{"word": "from-b", "start": 0.0, "end": 0.1}],
        }
    )

    outputs = [
        json.loads(data.get_property_to_json(None)[0])
        for call in ext.ten_env.send_data.await_args_list
        for data in [call.args[0]]
        if data.get_name() in {"asr_result", "asr_finalize_end"}
    ]
    results = [item for item in outputs if "text" in item]
    finalize_ends = [item for item in outputs if "finalize_id" in item]
    assert results[0]["text"] == "from-a"
    assert results[0]["metadata"]["session_id"] == "session-a"
    assert results[1]["text"] == "from-b"
    assert results[1]["metadata"]["session_id"] == "session-b"
    assert results[1]["metadata"]["asr_info"]["finalize_id"] == "final-b"
    assert [item["finalize_id"] for item in finalize_ends] == ["final-b"]


@pytest.mark.asyncio
async def test_disconnected_pending_vad_finalize_waits_for_reconnect():
    ext = _extension(mock_result=False)
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), ext
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-a",
            "audio_end_ms": 20,
        }
    )
    recognition._started = False
    recognition.websocket.open = False

    await ext._handle_finalize(
        "final-disconnected",
        asyncio.get_running_loop().time(),
        {"session_id": "session-a"},
    )

    assert recognition._pending[0].finalize_id == "final-disconnected"
    assert ext.send_asr_finalize_end.await_count == 0


@pytest.mark.asyncio
async def test_automatic_vad_final_does_not_consume_other_ttlw_context():
    ext = _extension(mock_result=False)
    ext.metadata = {"session_id": "session-b"}
    ext.session_id = "session-b"
    ext.finalize_id = "final-b"
    ext.last_finalize_time = 99.0
    ext.ttfw_sent = True
    ext._send_metrics_ttlw = AsyncMock()

    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a",
            "transcript": "automatic",
            "words": [{"word": "automatic", "start": 0.0, "end": 0.1}],
        },
        TranscriptSegment(
            0,
            320,
            metadata={"session_id": "session-a"},
            session_id="session-a",
        ),
    )

    ext._send_metrics_ttlw.assert_not_awaited()
    assert ext.last_finalize_time == 99.0
    sent = ext.ten_env.send_data.await_args.args[0]
    payload = json.loads(sent.get_property_to_json(None)[0])
    assert payload["metadata"]["session_id"] == "session-a"


@pytest.mark.asyncio
@pytest.mark.parametrize("close_during_send", [True, False])
async def test_handshake_normal_close_does_not_emit_error(
    monkeypatch, close_during_send
):
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)

    class HandshakeCloseWebSocket:
        open = True

        def __init__(self):
            self.sent = 0

        async def send(self, _raw):
            self.sent += 1
            if close_during_send:
                raise ConnectionClosedOK(
                    Close(1000, "bye"), Close(1000, "bye"), True
                )

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionClosedOK(
                Close(1000, "bye"), Close(1000, "bye"), True
            )

        async def close(self):
            self.open = False

    websocket = HandshakeCloseWebSocket()

    async def connect(_url, **_kwargs):
        return websocket

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )

    await recognition.start()

    assert callback.errors == []
    assert callback.closed == 1


@pytest.mark.asyncio
async def test_recovery_replay_normal_close_sets_flag(monkeypatch):
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    await recognition.send_audio(b"\x01\x02" * 160)

    class ReplayCloseWebSocket:
        open = True

        def __init__(self):
            self._ready = asyncio.Event()
            self._messages = [json.dumps({"type": "session.updated"})]

        async def send(self, raw):
            message = json.loads(raw)
            if message.get("type") == "input_audio_buffer.append":
                raise ConnectionClosedOK(
                    Close(1000, "bye"), Close(1000, "bye"), True
                )

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._messages:
                return self._messages.pop(0)
            await self._ready.wait()
            raise StopAsyncIteration

        async def close(self):
            self.open = False
            self._ready.set()

    async def connect(_url, **_kwargs):
        return ReplayCloseWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )

    await recognition.start()

    assert callback.errors == []
    assert recognition.normal_close is True
    assert callback.closed >= 1


@pytest.mark.asyncio
async def test_stop_cancels_in_flight_connect(monkeypatch):
    ext = _extension()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    gate = asyncio.Event()
    connect_entered = asyncio.Event()
    installed = {"count": 0}

    class LateWebSocket(ExhaustingWebSocket):
        def __init__(self):
            super().__init__()
            installed["count"] += 1

    async def slow_connect(_url, **_kwargs):
        connect_entered.set()
        await gate.wait()
        return LateWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", slow_connect
    )

    connect_task = asyncio.create_task(ext.start_connection())
    await connect_entered.wait()
    ext.stopped = True
    await ext.stop_connection()
    gate.set()
    with suppress(asyncio.CancelledError):
        await connect_task

    assert installed["count"] == 0
    ext.on_connected.assert_not_awaited()


@pytest.mark.asyncio
async def test_handshake_iterator_exhaustion_is_normal_close(monkeypatch):
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), callback)
    websocket = ExhaustingWebSocket()

    async def connect(_url, **_kwargs):
        return websocket

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )

    await recognition.start()

    assert callback.errors == []
    assert callback.closed == 1
    assert recognition.normal_close is True


@pytest.mark.asyncio
async def test_normal_handshake_closes_consume_retry_budget():
    ext = _extension()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext.reconnect_manager = ReconnectManager(max_attempts=2, base_delay=0)
    attempts = 0

    async def connect(_url, **_kwargs):
        nonlocal attempts
        attempts += 1
        return ExhaustingWebSocket()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "stepfun_asr_python.recognition.websockets.connect", connect
        )
        await ext.start_connection()
        assert ext._recovery_task is not None
        await asyncio.wait_for(ext._recovery_task, timeout=2)

    assert attempts == 2
    assert ext.reconnect_manager.attempts == 2
    assert ext._fatal is True
    assert ext.send_asr_error.await_count == 1


@pytest.mark.asyncio
async def test_invalid_url_does_not_leak_in_actual_error_payload():
    secret_url = "wss://example.test/asr?api_key=secret-value"
    ext = StepFunASRExtension("stepfun_asr_python")
    env = MagicMock()
    env.get_property_bool = AsyncMock(return_value=(True, None))
    env.get_property_to_json = AsyncMock(
        return_value=(
            json.dumps(
                {
                    "params": {
                        "api_key": "test-key",
                        "url": secret_url,
                        "model": "stepaudio-2.5-asr-stream",
                        "language": "en",
                        "sample_rate": 16000,
                        "bits": 16,
                        "channels": 1,
                    }
                }
            ),
            None,
        )
    )
    env.send_data = AsyncMock()
    env.log_info = MagicMock()
    env.log_warn = MagicMock()
    env.log_error = MagicMock()
    env.log_debug = MagicMock()

    await ext.on_init(env)

    assert ext.config is None
    payload = json.loads(
        env.send_data.await_args.args[0].get_property_to_json(None)[0]
    )
    serialized = json.dumps(payload)
    assert secret_url not in serialized
    assert "secret-value" not in serialized
    assert payload["metadata"]["vendor_metadata"] == {}
    await ext.stop_connection()


@pytest.mark.asyncio
async def test_finalize_timeout_uses_actual_error_and_finalize_outputs():
    ext = _real_output_extension()
    ext.config = _config(finalize_timeout=0.01)
    ext.metadata = {"session_id": "session-timeout"}
    ext.finalize_id = "final-timeout"
    ext.last_finalize_time = asyncio.get_running_loop().time()

    await ext.finalize("session-timeout")

    names = [
        call.args[0].get_name()
        for call in ext.ten_env.send_data.await_args_list
    ]
    assert names == ["error", "asr_finalize_end"]
    finalize_payload = json.loads(
        ext.ten_env.send_data.await_args_list[1]
        .args[0]
        .get_property_to_json(None)[0]
    )
    assert finalize_payload == {
        "finalize_id": "final-timeout",
        "metadata": {"session_id": "session-timeout"},
    }


@pytest.mark.asyncio
async def test_finalize_timeout_and_vendor_final_emit_once():
    ext = _extension()
    ext.recognition = MagicMock()
    gate = asyncio.Event()
    calls = {"n": 0}

    async def slow_error(*_args, **_kwargs):
        calls["n"] += 1
        await gate.wait()

    ext._send_error = slow_error
    timeout_task = asyncio.create_task(
        ext._finish_finalize(
            "final-race",
            "StepFun finalize timed out",
            metadata={"session_id": "s"},
            timed_out=True,
        )
    )
    await asyncio.sleep(0)
    vendor_task = asyncio.create_task(
        ext._finish_finalize(
            "final-race",
            metadata={"session_id": "s"},
        )
    )
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(timeout_task, vendor_task)
    assert ext.send_asr_finalize_end.await_count == 1
    assert list(ext._completed_finalizes) == ["final-race"]


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

    ext._safe_is_connected = MagicMock(return_value=True)
    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    assert ext.metadata["session_id"] == "sess-1"
    assert ext.finalize_id == "final-1"
    ext.finalize.assert_awaited_once()


@pytest.mark.asyncio
async def test_dump_matches_raw_pcm_input(tmp_path):
    ext = _extension()
    dump_path = Path(tmp_path) / "dump.pcm"
    ext.audio_dumper = Dumper(str(dump_path))
    await ext.audio_dumper.start()
    recognition = StepFunASRRecognition(
        ext.config, SimpleNamespace(), CapturingCallback()
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    payload = b"\x11\x22" * 160
    assert await ext.send_audio(FakeFrame(payload), "sess") is True
    await ext.audio_dumper.stop()
    assert dump_path.read_bytes() == payload


@pytest.mark.asyncio
async def test_stop_cancels_reconnect_without_restart():
    ext = _extension()
    ext.recognition = MagicMock()
    ext.recognition.shutdown = AsyncMock()
    started = asyncio.Event()

    async def slow_reconnect():
        started.set()
        await asyncio.sleep(60)

    ext._recovery_task = asyncio.create_task(slow_reconnect())
    await started.wait()
    await ext.stop_connection()
    assert ext._recovery_task is None
    ext.recognition.shutdown.assert_awaited()


class _ReadyWebSocket:
    """Confirmed session that stays open until close()."""

    open = True

    def __init__(self):
        self.sent = []
        self._messages = [json.dumps({"type": "session.updated"})]
        self._closed = asyncio.Event()

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        await self._closed.wait()
        raise StopAsyncIteration

    async def close(self):
        self.open = False
        self._closed.set()


def _capture_named(ext: StepFunASRExtension, *names: str) -> list[dict]:
    payloads = []
    for call in ext.ten_env.send_data.await_args_list:
        data = call.args[0]
        if data.get_name() in names:
            payloads.append(json.loads(data.get_property_to_json(None)[0]))
    return payloads


@pytest.mark.asyncio
async def test_successful_connection_status_masks_credentials(monkeypatch):
    ext = _real_output_extension()
    ext.config = _config(api_key="secret-api-key-value")
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext.metadata = {"session_id": "sess-connect"}
    ext.session_id = "sess-connect"

    async def connect(_url, **_kwargs):
        return _ReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    try:
        await ext.start_connection()

        statuses = _capture_named(ext, "connection_status_changed")
        assert [item["current"] for item in statuses] == [
            "connecting",
            "connected",
        ]
        vendor_meta = statuses[-1]["metadata"]["vendor_metadata"]
        assert vendor_meta["url"] == "wss://example.test/asr"
        assert vendor_meta["api_key"] != "secret-api-key-value"
        assert "secret-api-key-value" not in json.dumps(statuses)

        metrics = _capture_named(ext, "metrics")
        assert any(
            ModuleMetricKey.ASR_CONNECT_DELAY in item.get("metrics", {})
            for item in metrics
        )
    finally:
        ext.stopped = True
        await ext.stop_connection()


@pytest.mark.asyncio
async def test_connect_delay_ttfw_ttlw_json_and_session(monkeypatch):
    ext = _real_output_extension()
    ext.config = _config()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext.metadata = {"session_id": "sess-metrics"}
    ext.session_id = "sess-metrics"

    async def connect(_url, **_kwargs):
        return _ReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    try:
        await ext.start_connection()
        assert ext.is_connected()

        ext.first_audio_time = asyncio.get_running_loop().time() - 0.05
        ext.finalize_id = "final-metrics"
        ext.last_finalize_time = asyncio.get_running_loop().time() - 0.02
        await ext.on_result(
            {
                "type": "response.audio_transcription.completed",
                "item_id": "item-metrics",
                "transcript": "hello",
                "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
            },
            TranscriptSegment(
                0,
                320,
                finalize_id="final-metrics",
                finalize_time=ext.last_finalize_time,
                metadata={"session_id": "sess-metrics"},
                session_id="sess-metrics",
            ),
        )

        metrics = _capture_named(ext, "metrics")
        metric_keys = {
            key for item in metrics for key in item.get("metrics", {})
        }
        assert ModuleMetricKey.ASR_CONNECT_DELAY in metric_keys
        assert ModuleMetricKey.ASR_TTFW in metric_keys
        assert ModuleMetricKey.ASR_TTLW in metric_keys

        results = _capture_named(ext, "asr_result")
        assert results[-1]["metadata"]["session_id"] == "sess-metrics"
        assert (
            results[-1]["metadata"]["asr_info"]["finalize_id"]
            == "final-metrics"
        )
    finally:
        ext.stopped = True
        await ext.stop_connection()


@pytest.mark.asyncio
async def test_two_complete_same_session_cycles(monkeypatch):
    ext = _real_output_extension()
    ext.config = _config()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext.metadata = {"session_id": "sess-loop"}
    ext.session_id = "sess-loop"

    async def connect(_url, **_kwargs):
        return _ReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    try:
        await ext.start_connection()

        for index, finalize_id in enumerate(("final-1", "final-2"), start=1):
            ext.ten_env.send_data.reset_mock()
            audio = bytes([index, index + 1]) * 160
            assert (
                await ext.recognition.send_audio(
                    audio,
                    metadata={"session_id": "sess-loop"},
                    session_id="sess-loop",
                )
                is True
            )
            received_at = asyncio.get_running_loop().time()
            await ext._handle_finalize(
                finalize_id,
                received_at,
                {"session_id": "sess-loop"},
            )
            pending = ext.recognition._pending[-1]
            await ext.recognition._handle_message(
                {
                    "type": "input_audio_buffer.committed",
                    "item_id": f"item-{index}",
                }
            )
            await ext.recognition._handle_message(
                {
                    "type": "response.audio_transcription.completed",
                    "item_id": f"item-{index}",
                    "transcript": f"turn-{index}",
                    "words": [
                        {"word": f"turn-{index}", "start": 0.0, "end": 0.1}
                    ],
                }
            )
            outputs = _capture_named(ext, "asr_result", "asr_finalize_end")
            results = [item for item in outputs if "text" in item]
            ends = [item for item in outputs if "finalize_id" in item]
            assert results[-1]["text"] == f"turn-{index}"
            assert results[-1]["metadata"]["session_id"] == "sess-loop"
            assert ends[-1]["finalize_id"] == finalize_id
            assert pending.finalize_id == finalize_id
    finally:
        ext.stopped = True
        await ext.stop_connection()


@pytest.mark.asyncio
async def test_retained_span_replay_via_replacement_socket(monkeypatch):
    callback = CapturingCallback()
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), callback
    )
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-old",
            "audio_end_ms": 20,
        }
    )
    retained = recognition._pending[0]
    first_generation = recognition._generation

    ready = _ReadyWebSocket()

    async def connect(_url, **_kwargs):
        return ready

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    await recognition.start()
    assert recognition._generation == first_generation + 1
    assert recognition.is_connected()

    await recognition._handle_message(
        {
            "type": "response.audio_transcription.delta",
            "item_id": "item-replayed",
            "text": "hello",
        }
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-replayed",
            "audio_end_ms": 20,
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-replayed",
            "transcript": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        }
    )

    assert callback.errors == []
    assert callback.messages[-1][1] is retained
    assert retained.published is True
    await recognition.shutdown()
