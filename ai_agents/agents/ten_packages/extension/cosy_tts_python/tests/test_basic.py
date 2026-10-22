import json
from pathlib import Path
import tempfile

import pytest
from pytest_ten import TenTestContext, ten_test
from ten_ai_base.struct import TTSFlush, TTSTextInput
from ten_runtime import Data

from .test_connection_reuse import (
    PROPERTY_JSON,
    SERVER_PORT,
    FakeDashScopeServer,
)

DUMP_PATH = Path(tempfile.mkdtemp(prefix="cosy-basic-dump-"))


@pytest.fixture
def basic_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture(scope="module", autouse=True)
def ensure_dump_dir():
    DUMP_PATH.mkdir(parents=True, exist_ok=True)
    yield


def _dump_property() -> str:
    return json.dumps(
        {
            **json.loads(PROPERTY_JSON),
            "dump": True,
            "dump_path": str(DUMP_PATH),
        }
    )


async def _send(
    ctx: TenTestContext,
    request_id: str,
    text: str,
    *,
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


async def _collect_frame_sizes(ctx: TenTestContext, count: int) -> list[int]:
    sizes = []
    for _ in range(count):
        frame = await ctx.expect_audio_frame(timeout=0.5)
        buffer = frame.lock_buf()
        try:
            sizes.append(len(bytes(buffer)))
        finally:
            frame.unlock_buf(buffer)
    return sizes


@ten_test(
    "cosy_tts_python",
    property_json_str=_dump_property(),
    timeout=2.0,
)
async def test_dump_flushes_emitted_pcm_on_success(
    ctx: TenTestContext,
    basic_server: FakeDashScopeServer,
) -> None:
    basic_server.audio_chunk_count = 3
    await _send(
        ctx,
        "dump-success",
        "dump three chunks",
        text_input_end=True,
    )
    frames = await _collect_frame_sizes(ctx, 3)
    await ctx.expect_data("tts_audio_end", timeout=0.5)

    dump_files = list(DUMP_PATH.glob("*dump-success*.pcm"))
    assert dump_files
    assert sum(frames) == 3 * 320


@ten_test(
    "cosy_tts_python",
    property_json_str=_dump_property(),
    timeout=2.0,
)
async def test_append_input_accounts_for_all_emitted_pcm(
    ctx: TenTestContext,
    basic_server: FakeDashScopeServer,
) -> None:
    basic_server.audio_chunk_count = 2
    await _send(
        ctx,
        "append-accounting",
        "first part",
        text_input_end=False,
    )
    frames = await _collect_frame_sizes(ctx, 2)
    await _send(ctx, "append-accounting", "", text_input_end=True)

    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    end = json.loads(payload)
    assert sum(frames) == 2 * 320
    assert end["request_total_audio_duration_ms"] == 20


@ten_test(
    "cosy_tts_python",
    property_json_str=_dump_property(),
    timeout=2.0,
)
async def test_dump_is_finalized_on_partial_audio_error(
    ctx: TenTestContext,
    basic_server: FakeDashScopeServer,
) -> None:
    basic_server.audio_chunk_count = 2
    basic_server.fail_next_task = True
    await _send(
        ctx,
        "dump-error",
        "dump partial error",
        text_input_end=True,
    )

    frames = await _collect_frame_sizes(ctx, 2)
    await ctx.expect_data("tts_audio_end", timeout=0.5)
    await ctx.expect_data("error", timeout=0.5)

    dump_files = list(DUMP_PATH.glob("*dump-error*.pcm"))
    assert dump_files
    assert dump_files[-1].read_bytes() == b"\x01\x00" * 320
    assert sum(frames) == 2 * 320


@ten_test(
    "cosy_tts_python",
    property_json_str=_dump_property(),
    timeout=2.0,
)
async def test_flush_finalizes_current_request(
    ctx: TenTestContext,
    basic_server: FakeDashScopeServer,
) -> None:
    basic_server.audio_chunk_count = 2
    await _send(
        ctx,
        "flush-dump",
        "flush this request",
        text_input_end=False,
    )
    await _collect_frame_sizes(ctx, 2)

    flush = Data.create("tts_flush")
    flush.set_property_from_json(
        "",
        TTSFlush(flush_id="flush-dump").model_dump_json(),
    )
    await ctx.send_data(flush)
    await ctx.expect_data("tts_audio_end", timeout=0.5)
    await ctx.expect_data("tts_flush_end", timeout=0.5)

    dump_files = list(DUMP_PATH.glob("*flush-dump*.pcm"))
    assert dump_files
    assert dump_files[-1].read_bytes() == b"\x01\x00" * 320
