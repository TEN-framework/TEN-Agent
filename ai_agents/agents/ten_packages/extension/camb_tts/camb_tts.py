#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from typing import Any, AsyncIterator, Tuple

import aiohttp

from .config import CambTTSConfig
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient


BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1

# Model-specific sample rates (matching livekit)
MODEL_SAMPLE_RATES: dict[str, int] = {
    "mars-flash": 22050,
    "mars-pro": 48000,
    "mars-instruct": 22050,
}

# Defaults matching livekit
DEFAULT_VOICE_ID = 147320
DEFAULT_MODEL = "mars-flash"
DEFAULT_LANGUAGE = "en-us"

API_BASE_URL = "https://client.camb.ai/apis"
API_KEY_HEADER = "x-api-key"


class CambTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: CambTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.api_key = config.params.get("api_key", "")
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        try:
            self._session = aiohttp.ClientSession()
        except Exception:
            self._session = None

    async def cancel(self):
        self.ten_env.log_debug("CambTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request using raw HTTP (like livekit)."""
        self._is_cancelled = False

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"CambTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        # Validate text length (Camb.ai requires 3-3000 characters)
        text_len = len(text.strip())
        if text_len < 3:
            self.ten_env.log_warn(
                f"CambTTS: text too short ({text_len} chars, min 3) for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        if text_len > 3000:
            error_message = f"CambTTS: text too long ({text_len} chars, max 3000) for request_id: {request_id}."
            self.ten_env.log_error(
                error_message,
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR
            return

        try:
            speech_model = self.config.params.get("speech_model", DEFAULT_MODEL)
            voice_id = self.config.params.get("voice_id", DEFAULT_VOICE_ID)
            language = self.config.params.get("language", DEFAULT_LANGUAGE)
            output_format = self.config.params.get("format", "pcm_s16le")

            # Build payload (same structure as livekit)
            payload: dict = {
                "text": text,
                "voice_id": voice_id,
                "language": language,
                "speech_model": speech_model,
                "output_configuration": {
                    "format": output_format,
                },
            }

            # Add user_instructions only for mars-instruct model
            user_instructions = self.config.params.get("user_instructions")
            if speech_model == "mars-instruct" and user_instructions:
                payload["user_instructions"] = user_instructions

            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers[API_KEY_HEADER] = self.api_key

            self.ten_env.log_debug(
                f"CambTTS: requesting voice_id={voice_id}, model={speech_model}, format={output_format} for request_id: {request_id}."
            )

            async with self._session.post(
                f"{API_BASE_URL}/tts-stream",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status in (401, 403):
                    error_message = "Invalid Camb.ai API key."
                    self.ten_env.log_error(
                        f"CambTTS: {error_message} for request_id: {request_id}.",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                    return

                if resp.status != 200:
                    content = await resp.text()
                    error_message = f"API Error {resp.status}: {content}"
                    self.ten_env.log_error(
                        f"CambTTS: {error_message} for request_id: {request_id}.",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.ERROR
                    return

                # Stream audio chunks (same as livekit: resp.content.iter_chunks())
                async for data, _ in resp.content.iter_chunks():
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"CambTTS: cancellation detected for request_id: {request_id}."
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        break

                    if data and len(data) > 0:
                        self.ten_env.log_debug(
                            f"CambTTS: received {len(data)} bytes for request_id: {request_id}."
                        )
                        yield bytes(data), TTS2HttpResponseEventType.RESPONSE

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"CambTTS: stream complete for request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"CambTTS error: {error_message} for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        self.ten_env.log_debug("CambTTS: clean() called.")
        if self._session:
            await self._session.close()
            self._session = None

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "voice_id": self.config.params.get("voice_id", DEFAULT_VOICE_ID),
            "speech_model": self.config.params.get(
                "speech_model", DEFAULT_MODEL
            ),
        }

    def get_sample_rate(self) -> int:
        """Return the sample rate based on the selected model."""
        speech_model = self.config.params.get("speech_model", DEFAULT_MODEL)
        return MODEL_SAMPLE_RATES.get(speech_model, 22050)
