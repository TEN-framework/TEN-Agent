from typing import Any, AsyncIterator, Tuple
from httpx import AsyncClient, Timeout, Limits

from .config import SpekoTTSConfig, NON_PAYLOAD_KEYS
from ten_runtime import AsyncTenEnv
from ten_ai_base.const import LOG_CATEGORY_VENDOR
from ten_ai_base.struct import TTS2HttpResponseEventType
from ten_ai_base.tts2_http import AsyncTTS2HttpClient


class SpekoTTSClient(AsyncTTS2HttpClient):
    """Streams synthesis through the Speko router's chunked HTTP route.

    `POST {base_url}/v1/audio/speech/stream` streams raw PCM as it is
    decoded from whichever provider the router dialed. Every response
    is signed 16-bit mono 24 kHz little-endian PCM regardless of the
    serving provider, so failover never changes the audio format.
    """

    def __init__(
        self,
        config: SpekoTTSConfig,
        ten_env: AsyncTenEnv,
    ):
        super().__init__()
        self.config = config
        self.api_key = config.params.get("api_key", "")
        self.ten_env: AsyncTenEnv = ten_env
        self._is_cancelled = False
        self._last_route: dict[str, str] = {}
        base_url = config.params.get("base_url", "https://api.speko.ai")
        self.endpoint = f"{base_url}/v1/audio/speech/stream"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }
        # Routing preferences travel as headers; empty values are
        # omitted so the API key's routing policy stays authoritative.
        routing = {
            "X-Speko-Objective": config.params.get("objective", ""),
            "X-Speko-Allow": config.params.get("allow", ""),
            "X-Speko-Deny": config.params.get("deny", ""),
            "X-Speko-Max-Price": str(config.params.get("max_price", "")),
        }
        self.headers.update({k: v for k, v in routing.items() if v})
        self.client = AsyncClient(
            timeout=Timeout(timeout=30.0),
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=600.0,
            ),
        )

    async def cancel(self):
        self.ten_env.log_debug("SpekoTTS: cancel() called.")
        self._is_cancelled = True

    def _build_payload(self, text: str) -> dict[str, Any]:
        """Request body for the streaming speech route."""
        payload: dict[str, Any] = {
            "input": text,
            "response_format": "pcm",
        }
        for key, value in self.config.params.items():
            if key in NON_PAYLOAD_KEYS:
                continue
            if value == "" or value is None:
                continue
            payload[key] = value
        return payload

    async def get(
        self, text: str, request_id: str
    ) -> AsyncIterator[Tuple[bytes | None, TTS2HttpResponseEventType]]:
        """Process a single TTS request."""
        self._is_cancelled = False
        if not self.client:
            self.ten_env.log_error(
                f"SpekoTTS: client not initialized for "
                f"request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            raise RuntimeError(
                f"SpekoTTS: client not initialized for "
                f"request_id: {request_id}."
            )

        if len(text.strip()) == 0:
            self.ten_env.log_warn(
                f"SpekoTTS: empty text for request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield None, TTS2HttpResponseEventType.END
            return

        try:
            async with self.client.stream(
                "POST",
                self.endpoint,
                headers=self.headers,
                json=self._build_payload(text),
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode(
                        "utf-8", errors="replace"
                    )
                    self.ten_env.log_error(
                        f"vendor_error: HTTP {response.status_code} "
                        f"{body} of request_id: {request_id}.",
                        category=LOG_CATEGORY_VENDOR,
                    )
                    if response.status_code in (401, 403):
                        yield body.encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.INVALID_KEY_ERROR
                    else:
                        yield body.encode(
                            "utf-8"
                        ), TTS2HttpResponseEventType.ERROR
                    return

                # Which provider/model the router dialed, for metrics.
                self._last_route = {
                    "route": response.headers.get("x-route", ""),
                    "route_reason": response.headers.get("x-route-reason", ""),
                    "failover_count": response.headers.get(
                        "x-speko-failover-count", ""
                    ),
                }

                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if self._is_cancelled:
                        self.ten_env.log_debug(
                            f"Cancellation flag detected, stopping TTS "
                            f"stream of request_id: {request_id}."
                        )
                        yield None, TTS2HttpResponseEventType.FLUSH
                        break

                    if len(chunk) > 0:
                        yield bytes(chunk), TTS2HttpResponseEventType.RESPONSE

            if not self._is_cancelled:
                self.ten_env.log_debug(
                    f"SpekoTTS: sending EVENT_TTS_END of "
                    f"request_id: {request_id}."
                )
                yield None, TTS2HttpResponseEventType.END

        except Exception as e:
            error_message = str(e)
            self.ten_env.log_error(
                f"vendor_error: {error_message} of "
                f"request_id: {request_id}.",
                category=LOG_CATEGORY_VENDOR,
            )
            yield error_message.encode("utf-8"), TTS2HttpResponseEventType.ERROR

    async def clean(self):
        self.ten_env.log_debug("SpekoTTS: clean() called.")
        await self.client.aclose()

    def get_extra_metadata(self) -> dict[str, Any]:
        """Extra metadata for TTFB metrics: the route the router chose."""
        return {
            "model": self.config.params.get("model", "auto"),
            "voice": self.config.params.get("voice", ""),
            **self._last_route,
        }
