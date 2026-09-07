import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from ten_ai_base.message import ModuleErrorCode, TTSAudioEndReason
from ten_ai_base.struct import TTSTextInput

from fish_audio_tts_python.config import FishAudioTTSConfig
from fish_audio_tts_python.extension import FishAudioTTSExtension
from fish_audio_tts_python.fish_audio_tts import (
    EVENT_TTS_END,
    EVENT_TTS_ERROR,
    EVENT_TTS_FLUSH,
    EVENT_TTS_RESPONSE,
)


def _create_extension() -> FishAudioTTSExtension:
    extension = FishAudioTTSExtension("fish_audio_tts_python")
    extension.config = FishAudioTTSConfig(api_key="test-key")
    extension.ten_env = MagicMock()
    extension.client = MagicMock()
    extension.client.cancel = AsyncMock()
    extension.send_tts_audio_end = AsyncMock()
    extension.send_tts_error = AsyncMock()
    extension.finish_request = AsyncMock()
    return extension


def test_cancel_before_first_audio_sends_interrupted_without_finish() -> None:
    async def run_test() -> None:
        extension = _create_extension()
        extension.current_request_id = "interrupted-request"
        extension.current_request_finished = False
        extension.sent_ts = datetime.now()
        assert extension.request_ts is None

        await extension.cancel_tts()

        extension.client.cancel.assert_awaited_once()
        extension.send_tts_audio_end.assert_awaited_once()
        end_args = extension.send_tts_audio_end.await_args.kwargs
        assert end_args["request_id"] == "interrupted-request"
        assert end_args["request_event_interval_ms"] >= 0
        assert end_args["request_total_audio_duration_ms"] == 0
        assert end_args["reason"] == TTSAudioEndReason.INTERRUPTED
        # The base flush path clears request state after cancel_tts returns.
        extension.finish_request.assert_not_awaited()
        assert extension.current_request_finished is True

    asyncio.run(run_test())


def test_request_after_interrupt_still_completes() -> None:
    async def run_test() -> None:
        extension = _create_extension()
        extension.current_request_id = "interrupted-request"
        extension.sent_ts = datetime.now()

        await extension.cancel_tts()
        extension.finish_request.assert_not_awaited()

        extension.send_tts_audio_start = AsyncMock()
        extension.send_tts_ttfb_metrics = AsyncMock()
        extension.send_tts_audio_data = AsyncMock()

        async def audio_stream(_text: str):
            yield b"\x01\x02" * 160, EVENT_TTS_RESPONSE
            yield None, EVENT_TTS_END

        extension.client.get = audio_stream
        await extension.request_tts(
            TTSTextInput(
                request_id="next-request",
                text="next request",
                text_input_end=True,
                metadata={},
            )
        )

        extension.finish_request.assert_awaited_once_with(
            request_id="next-request",
            reason=TTSAudioEndReason.REQUEST_END,
        )
        assert extension.current_request_finished is True

    asyncio.run(run_test())


def test_empty_final_input_completes_without_vendor_call() -> None:
    async def run_test() -> None:
        extension = _create_extension()
        text_input = TTSTextInput(
            request_id="empty-request",
            text=" ",
            text_input_end=True,
            metadata={"session_id": "session", "turn_id": 1},
        )

        await extension.request_tts(text_input)

        extension.client.get.assert_not_called()
        extension.send_tts_error.assert_not_awaited()
        extension.send_tts_audio_end.assert_awaited_once()
        end_args = extension.send_tts_audio_end.await_args.kwargs
        assert end_args["request_id"] == "empty-request"
        assert end_args["request_event_interval_ms"] >= 0
        assert end_args["request_total_audio_duration_ms"] == 0
        assert end_args["reason"] == TTSAudioEndReason.REQUEST_END
        extension.finish_request.assert_awaited_once_with(
            request_id="empty-request",
            reason=TTSAudioEndReason.REQUEST_END,
        )

    asyncio.run(run_test())


def test_non_final_vendor_error_does_not_finish_request() -> None:
    async def run_test() -> None:
        extension = _create_extension()

        async def error_stream(_text: str):
            yield b"temporary failure", EVENT_TTS_ERROR

        extension.client.get = error_stream
        text_input = TTSTextInput(
            request_id="append-request",
            text="first chunk",
            text_input_end=False,
            metadata={"session_id": "session", "turn_id": 1},
        )

        await extension.request_tts(text_input)

        extension.send_tts_error.assert_awaited_once()
        sent_error = extension.send_tts_error.await_args.kwargs["error"]
        assert sent_error.code == int(ModuleErrorCode.NON_FATAL_ERROR.value)
        extension.send_tts_audio_end.assert_not_awaited()
        extension.finish_request.assert_not_awaited()
        assert extension.current_request_finished is False

    asyncio.run(run_test())


def test_append_input_ends_on_final_empty_chunk() -> None:
    async def run_test() -> None:
        extension = _create_extension()
        extension.send_tts_audio_start = AsyncMock()
        extension.send_tts_ttfb_metrics = AsyncMock()
        extension.send_tts_audio_data = AsyncMock()

        async def audio_stream(_text: str):
            yield b"\x01\x02" * 240, EVENT_TTS_RESPONSE
            yield None, EVENT_TTS_END

        extension.client.get = audio_stream
        metadata = {"session_id": "session", "turn_id": 1}

        await extension.request_tts(
            TTSTextInput(
                request_id="append-request",
                text="first chunk",
                text_input_end=False,
                metadata=metadata,
            )
        )
        await extension.request_tts(
            TTSTextInput(
                request_id="append-request",
                text=" ",
                text_input_end=True,
                metadata=metadata,
            )
        )

        extension.send_tts_audio_start.assert_awaited_once_with(
            request_id="append-request"
        )
        extension.send_tts_audio_data.assert_awaited_once()
        extension.send_tts_audio_end.assert_awaited_once()
        end_args = extension.send_tts_audio_end.await_args.kwargs
        assert end_args["request_id"] == "append-request"
        assert end_args["request_total_audio_duration_ms"] == 15
        assert end_args["reason"] == TTSAudioEndReason.REQUEST_END
        extension.finish_request.assert_awaited_once_with(
            request_id="append-request",
            reason=TTSAudioEndReason.REQUEST_END,
        )

    asyncio.run(run_test())


def test_empty_vendor_chunk_waits_for_end_event() -> None:
    async def run_test() -> None:
        extension = _create_extension()

        async def audio_stream(_text: str):
            yield b"", EVENT_TTS_RESPONSE
            yield None, EVENT_TTS_END

        extension.client.get = audio_stream
        await extension.request_tts(
            TTSTextInput(
                request_id="empty-vendor-chunk",
                text="hello",
                text_input_end=True,
                metadata={},
            )
        )

        extension.send_tts_audio_end.assert_awaited_once()
        extension.finish_request.assert_awaited_once_with(
            request_id="empty-vendor-chunk",
            reason=TTSAudioEndReason.REQUEST_END,
        )

    asyncio.run(run_test())


def test_flush_event_does_not_duplicate_cancel_completion() -> None:
    async def run_test() -> None:
        extension = _create_extension()

        async def flush_stream(_text: str):
            yield None, EVENT_TTS_FLUSH

        extension.client.get = flush_stream
        await extension.request_tts(
            TTSTextInput(
                request_id="flush-request",
                text="hello",
                text_input_end=False,
                metadata={},
            )
        )

        extension.send_tts_audio_end.assert_not_awaited()
        extension.finish_request.assert_not_awaited()

    asyncio.run(run_test())
