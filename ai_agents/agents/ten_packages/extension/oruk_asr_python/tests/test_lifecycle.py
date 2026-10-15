"""Local queue ordering and native-work deadline regressions, without models."""

import asyncio
import copy
import importlib
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Keep these tests runnable with only this extension's dependencies installed.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class Base:
    def __init__(self, name):
        self.stopped = False
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

    def input_audio_channels(self):
        return 1

    def input_audio_sample_width(self):
        return 2

    async def on_init(self, env):
        self.ten_env = env

    async def on_deinit(self, env):
        pass

    def _safe_is_connected(self):
        return self.is_connected()

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
namespace = types.ModuleType("_oruk_unit_local")
namespace.__path__ = [str(ROOT / "oruk_asr_python")]
sys.modules["_oruk_unit_local"] = namespace
local = importlib.import_module("_oruk_unit_local.extension")
assert local.OrukASRExtension.__mro__[1] is Base

for name, original in _original_modules.items():
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


class LocalLifecycle(unittest.IsolatedAsyncioTestCase):
    _consumer_stop = object()

    def new(self):
        extension = local.OrukASRExtension("test")
        extension.config = types.SimpleNamespace(
            sample_rate=16000, asr_result_language="en"
        )
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="words")
        )
        extension._connected = True
        return extension

    async def test_keep_buffer_evictions_and_oversize_are_counted_once(self):
        extension = self.new()
        extension._connected = False
        extension.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=640)
        )
        first, second, third = [self.frame(x) for x in ("a", "b", "c")]
        for frame in (first, second, third):
            await extension._handle_audio_frame(extension.ten_env, frame)
        self.assertEqual(extension.buffered_frames_size, 640)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertIs(extension.buffered_frames.get_nowait(), second)
        self.assertIs(extension.buffered_frames.get_nowait(), third)
        extension.buffered_frames_size = 0
        await extension._handle_audio_frame(
            extension.ten_env, self.frame("large", b"\0" * 960)
        )
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertEqual(extension.dropped_audio_frames, 2)
        self.assertEqual(
            [
                call.args[0]
                for call in extension.audio_timeline.add_dropped_audio.call_args_list
            ],
            [10, 30],
        )

    async def test_failed_flush_reapplies_bound_after_concurrent_arrival(self):
        extension = self.new()
        extension._flushing = True
        extension.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=640)
        )
        first, second, third = [self.frame(x) for x in ("a", "b", "c")]
        extension._retain_audio_frame(first)
        extension._retain_audio_frame(second)
        entered, release = asyncio.Event(), asyncio.Event()

        async def fail_send(frame, session):
            entered.set()
            await release.wait()
            return False

        extension.send_audio = fail_send
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertEqual(extension.buffered_frames_size, 320)
            await extension._handle_audio_frame(extension.ten_env, third)
            self.assertEqual(extension.buffered_frames_size, 640)
            self.assertEqual(extension.dropped_audio_frames, 0)
        finally:
            release.set()
            with self.assertRaises(ConnectionError):
                await asyncio.wait_for(flushing, 1)
        self.assertEqual(extension.buffered_frames_size, 640)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertIs(extension.buffered_frames.get_nowait(), second)
        self.assertIs(extension.buffered_frames.get_nowait(), third)
        extension.audio_timeline.add_dropped_audio.assert_called_once_with(10)

    async def test_oversize_aborts_partial_flush_without_replaying_inflight(
        self,
    ):
        extension = self.new()
        extension._flushing = True
        extension.buffer_strategy = Mock(
            return_value=types.SimpleNamespace(byte_limit=960)
        )
        for label in ("a", "b", "c"):
            extension._retain_audio_frame(self.frame(label))
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def dump(pcm):
            nonlocal calls
            calls += 1
            if calls == 2:
                entered.set()
                await release.wait()

        extension.audio_dumper = Mock(push_bytes=dump)
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            await extension._handle_audio_frame(
                extension.ten_env, self.frame("invalid", b"\0" * 1280)
            )
        finally:
            release.set()
            await asyncio.wait_for(flushing, 1)
        self.assertFalse(extension._utterance)
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertEqual(extension.dropped_audio_frames, 3)
        self.assertEqual(
            [
                call.args[0]
                for call in extension.audio_timeline.add_dropped_audio.call_args_list
            ],
            [10, 40, 10],
        )
        extension.audio_timeline.add_user_audio.assert_called_once_with(10)
        extension.send_asr_error.assert_awaited_once()
        await extension.finalize("invalid")
        extension.send_asr_result.assert_not_called()
        extension.send_asr_finalize_end.assert_awaited_once()
        self.assertFalse(extension._utterance_overflow)

    async def test_flush_does_not_replay_counted_utterance_rejection(self):
        extension = self.new()
        extension._retain_audio_frame(self.frame("a"))
        extension._retain_audio_frame(self.frame("b"))
        with patch.object(local, "MAX_UTTERANCE_BYTES", 320):
            await extension._flush_buffered_audio()
        self.assertTrue(extension._utterance_overflow)
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertEqual(extension.dropped_audio_frames, 1)
        extension.audio_timeline.add_dropped_audio.assert_called_once_with(10)

    def frame(self, session="a", pcm=b"\0\0" * 160):
        return Mock(
            lock_buf=Mock(return_value=pcm),
            get_buf=Mock(return_value=pcm),
            unlock_buf=Mock(),
            get_property_to_json=Mock(
                return_value=('{"session_id":"' + session + '"}', None)
            ),
        )

    def request(self, session="a"):
        return Mock(
            get_name=Mock(return_value="asr_finalize"),
            get_property_string=Mock(
                return_value=("finalize-" + session, None)
            ),
            get_property_to_json=Mock(
                return_value=('{"session_id":"' + session + '"}', None)
            ),
        )

    async def consumer(self, extension):
        while True:
            frame = await extension.audio_frames_queue.get()
            if frame is self._consumer_stop:
                return
            await extension._handle_audio_frame(extension.ten_env, frame)

    async def stop_consumer(self, extension, consumer, *requests):
        # A stop item survives nested wait_for cancellation races on 3.10.
        extension.audio_frames_queue.put_nowait(self._consumer_stop)
        for request in requests:
            if request is not None:
                request.cancel()
        await asyncio.wait_for(
            asyncio.gather(
                consumer,
                *(request for request in requests if request is not None),
                return_exceptions=True,
            ),
            timeout=1,
        )

    async def test_finalize_orders_queued_audio_and_blocked_dump(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        dumping, release_dump = asyncio.Event(), asyncio.Event()

        async def dump(_data):
            dumping.set()
            await release_dump.wait()

        async def handle(instance, _env, frame):
            await instance.send_audio(frame, instance.session_id)

        extension.audio_dumper = Mock(push_bytes=dump)
        with patch.object(Base, "_handle_audio_frame", new=handle, create=True):
            consumer = asyncio.create_task(self.consumer(extension))
            finalize = None
            try:
                extension.audio_frames_queue.put_nowait(self.frame())
                extension.audio_frames_queue.put_nowait(self.frame())
                await asyncio.wait_for(dumping.wait(), timeout=1)
                finalize = asyncio.create_task(
                    extension.on_data(extension.ten_env, self.request())
                )
                await asyncio.sleep(0)
                extension.audio_frames_queue.put_nowait(self.frame("b"))
                extension.send_asr_finalize_end.assert_not_called()
                release_dump.set()
                await asyncio.wait_for(finalize, 1)
                self.assertEqual(
                    extension.recognizer.recognize.call_args.args[0].size, 320
                )
                self.assertEqual(len(extension._utterance), 320)
                extension.send_asr_finalize_end.assert_awaited_once()
                result = extension.send_asr_result.await_args.args[0]
                self.assertEqual(result.metadata["session_id"], "a")
                self.assertEqual(extension.metadata["session_id"], "b")
            finally:
                release_dump.set()
                await self.stop_consumer(extension, consumer, finalize)

    async def test_overlapping_finalize_keeps_each_arrival_boundary(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        recognizing, release = asyncio.Event(), asyncio.Event()
        sizes, acknowledgements = [], []

        async def recognize(_function, samples, _rate):
            sizes.append(samples.size)
            if len(sizes) == 1:
                recognizing.set()
                await release.wait()
            return "words"

        async def acknowledge():
            acknowledgements.append(
                (extension.finalize_id, extension.metadata["session_id"])
            )

        extension.send_asr_finalize_end.side_effect = acknowledge
        with patch.object(local.asyncio, "to_thread", new=recognize):
            consumer = asyncio.create_task(self.consumer(extension))
            requests = []
            try:
                extension.audio_frames_queue.put_nowait(self.frame("a"))
                requests.append(
                    asyncio.create_task(
                        extension.on_data(extension.ten_env, self.request("a"))
                    )
                )
                await asyncio.wait_for(recognizing.wait(), 0.2)
                extension.audio_frames_queue.put_nowait(self.frame("b"))
                requests.append(
                    asyncio.create_task(
                        extension.on_data(extension.ten_env, self.request("b"))
                    )
                )
                await asyncio.sleep(0)
                extension.audio_frames_queue.put_nowait(self.frame("c"))
                await asyncio.sleep(0)
                self.assertEqual(len(extension._pending_boundaries), 2)
                self.assertEqual(len(extension._utterance), 320)
                self.assertEqual(extension.metadata["session_id"], "b")
                release.set()
                await asyncio.wait_for(asyncio.gather(*requests), 0.2)
                await asyncio.sleep(0)
                self.assertEqual(sizes, [160, 160])
                self.assertEqual(len(extension._utterance), 320)
                self.assertEqual(extension.metadata["session_id"], "c")
                self.assertEqual(
                    acknowledgements, [("finalize-a", "a"), ("finalize-b", "b")]
                )
                self.assertEqual(
                    [
                        call.args[0].metadata["session_id"]
                        for call in extension.send_asr_result.await_args_list
                    ],
                    ["a", "b"],
                )
                self.assertFalse(extension._pending_boundaries)
            finally:
                release.set()
                await self.stop_consumer(extension, consumer, *requests)

    async def test_metadata_less_finalize_uses_last_drained_frame(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        extension.audio_frames_queue.put_nowait(self.frame("a"))
        request = self.request()
        request.get_property_to_json.return_value = ("", None)
        finalize = asyncio.create_task(
            extension.on_data(extension.ten_env, request)
        )
        await asyncio.sleep(0)
        extension.audio_frames_queue.put_nowait(self.frame("b"))
        consumer = asyncio.create_task(self.consumer(extension))
        try:
            await asyncio.wait_for(finalize, 0.2)
            self.assertEqual(
                extension.send_asr_result.await_args.args[0].metadata[
                    "session_id"
                ],
                "a",
            )
            self.assertEqual(extension.metadata["session_id"], "b")
        finally:
            await self.stop_consumer(extension, consumer, finalize)

    async def test_cancel_queued_request_releases_its_marker(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        await extension._finalize_request_lock.acquire()
        request = asyncio.create_task(
            extension.on_data(extension.ten_env, self.request())
        )
        await asyncio.sleep(0)
        boundary = next(iter(extension._pending_boundaries))
        request.cancel()
        await asyncio.gather(request, return_exceptions=True)
        extension._finalize_request_lock.release()
        self.assertTrue(boundary.release.is_set())
        self.assertFalse(extension._pending_boundaries)

    async def test_stuck_drain_times_out_and_later_finalize_completes(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        dumping, release_dump = asyncio.Event(), asyncio.Event()

        async def dump(_data):
            dumping.set()
            await release_dump.wait()

        async def handle(instance, _env, frame):
            await instance.send_audio(frame, instance.session_id)

        extension.audio_dumper = Mock(push_bytes=dump)
        with patch.object(
            Base, "_handle_audio_frame", new=handle, create=True
        ), patch.object(local, "FINALIZE_TIMEOUT_SECONDS", 0.02):
            consumer = asyncio.create_task(self.consumer(extension))
            finalize = None
            try:
                extension.audio_frames_queue.put_nowait(self.frame())
                await asyncio.wait_for(dumping.wait(), timeout=1)
                finalize = asyncio.create_task(
                    extension.on_data(extension.ten_env, self.request())
                )
                await asyncio.sleep(0)
                boundary = extension._active_boundary
                await asyncio.wait_for(finalize, 0.2)
                self.assertTrue(boundary.release.is_set())
                self.assertTrue(extension._init_failed)
                extension.send_asr_finalize_end.assert_awaited_once()
                await asyncio.wait_for(
                    extension.on_data(extension.ten_env, self.request("b")), 0.1
                )
                self.assertEqual(extension.send_asr_finalize_end.await_count, 2)
                release_dump.set()
                await asyncio.sleep(0)
                self.assertEqual(len(extension._utterance), 0)
            finally:
                release_dump.set()
                await self.stop_consumer(extension, consumer, finalize)

    async def test_stop_releases_a_queued_finalize_boundary(self):
        extension = self.new()
        extension.audio_frames_queue = asyncio.Queue()
        finalize = asyncio.create_task(
            extension.on_data(extension.ten_env, self.request())
        )
        await asyncio.sleep(0)
        boundary = extension._active_boundary
        extension.stopped = True
        await asyncio.wait_for(extension.stop_connection(), 0.1)
        await asyncio.wait_for(finalize, 0.1)
        self.assertTrue(boundary.release.is_set())
        extension.send_asr_finalize_end.assert_awaited_once()

    async def test_overflow_discards_one_turn_then_recovers(self):
        extension = self.new()
        self.assertEqual(local.MAX_UTTERANCE_BYTES, 10 * 1024 * 1024)
        with patch.object(local, "MAX_UTTERANCE_BYTES", 4):
            self.assertTrue(
                await extension.send_audio(self.frame(pcm=b"\0" * 4), "a")
            )
            self.assertFalse(
                await extension.send_audio(self.frame(pcm=b"\0" * 2), "a")
            )
            self.assertFalse(
                await extension.send_audio(self.frame(pcm=b"\0" * 2), "a")
            )
            self.assertEqual(len(extension._utterance), 0)
            self.assertEqual(extension.dropped_audio_frames, 2)
            self.assertEqual(
                [
                    call.args[0]
                    for call in extension.audio_timeline.add_dropped_audio.call_args_list
                ],
                [0.0625, 0.0625],
            )
            extension.send_asr_error.assert_awaited_once()
            self.assertEqual(
                extension.send_asr_error.await_args.args[1].code,
                "utterance_too_long",
            )
            await extension.finalize("a")
            extension.recognizer.recognize.assert_not_called()
            self.assertTrue(
                await extension.send_audio(self.frame("b", b"\0" * 2), "b")
            )
            await extension.finalize("b")
            extension.recognizer.recognize.assert_called_once()

    async def test_readiness_timeout_latches_and_next_finalize_is_immediate(
        self,
    ):
        extension = self.new()
        extension._loading = True
        with patch.object(local, "FINALIZE_TIMEOUT_SECONDS", 0.02):
            await asyncio.wait_for(extension.finalize("a"), 0.2)
            self.assertTrue(extension._init_failed)
            await asyncio.wait_for(extension.finalize("b"), 0.01)
        self.assertEqual(extension.send_asr_finalize_end.await_count, 2)

    async def test_inference_timeout_closes_without_waiting_for_native_lock(
        self,
    ):
        extension = self.new()
        entered, release = threading.Event(), threading.Event()

        def recognize(*_args, **_kwargs):
            entered.set()
            release.wait()
            return "late words"

        recognizer = local.OrukeetRecognizer(
            cache_dir=None, local_files_only=True
        )
        backend = Mock(recognize=recognize)
        recognizer._recognizer = backend
        extension.recognizer = recognizer
        extension._utterance.extend(b"\0\0" * 160)
        try:
            with patch.object(local, "FINALIZE_TIMEOUT_SECONDS", 0.03):
                await asyncio.wait_for(extension.finalize("a"), 0.3)
            self.assertTrue(entered.is_set())
            self.assertTrue(recognizer._closed)
            self.assertTrue(extension._init_failed)
            extension.send_asr_result.assert_not_called()
            extension.send_asr_finalize_end.assert_awaited_once()
            await asyncio.wait_for(extension.finalize("b"), 0.05)
            started = time.monotonic()
            await asyncio.wait_for(extension.stop_connection(), 0.05)
            self.assertLess(time.monotonic() - started, 0.05)
            self.assertEqual(extension.send_asr_finalize_end.await_count, 2)
        finally:
            release.set()
            await asyncio.sleep(0.02)
        self.assertIsNone(recognizer._recognizer)
        extension.send_asr_result.assert_not_called()

    async def test_stop_cancels_waiter_and_suppresses_native_result(self):
        extension = self.new()
        entered, release = threading.Event(), threading.Event()

        def recognize(*_args, **_kwargs):
            entered.set()
            release.wait()
            return "late words"

        recognizer = local.OrukeetRecognizer(
            cache_dir=None, local_files_only=True
        )
        recognizer._recognizer = Mock(recognize=recognize)
        extension.recognizer = recognizer
        extension._utterance.extend(b"\0\0" * 160)
        finalize = asyncio.create_task(extension.finalize("a"))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.001)
            self.assertTrue(entered.is_set())
            extension.stopped = True
            await asyncio.wait_for(extension.stop_connection(), 0.1)
            await asyncio.wait_for(finalize, 0.1)
            extension.send_asr_finalize_end.assert_awaited_once()
            extension.send_asr_result.assert_not_called()
        finally:
            release.set()
            await asyncio.sleep(0.02)
        self.assertIsNone(recognizer._recognizer)

    async def test_concurrent_finalize_requests_preserve_id_and_session(self):
        e = local.OrukASRExtension("test")
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

    async def test_disconnected_finalize_discards_only_its_startup_audio(self):
        extension = self.new()
        extension.recognizer = None
        extension._connected = False
        extension.config.cache_dir = None
        extension.config.local_files_only = True
        first = self.frame("a")
        extension.buffered_frames.put_nowait(first)
        extension.buffered_frames_size = len(first.get_buf())
        await extension.on_data(extension.ten_env, self.request("a"))
        extension.send_asr_finalize_end.assert_awaited_once()
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertEqual(extension.dropped_audio_frames, 1)
        extension.audio_timeline.add_dropped_audio.assert_called_once_with(10)

        second = self.frame("b", b"\0\0" * 80)
        extension.buffered_frames.put_nowait(second)
        extension.buffered_frames_size = len(second.get_buf())
        recognizer = Mock(
            loaded=True, recognize=Mock(return_value="second turn")
        )
        with patch.object(local, "OrukeetRecognizer", return_value=recognizer):
            await extension.start_connection()
        await extension.on_data(extension.ten_env, self.request("b"))
        self.assertEqual(recognizer.recognize.call_args.args[0].size, 80)
        self.assertEqual(
            extension.send_asr_result.await_args.args[0].metadata["session_id"],
            "b",
        )
        self.assertEqual(extension.send_asr_finalize_end.await_count, 2)

    async def test_generated_metadata_survives_base_shallow_merge(self):
        extension = self.new()
        original = {
            "session_id": "a",
            "trace": "caller",
            "asr_info": {"vendor": "input", "model": "input", "custom": "kept"},
        }
        extension.metadata = copy.deepcopy(original)
        extension.session_id = "a"
        extension._utterance.extend(b"\0\0" * 160)
        emitted, acknowledged = [], []

        async def emit(result):
            result.metadata.update(extension.metadata)
            emitted.append(copy.deepcopy(result.metadata))

        async def acknowledge():
            acknowledged.append(copy.deepcopy(extension.metadata))

        extension.send_asr_result.side_effect = emit
        extension.send_asr_finalize_end.side_effect = acknowledge
        await extension.finalize("a")
        self.assertEqual(
            emitted,
            [
                {
                    "session_id": "a",
                    "trace": "caller",
                    "asr_info": {
                        "vendor": "oruk",
                        "model": "orukeet",
                        "custom": "kept",
                    },
                }
            ],
        )
        self.assertEqual(acknowledged, [original])
        self.assertEqual(extension.metadata, original)

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
        e.buffered_frames_size = len(f.get_buf())
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
                    await asyncio.wait_for(entered.wait(), timeout=1)
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
            await asyncio.wait_for(entered.wait(), timeout=1)
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


if __name__ == "__main__":
    unittest.main()
