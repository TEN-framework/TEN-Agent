from typing import Any, AsyncIterator, Tuple
from httpx import AsyncClient, Timeout, Limits

from .config import GandrTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient


BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1
# Gandr streams raw PCM as s16le, mono, 24000 Hz.
GANDR_SAMPLE_RATE = 24000


class GandrTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: GandrTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.api_key = config.params.get("api_key", "")
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        self.endpoint = config.params.get(
            "endpoint", "https://tts.gandr.ai/v1/audio/speech"
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }
        self.client = AsyncClient(
            timeout=Timeout(timeout=20.0),
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=600.0,  # 10 minutes keepalive
            ),
            http2=True,  # Enable HTTP/2 if server supports it
        )

    async def cancel(self):
        self.ten_env.log_debug("GandrTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request in serial manner"""
        self._is_cancelled = False
        if not self.client:
            self.ten_env.log_error(
                f"GandrTTS: client not initialized for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"GandrTTS: client not initialized for request_id: {request_id}."
            )

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"GandrTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Shallow copy params and strip api_key before sending to API
            payload = {**self.config.params}
            payload.pop("api_key", None)

            async with self.client.stream(
                "POST",
                self.endpoint,
                headers=self.headers,
                json={
                    "input": text,
                    **payload,
                },
            ) as response:
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"Cancellation flag detected, sending flush event and stopping TTS stream of request_id: {request_id}."
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        break

                    self.ten_env.log_debug(
                        f"GandrTTS: sending EVENT_TTS_RESPONSE, length: {len(chunk)} of request_id: {request_id}."
                    )

                    if len(chunk) > 0:
                        yield bytes(chunk), TTS2HttpResponseEventType.RESPONSE
                    else:
                        yield None, TTS2HttpResponseEventType.END

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"GandrTTS: sending EVENT_TTS_END of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            # Check if it's an API key authentication error
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            if "401" in error_message:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        # In this new model, most cleanup is handled by the connection object's lifecycle.
        # This can be used for any additional cleanup if needed.
        self.ten_env.log_debug("GandrTTS: clean() called.")
        try:
            await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "voice": self.config.params.get("voice", ""),
            "model": self.config.params.get("model", ""),
        }
