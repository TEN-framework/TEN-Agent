import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx


class SpekoRouterError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        request_id: str = "",
        status_code: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.request_id = request_id
        self.status_code = status_code

    @classmethod
    def from_envelope(
        cls, envelope: dict[str, Any], *, status_code: int = 0
    ) -> "SpekoRouterError":
        error = envelope.get("error", {})
        return cls(
            str(error.get("code", "relay_error")),
            str(error.get("message", "Speko Router error")),
            retryable=bool(error.get("retryable", False)),
            request_id=str(error.get("request_id", "")),
            status_code=status_code,
        )


@dataclass(frozen=True)
class SSEEvent:
    name: str
    data: dict[str, Any]


async def iter_sse(lines: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    event_name = "message"
    data_lines: list[str] = []
    async for line in lines:
        if line == "":
            if data_lines:
                yield SSEEvent(
                    event_name,
                    _decode_json("\n".join(data_lines)),
                )
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)

    if data_lines:
        yield SSEEvent(event_name, _decode_json("\n".join(data_lines)))


def _decode_json(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise SpekoRouterError(
            "relay_error", "Speko Router returned invalid SSE JSON"
        ) from error
    if not isinstance(decoded, dict):
        raise SpekoRouterError(
            "relay_error", "Speko Router SSE data must be a JSON object"
        )
    return decoded


class SpekoLLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_sec: float,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = f"{base_url.rstrip('/')}/v1/llm/responses"
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_sec)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
        }
        self.route: dict[str, Any] = {}

    async def stream(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> AsyncIterator[SSEEvent]:
        headers = {**self._headers, "Idempotency-Key": idempotency_key}
        terminal = False
        try:
            async with self._client.stream(
                "POST", self.url, headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    raise await self._error_from_response(response)
                self.route = {
                    "provider": response.headers.get("Speko-Provider", ""),
                    "model": response.headers.get("Speko-Model", ""),
                    "region": response.headers.get("Speko-Region", ""),
                    "attempt_id": response.headers.get("Speko-Attempt-ID", ""),
                }
                async for event in iter_sse(response.aiter_lines()):
                    if event.name == "error":
                        raise SpekoRouterError.from_envelope(event.data)
                    yield event
                    if event.name == "response.completed":
                        terminal = True
                        break
        except httpx.TimeoutException as error:
            raise SpekoRouterError(
                "request_timeout",
                "Timed out waiting for Speko Router",
                retryable=True,
            ) from error
        except httpx.HTTPError as error:
            raise SpekoRouterError(
                "relay_error", str(error), retryable=True
            ) from error
        if not terminal:
            raise SpekoRouterError(
                "relay_error",
                "Speko Router LLM stream ended without a terminal event",
                retryable=True,
            )

    async def complete(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        headers = {
            **self._headers,
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        try:
            response = await self._client.post(
                self.url, headers=headers, json=payload
            )
        except httpx.TimeoutException as error:
            raise SpekoRouterError(
                "request_timeout",
                "Timed out waiting for Speko Router",
                retryable=True,
            ) from error
        except httpx.HTTPError as error:
            raise SpekoRouterError(
                "relay_error", str(error), retryable=True
            ) from error
        if response.status_code >= 400:
            raise await self._error_from_response(response)
        decoded = response.json()
        if not isinstance(decoded, dict):
            raise SpekoRouterError(
                "relay_error", "Speko Router response must be a JSON object"
            )
        return decoded

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    async def _error_from_response(
        response: httpx.Response,
    ) -> SpekoRouterError:
        try:
            await response.aread()
            envelope = response.json()
        except (json.JSONDecodeError, ValueError, httpx.ResponseNotRead):
            return SpekoRouterError(
                "relay_error",
                f"Speko Router HTTP error ({response.status_code})",
                retryable=response.status_code >= 500,
                status_code=response.status_code,
            )
        if not isinstance(envelope, dict):
            envelope = {}
        return SpekoRouterError.from_envelope(
            envelope, status_code=response.status_code
        )
