import asyncio
import json
import sys
import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ten_ai_base.helper import PCMWriter
from ten_ai_base.tts2 import RequestState
from ten_ai_base.tts2_http import AsyncTTS2HttpExtension
from ten_runtime import Data

from typecast_tts_python.config import TypecastTTSConfig
from typecast_tts_python.extension import TypecastTTSExtension
from typecast_tts_python.typecast_tts import TypecastTTSClient


@pytest.mark.parametrize("failure_phase", ["dump", "usage"])
def test_terminal_failure_retries_without_duplicate_end(
    failure_phase, tmp_path
):
    async def run():
        env = MagicMock()
        events = []
        complete = asyncio.Event()
        failed = False
        extension = TypecastTTSExtension("test")
        extension.ten_env = env
        extension.config = TypecastTTSConfig(
            dump=True,
            dump_path=str(tmp_path),
            params={"api_key": "key", "voice_id": "voice"},
        )
        extension.config.update_params()
        extension.config.validate()
        extension.client = TypecastTTSClient(extension.config, env)
        original_flush = PCMWriter.flush
        original_usage = extension.send_usage_metrics
        original_finish = extension.finish_request

        async def flush(writer):
            nonlocal failed
            if failure_phase == "dump" and not failed:
                failed = True
                raise OSError("temporary dump I/O failure")
            await original_flush(writer)

        async def usage(*args, **kwargs):
            nonlocal failed
            if failure_phase == "usage" and not failed:
                failed = True
                raise OSError("temporary terminal metrics failure")
            await original_usage(*args, **kwargs)

        async def finish(*args, **kwargs):
            await original_finish(*args, **kwargs)
            complete.set()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            events.append((data.get_name(), json.loads(body)))

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock()
        extension.send_usage_metrics = usage
        extension.finish_request = finish
        sdk = MagicMock()
        sdk.__aenter__ = AsyncMock(return_value=sdk)
        sdk.__aexit__ = AsyncMock()

        async def stream(request, chunk_size):
            assert chunk_size == extension.config.chunk_size
            assert request.text in ("first", "recovery")
            header = (
                b"RIFF"
                + b"\xff" * 4
                + b"WAVEfmt "
                + struct.pack("<IHHIIHH", 16, 1, 1, 32000, 64000, 2, 16)
                + b"data"
                + b"\xff" * 4
            )
            yield header + b"\x01\x02" * 3200

        sdk.text_to_speech_stream = stream
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast", return_value=sdk
        ), patch.object(PCMWriter, "flush", flush):
            loop = asyncio.create_task(extension._process_input_queue(env))
            try:
                for request_id in ("first", "recovery"):
                    complete.clear()
                    data = Data.create("tts_text_input")
                    data.set_property_from_json(
                        None,
                        json.dumps(
                            {
                                "request_id": request_id,
                                "text": request_id,
                                "text_input_end": True,
                            }
                        ),
                    )
                    await extension.on_data(env, data)
                    await asyncio.wait_for(complete.wait(), 1)
                    ends = [
                        body
                        for name, body in events
                        if name == "tts_audio_end"
                        and body["request_id"] == request_id
                    ]
                    assert len(ends) == 1
                    assert ends[0]["request_total_audio_duration_ms"] == 100
                    assert extension.request_states[request_id] == (
                        RequestState.COMPLETED
                    )
                    assert extension._processing_request_id is None
                    assert request_id not in extension.recorder_map
                    assert (
                        tmp_path / f"typecast_dump_{request_id}.pcm"
                    ).read_bytes() == b"\x01\x02" * 3200
                assert failed
                assert env.send_audio_frame.await_count == 2
            finally:
                await extension.input_queue.put(None)
                await asyncio.wait_for(loop, 1)
                await extension.client.clean()

    asyncio.run(run())


def test_flush_before_next_http_request_enters_does_not_repeat_previous_end(
    tmp_path,
):
    async def run():
        env = MagicMock()
        events = []
        completed = asyncio.Event()
        waiting = asyncio.Event()
        release = asyncio.Event()
        extension = TypecastTTSExtension("test")
        extension.ten_env = env
        extension.config = TypecastTTSConfig(
            dump=True,
            dump_path=str(tmp_path),
            params={"api_key": "key", "voice_id": "voice"},
        )
        extension.config.update_params()
        extension.config.validate()
        extension.client = TypecastTTSClient(extension.config, env)
        original_request = AsyncTTS2HttpExtension.request_tts
        original_finish = extension.finish_request

        async def request(self, item):
            if item.request_id == "cancelled":
                waiting.set()
                await release.wait()
            await original_request(self, item)

        async def finish(*args, **kwargs):
            await original_finish(*args, **kwargs)
            completed.set()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            if data.get_name() != "metrics":
                events.append((data.get_name(), json.loads(body)))

        async def input_data(name, payload):
            data = Data.create(name)
            data.set_property_from_json(None, json.dumps(payload))
            await extension.on_data(env, data)

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock()
        extension.finish_request = finish
        sdk = MagicMock()
        sdk.__aenter__ = AsyncMock(return_value=sdk)
        sdk.__aexit__ = AsyncMock()
        requests = []

        async def stream(item, chunk_size):
            assert chunk_size == extension.config.chunk_size
            requests.append(item.text)
            header = (
                b"RIFF"
                + b"\xff" * 4
                + b"WAVEfmt "
                + struct.pack("<IHHIIHH", 16, 1, 1, 32000, 64000, 2, 16)
                + b"data"
                + b"\xff" * 4
            )
            yield header + b"\x01\x02" * 3200

        sdk.text_to_speech_stream = stream
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast", return_value=sdk
        ), patch.object(AsyncTTS2HttpExtension, "request_tts", request):
            loop = asyncio.create_task(extension._process_input_queue(env))
            try:
                for request_id in ("first", "cancelled", "recovery"):
                    completed.clear()
                    await input_data(
                        "tts_text_input",
                        {
                            "request_id": request_id,
                            "text": request_id,
                            "text_input_end": True,
                        },
                    )
                    if request_id == "cancelled":
                        await asyncio.wait_for(waiting.wait(), 1)
                        await asyncio.wait_for(
                            input_data("tts_flush", {"flush_id": "flush"}),
                            1,
                        )
                        assert not release.is_set()
                        assert extension._processing_request_id is None
                    else:
                        await asyncio.wait_for(completed.wait(), 1)
                assert requests == ["first", "recovery"]
                assert [name for name, _ in events] == [
                    "tts_audio_start",
                    "tts_audio_end",
                    "tts_flush_end",
                    "tts_audio_start",
                    "tts_audio_end",
                ]
                ends = [
                    body for name, body in events if name == "tts_audio_end"
                ]
                assert [body["request_id"] for body in ends] == [
                    "first",
                    "recovery",
                ]
                assert all(
                    body["request_total_audio_duration_ms"] == 100
                    for body in ends
                )
                assert env.send_audio_frame.await_count == 2
                assert not extension.recorder_map
                for request_id in ("first", "recovery"):
                    assert (
                        tmp_path / f"typecast_dump_{request_id}.pcm"
                    ).read_bytes() == b"\x01\x02" * 3200
            finally:
                release.set()
                await extension.input_queue.put(None)
                await asyncio.wait_for(loop, 1)
                await extension.client.clean()

    asyncio.run(run())
