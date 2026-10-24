"""
Mistral (Voxtral) TTS Client Implementation using httpx.

Mistral exposes an OpenAI-compatible Text-to-Speech endpoint
(`POST {base_url}/audio/speech`, default base_url `https://api.mistral.ai/v1`).
We talk to it with httpx directly (no vendor SDK) so we can stream the audio.

Audio format: we request `response_format="pcm"`, which Voxtral emits as a
headerless stream of raw float32 LE samples at 24 kHz mono. That is NOT the
PCM16 the TEN `pcm_frame` contract expects, so the client rescales each float32
sample to signed 16-bit on the fly (see Float32ToPcm16). Requesting raw `pcm`
(rather than a container like `wav`) keeps time-to-first-audio low — there is no
header to buffer before the first samples arrive.
"""

from collections.abc import Mapping
from typing import Any, AsyncIterator, Tuple
import base64
import json
import ssl
import struct
import certifi
import time

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

from .config import MistralTTSConfig


# ============================================================================
# Performance Optimization: Module-level pre-creation of SSL context
# ============================================================================
# Pre-create a global SSL context at module import time so every
# httpx.AsyncClient reuses it instead of re-loading CA certificates.
_GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


PCM16_MAX = 32767
_FLOAT32_BYTES = 4  # one 32-bit IEEE-float sample


class Float32ToPcm16:
    """Streaming converter: raw float32 LE bytes in, PCM16 LE bytes out.

    Mistral's `response_format="pcm"` is a headerless stream of 32-bit
    little-endian IEEE-float samples (24 kHz mono). We rescale each sample from
    [-1, 1] to signed 16-bit, holding back a trailing partial sample
    (< 4 bytes) between feeds so a float is never split across chunk boundaries.
    """

    def __init__(self) -> None:
        self._remainder = bytearray()  # leftover bytes < one float32 sample

    def feed(self, chunk: bytes) -> bytes:
        """Feed a chunk of the float32 stream; return PCM16 bytes available."""
        if not chunk:
            return b""

        data = bytes(self._remainder) + chunk
        self._remainder = bytearray()

        count = len(data) // _FLOAT32_BYTES
        usable = count * _FLOAT32_BYTES
        if usable < len(data):
            self._remainder = bytearray(data[usable:])
            data = data[:usable]
        if not data:
            return b""

        floats = struct.unpack(f"<{count}f", data)
        # Clamp to [-1, 1] before scaling; map NaN (`f != f`) to silence so a
        # corrupt sample can't crash the stream. ±inf clamps cleanly.
        ints = [
            0 if f != f else int(max(-1.0, min(1.0, f)) * PCM16_MAX)
            for f in floats
        ]
        return struct.pack(f"<{count}h", *ints)


class MistralTTSClient(AsyncTTS2HttpClient):
    """
    Mistral (Voxtral) TTS Client using httpx.

    Features:
    - OpenAI-compatible `/v1/audio/speech` request shape
    - Parameter passthrough (all params except api_key and base_url)
    - Base64 decoding of Mistral JSON/SSE audio payloads
    - float32 PCM -> PCM16 mono conversion (Voxtral's `pcm` format)
    - Comprehensive error handling and cancellation support
    """

    def __init__(
        self,
        config: MistralTTSConfig,
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
            f"MistralTTS initialized with endpoint: {self.config.url}"
        )

    async def cancel(self):
        """Cancel the current TTS request."""
        self.ten_env.log_debug("MistralTTS: cancel() called.")
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
                f"MistralTTS: empty text for request_id: {request_id}.",
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

            # Set input to the text to be synthesized
            payload["input"] = text

            self.ten_env.log_debug(
                f"MistralTTS: sending request for request_id: {request_id}"
            )

            converter = Float32ToPcm16()

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

                    # Validation responses can contain a structured `detail`
                    # value instead of a string message.  Normalize it before
                    # logging and encoding so the original vendor error is not
                    # hidden by an AttributeError.
                    if not isinstance(error_msg, str):
                        error_msg = json.dumps(error_msg, ensure_ascii=False)

                    self.ten_env.log_error(
                        f"vendor_error: HTTP {response.status_code}: {error_msg} for request_id: {request_id}",
                        category=LOG_CATEGORY_VENDOR,
                    )

                    # 401/403 -> auth/permission (Mistral also returns 403 when
                    # the input is rejected by content moderation).
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

                content_type = ""
                if isinstance(response.headers, Mapping):
                    content_type = response.headers.get(
                        "content-type", ""
                    ).lower()

                if "text/event-stream" in content_type:
                    # Mistral SSE events carry base64-encoded float32 PCM in
                    # `data: {"type":"speech.audio.delta", "audio_data":...}`.
                    async for line in response.aiter_lines():
                        if self._is_cancelled:
                            self.ten_env.log_debug(
                                f"Cancellation detected, flushing TTS stream for request_id: {request_id}"
                            )
                            yield None, TTS2HttpResponseEventType.FLUSH
                            break

                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        event_data = line.removeprefix("data:").strip()
                        if not event_data or event_data == "[DONE]":
                            continue

                        event = json.loads(event_data)
                        # Accept both the wire event and the OpenAPI envelope.
                        data = event.get("data", event)
                        if data.get("type") == "speech.audio.done":
                            break
                        audio_data = data.get("audio_data")
                        if not audio_data:
                            continue

                        self.record_audio_received()
                        pcm = converter.feed(
                            base64.b64decode(audio_data, validate=True)
                        )
                        if pcm:
                            yield pcm, TTS2HttpResponseEventType.RESPONSE
                elif "application/json" in content_type:
                    # Compatibility path for proxies that ignore stream=true.
                    body = json.loads(await response.aread())
                    audio_data = body.get("audio_data")
                    if not audio_data:
                        raise ValueError(
                            "Mistral response did not contain audio_data"
                        )
                    pcm = converter.feed(
                        base64.b64decode(audio_data, validate=True)
                    )
                    if pcm:
                        yield pcm, TTS2HttpResponseEventType.RESPONSE
                else:
                    # Some OpenAI-compatible proxies return raw PCM bytes.
                    async for chunk in response.aiter_bytes():
                        if self._is_cancelled:
                            self.ten_env.log_debug(
                                f"Cancellation detected, flushing TTS stream for request_id: {request_id}"
                            )
                            yield None, TTS2HttpResponseEventType.FLUSH
                            break

                        pcm = converter.feed(chunk)
                        if pcm:
                            yield pcm, TTS2HttpResponseEventType.RESPONSE

                # Send END event
                if not self._is_cancelled:
                    self.ten_env.log_debug(
                        f"MistralTTS: sending END event for request_id: {request_id}"
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
                # All other errors are treated as general errors
                # (including network errors: ConnectionRefusedError, TimeoutError, etc.)
                yield error_message.encode(
                    "utf-8"
                ), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        """Clean up resources."""
        self.ten_env.log_debug("MistralTTS: clean() called.")
        try:
            if self.client:
                await self.client.aclose()
        finally:
            pass

    def get_extra_metadata(self) -> dict[str, Any]:
        """Return extra metadata for TTFB metrics."""
        return {
            "model": self.config.params.get("model", ""),
            "voice": self.config.params.get(
                "voice_id", self.config.params.get("voice", "")
            ),
        }
