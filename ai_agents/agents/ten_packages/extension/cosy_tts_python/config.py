import copy
from typing import Any

from pydantic import BaseModel, Field
from ten_ai_base import utils


SUPPORTED_PCM_SAMPLE_RATES = frozenset(
    {8000, 16000, 22050, 24000, 44100, 48000}
)

_TYPED_PARAM_KEYS = (
    "api_key",
    "model",
    "voice",
    "sample_rate",
)

_IGNORED_PARAM_KEYS = (
    "pool_size",
    "format",
    "enable_ssml",
    "headers",
    "base_url",
    "workspace_id",
)


class CosyTTSConfig(BaseModel):
    # Cosy TTS credentials
    api_key: str = ""  # Cosy TTS API Key

    # TTS specific configs
    model: str = ""  # Model name
    voice: str = ""  # Voice name
    format: str = "pcm"
    sample_rate: int = 16000  # Audio sample rate
    url: str = ""  # DashScope WebSocket URL
    headers: dict[str, str] = Field(default_factory=dict)

    # Debug and dump settings
    dump: bool = False
    dump_path: str = "./"

    params: dict[str, Any] = Field(default_factory=dict)

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        return f"{utils.redact_json(self.model_dump())}"

    def update_params(self) -> None:
        """Extract dedicated config fields, leaving provider params behind."""
        params_url = self.params.pop("url", None)  # pylint: disable=no-member
        if not self.url:
            match params_url:
                case str() if params_url.strip():
                    self.url = params_url

        for param_name in _IGNORED_PARAM_KEYS:
            self.params.pop(param_name, None)  # pylint: disable=no-member

        for param_name in _TYPED_PARAM_KEYS:
            if param_name in self.params:
                value = self.params.pop(param_name)  # pylint: disable=no-member
                setattr(self, param_name, value)

        # The extension only emits streaming mono 16-bit PCM. Ignore any
        # externally supplied format instead of rejecting the request.
        self.format = "pcm"

    def validate_params(self) -> None:
        """Validate required configuration parameters."""
        required_fields = [
            "api_key",
            "model",
            "voice",
        ]

        for field_name in required_fields:
            value = getattr(self, field_name)
            match value:
                case str() if value.strip() == "":
                    missing = True
                case None:
                    missing = True
                case _:
                    missing = False
            if missing:
                raise ValueError(
                    f"required fields are missing or empty: params.{field_name}",
                )

        if self.sample_rate not in SUPPORTED_PCM_SAMPLE_RATES:
            supported = ", ".join(
                str(rate) for rate in sorted(SUPPORTED_PCM_SAMPLE_RATES)
            )
            raise ValueError(
                f"params.sample_rate must be one of: {supported}",
            )

    def provider_params(self) -> dict[str, Any]:
        """Return task parameters that should be forwarded to DashScope."""
        return copy.deepcopy(self.params)
