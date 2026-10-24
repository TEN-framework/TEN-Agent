"""
OpenAI TTS Client Implementation using httpx

This implementation replaces the OpenAI SDK with httpx for better compatibility
with third-party TTS servers while maintaining full backward compatibility.
"""

from typing import Any, AsyncIterator, Tuple
import json
import ssl
import certifi
import time

# ============================================================================
# Performance Optimization: Module-level pre-import of httpx
# ============================================================================
# Background:
#   Directly use httpx to send HTTP requests, avoiding delayed import overhead.
#
# Optimization:
#   Pre-load httpx at module import time (one-time cost), avoiding delays in __init__.
# ============================================================================
import httpcore  # noqa: F401  # pylint: disable=unused-import  # Note: This import cannot be removed, otherwise it will affect http client initialization time
import httpx  # noqa: F401  # pylint: disable=unused-import
from httpx import AsyncClient, Timeout, Limits

from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient

from .config import OpenAITTSConfig


# ============================================================================
# Performance Optimization: Module-level pre-creation of SSL context
# ============================================================================
# Background:
#   Each time httpx.AsyncClient is created, it defaults to calling
#   ssl.create_default_context(), which loads and parses 149 CA certificates.
#   If environment variables configure proxies (http_proxy,
#   https_proxy, all_proxy), httpx will create independent transports for each
#   proxy, causing SSL context to be loaded 4 times.
#
# Optimization:
#   Pre-create a global SSL context at module import time,
#   then pass it to all httpx.AsyncClient instances via the verify parameter.
#   httpx will pass this SSL context to all transports (including proxy
#   transports), achieving zero-cost reuse.
#
# Performance Improvement:
#   - All transports share the same SSL context, no need to disable trust_env
#
# Notes:
#   - SSLContext is thread-safe and can be safely shared across multiple coroutines
#   - Keep trust_env=True (default) to automatically support environment variable proxy config
#   - To update certificates, restart the application or provide a reload mechanism
# ============================================================================
_GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


BYTES_PER_SAMPLE = 2
NUMBER_OF_CHANNELS = 1


class OpenAITTSClient(AsyncTTS2HttpClient):
    """
    OpenAI TTS Client using httpx.

    Features:
    - Full OpenAI TTS API compatibility
    - Support for third-party TTS servers via base_url
    - Parameter passthrough (all params except api_key and base_url)
    - Comprehensive error handling
    - Audio frame alignment
    - Cancellation support
    """

    def __init__(
        self,
        config: OpenAITTSConfig,
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
        }
        # Merge: user headers override defaults
        self.headers = {**default_headers, **self.config.headers}

        # Create httpx client with optimized SSL context
        # Performance optimization: Reuse module-level pre-created SSL context
        # All transports (including proxy transports) will use this SSL context,
        # avoiding repeated certificate loading, initialization time reduced from ~268ms to <1ms (99.6% improvement)
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
            f"OpenAITTS initialized with endpoint: {self.config.url}"
        )

    async def cancel(self):
        """Cancel the current TTS request."""
        self.ten_env.log_debug("OpenAITTS: cancel() called.")
        self._is_cancelled = True

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """
        Process a single TTS request.

        Args:
            text: Text to synthesize
            request_id: Unique request identifier for logging

        Yields:
            Tuple of (audio_bytes, event_type):
            - (bytes, RESPONSE): Audio chunk
            - (None, END): Successful completion
            - (None, FLUSH): Cancelled
            - (bytes, ERROR): Error message
            - (bytes, INVALID_KEY_ERROR): Authentication error
        """
        self._is_cancelled = False

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"OpenAITTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            # Build request payload - pass through all params (except api_key and base_url)
            payload = {**self.config.params}
            payload.pop("api_key", None)  # Remove api_key from headers
            payload.pop("base_url", None)  # Remove base_url from payload

            # Set input to the text to be synthesized
            payload["input"] = text

            self.ten_env.log_debug(
                f"OpenAITTS: sending request for request_id: {request_id}"
            )

            # Send streaming request
            async with self.client.stream(
                "POST", self.config.url, headers=self.headers, json=payload
            ) as response:
                # Check cancellation flag
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
                        error_info = error_data.get("error", {})
                        error_msg = error_info.get("message", str(error_data))
                        error_code = error_info.get("code")
                    except Exception:
                        error_msg = error_body.decode("utf-8", errors="replace")
                        error_code = None

                    self.ten_env.log_error(
                        f"vendor_error: HTTP {response.status_code}: {error_msg} for request_id: {request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )

                    # Classify by status code and error code
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

                # Stream audio data
                cache_audio_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        self.record_audio_received()
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"Cancellation detected, flushing TTS stream for request_id: {request_id}"
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        break

                    self.ten_env.log_debug(
                        f"OpenAITTS: received chunk, length: {len(chunk)} for request_id: {request_id}"
                    )

                    # Process audio alignment (ensure it's a complete audio frame)
                    # This is important for PCM format, ensure each chunk is a complete sample point
                    if len(cache_audio_bytes) > 0:
                        chunk = cache_audio_bytes + chunk
                        cache_audio_bytes = bytearray()

                    left_size = len(chunk) % (
                        BYTES_PER_SAMPLE * NUMBER_OF_CHANNELS
                    )

                    if left_size > 0:
                        cache_audio_bytes = chunk[-left_size:]
                        chunk = chunk[:-left_size]

                    if len(chunk) > 0:
                        yield bytes(chunk), TTS2HttpResponseEventType.RESPONSE

                # Send END event
                if not self._is_cancelled:
                    self.ten_env.log_debug(
                        f"OpenAITTS: sending END event for request_id: {request_id}"
                    )
                    yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} for request_id: {request_id}",
                category=LOG_CATEGORY_VENDOR,
            )

            # Check if it's an authentication error
            if (
                "401" in error_message
                or "403" in error_message
                or "invalid_api_key" in error_message
            ):
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
            else:
                # All other errors are treated as general errors (NON_FATAL_ERROR)
                # Including network connection errors (ConnectionRefusedError, TimeoutError, etc.)
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        """Clean up resources."""
        self.ten_env.log_debug("OpenAITTS: clean() called.")
        try:
            if self.client:
                await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "model": self.config.params.get("model", ""),
            "voice": self.config.params.get("voice", ""),
        }
