"""Offline fault-injection tests of the actual extension and transport methods.

The thin TEN boundary is stubbed; these do not replace native ASR guarders.
Run: python -m unittest discover -s tests/unit -v
"""

import asyncio
import copy
import importlib
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
        self.uuid = "request-test"
        self.metadata = {"session_id": "session-a"}
        self.session_id = "session-a"
        self.buffered_frames = asyncio.Queue()
        self.buffered_frames_size = 0
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
for package, directory in [
    ("_oruk_unit_realtime", "oruk_realtime_asr_python"),
    ("_oruk_unit_local", "oruk_asr_python"),
]:
    namespace = types.ModuleType(package)
    namespace.__path__ = [str(ROOT / directory)]
    sys.modules[package] = namespace
rt = importlib.import_module("_oruk_unit_realtime.extension")
transport = importlib.import_module("_oruk_unit_realtime.recognition")
local = importlib.import_module("_oruk_unit_local.extension")

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
        for extension in (
            rt.OrukRealtimeASRExtension,
            local.OrukASRExtension,
        ):
            with self.subTest(extension=extension.__name__):
                e = extension("test")
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
                await entered.wait()
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
            await began.wait()
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
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
        )
        f = Mock(lock_buf=Mock(return_value=b"\0\0" * 160))
        self.assertFalse(await e.send_audio(f, None))
        f.unlock_buf.assert_called_once()
        e.audio_timeline.add_user_audio.assert_not_called()

    async def test_failed_flush_preserves_audio_in_order(self):
        e = self.new()
        e.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError()),
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

    async def test_local_finalize_waits_for_model_and_buffer_flush(self):
        e = local.OrukASRExtension("test")
        e.config = types.SimpleNamespace(
            sample_rate=16000, asr_result_language="en"
        )
        e.recognizer = Mock(loaded=True, recognize=Mock(return_value="hello"))
        e._loading = True
        f = Mock(
            lock_buf=Mock(return_value=b"\0\0" * 160),
            get_buf=Mock(return_value=b"\0\0" * 160),
            get_property_to_json=Mock(
                return_value=('{"session_id":"warmup-session"}', None)
            ),
        )
        await e.buffered_frames.put(f)
        task = asyncio.create_task(e.finalize(None))
        await asyncio.sleep(0)
        e.send_asr_result.assert_not_called()
        await e._flush_buffered_audio()
        e._loading = False
        e._ready_event.set()
        await task
        self.assertEqual(
            e.send_asr_result.await_args.args[0].metadata["session_id"],
            "warmup-session",
        )
        e.send_asr_finalize_end.assert_awaited_once()

    async def test_local_invalid_config_never_loads_model(self):
        e = local.OrukASRExtension("test")
        e._init_failed = True
        with patch.object(local, "OrukeetRecognizer") as constructor:
            await e.start_connection()
            constructor.assert_not_called()
        e.on_disconnected.assert_awaited_once()
        e.send_asr_error.assert_not_called()

    async def test_local_errors_include_vendor_details(self):
        for failure in (
            "invalid_config",
            "model_load_failed",
            "recognition_failed",
        ):
            with self.subTest(failure=failure):
                e = local.OrukASRExtension("test")
                if failure == "invalid_config":
                    env = Mock()
                    env.get_property_to_json = AsyncMock(
                        return_value=('{"params":{"sample_rate":8000}}', None)
                    )
                    await e.on_init(env)
                    with patch.object(
                        local, "OrukeetRecognizer"
                    ) as constructor:
                        await e.start_connection()
                        constructor.assert_not_called()
                    e.on_disconnected.assert_awaited_once()
                else:
                    e.config = types.SimpleNamespace(
                        sample_rate=16000,
                        asr_result_language="en",
                        cache_dir=None,
                        local_files_only=True,
                    )
                    e.recognizer = Mock(
                        prewarm=Mock(side_effect=RuntimeError("load failed")),
                        recognize=Mock(
                            side_effect=RuntimeError("inference failed")
                        ),
                    )
                    if failure == "model_load_failed":
                        await e.start_connection()
                        self.assertTrue(e._init_failed)
                        e.on_disconnected.assert_awaited_once()
                    else:
                        e._utterance.extend(b"\0\0" * 160)
                        await e.finalize(None)
                        e.send_asr_finalize_end.assert_awaited_once()
                e.send_asr_error.assert_awaited_once()
                vendor_info = e.send_asr_error.await_args.args[1]
                self.assertEqual(vendor_info.vendor, "oruk")
                self.assertEqual(vendor_info.code, failure)
                self.assertTrue(vendor_info.message)

    async def test_local_stop_suppresses_in_flight_result_and_error(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                e = local.OrukASRExtension("test")
                e.config = types.SimpleNamespace(
                    sample_rate=16000, asr_result_language="en"
                )
                e.recognizer = Mock()
                e._utterance.extend(b"\0\0" * 160)
                entered, release = asyncio.Event(), asyncio.Event()

                async def recognize(*args):
                    entered.set()
                    await release.wait()
                    if failure:
                        raise RuntimeError("closed during recognition")
                    return "late result"

                with patch.object(local.asyncio, "to_thread", new=recognize):
                    task = asyncio.create_task(e.finalize(None))
                    await entered.wait()
                    e.stopped = True
                    release.set()
                    await task
                e.send_asr_result.assert_not_called()
                e.send_asr_error.assert_not_called()
                e.send_asr_finalize_end.assert_awaited_once()

    async def test_local_next_turn_keeps_finalize_metadata_isolated(self):
        e = local.OrukASRExtension("test")
        e.config = types.SimpleNamespace(
            sample_rate=16000, asr_result_language="en"
        )
        e.recognizer = Mock(loaded=True)
        e._connected = True
        e._utterance.extend(b"\0\0" * 160)
        entered, release = asyncio.Event(), asyncio.Event()
        results, acknowledgements, metric_sessions = [], [], []

        async def emit_result(result):
            # The native helper merges current metadata even when the result
            # already carries a snapshot, then reads it again for metrics.
            result.metadata.update(e.metadata)
            results.append(copy.deepcopy(result.metadata))
            await asyncio.sleep(0)
            metric_sessions.append(e.session_id)

        async def emit_finalize_end():
            acknowledgements.append((e.finalize_id, copy.deepcopy(e.metadata)))

        e.send_asr_result = AsyncMock(side_effect=emit_result)
        e.send_asr_finalize_end = AsyncMock(side_effect=emit_finalize_end)

        def request(session):
            return Mock(
                get_name=Mock(return_value="asr_finalize"),
                get_property_string=Mock(
                    return_value=("finalize-" + session, None)
                ),
                get_property_to_json=Mock(
                    return_value=(
                        '{"session_id":"session-' + session + '"}',
                        None,
                    )
                ),
            )

        async def recognize(*args):
            entered.set()
            await release.wait()
            return "turn words"

        with patch.object(local.asyncio, "to_thread", new=recognize):
            first = asyncio.create_task(e.on_data(e.ten_env, request("a")))
            await entered.wait()
            self.assertTrue(e.is_connected())
            next_frame = Mock(
                lock_buf=Mock(return_value=b"\0\0" * 160),
                get_property_to_json=Mock(
                    return_value=('{"session_id":"session-b"}', None)
                ),
            )
            self.assertTrue(await e.send_audio(next_frame, "session-b"))
            release.set()
            await first
            self.assertEqual(e.metadata, {"session_id": "session-b"})
            self.assertEqual(e.session_id, "session-b")
            self.assertEqual(len(e._utterance), 320)
            await e.on_data(e.ten_env, request("b"))

        self.assertEqual(
            [result["session_id"] for result in results],
            ["session-a", "session-b"],
        )
        self.assertEqual(metric_sessions, ["session-a", "session-b"])
        self.assertEqual(
            acknowledgements,
            [
                ("finalize-a", {"session_id": "session-a"}),
                ("finalize-b", {"session_id": "session-b"}),
            ],
        )

    async def test_local_timeline_survives_model_reconnect(self):
        e = local.OrukASRExtension("test")
        e.config = types.SimpleNamespace(
            sample_rate=16000,
            asr_result_language="en",
            cache_dir="",
            local_files_only=True,
        )
        e.recognizer = Mock(loaded=True, recognize=Mock(return_value="hello"))
        f = Mock(lock_buf=Mock(return_value=b"\0\0" * 8000))
        await e.send_audio(f, None)
        await e.finalize(None)
        self.assertEqual(e.send_asr_result.await_args.args[0].start_ms, 700)
        e.audio_timeline.add_user_audio.assert_called_once_with(500)


class Transport(unittest.IsolatedAsyncioTestCase):
    def new(self):
        return transport.OrukRealtimeConnection(
            api_key="unit-key",
            url="wss://speech-api.oruk.ai/v1/audio/realtime",
            language="en",
            phrase_emotions=True,
            diarize=False,
            sample_rate=16000,
            callback=Mock(on_close=AsyncMock(), on_error=AsyncMock()),
            ten_env=Mock(),
        )

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
        e._committed = True
        self.assertFalse(e.is_connected())

    async def test_committed_turn_rejects_audio(self):
        e = self.new()
        e._committed = True
        with self.assertRaises(ConnectionError):
            await e.send_pcm(b"\0\0")


if __name__ == "__main__":
    unittest.main()
