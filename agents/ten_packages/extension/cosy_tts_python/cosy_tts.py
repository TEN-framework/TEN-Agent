import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Iterator

from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig
import dashscope
from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
from dashscope.audio.tts_v2 import *


@dataclass
class CosyTTSConfig(BaseConfig):
    api_key: str = ""
    voice: str = "longxiaochun"
    model: str = "cosyvoice-v1"
    sample_rate: int = 16000


class AsyncIteratorCallback(ResultCallback):
    def __init__(self, ten_env: AsyncTenEnv) -> None:
        self.queue = asyncio.Queue()
        self.closed = False
        self.ten_env = ten_env
        self.loop = asyncio.get_event_loop()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            data = await self.queue.get()
            if data is None:
                break
            yield data

    def close(self):
        self.closed = True
        asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)

    def on_open(self):
        self.ten_env.log_info("websocket is open.")

    def on_complete(self):
        self.ten_env.log_info("speech synthesis task complete successfully.")

    def on_error(self, message: str):
        self.ten_env.log_error(f"speech synthesis task failed, {message}")

    def on_close(self):
        self.ten_env.log_info("websocket is closed.")
        self.close()

    def on_event(self, message):
        pass
        # self.ten_env.log_info(f"recv speech synthesis message {message}")

    def on_data(self, data: bytes) -> None:
        # self.ten_env.log_info(f"recv speech synthesis data {len(data)}")
        asyncio.run_coroutine_threadsafe(self.queue.put(data), self.loop)

class CosyTTS:
    def __init__(self, config: CosyTTSConfig) -> None:
        self.config = config
        dashscope.api_key = config.api_key

    def text_to_speech_stream(self, ten_env:AsyncTenEnv, text: str, end_of_segment: bool) -> AsyncIterator[bytes]:
        callback = AsyncIteratorCallback(ten_env)
        synthesizer = SpeechSynthesizer(
            model=self.config.model,
            voice=self.config.voice,
            format=AudioFormat.PCM_16000HZ_MONO_16BIT,  
            callback=callback,
        )

        synthesizer.streaming_call(text)  # Direct call since it's synchronous
        synthesizer.streaming_complete()  # Direct call since it's synchronous
        return callback