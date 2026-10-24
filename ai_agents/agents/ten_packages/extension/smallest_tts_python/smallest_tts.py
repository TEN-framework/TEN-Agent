"""
Smallest AI (Lightning) TTS Client Implementation using httpx.

Talks to the Lightning streaming endpoint
(`POST {base_url}/waves/v1/tts/live`) which returns Server-Sent Events:
each `data:` line carries `{"audio": "<base64-pcm16>"}` and the final frame
carries `{"done": true}`. Audio is decoded to raw signed 16-bit LE mono PCM
— exactly what the TEN `pcm_frame` contract expects, so no sample-format
conversion is needed.
"""

from typing import Any, AsyncIterator, Tuple
import base64
import json
import ssl
import time

import certifi

# ============================================================================
# Performance Optimization: Module-level pre-import of httpx
# ============================================================================
import httpcore  # noqa: F401  # pylint: disable=unused-import  # Note: This import cannot be removed, otherwise it will affect http client initialization time
import httpx  # noqa: F401  # pylint: disable=unused-import
from httpx import AsyncClient, Timeout, Limits

from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient

from .config import SmallestTTSConfig


# ============================================================================
# Performance Optimization: Module-level pre-creation of SSL context
# ============================================================================
# Pre-create a global SSL context at module import time so every
# httpx.AsyncClient reuses it instead of re-loading CA certificates.
_GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Source attribution sent to the Smallest AI API on every request.
SOURCE_NAME = "ten-framework"


class SSEDecoder:
    """Incremental Server-Sent-Events decoder.

    Feeds arbitrary byte chunks in, yields the JSON payload of each complete
    `data:` line out. A partial line at the end of a chunk is held back until
    the rest of it arrives, so an event is never split across feeds.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, chunk: bytes) -> list[dict]:
        """Feed raw bytes; return the decoded `data:` payloads now complete."""
        if not chunk:
            return []

        self._buffer += chunk.decode("utf-8", errors="replace")
        lines = self._buffer.split("\n")
        # Last element is either "" (chunk ended on a newline) or a partial
        # line — keep it buffered either way.
        self._buffer = lines.pop()

        events: list[dict] = []
        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload:
                continue
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
        return events


class SmallestTTSClient(AsyncTTS2HttpClient):
    """
    Smallest AI (Lightning) TTS Client using httpx.

    Features:
    - SSE streaming from `/waves/v1/tts/live` (~100 ms to first audio chunk)
    - Parameter passthrough (all params except api_key and base_url)
    - Raw PCM16 mono output (no conversion needed)
    - Comprehensive error handling and cancellation support
    """

    def __init__(
        self,
        config: SmallestTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False

        # Build headers - merge user-provided headers with defaults
        api_key = self.config.params.get("api_key", "")
        default_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Source": SOURCE_NAME,
        }
        # Merge: user headers override defaults
        self.headers = {**default_headers, **self.config.headers}

        # Create httpx client reusing the module-level SSL context.
        _start_time = time.time()
        self.client = AsyncClient(
            timeout=Timeout(timeout=60.0),  # TTS may take longer
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=600.0,
            ),
            http2=True,
            verify=_GLOBAL_SSL_CONTEXT,
        )
        self.observe_http_ttfb(self.client)
        _elapsed_ms = (time.time() - _start_time) * 1000
        ten_env.log_debug(f"http client initialized in {_elapsed_ms:.2f}ms")

        ten_env.log_info(
            f"SmallestTTS initialized with endpoint: {self.config.url}"
        )

    async def cancel(self):
        """Cancel the current TTS request."""
        self.ten_env.log_debug("SmallestTTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """
        Process a single TTS request.

        Yields:
            Tuple of (audio_bytes, event_type):
            - (bytes, RESPONSE): PCM16 mono audio chunk
            - (None, END): Successful completion
            - (None, FLUSH): Cancelled
            - (bytes, ERROR): Error message
            - (bytes, INVALID_KEY_ERROR): Authentication error
        """
        self._is_cancelled = False

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"SmallestTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Build request payload - pass through all params
            # (except api_key and base_url)
            payload = {**self.config.params}
            payload.pop("api_key", None)  # api_key is sent via the header
            payload.pop("base_url", None)  # base_url was folded into the url

            # Set text to be synthesized
            payload["text"] = text

            self.ten_env.log_debug(
                f"SmallestTTS: sending request for request_id: {request_id}"
            )

            decoder = SSEDecoder()

            # Send streaming request
            async with self.client.stream(
                "POST", self.config.url, headers=self.headers, json=payload
            ) as response:
                if self._is_cancelled:
                    self.ten_env.log_debug(
                        f"Cancellation detected before processing response for request_id: {request_id}"
                    )
                    yield None, TTS2HttpResponseEventType.FLUSH
                    return

                # Handle non-200 status code
                if response.status_code != 200:
                    error_body = await response.aread()
                    try:
                        error_data = json.loads(error_body)
                        error_info = error_data.get("error", error_data)
                        if isinstance(error_info, dict):
                            error_msg = error_info.get(
                                "message", str(error_data)
                            )
                            error_code = error_info.get("code")
                        else:
                            error_msg = str(error_info)
                            error_code = None
                    except Exception:
                        error_msg = error_body.decode("utf-8", errors="replace")
                        error_code = None

                    self.ten_env.log_error(
                        f"vendor_error: HTTP {response.status_code}: {error_msg} for request_id: {request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )

                    if (
                        response.status_code in (401, 403)
                        or error_code == "invalid_api_key"
                    ):
                        yield error_msg.encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                    else:
                        yield error_msg.encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.ERROR
                    return

                # Stream SSE events, decoding base64 PCM16 audio chunks.
                done = False
                async for chunk in response.aiter_bytes():
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"Cancellation detected, flushing TTS stream for request_id: {request_id}"
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        break

                    for event in decoder.feed(chunk):
                        audio_b64 = event.get("audio") or event.get(
                            "data", {}
                        ).get("audio")
                        if audio_b64:
                            try:
                                pcm = base64.b64decode(audio_b64)
                            except (ValueError, TypeError):
                                self.ten_env.log_warn(
                                    f"SmallestTTS: invalid base64 audio chunk for request_id: {request_id}",
                                    category=LOG_CATEGORY_VENDOR,
                                )
                                continue
                            if pcm:
                                self.record_audio_received()
                                yield pcm, TTS2HttpResponseEventType.RESPONSE
                        if event.get("done") or event.get("status") in (
                            "complete",
                            "done",
                        ):
                            done = True
                    if done:
                        break

                # Send END event
                if not self._is_cancelled:
                    self.ten_env.log_debug(
                        f"SmallestTTS: sending END event for request_id: {request_id}"
                    )
                    yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} for request_id: {request_id}",
                category=LOG_CATEGORY_VENDOR,
            )

            # Auth failures surface as HTTP 401/403 and are classified in
            # the status-code branch above; exceptions reaching here are
            # transport-level (connection refused, timeout, ...), so they
            # are never key errors.
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        """Clean up resources."""
        self.ten_env.log_debug("SmallestTTS: clean() called.")
        try:
            if self.client:
                await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "model": self.config.params.get("model", ""),
            "voice": self.config.params.get("voice_id", ""),
        }
