"""Regressions through the installed TEN base and native emitted Data JSON."""

import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

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
