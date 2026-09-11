from typing import Any
import copy
from pathlib import Path
from ten_ai_base import utils
from ten_ai_base.tts2_http import AsyncTTS2HttpConfig

from pydantic import Field


class SarvamTTSConfig(AsyncTTS2HttpConfig):
    """Sarvam TTS Config"""

    # Debug and logging
    dump: bool = Field(default=False, description="Sarvam TTS dump")
    dump_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "sarvam_tts_in.pcm"
        ),
        description="Sarvam TTS dump path",
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Sarvam TTS params"
    )

    def update_params(self) -> None:
        """Update configuration from params dictionary"""
        # Keys to exclude from params after processing (not passthrough params)
        blacklist_keys = [
            "text",
            "endpoint",
        ]  # base_url is only used for endpoint

        # Normalize sample rate key - convert speech_sample_rate if needed
        if "speech_sample_rate" in self.params:
            self.params["speech_sample_rate"] = int(
                self.params["speech_sample_rate"]
            )

        # Sarvam only supports pitch and loudness with bulbul:v2. These
        # parameters make bulbul:v3 requests fail even when they contain the
        # old default values.
        if "model" in self.params and self.params["model"] == "bulbul:v3":
            for key in ["pitch", "loudness"]:
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
        if config.params and "api_subscription_key" in config.params:
            config.params["api_subscription_key"] = utils.encrypt(
                config.params["api_subscription_key"]
            )

        return f"{config}"

    def validate(self) -> None:
        """Validate Sarvam-specific configuration."""
        if (
            "api_subscription_key" not in self.params
            or not self.params["api_subscription_key"]
        ):
            raise ValueError("API subscription key is required for Sarvam TTS")
        if (
            "target_language_code" not in self.params
            or not self.params["target_language_code"]
        ):
            raise ValueError("target_language_code is required for Sarvam TTS")
