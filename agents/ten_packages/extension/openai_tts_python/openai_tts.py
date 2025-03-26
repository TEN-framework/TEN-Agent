from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator
from openai import AsyncOpenAI
from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig


@dataclass
class OpenAITTSConfig(BaseConfig):
    api_key: str = ""
    model: str = "gpt-4o-mini-tts"
    voice: str = "coral"
    instructions: str = "Speak in a cheerful and positive tone."
    response_format = "pcm"


class OpenAITTS:
    def __init__(self, config: OpenAITTSConfig):
        self.config = config
        self.openai = AsyncOpenAI()

    async def get(self, ten_env: AsyncTenEnv, text: str) -> AsyncIterator[bytes]:
        async with self.openai.audio.speech.with_streaming_response.create(
            model=self.config.model,
            voice=self.config.voice,
            input=text,
            instructions=self.config.instructions,
            response_format="pcm",
        ) as response:
            async for chunk in response.iter_bytes():
                yield chunk

    def _duration_in_ms(self, start: datetime, end: datetime) -> int:
        return int((end - start).total_seconds() * 1000)

    def _duration_in_ms_since(self, start: datetime) -> int:
        return self._duration_in_ms(start, datetime.now())
