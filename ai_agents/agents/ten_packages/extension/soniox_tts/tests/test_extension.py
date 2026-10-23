import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput
from ten_ai_base.tts2 import AsyncTTS2BaseExtension

from soniox_tts.config import SonioxTTSConfig
from soniox_tts.extension import SonioxTTSExtension
from soniox_tts.soniox_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
    SonioxTTSConnectionException,
    SonioxTTSError,
)


def make_extension(events):
    extension = SonioxTTSExtension("soniox")
    extension.config = SonioxTTSConfig(api_key="key")
    extension.ten_env = MagicMock()
    extension.client = MagicMock()
    extension.client.start = AsyncMock()
    extension.client.stop = AsyncMock()
    extension.client.cancel = AsyncMock()
    extension.client.start_stream = AsyncMock()
    extension.client.send_text = AsyncMock()
    extension.client.text_end_sent = False

    async def iter_events(_stream_id):
        for event in events:
            yield event

    extension.client.iter_events = iter_events
    extension.send_tts_audio_start = AsyncMock()
    extension.send_tts_audio_data = AsyncMock()
    extension.send_tts_audio_end = AsyncMock()
    extension.send_tts_ttfb_metrics = AsyncMock()
    extension.finish_request = AsyncMock()
    return extension


def test_extension_emits_pcm_and_exact_audio_end_metrics(monkeypatch):
    async def run():
        audio = b"\x00\x01" * 240
        extension = make_extension(
            [
                (100, EVENT_TTS_TTFB_METRIC),
                (audio[:101], EVENT_TTS_RESPONSE),
                (audio[101:], EVENT_TTS_RESPONSE),
                (None, EVENT_TTS_END),
            ]
        )
        clock = iter([10.0, 10.25])
        monkeypatch.setattr(
            "soniox_tts.extension.monotonic", lambda: next(clock)
        )

        await extension.request_tts(
            TTSTextInput(
                request_id="request-1", text="hello", text_input_end=True
            )
        )

        extension.send_tts_audio_start.assert_awaited_once()
        assert extension.send_tts_audio_data.await_count == 2
        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["request_id"] == "request-1"
        assert end["request_total_audio_duration_ms"] == 10
        assert end["request_event_interval_ms"] == 250
        assert end["reason"] == TTSAudioEndReason.REQUEST_END
        extension.finish_request.assert_awaited_once()

    asyncio.run(run())


def test_empty_final_request_has_no_audio_start():
    async def run():
        extension = make_extension([(None, EVENT_TTS_END)])
        await extension.request_tts(
            TTSTextInput(request_id="empty", text="", text_input_end=True)
        )

        extension.send_tts_audio_start.assert_not_awaited()
        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["request_total_audio_duration_ms"] == 0
        assert end["request_event_interval_ms"] == 0

    asyncio.run(run())


def test_dump_contains_emitted_pcm(tmp_path):
    async def run():
        audio = b"\x00\x01" * 20
        extension = make_extension(
            [
                (100, EVENT_TTS_TTFB_METRIC),
                (audio, EVENT_TTS_RESPONSE),
                (None, EVENT_TTS_END),
            ]
        )
        extension.config.dump = True
        extension.config.dump_path = str(tmp_path)
        await extension.request_tts(
            TTSTextInput(request_id="dump", text="hello", text_input_end=True)
        )

        dump_path = tmp_path / "soniox_dump_dump.pcm"
        assert dump_path.read_bytes() == audio

    asyncio.run(run())


def test_sequential_requests_reset_audio_state():
    async def run():
        extension = make_extension([])
        request_ids = []

        async def iter_events(_stream_id):
            yield 100, EVENT_TTS_TTFB_METRIC
            yield b"\x00\x01" * 120, EVENT_TTS_RESPONSE
            yield None, EVENT_TTS_END

        extension.client.iter_events = iter_events
        for request_id in ("first", "second"):
            await extension.request_tts(
                TTSTextInput(
                    request_id=request_id,
                    text="hello",
                    text_input_end=True,
                )
            )
            request_ids.append(
                extension.send_tts_audio_end.await_args.kwargs["request_id"]
            )

        assert request_ids == ["first", "second"]
        assert extension.send_tts_audio_end.await_count == 2
        assert extension.finish_request.await_count == 2

    asyncio.run(run())


def test_partial_audio_error_finishes_once_with_partial_duration():
    async def run():
        audio = b"\x00\x01" * 120
        extension = make_extension(
            [
                (100, EVENT_TTS_TTFB_METRIC),
                (audio, EVENT_TTS_RESPONSE),
                (RuntimeError("vendor failure"), EVENT_TTS_ERROR),
            ]
        )
        await extension.request_tts(
            TTSTextInput(request_id="error", text="hello", text_input_end=True)
        )

        assert extension.send_tts_audio_end.await_count == 1
        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["reason"] == TTSAudioEndReason.ERROR
        assert end["request_total_audio_duration_ms"] == 5
        assert extension.finish_request.await_count == 1
        assert extension.finish_request.await_args.kwargs["error"] is not None

    asyncio.run(run())


def test_vendor_request_timeout_finishes_with_error():
    async def run():
        extension = make_extension(
            [
                (100, EVENT_TTS_TTFB_METRIC),
                (b"\x00\x01" * 120, EVENT_TTS_RESPONSE),
                (
                    SonioxTTSError(
                        408,
                        "request_timeout",
                        "stream timed out",
                    ),
                    EVENT_TTS_ERROR,
                ),
            ]
        )
        await extension.request_tts(
            TTSTextInput(
                request_id="timeout", text="hello", text_input_end=False
            )
        )
        if extension._stream_task:
            await extension._stream_task

        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["reason"] == TTSAudioEndReason.ERROR
        extension.client.stop.assert_awaited_once()
        assert extension.finish_request.await_args.kwargs["error"] is not None

    asyncio.run(run())


def test_whitespace_fragment_is_sent_with_active_stream():
    async def run():
        extension = make_extension([])
        extension.current_request_id = "append"
        extension.current_stream_id = "stream-append"

        for text in ("hello", " ", "world"):
            await extension.request_tts(
                TTSTextInput(
                    request_id="append",
                    text=text,
                    text_input_end=False,
                )
            )

        assert [
            call.args[0] for call in extension.client.send_text.await_args_list
        ] == ["hello", " ", "world"]

    asyncio.run(run())


def test_partial_audio_flush_and_next_request_recover():
    async def run():
        audio_ready = asyncio.Event()
        release_audio = asyncio.Event()
        extension = make_extension([])

        async def iter_events(_stream_id):
            if extension.current_request_id == "first":
                yield 10, EVENT_TTS_TTFB_METRIC
                yield b"\x00\x01" * 120, EVENT_TTS_RESPONSE
                audio_ready.set()
                await release_audio.wait()
                return
            yield 10, EVENT_TTS_TTFB_METRIC
            yield b"\x00\x01" * 120, EVENT_TTS_RESPONSE
            yield None, EVENT_TTS_END

        extension.client.iter_events = iter_events
        await extension.request_tts(
            TTSTextInput(request_id="first", text="first", text_input_end=False)
        )
        await asyncio.wait_for(audio_ready.wait(), timeout=1)
        await extension.cancel_tts()

        interrupted = extension.send_tts_audio_end.await_args.kwargs
        assert interrupted["request_id"] == "first"
        assert interrupted["reason"] == TTSAudioEndReason.INTERRUPTED
        assert interrupted["request_total_audio_duration_ms"] == 5

        await extension.request_tts(
            TTSTextInput(
                request_id="second", text="second", text_input_end=True
            )
        )

        assert extension.send_tts_audio_end.await_count == 2
        assert (
            extension.send_tts_audio_end.await_args_list[1].kwargs["request_id"]
            == "second"
        )

    asyncio.run(run())


def test_late_stream_audio_after_cancel_is_discarded():
    async def run():
        extension = make_extension(
            [
                (1, EVENT_TTS_TTFB_METRIC),
                (b"\x00\x01" * 20, EVENT_TTS_RESPONSE),
            ]
        )
        extension.current_request_id = "cancelled"
        extension._terminal_sent = True

        await extension._consume_stream("cancelled", "old-stream")

        extension.send_tts_audio_data.assert_not_awaited()
        extension.send_tts_audio_end.assert_not_awaited()

    asyncio.run(run())


def test_dump_flush_failure_still_finishes_request():
    async def run():
        extension = make_extension([(None, EVENT_TTS_END)])
        extension.config.dump = True
        recorder = MagicMock()
        recorder.flush = AsyncMock(side_effect=OSError("disk full"))
        extension.recorder_map["dump-failure"] = recorder
        extension.send_tts_error = AsyncMock()

        await extension.request_tts(
            TTSTextInput(
                request_id="dump-failure",
                text="hello",
                text_input_end=True,
            )
        )

        extension.finish_request.assert_awaited_once()
        assert extension.finish_request.await_args.kwargs["error"] is not None

    asyncio.run(run())


def test_dump_is_flushed_after_stream_error(tmp_path):
    async def run():
        audio = b"\x00\x01" * 20
        extension = make_extension(
            [
                (audio, EVENT_TTS_RESPONSE),
                (
                    SonioxTTSError(500, "internal_error", "vendor failure"),
                    EVENT_TTS_ERROR,
                ),
            ]
        )
        extension.config.dump = True
        extension.config.dump_path = str(tmp_path)

        await extension.request_tts(
            TTSTextInput(
                request_id="dump-error", text="hello", text_input_end=False
            )
        )
        if extension._stream_task:
            await extension._stream_task

        assert (tmp_path / "soniox_dump_dump-error.pcm").read_bytes() == audio
        extension.finish_request.assert_awaited_once()

    asyncio.run(run())


def test_dump_is_flushed_after_cancellation(tmp_path):
    async def run():
        audio_ready = asyncio.Event()
        release = asyncio.Event()
        audio = b"\x00\x01" * 20
        extension = make_extension([])
        extension.config.dump = True
        extension.config.dump_path = str(tmp_path)

        async def iter_events(_stream_id):
            yield audio, EVENT_TTS_RESPONSE
            audio_ready.set()
            await release.wait()

        extension.client.iter_events = iter_events
        await extension.request_tts(
            TTSTextInput(
                request_id="dump-cancel", text="hello", text_input_end=False
            )
        )
        await audio_ready.wait()
        await extension.cancel_tts()
        release.set()

        assert (tmp_path / "soniox_dump_dump-cancel.pcm").read_bytes() == audio

    asyncio.run(run())


def test_audio_end_failure_still_finishes_request():
    async def run():
        extension = make_extension([(None, EVENT_TTS_END)])
        extension.send_tts_audio_end = AsyncMock(
            side_effect=OSError("downstream unavailable")
        )

        await extension.request_tts(
            TTSTextInput(
                request_id="audio-end-failure",
                text="hello",
                text_input_end=True,
            )
        )

        extension.finish_request.assert_awaited_once()
        error = extension.finish_request.await_args.kwargs["error"]
        assert error is not None
        assert "audio_end" in error.message

    asyncio.run(run())


def test_cancellation_wins_over_late_normal_termination():
    async def run():
        end_ready = asyncio.Event()
        release = asyncio.Event()
        extension = make_extension([])

        async def iter_events(_stream_id):
            yield b"\x00\x01" * 20, EVENT_TTS_RESPONSE
            end_ready.set()
            await release.wait()
            yield None, EVENT_TTS_END

        extension.client.iter_events = iter_events
        extension._cancel_stream_task = AsyncMock()
        await extension.request_tts(
            TTSTextInput(request_id="race", text="hello", text_input_end=False)
        )
        await end_ready.wait()
        await extension.cancel_tts()
        release.set()
        await extension._stream_task

        assert extension.send_tts_audio_end.await_count == 1
        assert (
            extension.send_tts_audio_end.await_args.kwargs["reason"]
            == TTSAudioEndReason.INTERRUPTED
        )

    asyncio.run(run())


def test_vendor_error_emits_ten_error_and_audio_end():
    async def run():
        extension = make_extension(
            [
                (
                    SonioxTTSError(401, "unauthenticated", "invalid key"),
                    EVENT_TTS_ERROR,
                )
            ]
        )
        extension.ten_env.send_data = AsyncMock()
        extension.ten_env.log_info = MagicMock()
        extension.ten_env.log_debug = MagicMock()
        extension.ten_env.log_warn = MagicMock()
        extension.ten_env.log_error = MagicMock()
        extension.send_tts_audio_end = (
            AsyncTTS2BaseExtension.send_tts_audio_end.__get__(
                extension, SonioxTTSExtension
            )
        )
        extension.send_tts_error = (
            AsyncTTS2BaseExtension.send_tts_error.__get__(
                extension, SonioxTTSExtension
            )
        )
        extension.finish_request = (
            AsyncTTS2BaseExtension.finish_request.__get__(
                extension, SonioxTTSExtension
            )
        )

        await extension.request_tts(
            TTSTextInput(
                request_id="vendor-error", text="hello", text_input_end=True
            )
        )

        names = [
            call.args[0].get_name()
            for call in extension.ten_env.send_data.await_args_list
        ]
        assert names == ["tts_audio_end", "error"]
        error_payload = extension.ten_env.send_data.await_args_list[1].args[0]
        payload, payload_error = error_payload.get_property_to_json("")
        assert payload_error is None
        assert "invalid key" in payload

    asyncio.run(run())


def test_shutdown_cancels_pending_request_operation():
    async def run():
        started = asyncio.Event()
        extension = make_extension([])
        client = extension.client

        async def pending_operation():
            started.set()
            await asyncio.Event().wait()

        operation_task = asyncio.create_task(pending_operation())
        extension._request_operation_task = operation_task
        await started.wait()

        with patch.object(AsyncTTS2BaseExtension, "on_stop", new=AsyncMock()):
            await extension.on_stop(extension.ten_env)

        assert operation_task.cancelled()
        client.stop.assert_awaited_once()

    asyncio.run(run())


def test_auth_connection_error_is_fatal_and_has_vendor_info():
    extension = SonioxTTSExtension("soniox")
    error = extension._connection_error(
        SonioxTTSConnectionException(401, "unauthenticated")
    )

    assert error.code == -1000
    assert error.vendor_info.vendor == "soniox"
    assert error.vendor_info.code == "401"


@pytest.mark.parametrize("sample_rate", [16000, 24000])
def test_output_frame_metadata_matches_configured_sample_rate(sample_rate):
    async def run():
        extension = SonioxTTSExtension("soniox")
        extension.config = SonioxTTSConfig(
            api_key="key", sample_rate=sample_rate
        )
        extension.ten_env = MagicMock()
        extension.ten_env.send_audio_frame = AsyncMock()
        extension.current_request_id = "frame"
        extension.current_audio_request_id = "frame"
        extension._audio_start_sent = True
        extension.send_tts_audio_data = (
            AsyncTTS2BaseExtension.send_tts_audio_data.__get__(
                extension, SonioxTTSExtension
            )
        )

        await extension._emit_audio(b"\x00\x01" * 240)

        frame = extension.ten_env.send_audio_frame.await_args.args[0]
        assert frame.get_sample_rate() == sample_rate
        assert frame.get_bytes_per_sample() == 2
        assert frame.get_number_of_channels() == 1
        assert len(frame.get_buf()) == 480

    asyncio.run(run())


def test_cancel_interrupts_stream_and_reports_emitted_audio():
    async def run():
        release = asyncio.Event()

        async def pending_events(_stream_id):
            await release.wait()
            if False:
                yield None, EVENT_TTS_END

        extension = make_extension([])
        extension.client.iter_events = pending_events
        await extension.request_tts(
            TTSTextInput(
                request_id="cancel", text="hello", text_input_end=False
            )
        )
        await asyncio.sleep(0)
        await extension.cancel_tts()

        extension.client.cancel.assert_awaited_once()
        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["reason"] == TTSAudioEndReason.INTERRUPTED
        assert end["request_total_audio_duration_ms"] == 0

    asyncio.run(run())


def test_cancel_during_stream_setup_interrupts_request():
    async def run():
        setup_started = asyncio.Event()
        release_setup = asyncio.Event()
        extension = make_extension([])

        async def start_stream(_stream_id):
            setup_started.set()
            await release_setup.wait()

        extension.client.start_stream = start_stream
        request_task = asyncio.create_task(
            extension.request_tts(
                TTSTextInput(
                    request_id="connecting",
                    text="hello",
                    text_input_end=False,
                )
            )
        )
        await setup_started.wait()
        await extension.cancel_tts()
        release_setup.set()
        with suppress(asyncio.CancelledError):
            await request_task

        extension.client.cancel.assert_awaited_once()
        end = extension.send_tts_audio_end.await_args.kwargs
        assert end["reason"] == TTSAudioEndReason.INTERRUPTED
        extension.client.send_text.assert_not_awaited()

    asyncio.run(run())


def test_terminated_fragment_releases_input_queue_ownership():
    async def run():
        extension = make_extension([])
        extension.finish_request = (
            AsyncTTS2BaseExtension.finish_request.__get__(
                extension, SonioxTTSExtension
            )
        )
        extension.ten_env.log_info = lambda *args, **kwargs: None
        extension.ten_env.log_debug = lambda *args, **kwargs: None
        extension.ten_env.log_warn = lambda *args, **kwargs: None
        extension.ten_env.log_error = lambda *args, **kwargs: None
        extension.send_tts_error = AsyncMock()

        b_finished = asyncio.Event()
        a_error_sent = asyncio.Event()

        async def iter_events(_stream_id):
            if extension.current_request_id == "A":
                a_error_sent.set()
                yield (
                    SonioxTTSError(500, "internal_error", "temporary"),
                    EVENT_TTS_ERROR,
                )
                return
            yield 1, EVENT_TTS_TTFB_METRIC
            yield b"\x00\x01" * 120, EVENT_TTS_RESPONSE
            b_finished.set()
            yield None, EVENT_TTS_END

        extension.client.iter_events = iter_events
        extension.client.stop = AsyncMock()

        queue_task = asyncio.create_task(
            extension._process_input_queue(extension.ten_env)
        )
        await extension.input_queue.put(
            TTSTextInput(request_id="A", text="first", text_input_end=False)
        )
        while not a_error_sent.is_set():
            await asyncio.sleep(0)
        await extension.input_queue.put(
            TTSTextInput(request_id="A", text="", text_input_end=True)
        )
        await extension.input_queue.put(
            TTSTextInput(request_id="B", text="second", text_input_end=True)
        )

        await asyncio.wait_for(b_finished.wait(), timeout=1)
        queue_task.cancel()
        with suppress(asyncio.CancelledError):
            await queue_task

        assert extension.send_tts_audio_end.await_count == 2
        assert (
            extension.send_tts_audio_end.await_args_list[0].kwargs["request_id"]
            == "A"
        )
        assert (
            extension.send_tts_audio_end.await_args_list[1].kwargs["request_id"]
            == "B"
        )

    asyncio.run(run())
