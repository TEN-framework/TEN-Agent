from typing import Any
import copy
from pathlib import Path
from pydantic import Field
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig


# Smallest AI (Lightning) TTS defaults.
DEFAULT_BASE_URL = "https://api.smallest.ai"
DEFAULT_MODEL = "lightning_v3.1"
DEFAULT_VOICE_ID = "magnus"
DEFAULT_SAMPLE_RATE = 24000
# Lightning emits raw signed 16-bit LE mono PCM when `output_format` is
# `pcm`, which is exactly the TEN `pcm_frame` contract — no conversion
# needed. Raw pcm (vs wav/mp3) also keeps time-to-first-audio low: there is
# no container header to buffer before the first samples arrive.
DEFAULT_OUTPUT_FORMAT = "pcm"


class SmallestTTSConfig(AsyncTTS2HttpConfig):
    """Smallest AI (Lightning) TTS Config"""

    dump: bool = Field(default=False, description="Smallest TTS dump")
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "smallest_tts_in.pcm"
        ),
        description="Smallest TTS dump path",
    )
    url: str | None = Field(
        default=None,
        description="Direct endpoint URL (takes precedence over base_url)",
    )
    headers: dict[str, Any] = Field(
        default_factory=dict, description="Smallest TTS headers"
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Smallest TTS params"
    )

    def update_params(self) -> None:
        """Update configuration from params dictionary"""
        # Set default values if not specified
        if "model" not in self.params:
            self.params["model"] = DEFAULT_MODEL
        if "voice_id" not in self.params:
            self.params["voice_id"] = DEFAULT_VOICE_ID
        if "sample_rate" not in self.params:
            self.params["sample_rate"] = DEFAULT_SAMPLE_RATE

        # Remove text if present (will be set per request)
        if "text" in self.params:
            del self.params["text"]

        # Always request raw PCM16; anything else would need conversion
        # before it can be sent through the pcm_frame contract.
        self.params["output_format"] = DEFAULT_OUTPUT_FORMAT

        # Set endpoint URL from base_url if url is not provided
        if not self.url:
            if "url" in self.params:
                self.url = self.params["url"]
                self.params.pop("url", None)  # pylint: disable=no-member
            else:
                base_url = self.params.get(  # pylint: disable=no-member
                    "base_url", DEFAULT_BASE_URL
                )
                # Remove trailing slash from base_url
                base_url = base_url.rstrip("/")
                # SSE streaming endpoint: audio chunks arrive as they are
                # synthesized (~100 ms to first chunk).
                self.url = f"{base_url}/waves/v1/tts/live"
                # Remove base_url from params since it's been used to set url
                self.params.pop("base_url", None)  # pylint: disable=no-member

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)

        # Encrypt sensitive fields in params
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])

        # Redact sensitive headers (e.g. Authorization) before logging —
        # `headers.Authorization` is a supported auth path merged into the
        # actual HTTP request, so it must not reach the key-point log in
        # plaintext.
        config.headers = utils.redact_headers(config.headers) or {}

        return f"{config}"

    def validate(self) -> None:
        """Validate Smallest-specific configuration."""
        # Check if API key is provided in params or Authorization header
        has_api_key_in_params = (
            "api_key" in self.params and self.params["api_key"]
        )
        # pylint: disable=no-member
        has_authorization_header = self.headers.get("Authorization") is not None
        if not has_api_key_in_params and not has_authorization_header:
            raise ValueError(
                "API key or Authorization header is required for Smallest TTS"
            )
        if "voice_id" not in self.params or not self.params["voice_id"]:
            raise ValueError("voice_id is required for Smallest TTS")
