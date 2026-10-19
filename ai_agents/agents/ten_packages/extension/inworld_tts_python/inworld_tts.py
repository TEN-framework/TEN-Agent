#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from typing import Any, AsyncIterator, Tuple
import aiohttp
import base64
import json

from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient

from .config import InworldTTSConfig

BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1

# Inworld TTS API endpoints
INWORLD_TTS_STREAM_URL = "https://api.inworld.ai/tts/v1/voice:stream"


class InworldTTSClient(AsyncTTS2HttpClient):
    def __init__(
        self,
        config: InworldTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        self._session: aiohttp.ClientSession | None = None

        try:
            api_key = config.params.get("api_key", "")
            if not api_key:
                raise ValueError("API key is required for Inworld TTS")

            # Create aiohttp session with auth header
            self._headers = {
                "Authorization": f"Basic {api_key}",
                "Content-Type": "application/json",
            }
            ten_env.log_info("InworldTTS client initialized successfully")
        except Exception as e:
            ten_env.log_error(
                f"error when initializing InworldTTS: {e}",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"error when initializing InworldTTS: {e}"
            ) from e

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def cancel(self):
        self.ten_env.log_debug("InworldTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request using Inworld API."""
        self._is_cancelled = False

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"InworldTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            session = await self._ensure_session()

            # Build request payload
            # Current API field names: voiceId/modelId (voice/model are
            # rejected with "voice_id can not be empty").
            payload = {
                "text": text,
                "voiceId": self.config.params.get("voice", "Ashley"),
                "modelId": self.config.params.get(
                    "model", "inworld-tts-1.5-max"
                ),
                "audio_config": {
                    "audio_encoding": self.config.params.get(
                        "encoding", "LINEAR16"
                    ),
                    "sample_rate_hertz": self.config.params.get(
                        "sample_rate", 24000
                    ),
                },
            }

            # Add optional parameters
            if "temperature" in self.config.params:
                payload["temperature"] = self.config.params["temperature"]
            if "speaking_rate" in self.config.params:
                payload["speakingRate"] = self.config.params["speaking_rate"]
            if "text_normalization" in self.config.params:
                payload["textNormalization"] = self.config.params[
                    "text_normalization"
                ]

            self.ten_env.log_debug(
                f"InworldTTS: sending request for request_id: {request_id}, "
                f"voice: {payload['voiceId']}, model: {payload['modelId']}"
            )

            async with session.post(
                INWORLD_TTS_STREAM_URL, json=payload
            ) as response:
                if response.status in (401, 403):
                    # The service reports bad credentials as 403
                    # ("Invalid authorization credentials").
                    error_message = f"Invalid API key (HTTP {response.status})"
                    self.ten_env.log_error(
                        f"InworldTTS: {error_message} for request_id: {request_id}.",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                    return

                if response.status != 200:
                    error_text = await response.text()
                    error_message = f"API error {response.status}: {error_text}"
                    self.ten_env.log_error(
                        f"InworldTTS: {error_message} for request_id: {request_id}.",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    yield error_message.encode(
                        "utf-8"
                    ), TTS2HttpResponseEventType.ERROR
                    return

                cache_audio_bytes = bytearray()

                # Process streaming response (NDJSON format)
                async for line in response.content:
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"Cancellation flag detected, sending flush event "
                            f"and stopping TTS stream of request_id: {request_id}."
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        return

                    line = line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # Check for error in response
                        if "error" in data:
                            error_message = data["error"].get(
                                "message", "Unknown error"
                            )
                            self.ten_env.log_error(
                                f"InworldTTS: API error: {error_message} "
                                f"for request_id: {request_id}.",
                                category=LOG_CATEGORY_VENDOR,
                            )
                            yield error_message.encode(
                                "utf-8"
                            ), TTS2HttpResponseEventType.ERROR
                            return

                        # Extract audio data (base64 encoded). The
                        # current API nests it under result.
                        audio_b64 = (
                            (data.get("result") or {}).get("audioContent")
                            or data.get("audioContent")
                            or data.get("audio", {}).get("content")
                        )
                        if audio_b64:
                            chunk = base64.b64decode(audio_b64)

                            # Each streamed chunk is a self-contained
                            # WAV; strip its header to get raw pcm.
                            if chunk[:4] == b"RIFF":
                                data_pos = chunk.find(b"data", 12)
                                if data_pos != -1:
                                    chunk = chunk[data_pos + 8 :]

                            self.ten_env.log_debug(
                                f"InworldTTS: received audio chunk, "
                                f"length: {len(chunk)} for request_id: {request_id}."
                            )

                            # Handle byte alignment
                            if len(cache_audio_bytes) > 0:
                                chunk = cache_audio_bytes + chunk
                                cache_audio_bytes = bytearray()

                            left_size = len(chunk) % (
                                BYTES_PER_SAMPLE * NUMBER_OF_CHANNELS
                            )

                            if left_size > 0:
                                cache_audio_bytes = bytearray(
                                    chunk[-left_size:]
                                )
                                chunk = chunk[:-left_size]

                            if len(chunk) > 0:
                                yield bytes(
                                    chunk
                                ), TTS2HttpResponseEventType.RESPONSE

                    except json.JSONDecodeError:
                        # Skip non-JSON lines
                        continue

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"InworldTTS: sending EVENT_TTS_END of request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except aiohttp.ClientError as e:
            error_message = f"Network error: {str(e)}"
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        """Clean up resources"""
        self.ten_env.log_debug("InworldTTS: clean() called.")
        try:
            if self._session and not self._session.closed:
                await self._session.close()
        finally:
            self._session = None

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "model": self.config.params.get("model", "inworld-tts-1.5-max"),
            "voice": self.config.params.get("voice", "Ashley"),
        }
