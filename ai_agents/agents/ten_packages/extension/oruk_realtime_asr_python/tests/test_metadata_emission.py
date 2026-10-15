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
