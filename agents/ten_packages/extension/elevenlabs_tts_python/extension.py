#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import traceback

from ten_ai_base.helper import PCMWriter
from .elevenlabs_tts import ElevenLabsTTS, ElevenLabsTTSConfig
from ten import (
    AsyncTenEnv,
)
from ten_ai_base.tts import AsyncTTSBaseExtension

class ElevenLabsTTSExtension(AsyncTTSBaseExtension):
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
            self.config = ElevenLabsTTSConfig.create(ten_env=ten_env)

            if not self.config.api_key:
                raise ValueError("api_key is required")

            self.client = ElevenLabsTTS(self.config)
        except Exception as err:
            ten_env.log_error(f"on_start failed: {traceback.format_exc()}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool) -> None:
        audio_stream = await self.client.text_to_speech_stream(input_text)

        async for audio_data in audio_stream:
            self.send_audio_out(ten_env, audio_data)

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        return await super().on_cancel_tts(ten_env)