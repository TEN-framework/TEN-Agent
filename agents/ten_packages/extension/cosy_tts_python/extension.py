#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from .cosy_tts import CosyTTS, CosyTTSConfig
from ten import (
    AudioFrame,
    VideoFrame,
    AsyncExtension,
    AsyncTenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)
from ten_ai_base.tts import AsyncTTSBaseExtension


class CosyTTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.client = None
        self.config = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        self.config = CosyTTSConfig.create(ten_env=ten_env)
        self.client = CosyTTS(self.config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool) -> None:
        audio_stream = self.client.text_to_speech_stream(ten_env, input_text, end_of_segment)

        self.begin_send_audio_out(ten_env)
        async for audio_data in audio_stream:
            self.send_audio_out(ten_env, audio_data)
        self.end_send_audio_out(ten_env)

    
    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        self.client.cancel()
