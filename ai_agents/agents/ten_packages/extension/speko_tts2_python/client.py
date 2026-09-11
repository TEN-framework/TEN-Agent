import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidStatus


class SpekoRouterError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        request_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.request_id = request_id

    @classmethod
    def from_event(cls, event: dict[str, Any]) -> "SpekoRouterError":
        error = event.get("error", {})
        return cls(
            str(error.get("code", "relay_error")),
            str(error.get("message", "Speko Router error")),
            retryable=bool(error.get("retryable", False)),
            request_id=str(error.get("request_id", "")),
        )


class SpekoTTSEventType(str, Enum):
    AUDIO = "audio"
    TTFB = "ttfb"
    DONE = "done"
    USAGE = "usage"


@dataclass(frozen=True)
class SpekoTTSEvent:
    type: SpekoTTSEventType
    value: bytes | int | dict[str, Any] | None = None


def websocket_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    scheme = {"https": "wss", "http": "ws"}.get(parsed.scheme, parsed.scheme)
    base_path = parsed.path.rstrip("/")
    return urlunparse((scheme, parsed.netloc, f"{base_path}{path}", "", "", ""))


class SpekoTTSClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        configure: dict[str, Any],
        ready_timeout_sec: float,
        receive_timeout_sec: float,
    ) -> None:
        self.api_key = api_key
        self.url = websocket_url(base_url, "/v1/tts/stream")
        self.configure = configure
        self.ready_timeout_sec = ready_timeout_sec
        self.receive_timeout_sec = receive_timeout_sec

        self.request_id = ""
        self.route: dict[str, Any] = {}
        self.usage: dict[str, Any] = {}
        self._ws: ClientConnection | None = None
        self._ready = False
        self._cancelled = False

    @property
    def is_ready(self) -> bool:
        return self._ready and self._ws is not None

    async def connect(self) -> None:
        if self.is_ready:
            return
        self._cancelled = False
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": uuid.uuid4().hex,
        }
        try:
            self._ws = await websockets.connect(
                self.url,
                additional_headers=headers,
                open_timeout=self.ready_timeout_sec,
                close_timeout=2.0,
            )
            await self._ws.send(
                json.dumps(self.configure, separators=(",", ":"))
            )
            raw = await asyncio.wait_for(
                self._ws.recv(), timeout=self.ready_timeout_sec
            )
            event = self._decode_event(raw)
            if event.get("type") == "error":
                raise SpekoRouterError.from_event(event)
            if event.get("type") != "session.ready":
                raise SpekoRouterError(
                    "relay_error",
                    "Expected session.ready from Speko Router",
                    retryable=True,
                )
            self.request_id = str(event.get("request_id", ""))
            self.route = dict(event.get("route", {}))
            self._ready = True
        except InvalidStatus as error:
            await self._close_socket()
            try:
                event = json.loads(error.response.body)
            except (ValueError, TypeError):
                event = {}
            if isinstance(event, dict) and isinstance(event.get("error"), dict):
                raise SpekoRouterError.from_event(event) from error
            status = error.response.status_code
            code = {
                400: "invalid_request",
                401: "authentication_failed",
                403: "authentication_failed",
                402: "insufficient_credit",
                404: "route_not_found",
                429: "rate_limited",
            }.get(status, "relay_error")
            raise SpekoRouterError(
                code,
                f"Speko Router WebSocket upgrade failed ({status})",
                retryable=status >= 500 or status == 429,
            ) from error
        except (Exception, asyncio.CancelledError):
            await self._close_socket()
            raise

    async def stream_text(self, text: str) -> AsyncIterator[SpekoTTSEvent]:
        if not self.is_ready or self._ws is None:
            raise SpekoRouterError(
                "relay_error", "Speko TTS session is not ready", retryable=True
            )

        websocket = self._ws
        await websocket.send(
            json.dumps(
                {"type": "input.append", "text": text},
                separators=(",", ":"),
            )
        )
        await websocket.send('{"type":"input.commit"}')
        sent_at = time.monotonic()
        sequence: int | None = None
        first_audio = True

        while not self._cancelled:
            try:
                raw = await asyncio.wait_for(
                    websocket.recv(), timeout=self.receive_timeout_sec
                )
            except ConnectionClosed:
                if self._cancelled:
                    return
                raise
            except asyncio.TimeoutError as error:
                raise SpekoRouterError(
                    "request_timeout",
                    "Timed out waiting for Speko TTS audio",
                    retryable=True,
                ) from error

            if self._cancelled:
                return
            if isinstance(raw, bytes):
                if sequence is None:
                    raise SpekoRouterError(
                        "relay_error",
                        "Received TTS audio before utterance.started",
                        retryable=True,
                    )
                if first_audio:
                    first_audio = False
                    yield SpekoTTSEvent(
                        SpekoTTSEventType.TTFB,
                        int((time.monotonic() - sent_at) * 1000),
                    )
                if self._cancelled:
                    return
                yield SpekoTTSEvent(SpekoTTSEventType.AUDIO, raw)
                continue

            event = self._decode_event(raw)
            event_type = event.get("type")
            if event_type == "error":
                self._ready = False
                raise SpekoRouterError.from_event(event)
            if event_type == "utterance.started":
                sequence = int(event["sequence"])
            elif event_type == "utterance.done":
                if sequence is None or int(event["sequence"]) != sequence:
                    raise SpekoRouterError(
                        "relay_error",
                        "Speko TTS utterance sequence mismatch",
                        retryable=True,
                    )
                yield SpekoTTSEvent(SpekoTTSEventType.DONE)
                return
            elif event_type == "usage.updated":
                self.usage = dict(event.get("usage", {}))
                yield SpekoTTSEvent(SpekoTTSEventType.USAGE, self.usage)
            elif event_type == "session.closed":
                self.usage = dict(event.get("usage", {}))
                self._ready = False
                raise SpekoRouterError(
                    "relay_error",
                    "Speko TTS session closed before utterance.done",
                    retryable=True,
                )

    async def cancel(self) -> None:
        self._cancelled = True
        if self._ws is not None and self._ready:
            try:
                await self._ws.send('{"type":"input.cancel"}')
            except Exception:
                pass
        await self.close(drain=False)

    async def close(self, *, drain: bool = True) -> None:
        try:
            if self._ws is not None and self._ready:
                try:
                    await self._ws.send('{"type":"session.close"}')
                except Exception:
                    pass
                if drain:
                    await self._drain_close()
        finally:
            await self._close_socket()

    async def _drain_close(self) -> None:
        websocket = self._ws
        assert websocket is not None
        try:
            while not self._cancelled:
                raw = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                if isinstance(raw, bytes):
                    continue
                event = self._decode_event(raw)
                event_type = event.get("type")
                if event_type in {"usage.updated", "session.closed"}:
                    self.usage = dict(event.get("usage", {}))
                if event_type == "error":
                    raise SpekoRouterError.from_event(event)
                if event_type == "session.closed":
                    return
        except asyncio.TimeoutError:
            return

    async def _close_socket(self) -> None:
        self._ready = False
        websocket, self._ws = self._ws, None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

    @staticmethod
    def _decode_event(raw: str | bytes) -> dict[str, Any]:
        if not isinstance(raw, str):
            raise SpekoRouterError(
                "relay_error", "Expected a JSON text frame", retryable=True
            )
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SpekoRouterError(
                "relay_error",
                "Speko Router returned invalid JSON",
                retryable=True,
            ) from error
        if not isinstance(event, dict):
            raise SpekoRouterError(
                "relay_error",
                "Speko Router event must be a JSON object",
                retryable=True,
            )
        return event
