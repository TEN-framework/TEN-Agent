import copy
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
    ready_timeout_sec: float = 10.0
    receive_timeout_sec: float = 30.0

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
        if not self.base_url.strip():
            raise ValueError("base_url is required")
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
            model = str(self.routing.get("model", ""))
            provider = str(self.routing.get("provider", ""))
            if not model or (not provider and "/" not in model):
                raise ValueError(
                    "explicit routing requires provider and model, "
                    "or a provider/model value"
                )
            return
        raise ValueError("routing mode must be auto or explicit")

    def to_str(self, sensitive_handling: bool = True) -> str:
        config = copy.deepcopy(self)
        if sensitive_handling and config.api_key:
            config.api_key = utils.encrypt(config.api_key)
        return f"{config}"
