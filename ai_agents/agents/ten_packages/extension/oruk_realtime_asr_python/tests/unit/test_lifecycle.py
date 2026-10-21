"""Offline fault-injection tests of the actual extension and transport methods.

The thin TEN boundary is stubbed; these do not replace native ASR guarders.
Run: python -m unittest discover -s tests/unit -v
"""

import asyncio
import copy
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


class Base:
    def __init__(self, name):
        self.stopped = False
        self.auto_connect = True
        self._connection_requested = False
        self.uuid = "request-test"
        self.metadata = {"session_id": "session-a"}
        self.session_id = "session-a"
        self.buffered_frames = asyncio.Queue()
        self.buffered_frames_size = 0
        self.dropped_audio_frames = 0
        self.sent_buffer_length = 0
        self.first_audio_time = None
        self.ten_env = Mock()
        self.audio_timeline = Mock()
        self.audio_timeline.get_total_user_audio_duration.return_value = 700
        for name in [
            "on_connected",
            "on_disconnected",
            "send_asr_error",
            "send_asr_result",
            "send_asr_finalize_end",
            "send_vendor_metrics",
            "send_connect_delay_metrics",
        ]:
            setattr(self, name, AsyncMock())

    async def on_init(self, env):
        self.ten_env = env

    async def on_deinit(self, env):
        pass

    def input_audio_channels(self):
        return 1

    def input_audio_sample_width(self):
        return 2

    async def _handle_audio_frame(self, env, audio_frame):
        await self.send_audio(audio_frame, self.session_id)

    async def on_data(self, env, data):
        # Mirror the native base's mutable finalize context, assigned before
        # it invokes the extension's finalize implementation.
        self.finalize_id, _ = data.get_property_string("finalize_id")
        await self.finalize(self.session_id)


_stub_names = [
    "ten_ai_base",
    "ten_ai_base.asr",
    "ten_ai_base.const",
    "ten_ai_base.dumper",
    "ten_ai_base.message",
    "ten_runtime",
]
_original_modules = {name: sys.modules.get(name) for name in _stub_names}
for name in _stub_names:
    sys.modules[name] = types.ModuleType(name)
a = sys.modules["ten_ai_base.asr"]
a.AsyncASRBaseExtension = Base
for name in ["ASRBufferConfig", "ASRBufferConfigModeKeep", "ASRResult"]:
    setattr(a, name, lambda **kw: types.SimpleNamespace(**kw))
sys.modules["ten_ai_base.const"].LOG_CATEGORY_KEY_POINT = "point"
sys.modules["ten_ai_base.const"].LOG_CATEGORY_VENDOR = "vendor"
sys.modules["ten_ai_base.dumper"].Dumper = Mock
m = sys.modules["ten_ai_base.message"]
m.ModuleError = m.ModuleErrorVendorInfo = lambda **kw: types.SimpleNamespace(
    **kw
)
from enum import Enum

m.ModuleErrorCode = Enum(
    "Code", {"FATAL_ERROR": -1000, "NON_FATAL_ERROR": 1000}
)
sys.modules["ten_runtime"].AsyncTenEnv = object
sys.modules["ten_runtime"].AudioFrame = object
namespace = types.ModuleType("_oruk_unit_realtime")
namespace.__path__ = [str(ROOT / "oruk_realtime_asr_python")]
sys.modules["_oruk_unit_realtime"] = namespace
rt = importlib.import_module("_oruk_unit_realtime.extension")
transport = importlib.import_module("_oruk_unit_realtime.recognition")
assert rt.OrukRealtimeASRExtension.__mro__[1] is Base

for name, original in _original_modules.items():
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


class Lifecycle(unittest.IsolatedAsyncioTestCase):
    def new(self):
        e = rt.OrukRealtimeASRExtension("test")
        e.config = rt.OrukRealtimeASRConfig(params={"api_key": "unit-key"})
        return e

    async def test_handshake_vendor_errors_preserve_classification(self):
        for phase in ("created", "updated"):
            for code in ("invalid_api_key", "forbidden", "rate_limit"):
                with self.subTest(phase=phase, code=code):
                    e = self.new()
                    error = {
                        "type": "error",
                        "error": {"code": code, "message": "vendor diagnostic"},
                    }
                    events = (
                        [error]
                        if phase == "created"
                        else [{"type": "session.created"}, error]
                    )
                    socket = Mock(
                        closed=False, send_json=AsyncMock(), close=AsyncMock()
                    )
                    session = Mock(
                        closed=False,
                        ws_connect=AsyncMock(return_value=socket),
                        close=AsyncMock(),
                    )
                    e._schedule_reconnect = Mock()
                    with (
                        patch.object(
                            transport.aiohttp,
                            "ClientSession",
                            return_value=session,
                        ) as factory,
                        patch.object(
                            transport.OrukRealtimeConnection,
                            "_receive_json",
                            AsyncMock(side_effect=events),
                        ),
                    ):
                        if code == "rate_limit":
                            await e.start_connection()
                        else:
                            await e._reopen()
                    factory.assert_called_once()
                    e.send_asr_error.assert_awaited_once()
                    error_arg, vendor = e.send_asr_error.await_args.args
                    self.assertEqual(vendor.code, code)
                    self.assertEqual(vendor.message, "vendor diagnostic")
                    self.assertEqual(
                        error_arg.code, 1000 if code == "rate_limit" else -1000
                    )
                    self.assertEqual(e._fatal, code != "rate_limit")
                    self.assertIsNone(e.connection)

    async def test_stale_close_cannot_clear_new_turn(self):
        e = self.new()
        e._generation = 4
        old = rt._TurnCallback(e, 3)
        new = Mock()
        e.connection = new
        await old.on_close(1000, "old")
        await old.on_final("old words")
        self.assertIs(e.connection, new)
        e.send_asr_result.assert_not_called()

    async def test_fatal_does_not_retry(self):
        e = self.new()
        await e.on_error("denied", "forbidden", True)
        e._schedule_reconnect()
        self.assertTrue(e._fatal)
        self.assertIsNone(e._reconnect_task)
        e.on_disconnected.reset_mock()
        with patch.object(rt, "OrukRealtimeConnection") as constructor:
            await e.start_connection()
            constructor.assert_not_called()
        self.assertIsNone(e.connection)
        e.on_disconnected.assert_awaited_once()
        e.send_asr_error.assert_awaited_once()

    async def test_queued_connect_rechecks_stop_and_fatal_latches(self):
        for latch in ("stopped", "_fatal", "_init_failed"):
            with self.subTest(latch=latch):
                e = self.new()
                await e._connect_lock.acquire()
                with patch.object(rt, "OrukRealtimeConnection") as constructor:
                    task = asyncio.create_task(e.start_connection())
                    await asyncio.sleep(0)
                    setattr(e, latch, True)
                    e._connect_lock.release()
                    await task
                    constructor.assert_not_called()
                e.on_disconnected.assert_awaited_once()
                e.send_asr_error.assert_not_called()

    async def test_already_connected_start_restores_connected_status(self):
        e = self.new()
        e.connection = Mock(is_connected=Mock(return_value=True))
        with patch.object(rt, "OrukRealtimeConnection") as constructor:
            await e.start_connection()
            constructor.assert_not_called()
        e.on_connected.assert_awaited_once()

    async def test_single_reconnect_owner(self):
        e = self.new()
        e._reopen = AsyncMock()
        e._schedule_reconnect()
        task = e._reconnect_task
        e._schedule_reconnect()
        self.assertIs(task, e._reconnect_task)
        await task
        e._reopen.assert_awaited_once()

    async def test_turns_and_handshake_retry_use_distinct_request_headers(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        ten_id, session_id = e.uuid, e.session_id
        sessions = []
        for attempt in range(4):
            socket = Mock(
                closed=False,
                send_json=AsyncMock(),
                send_bytes=AsyncMock(),
                close=AsyncMock(),
            )
            sessions.append(
                Mock(
                    closed=False,
                    ws_connect=AsyncMock(
                        return_value=socket,
                        side_effect=(
                            OSError("handshake failed")
                            if attempt == 2
                            else None
                        ),
                    ),
                    close=AsyncMock(),
                )
            )
        with (
            patch.object(
                transport.aiohttp, "ClientSession", side_effect=sessions
            ),
            patch.object(
                transport.OrukRealtimeConnection,
                "_receive_json",
                AsyncMock(
                    side_effect=[
                        {"type": "session.created"},
                        {"type": "session.updated"},
                    ]
                    * 3
                ),
            ),
            patch.object(
                transport.OrukRealtimeConnection,
                "_receive_loop",
                AsyncMock(),
            ),
        ):
            for turn in range(2):
                await e.start_connection()
                connection = e.connection
                frame = Mock(
                    get_property_to_json=Mock(return_value=("", None)),
                    lock_buf=Mock(return_value=b"\0" * 320),
                )
                self.assertTrue(await e.send_audio(frame, session_id))
                pending = asyncio.create_task(e.finalize(session_id))

                async def wait_for_commit():
                    while not connection._committed:
                        await asyncio.sleep(0)

                await asyncio.wait_for(wait_for_commit(), 1)
                await connection._dispatch(
                    {
                        "type": transport.TRANSCRIPT_PREFIX + "completed",
                        "transcript": f"Turn {turn + 1}",
                    }
                )
                await asyncio.wait_for(pending, 1)
                await connection.close()
                await e.on_close(1000, "turn complete")
            await e._reopen()
            self.assertTrue(e.is_connected())
            await e._close_current()

        request_ids = [
            session.ws_connect.await_args.kwargs["headers"]["X-Request-ID"]
            for session in sessions
        ]
        self.assertEqual(len(set(request_ids)), 4)
        self.assertNotIn(ten_id, request_ids)
        self.assertEqual((e.uuid, e.session_id), (ten_id, session_id))
        self.assertEqual(e.send_asr_finalize_end.await_count, 2)
        self.assertEqual(
            [call.args[0].text for call in e.send_asr_result.await_args_list],
            ["Turn 1", "Turn 2"],
        )
        self.assertEqual(
            [
                call.args[0].metadata["session_id"]
                for call in e.send_asr_result.await_args_list
            ],
            [session_id, session_id],
        )
        e.send_asr_error.assert_awaited_once()

    async def test_actual_reopen_preserves_committed_socket_until_final(self):
        e = self.new()
        committed = asyncio.Event()
        created = []

        class Connection:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]
                self.active = False
                self.committed = False
                self.close = AsyncMock(side_effect=self.deactivate)
                self.send_pcm = AsyncMock()
                created.append(self)

            def deactivate(self):
                self.active = False

            def is_active(self):
                return self.active

            def is_connected(self):
                return self.active and not self.committed

            async def start(self, **_kwargs):
                self.active = True
                await self.callback.on_open()

            async def commit(self):
                self.committed = True
                committed.set()

        async def metrics(_ms):
            await committed.wait()

        e.send_connect_delay_metrics = AsyncMock(side_effect=metrics)
        e.buffered_frames.put_nowait(
            Mock(
                get_buf=Mock(return_value=b"\0\0" * 160),
                lock_buf=Mock(return_value=b"\0\0" * 160),
            )
        )
        with patch.object(rt, "OrukRealtimeConnection", Connection):
            pending = asyncio.create_task(e.finalize("session-a"))
            await asyncio.wait_for(committed.wait(), 1)
            await asyncio.wait_for(e._reconnect_task, 1)
            await asyncio.sleep(0.6)
            await e.start_connection()
            self.assertEqual(len(created), 1)
            created[0].close.assert_not_called()
            self.assertFalse(pending.done())
            await created[0].callback.on_final("delayed final")
            await asyncio.wait_for(pending, 1)
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertEqual(
            e.send_asr_result.await_args.args[0].text, "delayed final"
        )

    async def test_closed_draining_socket_does_not_count_as_active(self):
        e = self.new()
        old = Mock(
            is_connected=Mock(return_value=False),
            is_active=Mock(return_value=False),
            close=AsyncMock(),
        )
        e.connection = old
        e._draining_connection = old
        replacement = Mock(start=AsyncMock(), close=AsyncMock())
        with patch.object(
            rt, "OrukRealtimeConnection", return_value=replacement
        ):
            await e.start_connection()
        old.close.assert_awaited_once()
        self.assertIs(e.connection, replacement)

    async def test_discard_owns_inflight_rejected_buffer_frame(self):
        e = self.new()
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(_frame, _session):
            entered.set()
            await release.wait()
            return False

        e.send_audio = AsyncMock(side_effect=send)
        e.buffered_frames.put_nowait(
            Mock(get_buf=Mock(return_value=b"\0" * 304))
        )
        e.buffered_frames.put_nowait(
            Mock(get_buf=Mock(return_value=b"\0" * 16))
        )
        flushing = asyncio.create_task(e._flush_buffered_audio())
        await entered.wait()
        e._discard_buffered_audio()
        release.set()
        await flushing
        self.assertTrue(e.buffered_frames.empty())
        self.assertEqual(e.dropped_audio_frames, 2)
        self.assertEqual(e._emitted_ms, 10)
        self.assertEqual(
            sum(
                call.args[0]
                for call in e.audio_timeline.add_dropped_audio.call_args_list
            ),
            10,
        )

    async def test_late_open_cannot_mark_replacement_ready(self):
        e = self.new()
        entered, release = asyncio.Event(), asyncio.Event()

        async def flush():
            entered.set()
            await release.wait()

        e._flush_buffered_audio = AsyncMock(side_effect=flush)
        e.connection = Mock()
        opening = asyncio.create_task(e.on_open())
        await entered.wait()
        e._generation += 1
        e.connection = Mock()
        e._flushing = True
        e._ready_event.clear()
        release.set()
        await opening
        self.assertTrue(e._flushing)
        self.assertFalse(e._ready_event.is_set())
        e.send_connect_delay_metrics.assert_not_called()

    async def test_close_waiting_for_ack_cannot_disconnect_replacement(self):
        e = self.new()
        e._finalize_pending = True
        e._schedule_reconnect = Mock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def acknowledge():
            entered.set()
            await release.wait()

        e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
        callback = rt._TurnCallback(e, e._generation)
        pending = asyncio.create_task(callback.on_close(1000, "old closed"))
        await asyncio.wait_for(entered.wait(), 1)
        e._generation += 1
        e._reset_turn()
        replacement = Mock(is_connected=Mock(return_value=True))
        e.connection = replacement
        release.set()
        await asyncio.wait_for(pending, 1)
        self.assertIs(e.connection, replacement)
        self.assertFalse(e._turn_done.is_set())
        e.on_disconnected.assert_not_called()
        e._schedule_reconnect.assert_not_called()

    async def test_remote_close_accounts_successful_inflight_send(self):
        e = self.new()
        e._turn_bytes = 32000
        e._schedule_reconnect = Mock()
        written, release = asyncio.Event(), asyncio.Event()

        async def write(_pcm):
            written.set()
            await release.wait()

        connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=write),
        )
        e.connection = connection
        frame = Mock(
            get_property_to_json=Mock(return_value=("", None)),
            lock_buf=Mock(return_value=b"\0" * 16000),
        )
        sending = asyncio.create_task(e.send_audio(frame, "session-a"))
        await asyncio.wait_for(written.wait(), 1)
        await rt._TurnCallback(e, e._generation).on_close(1006, "remote")
        retiring = tuple(e._remote_close_tasks)
        self.assertEqual(len(retiring), 1)
        self.assertFalse(e._turn_accounted)
        release.set()
        self.assertTrue(await asyncio.wait_for(sending, 1))
        await asyncio.wait_for(asyncio.gather(*retiring), 1)
        self.assertEqual(e._emitted_ms, 1500)
        self.assertEqual(e._turn_bytes, 48000)
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("next")
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual((result.start_ms, result.duration_ms), (1500, 500))
        self.assertEqual(e._emitted_ms, 2000)

    async def test_remote_close_waiting_for_io_preserves_replacement(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e.connection = Mock()
        await e._io_lock.acquire()
        await rt._TurnCallback(e, e._generation).on_close(1006, "old")
        retiring = tuple(e._remote_close_tasks)
        await asyncio.sleep(0)
        e._generation += 1
        e._reset_turn()
        replacement = Mock()
        e.connection = replacement
        e._turn_bytes = 16000
        e._io_lock.release()
        await asyncio.wait_for(asyncio.gather(*retiring), 1)
        self.assertIs(e.connection, replacement)
        self.assertEqual(e._emitted_ms, 0)
        self.assertFalse(e._turn_accounted)
        e.send_asr_finalize_end.assert_not_called()
        e.on_disconnected.assert_not_called()
        e._schedule_reconnect.assert_not_called()

    async def test_inline_transport_close_does_not_deadlock_io(self):
        for operation in ("send", "commit", "close"):
            with self.subTest(operation=operation):
                e = self.new()
                e._schedule_reconnect = Mock()
                e._turn_bytes = 32000
                callback = rt._TurnCallback(e, e._generation)

                async def close_inline(*_args):
                    await callback.on_close(1000, "inline close")

                connection = Mock(
                    is_connected=Mock(return_value=True),
                    send_pcm=AsyncMock(side_effect=close_inline),
                    commit=AsyncMock(side_effect=close_inline),
                    close=AsyncMock(side_effect=close_inline),
                )
                e.connection = connection
                if operation == "send":
                    frame = Mock(
                        get_property_to_json=Mock(return_value=("", None)),
                        lock_buf=Mock(return_value=b"\0" * 16000),
                    )
                    self.assertTrue(
                        await asyncio.wait_for(
                            e.send_audio(frame, "session-a"), 1
                        )
                    )
                elif operation == "commit":
                    await asyncio.wait_for(e.finalize("session-a"), 1)
                    e.send_asr_finalize_end.assert_awaited_once()
                else:
                    await asyncio.wait_for(e.stop_connection(), 1)
                await asyncio.wait_for(
                    asyncio.gather(*e._remote_close_tasks), 1
                )
                self.assertIsNone(e.connection)
                self.assertEqual(
                    e._emitted_ms, 1500 if operation == "send" else 1000
                )

    async def test_stop_cancels_deferred_close_waiting_for_ack(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e._finalize_pending = True
        e._turn_bytes = 32000
        acknowledging = asyncio.Event()

        async def acknowledge():
            acknowledging.set()
            await asyncio.Event().wait()

        e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
        e.connection = Mock(close=AsyncMock())
        await e._io_lock.acquire()
        await e.on_close(1000, "remote")
        retiring = tuple(e._remote_close_tasks)
        e._io_lock.release()
        await asyncio.wait_for(acknowledging.wait(), 1)
        await asyncio.wait_for(e.stop_connection(), 1)
        self.assertTrue(all(task.done() for task in retiring))
        self.assertEqual(e._emitted_ms, 1000)

    async def test_buffer_bytes_track_inflight_flush_and_arrival(self):
        e = self.new()
        e._flushing = True
        e.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=960)
        )
        frames = [
            Mock(get_buf=Mock(return_value=b"\0" * 320)) for _ in range(4)
        ]
        for frame in frames[:3]:
            await e._handle_audio_frame(e.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []

        async def send(frame, _session):
            sent.append(frame)
            if frame is frames[1]:
                entered.set()
                await release.wait()
            return True

        e.send_audio = AsyncMock(side_effect=send)
        flushing = asyncio.create_task(e._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        self.assertEqual(e.buffered_frames_size, 320)
        await e._handle_audio_frame(e.ten_env, frames[3])
        self.assertEqual(e.buffered_frames_size, 640)
        self.assertEqual(e.buffered_frames.qsize(), 2)
        release.set()
        await asyncio.wait_for(flushing, 1)
        self.assertEqual(sent, frames)
        self.assertEqual(e.buffered_frames_size, 0)
        self.assertEqual(e.dropped_audio_frames, 0)

    async def test_failed_flush_restore_reapplies_buffer_cap(self):
        e = self.new()
        e._flushing = True
        e.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=640)
        )
        frames = [
            Mock(get_buf=Mock(return_value=b"\0" * 320)) for _ in range(3)
        ]
        for frame in frames[:2]:
            await e._handle_audio_frame(e.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(_frame, _session):
            entered.set()
            await release.wait()
            return False

        e.send_audio = AsyncMock(side_effect=send)
        flushing = asyncio.create_task(e._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        await e._handle_audio_frame(e.ten_env, frames[2])
        self.assertEqual(e.buffered_frames_size, 640)
        release.set()
        with self.assertRaises(ConnectionError):
            await asyncio.wait_for(flushing, 1)
        self.assertEqual(e.buffered_frames_size, 640)
        self.assertEqual(e.buffered_frames.qsize(), 2)
        self.assertIs(e.buffered_frames.get_nowait(), frames[1])
        self.assertIs(e.buffered_frames.get_nowait(), frames[2])
        self.assertEqual(e.dropped_audio_frames, 1)
        self.assertEqual(e._emitted_ms, 10)
        e.audio_timeline.add_dropped_audio.assert_called_once_with(10.0)

    async def test_oversize_during_flush_aborts_partial_turn(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=32000)
        )
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            lock_buf=Mock(return_value=b"\0" * 32000),
        )
        await e._handle_audio_frame(e.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(_audio):
            entered.set()
            await release.wait()

        old = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=send),
            close=AsyncMock(),
        )
        e.connection = old
        e._flushing = True
        callback = rt._TurnCallback(e, e._generation)
        flushing = asyncio.create_task(e._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        oversized = Mock(get_buf=Mock(return_value=b"\0" * 64000))
        abort = asyncio.create_task(e._handle_audio_frame(e.ten_env, oversized))
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.gather(flushing, abort), 1)
        old.close.assert_awaited_once()
        await callback.on_final("late partial transcript")
        e.send_asr_result.assert_not_called()
        self.assertEqual(e._emitted_ms, 3000)
        self.assertEqual(e.dropped_audio_frames, 1)
        e.send_asr_error.assert_awaited_once()
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("next turn")
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual((result.start_ms, result.duration_ms), (3000, 500))

    async def test_replacement_keeps_original_finalize_ack_context(self):
        e = self.new()
        e.metadata = {"session_id": "finalize-a", "request_tag": "original"}
        e.session_id = "finalize-a"
        entered, release = asyncio.Event(), asyncio.Event()
        acknowledgements = []

        async def emit_error(*_args):
            entered.set()
            await release.wait()

        async def acknowledge():
            acknowledgements.append(copy.deepcopy(e.metadata))

        e.send_asr_error = AsyncMock(side_effect=emit_error)
        e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=OSError("broken commit")),
            close=AsyncMock(),
        )
        pending = asyncio.create_task(e.finalize("finalize-a"))
        await asyncio.wait_for(entered.wait(), 1)
        e._generation += 1
        e._reset_turn()
        e.metadata = {"session_id": "audio-b"}
        e.session_id = "audio-b"
        replacement = Mock(close=AsyncMock())
        e.connection = replacement
        release.set()
        await asyncio.wait_for(pending, 1)
        self.assertIs(e.connection, replacement)
        replacement.close.assert_not_called()
        self.assertEqual(
            acknowledgements,
            [{"session_id": "finalize-a", "request_tag": "original"}],
        )
        self.assertEqual(e.metadata, {"session_id": "audio-b"})

    async def test_finalize_drains_queued_audio_and_inflight_dump(self):
        e = self.new()
        e.audio_frames_queue = asyncio.Queue()
        entered, release = asyncio.Event(), asyncio.Event()
        sent, committed = [], []

        async def dump(pcm):
            if pcm == b"first":
                entered.set()
                await release.wait()

        async def commit():
            committed.append(list(sent))
            await e.on_final("first turn")

        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=sent.append),
            commit=AsyncMock(side_effect=commit),
        )
        e.audio_dumper = Mock(push_bytes=AsyncMock(side_effect=dump))

        def frame(pcm):
            return Mock(
                lock_buf=Mock(return_value=pcm),
                get_buf=Mock(return_value=pcm),
                get_property_to_json=Mock(return_value=(None, None)),
                unlock_buf=Mock(),
            )

        stop_consumer = object()

        async def consume():
            while True:
                item = await e.audio_frames_queue.get()
                if item is stop_consumer:
                    return
                await e._handle_audio_frame(e.ten_env, item)

        consumer = asyncio.create_task(consume())
        pending = None
        try:
            e.audio_frames_queue.put_nowait(frame(b"first"))
            e.audio_frames_queue.put_nowait(frame(b"second"))
            await asyncio.wait_for(entered.wait(), timeout=1)
            request = Mock(
                get_name=Mock(return_value="asr_finalize"),
                get_property_string=Mock(return_value=("drain-finalize", None)),
            )
            pending = asyncio.create_task(e.on_data(e.ten_env, request))
            await asyncio.sleep(0)
            e.audio_frames_queue.put_nowait(frame(b"next turn"))
            e.connection.commit.assert_not_called()
            release.set()
            await asyncio.wait_for(pending, timeout=1)
            self.assertEqual(committed, [[b"first", b"second"]])
            e.send_asr_finalize_end.assert_awaited_once()
        finally:
            release.set()
            # Python 3.10 wait_for can consume cancellation while its child
            # completes. Stop this queue consumer cooperatively instead.
            e.audio_frames_queue.put_nowait(stop_consumer)
            if pending is not None:
                pending.cancel()
            await asyncio.wait_for(
                asyncio.gather(
                    consumer,
                    *([pending] if pending is not None else []),
                    return_exceptions=True,
                ),
                timeout=1,
            )

    async def test_finalize_boundaries_mark_receipt_before_request_lock(self):
        e = self.new()
        e.audio_frames_queue = asyncio.Queue()
        await e._finalize_request_lock.acquire()

        def request(identifier):
            return Mock(
                get_name=Mock(return_value="asr_finalize"),
                get_property_string=Mock(return_value=(identifier, None)),
            )

        first = asyncio.create_task(e.on_data(e.ten_env, request("first")))
        await asyncio.sleep(0)
        between = object()
        e.audio_frames_queue.put_nowait(between)
        second = asyncio.create_task(e.on_data(e.ten_env, request("second")))
        await asyncio.sleep(0)
        self.assertIsInstance(
            e.audio_frames_queue.get_nowait(), rt._FinalizeBoundary
        )
        self.assertIs(e.audio_frames_queue.get_nowait(), between)
        self.assertIsInstance(
            e.audio_frames_queue.get_nowait(), rt._FinalizeBoundary
        )
        self.assertEqual(len(e._finalize_boundaries), 2)
        e.stopped = True
        await e.stop_connection()
        self.assertTrue(
            all(boundary.ready.is_set() for boundary in e._finalize_boundaries)
        )
        e._finalize_request_lock.release()
        await asyncio.gather(first, second)
        self.assertFalse(e._finalize_boundaries)
        self.assertEqual(e.send_asr_finalize_end.await_count, 2)

    async def test_audio_drain_timeout_is_bounded_and_acknowledged(self):
        e = self.new()
        e.audio_frames_queue = asyncio.Queue()
        request = Mock(
            get_name=Mock(return_value="asr_finalize"),
            get_property_string=Mock(return_value=("stalled-drain", None)),
        )
        with patch.object(rt, "AUDIO_DRAIN_TIMEOUT_SECONDS", 0.001):
            await asyncio.wait_for(e.on_data(e.ten_env, request), timeout=0.2)
        self.assertTrue(e._fatal)
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertEqual(
            e.send_asr_error.await_args.args[1].code, "drain_timeout"
        )
        self.assertTrue(e.audio_frames_queue.get_nowait().release.is_set())

    async def test_disconnected_buffer_is_flushed_before_finalize_commit(self):
        e = self.new()
        frame = Mock(
            lock_buf=Mock(return_value=b"buffered audio"),
            get_buf=Mock(return_value=b"buffered audio"),
            get_property_to_json=Mock(return_value=(None, None)),
            unlock_buf=Mock(),
        )
        e.buffered_frames.put_nowait(frame)
        sent = []

        async def commit():
            self.assertEqual(sent, [b"buffered audio"])
            await e.on_final("buffered turn")

        connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=sent.append),
            commit=AsyncMock(side_effect=commit),
        )

        async def reopen():
            e._generation += 1
            e._reset_turn()
            e._flushing = True
            e._connect_started = asyncio.get_running_loop().time()
            e.connection = connection
            await e.on_open()

        e._reopen = AsyncMock(side_effect=reopen)
        await asyncio.wait_for(e.finalize("session-a"), timeout=0.2)
        connection.commit.assert_awaited_once()
        self.assertTrue(e.buffered_frames.empty())
        e.send_asr_finalize_end.assert_awaited_once()
        e.send_asr_error.assert_not_called()
        await e._reconnect_task

    async def test_completed_turn_event_survives_immediate_next_connection(
        self,
    ):
        e = self.new()

        async def commit():
            await e.on_final("finished")
            e._generation += 1
            e._reset_turn()

        e.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=commit),
        )
        await asyncio.wait_for(e.finalize(None), timeout=0.2)
        e.send_asr_error.assert_not_called()
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertFalse(e._turn_done.is_set())

    async def test_previous_close_cannot_ack_next_buffered_turn(self):
        e = self.new()
        e._final_sent = True
        e.connection = Mock(is_connected=Mock(return_value=False))
        e._schedule_reconnect = Mock()
        e.buffered_frames.put_nowait(
            Mock(
                lock_buf=Mock(return_value=b"next audio"),
                get_buf=Mock(return_value=b"next audio"),
                get_property_to_json=Mock(return_value=(None, None)),
                unlock_buf=Mock(),
            )
        )
        pending = asyncio.create_task(e.finalize("session-b"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await e.on_close(1000, "previous turn closed")
        e.send_asr_finalize_end.assert_not_called()

        async def commit():
            self.assertTrue(e.buffered_frames.empty())
            e.send_asr_finalize_end.assert_not_called()
            await e.on_final("next turn")

        e._generation += 1
        e._reset_turn()
        e._flushing = True
        e._connect_started = asyncio.get_running_loop().time()
        connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(),
            commit=AsyncMock(side_effect=commit),
        )
        e.connection = connection
        await e.on_open()
        await asyncio.wait_for(pending, timeout=0.2)
        connection.commit.assert_awaited_once()
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_stalled_send_does_not_block_drain_timeout_cleanup(self):
        e = self.new()
        e.audio_frames_queue = asyncio.Queue()
        entered = asyncio.Event()

        async def stalled_send(_pcm):
            entered.set()
            await asyncio.Event().wait()

        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=stalled_send),
            close=AsyncMock(),
        )
        frame = Mock(lock_buf=Mock(return_value=b"stalled"))
        request = Mock(
            get_name=Mock(return_value="asr_finalize"),
            get_property_string=Mock(return_value=("stalled-send", None)),
        )
        with (
            patch.object(rt, "IO_TIMEOUT_SECONDS", 0.01),
            patch.object(rt, "AUDIO_DRAIN_TIMEOUT_SECONDS", 0.001),
        ):
            sender = asyncio.create_task(e.send_audio(frame, None))
            await asyncio.wait_for(entered.wait(), timeout=1)
            await asyncio.wait_for(e.on_data(e.ten_env, request), timeout=0.2)
            self.assertFalse(await sender)
        self.assertTrue(e._fatal)
        self.assertIsNone(e.connection)
        frame.unlock_buf.assert_called_once()
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_stalled_commit_is_bounded_and_acknowledged(self):
        e = self.new()

        async def commit():
            await asyncio.Event().wait()

        e.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=commit),
            close=AsyncMock(),
        )
        e._schedule_reconnect = Mock()
        with patch.object(rt, "IO_TIMEOUT_SECONDS", 0.001):
            await asyncio.wait_for(e.finalize(None), timeout=0.2)
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertEqual(
            e.send_asr_error.await_args.args[1].code, "finalize_timeout"
        )
        e._schedule_reconnect.assert_called_once()

    async def test_stop_cancels_reconnect(self):
        e = self.new()
        e._reconnect_task = asyncio.create_task(asyncio.sleep(20))
        task = e._reconnect_task
        await e.stop_connection()
        self.assertTrue(task.cancelled())
        self.assertIsNone(e.connection)

    async def test_retries_have_ceiling(self):
        e = self.new()
        e.start_connection = AsyncMock()
        with patch.object(rt.asyncio, "sleep", new=AsyncMock()):
            await e._reopen()
        self.assertEqual(e.start_connection.await_count, 5)
        self.assertTrue(e._fatal)

    async def test_disconnected_finalize_completes(self):
        e = self.new()
        await e.finalize("session-a")
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_timeout_finalize_completes_once(self):
        e = self.new()
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(),
            close=AsyncMock(),
        )
        e._schedule_reconnect = Mock()

        async def timeout(coro, **kw):
            coro.close()
            raise asyncio.TimeoutError

        with patch.object(rt.asyncio, "wait_for", new=timeout):
            await e.finalize("session-a")
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertIsNone(e.connection)

    async def test_commit_write_failure_closes_recovers_and_acks_once(self):
        e = self.new()
        connection = Mock(
            is_connected=Mock(return_value=True), close=AsyncMock()
        )

        async def commit():
            connection._committed = True
            raise OSError("write failed while receiver remains open")

        connection.commit = AsyncMock(side_effect=commit)
        e.connection = connection
        e._turn_bytes = 32000
        e._schedule_reconnect = Mock()
        await e.finalize("session-a")
        connection.close.assert_awaited_once()
        e.send_asr_finalize_end.assert_awaited_once()
        e._schedule_reconnect.assert_called_once()
        self.assertIsNone(e.connection)
        self.assertFalse(e._finalize_pending)
        self.assertEqual(
            e.send_asr_error.await_args.args[1].code, "finalize_failed"
        )
        self.assertEqual(e._emitted_ms, 1000)

    async def test_commit_failure_cannot_close_replacement_during_error_emit(
        self,
    ):
        e = self.new()
        entered, release = asyncio.Event(), asyncio.Event()

        async def send_error(*_args):
            entered.set()
            await release.wait()

        e.send_asr_error = AsyncMock(side_effect=send_error)
        old = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=OSError("failed")),
            close=AsyncMock(),
        )
        e.connection = old
        e._turn_bytes = 32000
        e._schedule_reconnect = Mock()
        pending = asyncio.create_task(e.finalize("session-a"))
        await entered.wait()
        await e.on_close(1006, "old closed")
        e._generation += 1
        e._reset_turn()
        replacement = Mock(
            is_connected=Mock(return_value=True), close=AsyncMock()
        )
        e.connection = replacement
        e._turn_bytes = 320
        e.on_disconnected.reset_mock()
        release.set()
        await pending
        replacement.close.assert_not_called()
        self.assertIs(e.connection, replacement)
        self.assertEqual(e._emitted_ms, 1000)
        self.assertFalse(e._turn_done.is_set())
        e.on_disconnected.assert_not_called()
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_timed_out_turn_advances_next_result_once(self):
        e = self.new()
        e._turn_bytes = 32000
        old_callback = rt._TurnCallback(e, e._generation)
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(),
            close=AsyncMock(),
        )
        e._schedule_reconnect = Mock()
        with patch.object(rt, "IO_TIMEOUT_SECONDS", 0.001):
            await e.finalize("session-a")
        await old_callback.on_close(1000, "late close")
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("next")
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual((result.start_ms, result.duration_ms), (1000, 500))
        self.assertEqual(e._emitted_ms, 1500)

    async def test_late_final_after_timeout_does_not_finish_next_turn(self):
        e = self.new()
        e._turn_bytes = 32000
        entered, release = asyncio.Event(), asyncio.Event()

        async def emit(_result):
            entered.set()
            await release.wait()

        e.send_asr_result = AsyncMock(side_effect=emit)
        e._finalize_pending = True
        pending = asyncio.create_task(e.on_final("late final"))
        await entered.wait()
        await e._close_current()
        await e._finish_finalize()
        self.assertEqual(e._emitted_ms, 1000)
        e._reset_turn()
        e._turn_bytes = 16000
        e._finalize_pending = True
        release.set()
        await pending
        self.assertEqual(e._emitted_ms, 1000)
        self.assertFalse(e._turn_done.is_set())
        self.assertTrue(e._finalize_pending)
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_reconnect_flush_cannot_replace_finalize_context(self):
        e = self.new()
        request_metadata = {
            "session_id": "finalize-session",
            "request": "finalize",
        }
        audio_metadata = {"session_id": "audio-session", "request": "audio"}
        e.metadata = copy.deepcopy(request_metadata)
        e.session_id = "finalize-session"
        frame = Mock(
            lock_buf=Mock(return_value=b"\0\0" * 160),
            get_buf=Mock(return_value=b"\0\0" * 160),
            get_property_to_json=Mock(
                return_value=(json.dumps(audio_metadata), None)
            ),
        )
        e.buffered_frames.put_nowait(frame)
        ack_metadata = []

        async def acknowledge():
            ack_metadata.append(copy.deepcopy(e.metadata))

        e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)

        async def commit():
            await e.on_final("buffered turn")

        connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(),
            commit=AsyncMock(side_effect=commit),
        )

        async def reopen():
            e._generation += 1
            e._reset_turn()
            e._flushing = True
            e.connection = connection
            await e.on_open()

        e._reopen = AsyncMock(side_effect=reopen)
        await e.finalize("finalize-session")
        await e._reconnect_task
        self.assertEqual(ack_metadata, [request_metadata])
        self.assertEqual(e.metadata, audio_metadata)
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual(result.metadata["session_id"], "finalize-session")
        self.assertEqual(result.metadata["request"], "finalize")

    async def test_final_then_close_only_completes_once(self):
        e = self.new()
        e._finalize_pending = True
        e._turn_bytes = 32000
        e._schedule_reconnect = Mock()
        await e.on_final("hello")
        await e.on_close(1000, "done")
        e.send_asr_finalize_end.assert_awaited_once()
        self.assertEqual(e._emitted_ms, 1000)

    async def test_empty_final_not_emitted(self):
        e = self.new()
        e._finalize_pending = True
        await e.on_final("  ")
        e.send_asr_result.assert_not_called()
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_empty_final_advances_next_turn_timeline_once(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e._turn_bytes = 32000
        await e.on_final("  ")
        await e.on_final("")
        await e.on_close(1000, "done")
        e.send_asr_result.assert_not_called()
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("hello")
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual((result.start_ms, result.duration_ms), (1000, 500))

    async def test_concurrent_finalize_requests_preserve_id_and_session(self):
        e = rt.OrukRealtimeASRExtension("test")
        entered, release = asyncio.Event(), asyncio.Event()
        completed = []

        async def finalize(session_id):
            if not entered.is_set():
                entered.set()
                await release.wait()
            completed.append((e.finalize_id, e.metadata["session_id"]))

        e.finalize = finalize

        def request(number):
            return Mock(
                get_name=Mock(return_value="asr_finalize"),
                get_property_string=Mock(
                    return_value=(f"finalize-{number}", None)
                ),
                get_property_to_json=Mock(
                    return_value=(
                        '{"session_id":"session-' + str(number) + '"}',
                        None,
                    )
                ),
            )

        first = asyncio.create_task(e.on_data(e.ten_env, request(1)))
        await asyncio.wait_for(entered.wait(), timeout=1)
        second = asyncio.create_task(e.on_data(e.ten_env, request(2)))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
        self.assertEqual(
            completed,
            [
                ("finalize-1", "session-1"),
                ("finalize-2", "session-2"),
            ],
        )

    async def test_two_turn_timeline(self):
        e = self.new()
        e._turn_bytes = 32000
        await e.on_final("one")
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("two")
        results = [x.args[0] for x in e.send_asr_result.await_args_list]
        self.assertEqual(
            [(x.start_ms, x.duration_ms) for x in results],
            [(0, 1000), (1000, 500)],
        )
        self.assertEqual(results[1].metadata["session_id"], "session-a")

    async def test_invalid_config_never_echoes_credential_values(self):
        e = self.new()
        env = Mock()
        secret = "DO_NOT_LOG_THIS_CREDENTIAL"
        env.get_property_to_json = AsyncMock(
            return_value=('{"params":"' + secret + '"}', None)
        )
        await e.on_init(env)
        self.assertNotIn(secret, e.send_asr_error.await_args.args[0].message)
        self.assertNotIn(secret, str(env.log_error.call_args))

    async def test_invalid_config_latches(self):
        e = self.new()
        env = Mock()
        env.get_property_to_json = AsyncMock(return_value=("{}", None))
        await e.on_init(env)
        with patch.object(rt, "OrukRealtimeConnection") as constructor:
            await e.start_connection()
            constructor.assert_not_called()
        self.assertTrue(e._init_failed)
        e.send_asr_error.assert_awaited_once()
        e.on_disconnected.assert_awaited_once()
        vendor_info = e.send_asr_error.await_args.args[1]
        self.assertEqual(vendor_info.vendor, "oruk")
        self.assertEqual(vendor_info.code, "invalid_config")
        self.assertEqual(vendor_info.message, "Invalid Oruk ASR configuration")

    async def test_stop_during_handshake_closes_late_client(self):
        e = self.new()
        began, release = asyncio.Event(), asyncio.Event()

        async def start(**kw):
            began.set()
            await release.wait()

        client = Mock(start=start, close=AsyncMock())
        with patch.object(rt, "OrukRealtimeConnection", return_value=client):
            task = asyncio.create_task(e.start_connection())
            await asyncio.wait_for(began.wait(), timeout=1)
            e.stopped = True
            await e.stop_connection()
            release.set()
            await task
        self.assertIsNone(e.connection)
        self.assertGreaterEqual(client.close.await_count, 1)
        e.on_connected.assert_not_called()

    async def test_failed_start_closes_transport(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        client = Mock(
            start=AsyncMock(side_effect=OSError("network")), close=AsyncMock()
        )
        with patch.object(rt, "OrukRealtimeConnection", return_value=client):
            await e.start_connection()
        client.close.assert_awaited_once()
        self.assertIsNone(e.connection)
        e.on_disconnected.assert_awaited_once()

    async def test_frame_unlocks_on_send_error(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
            close=AsyncMock(),
        )
        f = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))
        self.assertFalse(await e.send_audio(f, None))
        f.unlock_buf.assert_called_once()
        e.audio_timeline.add_user_audio.assert_not_called()

    async def test_send_failure_recovers_open_socket_after_unlock(self):
        for failure in (OSError("write failed"), asyncio.TimeoutError()):
            with self.subTest(failure=type(failure).__name__):
                e = self.new()
                e._schedule_reconnect = Mock()
                e._turn_bytes = 32000
                e._finalize_pending = True
                e._turn_finalize_context = e._snapshot_context()
                frame = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))

                async def close():
                    self.assertFalse(e._io_lock.locked())
                    frame.unlock_buf.assert_called_once()

                old_callback = rt._TurnCallback(e, e._generation)
                connection = Mock(
                    is_connected=Mock(return_value=True),
                    send_pcm=AsyncMock(side_effect=failure),
                    close=AsyncMock(side_effect=close),
                )
                e.connection = connection
                self.assertFalse(await e.send_audio(frame, None))
                connection.close.assert_awaited_once()
                self.assertIsNone(e.connection)
                e.on_disconnected.assert_awaited_once_with(
                    code=0, message="Oruk audio send failed"
                )
                e._schedule_reconnect.assert_called_once()
                e.send_asr_finalize_end.assert_awaited_once()
                self.assertEqual(
                    e.send_asr_error.await_args.args[1].code, "send_failed"
                )
                await old_callback.on_close(1000, "late")
                self.assertEqual(e._emitted_ms, 1010)
                e._reset_turn()
                e._turn_bytes = 16000
                await e.on_final("next turn")
                result = e.send_asr_result.await_args.args[0]
                self.assertEqual(
                    (result.start_ms, result.duration_ms), (1010, 500)
                )

    async def test_send_failure_cannot_close_replacement_during_error_emit(
        self,
    ):
        e = self.new()
        e._schedule_reconnect = Mock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def send_error(*_args):
            self.assertFalse(e._io_lock.locked())
            entered.set()
            await release.wait()

        e.send_asr_error = AsyncMock(side_effect=send_error)
        old = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
            close=AsyncMock(),
        )
        e.connection = old
        e._turn_bytes = 32000
        frame = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))
        pending = asyncio.create_task(e.send_audio(frame, None))
        await entered.wait()
        await e.on_close(1006, "old closed")
        e._generation += 1
        e._reset_turn()
        replacement = Mock(
            is_connected=Mock(return_value=True), close=AsyncMock()
        )
        e.connection = replacement
        e._turn_bytes = 320
        e.on_disconnected.reset_mock()
        e._schedule_reconnect.reset_mock()
        release.set()
        self.assertFalse(await pending)
        replacement.close.assert_not_called()
        self.assertIs(e.connection, replacement)
        self.assertEqual(e._emitted_ms, 1010)
        self.assertFalse(e._turn_done.is_set())
        e.on_disconnected.assert_not_called()
        e._schedule_reconnect.assert_not_called()

    async def test_send_failure_close_cannot_disconnect_replacement(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def close():
            entered.set()
            await release.wait()

        old = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
            close=AsyncMock(side_effect=close),
        )
        e.connection = old
        e._turn_bytes = 32000
        frame = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))
        pending = asyncio.create_task(e.send_audio(frame, None))
        await entered.wait()
        e._generation += 1
        e._reset_turn()
        replacement = Mock(
            is_connected=Mock(return_value=True), close=AsyncMock()
        )
        e.connection = replacement
        e._turn_bytes = 320
        release.set()
        self.assertFalse(await pending)
        replacement.close.assert_not_called()
        self.assertIs(e.connection, replacement)
        self.assertEqual(e._emitted_ms, 1010)
        self.assertFalse(e._turn_done.is_set())
        e.on_disconnected.assert_not_called()
        e._schedule_reconnect.assert_not_called()

    async def test_failed_flush_preserves_audio_in_order(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
            close=AsyncMock(),
        )
        frames = [
            Mock(
                lock_buf=Mock(return_value=b"\0\0"),
                get_buf=Mock(return_value=b"\0\0"),
            )
            for _ in range(2)
        ]
        for f in frames:
            await e.buffered_frames.put(f)
        with self.assertRaises(ConnectionError):
            await e._flush_buffered_audio()
        self.assertIs(e.buffered_frames.get_nowait(), frames[0])
        self.assertIs(e.buffered_frames.get_nowait(), frames[1])

    async def test_old_finalize_waiter_does_not_commit_new_turn(self):
        e = self.new()
        e.connection = Mock(is_connected=Mock(return_value=False))
        task = asyncio.create_task(e.finalize(None))
        await asyncio.sleep(0)
        e._generation += 1
        new = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(),
            close=AsyncMock(),
        )
        e.connection = new
        e._ready_event.set()
        await task
        new.commit.assert_not_called()
        new.close.assert_not_called()
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_dump_failure_does_not_repeat_accepted_audio(self):
        e = self.new()
        e.connection = Mock(
            is_connected=Mock(return_value=True), send_pcm=AsyncMock()
        )
        e.audio_dumper = Mock(push_bytes=AsyncMock(side_effect=OSError()))
        f = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))
        self.assertTrue(await e.send_audio(f, None))
        e.connection.send_pcm.assert_awaited_once()
        self.assertEqual(e._turn_bytes, 320)

    async def test_metadata_from_buffered_frame_preserved(self):
        e = self.new()
        f = Mock(
            get_property_to_json=Mock(
                return_value=(
                    '{"session_id":"buffered-session","request":"r"}',
                    None,
                )
            )
        )
        e._capture_metadata(f)
        self.assertEqual(e.session_id, "buffered-session")
        self.assertEqual(e._build_metadata()["session_id"], "buffered-session")

    async def test_realtime_open_flushes_before_ready(self):
        e = self.new()
        e._flushing = True
        e.connection = Mock(
            is_connected=Mock(return_value=True), send_pcm=AsyncMock()
        )
        f = Mock(
            lock_buf=Mock(return_value=b"\0\0" * 160),
            get_buf=Mock(return_value=b"\0\0" * 160),
            get_property_to_json=Mock(
                return_value=('{"session_id":"buffered-session"}', None)
            ),
        )
        await e.buffered_frames.put(f)
        await e.on_open()
        e.connection.send_pcm.assert_awaited_once()
        self.assertTrue(e._ready_event.is_set())
        self.assertFalse(e._flushing)
        self.assertEqual(e.session_id, "buffered-session")

    async def test_failed_write_after_eviction_abandons_affected_retry(self):
        e = self.new()
        e._schedule_reconnect = Mock()
        e.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=64000)
        )
        frames = [
            Mock(
                get_buf=Mock(return_value=b"\0" * n),
                lock_buf=Mock(return_value=b"\0" * n),
            )
            for n in (32000, 32000, 64000)
        ]
        for frame in frames[:2]:
            await e._handle_audio_frame(e.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(_data):
            entered.set()
            await release.wait()
            raise OSError("failed after eviction")

        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=send),
            close=AsyncMock(),
        )
        e._flushing = True
        flushing = asyncio.create_task(e._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        await e._handle_audio_frame(e.ten_env, frames[2])
        release.set()
        with self.assertRaises(ConnectionError):
            await asyncio.wait_for(flushing, 1)
        self.assertTrue(e.buffered_frames.empty())
        self.assertEqual(e.dropped_audio_frames, 3)
        self.assertEqual(e._emitted_ms, 4000)
        e._reset_turn()
        e._turn_bytes = 16000
        await e.on_final("next turn")
        result = e.send_asr_result.await_args.args[0]
        self.assertEqual((result.start_ms, result.duration_ms), (4000, 500))

    async def test_connected_finalize_preserves_known_or_explicit_session(self):
        for supplied in (
            {},
            {"request_tag": "x"},
            {"session_id": "override", "request_tag": "x"},
        ):
            with self.subTest(metadata=supplied):
                e = self.new()
                e.metadata = {"session_id": "session-s"}
                e.session_id = "session-s"
                acknowledgements = []

                async def commit():
                    await e.on_final("connected transcript")

                async def acknowledge():
                    acknowledgements.append(copy.deepcopy(e.metadata))

                e.connection = Mock(
                    is_connected=Mock(return_value=True),
                    commit=AsyncMock(side_effect=commit),
                )
                e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
                request = Mock(
                    get_name=Mock(return_value="asr_finalize"),
                    get_property_to_json=Mock(
                        return_value=(json.dumps(supplied), None)
                    ),
                    get_property_string=Mock(
                        return_value=("connected-finalize", None)
                    ),
                )
                await e.on_data(e.ten_env, request)
                expected = {"session_id": "session-s", **supplied}
                result = e.send_asr_result.await_args.args[0]
                self.assertEqual(
                    {key: result.metadata[key] for key in expected}, expected
                )
                self.assertEqual(acknowledgements, [expected])

    async def test_failed_readiness_uses_buffered_session_for_finalize(self):
        for failure in ("timeout", "fatal", "stopped"):
            for supplied in (
                None,
                {},
                {"request_tag": "x"},
                {"session_id": "override", "request_tag": "x"},
            ):
                with self.subTest(failure=failure, metadata=supplied):
                    e = self.new()
                    e._schedule_reconnect = Mock()
                    audio_metadata = {
                        "session_id": "session-b",
                        "audio_tag": "buffered",
                    }
                    frame = Mock(
                        get_buf=Mock(return_value=b"\0" * 32000),
                        get_property_to_json=Mock(
                            return_value=(json.dumps(audio_metadata), None)
                        ),
                    )
                    await e._handle_audio_frame(e.ten_env, frame)
                    e._fatal = failure == "fatal"
                    e.stopped = failure == "stopped"
                    acknowledgements, errors = [], []

                    async def acknowledge():
                        acknowledgements.append(copy.deepcopy(e.metadata))

                    async def report(*_args):
                        errors.append(copy.deepcopy(e.metadata))

                    e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
                    e.send_asr_error = AsyncMock(side_effect=report)
                    request = Mock(
                        get_name=Mock(return_value="asr_finalize"),
                        get_property_to_json=Mock(
                            return_value=(
                                (
                                    json.dumps(supplied)
                                    if supplied is not None
                                    else ""
                                ),
                                None,
                            )
                        ),
                        get_property_string=Mock(
                            return_value=("finalize-b", None)
                        ),
                    )
                    with patch.object(rt, "IO_TIMEOUT_SECONDS", 0.001):
                        await e.on_data(e.ten_env, request)
                    expected = (
                        supplied
                        if supplied and "session_id" in supplied
                        else {**audio_metadata, **(supplied or {})}
                    )
                    self.assertEqual(acknowledgements, [expected])
                    self.assertEqual(
                        errors, [expected] if failure == "timeout" else []
                    )
                    self.assertTrue(e.buffered_frames.empty())
                    self.assertEqual(e.dropped_audio_frames, 1)
                    self.assertEqual(e._emitted_ms, 1000)
                    e._fatal = False
                    e.stopped = False
                    e._reset_turn()
                    e._turn_bytes = 16000
                    await e.on_final("next turn")
                    result = e.send_asr_result.await_args.args[0]
                    self.assertEqual(
                        (result.start_ms, result.duration_ms), (1000, 500)
                    )

    async def test_finalize_before_trigger_never_starts_transport(self):
        e = self.new()
        e.auto_connect = False
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            get_property_to_json=Mock(
                return_value=(json.dumps({"session_id": "pretrigger"}), None)
            ),
        )
        await e._handle_audio_frame(e.ten_env, frame)
        e._finalize_metadata_explicit.set(False)
        acknowledgements = []

        async def acknowledge():
            acknowledgements.append(copy.deepcopy(e.metadata))

        e.send_asr_finalize_end = AsyncMock(side_effect=acknowledge)
        with patch.object(rt, "OrukRealtimeConnection") as constructor:
            await e.finalize(None)
            await e.start_connection()
            e._schedule_reconnect()
            await e._reopen()
            constructor.assert_not_called()
        self.assertIsNone(e._reconnect_task)
        self.assertTrue(e.buffered_frames.empty())
        self.assertEqual(e.dropped_audio_frames, 1)
        self.assertEqual(e._emitted_ms, 1000)
        self.assertEqual(acknowledgements, [{"session_id": "pretrigger"}])
        e._connection_requested = True
        e._reopen = AsyncMock()
        e._schedule_reconnect()
        await e._reconnect_task
        e._reopen.assert_awaited_once()

    async def test_partial_audio_metadata_keeps_interim_session(self):
        for supplied in (
            None,
            {},
            {"trace": "t"},
            {"session_id": "override", "trace": "t"},
        ):
            with self.subTest(metadata=supplied):
                e = self.new()
                e.connection = Mock(
                    is_connected=Mock(return_value=True), send_pcm=AsyncMock()
                )
                for metadata in ({"session_id": "session-s"}, supplied):
                    raw = json.dumps(metadata) if metadata is not None else ""
                    frame = Mock(
                        lock_buf=Mock(return_value=b"\0" * 320),
                        get_property_to_json=Mock(return_value=(raw, None)),
                    )
                    self.assertTrue(await e.send_audio(frame, e.session_id))
                await e.on_interim("first words")
                expected = {"session_id": "session-s", **(supplied or {})}
                result = e.send_asr_result.await_args.args[0]
                self.assertEqual(
                    {key: result.metadata[key] for key in expected}, expected
                )
                self.assertEqual(e.session_id, expected["session_id"])


class Transport(unittest.IsolatedAsyncioTestCase):
    def new(self):
        return transport.OrukRealtimeConnection(
            api_key="unit-key",
            url="wss://speech-api.oruk.ai/v1/audio/realtime",
            language="en",
            phrase_emotions=True,
            diarize=False,
            sample_rate=16000,
            callback=Mock(
                on_close=AsyncMock(),
                on_error=AsyncMock(),
                on_interim=AsyncMock(),
                on_final=AsyncMock(),
            ),
            ten_env=Mock(),
        )

    async def test_interim_deltas_accumulate_within_each_turn(self):
        first, second = self.new(), self.new()
        for delta in ("hello", " world"):
            await first._dispatch(
                {"type": transport.TRANSCRIPT_PREFIX + "delta", "delta": delta}
            )
        await first._dispatch(
            {
                "type": transport.TRANSCRIPT_PREFIX + "completed",
                "transcript": "Hello world.",
            }
        )
        await second._dispatch(
            {"type": transport.TRANSCRIPT_PREFIX + "delta", "delta": "next"}
        )
        self.assertEqual(
            [
                call.args[0]
                for call in first._callback.on_interim.await_args_list
            ],
            ["hello", "hello world"],
        )
        first._callback.on_final.assert_awaited_once_with("Hello world.")
        second._callback.on_interim.assert_awaited_once_with("next")

    async def test_interim_accumulator_has_a_size_limit(self):
        e = self.new()
        with patch.object(transport, "_MAX_TRANSCRIPT_CHARS", 8):
            await e._dispatch(
                {
                    "type": transport.TRANSCRIPT_PREFIX + "delta",
                    "delta": "hello",
                }
            )
            with self.assertRaisesRegex(RuntimeError, "exceeds limit"):
                await e._dispatch(
                    {
                        "type": transport.TRANSCRIPT_PREFIX + "delta",
                        "delta": " world",
                    }
                )
        self.assertEqual(e._interim_text, "hello")
        e._callback.on_interim.assert_awaited_once_with("hello")

    async def test_close_codes_distinguish_success_and_transport_failure(self):
        for code in (1000, 1001, 1011, None):
            with self.subTest(code=code):
                e = self.new()
                e._final_received = True
                e._socket = Mock(
                    closed=False,
                    close_code=code,
                    close=AsyncMock(),
                    receive=AsyncMock(
                        return_value=types.SimpleNamespace(
                            type=(
                                transport.aiohttp.WSMsgType.CLOSE
                                if code is not None
                                else transport.aiohttp.WSMsgType.CLOSED
                            ),
                            data=code,
                        )
                    ),
                )
                e._session = Mock(closed=False, close=AsyncMock())
                await e._receive_loop()
                reported_code = code or 1006
                self.assertEqual(
                    e._callback.on_close.await_args.args[0], reported_code
                )
                if code in (1000, 1001):
                    e._callback.on_error.assert_not_called()
                else:
                    e._callback.on_error.assert_awaited_once_with(
                        f"Oruk WebSocket closed abnormally ({reported_code})",
                        f"websocket_close_{reported_code}",
                        fatal=False,
                    )
                e._socket.close.assert_awaited_once()
                e._session.close.assert_awaited_once()

    async def test_committed_close_without_final_reports_incomplete_turn(self):
        e = self.new()
        e._committed = True
        e._socket = Mock(closed=False, close_code=1000, close=AsyncMock())
        e._session = Mock(closed=False, close=AsyncMock())
        e._receive_json = AsyncMock(return_value=None)
        await e._receive_loop()
        self.assertEqual(
            e._callback.on_error.await_args.args[1], "missing_final"
        )
        e._callback.on_close.assert_awaited_once()

    async def test_abnormal_close_emits_vendor_error_before_recovery(self):
        e = rt.OrukRealtimeASRExtension("test")
        e.config = rt.OrukRealtimeASRConfig(params={"api_key": "unit-key"})
        e._schedule_reconnect = Mock()
        connection = self.new()
        connection._callback = rt._TurnCallback(e, e._generation)
        connection._socket = Mock(
            closed=False, close_code=1011, close=AsyncMock()
        )
        connection._session = Mock(closed=False, close=AsyncMock())
        connection._receive_json = AsyncMock(return_value=None)
        e.connection = connection
        await connection._receive_loop()
        e.send_asr_error.assert_awaited_once()
        error, vendor = e.send_asr_error.await_args.args
        self.assertEqual(error.code, m.ModuleErrorCode.NON_FATAL_ERROR.value)
        self.assertEqual(vendor.vendor, "oruk")
        self.assertEqual(vendor.code, "websocket_close_1011")
        e.on_disconnected.assert_awaited_once_with(
            code=1011, message="Oruk WebSocket closed abnormally (1011)"
        )
        self.assertIsNone(e.connection)
        e._schedule_reconnect.assert_called_once()

    async def test_partial_handshake_failure_closes_session(self):
        e = self.new()
        session = Mock(
            closed=False,
            ws_connect=AsyncMock(side_effect=OSError()),
            close=AsyncMock(),
        )
        with patch.object(
            transport.aiohttp, "ClientSession", return_value=session
        ):
            with self.assertRaises(OSError):
                await e.start(request_id="test")
        session.close.assert_awaited_once()

    async def test_receive_end_closes_per_turn_session(self):
        e = self.new()
        e._socket = Mock(closed=False, close_code=1000, close=AsyncMock())
        e._session = Mock(closed=False, close=AsyncMock())
        e._receive_json = AsyncMock(return_value=None)
        await e._receive_loop()
        e._socket.close.assert_awaited_once()
        e._session.close.assert_awaited_once()
        e._callback.on_close.assert_awaited_once()

    async def test_close_from_own_receive_callback_no_self_await(self):
        e = self.new()
        e._receiver = asyncio.current_task()
        e._socket = Mock(closed=False, close=AsyncMock())
        e._session = Mock(closed=False, close=AsyncMock())
        session = e._session
        await e.close()
        self.assertTrue(e._closing)
        session.close.assert_awaited_once()

    async def test_committed_turn_reports_disconnected_for_buffering(self):
        e = self.new()
        e._ready = True
        e._socket = Mock(closed=False)
        self.assertTrue(e.is_connected())
        self.assertTrue(e.is_active())
        e._committed = True
        self.assertFalse(e.is_connected())
        self.assertTrue(e.is_active())
        e._socket.closed = True
        self.assertFalse(e.is_active())
        e._socket.closed = False
        e._closing = True
        self.assertFalse(e.is_active())

    async def test_committed_turn_rejects_audio(self):
        e = self.new()
        e._committed = True
        with self.assertRaises(ConnectionError):
            await e.send_pcm(b"\0\0")


if __name__ == "__main__":
    unittest.main()
