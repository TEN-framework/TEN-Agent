import asyncio
import json
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ten_ai_base.asr import AsyncASRBaseExtension
from ten_ai_base.dumper import Dumper
from ten_ai_base.message import ModuleErrorCode, ModuleMetricKey
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosedOK, InvalidStatus
from websockets.frames import Close
from websockets.http11 import Response

from ten_runtime import AudioFrame

from stepfun_asr_python.config import StepFunASRConfig
from stepfun_asr_python.extension import StepFunASRExtension
from stepfun_asr_python.recognition import (
    StepFunASRRecognition,
    StepFunASRRecognitionCallback,
    TranscriptSegment,
)
from stepfun_asr_python.reconnect_manager import ReconnectManager


def _audio_frame(payload: bytes, metadata: dict | None = None) -> AudioFrame:
    frame = AudioFrame.create("pcm")
    frame.alloc_buf(len(payload))
    buf = frame.lock_buf()
    buf[:] = payload
    frame.unlock_buf(buf)
    if metadata is not None:
        frame.set_property_from_json("metadata", json.dumps(metadata))
    return frame


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
async def test_finalize_preserves_other_session_after_buffer_absorption():
    ext = _real_output_extension()
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

    # A's absorbed audio must keep session A; B completes independently empty.
    assert recognition._current.session_id == "session-a"
    assert recognition._current.metadata["session_id"] == "session-a"
    assert recognition._current.finalize_id is None
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
async def test_confirmed_replay_survives_before_replacement_item_mapping(
    monkeypatch,
):
    """B published before A; after reconnect A's final arrives before B's item."""
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

    async def connect(_url, **_kwargs):
        return _ReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    await recognition.start()
    assert recognition._generation == 2

    # Only A's replacement item is mapped; B has no new mapping yet.
    recognition._items["item-a1"] = seg_a
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a1",
            "transcript": "a",
            "words": [{"word": "a", "start": 0.0, "end": 0.1}],
        }
    )
    assert seg_b in recognition._pending

    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-b1",
            "audio_end_ms": 40,
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
    assert seg_b.published is True
    assert seg_b not in recognition._pending
    assert recognition._base >= seg_b.end
    # Confirmed PCM released — subsequent audio must not hit the journal ceiling.
    await recognition.send_audio(b"\x05\x06" * 160, session_id="c")
    assert recognition._tail > recognition._base
    await recognition.shutdown()


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
async def test_empty_finalize_does_not_claim_other_session_open_span():
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
    assert recognition._current.start < recognition._tail

    await ext._handle_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-b"},
    )

    assert recognition._current.session_id == "session-a"
    assert recognition._current.finalize_id is None
    assert all(seg.finalize_id != "final-b" for seg in recognition._pending)
    finalize_ends = [
        json.loads(data.get_property_to_json(None)[0])
        for call in ext.ten_env.send_data.await_args_list
        for data in [call.args[0]]
        if data.get_name() == "asr_finalize_end"
    ]
    assert [item["finalize_id"] for item in finalize_ends] == ["final-b"]


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
async def test_reconnect_waits_for_active_connect_attempt(monkeypatch):
    ext = _extension()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    gate = asyncio.Event()
    connect_calls = {"n": 0}

    class HangReadyWebSocket:
        open = True

        def __init__(self):
            self._messages = [json.dumps({"type": "session.updated"})]
            self._closed = asyncio.Event()

        async def send(self, _raw):
            return None

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

    async def gated_connect(_url, **_kwargs):
        connect_calls["n"] += 1
        if connect_calls["n"] == 1:
            await gate.wait()
            return HangReadyWebSocket()
        return HangReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", gated_connect
    )

    original = asyncio.create_task(ext.start_connection())
    # Let the original attempt mark itself connecting and block in connect().
    for _ in range(50):
        if ext._connecting:
            break
        await asyncio.sleep(0)
    assert ext._connecting is True

    recovery = asyncio.create_task(ext._reconnect_loop())
    # Yield so recovery can reach start_connection while original is active.
    await asyncio.sleep(0)
    assert connect_calls["n"] == 1

    gate.set()
    await asyncio.wait_for(original, timeout=2)
    # Recovery must not busy-spin; after original completes it may exit or
    # observe connected and return without flooding connect().
    await asyncio.sleep(0.05)
    assert connect_calls["n"] <= 2
    recovery.cancel()
    with suppress(asyncio.CancelledError):
        await recovery
    ext.stopped = True
    await ext.stop_connection()


@pytest.mark.asyncio
async def test_malformed_config_error_hides_credential_input_values():
    ext = StepFunASRExtension("stepfun_asr_python")
    env = MagicMock()
    env.get_property_bool = AsyncMock(return_value=(True, None))
    env.get_property_to_json = AsyncMock(
        return_value=(
            json.dumps(
                {
                    "params": [
                        {"api_key": "secret-value", "url": "wss://example.test"}
                    ]
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
    assert ext._fatal is True
    payload = json.loads(
        env.send_data.await_args.args[0].get_property_to_json(None)[0]
    )
    serialized = json.dumps(payload)
    assert "secret-value" not in serialized
    log_blob = " ".join(
        str(call)
        for mock in (env.log_info, env.log_warn, env.log_error, env.log_debug)
        for call in mock.call_args_list
    )
    assert "secret-value" not in log_blob
    await ext.stop_connection()


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
async def test_normal_close_during_gated_on_open_does_not_raise(monkeypatch):
    gate = asyncio.Event()
    opened = asyncio.Event()
    allow_receive_end = asyncio.Event()

    class GatedCallback(CapturingCallback):
        async def on_open(self):
            opened.set()
            await gate.wait()
            await super().on_open()

    gated = GatedCallback()
    recognition = StepFunASRRecognition(_config(), SimpleNamespace(), gated)

    class CloseAfterUpdatedWebSocket:
        open = True

        def __init__(self):
            self._messages = [json.dumps({"type": "session.updated"})]

        async def send(self, _raw):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._messages:
                return self._messages.pop(0)
            await allow_receive_end.wait()
            raise StopAsyncIteration

        async def close(self):
            self.open = False
            allow_receive_end.set()

    async def connect(_url, **_kwargs):
        return CloseAfterUpdatedWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )

    start_task = asyncio.create_task(recognition.start())
    await opened.wait()
    # Finish the receive loop while on_open is still gated.
    allow_receive_end.set()
    await asyncio.sleep(0)
    assert recognition.normal_close is True
    gate.set()
    await start_task
    assert gated.errors == []


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
async def test_finalize_timeout_seals_queued_turn_before_next_finalize():
    """Blocked consumer + timeout A must not merge A's audio into finalize B."""
    ext = _extension()
    ext.config = _config(finalize_timeout=0.05, server_vad=False)
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext.audio_frames_queue = asyncio.Queue()

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    open_end = recognition._tail

    block = asyncio.Event()
    entered = asyncio.Event()
    original_finalize = ext._handle_finalize

    async def gated_finalize(finalize_id, received_at, metadata):
        entered.set()
        await block.wait()
        await original_finalize(finalize_id, received_at, metadata)

    ext._handle_finalize = gated_finalize
    consumer = asyncio.create_task(ext._audio_frame_consumer())

    ext.finalize_id = "final-a"
    ext.metadata = {"session_id": "session-a"}
    ext.last_finalize_time = asyncio.get_running_loop().time()
    finalize_task = asyncio.create_task(ext.finalize("session-a"))
    await entered.wait()
    await finalize_task
    assert "final-a" in ext._completed_finalizes

    block.set()
    for _ in range(50):
        if recognition._pending and recognition._pending[0].timed_out:
            break
        await asyncio.sleep(0.01)
    assert recognition._pending
    assert recognition._pending[0].finalize_id == "final-a"
    assert recognition._pending[0].timed_out is True
    assert recognition._pending[0].end == open_end

    await recognition.send_audio(
        b"\x03\x04" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await original_finalize(
        "final-b",
        asyncio.get_running_loop().time(),
        {"session_id": "session-a"},
    )
    assert recognition._pending[-1].finalize_id == "final-b"
    assert recognition._pending[-1].start == open_end

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_result_ttlw_context_isolated_from_concurrent_finalize():
    ext = _real_output_extension()
    ext.config = _config()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext.ttfw_sent = False
    ext.first_audio_time = asyncio.get_running_loop().time() - 0.1
    ttlw_values = []

    original_ttfw = ext._send_metrics_ttfw
    original_ttlw = ext._send_metrics_ttlw

    async def gated_ttfw(latency_ms):
        await asyncio.sleep(0.05)
        await original_ttfw(latency_ms)

    async def capture_ttlw(latency_ms):
        ttlw_values.append(
            {
                "latency_ms": latency_ms,
                "finalize_id": ext.finalize_id,
                "session_id": (
                    ext.metadata.get("session_id") if ext.metadata else None
                ),
            }
        )
        await original_ttlw(latency_ms)

    ext._send_metrics_ttfw = gated_ttfw
    ext._send_metrics_ttlw = capture_ttlw
    ext.finalize = AsyncMock()

    result_task = asyncio.create_task(
        ext.on_result(
            {
                "type": "response.audio_transcription.completed",
                "item_id": "item-a",
                "transcript": "from-a",
                "words": [{"word": "from-a", "start": 0.0, "end": 0.1}],
            },
            TranscriptSegment(
                0,
                320,
                finalize_id="final-a",
                finalize_time=10.0,
                metadata={"session_id": "session-a"},
                session_id="session-a",
            ),
        )
    )
    await asyncio.sleep(0)
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-b", None)
    data.get_property_to_json.return_value = (
        json.dumps({"session_id": "session-b"}),
        None,
    )
    # Boundary may enqueue immediately; context install still waits for A's lock.
    finalize_task = asyncio.create_task(
        StepFunASRExtension.on_data(ext, ext.ten_env, data)
    )
    await result_task
    await finalize_task

    assert ttlw_values
    assert ttlw_values[0]["finalize_id"] == "final-a"
    assert ttlw_values[0]["session_id"] == "session-a"
    metrics = _capture_named(ext, "metrics")
    assert any(
        ModuleMetricKey.ASR_TTLW in item.get("metrics", {}) for item in metrics
    )
    assert ext.finalize_id == "final-b"
    assert ext.session_id == "session-b"
    assert ext.metadata["session_id"] == "session-b"
    # Base on_data hook invokes finalize exactly once.
    ext.finalize.assert_awaited_once()


@pytest.mark.asyncio
async def test_server_vad_session_boundary_emits_vendor_commit():
    recognition = StepFunASRRecognition(
        _config(server_vad=True), SimpleNamespace(), CapturingCallback()
    )
    websocket = FakeWebSocket()
    recognition.websocket = websocket
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
    seg_a = recognition._pending[0]
    assert seg_a.session_id == "session-a"
    commits = [
        msg
        for msg in websocket.sent
        if msg.get("type") == "input_audio_buffer.commit"
    ]
    assert len(commits) >= 1
    assert seg_a.commit_generation == recognition._generation

    await recognition._handle_message(
        {"type": "input_audio_buffer.committed", "item_id": "item-a"}
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a",
            "transcript": "from-a",
            "words": [{"word": "from-a", "start": 0.0, "end": 0.1}],
        }
    )
    assert seg_a.published is True
    assert recognition._base >= seg_a.end


@pytest.mark.asyncio
async def test_recovery_flush_journals_before_concurrent_finalize():
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

    dump_gate = asyncio.Event()
    dump_entered = asyncio.Event()

    class GatedDumper:
        async def push_bytes(self, _data):
            dump_entered.set()
            await dump_gate.wait()

        async def start(self):
            return None

        async def stop(self):
            return None

    ext.audio_dumper = GatedDumper()
    frame = FakeFrame(b"\x01\x02" * 160, {"session_id": "session-a"})
    ext.buffered_frames.put_nowait(frame)
    ext.buffered_frames_size = len(frame.get_buf())

    flush_task = asyncio.create_task(ext._flush_buffered_frames())
    await dump_entered.wait()
    # Frame is journaled before dump gates; finalize must wait on the lock.
    assert recognition._tail > 0
    finalize_task = asyncio.create_task(
        ext._handle_finalize(
            "final-a",
            asyncio.get_running_loop().time(),
            {"session_id": "session-a"},
        )
    )
    await asyncio.sleep(0.02)
    assert not finalize_task.done()
    dump_gate.set()
    await flush_task
    await finalize_task
    assert recognition._pending[0].finalize_id == "final-a"
    assert recognition._pending[0].session_id == "session-a"


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
async def test_on_data_routes_finalize_under_context_lock():
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
    assert ext.last_finalize_time is not None
    # Exactly one base-hook finalize invocation per asr_finalize.
    ext.finalize.assert_awaited_once()
    assert "final-1" in ext._finalize_events or ext.audio_frames_queue.qsize() >= 1


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


@pytest.mark.asyncio
async def test_finalize_boundary_enqueued_before_result_lock():
    """Finalize must seal pre-finalize audio even while result output holds the lock."""
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    assert recognition._tail == 320

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    gate = asyncio.Event()
    original_ttfw = ext._send_metrics_ttfw
    ext.ttfw_sent = False
    ext.first_audio_time = asyncio.get_running_loop().time() - 0.1

    async def gated_ttfw(latency_ms):
        await gate.wait()
        await original_ttfw(latency_ms)

    ext._send_metrics_ttfw = gated_ttfw

    result_task = asyncio.create_task(
        ext.on_result(
            {
                "type": "response.audio_transcription.delta",
                "item_id": "item-a",
                "text": "partial",
            },
            TranscriptSegment(
                0,
                None,
                metadata={"session_id": "session-a"},
                session_id="session-a",
            ),
        )
    )
    await asyncio.sleep(0)

    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-a", None)
    data.get_property_to_json.return_value = (
        json.dumps({"session_id": "session-a"}),
        None,
    )
    finalize_task = asyncio.create_task(
        StepFunASRExtension.on_data(ext, ext.ten_env, data)
    )
    await asyncio.sleep(0)
    # Boundary is queued before on_data waits for the result lock.
    assert "final-a" in ext._finalize_events

    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-a"})
    )
    gate.set()
    await result_task
    await finalize_task

    for _ in range(50):
        if (
            recognition._pending
            and any(
                segment.finalize_id == "final-a" and segment.end is not None
                for segment in recognition._pending
            )
            and recognition._tail >= 640
        ):
            break
        await asyncio.sleep(0.01)

    assert recognition._pending
    sealed = next(
        segment
        for segment in recognition._pending
        if segment.finalize_id == "final-a"
    )
    assert sealed.end == 320
    assert recognition._current.start >= 320
    # Post-finalize audio must not be absorbed into the sealed finalize span.
    assert recognition._tail >= 640

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_live_audio_cannot_replace_in_flight_result_session():
    ext = _real_output_extension()
    ext.config = _config()
    ext.recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    ext.recognition.websocket = FakeWebSocket()
    ext.recognition._started = True
    ext.recognition._generation = 1
    ext.ttfw_sent = False
    ext.first_audio_time = asyncio.get_running_loop().time() - 0.1
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"
    ext._safe_is_connected = MagicMock(return_value=True)

    gate = asyncio.Event()
    original_ttfw = ext._send_metrics_ttfw

    async def gated_ttfw(latency_ms):
        await gate.wait()
        await original_ttfw(latency_ms)

    ext._send_metrics_ttfw = gated_ttfw

    result_task = asyncio.create_task(
        ext.on_result(
            {
                "type": "response.audio_transcription.delta",
                "item_id": "item-a",
                "text": "hello",
            },
            TranscriptSegment(
                0,
                320,
                metadata={"session_id": "session-a"},
                session_id="session-a",
            ),
        )
    )
    await asyncio.sleep(0)

    audio_task = asyncio.create_task(
        StepFunASRExtension._handle_audio_frame(
            ext,
            ext.ten_env,
            _audio_frame(b"\x05\x06" * 160, {"session_id": "session-b"}),
        )
    )
    await asyncio.sleep(0.02)
    assert not audio_task.done()
    assert ext.session_id == "session-a"

    gate.set()
    await result_task
    await audio_task

    metrics = _capture_named(ext, "metrics")
    ttfw = [
        item
        for item in metrics
        if ModuleMetricKey.ASR_TTFW in item.get("metrics", {})
    ]
    assert ttfw
    assert ttfw[0].get("metadata", {}).get("session_id") == "session-a"
    assert ext.session_id == "session-b"
    assert ext.metadata["session_id"] == "session-b"


@pytest.mark.asyncio
async def test_replay_final_without_words_is_non_fatal(monkeypatch):
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

    async def connect(_url, **_kwargs):
        return _ReadyWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )
    await recognition.start()
    assert recognition._replay_confirmed

    recognition._items["item-a1"] = seg_a
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a1",
            "transcript": "a-without-words",
        }
    )
    assert callback.errors == []
    assert seg_a.published is True
    assert any(
        message.get("transcript") == "a-without-words"
        for message, _ in callback.messages
    )

    # After retirement, obsolete confirmed ranges must not latch later turns.
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-b1",
            "audio_end_ms": 40,
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-b1",
            "transcript": "b-replay",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        }
    )
    await recognition.send_audio(b"\x05\x06" * 160, session_id="c")
    await recognition.commit(
        "final-c",
        asyncio.get_running_loop().time(),
        metadata={"session_id": "c"},
        session_id="c",
    )
    await recognition._handle_message(
        {
            "type": "input_audio_buffer.committed",
            "item_id": "item-c",
        }
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-c",
            "transcript": "later-turn-no-words",
        }
    )
    assert callback.errors == []
    assert recognition._replay_confirmed == []
    await recognition.shutdown()


@pytest.mark.asyncio
async def test_finalize_without_metadata_keeps_audio_session():
    """Optional finalize metadata must not wipe originating audio session_id."""
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-a", None)
    # Interface allows omitting metadata entirely.
    data.get_property_to_json.return_value = ("", None)

    finalize_task = asyncio.create_task(
        StepFunASRExtension.on_data(ext, ext.ten_env, data)
    )
    for _ in range(50):
        if (
            recognition._pending
            and recognition._pending[0].finalize_id == "final-a"
        ):
            break
        await asyncio.sleep(0.01)

    assert recognition._pending
    sealed = recognition._pending[0]
    assert sealed.end == 320
    assert sealed.session_id == "session-a"
    assert sealed.metadata and sealed.metadata.get("session_id") == "session-a"

    await recognition._handle_message(
        {"type": "input_audio_buffer.committed", "item_id": "item-a"}
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a",
            "transcript": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 0.1}],
        }
    )
    await finalize_task

    payloads = _capture_named(ext, "asr_result", "asr_finalize_end")
    results = [item for item in payloads if "text" in item]
    ends = [item for item in payloads if "finalize_id" in item]
    assert results
    assert results[-1]["metadata"]["session_id"] == "session-a"
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-a"
    assert ends[0]["metadata"].get("session_id") == "session-a"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_metadata_less_finalize_inherits_queued_session_b():
    """Omitted finalize metadata must resolve after preceding queued audio."""
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    # Seal A so B becomes the open span once journaled.
    await recognition.commit(
        "final-a-prev",
        asyncio.get_running_loop().time(),
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    await recognition._handle_message(
        {"type": "input_audio_buffer.committed", "item_id": "item-a-prev"}
    )
    await recognition._handle_message(
        {
            "type": "response.audio_transcription.completed",
            "item_id": "item-a-prev",
            "transcript": "a",
            "words": [{"word": "a", "start": 0.0, "end": 0.1}],
        }
    )

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    # Queue B before the metadata-less finalize while consumer is idle.
    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-b"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-b", None)
    data.get_property_to_json.return_value = ("", None)

    finalize_task = asyncio.create_task(
        StepFunASRExtension.on_data(ext, ext.ten_env, data)
    )
    await finalize_task

    for _ in range(50):
        if any(
            segment.finalize_id == "final-b" and segment.end is not None
            for segment in recognition._pending
        ):
            break
        await asyncio.sleep(0.01)

    sealed_b = next(
        segment
        for segment in recognition._pending
        if segment.finalize_id == "final-b"
    )
    assert sealed_b.session_id == "session-b"
    assert sealed_b.metadata and sealed_b.metadata.get("session_id") == (
        "session-b"
    )
    commits = [
        msg
        for msg in recognition.websocket.sent
        if msg.get("type") == "input_audio_buffer.commit"
    ]
    assert commits
    ends = _capture_named(ext, "asr_finalize_end")
    assert ends
    assert ends[-1]["finalize_id"] == "final-b"
    assert ends[-1]["metadata"].get("session_id") == "session-b"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_finish_finalize_does_not_restore_over_live_session():
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"
    ext.finalize_id = "final-a"
    ext.last_finalize_time = asyncio.get_running_loop().time()
    ext._finalize_contexts["final-a"] = {"session_id": "session-a"}
    ext._finalize_times["final-a"] = ext.last_finalize_time
    ext._finalize_events["final-a"] = asyncio.Event()

    release_end = asyncio.Event()
    entered_end = asyncio.Event()
    captured_ends: list[dict] = []
    original_send = ext.ten_env.send_data

    async def gated_send(data):
        if data.get_name() == "asr_finalize_end":
            captured_ends.append(
                json.loads(data.get_property_to_json(None)[0])
            )
            entered_end.set()
            await release_end.wait()
        await original_send(data)

    ext.ten_env.send_data = gated_send

    finish_task = asyncio.create_task(
        ext._finish_finalize(
            "final-a",
            metadata={"session_id": "session-a"},
        )
    )
    await entered_end.wait()
    audio_task = asyncio.create_task(
        StepFunASRExtension._handle_audio_frame(
            ext,
            ext.ten_env,
            _audio_frame(b"\x05\x06" * 160, {"session_id": "session-b"}),
        )
    )
    await asyncio.sleep(0)
    release_end.set()
    await finish_task
    await audio_task
    assert ext.session_id == "session-b"
    assert ext.metadata["session_id"] == "session-b"

    assert ext.session_id == "session-b"
    assert ext.metadata["session_id"] == "session-b"
    assert captured_ends[-1]["finalize_id"] == "final-a"
    assert captured_ends[-1]["metadata"].get("session_id") == "session-a"

    # Metadata-less finalize for B must target B's open audio.
    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-b", None)
    data.get_property_to_json.return_value = ("", None)
    await StepFunASRExtension.on_data(ext, ext.ten_env, data)
    for _ in range(50):
        if any(seg.finalize_id == "final-b" for seg in recognition._pending):
            break
        await asyncio.sleep(0.01)
    sealed = next(
        seg for seg in recognition._pending if seg.finalize_id == "final-b"
    )
    assert sealed.session_id == "session-b"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_metadata_less_finalize_timeout_emits_queued_session():
    """Omitted metadata + blocked consumer must still echo queued audio session."""
    ext = _real_output_extension()
    ext.config = _config(finalize_timeout=0.05, server_vad=False)
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext.metadata = {"session_id": "stale-session"}
    ext.session_id = "stale-session"

    await ext.audio_frames_queue.put(
        _audio_frame(b"\x01\x02" * 160, {"session_id": "session-queued"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-timeout", None)
    data.get_property_to_json.return_value = ("", None)

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-timeout"
    assert ends[0]["metadata"].get("session_id") == "session-queued"


@pytest.mark.asyncio
async def test_metadata_less_finalize_fatal_emits_queued_session():
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext._fatal = True
    ext.metadata = {"session_id": "stale-session"}
    ext.session_id = "stale-session"

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-fatal"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-fatal", None)
    data.get_property_to_json.return_value = ("", None)

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-fatal"
    assert ends[0]["metadata"].get("session_id") == "session-fatal"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_fatal_finalize_metadata_stops_at_dequeued_boundary():
    """Later queued audio must not override the discarded pre-boundary session."""
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext._fatal = True

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    await ext.audio_frames_queue.put(
        _audio_frame(b"\x01\x02" * 160, {"session_id": "session-a"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-a", None)
    data.get_property_to_json.return_value = ("", None)

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)
    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-b"})
    )

    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-a"
    assert ends[0]["metadata"].get("session_id") == "session-a"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_metadata_less_finalize_fatal_prefers_discarded_over_journal():
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    assert recognition._current.session_id == "session-a"

    ext._fatal = True
    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-b"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-b", None)
    data.get_property_to_json.return_value = ("", None)

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-b"
    assert ends[0]["metadata"].get("session_id") == "session-b"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_metadata_less_finalize_timeout_prefers_queued_over_journal():
    ext = _real_output_extension()
    ext.config = _config(finalize_timeout=0.05, server_vad=False)
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"

    await ext.audio_frames_queue.put(
        _audio_frame(b"\x03\x04" * 160, {"session_id": "session-b"})
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("final-b", None)
    data.get_property_to_json.return_value = ("", None)

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == "final-b"
    assert ends[0]["metadata"].get("session_id") == "session-b"


@pytest.mark.asyncio
async def test_replay_emits_stable_result_ids_per_segment():
    ext = _real_output_extension()
    ext.send_asr_result = AsyncASRBaseExtension.send_asr_result.__get__(ext)
    ext.config = _config(server_vad=True)
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition

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

    await ext.on_result(
        {
            "type": "response.audio_transcription.delta",
            "text": "partial-a",
        },
        seg_a,
    )
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "transcript": "b",
            "words": [{"word": "b", "start": 0.2, "end": 0.3}],
        },
        seg_b,
    )
    await ext.on_result(
        {
            "type": "response.audio_transcription.completed",
            "transcript": "a",
            "words": [{"word": "a", "start": 0.0, "end": 0.1}],
        },
        seg_a,
    )

    results = _capture_named(ext, "asr_result")
    assert len(results) == 3
    id_partial_a, id_final_b, id_final_a = (
        results[0]["id"],
        results[1]["id"],
        results[2]["id"],
    )
    assert id_partial_a == id_final_a
    assert id_final_b != id_final_a


@pytest.mark.asyncio
async def test_finish_finalize_serializes_with_in_flight_result():
    ext = _real_output_extension()
    ext.config = _config()
    ext.send_asr_result = AsyncASRBaseExtension.send_asr_result.__get__(ext)
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext.metadata = {"session_id": "session-b"}
    ext.session_id = "session-b"
    ext.finalize_id = "final-b"
    ext._finalize_contexts["final-a"] = {"session_id": "session-a"}
    ext._finalize_times["final-a"] = asyncio.get_running_loop().time()
    ext._finalize_events["final-a"] = asyncio.Event()

    release_result = asyncio.Event()
    entered_result = asyncio.Event()
    sent_payloads: list[dict] = []

    async def gated_send(data):
        if data.get_name() == "asr_result":
            entered_result.set()
            await release_result.wait()
        if data.get_name() == "asr_finalize_end":
            sent_payloads.append(
                json.loads(data.get_property_to_json(None)[0])
            )

    ext.ten_env.send_data = gated_send

    segment = TranscriptSegment(
        start=0,
        end=320,
        finalize_id="final-b",
        session_id="session-b",
        metadata={"session_id": "session-b"},
    )
    result_task = asyncio.create_task(
        ext.on_result(
            {
                "type": "response.audio_transcription.completed",
                "transcript": "b",
                "words": [{"word": "b", "start": 0.0, "end": 0.1}],
            },
            segment,
        )
    )
    await entered_result.wait()

    finish_task = asyncio.create_task(
        ext._finish_finalize(
            "final-a",
            metadata={"session_id": "session-a"},
        )
    )
    await asyncio.sleep(0)
    assert not finish_task.done()

    release_result.set()
    await result_task
    await finish_task

    assert ext.session_id == "session-b"
    assert ext.metadata["session_id"] == "session-b"
    end_a = next(
        payload for payload in sent_payloads if payload["finalize_id"] == "final-a"
    )
    assert end_a["metadata"].get("session_id") == "session-a"


@pytest.mark.asyncio
async def test_empty_string_finalize_id_acks_once_with_boundary():
    ext = _real_output_extension()
    ext.config = _config()
    recognition = StepFunASRRecognition(ext.config, SimpleNamespace(), ext)
    recognition.websocket = FakeWebSocket()
    recognition._started = True
    recognition._generation = 1
    ext.recognition = recognition
    ext._safe_is_connected = MagicMock(return_value=True)
    ext.metadata = {"session_id": "session-a"}
    ext.session_id = "session-a"

    await recognition.send_audio(
        b"\x01\x02" * 160,
        metadata={"session_id": "session-a"},
        session_id="session-a",
    )

    consumer = asyncio.create_task(
        StepFunASRExtension._audio_frame_consumer(ext)
    )
    data = MagicMock()
    data.get_name.return_value = "asr_finalize"
    data.get_property_string.return_value = ("", None)
    data.get_property_to_json.return_value = (
        json.dumps({"session_id": "session-a"}),
        None,
    )

    await StepFunASRExtension.on_data(ext, ext.ten_env, data)

    for _ in range(50):
        ends = _capture_named(ext, "asr_finalize_end")
        if ends:
            break
        await asyncio.sleep(0.01)

    sealed = next(
        (
            segment
            for segment in recognition._pending
            if segment.finalize_id == ""
        ),
        None,
    )
    assert sealed is not None
    assert sealed.end == 320
    ends = _capture_named(ext, "asr_finalize_end")
    assert len(ends) == 1
    assert ends[0]["finalize_id"] == ""
    assert ends[0]["metadata"].get("session_id") == "session-a"

    consumer.cancel()
    with suppress(asyncio.CancelledError):
        await consumer


@pytest.mark.asyncio
async def test_ws_config_rejection_reports_structured_fatal_once(monkeypatch):
    ext = _real_output_extension()
    ext.config = _config()
    ext.recognition = StepFunASRRecognition(ext.config, ext.ten_env, ext)
    ext._schedule_reconnect = MagicMock()

    class RejectWebSocket:
        open = True

        def __init__(self):
            self.sent = []
            self._messages = [
                json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "code": "invalid_value",
                            "message": "bad turn_detection",
                        },
                    }
                )
            ]
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

    async def connect(_url, **_kwargs):
        return RejectWebSocket()

    monkeypatch.setattr(
        "stepfun_asr_python.recognition.websockets.connect", connect
    )

    gate = asyncio.Event()
    entered = asyncio.Event()
    original_send_error = ext._send_error

    async def gated_send_error(*args, **kwargs):
        entered.set()
        await gate.wait()
        return await original_send_error(*args, **kwargs)

    ext._send_error = gated_send_error

    connect_task = asyncio.create_task(ext.start_connection())
    await entered.wait()
    # Handshake waiter must not race ahead and emit a second error while the
    # structured fatal report is still suspended.
    await asyncio.sleep(0.05)
    assert not connect_task.done()
    gate.set()
    await connect_task

    assert ext._fatal is True
    errors = _capture_named(ext, "error")
    assert len(errors) == 1
    assert int(errors[0]["code"]) == int(ModuleErrorCode.FATAL_ERROR.value)
    assert errors[0]["vendor_info"]["code"] == "invalid_value"
    ext._schedule_reconnect.assert_not_called()
