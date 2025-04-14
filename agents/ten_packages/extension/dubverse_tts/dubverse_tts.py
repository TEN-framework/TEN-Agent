#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
import requests
from dataclasses import dataclass
from typing import AsyncIterator
from ten_ai_base.config import BaseConfig


@dataclass
class DubverseTTSConfig(BaseConfig):
    base_url: str = "https://audio.dubverse.ai/api/tts"
    api_key: str = ""
    speaker_no: int = 184


class DubverseTTS:
    def __init__(self, config: 'DubverseTTSConfig') -> None:
        self.config = config
        self.header = {
            "X-API-KEY": self.config.api_key,
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.header)

    def text_to_speech_stream(self, text: str) -> requests.Response:
        payload = {
            "text": text,
            "speaker_no": self.config.speaker_no,
            "config": {
                "use_streaming_response": True,
                "sample_rate": 16000,
            }
        }

        response = self.session.post(
            url=self.config.base_url,
            json=payload,
            stream=True
        )
        return response
