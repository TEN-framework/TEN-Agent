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
        try:
            await super().on_start(ten_env)
            ten_env.log_debug("on_start")
            self.config = await PollyTTSConfig.create_async(ten_env=ten_env)

            if not self.config.access_key or not self.config.secret_key:
                raise ValueError("access_key and secret_key are required")

            self.client = PollyTTS(self.config, ten_env)
        except Exception:
            ten_env.log_error(f"on_start failed: {traceback.format_exc()}")

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        await super().on_stop(ten_env)
        ten_env.log_debug("on_stop")

        # TODO: clean up resources

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        await super().on_deinit(ten_env)
        ten_env.log_debug("on_deinit")

    async def on_request_tts(
        self, ten_env: AsyncTenEnv, input_text: str, end_of_segment: bool
    ) -> None:
        try:
            data = self.client.text_to_speech_stream(ten_env, input_text, end_of_segment)
            async for frame in data:
                await self.send_audio_out(
                    ten_env, frame, sample_rate=self.client.config.sample_rate
                )
        except Exception:
            ten_env.log_error(f"on_request_tts failed: {traceback.format_exc()}")

    async def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        """
        Cancel ongoing TTS operation
        """
        await super().on_cancel_tts(ten_env)
        try:
            if self.client:
                self.client._on_cancel_tts(ten_env)
        except Exception:
            ten_env.log_error(f"on_cancel_tts failed: {traceback.format_exc()}")
