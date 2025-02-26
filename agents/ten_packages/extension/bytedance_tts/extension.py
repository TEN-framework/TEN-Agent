#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import traceback

from .bytedance_tts import TTSConfig, TTSClient
from ten import (
    AsyncTenEnv,
)
from ten_ai_base.tts import AsyncTTSBaseExtension


class BytedanceTTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config = None
        self.client = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_start(ten_env)
            ten_env.log_debug("on_start")
            self.config = await TTSConfig.create_async(ten_env=ten_env)

            if not self.config.appid:
                raise ValueError("appid is required")

            if not self.config.token:
                raise ValueError("token is required")

            self.client = TTSClient(config=self.config, ten_env=ten_env)
            await self.client.connect()
        except Exception:
            ten_env.log_error(f"on_start failed: {traceback.format_exc()}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.close()

        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(
        self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool
    ) -> None:
        async for audio_data in self.client.text_to_speech_stream(input_text):
            await self.send_audio_out(ten_env, audio_data)

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        await self.client.cancel()
