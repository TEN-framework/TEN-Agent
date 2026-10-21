"""Regressions through the installed TEN base and native emitted Data JSON."""

import asyncio
import copy
import json
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ten_ai_base import asr as native_base
from ten_ai_base.message import ModuleMetricKey
from ten_runtime import Data

from .. import extension as local_extension
from ..config import OrukASRConfig
from ..extension import OrukASRExtension


class NativeMetadataEmission(unittest.IsolatedAsyncioTestCase):
    def new(self):
        extension = OrukASRExtension("native-metadata-test")
        extension.config = OrukASRConfig.model_validate({})
        extension.ten_env = Mock(send_data=AsyncMock())
        return extension

    def emitted(self, extension, name):
        values = []
        for call in extension.ten_env.send_data.await_args_list:
            data = call.args[0]
            if data.get_name() == name:
                raw, error = data.get_property_to_json(None)
                self.assertIsNone(error)
                values.append(json.loads(raw))
        return values

    def request(self, session):
        request = Data.create("asr_finalize")
        request.set_property_from_json(
            None,
            json.dumps(
                {
                    "finalize_id": "finalize-" + session,
                    "metadata": {"session_id": session},
                }
            ),
        )
        return request

    def frame(self, session, byte_count=320):
        pcm = b"\0" * byte_count
        return Mock(
            get_buf=Mock(return_value=pcm),
            lock_buf=Mock(return_value=pcm),
            unlock_buf=Mock(),
            get_property_to_json=Mock(
                return_value=(json.dumps({"session_id": session}), None)
            ),
        )

    async def consume(self, extension, frames):
        boundary = local_extension._FinalizeBoundary()
        for frame in frames:
            extension.audio_frames_queue.put_nowait(frame)
        extension.audio_frames_queue.put_nowait(boundary)
        consumer = asyncio.create_task(extension._audio_frame_consumer())
        try:
            await asyncio.wait_for(boundary.ready.wait(), 1)
        finally:
            extension.stopped = True
            boundary.release.set()
            await asyncio.wait_for(consumer, 1)
            extension.stopped = False

    async def test_keep_eviction_preserves_native_recovery_timestamps(self):
        extension = self.new()
        extension.buffer_strategy = Mock(
            return_value=local_extension.ASRBufferConfigModeKeep(byte_limit=640)
        )
        await self.consume(extension, [self.frame(x) for x in ("a", "b", "c")])
        self.assertEqual(extension.buffered_frames_size, 640)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertEqual(
            extension.audio_timeline.get_total_user_audio_duration(), 10
        )
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="retained audio")
        )
        extension._connected = True
        await extension._flush_buffered_audio()
        self.assertEqual(extension.buffered_frames_size, 0)
        extension.finalize_id = "recovered"
        await asyncio.wait_for(extension.finalize("c"), 1)
        result = self.emitted(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (10, 20))
        self.assertEqual(
            extension.audio_timeline.get_total_user_audio_duration(), 30
        )

    async def test_oversize_keep_input_is_dropped_before_recovery(self):
        extension = self.new()
        extension.buffer_strategy = Mock(
            return_value=local_extension.ASRBufferConfigModeKeep(byte_limit=640)
        )
        await self.consume(
            extension, [self.frame("queued", 320), self.frame("large", 960)]
        )
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertEqual(extension.dropped_audio_frames, 2)
        await self.consume(extension, [self.frame("retained", 320)])
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="retained audio")
        )
        extension._connected = True
        await extension._flush_buffered_audio()
        extension.finalize_id = "recovered"
        await asyncio.wait_for(extension.finalize("retained"), 1)
        result = self.emitted(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (40, 10))
        self.assertEqual(extension.dropped_audio_frames, 2)

    async def test_oversize_during_flush_aborts_accepted_and_inflight_turn(
        self,
    ):
        extension = self.new()
        extension.buffer_strategy = Mock(
            return_value=local_extension.ASRBufferConfigModeKeep(byte_limit=960)
        )
        await self.consume(extension, [self.frame(x) for x in ("a", "b", "c")])
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="next valid turn")
        )
        extension._connected = True
        extension._flushing = True
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
            await self.consume(extension, [self.frame("invalid", 1280)])
            self.assertEqual(extension.buffered_frames_size, 0)
            self.assertTrue(extension._utterance_overflow)
            self.assertFalse(extension._utterance)
        finally:
            release.set()
            await asyncio.wait_for(flushing, 1)
        extension._flushing = False
        extension.finalize_id = "invalid-turn"
        await asyncio.wait_for(extension.finalize("invalid"), 1)
        self.assertEqual(self.emitted(extension, "asr_result"), [])
        self.assertEqual(len(self.emitted(extension, "error")), 1)
        self.assertEqual(extension.dropped_audio_frames, 3)
        await self.consume(extension, [self.frame("next")])
        extension.finalize_id = "next-turn"
        await asyncio.wait_for(extension.finalize("next"), 1)
        result = self.emitted(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (70, 10))
        self.assertEqual(len(self.emitted(extension, "asr_finalize_end")), 2)

    async def test_arrival_during_native_flush_uses_freed_capacity(self):
        extension = self.new()
        extension.buffer_strategy = Mock(
            return_value=local_extension.ASRBufferConfigModeKeep(byte_limit=640)
        )
        await self.consume(extension, [self.frame("a"), self.frame("b")])
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="all three frames")
        )
        extension._connected = True
        extension._flushing = True
        entered, release = asyncio.Event(), asyncio.Event()

        async def dump(pcm):
            if not entered.is_set():
                entered.set()
                await release.wait()

        extension.audio_dumper = Mock(push_bytes=dump)
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertEqual(extension.buffered_frames_size, 320)
            await self.consume(extension, [self.frame("c")])
            self.assertEqual(extension.buffered_frames_size, 640)
            self.assertEqual(extension.dropped_audio_frames, 0)
        finally:
            release.set()
            await asyncio.wait_for(flushing, 1)
        extension._flushing = False
        self.assertEqual(extension.buffered_frames_size, 0)
        extension.finalize_id = "complete"
        await asyncio.wait_for(extension.finalize("c"), 1)
        result = self.emitted(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (0, 30))
        self.assertEqual(extension.dropped_audio_frames, 0)

    async def test_connected_partial_finalize_metadata_keeps_session(self):
        for supplied in ({}, {"request_tag": "x"}, {"session_id": "override"}):
            with self.subTest(supplied=supplied):
                extension = self.new()
                extension.recognizer = Mock(
                    loaded=True, recognize=Mock(return_value="spoken words")
                )
                extension._connected = True
                await self.consume(extension, [self.frame("audio-session")])
                request = Data.create("asr_finalize")
                request.set_property_from_json(
                    None,
                    json.dumps(
                        {"finalize_id": "request", "metadata": supplied}
                    ),
                )
                pending = asyncio.create_task(
                    extension.on_data(extension.ten_env, request)
                )
                boundary = await asyncio.wait_for(
                    extension.audio_frames_queue.get(), 1
                )
                consumer = asyncio.create_task(
                    extension._handle_audio_frame(extension.ten_env, boundary)
                )
                try:
                    await asyncio.wait_for(pending, 1)
                finally:
                    boundary.release.set()
                    await asyncio.wait_for(consumer, 1)
                expected = {"session_id": "audio-session", **supplied}
                result = self.emitted(extension, "asr_result")[0]
                self.assertEqual(
                    {key: result["metadata"][key] for key in expected}, expected
                )
                self.assertEqual(
                    self.emitted(extension, "asr_finalize_end"),
                    [{"finalize_id": "request", "metadata": expected}],
                )
                ttlw = [
                    item
                    for item in self.emitted(extension, "metrics")
                    if ModuleMetricKey.ASR_TTLW in item["metrics"]
                ]
                self.assertEqual(len(ttlw), 1)
                self.assertEqual(
                    ttlw[0]["metadata"]["session_id"], expected["session_id"]
                )

    async def test_startup_partial_finalize_metadata_uses_drained_audio(self):
        for supplied in (
            None,
            {},
            {"request_tag": "x"},
            {"session_id": "override"},
        ):
            with self.subTest(supplied=supplied):
                extension = self.new()
                extension.metadata = {"session_id": "previous-a"}
                extension.session_id = "previous-a"
                extension.recognizer = Mock(
                    loaded=True, recognize=Mock(return_value="startup words")
                )
                extension._loading = True
                extension._flushing = True
                extension._ready_event.clear()
                await self.consume(extension, [self.frame("audio-b")])
                request = Data.create("asr_finalize")
                payload = {"finalize_id": "startup-request"}
                if supplied is not None:
                    payload["metadata"] = supplied
                request.set_property_from_json(None, json.dumps(payload))
                pending = asyncio.create_task(
                    extension.on_data(extension.ten_env, request)
                )
                boundary = await asyncio.wait_for(
                    extension.audio_frames_queue.get(), 1
                )
                consumer = asyncio.create_task(
                    extension._handle_audio_frame(extension.ten_env, boundary)
                )
                try:
                    await asyncio.wait_for(boundary.ready.wait(), 1)
                    await extension._flush_buffered_audio()
                    extension._loading = False
                    extension._flushing = False
                    extension._connected = True
                    extension._ready_event.set()
                    await asyncio.wait_for(pending, 1)
                finally:
                    boundary.release.set()
                    await asyncio.wait_for(consumer, 1)
                expected = {"session_id": "audio-b", **(supplied or {})}
                result = self.emitted(extension, "asr_result")[0]
                self.assertEqual(
                    {key: result["metadata"][key] for key in expected}, expected
                )
                self.assertEqual(
                    self.emitted(extension, "asr_finalize_end"),
                    [{"finalize_id": "startup-request", "metadata": expected}],
                )
                ttlw = [
                    item
                    for item in self.emitted(extension, "metrics")
                    if ModuleMetricKey.ASR_TTLW in item["metrics"]
                ]
                self.assertEqual(len(ttlw), 1)
                self.assertEqual(
                    ttlw[0]["metadata"]["session_id"], expected["session_id"]
                )

    async def test_eviction_during_flush_preserves_start_and_elapsed_span(self):
        for blocked_call, sizes in (
            (1, (32000, 32000)),
            (2, (16000, 16000, 32000)),
        ):
            with self.subTest(blocked_call=blocked_call):
                extension = self.new()
                extension.buffer_strategy = Mock(
                    return_value=local_extension.ASRBufferConfigModeKeep(
                        byte_limit=64000
                    )
                )
                await self.consume(
                    extension, [self.frame("a", size) for size in sizes]
                )
                extension.recognizer = Mock(
                    loaded=True, recognize=Mock(return_value="retained words")
                )
                extension._connected = True
                extension._flushing = True
                entered, release = asyncio.Event(), asyncio.Event()
                calls = 0

                async def dump(pcm):
                    nonlocal calls
                    calls += 1
                    if calls == blocked_call:
                        entered.set()
                        await release.wait()

                extension.audio_dumper = Mock(push_bytes=dump)
                flushing = asyncio.create_task(
                    extension._flush_buffered_audio()
                )
                try:
                    await asyncio.wait_for(entered.wait(), 1)
                    await self.consume(extension, [self.frame("a", 64000)])
                finally:
                    release.set()
                    await asyncio.wait_for(flushing, 1)
                extension._flushing = False
                extension.finalize_id = "retained-turn"
                await asyncio.wait_for(extension.finalize("a"), 1)
                result = self.emitted(extension, "asr_result")[0]
                self.assertEqual(
                    (result["start_ms"], result["duration_ms"]), (0, 4000)
                )
                self.assertEqual(extension.dropped_audio_frames, 1)
                self.assertEqual(
                    extension.audio_timeline.get_total_user_audio_duration(),
                    4000,
                )
                await self.consume(extension, [self.frame("next", 16000)])
                extension.finalize_id = "next-turn"
                await asyncio.wait_for(extension.finalize("next"), 1)
                result = self.emitted(extension, "asr_result")[1]
                self.assertEqual(
                    (result["start_ms"], result["duration_ms"]), (4000, 500)
                )

    async def test_native_start_and_stop_finish_while_prewarm_is_stalled(self):
        for mode in ("startup", "readiness"):
            with self.subTest(mode=mode):
                extension = self.new()
                model = local_extension.OrukeetRecognizer(
                    cache_dir=None, local_files_only=True
                )
                extension.recognizer = model
                release, entered, finished = (
                    threading.Event(),
                    threading.Event(),
                    threading.Event(),
                )
                original = model.prewarm

                def load():
                    entered.set()
                    release.wait()
                    model._recognizer = object()

                def prewarm():
                    try:
                        original()
                    finally:
                        finished.set()

                with (
                    patch.object(
                        native_base, "send_provide_features", new=AsyncMock()
                    ),
                    patch.object(model, "_load", side_effect=load),
                    patch.object(model, "prewarm", side_effect=prewarm),
                    patch.object(
                        local_extension,
                        "MODEL_START_TIMEOUT_SECONDS",
                        0.02 if mode == "startup" else 2,
                    ),
                    patch.object(
                        local_extension, "FINALIZE_TIMEOUT_SECONDS", 0.02
                    ),
                ):
                    pending = asyncio.create_task(
                        extension.on_start(extension.ten_env)
                    )
                    try:
                        self.assertTrue(
                            await asyncio.to_thread(entered.wait, 0.5)
                        )
                        if mode == "readiness":
                            await asyncio.wait_for(
                                extension.finalize(None), 0.5
                            )
                        await asyncio.wait_for(pending, 0.5)
                        self.assertFalse(finished.is_set())
                        self.assertTrue(extension._init_failed)
                        self.assertIsNone(extension.recognizer)
                        self.assertIsNone(extension._prewarm_task)
                        self.assertTrue(model._closed)
                        await asyncio.wait_for(
                            extension.on_stop(extension.ten_env), 0.5
                        )
                    finally:
                        release.set()
                        self.assertTrue(
                            await asyncio.to_thread(finished.wait, 0.5)
                        )
                        if not pending.done():
                            await asyncio.wait_for(pending, 0.5)
                self.assertFalse(extension.is_connected())
                self.assertIsNone(model._recognizer)
                errors = self.emitted(extension, "error")
                self.assertEqual(len(errors), 1)
                self.assertEqual(
                    errors[0]["vendor_info"]["code"],
                    (
                        "model_load_timeout"
                        if mode == "startup"
                        else "readiness_timeout"
                    ),
                )
                self.assertEqual(self.emitted(extension, "asr_result"), [])
                self.assertNotIn(
                    "connected",
                    [
                        item["current"]
                        for item in self.emitted(
                            extension, "connection_status_changed"
                        )
                    ],
                )

    async def test_repeated_pretrigger_finalize_resolves_each_buffer_session(
        self,
    ):
        extension = self.new()
        extension.auto_connect = False
        cases = (
            ("a", None),
            ("b", None),
            ("c", {"request_tag": "x"}),
            ("d", {"session_id": "override"}),
        )
        for session, supplied in cases:
            await self.consume(extension, [self.frame(session)])
            request = Data.create("asr_finalize")
            payload = {"finalize_id": "finalize-" + session}
            if supplied is not None:
                payload["metadata"] = supplied
            request.set_property_from_json(None, json.dumps(payload))
            pending = asyncio.create_task(
                extension.on_data(extension.ten_env, request)
            )
            boundary = await asyncio.wait_for(
                extension.audio_frames_queue.get(), 1
            )
            consumer = asyncio.create_task(
                extension._handle_audio_frame(extension.ten_env, boundary)
            )
            try:
                await asyncio.wait_for(pending, 1)
            finally:
                boundary.release.set()
                await asyncio.wait_for(consumer, 1)
        expected = [
            {"session_id": session, **(supplied or {})}
            for session, supplied in cases
        ]
        acks = self.emitted(extension, "asr_finalize_end")
        self.assertEqual([item["metadata"] for item in acks], expected)
        self.assertEqual(
            [item["finalize_id"] for item in acks],
            ["finalize-" + session for session, _ in cases],
        )
        self.assertEqual(extension.dropped_audio_frames, 4)
        self.assertEqual(
            extension.audio_timeline.get_total_user_audio_duration(), 40
        )
        self.assertEqual(self.emitted(extension, "asr_result"), [])
        self.assertIsNone(extension.recognizer)

    async def test_result_keeps_generated_fields_and_ack_echoes_input(self):
        extension = self.new()
        original = {
            "session_id": "session-a",
            "trace": "caller-trace",
            "asr_info": {
                "vendor": "caller-vendor",
                "model": "caller-model",
                "custom": "preserved",
            },
        }
        extension.metadata = copy.deepcopy(original)
        extension.session_id = "session-a"
        extension.finalize_id = "finalize-a"
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="hello")
        )
        extension._connected = True
        extension._utterance.extend(b"\0\0" * 160)
        await asyncio.wait_for(extension.finalize("session-a"), timeout=1)
        results = self.emitted(extension, "asr_result")
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["metadata"],
            {
                "session_id": "session-a",
                "trace": "caller-trace",
                "asr_info": {
                    "vendor": "oruk",
                    "model": "orukeet",
                    "custom": "preserved",
                },
            },
        )
        self.assertEqual(
            self.emitted(extension, "asr_finalize_end"),
            [
                {
                    "finalize_id": "finalize-a",
                    "metadata": original,
                }
            ],
        )
        self.assertEqual(extension.metadata, original)

    async def test_overflow_preserves_rejected_input_in_native_timeline(self):
        extension = self.new()
        extension.recognizer = Mock(
            loaded=True, recognize=Mock(return_value="next turn")
        )
        extension._connected = True

        def frame(session, byte_count):
            pcm = b"\0" * byte_count
            return Mock(
                get_buf=Mock(return_value=pcm),
                lock_buf=Mock(return_value=pcm),
                unlock_buf=Mock(),
                get_property_to_json=Mock(
                    return_value=(json.dumps({"session_id": session}), None)
                ),
            )

        with patch.object(local_extension, "MAX_UTTERANCE_BYTES", 320):
            # Native base accepts 10 ms, then rejects the triggering 5 ms and
            # another 10 ms until finalize. Their input offset must survive.
            for byte_count in (320, 160, 320):
                await extension._handle_audio_frame(
                    extension.ten_env, frame("a", byte_count)
                )
            self.assertEqual(extension.dropped_audio_frames, 2)
            self.assertEqual(
                extension.audio_timeline.get_total_user_audio_duration(), 25
            )
            self.assertEqual(len(self.emitted(extension, "error")), 1)
            extension.finalize_id = "overflow-a"
            await asyncio.wait_for(extension.finalize("a"), timeout=1)
            self.assertEqual(self.emitted(extension, "asr_result"), [])

            await extension._handle_audio_frame(
                extension.ten_env, frame("b", 320)
            )
            extension.finalize_id = "next-b"
            await asyncio.wait_for(extension.finalize("b"), timeout=1)
        results = self.emitted(extension, "asr_result")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["start_ms"], 25)
        self.assertEqual(results[0]["duration_ms"], 10)
        self.assertEqual(results[0]["metadata"]["session_id"], "b")
        self.assertEqual(len(self.emitted(extension, "asr_finalize_end")), 2)

    async def test_disconnected_finalize_before_trigger_connect_drops_old_turn(
        self,
    ):
        extension = self.new()
        extension.auto_connect = False
        stop_consumer = object()
        second_buffered = asyncio.Event()
        model = Mock(loaded=True, recognize=Mock(return_value="second turn"))

        def frame(session, samples):
            pcm = b"\0\0" * samples
            return Mock(
                get_buf=Mock(return_value=pcm),
                lock_buf=Mock(return_value=pcm),
                unlock_buf=Mock(),
                get_property_to_json=Mock(
                    return_value=(json.dumps({"session_id": session}), None)
                ),
            )

        second = frame("b", 80)

        async def consume():
            while True:
                item = await extension.audio_frames_queue.get()
                if item is stop_consumer:
                    return
                await extension._handle_audio_frame(extension.ten_env, item)
                if item is second:
                    second_buffered.set()

        consumer = asyncio.create_task(consume())
        try:
            await extension.on_audio_frame(extension.ten_env, frame("a", 160))
            await asyncio.wait_for(
                extension.on_data(extension.ten_env, self.request("a")),
                timeout=1,
            )
            self.assertTrue(extension.buffered_frames.empty())
            self.assertEqual(extension.dropped_audio_frames, 1)
            self.assertIsNone(extension.recognizer)
            self.assertEqual(
                self.emitted(extension, "asr_finalize_end"),
                [
                    {
                        "finalize_id": "finalize-a",
                        "metadata": {"session_id": "a"},
                    }
                ],
            )

            await extension.on_audio_frame(extension.ten_env, second)
            await asyncio.wait_for(second_buffered.wait(), timeout=1)
            with patch.object(
                local_extension,
                "OrukeetRecognizer",
                return_value=model,
            ):
                await asyncio.wait_for(
                    extension.on_data(
                        extension.ten_env, Data.create("trigger_connect")
                    ),
                    timeout=1,
                )
            await asyncio.wait_for(
                extension.on_data(extension.ten_env, self.request("b")),
                timeout=1,
            )
            self.assertEqual(model.recognize.call_args.args[0].size, 80)
            results = self.emitted(extension, "asr_result")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["metadata"]["session_id"], "b")
            self.assertEqual(results[0]["start_ms"], 10)
            self.assertEqual(
                len(self.emitted(extension, "asr_finalize_end")), 2
            )
        finally:
            extension.stopped = True
            await extension.stop_connection()
            extension.audio_frames_queue.put_nowait(stop_consumer)
            await asyncio.wait_for(consumer, timeout=1)
