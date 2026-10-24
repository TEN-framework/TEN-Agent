from typing import Any, AsyncIterator, Tuple
import base64
import io
import wave
from httpx import AsyncClient, Timeout, Limits

from .config import SarvamTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient


BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1


def wav_to_pcm(wav_data: bytes) -> bytes:
    """Convert WAV format audio data to PCM format"""
    try:
        # Create a BytesIO object from the WAV data
        wav_io = io.BytesIO(wav_data)

        # Open the WAV data with wave module
        with wave.open(wav_io, "rb") as wav_file:
            # Read all frames (PCM data)
            pcm_data = wav_file.readframes(wav_file.getnframes())
            return pcm_data

    except Exception:
        # If conversion fails, return original data
        # This handles cases where the data might already be PCM
        return wav_data


class SarvamTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: SarvamTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.api_subscription_key = config.params.get(
            "api_subscription_key", ""
        )
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        self.endpoint = config.params.get(
            "endpoint", "https://api.sarvam.ai/text-to-speech"
        )
        self.headers = {
            "api-subscription-key": self.api_subscription_key,
            "Content-Type": "application/json",
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
        self.observe_http_ttfb(self.client)

    async def cancel(self):
        self.ten_env.log_debug("SarvamTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request in serial manner"""
        self._is_cancelled = False
        if not self.client:
            self.ten_env.log_error(
                f"SarvamTTS: client not initialized for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"SarvamTTS: client not initialized for request_id: {request_id}."
            )

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"SarvamTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Shallow copy params and strip api_subscription_key before sending to API
            payload = {**self.config.params}
            payload.pop("api_subscription_key", None)

            # Ensure text is in the payload
            payload["text"] = text

            # Make POST request to Sarvam API
            response = await self.client.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
            )

            if self._is_cancelled:
                self.ten_env.log_debug(
                    f"Cancellation flag detected, sending flush event and stopping TTS stream of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.FLUSH
                return

            # Check response status
            if response.status_code != 200:
                error_message = f"HTTP {response.status_code}: {response.text}"
                self.ten_env.log_error(
                    f"vendor_error: {error_message} of request_id: {request_id}.",
                    category=LOG_CATEGORY_VENDOR,
                )
                if response.status_code == 401 or response.status_code == 403:
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                else:
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.ERROR
                return

            # Parse JSON response
            response_data = response.json()
            audios = response_data.get("audios", [])

            if not audios or len(audios) == 0:
                self.ten_env.log_warn(
                    f"SarvamTTS: no audio data in response for request_id: {request_id}.",
                    category=LOG_CATEGORY_VENDOR,
                )
                yield None, TTS2HttpResponseEventType.END
                return

            # Decode base64 WAV data
            audio_base64 = audios[0]
            try:
                wav_bytes = base64.b64decode(audio_base64)
                if wav_bytes:
                    self.record_audio_received()
                # Convert WAV to PCM
                pcm_data = wav_to_pcm(wav_bytes)

                self.ten_env.log_debug(
                    f"SarvamTTS: decoded WAV ({len(wav_bytes)} bytes) to PCM ({len(pcm_data)} bytes) for request_id: {request_id}."
                )

                if len(pcm_data) > 0:
                    yield pcm_data, TTS2HttpResponseEventType.RESPONSE
                else:
                    yield None, TTS2HttpResponseEventType.END

            except Exception as decode_error:
                error_message = f"Failed to decode audio: {str(decode_error)}"
                self.ten_env.log_error(
                    f"vendor_error: {error_message} of request_id: {request_id}.",
                    category=LOG_CATEGORY_VENDOR,
                )
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR
                return

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"SarvamTTS: sending EVENT_TTS_END of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            # Check if it's an API key authentication error
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            if "401" in error_message or "403" in error_message:
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
        self.ten_env.log_debug("SarvamTTS: clean() called.")
        try:
            await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "speaker": self.config.params.get("speaker", ""),
            "model": self.config.params.get("model", ""),
            "target_language_code": self.config.params.get(
                "target_language_code", ""
            ),
        }
