#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import traceback
from ten.data import Data
from ten_ai_base.tts import AsyncTTSBaseExtension
from .minimax_tts import MinimaxTTS, MinimaxTTSConfig
from ten import (
    AsyncTenEnv,
)


class MinimaxTTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.client = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        config = MinimaxTTSConfig.create(ten_env=ten_env)

        ten_env.log_info(f"config: {config.api_key}, {config.group_id}")

        if not config.api_key or not config.group_id:
            raise ValueError("api_key and group_id are required")

        self.client = MinimaxTTS(config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(self, ten_env: AsyncTenEnv, input_text: str) -> None:
        try:
            self.begin_send_audio_out(ten_env, sample_rate=self.client.config.sample_rate)
            data = self.client.get(ten_env, input_text)
            async for frame in data:
                self.send_audio_out(ten_env, frame)
            self.end_send_audio_out(ten_env)
        except Exception as err:
            ten_env.log_error(f"on_request_tts failed: {traceback.format_exc()}")
