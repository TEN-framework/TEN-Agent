import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
from typing import Any

import pytest
from pytest_ten import TenTestContext, ten_test
from ten_ai_base.struct import TTSFlush, TTSTextInput
from ten_runtime import Data
from websockets.sync.server import Server, ServerConnection, serve


def _find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


SERVER_PORT = _find_available_port()
DUMP_PATH = Path(tempfile.gettempdir()) / f"cosy-tts-dump-{os.getpid()}"


class FakeDashScopeServer:
    """Exercise the provider protocol while recording WebSocket reuse."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.connection_count = 0
        self.task_ids: list[str] = []
        self.fail_next_task = False
        self.fail_error_code = "InvalidParameter"
        self.fail_error_message = "invalid voice"
        self.close_on_finish = False
        self.first_audio_delay = 0.0
        self.audio_chunk_interval = 0.0
        self.audio_chunk_count = 1
        self.task_parameters: list[dict[str, Any]] = []
        self.usage_character_counts: list[int] = []
        self.finish_task_delay = 0.0
        self.finish_task_received = threading.Event()
        self._server: Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._connections: set[ServerConnection] = set()
        self._connections_lock = threading.Lock()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(0.5)
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        with self._connections_lock:
            connections = list(self._connections)
        for connection in connections:
            connection.close()
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=0.5)

    def _run(self) -> None:
        try:
            with serve(self._handle, "127.0.0.1", self.port) as server:
                self._server = server
                self._ready.set()
                server.serve_forever()
        except Exception as exc:
            self._error = exc
            self._ready.set()

    def _handle(self, websocket: ServerConnection) -> None:
        self.connection_count += 1
        with self._connections_lock:
            self._connections.add(websocket)
        try:
            for raw_message in websocket:
                match raw_message:
                    case str():
                        pass
                    case _:
                        continue
                message = json.loads(raw_message)
                header = message["header"]
                action = header["action"]
                task_id = header["task_id"]

                match action:
                    case "run-task":
                        self.task_ids.append(task_id)
                        self.task_parameters.append(
                            message["payload"]["parameters"]
                        )
                        websocket.send(self._event("task-started", task_id))
                    case "continue-task":
                        text = message["payload"]["input"]["text"]
                        if self.first_audio_delay > 0:
                            time.sleep(self.first_audio_delay)
                        for chunk_index in range(self.audio_chunk_count):
                            websocket.send(b"\x01\x00" * 160)
                            if chunk_index + 1 < self.audio_chunk_count:
                                time.sleep(self.audio_chunk_interval)
                        usage_counts = self.usage_character_counts or [
                            len(text)
                        ]
                        for character_count in usage_counts:
                            websocket.send(
                                self._event(
                                    "result-generated",
                                    task_id,
                                    payload={
                                        "usage": {"characters": character_count}
                                    },
                                ),
                            )
                    case "finish-task":
                        self.finish_task_received.set()
                        if self.finish_task_delay > 0:
                            time.sleep(self.finish_task_delay)
                        if self.close_on_finish:
                            websocket.close()
                        elif self.fail_next_task:
                            self.fail_next_task = False
                            websocket.send(
                                self._event(
                                    "task-failed",
                                    task_id,
                                    error_code=self.fail_error_code,
                                    error_message=self.fail_error_message,
                                ),
                            )
                            websocket.close()
                        else:
                            websocket.send(
                                self._event("task-finished", task_id)
                            )
        finally:
            with self._connections_lock:
                self._connections.discard(websocket)

    @staticmethod
    def _event(
        event: str,
        task_id: str,
        payload: dict[str, Any] | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> str:
        header = {"event": event, "task_id": task_id}
        if error_code:
            header["error_code"] = error_code
        if error_message:
            header["error_message"] = error_message
        return json.dumps(
            {
                "header": header,
                "payload": payload or {},
            },
        )


@pytest.fixture
def dashscope_server() -> FakeDashScopeServer:
    server = FakeDashScopeServer(SERVER_PORT)
    server.start()
    try:
        yield server
    finally:
        server.stop()


PROPERTY_JSON = json.dumps(
    {
        "params": {
            "api_key": "test-key",
            "model": "cosyvoice-v3-flash",
            "pool_size": 1,
            "sample_rate": 16000,
            "url": f"ws://127.0.0.1:{SERVER_PORT}",
            "voice": "longanyang",
        },
    },
)


async def _synthesize(
    ctx: TenTestContext,
    request_id: str,
    text: str,
    audio_timeout: float = 0.5,
) -> dict[str, Any]:
    request = TTSTextInput(
        request_id=request_id,
        text=text,
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=audio_timeout)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    payload_dict = json.loads(payload)
    assert payload_dict["request_id"] == request_id
    return payload_dict


async def _collect_audio_frames(
    ctx: TenTestContext,
    count: int,
    timeout: float = 0.5,
) -> list[int]:
    sizes: list[int] = []
    for _ in range(count):
        frame = await ctx.expect_audio_frame(timeout=timeout)
        buffer = frame.lock_buf()
        try:
            sizes.append(len(bytes(buffer)))
        finally:
            frame.unlock_buf(buffer)
    return sizes


async def _expect_metrics(
    ctx: TenTestContext,
    metric_name: str,
) -> dict[str, Any]:
    while True:
        data = await ctx.expect_data("metrics", timeout=0.5)
        payload, error = data.get_property_to_json("")
        assert error is None
        metrics = json.loads(payload)
        if metric_name in metrics["metrics"]:
            return metrics


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_sequential_tasks_reuse_preconnected_pool(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    first_request = TTSTextInput(
        request_id="request-0",
        text="sequential request 0",
        text_input_end=True,
    )
    first_data = Data.create("tts_text_input")
    first_data.set_property_from_json("", first_request.model_dump_json())
    await ctx.send_data(first_data)
    connect_metrics = await _expect_metrics(ctx, "connect_delay")
    assert connect_metrics["metrics"]["connect_delay"] >= 0
    await ctx.expect_audio_frame(timeout=0.5)
    await ctx.expect_data("tts_audio_end", timeout=0.5)

    for task_index in range(1, 5):
        await _synthesize(
            ctx,
            f"request-{task_index}",
            f"sequential request {task_index}",
        )

    assert dashscope_server.connection_count == 2
    assert len(dashscope_server.task_ids) == 5
    assert len(set(dashscope_server.task_ids)) == 5


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_failed_connection_is_replaced_for_next_task(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.fail_next_task = True

    await _synthesize(ctx, "failed-request", "first")
    await _synthesize(ctx, "recovered-request", "second")

    assert dashscope_server.connection_count == 2
    assert len(dashscope_server.task_ids) == 2


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_cancelled_task_reuses_connection_after_task_finished(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    request = TTSTextInput(
        request_id="cancelled-request",
        text="cancel me",
        text_input_end=False,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)
    await ctx.expect_audio_frame(timeout=0.5)

    flush = Data.create("tts_flush")
    flush.set_property_from_json(
        "",
        TTSFlush(flush_id="flush-1").model_dump_json(),
    )
    await ctx.send_data(flush)
    await ctx.expect_data("tts_flush_end", timeout=0.5)

    await _synthesize(ctx, "request-after-cancel", "second")

    assert dashscope_server.connection_count == 2
    assert len(dashscope_server.task_ids) == 2


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_finalizing_request_does_not_block_next_request_after_flush(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.finish_task_delay = 0.4
    request_id = "interrupted-finalizing-request"

    for text, text_input_end in (("first", False), ("", True)):
        request = TTSTextInput(
            request_id=request_id,
            text=text,
            text_input_end=text_input_end,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json("", request.model_dump_json())
        await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=0.5)
    finish_started = await asyncio.to_thread(
        dashscope_server.finish_task_received.wait,
        0.5,
    )
    assert finish_started

    flush = Data.create("tts_flush")
    flush.set_property_from_json(
        "",
        TTSFlush(flush_id="flush-finalizing").model_dump_json(),
    )
    await ctx.send_data(flush)
    await ctx.expect_data("tts_flush_end", timeout=0.2)

    dashscope_server.finish_task_delay = 0.0
    next_request = TTSTextInput(
        request_id="request-after-finalizing-cancel",
        text="second",
        text_input_end=True,
    )
    next_data = Data.create("tts_text_input")
    next_data.set_property_from_json("", next_request.model_dump_json())
    await ctx.send_data(next_data)

    await ctx.expect_audio_frame(timeout=0.5)


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_audio_end_interval_excludes_ttfb(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.first_audio_delay = 0.2
    dashscope_server.audio_chunk_interval = 0.04
    dashscope_server.audio_chunk_count = 3

    payload = await _synthesize(
        ctx,
        "interval-request",
        "measure interval",
        audio_timeout=1.0,
    )
    interval_ms = payload["request_event_interval_ms"]

    assert 40 <= interval_ms < 180, (
        "Expected the audio receive window to include chunk spacing but exclude "
        f"the 200ms TTFB, got {interval_ms}ms"
    )


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_audio_end_accounts_emitted_pcm_and_monotonic_interval(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
    monotonic_clock,
) -> None:
    monotonic_clock(100.0, 100.25)
    dashscope_server.audio_chunk_count = 3

    request = TTSTextInput(
        request_id="accounting-success",
        text="three audio chunks",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    frame_sizes = await _collect_audio_frames(ctx, 3)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    end = json.loads(payload)

    emitted_bytes = sum(frame_sizes)
    assert emitted_bytes == 3 * 320
    assert end["request_total_audio_duration_ms"] == 30
    assert end["request_event_interval_ms"] == 250


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_partial_audio_error_accounts_only_emitted_pcm(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.audio_chunk_count = 2
    dashscope_server.fail_next_task = True

    request = TTSTextInput(
        request_id="partial-error",
        text="partial audio error",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    frame_sizes = await _collect_audio_frames(ctx, 2)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    end = json.loads(payload)
    assert end["reason"] == 3
    assert end["request_total_audio_duration_ms"] == 20
    assert sum(frame_sizes) == 2 * 320

    await ctx.expect_data("error", timeout=0.5)
    await ctx.assert_no_data("tts_audio_end", timeout=0.2)


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_flush_accounts_emitted_pcm_and_terminates_once(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.audio_chunk_count = 2
    request = TTSTextInput(
        request_id="flush-accounting",
        text="flush after audio",
        text_input_end=False,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    frame_sizes = await _collect_audio_frames(ctx, 2)
    flush = Data.create("tts_flush")
    flush.set_property_from_json(
        "",
        TTSFlush(flush_id="flush-accounting").model_dump_json(),
    )
    await ctx.send_data(flush)

    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    end = json.loads(payload)
    assert end["reason"] == 2
    assert end["request_total_audio_duration_ms"] == 20
    assert sum(frame_sizes) == 2 * 320

    await ctx.expect_data("tts_flush_end", timeout=0.5)
    await ctx.assert_no_data("tts_audio_end", timeout=0.2)
    await ctx.assert_no_audio_frame(timeout=0.2)


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_empty_final_chunk_waits_for_delayed_audio(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.first_audio_delay = 0.1
    request_id = "delayed-audio-request"

    for text, text_input_end in (("stream this text", False), ("", True)):
        request = TTSTextInput(
            request_id=request_id,
            text=text,
            text_input_end=text_input_end,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json("", request.model_dump_json())
        await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=0.5)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    assert json.loads(payload)["request_id"] == request_id


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_audio_end_interval_is_zero_without_audio(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.audio_chunk_count = 0
    request = TTSTextInput(
        request_id="no-audio-request",
        text="no audio",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    end = json.loads(payload)
    assert end["request_event_interval_ms"] == 0
    assert end["request_total_audio_duration_ms"] == 0


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **json.loads(PROPERTY_JSON)["params"],
                "instruction": "speak happily",
                "enable_markdown_filter": True,
                "future_protocol_parameter": "future-value",
            },
        },
    ),
    timeout=1.5,
)
async def test_provider_params_are_forwarded_to_sdk(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    await _synthesize(ctx, "params-request", "forward params")

    parameters = dashscope_server.task_parameters[0]
    assert parameters["instruction"] == "speak happily"
    assert parameters["enable_markdown_filter"] is True
    assert parameters["future_protocol_parameter"] == "future-value"
    assert "api_key" not in parameters
    assert "pool_size" not in parameters
    assert "url" not in parameters


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **json.loads(PROPERTY_JSON)["params"],
                "speech_rate": 2.0,
                "pitch_rate": 0.5,
                "volume": 70,
                "seed": 7,
                "instruction": "speak happily",
                "language_hints": ["zh"],
                "hot_fix": {"replace": [{"今天": "金天"}]},
                "enable_markdown_filter": True,
                "bit_rate": 128,
            },
        },
    ),
    timeout=1.5,
)
async def test_speech_rate_is_sent_as_provider_rate(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    await _synthesize(ctx, "rate-request", "forward speech rate")

    parameters = dashscope_server.task_parameters[0]
    # The SDK maps its constructor arguments onto the wire parameters.
    assert parameters["rate"] == 2.0
    assert parameters["pitch"] == 0.5
    assert parameters["volume"] == 70
    assert parameters["seed"] == 7
    assert parameters["instruction"] == "speak happily"
    assert parameters["language_hints"] == ["zh"]
    # Documented `additional_params` entries stay on the wire as they are.
    assert parameters["hot_fix"] == {"replace": [{"今天": "金天"}]}
    assert parameters["enable_markdown_filter"] is True
    assert parameters["bit_rate"] == 128
    # Constructor arguments must not leak as unknown protocol parameters.
    assert "speech_rate" not in parameters
    assert "pitch_rate" not in parameters


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **json.loads(PROPERTY_JSON)["params"],
                "sample_rate": 12345,
            },
        },
    ),
    timeout=1.5,
)
async def test_invalid_sample_rate_reports_fatal_error(
    ctx: TenTestContext,
) -> None:
    error_data = await ctx.expect_data("error", timeout=0.5)
    payload, error = error_data.get_property_to_json("")
    assert error is None
    error_payload = json.loads(payload)
    assert error_payload["code"] == -1000
    assert error_payload["module"] == "tts"


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **json.loads(PROPERTY_JSON)["params"],
                "enable_ssml": True,
                "format": "mp3",
            },
        },
    ),
    timeout=1.5,
)
async def test_unsupported_controls_are_ignored(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    await _synthesize(ctx, "ignored-controls-request", "stream this text")

    parameters = dashscope_server.task_parameters[0]
    assert "enable_ssml" not in parameters
    assert parameters["format"] == "pcm"


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            "params": {
                **json.loads(PROPERTY_JSON)["params"],
                "sample_rate": 24000,
            },
        },
    ),
    timeout=1.5,
)
async def test_configured_sample_rate_is_used_for_sdk_and_audio_frame(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    request = TTSTextInput(
        request_id="sample-rate-request",
        text="sample rate",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    audio_frame = await ctx.expect_audio_frame(timeout=0.5)
    assert audio_frame.get_sample_rate() == 24000
    await ctx.expect_data("tts_audio_end", timeout=0.5)
    assert dashscope_server.task_parameters[0]["sample_rate"] == 24000


@pytest.fixture
def dump_path() -> Path:
    shutil.rmtree(DUMP_PATH, ignore_errors=True)
    DUMP_PATH.mkdir(parents=True)
    try:
        yield DUMP_PATH
    finally:
        shutil.rmtree(DUMP_PATH, ignore_errors=True)


@ten_test(
    "cosy_tts_python",
    property_json_str=json.dumps(
        {
            **json.loads(PROPERTY_JSON),
            "dump": True,
            "dump_path": str(DUMP_PATH),
        },
    ),
    timeout=1.5,
)
async def test_dump_flushes_complete_pcm_before_audio_end(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
    dump_path: Path,
) -> None:
    dashscope_server.audio_chunk_count = 3
    await _synthesize(ctx, "dump-request", "dump audio")

    dump_files = list(dump_path.glob("*.pcm"))
    assert len(dump_files) == 1
    assert dump_files[0].read_bytes() == b"\x01\x00" * 160 * 3


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_usage_uses_provider_cumulative_total_once(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.usage_character_counts = [5, 10]

    await _synthesize(ctx, "usage-request", "ten chars!")
    metrics = await _expect_metrics(ctx, "input_characters")

    assert metrics["metrics"]["input_characters"] == 10


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=1.5,
)
async def test_task_failed_reports_vendor_error_and_finishes_request(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.fail_next_task = True
    request = TTSTextInput(
        request_id="vendor-error-request",
        text="fail this request",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=0.5)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    audio_end_payload, audio_end_error = audio_end.get_property_to_json("")
    assert audio_end_error is None
    assert json.loads(audio_end_payload)["reason"] == 3

    error_data = await ctx.expect_data("error", timeout=0.5)
    error_payload, error = error_data.get_property_to_json("")
    assert error is None
    parsed_error = json.loads(error_payload)
    assert parsed_error["id"] == "vendor-error-request"
    assert parsed_error["vendor_info"] == {
        "vendor": "cosy",
        "code": "InvalidParameter",
        "message": "invalid voice",
    }


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_quota_failure_is_reported_as_fatal_vendor_error(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.fail_next_task = True
    dashscope_server.fail_error_code = "Arrearage"
    dashscope_server.fail_error_message = "account has an outstanding balance"
    request = TTSTextInput(
        request_id="quota-error",
        text="quota error",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=0.5)
    end = await ctx.expect_data("tts_audio_end", timeout=0.5)
    payload, error = end.get_property_to_json("")
    assert error is None
    assert json.loads(payload)["reason"] == 3

    error_data = await ctx.expect_data("error", timeout=0.5)
    payload, error = error_data.get_property_to_json("")
    assert error is None
    error_payload = json.loads(payload)
    assert error_payload["code"] == -1000
    assert error_payload["vendor_info"]["code"] == "Arrearage"


@ten_test(
    "cosy_tts_python",
    property_json_str=PROPERTY_JSON,
    timeout=2.0,
)
async def test_socket_close_without_task_finished_reports_error(
    ctx: TenTestContext,
    dashscope_server: FakeDashScopeServer,
) -> None:
    dashscope_server.close_on_finish = True
    request = TTSTextInput(
        request_id="socket-close-request",
        text="close without completion",
        text_input_end=True,
    )
    data = Data.create("tts_text_input")
    data.set_property_from_json("", request.model_dump_json())
    await ctx.send_data(data)

    await ctx.expect_audio_frame(timeout=0.5)
    audio_end = await ctx.expect_data("tts_audio_end", timeout=1.0)
    payload, error = audio_end.get_property_to_json("")
    assert error is None
    assert json.loads(payload)["reason"] == 3

    error_data = await ctx.expect_data("error", timeout=1.0)
    payload, error = error_data.get_property_to_json("")
    assert error is None
    assert json.loads(payload)["vendor_info"]["code"] == "ConnectionClosed"

    dashscope_server.close_on_finish = False
    await _synthesize(
        ctx,
        "after-socket-close",
        "replacement connection",
        audio_timeout=1.0,
    )
    assert len(dashscope_server.task_ids) == 2
