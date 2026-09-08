#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Gandr TTS Extension

This extension implements text-to-speech using the Gandr TTS API.
It extends the AsyncTTS2HttpExtension for HTTP-based TTS services.
"""

from ten_ai_base.tts2_http import (
    AsyncTTS2HttpExtension,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpClient,
)
from ten_runtime import AsyncTenEnv

from .config import GandrTTSConfig
from .gandr_tts import GandrTTSClient, GANDR_SAMPLE_RATE


class GandrTTSExtension(AsyncTTS2HttpExtension):
    """
    Gandr TTS Extension implementation.

    Provides text-to-speech synthesis using Gandr's OpenAI compatible HTTP API.
    Inherits all common HTTP TTS functionality from AsyncTTS2HttpExtension.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        # Type hints for better IDE support
        self.config: GandrTTSConfig = None
        self.client: GandrTTSClient = None

    # ============================================================
    # Required method implementations
    # ============================================================

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        """Create Gandr TTS configuration from JSON string."""
        return GandrTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        """Create Gandr TTS client."""
        return GandrTTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        """Return vendor name."""
        return "gandr"

    def synthesize_audio_sample_rate(self) -> int:
        """Return the sample rate for synthesized audio.

        Gandr PCM output is fixed at 24000 Hz (s16le, mono).
        """
        return GANDR_SAMPLE_RATE
