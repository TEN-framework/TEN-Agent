#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from typing import Any, AsyncGenerator, AsyncIterator, Tuple

from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient
from ten_runtime import AsyncTenEnv
from typecast import AsyncTypecast, TypecastError
from typecast.models import TTSRequestStream

from .config import TypecastTTSConfig
from .pcm import StreamingWavToPcm16

TYPECAST_STREAM_SAMPLE_RATE = 32000


class TypecastTTSClient(AsyncTTS2HttpClient):
    """Typecast TTS client backed by the official Typecast Python SDK."""

    def __init__(self, config: TypecastTTSConfig, ten_env: AsyncTenEnv):
        super().__init__()
        self.config = config
        self.ten_env = ten_env
        self._is_cancelled = False
        self._client: AsyncTypecast | None = None
        self._stream: AsyncGenerator[bytes, None] | None = None

        ten_env.log_info(f"TypecastTTS initialized with URL: {self.config.url}")

    async def _ensure_client(self) -> AsyncTypecast:
        if self._client is None:
            self._client = AsyncTypecast(
                host=self.config.url,
                api_key=self.config.params["api_key"],
            )
            await self._client.__aenter__()
            self._client.session.headers["User-Agent"] += " ten-framework"
        return self._client

    async def cancel(self):
        self.ten_env.log_debug("TypecastTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        self._is_cancelled = False

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"TypecastTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            payload = {**self.config.params}
            payload.pop("api_key", None)

            output = dict(payload.get("output") or {})
            output["audio_format"] = "wav"
            payload["output"] = output
            payload["text"] = text

            request = TTSRequestStream.model_validate(payload)
            converter = StreamingWavToPcm16()
            client = await self._ensure_client()

            self.ten_env.log_debug(
                f"TypecastTTS: sending request for request_id: {request_id}"
            )

            self._stream = client.text_to_speech_stream(
                request, chunk_size=self.config.chunk_size
            )
            async for chunk in self._stream:
                if self._is_cancelled:
                    self.ten_env.log_debug(
                        f"Cancellation detected, flushing TTS stream for request_id: {request_id}"
                    )
                    yield None, TTS2HttpResponseEventType.FLUSH
                    return

                pcm = converter.feed(chunk)
                if pcm:
                    yield pcm, TTS2HttpResponseEventType.RESPONSE

            if not self._is_cancelled:
                converter.finish()
                self.ten_env.log_debug(
                    f"TypecastTTS: sending END event for request_id: {request_id}"
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} for request_id: {request_id}",
                category=LOG_CATEGORY_VENDOR,
            )
            event = (
                TTS2HttpResponseEventType.INVALID_KEY_ERROR
                if isinstance(e, TypecastError)
                and getattr(e, "status_code", None) in (401, 403)
                else TTS2HttpResponseEventType.ERROR
            )
            yield error_message.encode("utf-8"), event

    async def close_stream(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            await stream.aclose()

    async def clean(self):
        self.ten_env.log_debug("TypecastTTS: clean() called.")
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    def get_extra_metadata(self) -> dict[str, Any]:
        return {
            "vendor": "typecast",
            "model": self.config.params.get("model", ""),
            "voice_id": self.config.params.get("voice_id", ""),
        }
