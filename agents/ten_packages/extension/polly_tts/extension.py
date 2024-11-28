from ten_ai_base.tts import AsyncTTSBaseExtension
from .polly_tts import PollyTTS, PollyTTSConfig
import traceback
from ten import (
    AsyncTenEnv,
)
PROPERTY_REGION = "region"  # Optional
PROPERTY_ACCESS_KEY = "access_key"  # Optional
PROPERTY_SECRET_KEY = "secret_key"  # Optional
PROPERTY_ENGINE = "engine"  # Optional
PROPERTY_VOICE = "voice"  # Optional
PROPERTY_SAMPLE_RATE = "sample_rate"  # Optional
PROPERTY_LANG_CODE = "lang_code"  # Optional

class PollyTTSExtension(AsyncTTSBaseExtension):
    def __init__(self, name: str):
        super().__init__(name)
        self.client = None
        self.config = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        await super().on_init(ten_env)
        ten_env.log_debug("on_init")

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        await super().on_start(ten_env)
        ten_env.log_debug("on_start")

        self.config = PollyTTSConfig.create(ten_env=ten_env)

        ten_env.log_info(f"config: {self.config.api_key}, {self.config.group_id}")

        if not self.config.access_key or not self.config.secret_key:
            ten_env.log_info("access_key and secret_key are required")
            raise ValueError("access_key and secret_key are required")
        
        ten_env.log_info(f"start init client")
        self.client = PollyTTS(self.config)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool) -> None:
        ten_env.log_info(f"on_request_tts: {input_text}")
        try:
            data = self.client.get(ten_env, input_text, end_of_segment)
            async for frame in data:
                self.send_audio_out(ten_env, frame, sample_rate=self.client.config.sample_rate)
        except Exception as err:
            ten_env.log_error(f"on_request_tts failed: {traceback.format_exc()}")

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        return await super().on_cancel_tts(ten_env)