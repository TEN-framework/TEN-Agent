from __future__ import annotations

import tempfile
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from ten_ai_base.utils import encrypt


DEFAULT_URL = "wss://api.stepfun.com/v1/realtime/asr/stream"
DEFAULT_MODEL = "stepaudio-2.5-asr-stream"


class StepFunASRConfig(BaseModel):
    """Configuration for StepAudio 2.5 real-time ASR."""

    dump: bool = False
    dump_path: str = Field(default_factory=tempfile.gettempdir)
    finalize_timeout: float = Field(default=10.0, gt=0, le=120)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def validate_params_type(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("params must be an object")
        return value

    def validate_config(self) -> None:
        if not self.api_key:
            raise ValueError("params.api_key is required")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise ValueError("params.url must be a ws:// or wss:// URL")
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "params.url must not contain credentials or query data"
            )
        if self.model == "":
            raise ValueError("params.model must not be empty")
        if self.language == "":
            raise ValueError("params.language must not be empty")
        if self.sample_rate != 16000 or self.bits != 16 or self.channels != 1:
            raise ValueError("StepFun requires 16 kHz mono PCM s16le")

    def update(self, params: dict[str, Any]) -> None:
        if params:
            self.params_dict().update(params)

    def to_json(self, sensitive_handling: bool = False) -> str:
        config = self.model_copy(deep=True)
        if sensitive_handling:
            config_params = dict(config.params_dict())
            for name in ("api_key", "key", "token", "secret"):
                value = config_params.get(name)
                if isinstance(value, str) and value:
                    config_params[name] = encrypt(value)
            setattr(config, "params", config_params)
        return config.model_dump_json()

    def to_str(self, sensitive_handling: bool = False) -> str:
        return self.to_json(sensitive_handling)

    def params_dict(self) -> dict[str, Any]:
        return getattr(self, "params", {})

    @property
    def api_key(self) -> str:
        params = self.params_dict()
        value = params.get("api_key") or params.get("key") or ""
        return str(value).strip()

    @property
    def url(self) -> str:
        return str(self.params_dict().get("url") or DEFAULT_URL).strip()

    @property
    def model(self) -> str:
        return str(self.params_dict().get("model") or DEFAULT_MODEL).strip()

    @property
    def language(self) -> str:
        return str(self.params_dict().get("language") or "en").strip()

    @property
    def sample_rate(self) -> int:
        return int(self.params_dict().get("sample_rate") or 16000)

    @property
    def bits(self) -> int:
        return int(self.params_dict().get("bits") or 16)

    @property
    def channels(self) -> int:
        return int(self.params_dict().get("channels") or 1)

    @property
    def enable_itn(self) -> bool:
        return _as_bool(self.params_dict().get("enable_itn"), True)

    @property
    def full_rerun_on_commit(self) -> bool:
        return _as_bool(self.params_dict().get("full_rerun_on_commit"), True)

    @property
    def enable_timestamp_align(self) -> bool:
        return _as_bool(
            self.params_dict().get("enable_timestamp_align"),
            False,
        )

    @property
    def connection_timeout(self) -> float:
        return max(
            0.1,
            float(self.params_dict().get("connection_timeout", 15.0)),
        )

    @property
    def reconnect_base_delay(self) -> float:
        return max(
            0.0,
            float(self.params_dict().get("reconnect_base_delay", 0.5)),
        )

    @property
    def reconnect_max_attempts(self) -> int:
        return max(1, int(self.params_dict().get("reconnect_max_attempts", 5)))

    @property
    def server_vad(self) -> bool:
        return _as_bool(self.params_dict().get("server_vad"), False)

    @property
    def silence_duration_ms(self) -> int:
        return max(
            1,
            int(self.params_dict().get("silence_duration_ms") or 800),
        )

    @property
    def vad_threshold(self) -> float:
        return float(self.params_dict().get("threshold") or 0.5)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
