import asyncio
import json
from typing import Any

from ten_runtime import AudioFrame, Data

from iflytek_asr_python.config import IFlytekAsrConfig
from iflytek_asr_python.extension import IFlytekAsrExtension
from iflytek_asr_python.extension import (
    LOG_CATEGORY_KEY_POINT,
    LOG_CATEGORY_VENDOR,
)
from iflytek_asr_python.protocol import IFlytekProtocolError, parse_response
from iflytek_asr_python.reconnect_manager import ReconnectManager


class FakeTenEnv:
    def __init__(self) -> None:
        self.data: list[Data] = []
        self.logs: list[tuple[str, str, str | None]] = []

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        self.logs.append((level, message, kwargs.get("category")))

    def log_debug(self, message: str, **kwargs: Any) -> None:
        self._log("debug", message, **kwargs)

    def log_info(self, message: str, **kwargs: Any) -> None:
        self._log("info", message, **kwargs)

    def log_warn(self, message: str, **kwargs: Any) -> None:
        self._log("warn", message, **kwargs)

    def log_error(self, message: str, **kwargs: Any) -> None:
        self._log("error", message, **kwargs)

    async def send_data(self, data: Data) -> None:
        self.data.append(data)


class FakeClient:
    def __init__(self, start_errors: list[Exception] | None = None) -> None:
        self.audio: list[bytes] = []
        self.connected = True
        self.finalized = False
        self.start_errors = list(start_errors or [])
        self.start_calls = 0

    async def start(self) -> None:
        self.start_calls += 1
        if self.start_errors:
            self.connected = False
            raise self.start_errors.pop(0)
        self.connected = True

    async def stop(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    async def send_audio(self, audio: bytes) -> bool:
        self.audio.append(audio)
        return True

    async def finalize(self) -> bool:
        self.finalized = True
        return True


def create_extension() -> tuple[IFlytekAsrExtension, FakeTenEnv, FakeClient]:
    extension = IFlytekAsrExtension("iflytek")
    ten_env = FakeTenEnv()
    client = FakeClient()
    extension.ten_env = ten_env  # type: ignore[assignment]
    extension.config = IFlytekAsrConfig(
        params={
            "url": "ws://127.0.0.1:9990/tuling/ast/v3",
            "biz_id": "tenant-1",
            "sample_rate": 16000,
            "language": "zh",
        }
    )
    extension.client = client  # type: ignore[assignment]
    extension._should_reconnect = False
    return extension, ten_env, client


def data_as_dict(data: Data) -> dict[str, Any]:
    value, error = data.get_property_to_json()
    assert error is None
    return json.loads(value)


def test_extension_sends_audio_frame_bytes() -> None:
    async def run() -> None:
        extension, _, client = create_extension()
        frame = AudioFrame.create("pcm_frame")
        frame.alloc_buf(320)
        buffer = frame.lock_buf()
        buffer[:] = b"\x01\x02" * 160
        frame.unlock_buf(buffer)

        assert await extension.send_audio(frame, "session-1") is True
        assert client.audio == [b"\x01\x02" * 160]
        assert extension.audio_timeline.total_user_audio_duration == 10

    asyncio.run(run())


def test_extension_outputs_ten_result_and_finalize_end() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        extension.metadata = {"session_id": "session-1"}
        extension.finalize_id = "finalize-1"
        extension._finalize_pending = True
        response = parse_response(
            {
                "header": {
                    "code": 0,
                    "status": 2,
                    "sid": "AST-1",
                    "traceId": "trace-1",
                },
                "payload": {
                    "result": {
                        "bg": 100,
                        "ed": 500,
                        "ls": True,
                        "msgtype": "sentence",
                        "ws": [{"cw": [{"w": "你好", "wb": 10, "we": 50}]}],
                    }
                },
            },
            language="zh",
        )

        await extension.on_response(response)

        assert [data.get_name() for data in ten_env.data] == [
            "asr_result",
            "asr_finalize_end",
        ]
        result = data_as_dict(ten_env.data[0])
        assert result["text"] == "你好"
        assert result["final"] is True
        assert result["start_ms"] == 100
        assert result["duration_ms"] == 400
        assert result["metadata"]["session_id"] == "session-1"
        assert result["metadata"]["asr_info"]["vendor"] == "iflytek"
        assert result["metadata"]["asr_info"]["sid"] == "AST-1"

        finalized = data_as_dict(ten_env.data[1])
        assert finalized["finalize_id"] == "finalize-1"
        assert finalized["metadata"]["session_id"] == "session-1"

    asyncio.run(run())


def test_extension_reports_vendor_error_details() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        await extension.on_error(
            IFlytekProtocolError(
                "1", "unknown error", sid="AST-1", trace_id="trace-1"
            )
        )

        assert len(ten_env.data) == 1
        error = data_as_dict(ten_env.data[0])
        assert error["module"] == "asr"
        assert error["code"] == 1000
        assert error["vendor_info"] == {
            "vendor": "iflytek",
            "code": "1",
            "message": "unknown error",
        }

    asyncio.run(run())


def test_extension_completes_finalize_when_connection_closes_early() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        extension.metadata = {"session_id": "session-1"}
        extension.finalize_id = "finalize-1"
        extension._finalize_pending = True

        await extension.on_closed(terminal_received=False)

        assert extension._finalize_pending is False
        assert [data.get_name() for data in ten_env.data] == [
            "asr_finalize_end"
        ]
        finalized = data_as_dict(ten_env.data[0])
        assert finalized["finalize_id"] == "finalize-1"

    asyncio.run(run())


def test_extension_uses_ten_megabyte_audio_buffer() -> None:
    extension, _, _ = create_extension()

    strategy = extension.buffer_strategy()

    assert strategy.byte_limit == 10 * 1024 * 1024


def test_extension_logs_only_redacted_configuration() -> None:
    extension, ten_env, _ = create_extension()
    assert extension.config is not None
    extension.config.app_id = "sensitive-app-id"
    extension.config.biz_id = "sensitive-business-id"
    extension.config.engine = {
        "private_vendor_option": "sensitive-engine-value"
    }

    extension._log_configuration()

    config_logs = [
        message
        for _, message, category in ten_env.logs
        if category == LOG_CATEGORY_KEY_POINT
    ]
    assert len(config_logs) == 1
    assert config_logs[0].startswith("config: ")
    assert "sensitive" not in config_logs[0]


def test_start_connection_emits_connect_delay_metric_and_categorized_logs() -> (
    None
):
    async def run() -> None:
        extension, ten_env, client = create_extension()

        await extension.start_connection()

        assert client.start_calls == 1
        metrics = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "metrics"
        ]
        assert len(metrics) == 1
        assert metrics[0]["metrics"]["connect_delay"] >= 0
        assert any(
            category == LOG_CATEGORY_VENDOR for _, _, category in ten_env.logs
        )

    asyncio.run(run())


def test_initial_connection_failure_is_nonfatal_and_reconnects() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        client = FakeClient([ConnectionError("offline")])
        client.connected = False
        extension.client = client  # type: ignore[assignment]

        async def no_delay(_delay: float) -> None:
            return None

        extension.reconnect_manager = ReconnectManager(
            base_delay=0,
            max_delay=0,
            max_attempts=2,
            sleep=no_delay,
        )

        await extension.start_connection()
        reconnect_task = extension._reconnect_task
        assert reconnect_task is not None
        await reconnect_task

        errors = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "error"
        ]
        assert [error["code"] for error in errors] == [1000]
        assert client.start_calls == 2
        assert client.connected is True

    asyncio.run(run())


def test_reconnect_retries_nonfatal_errors_then_resets_after_success() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        client = FakeClient(
            [ConnectionError("offline-1"), ConnectionError("offline-2")]
        )
        client.connected = False
        extension.client = client  # type: ignore[assignment]
        extension._should_reconnect = True
        delays: list[float] = []

        async def sleep(delay: float) -> None:
            delays.append(delay)

        extension.reconnect_manager = ReconnectManager(
            base_delay=0.5,
            max_delay=2.0,
            max_attempts=3,
            sleep=sleep,
        )

        await extension._reconnect()

        errors = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "error"
        ]
        assert [error["code"] for error in errors] == [1000, 1000]
        assert client.start_calls == 3
        assert client.connected is True
        assert delays == [0.5, 1.0, 2.0]
        assert extension.reconnect_manager.current_attempts == 0

    asyncio.run(run())


def test_reconnect_limit_reports_fatal_error() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        client = FakeClient(
            [ConnectionError("offline-1"), ConnectionError("offline-2")]
        )
        client.connected = False
        extension.client = client  # type: ignore[assignment]
        extension._should_reconnect = True

        async def sleep(_delay: float) -> None:
            pass

        extension.reconnect_manager = ReconnectManager(
            base_delay=0,
            max_delay=0,
            max_attempts=2,
            sleep=sleep,
        )

        await extension._reconnect()

        errors = [
            data_as_dict(data)
            for data in ten_env.data
            if data.get_name() == "error"
        ]
        assert [error["code"] for error in errors] == [1000, -1000]
        assert errors[-1]["vendor_info"]["code"] == "reconnect_exhausted"
        assert extension._should_reconnect is False

    asyncio.run(run())


def test_result_send_does_not_overwrite_newer_session_metadata() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        extension.metadata = {"session_id": "session-1"}
        original_send_data = ten_env.send_data

        async def send_data(data: Data) -> None:
            if data.get_name() == "asr_result":
                extension.metadata = {"session_id": "session-2"}
            await original_send_data(data)

        ten_env.send_data = send_data  # type: ignore[method-assign]

        response = parse_response(
            {
                "header": {"code": 0, "status": 1},
                "payload": {
                    "result": {
                        "bg": 0,
                        "ed": 100,
                        "ls": False,
                        "msgtype": "Progressive",
                        "ws": [{"cw": [{"w": "hello", "wb": 0, "we": 10}]}],
                    }
                },
            },
            language="en-US",
        )

        await extension.on_response(response)

        result = data_as_dict(
            next(
                data for data in ten_env.data if data.get_name() == "asr_result"
            )
        )
        assert result["metadata"]["session_id"] == "session-1"
        assert extension.metadata == {"session_id": "session-2"}

    asyncio.run(run())


def test_network_errors_are_sanitized_before_logging_and_reporting() -> None:
    async def run() -> None:
        extension, ten_env, _ = create_extension()
        extension.config = IFlytekAsrConfig(
            params={
                "url": (
                    "wss://user:password@example.com/tuling/ast/v3"
                    "?token=secret-token"
                ),
                "app_id": "sensitive-app-id",
                "biz_id": "sensitive-business-id",
            }
        )
        raw_message = (
            f"failed to connect {extension.config.url}\n"
            f"app={extension.config.app_id} biz={extension.config.biz_id}"
        )

        await extension.on_error(ConnectionError(raw_message))

        serialized = json.dumps(
            [data_as_dict(data) for data in ten_env.data], ensure_ascii=False
        )
        logs = "\n".join(message for _, message, _ in ten_env.logs)
        for secret in (
            "user",
            "password",
            "secret-token",
            "sensitive-app-id",
            "sensitive-business-id",
        ):
            assert secret not in serialized
            assert secret not in logs
        assert "wss://example.com/tuling/ast/v3" in serialized
        assert "\n" not in data_as_dict(ten_env.data[0])["message"]

    asyncio.run(run())
