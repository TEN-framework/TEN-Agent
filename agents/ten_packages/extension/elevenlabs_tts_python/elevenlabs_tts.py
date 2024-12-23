#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from dataclasses import dataclass
from typing import AsyncIterator
from ten_ai_base.config import BaseConfig


@dataclass
class ElevenLabsTTSConfig(BaseConfig):
    api_key: str = ""
    model_id: str = "eleven_multilingual_v2"
    optimize_streaming_latency: int = 0
    similarity_boost: float = 0.75
    speaker_boost: bool = False
    stability: float = 0.5
    request_timeout_seconds: int = 10
    style: float = 0.0
    voice_id: str = "pNInz6obpgDQGcFmaJgB"


class ElevenLabsTTS:
    def __init__(self, config: ElevenLabsTTSConfig) -> None:
        self.config = config
        self.client = None

    def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        # to avoid circular import issue when using openai with 11labs
        from elevenlabs.client import AsyncElevenLabs
        from elevenlabs import Voice, VoiceSettings

        if not self.client:
            self.client = AsyncElevenLabs(
                api_key=self.config.api_key, timeout=self.config.request_timeout_seconds
            )

        return self.client.generate(
            text=text,
            model=self.config.model_id,
            optimize_streaming_latency=self.config.optimize_streaming_latency,
            output_format="pcm_16000",
            stream=True,
            voice=Voice(
                voice_id=self.config.voice_id,
                settings=VoiceSettings(
                    stability=self.config.stability,
                    similarity_boost=self.config.similarity_boost,
                    style=self.config.style,
                    speaker_boost=self.config.speaker_boost,
                ),
            ),
        )
