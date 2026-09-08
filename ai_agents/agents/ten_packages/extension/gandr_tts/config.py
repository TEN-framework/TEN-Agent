from typing import Any
import copy
from pathlib import Path
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig

from pydantic import Field


class GandrTTSConfig(AsyncTTS2HttpConfig):
    """Gandr TTS Config"""

    # Debug and logging
    dump: bool = Field(default=False, description="Gandr TTS dump")
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "gandr_tts_in.pcm"
        ),
        description="Gandr TTS dump path",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Gandr TTS params"
    )

    def update_params(self) -> None:
        """Update configuration from params dictionary"""
        # Keys to exclude from params after processing (not passthrough params)
        blacklist_keys = [
            "text",
            "input",
            "endpoint",
        ]  # endpoint is only used for the request URL

        # This extension always requests raw PCM from Gandr.
        self.params["response_format"] = "pcm"

        # Gandr PCM output is fixed at 24000 Hz (s16le, mono). The sample rate
        # is not a request parameter, so drop any sample rate keys callers may
        # pass to avoid sending unknown fields to the API.
        for key in ("sample_rate", "samplingRate", "sampling_rate"):
            if key in self.params:
                del self.params[key]

        # Remove blacklisted keys from params
        for key in blacklist_keys:
            if key in self.params:
                del self.params[key]

    def to_str(self, sensitive_handling: bool = True) -> str:
        """Convert config to string with optional sensitive data handling."""
        if not sensitive_handling:
            return f"{self}"

        config = copy.deepcopy(self)

        # Encrypt sensitive fields in params
        if config.params and "api_key" in config.params:
            config.params["api_key"] = utils.encrypt(config.params["api_key"])

        return f"{config}"

    def validate(self) -> None:
        """Validate Gandr-specific configuration."""
        if "api_key" not in self.params or not self.params["api_key"]:
            raise ValueError("API key is required for Gandr TTS")
