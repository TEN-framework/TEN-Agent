from typing import Any
import copy
import math
from pathlib import Path
from pydantic import Field
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig


def _safe_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(converted):
        return default
    return converted


class OpenAITTSConfig(AsyncTTS2HttpConfig):
    """OpenAI TTS Config"""

    dump: bool = Field(default=False, description="OpenAI TTS dump")
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "openai_tts_in.pcm"
        ),
        description="OpenAI TTS dump path",
    )
    url: str | None = Field(
        default=None,
        description="Direct endpoint URL (takes precedence over base_url)",
    )
    headers: dict[str, Any] = Field(
        default_factory=dict, description="OpenAI TTS headers"
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="OpenAI TTS params"
    )

    def update_params(self) -> None:
        """Update configuration from params dictionary"""
        # Set default values if not specified
        if "model" not in self.params:
            self.params["model"] = "gpt-4o-mini-tts"
        if "voice" not in self.params:
            self.params["voice"] = "coral"
        speed = self.params["speed"] if "speed" in self.params else 1.0
        self.params["speed"] = _safe_float(speed, 1.0)
        if "api_key" in self.params and not isinstance(
            self.params["api_key"], str
        ):
            self.params["api_key"] = ""
        if "instructions" not in self.params:
            self.params["instructions"] = ""

        # Remove input if present (will be set from text)
        if "input" in self.params:
            del self.params["input"]

        # Use fixed value
        self.params["response_format"] = "pcm"

        # Remove endpoint-only params after selecting the endpoint.
        param_url = self.params.pop("url", None)  # pylint: disable=no-member
        base_url = self.params.pop(  # pylint: disable=no-member
            "base_url", "https://api.openai.com/v1"
        )
        if not self.url:
            if isinstance(param_url, str) and param_url.strip():
                self.url = param_url
            else:
                if not isinstance(base_url, str) or not base_url.strip():
                    base_url = "https://api.openai.com/v1"
                base_url = base_url.rstrip("/")
                self.url = f"{base_url}/audio/speech"

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)

        # Encrypt sensitive fields in params
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])
        for header_key in ("Authorization", "authorization"):
            if header_key in config.headers:
                config.headers[header_key] = utils.encrypt(
                    config.headers[header_key]
                )

        return f"{config}"

    def validate(self) -> None:
        """Validate OpenAI-specific configuration."""
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("URL is required for OpenAI TTS")
        # Check if API key is provided in params or Authorization header
        has_api_key_in_params = (
            "api_key" in self.params and self.params["api_key"]
        )
        # pylint: disable=no-member
        has_authorization_header = self.headers.get("Authorization") is not None
        if not has_api_key_in_params and not has_authorization_header:
            raise ValueError(
                "API key or Authorization header is required for OpenAI TTS"
            )
        if "model" not in self.params or not self.params["model"]:
            raise ValueError("Model is required for OpenAI TTS")
        if "voice" not in self.params or not self.params["voice"]:
            raise ValueError("Voice is required for OpenAI TTS")
