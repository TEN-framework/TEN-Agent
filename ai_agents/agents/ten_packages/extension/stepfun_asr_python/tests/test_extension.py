import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ten_ai_base.dumper import Dumper
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
