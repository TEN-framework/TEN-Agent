import copy
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
    timeout_sec: float = Field(default=60.0, gt=0)
    routing: dict[str, Any] = Field(
        default_factory=lambda: {
            "mode": "auto",
            "objective": "balanced",
        }
    )

    def validate_required(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key is required")
        if not self.base_url.strip():
            raise ValueError("base_url is required")
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
