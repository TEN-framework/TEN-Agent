import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock

from ten_ai_base.message import TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput

from soniox_tts.config import SonioxTTSConfig
from soniox_tts.extension import SonioxTTSExtension
from soniox_tts.soniox_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_RESPONSE,
    EVENT_TTS_TTFB_METRIC,
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


def test_vendor_request_timeout_completes_stream_normally():
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
        assert end["reason"] == TTSAudioEndReason.REQUEST_END
        extension.client.stop.assert_awaited_once()

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
