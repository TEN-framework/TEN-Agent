#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
import copy
from typing import Any

from pydantic import BaseModel, Field
from ten_ai_base import utils

DEFAULT_BASE_URL = "wss://fal.run/Kotoba-Technologies/kotoba-tts/v2/tts/ws"
SUPPORTED_SAMPLE_RATES = (8000, 16000, 24000)

# Keys the extension understands under ``params``. Everything else is
# reported as ignored and never forwarded to the service.
_KNOWN_PARAMS = (
    "key",
    "api_key",
    "base_url",
    "language",
    "speaker_id",
    "sample_rate",
    "request_timeout_seconds",
    "segment_soft_limit_chars",
)


class KotobaTTSConfig(BaseModel):
    dump: bool = False
    dump_path: str = "./"
    params: dict[str, Any] = Field(default_factory=dict)

    # Resolved from ``params`` by ``update_params()``.
    key: str = ""
    base_url: str = DEFAULT_BASE_URL
    language: str = "ja"
    speaker_id: str = "male-01"
    sample_rate: int = 16000
    # Longest gap tolerated between sending a segment and its first audio
    # chunk, and between two audio chunks.
    request_timeout_seconds: float = 30.0
    # Buffered text longer than this is cut at a comma; twice this length
    # is cut unconditionally so buffering stays bounded.
    segment_soft_limit_chars: int = 120

    def update_params(self) -> None:
        """Move known keys from ``params`` into typed fields.

        ``params`` keeps only the keys the extension does not understand,
        so the caller can log them as ignored.
        """
        params = dict(self.params)

        key = params.pop("key", None)
        api_key = params.pop("api_key", None)
        resolved_key = key if key else api_key
        if isinstance(resolved_key, str):
            self.key = resolved_key

        for name in ("base_url", "language", "speaker_id"):
            value = params.pop(name, None)
            if isinstance(value, str) and value.strip():
                setattr(self, name, value.strip())

        sample_rate = params.pop("sample_rate", None)
        if sample_rate is not None:
            self.sample_rate = _as_int(sample_rate, "sample_rate")

        timeout = params.pop("request_timeout_seconds", None)
        if timeout is not None:
            self.request_timeout_seconds = _as_float(
                timeout, "request_timeout_seconds"
            )

        soft_limit = params.pop("segment_soft_limit_chars", None)
        if soft_limit is not None:
            self.segment_soft_limit_chars = _as_int(
                soft_limit, "segment_soft_limit_chars"
            )

        self.params = params

    def validate_config(self) -> None:
        """Raise ``ValueError`` when a request could not succeed."""
        if not self.key:
            raise ValueError("params.key (fal API key) is required")
        if not self.base_url.startswith(("ws://", "wss://")):
            raise ValueError("params.base_url must be a ws:// or wss:// URL")
        if not self.language:
            raise ValueError("params.language must not be empty")
        if not self.speaker_id:
            raise ValueError("params.speaker_id must not be empty")
        if self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ValueError(
                "params.sample_rate must be one of "
                f"{SUPPORTED_SAMPLE_RATES}, got {self.sample_rate}"
            )
        if not self.request_timeout_seconds > 0:
            raise ValueError("params.request_timeout_seconds must be > 0")
        if self.segment_soft_limit_chars < 1:
            raise ValueError("params.segment_soft_limit_chars must be >= 1")

    def ignored_params(self) -> list[str]:
        return sorted(self.params.keys())

    def to_str(self, sensitive_handling: bool = True) -> str:
        if not sensitive_handling:
            return f"{self}"
        config = copy.deepcopy(self)
        if config.key:
            config.key = utils.encrypt(config.key)
        for name in ("key", "api_key"):
            if config.params.get(name):
                config.params[name] = utils.encrypt(str(config.params[name]))
        return f"{config}"


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"params.{name} must be an integer, got a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"params.{name} must be an integer, got {value!r}")


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"params.{name} must be a number, got a boolean")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"params.{name} must be a number, got {value!r}"
        ) from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"params.{name} must be finite, got {value!r}")
    return result
