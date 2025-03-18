#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from dataclasses import dataclass
from typing import AsyncIterator, Optional, Literal
from pyneuphonic import Neuphonic, TTSConfig
from pyneuphonic.models import APIResponse, TTSResponse

from ten_ai_base.config import BaseConfig


@dataclass
class NeuphonicTTSConfig(BaseConfig):
    api_key: str = ""
    lang_code: str = "en"
    sample_rate: int = 16000
    voice_id: Optional[str] = None
    speed: float = 1.0
    encoding: Literal["pcm_linear", "pcm_mulaw"] = "pcm_linear"
    request_timeout_seconds: int = 10

class NeuphonicTTS:
    def __init__(self, config: NeuphonicTTSConfig) -> None:
        self.config = config
        self.client = Neuphonic(api_key=config.api_key)

    def text_to_speech_stream(self, text: str) -> AsyncIterator[APIResponse[TTSResponse]]:
        sse_client = self.client.tts.AsyncSSEClient(timeout=self.config.request_timeout_seconds)
        tts_config = TTSConfig(
            lang_code=self.config.lang_code,
            sampling_rate=self.config.sample_rate,
            voice_id=self.config.voice_id,
            speed=self.config.speed,
            encoding=self.config.encoding,
        )

        return sse_client.send(text, tts_config=tts_config)
