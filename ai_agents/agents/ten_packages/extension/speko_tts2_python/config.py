import copy
import re
from urllib.parse import urlsplit, urlunsplit
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ten_ai_base import utils


class SpekoTTS2Config(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    dump: bool = False
    dump_path: str = "/tmp"
    params: dict[str, Any] = Field(default_factory=dict)

    api_key: str = ""
    base_url: str = "https://router.speko.dev"
    sample_rate: int = 24000
    channels: int = 1
    language: str = "en"
    voice: str = ""
    routing: dict[str, Any] = Field(
        default_factory=lambda: {
            "mode": "auto",
            "objective": "balanced",
        }
    )
    ready_timeout_sec: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    receive_timeout_sec: float = Field(default=30.0, gt=0, allow_inf_nan=False)

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, value: int) -> int:
        if not 8000 <= value <= 192000:
            raise ValueError("sample_rate must be between 8000 and 192000")
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: int) -> int:
        if not 1 <= value <= 8:
            raise ValueError("channels must be between 1 and 8")
        return value

    def update_params(self) -> None:
        values = dict(self.params)
        for name in (
            "api_key",
            "base_url",
            "sample_rate",
            "channels",
            "language",
            "voice",
            "routing",
            "ready_timeout_sec",
            "receive_timeout_sec",
        ):
            if name in values:
                setattr(self, name, values.pop(name))
        self.params = values
        self._validate_required()

    def _validate_required(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key is required")
        validate_base_url(self.base_url)
        if not re.fullmatch(
            r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", self.language
        ):
            raise ValueError("language must be a language tag, e.g. en-US")
        self._validate_routing()

    def _validate_routing(self) -> None:
        # pylint: disable=no-member
        mode = self.routing.get("mode", "auto")
        if mode == "auto":
            objective = self.routing.get("objective", "balanced")
            if objective not in {"balanced", "quality", "latency", "cost"}:
                raise ValueError("unsupported routing objective")
            return
        if mode == "explicit":
            # TEN recursively merges property.json defaults into graph params.
            # An explicit route must not retain the default auto objective.
            self.routing.pop("objective", None)
            model = self.routing.get("model", "")
            provider = self.routing.get("provider", "")
            if (
                not isinstance(model, str)
                or not model.strip()
                or not isinstance(provider, str)
                or (
                    not provider
                    and ("/" not in model or not all(model.split("/", 1)))
                )
            ):
                raise ValueError(
                    "explicit routing requires provider and model, "
                    "or a provider/model value"
                )
            return
        raise ValueError("routing mode must be auto or explicit")

    def to_str(self, sensitive_handling: bool = True) -> str:
        config = copy.deepcopy(self)
        if sensitive_handling:
            config.api_key = utils.encrypt(config.api_key)
            config.base_url = safe_url(config.base_url)
        return f"{config}"


def validate_base_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https", "ws", "wss"}
            and bool(parsed.hostname)
            and not any(char.isspace() for char in value)
        )
        # Accessing port also validates its syntax and range.
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("base_url must have a supported scheme and hostname")


def safe_url(value: str) -> str:
    """Only report endpoint identity; userinfo, queries and fragments are private."""
    try:
        parsed = urlsplit(value)
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc.rsplit("@", 1)[-1],
                parsed.path,
                "",
                "",
            )
        )
    except ValueError:
        return "<invalid endpoint>"


def safe_error(error: Exception) -> str:
    """Do not include Pydantic input values or transport URLs in diagnostics."""
    from pydantic import ValidationError

    if isinstance(error, ValidationError):
        return "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
    return re.sub(
        r"(?:https?|wss?)://[^\s'\"<>]+",
        lambda m: safe_url(m.group()),
        str(error),
    )
