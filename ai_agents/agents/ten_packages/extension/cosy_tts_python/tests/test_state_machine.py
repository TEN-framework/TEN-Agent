import json

import pytest
from pytest_ten import TenTestContext, ten_test
from ten_ai_base.struct import TTSTextInput
from ten_runtime import Data

from .test_connection_reuse import (
    PROPERTY_JSON,
    SERVER_PORT,
    FakeDashScopeServer,
)


@pytest.fixture
def state_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


async def _send(
    ctx: TenTestContext,
    request_id: str,
    text: str,
    text_input_end: bool,
) -> None:
    request = TTSTextInput(
        request_id=request_id,
        text=text,
        text_input_end=text_input_end,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_interleaved_request_ids_keep_separate_terminal_events(
    ctx: TenTestContext,
    state_server: FakeDashScopeServer,
) -> None:
    await _send(ctx, "request-a", "first part", False)
    await ctx.expect_audio_frame(timeout=0.5)

    await _send(ctx, "request-b", "next request", True)
    await _send(ctx, "request-a", "", True)

    await ctx.expect_audio_frame(timeout=0.5)

    first_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    second_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    first_payload, first_error = first_end.get_property_to_json("")
    second_payload, second_error = second_end.get_property_to_json("")
    assert first_error is None
    assert second_error is None

    assert json.loads(first_payload)["request_id"] == "request-a"
    assert json.loads(second_payload)["request_id"] == "request-b"
    assert len(state_server.task_ids) == 2


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_sequential_requests_reset_audio_accounting(
    ctx: TenTestContext,
    state_server: FakeDashScopeServer,
) -> None:
    expected_durations = (10, 20)
    for index, duration_ms in enumerate(expected_durations):
        state_server.audio_chunk_count = index + 1
        await _send(
            ctx,
            f"reset-request-{index}",
            f"request {index}",
            True,
        )
        for _ in range(index + 1):
            await ctx.expect_audio_frame(timeout=0.5)
        end = await ctx.expect_data("tts_audio_end", timeout=0.5)
        payload, error = end.get_property_to_json("")
        assert error is None
        assert json.loads(payload)["request_total_audio_duration_ms"] == (
            duration_ms
        )
