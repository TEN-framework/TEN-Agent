#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import traceback
from ten_ai_base.tts import AsyncTTSBaseExtension
from .openai_tts import OpenAITTS, OpenAITTSConfig
from ten import (
    AsyncTenEnv,
)


class OpenAITTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.client = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        config = await OpenAITTSConfig.create_async(ten_env=ten_env)

        if not config.api_key:
            raise ValueError("api_key is required")

        self.client = OpenAITTS(config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(
        self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool
    ) -> None:
        try:
            data = self.client.get(ten_env, input_text)
            async for frame in data:
                await self.send_audio_out(ten_env, frame, sample_rate=16000)
        except Exception:
            ten_env.log_error(f"on_request_tts failed: {traceback.format_exc()}")

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        return await super().on_cancel_tts(ten_env)
