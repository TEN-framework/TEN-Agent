import copy
import re
from urllib.parse import urlsplit, urlunsplit
from typing import Any

from pydantic import BaseModel, Field
from ten_ai_base import utils


class SpekoLLM2Config(BaseModel):
    api_key: str = ""
    base_url: str = "https://router.speko.dev"
    prompt: str = "You are a helpful assistant."
    max_output_tokens: int = Field(default=512, ge=1)
    temperature: float | None = Field(default=0.7, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    timeout_sec: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    routing: dict[str, Any] = Field(
        default_factory=lambda: {
            "mode": "auto",
            "objective": "balanced",
        }
    )

    def validate_required(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key is required")
        validate_base_url(self.base_url)
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
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
            parsed.scheme in {"http", "https"}
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
