#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import asyncio
import time
from typing import Awaitable, Callable, Tuple

import httpx
from speechify import AsyncSpeechify
from speechify.core.api_error import ApiError

from ten_ai_base.message import (
    ModuleError,
    ModuleErrorCode,
    ModuleErrorVendorInfo,
    ModuleVendorException,
)
from ten_ai_base import ModuleType
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_runtime import AsyncTenEnv
from .config import SpeechifyTTSConfig

# Every outbound Speechify request must attribute usage to this integration;
# see docs.speechify.ai's third-party integration guidelines.
CALLER_HEADER = "Speechify-Caller"
CALLER_VALUE = "ten-framework"

VENDOR = "speechify"


class SpeechifyTTSSynthesizer:
    """
    Speechify's public API (`POST /v1/audio/stream/with-timestamps`) is a
    one-shot request/response HTTP endpoint that returns audio with word-level
    timestamps, unlike ElevenLabs' persistent bidirectional websocket. A
    synthesizer instance therefore represents a single TTS request: text deltas
    are buffered as they arrive and only sent once `text_input_end` closes the
    request, at which point the audio and speech marks are returned.
    """

    def __init__(
        self,
        sdk_client: AsyncSpeechify,
        config: SpeechifyTTSConfig,
        ten_env: AsyncTenEnv,
        error_callback: Callable[[str, ModuleError], Awaitable[None]] = None,
        response_msgs: asyncio.Queue[Tuple[bytes, bool, str, int]] = None,
    ) -> None:
        self.sdk_client = sdk_client
        self.config = config
        self.ten_env = ten_env
        self.error_callback = error_callback
        self.response_msgs = response_msgs

        self.text_buffer = ""
        self.request_id: str | None = None
        # Whether any non-empty text has been buffered for this request, i.e.
        # whether cancelling it would actually interrupt an in-flight call.
        self.send_text_in_connection = False
        self._closing = False
        self.stream_task: asyncio.Task | None = None

    async def send_text(self, text_data) -> None:
        if self.request_id is None:
            self.request_id = text_data.request_id

        if text_data.text:
            self.text_buffer += text_data.text
            self.send_text_in_connection = True
            self.ten_env.log_debug(
                f"send_text_to_tts_server: {text_data.text} of request_id: {text_data.request_id}",
                category=LOG_CATEGORY_VENDOR,
            )

        if text_data.text_input_end:
            self.stream_task = asyncio.create_task(self._run_stream())

    async def _run_stream(self) -> None:
        text = self.text_buffer
        if text.strip() == "":
            if self.response_msgs is not None:
                await self.response_msgs.put((None, True, "", None))
            return

        start_ts = time.time()
        first_chunk = True
        try:
            options = {}
            if self.config.params.get("loudness_normalization") is not None:
                options["loudness_normalization"] = self.config.params.get(
                    "loudness_normalization"
                )
            if self.config.params.get("text_normalization") is not None:
                options["text_normalization"] = self.config.params.get(
                    "text_normalization"
                )

            # Direct HTTP call to /v1/audio/stream/with-timestamps for word-level timing
            base_url = self.config.params.get("base_url") or "https://api.sws.speechify.com"
            url = f"{base_url}/v1/audio/stream/with-timestamps"
            
            request_body = {
                "input": text,
                "voice_id": self.config.params.get("voice_id"),
                "model": self.config.params.get("model", "simba-3.2"),
                "output_format": f"pcm_{self.config.sample_rate}",
            }
            
            if self.config.params.get("language"):
                request_body["language"] = self.config.params.get("language")
            
            if options:
                request_body["options"] = options
            
            headers = {
                "Authorization": f"Bearer {self.config.params.get('key')}",
                "Content-Type": "application/json",
                CALLER_HEADER: CALLER_VALUE,
            }
            
            # Get the httpx client from parent
            import json
            response = await self.sdk_client._client.post(
                url,
                headers=headers,
                content=json.dumps(request_body),
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise ApiError(status_code=response.status_code, body=error_text)
            
            # Parse JSON response
            data = response.json()
            audio_data = data.get("audio_data", "")
            
            # Decode base64 audio and stream it in chunks
            import base64
            audio_bytes = base64.b64decode(audio_data)
            
            # Stream audio in chunks
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                if self._closing:
                    return
                ttfb_ms = None
                if first_chunk:
                    ttfb_ms = int((time.time() - start_ts) * 1000)
                    first_chunk = False
                if self.response_msgs is not None:
                    await self.response_msgs.put((chunk, False, "", ttfb_ms))

            if self.response_msgs is not None:
                await self.response_msgs.put((None, True, text, None))

        except ApiError as e:
            error_info = ModuleErrorVendorInfo(
                vendor=VENDOR,
                code=str(e.status_code or 0),
                message=str(e.body or e),
            )
            self.ten_env.log_error(
                f"vendor_error: code: {e.status_code} reason: {e.body}",
                category=LOG_CATEGORY_VENDOR,
            )
            # 401/403 mean the request cannot succeed on retry either, so
            # treat auth failures as fatal and everything else as per-request.
            code = (
                ModuleErrorCode.FATAL_ERROR
                if e.status_code in (401, 403)
                else ModuleErrorCode.NON_FATAL_ERROR
            )
            if self.error_callback:
                await self.error_callback(
                    self.request_id or "",
                    ModuleError(
                        message=str(e.body or e),
                        module=ModuleType.TTS,
                        code=code,
                        vendor_info=error_info,
                    ),
                )
            else:
                raise ModuleVendorException(error_info)
        except asyncio.CancelledError:
            self.ten_env.log_debug(
                "vendor_status: stream task cancelled",
                category=LOG_CATEGORY_VENDOR,
            )
            raise
        except Exception as e:
            self.ten_env.log_error(f"Exception in Speechify TTS stream: {e}")
            if self.error_callback:
                await self.error_callback(
                    self.request_id or "",
                    ModuleError(
                        message=str(e),
                        module=ModuleType.TTS,
                        code=ModuleErrorCode.NON_FATAL_ERROR,
                        vendor_info=ModuleErrorVendorInfo(vendor=VENDOR),
                    ),
                )

    def cancel(self) -> None:
        """Cancel this synthesizer's in-flight stream, used for flush scenarios."""
        self.ten_env.log_info("Cancelling the request.")
        self._closing = True
        if self.stream_task and not self.stream_task.done():
            self.stream_task.cancel()

    async def close(self) -> None:
        self._closing = True
        if self.stream_task and not self.stream_task.done():
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
        self.response_msgs = None


class SpeechifyTTSClient:
    def __init__(
        self,
        config: SpeechifyTTSConfig,
        ten_env: AsyncTenEnv,
        error_callback: Callable[[str, ModuleError], Awaitable[None]] = None,
        response_msgs: asyncio.Queue[Tuple[bytes, bool, str, int]] = None,
    ):
        self.config = config
        self.ten_env = ten_env
        self.error_callback = error_callback
        self.response_msgs = response_msgs

        # The SDK's httpx.AsyncClient is created here (instead of letting the
        # SDK build its own) so we own its lifecycle and can close it
        # deterministically in `close()`; it is shared across every
        # synthesizer/request rather than reconnected per request, since it
        # is a plain HTTP client, not a stateful connection.
        timeout = self.config.params.get("request_timeout_seconds") or 30
        self._httpx_client = httpx.AsyncClient(timeout=timeout)
        self.sdk_client = AsyncSpeechify(
            base_url=self.config.params.get("base_url"),
            token=self.config.params.get("key"),
            headers={CALLER_HEADER: CALLER_VALUE},
            httpx_client=self._httpx_client,
        )

        # Current active synthesizer (one per in-flight request).
        self.synthesizer: SpeechifyTTSSynthesizer = self._create_synthesizer()

        # Cancelled synthesizers waiting for their stream task to finish.
        self.cancelled_synthesizers: list[SpeechifyTTSSynthesizer] = []
        self.cleanup_task = asyncio.create_task(
            self._cleanup_cancelled_synthesizers()
        )

    def _create_synthesizer(self) -> SpeechifyTTSSynthesizer:
        """Create new synthesizer instance"""
        return SpeechifyTTSSynthesizer(
            self.sdk_client,
            self.config,
            self.ten_env,
            self.error_callback,
            self.response_msgs,
        )

    async def _cleanup_cancelled_synthesizers(self) -> None:
        """Periodically clean up completed cancelled synthesizers"""
        while True:
            try:
                for synthesizer in self.cancelled_synthesizers[:]:
                    if (
                        synthesizer.stream_task is None
                        or synthesizer.stream_task.done()
                    ):
                        self.ten_env.log_info(
                            f"Cleaning up cancelled synthesizer {id(synthesizer)}"
                        )
                        self.cancelled_synthesizers.remove(synthesizer)

                await asyncio.sleep(5.0)
            except Exception as e:
                self.ten_env.log_error(f"Error in cleanup task: {e}")
                await asyncio.sleep(5.0)

    def cancel(self) -> None:
        """Cancel current synthesizer and create new synthesizer"""
        self.ten_env.log_info(
            "Cancelling current synthesizer and creating new one"
        )

        if self.response_msgs:
            while not self.response_msgs.empty():
                try:
                    self.response_msgs.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.ten_env.log_debug(
                "Response messages queue cleared during cancel"
            )

        if self.synthesizer.send_text_in_connection is False:
            self.ten_env.log_debug(
                "No text sent for this request, no need to cancel"
            )
            return

        self.cancelled_synthesizers.append(self.synthesizer)
        self.synthesizer.cancel()

        self.synthesizer = self._create_synthesizer()
        self.ten_env.log_debug("New synthesizer created successfully")

    async def send_text(self, text_data):
        """Send text"""
        await self.synthesizer.send_text(text_data)

    async def close(self):
        """Close client"""
        self.ten_env.log_debug("Closing SpeechifyTTSClient")

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        if self.synthesizer:
            await self.synthesizer.close()

        for synthesizer in self.cancelled_synthesizers:
            try:
                await synthesizer.close()
            except Exception as e:
                self.ten_env.log_error(
                    f"Error closing cancelled synthesizer: {e}"
                )
        self.cancelled_synthesizers.clear()

        await self._httpx_client.aclose()
        self.ten_env.log_debug("SpeechifyTTSClient closed")
