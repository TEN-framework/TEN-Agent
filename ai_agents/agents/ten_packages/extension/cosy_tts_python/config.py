import copy
import re
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
    # DashScope constructor parameters. They must reach the SDK constructor,
    # which maps them onto the wire parameters (`speech_rate` -> `rate`,
    # `pitch_rate` -> `pitch`); `additional_params` would keep only the raw
    # names and the service would ignore them.
    "volume",
    "speech_rate",
    "pitch_rate",
    "seed",
    "instruction",
    "language_hints",
)

_IGNORED_PARAM_KEYS = (
    "pool_size",
    "format",
    "enable_ssml",
    "headers",
    "base_url",
    # Workspace selection happens through the configured URL; the SDK pool's
    # workspace is fixed at construction, so per-request values are dropped.
    "workspace",
    "workspace_id",
)

# `utils.redact_json` only exists in ten_ai_base >= 0.7.45. Keep the same
# masking behaviour on older releases without taking a hard dependency on it.
_SENSITIVE_JSON_KEYS = frozenset(
    {
        "accesskey",
        "apikey",
        "api_key",
        "appkey",
        "authorization",
        "key",
        "password",
        "secret",
        "secretid",
        "secretkey",
        "ststoken",
        "token",
    },
)


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _mask_secret(value: Any) -> Any:
    if value in (None, ""):
        return value
    text = str(value)
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}...{text[-4:]}"


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _mask_secret(item)
                if _normalize_key(str(key)) in _SENSITIVE_JSON_KEYS
                else _redact_json(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    return value


def redact_config(value: Any) -> Any:
    """Mask secrets, falling back to a local implementation on older bases."""
    redact_json = getattr(utils, "redact_json", None)
    if callable(redact_json):
        return redact_json(value)
    return _redact_json(value)


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
    # Word-level subtitle alignment. This extension-owned switch decides
    # whether DashScope returns word timestamps; it always overrides any
    # provider parameter supplied through `params`.
    enable_words: bool = False
    # DashScope constructor parameters (see `_TYPED_PARAM_KEYS`).
    volume: int | None = None
    speech_rate: float | None = None
    pitch_rate: float | None = None
    seed: int | None = None
    instruction: str | None = None
    language_hints: list[str] | None = None

    # Debug and dump settings
    dump: bool = False
    dump_path: str = "./"

    params: dict[str, Any] = Field(default_factory=dict)

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        return f"{redact_config(self.model_dump())}"

    def update_params(self) -> None:
        """Extract dedicated config fields, leaving provider params behind."""
        params_url = self.params.pop("url", None)  # pylint: disable=no-member
        if not self.url:
            match params_url:
                case str() if params_url.strip():
                    self.url = params_url

        for param_name in _IGNORED_PARAM_KEYS:
            self.params.pop(param_name, None)  # pylint: disable=no-member

        # `enable_words` is the top-level property only; drop a nested copy so
        # it is never forwarded to DashScope as an unknown parameter.
        self.params.pop("enable_words", None)  # pylint: disable=no-member

        for param_name in _TYPED_PARAM_KEYS:
            if param_name in self.params:
                value = self.params.pop(param_name)  # pylint: disable=no-member
                setattr(self, param_name, value)

        # The extension only emits streaming mono 16-bit PCM. Ignore any
        # externally supplied format instead of rejecting the request.
        self.format = "pcm"

        # enable_words is the single source of truth: force the provider
        # switch in both directions so subtitles and audio cannot desync.
        self.params["word_timestamp_enabled"] = self.enable_words

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
