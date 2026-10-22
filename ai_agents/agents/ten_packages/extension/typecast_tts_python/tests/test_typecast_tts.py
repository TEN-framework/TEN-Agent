import sys
import struct
from pathlib import Path
import asyncio
import json
import threading
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ten_runtime import AsyncExtensionTester, AsyncTenEnvTester, Data, TenError
from ten_runtime import TenErrorCode
from ten_ai_base.struct import TTS2HttpResponseEventType, TTSTextInput
from ten_ai_base.helper import PCMWriter
from ten_ai_base.helper import write_pcm_to_file
from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.tts2_http import AsyncTTS2HttpExtension
from ten_ai_base.tts2 import RequestState

from pcm import StreamingWavToPcm16
from typecast_tts_python.config import TypecastTTSConfig
from typecast_tts_python.extension import TypecastTTSExtension
from typecast_tts_python.typecast_tts import TypecastTTSClient
from typecast import TypecastError, UnauthorizedError

WAV_HEADER = (
    b"RIFF"
    + b"\xff" * 4
    + b"WAVEfmt "
    + struct.pack("<IHHIIHH", 16, 1, 1, 32000, 64000, 2, 16)
    + b"data"
    + b"\xff" * 4
)


def test_config_defaults_and_forces_wav():
    config = TypecastTTSConfig(
        params={
            "api_key": "key",
            "voice_id": "voice",
            "url": "https://example.com/",
            "output": {
                "audio_format": "mp3",
                "audio_tempo": 1.1,
                "remove_silence_ms": 0,
            },
        }
    )

    config.update_params()
    config.validate()

    assert config.url == "https://example.com"
    assert "url" not in config.params
    assert config.params["model"] == "ssfm-v30"
    assert config.params["output"] == {
        "audio_format": "wav",
        "audio_tempo": 1.1,
        "remove_silence_ms": 0,
    }


@pytest.mark.parametrize("missing", ["api_key", "voice_id"])
def test_config_requires_credentials_and_voice(missing):
    params = {"api_key": "key", "voice_id": "voice"}
    params[missing] = ""
    config = TypecastTTSConfig(params=params)
    config.update_params()

    with pytest.raises(ValueError, match=missing):
        config.validate()


@pytest.mark.parametrize("value", [-1, 1001, True, False, 1.5, "0"])
def test_config_rejects_invalid_silence(value):
    config = TypecastTTSConfig(
        params={
            "api_key": "key",
            "voice_id": "voice",
            "output": {"remove_silence_ms": value},
        }
    )
    config.update_params()
    with pytest.raises(ValueError, match="remove_silence_ms"):
        config.validate()


@pytest.mark.parametrize(
    "output",
    [
        {},
        {"remove_silence_ms": None},
        {"remove_silence_ms": 0},
        {"remove_silence_ms": 1000},
    ],
)
def test_config_accepts_silence_bounds_and_omission(output):
    config = TypecastTTSConfig(
        params={
            "api_key": "key",
            "voice_id": "voice",
            "output": output.copy(),
        }
    )
    config.update_params()
    config.validate()
    assert config.params["output"] == {**output, "audio_format": "wav"}


@pytest.mark.parametrize("late_chunk", [False, True])
@pytest.mark.parametrize("dump", [False, True, "existing"])
@pytest.mark.parametrize(
    "phase",
    [
        "first_byte",
        "start",
        "start_sent",
        "ttfb",
        "audio",
        "next_byte",
        "end",
        "finish",
    ],
)
def test_real_flush_at_emission_boundaries_recovers(
    late_chunk, dump, phase, tmp_path
):
    previous = b"\x11\x22" * 50 if dump == "existing" else b""
    previous_recovery = b"\x33\x44" * 75 if dump == "existing" else b""
    if dump == "existing":
        (tmp_path / "typecast_dump_first.pcm").write_bytes(previous)
        (tmp_path / "typecast_dump_recovery.pcm").write_bytes(previous_recovery)

    async def run():
        waiting = asyncio.Event()
        release = asyncio.Event()
        closed = asyncio.Event()
        recovered = asyncio.Event()
        cancelled = asyncio.Event()
        terminal = phase in ("end", "finish")
        events = []
        now = datetime(2026, 1, 1)
        env = MagicMock()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            payload = json.loads(body)
            if extension.current_request_id == "first" and not waiting.is_set():
                if (
                    (
                        phase in ("start", "start_sent")
                        and data.get_name() == "tts_audio_start"
                    )
                    or (phase == "end" and data.get_name() == "tts_audio_end")
                    or (
                        phase == "ttfb"
                        and data.get_name() == "metrics"
                        and extension.request_ts is not None
                    )
                ):
                    if phase == "start_sent":
                        events.append((data.get_name(), payload))
                    waiting.set()
                    await release.wait()
                    if phase == "start_sent":
                        return
            if data.get_name() != "metrics":
                events.append((data.get_name(), payload))

        async def send_audio(frame):
            if phase == "audio" and extension.current_request_id == "first":
                waiting.set()
                await release.wait()
            buffer = frame.lock_buf()
            try:
                events.append(("pcm", bytes(buffer)))
            finally:
                frame.unlock_buf(buffer)

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock(side_effect=send_audio)
        extension = TypecastTTSExtension("test")
        extension.ten_env = env
        extension.config = TypecastTTSConfig(
            dump=bool(dump),
            dump_path=str(tmp_path),
            params={"api_key": "key", "voice_id": "voice"},
        )
        extension.config.update_params()
        extension.config.validate()
        extension.client = TypecastTTSClient(extension.config, env)
        cancel_task = extension._cancel_current_task
        finish_request = extension.finish_request

        async def cancel_current_task():
            await cancel_task()
            if phase in ("start", "start_sent"):
                assert extension.request_ts == datetime(2026, 1, 1)
            cancelled.set()

        async def finish(*args, **kwargs):
            if (
                phase == "finish"
                and kwargs.get("request_id") == "first"
                and not waiting.is_set()
            ):
                waiting.set()
                await release.wait()
            await finish_request(*args, **kwargs)
            if kwargs.get("request_id") == "recovery":
                recovered.set()

        extension._cancel_current_task = cancel_current_task
        extension.finish_request = finish
        sdk = MagicMock()
        sdk.__aenter__ = AsyncMock(return_value=sdk)
        sdk.__aexit__ = AsyncMock()

        async def stream(request, chunk_size):
            nonlocal now
            assert chunk_size == extension.config.chunk_size
            if request.text == "first":
                try:
                    if phase != "first_byte":
                        # Exceed the dump writer's buffer while frame emission stalls.
                        samples = 40000 if phase == "audio" else 3200
                        yield WAV_HEADER + b"\x05\x06" * samples
                    now += timedelta(milliseconds=275)
                    if terminal:
                        return
                    waiting.set()
                    await release.wait()
                except asyncio.CancelledError:
                    if not late_chunk:
                        raise
                    yield (
                        WAV_HEADER if phase == "first_byte" else b""
                    ) + b"\x09\x09" * 3200
                finally:
                    closed.set()
                return
            assert closed.is_set()
            yield WAV_HEADER + b"\x01\x02" * 3200
            now += timedelta(milliseconds=275)

        async def input_data(name, payload):
            data = Data.create(name)
            data.set_property_from_json(None, json.dumps(payload))
            await extension.on_data(env, data)

        sdk.text_to_speech_stream = stream
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast", return_value=sdk
        ), patch("ten_ai_base.tts2_http.datetime") as clock:
            clock.now.side_effect = lambda: now
            loop = asyncio.create_task(extension._process_input_queue(env))
            try:
                await input_data(
                    "tts_text_input",
                    {
                        "request_id": "first",
                        "text": "first",
                        "text_input_end": True,
                    },
                )
                await asyncio.wait_for(waiting.wait(), 1)
                if not terminal:
                    now += timedelta(milliseconds=125)
                flush = asyncio.create_task(
                    input_data("tts_flush", {"flush_id": "flush-first"})
                )
                if terminal:
                    await asyncio.wait_for(cancelled.wait(), 1)
                    assert not flush.done()
                    release.set()
                await asyncio.wait_for(flush, 1)
                if phase in ("start", "start_sent"):
                    await asyncio.wait_for(closed.wait(), 1)
                    assert extension.request_ts == datetime(2026, 1, 1)
                prefix = []
                if phase != "first_byte":
                    if phase != "start":
                        prefix.append("tts_audio_start")
                    if phase == "next_byte" or terminal:
                        prefix.append("pcm")
                    prefix.append("tts_audio_end")
                    end = events[-2][1]
                    assert end["request_id"] == "first"
                    assert (
                        end["reason"]
                        == (
                            TTSAudioEndReason.REQUEST_END
                            if terminal
                            else TTSAudioEndReason.INTERRUPTED
                        ).value
                    )
                    assert end["request_total_audio_duration_ms"] == (
                        100 if phase == "next_byte" or terminal else 0
                    )
                    assert end["request_event_interval_ms"] == (
                        275
                        if terminal
                        else 400 if phase == "next_byte" else 125
                    )
                prefix.append("tts_flush_end")
                assert [name for name, _ in events] == prefix
                assert events[-1][1]["flush_id"] == "flush-first"
                if phase == "next_byte" or terminal:
                    assert events[1][1] == b"\x05\x06" * 3200
                if dump:
                    output = tmp_path / "typecast_dump_first.pcm"
                    assert (
                        output.read_bytes() if output.exists() else b""
                    ) == previous + b"".join(
                        body for name, body in events if name == "pcm"
                    )
                if phase in ("start", "start_sent"):
                    # A repeated flush must not emit a second terminal event.
                    await input_data("tts_flush", {"flush_id": "flush-again"})
                    assert [name for name, _ in events] == prefix + [
                        "tts_flush_end"
                    ]
                events.clear()
                await input_data(
                    "tts_text_input",
                    {
                        "request_id": "recovery",
                        "text": "recovery",
                        "text_input_end": True,
                    },
                )
                # Recovery must finish without releasing the stalled stream.
                await asyncio.wait_for(recovered.wait(), 1)
                assert release.is_set() == terminal
                assert closed.is_set()
                assert [name for name, _ in events] == [
                    "tts_audio_start",
                    "pcm",
                    "tts_audio_end",
                ]
                assert events[0][1]["request_id"] == "recovery"
                assert events[1][1] == b"\x01\x02" * 3200
                end = events[2][1]
                assert end["request_id"] == "recovery"
                assert end["reason"] == TTSAudioEndReason.REQUEST_END.value
                assert end["request_total_audio_duration_ms"] == 100
                assert end["request_event_interval_ms"] == 275
                assert "first" not in extension.request_states
                assert extension._processing_request_id is None
                if dump:
                    assert (
                        tmp_path / "typecast_dump_recovery.pcm"
                    ).read_bytes() == previous_recovery + events[1][1]
            finally:
                release.set()
                await extension.input_queue.put(None)
                loop.cancel()
                await asyncio.gather(loop, return_exceptions=True)
                await extension.client.clean()

    asyncio.run(run())


def test_appended_text_finishes_before_buffered_request(tmp_path):
    async def run():
        waiting, release, completed = (asyncio.Event() for _ in range(3))
        events, calls, closed = [], [], []
        metrics = []
        now = datetime(2026, 1, 1)
        env = MagicMock()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            if data.get_name() == "metrics":
                metrics.append(json.loads(body)["metrics"])
            else:
                events.append((data.get_name(), json.loads(body)))

        async def send_audio(frame):
            buffer = frame.lock_buf()
            try:
                events.append(("pcm", bytes(buffer)))
            finally:
                frame.unlock_buf(buffer)

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock(side_effect=send_audio)
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
        finish_request = extension.finish_request

        async def finish(*args, **kwargs):
            await finish_request(*args, **kwargs)
            if kwargs.get("request_id") == "buffered":
                completed.set()

        extension.finish_request = finish
        sdk = MagicMock()
        sdk.__aenter__ = AsyncMock(return_value=sdk)
        sdk.__aexit__ = AsyncMock()
        pcm = {
            "part1": b"\x01\x02" * 3200,
            "part2": b"\x03\x04" * 1600,
            "buffered": b"\x05\x06" * 6400,
        }

        async def stream(request, chunk_size):
            nonlocal now
            assert chunk_size == extension.config.chunk_size
            assert calls == closed  # Prior segment's SDK stream is closed.
            calls.append(request.text)
            try:
                yield WAV_HEADER + pcm[request.text]
                now += timedelta(milliseconds=100)
                if request.text == "part1":
                    waiting.set()
                    await release.wait()
                elif request.text == "part2":
                    now += timedelta(milliseconds=50)
            finally:
                closed.append(request.text)

        async def enqueue(request_id, text, final):
            data = Data.create("tts_text_input")
            data.set_property_from_json(
                None,
                json.dumps(
                    {
                        "request_id": request_id,
                        "text": text,
                        "text_input_end": final,
                    }
                ),
            )
            await extension.on_data(env, data)

        sdk.text_to_speech_stream = stream
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast", return_value=sdk
        ), patch("ten_ai_base.tts2_http.datetime") as clock:
            clock.now.side_effect = lambda: now
            loop = asyncio.create_task(extension._process_input_queue(env))
            try:
                await enqueue("first", "part1", False)
                await asyncio.wait_for(waiting.wait(), 1)
                assert [name for name, _ in events] == [
                    "tts_audio_start",
                    "pcm",
                ]
                await enqueue("buffered", "buffered", True)
                await enqueue("first", "part2", True)
                release.set()
                await asyncio.wait_for(completed.wait(), 1)
                assert calls == closed == ["part1", "part2", "buffered"]
                assert [name for name, _ in events] == [
                    "tts_audio_start",
                    "pcm",
                    "pcm",
                    "tts_audio_end",
                    "tts_audio_start",
                    "pcm",
                    "tts_audio_end",
                ]
                for start, end, request_id, duration, interval in (
                    (0, 3, "first", 150, 250),
                    (4, 6, "buffered", 200, 100),
                ):
                    assert events[start][1]["request_id"] == request_id
                    payload = events[end][1]
                    assert payload["request_id"] == request_id
                    assert (
                        payload["reason"] == TTSAudioEndReason.REQUEST_END.value
                    )
                    assert (
                        payload["request_total_audio_duration_ms"] == duration
                    )
                    assert payload["request_event_interval_ms"] == interval
                assert [body for name, body in events if name == "pcm"] == list(
                    pcm.values()
                )
                assert (
                    tmp_path / "typecast_dump_first.pcm"
                ).read_bytes() == pcm["part1"] + pcm["part2"]
                assert (
                    tmp_path / "typecast_dump_buffered.pcm"
                ).read_bytes() == pcm["buffered"]
                assert not extension._pending_messages
                assert extension._processing_request_id is None
                # Appended text remains one logical request, including TTFB.
                assert [m["ttfb"] for m in metrics if "ttfb" in m] == [0, 0]
                usage = [m for m in metrics if "output_characters" in m]
                assert [m["output_characters"] for m in usage] == [10, 8]
                assert [m["recv_audio_duration"] for m in usage] == [150, 200]
                assert [m["total_output_characters"] for m in usage] == [10, 18]
                assert [m["total_recv_audio_duration"] for m in usage] == [
                    150,
                    350,
                ]
                assert extension.output_characters == 0
                assert extension.recv_audio_chunks_len == 0
            finally:
                release.set()
                await extension.input_queue.put(None)
                loop.cancel()
                await asyncio.gather(loop, return_exceptions=True)
                await extension.client.clean()

    asyncio.run(run())


@pytest.mark.parametrize("scenario", ["success", "error", "flush", "empty"])
def test_extension_audio_accounting_and_recovery(scenario, tmp_path):
    async def run():
        events = []
        metrics = []
        now = datetime(2026, 1, 1)
        env = MagicMock()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            if data.get_name() == "metrics":
                metrics.append(json.loads(body)["metrics"])
            else:
                events.append((data.get_name(), json.loads(body)))

        async def send_audio(frame):
            buffer = frame.lock_buf()
            try:
                events.append(("pcm", bytes(buffer)))
            finally:
                frame.unlock_buf(buffer)
            assert frame.get_sample_rate() == 32000
            assert frame.get_bytes_per_sample() == 2
            assert frame.get_number_of_channels() == 1

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock(side_effect=send_audio)
        extension = TypecastTTSExtension("test")
        extension.ten_env = env
        extension.config = TypecastTTSConfig(
            dump=True,
            dump_path=str(tmp_path),
            params={
                "api_key": "key",
                "voice_id": "voice",
                "output": {"remove_silence_ms": 0},
            },
        )
        extension.config.update_params()
        extension.config.validate()
        extension.client = TypecastTTSClient(extension.config, env)
        sdk = MagicMock()
        sdk.__aenter__ = AsyncMock(return_value=sdk)
        sdk.__aexit__ = AsyncMock()

        async def stream(request, chunk_size):
            nonlocal now
            assert request.output.remove_silence_ms == 0
            assert chunk_size == 8192
            mode = scenario if request.text == "first" else "success"
            if mode == "empty":
                return
            now += timedelta(milliseconds=100)
            yield WAV_HEADER[:20]
            yield WAV_HEADER[20:] + b"\x01\x02" * 3200
            now += timedelta(milliseconds=275)
            if mode == "error":
                raise TypecastError("temporary failure", 500)
            if mode == "flush":
                await extension.cancel_tts()
            # A late chunk after cancellation must not become a PCM frame.
            yield b"\x03\x04" * 1600

        sdk.text_to_speech_stream = stream
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast", return_value=sdk
        ), patch("ten_ai_base.tts2_http.datetime") as clock:
            clock.now.side_effect = lambda: now
            try:
                for request_id in ("first", "recovery"):
                    events.clear()
                    metrics.clear()
                    # Enter the inherited HTTP handler at its queue dispatch boundary.
                    extension.request_states[request_id] = (
                        RequestState.FINALIZING
                    )
                    extension._processing_request_id = request_id
                    await extension.request_tts(
                        TTSTextInput(
                            request_id=request_id,
                            text=request_id,
                            text_input_end=True,
                        )
                    )
                    mode = scenario if request_id == "first" else "success"
                    names = [name for name, _ in events]
                    expected = {
                        "success": [
                            "tts_audio_start",
                            "pcm",
                            "pcm",
                            "tts_audio_end",
                        ],
                        "error": [
                            "tts_audio_start",
                            "pcm",
                            "error",
                            "tts_audio_end",
                        ],
                        "flush": ["tts_audio_start", "pcm", "tts_audio_end"],
                        "empty": ["tts_audio_end"],
                    }
                    assert names == expected[mode]
                    end = events[-1][1]
                    assert end["request_id"] == request_id
                    assert (
                        end["request_total_audio_duration_ms"]
                        == {
                            "success": 150,
                            "error": 100,
                            "flush": 100,
                            "empty": 0,
                        }[mode]
                    )
                    assert end["request_event_interval_ms"] == (
                        0 if mode == "empty" else 275
                    )
                    assert (
                        end["reason"]
                        == {
                            "success": TTSAudioEndReason.REQUEST_END,
                            "error": TTSAudioEndReason.ERROR,
                            "flush": TTSAudioEndReason.INTERRUPTED,
                            "empty": TTSAudioEndReason.REQUEST_END,
                        }[mode].value
                    )
                    if mode != "empty":
                        assert events[0][1]["request_id"] == request_id
                    pcm = b"".join(
                        body for name, body in events if name == "pcm"
                    )
                    assert pcm == (
                        b""
                        if mode == "empty"
                        else b"\x01\x02" * 3200
                        + (b"\x03\x04" * 1600 if mode == "success" else b"")
                    )
                    assert (
                        extension.request_states[request_id]
                        == RequestState.COMPLETED
                    )
                    assert extension._processing_request_id is None
                    assert extension.current_audio_request_id is None
                    assert [m["ttfb"] for m in metrics if "ttfb" in m] == (
                        [] if mode == "empty" else [100]
                    )
                    usage = [m for m in metrics if "output_characters" in m]
                    assert len(usage) == 1
                    assert usage[0]["output_characters"] == len(request_id)
                    assert usage[0]["input_characters"] == 0
                    assert usage[0]["recv_audio_duration"] == len(pcm) / 64
                    assert extension.output_characters == 0
                    assert extension.recv_audio_chunks_len == 0
                    assert request_id not in extension.recorder_map
                    dump = tmp_path / f"typecast_dump_{request_id}.pcm"
                    if pcm:
                        assert dump.read_bytes() == pcm
                    else:
                        assert not dump.exists() or dump.read_bytes() == b""
            finally:
                await extension.client.clean()
        sdk.__aexit__.assert_awaited_once_with(None, None, None)

    asyncio.run(run())


def test_streaming_wav_to_pcm16_strips_header_across_chunks():
    converter = StreamingWavToPcm16()
    header = WAV_HEADER

    assert converter.feed(header[:20]) == b""
    assert converter.feed(header[20:] + b"\x01\x02\x03") == b"\x01\x02"
    assert converter.feed(b"\x04\x05") == b"\x03\x04"
    assert converter.feed(b"\x06") == b"\x05\x06"


def test_streaming_wav_to_pcm16_strips_header_in_single_chunk():
    converter = StreamingWavToPcm16()
    header = WAV_HEADER

    assert converter.feed(header + b"\x01\x02\x03\x04") == b"\x01\x02\x03\x04"


def test_extension_flushes_dump_tail_added_during_write(tmp_path):
    output = tmp_path / "dump.pcm"
    first_write_started = threading.Event()
    release_first_write = threading.Event()
    write_count = 0

    def delayed_write(buffer, file_name):
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            first_write_started.set()
            release_first_write.wait()
        write_pcm_to_file(buffer, file_name)

    async def run():
        writer = PCMWriter(str(output), buffer_size=4)
        extension = TypecastTTSExtension("test")
        extension.recorder_map = {"request-id": writer}

        async def base_finish(self, request_id, reason, log_message=None):
            await self.recorder_map[request_id].flush()

        with patch(
            "ten_ai_base.helper.write_pcm_to_file",
            side_effect=delayed_write,
        ), patch.object(
            AsyncTTS2HttpExtension,
            "_send_audio_end_and_finish",
            base_finish,
        ):
            await writer.write(b"head")
            while not first_write_started.is_set():
                await asyncio.sleep(0)
            await writer.write(b"tail")
            flush_task = asyncio.create_task(
                extension._send_audio_end_and_finish(
                    request_id="request-id",
                    reason=TTSAudioEndReason.REQUEST_END,
                )
            )
            await asyncio.sleep(0)
            release_first_write.set()
            await flush_task

    asyncio.run(run())

    assert output.read_bytes() == b"headtail"


def test_client_empty_text_ends_without_request():
    config = TypecastTTSConfig(params={"api_key": "key", "voice_id": "voice"})
    config.update_params()
    client = TypecastTTSClient(config, MagicMock())

    async def collect():
        return [event async for event in client.get("  ", "request-id")]

    assert asyncio.run(collect()) == [(None, TTS2HttpResponseEventType.END)]


def test_client_preserves_sdk_headers_and_adds_ten_user_agent():
    async def run():
        headers = []

        async def stream(request):
            headers.append(dict(request.headers))
            return web.Response(
                body=WAV_HEADER + b"\x01\x02", content_type="audio/wav"
            )

        app = web.Application()
        app.router.add_post("/v1/text-to-speech/stream", stream)
        async with TestServer(app) as server:
            config = TypecastTTSConfig(
                params={
                    "api_key": "test_api_key",
                    "voice_id": "test_voice_id",
                    "url": str(server.make_url("/")),
                }
            )
            config.update_params()
            client = TypecastTTSClient(config, MagicMock())
            try:
                for _ in range(2):
                    events = [
                        event async for event in client.get("hello", "id")
                    ]
                    assert events == [
                        (b"\x01\x02", TTS2HttpResponseEventType.RESPONSE),
                        (None, TTS2HttpResponseEventType.END),
                    ]
                session = client._client.session
            finally:
                await client.clean()
            assert session.closed

        assert len(headers) == 2
        for request_headers in headers:
            user_agent = request_headers["User-Agent"]
            assert user_agent.startswith("typecast-python/0.3.15 ")
            assert " Python/" in user_agent
            assert "mode=async; base=custom; transport=rest" in user_agent
            assert user_agent.endswith(" ten-framework")
            assert user_agent.count("ten-framework") == 1
            assert request_headers["X-API-KEY"] == "test_api_key"

    asyncio.run(run())


@pytest.mark.parametrize(
    ("error", "expected_event"),
    [
        (
            UnauthorizedError("invalid key"),
            TTS2HttpResponseEventType.INVALID_KEY_ERROR,
        ),
        (TypecastError("rate limited", 429), TTS2HttpResponseEventType.ERROR),
    ],
)
def test_client_maps_vendor_errors(error, expected_event):
    config = TypecastTTSConfig(params={"api_key": "key", "voice_id": "voice"})
    config.update_params()
    client = TypecastTTSClient(config, MagicMock())

    async def failing_stream(request, chunk_size):
        raise error
        yield b""  # pragma: no cover

    mock_sdk = MagicMock()
    mock_sdk.__aenter__ = AsyncMock(return_value=mock_sdk)
    mock_sdk.__aexit__ = AsyncMock(return_value=None)
    mock_sdk.text_to_speech_stream = failing_stream

    async def collect():
        with patch(
            "typecast_tts_python.typecast_tts.AsyncTypecast",
            return_value=mock_sdk,
        ):
            return [event async for event in client.get("hello", "request-id")]

    events = asyncio.run(collect())
    assert events == [(str(error).encode(), expected_event)]


@pytest.mark.parametrize(
    "mode",
    [
        "first_byte",
        "next_byte",
        "401",
        "429",
        "500",
        "octet",
        "html",
        "json",
        "truncated",
        "odd",
    ],
)
def test_real_http_response_cleanup_and_recovery(mode):
    async def run():
        waiting, release, server_done, got_audio, completed = (
            asyncio.Event() for _ in range(5)
        )
        events = []
        transports = []
        pcm = b"\x01\x02" * 3200
        # Standard PCM16 mono WAV header; the body can be served as octet-stream.

        header = (
            b"RIFF"
            + struct.pack("<I", 36 + len(pcm))
            + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, 32000, 64000, 2, 16)
            + b"data"
            + struct.pack("<I", len(pcm))
        )

        async def serve(request):
            body = await request.json()
            if body["text"] == "recovery" or mode == "octet":
                return web.Response(
                    body=header + pcm, content_type="application/octet-stream"
                )
            if mode.isdigit():
                return web.Response(
                    status=int(mode),
                    text="upstream unavailable",
                    content_type="text/html",
                )
            if mode in ("html", "json", "truncated", "odd"):
                body, content_type = {
                    "html": (b"<html>upstream error</html>" * 4, "text/html"),
                    "json": (b'{"error":"unavailable"}', "application/json"),
                    "truncated": (header[:20], "audio/wav"),
                    "odd": (header + pcm + b"\x01", "audio/wav"),
                }[mode]
                return web.Response(body=body, content_type=content_type)
            transport = request.transport
            transports.append(transport)
            response = web.StreamResponse(headers={"Content-Type": "audio/wav"})
            await response.prepare(request)
            if mode == "next_byte":
                await response.write(header + pcm)
            waiting.set()
            try:
                await release.wait()
                await response.write(
                    header + pcm if mode == "first_byte" else pcm
                )
            except ConnectionResetError:
                pass
            finally:
                server_done.set()
            return response

        env = MagicMock()

        async def send_data(data):
            body, _ = data.get_property_to_json()
            if data.get_name() != "metrics":
                events.append((data.get_name(), json.loads(body)))

        async def send_audio(frame):
            buffer = frame.lock_buf()
            try:
                events.append(("pcm", bytes(buffer)))
            finally:
                frame.unlock_buf(buffer)
            got_audio.set()

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock(side_effect=send_audio)
        app = web.Application()
        app.router.add_post("/v1/text-to-speech/stream", serve)
        async with TestServer(app) as server:
            extension = TypecastTTSExtension("test")
            extension.ten_env = env
            extension.config = TypecastTTSConfig(
                params={
                    "api_key": "local-test-key",
                    "voice_id": "voice",
                    "url": str(server.make_url("/")),
                }
            )
            extension.config.update_params()
            extension.config.validate()
            extension.client = TypecastTTSClient(extension.config, env)
            original_finish = extension.finish_request

            async def finish(*args, **kwargs):
                await original_finish(*args, **kwargs)
                completed.set()

            extension.finish_request = finish

            async def input_data(name, payload):
                data = Data.create(name)
                data.set_property_from_json(None, json.dumps(payload))
                await extension.on_data(env, data)

            async def released_response():
                while extension.client._client.session.connector._acquired or (
                    transports and not transports[0].is_closing()
                ):
                    await asyncio.sleep(0.005)

            loop = asyncio.create_task(extension._process_input_queue(env))
            try:
                await input_data(
                    "tts_text_input",
                    {
                        "request_id": "first",
                        "text": "first",
                        "text_input_end": True,
                    },
                )
                if mode in ("first_byte", "next_byte"):
                    await asyncio.wait_for(waiting.wait(), 2)
                    if mode == "next_byte":
                        await asyncio.wait_for(got_audio.wait(), 2)
                    await asyncio.wait_for(
                        input_data("tts_flush", {"flush_id": "f"}), 2
                    )
                    await asyncio.wait_for(released_response(), 2)
                    assert [name for name, _ in events] == (
                        [
                            "tts_audio_start",
                            "pcm",
                            "tts_audio_end",
                            "tts_flush_end",
                        ]
                        if mode == "next_byte"
                        else ["tts_flush_end"]
                    )
                    if mode == "next_byte":
                        assert (
                            events[2][1]["reason"]
                            == TTSAudioEndReason.INTERRUPTED.value
                        )
                        assert (
                            events[2][1]["request_total_audio_duration_ms"]
                            == 100
                        )
                else:
                    await asyncio.wait_for(completed.wait(), 2)
                    assert [name for name, _ in events] == (
                        ["tts_audio_start", "pcm", "tts_audio_end"]
                        if mode == "octet"
                        else (
                            ["tts_audio_start", "pcm", "error", "tts_audio_end"]
                            if mode == "odd"
                            else ["error", "tts_audio_end"]
                        )
                    )
                    assert (
                        events[-1][1]["reason"]
                        == (
                            TTSAudioEndReason.REQUEST_END
                            if mode == "octet"
                            else TTSAudioEndReason.ERROR
                        ).value
                    )
                events.clear()
                completed.clear()
                await input_data(
                    "tts_text_input",
                    {
                        "request_id": "recovery",
                        "text": "recovery",
                        "text_input_end": True,
                    },
                )
                await asyncio.wait_for(completed.wait(), 2)
                assert [name for name, _ in events] == [
                    "tts_audio_start",
                    "pcm",
                    "tts_audio_end",
                ]
                assert events[0][1]["request_id"] == "recovery"
                assert events[1][1] == pcm
                assert events[2][1]["request_id"] == "recovery"
                assert events[2][1]["request_total_audio_duration_ms"] == 100
                assert not extension.client._client.session.connector._acquired
                release.set()
                if transports:
                    await asyncio.wait_for(server_done.wait(), 2)
                    assert (
                        len(events) == 3
                    )  # The stalled response cannot emit late PCM.
                assert extension._processing_request_id is None
            finally:
                release.set()
                await extension.input_queue.put(None)
                loop.cancel()
                await asyncio.gather(loop, return_exceptions=True)
                session = extension.client._client.session
                await extension.client.clean()
                assert session.closed

    asyncio.run(run())


def test_dump_stat_failure_finishes_and_recovers(tmp_path):
    async def run():
        env = MagicMock()
        events = []

        async def send_data(data):
            body, _ = data.get_property_to_json()
            if data.get_name() != "metrics":
                events.append((data.get_name(), json.loads(body)))

        env.send_data = AsyncMock(side_effect=send_data)
        env.send_audio_frame = AsyncMock()
        extension = TypecastTTSExtension("test")
        extension.ten_env = env
        extension.config = TypecastTTSConfig(
            dump=True,
            dump_path=str(tmp_path),
            params={"api_key": "key", "voice_id": "voice"},
        )
        extension.client = MagicMock()
        extension.client.close_stream = AsyncMock()
        extension.client.get_extra_metadata.return_value = {}

        async def stream(*_):
            yield b"\x01\x02" * 3200, TTS2HttpResponseEventType.RESPONSE
            yield None, TTS2HttpResponseEventType.END

        extension.client.get = stream
        with patch(
            "typecast_tts_python.extension.os.path.getsize",
            side_effect=[PermissionError("cannot stat dump"), 0],
        ):
            for request_id, reason in (
                ("first", TTSAudioEndReason.ERROR),
                ("recovery", TTSAudioEndReason.REQUEST_END),
            ):
                events.clear()
                extension.request_states[request_id] = RequestState.FINALIZING
                extension._processing_request_id = request_id
                await extension.request_tts(
                    TTSTextInput(
                        request_id=request_id, text="text", text_input_end=True
                    )
                )
                assert events[-1][0] == "tts_audio_end"
                assert events[-1][1]["reason"] == reason.value
                assert events[-1][1]["request_total_audio_duration_ms"] == (
                    0 if request_id == "first" else 100
                )
                assert (
                    extension.request_states[request_id]
                    == RequestState.COMPLETED
                )
                assert extension._processing_request_id is None

    asyncio.run(run())


class TypecastTTSExtensionTester(AsyncExtensionTester):
    def __init__(self):
        super().__init__()
        self.audio_end_received = False
        self.received_audio_chunks = []

    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        tts_input = TTSTextInput(
            request_id="tts_request_1",
            text="hello typecast",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        await ten_env.send_data(data)
        asyncio.create_task(self._stop_on_timeout(ten_env))

    async def on_data(self, ten_env: AsyncTenEnvTester, data: Data) -> None:
        if data.get_name() == "tts_audio_end":
            data_json, _ = data.get_property_to_json()
            data_dict = json.loads(data_json)
            assert data_dict["request_id"] == "tts_request_1"
            self.audio_end_received = True
            ten_env.stop_test()

    async def on_audio_frame(self, ten_env: AsyncTenEnvTester, audio_frame):
        buf = audio_frame.lock_buf()
        try:
            self.received_audio_chunks.append(bytes(buf))
        finally:
            audio_frame.unlock_buf(buf)

    async def _stop_on_timeout(self, ten_env: AsyncTenEnvTester) -> None:
        await asyncio.sleep(10)
        ten_env.stop_test(
            TenError.create(
                error_code=TenErrorCode.ErrorCodeGeneric,
                error_message="test timeout",
            )
        )


def test_typecast_tts_extension_success():
    wav_header = WAV_HEADER
    audio_chunk_1 = b"\x01\x02\x03\x04"
    audio_chunk_2 = b"\x05\x06\x07\x08"

    async def mock_text_to_speech_stream(request, chunk_size):
        assert request.text == "hello typecast"
        assert request.output.audio_format == "wav"
        assert request.output.remove_silence_ms == 0
        assert chunk_size == 8192
        yield wav_header[:20]
        yield wav_header[20:] + audio_chunk_1
        yield audio_chunk_2

    with patch("typecast_tts_python.typecast_tts.AsyncTypecast") as mock_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.text_to_speech_stream = mock_text_to_speech_stream
        mock_cls.return_value = mock_client

        property_json = {
            "params": {
                "api_key": "test_api_key",
                "voice_id": "test_voice_id",
                "model": "ssfm-v30",
                "output": {"remove_silence_ms": 0},
            }
        }

        tester = TypecastTTSExtensionTester()
        tester.set_test_mode_single(
            "typecast_tts_python", json.dumps(property_json)
        )

        err = tester.run()

    assert err is None, (
        "test_typecast_tts_extension_success err: "
        f"{err.error_message() if err else 'None'}"
    )
    assert tester.audio_end_received
    assert b"".join(tester.received_audio_chunks) == (
        audio_chunk_1 + audio_chunk_2
    )
    mock_cls.assert_called_once_with(
        host="https://api.typecast.ai",
        api_key="test_api_key",
    )
    mock_client.__aexit__.assert_awaited_once_with(None, None, None)


if __name__ == "__main__":
    test_streaming_wav_to_pcm16_strips_header_across_chunks()
    test_streaming_wav_to_pcm16_strips_header_in_single_chunk()
