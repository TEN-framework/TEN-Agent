#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from dataclasses import dataclass
from typing import AsyncIterator
from cartesia import AsyncCartesia

from ten_ai_base.config import BaseConfig


@dataclass
class CartesiaTTSConfig(BaseConfig):
    api_key: str = ""
    language: str = "en"
    model_id: str = "sonic-english"
    request_timeout_seconds: int = 10
    sample_rate: int = 16000
    voice_id: str = "f9836c6e-a0bd-460e-9d3c-f7299fa60f94"


class CartesiaTTS:
    def __init__(self, config: CartesiaTTSConfig) -> None:
        self.config = config
        self.client = AsyncCartesia(
            api_key=config.api_key, timeout=config.request_timeout_seconds
        )

    def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        return self.client.tts.sse(
            language=self.config.language,
            model_id=self.config.model_id,
            output_format={
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self.config.sample_rate,
            },
            stream=True,
            transcript=text,
            voice_id=self.config.voice_id,
        )
