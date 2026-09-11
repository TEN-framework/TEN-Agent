#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten_ai_base.tts2_http import (
    AsyncTTS2HttpExtension,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpClient,
)
from ten_runtime import AsyncTenEnv

from .config import OpenAITTSConfig
from .openai_tts import OpenAITTSClient


class OpenAITTSExtension(AsyncTTS2HttpExtension):
    """
    OpenAI TTS Extension implementation.

    Provides text-to-speech synthesis using OpenAI's HTTP API.
    Inherits all common HTTP TTS functionality from AsyncTTS2HttpExtension.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        # Type hints for better IDE support
        self.config: OpenAITTSConfig = None
        self.client: OpenAITTSClient = None

    # ============================================================
    # Required method implementations
    # ============================================================

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        """Create OpenAI TTS configuration from JSON string."""
        return OpenAITTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        """Create OpenAI TTS client."""
        return OpenAITTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        """Return vendor name."""
        return "openai"

    def vendor_metadata(self) -> dict:
        if self.config is None:
            return {}

        authorization = self.config.headers.get(
            "Authorization",
            "",
        ) or self.config.headers.get("authorization", "")
        return {
            "url": self.config.url or "",
            "model": self.config.params.get("model", ""),
            "api_key": self.config.params.get("api_key", ""),
            "authorization": authorization,
            "voice": self.config.params.get("voice", ""),
        }

    def synthesize_audio_sample_rate(self) -> int:
        return 24000
