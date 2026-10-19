#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Camb.ai TTS Extension

This extension implements text-to-speech using the Camb.ai MARS TTS API.
It extends the AsyncTTS2HttpExtension for HTTP-based TTS services.

Models:
    - mars-flash: Fast inference, 22.05kHz output (default)
    - mars-pro: High quality, 48kHz output
    - mars-instruct: Supports user_instructions, 22.05kHz output
"""

from ten_ai_base.tts2_http import (
    AsyncTTS2HttpExtension,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpClient,
)
from ten_runtime import AsyncTenEnv

from .config import CambTTSConfig
from .camb_tts import CambTTSClient, MODEL_SAMPLE_RATES, DEFAULT_MODEL


class CambTTSExtension(AsyncTTS2HttpExtension):
    """
    Camb.ai TTS Extension implementation.

    Provides text-to-speech synthesis using Camb.ai's MARS HTTP API.
    Inherits all common HTTP TTS functionality from AsyncTTS2HttpExtension.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        # Type hints for better IDE support
        self.config: CambTTSConfig = None
        self.client: CambTTSClient = None

    # ============================================================
    # Required method implementations
    # ============================================================

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        """Create Camb TTS configuration from JSON string."""
        return CambTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        """Create Camb TTS client."""
        return CambTTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        """Return vendor name."""
        return "camb"

    def synthesize_audio_sample_rate(self) -> int:
        """Return the sample rate for synthesized audio.

        Returns model-specific sample rate:
        - mars-flash: 22050 Hz
        - mars-pro: 48000 Hz
        - mars-instruct: 22050 Hz
        """
        if self.client:
            return self.client.get_sample_rate()
        # Fallback to default model's sample rate
        return MODEL_SAMPLE_RATES.get(DEFAULT_MODEL, 22050)
