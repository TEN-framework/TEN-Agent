#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
"""
Speko TTS Extension

Text-to-speech through the Speko model router (api.speko.ai). The
router benchmarks TTS providers per language and dials the best one
per request, with automatic failover before the first byte. Extends
AsyncTTS2HttpExtension for HTTP-based streaming synthesis.
"""

from ten_ai_base.tts2_http import (
    AsyncTTS2HttpExtension,
    AsyncTTS2HttpConfig,
    AsyncTTS2HttpClient,
)
from ten_runtime import AsyncTenEnv

from .config import SpekoTTSConfig, SPEKO_OUTPUT_SAMPLE_RATE
from .speko_tts import SpekoTTSClient


class SpekoTTSExtension(AsyncTTS2HttpExtension):
    """Speko TTS Extension implementation.

    Inherits all common HTTP TTS functionality (request state machine,
    flush handling, metrics, dump) from AsyncTTS2HttpExtension.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config: SpekoTTSConfig = None
        self.client: SpekoTTSClient = None

    async def create_config(self, config_json_str: str) -> AsyncTTS2HttpConfig:
        """Create Speko TTS configuration from JSON string."""
        return SpekoTTSConfig.model_validate_json(config_json_str)

    async def create_client(
        self, config: AsyncTTS2HttpConfig, ten_env: AsyncTenEnv
    ) -> AsyncTTS2HttpClient:
        """Create Speko TTS client."""
        return SpekoTTSClient(config=config, ten_env=ten_env)

    def vendor(self) -> str:
        """Return vendor name."""
        return "speko"

    def synthesize_audio_sample_rate(self) -> int:
        """The router normalizes all providers to 24 kHz mono s16le."""
        return SPEKO_OUTPUT_SAMPLE_RATE
