#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import tempfile
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
}
VENDOR_LANGUAGE_ALIASES = {
    "zh-CN": "zh",
    "en-US": "en",
}
MAX_ERROR_MESSAGE_LENGTH = 2048
REDACTED_VALUE = "<redacted>"
PARAM_FIELDS = frozenset(
    {
        "url",
        "app_id",
        "biz_id",
        "trace_id_prefix",
        "sample_rate",
        "language",
        "engine",
        "res_id_list",
        "hotwords",
        "hotword_weight",
        "voiceprints",
        "connect_timeout",
        "finalize_timeout",
        "reconnect_delay",
        "reconnect_max_delay",
        "reconnect_max_attempts",
        "buffer_max_bytes",
    }
)


class IFlytekAsrConfig(BaseModel):
    url: str = Field(
        default="ws://127.0.0.1:9990/tuling/ast/v3",
        description="iFLYTEK realtime transcription WebSocket endpoint",
    )
    app_id: str = Field(default="", description="Application system ID")
    biz_id: str = Field(min_length=1, description="Required business ID")
    trace_id_prefix: str = Field(default="ten", min_length=1)
    sample_rate: int = Field(default=16000, gt=0)
    language: str = Field(default="zh-CN", min_length=1)
    engine: dict[str, str] = Field(default_factory=dict)
    res_id_list: list[str] = Field(default_factory=list)
    hotwords: str = ""
    hotword_weight: float = Field(default=1.0, ge=1.0, le=4.0)
    voiceprints: dict[str, str] = Field(default_factory=dict)
    dump: bool = False
    dump_path: str = Field(default_factory=tempfile.gettempdir)
    connect_timeout: float = Field(default=10.0, gt=0)
    finalize_timeout: float = Field(default=5.0, gt=0, le=60)
    reconnect_delay: float = Field(default=0.5, ge=0)
    reconnect_max_delay: float = Field(default=8.0, ge=0)
    reconnect_max_attempts: int = Field(default=5, ge=1)
    buffer_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def extract_params(cls, data: Any) -> Any:
        if isinstance(data, dict):
            top_level_params = PARAM_FIELDS.intersection(data)
            if top_level_params:
                field_names = ", ".join(sorted(top_level_params))
                raise ValueError(
                    f"iFLYTEK parameters must be nested under params: "
                    f"{field_names}"
                )
            nested_params = data.get("params")
            if isinstance(nested_params, dict):
                merged = dict(data)
                merged.update(
                    {
                        key: value
                        for key, value in nested_params.items()
                        if key in PARAM_FIELDS
                    }
                )
                return merged
        return data

    @field_validator("url")
    @classmethod
    def validate_websocket_url(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = urlsplit(normalized)
            _ = parsed.port
        except ValueError as error:
            raise ValueError("url must be a valid WebSocket URL") from error
        if parsed.scheme.casefold() not in ("ws", "wss"):
            raise ValueError("url must use the ws:// or wss:// scheme")
        if not parsed.hostname:
            raise ValueError("url must include a host")
        if parsed.fragment:
            raise ValueError("url must not include a fragment")
        return normalized

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        languages = [language.strip() for language in value.split("|")]
        if not languages or any(not language for language in languages):
            raise ValueError("language must contain non-empty language codes")
        return "|".join(
            LANGUAGE_ALIASES.get(language.casefold(), language)
            for language in languages
        )

    @field_validator("dump_path")
    @classmethod
    def validate_dump_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("dump_path must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_reconnect_delays(self) -> "IFlytekAsrConfig":
        if self.reconnect_max_delay < self.reconnect_delay:
            raise ValueError(
                "reconnect_max_delay must be greater than or equal to "
                "reconnect_delay"
            )
        return self

    def vendor_language(self) -> str:
        languages = self.language.split("|")  # pylint: disable=no-member
        return "|".join(
            VENDOR_LANGUAGE_ALIASES.get(language, language)
            for language in languages
        )

    def output_language(self) -> str:
        return self.language

    def engine_parameters(self) -> dict[str, str]:
        parameters = dict(self.engine)
        parameters.setdefault(
            "wrec_param_language_name", self.vendor_language()
        )
        return parameters

    def log_summary(self) -> dict[str, Any]:
        engine_parameter_keys = sorted(self.engine_parameters())
        return {
            "url": self.sanitized_url(),
            "has_app_id": bool(self.app_id),
            "has_biz_id": bool(self.biz_id),
            "sample_rate": self.sample_rate,
            "language": self.language,
            "engine_parameter_keys": engine_parameter_keys,
            "res_id_count": len(self.res_id_list),
            "has_hotwords": bool(self.hotwords),
            "voiceprint_count": len(self.voiceprints),
            "dump": self.dump,
            "finalize_timeout": self.finalize_timeout,
            "reconnect_max_attempts": self.reconnect_max_attempts,
            "buffer_max_bytes": self.buffer_max_bytes,
        }

    def sanitized_url(self) -> str:
        parsed_url = urlsplit(self.url)
        host = parsed_url.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parsed_url.port is not None:
            host = f"{host}:{parsed_url.port}"
        return urlunsplit((parsed_url.scheme, host, parsed_url.path, "", ""))

    def sanitize_message(self, message: object) -> str:
        sanitized = str(message).replace(self.url, self.sanitized_url())
        parsed_url = urlsplit(self.url)
        # Pylint infers Pydantic field descriptors as FieldInfo instances.
        # pylint: disable=no-member
        sensitive_values = [
            parsed_url.username or "",
            parsed_url.password or "",
            self.app_id,
            self.biz_id,
            self.hotwords,
            *self.res_id_list,
            *self.engine.values(),
            *self.voiceprints.keys(),
            *self.voiceprints.values(),
            *(value for _, value in parse_qsl(parsed_url.query)),
        ]
        # pylint: enable=no-member
        for sensitive_value in sorted(
            {value for value in sensitive_values if len(value) >= 4},
            key=len,
            reverse=True,
        ):
            sanitized = sanitized.replace(sensitive_value, REDACTED_VALUE)
        sanitized = " ".join(sanitized.split())
        return sanitized[:MAX_ERROR_MESSAGE_LENGTH]
