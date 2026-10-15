"""Regression tests using the installed TEN helpers and actual Data JSON."""

import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ten_ai_base.message import ModuleMetricKey
from ten_runtime import Data

from .. import extension as module
from ..config import OrukRealtimeASRConfig
from ..const import MODEL
from ..extension import OrukRealtimeASRExtension, _TurnCallback


class MetadataEmission(unittest.IsolatedAsyncioTestCase):
    def new_extension(self):
        extension = OrukRealtimeASRExtension("native-metadata-test")
        extension.config = OrukRealtimeASRConfig(params={"api_key": "test-key"})
        extension.ten_env = Mock(send_data=AsyncMock())
        extension._connect_started = asyncio.get_running_loop().time()
        return extension

    def outputs(self, extension, name):
        return [
            json.loads(call.args[0].get_property_to_json(None)[0])
            for call in extension.ten_env.send_data.await_args_list
            if call.args[0].get_name() == name
        ]

    async def test_reconnect_preserves_request_and_generated_metadata(self):
        extension = self.new_extension()
        request_metadata = {
            "session_id": "finalize-session",
            "request": "request-marker",
            "asr_info": {
                "caller_tag": "keep-me",
                "vendor": "caller-vendor",
                "model": "caller-model",
                "phrases": ["caller-phrases"],
            },
        }
        audio_metadata = {
            "session_id": "audio-session",
            "frame": "frame-marker",
        }
        phrase = {"phrase_id": "phrase-1", "emotion": "interested"}
        frame = Mock(
            get_buf=Mock(return_value=b"\0\0" * 160),
            lock_buf=Mock(return_value=b"\0\0" * 160),
            get_property_to_json=Mock(
                return_value=(json.dumps(audio_metadata), None)
            ),
        )
        extension.buffered_frames.put_nowait(frame)
        original_request = copy.deepcopy(request_metadata)
        request = Data.create("asr_finalize")
        request.set_property_from_json(
            None,
            json.dumps(
                {"finalize_id": "finalize-42", "metadata": request_metadata}
            ),
        )

        async def commit():
            extension._phrases = [phrase]
            await extension.on_final("The buffered transcript.")
            await extension.on_usage({"audio_seconds": 0.01})
            await extension.on_error("diagnostic", "test_vendor_code", False)

        connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(),
            commit=AsyncMock(side_effect=commit),
        )

        async def reopen():
            extension._generation += 1
            extension._reset_turn()
            extension._flushing = True
            extension.connection = connection
            await extension.on_open()

        extension._reopen = AsyncMock(side_effect=reopen)
        pending = asyncio.create_task(
            extension.on_data(extension.ten_env, request)
        )
        boundary = await asyncio.wait_for(extension.audio_frames_queue.get(), 1)
        consumer = asyncio.create_task(
            extension._handle_audio_frame(extension.ten_env, boundary)
        )
        await asyncio.wait_for(pending, 1)
        await asyncio.wait_for(consumer, 1)
        await extension._reconnect_task

        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(result["metadata"]["session_id"], "finalize-session")
        self.assertEqual(result["metadata"]["request"], "request-marker")
        self.assertEqual(
            result["metadata"]["asr_info"],
            {
                "caller_tag": "keep-me",
                "vendor": "oruk",
                "model": MODEL,
                "phrases": [phrase],
            },
        )
        self.assertEqual(
            self.outputs(extension, "asr_finalize_end"),
            [{"finalize_id": "finalize-42", "metadata": original_request}],
        )
        metrics = self.outputs(extension, "metrics")
        attributed = [
            item
            for item in metrics
            if ModuleMetricKey.ASR_TTLW in item["metrics"]
            or ModuleMetricKey.ASR_VENDOR_METRICS in item["metrics"]
        ]
        self.assertEqual(len(attributed), 2)
        self.assertTrue(
            all(
                item["metadata"]["session_id"] == "finalize-session"
                for item in attributed
            )
        )
        error = self.outputs(extension, "error")[0]
        self.assertEqual(error["metadata"]["session_id"], "finalize-session")
        self.assertEqual(request_metadata, original_request)
        self.assertEqual(extension.metadata, audio_metadata)

    async def test_interim_native_merge_preserves_root_and_nested_fields(self):
        extension = self.new_extension()
        supplied = {
            "session_id": "session-a",
            "root_tag": "keep",
            "asr_info": {"nested_tag": "keep", "vendor": "wrong"},
        }
        extension.metadata = copy.deepcopy(supplied)
        extension.session_id = "session-a"
        await extension.on_interim("hello")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            result["metadata"],
            {
                "session_id": "session-a",
                "root_tag": "keep",
                "asr_info": {
                    "nested_tag": "keep",
                    "vendor": "oruk",
                    "model": MODEL,
                },
            },
        )
        self.assertEqual(extension.metadata, supplied)

    async def test_commit_failure_emits_error_ack_and_continuous_timeline(self):
        extension = self.new_extension()
        extension.metadata = {"session_id": "failed-session"}
        extension.session_id = "failed-session"
        extension.finalize_id = "failed-finalize"
        extension._turn_bytes = 32000
        callback = _TurnCallback(extension, extension._generation)
        connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=OSError("commit write failed")),
            close=AsyncMock(),
        )
        extension.connection = connection
        extension._schedule_reconnect = Mock()
        await extension.finalize("failed-session")
        connection.close.assert_awaited_once()
        extension._schedule_reconnect.assert_called_once()
        error = self.outputs(extension, "error")[0]
        self.assertEqual(error["vendor_info"]["code"], "finalize_failed")
        self.assertEqual(error["metadata"]["session_id"], "failed-session")
        self.assertEqual(
            self.outputs(extension, "asr_finalize_end"),
            [
                {
                    "finalize_id": "failed-finalize",
                    "metadata": {"session_id": "failed-session"},
                }
            ],
        )
        await callback.on_close(1000, "late")
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (1000, 500)
        )

    async def test_timeout_advances_native_result_offset_once(self):
        extension = self.new_extension()
        extension.metadata = {"session_id": "session-a"}
        extension.session_id = "session-a"
        extension.finalize_id = "timed-out-finalize"
        extension._turn_bytes = 32000
        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(),
            close=AsyncMock(),
        )
        callback = _TurnCallback(extension, extension._generation)
        extension._schedule_reconnect = Mock()
        with patch.object(module, "IO_TIMEOUT_SECONDS", 0.001):
            await extension.finalize("session-a")
        await callback.on_close(1000, "late")
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (1000, 500)
        )
        self.assertEqual(extension._emitted_ms, 1500)
        self.assertEqual(len(self.outputs(extension, "asr_finalize_end")), 1)

    async def test_remote_close_waits_for_successful_send_before_next_result(
        self,
    ):
        extension = self.new_extension()
        extension.metadata = {"session_id": "session-a"}
        extension.session_id = "session-a"
        extension._turn_bytes = 32000
        extension._schedule_reconnect = Mock()
        written, release = asyncio.Event(), asyncio.Event()

        async def write(_pcm):
            written.set()
            await release.wait()

        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=write),
        )
        frame = Mock(
            get_property_to_json=Mock(return_value=("", None)),
            lock_buf=Mock(return_value=b"\0" * 16000),
        )
        pending = asyncio.create_task(extension.send_audio(frame, "session-a"))
        await asyncio.wait_for(written.wait(), 1)
        await _TurnCallback(extension, extension._generation).on_close(
            1006, "remote close"
        )
        retiring = tuple(extension._remote_close_tasks)
        self.assertFalse(extension._turn_accounted)
        release.set()
        self.assertTrue(await asyncio.wait_for(pending, 1))
        await asyncio.wait_for(asyncio.gather(*retiring), 1)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (1500, 500)
        )
        self.assertEqual(result["metadata"]["session_id"], "session-a")
        self.assertEqual(extension._emitted_ms, 2000)

    async def test_buffered_timeout_keeps_native_timeline_continuous(self):
        for accepted_bytes in (0, 32000):
            with self.subTest(accepted_bytes=accepted_bytes):
                extension = self.new_extension()
                extension.metadata = {"session_id": "buffered-session"}
                extension.session_id = "buffered-session"
                extension.finalize_id = "buffered-finalize"
                extension._turn_bytes = accepted_bytes
                extension.connection = Mock(
                    is_connected=Mock(return_value=False), close=AsyncMock()
                )
                extension._flushing = True
                extension._schedule_reconnect = Mock()
                extension.buffered_frames.put_nowait(
                    Mock(get_buf=Mock(return_value=b"\0" * 32000))
                )
                callback = _TurnCallback(extension, extension._generation)
                timeline = extension.audio_timeline
                with (
                    patch.object(module, "IO_TIMEOUT_SECONDS", 0.001),
                    patch.object(
                        timeline,
                        "add_dropped_audio",
                        wraps=timeline.add_dropped_audio,
                    ) as dropped,
                ):
                    await extension.finalize("buffered-session")
                dropped.assert_called_once_with(1000.0)
                self.assertEqual(extension.dropped_audio_frames, 1)
                self.assertTrue(extension.buffered_frames.empty())
                await callback.on_close(1000, "late")
                await callback.on_final("late transcript")
                extension._reset_turn()
                extension._turn_bytes = 16000
                await extension.on_final("next turn")
                results = self.outputs(extension, "asr_result")
                self.assertEqual(len(results), 1)
                expected_start = 1000 + accepted_bytes // 32
                self.assertEqual(
                    (results[0]["start_ms"], results[0]["duration_ms"]),
                    (expected_start, 500),
                )
                self.assertEqual(extension._emitted_ms, expected_start + 500)
                self.assertEqual(
                    self.outputs(extension, "asr_finalize_end"),
                    [
                        {
                            "finalize_id": "buffered-finalize",
                            "metadata": {"session_id": "buffered-session"},
                        }
                    ],
                )

    async def test_partial_drops_accumulate_before_integer_result_offset(self):
        extension = self.new_extension()
        for byte_count in (304, 16):
            extension.buffered_frames.put_nowait(
                Mock(get_buf=Mock(return_value=b"\0" * byte_count))
            )
            extension._discard_buffered_audio()
        extension._turn_bytes = 16000
        await extension.on_final("after partial frames")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(result["start_ms"], 10)
        self.assertIsInstance(result["start_ms"], int)
        self.assertEqual(result["duration_ms"], 500)
        self.assertEqual(extension.dropped_audio_frames, 2)

    async def test_replacement_keeps_original_finalize_ack_metadata(self):
        extension = self.new_extension()
        request_metadata = {
            "session_id": "finalize-a",
            "request_tag": "original",
        }
        extension.metadata = copy.deepcopy(request_metadata)
        extension.session_id = "finalize-a"
        extension.finalize_id = "request-a"
        entered, release = asyncio.Event(), asyncio.Event()

        async def emit(data):
            if data.get_name() == "error":
                entered.set()
                await release.wait()

        extension.ten_env.send_data.side_effect = emit
        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            commit=AsyncMock(side_effect=OSError("broken commit")),
            close=AsyncMock(),
        )
        pending = asyncio.create_task(extension.finalize("finalize-a"))
        await asyncio.wait_for(entered.wait(), 1)
        extension._generation += 1
        extension._reset_turn()
        extension.metadata = {"session_id": "audio-b"}
        extension.session_id = "audio-b"
        replacement = Mock(close=AsyncMock())
        extension.connection = replacement
        release.set()
        await asyncio.wait_for(pending, 1)
        self.assertIs(extension.connection, replacement)
        replacement.close.assert_not_called()
        self.assertEqual(
            self.outputs(extension, "asr_finalize_end"),
            [{"finalize_id": "request-a", "metadata": request_metadata}],
        )
        self.assertEqual(extension.metadata, {"session_id": "audio-b"})

    async def test_native_consumer_counts_failed_live_frame_once(self):
        extension = self.new_extension()
        extension._schedule_reconnect = Mock()
        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError("write failed")),
            close=AsyncMock(),
        )
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            lock_buf=Mock(return_value=b"\0" * 32000),
            get_property_to_json=Mock(
                return_value=(json.dumps({"session_id": "live-session"}), None)
            ),
        )
        boundary = module._FinalizeBoundary()
        extension.audio_frames_queue.put_nowait(frame)
        extension.audio_frames_queue.put_nowait(boundary)
        consumer = asyncio.create_task(extension._audio_frame_consumer())
        timeline = extension.audio_timeline
        with patch.object(
            timeline, "add_dropped_audio", wraps=timeline.add_dropped_audio
        ) as dropped:
            try:
                await asyncio.wait_for(boundary.ready.wait(), 1)
            finally:
                extension.stopped = True
                boundary.release.set()
                await asyncio.wait_for(consumer, 1)
        dropped.assert_called_once_with(1000.0)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertEqual(extension._emitted_ms, 1000)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next successful turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (1000, 500)
        )

    async def test_failed_buffered_frame_retried_without_drop(self):
        extension = self.new_extension()
        extension._schedule_reconnect = Mock()
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            lock_buf=Mock(return_value=b"\0" * 32000),
        )
        extension.buffered_frames.put_nowait(frame)
        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError("write failed")),
            close=AsyncMock(),
        )
        with self.assertRaises(ConnectionError):
            await extension._flush_buffered_audio()
        self.assertEqual(extension.buffered_frames.qsize(), 1)
        self.assertEqual(extension.dropped_audio_frames, 0)
        extension._reset_turn()
        extension.connection = Mock(
            is_connected=Mock(return_value=True), send_pcm=AsyncMock()
        )
        await extension._flush_buffered_audio()
        await extension.on_final("successfully retried")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (0, 1000))
        self.assertEqual(extension.dropped_audio_frames, 0)

    async def test_native_consumer_eviction_preserves_timeline(self):
        extension = self.new_extension()
        extension.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=32000)
        )
        frames = [
            Mock(
                get_buf=Mock(return_value=b"\0" * size),
                lock_buf=Mock(return_value=b"\0" * size),
                get_property_to_json=Mock(
                    return_value=(
                        json.dumps({"session_id": "buffered-session"}),
                        None,
                    )
                ),
            )
            for size in (32000, 16000)
        ]
        boundary = module._FinalizeBoundary()
        for frame in frames:
            extension.audio_frames_queue.put_nowait(frame)
        extension.audio_frames_queue.put_nowait(boundary)
        consumer = asyncio.create_task(extension._audio_frame_consumer())
        timeline = extension.audio_timeline
        with patch.object(
            timeline, "add_dropped_audio", wraps=timeline.add_dropped_audio
        ) as dropped:
            try:
                await asyncio.wait_for(boundary.ready.wait(), 1)
                self.assertEqual(extension.buffered_frames_size, 16000)
                self.assertEqual(extension.buffered_frames.qsize(), 1)
                extension.connection = Mock(
                    is_connected=Mock(return_value=True), send_pcm=AsyncMock()
                )
                await extension._flush_buffered_audio()
                await extension.on_final("retained audio")
            finally:
                extension.stopped = True
                boundary.release.set()
                await asyncio.wait_for(consumer, 1)
        dropped.assert_called_once_with(1000.0)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertEqual(extension.buffered_frames_size, 0)
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (1000, 500)
        )

    async def test_oversize_frame_discards_affected_buffered_turn(self):
        extension = self.new_extension()
        extension._schedule_reconnect = Mock()
        extension.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=32000)
        )
        retained = Mock(get_buf=Mock(return_value=b"\0" * 16000))
        oversized = Mock(get_buf=Mock(return_value=b"\0" * 64000))
        await extension._handle_audio_frame(extension.ten_env, retained)
        await extension._handle_audio_frame(extension.ten_env, oversized)
        self.assertEqual(extension.buffered_frames_size, 0)
        self.assertTrue(extension.buffered_frames.empty())
        self.assertEqual(extension.dropped_audio_frames, 2)
        self.assertEqual(extension._emitted_ms, 2500)
        error = self.outputs(extension, "error")[0]
        self.assertEqual(error["vendor_info"]["code"], "audio_frame_too_large")
        self.assertEqual(len(self.outputs(extension, "error")), 1)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (2500, 500)
        )

    async def test_oversize_during_flush_aborts_partial_turn(self):
        extension = self.new_extension()
        extension._schedule_reconnect = Mock()
        extension.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=32000)
        )
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            lock_buf=Mock(return_value=b"\0" * 32000),
        )
        await extension._handle_audio_frame(extension.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(_audio):
            entered.set()
            await release.wait()

        old = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=send),
            close=AsyncMock(),
        )
        extension.connection = old
        extension._flushing = True
        callback = _TurnCallback(extension, extension._generation)
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        oversized = Mock(get_buf=Mock(return_value=b"\0" * 64000))
        abort = asyncio.create_task(
            extension._handle_audio_frame(extension.ten_env, oversized)
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.gather(flushing, abort), 1)
        old.close.assert_awaited_once()
        await callback.on_final("late partial transcript")
        self.assertEqual(self.outputs(extension, "asr_result"), [])
        self.assertEqual(extension._emitted_ms, 3000)
        self.assertEqual(extension.dropped_audio_frames, 1)
        self.assertEqual(len(self.outputs(extension, "error")), 1)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (3000, 500)
        )

    async def test_old_close_ack_cannot_emit_replacement_disconnected(self):
        extension = self.new_extension()
        extension.finalize_id = "old-finalize"
        extension._finalize_pending = True
        extension._schedule_reconnect = Mock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def emit(data):
            if data.get_name() == "asr_finalize_end":
                entered.set()
                await release.wait()

        extension.ten_env.send_data.side_effect = emit
        callback = _TurnCallback(extension, extension._generation)
        pending = asyncio.create_task(callback.on_close(1000, "old closed"))
        await asyncio.wait_for(entered.wait(), 1)
        extension._generation += 1
        extension._reset_turn()
        replacement = Mock(is_connected=Mock(return_value=True))
        extension.connection = replacement
        await extension.on_connected()
        release.set()
        await asyncio.wait_for(pending, 1)
        self.assertIs(extension.connection, replacement)
        statuses = self.outputs(extension, "connection_status_changed")
        self.assertEqual([item["current"] for item in statuses], ["connected"])
        extension._schedule_reconnect.assert_not_called()

    async def test_finalize_inherits_buffered_audio_unless_session_explicit(
        self,
    ):
        for supplied in (
            None,
            {"request_tag": "x"},
            {"session_id": "override", "request_tag": "x"},
        ):
            with self.subTest(metadata=supplied):
                extension = self.new_extension()
                extension.metadata = {"session_id": "session-a"}
                extension.session_id = "session-a"
                audio_metadata = {"session_id": "session-b", "frame_tag": "b"}
                frame = Mock(
                    get_buf=Mock(return_value=b"\0" * 320),
                    lock_buf=Mock(return_value=b"\0" * 320),
                    get_property_to_json=Mock(
                        return_value=(json.dumps(audio_metadata), None)
                    ),
                )
                extension.buffered_frames.put_nowait(frame)
                extension.buffered_frames_size = 320
                connection = Mock(
                    is_connected=Mock(return_value=True), send_pcm=AsyncMock()
                )

                async def commit():
                    await extension.on_final("session b transcript")

                connection.commit = AsyncMock(side_effect=commit)

                async def reopen():
                    extension._generation += 1
                    extension._reset_turn()
                    extension._flushing = True
                    extension.connection = connection
                    await extension.on_open()

                extension._reopen = AsyncMock(side_effect=reopen)
                request = Data.create("asr_finalize")
                payload = {"finalize_id": "finalize-b"}
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
                await asyncio.wait_for(pending, 1)
                await asyncio.wait_for(consumer, 1)
                await extension._reconnect_task
                expected = (
                    dict(supplied)
                    if supplied and "session_id" in supplied
                    else {**audio_metadata, **(supplied or {})}
                )
                result = self.outputs(extension, "asr_result")[0]
                self.assertEqual(
                    {key: result["metadata"][key] for key in expected}, expected
                )
                self.assertEqual(
                    self.outputs(extension, "asr_finalize_end"),
                    [{"finalize_id": "finalize-b", "metadata": expected}],
                )
                ttlw = [
                    item
                    for item in self.outputs(extension, "metrics")
                    if ModuleMetricKey.ASR_TTLW in item["metrics"]
                ]
                self.assertEqual(len(ttlw), 1)
                self.assertEqual(
                    ttlw[0]["metadata"]["session_id"], expected["session_id"]
                )
                self.assertEqual(extension.metadata, audio_metadata)

    async def test_eviction_during_flush_keeps_start_and_includes_gap(self):
        extension = self.new_extension()
        extension.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=64000)
        )
        frames = [
            Mock(
                get_buf=Mock(return_value=b"\0" * size),
                lock_buf=Mock(return_value=b"\0" * size),
            )
            for size in (32000, 32000, 64000)
        ]
        for frame in frames[:2]:
            await extension._handle_audio_frame(extension.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def dump(_data):
            if not entered.is_set():
                entered.set()
                await release.wait()

        extension.audio_dumper = Mock(push_bytes=AsyncMock(side_effect=dump))
        extension.connection = Mock(
            is_connected=Mock(return_value=True), send_pcm=AsyncMock()
        )
        extension._flushing = True
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        await extension._handle_audio_frame(extension.ten_env, frames[2])
        release.set()
        await asyncio.wait_for(flushing, 1)
        await extension.on_final("first and third frames")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual((result["start_ms"], result["duration_ms"]), (0, 4000))
        self.assertEqual(extension._emitted_ms, 4000)
        self.assertEqual(extension.dropped_audio_frames, 1)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("next turn")
        self.assertEqual(
            self.outputs(extension, "asr_result")[1]["start_ms"], 4000
        )

    async def test_abort_claims_failed_buffer_before_delayed_error_returns(
        self,
    ):
        extension = self.new_extension()
        extension._schedule_reconnect = Mock()
        extension.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=32000)
        )
        frame = Mock(
            get_buf=Mock(return_value=b"\0" * 32000),
            lock_buf=Mock(return_value=b"\0" * 32000),
        )
        await extension._handle_audio_frame(extension.ten_env, frame)
        entered, release = asyncio.Event(), asyncio.Event()

        async def emit(data):
            value = json.loads(data.get_property_to_json(None)[0])
            if (
                data.get_name() == "error"
                and value["vendor_info"]["code"] == "send_failed"
            ):
                entered.set()
                await release.wait()

        extension.ten_env.send_data.side_effect = emit
        extension.connection = Mock(
            is_connected=Mock(return_value=True),
            send_pcm=AsyncMock(side_effect=OSError("failed")),
            close=AsyncMock(),
        )
        extension._flushing = True
        flushing = asyncio.create_task(extension._flush_buffered_audio())
        await asyncio.wait_for(entered.wait(), 1)
        await extension._handle_audio_frame(
            extension.ten_env, Mock(get_buf=Mock(return_value=b"\0" * 64000))
        )
        self.assertEqual(extension._emitted_ms, 3000)
        self.assertEqual(extension.dropped_audio_frames, 2)
        extension._reset_turn()
        extension._turn_bytes = 16000
        await extension.on_final("new turn before old error completes")
        result = self.outputs(extension, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (3000, 500)
        )
        release.set()
        await asyncio.wait_for(flushing, 1)
        self.assertEqual(extension._emitted_ms, 3500)
        self.assertEqual(extension.dropped_audio_frames, 2)

    async def test_failed_write_after_eviction_abandons_affected_retry(self):
        e = self.new_extension()
        e._schedule_reconnect = Mock()
        e.buffer_strategy = Mock(
            return_value=module.ASRBufferConfigModeKeep(byte_limit=64000)
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
        result = self.outputs(e, "asr_result")[0]
        self.assertEqual(
            (result["start_ms"], result["duration_ms"]), (4000, 500)
        )

    async def test_connected_finalize_preserves_known_or_explicit_session(self):
        for supplied in (
            {},
            {"request_tag": "x"},
            {"session_id": "override", "request_tag": "x"},
        ):
            with self.subTest(metadata=supplied):
                extension = self.new_extension()
                frame = Mock(
                    get_buf=Mock(return_value=b"\0" * 320),
                    lock_buf=Mock(return_value=b"\0" * 320),
                    get_property_to_json=Mock(
                        return_value=(
                            json.dumps({"session_id": "session-s"}),
                            None,
                        )
                    ),
                )

                async def commit():
                    await extension.on_final("connected transcript")

                extension.connection = Mock(
                    is_connected=Mock(return_value=True),
                    send_pcm=AsyncMock(),
                    commit=AsyncMock(side_effect=commit),
                )
                await extension._handle_audio_frame(extension.ten_env, frame)
                request = Data.create("asr_finalize")
                request.set_property_from_json(
                    None,
                    json.dumps(
                        {
                            "finalize_id": "connected-finalize",
                            "metadata": supplied,
                        }
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
                await asyncio.wait_for(pending, 1)
                await asyncio.wait_for(consumer, 1)
                expected = {"session_id": "session-s", **supplied}
                result = self.outputs(extension, "asr_result")[0]
                self.assertEqual(
                    {key: result["metadata"][key] for key in expected}, expected
                )
                self.assertEqual(
                    self.outputs(extension, "asr_finalize_end"),
                    [
                        {
                            "finalize_id": "connected-finalize",
                            "metadata": expected,
                        }
                    ],
                )
                ttlw = [
                    item
                    for item in self.outputs(extension, "metrics")
                    if ModuleMetricKey.ASR_TTLW in item["metrics"]
                ]
                self.assertEqual(len(ttlw), 1)
                self.assertEqual(
                    ttlw[0]["metadata"]["session_id"], expected["session_id"]
                )
                self.assertEqual(
                    supplied, {key: expected[key] for key in supplied}
                )

    async def test_finalize_before_trigger_discards_then_trigger_allows_recovery(
        self,
    ):
        extension = self.new_extension()
        extension.auto_connect = False
        created = []

        class Connection:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]
                self.active = False
                self.send_pcm = AsyncMock()
                self.close = AsyncMock()
                created.append(self)

            def is_connected(self):
                return self.active

            async def start(self, **_kwargs):
                self.active = True
                await self.callback.on_open()

            async def commit(self):
                await self.callback.on_final("after explicit trigger")

        def audio(size, session):
            return Mock(
                get_buf=Mock(return_value=b"\0" * size),
                lock_buf=Mock(return_value=b"\0" * size),
                get_property_to_json=Mock(
                    return_value=(json.dumps({"session_id": session}), None)
                ),
            )

        async def finalize(finalize_id):
            request = Data.create("asr_finalize")
            request.set_property_from_json(
                None, json.dumps({"finalize_id": finalize_id})
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
            await asyncio.wait_for(pending, 1)
            await asyncio.wait_for(consumer, 1)

        with patch.object(module, "OrukRealtimeConnection", Connection):
            await extension._handle_audio_frame(
                extension.ten_env, audio(32000, "before-trigger")
            )
            await finalize("pretrigger-finalize")
            await extension.start_connection()
            extension._schedule_reconnect()
            self.assertEqual(created, [])
            self.assertIsNone(extension._reconnect_task)
            self.assertTrue(extension.buffered_frames.empty())
            self.assertEqual(extension.dropped_audio_frames, 1)
            self.assertEqual(extension._emitted_ms, 1000)
            self.assertEqual(
                self.outputs(extension, "asr_finalize_end"),
                [
                    {
                        "finalize_id": "pretrigger-finalize",
                        "metadata": {"session_id": "before-trigger"},
                    }
                ],
            )
            trigger = Data.create("trigger_connect")
            await extension.on_data(extension.ten_env, trigger)
            self.assertTrue(extension._connection_requested)
            self.assertEqual(len(created), 1)
            await extension._handle_audio_frame(
                extension.ten_env, audio(16000, "after-trigger")
            )
            await finalize("posttrigger-finalize")
            created[0].send_pcm.assert_awaited_once_with(b"\0" * 16000)
            result = self.outputs(extension, "asr_result")[0]
            self.assertEqual(
                (result["start_ms"], result["duration_ms"]), (1000, 500)
            )
            self.assertEqual(result["metadata"]["session_id"], "after-trigger")
            self.assertEqual(
                self.outputs(extension, "asr_finalize_end")[1],
                {
                    "finalize_id": "posttrigger-finalize",
                    "metadata": {"session_id": "after-trigger"},
                },
            )
            self.assertEqual(
                len(self.outputs(extension, "asr_finalize_end")), 2
            )
            created[0].active = False
            await created[0].callback.on_close(1000, "turn complete")
            await asyncio.wait_for(extension._reconnect_task, 1)
            self.assertEqual(len(created), 2)
            self.assertTrue(extension.is_connected())
            self.assertEqual(extension.dropped_audio_frames, 1)
            await extension.stop_connection()

    async def test_partial_audio_metadata_preserves_interim_and_ttfw_session(
        self,
    ):
        for supplied in (
            None,
            {},
            {"trace": "t"},
            {"session_id": "override", "trace": "t"},
        ):
            with self.subTest(metadata=supplied):
                extension = self.new_extension()
                extension.connection = Mock(
                    is_connected=Mock(return_value=True), send_pcm=AsyncMock()
                )

                def frame(metadata):
                    raw = json.dumps(metadata) if metadata is not None else ""
                    return Mock(
                        get_buf=Mock(return_value=b"\0" * 320),
                        lock_buf=Mock(return_value=b"\0" * 320),
                        get_property_to_json=Mock(return_value=(raw, None)),
                    )

                await extension._handle_audio_frame(
                    extension.ten_env, frame({"session_id": "session-s"})
                )
                original = copy.deepcopy(supplied)
                await extension._handle_audio_frame(
                    extension.ten_env, frame(supplied)
                )
                await extension.on_interim("first words")
                expected = {"session_id": "session-s", **(supplied or {})}
                result = self.outputs(extension, "asr_result")[0]
                self.assertFalse(result["final"])
                self.assertEqual(
                    {key: result["metadata"][key] for key in expected}, expected
                )
                ttfw = [
                    item
                    for item in self.outputs(extension, "metrics")
                    if ModuleMetricKey.ASR_TTFW in item["metrics"]
                ]
                self.assertEqual(len(ttfw), 1)
                self.assertEqual(
                    ttfw[0]["metadata"]["session_id"], expected["session_id"]
                )
                self.assertEqual(extension.session_id, expected["session_id"])
                self.assertEqual(supplied, original)
