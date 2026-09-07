import time
from typing import AsyncIterator

# Only import the specific TTS modules we need to avoid PortAudio dependency
from fish_audio_sdk import AsyncWebSocketSession, TTSRequest
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from .config import FishAudioTTSConfig

# Custom event types to communicate status back to the extension
EVENT_TTS_RESPONSE = 1
EVENT_TTS_END = 2
EVENT_TTS_ERROR = 3
EVENT_TTS_INVALID_KEY_ERROR = 4
EVENT_TTS_FLUSH = 5


class FishAudioTTSClient:
    def __init__(self, config: FishAudioTTSConfig, ten_env: AsyncTenEnv):
        self.config = config
        self.ten_env = ten_env
        self.client: AsyncWebSocketSession | None = self._create_session()
        self._is_cancelled = False

    def _create_session(self) -> AsyncWebSocketSession:
        if self.config.base_url.strip() != "":
            return AsyncWebSocketSession(
                self.config.api_key, base_url=self.config.base_url
            )
        return AsyncWebSocketSession(self.config.api_key)

    async def _text_stream(self, text: str) -> AsyncIterator[str]:
        yield text

    async def get(self, text: str) -> AsyncIterator[tuple[bytes | None, int]]:
        """Process a single TTS request in serial manner"""
        self._is_cancelled = False
        if self.client is None:
            self.client = self._create_session()

        session = self.client

        tts_request = TTSRequest(
            text="", chunk_length=200, **self.config.params
        )

        start_time = time.time()

        try:
            gen = session.tts(
                request=tts_request,
                text_stream=self._text_stream(text),
                backend=self.config.backend,
            )
            async for chunk in gen:
                if self._is_cancelled:
                    self.ten_env.log_debug(
                        "Cancellation flag detected, sending flush event and stopping TTS stream."
                    )
                    yield None, EVENT_TTS_FLUSH
                    return

                self.ten_env.log_debug(
                    f"FishAudioTTS: sending EVENT_TTS_RESPONSE, length: {len(chunk)}"
                )
                if len(chunk) > 0:
                    yield chunk, EVENT_TTS_RESPONSE

                # Only send EVENT_TTS_END if not cancelled (flush event already sent)

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"FishAudioTTS: sending EVENT_TTS_END, total time: {time.time() - start_time}"
                )
                yield None, EVENT_TTS_END

        except Exception as e:
            if self._is_cancelled:
                self.ten_env.log_debug(
                    "FishAudioTTS: vendor stream stopped after cancellation."
                )
                yield None, EVENT_TTS_FLUSH
                return

            error_message = str(e)
            self.ten_env.log_error(
                "vendor_error: "
                f"type={type(e).__name__}, message={error_message}",
                category=LOG_CATEGORY_VENDOR,
            )

            # Check if it's an API key authentication error
            if (
                "402" in error_message and "Payment Required" in error_message
            ) or ("Payment Required" in error_message):
                yield error_message.encode("utf-8"), EVENT_TTS_INVALID_KEY_ERROR
            else:
                yield error_message.encode("utf-8"), EVENT_TTS_ERROR

    async def cancel(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: cancel() called.")
        self._is_cancelled = True

        # Closing the owning SDK session tears down the active WebSocket and
        # releases a blocked receive immediately. Do not call gen.aclose(): the
        # Fish Audio SDK performs a graceful WebSocket context shutdown there,
        # which can wait forever after an interrupted stream.
        session = self.client
        self.client = None
        if session is not None:
            try:
                await session.close()
            except Exception as close_error:
                self.ten_env.log_warn(
                    "FishAudioTTS: failed to close cancelled session: "
                    f"{close_error}"
                )

    async def clean(self) -> None:
        self.ten_env.log_debug("FishAudioTTS: clean() called.")
        session = self.client
        self.client = None
        if session is not None:
            try:
                await session.close()
            except Exception as close_error:
                # Shutdown must continue even when the vendor connection is
                # already broken. Avoid logging exception repr because HTTP
                # exception objects may retain sensitive request headers.
                self.ten_env.log_warn(
                    "FishAudioTTS: failed to close session during cleanup: "
                    f"type={type(close_error).__name__}, "
                    f"message={str(close_error)}"
                )
