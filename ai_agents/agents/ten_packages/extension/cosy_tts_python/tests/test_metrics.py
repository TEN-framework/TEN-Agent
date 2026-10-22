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
def metrics_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


async def _collect_until(
    ctx: TenTestContext,
    metric_name: str,
    timeout: float = 1.0,
) -> tuple[dict, dict]:
    metrics = None
    audio_end = None
    while metrics is None or audio_end is None:
        data = await ctx.expect_data(timeout=timeout)
        if data.get_name() == "tts_audio_end":
            payload, error = data.get_property_to_json("")
            assert error is None
            audio_end = json.loads(payload)
        elif data.get_name() == "metrics":
            payload, error = data.get_property_to_json("")
            assert error is None
            candidate = json.loads(payload)
            if metric_name in candidate["metrics"]:
                metrics = candidate
    assert metrics is not None
    assert audio_end is not None
    return metrics, audio_end


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_ttfb_is_measured_from_vendor_request_to_first_audio(
    ctx: TenTestContext,
    metrics_server: FakeDashScopeServer,
) -> None:
    metrics_server.first_audio_delay = 0.15
    request = TTSTextInput(
        request_id="ttfb-request",
        text="measure ttfb",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=1.0)
    metrics, _ = await _collect_until(ctx, "ttfb")

    assert 100 <= metrics["metrics"]["ttfb"] < 500


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_request_metrics_do_not_leak_between_requests(
    ctx: TenTestContext,
    metrics_server: FakeDashScopeServer,
) -> None:
    for index in range(2):
        request = TTSTextInput(
            request_id=f"metrics-reset-{index}",
            text=f"request {index}",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json("", request.model_dump_json())
        await ctx.send_data(data)
        await ctx.expect_audio_frame(timeout=0.5)
        metrics, _ = await _collect_until(ctx, "output_characters")
        assert metrics["metrics"]["output_characters"] == len(
            f"request {index}"
        )
