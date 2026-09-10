#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""Blaze TTS TEN extension (HTTP job + download polling)."""

from ten_ai_base.tts2_http import (
    AsyncTTS2HttpClient,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpExtension,
)
from ten_runtime import AsyncTenEnv

from .config import BlazeTTSConfig, DEFAULT_SAMPLE_RATE
from .ten_tts_client import BlazeTTSHttpClient


class BlazeTTSExtension(AsyncTTS2HttpExtension):
    """Text-to-speech via Blaze (2.0-realtime alias -> v2.0_flash HTTP)."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: BlazeTTSConfig | None = None
        self.client: BlazeTTSHttpClient | None = None

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        return BlazeTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        return BlazeTTSHttpClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        return "blaze"

    def synthesize_audio_sample_rate(self) -> int:
        if self.config is None:
            return DEFAULT_SAMPLE_RATE
        return int(self.config.params.get("sample_rate", DEFAULT_SAMPLE_RATE))
