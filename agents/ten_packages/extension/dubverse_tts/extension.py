#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    AsyncTenEnv,
)
from ten_ai_base.tts import AsyncTTSBaseExtension
from .dubverse_tts import DubverseTTS, DubverseTTSConfig
import traceback


class DubverseTTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        try:
            await super().on_start(ten_env)
            ten_env.log_debug("on_start")
            self.config = await DubverseTTSConfig.create_async(ten_env=ten_env)

            if not self.config.api_key:
                raise ValueError("api_key is required")

            self.client = DubverseTTS(self.config)
        except Exception:
            ten_env.log_error(f"on_start failed: {traceback.format_exc()}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(
        self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool
    ) -> None:
        skip_bytes = 44
        header_skipped = False
        audio_stream = self.client.text_to_speech_stream(input_text)
        for chunk in audio_stream.iter_content(chunk_size=1024 * 8):
            if not header_skipped:
                chunk = chunk[skip_bytes:]
                header_skipped = True
                if not chunk:
                    continue  # in case the first chunk was less than 44 bytes
            await self.send_audio_out(ten_env, chunk)
        ten_env.log_info(f"on_request_tts: {input_text} done")

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        return await super().on_cancel_tts(ten_env)
