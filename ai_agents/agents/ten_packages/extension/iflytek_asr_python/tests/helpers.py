import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any

from ten_runtime import AudioFrame, Data

from iflytek_asr_python.config import IFlytekAsrConfig
from iflytek_asr_python.extension import IFlytekAsrExtension
from iflytek_asr_python.protocol import IFlytekResponse, parse_response


class FakePropertyError:
    def __init__(self, message: str) -> None:
        self._message = message

    def error_message(self) -> str:
        return self._message

    def __str__(self) -> str:
        return self._message


class FakeTenEnv:
    def __init__(
        self,
        property_value: dict[str, Any] | None = None,
        property_error: object | None = None,
    ) -> None:
        self.property_value = property_value
        self.property_error = property_error
        self.data: list[Data] = []
        self.logs: list[tuple[str, str, str | None]] = []

    async def get_property_to_json(
        self, _path: str
    ) -> tuple[str, object | None]:
        return json.dumps(self.property_value or {}), self.property_error

    async def get_property_bool(self, path: str) -> tuple[bool, object | None]:
        properties = self.property_value or {}
        value = properties.get(path)
        if not isinstance(value, bool):
            return False, FakePropertyError(f"property not found: {path}")
        return value, None

    async def send_data(self, data: Data) -> None:
        self.data.append(data)

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


FinalizeCallback = Callable[[], Awaitable[None] | None]


class FakeClient:
    def __init__(
        self,
        *,
        start_errors: list[Exception] | None = None,
        finalize_result: bool = True,
        on_finalize: FinalizeCallback | None = None,
    ) -> None:
        self.audio: list[bytes] = []
        self.connected = True
        self.finalized = False
        self.finalizing = False
        self.start_errors = list(start_errors or [])
        self.start_calls = 0
        self.stop_calls = 0
        self.finalize_result = finalize_result
        self.on_finalize = on_finalize

    async def start(self) -> None:
        self.start_calls += 1
        if self.start_errors:
            self.connected = False
            raise self.start_errors.pop(0)
        self.connected = True
        self.finalizing = False

    async def stop(self) -> None:
        self.stop_calls += 1
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    async def send_audio(self, audio: bytes) -> bool:
        if not self.connected or self.finalizing:
            return False
        self.audio.append(audio)
        return True

    async def finalize(self) -> bool:
        if not self.connected or self.finalizing:
            return False
        self.finalized = True
        self.finalizing = True
        if self.on_finalize is not None:
            callback_result = self.on_finalize()
            if inspect.isawaitable(callback_result):
                await callback_result
        return self.finalize_result


def create_config(**overrides: Any) -> IFlytekAsrConfig:
    params: dict[str, Any] = {
        "url": "ws://127.0.0.1:9990/tuling/ast/v3",
        "biz_id": "tenant-1",
        "sample_rate": 16000,
        "language": "en-US",
    }
    properties: dict[str, Any] = {"params": params}
    for key, value in overrides.items():
        if key in ("dump", "dump_path"):
            properties[key] = value
        else:
            params[key] = value
    return IFlytekAsrConfig.model_validate(properties)


def create_extension(
    *,
    config: IFlytekAsrConfig | None = None,
    client: FakeClient | None = None,
) -> tuple[IFlytekAsrExtension, FakeTenEnv, FakeClient]:
    extension = IFlytekAsrExtension("iflytek")
    ten_env = FakeTenEnv()
    fake_client = client or FakeClient()
    extension.ten_env = ten_env  # type: ignore[assignment]
    extension.config = config or create_config()
    extension.client = fake_client  # type: ignore[assignment]
    extension._should_reconnect = False
    return extension, ten_env, fake_client


def data_as_dict(data: Data) -> dict[str, Any]:
    value, error = data.get_property_to_json()
    assert error is None
    return json.loads(value)


def make_audio_frame(
    content: bytes, session_id: str = "session-1"
) -> AudioFrame:
    frame = AudioFrame.create("pcm_frame")
    frame.set_property_from_json(
        "metadata", json.dumps({"session_id": session_id})
    )
    frame.alloc_buf(len(content))
    buffer = frame.lock_buf()
    buffer[:] = content
    frame.unlock_buf(buffer)
    return frame


def make_response(
    *,
    text: str,
    final: bool,
    terminal: bool = False,
    language: str = "en-US",
    temporary_voiceprints: dict[str, str] | None = None,
) -> IFlytekResponse:
    result: dict[str, Any] = {
        "bg": 100,
        "ed": 500,
        "ls": final,
        "msgtype": "sentence" if final else "Progressive",
        "ws": [
            {
                "cw": [
                    {
                        "w": text,
                        "wb": 10,
                        "we": 50,
                    }
                ]
            }
        ],
    }
    if temporary_voiceprints is not None:
        result["tmpSwk"] = temporary_voiceprints
    return parse_response(
        {
            "header": {
                "code": 0,
                "status": 2 if terminal else 1,
                "sid": "AST-1",
                "traceId": "trace-1",
            },
            "payload": {"result": result},
        },
        language=language,
    )
